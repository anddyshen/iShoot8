# utils.py
from datetime import datetime, timedelta, date
import math
from collections import Counter, OrderedDict
import random
from config import PRIZE_RULES, CURRENT_SETTINGS, PER_BET_PRICE, PER_BET_ADD_PRICE, FUYUN_PRIZE_ENABLE_THRESHOLD, FUYUN_PRIZE_DISABLE_THRESHOLD, DLT_POOL_LINKAGE_THRESHOLD # 导入中奖规则和当前设置
from models import SSQDraw, DLTDraw, KL8Draw, SevenXCDraw, SevenLCDraw, db # 新增导入

# 版本号，每次生成文件时更新
__version__ = "2.0.0" # 更新版本号 - 2026年新奖金规则

from flask import current_app # Import current_app for logging

def format_lottery_numbers(numbers_str):
    """将逗号分隔的数字字符串转换为整数列表并排序"""
    if not isinstance(numbers_str, str):
        current_app.logger.error(f"format_lottery_numbers received non-string input: {numbers_str} (type: {type(numbers_str)})")
        return []
    try:
        # 过滤掉空字符串和非数字字符，并转换为整数
        parsed_numbers = []
        for x in numbers_str.split(','):
            stripped_x = x.strip()
            if stripped_x:
                try:
                    parsed_numbers.append(int(stripped_x))
                except ValueError:
                    current_app.logger.warning(f"Skipping non-integer part in lottery numbers string: '{stripped_x}' from '{numbers_str}'")
        return sorted(parsed_numbers)
    except Exception as e:
        current_app.logger.error(f"Error formatting lottery numbers string '{numbers_str}': {e}")
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
    
    # 创建一个字典，将每个连续的球映射到其连号长度和组序号
    consecutive_map = {}
    # 统计每种长度的连号组出现的次数，用于区分多个同长度组
    length_counters = {}
    for idx, group in enumerate(groups):
        group_len = len(group)
        if group_len > 1: # 只对长度大于1的连续组进行标记
            if group_len not in length_counters:
                length_counters[group_len] = 0
            else:
                length_counters[group_len] += 1
            # 格式: "长度_序号"，如 "2_0" 表示第1个2连号组，"2_1" 表示第2个2连号组
            group_key = f"{group_len}_{length_counters[group_len]}"
            for ball in group:
                consecutive_map[ball] = group_key
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

def calculate_odd_even_ratio_per_draw(balls):
    """计算单期号码的奇偶比"""
    if not balls:
        return "0:0"
    odd_count = sum(1 for n in balls if n % 2 != 0)
    even_count = len(balls) - odd_count
    return f"{odd_count}:{even_count}"

def calculate_sum_per_draw(balls):
    """计算单期号码的总和"""
    if not balls:
        return 0
    return sum(balls)

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

def calculate_mean_per_draw(balls):
    """计算单期号码的均值"""
    if not balls:
        return 0.0
    return sum(balls) / len(balls)

def calculate_remainder_group_counts_per_draw(balls, divisor):
    """
    计算单期号码按指定除数分组的余数相同数量。
    例如，除数3，统计余数为0, 1, 2的号码数量。
    """
    if not balls or divisor <= 0:
        return {}
    
    remainder_counts = Counter(ball % divisor for ball in balls)
    # 确保所有余数类别都存在，即使数量为0
    for i in range(divisor):
        if i not in remainder_counts:
            remainder_counts[i] = 0
    
    return dict(sorted(remainder_counts.items()))

def calculate_red_ball_area_distribution_per_draw(balls, area_ranges):
    """
    计算单期红球在指定分区范围内的分布情况。
    area_ranges: 列表，每个元素是一个元组 (start, end)，表示一个分区范围。
    例如: [(1,8), (9,16), (17,24), (25,33)]
    返回: 字典，键为分区索引 (从0开始)，值为该分区内的号码数量。
    """
    if not balls or not area_ranges:
        return {}
    
    distribution = Counter()
    for ball in balls:
        for i, (start, end) in enumerate(area_ranges):
            if start <= ball <= end:
                distribution[f'Area {i+1} ({start}-{end})'] += 1
                break
    
    # 确保所有分区都存在，即使数量为0
    for i, (start, end) in enumerate(area_ranges):
        area_key = f'Area {i+1} ({start}-{end})'
        if area_key not in distribution:
            distribution[area_key] = 0
            
    return dict(distribution)

def calculate_multi_draw_repeat_balls(draws_list, num_previous_draws, ball_type='red'):
    """
    计算在最近 N 期内重复出现的号码及其重复次数。
    draws_list: 降序排列的开奖数据列表 (最新在前面)
    num_previous_draws: 要检查的期数 N
    ball_type: 'red' 或 'blue'
    返回: 字典 {号码: 重复次数}
    """
    if not draws_list or num_previous_draws <= 0:
        return {}

    # 获取最近 N 期的开奖数据
    recent_draws = draws_list[:num_previous_draws]
    
    all_recent_balls = []
    for draw in recent_draws:
        if ball_type == 'red':
            all_recent_balls.extend(draw.get_red_balls_list())
        elif ball_type == 'blue':
            all_recent_balls.extend(draw.get_blue_balls_list())
            
    # 统计每个号码的出现次数
    repeat_counts = Counter(all_recent_balls)
    
    # 过滤掉只出现一次的号码，只保留重复出现的
    return {ball: count for ball, count in repeat_counts.items() if count > 1}

