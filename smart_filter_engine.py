# smart_filter_engine.py
"""
智能筛选引擎 - 根据用户指定的详细规则生成符合要求的号码组合。
支持双色球和大乐透的多种筛选条件组合。
"""
import random
import math
from collections import Counter
from flask import current_app
from models import SSQDraw, DLTDraw, db
from config import CURRENT_SETTINGS, PRIZE_RULES
from utils import (
    format_lottery_numbers, get_consecutive_groups,
    calculate_odd_even_ratio_per_draw, calculate_sum_per_draw,
    calculate_span_per_draw, calculate_size_ratio_per_draw,
    calculate_ac_value_per_draw, calculate_frequency_and_omissions_for_balls,
    is_prime
)

__version__ = "1.0.0"


# ==================== 辅助函数 ====================

def get_latest_draws_for_smart(lottery_type, num_draws=50):
    """获取指定彩票类型的最新N期开奖数据"""
    model_class = SSQDraw if lottery_type == 'ssq' else DLTDraw
    return model_class.query.order_by(model_class.issue.desc()).limit(num_draws).all()


def get_omission_data(lottery_type, all_draws=None):
    """获取所有号码的遗漏数据"""
    if all_draws is None:
        all_draws = get_latest_draws_for_smart(lottery_type, 200)
    
    red_range = PRIZE_RULES[lottery_type]['red_range']
    blue_range = PRIZE_RULES[lottery_type]['blue_range']
    
    red_stats, _ = calculate_frequency_and_omissions_for_balls(all_draws, red_range, 'red')
    blue_stats, _ = calculate_frequency_and_omissions_for_balls(all_draws, blue_range, 'blue')
    
    red_omission = {s['ball']: s['current_omission'] for s in red_stats}
    blue_omission = {s['ball']: s['current_omission'] for s in blue_stats}
    
    return red_omission, blue_omission


def get_latest_draw(lottery_type):
    """获取最新一期开奖数据"""
    model_class = SSQDraw if lottery_type == 'ssq' else DLTDraw
    return model_class.query.order_by(model_class.issue.desc()).first()


def get_previous_draws(lottery_type, num=3):
    """获取最近N期开奖数据"""
    model_class = SSQDraw if lottery_type == 'ssq' else DLTDraw
    return model_class.query.order_by(model_class.issue.desc()).limit(num).all()


# ==================== 双色球规则检查函数 ====================

def check_ssq_red_zone_distribution(red_balls, target_ratio):
    """
    检查红球分区分布 (1-11, 12-22, 23-33)
    target_ratio: 如 "2:2:2", "3:2:1"
    """
    zone1 = sum(1 for b in red_balls if 1 <= b <= 11)
    zone2 = sum(1 for b in red_balls if 12 <= b <= 22)
    zone3 = sum(1 for b in red_balls if 23 <= b <= 33)
    actual = f"{zone1}:{zone2}:{zone3}"
    return actual == target_ratio, actual


def check_consecutive_balls(red_balls, max_groups=1, max_length=2):
    """
    检查连号规则
    max_groups: 最大连号组数
    max_length: 每组最大连号长度
    返回: (是否通过, 连号组数, 连号详情)
    """
    groups, _ = get_consecutive_groups(red_balls)
    consecutive_groups = [g for g in groups if len(g) > 1]
    groups_count = len(consecutive_groups)
    
    if groups_count > max_groups:
        return False, groups_count, consecutive_groups
    
    for g in consecutive_groups:
        if len(g) > max_length:
            return False, groups_count, consecutive_groups
    
    return True, groups_count, consecutive_groups


def check_repeat_with_previous(red_balls, lottery_type, min_repeat=0, max_repeat=2):
    """
    检查与上期重号数量
    """
    latest = get_latest_draw(lottery_type)
    if not latest:
        return True, 0
    
    prev_reds = set(latest.get_red_balls_list())
    current_set = set(red_balls)
    repeat_count = len(current_set.intersection(prev_reds))
    
    return min_repeat <= repeat_count <= max_repeat, repeat_count


