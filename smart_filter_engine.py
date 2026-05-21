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
    
    # 只有当 max_groups > 0 时才检查 max_length
    # 如果 max_groups == 0（无连号模式），不需要检查长度
    if max_groups > 0:
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
    检查遗漏号规则 - 双色球红球遗漏号原则
    支持多种热温冷组合模式：
    - "4+1+1": 热号3-5个，温号0-2个，冷号0-2个
    - "4+2+0": 热号4个，温号2个，冷号0个
    - "3+3+0": 热号3个，温号3个，冷号0个
    - "3+2+1": 热号3个，温号2个，冷号1个
    - "2+3+1": 热号2个，温号3个，冷号1个
    - "2+2+2": 热号2个，温号2个，冷号2个
    """
    hot = [b for b in red_balls if red_omission.get(b, 0) <= 4]
    warm = [b for b in red_balls if 5 <= red_omission.get(b, 0) <= 9]
    cold = [b for b in red_balls if red_omission.get(b, 0) >= 10]
    
    h, w, c = len(hot), len(warm), len(cold)
    
    if pattern == "4+1+1":
        # 热号4个，温号1个，冷号1个（精确匹配，不允许偏差）
        if h == 4 and w == 1 and c == 1:
            return True, f"热{h}温{w}冷{c}"
    elif pattern == "5+1+0":
        # 热号5个，温号1个，冷号0个
        if h == 5 and w == 1 and c == 0:
            return True, f"热{h}温{w}冷{c}"
    elif pattern == "5+0+1":
        # 热号5个，温号0个，冷号1个
        if h == 5 and w == 0 and c == 1:
            return True, f"热{h}温{w}冷{c}"
    elif pattern == "4+2+0":
        if h == 4 and w == 2 and c == 0:
            return True, f"热{h}温{w}冷{c}"
    elif pattern == "3+3+0":
        if h == 3 and w == 3 and c == 0:
            return True, f"热{h}温{w}冷{c}"
    elif pattern == "3+2+1":
        if h == 3 and w == 2 and c == 1:
            return True, f"热{h}温{w}冷{c}"
    elif pattern == "3+1+2":
        if h == 3 and w == 1 and c == 2:
            return True, f"热{h}温{w}冷{c}"
    elif pattern == "2+3+1":
        if h == 2 and w == 3 and c == 1:
            return True, f"热{h}温{w}冷{c}"
    elif pattern == "2+2+2":
        if h == 2 and w == 2 and c == 2:
            return True, f"热{h}温{w}冷{c}"
    elif pattern == "2+4+0":
        if h == 2 and w == 4 and c == 0:
            return True, f"热{h}温{w}冷{c}"
    elif pattern == "1+4+1":
        if h == 1 and w == 4 and c == 1:
            return True, f"热{h}温{w}冷{c}"
    elif pattern == "1+5+0":
        if h == 1 and w == 5 and c == 0:
            return True, f"热{h}温{w}冷{c}"
    elif pattern == "6+0+0":
        # 热号6个，温号0个，冷号0个
        if h == 6 and w == 0 and c == 0:
            return True, f"热{h}温{w}冷{c}"
    else:
        # 未知模式，使用宽松检查
        if h + w + c == 6:
            return True, f"热{h}温{w}冷{c}"
    
    return False, f"热{h}温{w}冷{c}"


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


def check_max_span(balls, min_span=None, max_span=None):
    """
    检查最大跨度
    Args:
        balls: 号码列表
        min_span: 最小跨度（如果设置，则 span >= min_span）
        max_span: 最大跨度（如果设置，则 span < max_span）
    如果 min_span 和 max_span 都设置，则 min_span <= span < max_span
    如果只设置 min_span，则 span >= min_span
    如果只设置 max_span，则 span < max_span
    """
    span = calculate_span_per_draw(balls)
    if min_span is not None and max_span is not None:
        return min_span <= span < max_span, span
    elif min_span is not None:
        return span >= min_span, span
    elif max_span is not None:
        return span < max_span, span
    return True, span


def check_sum_range(balls, min_sum=70, max_sum=129):
    """检查号码总和范围"""
    total = calculate_sum_per_draw(balls)
    return min_sum <= total <= max_sum, total


def check_same_tail(red_balls, mode="exactly_1"):
    """
    检查同尾号 - 同尾号指个位数相同的号码，如 01, 11, 21, 31
    mode: 
      - "exactly_1": 有且只有1组同尾号
      - "at_least_1": 至少1组同尾号
      - "none": 无同尾号
      - "0": 0组同尾号（无同尾号）
      - "1": 有且只有1组同尾号
      - "2": 有且只有2组同尾号
      - "3": 有且只有3组同尾号
    返回: (是否通过, 同尾号组数)
    """
    tail_groups = Counter(b % 10 for b in red_balls)
    same_tail_groups = [tail for tail, count in tail_groups.items() if count >= 2]
    count = len(same_tail_groups)
    
    if mode == "exactly_1" or mode == "1":
        return count == 1, count
    elif mode == "at_least_1":
        return count >= 1, count
    elif mode == "none" or mode == "0":
        return count == 0, count
    elif mode == "2":
        return count == 2, count
    elif mode == "3":
        return count == 3, count
    else:
        return True, count


def check_neighbor_numbers(red_balls, lottery_type, min_groups=1, mode='at_least'):
    """
    检查邻号（边号）- 与上期开奖号码相差±1的号码
    邻号定义：上期开奖号码的相邻号码（+1或-1）
    例如上期有05，则04、06是邻号
    mode: 'at_least' - 至少min_groups个, 'exactly' - 正好min_groups个
    """
    latest = get_latest_draw(lottery_type)
    if not latest:
        return True, 0
    
    prev_reds = set(latest.get_red_balls_list())
    neighbor_count = 0
    neighbor_balls = []
    
    for b in red_balls:
        if (b - 1) in prev_reds or (b + 1) in prev_reds:
            neighbor_count += 1
            neighbor_balls.append(b)
    
    if mode == 'at_least':
        return neighbor_count >= min_groups, neighbor_count
    else:
        return neighbor_count == min_groups, neighbor_count


def check_ac_value(red_balls, target_values):
    """
    检查AC值
    target_values: 允许的AC值列表，如 [6, 7]
    """
    ac = calculate_ac_value_per_draw(red_balls)
    return ac in target_values, ac


def check_ssq_blue_omission(blue_balls, blue_omission, mode="6-12_primary"):
    """
    检查蓝球遗漏规则
    mode: 
      - "6-12_primary": 优先遗漏6-12期，次选0-2期
      - "5-15_primary": 优先遗漏5-15期，次选0-2期
      - "0-2_primary": 优先遗漏0-2期
      - "0-4_primary": 优先遗漏0-4期
    返回: (是否通过, 描述信息)
    """
    if mode == "6-12_primary":
        primary_range = (6, 12)
        secondary_range = (0, 2)
    elif mode == "5-15_primary":
        primary_range = (5, 15)
        secondary_range = (0, 2)
    elif mode == "0-2_primary":
        primary_range = (0, 2)
        secondary_range = None
    elif mode == "0-4_primary":
        primary_range = (0, 4)
        secondary_range = None
    elif mode == "0":
        primary_range = (0, 0)
        secondary_range = None
    elif mode == "0-5_primary":
        primary_range = (0, 5)
        secondary_range = None
    else:
        return True, ""
    
    for b in blue_balls:
        omission = blue_omission.get(b, 0)
        # 检查是否在优先范围内
        if primary_range[0] <= omission <= primary_range[1]:
            continue
        # 如果有次选范围，检查是否在次选范围内
        elif secondary_range and secondary_range[0] <= omission <= secondary_range[1]:
            continue
        else:
            # 不在任何允许范围内，不通过
            return False, f"蓝球{b}遗漏{omission}期不在允许范围"
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
    检查遗漏号规则 - 大乐透前区遗漏号原则
    支持多种热温冷组合模式：
    - "3:1:1": 热号2-4个，温号0-2个，冷号0-2个
    - "4:1:0": 热号3-5个，温号0-2个，冷号0个
    - "3:2:0": 热号3个，温号2个，冷号0个
    - "2:2:1": 热号2个，温号2个，冷号1个
    - "2:1:2": 热号2个，温号1个，冷号2个
    - "1:2:2": 热号1个，温号2个，冷号2个
    """
    hot = [b for b in front_balls if red_omission.get(b, 0) <= 4]
    warm = [b for b in front_balls if 5 <= red_omission.get(b, 0) <= 9]
    cold = [b for b in front_balls if red_omission.get(b, 0) >= 10]
    
    h, w, c = len(hot), len(warm), len(cold)
    
    if pattern == "3:1:1":
        # 热号2-4个，温号0-2个，冷号0-2个
        if 2 <= h <= 4 and w <= 2 and c <= 2 and h + w + c == 5:
            return True, f"热{h}温{w}冷{c}"
    elif pattern == "4:1:0":
        # 热号3-5个，温号0-2个，冷号0个
        if 3 <= h <= 5 and w <= 2 and c == 0 and h + w + c == 5:
            return True, f"热{h}温{w}冷{c}"
    elif pattern == "3:2:0":
        if h == 3 and w == 2 and c == 0:
            return True, f"热{h}温{w}冷{c}"
    elif pattern == "2:2:1":
        if h == 2 and w == 2 and c == 1:
            return True, f"热{h}温{w}冷{c}"
    elif pattern == "2:1:2":
        if h == 2 and w == 1 and c == 2:
            return True, f"热{h}温{w}冷{c}"
    elif pattern == "1:2:2":
        if h == 1 and w == 2 and c == 2:
            return True, f"热{h}温{w}冷{c}"
    elif pattern == "3+2+0":
        if h == 3 and w == 2 and c == 0:
            return True, f"热{h}温{w}冷{c}"
    elif pattern == "2+2+1":
        if h == 2 and w == 2 and c == 1:
            return True, f"热{h}温{w}冷{c}"
    elif pattern == "2+1+2":
        if h == 2 and w == 1 and c == 2:
            return True, f"热{h}温{w}冷{c}"
    elif pattern == "1+3+1":
        if h == 1 and w == 3 and c == 1:
            return True, f"热{h}温{w}冷{c}"
    elif pattern == "1+4+0":
        if h == 1 and w == 4 and c == 0:
            return True, f"热{h}温{w}冷{c}"
    elif pattern == "5+0+0" or pattern == "5:0:0":
        if h == 5 and w == 0 and c == 0:
            return True, f"热{h}温{w}冷{c}"
    elif pattern == "0+5+0" or pattern == "0:5:0":
        if h == 0 and w == 5 and c == 0:
            return True, f"热{h}温{w}冷{c}"
    else:
        # 未知模式，使用宽松检查
        if h + w + c == 5:
            return True, f"热{h}温{w}冷{c}"
    
    return False, f"热{h}温{w}冷{c}"


