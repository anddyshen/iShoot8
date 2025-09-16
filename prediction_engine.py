# prediction_engine.py
import random
from collections import Counter
from flask import current_app
from models import SSQDraw, DLTDraw, db
from config import CURRENT_SETTINGS
from utils import format_lottery_numbers, calculate_omissions, get_consecutive_groups, calculate_odd_even_sum

# 版本号，每次生成文件时更新
__version__ = "1.0.4" # 更新版本号

# --- 辅助函数：获取指定期号之前的历史开奖数据 ---
def _get_previous_draws(model_class, current_issue, num_draws):
    """
    获取指定期号之前的num_draws期开奖数据。
    返回的列表按issue降序排列 (即最新一期在前)。
    """
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
    
    # TODO: 规则 4.1.2 和 4.1.10 主要是用于“生成”号码时调整概率的，
    # 如果要用于“检查”，需要明确其通过/不通过的判断标准。
    # 暂时不实现这些生成型规则的检查。

    return results

def check_dlt_rules_for_draw(draw: DLTDraw):
    """
    检查大乐透开奖号码是否符合预设规则。
    返回一个字典，包含规则检查结果。
    """
    results = {}
    front_balls = draw.get_red_balls_list() # 大乐透前区对应 LotteryDraw 的 red_balls
    
    # 应用大乐透规则
    results['rule_4_2_1_blue_repeat_latest'] = _check_dlt_rule_4_2_1_blue_repeat_latest(draw)
    results['rule_4_2_3_red_consecutive_repeat'] = _check_dlt_rule_4_2_3_red_consecutive_repeat(draw)
    results['rule_4_2_4_red_area_distribution'] = _check_dlt_rule_4_2_4_red_area_distribution(front_balls)
    results['rule_4_2_5_red_repeat_previous_2'] = _check_dlt_rule_4_2_5_red_repeat_previous_2(draw)
    results['rule_4_2_6_red_consecutive_4_plus'] = _check_dlt_rule_4_2_6_red_consecutive_4_plus(front_balls)

    # TODO: 规则 4.2.2 和 4.2.10 主要是用于“生成”号码时调整概率的，
    # 如果要用于“检查”，需要明确其通过/不通过的判断标准。
    # 暂时不实现这些生成型规则的检查。

    return results


def check_lottery_rules(lottery_type: str, issue: str):
    """
    根据彩种类型和期号，调用相应的规则检查函数。
    """
    if lottery_type == 'ssq':
        draw = SSQDraw.query.filter_by(issue=issue).first()
        if draw:
            return check_ssq_rules_for_draw(draw)
        else:
            return {'error': 'SSQDraw not found', 'message': f'未找到双色球期号 {issue} 的数据。'}
    elif lottery_type == 'dlt':
        draw = DLTDraw.query.filter_by(issue=issue).first()
        if draw:
            return check_dlt_rules_for_draw(draw)
        else:
            return {'error': 'DLTDraw not found', 'message': f'未找到大乐透期号 {issue} 的数据。'}
    else:
        return {'error': 'Invalid lottery type', 'message': f'不支持的彩种类型: {lottery_type}。'}


