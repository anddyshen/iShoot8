from flask import Blueprint, render_template, request, flash, redirect, url_for, session, jsonify, current_app
from datetime import datetime, date
from models import SSQDraw, DLTDraw, News, db
from data_manager import get_latest_draws
import threading
import uuid
from time import sleep
from config import CURRENT_SETTINGS, STAT_EXPLANATIONS, PRIZE_RULES, PER_BET_PRICE, SETTING_LABELS_CHINESE
from utils import (
    format_lottery_numbers, 
    get_aggregated_stats, calculate_frequency_and_omissions_for_balls,
    calculate_combination_cost, calculate_prize_details, simulate_fun_game, calculate_total_lottery_combinations,
    get_consecutive_groups, # Import the new function
    calculate_odd_even_ratio_per_draw, calculate_sum_per_draw # 新增导入统计函数
)
from prediction_engine import (
    check_lottery_rules, generate_random_balls, get_omitted_balls_for_prediction, 
    generate_predicted_balls, check_ssq_rules_for_balls, check_dlt_rules_for_balls, # 导入新的规则检查函数
    get_draw_and_matched_omitted_balls_for_offset # 导入新的函数
)

bp = Blueprint('routes', __name__)

@bp.route('/')
def index():
    latest_ssq = get_latest_draws(SSQDraw, 1)
    latest_dlt = get_latest_draws(DLTDraw, 1)
    homepage_news = News.query.filter_by(is_homepage_display=True, is_public=True).order_by(News.created_at.desc()).limit(3).all()

    ssq_red_consecutive_map = {}
    ssq_blue_consecutive_map = {}
    dlt_red_consecutive_map = {}
    dlt_blue_consecutive_map = {}

    if latest_ssq:
        _, ssq_red_consecutive_map = get_consecutive_groups(latest_ssq[0].get_red_balls_list())
        _, ssq_blue_consecutive_map = get_consecutive_groups(latest_ssq[0].get_blue_balls_list())
    if latest_dlt:
        _, dlt_red_consecutive_map = get_consecutive_groups(latest_dlt[0].get_red_balls_list())
        _, dlt_blue_consecutive_map = get_consecutive_groups(latest_dlt[0].get_blue_balls_list())

    return render_template('index.html',
                           latest_ssq=latest_ssq[0] if latest_ssq else None,
                           latest_dlt=latest_dlt[0] if latest_dlt else None,
                           homepage_news=homepage_news,
                           ssq_red_consecutive_map=ssq_red_consecutive_map,
                           ssq_blue_consecutive_map=ssq_blue_consecutive_map,
                           dlt_red_consecutive_map=dlt_red_consecutive_map,
                           dlt_blue_consecutive_map=dlt_blue_consecutive_map)

@bp.route('/history')
def history():
    lottery_type = request.args.get('lottery_type', 'ssq')
    if lottery_type not in ['ssq', 'dlt']:
        flash('无效的彩票类型。', 'danger')
        return redirect(url_for('routes.index'))

    page = request.args.get('page', 1, type=int)
    if page < 1:
        page = 1 # 确保页码不小于1

    per_page = request.args.get('per_page', CURRENT_SETTINGS['history_page_size'], type=int)
    if per_page < 1 or per_page > 100: # 限制每页显示数量在合理范围
        per_page = CURRENT_SETTINGS['history_page_size']

    # 获取日期筛选参数
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')

    start_date_obj = None
    end_date_obj = None

    if start_date_str:
        try:
            start_date_obj = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        except ValueError:
            flash('开始日期格式不正确。', 'warning')
    if end_date_str:
        try:
            end_date_obj = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except ValueError:
            flash('结束日期格式不正确。', 'warning')

    # 构建查询
    if lottery_type == 'ssq':
        model_class = SSQDraw
    else: # default to dlt
        model_class = DLTDraw

    # --- 历史开奖数据分页查询 ---
    query = model_class.query
    if start_date_obj:
        query = query.filter(model_class.draw_date >= start_date_obj)
    if end_date_obj:
        query = query.filter(model_class.draw_date <= end_date_obj)
    
    draws_pagination = query.order_by(model_class.issue.desc()).paginate(page=page, per_page=per_page, error_out=False)

    return render_template('history.html',
                           draws_pagination=draws_pagination,
                           lottery_type=lottery_type,
                           per_page=per_page,
                           start_date=start_date_str,
                           end_date=end_date_str,
                           get_consecutive_groups=get_consecutive_groups, # Pass the function to the template
                           calculate_odd_even_ratio_per_draw=calculate_odd_even_ratio_per_draw, # Pass new function
                           calculate_sum_per_draw=calculate_sum_per_draw # Pass new function
                           )

