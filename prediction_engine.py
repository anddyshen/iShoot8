# prediction_engine.py
import random
from collections import Counter
from datetime import date
from flask import current_app
from models import SSQDraw, DLTDraw, db # 确保 db 已导入
from config import CURRENT_SETTINGS, PRIZE_RULES
from utils import format_lottery_numbers, calculate_omissions, get_consecutive_groups, calculate_odd_even_sum, calculate_frequency_and_omissions_for_balls

# 版本号，每次生成文件时更新
__version__ = "1.0.10" # 更新版本号

# --- 辅助函数：加权随机采样 (不重复) ---
def weighted_random_sample_without_replacement(population, weights, k):
    """
    从给定总体中进行加权随机采样，不重复。
    population: 总体元素列表
    weights: 对应元素的权重列表
    k: 采样数量
    """
    if k > len(population):
        raise ValueError("Sample size k cannot be greater than population size.")

    sampled_elements = []
    current_population = list(population)
    current_weights = list(weights)

    for _ in range(k):
        # 归一化当前权重
        total_weight = sum(current_weights)
        if total_weight == 0: # 避免除以零，如果所有权重都为0，则均匀选择
            current_app.logger.warning("All weights are zero in weighted_random_sample_without_replacement. Resetting to uniform distribution for remaining samples.")
            current_weights = [1.0] * len(current_population)
            total_weight = sum(current_weights)
        
        normalized_weights = [w / total_weight for w in current_weights]
        
        # 加权选择一个元素
        chosen_element = random.choices(current_population, weights=normalized_weights, k=1)[0]
        sampled_elements.append(chosen_element)
        
        # 从总体中移除选中的元素及其权重
        chosen_index = current_population.index(chosen_element)
        current_population.pop(chosen_index)
        current_weights.pop(chosen_index)
        
    return sampled_elements

# --- 辅助函数：获取指定期号之前的历史开奖数据 ---
def _get_previous_draws(model_class, current_issue, num_draws):
    """
    获取指定期号之前的num_draws期开奖数据。
    返回的列表按issue降序排列 (即最新一期在前)。
    如果 current_issue 为 None，则获取最新的 num_draws 期数据。
    """
    # 如果 current_issue 为 None，则获取最新的 num_draws 期数据
    if current_issue is None:
        return model_class.query.order_by(model_class.issue.desc()).limit(num_draws).all()
    
    # 否则，获取指定期号之前的 num_draws 期开奖数据
    # 注意：这里不查找 current_issue 本身，因为在预测场景中 current_issue 可能是模拟的未来期号
    return model_class.query.filter(model_class.issue < current_issue)\
                            .order_by(model_class.issue.desc())\
                            .limit(num_draws).all()

# --- 双色球规则检查函数 (针对历史开奖数据) ---
# (这部分保持不变，因为这些是检查历史数据的规则)

def _check_ssq_rule_4_1_1_blue_consecutive(draw: SSQDraw):
    """
    规则 4.1.1 蓝球连续开出检查
    检查当前期开出的蓝球，是否在当前期及之前的连续N期中都出现。
    修改为：未连续3期及以上。并显示连续开了几期，如之前没开过就是0期。
    """
    blue_ball = draw.get_blue_balls_list()[0]
    
    # 获取所有期号小于或等于当前期的开奖数据，按期号降序排列
    all_previous_draws = SSQDraw.query.filter(SSQDraw.issue <= draw.issue)\
                                .order_by(SSQDraw.issue.desc()).all()

    current_app.logger.debug(f"Rule 4.1.1: Checking blue ball {blue_ball} for issue {draw.issue}.")
    current_app.logger.debug(f"All previous draws (newest to oldest, including current): {[d.issue for d in all_previous_draws]}")

    consecutive_count = 0
    for d in all_previous_draws:
        if d.get_blue_balls_list() and blue_ball == d.get_blue_balls_list()[0]:
            consecutive_count += 1
            current_app.logger.debug(f"  Issue {d.issue} has blue ball {d.get_blue_balls_list()[0]}. Consecutive count: {consecutive_count}")
        else:
            current_app.logger.debug(f"  Issue {d.issue} has blue ball {d.get_blue_balls_list()[0] if d.get_blue_balls_list() else 'N/A'}. Break consecutive check.")
            break
    
    if consecutive_count >= 3:
        return {'passed': False, 'message': f'蓝球 {blue_ball} 连续开出 {consecutive_count} 期。'}
    else:
        return {'passed': True, 'message': f'蓝球 {blue_ball} 连续开出 {consecutive_count} 期。'}

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
        return {'passed': True, 'message': '1: 无足够前期数据进行红球连续重复检查。'}

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
            return {'passed': False, 'message': f'1: 红球 {ball} 连续3期及以上开出。'}
            
    return {'passed': True, 'message': '1: 红球未出现连续3期及以上重复。'}


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
        return {'passed': True, 'message': f'2: 红球分布在 {distributed_areas} 个区域 (>=2个)。'}
    else:
        return {'passed': False, 'message': f'2: 红球仅分布在 {distributed_areas} 个区域 (<2个)。'}

def _check_ssq_rule_4_1_5_red_repeat_previous_2(draw: SSQDraw):
    """
    规则 4.1.5 红球与前2期重复号码不超过2个。
    """
    current_red_balls = set(draw.get_red_balls_list())
    previous_draws = _get_previous_draws(SSQDraw, draw.issue, 2)
    
    current_app.logger.debug(f"Rule 4.1.5: Checking red balls {current_red_balls} for issue {draw.issue} against previous 2 draws.")
    current_app.logger.debug(f"Previous 2 draws (newest to oldest): {[d.issue for d in previous_draws]}")

    if len(previous_draws) < 2:
        # 如果前期数据不足2期，则认为没有超过2个重复号码，规则通过
        return {'passed': True, 'message': '规则4.1.5: 无足够前期数据进行红球重复检查，默认规则通过。'}

    all_prev_red_balls = set()
    for prev_draw in previous_draws:
        all_prev_red_balls.update(prev_draw.get_red_balls_list())
    
    repeated_count = len(current_red_balls.intersection(all_prev_red_balls))
    # current_app.logger.debug(f"  Current red balls: {current_red_balls}")
    # current_app.logger.debug(f"  All previous 2 draws' red balls: {all_prev_red_balls}")
    # current_app.logger.debug(f"  Intersection (repeated balls): {current_red_balls.intersection(all_prev_red_balls)}")
    current_app.logger.debug(f"  Repeated count with previous 2 draws: {repeated_count}")

    if repeated_count <= 2:
        # current_app.logger.debug(f"  Rule 4.1.5 result: PASSED (repeated count {repeated_count} <= 2)")
        return {'passed': True, 'message': f'3: 红球与前2期重复号码 {repeated_count} 个 (<=2个)。'}
    else:
        # current_app.logger.debug(f"  Rule 4.1.5 result: FAILED (repeated count {repeated_count} > 2)")
        return {'passed': False, 'message': f'3: 红球与前2期重复号码 {repeated_count} 个 (>2个)。'}

