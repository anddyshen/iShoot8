# data_manager.py
import requests
from datetime import datetime
from flask import current_app
from models import db, SSQDraw, DLTDraw
from config import SSQ_URL, DLT_URL, USER_AGENT

# 版本号，每次生成文件时更新
__version__ = "1.0.1"

def fetch_raw_data(url, app): # <--- 添加 app 参数
    """从指定URL获取原始文本数据"""
    headers = {'User-agent': USER_AGENT}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status() # 检查HTTP错误
        return response.text
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Error fetching data from {url}: {e}") # <--- 使用 app.logger
        return None

def parse_ssq_data(raw_data, app): # <--- 添加 app 参数
    """解析双色球原始数据"""
    draws = []
    if not raw_data:
        return draws
    lines = raw_data.strip().split('\n')
    for line in lines:
        parts = line.split()
        if len(parts) < 18:
            app.logger.warning(f"Skipping malformed SSQ line: {line}") # <--- 使用 app.logger
            continue
        try:
            # ... (代码不变)
            pass
        except (ValueError, IndexError) as e:
            app.logger.error(f"Error parsing SSQ line '{line}': {e}") # <--- 使用 app.logger
    return draws

def parse_dlt_data(raw_data, app): # <--- 添加 app 参数
    """解析大乐透原始数据"""
    draws = []
    if not raw_data:
        return draws
    lines = raw_data.strip().split('\n')
    for line in lines:
        parts = line.split()
        if len(parts) < 30:
            app.logger.warning(f"Skipping malformed DLT line: {line}") # <--- 使用 app.logger
            continue
        try:
            # ... (代码不变)
            pass
        except (ValueError, IndexError) as e:
            app.logger.error(f"Error parsing DLT line '{line}': {e}") # <--- 使用 app.logger
    return draws

def save_draw_data(draw_objects, lottery_type):
    """将解析后的开奖数据保存到数据库"""
    new_entries_count = 0
    for draw in draw_objects:
        existing_draw = None
        if lottery_type == 'ssq':
            existing_draw = SSQDraw.query.filter_by(issue=draw.issue).first()
        elif lottery_type == 'dlt':
            existing_draw = DLTDraw.query.filter_by(issue=draw.issue).first()

        if not existing_draw:
            db.session.add(draw)
            new_entries_count += 1
    db.session.commit()
    return new_entries_count

def update_latest_draws(app): # <--- 修改这里，接收 app 参数
    """手动或定时更新最新开奖信息"""
    with app.app_context(): # <--- 修改这里，使用 app.app_context()
        app.logger.info("Starting data update...") # <--- 使用 app.logger

        # 更新双色球
        ssq_raw = fetch_raw_data(SSQ_URL, app) # <--- 传递 app
        ssq_draws = parse_ssq_data(ssq_raw, app) # <--- 传递 app
        new_ssq_count = save_draw_data(ssq_draws, 'ssq')
        app.logger.info(f"SSQ data updated. Added {new_ssq_count} new entries.") # <--- 使用 app.logger

        # 更新大乐透
        dlt_raw = fetch_raw_data(DLT_URL, app) # <--- 传递 app
        dlt_draws = parse_dlt_data(dlt_raw, app) # <--- 传递 app
        new_dlt_count = save_draw_data(dlt_draws, 'dlt')
        app.logger.info(f"DLT data updated. Added {new_dlt_count} new entries.") # <--- 使用 app.logger

        return new_ssq_count, new_dlt_count

def get_latest_draws(model, count=1):
    """获取最新N期开奖数据"""
    return model.query.order_by(model.issue.desc()).limit(count).all()

def get_draw_by_issue(model, issue):
    """根据期号获取开奖数据"""
    return model.query.filter_by(issue=issue).first()

def add_manual_draw(lottery_type, data_string):
    """手动添加一期开奖数据"""
    if lottery_type == 'ssq':
        # 假设 data_string 是 '2025105 2025-09-11 04 07 18 24 26 28 08 ...'
        draw_objects = parse_ssq_data(data_string + '\n') # 模拟文件内容
        if draw_objects:
            return save_draw_data(draw_objects, 'ssq')
    elif lottery_type == 'dlt':
        draw_objects = parse_dlt_data(data_string + '\n')
        if draw_objects:
            return save_draw_data(draw_objects, 'dlt')
    return 0

# 格式校验函数 (用于手动输入)
def validate_ssq_format(data_string):
    parts = data_string.split()
    if len(parts) < 29: # 至少包含到第六等奖金额
        return False, "双色球数据格式不完整，至少需要29个字段。"
    try:
        datetime.strptime(parts[1], '%Y-%m-%d') # 日期
        [int(p) for p in parts[2:9]] # 红蓝球
        [int(p) for p in parts[9:15]] # 红球出球顺序
        int(parts[15]) # 销售额
        # ... 更多详细校验
        return True, ""
    except (ValueError, IndexError):
        return False, "双色球数据格式错误，请检查数字和日期格式。"

def validate_dlt_format(data_string):
    parts = data_string.split()
    if len(parts) < 40: # 至少包含到追加二等奖金额
        return False, "大乐透数据格式不完整，至少需要40个字段。"
    try:
        datetime.strptime(parts[1], '%Y-%m-%d') # 日期
        [int(p) for p in parts[2:9]] # 红蓝球
        [int(p) for p in parts[9:16]] # 红蓝球出球顺序
        int(parts[16]) # 销售额
        # ... 更多详细校验
        return True, ""
    except (ValueError, IndexError):
        return False, "大乐透数据格式错误，请检查数字和日期格式。"