def calculate_diagonal_skip_numbers(draws_list, ball_type='red', lookback_periods=5):
    """
    计算斜连号和跳号。
    斜连号: 号码在连续期数中递增或递减1。例如：10(期N), 11(期N-1), 12(期N-2)
    跳号: 号码在间隔期数中出现。例如：10(期N), 10(期N-2), 10(期N-4)
    draws_list: 降序排列的开奖数据列表 (最新在前面)
    ball_type: 'red' 或 'blue'
    lookback_periods: 往前追溯的期数
    返回: 字典 {'diagonal_numbers': [], 'skip_numbers': []}
    """
    diagonal_numbers = set()
    skip_numbers = set()

    if not draws_list or len(draws_list) < 2:
        return {'diagonal_numbers': [], 'skip_numbers': []}

    # 确保 lookback_periods 不超过实际的开奖期数
    actual_lookback = min(lookback_periods, len(draws_list))

    for i in range(actual_lookback):
        current_draw = draws_list[i]
        current_balls = set(current_draw.get_red_balls_list() if ball_type == 'red' else current_draw.get_blue_balls_list())

        # 检查斜连号
        if i + 1 < len(draws_list):
            prev_draw = draws_list[i+1]
            prev_balls = set(prev_draw.get_red_balls_list() if ball_type == 'red' else prev_draw.get_blue_balls_list())
            
            for ball in current_balls:
                # 检查递增斜连 (ball in current, ball-1 in prev)
                if (ball - 1) in prev_balls:
                    diagonal_numbers.add(ball)
                    diagonal_numbers.add(ball - 1)
                # 检查递减斜连 (ball in current, ball+1 in prev)
                if (ball + 1) in prev_balls:
                    diagonal_numbers.add(ball)
                    diagonal_numbers.add(ball + 1)

        # 检查跳号 (间隔一期重复)
        if i + 2 < len(draws_list):
            skip_draw = draws_list[i+2]
            skip_balls = set(skip_draw.get_red_balls_list() if ball_type == 'red' else skip_draw.get_blue_balls_list())
            
            for ball in current_balls:
                if ball in skip_balls:
                    skip_numbers.add(ball)
    
    return {
        'diagonal_numbers': sorted(list(diagonal_numbers)),
        'skip_numbers': sorted(list(skip_numbers))
    }

def calculate_consecutive_trend_over_draws(draws_list, ball_type='red', min_consecutive_length=2):
    """
    计算在历史开奖中，不同长度连号出现的频率。
    draws_list: 降序排列的开奖数据列表 (最新在前面)
    ball_type: 'red' 或 'blue'
    min_consecutive_length: 最小连号长度，例如2表示统计2连号、3连号等
    返回: 字典 {连号长度: 出现次数}
    """
    consecutive_counts = Counter()
    
    for draw in draws_list:
        balls = draw.get_red_balls_list() if ball_type == 'red' else draw.get_blue_balls_list()
        groups, _ = get_consecutive_groups(balls)
        for group in groups:
            length = len(group)
            if length >= min_consecutive_length:
                consecutive_counts[length] += 1
                
    return dict(sorted(consecutive_counts.items()))


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

def calculate_kl8_prize(user_balls, draw_balls, play_type=None):
    """
    快乐8对奖计算：
    user_balls: 用户选号列表 (1-80)
    draw_balls: 当期开奖号码列表 (20个球, 1-80)
    play_type: 玩法(选1-选10)，如果不传则根据 len(user_balls) 决定 (不超过10)
    返回: OrderedDict( { '奖级名称': {'count': count, 'amount': amount} } )
    """
    user_set = set(user_balls)
    draw_set = set(draw_balls)
    n = len(user_set)
    k = play_type or min(n, 10)
    if k < 1:
        return OrderedDict()

    # 官方固定奖金对照表
    kl8_rules = {
        10: {10: ('选十中10', 5000000), 9: ('选十中9', 8000), 8: ('选十中8', 800), 7: ('选十中7', 80), 6: ('选十中6', 5), 0: ('选十中0', 2)},
        9: {9: ('选九中9', 300000), 8: ('选九中8', 2000), 7: ('选九中7', 200), 6: ('选九中6', 20), 5: ('选九中5', 5), 0: ('选九中0', 2)},
        8: {8: ('选八中8', 50000), 7: ('选八中7', 800), 6: ('选八中6', 88), 5: ('选八中5', 10), 4: ('选八中4', 3), 0: ('选八中0', 2)},
        7: {7: ('选七中7', 10000), 6: ('选七中6', 288), 5: ('选七中5', 28), 4: ('选七中4', 4), 0: ('选七中0', 2)},
        6: {6: ('选六中6', 3000), 5: ('选六中5', 30), 4: ('选六中4', 10), 3: ('选六中3', 3)},
        5: {5: ('选五中5', 1000), 4: ('选五中4', 21), 3: ('选五中3', 3)},
        4: {4: ('选四中4', 100), 3: ('选四中3', 5), 2: ('选四中2', 3)},
        3: {3: ('选三中3', 53), 2: ('选三中2', 2)},
        2: {2: ('选二中2', 19)},
        1: {1: ('选一中1', 4.6)}
    }

    rule = kl8_rules.get(k, {})
    matched_set = user_set.intersection(draw_set)
    m = len(matched_set) # 命中的球数
    unm = n - m # 未命中的球数

    prize_details = OrderedDict()
    
    # 如果是单注 (选球数等于玩法球数 k)
    if n == k:
        if m in rule:
            lvl_name, amt = rule[m]
            prize_details[lvl_name] = {'count': 1, 'amount': amt}
    else:
        # 复式投注：用户选了 n 个球 (n > k)，投注 C(n, k) 注
        for r, (lvl_name, amt) in rule.items():
            if r <= m and (k - r) <= unm:
                comb_count = combinations(m, r) * combinations(unm, k - r)
                if comb_count > 0:
                    if lvl_name not in prize_details:
                        prize_details[lvl_name] = {'count': 0, 'amount': 0}
                    prize_details[lvl_name]['count'] += comb_count
                    prize_details[lvl_name]['amount'] += comb_count * amt

    return prize_details