def _check_ssq_rule_4_1_6_red_consecutive_4_plus(red_balls):
    """
    规则 4.1.6 红球不出现连续[4]个及以上数字的号码。
    """
    consecutive_groups, _ = get_consecutive_groups(red_balls) # Unpack the tuple
    current_app.logger.debug(f"Rule 4.1.6: Checking red balls {red_balls} for consecutive groups. Groups: {consecutive_groups}")
    for group in consecutive_groups:
        if len(group) >= 4:
            return {'passed': False, 'message': f'4: 红球出现连续 {len(group)} 个号码: {group} (>=4个)。'}
    return {'passed': True, 'message': '4: 红球未出现连续4个及以上号码。'}

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
        # 如果前期数据不足2期，则认为没有超过2个重复号码，规则通过
        return {'passed': True, 'message': '规则4.2.5: 无足够前期数据进行前区重复检查，默认规则通过。'}

    all_prev_front_balls = set()
    for prev_draw in previous_draws:
        all_prev_front_balls.update(prev_draw.get_red_balls_list())
    
    repeated_count = len(current_front_balls.intersection(all_prev_front_balls))
    # current_app.logger.debug(f"  Current front balls: {current_front_balls}")
    # current_app.logger.debug(f"  All previous 2 draws' front balls: {all_prev_front_balls}")
    # current_app.logger.debug(f"  Intersection (repeated balls): {current_front_balls.intersection(all_prev_front_balls)}")
    current_app.logger.debug(f"  Repeated count with previous 2 draws: {repeated_count}")
    
    if repeated_count <= 2:
        # current_app.logger.debug(f"  Rule 4.2.5 result: PASSED (repeated count {repeated_count} <= 2)")
        return {'passed': True, 'message': f'规则4.2.5: 前区与前2期重复号码 {repeated_count} 个 (<=2个)。'}
    else:
        # current_app.logger.debug(f"  Rule 4.2.5 result: FAILED (repeated count {repeated_count} > 2)")
        return {'passed': False, 'message': f'规则4.2.5: 前区与前2期重复号码 {repeated_count} 个 (>2个)。'}

def _check_dlt_rule_4_2_6_red_consecutive_4_plus(front_balls):
    """
    规则 4.2.6 大乐透前区不出现连续[4]个及以上数字的号码。
    """
    consecutive_groups, _ = get_consecutive_groups(front_balls) # Unpack the tuple
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
    results['rule_4_2_3_red_consecutive_repeat'] = _check_dlt_rule_4_2_3_red_consecutive_3_repeat(draw)
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

# --- 新增：检查生成号码的规则函数 ---
def check_ssq_rules_for_balls(red_balls: list, blue_balls: list):
    """
    检查一组双色球号码是否符合预设规则。
    此函数用于检查生成的号码，因此需要模拟一个 Draw 对象。
    """
    current_app.logger.info(f"Checking SSQ rules for generated balls: Red={red_balls}, Blue={blue_balls}")
    results = {}
    
    # 获取最新的实际开奖期号，用于模拟新生成的号码的“前N期”查询
    latest_ssq_draw = SSQDraw.query.order_by(SSQDraw.issue.desc()).first()
    
    if latest_ssq_draw:
        # 创建一个临时的 SSQDraw 对象，模拟为最新开奖的下一期
        dummy_draw_issue = int(latest_ssq_draw.issue) + 1
        dummy_draw_date = date.today()
    else:
        # 如果没有历史数据，则使用一个默认的期号和日期
        dummy_draw_issue = 2023001 # 任意一个起始期号
        dummy_draw_date = date.today()

    dummy_draw = SSQDraw(issue=dummy_draw_issue, draw_date=dummy_draw_date, 
                         red_balls=','.join(map(str, red_balls)), 
                         blue_balls=','.join(map(str, blue_balls)))
    
    # 应用双色球规则
    results['rule_4_1_1_blue_consecutive'] = _check_ssq_rule_4_1_1_blue_consecutive(dummy_draw)
    results['rule_4_1_3_red_consecutive_repeat'] = _check_ssq_rule_4_1_3_red_consecutive_repeat(dummy_draw)
    results['rule_4_1_4_red_area_distribution'] = _check_ssq_rule_4_1_4_red_area_distribution(red_balls)
    results['rule_4_1_5_red_repeat_previous_2'] = _check_ssq_rule_4_1_5_red_repeat_previous_2(dummy_draw)
    results['rule_4_1_6_red_consecutive_4_plus'] = _check_ssq_rule_4_1_6_red_consecutive_4_plus(red_balls)
    # TODO: Add other SSQ rules here as they are implemented, adapting them for raw balls
    
    return results

def check_dlt_rules_for_balls(front_balls: list, blue_balls: list):
    """
    检查一组大乐透号码是否符合预设规则。
    此函数用于检查生成的号码，因此需要模拟一个 Draw 对象。
    """
    current_app.logger.info(f"Checking DLT rules for generated balls: Front={front_balls}, Blue={blue_balls}")
    results = {}

    # 获取最新的实际开奖期号，用于模拟新生成的号码的“前N期”查询
    latest_dlt_draw = DLTDraw.query.order_by(DLTDraw.issue.desc()).first()

    if latest_dlt_draw:
        # 创建一个临时的 DLTDraw 对象，模拟为最新开奖的下一期
        dummy_draw_issue = int(latest_dlt_draw.issue) + 1
        dummy_draw_date = date.today()
    else:
        # 如果没有历史数据，则使用一个默认的期号和日期
        dummy_draw_issue = 2023001 # 任意一个起始期号
        dummy_draw_date = date.today()

    dummy_draw = DLTDraw(issue=dummy_draw_issue, draw_date=dummy_draw_date, 
                         red_balls=','.join(map(str, front_balls)), 
                         blue_balls=','.join(map(str, blue_balls)))

    # 应用大乐透规则
    results['rule_4_2_1_blue_repeat_latest'] = _check_dlt_rule_4_2_1_blue_repeat_latest(dummy_draw)
    results['rule_4_2_3_red_consecutive_repeat'] = _check_dlt_rule_4_2_3_red_consecutive_repeat(dummy_draw)
    results['rule_4_2_4_red_area_distribution'] = _check_dlt_rule_4_2_4_red_area_distribution(front_balls)
    results['rule_4_2_5_red_repeat_previous_2'] = _check_dlt_rule_4_2_5_red_repeat_previous_2(dummy_draw)
    results['rule_4_2_6_red_consecutive_4_plus'] = _check_dlt_rule_4_2_6_red_consecutive_4_plus(front_balls)
    # TODO: Add other DLT rules here as they are implemented, adapting them for raw balls

    return results


