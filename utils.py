# utils.py
from datetime import datetime, timedelta, date
import math
from collections import Counter, OrderedDict
import random
from config import PRIZE_RULES, CURRENT_SETTINGS, PER_BET_PRICE # 导入中奖规则和当前设置
from models import SSQDraw, DLTDraw, db # 新增导入

# 版本号，每次生成文件时更新
__version__ = "1.0.2" # 更新版本号

def format_lottery_numbers(numbers_str):
    """将逗号分隔的数字字符串转换为整数列表并排序"""
    try:
        return sorted([int(x) for x in numbers_str.split(',') if x.strip()]) # 确保处理空字符串
    except (ValueError, AttributeError):
        return []

def get_consecutive_groups(numbers):
    """
    识别数字列表中的连续号码组。
    返回一个列表，每个元素是一个连续号码组的列表。
    例如: [1, 2, 3, 5, 6] -> [[1, 2, 3], [5, 6]]
    """
    if not numbers:
        return []
    sorted_numbers = sorted(list(set(numbers))) # 去重并排序
    groups = []
    current_group = [sorted_numbers[0]]

    for i in range(1, len(sorted_numbers)):
        if sorted_numbers[i] == sorted_numbers[i-1] + 1:
            current_group.append(sorted_numbers[i])
        else:
            groups.append(current_group)
            current_group = [sorted_numbers[i]]
    groups.append(current_group)
    
    # 创建一个字典，将每个连续的球映射到其组索引
    consecutive_map = {}
    for idx, group in enumerate(groups):
        if len(group) > 1: # 只对长度大于1的连续组进行标记
            for ball in group:
                consecutive_map[ball] = idx % 3 # 使用模3来循环分配三种颜色

    return groups, consecutive_map

def calculate_omissions(all_draws, ball_range, ball_type='red'):
    """
    计算每个号码的遗漏期数。
    all_draws: 历史开奖数据列表 (例如 SSQDraw.query.order_by(SSQDraw.issue.desc()).all())
    ball_range: 号码范围 (例如双色球红球 1-33)
    ball_type: 'red' 或 'blue'
    返回一个字典 {号码: 遗漏期数}
    """
    omissions = {i: 0 for i in range(1, ball_range + 1)}
    last_seen = {i: -1 for i in range(1, ball_range + 1)} # 记录上次出现是第几期 (从最新期开始倒数)

    for i, draw in enumerate(all_draws):
        balls = []
        if ball_type == 'red':
            balls = draw.get_red_balls_list()
        elif ball_type == 'blue':
            balls = draw.get_blue_balls_list()

        for ball in range(1, ball_range + 1):
            if ball in balls:
                if last_seen[ball] == -1: # 第一次出现
                    omissions[ball] = 0
                else:
                    omissions[ball] = i - last_seen[ball] -1 # 遗漏期数 = 当前期数 - 上次出现期数 - 1
                last_seen[ball] = i
            elif last_seen[ball] == -1: # 如果从未出现过，则遗漏期数持续增加
                omissions[ball] = i + 1 # 从最新期开始，遗漏了 i+1 期
            else: # 出现过，但本期没出现，遗漏期数增加
                omissions[ball] = i - last_seen[ball]

    # 对于最新一期之后仍未出现的号码，其遗漏期数是当前期数
    for ball in range(1, ball_range + 1):
        if last_seen[ball] == -1:
            omissions[ball] = len(all_draws) # 如果从未出现，遗漏期数就是总期数
        else:
            omissions[ball] = len(all_draws) - last_seen[ball] - 1 # 遗漏期数 = 总期数 - 上次出现期数 - 1

    return omissions

def calculate_frequency(all_draws, ball_range, ball_type='red'):
    """
    计算每个号码的出现频率。
    返回一个字典 {号码: 出现次数}
    """
    frequency = {i: 0 for i in range(1, ball_range + 1)}
    total_draws = len(all_draws)
    if total_draws == 0:
        return frequency

    for draw in all_draws:
        balls = []
        if ball_type == 'red':
            balls = draw.get_red_balls_list()
        elif ball_type == 'blue':
            balls = draw.get_blue_balls_list()
        for ball in balls:
            if ball in frequency:
                frequency[ball] += 1
    return frequency