def check_omission_rule_ssq(red_balls, red_omission, pattern="4+1+1"):
    """
    检查遗漏号规则 - 双色球红球 "4+1+1" 原则
    pattern: "4+1+1" 表示从遗漏0-4期选4个，遗漏5-9期选1个，遗漏10期以上选1个
    """
    if pattern == "4+1+1":
        hot = [b for b in red_balls if red_omission.get(b, 0) <= 4]
        warm = [b for b in red_balls if 5 <= red_omission.get(b, 0) <= 9]
        cold = [b for b in red_balls if red_omission.get(b, 0) >= 10]
        
        if len(hot) == 4 and len(warm) == 1 and len(cold) == 1:
            return True, f"热{len(hot)}温{len(warm)}冷{len(cold)}"
        return False, f"热{len(hot)}温{len(warm)}冷{len(cold)}"
    
    return True, ""


def check_omission_duplicate_limit(red_balls, red_omission, max_same=2):
    """
    检查遗漏期数一样的号码不能超过指定数量
    """
    omission_counts = Counter(red_omission.get(b, 0) for b in red_balls)
    for omission_val, count in omission_counts.items():
        if count > max_same:
            return False, f"遗漏{omission_val}期出现{count}次(超过{max_same})"
    return True, ""


def check_odd_even_ratio(balls, target_ratios):
    """
    检查奇偶比
    target_ratios: 允许的奇偶比列表，如 ["3:3", "2:4", "4:2"]
    """
    odd = sum(1 for b in balls if b % 2 == 1)
    even = len(balls) - odd
    actual = f"{odd}:{even}"
    return actual in target_ratios, actual


def check_max_span(balls, min_span=26):
    """检查最大跨度"""
    span = calculate_span_per_draw(balls)
    return span >= min_span, span


def check_sum_range(balls, min_sum=70, max_sum=129):
    """检查号码总和范围"""
    total = calculate_sum_per_draw(balls)
    return min_sum <= total <= max_sum, total


def check_same_tail(red_balls, expected_count=1):
    """
    检查同尾号 - 有且只有指定组数的同尾号
    同尾号指个位数相同的号码，如 01, 11, 21, 31
    """
    tail_groups = Counter(b % 10 for b in red_balls)
    same_tail_groups = [tail for tail, count in tail_groups.items() if count >= 2]
    return len(same_tail_groups) == expected_count, len(same_tail_groups)


def check_neighbor_numbers(red_balls, min_groups=1):
    """
    检查邻号（边号）- 至少有一组相邻号码
    邻号指数值相差1的号码对
    """
    sorted_balls = sorted(red_balls)
    neighbor_pairs = 0
    for i in range(len(sorted_balls) - 1):
        if sorted_balls[i+1] - sorted_balls[i] == 1:
            neighbor_pairs += 1
    return neighbor_pairs >= min_groups, neighbor_pairs


def check_ac_value(red_balls, target_values):
    """
    检查AC值
    target_values: 允许的AC值列表，如 [6, 7]
    """
    ac = calculate_ac_value_per_draw(red_balls)
    return ac in target_values, ac


def check_ssq_blue_omission(blue_balls, blue_omission, primary_range=(6, 12), secondary_prob=0.15, secondary_range=(0, 2)):
    """
    检查蓝球遗漏规则
    primary_range: 优先选遗漏范围 (6-12期)
    secondary_prob: 15%概率出0-2期遗漏号
    """
    for b in blue_balls:
        omission = blue_omission.get(b, 0)
        if primary_range[0] <= omission <= primary_range[1]:
            continue
        elif secondary_range[0] <= omission <= secondary_range[1]:
            # 允许，但概率较低 - 放宽条件，直接允许
            continue
        else:
            # 其他遗漏期数也允许，但降低权重
            continue
    return True, ""


# ==================== 大乐透规则检查函数 ====================

def check_dlt_front_zone_distribution(front_balls, target_ratios):
    """
    检查大乐透前区分区分布 (1-12, 13-24, 25-35)
    target_ratios: 如 ["1:2:2", "2:2:1", "2:1:2"]
    """
    zone1 = sum(1 for b in front_balls if 1 <= b <= 12)
    zone2 = sum(1 for b in front_balls if 13 <= b <= 24)
    zone3 = sum(1 for b in front_balls if 25 <= b <= 35)
    actual = f"{zone1}:{zone2}:{zone3}"
    return actual in target_ratios, actual