def check_dlt_omission_duplicate_limit(front_balls, red_omission, max_same=1):
    """大乐透遗漏期数一样的不能超过1个"""
    omission_counts = Counter(red_omission.get(b, 0) for b in front_balls)
    for omission_val, count in omission_counts.items():
        if count > max_same:
            return False, f"遗漏{omission_val}期出现{count}次(超过{max_same})"
    return True, ""


def check_dlt_blue_omission(blue_balls, blue_omission, mode="5-15_primary"):
    """
    检查大乐透后区遗漏规则
    mode:
      - "5-15_primary": 至少一个号码来自遗漏5-15期
      - "0-2_primary": 优先遗漏0-2期
      - "0-4_primary": 优先遗漏0-4期
    返回: (是否通过, 描述信息)
    """
    if mode == "5-15_primary":
        # 至少一个号码来自遗漏5-15期
        has_warm = False
        for b in blue_balls:
            omission = blue_omission.get(b, 0)
            if 5 <= omission <= 15:
                has_warm = True
                break
        if not has_warm:
            return False, "后区没有遗漏5-15期的号码"
        return True, ""
    elif mode == "0-2_primary":
        # 所有号码应在遗漏0-2期范围内
        for b in blue_balls:
            omission = blue_omission.get(b, 0)
            if not (0 <= omission <= 2):
                return False, f"后区{b}遗漏{omission}期不在0-2期范围"
        return True, ""
    elif mode == "0-4_primary":
        # 所有号码应在遗漏0-4期范围内
        for b in blue_balls:
            omission = blue_omission.get(b, 0)
            if not (0 <= omission <= 4):
                return False, f"后区{b}遗漏{omission}期不在0-4期范围"
        return True, ""
    else:
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
    
    front_rules = [
        'zone_ratio', 'consecutive', 'repeat', 'omission_pattern',
        'odd_even', 'span', 'sum', 'same_tail', 'neighbor', 'ac_value'
    ]
    
    generated = []
    max_attempts = 50000  # 增加尝试次数，因为多个条件组合需要更多尝试
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
        
        # 每组号码独立随机忽略 0-2 个前区规则
        # 这样用户在一批5组结果中能看到不同的忽略组合
        ignore_count_for_group = random.randint(0, 2)
        group_ignored_rules = random.sample(front_rules, ignore_count_for_group) if ignore_count_for_group > 0 else []
        
        # 验证所有规则（每组使用独立的 ignored_rules）
        if _validate_all_rules(lottery_type, red_balls, blue_balls, red_omission, blue_omission, options, group_ignored_rules):
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
    """智能生成红球 - 根据遗漏规则加权随机生成，然后由验证函数过滤"""
    max_attempts = 2000
    
    # 检查是否只选了"无连号"（没有其他连号选项）
    # 如果只选无连号，在生成阶段就排除连号以提高效率
    # 如果同时选了无连号和其他连号选项，让验证阶段处理过滤逻辑
    consecutive_options = options.get('consecutive', None)
    if consecutive_options is None:
        no_consecutive_mode = False
    else:
        if isinstance(consecutive_options, str):
            consecutive_options = [consecutive_options]
        # 只有当选中的唯一选项就是'no_consecutive'时，才在生成阶段启用无连号模式
        no_consecutive_mode = (len(consecutive_options) == 1 and 'no_consecutive' in consecutive_options)
    
    # 获取遗漏号原则选项，用于加权生成
    omission_patterns = options.get('omission_pattern', None)
    if isinstance(omission_patterns, str):
        omission_patterns = [omission_patterns]
    
    # 计算每个号码的权重，基于遗漏值和选择的遗漏号原则
    candidates = list(range(1, red_range + 1))
    weights = []
    
    for b in candidates:
        omission = red_omission.get(b, 0)
        w = 1.0
        
        if omission_patterns and 'disabled' not in omission_patterns:
            # 根据遗漏值分类
            is_hot = omission <= 4
            is_warm = 5 <= omission <= 9
            is_cold = omission >= 10
            
            # 根据选择的模式调整权重
            for pattern in omission_patterns:
                if pattern == '4+1+1':
                    # 热号4个，温号1个，冷号1个 - 热号权重最高以生成4个热号
                    if is_hot: w = max(w, 3.0)
                    elif is_warm: w = max(w, 2.0)
                    elif is_cold: w = max(w, 2.0)
                elif pattern == '4+2+0':
                    if is_hot: w = max(w, 3.0)
                    elif is_warm: w = max(w, 2.0)
                    elif is_cold: w = max(w, 0.3)
                elif pattern == '3+3+0':
                    if is_hot: w = max(w, 2.0)
                    elif is_warm: w = max(w, 3.0)
                    elif is_cold: w = max(w, 0.3)
                elif pattern == '3+2+1':
                    if is_hot: w = max(w, 2.5)
                    elif is_warm: w = max(w, 2.0)
                    elif is_cold: w = max(w, 1.5)
                elif pattern == '3+1+2':
                    if is_hot: w = max(w, 2.5)
                    elif is_warm: w = max(w, 1.5)
                    elif is_cold: w = max(w, 2.0)
                elif pattern == '2+3+1':
                    if is_hot: w = max(w, 1.5)
                    elif is_warm: w = max(w, 3.0)
                    elif is_cold: w = max(w, 1.5)
                elif pattern == '2+2+2':
                    if is_hot: w = max(w, 2.0)
                    elif is_warm: w = max(w, 2.0)
                    elif is_cold: w = max(w, 2.0)
                elif pattern == '2+4+0':
                    if is_hot: w = max(w, 1.5)
                    elif is_warm: w = max(w, 3.0)
                    elif is_cold: w = max(w, 0.3)
                elif pattern == '1+4+1':
                    if is_hot: w = max(w, 1.0)
                    elif is_warm: w = max(w, 3.0)
                    elif is_cold: w = max(w, 1.5)
                elif pattern == '1+5+0':
                    if is_hot: w = max(w, 1.0)
                    elif is_warm: w = max(w, 3.0)
                    elif is_cold: w = max(w, 0.3)
                elif pattern == '5+1+0':
                    # 热号5个，温号1个，冷号0个
                    if is_hot: w = max(w, 3.5)
                    elif is_warm: w = max(w, 2.0)
                    elif is_cold: w = max(w, 0.3)
                elif pattern == '5+0+1':
                    # 热号5个，温号0个，冷号1个
                    if is_hot: w = max(w, 3.5)
                    elif is_warm: w = max(w, 0.3)
                    elif is_cold: w = max(w, 2.0)
                # DLT patterns
                elif pattern == '3+1+1':
                    if is_hot: w = max(w, 3.0)
                    elif is_warm: w = max(w, 1.5)
                    elif is_cold: w = max(w, 1.5)
                elif pattern == '4+1+0':
                    if is_hot: w = max(w, 3.0)
                    elif is_warm: w = max(w, 1.5)
                    elif is_cold: w = max(w, 0.3)
                elif pattern == '3+2+0':
                    if is_hot: w = max(w, 2.5)
                    elif is_warm: w = max(w, 2.5)
                    elif is_cold: w = max(w, 0.3)
                elif pattern == '2+2+1':
                    if is_hot: w = max(w, 2.0)
                    elif is_warm: w = max(w, 2.0)
                    elif is_cold: w = max(w, 1.5)
                elif pattern == '2+1+2':
                    if is_hot: w = max(w, 2.0)
                    elif is_warm: w = max(w, 1.5)
                    elif is_cold: w = max(w, 2.0)
                elif pattern == '1+3+1':
                    if is_hot: w = max(w, 1.0)
                    elif is_warm: w = max(w, 3.0)
                    elif is_cold: w = max(w, 1.5)
                elif pattern == '1+4+0':
                    if is_hot: w = max(w, 1.0)
                    elif is_warm: w = max(w, 3.0)
                    elif is_cold: w = max(w, 0.3)
        else:
            # 没有选择遗漏号原则，使用默认权重（偏向热号）
            if omission <= 4:
                w = 2.0
            elif omission <= 9:
                w = 1.5
            else:
                w = 1.0
        
        weights.append(w)
    
    for _ in range(max_attempts):
        try:
            # 使用加权随机生成
            temp_candidates = list(candidates)
            temp_weights = list(weights)
            
            selected = set()
            while len(selected) < num_red:
                if not temp_candidates:
                    break
                total = sum(temp_weights)
                probs = [w / total for w in temp_weights]
                idx = random.choices(range(len(temp_candidates)), weights=probs, k=1)[0]
                b = temp_candidates[idx]
                
                # 如果是无连号模式，检查是否会形成连号
                if no_consecutive_mode and selected:
                    if any(abs(b - s) == 1 for s in selected):
                        temp_candidates.pop(idx)
                        temp_weights.pop(idx)
                        continue
                
                selected.add(b)
                temp_candidates.pop(idx)
                temp_weights.pop(idx)
            
            if len(selected) == num_red:
                return sorted(list(selected))
        except Exception:
            continue
    
    return None


