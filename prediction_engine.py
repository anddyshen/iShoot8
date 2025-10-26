# prediction_engine.py
import random
from collections import Counter
from datetime import date
from flask import current_app
from models import SSQDraw, DLTDraw, db # 确保 db 已导入
from config import CURRENT_SETTINGS, PRIZE_RULES
from utils import (
    format_lottery_numbers, calculate_omissions, get_consecutive_groups, 
    calculate_frequency_and_omissions_for_balls,
    calculate_odd_even_ratio_per_draw, calculate_sum_per_draw, 
    calculate_span_per_draw, calculate_size_ratio_per_draw,
    calculate_mean_per_draw, calculate_remainder_group_counts_per_draw,
    calculate_prime_composite_ratio_per_draw, calculate_red_ball_area_distribution_per_draw,
    calculate_multi_draw_repeat_balls, calculate_diagonal_skip_numbers,
    calculate_consecutive_trend_over_draws # 新增导入趋势计算函数
)

# 版本号，每次生成文件时更新
__version__ = "1.0.12" # 更新版本号

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
            return {'passed': False, 'message': f'1: 后区号码 {list(intersection)} 与前一期有重复。'}
    
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
            return {'passed': False, 'message': f'1: 后区号码 {current_ball} 连续开出 {consecutive_count} 期 (>=5期)。'}

    return {'passed': True, 'message': '1: 后区号码与前一期无重复，且无号码连续开出5期。'}

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
        return {'passed': True, 'message': '2: 无足够前期数据进行前区连续重复检查。'}

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
            return {'passed': False, 'message': f'2: 前区号码 {ball} 连续3期及以上开出。'}
            
    return {'passed': True, 'message': '2: 前区号码未出现连续3期及以上重复。'}


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
        return {'passed': True, 'message': f'3: 前区分布在 {distributed_areas} 个区域 (>=2个)。'}
    else:
        return {'passed': False, 'message': f'3: 前区仅分布在 {distributed_areas} 个区域 (<2个)。'}

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
        return {'passed': True, 'message': '4: 无足够前期数据进行前区重复检查，默认规则通过。'}

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
        return {'passed': True, 'message': f'4: 前区与前2期重复号码 {repeated_count} 个 (<=2个)。'}
    else:
        # current_app.logger.debug(f"  Rule 4.2.5 result: FAILED (repeated count {repeated_count} > 2)")
        return {'passed': False, 'message': f'4: 前区与前2期重复号码 {repeated_count} 个 (>2个)。'}

def _check_dlt_rule_4_2_6_red_consecutive_4_plus(front_balls):
    """
    规则 4.2.6 大乐透前区不出现连续[4]个及以上数字的号码。
    """
    consecutive_groups, _ = get_consecutive_groups(front_balls) # Unpack the tuple
    current_app.logger.debug(f"Rule 4.2.6: Checking DLT front balls {front_balls} for consecutive groups. Groups: {consecutive_groups}")
    for group in consecutive_groups:
        if len(group) >= 4:
            return {'passed': False, 'message': f'5: 前区出现连续 {len(group)} 个号码: {group} (>=4个)。'}
    return {'passed': True, 'message': '5: 前区未出现连续4个及以上号码。'}


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

