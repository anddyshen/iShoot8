# data_manager.py
import requests
from datetime import datetime, date
from flask import current_app
from models import db, SSQDraw, DLTDraw, KL8Draw, SevenXCDraw, SevenLCDraw
from config import SSQ_URL, DLT_URL, KL8_URL, SEVEN_XC_URL, SEVEN_LC_URL, USER_AGENT
from utils import calculate_all_trend_data, update_fuyun_prize_status # 导入趋势计算函数和福运奖状态更新函数

# 版本号，每次生成文件时更新
__version__ = "1.0.1" # 更新版本号

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

            # 福运奖仅在2026年2月1日（含）之后生效
            FUYUN_START_DATE = date(2026, 2, 1)
            if draw_date < FUYUN_START_DATE:
                # 2026年2月1日之前，福运奖强制关闭
                current_fuyun_active = False
            else:
                # 2026年2月1日之后，根据奖池金额计算福运奖状态
                # 使用draws列表中前一条记录的福运奖状态作为当前状态，实现正确的滞后性递推
                if draws:
                    prev_fuyun_active = draws[-1].fuyun_prize_active if hasattr(draws[-1], 'fuyun_prize_active') else False
                else:
                    prev_fuyun_active = False
                current_fuyun_active = update_fuyun_prize_status(prize_pool, prev_fuyun_active)

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
                sixth_prize_count=sixth_prize_count, sixth_prize_amount=sixth_prize_amount,
                fuyun_prize_active=current_fuyun_active
            ))
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
        if len(parts) < 36:
            app.logger.warning(f"Skipping malformed DLT line: {line}") # <--- 使用 app.logger
            continue
        try:
            issue = parts[0]
            draw_date = datetime.strptime(parts[1], '%Y-%m-%d').date()
            red_balls = ','.join(sorted([str(int(p)) for p in parts[2:7]]))
            blue_balls = ','.join(sorted([str(int(p)) for p in parts[7:9]]))
            # 出球顺序字段可能为 '-'（无实际出球顺序数据），需要特殊处理
            try:
                red_order = ','.join([str(int(p)) for p in parts[9:14]])
            except ValueError:
                red_order = ','.join(parts[9:14])  # 保留原始值（可能包含 '-'）
            try:
                blue_order = ','.join([str(int(p)) for p in parts[14:16]])
            except ValueError:
                blue_order = ','.join(parts[14:16])  # 保留原始值（可能包含 '-'）
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
            additional_first_prize_count = int(parts[32])
            additional_first_prize_amount = int(parts[33])
            additional_second_prize_count = int(parts[34])
            additional_second_prize_amount = int(parts[35])
            reserve1 = parts[36] if len(parts) > 36 else None
            reserve2 = parts[37] if len(parts) > 37 else None
            reserve3 = parts[38] if len(parts) > 38 else None
            reserve4 = parts[39] if len(parts) > 39 else None
            reserve5 = parts[40] if len(parts) > 40 else None

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
                additional_first_prize_count=additional_first_prize_count, additional_first_prize_amount=additional_first_prize_amount,
                additional_second_prize_count=additional_second_prize_count, additional_second_prize_amount=additional_second_prize_amount,
                reserve1=reserve1, reserve2=reserve2, reserve3=reserve3, reserve4=reserve4, reserve5=reserve5
            ))
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
        elif lottery_type == 'kl8':
            existing_draw = KL8Draw.query.filter_by(issue=draw.issue).first()
        elif lottery_type == '7xc':
            existing_draw = SevenXCDraw.query.filter_by(issue=draw.issue).first()
        elif lottery_type == '7lc':
            existing_draw = SevenLCDraw.query.filter_by(issue=draw.issue).first()

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

        # 数据更新完成后，触发趋势数据预计算
        ssq_trend_count = 0
        dlt_trend_count = 0
        ssq_smart_count = 0
        dlt_smart_count = 0
        if new_ssq_count > 0:
            app.logger.info("触发双色球趋势数据预计算...")
            result = calculate_all_trend_data(app, 'ssq')
            ssq_trend_count = len(result) if result else 0
        if new_dlt_count > 0:
            app.logger.info("触发大乐透趋势数据预计算...")
            result = calculate_all_trend_data(app, 'dlt')
            dlt_trend_count = len(result) if result else 0

        # 数据更新完成后，触发智能筛选规则统计更新
        if new_ssq_count > 0:
            app.logger.info("触发双色球智能筛选规则统计更新...")
            from smart_filter_engine import update_smart_filter_stats
            ssq_smart_count = update_smart_filter_stats('ssq', app) or 0
        if new_dlt_count > 0:
            app.logger.info("触发大乐透智能筛选规则统计更新...")
            from smart_filter_engine import update_smart_filter_stats
            dlt_smart_count = update_smart_filter_stats('dlt', app) or 0

        total_trend = ssq_trend_count + dlt_trend_count
        total_smart = ssq_smart_count + dlt_smart_count

        return new_ssq_count, new_dlt_count, total_trend, total_smart