def calculate_7xc_prize(user_front, user_back, draw_front, draw_back):
    """
    七星彩对奖计算（2020新规）：
    user_front: 用户前区6位数字列表 [d0, d1, d2, d3, d4, d5]
    user_back: 用户后区数字 (0-14)
    draw_front: 开奖前区6位数字列表
    draw_back: 开奖后区数字
    返回: OrderedDict( { '奖级名称': {'count': count, 'amount': amount} } )
    """
    prize_details = OrderedDict()
    if len(user_front) != 6 or len(draw_front) != 6:
        return prize_details

    try:
        back_matched = (int(user_back) == int(draw_back))
    except (ValueError, TypeError):
        back_matched = False
    
    # 计算前区连续匹配最大长度
    try:
        is_match = [1 if int(user_front[i]) == int(draw_front[i]) else 0 for i in range(6)]
    except (ValueError, TypeError):
        return prize_details

    max_consec = 0
    cur_consec = 0
    for match in is_match:
        if match == 1:
            cur_consec += 1
            if cur_consec > max_consec:
                max_consec = cur_consec
        else:
            cur_consec = 0
            
    level_name = None
    amount = 0
    
    if max_consec == 6 and back_matched:
        level_name = '一等奖'
        amount = 5000000
    elif max_consec == 6 and not back_matched:
        level_name = '二等奖'
        amount = 500000
    elif max_consec == 5 and back_matched:
        level_name = '三等奖'
        amount = 3000
    elif (max_consec == 5 and not back_matched) or (max_consec == 4 and back_matched):
        level_name = '四等奖'
        amount = 500
    elif (max_consec == 4 and not back_matched) or (max_consec == 3 and back_matched):
        level_name = '五等奖'
        amount = 30
    elif (max_consec == 3 and not back_matched) or (max_consec == 2 and back_matched) or (max_consec == 1 and back_matched) or (max_consec == 0 and back_matched):
        level_name = '六等奖'
        amount = 5
        
    if level_name:
        prize_details[level_name] = {'count': 1, 'amount': amount}
        
    return prize_details

def calculate_7lc_prize(user_basic, draw_basic, draw_special):
    """
    七乐彩对奖计算（30选7+1特别号）：
    user_basic: 用户选号列表 (1-30)
    draw_basic: 开奖基本号 (7个球, 1-30)
    draw_special: 开奖特别号 (1个球, 1-30)
    返回: OrderedDict( { '奖级名称': {'count': count, 'amount': amount} } )
    """
    user_set = set(user_basic)
    draw_set = set(draw_basic)
    n = len(user_set)
    if n < 7:
        return OrderedDict()

    lc_rules = {
        (7, 0): ('一等奖', 5000000),
        (6, 1): ('二等奖', 500000),
        (6, 0): ('三等奖', 10000),
        (5, 1): ('四等奖', 200),
        (5, 0): ('五等奖', 50),
        (4, 1): ('六等奖', 10),
        (4, 0): ('七等奖', 5)
    }

    matched_basic = len(user_set.intersection(draw_set))
    try:
        has_special = 1 if int(draw_special) in user_set else 0
    except (ValueError, TypeError):
        has_special = 0
    unmatched_non_special = n - matched_basic - has_special

    prize_details = OrderedDict()

    if n == 7:
        key = (matched_basic, has_special if matched_basic in (4, 5, 6) else 0)
        if matched_basic == 7:
            key = (7, 0)
        if key in lc_rules:
            lvl_name, amt = lc_rules[key]
            prize_details[lvl_name] = {'count': 1, 'amount': amt}
    else:
        # 复式投注：从 user_set 中选 7 个球的全部组合
        for (req_b, req_s), (lvl_name, amt) in lc_rules.items():
            if req_b <= matched_basic and req_s <= has_special:
                needed_other = 7 - req_b - req_s
                if 0 <= needed_other <= unmatched_non_special:
                    c_basic = combinations(matched_basic, req_b)
                    c_special = combinations(has_special, req_s)
                    c_other = combinations(unmatched_non_special, needed_other)
                    comb_count = c_basic * c_special * c_other
                    if comb_count > 0:
                        if lvl_name not in prize_details:
                            prize_details[lvl_name] = {'count': 0, 'amount': 0}
                        prize_details[lvl_name]['count'] += comb_count
                        prize_details[lvl_name]['amount'] += comb_count * amt

    return prize_details

def calculate_combination_cost(user_red_balls_count, user_blue_balls_count, lottery_type, is_addition=False):
    """
    根据用户选择的号码计算复式投注的总注数和花费。
    """
    if lottery_type == 'ssq':
        red_bets = combinations(user_red_balls_count, 6)
        blue_bets = combinations(user_blue_balls_count, 1)
        total_bets = red_bets * blue_bets
    elif lottery_type == 'dlt':
        red_bets = combinations(user_red_balls_count, 5)
        blue_bets = combinations(user_blue_balls_count, 2)
        total_bets = red_bets * blue_bets
    elif lottery_type == 'kl8':
        if user_red_balls_count <= 10:
            total_bets = 1
        else:
            total_bets = combinations(user_red_balls_count, 10)
    elif lottery_type == '7xc':
        total_bets = 1
    elif lottery_type == '7lc':
        if user_red_balls_count >= 7:
            total_bets = combinations(user_red_balls_count, 7)
        else:
            total_bets = 1
    else:
        return {'total_bets': 0, 'total_cost': 0, 'base_cost': 0, 'add_cost': 0}
    # 计算基础花费
    base_cost = total_bets * PER_BET_PRICE
    # 追加投注只在浮动奖有效，但价格按每注+1元计算
    add_cost = total_bets * PER_BET_ADD_PRICE if is_addition and lottery_type == 'dlt' else 0
    total_cost = base_cost + add_cost
    return {'total_bets': total_bets, 'total_cost': total_cost, 'base_cost': base_cost, 'add_cost': add_cost}

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