def generate_random_balls(lottery_type, num_red, num_blue, red_odd_even_ratio=None, red_size_ratio=None):
    """
    生成一组完全随机的号码，并根据奇偶比和大小比进行筛选。
    """
    current_app.logger.info(f"Attempting to generate random balls for {lottery_type}: num_red={num_red}, num_blue={num_blue}, odd/even={red_odd_even_ratio}, size={red_size_ratio}")

    if lottery_type == 'ssq':
        red_range = PRIZE_RULES['ssq']['red_range']
        blue_range = PRIZE_RULES['ssq']['blue_range']
    elif lottery_type == 'dlt':
        red_range = PRIZE_RULES['dlt']['red_range']
        blue_range = PRIZE_RULES['dlt']['blue_range']
    else:
        current_app.logger.error(f"Invalid lottery type '{lottery_type}' provided to generate_random_balls.")
        return None

    current_app.logger.info(f"Ranges for {lottery_type}: red_range={red_range}, blue_range={blue_range}")

    if num_red > red_range or num_blue > blue_range:
        current_app.logger.error(f"Attempted to generate too many balls for {lottery_type}: red={num_red}/{red_range}, blue={num_blue}/{blue_range}. This will cause random.sample to fail.")
        return None

    max_attempts = 1000 # 增加尝试次数以找到符合条件的号码
    attempts_made = 0
    filtered_count = 0

    while attempts_made < max_attempts:
        attempts_made += 1
        try:
            red_balls = sorted(random.sample(range(1, red_range + 1), num_red))
            blue_balls = sorted(random.sample(range(1, blue_range + 1), num_blue))

            # 计算统计数据
            red_size_midpoint = CURRENT_SETTINGS.get('ssq_red_size_midpoint', 17) if lottery_type == 'ssq' else CURRENT_SETTINGS.get('dlt_front_size_midpoint', 18)
            blue_size_midpoint = CURRENT_SETTINGS.get('ssq_blue_size_midpoint', 9) if lottery_type == 'ssq' else CURRENT_SETTINGS.get('dlt_back_size_midpoint', 7)

            current_red_odd_even_ratio = calculate_odd_even_ratio_per_draw(red_balls)
            current_red_size_ratio = calculate_size_ratio_per_draw(red_balls, red_size_midpoint)

            # 应用筛选条件
            if red_odd_even_ratio and red_odd_even_ratio != "" and current_red_odd_even_ratio != red_odd_even_ratio:
                filtered_count += 1
                continue
            if red_size_ratio and red_size_ratio != "" and current_red_size_ratio != red_size_ratio:
                filtered_count += 1
                continue

            # 如果通过所有筛选，则返回结果
            stats = {
                'red_odd_even_ratio': current_red_odd_even_ratio,
                'red_sum': calculate_sum_per_draw(red_balls),
                'red_span': calculate_span_per_draw(red_balls),
                'red_size_ratio': current_red_size_ratio,
                'blue_odd_even_ratio': calculate_odd_even_ratio_per_draw(blue_balls),
                'blue_sum': calculate_sum_per_draw(blue_balls),
                'blue_span': calculate_span_per_draw(blue_balls),
                'blue_size_ratio': calculate_size_ratio_per_draw(blue_balls, blue_size_midpoint),
            }
            current_app.logger.info(f"Successfully generated random balls after {attempts_made} attempts: Red={red_balls}, Blue={blue_balls}")
            return {'red_balls': red_balls, 'blue_balls': blue_balls, 'stats': stats, 'attempts_made': attempts_made, 'filtered_count': filtered_count}

        except ValueError as e:
            current_app.logger.error(f"Error generating random balls for {lottery_type}: {e}")
            return None

    current_app.logger.warning(f"Max attempts ({max_attempts}) reached for random ball generation with filters. No suitable combination found.")
    return None # 达到最大尝试次数仍未找到符合条件的组合