def _generate_blue_balls_smart(lottery_type, num_blue, blue_range, blue_omission, options):
    """智能生成蓝球 - 支持 blue_selected_balls 选项"""
    max_attempts = 100
    
    # 判断是否无限制（用户勾选了"不限制"或没有选择任何具体号码）
    blue_selected = options.get('blue_selected_balls', None)
    blue_disabled = options.get('blue_disabled', False) or options.get('disabled', False)
    is_unrestricted = (blue_selected is None or len(blue_selected) == 0 or blue_disabled)
    
    if is_unrestricted:
        # ===== 情况1：无限制 =====
        # 用户勾选了"不限制"，应该使用纯随机生成，所有号码权重相等
        all_balls = list(range(1, blue_range + 1))
        for _ in range(max_attempts):
            try:
                selected = random.sample(all_balls, num_blue)
                return sorted(selected)
            except ValueError:
                continue
        return None
    
    # ===== 情况2：用户选择了具体号码 =====
    # 选中的号码权重加成（约75%），其他号码用遗漏趋势权重补充（约25%）
    available_balls = [b for b in blue_selected if 1 <= b <= blue_range]
    all_balls = list(range(1, blue_range + 1))
    
    # 选中的号码权重设为 5.0（约75%被选中概率）
    SELECTED_WEIGHT = 5.0
    # 未选中的号码基础权重
    UNSELECTED_BASE_WEIGHT = 1.0
    
    if len(available_balls) >= num_blue:
        # 选中的号码足够，全部从选中号码中生成，但使用权重微调
        for _ in range(max_attempts):
            try:
                candidates = list(available_balls)
                weights = []
                for b in candidates:
                    omission = blue_omission.get(b, 0)
                    w = SELECTED_WEIGHT  # 基础权重 5.0
                    
                    # 在选中的号码内部用遗漏趋势微调
                    if lottery_type == 'ssq':
                        if 6 <= omission <= 12:
                            w *= 1.3  # 遗漏6-12期略微提高
                        elif 0 <= omission <= 2:
                            w *= 0.8  # 热号略微降低
                    else:
                        if 5 <= omission <= 15:
                            w *= 1.3  # 遗漏5-15期略微提高
                        elif 0 <= omission <= 2:
                            w *= 0.8  # 热号略微降低
                    weights.append(w)
                
                total = sum(weights)
                probs = [w / total for w in weights]
                
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
    
    elif len(available_balls) > 0:
        # 选中的号码不足（如大乐透只选了1个后区号码），保留选中的从选中池，
        # 再从全部号码池用权重补充（选中的权重5.0，未选中的权重1.0+遗漏趋势）
        needed = num_blue - len(available_balls)
        
        for _ in range(max_attempts):
            try:
                selected = list(available_balls)  # 保留已选中的号码
                
                # 从剩余号码中按权重选需要的数量
                remaining = [b for b in all_balls if b not in available_balls]
                candidates = list(remaining)
                weights = []
                
                for b in candidates:
                    omission = blue_omission.get(b, 0)
                    w = UNSELECTED_BASE_WEIGHT  # 未选中的基础权重 1.0
                    
                    # 用遗漏趋势微调
                    if lottery_type == 'ssq':
                        if 6 <= omission <= 12:
                            w = 2.0   # 遗漏6-12期权重高一些
                        elif 0 <= omission <= 2:
                            w = 1.2
                        else:
                            w = 1.5
                    else:
                        if 5 <= omission <= 15:
                            w = 2.0   # 遗漏5-15期权重高一些
                        elif 0 <= omission <= 2:
                            w = 1.2
                        elif omission >= 16:
                            w = 1.0
                        else:
                            w = 1.5
                    weights.append(w)
                
                total = sum(weights)
                probs = [w / total for w in weights]
                
                temp_candidates = list(candidates)
                temp_probs = list(probs)
                
                while len(selected) < num_blue:
                    idx = random.choices(range(len(temp_candidates)), weights=temp_probs, k=1)[0]
                    selected.append(temp_candidates[idx])
                    temp_candidates.pop(idx)
                    temp_probs.pop(idx)
                    if temp_probs:
                        total = sum(temp_probs)
                        temp_probs = [w / total for w in temp_probs]
                
                return sorted(selected)
            except Exception:
                continue
    
    return None