# --- 2026年新版对奖逻辑辅助函数 ---

def _get_prize_amount_for_rule(prize_rule, pool_amount=None, is_addition=False, draw_date=None):
    """
    根据奖池情况获取奖项的实际金额。
    prize_rule: 奖项规则字典
    pool_amount: 当前奖池金额（大乐透用于固定奖联动判断）
    is_addition: 是否追加投注（仅大乐透浮动奖有效）
    draw_date: 开奖日期（用于判断大乐透加奖是否生效，2026年2月1日之后才启用）
    """
    if isinstance(prize_rule['amount'], (int, float)):
        # 固定奖 - 检查是否有奖池联动
        base_amount = prize_rule['amount']
        # 大乐透加奖联动仅在2026年2月1日（含）之后生效
        DLT_BONUS_START_DATE = date(2026, 2, 1)
        if (pool_amount is not None and pool_amount >= DLT_POOL_LINKAGE_THRESHOLD 
            and draw_date is not None and draw_date >= DLT_BONUS_START_DATE):
            # 奖池≥8亿且日期在2026年2月1日之后，使用提升后的金额
            return prize_rule.get('amount_pool_ge_8e8', base_amount)
        return base_amount
    else:
        # 浮动奖 - 返回0（调用方会从开奖数据中获取实际金额）
        return 0

def calculate_prize_details(user_red_balls, user_blue_balls, draw_red_balls, draw_blue_balls, lottery_type, 
                            pool_amount=None, is_addition=False, fuyun_prize_active=False, draw_date=None):
    """
    检查用户号码与一期开奖号码的中奖情况，并计算每个奖项的中奖注数。
    user_red_balls: 用户选择的红球列表 (已排序)
    user_blue_balls: 用户选择的蓝球列表 (已排序)
    draw_red_balls: 开奖红球列表 (已排序)
    draw_blue_balls: 开奖蓝球列表 (已排序)
    lottery_type: 'ssq' 或 'dlt'
    pool_amount: 当前奖池金额（用于福运奖和大乐透固定奖联动）
    is_addition: 是否追加投注（仅大乐透浮动奖有效）
    fuyun_prize_active: 福运奖是否启用（仅双色球）
    返回: { 'prize_level': {'count': count, 'amount': amount}, ... }
    """
    if lottery_type == 'kl8':
        return calculate_kl8_prize(user_red_balls, draw_red_balls)
    elif lottery_type == '7xc':
        user_back = user_blue_balls[0] if user_blue_balls else 0
        draw_back = draw_blue_balls[0] if draw_blue_balls else 0
        return calculate_7xc_prize(user_red_balls, user_back, draw_red_balls, draw_back)
    elif lottery_type == '7lc':
        draw_special = draw_blue_balls[0] if draw_blue_balls else 0
        return calculate_7lc_prize(user_red_balls, draw_red_balls, draw_special)

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

    # 标准单式号码数量
    standard_red_count = rules['standard_red']  # SSQ: 6, DLT: 5
    standard_blue_count = rules['standard_blue']  # SSQ: 1, DLT: 2

    # 判断是否为单式投注（单式投注只能中一个最高奖项，不能叠加小奖）
    is_single_bet = (len(user_red_balls) == standard_red_count and len(user_blue_balls) == standard_blue_count)

    # 存储中奖详情
    prize_details = OrderedDict()

    # 遍历所有奖项规则，计算中奖注数
    for prize_rule in rules['prizes']:
        # 单式投注：如果已经中了更高的奖项，则跳过后续所有奖项的检查
        if is_single_bet and prize_details:
            continue
        # 检查是否为特殊条件奖项（如福运奖）
        special = prize_rule.get('special')
        if special == 'fuyun_prize':
            # 福运奖：仅当福运奖启用时有效
            if not fuyun_prize_active:
                continue
            # 福运奖条件：3红+0蓝
            if matched_red_count == 3 and matched_blue_count == 0:
                # 从用户选中的匹配红球中选3个
                c_matched_red = combinations(matched_red_count, 3)
                # 从用户选中的非匹配红球中选(standard_red_count - 3)个
                c_unmatched_red = combinations(len(user_red_set - draw_red_set), standard_red_count - 3)
                # 蓝球必须全不匹配：从用户选中的非匹配蓝球中选standard_blue_count个
                c_unmatched_blue = combinations(len(user_blue_set - draw_blue_set), standard_blue_count)
                total_count = c_matched_red * c_unmatched_red * c_unmatched_blue
                if total_count > 0:
                    amount = prize_rule['amount']
                    level_name = prize_rule['level']
                    if level_name not in prize_details:
                        prize_details[level_name] = {'count': 0, 'amount': 0}
                    prize_details[level_name]['count'] += total_count
                    prize_details[level_name]['amount'] += amount * total_count
            continue

        # 检查是否为六等奖（中蓝球即中奖）- 使用 match_red_min / match_red_max
        if 'match_red_min' in prize_rule and 'match_red_max' in prize_rule:
            # 六等奖条件：红球在0-5范围内 + 蓝球匹配
            if prize_rule['match_red_min'] <= matched_red_count <= prize_rule['match_red_max'] and matched_blue_count >= prize_rule['match_blue']:
                # 从匹配蓝球中选match_blue个
                c_matched_blue = combinations(matched_blue_count, prize_rule['match_blue'])
                # 从非匹配蓝球中选(standard_blue_count - match_blue)个
                c_unmatched_blue = combinations(len(user_blue_set - draw_blue_set), standard_blue_count - prize_rule['match_blue'])
                total_count = c_matched_blue * c_unmatched_blue
                if total_count > 0:
                    amount = _get_prize_amount_for_rule(prize_rule, pool_amount, is_addition, draw_date)
                    level_name = prize_rule['level']
                    if level_name not in prize_details:
                        prize_details[level_name] = {'count': 0, 'amount': 0}
                    prize_details[level_name]['count'] += total_count
                    prize_details[level_name]['amount'] += amount * total_count
            continue

        # 标准奖项规则
        required_red = prize_rule['match_red']
        required_blue = prize_rule['match_blue']

        # 检查红球是否满足条件
        if matched_red_count < required_red:
            continue
        # 检查蓝球是否满足条件
        if matched_blue_count < required_blue:
            continue

        # 计算红球组合
        c_matched_red = combinations(matched_red_count, required_red)
        # 从非匹配红球中选 (standard_red_count - required_red) 个
        c_unmatched_red = combinations(len(user_red_set - draw_red_set), standard_red_count - required_red)
        red_prize_combinations = c_matched_red * c_unmatched_red

        # 计算蓝球组合
        c_matched_blue = combinations(matched_blue_count, required_blue)
        # 从非匹配蓝球中选 (standard_blue_count - required_blue) 个
        c_unmatched_blue = combinations(len(user_blue_set - draw_blue_set), standard_blue_count - required_blue)
        blue_prize_combinations = c_matched_blue * c_unmatched_blue

        total_count = red_prize_combinations * blue_prize_combinations

        if total_count > 0:
            # 获取奖金金额
            amount = _get_prize_amount_for_rule(prize_rule, pool_amount, is_addition, draw_date)
            level_name = prize_rule['level']
            if level_name not in prize_details:
                prize_details[level_name] = {'count': 0, 'amount': 0}
            prize_details[level_name]['count'] += total_count
            prize_details[level_name]['amount'] += amount * total_count

    return prize_details