def calculate_odd_even_sum(draw_balls_list): # 接收的是列表，不是draw对象
    """计算数字列表的奇偶比和总和"""
    numbers = sorted([int(x) for x in draw_balls_list if x is not None]) # 确保是数字列表
    if not numbers:
        return 0, 0, 0 # 默认值

    odd_count = sum(1 for n in numbers if n % 2 != 0)
    even_count = len(numbers) - odd_count
    total_sum = sum(numbers)
    return odd_count, even_count, total_sum # 返回一个元组

def calculate_frequency_and_omissions_for_balls(draws_list, ball_range, ball_type):
    """
    计算指定球类型（红球或蓝球）的出现频率、当前遗漏和最大遗漏。
    draws_list: 降序排列的开奖数据列表 (最新在前面)
    ball_range: 球的最大值 (例如，双色球红球33，蓝球16)
    ball_type: 'red' 或 'blue'
    """
    stats = {i: {'frequency_count': 0, 'current_omission': 0, 'max_omission': 0, 'last_seen_index': -1} 
             for i in range(1, ball_range + 1)}
    
    total_draws_in_range = len(draws_list)

    # 第一次遍历：计算出现频率和最大遗漏
    for draw_index, draw in enumerate(draws_list):
        balls = draw.get_red_balls_list() if ball_type == 'red' else draw.get_blue_balls_list()
        
        # 更新当前期出现的球的最后出现位置
        for ball in balls:
            if 1 <= ball <= ball_range:
                stats[ball]['frequency_count'] += 1
                stats[ball]['last_seen_index'] = draw_index # 更新最后出现位置

        # 对于本期未出现的球，更新其遗漏计数
        for b_num in range(1, ball_range + 1):
            if b_num not in balls:
                if stats[b_num]['last_seen_index'] != -1: # 如果之前出现过
                    current_omission_since_last_seen = draw_index - stats[b_num]['last_seen_index']
                    if current_omission_since_last_seen > stats[b_num]['max_omission']:
                        stats[b_num]['max_omission'] = current_omission_since_last_seen
                # 如果从未出现过，max_omission 保持 0，current_omission 会在第二次遍历中处理

    # 第二次遍历：计算当前遗漏
    for ball_num in range(1, ball_range + 1):
        found_in_recent = False
        for draw_index, draw in enumerate(draws_list):
            balls = draw.get_red_balls_list() if ball_type == 'red' else draw.get_blue_balls_list()
            if ball_num in balls:
                stats[ball_num]['current_omission'] = draw_index # 遗漏期数是它在列表中的索引 (0表示最新一期出现)
                found_in_recent = True
                break
        if not found_in_recent:
            stats[ball_num]['current_omission'] = total_draws_in_range # 如果在范围内从未出现，遗漏期数就是总期数

        # 确保 max_omission 至少是 current_omission
        if stats[ball_num]['current_omission'] > stats[ball_num]['max_omission']:
            stats[ball_num]['max_omission'] = stats[ball_num]['current_omission']

    # 计算频率百分比
    for ball_num in range(1, ball_range + 1):
        if total_draws_in_range > 0:
            stats[ball_num]['frequency_percentage'] = (stats[ball_num]['frequency_count'] / total_draws_in_range) * 100
        else:
            stats[ball_num]['frequency_percentage'] = 0

    # 将字典转换为列表，方便模板遍历和排序
    stats_list = []
    for ball_num in range(1, ball_range + 1):
        stats_list.append({
            'ball': ball_num,
            'frequency_count': stats[ball_num]['frequency_count'],
            'frequency_percentage': round(stats[ball_num]['frequency_percentage'], 2),
            'current_omission': stats[ball_num]['current_omission'],
            'max_omission': stats[ball_num]['max_omission']
        })
    
    return stats_list, total_draws_in_range


# --- 辅助函数：判断是否为质数 ---
def is_prime(n):
    if n < 2:
        return False
    for i in range(2, int(math.sqrt(n)) + 1):
        if n % i == 0:
            return False
    return True