def update_ssq_fuyun_status(app):
    """
    批量更新已有双色球开奖记录的福运奖状态。
    按期号升序遍历所有SSQDraw记录，根据奖池金额递推福运奖状态。
    2026年2月1日之前的记录强制关闭福运奖（福运奖规则当日才启用）。
    """
    FUYUN_START_DATE = date(2026, 2, 1)  # 福运奖启用日期
    
    with app.app_context():
        app.logger.info("开始批量更新双色球福运奖状态...")
        records = SSQDraw.query.order_by(SSQDraw.issue.asc()).all()
        updated_count = 0
        current_fuyun_status = False  # 初始状态：关闭
        before_start_date = True  # 标记是否还在福运奖启用日期之前
        
        for record in records:
            # 2026年2月1日之前的记录，福运奖强制关闭
            if record.draw_date < FUYUN_START_DATE:
                if record.fuyun_prize_active:
                    record.fuyun_prize_active = False
                    updated_count += 1
                current_fuyun_status = False  # 保持递推状态为关闭
                continue
            
            # 2026年2月1日（含）之后，按奖池递推
            old_status = record.fuyun_prize_active
            new_status = update_fuyun_prize_status(record.prize_pool, current_fuyun_status)
            if old_status != new_status:
                record.fuyun_prize_active = new_status
                updated_count += 1
            current_fuyun_status = new_status  # 更新当前状态，用于下一期的递推
        
        db.session.commit()
        app.logger.info(f"双色球福运奖状态批量更新完成，共更新 {updated_count} 条记录。")
        return updated_count

def get_latest_draws(model, count=1):
    """获取最新N期开奖数据"""
    return model.query.order_by(model.issue.desc()).limit(count).all()

def get_draw_by_issue(model, issue):
    """根据期号获取开奖数据"""
    return model.query.filter_by(issue=issue).first()

def add_manual_draw(lottery_type, data_string, app=None):
    """手动添加一期开奖数据"""
    if app is None:
        from flask import current_app
        app = current_app._get_current_object()
    if lottery_type == 'ssq':
        # 假设 data_string 是 '2025105 2025-09-11 04 07 18 24 26 28 08 ...'
        draw_objects = parse_ssq_data(data_string + '\n', app) # 模拟文件内容
        if draw_objects:
            return save_draw_data(draw_objects, 'ssq')
    elif lottery_type == 'dlt':
        draw_objects = parse_dlt_data(data_string + '\n', app)
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
    if len(parts) < 41: # 至少包含到备用字段5
        return False, "大乐透数据格式不完整，至少需要41个字段。"
    try:
        datetime.strptime(parts[1], '%Y-%m-%d') # 日期
        [int(p) for p in parts[2:9]] # 红蓝球
        # 出球顺序字段可能为 '-'，特殊处理
        for p in parts[9:16]:
            if p != '-':
                int(p)
        int(parts[16]) # 销售额
        # ... 更多详细校验
        return True, ""
    except (ValueError, IndexError):
        return False, "大乐透数据格式错误，请检查数字和日期格式。"


def clean_amount(val_str):
    """清理金额字符串中的逗号和小数点，返回整型"""
    if not val_str:
        return 0
    try:
        cleaned = str(val_str).replace(',', '').strip()
        return int(float(cleaned))
    except (ValueError, TypeError):
        return 0

