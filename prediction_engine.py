# prediction_engine.py
import random
from collections import Counter
from flask import current_app
from models import SSQDraw, DLTDraw, db
from config import CURRENT_SETTINGS, PRIZE_RULES
from utils import format_lottery_numbers, calculate_omissions, get_consecutive_groups, calculate_odd_even_sum, calculate_frequency_and_omissions_for_balls

# 版本号，每次生成文件时更新
__version__ = "1.0.6" # 更新版本号

# --- 辅助函数：获取指定期号之前的历史开奖数据 ---
def _get_previous_draws(model_class, current_issue, num_draws):
    """
    获取指定期号之前的num_draws期开奖数据。
    返回的列表按issue降序排列 (即最新一期在前)。
    """
    # 如果没有提供 current_issue (例如，在预测最新一期时)，则从最新期开始获取
    if current_issue is None:
        return model_class.query.order_by(model_class.issue.desc()).limit(num_draws).all()

    current_draw = model_class.query.filter_by(issue=current_issue).first()
    if not current_draw:
        current_app.logger.warning(f"Could not find draw for issue {current_issue} in {model_class.__name__}.")
        return []
    
    return model_class.query.filter(model_class.issue < current_issue)\
                            .order_by(model_class.issue.desc())\
                            .limit(num_draws).all()

# --- 双色球规则检查函数 (针对历史开奖数据) ---
# (这部分保持不变，因为这些是检查历史数据的规则)

def _check_ssq_rule_4_1_1_blue_consecutive(draw: SSQDraw):
    """
    规则 4.1.1 蓝球连续开出检查
    检查当前期开出的蓝球，是否在当前期及之前的连续N期中都出现。
    """
    blue_ball = draw.get_blue_balls_list()[0]
    recent_draws_including_current = SSQDraw.query.filter(SSQDraw.issue <= draw.issue)\
                                .order_by(SSQDraw.issue.desc())\
                                .limit(5).all() 

    current_app.logger.debug(f"Rule 4.1.1: Checking blue ball {blue_ball} for issue {draw.issue}.")
    current_app.logger.debug(f"Recent draws (newest to oldest, including current): {[d.issue for d in recent_draws_including_current]}")

    consecutive_count = 0
    for d in recent_draws_including_current:
        if d.get_blue_balls_list() and blue_ball == d.get_blue_balls_list()[0]:
            consecutive_count += 1
            current_app.logger.debug(f"  Issue {d.issue} has blue ball {d.get_blue_balls_list()[0]}. Consecutive count: {consecutive_count}")
        else:
            current_app.logger.debug(f"  Issue {d.issue} has blue ball {d.get_blue_balls_list()[0] if d.get_blue_balls_list() else 'N/A'}. Break consecutive check.")
            break

    if consecutive_count >= 5:
        return {'passed': False, 'message': f'规则4.1.1: 蓝球 {blue_ball} 连续开出 {consecutive_count} 期 (>=5期)。'}
    elif consecutive_count >= 3:
        return {'passed': False, 'message': f'规则4.1.1: 蓝球 {blue_ball} 连续开出 {consecutive_count} 期 (>=3期)。'}
    return {'passed': True, 'message': f'规则4.1.1: 蓝球 {blue_ball} 未连续开出3或5期。'}

def _check_ssq_rule_4_1_3_red_consecutive_repeat(draw: SSQDraw):
    """
    规则 4.1.3 红球连续重复检查
    检查当前期开出的红球中，是否有号码在当前期及之前的连续3期中都出现。
    """
    current_red_balls = set(draw.get_red_balls_list())
    recent_draws_including_current = SSQDraw.query.filter(SSQDraw.issue <= draw.issue)\
                                .order_by(SSQDraw.issue.desc())\
                                .limit(3).all()

    current_app.logger.debug(f"Rule 4.1.3: Checking red balls {current_red_balls} for issue {draw.issue}.")
    current_app.logger.debug(f"Recent draws (newest to oldest, including current): {[d.issue for d in recent_draws_including_current]}")

    if len(recent_draws_including_current) < 3:
        return {'passed': True, 'message': '规则4.1.3: 无足够前期数据进行红球连续重复检查。'}

    for ball in current_red_balls:
        is_consecutive_3 = True
        current_app.logger.debug(f"  Checking red ball {ball} for 3 consecutive appearances.")
        for d in recent_draws_including_current:
            if ball not in d.get_red_balls_list():
                is_consecutive_3 = False
                current_app.logger.debug(f"    Ball {ball} not in issue {d.issue}'s red balls {d.get_red_balls_list()}. Not consecutive.")
                break
            else:
                current_app.logger.debug(f"    Ball {ball} found in issue {d.issue}'s red balls {d.get_red_balls_list()}.")
        if is_consecutive_3:
            return {'passed': False, 'message': f'规则4.1.3: 红球 {ball} 连续3期及以上开出。'}
            
    return {'passed': True, 'message': '规则4.1.3: 红球未出现连续3期及以上重复。'}