# --- 单期开奖的统计计算函数 ---

def calculate_size_ratio_per_draw(balls, mid_point):
    """计算单期号码的大小比"""
    small_count = sum(1 for ball in balls if ball < mid_point)
    large_count = len(balls) - small_count
    return f"{small_count}:{large_count}"

def calculate_prime_composite_ratio_per_draw(balls):
    """计算单期号码的质合比"""
    prime_count = sum(1 for ball in balls if is_prime(ball))
    composite_count = sum(1 for ball in balls if not is_prime(ball) and ball != 1) # 1既非质数也非合数
    return f"{prime_count}:{composite_count}"

def calculate_012_way_ratio_per_draw(balls):
    """计算单期号码的012路比"""
    count_0 = sum(1 for ball in balls if ball % 3 == 0)
    count_1 = sum(1 for ball in balls if ball % 3 == 1)
    count_2 = sum(1 for ball in balls if ball % 3 == 2)
    return f"{count_0}:{count_1}:{count_2}"

def calculate_consecutive_stats_per_draw(balls):
    """计算单期号码的连号数量和最长连号长度"""
    groups = get_consecutive_groups(balls)
    groups_count = len(groups)
    max_length = max((len(g) for g in groups), default=0)
    return {'groups_count': groups_count, 'max_length': max_length}

def calculate_repeated_count_per_draw(current_balls, previous_balls):
    """计算单期号码与前一期号码的重号数量"""
    if not previous_balls:
        return 0
    current_set = set(current_balls)
    previous_set = set(previous_balls)
    return len(current_set.intersection(previous_set))

def calculate_span_per_draw(balls):
    """计算单期号码的跨度"""
    if not balls:
        return 0
    return max(balls) - min(balls)

def calculate_head_tail_per_draw(balls):
    """计算单期号码的龙头凤尾"""
    if not balls:
        return {'head': None, 'tail': None}
    sorted_balls = sorted(balls)
    return {'head': sorted_balls[0], 'tail': sorted_balls[-1]}

def calculate_ac_value_per_draw(balls):
    """计算单期号码的AC值"""
    if len(balls) < 2:
        return 0
    
    diffs = set()
    sorted_balls = sorted(balls)
    for i in range(len(sorted_balls)):
        for j in range(i + 1, len(sorted_balls)):
            diffs.add(sorted_balls[j] - sorted_balls[i])
    
    return len(diffs) - (len(balls) - 1)

# --- 聚合统计函数 (用于 statistics 页面) ---