def _validate_all_rules(lottery_type, red_balls, blue_balls, red_omission, blue_omission, options, ignored_rules=None):
    """验证所有启用的规则
    
    Args:
        ignored_rules: 本次验证中要忽略的前区规则名称列表。
                       如果为 None，则随机决定忽略 0-2 个规则（向后兼容）。
                       建议在生成整批号码前统一决定，使效果对用户可见。
    """
    
    if ignored_rules is None:
        # 随机决定忽略 0-2 个前区规则，实现"可以不完全满足所有条件"的需求
        # 所有规则（包括连号原则）平等参与随机忽略
        front_rules = [
            'zone_ratio', 'consecutive', 'repeat', 'omission_pattern',
            'odd_even', 'span', 'sum', 'same_tail', 'neighbor', 'ac_value'
        ]
        ignore_count = random.randint(0, 2)
        ignored_rules = random.sample(front_rules, ignore_count) if ignore_count > 0 else []
    
    if lottery_type == 'ssq':
        return _validate_ssq_rules(red_balls, blue_balls, red_omission, blue_omission, options, ignored_rules)
    else:
        return _validate_dlt_rules(red_balls, blue_balls, red_omission, blue_omission, options, ignored_rules)


def _validate_ssq_rules(red_balls, blue_balls, red_omission, blue_omission, options, ignored_rules=None):
    """验证双色球所有规则 - 支持多选合集
    ignored_rules: 本次验证中要忽略的前区规则名称列表（随机忽略0-2个）
    """
    if ignored_rules is None:
        ignored_rules = []
    
    # 1. 分区原则 - 支持多选
    if 'zone_ratio' not in ignored_rules:
        zone_ratios = options.get('zone_ratio', ['2:2:2'])
        if isinstance(zone_ratios, str):
            zone_ratios = [zone_ratios]
        if 'disabled' not in zone_ratios:
            passed = any(check_ssq_red_zone_distribution(red_balls, ratio)[0] for ratio in zone_ratios)
            if not passed:
                return False
    
    # 2. 连号号码原则 - 支持多选
    if 'consecutive' not in ignored_rules:
        consecutive_options = options.get('consecutive', None)
        if consecutive_options is None:
            pass  # 没有提供连号选项，视为不限制
        else:
            if isinstance(consecutive_options, str):
                consecutive_options = [consecutive_options]
            if 'disabled' not in consecutive_options:
                passed = False
                for opt in consecutive_options:
                    if opt == 'no_consecutive':
                        p, count, _ = check_consecutive_balls(red_balls, max_groups=0, max_length=0)
                        if p and count == 0: passed = True; break
                    elif opt == '1_group_2':
                        # 恰好1组2连号：精确匹配1组且长度为2，不能无连号也不能有其他类型连号
                        p, count, groups = check_consecutive_balls(red_balls, max_groups=1, max_length=2)
                        if p and count == 1:
                            for g in groups:
                                if len(g) == 2:
                                    passed = True; break
                        if passed: break
                    elif opt == '2_group_2':
                        # 恰好2组2连号：精确匹配2组且每组的长度为2
                        p, count, groups = check_consecutive_balls(red_balls, max_groups=2, max_length=2)
                        if p and count == 2:
                            # 确保每组都是2连号
                            all_are_2 = all(len(g) == 2 for g in groups)
                            if all_are_2:
                                passed = True; break
                    elif opt == '1_group_3':
                        # 恰好1组3连号：精确匹配1组且长度为3，不能有其他连号组
                        p, count, groups = check_consecutive_balls(red_balls, max_groups=1, max_length=3)
                        if p and count == 1:
                            for g in groups:
                                if len(g) == 3:
                                    passed = True; break
                        if passed: break
            if not passed:
                return False
    
    # 3. 与上期重号原则 - 支持多选
    if 'repeat' not in ignored_rules:
        repeat_options = options.get('repeat', ['1_or_2'])
        if isinstance(repeat_options, str):
            repeat_options = [repeat_options]
        if 'disabled' not in repeat_options:
            passed = False
            for opt in repeat_options:
                if opt == '1':
                    p, _ = check_repeat_with_previous(red_balls, 'ssq', min_repeat=1, max_repeat=1)
                    if p: passed = True; break
                elif opt == '2':
                    p, _ = check_repeat_with_previous(red_balls, 'ssq', min_repeat=2, max_repeat=2)
                    if p: passed = True; break
                elif opt == '1_or_2':
                    p, _ = check_repeat_with_previous(red_balls, 'ssq', min_repeat=1, max_repeat=2)
                    if p: passed = True; break
                elif opt == '3':
                    p, _ = check_repeat_with_previous(red_balls, 'ssq', min_repeat=3, max_repeat=3)
                    if p: passed = True; break
                elif opt == '0':
                    p, _ = check_repeat_with_previous(red_balls, 'ssq', min_repeat=0, max_repeat=0)
                    if p: passed = True; break
            if not passed:
                return False
    
    # 4. 遗漏号原则 - 支持多选
    if 'omission_pattern' not in ignored_rules:
        omission_patterns = options.get('omission_pattern', ['4+1+1'])
        if isinstance(omission_patterns, str):
            omission_patterns = [omission_patterns]
        if 'disabled' not in omission_patterns:
            passed = any(check_omission_rule_ssq(red_balls, red_omission, pattern)[0] for pattern in omission_patterns)
            if not passed:
                return False
    
    # 5. 遗漏期数一样的不超过3个（放宽条件，原为2个）
    if 'omission_pattern' not in ignored_rules:
        if options.get('omission_duplicate_limit', True):
            passed, _ = check_omission_duplicate_limit(red_balls, red_omission, max_same=3)
            if not passed:
                return False
    
    # 6. 奇偶原则 - 支持多选
    if 'odd_even' not in ignored_rules:
        odd_even_options = options.get('odd_even', ['3:3', '2:4', '4:2'])
        if isinstance(odd_even_options, str):
            odd_even_options = odd_even_options.split(',')
        if 'disabled' not in odd_even_options:
            passed, _ = check_odd_even_ratio(red_balls, odd_even_options)
            if not passed:
                return False
    
    # 7. 最大跨度原则 - 支持多选
    if 'span' not in ignored_rules:
        span_options = options.get('span', ['gt_26'])
        if isinstance(span_options, str):
            span_options = [span_options]
        if 'disabled' not in span_options:
            passed = False
            for opt in span_options:
                if opt == 'lt_20':
                    p, _ = check_max_span(red_balls, max_span=20)
                    if p: passed = True; break
                elif opt == 'gt_20':
                    p, _ = check_max_span(red_balls, min_span=20)
                    if p: passed = True; break
                elif opt == 'gt_22':
                    p, _ = check_max_span(red_balls, min_span=22)
                    if p: passed = True; break
                elif opt == 'gt_24':
                    p, _ = check_max_span(red_balls, min_span=24)
                    if p: passed = True; break
                elif opt == 'gt_26':
                    p, _ = check_max_span(red_balls, min_span=26)
                    if p: passed = True; break
                elif opt == 'gt_28':
                    p, _ = check_max_span(red_balls, min_span=28)
                    if p: passed = True; break
                elif opt == 'gt_30':
                    p, _ = check_max_span(red_balls, min_span=30)
                    if p: passed = True; break
            if not passed:
                return False
    
    # 8. 号码总和原则 - 支持多选（checkbox）
    if 'sum' not in ignored_rules:
        sum_options = options.get('sum', ['71-90', '91-110'])
        if isinstance(sum_options, str):
            sum_options = [sum_options]
        if 'disabled' not in sum_options:
            passed = False
            for opt in sum_options:
                if opt == 'lt_70':
                    p, total = check_sum_range(red_balls, 1, 69)
                    if p: passed = True; break
                elif opt == '71-90':
                    p, total = check_sum_range(red_balls, 71, 90)
                    if p: passed = True; break
                elif opt == '91-110':
                    p, total = check_sum_range(red_balls, 91, 110)
                    if p: passed = True; break
                elif opt == '111-120':
                    p, total = check_sum_range(red_balls, 111, 120)
                    if p: passed = True; break
                elif opt == 'gt_120':
                    p, total = check_sum_range(red_balls, 121, 200)
                    if p: passed = True; break
            if not passed:
                return False
    
    # 9. 同尾号原则 - 支持多选（checkbox）
    if 'same_tail' not in ignored_rules:
        tail_options = options.get('same_tail', ['1'])
        if isinstance(tail_options, str):
            tail_options = [tail_options]
        if 'disabled' not in tail_options:
            passed = False
            for opt in tail_options:
                if opt == 'exactly_1' or opt == '1':
                    p, _ = check_same_tail(red_balls, '1')
                    if p: passed = True; break
                elif opt == 'at_least_1':
                    p, _ = check_same_tail(red_balls, 'at_least_1')
                    if p: passed = True; break
                elif opt == 'none' or opt == '0':
                    p, _ = check_same_tail(red_balls, '0')
                    if p: passed = True; break
                elif opt == '2':
                    p, _ = check_same_tail(red_balls, '2')
                    if p: passed = True; break
                elif opt == '3':
                    p, _ = check_same_tail(red_balls, '3')
                    if p: passed = True; break
            if not passed:
                return False
    
    # 10. 邻号原则 - 支持多选（0,1,2,3,4,disabled）
    if 'neighbor' not in ignored_rules:
        neighbor_options = options.get('neighbor', ['2'])
        if isinstance(neighbor_options, str):
            neighbor_options = [neighbor_options]
        if 'disabled' not in neighbor_options:
            passed = False
            for opt in neighbor_options:
                neighbor_count = int(opt) if opt.isdigit() else None
                if neighbor_count is not None:
                    p, count = check_neighbor_numbers(red_balls, 'ssq', neighbor_count, 'exactly')
                    if p: passed = True; break
            if not passed:
                return False
    
    # 11. AC值原则 - 支持多选（SSQ: lt_5,5,6,7,8,9,10,disabled）
    if 'ac_value' not in ignored_rules:
        ac_options = options.get('ac_value', ['6'])
        if isinstance(ac_options, str):
            ac_options = [ac_options]
        if 'disabled' not in ac_options:
            passed = False
            for opt in ac_options:
                if opt == 'lt_5':
                    # AC < 5 即 0-4
                    p, ac_val = check_ac_value(red_balls, [0, 1, 2, 3, 4])
                    if p: passed = True; break
                elif opt in ['5', '6', '7', '8', '9', '10']:
                    p, ac_val = check_ac_value(red_balls, [int(opt)])
                    if p: passed = True; break
            if not passed:
                return False
    
    # 12. 蓝球选择 - 验证选中的蓝球是否在 blue_selected_balls 中
    blue_selected = options.get('blue_selected_balls', None)
    if blue_selected:
        for b in blue_balls:
            if b not in blue_selected:
                return False
    
    # 13. 蓝球遗漏原则 - 支持多选（仅在未指定具体蓝球号码时使用）
    blue_options = options.get('blue_omission', ['6-12_primary'])
    if isinstance(blue_options, str):
        blue_options = [blue_options]
    if 'disabled' not in blue_options and 'any' not in blue_options and not blue_selected:
        passed = False
        for opt in blue_options:
            if opt in ['6-12_primary', '5-15_primary', '0-2_primary', '0-4_primary', '0', '0-5_primary']:
                p, _ = check_ssq_blue_omission(blue_balls, blue_omission, mode=opt)
                if p: passed = True; break
        if not passed:
            return False
    
    return True