def _check_ssq_rule_4_1_4_red_area_distribution(red_balls):
    """
    规则 4.1.4 红球数字区域分布
    区域: [1-8], [9-16], [17-24], [25-33]
    要求分布在 >= 2个数字区间。
    """
    areas = set()
    for ball in red_balls:
        if 1 <= ball <= 8:
            areas.add(1)
        elif 9 <= ball <= 16:
            areas.add(2)
        elif 17 <= ball <= 24:
            areas.add(3)
        elif 25 <= ball <= 33:
            areas.add(4)
    
    distributed_areas = len(areas)
    if distributed_areas >= 2:
        return {'passed': True, 'message': f'规则4.1.4: 红球分布在 {distributed_areas} 个区域 (>=2个)。'}
    else:
        return {'passed': False, 'message': f'规则4.1.4: 红球仅分布在 {distributed_areas} 个区域 (<2个)。'}

def _check_ssq_rule_4_1_5_red_repeat_previous_2(draw: SSQDraw):
    """
    规则 4.1.5 红球与前2期重复号码不超过2个。
    """
    current_red_balls = set(draw.get_red_balls_list())
    previous_draws = _get_previous_draws(SSQDraw, draw.issue, 2)
    
    current_app.logger.debug(f"Rule 4.1.5: Checking red balls {current_red_balls} for issue {draw.issue} against previous 2 draws.")
    current_app.logger.debug(f"Previous 2 draws (newest to oldest): {[d.issue for d in previous_draws]}")

    if len(previous_draws) < 2:
        return {'passed': True, 'message': '规则4.1.5: 无足够前期数据进行红球重复检查。'}

    all_prev_red_balls = set()
    for prev_draw in previous_draws:
        all_prev_red_balls.update(prev_draw.get_red_balls_list())
    
    repeated_count = len(current_red_balls.intersection(all_prev_red_balls))
    current_app.logger.debug(f"  Repeated count with previous 2 draws: {repeated_count}")

    if repeated_count <= 2:
        return {'passed': True, 'message': f'规则4.1.5: 红球与前2期重复号码 {repeated_count} 个 (<=2个)。'}
    else:
        return {'passed': False, 'message': f'规则4.1.5: 红球与前2期重复号码 {repeated_count} 个 (>2个)。'}

def _check_ssq_rule_4_1_6_red_consecutive_4_plus(red_balls):
    """
    规则 4.1.6 红球不出现连续[4]个及以上数字的号码。
    """
    consecutive_groups = get_consecutive_groups(red_balls)
    current_app.logger.debug(f"Rule 4.1.6: Checking red balls {red_balls} for consecutive groups. Groups: {consecutive_groups}")
    for group in consecutive_groups:
        if len(group) >= 4:
            return {'passed': False, 'message': f'规则4.1.6: 红球出现连续 {len(group)} 个号码: {group} (>=4个)。'}
    return {'passed': True, 'message': '规则4.1.6: 红球未出现连续4个及以上号码。'}

# --- 大乐透规则检查函数 (针对历史开奖数据) ---
# (这部分保持不变，因为这些是检查历史数据的规则)