def _calculate_draws_in_years(lottery_type, num_years, start_date=None):
    """
    计算指定彩票类型在给定年数内的总开奖期数，考虑每周开奖日和年度节假日。
    """
    if start_date is None:
        start_date = date.today()

    end_date = date(start_date.year + num_years, start_date.month, start_date.day)
    
    draw_days_raw = []
    if lottery_type == 'ssq':
        draw_days_raw = CURRENT_SETTINGS.get('ssq_draw_days', [2, 4, 7])  # 默认: 周二、周四、周日
    elif lottery_type == 'dlt':
        draw_days_raw = CURRENT_SETTINGS.get('dlt_draw_days', [1, 3, 6])  # 默认: 周一、周三、周六
    else:
        return 0
    
    # 类型安全校验：确保 draw_days 是列表，防止 settings.json 被错误保存为字符串
    draw_days = []
    if isinstance(draw_days_raw, list):
        draw_days = [int(d) for d in draw_days_raw if isinstance(d, (int, float)) or (isinstance(d, str) and d.strip().isdigit())]
    elif isinstance(draw_days_raw, str):
        # 如果配置被错误保存为字符串如 "[2, 4, 7]"，尝试解析
        current_app.logger.warning(f"_calculate_draws_in_years: {lottery_type} draw_days is a string '{draw_days_raw}', attempting to parse")
        import ast
        try:
            parsed = ast.literal_eval(draw_days_raw)
            if isinstance(parsed, (list, tuple)):
                draw_days = [int(d) for d in parsed]
        except (ValueError, SyntaxError):
            # 尝试按逗号分割
            try:
                draw_days = [int(d.strip()) for d in draw_days_raw.strip('[]').split(',') if d.strip().isdigit()]
            except Exception:
                pass

    # 如果没有开奖日配置，返回0
    if not draw_days:
        current_app.logger.warning(f"_calculate_draws_in_years: {lottery_type} draw_days is empty, using fallback defaults")
        draw_days = [2, 4, 7] if lottery_type == 'ssq' else [1, 3, 6]

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
    draw_days_raw = []
    if lottery_type == 'ssq':
        draw_days_raw = CURRENT_SETTINGS.get('ssq_draw_days', [2, 4, 7])  # 默认: 周二、周四、周日
    elif lottery_type == 'dlt':
        draw_days_raw = CURRENT_SETTINGS.get('dlt_draw_days', [1, 3, 6])  # 默认: 周一、周三、周六
    else:
        return None
    
    # 类型安全校验
    draw_days = []
    if isinstance(draw_days_raw, list):
        draw_days = [int(d) for d in draw_days_raw if isinstance(d, (int, float)) or (isinstance(d, str) and d.strip().isdigit())]
    elif isinstance(draw_days_raw, str):
        current_app.logger.warning(f"_calculate_future_draw_date: {lottery_type} draw_days is a string '{draw_days_raw}', attempting to parse")
        import ast
        try:
            parsed = ast.literal_eval(draw_days_raw)
            if isinstance(parsed, (list, tuple)):
                draw_days = [int(d) for d in parsed]
        except (ValueError, SyntaxError):
            try:
                draw_days = [int(d.strip()) for d in draw_days_raw.strip('[]').split(',') if d.strip().isdigit()]
            except Exception:
                pass

    # 如果没有开奖日配置，使用默认值
    if not draw_days:
        current_app.logger.warning(f"_calculate_future_draw_date: {lottery_type} draw_days is empty, using fallback defaults")
        draw_days = [2, 4, 7] if lottery_type == 'ssq' else [1, 3, 6]

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


