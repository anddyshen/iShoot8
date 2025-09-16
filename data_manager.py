# data_manager.py
import requests
from datetime import datetime
from flask import current_app
from models import db, SSQDraw, DLTDraw
from config import SSQ_URL, DLT_URL, USER_AGENT

# 版本号，每次生成文件时更新
__version__ = "1.0.0"

def fetch_raw_data(url):
    """从指定URL获取原始文本数据"""
    headers = {'User-agent': USER_AGENT}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status() # 检查HTTP错误
        return response.text
    except requests.exceptions.RequestException as e:
        current_app.logger.error(f"Error fetching data from {url}: {e}")
        return None

def parse_ssq_data(raw_data):
    """解析双色球原始数据"""
    draws = []
    if not raw_data:
        return draws
    lines = raw_data.strip().split('\n')
    for line in lines:
        parts = line.split()
        if len(parts) < 18: # 根据实际数据格式调整长度
            current_app.logger.warning(f"Skipping malformed SSQ line: {line}")
            continue
        try:
            issue = parts[0]
            draw_date = datetime.strptime(parts[1], '%Y-%m-%d').date()
            red_balls = ','.join(sorted([str(int(p)) for p in parts[2:8]])) # 确保两位数格式
            blue_balls = str(int(parts[8]))
            red_order = ','.join([str(int(p)) for p in parts[9:15]])
            sales_amount = int(parts[15])
            prize_pool = int(parts[16])
            first_prize_count = int(parts[17])
            first_prize_amount = int(parts[18])
            second_prize_count = int(parts[19])
            second_prize_amount = int(parts[20])
            third_prize_count = int(parts[21])
            third_prize_amount = int(parts[22])
            fourth_prize_count = int(parts[23])
            fourth_prize_amount = int(parts[24])
            fifth_prize_count = int(parts[25])
            fifth_prize_amount = int(parts[26])
            sixth_prize_count = int(parts[27])
            sixth_prize_amount = int(parts[28])

            draws.append(SSQDraw(
                issue=issue, draw_date=draw_date,
                red_balls=red_balls, blue_balls=blue_balls,
                red_order=red_order,
                sales_amount=sales_amount, prize_pool=prize_pool,
                first_prize_count=first_prize_count, first_prize_amount=first_prize_amount,
                second_prize_count=second_prize_count, second_prize_amount=second_prize_amount,
                third_prize_count=third_prize_count, third_prize_amount=third_prize_amount,
                fourth_prize_count=fourth_prize_count, fourth_prize_amount=fourth_prize_amount,
                fifth_prize_count=fifth_prize_count, fifth_prize_amount=fifth_prize_amount,
                sixth_prize_count=sixth_prize_count, sixth_prize_amount=sixth_prize_amount
            ))
        except (ValueError, IndexError) as e:
            current_app.logger.error(f"Error parsing SSQ line '{line}': {e}")
    return draws

def parse_dlt_data(raw_data):
    """解析大乐透原始数据"""
    draws = []
    if not raw_data:
        return draws
    lines = raw_data.strip().split('\n')
    for line in lines:
        parts = line.split()
        if len(parts) < 30: # 根据实际数据格式调整长度
            current_app.logger.warning(f"Skipping malformed DLT line: {line}")
            continue
        try:
            issue = parts[0]
            draw_date = datetime.strptime(parts[1], '%Y-%m-%d').date()
            red_balls = ','.join(sorted([str(int(p)) for p in parts[2:7]]))
            blue_balls = ','.join(sorted([str(int(p)) for p in parts[7:9]]))
            red_order = ','.join([str(int(p)) for p in parts[9:14]])
            blue_order = ','.join([str(int(p)) for p in parts[14:16]])
            sales_amount = int(parts[16])
            prize_pool = int(parts[17])
            first_prize_count = int(parts[18])
            first_prize_amount = int(parts[19])
            second_prize_count = int(parts[20])
            second_prize_amount = int(parts[21])
            third_prize_count = int(parts[22])
            third_prize_amount = int(parts[23])
            fourth_prize_count = int(parts[24])
            fourth_prize_amount = int(parts[25])
            fifth_prize_count = int(parts[26])
            fifth_prize_amount = int(parts[27])
            sixth_prize_count = int(parts[28])
            sixth_prize_amount = int(parts[29])
            seventh_prize_count = int(parts[30])
            seventh_prize_amount = int(parts[31])
            eighth_prize_count = int(parts[32])
            eighth_prize_amount = int(parts[33])
            ninth_prize_count = int(parts[34])
            ninth_prize_amount = int(parts[35])
            additional_first_prize_count = int(parts[36])
            additional_first_prize_amount = int(parts[37])
            additional_second_prize_count = int(parts[38])
            additional_second_prize_amount = int(parts[39])
            reserve1 = parts[40] if len(parts) > 40 else None
            reserve2 = parts[41] if len(parts) > 41 else None
            reserve3 = parts[42] if len(parts) > 42 else None
            reserve4 = parts[43] if len(parts) > 43 else None
            reserve5 = parts[44] if len(parts) > 44 else None

            draws.append(DLTDraw(
                issue=issue, draw_date=draw_date,
                red_balls=red_balls, blue_balls=blue_balls,
                red_order=red_order, blue_order=blue_order,
                sales_amount=sales_amount, prize_pool=prize_pool,
                first_prize_count=first_prize_count, first_prize_amount=first_prize_amount,
                second_prize_count=second_prize_count, second_prize_amount=second_prize_amount,
                third_prize_count=third_prize_count, third_prize_amount=third_prize_amount,
                fourth_prize_count=fourth_prize_count, fourth_prize_amount=fourth_prize_amount,
                fifth_prize_count=fifth_prize_count, fifth_prize_amount=fifth_prize_amount,
                sixth_prize_count=sixth_prize_count, sixth_prize_amount=sixth_prize_amount,
                seventh_prize_count=seventh_prize_count, seventh_prize_amount=seventh_prize_amount,
                eighth_prize_count=eighth_prize_count, eighth_prize_amount=eighth_prize_amount,
                ninth_prize_count=ninth_prize_count, ninth_prize_amount=ninth_prize_amount,
                additional_first_prize_count=additional_first_prize_count, additional_first_prize_amount=additional_first_prize_amount,
                additional_second_prize_count=additional_second_prize_count, additional_second_prize_amount=additional_second_prize_amount,
                reserve1=reserve1, reserve2=reserve2, reserve3=reserve3, reserve4=reserve4, reserve5=reserve5
            ))
        except (ValueError, IndexError) as e:
            current_app.logger.error(f"Error parsing DLT line '{line}': {e}")
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

def update_latest_draws():
    """手动或定时更新最新开奖信息"""
    with current_app.app_context():
        current_app.logger.info("Starting data update...")

        # 更新双色球
        ssq_raw = fetch_raw_data(SSQ_URL)
        ssq_draws = parse_ssq_data(ssq_raw)
        new_ssq_count = save_draw_data(ssq_draws, 'ssq')
        current_app.logger.info(f"SSQ data updated. Added {new_ssq_count} new entries.")

        # 更新大乐透
        dlt_raw = fetch_raw_data(DLT_URL)
        dlt_draws = parse_dlt_data(dlt_raw)
        new_dlt_count = save_draw_data(dlt_draws, 'dlt')
        current_app.logger.info(f"DLT data updated. Added {new_dlt_count} new entries.")

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