@bp.route('/statistics')
def statistics():
    lottery_type = request.args.get('lottery_type', 'ssq')
    if lottery_type not in ['ssq', 'dlt']:
        flash('无效的彩票类型。', 'danger')
        return redirect(url_for('routes.index'))


    # 获取日期筛选参数
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')

    start_date_obj = None
    end_date_obj = None

    if start_date_str:
        try:
            start_date_obj = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        except ValueError:
            flash('开始日期格式不正确。', 'warning')
    if end_date_str:
        try:
            end_date_obj = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except ValueError:
            flash('结束日期格式不正确。', 'warning')

    # 获取统计范围参数
    stats_range = request.args.get('stats_range', CURRENT_SETTINGS['history_stats_range_default'], type=int)
    if stats_range < 0: # 0 表示所有历史数据，所以允许0
        stats_range = CURRENT_SETTINGS['history_stats_range_default']

    # 构建查询
    if lottery_type == 'ssq':
        model_class = SSQDraw
        red_ball_range = 33
        blue_ball_range = 16
    else: # default to dlt
        model_class = DLTDraw
        red_ball_range = 35
        blue_ball_range = 12

    # --- 统计数据查询与计算 ---
    stats_query = model_class.query
    if start_date_obj:
        stats_query = stats_query.filter(model_class.draw_date >= start_date_obj)
    if end_date_obj:
        stats_query = stats_query.filter(model_class.draw_date <= end_date_obj)
    
    # 应用统计范围 (如果 stats_range 不为 0)
    if stats_range > 0:
        all_draws_for_stats = stats_query.order_by(model_class.issue.desc()).limit(stats_range).all()
    else: # stats_range == 0, 表示所有历史数据
        all_draws_for_stats = stats_query.order_by(model_class.issue.desc()).all()

    # 调用聚合统计函数
    aggregated_stats = get_aggregated_stats(all_draws_for_stats, lottery_type, CURRENT_SETTINGS)

    return render_template('statistics.html',
                           lottery_type=lottery_type,
                           start_date=start_date_str,
                           end_date=end_date_str,
                           stats_range=stats_range,
                           stats_range_options=CURRENT_SETTINGS['history_stats_range_options'],
                           red_ball_range=red_ball_range,
                           blue_ball_range=blue_ball_range,
                           aggregated_stats=aggregated_stats,
                           stat_explanations=STAT_EXPLANATIONS
                           )

@bp.route('/prediction')
def prediction():
    # 获取最新开奖号码用于显示
    num_latest_draws = CURRENT_SETTINGS.get('prediction_latest_draws', 3)
    
    current_app.logger.info(f"Fetching latest {num_latest_draws} SSQ draws for prediction page.")
    latest_ssq_draws = get_latest_draws(SSQDraw, num_latest_draws)
    current_app.logger.info(f"Fetched {len(latest_ssq_draws)} SSQ draws.")

    current_app.logger.info(f"Fetching latest {num_latest_draws} DLT draws for prediction page.")
    latest_dlt_draws = get_latest_draws(DLTDraw, num_latest_draws)
    current_app.logger.info(f"Fetched {len(latest_dlt_draws)} DLT draws.")

    return render_template('prediction.html',
                           latest_ssq_draws=latest_ssq_draws,
                           latest_dlt_draws=latest_dlt_draws,
                           get_consecutive_groups=get_consecutive_groups, # Pass the function to the template
                           ssq_red_trend_rules=CURRENT_SETTINGS.get('ssq_red_trend_rules', {}),
                           ssq_blue_trend_rules=CURRENT_SETTINGS.get('ssq_blue_trend_rules', {}),
                           dlt_red_trend_rules=CURRENT_SETTINGS.get('dlt_red_trend_rules', {}),
                           dlt_blue_trend_rules=CURRENT_SETTINGS.get('dlt_blue_trend_rules', {}),
                           setting_labels=SETTING_LABELS_CHINESE, # 传递中文标签
                           prediction_generation_mode=CURRENT_SETTINGS.get('prediction_generation_mode', 'rule_based') # 传递默认生成模式
                           )

@bp.route('/api/prediction/active_rules', methods=['GET'])
def api_prediction_active_rules():
    lottery_type = request.args.get('lottery_type')
    if not lottery_type or lottery_type not in ['ssq', 'dlt']:
        return jsonify({'error': 'Invalid or missing lottery_type'}), 400

    active_rules = []
    red_rules_key = f'{lottery_type}_red_trend_rules'
    blue_rules_key = f'{lottery_type}_blue_trend_rules'

    # 获取红球规则
    if red_rules_key in CURRENT_SETTINGS:
        for rule_name, rule_config in CURRENT_SETTINGS[red_rules_key].items():
            if rule_config.get('enabled'):
                active_rules.append({
                    'ball_type': 'red',
                    'rule_name': rule_name,
                    'label': SETTING_LABELS_CHINESE.get(rule_name, rule_name),
                    'params': rule_config.get('params', {}),
                    'logic': rule_config.get('logic', 'AND')
                })
    
    # 获取蓝球规则
    if blue_rules_key in CURRENT_SETTINGS:
        for rule_name, rule_config in CURRENT_SETTINGS[blue_rules_key].items():
            if rule_config.get('enabled'):
                active_rules.append({
                    'ball_type': 'blue',
                    'rule_name': rule_name,
                    'label': SETTING_LABELS_CHINESE.get(rule_name, rule_name),
                    'params': rule_config.get('params', {}),
                    'logic': rule_config.get('logic', 'AND')
                })
    
    return jsonify({'active_rules': active_rules})