def generate_predicted_balls(lottery_type, red_odd_even_ratio=None, red_size_ratio=None, blue_strategy=None):
    """
    根据预测规则生成一组号码，并根据奇偶比和大小比进行筛选。
    这部分将是核心逻辑，需要根据 config.py 中的规则进行复杂的加权和筛选。
    blue_strategy: 蓝球预测策略 (例如 'hot', 'cold', 'balanced', 'trend')
    """
    current_app.logger.info(f"Attempting to generate predicted balls for {lottery_type}, odd/even={red_odd_even_ratio}, size={red_size_ratio}, blue_strategy={blue_strategy}.")
    
    red_range = PRIZE_RULES[lottery_type]['red_range']
    blue_range = PRIZE_RULES[lottery_type]['blue_range']

    num_red = 6 if lottery_type == 'ssq' else 5
    num_blue = 1 if lottery_type == 'ssq' else 2

    model_class = SSQDraw if lottery_type == 'ssq' else DLTDraw
    all_draws = model_class.query.order_by(model_class.issue.desc()).all()
    
    if not all_draws:
        current_app.logger.warning(f"No historical {lottery_type.upper()} data available for prediction. Returning random balls.")
        # 如果没有历史数据，则返回随机号码，并传递筛选条件
        random_result = generate_random_balls(lottery_type, num_red, num_blue, red_odd_even_ratio, red_size_ratio)
        if random_result:
            return {**random_result, 'attempts_made': 0, 'filtered_count': 0}
        return None

    latest_draw = all_draws[0]
    dummy_draw_issue = int(latest_draw.issue) + 1
    dummy_draw_date = date.today()

    max_attempts = 1000 # 增加尝试次数以找到符合条件的号码
    attempts_made = 0
    filtered_count = 0

    while attempts_made < max_attempts:
        attempts_made += 1
        
        # --- 蓝球预测逻辑 ---
        blue_probabilities = {ball: 1.0 for ball in range(1, blue_range + 1)}
        blue_stats_list, _ = calculate_frequency_and_omissions_for_balls(all_draws, blue_range, 'blue')
        sorted_blue_omissions = sorted(blue_stats_list, key=lambda x: x['current_omission'], reverse=True)
        sorted_blue_frequencies = sorted(blue_stats_list, key=lambda x: x['frequency_count'], reverse=True)

        # 根据策略调整蓝球概率
        if blue_strategy == 'hot': # 策略一：倾向于选择“热号”
            # 增加出现频率高的号码的权重
            for i, ball_data in enumerate(sorted_blue_frequencies):
                # 可以根据排名或频率值设置不同的权重
                blue_probabilities[ball_data['ball']] += (len(sorted_blue_frequencies) - i) * 0.1 
        elif blue_strategy == 'cold': # 策略二：关注“冷号回补”
            # 增加遗漏期数长的号码的权重
            for i, ball_data in enumerate(sorted_blue_omissions):
                blue_probabilities[ball_data['ball']] += ball_data['current_omission'] * 0.1
        elif blue_strategy == 'balanced': # 策略三：平衡冷热号分布
            # 结合频率和遗漏，例如，频率高的略微增加，遗漏长的也略微增加
            for ball_data in blue_stats_list:
                # 频率权重
                blue_probabilities[ball_data['ball']] += ball_data['frequency_percentage'] * 0.01
                # 遗漏权重
                blue_probabilities[ball_data['ball']] += ball_data['current_omission'] * 0.05
        elif blue_strategy == 'trend': # 策略四：结合遗漏值趋势分析
            # 这是一个更复杂的策略，可能需要分析遗漏值的变化趋势
            # 暂时先简单实现为：对当前遗漏值处于“中等”水平的号码给予更高权重，避免过冷或过热
            # 假设中等遗漏范围是总期数的 1/4 到 1/2
            total_draws_count = len(all_draws)
            if total_draws_count > 0:
                mid_omission_lower = total_draws_count // 4
                mid_omission_upper = total_draws_count // 2
                for ball_data in blue_stats_list:
                    if mid_omission_lower <= ball_data['current_omission'] <= mid_omission_upper:
                        blue_probabilities[ball_data['ball']] += 0.5 # 给予中等遗漏号码额外权重
        
        # 现有蓝球预测逻辑 (遗漏和重复)
        if lottery_type == 'ssq':
            num_omit_latest_blue = CURRENT_SETTINGS.get('ssq_blue_omit_latest_draws', 1)
            excluded_blue_balls = set()
            for i in range(min(num_omit_latest_blue, len(all_draws))):
                excluded_blue_balls.update(all_draws[i].get_blue_balls_list())
            for ball in excluded_blue_balls:
                if ball in blue_probabilities:
                    blue_probabilities[ball] = min(blue_probabilities[ball], 0.0) # 确保排除的号码概率为0

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
                        blue_probabilities[ball] = min(blue_probabilities[ball], ssq_blue_consecutive_5_prob)
                    elif consecutive_count >= 3:
                        blue_probabilities[ball] = min(blue_probabilities[ball], ssq_blue_consecutive_3_prob)
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
                    blue_probabilities[ball] = min(blue_probabilities[ball], dlt_blue_consecutive_5_prob)
        
        total_blue_prob = sum(blue_probabilities.values())
        if total_blue_prob == 0:
            current_app.logger.warning(f"All {lottery_type.upper()} blue balls have 0 probability. Resetting to uniform distribution.")
            blue_probabilities = {ball: 1.0 for ball in range(1, blue_range + 1)}
            total_blue_prob = sum(blue_probabilities.values())
        normalized_blue_probabilities = {ball: prob / total_blue_prob for ball, prob in blue_probabilities.items()}
        
        predicted_blue_balls = sorted(weighted_random_sample_without_replacement(
            list(normalized_blue_probabilities.keys()), 
            list(normalized_blue_probabilities.values()), 
            k=num_blue
        ))

        # --- 红球预测逻辑 ---
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

            ssq_red_omit_threshold_1 = CURRENT_SETTINGS.get('ssq_red_omit_threshold_1', 12)
            ssq_red_omit_threshold_2 = CURRENT_SETTINGS.get('ssq_red_omit_threshold_2', 13)
            ssq_red_omit_threshold_3 = CURRENT_SETTINGS.get('ssq_red_omit_threshold_3', 14)
            ssq_red_omit_prob_threshold_1 = CURRENT_SETTINGS.get('ssq_red_omit_prob_threshold_1', 0.015)
            ssq_red_omit_prob_threshold_2 = CURRENT_SETTINGS.get('ssq_red_omit_prob_threshold_2', 0.0)
            ssq_red_omit_prob_threshold_3 = CURRENT_SETTINGS.get('ssq_red_omit_prob_threshold_3', 0.0)

            for ball_data in red_omission_stats:
                ball = ball_data['ball']
                omission = ball_data['current_omission']
                if omission >= ssq_red_omit_threshold_3:
                    red_probabilities[ball] = ssq_red_omit_prob_threshold_3
                elif omission >= ssq_red_omit_threshold_2:
                    red_probabilities[ball] = ssq_red_omit_prob_threshold_2
                elif omission >= ssq_red_omit_threshold_1:
                    red_probabilities[ball] = ssq_red_omit_prob_threshold_1

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

            dlt_red_omit_threshold_1 = CURRENT_SETTINGS.get('dlt_red_omit_threshold_1', 12)
            dlt_red_omit_threshold_2 = CURRENT_SETTINGS.get('dlt_red_omit_threshold_2', 13)
            dlt_red_omit_threshold_3 = CURRENT_SETTINGS.get('dlt_red_omit_threshold_3', 14)
            dlt_red_omit_prob_threshold_1 = CURRENT_SETTINGS.get('dlt_red_omit_prob_threshold_1', 0.015)
            dlt_red_omit_prob_threshold_2 = CURRENT_SETTINGS.get('dlt_red_omit_prob_threshold_2', 0.0)
            dlt_red_omit_prob_threshold_3 = CURRENT_SETTINGS.get('dlt_red_omit_prob_threshold_3', 0.0)

            for ball_data in red_omission_stats:
                ball = ball_data['ball']
                omission = ball_data['current_omission']
                if omission >= dlt_red_omit_threshold_3:
                    red_probabilities[ball] = dlt_red_omit_prob_threshold_3
                elif omission >= dlt_red_omit_threshold_2:
                    red_probabilities[ball] = dlt_red_omit_prob_threshold_2
                elif omission >= dlt_red_omit_threshold_1:
                    red_probabilities[ball] = dlt_red_omit_prob_threshold_1
        
        total_red_prob = sum(red_probabilities.values())
        if total_red_prob == 0:
            current_app.logger.warning(f"All {lottery_type.upper()} red balls have 0 probability. Resetting to uniform distribution.")
            red_probabilities = {ball: 1.0 for ball in range(1, red_range + 1)}
            total_red_prob = sum(red_probabilities.values())
        normalized_red_probabilities = {ball: prob / total_red_prob for ball, prob in red_probabilities.items()}

        # 加权随机采样红球，并检查结构性约束和用户筛选条件
        try:
            predicted_red_balls = weighted_random_sample_without_replacement(
                list(normalized_red_probabilities.keys()), 
                list(normalized_red_probabilities.values()), 
                k=num_red
            )
        except ValueError as e:
            current_app.logger.error(f"Error during weighted_random_sample_without_replacement for {lottery_type.upper()} red balls: {e}")
            predicted_red_balls = sorted(random.sample(range(1, red_range + 1), num_red))
        
        # 检查规则 4.1.4/4.2.4 红球区域分布
        area_check_func = _check_ssq_rule_4_1_4_red_area_distribution if lottery_type == 'ssq' else _check_dlt_rule_4_2_4_red_area_distribution
        rule_area_passed = area_check_func(predicted_red_balls)['passed']
        
        # 检查规则 4.1.5/4.2.5 红球限重复数量
        repeat_check_func = _check_ssq_rule_4_1_5_red_repeat_previous_2 if lottery_type == 'ssq' else _check_dlt_rule_4_2_5_red_repeat_previous_2
        dummy_draw = model_class(issue=dummy_draw_issue, draw_date=dummy_draw_date, 
                                 red_balls=','.join(map(str, predicted_red_balls)), 
                                 blue_balls=','.join(map(str, predicted_blue_balls)))
        rule_repeat_passed = repeat_check_func(dummy_draw)['passed']

        # 检查规则 4.1.6/4.2.6 红球禁连续数字
        consecutive_check_func = _check_ssq_rule_4_1_6_red_consecutive_4_plus if lottery_type == 'ssq' else _check_dlt_rule_4_2_6_red_consecutive_4_plus
        rule_consecutive_passed = consecutive_check_func(predicted_red_balls)['passed']

        # 计算当前红球的奇偶比和大小比
        red_size_midpoint = CURRENT_SETTINGS.get('ssq_red_size_midpoint', 17) if lottery_type == 'ssq' else CURRENT_SETTINGS.get('dlt_front_size_midpoint', 18)
        current_red_odd_even_ratio = calculate_odd_even_ratio_per_draw(predicted_red_balls)
        current_red_size_ratio = calculate_size_ratio_per_draw(predicted_red_balls, red_size_midpoint)

        # 应用用户筛选条件
        user_filters_passed = True
        if red_odd_even_ratio and red_odd_even_ratio != "" and current_red_odd_even_ratio != red_odd_even_ratio:
            user_filters_passed = False
        if red_size_ratio and red_size_ratio != "" and current_red_size_ratio != red_size_ratio:
            user_filters_passed = False

        if rule_area_passed and rule_repeat_passed and rule_consecutive_passed and user_filters_passed:
            predicted_red_balls = sorted(predicted_red_balls)
            predicted_blue_balls = sorted(predicted_blue_balls)

            # 计算统计数据
            blue_size_midpoint = CURRENT_SETTINGS.get('ssq_blue_size_midpoint', 9) if lottery_type == 'ssq' else CURRENT_SETTINGS.get('dlt_back_size_midpoint', 7)
            stats = {
                'red_odd_even_ratio': current_red_odd_even_ratio,
                'red_sum': calculate_sum_per_draw(predicted_red_balls),
                'red_span': calculate_span_per_draw(predicted_red_balls),
                'red_size_ratio': current_red_size_ratio,
                'blue_odd_even_ratio': calculate_odd_even_ratio_per_draw(predicted_blue_balls),
                'blue_sum': calculate_sum_per_draw(predicted_blue_balls),
                'blue_span': calculate_span_per_draw(predicted_blue_balls),
                'blue_size_ratio': calculate_size_ratio_per_draw(predicted_blue_balls, blue_size_midpoint),
            }
            current_app.logger.info(f"Successfully generated predicted balls after {attempts_made} attempts: Red={predicted_red_balls}, Blue={predicted_blue_balls}, Stats={stats}")
            return {'red_balls': predicted_red_balls, 'blue_balls': predicted_blue_balls, 'stats': stats, 'attempts_made': attempts_made, 'filtered_count': filtered_count}
        else:
            filtered_count += 1 # 记录被规则或用户筛选掉的组合

    current_app.logger.warning(f"Max attempts ({max_attempts}) reached for predicted ball generation with filters. No suitable combination found.")
    return None # 达到最大尝试次数仍未找到符合条件的组合