def _check_dlt_rule_4_2_1_blue_repeat_latest(draw: DLTDraw):
    """
    规则 4.2.1 大乐透蓝球重复最新一期检查 & 连续开出检查
    """
    current_blue_balls = set(draw.get_blue_balls_list())
    
    current_app.logger.debug(f"Rule 4.2.1: Checking DLT blue balls {current_blue_balls} for issue {draw.issue}.")

    # Part 1: Check repeat with immediately previous draw
    previous_draws_1 = _get_previous_draws(DLTDraw, draw.issue, 1)
    if previous_draws_1:
        prev_blue_balls = set(previous_draws_1[0].get_blue_balls_list())
        intersection = current_blue_balls.intersection(prev_blue_balls)
        if intersection:
            current_app.logger.debug(f"  Intersection with previous blue balls {prev_blue_balls}: {list(intersection)}")
            return {'passed': False, 'message': f'规则4.2.1: 后区号码 {list(intersection)} 与前一期有重复。'}
    
    # Part 2: Check for 5 consecutive appearances of *any* blue ball in the current draw
    recent_draws_including_current = DLTDraw.query.filter(DLTDraw.issue <= draw.issue)\
                                .order_by(DLTDraw.issue.desc())\
                                .limit(5).all()

    current_app.logger.debug(f"Recent DLT draws (newest to oldest, including current): {[d.issue for d in recent_draws_including_current]}")

    for current_ball in current_blue_balls:
        consecutive_count = 0
        for d in recent_draws_including_current:
            if d.get_blue_balls_list() and current_ball in d.get_blue_balls_list():
                consecutive_count += 1
                current_app.logger.debug(f"  Issue {d.issue} has blue ball {current_ball}. Consecutive count: {consecutive_count}")
            else:
                current_app.logger.debug(f"  Issue {d.issue} does not have blue ball {current_ball}. Break consecutive check for this ball.")
                break
        
        if consecutive_count >= 5:
            return {'passed': False, 'message': f'规则4.2.1: 后区号码 {current_ball} 连续开出 {consecutive_count} 期 (>=5期)。'}

    return {'passed': True, 'message': '规则4.2.1: 后区号码与前一期无重复，且无号码连续开出5期。'}

def _check_dlt_rule_4_2_3_red_consecutive_repeat(draw: DLTDraw):
    """
    规则 4.2.3 大乐透红球连续重复检查
    检查当前期开出的前区中，是否有号码在当前期及之前的连续3期中都出现。
    """
    current_front_balls = set(draw.get_red_balls_list())
    recent_draws_including_current = DLTDraw.query.filter(DLTDraw.issue <= draw.issue)\
                                .order_by(DLTDraw.issue.desc())\
                                .limit(3).all()

    current_app.logger.debug(f"Rule 4.2.3: Checking DLT front balls {current_front_balls} for issue {draw.issue}.")
    current_app.logger.debug(f"Recent DLT draws (newest to oldest, including current): {[d.issue for d in recent_draws_including_current]}")

    if len(recent_draws_including_current) < 3:
        return {'passed': True, 'message': '规则4.2.3: 无足够前期数据进行前区连续重复检查。'}

    for ball in current_front_balls:
        is_consecutive_3 = True
        current_app.logger.debug(f"  Checking front ball {ball} for 3 consecutive appearances.")
        for d in recent_draws_including_current:
            if ball not in d.get_red_balls_list():
                is_consecutive_3 = False
                current_app.logger.debug(f"    Ball {ball} not in issue {d.issue}'s front balls {d.get_red_balls_list()}. Not consecutive.")
                break
            else:
                current_app.logger.debug(f"    Ball {ball} found in issue {d.issue}'s front balls {d.get_red_balls_list()}.")
        if is_consecutive_3:
            return {'passed': False, 'message': f'规则4.2.3: 前区号码 {ball} 连续3期及以上开出。'}
            
    return {'passed': True, 'message': '规则4.2.3: 前区号码未出现连续3期及以上重复。'}


def _check_dlt_rule_4_2_4_red_area_distribution(front_balls):
    """
    规则 4.2.4 大乐透前区数字区域分布
    区域: [1-8], [9-16], [17-24], [25-35]
    要求分布在 >= 2个数字区间。
    """
    areas = set()
    for ball in front_balls:
        if 1 <= ball <= 8:
            areas.add(1)
        elif 9 <= ball <= 16:
            areas.add(2)
        elif 17 <= ball <= 24:
            areas.add(3)
        elif 25 <= ball <= 35:
            areas.add(4)
    
    distributed_areas = len(areas)
    if distributed_areas >= 2:
        return {'passed': True, 'message': f'规则4.2.4: 前区分布在 {distributed_areas} 个区域 (>=2个)。'}
    else:
        return {'passed': False, 'message': f'规则4.2.4: 前区仅分布在 {distributed_areas} 个区域 (<2个)。'}