# --- 号码生成逻辑 ---

def generate_random_balls(lottery_type, num_red, num_blue):
    """
    生成一组完全随机的号码。
    """
    current_app.logger.info(f"Attempting to generate random balls for {lottery_type}: num_red={num_red}, num_blue={num_blue}")

    if lottery_type == 'ssq':
        red_range = PRIZE_RULES['ssq']['red_range']
        blue_range = PRIZE_RULES['ssq']['blue_range']
    elif lottery_type == 'dlt':
        red_range = PRIZE_RULES['dlt']['red_range']
        blue_range = PRIZE_RULES['dlt']['blue_range']
    else:
        current_app.logger.error(f"Invalid lottery type '{lottery_type}' provided to generate_random_balls.")
        return None, None

    current_app.logger.info(f"Ranges for {lottery_type}: red_range={red_range}, blue_range={blue_range}")

    if num_red > red_range or num_blue > blue_range:
        current_app.logger.error(f"Attempted to generate too many balls for {lottery_type}: red={num_red}/{red_range}, blue={num_blue}/{blue_range}. This will cause random.sample to fail.")
        # 返回 None, None 表示生成失败，而不是空列表，以便上层函数可以区分是参数错误还是数据不足
        return None, None 

    try:
        red_balls = sorted(random.sample(range(1, red_range + 1), num_red))
        blue_balls = sorted(random.sample(range(1, blue_range + 1), num_blue))
        current_app.logger.info(f"Successfully generated random balls: Red={red_balls}, Blue={blue_balls}")
        return red_balls, blue_balls
    except ValueError as e:
        current_app.logger.error(f"Error generating random balls for {lottery_type}: {e}")
        return None, None # 返回 None, None 表示生成失败