def _get_latest_draw(model_class):
    """
    获取指定彩票类型的最新一期开奖数据。
    """
    return None # 达到最大尝试次数仍未找到符合条件的组合

def _get_latest_draw(model_class):
    """
    获取指定彩票类型的最新一期开奖数据。
    """
    return model_class.query.order_by(model_class.issue.desc()).first()

def get_omitted_balls_for_prediction(lottery_type, offset=0, blue_strategy=None):
    """
    获取遗漏最多的红球和蓝球，并包含其遗漏期数，用于预测页面显示。
    offset: 0表示最新一期，1表示上一期，以此类推。
    blue_strategy: 蓝球预测策略 (例如 'hot', 'cold', 'balanced', 'trend')
    返回格式: {'red_balls_with_omission': [{'ball': 1, 'omission': 10}, ...], 'issue': 2023123, 'max_offset': 5}
    """
    current_app.logger.info(f"Attempting to get omitted balls for {lottery_type} with offset {offset}, blue_strategy={blue_strategy}")

    model_class = SSQDraw if lottery_type == 'ssq' else DLTDraw
    red_ball_range = PRIZE_RULES[lottery_type]['red_range']
    blue_ball_range = PRIZE_RULES[lottery_type]['blue_range']

    all_draws = model_class.query.order_by(model_class.issue.desc()).all()
    
    current_app.logger.info(f"Found {len(all_draws)} historical draws for {lottery_type}.")

    if not all_draws:
        current_app.logger.warning(f"No historical data available for {lottery_type} to calculate omissions.")
        return {'error': 'No historical data available.'}

    max_offset = len(all_draws) - 1 # 最大偏移量，对应最老的一期数据
    
    if offset > max_offset:
        current_app.logger.warning(f"Requested offset {offset} exceeds max_offset {max_offset}. Adjusting to max_offset.")
        offset = max_offset
    
    # 获取用于计算遗漏的“当前期”数据
    # 实际上，我们是想看“在某一期开奖之后，哪些号码遗漏最多”
    # 所以，如果 offset=0，我们看最新一期开奖后的遗漏
    # 如果 offset=1，我们看倒数第二期开奖后的遗漏
    # 因此，用于计算遗漏的“历史数据”应该是从 all_draws[offset] 往后的所有数据
    
    current_draw_for_display = all_draws[offset]
    draws_for_omission_calculation = all_draws[offset:]

    current_issue = current_draw_for_display.issue

    # 计算红球遗漏
    red_stats_list, _ = calculate_frequency_and_omissions_for_balls(draws_for_omission_calculation, red_ball_range, 'red')
    # 按照当前遗漏期数降序排序
    sorted_red_omissions = sorted(red_stats_list, key=lambda x: x['current_omission'], reverse=True)
    
    # 获取遗漏最多的 N 个红球 (包含遗漏期数)
    num_omitted_red = CURRENT_SETTINGS.get('prediction_omitted_red_balls', 7)
    top_omitted_red_with_omission = sorted_red_omissions[:num_omitted_red]

    # 计算蓝球遗漏
    blue_stats_list, _ = calculate_frequency_and_omissions_for_balls(draws_for_omission_calculation, blue_ball_range, 'blue')
    # 按照当前遗漏期数降序排序
    sorted_blue_omissions = sorted(blue_stats_list, key=lambda x: x['current_omission'], reverse=True)
    
    # 获取遗漏最多的 N 个蓝球 (包含遗漏期数)
    num_omitted_blue = CURRENT_SETTINGS.get('prediction_omitted_blue_balls', 7)
    top_omitted_blue_with_omission = sorted_blue_omissions[:num_omitted_blue]

    current_app.logger.info(f"Omitted balls for {lottery_type} (issue {current_issue}, offset {offset}): Red={top_omitted_red_with_omission}, Blue={top_omitted_blue_with_omission}")

    return {
        'red_balls_with_omission': top_omitted_red_with_omission,
        'blue_balls_with_omission': top_omitted_blue_with_omission,
        'issue': current_issue,
        'max_offset': max_offset
    }