def _validate_dlt_rules(front_balls, blue_balls, red_omission, blue_omission, options, ignored_rules=None):
    """验证大乐透所有规则 - 支持多选合集
    ignored_rules: 本次验证中要忽略的前区规则名称列表（随机忽略0-2个）
    """
    if ignored_rules is None:
        ignored_rules = []
    
    import logging
    logger = logging.getLogger(__name__)
    
    # 1. 分区原则 - 支持多选
    if 'zone_ratio' not in ignored_rules:
        zone_ratios = options.get('zone_ratio', ['2:2:1'])
        if isinstance(zone_ratios, str):
            zone_ratios = [zone_ratios]
        if 'disabled' not in zone_ratios:
            passed, actual = check_dlt_front_zone_distribution(front_balls, zone_ratios)
            if not passed:
                logger.debug(f"DLT FAIL: zone_ratio. balls={front_balls}, actual={actual}, expected={zone_ratios}")
                return False
            logger.debug(f"DLT PASS: zone_ratio. actual={actual}")
    
    # 2. 连号号码原则 - 支持多选
    if 'consecutive' not in ignored_rules:
        consecutive_options = options.get('consecutive', None)
        if consecutive_options is None:
            pass  # 没有提供连号选项，视为不限制
        else:
            if isinstance(consecutive_options, str):
                consecutive_options = [consecutive_options]
            if 'disabled' not in consecutive_options:
                passed = False
                for opt in consecutive_options:
                    if opt == 'no_consecutive':
                        p, count, _ = check_consecutive_balls(front_balls, max_groups=0, max_length=0)
                        if p and count == 0: passed = True; break
                    elif opt == '1_group_2':
                        # 恰好1组2连号：精确匹配1组且长度为2
                        p, count, groups = check_consecutive_balls(front_balls, max_groups=1, max_length=2)
                        if p and count == 1:
                            for g in groups:
                                if len(g) == 2:
                                    passed = True; break
                        if passed: break
                    elif opt == '2_group_2':
                        # 恰好2组2连号：精确匹配2组且每组的长度为2
                        p, count, groups = check_consecutive_balls(front_balls, max_groups=2, max_length=2)
                        if p and count == 2:
                            # 确保每组都是2连号
                            all_are_2 = all(len(g) == 2 for g in groups)
                            if all_are_2:
                                passed = True; break
                    elif opt == '1_group_3':
                        # 恰好1组3连号：精确匹配1组且长度为3
                        p, count, groups = check_consecutive_balls(front_balls, max_groups=1, max_length=3)
                        if p and count == 1:
                            for g in groups:
                                if len(g) == 3:
                                    passed = True; break
                        if passed: break
                if not passed:
                    logger.debug(f"DLT FAIL: consecutive. balls={front_balls}, options={consecutive_options}")
                    return False
                logger.debug(f"DLT PASS: consecutive.")
    
    # 3. 与上期重号原则 - 支持多选
    if 'repeat' not in ignored_rules:
        repeat_options = options.get('repeat', ['1_or_2'])
        if isinstance(repeat_options, str):
            repeat_options = [repeat_options]
        if 'disabled' not in repeat_options:
            passed = False
            for opt in repeat_options:
                if opt == '1':
                    p, count = check_repeat_with_previous(front_balls, 'dlt', min_repeat=1, max_repeat=1)
                    if p: passed = True; break
                elif opt == '2':
                    p, count = check_repeat_with_previous(front_balls, 'dlt', min_repeat=2, max_repeat=2)
                    if p: passed = True; break
                elif opt == '1_or_2':
                    p, count = check_repeat_with_previous(front_balls, 'dlt', min_repeat=1, max_repeat=2)
                    if p: passed = True; break
                elif opt == '3':
                    p, count = check_repeat_with_previous(front_balls, 'dlt', min_repeat=3, max_repeat=3)
                    if p: passed = True; break
                elif opt == '0':
                    p, count = check_repeat_with_previous(front_balls, 'dlt', min_repeat=0, max_repeat=0)
                    if p: passed = True; break
            if not passed:
                logger.debug(f"DLT FAIL: repeat. balls={front_balls}, options={repeat_options}, count={count}")
                return False
            logger.debug(f"DLT PASS: repeat. count={count}")
    
    # 4. 遗漏号原则 - 支持多选
    if 'omission_pattern' not in ignored_rules:
        omission_patterns = options.get('omission_pattern', ['3+1+1'])
        if isinstance(omission_patterns, str):
            omission_patterns = [omission_patterns]
        if 'disabled' not in omission_patterns:
            # 将前端格式 (3+1+1) 转换为后端格式 (3:1:1)
            converted_patterns = []
            for p in omission_patterns:
                converted_patterns.append(p.replace('+', ':'))
            passed = False
            last_result = ""
            for pattern in converted_patterns:
                p, result = check_omission_rule_dlt(front_balls, red_omission, pattern)
                if p: passed = True; break
                last_result = result
            if not passed:
                logger.debug(f"DLT FAIL: omission_pattern. balls={front_balls}, patterns={converted_patterns}, result={last_result}")
                return False
            logger.debug(f"DLT PASS: omission_pattern. result={last_result}")
    
    # 5. 遗漏期数一样的不超过2个（放宽限制，避免生成速度过慢）
    if 'omission_pattern' not in ignored_rules:
        if options.get('omission_duplicate_limit', True):
            passed, msg = check_dlt_omission_duplicate_limit(front_balls, red_omission, max_same=2)
            if not passed:
                logger.debug(f"DLT FAIL: omission_duplicate. balls={front_balls}, msg={msg}")
                return False
            logger.debug(f"DLT PASS: omission_duplicate.")
    
    # 6. 奇偶原则 - 支持多选
    if 'odd_even' not in ignored_rules:
        odd_even_options = options.get('odd_even', ['3:2', '2:3'])
        if isinstance(odd_even_options, str):
            odd_even_options = odd_even_options.split(',')
        if 'disabled' not in odd_even_options:
            passed, actual = check_odd_even_ratio(front_balls, odd_even_options)
            if not passed:
                logger.debug(f"DLT FAIL: odd_even. balls={front_balls}, actual={actual}, expected={odd_even_options}")
                return False
            logger.debug(f"DLT PASS: odd_even. actual={actual}")
    
    # 7. 最大跨度原则 - 支持多选
    if 'span' not in ignored_rules:
        span_options = options.get('span', ['gt_28'])
        if isinstance(span_options, str):
            span_options = [span_options]
        if 'disabled' not in span_options:
            passed = False
            for opt in span_options:
                if opt == 'lt_20':
                    p, span = check_max_span(front_balls, max_span=20)
                    if p: passed = True; break
                elif opt == 'gt_20':
                    p, span = check_max_span(front_balls, min_span=20)
                    if p: passed = True; break
                elif opt == 'gt_22':
                    p, span = check_max_span(front_balls, min_span=22)
                    if p: passed = True; break
                elif opt == 'gt_24':
                    p, span = check_max_span(front_balls, min_span=24)
                    if p: passed = True; break
                elif opt == 'gt_26':
                    p, span = check_max_span(front_balls, min_span=26)
                    if p: passed = True; break
                elif opt == 'gt_28':
                    p, span = check_max_span(front_balls, min_span=28)
                    if p: passed = True; break
                elif opt == 'gt_30':
                    p, span = check_max_span(front_balls, min_span=30)
                    if p: passed = True; break
            if not passed:
                logger.debug(f"DLT FAIL: span. balls={front_balls}, span={span}, options={span_options}")
                return False
            logger.debug(f"DLT PASS: span. span={span}")
    
    # 8. 号码总和原则 - 支持多选（checkbox）
    if 'sum' not in ignored_rules:
        sum_options = options.get('sum', ['71-90', '91-110'])
        if isinstance(sum_options, str):
            sum_options = [sum_options]
        if 'disabled' not in sum_options:
            passed = False
            for opt in sum_options:
                if opt == 'lt_70':
                    p, total = check_sum_range(front_balls, 1, 69)
                    if p: passed = True; break
                elif opt == '71-90':
                    p, total = check_sum_range(front_balls, 71, 90)
                    if p: passed = True; break
                elif opt == '91-110':
                    p, total = check_sum_range(front_balls, 91, 110)
                    if p: passed = True; break
                elif opt == '111-120':
                    p, total = check_sum_range(front_balls, 111, 120)
                    if p: passed = True; break
                elif opt == 'gt_120':
                    p, total = check_sum_range(front_balls, 121, 200)
                    if p: passed = True; break
            if not passed:
                logger.debug(f"DLT FAIL: sum. balls={front_balls}, total={total}, options={sum_options}")
                return False
            logger.debug(f"DLT PASS: sum. total={total}")
    
    # 9. 同尾号原则 - 支持多选（checkbox）
    if 'same_tail' not in ignored_rules:
        tail_options = options.get('same_tail', ['1'])
        if isinstance(tail_options, str):
            tail_options = [tail_options]
        if 'disabled' not in tail_options:
            passed = False
            for opt in tail_options:
                if opt == 'exactly_1' or opt == '1':
                    p, count = check_same_tail(front_balls, '1')
                    if p: passed = True; break
                elif opt == 'at_least_1':
                    p, count = check_same_tail(front_balls, 'at_least_1')
                    if p: passed = True; break
                elif opt == 'none' or opt == '0':
                    p, count = check_same_tail(front_balls, '0')
                    if p: passed = True; break
                elif opt == '2':
                    p, count = check_same_tail(front_balls, '2')
                    if p: passed = True; break
                elif opt == '3':
                    p, count = check_same_tail(front_balls, '3')
                    if p: passed = True; break
            if not passed:
                logger.debug(f"DLT FAIL: same_tail. balls={front_balls}, count={count}, options={tail_options}")
                return False
            logger.debug(f"DLT PASS: same_tail. count={count}")
    
    # 10. 邻号原则 - 支持多选（0,1,2,3,4,disabled）
    if 'neighbor' not in ignored_rules:
        neighbor_options = options.get('neighbor', ['1'])
        if isinstance(neighbor_options, str):
            neighbor_options = [neighbor_options]
        if 'disabled' not in neighbor_options:
            passed = False
            for opt in neighbor_options:
                neighbor_count = int(opt) if opt.isdigit() else None
                if neighbor_count is not None:
                    p, count = check_neighbor_numbers(front_balls, 'dlt', neighbor_count, 'exactly')
                    if p: passed = True; break
            if not passed:
                logger.debug(f"DLT FAIL: neighbor. balls={front_balls}, count={count}, options={neighbor_options}")
                return False
            logger.debug(f"DLT PASS: neighbor. count={count}")
    
    # 11. AC值原则 - 支持多选（DLT: 0,1,2,3,4,5,6,disabled）
    if 'ac_value' not in ignored_rules:
        ac_options = options.get('ac_value', ['5'])
        if isinstance(ac_options, str):
            ac_options = [ac_options]
        if 'disabled' not in ac_options:
            passed = False
            for opt in ac_options:
                if opt in ['0', '1', '2', '3', '4', '5', '6']:
                    p, ac = check_ac_value(front_balls, [int(opt)])
                    if p: passed = True; break
            if not passed:
                logger.debug(f"DLT FAIL: ac_value. balls={front_balls}, ac={ac}, options={ac_options}")
                return False
            logger.debug(f"DLT PASS: ac_value. ac={ac}")
    
    # 12. 后区选择 - 验证选中的后区号码是否在 blue_selected_balls 中
    blue_selected = options.get('blue_selected_balls', None)
    if blue_selected:
        for b in blue_balls:
            if b not in blue_selected:
                logger.debug(f"DLT FAIL: blue_selected_balls. blue_balls={blue_balls}, selected={blue_selected}")
                return False
    
    # 13. 蓝球后区原则
    # 遗漏规则（仅在未指定具体后区号码时使用）
    blue_selected = options.get('blue_selected_balls', None)
    blue_omission_options = options.get('blue_omission', ['disabled'])
    if isinstance(blue_omission_options, str):
        blue_omission_options = [blue_omission_options]
    if 'disabled' not in blue_omission_options and 'any' not in blue_omission_options and not blue_selected:
        passed = False
        for opt in blue_omission_options:
            if opt in ['5-15_primary', '0-2_primary', '0-4_primary']:
                p, msg = check_dlt_blue_omission(blue_balls, blue_omission, mode=opt)
                if p: passed = True; break
        if not passed:
            logger.debug(f"DLT FAIL: blue_omission. blue_balls={blue_balls}, msg={msg}")
            return False
        logger.debug(f"DLT PASS: blue_omission.")
    
    # 后区奇偶（仅在未指定具体后区号码时使用）
    blue_odd_even_options = options.get('blue_odd_even', ['disabled'])
    if isinstance(blue_odd_even_options, str):
        blue_odd_even_options = [blue_odd_even_options]
    if 'disabled' not in blue_odd_even_options and not blue_selected:
        passed = False
        for opt in blue_odd_even_options:
            if opt == '1_odd_1_even':
                p, actual = check_dlt_blue_odd_even(blue_balls, '1:1')
                if p: passed = True; break
            elif opt == '2_odd':
                p, actual = check_dlt_blue_odd_even(blue_balls, '2:0')
                if p: passed = True; break
            elif opt == '2_even':
                p, actual = check_dlt_blue_odd_even(blue_balls, '0:2')
                if p: passed = True; break
        if not passed:
            logger.debug(f"DLT FAIL: blue_odd_even. blue_balls={blue_balls}, actual={actual}, options={blue_odd_even_options}")
            return False
        logger.debug(f"DLT PASS: blue_odd_even. actual={actual}")
    
    # 后区大小（仅在未指定具体后区号码时使用）
    blue_size_options = options.get('blue_size', ['disabled'])
    if isinstance(blue_size_options, str):
        blue_size_options = [blue_size_options]
    if 'disabled' not in blue_size_options and not blue_selected:
        passed = False
        for opt in blue_size_options:
            if opt == '1_big_1_small':
                p, actual = check_dlt_blue_size(blue_balls, '1:1')
                if p: passed = True; break
            elif opt == '2_big':
                p, actual = check_dlt_blue_size(blue_balls, '2:0')
                if p: passed = True; break
            elif opt == '2_small':
                p, actual = check_dlt_blue_size(blue_balls, '0:2')
                if p: passed = True; break
        if not passed:
            logger.debug(f"DLT FAIL: blue_size. blue_balls={blue_balls}, actual={actual}, options={blue_size_options}")
            return False
        logger.debug(f"DLT PASS: blue_size. actual={actual}")
    
    return True