def parse_kl8_data(raw_data, app):
    """解析快乐8原始数据 (80选20)"""
    draws = []
    if not raw_data:
        return draws
    lines = raw_data.strip().split('\n')
    for line in lines:
        parts = line.split()
        if len(parts) < 24:
            continue
        try:
            issue = parts[0]
            draw_date = datetime.strptime(parts[1], '%Y-%m-%d').date()
            # 20 个开奖号码
            raw_balls = sorted([int(p) for p in parts[2:22]])
            winning_balls = ','.join([f"{b:02d}" for b in raw_balls])
            
            # 计算衍生统计数据
            sum_val = sum(raw_balls)
            odd_count = sum(1 for b in raw_balls if b % 2 != 0)
            even_count = 20 - odd_count
            top_count = sum(1 for b in raw_balls if b <= 40)
            bottom_count = 20 - top_count

            sales_amount = clean_amount(parts[22])
            prize_pool = clean_amount(parts[23])

            # 选十主要奖项 (若字段足够)
            first_prize_count = clean_amount(parts[24]) if len(parts) > 24 else 0
            first_prize_amount = clean_amount(parts[25]) if len(parts) > 25 else 0
            pick10_hit9_count = clean_amount(parts[26]) if len(parts) > 26 else 0
            pick10_hit9_amount = clean_amount(parts[27]) if len(parts) > 27 else 0
            pick10_hit8_count = clean_amount(parts[28]) if len(parts) > 28 else 0
            pick10_hit8_amount = clean_amount(parts[29]) if len(parts) > 29 else 0
            pick10_hit7_count = clean_amount(parts[30]) if len(parts) > 30 else 0
            pick10_hit7_amount = clean_amount(parts[31]) if len(parts) > 31 else 0
            pick10_hit0_count = clean_amount(parts[36]) if len(parts) > 36 else 0
            pick10_hit0_amount = clean_amount(parts[37]) if len(parts) > 37 else 0

            draws.append(KL8Draw(
                issue=issue,
                draw_date=draw_date,
                winning_balls=winning_balls,
                sales_amount=sales_amount,
                prize_pool=prize_pool,
                sum_val=sum_val,
                odd_count=odd_count,
                even_count=even_count,
                top_count=top_count,
                bottom_count=bottom_count,
                first_prize_count=first_prize_count,
                first_prize_amount=first_prize_amount,
                pick10_hit9_count=pick10_hit9_count,
                pick10_hit9_amount=pick10_hit9_amount,
                pick10_hit8_count=pick10_hit8_count,
                pick10_hit8_amount=pick10_hit8_amount,
                pick10_hit7_count=pick10_hit7_count,
                pick10_hit7_amount=pick10_hit7_amount,
                pick10_hit0_count=pick10_hit0_count,
                pick10_hit0_amount=pick10_hit0_amount
            ))
        except (ValueError, IndexError) as e:
            app.logger.error(f"Error parsing KL8 line '{line}': {e}")
    return draws

def parse_7xc_data(raw_data, app):
    """解析七星彩原始数据 (前6位0-9 + 后区1位0-14)"""
    draws = []
    if not raw_data:
        return draws
    lines = raw_data.strip().split('\n')
    for line in lines:
        parts = line.split()
        if len(parts) < 13:
            continue
        try:
            issue = parts[0]
            draw_date = datetime.strptime(parts[1], '%Y-%m-%d').date()
            front_numbers = ','.join([str(int(p)) for p in parts[2:8]])
            back_number = int(parts[8])
            sales_amount = clean_amount(parts[9])
            prize_pool = clean_amount(parts[10])

            first_prize_count = clean_amount(parts[11]) if len(parts) > 11 else 0
            first_prize_amount = clean_amount(parts[12]) if len(parts) > 12 else 0
            second_prize_count = clean_amount(parts[13]) if len(parts) > 13 else 0
            second_prize_amount = clean_amount(parts[14]) if len(parts) > 14 else 0
            third_prize_count = clean_amount(parts[15]) if len(parts) > 15 else 0
            third_prize_amount = clean_amount(parts[16]) if len(parts) > 16 else 0
            fourth_prize_count = clean_amount(parts[17]) if len(parts) > 17 else 0
            fourth_prize_amount = clean_amount(parts[18]) if len(parts) > 18 else 0
            fifth_prize_count = clean_amount(parts[19]) if len(parts) > 19 else 0
            fifth_prize_amount = clean_amount(parts[20]) if len(parts) > 20 else 0
            sixth_prize_count = clean_amount(parts[21]) if len(parts) > 21 else 0
            sixth_prize_amount = clean_amount(parts[22]) if len(parts) > 22 else 0

            draws.append(SevenXCDraw(
                issue=issue,
                draw_date=draw_date,
                front_numbers=front_numbers,
                back_number=back_number,
                sales_amount=sales_amount,
                prize_pool=prize_pool,
                first_prize_count=first_prize_count,
                first_prize_amount=first_prize_amount,
                second_prize_count=second_prize_count,
                second_prize_amount=second_prize_amount,
                third_prize_count=third_prize_count,
                third_prize_amount=third_prize_amount,
                fourth_prize_count=fourth_prize_count,
                fourth_prize_amount=fourth_prize_amount,
                fifth_prize_count=fifth_prize_count,
                fifth_prize_amount=fifth_prize_amount,
                sixth_prize_count=sixth_prize_count,
                sixth_prize_amount=sixth_prize_amount
            ))
        except (ValueError, IndexError) as e:
            app.logger.error(f"Error parsing 7XC line '{line}': {e}")
    return draws