def get_draw_and_matched_omitted_balls_for_offset(lottery_type, current_display_offset=0, blue_strategy=None):
    """
    获取指定 offset 的开奖号码，以及该期开奖号码中与“其上一期”遗漏号码重合的号码。
    current_display_offset: 0表示最新一期，1表示上一期，以此类推。
    blue_strategy: 蓝球预测策略 (例如 'hot', 'cold', 'balanced', 'trend')
    """
    model_class = SSQDraw if lottery_type == 'ssq' else DLTDraw

    all_draws = model_class.query.order_by(model_class.issue.desc()).all()
    if not all_draws:
        return {'error': 'No historical data available.'}

    # 确保 offset 在有效范围内
    if current_display_offset >= len(all_draws):
        current_app.logger.warning(f"Requested current_display_offset {current_display_offset} exceeds available draws. Adjusting to latest.")
        current_display_offset = 0 # 默认显示最新一期

    # 1. 获取当前显示期号的开奖号码 (本期号码)
    current_draw_for_display = all_draws[current_display_offset]
    display_red_balls = set(current_draw_for_display.get_red_balls_list())
    display_blue_balls = set(current_draw_for_display.get_blue_balls_list())

    # 2. 获取“当前显示期号的上一期”的遗漏最多的号码 (offset = current_display_offset + 1)
    # 确保有足够的数据来获取上一期的遗漏
    previous_omitted_red_balls = []
    previous_omitted_blue_balls = []
    if (current_display_offset + 1) < len(all_draws):
        previous_omitted_data = get_omitted_balls_for_prediction(lottery_type, offset=current_display_offset + 1, blue_strategy=blue_strategy)
        if 'error' in previous_omitted_data:
            current_app.logger.warning(f"Could not retrieve previous omitted balls for {lottery_type} at offset {current_display_offset + 1}: {previous_omitted_data['error']}")
        else:
            previous_omitted_red_balls_with_omission = previous_omitted_data['red_balls_with_omission']
            previous_omitted_blue_balls_with_omission = previous_omitted_data['blue_balls_with_omission']
            
            # Create dictionaries for quick lookup of omission counts
            previous_omitted_red_map = {item['ball']: item['current_omission'] for item in previous_omitted_red_balls_with_omission}
            previous_omitted_blue_map = {item['ball']: item['current_omission'] for item in previous_omitted_blue_balls_with_omission}
    else:
        previous_omitted_red_map = {}
        previous_omitted_blue_map = {}

    # 3. 比较当前显示期号的号码与“其上一期”遗漏最多的号码，并包含遗漏期数
    matched_red_balls_with_omission = []
    for ball in sorted(list(display_red_balls)):
        if ball in previous_omitted_red_map:
            matched_red_balls_with_omission.append({'ball': ball, 'current_omission': previous_omitted_red_map[ball]})
    
    matched_blue_balls_with_omission = []
    for ball in sorted(list(display_blue_balls)):
        if ball in previous_omitted_blue_map:
            matched_blue_balls_with_omission.append({'ball': ball, 'current_omission': previous_omitted_blue_map[ball]})

    return {
        'display_red_balls': sorted(list(display_red_balls)),
        'display_blue_balls': sorted(list(display_blue_balls)),
        'matched_red_balls': matched_red_balls_with_omission, # Now includes omission count
        'matched_blue_balls': matched_blue_balls_with_omission, # Now includes omission count
        'display_issue': current_draw_for_display.issue, # 返回当前显示期号
        'display_draw_date': current_draw_for_display.draw_date.strftime('%Y-%m-%d') # 返回当前显示期号的日期
    }