def _calculate_stats(lottery_type, red_balls, blue_balls):
    """计算号码组合的统计信息"""
    red_odd = sum(1 for b in red_balls if b % 2 == 1)
    red_even = len(red_balls) - red_odd
    red_sum = calculate_sum_per_draw(red_balls)
    red_span = calculate_span_per_draw(red_balls)
    red_small = sum(1 for b in red_balls if b <= (17 if lottery_type == 'ssq' else 18))
    red_large = len(red_balls) - red_small
    
    blue_odd = sum(1 for b in blue_balls if b % 2 == 1)
    blue_even = len(blue_balls) - blue_odd
    blue_sum = calculate_sum_per_draw(blue_balls)
    blue_span = calculate_span_per_draw(blue_balls)
    blue_small = sum(1 for b in blue_balls if b <= (8 if lottery_type == 'ssq' else 6))
    blue_large = len(blue_balls) - blue_small
    
    return {
        'red_odd_even_ratio': f"{red_odd}:{red_even}",
        'red_sum': red_sum,
        'red_span': red_span,
        'red_size_ratio': f"{red_small}:{red_large}",
        'blue_odd_even_ratio': f"{blue_odd}:{blue_even}",
        'blue_sum': blue_sum,
        'blue_span': blue_span,
        'blue_size_ratio': f"{blue_small}:{blue_large}"
    }