def generate_predicted_balls(lottery_type):
    """
    根据预测规则生成一组号码。
    这部分将是核心逻辑，需要根据 config.py 中的规则进行复杂的加权和筛选。
    """
    current_app.logger.info(f"Attempting to generate predicted balls for {lottery_type}.")
    

    red_range = PRIZE_RULES[lottery_type]['red_range']
    blue_range = PRIZE_RULES[lottery_type]['blue_range']

    predicted_red_balls = []
    predicted_blue_balls = []

    if lottery_type == 'ssq':
        # 获取所有历史开奖数据
        all_ssq_draws = SSQDraw.query.order_by(SSQDraw.issue.desc()).all()
        if not all_ssq_draws:
            current_app.logger.warning("No historical SSQ data available for prediction.")
            return generate_random_balls('ssq', 6, 1) # 如果没有历史数据，则返回随机号码

        latest_ssq_draw = all_ssq_draws[0]
        
        # --- 蓝球预测逻辑 ---
        blue_probabilities = {ball: 1.0 for ball in range(1, blue_range + 1)} # 初始均匀概率

        # 规则 4.1.1 / 1.1 蓝球避免最近重复与连续开出概率调整
        # 排除最新 N 期开出的蓝球
        num_omit_latest_blue = CURRENT_SETTINGS.get('ssq_blue_omit_latest_draws', 1)
        excluded_blue_balls = set()
        for i in range(min(num_omit_latest_blue, len(all_ssq_draws))):
            excluded_blue_balls.update(all_ssq_draws[i].get_blue_balls_list())
        
        for ball in excluded_blue_balls:
            if ball in blue_probabilities:
                blue_probabilities[ball] = 0.0 # 将排除的蓝球概率设为0

        # 蓝球连续开出概率调整
        ssq_blue_consecutive_3_prob = CURRENT_SETTINGS.get('ssq_blue_consecutive_3_prob', 0.08)
        ssq_blue_consecutive_5_prob = CURRENT_SETTINGS.get('ssq_blue_consecutive_5_prob', 0.35)

        for ball in range(1, blue_range + 1):
            if blue_probabilities[ball] > 0: # 只考虑未被排除的蓝球
                consecutive_count = 0
                for draw in all_ssq_draws:
                    if draw.get_blue_balls_list() and ball == draw.get_blue_balls_list()[0]:
                        consecutive_count += 1
                    else:
                        break # 不连续则中断
                
                if consecutive_count >= 5:
                    blue_probabilities[ball] = ssq_blue_consecutive_5_prob
                elif consecutive_count >= 3:
                    blue_probabilities[ball] = ssq_blue_consecutive_3_prob
        
        # 归一化蓝球概率
        total_blue_prob = sum(blue_probabilities.values())
        if total_blue_prob == 0: # 如果所有蓝球都被排除或概率为0，则恢复均匀分布
            current_app.logger.warning("All blue balls have 0 probability. Resetting to uniform distribution.")
            blue_probabilities = {ball: 1.0 for ball in range(1, blue_range + 1)}
            total_blue_prob = sum(blue_probabilities.values())
        
        normalized_blue_probabilities = {ball: prob / total_blue_prob for ball, prob in blue_probabilities.items()}
        
        # 采样蓝球
        predicted_blue_balls = sorted(random.choices(list(normalized_blue_probabilities.keys()), 
                                                     weights=list(normalized_blue_probabilities.values()), 
                                                     k=1))

        # --- 红球预测逻辑 ---
        red_probabilities = {ball: 1.0 for ball in range(1, red_range + 1)} # 初始均匀概率

        # 规则 4.1.2 / 1.2 红球遗漏优先权重
        red_omission_stats, _ = calculate_frequency_and_omissions_for_balls(all_ssq_draws, red_range, 'red')
        sorted_red_omissions = sorted(red_omission_stats, key=lambda x: x['current_omission'], reverse=True)
        
        omit_weights = {
            1: CURRENT_SETTINGS.get('ssq_red_omit_1_weight', 0.01),
            2: CURRENT_SETTINGS.get('ssq_red_omit_2_weight', 0.015),
            3: CURRENT_SETTINGS.get('ssq_red_omit_3_weight', 0.02),
            4: CURRENT_SETTINGS.get('ssq_red_omit_4_weight', 0.03),
            5: CURRENT_SETTINGS.get('ssq_red_omit_5_weight', 0.03),
            6: CURRENT_SETTINGS.get('ssq_red_omit_6_weight', 0.03),
        }
        
        total_assigned_weight = 0
        for i, ball_data in enumerate(sorted_red_omissions[:6]): # 前6个遗漏最多的红球
            rank = i + 1
            weight = omit_weights.get(rank, 0)
            red_probabilities[ball_data['ball']] += weight # 增加权重
            total_assigned_weight += weight
        
        # 剩余权重平分给其他号码 (这里简化处理，直接在现有概率上增加，后续归一化会处理)
        # 规则描述是“其他所有号码数字占比加起来平分剩下的百分比”，这里需要更精细的实现
        # 暂时先不实现剩余平分，因为会与后续规则冲突，先让所有规则独立调整，最后归一化

        # 规则 4.1.3 / 1.3 红球重复高概率
        ssq_red_consecutive_3_prob = CURRENT_SETTINGS.get('ssq_red_consecutive_3_prob', 0.35)
        ssq_red_consecutive_3_second_prob = CURRENT_SETTINGS.get('ssq_red_consecutive_3_second_prob', 0.0)

        latest_3_draws = all_ssq_draws[:3]
        if len(latest_3_draws) >= 3:
            red_ball_counts = Counter()
            for draw in latest_3_draws:
                red_ball_counts.update(draw.get_red_balls_list())
            
            consecutive_repeat_balls = [ball for ball, count in red_ball_counts.items() if count >= 3]
            
            if consecutive_repeat_balls:
                # 规则冲突优先级：先的优先考虑
                # 如果一个球同时是遗漏最多的和连续重复的，这里会叠加概率
                if len(consecutive_repeat_balls) >= 1:
                    red_probabilities[consecutive_repeat_balls[0]] += ssq_red_consecutive_3_prob
                if len(consecutive_repeat_balls) >= 2:
                    red_probabilities[consecutive_repeat_balls[1]] += ssq_red_consecutive_3_second_prob

        # 规则 4.1.10 / 1.10 红球高遗漏降概率
        ssq_red_omit_prob_threshold_1 = CURRENT_SETTINGS.get('ssq_red_omit_prob_threshold_1', 0.015)
        ssq_red_omit_prob_threshold_2 = CURRENT_SETTINGS.get('ssq_red_omit_prob_threshold_2', 0.0)
        ssq_red_omit_prob_threshold_3 = CURRENT_SETTINGS.get('ssq_red_omit_prob_threshold_3', 0.0)
        
        ssq_red_omit_threshold_1 = CURRENT_SETTINGS.get('ssq_red_omit_threshold_1', 12)
        ssq_red_omit_threshold_2 = CURRENT_SETTINGS.get('ssq_red_omit_threshold_2', 13)
        ssq_red_omit_threshold_3 = CURRENT_SETTINGS.get('ssq_red_omit_threshold_3', 14)

        for ball_data in red_omission_stats:
            ball = ball_data['ball']
            omission = ball_data['current_omission']
            if omission >= ssq_red_omit_threshold_3:
                red_probabilities[ball] = ssq_red_omit_prob_threshold_3
            elif omission >= ssq_red_omit_threshold_2:
                red_probabilities[ball] = ssq_red_omit_prob_threshold_2
            elif omission >= ssq_red_omit_threshold_1:
                red_probabilities[ball] = ssq_red_omit_prob_threshold_1
        
        # 归一化红球概率
        total_red_prob = sum(red_probabilities.values())
        if total_red_prob == 0: # 如果所有红球都被排除或概率为0，则恢复均匀分布
            current_app.logger.warning("All red balls have 0 probability. Resetting to uniform distribution.")
            red_probabilities = {ball: 1.0 for ball in range(1, red_range + 1)}
            total_red_prob = sum(red_probabilities.values())

        normalized_red_probabilities = {ball: prob / total_red_prob for ball, prob in red_probabilities.items()}

        # 加权随机采样红球，并检查结构性约束
        max_attempts = 200 # 增加尝试次数，避免因约束严格而无法找到组合
        for attempt in range(max_attempts):
            try:
                predicted_red_balls = weighted_random_sample_without_replacement(
                    list(normalized_red_probabilities.keys()), 
                    list(normalized_red_probabilities.values()), 
                    k=6
                )
            except ValueError as e:
                current_app.logger.error(f"Error during weighted_random_sample_without_replacement for SSQ red balls: {e}")
                # 如果采样失败，可能是因为 k > len(population)，这不应该发生，但作为回退
                predicted_red_balls = sorted(random.sample(range(1, red_range + 1), 6))
            
            # 检查规则 4.1.4 红球区域分布
            rule_4_1_4_passed = _check_ssq_rule_4_1_4_red_area_distribution(predicted_red_balls)['passed']
            
            # 检查规则 4.1.5 红球限重复数量
            # 需要模拟一个 Draw 对象来调用 _check_ssq_rule_4_1_5_red_repeat_previous_2
            dummy_draw_issue = int(latest_ssq_draw.issue) + 1 if latest_ssq_draw else 2023001
            dummy_draw_date = date.today()
            dummy_draw = SSQDraw(issue=dummy_draw_issue, draw_date=dummy_draw_date, 
                                 red_balls=','.join(map(str, predicted_red_balls)), 
                                 blue_balls='1') # 蓝球随便给一个，不影响红球规则检查
            rule_4_1_5_passed = _check_ssq_rule_4_1_5_red_repeat_previous_2(dummy_draw)['passed']

            # 检查规则 4.1.6 红球禁连续数字
            rule_4_1_6_passed = _check_ssq_rule_4_1_6_red_consecutive_4_plus(predicted_red_balls)['passed']

            if rule_4_1_4_passed and rule_4_1_5_passed and rule_4_1_6_passed:
                break
            elif attempt == max_attempts - 1:
                current_app.logger.warning("Max attempts reached for SSQ red ball generation, some structural rules might not be met. Returning None.")
                # 返回 None, None, attempts + 1, attempts 表示生成失败
                return None, None, attempts + 1, attempts 
        
        predicted_red_balls = sorted(predicted_red_balls) # 确保最终红球是排序的

    elif lottery_type == 'dlt':
        # 获取所有历史开奖数据
        all_dlt_draws = DLTDraw.query.order_by(DLTDraw.issue.desc()).all()
        if not all_dlt_draws:
            current_app.logger.warning("No historical DLT data available for prediction.")
            return generate_random_balls('dlt', 5, 2) # 如果没有历史数据，则返回随机号码

        latest_dlt_draw = all_dlt_draws[0]

        # --- 蓝球预测逻辑 ---
        blue_probabilities = {ball: 1.0 for ball in range(1, blue_range + 1)} # 初始均匀概率

        # 规则 4.2.1 / 2.1 蓝球限重复概率与连续开出概率调整
        # 如果与最新一期的蓝球重复，则重复的每个号码数字在候选池中的出现概率不超过 dlt_blue_repeat_prob
        dlt_blue_repeat_prob = CURRENT_SETTINGS.get('dlt_blue_repeat_prob', 0.035)
        if latest_dlt_draw:
            latest_blue_balls = set(latest_dlt_draw.get_blue_balls_list())
            for ball in latest_blue_balls:
                if ball in blue_probabilities:
                    blue_probabilities[ball] = min(blue_probabilities[ball], dlt_blue_repeat_prob) # 限制概率

        # 如果任何一个蓝球号码连续5期开出，则此号码候选池内的出现的概率为25%。
        dlt_blue_consecutive_5_prob = CURRENT_SETTINGS.get('dlt_blue_consecutive_5_prob', 0.25)
        for ball in range(1, blue_range + 1):
            consecutive_count = 0
            for draw in all_dlt_draws:
                if draw.get_blue_balls_list() and ball in draw.get_blue_balls_list():
                    consecutive_count += 1
                else:
                    break # 不连续则中断
            
            if consecutive_count >= 5:
                blue_probabilities[ball] = dlt_blue_consecutive_5_prob
        
        # 归一化蓝球概率
        total_blue_prob = sum(blue_probabilities.values())
        if total_blue_prob == 0:
            current_app.logger.warning("All DLT blue balls have 0 probability. Resetting to uniform distribution.")
            blue_probabilities = {ball: 1.0 for ball in range(1, blue_range + 1)}
            total_blue_prob = sum(blue_probabilities.values())
        
        normalized_blue_probabilities = {ball: prob / total_blue_prob for ball, prob in blue_probabilities.items()}
        
        # 采样蓝球
        predicted_blue_balls = sorted(random.choices(list(normalized_blue_probabilities.keys()), 
                                                     weights=list(normalized_blue_probabilities.values()), 
                                                     k=2)) # 大乐透选2个蓝球

        # --- 红球预测逻辑 ---
        red_probabilities = {ball: 1.0 for ball in range(1, red_range + 1)} # 初始均匀概率

        # 规则 4.2.2 / 2.2 红球遗漏优先权重
        red_omission_stats, _ = calculate_frequency_and_omissions_for_balls(all_dlt_draws, red_range, 'red')
        sorted_red_omissions = sorted(red_omission_stats, key=lambda x: x['current_omission'], reverse=True)
        
        omit_weights = {
            1: CURRENT_SETTINGS.get('dlt_red_omit_1_weight', 0.01),
            2: CURRENT_SETTINGS.get('dlt_red_omit_2_weight', 0.015),
            3: CURRENT_SETTINGS.get('dlt_red_omit_3_weight', 0.02),
            4: CURRENT_SETTINGS.get('dlt_red_omit_4_weight', 0.03),
            5: CURRENT_SETTINGS.get('dlt_red_omit_5_weight', 0.03),
            6: CURRENT_SETTINGS.get('dlt_red_omit_6_weight', 0.03), # 大乐透规则描述是前5个，但config有6个，这里取前6个
        }
        
        for i, ball_data in enumerate(sorted_red_omissions[:6]): # 前6个遗漏最多的红球
            rank = i + 1
            weight = omit_weights.get(rank, 0)
            red_probabilities[ball_data['ball']] += weight # 增加权重

        # 规则 4.2.3 / 2.3 红球重复高概率
        dlt_red_consecutive_3_prob = CURRENT_SETTINGS.get('dlt_red_consecutive_3_prob', 0.35)

        latest_3_draws = all_dlt_draws[:3]
        if len(latest_3_draws) >= 3:
            red_ball_counts = Counter()
            for draw in latest_3_draws:
                red_ball_counts.update(draw.get_red_balls_list())
            
            consecutive_repeat_balls = [ball for ball, count in red_ball_counts.items() if count >= 3]
            
            if consecutive_repeat_balls:
                # 规则冲突优先级：先的优先考虑
                if len(consecutive_repeat_balls) >= 1:
                    red_probabilities[consecutive_repeat_balls[0]] += dlt_red_consecutive_3_prob

        # 规则 4.2.10 / 2.10 红球高遗漏降概率
        dlt_red_omit_prob_threshold_1 = CURRENT_SETTINGS.get('dlt_red_omit_prob_threshold_1', 0.015)
        dlt_red_omit_prob_threshold_2 = CURRENT_SETTINGS.get('dlt_red_omit_prob_threshold_2', 0.0)
        dlt_red_omit_prob_threshold_3 = CURRENT_SETTINGS.get('dlt_red_omit_prob_threshold_3', 0.0)

        dlt_red_omit_threshold_1 = CURRENT_SETTINGS.get('dlt_red_omit_threshold_1', 12)
        dlt_red_omit_threshold_2 = CURRENT_SETTINGS.get('dlt_red_omit_threshold_2', 13)
        dlt_red_omit_threshold_3 = CURRENT_SETTINGS.get('dlt_red_omit_threshold_3', 14)

        for ball_data in red_omission_stats:
            ball = ball_data['ball']
            omission = ball_data['current_omission']
            if omission >= dlt_red_omit_threshold_3:
                red_probabilities[ball] = dlt_red_omit_prob_threshold_3
            elif omission >= dlt_red_omit_threshold_2:
                red_probabilities[ball] = dlt_red_omit_prob_threshold_2
            elif omission >= dlt_red_omit_threshold_1:
                red_probabilities[ball] = dlt_red_omit_prob_threshold_1
        
        # 归一化红球概率
        total_red_prob = sum(red_probabilities.values())
        if total_red_prob == 0:
            current_app.logger.warning("All DLT red balls have 0 probability. Resetting to uniform distribution.")
            red_probabilities = {ball: 1.0 for ball in range(1, red_range + 1)}
            total_red_prob = sum(red_probabilities.values())

        normalized_red_probabilities = {ball: prob / total_red_prob for ball, prob in red_probabilities.items()}

        # 加权随机采样红球，并检查结构性约束
        max_attempts = 200 # 增加尝试次数
        for attempt in range(max_attempts):
            try:
                predicted_red_balls = weighted_random_sample_without_replacement(
                    list(normalized_red_probabilities.keys()), 
                    list(normalized_red_probabilities.values()), 
                    k=5
                ) # 大乐透选5个红球
            except ValueError as e:
                current_app.logger.error(f"Error during weighted_random_sample_without_replacement for DLT red balls: {e}")
                predicted_red_balls = sorted(random.sample(range(1, red_range + 1), 5))
            
            # 检查规则 4.2.4 红球区域分布
            rule_4_2_4_passed = _check_dlt_rule_4_2_4_red_area_distribution(predicted_red_balls)['passed']
            
            # 检查规则 4.2.5 红球限重复数量
            dummy_draw_issue = int(latest_dlt_draw.issue) + 1 if latest_dlt_draw else 2023001
            dummy_draw_date = date.today()
            dummy_draw = DLTDraw(issue=dummy_draw_issue, draw_date=dummy_draw_date, 
                                 red_balls=','.join(map(str, predicted_red_balls)), 
                                 blue_balls='1,2') # 蓝球随便给两个，不影响红球规则检查
            rule_4_2_5_passed = _check_dlt_rule_4_2_5_red_repeat_previous_2(dummy_draw)['passed']

            # 检查规则 4.2.6 红球禁连续数字
            rule_4_2_6_passed = _check_dlt_rule_4_2_6_red_consecutive_4_plus(predicted_red_balls)['passed']

            if rule_4_2_4_passed and rule_4_2_5_passed and rule_4_2_6_passed:
                break
            elif attempt == max_attempts - 1:
                current_app.logger.warning("Max attempts reached for DLT red ball generation, some structural rules might not be met.")
        
        predicted_red_balls = sorted(predicted_red_balls) # 确保最终红球是排序的
        return predicted_red_balls, predicted_blue_balls, attempt + 1, attempt # 返回成功生成的号码，尝试次数，以及过滤掉的次数

    else:
        current_app.logger.error(f"Invalid lottery type '{lottery_type}' provided to generate_predicted_balls.")
        return None, None
    
    current_app.logger.info(f"Generated predicted balls: Red={predicted_red_balls}, Blue={predicted_blue_balls}")
    return predicted_red_balls, predicted_blue_balls, attempt + 1, attempt