@bp.route('/api/prediction/omitted_balls', methods=['GET'])
def api_prediction_omitted_balls():
    lottery_type = request.args.get('lottery_type')
    offset_str = request.args.get('offset', '0') # 重新接受 offset 参数
    current_app.logger.info(f"API call: /api/prediction/omitted_balls for {lottery_type} with offset {offset_str}")

    if not lottery_type or lottery_type not in ['ssq', 'dlt']:
        current_app.logger.warning("API call: Invalid or missing lottery_type for omitted_balls.")
        return jsonify({'error': 'Invalid or missing lottery_type'}), 400
    
    try:
        offset = int(offset_str)
        if offset < 0:
            raise ValueError("Offset cannot be negative.")
    except (ValueError, TypeError):
        current_app.logger.warning(f"API call: Invalid offset '{offset_str}' for omitted_balls.")
        return jsonify({'error': 'Invalid offset parameter, must be a non-negative integer.'}), 400

    # 1. 获取指定 offset 的遗漏数据 (用于可导航的“遗漏最多”部分)
    omitted_data_for_offset = get_omitted_balls_for_prediction(lottery_type, offset)
    if 'error' in omitted_data_for_offset:
        current_app.logger.error(f"API call: Error getting omitted balls for {lottery_type} with offset {offset}: {omitted_data_for_offset['error']}")
        return jsonify(omitted_data_for_offset), 500
    
    # 2. 获取当前显示期号的开奖号码和匹配的遗漏号码 (这部分现在也受 offset 影响)
    draw_and_matched_data = get_draw_and_matched_omitted_balls_for_offset(lottery_type, offset)
    if 'error' in draw_and_matched_data:
        current_app.logger.error(f"API call: Error getting draw and matched omitted balls for {lottery_type} with offset {offset}: {draw_and_matched_data['error']}")
        return jsonify(draw_and_matched_data), 500

    # 3. 合并两个结果，并调整键名以匹配前端期望
    combined_data = {
        'red_balls': omitted_data_for_offset['red_balls_with_omission'], # 遗漏最多的红球
        'blue_balls': omitted_data_for_offset['blue_balls_with_omission'], # 遗漏最多的蓝球
        'current_omission_issue': omitted_data_for_offset['issue'], # 当前遗漏数据对应的期号
        'max_offset': omitted_data_for_offset['max_offset'], # 最大偏移量
        
        'display_issue': draw_and_matched_data['display_issue'], # Issue for the displayed draw
        'display_draw_date': draw_and_matched_data['display_draw_date'],
        'display_red_balls': draw_and_matched_data['display_red_balls'],
        'display_blue_balls': draw_and_matched_data['display_blue_balls'],
        'matched_omitted_balls': draw_and_matched_data['matched_red_balls'] # This is already in the correct format
    }
    
    current_app.logger.info(f"API call: Successfully returned combined omitted and matched balls for {lottery_type} with offset {offset}.")
    return jsonify(combined_data)


@bp.route('/api/prediction/generate_random', methods=['POST'])
def api_generate_random_numbers():
    data = request.get_json()
    lottery_type = data.get('lottery_type')
    count_str = data.get('count', '1') # 先作为字符串获取
    red_odd_even_ratio_str = data.get('red_odd_even_ratio')
    red_size_ratio_str = data.get('red_size_ratio')

    if not lottery_type or lottery_type not in ['ssq', 'dlt']:
        current_app.logger.warning("API call: Invalid or missing lottery_type for generate_random.")
        return jsonify({'error': 'Invalid or missing lottery_type'}), 400

    try:
        count = int(count_str)
        if count < 1 or count > 100: # 限制生成组数在合理范围
            raise ValueError("Count must be between 1 and 100.")
    except (ValueError, TypeError):
        current_app.logger.warning(f"API call: Invalid count '{count_str}' for generate_random.")
        return jsonify({'error': 'Invalid count parameter, must be an integer between 1 and 100.'}), 400

    # red_odd_even_ratio 和 red_size_ratio 应该作为字符串传递，因为它们是 "odd:even" 格式
    # 移除浮点数转换和范围验证
    red_odd_even_ratio = red_odd_even_ratio_str if red_odd_even_ratio_str else None
    red_size_ratio = red_size_ratio_str if red_size_ratio_str else None

    current_app.logger.info(f"API call: /api/prediction/generate_random for {lottery_type}, count={count}, odd/even={red_odd_even_ratio}, size={red_size_ratio}")

    if lottery_type == 'ssq':
        num_red = 6
        num_blue = 1
    elif lottery_type == 'dlt':
        num_red = 5
        num_blue = 2
    # else 块不再需要，因为 lottery_type 已经在前面验证过了

    generated_numbers = []
    for _ in range(count):
        result = generate_random_balls(
            lottery_type, 
            num_red, 
            num_blue, 
            red_odd_even_ratio=red_odd_even_ratio, 
            red_size_ratio=red_size_ratio
        )
        if result is None: 
            current_app.logger.error(f"API call: Failed to generate random numbers for {lottery_type} due to internal error or invalid ranges.")
            return jsonify({'error': 'Failed to generate random numbers due to internal error or invalid ranges.'}), 500
        
        generated_numbers.append({
            'red_balls': ','.join(map(str, result['red_balls'])),
            'blue_balls': ','.join(map(str, result['blue_balls'])),
            'stats': result['stats']
        })
    
    current_app.logger.info(f"API call: Successfully generated {len(generated_numbers)} random numbers for {lottery_type}.")
    return jsonify({'numbers': generated_numbers})