# --- 趣味游戏模拟函数 (2026年升级版) ---
def simulate_fun_game(user_red_balls, user_blue_balls, lottery_type, task_id=None, tasks_dict=None, is_addition=False):
    """
    模拟虚拟开奖，在指定年数内进行对奖。
    返回模拟结果，包括中奖次数、总花费、预计中奖日期等。
    task_id 和 tasks_dict 用于在长时间运行时更新进度。
    is_addition: 是否追加投注（仅大乐透有效）
    """
    rules = PRIZE_RULES.get(lottery_type)
    if not rules:
        return {'error': 'Invalid lottery type'}

    red_range = rules['red_range']
    blue_range = rules['blue_range']
    
    if not user_red_balls and not user_blue_balls:
        return {'error': '请至少选择一个红球或一个蓝球进行模拟。'}

    num_red_balls_to_draw = rules['standard_red']  # SSQ: 6, DLT: 5
    num_blue_balls_to_draw = rules['standard_blue']  # SSQ: 1, DLT: 2

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

    # 获取最新一期开奖数据，用于浮动奖金计算和福运奖状态
    latest_draw = None
    if lottery_type == 'ssq':
        latest_draw = db.session.query(SSQDraw).order_by(SSQDraw.issue.desc()).first()
    elif lottery_type == 'dlt':
        latest_draw = db.session.query(DLTDraw).order_by(DLTDraw.issue.desc()).first()

    # 获取最新奖池金额（大乐透用于固定奖联动，双色球用于福运奖）
    latest_pool_amount = latest_draw.prize_pool if latest_draw else None
    
    # 判断福运奖状态（双色球）
    fuyun_prize_active = False
    if lottery_type == 'ssq' and latest_draw:
        fuyun_prize_active = latest_draw.fuyun_prize_active if hasattr(latest_draw, 'fuyun_prize_active') else False

    draw_count = 0
    total_prizes_counter = Counter() # 统计各奖项中奖次数
    total_prize_level_amounts = OrderedDict() # 存储各奖项的总中奖金额
    total_winning_amount = 0.0 # 总中奖金额
    first_prize_won = False # 标记是否中过一等奖
    first_prize_draw_count = None # 第一次中一等奖的模拟期数
    estimated_first_prize_date = None # 预计中一等奖的日期

    # 计算单次投注花费
    cost_details = calculate_combination_cost(len(user_red_balls), len(user_blue_balls), lottery_type, is_addition)
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
            lottery_type,
            pool_amount=latest_pool_amount,
            is_addition=is_addition,
            fuyun_prize_active=fuyun_prize_active,
            draw_date=date.today()  # 模拟游戏使用当前日期，大乐透加奖按当前规则
        )

        for level, info in prize_details_for_draw.items():
            count = info['count']
            if count > 0:
                total_prizes_counter[level] += count
                prize_rule = next((p for p in rules['prizes'] if p['level'] == level), None)
                
                current_prize_amount_numeric = 0
                if prize_rule:
                    if prize_rule['amount'] == '浮动':
                        if latest_draw:
                            if level == '一等奖':
                                current_prize_amount_numeric = latest_draw.first_prize_amount
                                # 追加投注情况下，一等奖奖金为基本+追加
                                if is_addition and lottery_type == 'dlt':
                                    add_amount = prize_rule.get('max_single_add', 18000000)
                                    current_prize_amount_numeric = min(current_prize_amount_numeric + add_amount, prize_rule.get('max_single_add', 18000000))
                            elif level == '二等奖':
                                current_prize_amount_numeric = latest_draw.second_prize_amount
                                # 追加投注情况下，二等奖奖金为基本+追加
                                if is_addition and lottery_type == 'dlt':
                                    add_amount = prize_rule.get('max_single_add', 9000000)
                                    current_prize_amount_numeric = min(current_prize_amount_numeric + add_amount, prize_rule.get('max_single_add', 9000000))
                        # 如果没有最新开奖数据，浮动奖金按0处理
                    else:
                        # 固定奖 - 使用实际金额
                        current_prize_amount_numeric = info['amount'] / count if count > 0 else 0
                
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
        
        # 如果已经中了一等奖，则中止模拟
        if first_prize_won:
            break
    
    # 获取奖项的固定顺序 (从 config.py 中定义，通常是从高到低)
    prize_level_order = [p['level'] for p in rules['prizes']]
    # 去重保留顺序
    seen = set()
    prize_level_order_unique = []
    for level in prize_level_order:
        if level not in seen:
            seen.add(level)
            prize_level_order_unique.append(level)
    
    # 创建一个新的 OrderedDict，按照 prize_level_order 的顺序填充中奖次数
    ordered_total_prizes = OrderedDict()
    for level in prize_level_order_unique:
        if level in total_prizes_counter:
            ordered_total_prizes[level] = total_prizes_counter[level]
        else:
            ordered_total_prizes[level] = 0 # 确保所有奖项都显示，即使中奖次数为0

    # 同样，按照 prize_level_order 的顺序填充中奖金额
    ordered_total_prize_level_amounts = OrderedDict()
    for level in prize_level_order_unique:
        if level in total_prize_level_amounts:
            ordered_total_prize_level_amounts[level] = total_prize_level_amounts[level]
        else:
            ordered_total_prize_level_amounts[level] = 0.0 # 确保所有奖项都显示，即使金额为0

    total_cost_for_simulations = draw_count * cost_per_draw # 修正：总花费应为实际模拟的期数 * 单次投注花费
    
    message = ""
    if first_prize_won:
        message_template = CURRENT_SETTINGS.get('fun_game_prize_message', "恭喜你！在时光机中成功命中一等奖！预计在 {estimated_date} 左右中奖。")
        message = message_template.format(estimated_date=estimated_first_prize_date.strftime('%Y年%m月%d日'))
    else:
        message_template = CURRENT_SETTINGS.get('fun_game_no_prize_message', "哇哦，看样子在这个世界里的未来{simulation_years}年没有命中一等奖了，让我们赶紧再次按动 大奖时光机 按钮，穿梭到其他的平行时空，看看能不能中到大奖。")
        message = message_template.format(simulation_years=simulation_years)

    return {
        'input_red_balls': user_red_balls,
        'input_blue_balls': user_blue_balls,
        'total_simulations': draw_count, # 修正：返回实际模拟的期数
        'total_prizes': ordered_total_prizes, # 各奖项中奖次数
        'total_prize_level_amounts': ordered_total_prize_level_amounts, # 各奖项总中奖金额
        'total_winning_amount': total_winning_amount, # 所有奖项总金额
        'total_cost_for_simulations': total_cost_for_simulations,
        'first_prize_won': first_prize_won,
        'first_prize_draw_count': first_prize_draw_count,
        'estimated_first_prize_date': estimated_first_prize_date.strftime('%Y-%m-%d') if estimated_first_prize_date else None,
        'message': message,
        'is_addition': is_addition
    }