def get_omitted_balls_for_prediction(lottery_type):
    """
    获取遗漏最多的红球和蓝球，并包含其遗漏期数，用于预测页面显示。
    返回格式: {'red_balls_with_omission': [{'ball': 1, 'omission': 10}, ...], ...}
    """
    current_app.logger.info(f"Attempting to get omitted balls for {lottery_type}")

    model_class = SSQDraw if lottery_type == 'ssq' else DLTDraw
    red_ball_range = PRIZE_RULES[lottery_type]['red_range']
    blue_ball_range = PRIZE_RULES[lottery_type]['blue_range']

    all_draws = model_class.query.order_by(model_class.issue.desc()).all()
    
    current_app.logger.info(f"Found {len(all_draws)} historical draws for {lottery_type}.")

    if not all_draws:
        current_app.logger.warning(f"No historical data available for {lottery_type} to calculate omissions.")
        return {'error': 'No historical data available.'}

    # 计算红球遗漏
    red_stats_list, _ = calculate_frequency_and_omissions_for_balls(all_draws, red_ball_range, 'red')
    current_app.logger.debug(f"Raw red_stats_list for {lottery_type}: {red_stats_list[:5]}...") # 打印前5个，检查结构
    # 按照当前遗漏期数降序排序
    sorted_red_omissions = sorted(red_stats_list, key=lambda x: x['current_omission'], reverse=True)
    
    # 获取遗漏最多的 N 个红球 (包含遗漏期数)
    num_omitted_red = CURRENT_SETTINGS.get('prediction_omitted_red_balls', 7)
    top_omitted_red_with_omission = sorted_red_omissions[:num_omitted_red]

    # 计算蓝球遗漏
    blue_stats_list, _ = calculate_frequency_and_omissions_for_balls(all_draws, blue_ball_range, 'blue')
    current_app.logger.debug(f"Raw blue_stats_list for {lottery_type}: {blue_stats_list[:5]}...") # 打印前5个，检查结构
    # 按照当前遗漏期数降序排序
    sorted_blue_omissions = sorted(blue_stats_list, key=lambda x: x['current_omission'], reverse=True)
    
    # 获取遗漏最多的 N 个蓝球 (包含遗漏期数)
    num_omitted_blue = CURRENT_SETTINGS.get('prediction_omitted_blue_balls', 7)
    top_omitted_blue_with_omission = sorted_blue_omissions[:num_omitted_blue]

    current_app.logger.info(f"Omitted balls for {lottery_type}: Red={top_omitted_red_with_omission}, Blue={top_omitted_blue_with_omission}")

    return {
        'red_balls_with_omission': top_omitted_red_with_omission,
        'blue_balls_with_omission': top_omitted_blue_with_omission
    }