def _check_dlt_rule_4_2_5_red_repeat_previous_2(draw: DLTDraw):
    """
    规则 4.2.5 大乐透前区与前2期重复号码不超过2个。
    """
    current_front_balls = set(draw.get_red_balls_list())
    previous_draws = _get_previous_draws(DLTDraw, draw.issue, 2)
    
    current_app.logger.debug(f"Rule 4.2.5: Checking DLT front balls {current_front_balls} for issue {draw.issue} against previous 2 draws.")
    current_app.logger.debug(f"Previous 2 draws (newest to oldest): {[d.issue for d in previous_draws]}")

    if len(previous_draws) < 2:
        return {'passed': True, 'message': '规则4.2.5: 无足够前期数据进行前区重复检查。'}

    all_prev_front_balls = set()
    for prev_draw in previous_draws:
        all_prev_front_balls.update(prev_draw.get_red_balls_list())
    
    repeated_count = len(current_front_balls.intersection(all_prev_front_balls))
    current_app.logger.debug(f"  Repeated count with previous 2 draws: {repeated_count}")
    
    if repeated_count <= 2:
        return {'passed': True, 'message': f'规则4.2.5: 前区与前2期重复号码 {repeated_count} 个 (<=2个)。'}
    else:
        return {'passed': False, 'message': f'规则4.2.5: 前区与前2期重复号码 {repeated_count} 个 (>2个)。'}

def _check_dlt_rule_4_2_6_red_consecutive_4_plus(front_balls):
    """
    规则 4.2.6 大乐透前区不出现连续[4]个及以上数字的号码。
    """
    consecutive_groups = get_consecutive_groups(front_balls)
    current_app.logger.debug(f"Rule 4.2.6: Checking DLT front balls {front_balls} for consecutive groups. Groups: {consecutive_groups}")
    for group in consecutive_groups:
        if len(group) >= 4:
            return {'passed': False, 'message': f'规则4.2.6: 前区出现连续 {len(group)} 个号码: {group} (>=4个)。'}
    return {'passed': True, 'message': '规则4.2.6: 前区未出现连续4个及以上号码。'}


# --- 主规则检查函数 (供API调用) ---
def check_ssq_rules_for_draw(draw: SSQDraw):
    """
    检查双色球开奖号码是否符合预设规则。
    返回一个字典，包含规则检查结果。
    """
    results = {}
    red_balls = draw.get_red_balls_list()
    
    # 应用双色球规则
    results['rule_4_1_1_blue_consecutive'] = _check_ssq_rule_4_1_1_blue_consecutive(draw)
    results['rule_4_1_3_red_consecutive_repeat'] = _check_ssq_rule_4_1_3_red_consecutive_repeat(draw)
    results['rule_4_1_4_red_area_distribution'] = _check_ssq_rule_4_1_4_red_area_distribution(red_balls)
    results['rule_4_1_5_red_repeat_previous_2'] = _check_ssq_rule_4_1_5_red_repeat_previous_2(draw)
    results['rule_4_1_6_red_consecutive_4_plus'] = _check_ssq_rule_4_1_6_red_consecutive_4_plus(red_balls)
    # TODO: Add other SSQ rules here as they are implemented

    return results

def check_dlt_rules_for_draw(draw: DLTDraw):
    """
    检查大乐透开奖号码是否符合预设规则。
    返回一个字典，包含规则检查结果。
    """
    results = {}
    front_balls = draw.get_red_balls_list() # DLT uses 'red_balls' for front area
    
    # 应用大乐透规则
    results['rule_4_2_1_blue_repeat_latest'] = _check_dlt_rule_4_2_1_blue_repeat_latest(draw)
    results['rule_4_2_3_red_consecutive_repeat'] = _check_dlt_rule_4_2_3_red_consecutive_repeat(draw)
    results['rule_4_2_4_red_area_distribution'] = _check_dlt_rule_4_2_4_red_area_distribution(front_balls)
    results['rule_4_2_5_red_repeat_previous_2'] = _check_dlt_rule_4_2_5_red_repeat_previous_2(draw)
    results['rule_4_2_6_red_consecutive_4_plus'] = _check_dlt_rule_4_2_6_red_consecutive_4_plus(front_balls)
    # TODO: Add other DLT rules here as they are implemented

    return results

def check_lottery_rules(lottery_type, issue):
    """
    根据彩票类型和期号，调用相应的规则检查函数。
    """
    if lottery_type == 'ssq':
        model_class = SSQDraw
        check_func = check_ssq_rules_for_draw
    elif lottery_type == 'dlt':
        model_class = DLTDraw
        check_func = check_dlt_rules_for_draw
    else:
        return {'error': 'Invalid lottery type'}

    draw = model_class.query.filter_by(issue=issue).first()
    if not draw:
        return {'error': f'{model_class.__name__} not found for issue {issue}'}

    return check_func(draw)