def get_aggregated_stats(draws_list, lottery_type, config_settings):
    """
    计算并聚合所有指定维度的统计数据。
    draws_list: 降序排列的开奖数据列表 (最新在前面)
    lottery_type: 'ssq' 或 'dlt'
    config_settings: 包含大小号界限等配置的字典
    """
    if not draws_list:
        return {
            'total_draws': 0,
            'red_stats': [],
            'blue_stats': [],
            'red_size_ratio_counts': {},
            'red_prime_composite_ratio_counts': {},
            'red_012_way_ratio_counts': {},
            'red_consecutive_groups_counts': {},
            'red_max_consecutive_length_counts': {},
            'red_repeated_counts': {},
            'red_span_counts': {},
            'red_head_counts': {},
            'red_tail_counts': {},
            'red_ac_value_counts': {},
            'blue_size_ratio_counts': {},
            'blue_prime_composite_ratio_counts': {},
            'blue_012_way_ratio_counts': {},
            'blue_repeated_counts': {},
            'blue_head_counts': {},
            'blue_tail_counts': {},
        }

    total_draws = len(draws_list)
    
    # 初始化聚合计数器
    red_size_ratio_counts = Counter()
    red_prime_composite_ratio_counts = Counter()
    red_012_way_ratio_counts = Counter()
    red_consecutive_groups_counts = Counter()
    red_max_consecutive_length_counts = Counter()
    red_repeated_counts = Counter()
    red_span_counts = Counter()
    red_head_counts = Counter()
    red_tail_counts = Counter()
    red_ac_value_counts = Counter()

    blue_size_ratio_counts = Counter()
    blue_prime_composite_ratio_counts = Counter()
    blue_012_way_ratio_counts = Counter()
    blue_repeated_counts = Counter()
    blue_head_counts = Counter()
    blue_tail_counts = Counter()

    # 获取配置参数
    if lottery_type == 'ssq':
        red_ball_range = 33
        blue_ball_range = 16
        red_size_midpoint = config_settings.get('ssq_red_size_midpoint', 17)
        blue_size_midpoint = config_settings.get('ssq_blue_size_midpoint', 9)
    else: # dlt
        red_ball_range = 35
        blue_ball_range = 12
        red_size_midpoint = config_settings.get('dlt_front_size_midpoint', 18)
        blue_size_midpoint = config_settings.get('dlt_back_size_midpoint', 7)

    # 遍历所有开奖数据进行单期计算和聚合
    for i, draw in enumerate(draws_list):
        current_red_balls = draw.get_red_balls_list()
        current_blue_balls = draw.get_blue_balls_list()
        
        # 获取前一期数据用于重号计算
        previous_red_balls = []
        previous_blue_balls = []
        if i + 1 < total_draws: # 确保有前一期
            previous_draw = draws_list[i+1]
            previous_red_balls = previous_draw.get_red_balls_list()
            previous_blue_balls = previous_draw.get_blue_balls_list()

        # 红球统计
        if current_red_balls:
            red_size_ratio_counts[calculate_size_ratio_per_draw(current_red_balls, red_size_midpoint)] += 1
            red_prime_composite_ratio_counts[calculate_prime_composite_ratio_per_draw(current_red_balls)] += 1
            red_012_way_ratio_counts[calculate_012_way_ratio_per_draw(current_red_balls)] += 1
            
            consecutive_stats = calculate_consecutive_stats_per_draw(current_red_balls)
            red_consecutive_groups_counts[consecutive_stats['groups_count']] += 1
            red_max_consecutive_length_counts[consecutive_stats['max_length']] += 1
            
            red_repeated_counts[calculate_repeated_count_per_draw(current_red_balls, previous_red_balls)] += 1
            red_span_counts[calculate_span_per_draw(current_red_balls)] += 1
            
            head_tail = calculate_head_tail_per_draw(current_red_balls)
            if head_tail['head'] is not None:
                red_head_counts[head_tail['head']] += 1
            if head_tail['tail'] is not None:
                red_tail_counts[head_tail['tail']] += 1
            
            red_ac_value_counts[calculate_ac_value_per_draw(current_red_balls)] += 1

        # 蓝球统计
        if current_blue_balls:
            blue_size_ratio_counts[calculate_size_ratio_per_draw(current_blue_balls, blue_size_midpoint)] += 1
            blue_prime_composite_ratio_counts[calculate_prime_composite_ratio_per_draw(current_blue_balls)] += 1
            blue_012_way_ratio_counts[calculate_012_way_ratio_per_draw(current_blue_balls)] += 1
            blue_repeated_counts[calculate_repeated_count_per_draw(current_blue_balls, previous_blue_balls)] += 1
            
            head_tail = calculate_head_tail_per_draw(current_blue_balls)
            if head_tail['head'] is not None:
                blue_head_counts[head_tail['head']] += 1
            if head_tail['tail'] is not None:
                blue_tail_counts[head_tail['tail']] += 1

    # 计算单个号码的频率和遗漏 (使用原有的逻辑，但现在是针对 draws_list)
    red_ball_stats_list, _ = calculate_frequency_and_omissions_for_balls(draws_list, red_ball_range, 'red')
    blue_ball_stats_list, _ = calculate_frequency_and_omissions_for_balls(draws_list, blue_ball_range, 'blue')

    return {
        'total_draws': total_draws,
        'red_stats': red_ball_stats_list,
        'blue_stats': blue_ball_stats_list,
        'red_size_ratio_counts': dict(red_size_ratio_counts),
        'red_prime_composite_ratio_counts': dict(red_prime_composite_ratio_counts),
        'red_012_way_ratio_counts': dict(red_012_way_ratio_counts),
        'red_consecutive_groups_counts': dict(red_consecutive_groups_counts),
        'red_max_consecutive_length_counts': dict(red_max_consecutive_length_counts),
        'red_repeated_counts': dict(red_repeated_counts),
        'red_span_counts': dict(red_span_counts),
        'red_head_counts': dict(red_head_counts),
        'red_tail_counts': dict(red_tail_counts),
        'red_ac_value_counts': dict(red_ac_value_counts),
        'blue_size_ratio_counts': dict(blue_size_ratio_counts),
        'blue_prime_composite_ratio_counts': dict(blue_prime_composite_ratio_counts),
        'blue_012_way_ratio_counts': dict(blue_012_way_ratio_counts),
        'blue_repeated_counts': dict(blue_repeated_counts),
        'blue_head_counts': dict(blue_head_counts),
        'blue_tail_counts': dict(blue_tail_counts),
    }