def generate_complex_prediction_balls(lottery_type: str, red_count: int, blue_count: int, blue_strategy=None):
    """
    根据预测规则生成一组复式号码。
    复用 generate_predicted_balls 的概率计算逻辑，但根据 red_count 和 blue_count 采样。
    blue_strategy: 蓝球预测策略 (例如 'hot', 'cold', 'balanced', 'trend')
    """
    current_app.logger.info(f"Attempting to generate complex prediction balls for {lottery_type}: red_count={red_count}, blue_count={blue_count}, blue_strategy={blue_strategy}")

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
    blue_stats_list, _ = calculate_frequency_and_omissions_for_balls(all_draws, blue_range, 'blue')
    sorted_blue_omissions = sorted(blue_stats_list, key=lambda x: x['current_omission'], reverse=True)
    sorted_blue_frequencies = sorted(blue_stats_list, key=lambda x: x['frequency_count'], reverse=True)

    # 根据策略调整蓝球概率
    if blue_strategy == 'hot': # 策略一：倾向于选择“热号”
        for i, ball_data in enumerate(sorted_blue_frequencies):
            blue_probabilities[ball_data['ball']] += (len(sorted_blue_frequencies) - i) * 0.1 
    elif blue_strategy == 'cold': # 策略二：关注“冷号回补”
        for i, ball_data in enumerate(sorted_blue_omissions):
            blue_probabilities[ball_data['ball']] += ball_data['current_omission'] * 0.1
    elif blue_strategy == 'balanced': # 策略三：平衡冷热号分布
        for ball_data in blue_stats_list:
            blue_probabilities[ball_data['ball']] += ball_data['frequency_percentage'] * 0.01
            blue_probabilities[ball_data['ball']] += ball_data['current_omission'] * 0.05
    elif blue_strategy == 'trend': # 策略四：结合遗漏值趋势分析
        total_draws_count = len(all_draws)
        if total_draws_count > 0:
            mid_omission_lower = total_draws_count // 4
            mid_omission_upper = total_draws_count // 2
            for ball_data in blue_stats_list:
                if mid_omission_lower <= ball_data['current_omission'] <= mid_omission_upper:
                    blue_probabilities[ball_data['ball']] += 0.5 
    
    # 现有蓝球预测逻辑 (遗漏和重复)
    if lottery_type == 'ssq':
        num_omit_latest_blue = CURRENT_SETTINGS.get('ssq_blue_omit_latest_draws', 1)
        excluded_blue_balls = set()
        for i in range(min(num_omit_latest_blue, len(all_draws))):
            excluded_blue_balls.update(all_draws[i].get_blue_balls_list())
        for ball in excluded_blue_balls:
            if ball in blue_probabilities:
                blue_probabilities[ball] = min(blue_probabilities[ball], 0.0) 

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
                    blue_probabilities[ball] = min(blue_probabilities[ball], ssq_blue_consecutive_5_prob)
                elif consecutive_count >= 3:
                    blue_probabilities[ball] = min(blue_probabilities[ball], ssq_blue_consecutive_3_prob)
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
                blue_probabilities[ball] = min(blue_probabilities[ball], dlt_blue_consecutive_5_prob)
    
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
                
                # 计算统计数据
                red_size_midpoint = CURRENT_SETTINGS.get('ssq_red_size_midpoint', 17)
                blue_size_midpoint = CURRENT_SETTINGS.get('ssq_blue_size_midpoint', 9)

                stats = {
                    'red_odd_even_ratio': calculate_odd_even_ratio_per_draw(predicted_red_balls),
                    'red_sum': calculate_sum_per_draw(predicted_red_balls),
                    'red_span': calculate_span_per_draw(predicted_red_balls),
                    'red_size_ratio': calculate_size_ratio_per_draw(predicted_red_balls, red_size_midpoint),
                    'blue_odd_even_ratio': calculate_odd_even_ratio_per_draw(predicted_blue_balls),
                    'blue_sum': calculate_sum_per_draw(predicted_blue_balls),
                    'blue_span': calculate_span_per_draw(predicted_blue_balls),
                    'blue_size_ratio': calculate_size_ratio_per_draw(predicted_blue_balls, blue_size_midpoint),
                }
                return {'red_balls': predicted_red_balls, 'blue_balls': predicted_blue_balls, 'stats': stats}

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
                
                # 计算统计数据
                red_size_midpoint = CURRENT_SETTINGS.get('dlt_front_size_midpoint', 18)
                blue_size_midpoint = CURRENT_SETTINGS.get('dlt_back_size_midpoint', 7)

                stats = {
                    'red_odd_even_ratio': calculate_odd_even_ratio_per_draw(predicted_red_balls),
                    'red_sum': calculate_sum_per_draw(predicted_red_balls),
                    'red_span': calculate_span_per_draw(predicted_red_balls),
                    'red_size_ratio': calculate_size_ratio_per_draw(predicted_red_balls, red_size_midpoint),
                    'blue_odd_even_ratio': calculate_odd_even_ratio_per_draw(predicted_blue_balls),
                    'blue_sum': calculate_sum_per_draw(predicted_blue_balls),
                    'blue_span': calculate_span_per_draw(predicted_blue_balls),
                    'blue_size_ratio': calculate_size_ratio_per_draw(predicted_blue_balls, blue_size_midpoint),
                }
                return {'red_balls': predicted_red_balls, 'blue_balls': predicted_blue_balls, 'stats': stats}
        
        if attempt == max_attempts - 1:
            current_app.logger.warning(f"Max attempts reached for {lottery_type.upper()} complex ball generation, some structural rules might not be met. Returning None.")
            return None
    
    return None # 如果达到最大尝试次数仍未找到符合规则的组合

