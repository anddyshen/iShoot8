# utils.py
from datetime import datetime, timedelta, date
import math
from collections import Counter
import random
from config import PRIZE_RULES, CURRENT_SETTINGS, PER_BET_PRICE # 导入中奖规则和当前设置

# 版本号，每次生成文件时更新
__version__ = "1.0.0"

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


# --- 对奖逻辑辅助函数 ---
def calculate_prize_details(user_red_balls, user_blue_balls, draw_red_balls, draw_blue_balls, lottery_type):
    """
    检查用户号码与一期开奖号码的中奖情况，并计算每个奖项的中奖注数。
    user_red_balls: 用户选择的红球列表 (已排序)
    user_blue_balls: 用户选择的蓝球列表 (已排序)
    draw_red_balls: 开奖红球列表 (已排序)
    draw_blue_balls: 开奖蓝球列表 (已排序)
    lottery_type: 'ssq' 或 'dlt'
    返回: { 'prize_level': { 'count': int, 'amount': float }, ... }
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

    # 未匹配的红球和蓝球 (用户选择但未中奖)
    unmatched_user_red_count = len(user_red_set) - matched_red_count
    unmatched_user_blue_count = len(user_blue_set) - matched_blue_count

    # 实际开奖但用户未选择的红球和蓝球 (用于计算组合数)
    draw_unmatched_red_count = len(draw_red_set) - matched_red_count
    draw_unmatched_blue_count = len(draw_blue_set) - matched_blue_count

    # 存储中奖详情
    prize_details = Counter()

    # 遍历所有奖项规则，计算中奖注数
    for prize_rule in rules['prizes']:
        required_red = prize_rule['match_red']
        required_blue = prize_rule['match_blue']

        # 计算红球中奖注数
        # 从匹配的红球中选择 required_red 个
        # 从用户未匹配的红球中选择 (6 - required_red) 个，且这些球必须是开奖号码中未匹配的
        # 简化：这里我们只考虑用户选择的号码与开奖号码的匹配情况
        
        # 假设用户选择的红球数量 >= required_red
        # 且用户选择的蓝球数量 >= required_blue
        
        # 从用户选择的红球中，有多少种方式能匹配 required_red 个开奖红球
        # 并且有多少种方式能匹配 (用户红球总数 - required_red) 个非开奖红球
        
        # 实际中奖注数计算：
        # 从用户匹配的红球中选 required_red 个 (C(matched_red_count, required_red))
        # 从用户未匹配的红球中选 (num_red_balls_to_draw - required_red) 个，且这些球必须是开奖号码中未匹配的
        # 简化为：从用户匹配的红球中选 required_red 个
        # 从用户未匹配的红球中选 (num_red_balls_to_draw - required_red) 个，且这些球必须是开奖号码中未匹配的
        
        # 修正复式中奖注数计算逻辑
        # 假设标准玩法是 SSQ: 6红1蓝, DLT: 5红2蓝
        standard_red_count = 6 if lottery_type == 'ssq' else 5
        standard_blue_count = 1 if lottery_type == 'ssq' else 2

        # 计算红球部分的中奖注数
        # 从用户选中的且与开奖号码匹配的红球中，选择 required_red 个
        c_matched_red = combinations(matched_red_count, required_red)
        
        # 从用户选中的但未与开奖号码匹配的红球中，选择 (standard_red_count - required_red) 个
        # 且这些球必须是开奖号码中未匹配的
        # 这一步是复式计算的核心，需要从用户选择的非中奖红球中，选择与开奖号码中非中奖红球匹配的
        # 简化为：从用户选择的非中奖红球中，选择 (standard_red_count - required_red) 个
        # 且这些球必须是开奖号码中未匹配的
        
        # 实际计算：
        # 从用户选中的且与开奖号码匹配的红球中，选择 required_red 个
        # 从用户选中的但未与开奖号码匹配的红球中，选择 (standard_red_count - required_red) 个
        # 这里的 (standard_red_count - required_red) 是指构成一注标准彩票所需的非中奖红球数量
        
        # 假设用户选择的红球总数为 N_red_user
        # 匹配红球 M_red
        # 未匹配红球 U_red = N_red_user - M_red
        # 开奖红球总数 N_red_draw = 6 (SSQ) 或 5 (DLT)
        # 开奖红球中未匹配的 (即用户没选中的) U_red_draw = N_red_draw - M_red
        
        # 红球中奖注数 = C(M_red, required_red) * C(U_red, N_red_draw - required_red)
        # 注意：C(U_red, N_red_draw - required_red) 这里的 U_red 是用户选择的非中奖红球
        # N_red_draw - required_red 是开奖号码中非中奖红球的数量
        # 实际上，我们应该从用户选择的红球中，选出 required_red 个匹配的，
        # 再从用户选择的红球中，选出 (standard_red_count - required_red) 个不匹配的。
        # 且这 (standard_red_count - required_red) 个不匹配的红球，必须是开奖号码中没有的。
        
        # 更准确的复式计算：
        # 从用户选中的匹配红球中选 `required_red` 个: C(matched_red_count, required_red)
        # 从用户选中的非匹配红球中选 `standard_red_count - required_red` 个: C(len(user_red_set - draw_red_set), standard_red_count - required_red)
        red_prize_combinations = combinations(matched_red_count, required_red) * \
                                 combinations(len(user_red_set - draw_red_set), standard_red_count - required_red)

        # 计算蓝球部分的中奖注数
        # 从用户选中的匹配蓝球中选 `required_blue` 个: C(matched_blue_count, required_blue)
        # 从用户选中的非匹配蓝球中选 `standard_blue_count - required_blue` 个: C(len(user_blue_set - draw_blue_set), standard_blue_count - required_blue)
        blue_prize_combinations = combinations(matched_blue_count, required_blue) * \
                                  combinations(len(user_blue_set - draw_blue_set), standard_blue_count - required_blue)
        
        total_prize_count_for_level = red_prize_combinations * blue_prize_combinations
        
        if total_prize_count_for_level > 0:
            prize_details[prize_rule['level']] += total_prize_count_for_level
            
    return prize_details

# --- 趣味游戏模拟函数 ---
def simulate_fun_game(user_red_balls, user_blue_balls, lottery_type, max_simulations=1000000):
    """
    模拟虚拟开奖，直到用户号码中得一等奖，或达到最大模拟次数。
    返回模拟结果，包括中奖次数、预计时间等。
    """
    rules = PRIZE_RULES.get(lottery_type)
    if not rules:
        return {'error': 'Invalid lottery type'}

    red_range = rules['red_range'] # 从 PRIZE_RULES 获取范围
    blue_range = rules['blue_range'] # 从 PRIZE_RULES 获取范围
    
    # 确保用户至少选择了一个红球或一个蓝球
    if not user_red_balls and not user_blue_balls:
        return {'error': '请至少选择一个红球或一个蓝球进行模拟。'}

    # 模拟开奖需要知道开奖号码的数量，这里假设是标准玩法
    num_red_balls_to_draw = 6 if lottery_type == 'ssq' else 5
    num_blue_balls_to_draw = 1 if lottery_type == 'ssq' else 2

    # 修正：这里只检查用户选择的号码是否在有效范围内，不限制数量
    for ball in user_red_balls:
        if not (1 <= ball <= red_range):
            return {'error': f"用户选择的红球 {ball} 超出了有效范围 (1-{red_range})。"}
    for ball in user_blue_balls:
        if not (1 <= ball <= blue_range):
            return {'error': f"用户选择的蓝球 {ball} 超出了有效范围 (1-{blue_range})。"}

    first_prize_found = False
    draw_count = 0
    total_prizes_counter = Counter() # 统计各奖项中奖次数

    while not first_prize_found and draw_count < max_simulations:
        draw_count += 1
        
        # 模拟开奖号码：从所有可能的球中随机抽取固定数量的球
        if num_red_balls_to_draw > red_range:
            return {'error': f"模拟红球数量 ({num_red_balls_to_draw}) 超过了红球范围 ({red_range})。"}
        if num_blue_balls_to_draw > blue_range:
            return {'error': f"模拟蓝球数量 ({num_blue_balls_to_draw}) 超过了蓝球范围 ({blue_range})。"}

        simulated_red_balls = sorted(random.sample(range(1, red_range + 1), num_red_balls_to_draw))
        simulated_blue_balls = sorted(random.sample(range(1, blue_range + 1), num_blue_balls_to_draw))

        # 检查中奖情况，现在使用 calculate_prize_details 获取所有奖项的注数
        prize_details_for_draw = calculate_prize_details(
            user_red_balls, user_blue_balls,
            simulated_red_balls, simulated_blue_balls,
            lottery_type
        )

        for level, count in prize_details_for_draw.items():
            total_prizes_counter[level] += count
            if level == '一等奖' and count > 0:
                first_prize_found = True
                # break # 循环条件已经包含 first_prize_found，所以这里可以省略
    
    result = {
        'input_red_balls': user_red_balls,
        'input_blue_balls': user_blue_balls,
        'total_prizes': dict(total_prizes_counter), # 使用 Counter 的结果
        'first_prize_info': None
    }

    if first_prize_found:
        # 估算中奖时间
        # 计算每周开奖次数
        draw_days_count = 0
        if lottery_type == 'ssq':
            draw_days_count = len(CURRENT_SETTINGS.get('ssq_draw_days', []))
        elif lottery_type == 'dlt':
            draw_days_count = len(CURRENT_SETTINGS.get('dlt_draw_days', []))
        
        draws_per_week = draw_days_count if draw_days_count > 0 else 1 # 至少1次/周

        # 考虑年度节假日
        annual_holidays = CURRENT_SETTINGS.get('annual_holidays', [])
        
        actual_draw_count = 0
        current_sim_date = datetime.now().date()
        
        # 计算总共需要跳过的节假日天数
        total_holiday_days_skipped = 0
        
        # 模拟每一天，直到达到中一等奖所需的开奖次数
        while actual_draw_count < draw_count:
            current_sim_date += timedelta(days=1)
            
            is_draw_day = False
            if lottery_type == 'ssq' and current_sim_date.isoweekday() in CURRENT_SETTINGS.get('ssq_draw_days', []):
                is_draw_day = True
            elif lottery_type == 'dlt' and current_sim_date.isoweekday() in CURRENT_SETTINGS.get('dlt_draw_days', []):
                is_draw_day = True
            
            is_holiday = False
            for holiday in annual_holidays:
                holiday_start_str = holiday['start']
                holiday_start_month = int(holiday_start_str.split('-')[0])
                holiday_start_day = int(holiday_start_str.split('-')[1])
                
                holiday_start_date_this_year = date(current_sim_date.year, holiday_start_month, holiday_start_day)
                holiday_end_date_this_year = holiday_start_date_this_year + timedelta(weeks=holiday['duration_weeks']) - timedelta(days=1) # 结束日期包含在内
                
                if holiday_start_date_this_year <= current_sim_date <= holiday_end_date_this_year:
                    is_holiday = True
                    break
            
            if is_draw_day and not is_holiday:
                actual_draw_count += 1
            # else:
            #     if is_holiday:
            #         total_holiday_days_skipped += 1 # 统计跳过的节假日天数，但这里不需要精确到天，只需要最终日期

        estimated_date = current_sim_date.strftime('%Y年%m月%d日') # 格式化为中文日期
        
        # 计算单次投注花费
        cost_details = calculate_combination_cost(len(user_red_balls), len(user_blue_balls), lottery_type)
        estimated_cost = draw_count * cost_details['total_cost'] # 假设每期买一注复式

        result['first_prize_info'] = {
            'draw_count': draw_count,
            'estimated_date': estimated_date,
            'estimated_cost': f"{estimated_cost:,.0f}" # 格式化金额
        }
    
    # 按奖项级别降序排列 total_prizes
    # 获取奖项的固定顺序
    prize_level_order = [p['level'] for p in rules['prizes']]
    
    # 根据固定顺序对 total_prizes 进行排序
    sorted_prizes = sorted(total_prizes_counter.items(), key=lambda item: prize_level_order.index(item[0]) if item[0] in prize_level_order else len(prize_level_order))
    result['total_prizes'] = {level: count for level, count in sorted_prizes}

    return result