# ==================== 智能筛选规则统计 ====================

def calculate_smart_filter_stats_for_draw(lottery_type, draw):
    """
    计算一期开奖号码的所有智能筛选规则实际值
    返回规则名 -> 规则值的字典
    """
    red_balls = draw.get_red_balls_list()
    blue_balls = draw.get_blue_balls_list()
    
    stats = {}
    
    # 获取遗漏数据（用于遗漏号原则计算）
    all_draws = get_latest_draws_for_smart(lottery_type, 200)
    red_omission, blue_omission = get_omission_data(lottery_type, all_draws)
    
    if lottery_type == 'ssq':
        # 1. 分区原则
        _, zone_actual = check_ssq_red_zone_distribution(red_balls, "2:2:2")
        stats['zone_ratio'] = zone_actual
        
        # 2. 连号
        _, count, groups = check_consecutive_balls(red_balls, max_groups=3, max_length=3)
        if count == 0:
            stats['consecutive'] = '无连号'
        else:
            group_strs = []
            for g in groups:
                group_strs.append(f"{len(g)}连号")
            stats['consecutive'] = f"{count}组{' + '.join(group_strs)}"
        
        # 3. 与上期重号
        _, repeat_count = check_repeat_with_previous(red_balls, 'ssq', min_repeat=0, max_repeat=6)
        stats['repeat'] = str(repeat_count)
        
        # 4. 遗漏号原则 - 计算热温冷分布
        hot = sum(1 for b in red_balls if red_omission.get(b, 0) <= 4)
        warm = sum(1 for b in red_balls if 5 <= red_omission.get(b, 0) <= 9)
        cold = sum(1 for b in red_balls if red_omission.get(b, 0) >= 10)
        stats['omission_pattern'] = f"热{hot}温{warm}冷{cold}"
        
        # 5. 奇偶比
        _, oe_actual = check_odd_even_ratio(red_balls, ["3:3"])
        stats['odd_even'] = oe_actual
        
        # 6. 最大跨度
        _, span = check_max_span(red_balls, min_span=1)
        stats['span'] = str(span)
        
        # 7. 号码总和
        _, total_sum = check_sum_range(red_balls, 1, 200)
        stats['sum'] = str(total_sum)
        
        # 8. 同尾号
        _, tail_count = check_same_tail(red_balls, 'at_least_1')
        stats['same_tail'] = str(tail_count)
        
        # 9. 邻号
        _, neighbor_count = check_neighbor_numbers(red_balls, 'ssq', 0)
        stats['neighbor'] = str(neighbor_count)
        
        # 10. AC值
        _, ac = check_ac_value(red_balls, [1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
        stats['ac_value'] = str(ac)
        
        # 11. 蓝球遗漏 - 原始遗漏期数
        stats['blue_omission'] = str(blue_omission.get(blue_balls[0], 0))
        
    else:  # dlt
        # 1. 分区原则
        _, zone_actual = check_dlt_front_zone_distribution(red_balls, ["2:2:1"])
        stats['zone_ratio'] = zone_actual
        
        # 2. 连号
        _, count, groups = check_consecutive_balls(red_balls, max_groups=3, max_length=3)
        if count == 0:
            stats['consecutive'] = '无连号'
        else:
            group_strs = []
            for g in groups:
                group_strs.append(f"{len(g)}连号")
            stats['consecutive'] = f"{count}组{' + '.join(group_strs)}"
        
        # 3. 与上期重号
        _, repeat_count = check_repeat_with_previous(red_balls, 'dlt', min_repeat=0, max_repeat=5)
        stats['repeat'] = str(repeat_count)
        
        # 4. 遗漏号原则
        hot = sum(1 for b in red_balls if red_omission.get(b, 0) <= 4)
        warm = sum(1 for b in red_balls if 5 <= red_omission.get(b, 0) <= 9)
        cold = sum(1 for b in red_balls if red_omission.get(b, 0) >= 10)
        stats['omission_pattern'] = f"热{hot}温{warm}冷{cold}"
        
        # 5. 奇偶比
        _, oe_actual = check_odd_even_ratio(red_balls, ["3:2"])
        stats['odd_even'] = oe_actual
        
        # 6. 最大跨度
        _, span = check_max_span(red_balls, min_span=1)
        stats['span'] = str(span)
        
        # 7. 号码总和
        _, total_sum = check_sum_range(red_balls, 1, 200)
        stats['sum'] = str(total_sum)
        
        # 8. 同尾号
        _, tail_count = check_same_tail(red_balls, 'at_least_1')
        stats['same_tail'] = str(tail_count)
        
        # 9. 邻号
        _, neighbor_count = check_neighbor_numbers(red_balls, 'dlt', 0)
        stats['neighbor'] = str(neighbor_count)
        
        # 10. AC值
        _, ac = check_ac_value(red_balls, [1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
        stats['ac_value'] = str(ac)
        
        # 11. 后区遗漏 - 每个球的原始遗漏期数，用逗号分隔
        omissions = [str(blue_omission.get(b, 0)) for b in blue_balls]
        stats['blue_omission'] = ','.join(omissions)
        
        # 12. 后区奇偶
        _, blue_oe = check_dlt_blue_odd_even(blue_balls, '1:1')
        stats['blue_odd_even'] = blue_oe
        
        # 13. 后区大小
        _, blue_size = check_dlt_blue_size(blue_balls, '1:1')
        stats['blue_size'] = blue_size
    
    return stats


def update_smart_filter_stats(lottery_type, app=None):
    """
    更新智能筛选规则统计数据
    1. 遍历所有开奖数据，计算每期的规则值
    2. 更新 SmartFilterStats 表
    3. 重新计算排名并更新 SmartFilterStatsRanking 表（按不同回溯期数分别统计）
    """
    from models import SmartFilterStats, SmartFilterStatsRanking, SSQDraw, DLTDraw, db
    from collections import Counter
    from datetime import datetime
    
    model_class = SSQDraw if lottery_type == 'ssq' else DLTDraw
    
    if app:
        app.logger.info(f"开始更新 {lottery_type} 智能筛选规则统计...")
    
    # 获取所有开奖数据（按期号升序，从旧到新）
    all_draws = model_class.query.order_by(model_class.issue.asc()).all()
    
    if not all_draws:
        if app:
            app.logger.warning(f"没有 {lottery_type} 开奖数据，跳过统计更新")
        return
    
    if app:
        app.logger.info(f"共 {len(all_draws)} 期 {lottery_type} 数据需要处理")
    
    # 逐期计算并保存
    new_count = 0
    for draw in all_draws:
        # 检查是否已存在该期的统计
        existing = SmartFilterStats.query.filter_by(
            lottery_type=lottery_type,
            issue=draw.issue
        ).first()
        if existing:
            continue  # 已存在，跳过
        
        # 计算该期的所有规则值
        stats = calculate_smart_filter_stats_for_draw(lottery_type, draw)
        
        # 保存到数据库
        for rule_name, rule_value in stats.items():
            record = SmartFilterStats(
                lottery_type=lottery_type,
                issue=draw.issue,
                draw_date=draw.draw_date,
                rule_name=rule_name,
                rule_value=str(rule_value)
            )
            db.session.add(record)
            new_count += 1
    
    db.session.commit()
    
    if app:
        app.logger.info(f"新增 {new_count} 条 {lottery_type} 智能筛选规则统计记录")
    
    # 重新计算排名（按不同回溯期数）
    _update_smart_filter_rankings(lottery_type, app)
    
    if app:
        app.logger.info(f"{lottery_type} 智能筛选规则统计更新完成")
    return new_count


def _update_smart_filter_rankings(lottery_type, app=None):
    """
    重新计算指定彩票类型的智能筛选规则排名（前3名）
    按不同回溯期数分别统计：50, 100, 200, 500, 0(全部)
    包含出现次数和百分比
    """
    from models import SmartFilterStats, SmartFilterStatsRanking, SSQDraw, DLTDraw, db
    from collections import Counter
    
    # 定义要统计的回溯期数
    lookback_periods = [50, 100, 200, 500, 0]  # 0 表示全部
    
    # 获取所有规则名称
    rule_names = db.session.query(SmartFilterStats.rule_name).filter_by(
        lottery_type=lottery_type
    ).distinct().all()
    rule_names = [r[0] for r in rule_names]
    
    # 获取所有期号（按降序排列，最新的在前）
    model_class = SSQDraw if lottery_type == 'ssq' else DLTDraw
    all_issues = db.session.query(SmartFilterStats.issue).filter_by(
        lottery_type=lottery_type
    ).distinct().order_by(SmartFilterStats.issue.desc()).all()
    all_issues = [r[0] for r in all_issues]
    
    latest_issue = all_issues[0] if all_issues else ""
    
    if app:
        app.logger.info(f"重新计算 {lottery_type} 排名，共 {len(rule_names)} 个规则，{len(all_issues)} 期数据")
    
    # 删除旧排名
    SmartFilterStatsRanking.query.filter_by(lottery_type=lottery_type).delete()
    db.session.commit()
    
    # 为每个回溯期数计算排名（排除 blue_omission，因为蓝球遗漏使用单独的逐个号码排名）
    for lookback in lookback_periods:
        # 确定要统计的期号范围
        if lookback == 0:
            # 全部期数
            target_issues = all_issues
        else:
            target_issues = all_issues[:lookback]
        
        if not target_issues:
            continue
        
        total_draws = len(target_issues)
        
        if app:
            app.logger.info(f"  计算 {lottery_type} 回溯{lookback}期排名（{total_draws}期数据）")
        
        # 为每个规则计算排名（排除 blue_omission，由下方单独处理）
        for rule_name in rule_names:
            if rule_name == 'blue_omission':
                continue  # 跳过 blue_omission，使用下方的逐个号码排名
            
            # 获取该规则在目标期号范围内的所有值
            records = SmartFilterStats.query.filter(
                SmartFilterStats.lottery_type == lottery_type,
                SmartFilterStats.rule_name == rule_name,
                SmartFilterStats.issue.in_(target_issues)
            ).all()
            
            if not records:
                continue
            
            # 统计各值出现频率
            value_counts = Counter(r.rule_value for r in records)
            
            # 按频率降序排列，取前3名
            top_3 = value_counts.most_common(3)
            
            # 保存排名
            for rank, (value, freq) in enumerate(top_3, 1):
                percentage = round((freq / total_draws) * 100, 1) if total_draws > 0 else 0.0
                ranking = SmartFilterStatsRanking(
                    lottery_type=lottery_type,
                    lookback_period=lookback,
                    rule_name=rule_name,
                    rule_value=value,
                    frequency=freq,
                    percentage=percentage,
                    rank=rank,
                    total_draws=total_draws,
                    last_updated_issue=latest_issue
                )
                db.session.add(ranking)
    
    db.session.commit()
    
    # ==================== 蓝球遗漏排名计算 ====================
    # 为每个回溯期数计算每个蓝球的出现频率排名
    if app:
        app.logger.info(f"开始计算 {lottery_type} 蓝球遗漏排名...")
    
    blue_range = 16 if lottery_type == 'ssq' else 12
    
    for lookback in lookback_periods:
        # 确定要统计的期号范围
        if lookback == 0:
            target_issues = all_issues
        else:
            target_issues = all_issues[:lookback]
        
        if not target_issues or not target_issues:
            continue
        
        # 获取该回溯期数内的所有开奖数据
        target_draws = model_class.query.filter(
            model_class.issue.in_(target_issues)
        ).order_by(model_class.issue.desc()).all()
        
        if not target_draws:
            continue
        
        # 计算所有蓝球的出现频率和遗漏数据
        from utils import calculate_frequency_and_omissions_for_balls
        blue_stats_list, blue_num_draws = calculate_frequency_and_omissions_for_balls(target_draws, blue_range, 'blue')
        
        # 按出现频率降序排列（出现次数越多排名越前）
        sorted_by_frequency = sorted(blue_stats_list, key=lambda x: x['frequency_count'], reverse=True)
        
        # 存储所有蓝球的排名
        for rank_idx, item in enumerate(sorted_by_frequency, 1):
            ball_num = item['ball']
            freq_count = item['frequency_count']
            freq_pct = item['frequency_percentage']
            
            ranking = SmartFilterStatsRanking(
                lottery_type=lottery_type,
                lookback_period=lookback,
                rule_name='blue_omission',
                rule_value=str(ball_num).zfill(2),
                frequency=freq_count,
                percentage=round(freq_pct, 2),
                rank=rank_idx,
                total_draws=blue_num_draws,
                last_updated_issue=latest_issue
            )
            db.session.add(ranking)
    
    db.session.commit()
    
    if app:
        app.logger.info(f"{lottery_type} 排名更新完成（共 {len(lookback_periods)} 个回溯期数，含蓝球遗漏排名）")