# --- 组合数学函数 ---
def combinations(n, k):
    """计算组合数 C(n, k)"""
    if k < 0 or k > n:
        return 0
    if k == 0 or k == n:
        return 1
    if k > n // 2:
        k = n - k
    
    res = 1
    for i in range(k):
        res = res * (n - i) // (i + 1)
    return res

# --- 计算复式投注花费 ---
def calculate_combination_cost(user_red_balls_count, user_blue_balls_count, lottery_type):
    """
    根据用户选择的红蓝球数量，计算复式投注的总注数和花费。
    user_red_balls_count: 用户选择的红球数量
    user_blue_balls_count: 用户选择的蓝球数量
    lottery_type: 'ssq' 或 'dlt'
    返回: {'total_bets': int, 'total_cost': float}
    """
    if lottery_type == 'ssq':
        # 双色球标准：6红1蓝
        red_bets = combinations(user_red_balls_count, 6)
        blue_bets = combinations(user_blue_balls_count, 1)
    elif lottery_type == 'dlt':
        # 大乐透标准：5红2蓝
        red_bets = combinations(user_red_balls_count, 5)
        blue_bets = combinations(user_blue_balls_count, 2)
    else:
        return {'total_bets': 0, 'total_cost': 0}
    
    total_bets = red_bets * blue_bets
    total_cost = total_bets * PER_BET_PRICE
    return {'total_bets': total_bets, 'total_cost': total_cost}

def calculate_total_lottery_combinations(lottery_type):
    """
    计算指定彩票类型的总组合数。
    """
    if lottery_type == 'ssq':
        # 双色球: 红球 33 选 6, 蓝球 16 选 1
        red_total = 33
        red_pick = 6
        blue_total = 16
        blue_pick = 1
    elif lottery_type == 'dlt':
        # 大乐透: 红球 35 选 5, 蓝球 12 选 2
        red_total = 35
        red_pick = 5
        blue_total = 12
        blue_pick = 2
    else:
        return 0
    return combinations(red_total, red_pick) * combinations(blue_total, blue_pick)