@bp.route('/api/prediction/generate_predicted', methods=['POST'])
def api_generate_predicted_numbers():
    data = request.get_json()
    lottery_type = data.get('lottery_type')
    count_str = data.get('count', '1')
    red_odd_even_ratio_str = data.get('red_odd_even_ratio')
    red_size_ratio_str = data.get('red_size_ratio')

    if not lottery_type or lottery_type not in ['ssq', 'dlt']:
        current_app.logger.warning("API call: Invalid or missing lottery_type for generate_predicted.")
        return jsonify({'error': 'Invalid or missing lottery_type'}), 400

    try:
        count = int(count_str)
        if count < 1 or count > 100: # 限制生成组数在合理范围
            raise ValueError("Count must be between 1 and 100.")
    except (ValueError, TypeError):
        current_app.logger.warning(f"API call: Invalid count '{count_str}' for generate_predicted.")
        return jsonify({'error': 'Invalid count parameter, must be an integer between 1 and 100.'}), 400

    # red_odd_even_ratio 和 red_size_ratio 应该作为字符串传递，因为它们是 "odd:even" 格式
    # 移除浮点数转换和范围验证
    red_odd_even_ratio = red_odd_even_ratio_str if red_odd_even_ratio_str else None
    red_size_ratio = red_size_ratio_str if red_size_ratio_str else None

    current_app.logger.info(f"API call: /api/prediction/generate_predicted for {lottery_type}, count={count}, odd/even={red_odd_even_ratio}, size={red_size_ratio}")

    if lottery_type == 'ssq':
        num_red = 6
        num_blue = 1
    elif lottery_type == 'dlt':
        num_red = 5
        num_blue = 2
    # else 块不再需要，因为 lottery_type 已经在前面验证过了

    generated_numbers = []
    total_attempts = 0
    total_filtered_count = 0

    for _ in range(count):
        result = generate_predicted_balls(
            lottery_type, 
            red_odd_even_ratio=red_odd_even_ratio, 
            red_size_ratio=red_size_ratio
        )
        if result is None:
            current_app.logger.error(f"API call: Failed to generate predicted numbers for {lottery_type} due to internal error.")
            return jsonify({'error': 'Failed to generate predicted numbers due to internal error.'}), 500
        
        generated_numbers.append({
            'red_balls': ','.join(map(str, result['red_balls'])),
            'blue_balls': ','.join(map(str, result['blue_balls'])),
            'stats': result['stats']
        })
        total_attempts += result['attempts_made']
        total_filtered_count += result['filtered_count']

    total_combinations = calculate_total_lottery_combinations(lottery_type)
    unfiltered_winning_chance = 1 / total_combinations if total_combinations > 0 else 0

    current_app.logger.info(f"API call: Successfully generated {len(generated_numbers)} predicted numbers for {lottery_type}.")
    return jsonify({
        'numbers': generated_numbers,
        'total_combinations': total_combinations,
        'unfiltered_winning_chance': unfiltered_winning_chance,
        'filtered_by_rules_count': total_filtered_count
    })

@bp.route('/api/prediction/generate_complex', methods=['POST'])
def api_generate_complex_prediction():
    data = request.get_json()
    lottery_type = data.get('lottery_type')
    red_count_str = data.get('red_count')
    blue_count_str = data.get('blue_count')
    count_str = data.get('count', '1')

    if not lottery_type or lottery_type not in ['ssq', 'dlt']:
        current_app.logger.warning("API call: Invalid or missing lottery_type for generate_complex.")
        return jsonify({'error': 'Invalid or missing lottery_type'}), 400

    try:
        red_count = int(red_count_str)
        blue_count = int(blue_count_str)
        count = int(count_str)

        if count < 1 or count > 100: # 限制生成组数在合理范围
            raise ValueError("Count must be between 1 and 100.")

        if lottery_type == 'ssq':
            if not (6 <= red_count <= 16) or not (1 <= blue_count <= 16):
                raise ValueError("SSQ red_count must be between 6 and 16, blue_count between 1 and 16.")
        elif lottery_type == 'dlt':
            if not (5 <= red_count <= 16) or not (2 <= blue_count <= 12):
                raise ValueError("DLT red_count must be between 5 and 16, blue_count between 2 and 12.")

    except (ValueError, TypeError) as e:
        current_app.logger.warning(f"API call: Invalid parameters for generate_complex: {e}")
        return jsonify({'error': f'Invalid parameter: {e}'}), 400

    current_app.logger.info(f"API call: /api/prediction/generate_complex for {lottery_type}, red_count={red_count}, blue_count={blue_count}, count={count}")

    # 调用 prediction_engine 中的复式号码生成逻辑
    from prediction_engine import generate_complex_prediction_balls # 局部导入以避免循环依赖

    generated_complex_numbers = []
    for _ in range(count):
        try:
            complex_balls_result = generate_complex_prediction_balls(lottery_type, red_count, blue_count)
            if complex_balls_result is None:
                current_app.logger.error(f"API call: Failed to generate complex numbers for {lottery_type} due to internal error or invalid parameters.")
                # 如果单次生成失败，可以跳过或返回错误，这里选择返回错误
                return jsonify({'error': 'Failed to generate complex numbers due to internal error or invalid parameters.'}), 500
            
            # 计算该组合的投注花费
            cost_details = calculate_combination_cost(red_count, blue_count, lottery_type)

            generated_complex_numbers.append({
                'red_balls': ','.join(map(str, complex_balls_result['red_balls'])),
                'blue_balls': ','.join(map(str, complex_balls_result['blue_balls'])),
                'red_count': red_count,
                'blue_count': blue_count,
                'total_cost': cost_details['total_cost'],
                'stats': complex_balls_result['stats'] # Include the statistics
            })
        except ValueError as e:
            current_app.logger.warning(f"API call: Invalid parameters for complex prediction: {e}")
            return jsonify({'error': str(e)}), 400
        except Exception as e:
            current_app.logger.error(f"API call: Error generating complex prediction for {lottery_type}: {e}")
            return jsonify({'error': 'Internal server error during complex prediction.'}), 500
    
    current_app.logger.info(f"API call: Successfully generated {len(generated_complex_numbers)} complex numbers for {lottery_type}.")
    return jsonify({'numbers': generated_complex_numbers}) # 返回一个列表，因为前端期望 numbers 是一个数组