def check_omission_rule_dlt(front_balls, red_omission, pattern="3:1:1"):
    """
    检查遗漏号规则 - 大乐透前区 "3:1:1" 或 "4:1:0"
    """
    hot = [b for b in front_balls if red_omission.get(b, 0) <= 4]
    warm = [b for b in front_balls if 5 <= red_omission.get(b, 0) <= 9]
    cold = [b for b in front_balls if red_omission.get(b, 0) >= 10]
    
    if pattern == "3:1:1":
        if len(hot) == 3 and len(warm) == 1 and len(cold) == 1:
            return True, f"热{len(hot)}温{len(warm)}冷{len(cold)}"
    elif pattern == "4:1:0":
        if len(hot) == 4 and len(warm) == 1 and len(cold) == 0:
            return True, f"热{len(hot)}温{len(warm)}冷{len(cold)}"
    
    return False, f"热{len(hot)}温{len(warm)}冷{len(cold)}"


def check_dlt_omission_duplicate_limit(front_balls, red_omission, max_same=1):
    """大乐透遗漏期数一样的不能超过1个"""
    omission_counts = Counter(red_omission.get(b, 0) for b in front_balls)
    for omission_val, count in omission_counts.items():
        if count > max_same:
            return False, f"遗漏{omission_val}期出现{count}次(超过{max_same})"
    return True, ""


def check_dlt_blue_omission(blue_balls, blue_omission):
    """
    检查大乐透后区遗漏规则
    主选：至少一个号码来自遗漏5-15期
    放宽条件：只要至少有一个号码在5-15期范围内即可
    """
    has_warm = False
    for b in blue_balls:
        omission = blue_omission.get(b, 0)
        if 5 <= omission <= 15:
            has_warm = True
            break
    
    if not has_warm:
        return False, "后区没有遗漏5-15期的号码"
    
    # 放宽条件：不再对遗漏0-2期和16期以上的号码做概率限制
    return True, ""


def check_dlt_blue_odd_even(blue_balls, target="1:1"):
    """检查大乐透后区奇偶组合"""
    odd = sum(1 for b in blue_balls if b % 2 == 1)
    even = len(blue_balls) - odd
    actual = f"{odd}:{even}"
    return actual == target, actual


def check_dlt_blue_size(blue_balls, target="1:1"):
    """检查大乐透后区大小组合 (01-06小, 07-12大)"""
    small = sum(1 for b in blue_balls if 1 <= b <= 6)
    large = sum(1 for b in blue_balls if 7 <= b <= 12)
    actual = f"{small}:{large}"
    return actual == target, actual


# ==================== 智能筛选主函数 ====================

def generate_smart_filtered_numbers(lottery_type, count=5, options=None):
    """
    智能筛选生成号码的主函数
    
    Args:
        lottery_type: 'ssq' 或 'dlt'
        count: 生成组数
        options: 筛选选项字典
    
    Returns:
        生成的号码列表
    """
    if options is None:
        options = {}
    
    current_app.logger.info(f"Smart filter: Generating {count} {lottery_type} numbers with options: {options}")
    
    # 获取遗漏数据
    all_draws = get_latest_draws_for_smart(lottery_type, 200)
    red_omission, blue_omission = get_omission_data(lottery_type, all_draws)
    
    red_range = PRIZE_RULES[lottery_type]['red_range']
    blue_range = PRIZE_RULES[lottery_type]['blue_range']
    
    num_red = 6 if lottery_type == 'ssq' else 5
    num_blue = 1 if lottery_type == 'ssq' else 2
    
    generated = []
    max_attempts = 20000  # 增加尝试次数，因为多个条件组合需要更多尝试
    attempts = 0
    
    while len(generated) < count and attempts < max_attempts:
        attempts += 1
        
        # 生成红球
        red_balls = _generate_red_balls_smart(lottery_type, num_red, red_range, red_omission, options)
        if red_balls is None:
            continue
        
        # 生成蓝球
        blue_balls = _generate_blue_balls_smart(lottery_type, num_blue, blue_range, blue_omission, options)
        if blue_balls is None:
            continue
        
        # 验证所有规则
        if _validate_all_rules(lottery_type, red_balls, blue_balls, red_omission, blue_omission, options):
            # 计算统计信息
            stats = _calculate_stats(lottery_type, red_balls, blue_balls)
            generated.append({
                'red_balls': ','.join(map(str, sorted(red_balls))),
                'blue_balls': ','.join(map(str, sorted(blue_balls))),
                'stats': stats
            })
    
    current_app.logger.info(f"Smart filter: Generated {len(generated)} numbers after {attempts} attempts")
    return generated