def calculate_red_ball_trends(draws_list, lottery_type):
    """
    计算所有红球趋势指标。
    draws_list: 降序排列的开奖数据列表 (最新在前面)
    lottery_type: 'ssq' 或 'dlt'
    """
    if not draws_list:
        return {'error': 'No historical data available for trend calculation.'}

    red_ball_range = PRIZE_RULES[lottery_type]['red_range']
    
    # 获取配置参数
    if lottery_type == 'ssq':
        red_size_midpoint = CURRENT_SETTINGS.get('ssq_red_size_midpoint', 17)
        red_area_ranges = CURRENT_SETTINGS.get('ssq_red_area_ranges', [(1,8), (9,16), (17,24), (25,33)])
    else: # dlt
        red_size_midpoint = CURRENT_SETTINGS.get('dlt_front_size_midpoint', 18)
        red_area_ranges = CURRENT_SETTINGS.get('dlt_front_area_ranges', [(1,8), (9,16), (17,24), (25,35)])

    # 获取最新一期的红球
    latest_red_balls = draws_list[0].get_red_balls_list() if draws_list else []

    trends = {}

    # 4.1 奇偶比
    trends['odd_even_ratio'] = calculate_odd_even_ratio_per_draw(latest_red_balls)

    # 4.2 连号出现的概率 (这里计算的是历史连号的频率)
    trends['consecutive_trend_over_draws'] = calculate_consecutive_trend_over_draws(draws_list, 'red')

    # 4.3 余数相同数量 (基数可配置，例如除3余数)
    remainder_divisor = CURRENT_SETTINGS.get(f'{lottery_type}_red_remainder_divisor', 3)
    trends['remainder_group_counts'] = calculate_remainder_group_counts_per_draw(latest_red_balls, remainder_divisor)

    # 4.4 多期号码重复 (N 可配置)
    multi_draw_repeat_periods = CURRENT_SETTINGS.get(f'{lottery_type}_red_multi_draw_repeat_periods', 5)
    trends['multi_draw_repeat_balls'] = calculate_multi_draw_repeat_balls(draws_list, multi_draw_repeat_periods, 'red')

    # 4.5 红球大小比 (界限可配置)
    trends['size_ratio'] = calculate_size_ratio_per_draw(latest_red_balls, red_size_midpoint)

    # 4.6 红球质合比
    trends['prime_composite_ratio'] = calculate_prime_composite_ratio_per_draw(latest_red_balls)

    # 4.7 红球斜连号/跳号
    diagonal_skip_lookback = CURRENT_SETTINGS.get(f'{lottery_type}_red_diagonal_skip_lookback', 5)
    trends['diagonal_skip_numbers'] = calculate_diagonal_skip_numbers(draws_list, 'red', diagonal_skip_lookback)

    # 4.8 红球和值与均值
    trends['sum'] = calculate_sum_per_draw(latest_red_balls)
    trends['mean'] = calculate_mean_per_draw(latest_red_balls)

    # 4.9 红球跨度
    trends['span'] = calculate_span_per_draw(latest_red_balls)

    # 4.10 红球分区分布 (分区范围可配置)
    trends['area_distribution'] = calculate_red_ball_area_distribution_per_draw(latest_red_balls, red_area_ranges)

    # 4.11 红球遗漏值分析 (使用 calculate_frequency_and_omissions_for_balls 结果)
    red_stats_list, _ = calculate_frequency_and_omissions_for_balls(draws_list, red_ball_range, 'red')
    trends['omission_analysis'] = sorted(red_stats_list, key=lambda x: x['current_omission'], reverse=True)

    return trends