@bp.route('/prize_check')
def prize_check():
    # 获取最新一期开奖信息，用于页面显示
    latest_ssq = get_latest_draws(SSQDraw, 1)
    latest_dlt = get_latest_draws(DLTDraw, 1)

    ssq_latest_info = None
    if latest_ssq:
        ssq_latest_info = {
            'issue': latest_ssq[0].issue,
            'draw_date': latest_ssq[0].draw_date.strftime('%Y-%m-%d')
        }
    
    dlt_latest_info = None
    if latest_dlt:
        dlt_latest_info = {
            'issue': latest_dlt[0].issue,
            'draw_date': latest_dlt[0].draw_date.strftime('%Y-%m-%d')
        }

    # 获取总期数，用于设置滑块的最大值
    ssq_total_draws = db.session.query(SSQDraw).count()
    dlt_total_draws = db.session.query(DLTDraw).count()

    return render_template('prize_check.html',
                           ssq_latest_info=ssq_latest_info,
                           dlt_latest_info=dlt_latest_info,
                           prize_check_range=CURRENT_SETTINGS.get('prize_check_range', 10),
                           prediction_generated_count=CURRENT_SETTINGS.get('prediction_generated_count', 10),
                           ssq_total_draws=ssq_total_draws,
                           dlt_total_draws=dlt_total_draws,
                           per_bet_price=PER_BET_PRICE,
                           prize_rules=PRIZE_RULES,
                           CURRENT_SETTINGS=CURRENT_SETTINGS # 传递 CURRENT_SETTINGS 到模板
                           )

@bp.route('/api/check_prizes', methods=['POST'])
def api_check_prizes():
    data = request.get_json()
    lottery_type = data.get('lottery_type')
    combinations = data.get('combinations') # [{red_balls: '1,2,3', blue_balls: '1'}, ...]
    
    if not lottery_type or lottery_type not in ['ssq', 'dlt']:
        return jsonify({'error': 'Invalid or missing lottery_type'}), 400

    if not isinstance(combinations, list) or not combinations:
        return jsonify({'error': 'Missing or invalid combinations data'}), 400

    check_range_val = data.get('check_range', CURRENT_SETTINGS.get('prize_check_range', 10))
    try:
        check_range = int(check_range_val)
        if check_range < 0: # 允许0表示所有历史数据
            raise ValueError("Check range cannot be negative.")
    except (ValueError, TypeError):
        check_range = CURRENT_SETTINGS.get('prize_check_range', 10) # Fallback to default if conversion fails
        current_app.logger.warning(f"API call: Invalid check_range '{check_range_val}', falling back to default {check_range}.")

    model_class = SSQDraw if lottery_type == 'ssq' else DLTDraw
    
    # 获取最近 N 期开奖数据，如果 check_range 为 0，则获取所有
    if check_range == 0: # 0 表示全部期数
        recent_draws = model_class.query.order_by(model_class.issue.desc()).all()
    else:
        recent_draws = model_class.query.order_by(model_class.issue.desc()).limit(check_range).all()
    
    # 实际检查的期数
    actual_checked_draws_count = len(recent_draws)

    if not recent_draws:
        return jsonify({'error': '未找到历史开奖数据'}), 404

    all_results = []
    for combo in combinations:
        user_red_balls_str = combo.get('red_balls')
        user_blue_balls_str = combo.get('blue_balls')

        if not user_red_balls_str or not user_blue_balls_str:
            return jsonify({'error': 'Each combination must contain red_balls and blue_balls'}), 400

        try:
            user_red_balls = format_lottery_numbers(user_red_balls_str)
            user_blue_balls = format_lottery_numbers(user_blue_balls_str)

            # 添加更严格的号码验证
            if lottery_type == 'ssq':
                if not (len(user_red_balls) >= 6 and len(user_red_balls) <= 16 and 
                        all(1 <= b <= 33 for b in user_red_balls) and len(set(user_red_balls)) == len(user_red_balls)):
                    raise ValueError("SSQ red balls must be 6-16 unique numbers between 1 and 33.")
                if not (len(user_blue_balls) >= 1 and len(user_blue_balls) <= 16 and 
                        all(1 <= b <= 16 for b in user_blue_balls) and len(set(user_blue_balls)) == len(user_blue_balls)):
                    raise ValueError("SSQ blue balls must be 1-16 unique numbers between 1 and 16.")
            elif lottery_type == 'dlt':
                if not (len(user_red_balls) >= 5 and len(user_red_balls) <= 16 and 
                        all(1 <= b <= 35 for b in user_red_balls) and len(set(user_red_balls)) == len(user_red_balls)):
                    raise ValueError("DLT red balls must be 5-16 unique numbers between 1 and 35.")
                if not (len(user_blue_balls) >= 2 and len(user_blue_balls) <= 12 and 
                        all(1 <= b <= 12 for b in user_blue_balls) and len(set(user_blue_balls)) == len(user_blue_balls)):
                    raise ValueError("DLT blue balls must be 2-12 unique numbers between 1 and 12.")

        except ValueError as e:
            return jsonify({'error': f'Invalid lottery balls format or range: {e}'}), 400
        except Exception as e:
            current_app.logger.error(f"Error processing combination: {combo}. Error: {e}")
            return jsonify({'error': 'Error processing lottery combination.'}), 500

        # 计算该组合的投注花费
        cost_details = calculate_combination_cost(len(user_red_balls), len(user_blue_balls), lottery_type)

        matches = []
        total_winning_bets_for_combo = 0
        total_winning_amount_for_combo = 0.0 # 使用浮点数进行金额计算

        for draw in recent_draws:
            draw_red_balls = draw.get_red_balls_list()
            draw_blue_balls = draw.get_blue_balls_list()

            # 使用新的 calculate_prize_details 获取所有奖项的中奖注数
            prize_details_for_draw = calculate_prize_details(
                user_red_balls, user_blue_balls,
                draw_red_balls, draw_blue_balls,
                lottery_type
            )
            
            if prize_details_for_draw: # 如果有任何奖项中奖
                # 遍历所有中奖的奖项和注数
                for prize_level, prize_count in prize_details_for_draw.items():
                    if prize_count > 0:
                        # 从 PRIZE_RULES 中获取该奖项的固定金额
                        prize_rule = next((p for p in PRIZE_RULES[lottery_type]['prizes'] if p['level'] == prize_level), None)
                        if prize_rule:
                            current_prize_amount_numeric = 0 # 用于计算总金额的数字
                            prize_amount_display = "" # 用于前端显示的字符串

                            if prize_rule['amount'] == '浮动':
                                # 根据实际开奖数据获取浮动奖金
                                if prize_level == '一等奖':
                                    current_prize_amount_numeric = draw.first_prize_amount
                                elif prize_level == '二等奖':
                                    current_prize_amount_numeric = draw.second_prize_amount
                                # 大乐透的浮动奖金也需要类似处理
                                elif lottery_type == 'dlt':
                                    if prize_level == '一等奖':
                                        current_prize_amount_numeric = draw.first_prize_amount
                                    elif prize_level == '二等奖':
                                        current_prize_amount_numeric = draw.second_prize_amount
                                prize_amount_display = f"{current_prize_amount_numeric:,.0f}" # 格式化为字符串
                            else:
                                current_prize_amount_numeric = prize_rule['amount']
                                prize_amount_display = f"{current_prize_amount_numeric:,.0f}" # 固定奖金也格式化

                            # 累加总中奖注数和总中奖金额
                            total_winning_bets_for_combo += prize_count
                            total_winning_amount_for_combo += prize_count * current_prize_amount_numeric
                            
                            matches.append({
                                'issue': draw.issue,
                                'draw_date': draw.draw_date.strftime('%Y-%m-%d'),
                                'prize_level': prize_level,
                                'prize_count': prize_count, # 中奖注数
                                'prize_amount': prize_amount_display # 用于显示的格式化字符串
                            })
        
        # 计算总花费 (单次投注花费 * 实际检查的期数)
        total_cost_for_range = cost_details['total_cost'] * actual_checked_draws_count
        
        # 计算回报率
        return_rate = 0.0
        if total_cost_for_range > 0:
            return_rate = (total_winning_amount_for_combo / total_cost_for_range) * 100
        
        all_results.append({
            'input_red_balls': user_red_balls_str,
            'input_blue_balls': user_blue_balls_str,
            'total_bets_per_draw': cost_details['total_bets'], # 单次投注总注数
            'cost_per_draw': cost_details['total_cost'], # 单次投注花费
            'total_winning_bets': total_winning_bets_for_combo, # 总中奖注数
            'total_winning_amount': total_winning_amount_for_combo, # 总中奖金额
            'actual_checked_draws_count': actual_checked_draws_count, # 实际检查的期数
            'total_cost_for_range': total_cost_for_range, # 在此范围内的总花费
            'return_rate': round(return_rate, 1), # 新增：回报率，保留1位小数
            'matches': matches
        })
    
    return jsonify({'results': all_results})