# --- 对奖逻辑辅助函数 ---
def calculate_prize_details(user_red_balls, user_blue_balls, draw_red_balls, draw_blue_balls, lottery_type):
    """
    检查用户号码与一期开奖号码的中奖情况，并计算每个奖项的中奖注数。
    user_red_balls: 用户选择的红球列表 (已排序)
    user_blue_balls: 用户选择的蓝球列表 (已排序)
    draw_red_balls: 开奖红球列表 (已排序)
    draw_blue_balls: 开奖蓝球列表 (已排序)
    lottery_type: 'ssq' 或 'dlt'
    返回: { 'prize_level': count, ... }
    """
    rules = PRIZE_RULES.get(lottery_type)
    if not rules:
        return {}

    # 用户选择的号码集合
    user_red_set = set(user_red_balls)
    user_blue_set = set(user_blue_balls)

    # 开奖号码集合
    draw_red_set = set(draw_red_balls)
    draw_blue_set = set(draw_blue_balls)

    # 匹配的红球和蓝球
    matched_red_balls = user_red_set.intersection(draw_red_set)
    matched_blue_balls = user_blue_set.intersection(draw_blue_set)

    matched_red_count = len(matched_red_balls)
    matched_blue_count = len(matched_blue_balls)

    # 假设标准玩法是 SSQ: 6红1蓝, DLT: 5红2蓝
    standard_red_count = 6 if lottery_type == 'ssq' else 5
    standard_blue_count = 1 if lottery_type == 'ssq' else 2

    # 存储中奖详情
    prize_details = Counter()

    # 遍历所有奖项规则，计算中奖注数
    for prize_rule in rules['prizes']:
        required_red = prize_rule['match_red']
        required_blue = prize_rule['match_blue']

        # 计算红球部分的中奖注数
        # 从用户选中的匹配红球中选 `required_red` 个
        c_matched_red = combinations(matched_red_count, required_red)
        
        # 从用户选中的非匹配红球中选 `standard_red_count - required_red` 个
        # 这些非匹配红球必须是用户选了但开奖号码中没有的
        c_unmatched_red = combinations(len(user_red_set - draw_red_set), standard_red_count - required_red)
        
        red_prize_combinations = c_matched_red * c_unmatched_red

        # 计算蓝球部分的中奖注数
        # 从用户选中的匹配蓝球中选 `required_blue` 个
        c_matched_blue = combinations(matched_blue_count, required_blue)
        
        # 从用户选中的非匹配蓝球中选 `standard_blue_count - required_blue` 个
        c_unmatched_blue = combinations(len(user_blue_set - draw_blue_set), standard_blue_count - required_blue)
        
        blue_prize_combinations = c_matched_blue * c_unmatched_blue
        
        total_prize_count_for_level = red_prize_combinations * blue_prize_combinations
        
        if total_prize_count_for_level > 0:
            prize_details[prize_rule['level']] += total_prize_count_for_level
            
    return prize_details

def _calculate_draws_in_years(lottery_type, num_years, start_date=None):
    """
    计算指定彩票类型在给定年数内的总开奖期数，考虑每周开奖日和年度节假日。
    """
    if start_date is None:
        start_date = date.today()

    end_date = date(start_date.year + num_years, start_date.month, start_date.day)
    
    draw_days = []
    if lottery_type == 'ssq':
        draw_days = CURRENT_SETTINGS.get('ssq_draw_days', [])
    elif lottery_type == 'dlt':
        draw_days = CURRENT_SETTINGS.get('dlt_draw_days', [])
    else:
        return 0

    annual_holidays = CURRENT_SETTINGS.get('annual_holidays', [])
    
    total_draws = 0
    current_date = start_date
    
    while current_date < end_date:
        is_draw_day = False
        # isoweekday() 返回 1 (周一) 到 7 (周日)
        if current_date.isoweekday() in draw_days:
            is_draw_day = True
        
        is_holiday = False
        for holiday in annual_holidays:
            holiday_start_str = holiday['start']
            holiday_start_month = int(holiday_start_str.split('-')[0])
            holiday_start_day = int(holiday_start_str.split('-')[1])
            
            # 考虑跨年情况，但简化处理为只检查当前年份的节假日
            holiday_start_date_this_year = date(current_date.year, holiday_start_month, holiday_start_day)
            holiday_end_date_this_year = holiday_start_date_this_year + timedelta(weeks=holiday['duration_weeks']) - timedelta(days=1)
            
            if holiday_start_date_this_year <= current_date <= holiday_end_date_this_year:
                is_holiday = True
                break
        
        if is_draw_day and not is_holiday:
            total_draws += 1
            
        current_date += timedelta(days=1)
        
    return total_draws