def calculate_blue_ball_trends(draws_list, lottery_type):
    """
    计算所有蓝球趋势指标。
    draws_list: 降序排列的开奖数据列表 (最新在前面)
    lottery_type: 'ssq' 或 'dlt'
    """
    if not draws_list:
        return {'error': 'No historical data available for trend calculation.'}

    blue_ball_range = PRIZE_RULES[lottery_type]['blue_range']
    
    # 获取配置参数
    if lottery_type == 'ssq':
        blue_size_midpoint = CURRENT_SETTINGS.get('ssq_blue_size_midpoint', 9)
    else: # dlt
        blue_size_midpoint = CURRENT_SETTINGS.get('dlt_back_size_midpoint', 7)

    # 获取最新一期的蓝球
    latest_blue_balls = draws_list[0].get_blue_balls_list() if draws_list else []

    trends = {}

    # 蓝球遗漏值分析
    blue_stats_list, _ = calculate_frequency_and_omissions_for_balls(draws_list, blue_ball_range, 'blue')
    trends['omission_analysis'] = sorted(blue_stats_list, key=lambda x: x['current_omission'], reverse=True)

    # 蓝球重复值计算 (多期号码重复)
    multi_draw_repeat_periods = CURRENT_SETTINGS.get(f'{lottery_type}_blue_multi_draw_repeat_periods', 5)
    trends['multi_draw_repeat_balls'] = calculate_multi_draw_repeat_balls(draws_list, multi_draw_repeat_periods, 'blue')

    if lottery_type == 'dlt':
        # 大乐透蓝球特有指标
        trends['odd_even_ratio'] = calculate_odd_even_ratio_per_draw(latest_blue_balls)
        trends['size_ratio'] = calculate_size_ratio_per_draw(latest_blue_balls, blue_size_midpoint)
        trends['prime_composite_ratio'] = calculate_prime_composite_ratio_per_draw(latest_blue_balls)
        trends['sum'] = calculate_sum_per_draw(latest_blue_balls)
        trends['mean'] = calculate_mean_per_draw(latest_blue_balls)
        trends['span'] = calculate_span_per_draw(latest_blue_balls)
        trends['consecutive_trend_over_draws'] = calculate_consecutive_trend_over_draws(draws_list, 'blue')
        diagonal_skip_lookback = CURRENT_SETTINGS.get(f'{lottery_type}_blue_diagonal_skip_lookback', 5)
        trends['diagonal_skip_numbers'] = calculate_diagonal_skip_numbers(draws_list, 'blue', diagonal_skip_lookback)

    return trends