@bp.route('/api/prediction/check_generated_rules', methods=['POST']) # 新增API路由，用于检查生成号码的规则
def api_check_generated_rules():
    data = request.get_json()
    lottery_type = data.get('lottery_type')
    red_balls_str = data.get('red_balls')
    blue_balls_str = data.get('blue_balls')

    current_app.logger.info(f"API call: /api/prediction/check_generated_rules for {lottery_type}. Red: {red_balls_str}, Blue: {blue_balls_str}")

    if not lottery_type or lottery_type not in ['ssq', 'dlt']:
        return jsonify({'error': 'Invalid or missing lottery_type'}), 400
    
    if not red_balls_str or not blue_balls_str:
        return jsonify({'error': 'Missing red_balls or blue_balls data'}), 400

    try:
        red_balls = format_lottery_numbers(red_balls_str)
        blue_balls = format_lottery_numbers(blue_balls_str)

        # 添加更严格的号码验证
        if lottery_type == 'ssq':
            # 允许复式号码的范围
            if not (len(red_balls) >= 6 and len(red_balls) <= 16 and all(1 <= b <= 33 for b in red_balls) and len(set(red_balls)) == len(red_balls)):
                raise ValueError("SSQ red balls must be 6-16 unique numbers between 1 and 33.")
            if not (len(blue_balls) >= 1 and len(blue_balls) <= 16 and all(1 <= b <= 16 for b in blue_balls) and len(set(blue_balls)) == len(blue_balls)):
                raise ValueError("SSQ blue balls must be 1-16 unique numbers between 1 and 16.")
        elif lottery_type == 'dlt':
            # 允许复式号码的范围
            if not (len(red_balls) >= 5 and len(red_balls) <= 16 and all(1 <= b <= 35 for b in red_balls) and len(set(red_balls)) == len(red_balls)):
                raise ValueError("DLT red balls must be 5-16 unique numbers between 1 and 35.")
            if not (len(blue_balls) >= 2 and len(blue_balls) <= 12 and all(1 <= b <= 12 for b in blue_balls) and len(set(blue_balls)) == len(blue_balls)):
                raise ValueError("DLT blue balls must be 2-12 unique numbers between 1 and 12.")

    except ValueError as e:
        return jsonify({'error': f'Invalid lottery balls format or range: {e}'}), 400
    except Exception as e:
        current_app.logger.error(f"Error processing balls for rule check: Red: {red_balls_str}, Blue: {blue_balls_str}. Error: {e}")
        return jsonify({'error': 'Error processing lottery balls for rule check.'}), 500

    if lottery_type == 'ssq':
        results = check_ssq_rules_for_balls(red_balls, blue_balls)
    elif lottery_type == 'dlt':
        results = check_dlt_rules_for_balls(red_balls, blue_balls) # DLT uses red_balls for front_balls
    # else 块不再需要，因为 lottery_type 已经在前面验证过了
    
    current_app.logger.info(f"API call: Successfully checked generated rules for {lottery_type}.")
    return jsonify(results)