def _calculate_future_draw_date(lottery_type, start_date, draw_offset):
    """
    根据彩票类型、起始日期和开奖期数偏移量，计算未来的预计中奖日期。
    start_date: 计算的起始日期 (datetime.date 对象)
    draw_offset: 从 start_date 开始的第 N 期开奖 (例如，如果 draw_offset=1，表示下一期开奖)
    """
    draw_days = []
    if lottery_type == 'ssq':
        draw_days = CURRENT_SETTINGS.get('ssq_draw_days', [])
    elif lottery_type == 'dlt':
        draw_days = CURRENT_SETTINGS.get('dlt_draw_days', [])
    else:
        return None

    annual_holidays = CURRENT_SETTINGS.get('annual_holidays', [])
    
    current_date = start_date
    draws_found = 0

    # 避免无限循环，设置一个合理的上限，例如 365 * 500 天
    max_days_to_check = 365 * CURRENT_SETTINGS.get('fun_game_simulation_years', 500) * 2 # 乘以2作为安全边际

    while draws_found < draw_offset and max_days_to_check > 0:
        is_draw_day = False
        if current_date.isoweekday() in draw_days:
            is_draw_day = True
        
        is_holiday = False
        for holiday in annual_holidays:
            holiday_start_str = holiday['start']
            holiday_start_month = int(holiday_start_str.split('-')[0])
            holiday_start_day = int(holiday_start_str.split('-')[1])
            
            holiday_start_date_this_year = date(current_date.year, holiday_start_month, holiday_start_day)
            holiday_end_date_this_year = holiday_start_date_this_year + timedelta(weeks=holiday['duration_weeks']) - timedelta(days=1)
            
            if holiday_start_date_this_year <= current_date <= holiday_end_date_this_year:
                is_holiday = True
                break
        
        if is_draw_day and not is_holiday:
            draws_found += 1
            
        if draws_found < draw_offset: # 只有在还没找到目标期数时才增加日期
            current_date += timedelta(days=1)
        max_days_to_check -= 1
        
    if draws_found == draw_offset:
        return current_date
    return None