def generate_complex_prediction_balls(lottery_type: str, red_count: int, blue_count: int):
    """
    根据预测规则生成一组复式号码。
    复用 generate_predicted_balls 的概率计算逻辑，但根据 red_count 和 blue_count 采样。
    """
    current_app.logger.info(f"Attempting to generate complex prediction balls for {lottery_type}: red_count={red_count}, blue_count={blue_count}")

    red_range = PRIZE_RULES[lottery_type]['red_range']
    blue_range = PRIZE_RULES[lottery_type]['blue_range']

    if red_count > red_range or blue_count > blue_range:
        raise ValueError(f"Requested counts exceed available ranges for {lottery_type}. Red: {red_count}/{red_range}, Blue: {blue_count}/{blue_range}")
    
    if (lottery_type == 'ssq' and red_count < 6) or \
       (lottery_type == 'dlt' and red_count < 5):
        raise ValueError(f"Red ball count {red_count} is less than minimum required for {lottery_type}.")
    
    if (lottery_type == 'ssq' and blue_count < 1) or \
       (lottery_type == 'dlt' and blue_count < 2):
        raise ValueError(f"Blue ball count {blue_count} is less than minimum required for {lottery_type}.")

    predicted_red_balls = []
    predicted_blue_balls = []

    if lottery_type == 'ssq':
        model_class = SSQDraw
        num_red_required = 6
        num_blue_required = 1
    elif lottery_type == 'dlt':
        model_class = DLTDraw
        num_red_required = 5
        num_blue_required = 2
    else:
        current_app.logger.error(f"Invalid lottery type '{lottery_type}' provided to generate_complex_prediction_balls.")
        return None

    all_draws = model_class.query.order_by(model_class.issue.desc()).all()
    if not all_draws:
        current_app.logger.warning(f"No historical {lottery_type.upper()} data available for complex prediction. Returning random balls.")
        return {
            'red_balls': sorted(random.sample(range(1, red_range + 1), red_count)),
            'blue_balls': sorted(random.sample(range(1, blue_range + 1), blue_count))
        }

    latest_draw = all_draws[0]
    dummy_draw_issue = int(latest_draw.issue) + 1
    dummy_draw_date = date.today()

    # --- 蓝球预测逻辑 (复用 generate_predicted_balls 的概率计算) ---
    blue_probabilities = {ball: 1.0 for ball in range(1, blue_range + 1)}

    if lottery_type == 'ssq':
        num_omit_latest_blue = CURRENT_SETTINGS.get('ssq_blue_omit_latest_draws', 1)
        excluded_blue_balls = set()
        for i in range(min(num_omit_latest_blue, len(all_draws))):
            excluded_blue_balls.update(all_draws[i].get_blue_balls_list())
        for ball in excluded_blue_balls:
            if ball in blue_probabilities:
                blue_probabilities[ball] = 0.0

        ssq_blue_consecutive_3_prob = CURRENT_SETTINGS.get('ssq_blue_consecutive_3_prob', 0.08)
        ssq_blue_consecutive_5_prob = CURRENT_SETTINGS.get('ssq_blue_consecutive_5_prob', 0.35)
        for ball in range(1, blue_range + 1):
            if blue_probabilities[ball] > 0:
                consecutive_count = 0
                for draw in all_draws:
                    if draw.get_blue_balls_list() and ball == draw.get_blue_balls_list()[0]:
                        consecutive_count += 1
                    else:
                        break
                if consecutive_count >= 5:
                    blue_probabilities[ball] = ssq_blue_consecutive_5_prob
                elif consecutive_count >= 3:
                    blue_probabilities[ball] = ssq_blue_consecutive_3_prob
    elif lottery_type == 'dlt':
        dlt_blue_repeat_prob = CURRENT_SETTINGS.get('dlt_blue_repeat_prob', 0.035)
        if latest_draw:
            latest_blue_balls = set(latest_draw.get_blue_balls_list())
            for ball in latest_blue_balls:
                if ball in blue_probabilities:
                    blue_probabilities[ball] = min(blue_probabilities[ball], dlt_blue_repeat_prob)

        dlt_blue_consecutive_5_prob = CURRENT_SETTINGS.get('dlt_blue_consecutive_5_prob', 0.25)
        for ball in range(1, blue_range + 1):
            consecutive_count = 0
            for draw in all_draws:
                if draw.get_blue_balls_list() and ball in draw.get_blue_balls_list():
                    consecutive_count += 1
                else:
                    break
            if consecutive_count >= 5:
                blue_probabilities[ball] = dlt_blue_consecutive_5_prob
    
    total_blue_prob = sum(blue_probabilities.values())
    if total_blue_prob == 0:
        current_app.logger.warning(f"All {lottery_type.upper()} blue balls have 0 probability. Resetting to uniform distribution.")
        blue_probabilities = {ball: 1.0 for ball in range(1, blue_range + 1)}
        total_blue_prob = sum(blue_probabilities.values())
    normalized_blue_probabilities = {ball: prob / total_blue_prob for ball, prob in blue_probabilities.items()}

    # --- 红球预测逻辑 (复用 generate_predicted_balls 的概率计算) ---
    red_probabilities = {ball: 1.0 for ball in range(1, red_range + 1)}

    red_omission_stats, _ = calculate_frequency_and_omissions_for_balls(all_draws, red_range, 'red')
    sorted_red_omissions = sorted(red_omission_stats, key=lambda x: x['current_omission'], reverse=True)

    if lottery_type == 'ssq':
        omit_weights = {
            1: CURRENT_SETTINGS.get('ssq_red_omit_1_weight', 0.01), 2: CURRENT_SETTINGS.get('ssq_red_omit_2_weight', 0.015),
            3: CURRENT_SETTINGS.get('ssq_red_omit_3_weight', 0.02), 4: CURRENT_SETTINGS.get('ssq_red_omit_4_weight', 0.03),
            5: CURRENT_SETTINGS.get('ssq_red_omit_5_weight', 0.03), 6: CURRENT_SETTINGS.get('ssq_red_omit_6_weight', 0.03),
        }
        for i, ball_data in enumerate(sorted_red_omissions[:6]):
            rank = i + 1
            weight = omit_weights.get(rank, 0)
            red_probabilities[ball_data['ball']] += weight

        ssq_red_consecutive_3_prob = CURRENT_SETTINGS.get('ssq_red_consecutive_3_prob', 0.35)
        ssq_red_consecutive_3_second_prob = CURRENT_SETTINGS.get('ssq_red_consecutive_3_second_prob', 0.0)
        latest_3_draws = all_draws[:3]
        if len(latest_3_draws) >= 3:
            red_ball_counts = Counter()
            for draw in latest_3_draws:
                red_ball_counts.update(draw.get_red_balls_list())
            consecutive_repeat_balls = [ball for ball, count in red_ball_counts.items() if count >= 3]
            if consecutive_repeat_balls:
                if len(consecutive_repeat_balls) >= 1:
                    red_probabilities[consecutive_repeat_balls[0]] += ssq_red_consecutive_3_prob
                if len(consecutive_repeat_balls) >= 2:
                    red_probabilities[consecutive_repeat_balls[1]] += ssq_red_consecutive_3_second_prob

        ssq_red_omit_12_prob = CURRENT_SETTINGS.get('ssq_red_omit_12_prob', 0.015)
        ssq_red_omit_13_prob = CURRENT_SETTINGS.get('ssq_red_omit_13_prob', 0.0)
        ssq_red_omit_14_prob = CURRENT_SETTINGS.get('ssq_red_omit_14_prob', 0.0)
        for ball_data in red_omission_stats:
            ball = ball_data['ball']
            omission = ball_data['current_omission']
            if omission >= 14: red_probabilities[ball] = ssq_red_omit_14_prob
            elif omission >= 13: red_probabilities[ball] = ssq_red_omit_13_prob
            elif omission >= 12: red_probabilities[ball] = ssq_red_omit_12_prob

    elif lottery_type == 'dlt':
        omit_weights = {
            1: CURRENT_SETTINGS.get('dlt_red_omit_1_weight', 0.01), 2: CURRENT_SETTINGS.get('dlt_red_omit_2_weight', 0.015),
            3: CURRENT_SETTINGS.get('dlt_red_omit_3_weight', 0.02), 4: CURRENT_SETTINGS.get('dlt_red_omit_4_weight', 0.03),
            5: CURRENT_SETTINGS.get('dlt_red_omit_5_weight', 0.03), 6: CURRENT_SETTINGS.get('dlt_red_omit_6_weight', 0.03),
        }
        for i, ball_data in enumerate(sorted_red_omissions[:6]):
            rank = i + 1
            weight = omit_weights.get(rank, 0)
            red_probabilities[ball_data['ball']] += weight

        dlt_red_consecutive_3_prob = CURRENT_SETTINGS.get('dlt_red_consecutive_3_prob', 0.35)
        latest_3_draws = all_draws[:3]
        if len(latest_3_draws) >= 3:
            red_ball_counts = Counter()
            for draw in latest_3_draws:
                red_ball_counts.update(draw.get_red_balls_list())
            consecutive_repeat_balls = [ball for ball, count in red_ball_counts.items() if count >= 3]
            if consecutive_repeat_balls:
                if len(consecutive_repeat_balls) >= 1:
                    red_probabilities[consecutive_repeat_balls[0]] += dlt_red_consecutive_3_prob

        dlt_red_omit_12_prob = CURRENT_SETTINGS.get('dlt_red_omit_12_prob', 0.015)
        dlt_red_omit_13_prob = CURRENT_SETTINGS.get('dlt_red_omit_13_prob', 0.0)
        dlt_red_omit_14_prob = CURRENT_SETTINGS.get('dlt_red_omit_14_prob', 0.0)
        for ball_data in red_omission_stats:
            ball = ball_data['ball']
            omission = ball_data['current_omission']
            if omission >= 14: red_probabilities[ball] = dlt_red_omit_14_prob
            elif omission >= 13: red_probabilities[ball] = dlt_red_omit_13_prob
            elif omission >= 12: red_probabilities[ball] = dlt_red_omit_12_prob

    total_red_prob = sum(red_probabilities.values())
    if total_red_prob == 0:
        current_app.logger.warning(f"All {lottery_type.upper()} red balls have 0 probability. Resetting to uniform distribution.")
        red_probabilities = {ball: 1.0 for ball in range(1, red_range + 1)}
        total_red_prob = sum(red_probabilities.values())
    normalized_red_probabilities = {ball: prob / total_red_prob for ball, prob in red_probabilities.items()}

    # --- 加权随机采样红球和蓝球，并检查结构性约束 ---
    max_attempts = 500 # 增加尝试次数，因为复式号码的约束可能更难满足
    for attempt in range(max_attempts):
        try:
            # 采样红球
            sampled_red_balls = weighted_random_sample_without_replacement(
                list(normalized_red_probabilities.keys()), 
                list(normalized_red_probabilities.values()), 
                k=red_count
            )
            # 采样蓝球
            sampled_blue_balls = weighted_random_sample_without_replacement(
                list(normalized_blue_probabilities.keys()), 
                list(normalized_blue_probabilities.values()), 
                k=blue_count
            )
        except ValueError as e:
            current_app.logger.error(f"Error during weighted_random_sample_without_replacement for complex prediction: {e}")
            # 如果采样失败，可能是因为 k > len(population)，作为回退，生成随机号码
            sampled_red_balls = sorted(random.sample(range(1, red_range + 1), red_count))
            sampled_blue_balls = sorted(random.sample(range(1, blue_range + 1), blue_count))

        # 检查结构性规则
        # 需要模拟一个 Draw 对象来调用规则检查函数
        if lottery_type == 'ssq':
            dummy_draw = SSQDraw(issue=dummy_draw_issue, draw_date=dummy_draw_date, 
                                 red_balls=','.join(map(str, sampled_red_balls[:num_red_required])), # 只检查前6个红球
                                 blue_balls=','.join(map(str, sampled_blue_balls[:num_blue_required]))) # 只检查前1个蓝球
            
            # 规则 4.1.4 红球区域分布 (检查所有选中的红球)
            rule_4_1_4_passed = _check_ssq_rule_4_1_4_red_area_distribution(sampled_red_balls)['passed']
            # 规则 4.1.5 红球限重复数量 (检查所有选中的红球)
            rule_4_1_5_passed = _check_ssq_rule_4_1_5_red_repeat_previous_2(dummy_draw)['passed']
            # 规则 4.1.6 红球禁连续数字 (检查所有选中的红球)
            rule_4_1_6_passed = _check_ssq_rule_4_1_6_red_consecutive_4_plus(sampled_red_balls)['passed']

            # 对于复式号码，我们只检查其“核心”部分是否符合单式规则
            # 例如，双色球复式7红1蓝，我们从7个红球中随机选6个，检查这6个是否符合规则
            # 这里简化处理，直接检查选出的 red_count 个红球是否符合规则
            # 更严谨的做法是，从 red_count 个红球中生成所有 C(red_count, 6) 组合，然后检查每个组合是否符合规则
            # 但这会非常复杂且计算量大，对于“生成复式号码”的按钮，通常是生成一个符合规则的“复式号码本身”
            # 而不是生成所有符合规则的单式组合。
            # 因此，我们检查选出的 red_count 个红球和 blue_count 个蓝球是否符合规则。
            
            # 暂时只检查红球的结构性规则，蓝球的结构性规则（如重复）已经在概率调整中处理
            if rule_4_1_4_passed and rule_4_1_5_passed and rule_4_1_6_passed:
                predicted_red_balls = sorted(sampled_red_balls)
                predicted_blue_balls = sorted(sampled_blue_balls)
                current_app.logger.info(f"Successfully generated complex SSQ balls after {attempt+1} attempts: Red={predicted_red_balls}, Blue={predicted_blue_balls}")
                return {'red_balls': predicted_red_balls, 'blue_balls': predicted_blue_balls}

        elif lottery_type == 'dlt':
            dummy_draw = DLTDraw(issue=dummy_draw_issue, draw_date=dummy_draw_date, 
                                 red_balls=','.join(map(str, sampled_red_balls[:num_red_required])), # 只检查前5个红球
                                 blue_balls=','.join(map(str, sampled_blue_balls[:num_blue_required]))) # 只检查前2个蓝球

            # 规则 4.2.4 红球区域分布 (检查所有选中的红球)
            rule_4_2_4_passed = _check_dlt_rule_4_2_4_red_area_distribution(sampled_red_balls)['passed']
            # 规则 4.2.5 红球限重复数量 (检查所有选中的红球)
            rule_4_2_5_passed = _check_dlt_rule_4_2_5_red_repeat_previous_2(dummy_draw)['passed']
            # 规则 4.2.6 红球禁连续数字 (检查所有选中的红球)
            rule_4_2_6_passed = _check_dlt_rule_4_2_6_red_consecutive_4_plus(sampled_red_balls)['passed']

            if rule_4_2_4_passed and rule_4_2_5_passed and rule_4_2_6_passed:
                predicted_red_balls = sorted(sampled_red_balls)
                predicted_blue_balls = sorted(sampled_blue_balls)
                current_app.logger.info(f"Successfully generated complex DLT balls after {attempt+1} attempts: Red={predicted_red_balls}, Blue={predicted_blue_balls}")
                return {'red_balls': predicted_red_balls, 'blue_balls': predicted_blue_balls}
        
        if attempt == max_attempts - 1:
            current_app.logger.warning(f"Max attempts reached for {lottery_type.upper()} complex ball generation, some structural rules might not be met. Returning None.")
            return None
    
    return None # 如果达到最大尝试次数仍未找到符合规则的组合