# @bp.route('/api/fun_game', methods=['POST'])
# def api_fun_game():
#     data = request.get_json()
#     lottery_type = data.get('lottery_type')
#     combinations = data.get('combinations') # [{red_balls: '1,2,3', blue_balls: '1'}, ...]

#     if not lottery_type or not combinations:
#         return jsonify({'error': '缺少彩票类型或号码组合'}), 400

#     # 趣味游戏只处理第一个号码组合
#     first_combo = combinations[0]
#     user_red_balls_str = first_combo.get('red_balls')
#     user_blue_balls_str = first_combo.get('blue_balls')

#     user_red_balls = format_lottery_numbers(user_red_balls_str)
#     user_blue_balls = format_lottery_numbers(user_blue_balls_str)

#     max_simulations_val = data.get('max_simulations', CURRENT_SETTINGS.get('fun_game_max_simulations', 1000000))
#     try:
#         max_simulations = int(max_simulations_val)
#     except (ValueError, TypeError):
#         max_simulations = CURRENT_SETTINGS.get('fun_game_max_simulations', 1000000) # Fallback to default

#     # 调用 simulate_fun_game，只传递一个组合
#     sim_result = simulate_fun_game(user_red_balls, user_blue_balls, lottery_type, max_simulations)
    
#     # 返回结果，因为只模拟了一个组合，所以直接返回其结果
#     return jsonify({'results': [sim_result]})


@bp.route('/news/<int:news_id>')
def news_detail(news_id):
    if news_id < 1:
        flash('无效的新闻ID。', 'danger')
        return redirect(url_for('routes.index'))
    news_item = News.query.get_or_404(news_id)
    if not news_item.is_public and not session.get('logged_in_admin'):
        flash('该文章不公开或您没有权限访问。', 'danger')
        return redirect(url_for('routes.index'))

    prev_news = News.query.filter(News.id < news_id, News.is_public == True).order_by(News.id.desc()).first()
    next_news = News.query.filter(News.id > news_id, News.is_public == True).order_by(News.id.asc()).first()

    return render_template('news_detail.html', news_item=news_item, prev_news=prev_news, next_news=next_news)

# 原有的 /api/check_rules 保持不变，用于检查历史期号
@bp.route('/api/check_rules', methods=['GET']) # 保持GET请求，用于检查历史期号
def api_check_rules_historical(): # 重命名以避免与新的POST路由冲突
    lottery_type = request.args.get('lottery_type')
    issue_str = request.args.get('issue')

    if not lottery_type or lottery_type not in ['ssq', 'dlt']:
        return jsonify({'error': 'Invalid or missing lottery_type'}), 400
    
    if not issue_str:
        return jsonify({'error': 'Missing issue'}), 400

    try:
        issue = int(issue_str)
        if issue < 1:
            raise ValueError("Issue number must be a positive integer.")
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid issue parameter, must be a positive integer.'}), 400

    results = check_lottery_rules(lottery_type, issue)

    if 'error' in results:
        if results.get('error') in ['SSQDraw not found', 'DLTDraw not found']:
            return jsonify(results), 404
        return jsonify(results), 500

    return jsonify(results)

# 创建一个全局字典来存储后台任务的状态和结果
# 格式: { 'task_id': {'status': 'running', 'progress': 0, 'result': None} }
# 注意：在生产环境中，最好使用 Redis 或数据库来代替内存字典，以支持多进程部署
tasks = {}

def run_simulation_in_background(task_id, user_red_balls, user_blue_balls, lottery_type, app):
    """这个函数将在一个单独的线程中运行"""
    with app.app_context(): # 在线程中手动创建应用上下文
        try:
            # 调用核心计算函数，并传入 task_id 以便更新进度
            sim_result = simulate_fun_game(
                user_red_balls, 
                user_blue_balls, 
                lottery_type, 
                task_id=task_id, # <--- 传入 task_id
                tasks_dict=tasks # <--- 传入任务字典
            )
            # 任务完成后，更新状态和结果
            tasks[task_id]['status'] = 'completed'
            tasks[task_id]['result'] = sim_result
            tasks[task_id]['progress'] = 100
        except Exception as e:
            app.logger.error(f"Task {task_id} failed: {e}") # 使用 app.logger
            tasks[task_id]['status'] = 'failed'
            tasks[task_id]['result'] = {'error': '任务执行失败，请查看服务器日志。'}