# --- 您原有的 LotteryPredictor 类 (用于生成预测号码) ---
class LotteryPredictor:
    def __init__(self, lottery_type):
        self.lottery_type = lottery_type
        self.settings = CURRENT_SETTINGS
        self.draw_model = SSQDraw if lottery_type == 'ssq' else DLTDraw
        self.red_ball_range = 33 if lottery_type == 'ssq' else 35
        self.blue_ball_range = 16 if lottery_type == 'ssq' else 12
        self.red_ball_count = 6 if lottery_type == 'ssq' else 5
        self.blue_ball_count = 1 if lottery_type == 'ssq' else 2
        
        # 优化：只查询最近需要的数据，而不是所有
        # 获取用于预测的最新期数，例如用于规则 4.1.11/4.2.11
        max_recent_draws_needed = max(
            self.settings.get('prediction_latest_draws', 10), # 用于 LotteryPredictor 初始化
            self.settings.get('ssq_blue_recent_occurrence_draws', 10),
            self.settings.get('dlt_blue_recent_occurrence_draws', 10)
        )
        # 确保加载足够多的历史数据以满足所有规则的需求
        self.all_draws = self.draw_model.query.order_by(self.draw_model.issue.desc()).limit(max_recent_draws_needed + 5).all() # 加一点余量
        self.recent_draws_for_prediction = self.all_draws[:max_recent_draws_needed]
        self.latest_draws = self.recent_draws_for_prediction[:self.settings.get('prediction_latest_draws', 10)]


    def _get_all_red_balls_history(self):
        # 注意：此方法现在只返回 self.all_draws 中的红球，而不是所有历史红球
        return [ball for draw in self.all_draws for ball in draw.get_red_balls_list()]

    def _get_all_blue_balls_history(self):
        # 注意：此方法现在只返回 self.all_draws 中的蓝球，而不是所有历史蓝球
        return [ball for draw in self.all_draws for ball in draw.get_blue_balls_list()]

    def _get_recent_red_balls(self, num_draws):
        return [ball for draw in self.recent_draws_for_prediction[:num_draws] for ball in draw.get_red_balls_list()]

    def _get_recent_blue_balls(self, num_draws):
        return [ball for draw in self.recent_draws_for_prediction[:num_draws] for ball in draw.get_blue_balls_list()]

    def _get_omitted_balls(self, ball_type):
        # calculate_omissions 函数需要所有历史数据，这里需要调整
        # 如果 self.all_draws 只是部分数据，那么遗漏计算可能不准确
        # 暂时保持原样，但需注意此处的潜在问题
        return calculate_omissions(self.all_draws, self.red_ball_range if ball_type == 'red' else self.blue_ball_range, ball_type)

    def _apply_rule_4_1_1_ssq(self, blue_candidates):
        """双色球蓝球规则 4.1.1 (用于生成预测号码)"""
        latest_blue = self.latest_draws[0].get_blue_balls_list()[0] if self.latest_draws else None
        if latest_blue and latest_blue in blue_candidates:
            blue_candidates.remove(latest_blue) # 最新一期开出过的号码不作为本期的预测候选号码

        # 连续开出号码的概率调整 (这里需要一个权重调整机制)
        # 规则 4.1.1: 连续5期开出，概率35%；连续3期开出，概率8%
        # 这部分逻辑需要更复杂的权重系统，暂时留空或简化
        
        return blue_candidates # 暂时只处理移除逻辑

    def _apply_rule_4_1_2_ssq(self, red_weights):
        """双色球红球规则 4.1.2 (遗漏期数权重，用于生成预测号码)"""
        omissions = self._get_omitted_balls('red')
        sorted_omissions = sorted(omissions.items(), key=lambda item: item[1], reverse=True)

        # 权重分配 (从 config.py 获取，如果不存在则使用默认值)
        weights_config = [
            self.settings.get('ssq_red_omit_1_weight', 0.01),
            self.settings.get('ssq_red_omit_2_weight', 0.015),
            self.settings.get('ssq_red_omit_3_weight', 0.02),
            self.settings.get('ssq_red_omit_4_weight', 0.03),
            self.settings.get('ssq_red_omit_5_weight', 0.03),
            self.settings.get('ssq_red_omit_6_weight', 0.03)
        ]
        
        total_assigned_weight = 0
        for i, (ball, omit_count) in enumerate(sorted_omissions):
            if i < len(weights_config):
                red_weights[ball] = weights_config[i]
                total_assigned_weight += weights_config[i]
            else:
                break # 只处理前6个

        # 剩余权重平分给其他球
        remaining_balls_count = self.red_ball_range - len(weights_config)
        if remaining_balls_count > 0:
            remaining_weight_per_ball = (1.0 - total_assigned_weight) / remaining_balls_count
            for ball in range(1, self.red_ball_range + 1):
                if ball not in [item[0] for item in sorted_omissions[:len(weights_config)]]:
                    red_weights[ball] = remaining_weight_per_ball
        
        return red_weights

    # --- 新增规则 4.1.11 (双色球蓝球最新出现频率) ---
    def _apply_rule_4_1_11_ssq(self, blue_weights):
        """
        规则 4.1.11 双色球蓝球最新出现频率
        最新的蓝球号码在前[10]期内出现[5]次以上的，在预测池中出现概率变为到[40]%,其他的号码平分剩下的概率。
        """
        if not self.latest_draws:
            return blue_weights

        latest_blue_ball = self.latest_draws[0].get_blue_balls_list()[0]
        
        num_draws_to_check = self.settings.get('ssq_blue_recent_occurrence_draws', 10)
        occurrence_threshold = self.settings.get('ssq_blue_recent_occurrence_threshold', 5)
        boost_weight = self.settings.get('ssq_blue_recent_occurrence_weight', 0.40)

        # 统计最新蓝球在最近N期内的出现次数
        count = 0
        for draw in self.recent_draws_for_prediction[:num_draws_to_check]:
            if draw.get_blue_balls_list() and latest_blue_ball == draw.get_blue_balls_list()[0]:
                count += 1
        
        current_app.logger.debug(f"Rule 4.1.11: Latest SSQ blue ball {latest_blue_ball} appeared {count} times in last {num_draws_to_check} draws.")

        if count >= occurrence_threshold:
            blue_weights[latest_blue_ball] = boost_weight
            remaining_weight = 1.0 - boost_weight
            
            other_balls_count = len(blue_weights) - 1
            if other_balls_count > 0:
                weight_per_other_ball = remaining_weight / other_balls_count
                for ball in blue_weights:
                    if ball != latest_blue_ball:
                        blue_weights[ball] = weight_per_other_ball
            else: # 只有一个蓝球候选，且就是最新蓝球
                blue_weights[latest_blue_ball] = 1.0
            current_app.logger.info(f"Rule 4.1.11: SSQ blue ball {latest_blue_ball} boosted to {boost_weight*100:.0f}% probability.")
        
        return blue_weights

    # TODO: 实现其他规则的 _apply_ 或 _filter_ 方法，用于生成预测号码

    def generate_ssq_prediction(self, num_combinations=10, is_complex_bet=False, red_count=6, blue_count=1):
        """
        生成双色球预测号码。
        is_complex_bet: 是否为复式投注
        red_count: 复式红球数量
        blue_count: 复式蓝球数量
        """
        # 1. 初始化红蓝球候选池和权重
        red_candidates = list(range(1, self.red_ball_range + 1))
        blue_candidates = list(range(1, self.blue_ball_range + 1))
        red_weights = {ball: 1.0 / self.red_ball_range for ball in red_candidates} # 初始平均权重
        blue_weights = {ball: 1.0 / self.blue_ball_range for ball in blue_candidates}

        # 2. 应用规则调整候选池和权重 (按优先级顺序)
        # 蓝球规则 4.1.1
        blue_candidates = self._apply_rule_4_1_1_ssq(blue_candidates)
        # 红球规则 4.1.2
        red_weights = self._apply_rule_4_1_2_ssq(red_weights)
        # 新增规则 4.1.11
        blue_weights = self._apply_rule_4_1_11_ssq(blue_weights)
        # TODO: 应用其他规则 4.1.3, 4.1.10 等，这些规则会修改 red_weights 或 blue_weights

        # 3. 归一化权重 (Rule 9)
        total_red_weight = sum(red_weights.values())
        if total_red_weight > 0:
            red_weights = {ball: weight / total_red_weight for ball, weight in red_weights.items()}
        else:
            current_app.logger.warning("Red ball total weight is zero after rules, resetting to uniform.")
            red_weights = {ball: 1.0 / len(red_candidates) for ball in red_candidates}

        total_blue_weight = sum(blue_weights.values())
        if total_blue_weight > 0:
            blue_weights = {ball: weight / total_blue_weight for ball, weight in blue_weights.items()}
        else:
            current_app.logger.warning("Blue ball total weight is zero after rules, resetting to uniform.")
            blue_weights = {ball: 1.0 / len(blue_candidates) for ball in blue_candidates}

        current_app.logger.info(f"Red weights normalized: {sum(red_weights.values()):.2f}%")
        current_app.logger.info(f"Blue weights normalized: {sum(blue_weights.values()):.2f}%")

        # 4. 生成号码组合并进行筛选 (Rule 4.1.4, 4.1.5, 4.1.6)
        predicted_combinations = []
        attempts = 0
        max_attempts_per_combo = 1000 # 防止无限循环
        
        while len(predicted_combinations) < num_combinations and attempts < num_combinations * max_attempts_per_combo:
            attempts += 1
            
            # 根据权重随机选择红球
            chosen_red_balls = random.choices(
                list(red_weights.keys()),
                weights=list(red_weights.values()),
                k=red_count
            )
            chosen_red_balls = sorted(list(set(chosen_red_balls))) # 去重并排序

            # 如果是单式，确保红球数量正确
            if not is_complex_bet and len(chosen_red_balls) != self.red_ball_count:
                continue # 重新生成

            # 根据权重随机选择蓝球
            chosen_blue_balls = random.choices(
                list(blue_weights.keys()),
                weights=list(blue_weights.values()),
                k=blue_count
            )
            chosen_blue_balls = sorted(list(set(chosen_blue_balls)))

            # 如果是单式，确保蓝球数量正确
            if not is_complex_bet and len(chosen_blue_balls) != self.blue_ball_count:
                continue # 重新生成

            # 应用筛选规则 (这里需要针对生成号码的列表进行检查，而不是针对 draw 对象)
            # 这些检查函数需要独立于 _check_ssq_rule_..._for_draw
            # 例如：
            # if not _check_ssq_rule_4_1_4_red_area_distribution(chosen_red_balls)['passed']: continue
            # if not _check_ssq_rule_4_1_6_red_consecutive_4_plus(chosen_red_balls)['passed']: continue
            # TODO: 应用其他筛选规则

            predicted_combinations.append({'red': chosen_red_balls, 'blue': chosen_blue_balls})

        return predicted_combinations

    # --- 新增规则 4.2.11 (大乐透蓝球最新出现频率) ---
    def _apply_rule_4_2_11_dlt(self, blue_weights):
        """
        规则 4.2.11 大乐透蓝球最新出现频率
        最新的蓝球号码在前[10]期内出现[8]次以上的，在预测池中出现概率变为到[40]%,其他的号码平分剩下的概率。
        """
        if not self.latest_draws:
            return blue_weights

        # 大乐透蓝球可能有多个，这里规则描述是“最新的蓝球号码”，通常指最新一期开出的所有蓝球
        # 我们假设这里指的是最新一期开出的所有蓝球中的每一个，如果其中任何一个满足条件，则提升其概率。
        # 如果多个满足，则多个提升。
        latest_blue_balls = self.latest_draws[0].get_blue_balls_list()
        
        num_draws_to_check = self.settings.get('dlt_blue_recent_occurrence_draws', 10)
        occurrence_threshold = self.settings.get('dlt_blue_recent_occurrence_threshold', 8)
        boost_weight = self.settings.get('dlt_blue_recent_occurrence_weight', 0.40)

        # 存储需要提升权重的蓝球
        balls_to_boost = set()
        for lb in latest_blue_balls:
            count = 0
            for draw in self.recent_draws_for_prediction[:num_draws_to_check]:
                if draw.get_blue_balls_list() and lb in draw.get_blue_balls_list():
                    count += 1
            
            current_app.logger.debug(f"Rule 4.2.11: Latest DLT blue ball {lb} appeared {count} times in last {num_draws_to_check} draws.")
            if count >= occurrence_threshold:
                balls_to_boost.add(lb)
        
        if balls_to_boost:
            # 计算总的提升权重
            # 确保总权重不会超过 1.0
            total_boost_weight_needed = len(balls_to_boost) * boost_weight
            
            if total_boost_weight_needed >= 1.0:
                current_app.logger.warning(f"Rule 4.2.11: Total boost weight {total_boost_weight_needed} for DLT blue balls exceeds 1.0. Distributing evenly among all blue balls.")
                # 如果提升的权重总和过大，则将所有蓝球权重平均分配
                for ball in blue_weights:
                    blue_weights[ball] = 1.0 / len(blue_weights)
                return blue_weights

            # 提升满足条件的蓝球权重
            for ball in balls_to_boost:
                blue_weights[ball] = boost_weight
            
            # 将剩余权重平分给其他未被提升的蓝球
            remaining_weight = 1.0 - total_boost_weight_needed
            other_balls_count = len(blue_weights) - len(balls_to_boost)
            
            if other_balls_count > 0:
                weight_per_other_ball = remaining_weight / other_balls_count
                for ball in blue_weights:
                    if ball not in balls_to_boost:
                        blue_weights[ball] = weight_per_other_ball
            
            current_app.logger.info(f"Rule 4.2.11: DLT blue balls {list(balls_to_boost)} boosted to {boost_weight*100:.0f}% probability each.")
        
        return blue_weights


    def generate_dlt_prediction(self, num_combinations=10, is_complex_bet=False, red_count=5, blue_count=2):
        """生成大乐透预测号码 (结构与双色球类似，但规则不同)"""
        # 1. 初始化红蓝球候选池和权重
        red_candidates = list(range(1, self.red_ball_range + 1))
        blue_candidates = list(range(1, self.blue_ball_range + 1))
        red_weights = {ball: 1.0 / self.red_ball_range for ball in red_candidates} # 初始平均权重
        blue_weights = {ball: 1.0 / self.blue_ball_range for ball in blue_candidates}

        # 2. 应用规则调整候选池和权重 (按优先级顺序)
        # TODO: 应用大乐透规则 4.2.1, 4.2.2, 4.2.3, 4.2.10 等
        # 新增规则 4.2.11
        blue_weights = self._apply_rule_4_2_11_dlt(blue_weights)

        # 3. 归一化权重 (Rule 9)
        total_red_weight = sum(red_weights.values())
        if total_red_weight > 0:
            red_weights = {ball: weight / total_red_weight for ball, weight in red_weights.items()}
        else:
            current_app.logger.warning("DLT Red ball total weight is zero after rules, resetting to uniform.")
            red_weights = {ball: 1.0 / len(red_candidates) for ball in red_candidates}

        total_blue_weight = sum(blue_weights.values())
        if total_blue_weight > 0:
            blue_weights = {ball: weight / total_blue_weight for ball, weight in blue_weights.items()}
        else:
            current_app.logger.warning("DLT Blue ball total weight is zero after rules, resetting to uniform.")
            blue_weights = {ball: 1.0 / len(blue_candidates) for ball in blue_candidates}

        current_app.logger.info(f"DLT Red weights normalized: {sum(red_weights.values()):.2f}%")
        current_app.logger.info(f"DLT Blue weights normalized: {sum(blue_weights.values()):.2f}%")

        # 4. 生成号码组合并进行筛选 (Rule 4.2.4, 4.2.5, 4.2.6)
        predicted_combinations = []
        attempts = 0
        max_attempts_per_combo = 1000 # 防止无限循环
        
        while len(predicted_combinations) < num_combinations and attempts < num_combinations * max_attempts_per_combo:
            attempts += 1
            
            # 根据权重随机选择红球
            chosen_red_balls = random.choices(
                list(red_weights.keys()),
                weights=list(red_weights.values()),
                k=red_count
            )
            chosen_red_balls = sorted(list(set(chosen_red_balls))) # 去重并排序

            if not is_complex_bet and len(chosen_red_balls) != self.red_ball_count:
                continue # 重新生成

            # 根据权重随机选择蓝球
            chosen_blue_balls = random.choices(
                list(blue_weights.keys()),
                weights=list(blue_weights.values()),
                k=blue_count
            )
            chosen_blue_balls = sorted(list(set(chosen_blue_balls)))

            if not is_complex_bet and len(chosen_blue_balls) != self.blue_ball_count:
                continue # 重新生成

            # TODO: 应用筛选规则 (这里需要针对生成号码的列表进行检查)
            # 例如：
            # if not _check_dlt_rule_4_2_4_red_area_distribution(chosen_red_balls)['passed']: continue
            # if not _check_dlt_rule_4_2_6_red_consecutive_4_plus(chosen_red_balls)['passed']: continue

            predicted_combinations.append({'red': chosen_red_balls, 'blue': chosen_blue_balls})

        return predicted_combinations

    def check_rules_for_combination(self, lottery_type, red_balls, blue_balls):
        """
        检查一组号码是否符合所有预测规则。
        返回一个字典，包含符合/不符合的规则列表。
        这个方法是 LotteryPredictor 的一部分，但 API 端点将使用独立的 check_lottery_rules。
        这个方法更适合用于规则 4.1.9 (检查生成的随机号码)。
        """
        # TODO: 实现所有规则的检查函数，并在此处调用
        # 这将需要创建虚拟的 draw 对象或调整 check_ssq_rules_for_draw
        # 和 check_dlt_rules_for_draw 以接受原始号码列表。
        # 为简单起见，假设这是用于检查“生成”的号码，而不是历史号码。
        # API 端点将使用独立的 `check_lottery_rules` 函数，该函数会查询一个 draw 对象。
        return {"message": "此方法用于检查生成的组合，而非通过API检查历史开奖。"}


    def get_top_omitted_balls(self, count, ball_type):
        """获取遗漏期数最多的N个号码"""
        omissions = self._get_omitted_balls(ball_type)
        sorted_omissions = sorted(omissions.items(), key=lambda item: item[1], reverse=True)
        return sorted_omissions[:count]

    def get_total_combinations_and_filtered_percentage(self, lottery_type):
        """
        计算总组合数及通过规则筛选掉的百分比。
        这是一个非常复杂的计算，可能需要蒙特卡罗模拟或组合数学。
        """
        # TODO: 实现此功能
        pass

# TODO: 兑奖逻辑 (中奖等级判断)
def check_prize(lottery_type, input_red_balls, input_blue_balls, draw_red_balls, draw_blue_balls):
    """
    核对一组号码与开奖号码的中奖情况。
    返回中奖等级和奖金。
    """
    # TODO: 根据双色球/大乐透的官方中奖规则实现
    pass

# TODO: 趣味游戏逻辑
def simulate_lottery_game(lottery_type, user_combinations, start_date, end_date):
    """
    模拟彩票开奖，计算用户号码中奖情况和所需时间/花费。
    """
    # TODO: 实现此功能，包括日期计算、节假日跳过、模拟开奖、中奖核对
    pass