# --- 趣味游戏模拟函数 ---
def simulate_fun_game(user_red_balls, user_blue_balls, lottery_type, task_id=None, tasks_dict=None):
    """
    模拟虚拟开奖，在指定年数内进行对奖。
    返回模拟结果，包括中奖次数、总花费、预计中奖日期等。
    task_id 和 tasks_dict 用于在长时间运行时更新进度。
    """
    rules = PRIZE_RULES.get(lottery_type)
    if not rules:
        return {'error': 'Invalid lottery type'}

    red_range = rules['red_range']
    blue_range = rules['blue_range']
    
    if not user_red_balls and not user_blue_balls:
        return {'error': '请至少选择一个红球或一个蓝球进行模拟。'}

    num_red_balls_to_draw = 6 if lottery_type == 'ssq' else 5
    num_blue_balls_to_draw = 1 if lottery_type == 'ssq' else 2

    for ball in user_red_balls:
        if not (1 <= ball <= red_range):
            return {'error': f"用户选择的红球 {ball} 超出了有效范围 (1-{red_range})。"}
    for ball in user_blue_balls:
        if not (1 <= ball <= blue_range):
            return {'error': f"用户选择的蓝球 {ball} 超出了有效范围 (1-{blue_range})。"}

    # 获取模拟年份和计算总模拟期数
    simulation_years = CURRENT_SETTINGS.get('fun_game_simulation_years', 500)
    max_simulations = _calculate_draws_in_years(lottery_type, simulation_years)

    if max_simulations == 0:
        return {'error': f"无法计算 {simulation_years} 年内的开奖期数，请检查配置。"}

    # 获取最新一期开奖数据，用于浮动奖金计算
    latest_draw = None
    if lottery_type == 'ssq':
        latest_draw = db.session.query(SSQDraw).order_by(SSQDraw.issue.desc()).first()
    elif lottery_type == 'dlt':
        latest_draw = db.session.query(DLTDraw).order_by(DLTDraw.issue.desc()).first()

    draw_count = 0
    total_prizes_counter = Counter() # 统计各奖项中奖次数
    total_prize_level_amounts = OrderedDict() # 存储各奖项的总中奖金额
    total_winning_amount = 0.0 # 总中奖金额
    first_prize_won = False # 标记是否中过一等奖
    first_prize_draw_count = None # 第一次中一等奖的模拟期数
    estimated_first_prize_date = None # 预计中一等奖的日期

    # 计算单次投注花费
    cost_details = calculate_combination_cost(len(user_red_balls), len(user_blue_balls), lottery_type)
    cost_per_draw = cost_details['total_cost']
    
    progress_update_interval = max(1, max_simulations // 1000) # 至少每千分之一更新一次，避免频繁更新

    while draw_count < max_simulations:
        draw_count += 1

        if task_id and tasks_dict and (draw_count % progress_update_interval == 0 or draw_count == max_simulations):
            progress = (draw_count / max_simulations) * 100
            tasks_dict[task_id]['progress'] = round(progress, 2)
            tasks_dict[task_id]['status'] = 'running'

        simulated_red_balls = sorted(random.sample(range(1, red_range + 1), num_red_balls_to_draw))
        simulated_blue_balls = sorted(random.sample(range(1, blue_range + 1), num_blue_balls_to_draw))

        prize_details_for_draw = calculate_prize_details(
            user_red_balls, user_blue_balls,
            simulated_red_balls, simulated_blue_balls,
            lottery_type
        )

        for level, count in prize_details_for_draw.items():
            if count > 0:
                total_prizes_counter[level] += count
                prize_rule = next((p for p in rules['prizes'] if p['level'] == level), None)
                
                current_prize_amount_numeric = 0
                if prize_rule:
                    if prize_rule['amount'] == '浮动':
                        if latest_draw:
                            if level == '一等奖':
                                current_prize_amount_numeric = latest_draw.first_prize_amount
                            elif level == '二等奖':
                                current_prize_amount_numeric = latest_draw.second_prize_amount
                        # 如果没有最新开奖数据，浮动奖金按0处理
                    else:
                        current_prize_amount_numeric = prize_rule['amount']
                
                level_total_amount = current_prize_amount_numeric * count
                total_winning_amount += level_total_amount
                
                # 累加每个奖项等级的总金额
                if level not in total_prize_level_amounts:
                    total_prize_level_amounts[level] = 0.0
                total_prize_level_amounts[level] += level_total_amount
                
                if level == '一等奖' and not first_prize_won:
                    first_prize_won = True
                    first_prize_draw_count = draw_count
                    estimated_first_prize_date = _calculate_future_draw_date(lottery_type, date.today(), draw_count)
    
    # 获取奖项的固定顺序 (从 config.py 中定义，通常是从高到低)
    prize_level_order = [p['level'] for p in rules['prizes']]
    
    # 创建一个新的 OrderedDict，按照 prize_level_order 的顺序填充中奖次数
    ordered_total_prizes = OrderedDict()
    for level in prize_level_order:
        if level in total_prizes_counter:
            ordered_total_prizes[level] = total_prizes_counter[level]
        else:
            ordered_total_prizes[level] = 0 # 确保所有奖项都显示，即使中奖次数为0

    # 同样，按照 prize_level_order 的顺序填充中奖金额
    ordered_total_prize_level_amounts = OrderedDict()
    for level in prize_level_order:
        if level in total_prize_level_amounts:
            ordered_total_prize_level_amounts[level] = total_prize_level_amounts[level]
        else:
            ordered_total_prize_level_amounts[level] = 0.0 # 确保所有奖项都显示，即使金额为0

    total_cost_for_simulations = max_simulations * cost_per_draw
    
    message = ""
    if first_prize_won:
        message = f"恭喜你！在时光机中成功命中一等奖！预计在 {estimated_first_prize_date.strftime('%Y年%m月%d日')} 左右中奖。"
    else:
        message = f"哇哦，看样子在这个世界里的未来{simulation_years}年没有命中一等奖了，让我们赶紧再次按动 大奖时光机 按钮，穿梭到其他的平行时空，看看能不能中到大奖。"

    return {
        'input_red_balls': user_red_balls,
        'input_blue_balls': user_blue_balls,
        'total_simulations': max_simulations,
        'total_prizes': ordered_total_prizes, # 各奖项中奖次数
        'total_prize_level_amounts': ordered_total_prize_level_amounts, # 各奖项总中奖金额
        'total_winning_amount': total_winning_amount, # 所有奖项总金额
        'total_cost_for_simulations': total_cost_for_simulations,
        'first_prize_won': first_prize_won,
        'first_prize_draw_count': first_prize_draw_count,
        'estimated_first_prize_date': estimated_first_prize_date.strftime('%Y-%m-%d') if estimated_first_prize_date else None,
        'message': message
    }