@bp.route('/api/fun_game/start', methods=['POST'])
def api_fun_game_start():
    data = request.get_json()
    lottery_type = data.get('lottery_type')
    combinations = data.get('combinations')

    if not lottery_type or lottery_type not in ['ssq', 'dlt']:
        return jsonify({'error': 'Invalid or missing lottery_type'}), 400

    if not isinstance(combinations, list) or not combinations:
        return jsonify({'error': 'Missing or invalid combinations data'}), 400

    first_combo = combinations[0]
    user_red_balls_str = first_combo.get('red_balls')
    user_blue_balls_str = first_combo.get('blue_balls')

    if not user_red_balls_str or not user_blue_balls_str:
        return jsonify({'error': 'The first combination must contain red_balls and blue_balls'}), 400

    try:
        user_red_balls = format_lottery_numbers(user_red_balls_str)
        user_blue_balls = format_lottery_numbers(user_blue_balls_str)

        # 添加更严格的号码验证 (趣味游戏通常是单式投注，所以数量是固定的)
        if lottery_type == 'ssq':
            # 允许用户输入任意数量的红球和蓝球，只要它们在有效范围内且唯一
            if not (len(user_red_balls) >= 1 and all(1 <= b <= 33 for b in user_red_balls) and len(set(user_red_balls)) == len(user_red_balls)):
                raise ValueError("SSQ red balls must be unique numbers between 1 and 33.")
            if not (len(user_blue_balls) >= 1 and all(1 <= b <= 16 for b in user_blue_balls) and len(set(user_blue_balls)) == len(user_blue_balls)):
                raise ValueError("SSQ blue balls must be unique numbers between 1 and 16.")
        elif lottery_type == 'dlt':
            if not (len(user_red_balls) >= 1 and all(1 <= b <= 35 for b in user_red_balls) and len(set(user_red_balls)) == len(user_red_balls)):
                raise ValueError("DLT red balls must be unique numbers between 1 and 35.")
            if not (len(user_blue_balls) >= 1 and all(1 <= b <= 12 for b in user_blue_balls) and len(set(user_blue_balls)) == len(user_blue_balls)):
                raise ValueError("DLT blue balls must be unique numbers between 1 and 12.")

    except ValueError as e:
        return jsonify({'error': f'Invalid lottery balls format or range in combination: {e}'}), 400
    except Exception as e:
        current_app.logger.error(f"Error processing combination for fun game: Red: {user_red_balls_str}, Blue: {user_blue_balls_str}. Error: {e}")
        return jsonify({'error': 'Error processing lottery combination for fun game.'}), 500

    # max_simulations 不再需要，因为 simulate_fun_game 会根据配置自行计算
    # max_simulations = int(data.get('max_simulations', CURRENT_SETTINGS.get('fun_game_max_simulations')))

    # 创建一个唯一的任务ID
    task_id = str(uuid.uuid4())
    
    # 初始化任务状态
    tasks[task_id] = {'status': 'pending', 'progress': 0, 'result': None}

    # 创建并启动后台线程
    thread = threading.Thread(
        target=run_simulation_in_background, 
        args=(task_id, user_red_balls, user_blue_balls, lottery_type, current_app._get_current_object()) # 传递 app 实例
    )
    thread.daemon = True # 设置为守护线程，主程序退出时线程也退出
    thread.start()

    # 立即返回任务ID
    return jsonify({'task_id': task_id})


@bp.route('/api/fun_game/status/<task_id>', methods=['GET'])
def api_fun_game_status(task_id):
    task = tasks.get(task_id)
    if not task:
        return jsonify({'error': '未找到该任务'}), 404
    
    return jsonify(task)


# New route for Intelligent Analysis page
@bp.route('/intelligent_analysis')
def intelligent_analysis():
    return render_template('intelligent_analysis.html')

# New API endpoint to get draw data for clipboard
@bp.route('/api/get_draw_data_for_clipboard', methods=['GET'])
def get_draw_data_for_clipboard():
    lottery_type = request.args.get('lottery_type')
    num_periods_str = request.args.get('num_periods')

    if not lottery_type or lottery_type not in ['ssq', 'dlt']:
        return jsonify({'error': 'Invalid or missing lottery_type'}), 400

    if not num_periods_str:
        return jsonify({'error': 'Missing num_periods'}), 400

    try:
        if num_periods_str == 'all':
            num_periods = 0 # 0 will indicate all draws
        else:
            num_periods = int(num_periods_str)
            if num_periods <= 0:
                raise ValueError("Number of periods must be a positive integer or 'all'.")
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid num_periods parameter, must be a positive integer or "all".'}), 400

    model_class = SSQDraw if lottery_type == 'ssq' else DLTDraw
    
    # Fetch draws
    if num_periods == 0: # All draws
        draws = model_class.query.order_by(model_class.issue.desc()).all()
    else:
        draws = model_class.query.order_by(model_class.issue.desc()).limit(num_periods).all()

    if not draws:
        return jsonify({'error': 'No draw data found for the selected type and periods.'}), 404

    formatted_data = []
    for draw in draws:
        red_balls = ','.join(map(str, draw.get_red_balls_list()))
        blue_balls = ','.join(map(str, draw.get_blue_balls_list()))
        formatted_data.append(f"期号: {draw.issue}, 开奖日期: {draw.draw_date.strftime('%Y-%m-%d')}, 红球: {red_balls}, 蓝球: {blue_balls}")
    
    return jsonify({'data': '\n'.join(formatted_data)}) # Use \n for newlines in JSON string