def parse_7lc_data(raw_data, app):
    """解析七乐彩原始数据 (30选7基本号 + 1特别号)"""
    draws = []
    if not raw_data:
        return draws
    lines = raw_data.strip().split('\n')
    for line in lines:
        parts = line.split()
        if len(parts) < 14:
            continue
        try:
            issue = parts[0]
            draw_date = datetime.strptime(parts[1], '%Y-%m-%d').date()
            raw_basic = sorted([int(p) for p in parts[2:9]])
            basic_balls = ','.join([f"{b:02d}" for b in raw_basic])
            special_ball = int(parts[9])

            sales_amount = clean_amount(parts[10])
            prize_pool = clean_amount(parts[11])

            first_prize_count = clean_amount(parts[12]) if len(parts) > 12 else 0
            first_prize_amount = clean_amount(parts[13]) if len(parts) > 13 else 0
            second_prize_count = clean_amount(parts[14]) if len(parts) > 14 else 0
            second_prize_amount = clean_amount(parts[15]) if len(parts) > 15 else 0
            third_prize_count = clean_amount(parts[16]) if len(parts) > 16 else 0
            third_prize_amount = clean_amount(parts[17]) if len(parts) > 17 else 0
            fourth_prize_count = clean_amount(parts[18]) if len(parts) > 18 else 0
            fourth_prize_amount = clean_amount(parts[19]) if len(parts) > 19 else 0
            fifth_prize_count = clean_amount(parts[20]) if len(parts) > 20 else 0
            fifth_prize_amount = clean_amount(parts[21]) if len(parts) > 21 else 0
            sixth_prize_count = clean_amount(parts[22]) if len(parts) > 22 else 0
            sixth_prize_amount = clean_amount(parts[23]) if len(parts) > 23 else 0
            seventh_prize_count = clean_amount(parts[24]) if len(parts) > 24 else 0
            seventh_prize_amount = clean_amount(parts[25]) if len(parts) > 25 else 0

            draws.append(SevenLCDraw(
                issue=issue,
                draw_date=draw_date,
                basic_balls=basic_balls,
                special_ball=special_ball,
                sales_amount=sales_amount,
                prize_pool=prize_pool,
                first_prize_count=first_prize_count,
                first_prize_amount=first_prize_amount,
                second_prize_count=second_prize_count,
                second_prize_amount=second_prize_amount,
                third_prize_count=third_prize_count,
                third_prize_amount=third_prize_amount,
                fourth_prize_count=fourth_prize_count,
                fourth_prize_amount=fourth_prize_amount,
                fifth_prize_count=fifth_prize_count,
                fifth_prize_amount=fifth_prize_amount,
                sixth_prize_count=sixth_prize_count,
                sixth_prize_amount=sixth_prize_amount,
                seventh_prize_count=seventh_prize_count,
                seventh_prize_amount=seventh_prize_amount
            ))
        except (ValueError, IndexError) as e:
            app.logger.error(f"Error parsing 7LC line '{line}': {e}")
    return draws


def update_single_lottery(lottery_type, app):
    '''更新指定单彩种的数据 (ssq, dlt, kl8, 7xc, 7lc)'''
    with app.app_context():
        if lottery_type == 'ssq':
            raw = fetch_raw_data(SSQ_URL, app)
            draws = parse_ssq_data(raw, app)
            return save_draw_data(draws, 'ssq')
        elif lottery_type == 'dlt':
            raw = fetch_raw_data(DLT_URL, app)
            draws = parse_dlt_data(raw, app)
            return save_draw_data(draws, 'dlt')
        elif lottery_type == 'kl8':
            raw = fetch_raw_data(KL8_URL, app)
            draws = parse_kl8_data(raw, app)
            return save_draw_data(draws, 'kl8')
        elif lottery_type == '7xc':
            raw = fetch_raw_data(SEVEN_XC_URL, app)
            draws = parse_7xc_data(raw, app)
            return save_draw_data(draws, '7xc')
        elif lottery_type == '7lc':
            raw = fetch_raw_data(SEVEN_LC_URL, app)
            draws = parse_7lc_data(raw, app)
            return save_draw_data(draws, '7lc')
        else:
            app.logger.error(f"Unknown lottery type: {lottery_type}")
            return 0
