# utils.py
from datetime import datetime, timedelta
import math
from collections import Counter


# 版本号，每次生成文件时更新
__version__ = "1.0.0"

def format_lottery_numbers(numbers_str):
    """将逗号分隔的数字字符串转换为整数列表并排序"""
    try:
        return sorted([int(x) for x in numbers_str.split(',')])
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
    return groups

def is_consecutive_ball(ball, all_balls_list):
    """检查一个球是否是连续号码组的一部分"""
    if not all_balls_list:
        return False
    # 检查前一个或后一个是否存在且连续
    return (ball - 1 in all_balls_list) or (ball + 1 in all_balls_list)

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
'''
def calculate_odd_even_sum(draw):
    """计算一期开奖的奇偶比和红球和值"""
    red_balls = draw.get_red_balls_list()
    odd_count = sum(1 for x in red_balls if x % 2 != 0)
    even_count = len(red_balls) - odd_count
    red_sum = sum(red_balls)
    return odd_count, even_count, red_sum
'''
def calculate_odd_even_sum(draw):
    """计算数字字符串的奇偶比和总和"""
    numbers = format_lottery_numbers(draw) # 使用 format_lottery_numbers 确保是列表
    if not numbers:
        return 0, 0, 0 # 默认值

    odd_count = sum(1 for n in numbers if n % 2 != 0)
    even_count = len(numbers) - odd_count
    total_sum = sum(numbers)
    return odd_count, even_count, total_sum # 返回一个元组

def calculate_frequency_and_omissions(draws_list, ball_range, ball_type):
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
        
        for ball in balls:
            if 1 <= ball <= ball_range:
                stats[ball]['frequency_count'] += 1
                
                # 更新最大遗漏 (如果当前球出现，则重置其遗漏计数器)
                for b_num in range(1, ball_range + 1):
                    if b_num != ball and stats[b_num]['last_seen_index'] != -1: # 如果这个球不是当前出现的球，且之前出现过
                        current_omission_for_b = draw_index - stats[b_num]['last_seen_index'] -1 # 从上次出现到当前期之间的期数
                        if current_omission_for_b > stats[b_num]['max_omission']:
                            stats[b_num]['max_omission'] = current_omission_for_b
                stats[ball]['last_seen_index'] = draw_index # 更新当前球的最后出现位置

    # 第二次遍历：计算当前遗漏 (从最新一期开始算)
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

# --- 聚合统计函数 (用于 history 页面) ---

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

# 重命名并调整原有的 calculate_frequency_and_omissions，使其只关注单个号码的统计
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

# TODO: 更多统计函数，如热号/冷号图表数据准备c
# TODO: 兑奖逻辑辅助函数
# TODO: 趣味游戏日期计算辅助函数 (考虑节假日)