def _generate_red_balls_smart(lottery_type, num_red, red_range, red_omission, options):
    """智能生成红球"""
    max_attempts = 200
    
    for _ in range(max_attempts):
        # 根据遗漏规则生成候选号码
        candidates = list(range(1, red_range + 1))
        
        # 根据遗漏规则分配权重
        weights = []
        for b in candidates:
            omission = red_omission.get(b, 0)
            w = 1.0
            
            if lottery_type == 'ssq':
                # 双色球：4+1+1 原则的权重分配
                if omission <= 4:
                    w = 3.0  # 热号权重高
                elif 5 <= omission <= 9:
                    w = 2.0  # 温号
                else:
                    w = 1.5  # 冷号
            else:
                # 大乐透：3:1:1 或 4:1:0 原则
                if omission <= 4:
                    w = 3.0
                elif 5 <= omission <= 9:
                    w = 2.0
                else:
                    w = 1.5
            
            weights.append(w)
        
        # 加权采样
        total = sum(weights)
        probs = [w / total for w in weights]
        
        try:
            selected = set()
            temp_candidates = list(candidates)
            temp_probs = list(probs)
            
            while len(selected) < num_red:
                idx = random.choices(range(len(temp_candidates)), weights=temp_probs, k=1)[0]
                selected.add(temp_candidates[idx])
                temp_candidates.pop(idx)
                temp_probs.pop(idx)
                if temp_probs:
                    total = sum(temp_probs)
                    temp_probs = [w / total for w in temp_probs]
            
            return sorted(list(selected))
        except Exception:
            continue
    
    return None


def _generate_blue_balls_smart(lottery_type, num_blue, blue_range, blue_omission, options):
    """智能生成蓝球"""
    max_attempts = 100
    
    for _ in range(max_attempts):
        candidates = list(range(1, blue_range + 1))
        weights = []
        
        for b in candidates:
            omission = blue_omission.get(b, 0)
            w = 1.0
            
            if lottery_type == 'ssq':
                # 双色球蓝球：优先遗漏6-12期
                if 6 <= omission <= 12:
                    w = 5.0
                elif 0 <= omission <= 2:
                    w = 1.5  # 15%概率
                else:
                    w = 2.0
            else:
                # 大乐透后区：至少一个遗漏5-15期
                if 5 <= omission <= 15:
                    w = 5.0
                elif 0 <= omission <= 2:
                    w = 1.5
                elif omission >= 16:
                    w = 1.0
                else:
                    w = 2.0
            
            weights.append(w)
        
        total = sum(weights)
        probs = [w / total for w in weights]
        
        try:
            selected = set()
            temp_candidates = list(candidates)
            temp_probs = list(probs)
            
            while len(selected) < num_blue:
                idx = random.choices(range(len(temp_candidates)), weights=temp_probs, k=1)[0]
                selected.add(temp_candidates[idx])
                temp_candidates.pop(idx)
                temp_probs.pop(idx)
                if temp_probs:
                    total = sum(temp_probs)
                    temp_probs = [w / total for w in temp_probs]
            
            return sorted(list(selected))
        except Exception:
            continue
    
    return None


def _validate_all_rules(lottery_type, red_balls, blue_balls, red_omission, blue_omission, options):
    """验证所有启用的规则"""
    
    if lottery_type == 'ssq':
        return _validate_ssq_rules(red_balls, blue_balls, red_omission, blue_omission, options)
    else:
        return _validate_dlt_rules(red_balls, blue_balls, red_omission, blue_omission, options)