# --- 号码生成逻辑 ---

def generate_random_balls(lottery_type, num_red, num_blue):
    """
    生成一组完全随机的号码。
    """
    if lottery_type == 'ssq':
        red_range = PRIZE_RULES['ssq']['red_range']
        blue_range = PRIZE_RULES['ssq']['blue_range']
    elif lottery_type == 'dlt':
        red_range = PRIZE_RULES['dlt']['red_range']
        blue_range = PRIZE_RULES['dlt']['blue_range']
    else:
        return None, None

    if num_red > red_range or num_blue > blue_range:
        current_app.logger.error(f"Attempted to generate too many balls for {lottery_type}: red={num_red}/{red_range}, blue={num_blue}/{blue_range}")
        return [], []

    red_balls = sorted(random.sample(range(1, red_range + 1), num_red))
    blue_balls = sorted(random.sample(range(1, blue_range + 1), num_blue))
    return red_balls, blue_balls

def generate_predicted_balls(lottery_type):
    """
    根据预测规则生成一组号码。
    这部分将是核心逻辑，需要根据 config.py 中的规则进行复杂的加权和筛选。
    目前先返回一个占位符。
    """
    # TODO: Implement actual prediction logic based on rules from CURRENT_SETTINGS
    # This will involve:
    # 1. Fetching historical data (e.g., latest N draws)
    # 2. Calculating frequencies, omissions, etc.
    # 3. Applying weights and probabilities from CURRENT_SETTINGS
    # 4. Generating candidate pools for red and blue balls
    # 5. Iteratively selecting balls, checking against rules (e.g., consecutive, area distribution, repeat limits)
    # 6. Normalizing probabilities and sampling.

    # Placeholder for now
    if lottery_type == 'ssq':
        red_balls, blue_balls = generate_random_balls('ssq', 6, 1) # For now, just random
    elif lottery_type == 'dlt':
        red_balls, blue_balls = generate_random_balls('dlt', 5, 2) # For now, just random
    else:
        return [], []
    
    return red_balls, blue_balls

def get_omitted_balls_for_prediction(lottery_type):
    """
    获取遗漏最多的红球和蓝球，用于预测页面显示。
    """
    current_app.logger.info(f"Attempting to get omitted balls for {lottery_type}") # 新增日志

    model_class = SSQDraw if lottery_type == 'ssq' else DLTDraw
    red_ball_range = PRIZE_RULES[lottery_type]['red_range']
    blue_ball_range = PRIZE_RULES[lottery_type]['blue_range']

    all_draws = model_class.query.order_by(model_class.issue.desc()).all()
    
    current_app.logger.info(f"Found {len(all_draws)} historical draws for {lottery_type}.") # 新增日志

    if not all_draws:
        current_app.logger.warning(f"No historical data available for {lottery_type} to calculate omissions.") # 新增日志
        return {'error': 'No historical data available.'}

    # 计算红球遗漏
    red_stats_list, _ = calculate_frequency_and_omissions_for_balls(all_draws, red_ball_range, 'red')
    # 按照当前遗漏期数降序排序
    sorted_red_omissions = sorted(red_stats_list, key=lambda x: x['current_omission'], reverse=True)
    
    # 获取遗漏最多的 N 个红球
    num_omitted_red = CURRENT_SETTINGS.get('prediction_omitted_red_balls', 7)
    top_omitted_red = [ball_data['ball'] for ball_data in sorted_red_omissions[:num_omitted_red]]

    # 计算蓝球遗漏
    blue_stats_list, _ = calculate_frequency_and_omissions_for_balls(all_draws, blue_ball_range, 'blue')
    # 按照当前遗漏期数降序排序
    sorted_blue_omissions = sorted(blue_stats_list, key=lambda x: x['current_omission'], reverse=True)
    
    # 获取遗漏最多的 N 个蓝球
    num_omitted_blue = CURRENT_SETTINGS.get('prediction_omitted_blue_balls', 7)
    top_omitted_blue = [ball_data['ball'] for ball_data in sorted_blue_omissions[:num_omitted_blue]]

    current_app.logger.info(f"Omitted balls for {lottery_type}: Red={top_omitted_red}, Blue={top_omitted_blue}") # 新增日志

    return {
        'red_balls': top_omitted_red,
        'blue_balls': top_omitted_blue
    }