def calculate_all_trend_data(app, lottery_type, lookback_periods=None):
    """
    计算所有必要的趋势概率数据。
    app: Flask 应用实例，用于访问数据库和日志。
    lottery_type: 'ssq' 或 'dlt'。
    lookback_periods: 回溯期数，如果为 None，则计算所有历史数据。
    """
    with app.app_context():
        app.logger.info(f"开始计算 {lottery_type} 趋势数据...")

        Model = SSQDraw if lottery_type == 'ssq' else DLTDraw
        
        # 获取历史开奖数据
        if lookback_periods:
            all_draws = Model.query.order_by(Model.issue.desc()).limit(lookback_periods).all()
        else:
            all_draws = Model.query.order_by(Model.issue.desc()).all()

        if not all_draws:
            app.logger.warning(f"没有 {lottery_type} 的历史开奖数据，跳过趋势计算。")
            return None

        # 获取配置设置
        config_settings = CURRENT_SETTINGS # 假设 CURRENT_SETTINGS 包含了所有彩票类型的配置

        # 1. 聚合统计数据 (大小比、奇偶比、012路比、连号、重号、跨度、龙头凤尾、AC值等)
        aggregated_stats = get_aggregated_stats(all_draws, lottery_type, config_settings)

        # 2. 单个号码的频率和遗漏
        red_ball_range = 33 if lottery_type == 'ssq' else 35
        blue_ball_range = 16 if lottery_type == 'ssq' else 12
        
        red_stats_list, _ = calculate_frequency_and_omissions_for_balls(all_draws, red_ball_range, 'red')
        blue_stats_list, _ = calculate_frequency_and_omissions_for_balls(all_draws, blue_ball_range, 'blue')

        # 3. 多期重复号码
        multi_draw_repeat_red = calculate_multi_draw_repeat_balls(all_draws, num_previous_draws=5, ball_type='red')
        multi_draw_repeat_blue = calculate_multi_draw_repeat_balls(all_draws, num_previous_draws=5, ball_type='blue')

        # 4. 斜连号和跳号
        diagonal_skip_red = calculate_diagonal_skip_numbers(all_draws, ball_type='red', lookback_periods=10)
        diagonal_skip_blue = calculate_diagonal_skip_numbers(all_draws, ball_type='blue', lookback_periods=10)

        # 5. 连号趋势
        consecutive_trend_red = calculate_consecutive_trend_over_draws(all_draws, ball_type='red')
        consecutive_trend_blue = calculate_consecutive_trend_over_draws(all_draws, ball_type='blue')

        # 清除旧的趋势数据
        from models import TrendProbabilities # 确保导入 TrendProbabilities
        TrendProbabilities.query.filter_by(lottery_type=lottery_type, lookback_period=len(all_draws)).delete()
        db.session.commit()
        app.logger.info(f"已清除 {lottery_type} (回溯期数: {len(all_draws)}) 的旧趋势数据。")

        trend_entries = []
        current_time = datetime.utcnow()
        
        # 存储聚合统计数据
        for metric_group, stats_dict in aggregated_stats.items():
            if isinstance(stats_dict, dict):
                for metric_value, count in stats_dict.items():
                    # 避免存储空字典或列表
                    if not metric_value:
                        continue
                    
                    # 计算概率 (如果适用)
                    probability = count / len(all_draws) if len(all_draws) > 0 else 0

                    trend_entries.append(TrendProbabilities(
                        lottery_type=lottery_type,
                        lookback_period=len(all_draws),
                        trend_metric=metric_group,
                        metric_value=str(metric_value), # 确保是字符串
                        probability=probability,
                        distribution_data={'count': count}, # 存储计数
                        last_calculated_at=current_time
                    ))
            elif isinstance(stats_dict, list): # 例如 red_stats, blue_stats
                for item in stats_dict:
                    ball = item.get('ball')
                    if ball is not None:
                        # 存储单个号码的频率和遗漏
                        trend_entries.append(TrendProbabilities(
                            lottery_type=lottery_type,
                            lookback_period=len(all_draws),
                            trend_metric=f"{metric_group}_ball_{ball}", # 例如 "red_stats_ball_1"
                            metric_value=str(ball),
                            probability=item.get('frequency_percentage', 0) / 100, # 转换为小数
                            distribution_data={
                                'frequency_count': item.get('frequency_count'),
                                'current_omission': item.get('current_omission'),
                                'max_omission': item.get('max_omission')
                            },
                            last_calculated_at=current_time
                        ))

        # 存储多期重复号码
        for ball, count in multi_draw_repeat_red.items():
            trend_entries.append(TrendProbabilities(
                lottery_type=lottery_type,
                lookback_period=len(all_draws),
                trend_metric='multi_draw_repeat_red',
                metric_value=str(ball),
                probability=count / len(all_draws) if len(all_draws) > 0 else 0,
                distribution_data={'count': count},
                last_calculated_at=current_time
            ))
        for ball, count in multi_draw_repeat_blue.items():
            trend_entries.append(TrendProbabilities(
                lottery_type=lottery_type,
                lookback_period=len(all_draws),
                trend_metric='multi_draw_repeat_blue',
                metric_value=str(ball),
                probability=count / len(all_draws) if len(all_draws) > 0 else 0,
                distribution_data={'count': count},
                last_calculated_at=current_time
            ))

        # 存储斜连号和跳号
        if diagonal_skip_red:
            trend_entries.append(TrendProbabilities(
                lottery_type=lottery_type,
                lookback_period=len(all_draws),
                trend_metric='diagonal_numbers_red',
                metric_value=','.join(map(str, diagonal_skip_red.get('diagonal_numbers', []))),
                probability=len(diagonal_skip_red.get('diagonal_numbers', [])) / red_ball_range if red_ball_range > 0 else 0,
                distribution_data={'numbers': diagonal_skip_red.get('diagonal_numbers', [])},
                last_calculated_at=current_time
            ))
            trend_entries.append(TrendProbabilities(
                lottery_type=lottery_type,
                lookback_period=len(all_draws),
                trend_metric='skip_numbers_red',
                metric_value=','.join(map(str, diagonal_skip_red.get('skip_numbers', []))),
                probability=len(diagonal_skip_red.get('skip_numbers', [])) / red_ball_range if red_ball_range > 0 else 0,
                distribution_data={'numbers': diagonal_skip_red.get('skip_numbers', [])},
                last_calculated_at=current_time
            ))
        if diagonal_skip_blue:
            trend_entries.append(TrendProbabilities(
                lottery_type=lottery_type,
                lookback_period=len(all_draws),
                trend_metric='diagonal_numbers_blue',
                metric_value=','.join(map(str, diagonal_skip_blue.get('diagonal_numbers', []))),
                probability=len(diagonal_skip_blue.get('diagonal_numbers', [])) / blue_ball_range if blue_ball_range > 0 else 0,
                distribution_data={'numbers': diagonal_skip_blue.get('diagonal_numbers', [])},
                last_calculated_at=current_time
            ))
            trend_entries.append(TrendProbabilities(
                lottery_type=lottery_type,
                lookback_period=len(all_draws),
                trend_metric='skip_numbers_blue',
                metric_value=','.join(map(str, diagonal_skip_blue.get('skip_numbers', []))),
                probability=len(diagonal_skip_blue.get('skip_numbers', [])) / blue_ball_range if blue_ball_range > 0 else 0,
                distribution_data={'numbers': diagonal_skip_blue.get('skip_numbers', [])},
                last_calculated_at=current_time
            ))

        # 存储连号趋势
        for length, count in consecutive_trend_red.items():
            trend_entries.append(TrendProbabilities(
                lottery_type=lottery_type,
                lookback_period=len(all_draws),
                trend_metric='consecutive_trend_red',
                metric_value=f"{length}_consecutive",
                probability=count / len(all_draws) if len(all_draws) > 0 else 0,
                distribution_data={'count': count},
                last_calculated_at=current_time
            ))
        for length, count in consecutive_trend_blue.items():
            trend_entries.append(TrendProbabilities(
                lottery_type=lottery_type,
                lookback_period=len(all_draws),
                trend_metric='consecutive_trend_blue',
                metric_value=f"{length}_consecutive",
                probability=count / len(all_draws) if len(all_draws) > 0 else 0,
                distribution_data={'count': count},
                last_calculated_at=current_time
            ))

        db.session.add_all(trend_entries)
        db.session.commit()
        app.logger.info(f"{lottery_type} 趋势数据计算完成并存储到数据库。共 {len(trend_entries)} 条记录。")
        return trend_entries # 返回存储的记录列表


# --- 福运奖状态管理 ---
def update_fuyun_prize_status(pool_amount, current_status):
    """
    更新福运奖的启用/关闭状态。
    pool_amount: 当前奖池金额
    current_status: 当前福运奖状态 (True/False)
    返回: 新的福运奖状态
    """
    if pool_amount is None:
        return current_status
    
    new_status = current_status
    if pool_amount >= FUYUN_PRIZE_ENABLE_THRESHOLD:
        # 奖池≥15亿，启用福运奖
        new_status = True
    elif pool_amount < FUYUN_PRIZE_DISABLE_THRESHOLD:
        # 奖池<3亿，关闭福运奖
        new_status = False
    # 奖池在3亿~15亿之间时，保持当前状态不变（有滞后性）
    
    return new_status