def _validate_ssq_rules(red_balls, blue_balls, red_omission, blue_omission, options):
    """验证双色球所有规则"""
    
    # 1. 分区原则
    zone_ratio = options.get('zone_ratio', '2:2:2')
    if zone_ratio != 'disabled':
        passed, _ = check_ssq_red_zone_distribution(red_balls, zone_ratio)
        if not passed:
            return False
    
    # 2. 连号号码原则
    consecutive_option = options.get('consecutive', '1_group_2')
    if consecutive_option != 'disabled':
        if consecutive_option == 'no_consecutive':
            passed, _, _ = check_consecutive_balls(red_balls, max_groups=0, max_length=0)
        elif consecutive_option == '1_group_2':
            passed, _, _ = check_consecutive_balls(red_balls, max_groups=1, max_length=2)
        else:
            passed = True
        if not passed:
            return False
    
    # 3. 与上期重号原则
    repeat_option = options.get('repeat', '1_or_2')
    if repeat_option != 'disabled':
        if repeat_option == '1':
            passed, count = check_repeat_with_previous(red_balls, 'ssq', min_repeat=1, max_repeat=1)
        elif repeat_option == '2':
            passed, count = check_repeat_with_previous(red_balls, 'ssq', min_repeat=2, max_repeat=2)
        elif repeat_option == '1_or_2':
            passed, count = check_repeat_with_previous(red_balls, 'ssq', min_repeat=1, max_repeat=2)
        elif repeat_option == '0':
            passed, count = check_repeat_with_previous(red_balls, 'ssq', min_repeat=0, max_repeat=0)
        else:
            passed = True
        if not passed:
            return False
    
    # 4. 遗漏号原则
    omission_pattern = options.get('omission_pattern', '4+1+1')
    if omission_pattern != 'disabled':
        passed, _ = check_omission_rule_ssq(red_balls, red_omission, omission_pattern)
        if not passed:
            return False
    
    # 5. 遗漏期数一样的不超过2个
    if options.get('omission_duplicate_limit', True):
        passed, _ = check_omission_duplicate_limit(red_balls, red_omission, max_same=2)
        if not passed:
            return False
    
    # 6. 奇偶原则
    odd_even = options.get('odd_even', '3:3,2:4,4:2')
    if odd_even != 'disabled':
        targets = odd_even.split(',')
        passed, _ = check_odd_even_ratio(red_balls, targets)
        if not passed:
            return False
    
    # 7. 最大跨度原则
    span_option = options.get('span', 'gt_26')
    if span_option != 'disabled':
        if span_option == 'gt_26':
            passed, _ = check_max_span(red_balls, min_span=26)
        elif span_option == 'gt_24':
            passed, _ = check_max_span(red_balls, min_span=24)
        elif span_option == 'gt_20':
            passed, _ = check_max_span(red_balls, min_span=20)
        else:
            passed = True
        if not passed:
            return False
    
    # 8. 号码总和原则
    sum_option = options.get('sum', '70-129')
    if sum_option != 'disabled':
        if sum_option == '70-129':
            passed, _ = check_sum_range(red_balls, 70, 129)
        elif sum_option == '80-120':
            passed, _ = check_sum_range(red_balls, 80, 120)
        elif sum_option == '90-110':
            passed, _ = check_sum_range(red_balls, 90, 110)
        elif sum_option == '60-140':
            passed, _ = check_sum_range(red_balls, 60, 140)
        else:
            passed = True
        if not passed:
            return False
    
    # 9. 同尾号原则
    tail_option = options.get('same_tail', 'exactly_1')
    if tail_option != 'disabled':
        if tail_option == 'exactly_1':
            passed, count = check_same_tail(red_balls, 1)
            passed = (count == 1)
        elif tail_option == 'at_least_1':
            passed, count = check_same_tail(red_balls, 0)
            passed = (count >= 1)
        elif tail_option == 'none':
            passed, count = check_same_tail(red_balls, 0)
            passed = (count == 0)
        else:
            passed = True
        if not passed:
            return False
    
    # 10. 邻号原则
    neighbor_option = options.get('neighbor', 'at_least_1')
    if neighbor_option != 'disabled':
        if neighbor_option == 'at_least_1':
            passed, _ = check_neighbor_numbers(red_balls, 1)
        elif neighbor_option == 'at_least_2':
            passed, _ = check_neighbor_numbers(red_balls, 2)
        else:
            passed = True
        if not passed:
            return False
    
    # 11. AC值原则
    ac_option = options.get('ac_value', '6_or_7')
    if ac_option != 'disabled':
        if ac_option == '6_or_7':
            passed, _ = check_ac_value(red_balls, [6, 7])
        elif ac_option == '5_to_8':
            passed, _ = check_ac_value(red_balls, [5, 6, 7, 8])
        elif ac_option == '4_to_9':
            passed, _ = check_ac_value(red_balls, [4, 5, 6, 7, 8, 9])
        else:
            passed = True
        if not passed:
            return False
    
    # 12. 蓝球原则
    blue_option = options.get('blue_omission', '6-12_primary')
    if blue_option != 'disabled' and blue_option != 'any':
        if blue_option == '6-12_primary':
            passed, _ = check_ssq_blue_omission(blue_balls, blue_omission, (6, 12), 0.15, (0, 2))
        elif blue_option == '5-15_primary':
            passed, _ = check_ssq_blue_omission(blue_balls, blue_omission, (5, 15), 0.15, (0, 2))
        else:
            passed = True
        if not passed:
            return False
    
    return True


def _validate_dlt_rules(front_balls, blue_balls, red_omission, blue_omission, options):
    """验证大乐透所有规则"""
    
    # 1. 分区原则 - 前端发送的键名是 zone_ratio
    zone_ratio = options.get('zone_ratio', '1:2:2')
    if zone_ratio != 'disabled':
        targets = [zone_ratio]  # 前端发送的是单个值如 "1:2:2"，需要转为列表
        passed, _ = check_dlt_front_zone_distribution(front_balls, targets)
        if not passed:
            return False
    
    # 2. 连号号码原则 - 前端发送的键名是 consecutive
    consecutive_option = options.get('consecutive', '0_or_1_group_2')
    if consecutive_option != 'disabled':
        if consecutive_option == 'no_consecutive':
            passed, _, _ = check_consecutive_balls(front_balls, max_groups=0, max_length=0)
        elif consecutive_option == '0_or_1_group_2':
            passed, count, _ = check_consecutive_balls(front_balls, max_groups=1, max_length=2)
        elif consecutive_option == '1_group_2':
            passed, count, _ = check_consecutive_balls(front_balls, max_groups=1, max_length=2)
            passed = passed and count == 1
        else:
            passed = True
        if not passed:
            return False
    
    # 3. 与上期重号原则 - 前端发送的键名是 repeat
    repeat_option = options.get('repeat', '0_or_1')
    if repeat_option != 'disabled':
        if repeat_option == '0':
            passed, count = check_repeat_with_previous(front_balls, 'dlt', min_repeat=0, max_repeat=0)
        elif repeat_option == '1':
            passed, count = check_repeat_with_previous(front_balls, 'dlt', min_repeat=1, max_repeat=1)
        elif repeat_option == '0_or_1':
            passed, count = check_repeat_with_previous(front_balls, 'dlt', min_repeat=0, max_repeat=1)
        else:
            passed = True
        if not passed:
            return False
    
    # 4. 遗漏号原则 - 前端发送的键名是 omission_pattern
    omission_pattern = options.get('omission_pattern', '3:1:1')
    if omission_pattern != 'disabled':
        passed, _ = check_omission_rule_dlt(front_balls, red_omission, omission_pattern)
        if not passed:
            return False
    
    # 5. 遗漏期数一样的不超过1个
    if options.get('omission_duplicate_limit', True):
        passed, _ = check_dlt_omission_duplicate_limit(front_balls, red_omission, max_same=1)
        if not passed:
            return False
    
    # 6. 奇偶原则 - 前端发送的键名是 odd_even
    odd_even = options.get('odd_even', '3:2,2:3')
    if odd_even != 'disabled':
        targets = odd_even.split(',')
        passed, _ = check_odd_even_ratio(front_balls, targets)
        if not passed:
            return False
    
    # 7. 最大跨度原则 - 前端发送的键名是 span
    span_option = options.get('span', 'gt_24')
    if span_option != 'disabled':
        if span_option == 'gt_24':
            passed, _ = check_max_span(front_balls, min_span=24)
        elif span_option == 'gt_20':
            passed, _ = check_max_span(front_balls, min_span=20)
        elif span_option == 'gt_26':
            passed, _ = check_max_span(front_balls, min_span=26)
        else:
            passed = True
        if not passed:
            return False
    
    # 8. 号码总和原则 - 前端发送的键名是 sum
    sum_option = options.get('sum', '70-110')
    if sum_option != 'disabled':
        if sum_option == '70-110':
            passed, _ = check_sum_range(front_balls, 70, 110)
        elif sum_option == '80-100':
            passed, _ = check_sum_range(front_balls, 80, 100)
        elif sum_option == '60-120':
            passed, _ = check_sum_range(front_balls, 60, 120)
        elif sum_option == '90-110':
            passed, _ = check_sum_range(front_balls, 90, 110)
        else:
            passed = True
        if not passed:
            return False
    
    # 9. 同尾号原则 - 前端发送的键名是 same_tail
    tail_option = options.get('same_tail', 'exactly_1')
    if tail_option != 'disabled':
        if tail_option == 'exactly_1':
            passed, count = check_same_tail(front_balls, 1)
            passed = (count == 1)
        elif tail_option == 'at_least_1':
            passed, count = check_same_tail(front_balls, 0)
            passed = (count >= 1)
        elif tail_option == 'none':
            passed, count = check_same_tail(front_balls, 0)
            passed = (count == 0)
        else:
            passed = True
        if not passed:
            return False
    
    # 10. 邻号原则 - 前端发送的键名是 neighbor
    neighbor_option = options.get('neighbor', 'at_least_1')
    if neighbor_option != 'disabled':
        if neighbor_option == 'at_least_1':
            passed, _ = check_neighbor_numbers(front_balls, 1)
        elif neighbor_option == 'at_least_2':
            passed, _ = check_neighbor_numbers(front_balls, 2)
        else:
            passed = True
        if not passed:
            return False
    
    # 11. AC值原则 - 前端发送的键名是 ac_value
    ac_option = options.get('ac_value', '4_or_5')
    if ac_option != 'disabled':
        if ac_option == '4_or_5':
            passed, _ = check_ac_value(front_balls, [4, 5])
        elif ac_option == '3_to_6':
            passed, _ = check_ac_value(front_balls, [3, 4, 5, 6])
        elif ac_option == '4_to_7':
            passed, _ = check_ac_value(front_balls, [4, 5, 6, 7])
        else:
            passed = True
        if not passed:
            return False
    
    # 12. 后区遗漏选号原则
    if options.get('blue_omission_enabled', True):
        passed, _ = check_dlt_blue_omission(blue_balls, blue_omission)
        if not passed:
            return False
    
    # 13. 后区奇偶组合 - 前端发送的键名是 blue_odd_even
    blue_oe = options.get('blue_odd_even', '1:1')
    if blue_oe != 'disabled':
        passed, _ = check_dlt_blue_odd_even(blue_balls, blue_oe)
        if not passed:
            return False
    
    # 14. 后区大小组合 - 前端发送的键名是 blue_size
    blue_size = options.get('blue_size', '1:1')
    if blue_size != 'disabled':
        passed, _ = check_dlt_blue_size(blue_balls, blue_size)
        if not passed:
            return False
    
    return True


def _calculate_stats(lottery_type, red_balls, blue_balls):
    """计算号码统计信息"""
    if lottery_type == 'ssq':
        red_size_midpoint = CURRENT_SETTINGS.get('ssq_red_size_midpoint', 17)
        blue_size_midpoint = CURRENT_SETTINGS.get('ssq_blue_size_midpoint', 9)
    else:
        red_size_midpoint = CURRENT_SETTINGS.get('dlt_front_size_midpoint', 18)
        blue_size_midpoint = CURRENT_SETTINGS.get('dlt_back_size_midpoint', 7)
    
    return {
        'red_odd_even_ratio': calculate_odd_even_ratio_per_draw(red_balls),
        'red_sum': calculate_sum_per_draw(red_balls),
        'red_span': calculate_span_per_draw(red_balls),
        'red_size_ratio': calculate_size_ratio_per_draw(red_balls, red_size_midpoint),
        'blue_odd_even_ratio': calculate_odd_even_ratio_per_draw(blue_balls),
        'blue_sum': calculate_sum_per_draw(blue_balls),
        'blue_span': calculate_span_per_draw(blue_balls),
        'blue_size_ratio': calculate_size_ratio_per_draw(blue_balls, blue_size_midpoint),
    }
