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
from smart_filter_engine import generate_smart_filtered_numbers, update_smart_filter_stats, check_draw_against_smart_filter_rankings, calculate_smart_filter_stats_for_draw # 导入智能筛选引擎

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
                           get_consecutive_groups=get_consecutive_groups # Pass the function to the template
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
    # 获取最新5期开奖号码用于显示（固定5期）
    num_latest_draws = 5
    
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
                           settings=CURRENT_SETTINGS, # 传递设置到模板
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

    # 1. 获取指定 offset 的遗漏数据 (用于可导航的"遗漏最多"部分)
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

@bp.route('/api/prize_check/next_prediction', methods=['GET'])
def api_prize_check_next_prediction():
    """
    获取指定彩票类型的"下期"开奖号码。
    当查看第 N 期时，"下期号码"显示第 N-1 期（即下一期）的实际开奖号码。
    用于对奖中心页面的"下期号码"高亮显示。
    """
    lottery_type = request.args.get('lottery_type')
    offset_str = request.args.get('offset', '0')

    if not lottery_type or lottery_type not in ['ssq', 'dlt']:
        return jsonify({'error': 'Invalid or missing lottery_type'}), 400

    try:
        offset = int(offset_str)
        if offset < 0:
            raise ValueError("Offset cannot be negative.")
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid offset parameter, must be a non-negative integer.'}), 400

    model_class = SSQDraw if lottery_type == 'ssq' else DLTDraw

    all_draws = model_class.query.order_by(model_class.issue.desc()).all()
    if not all_draws:
        return jsonify({'error': 'No historical data available.'}), 404

    max_offset = len(all_draws) - 1
    if offset > max_offset:
        offset = max_offset

    # 获取当前显示期数的开奖数据
    current_draw = all_draws[offset]

    # "下期号码" = 下一期（offset-1）的实际开奖号码
    # 数据按期号降序排列，offset=0 是最新一期
    # 所以 offset-1 是下一期（更晚一期，更接近最新），offset+1 是上一期（更早一期）
    # 当 offset=0（最新一期）时，没有"下一期"数据
    next_offset = offset - 1
    if next_offset < 0:
        # 没有下一期数据
        return jsonify({
            'issue': current_draw.issue,
            'draw_date': current_draw.draw_date.strftime('%Y-%m-%d'),
            'next_red_balls': [],
            'next_blue_balls': [],
            'is_latest': True,  # 没有下一期，视为"最新"
            'has_next': False,
            'max_offset': max_offset,
            'current_offset': offset
        })

    next_draw = all_draws[next_offset]
    next_red_balls = next_draw.get_red_balls_list()
    next_blue_balls = next_draw.get_blue_balls_list()

    # 判断是否是最新一期（offset=0），最新一期时没有"下一期"数据
    is_latest = (offset == 0)

    return jsonify({
        'issue': current_draw.issue,
        'draw_date': current_draw.draw_date.strftime('%Y-%m-%d'),
        'next_issue': next_draw.issue,
        'next_draw_date': next_draw.draw_date.strftime('%Y-%m-%d'),
        'next_red_balls': next_red_balls,
        'next_blue_balls': next_blue_balls,
        'is_latest': is_latest,
        'has_next': True,
        'max_offset': max_offset,
        'current_offset': offset
    })


@bp.route('/api/prize_check/latest_draws', methods=['GET'])
def api_prize_check_latest_draws():
    """
    获取指定彩票类型的最新开奖号码及每个号码的遗漏期数。
    支持 offset 参数用于前一期/后一期导航。
    """
    lottery_type = request.args.get('lottery_type')
    offset_str = request.args.get('offset', '0')

    if not lottery_type or lottery_type not in ['ssq', 'dlt']:
        return jsonify({'error': 'Invalid or missing lottery_type'}), 400

    try:
        offset = int(offset_str)
        if offset < 0:
            raise ValueError("Offset cannot be negative.")
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid offset parameter, must be a non-negative integer.'}), 400

    model_class = SSQDraw if lottery_type == 'ssq' else DLTDraw
    red_ball_range = 33 if lottery_type == 'ssq' else 35
    blue_ball_range = 16 if lottery_type == 'ssq' else 12

    all_draws = model_class.query.order_by(model_class.issue.desc()).all()
    if not all_draws:
        return jsonify({'error': 'No historical data available.'}), 404

    max_offset = len(all_draws) - 1
    if offset > max_offset:
        offset = max_offset

    # 获取当前显示期数的开奖数据
    current_draw = all_draws[offset]
    display_red_balls = current_draw.get_red_balls_list()
    display_blue_balls = current_draw.get_blue_balls_list()

    # 计算遗漏数据（从当前期往后计算）
    draws_for_omission = all_draws[offset:]

    # 计算红球遗漏
    red_stats_list, _ = calculate_frequency_and_omissions_for_balls(draws_for_omission, red_ball_range, 'red')
    red_omissions = {item['ball']: item['current_omission'] for item in red_stats_list}

    # 计算蓝球遗漏
    blue_stats_list, _ = calculate_frequency_and_omissions_for_balls(draws_for_omission, blue_ball_range, 'blue')
    blue_omissions = {item['ball']: item['current_omission'] for item in blue_stats_list}

    # 为当前开奖号码构建带遗漏的数据
    red_balls_with_omission = []
    for ball in display_red_balls:
        red_balls_with_omission.append({
            'ball': ball,
            'omission': red_omissions.get(ball, 0)
        })

    blue_balls_with_omission = []
    for ball in display_blue_balls:
        blue_balls_with_omission.append({
            'ball': ball,
            'omission': blue_omissions.get(ball, 0)
        })

    # 构建所有号码的遗漏数据（用于号码选择器显示）
    all_red_omissions = []
    for ball_num in range(1, red_ball_range + 1):
        all_red_omissions.append({
            'ball': ball_num,
            'omission': red_omissions.get(ball_num, 0)
        })

    all_blue_omissions = []
    for ball_num in range(1, blue_ball_range + 1):
        all_blue_omissions.append({
            'ball': ball_num,
            'omission': blue_omissions.get(ball_num, 0)
        })

    return jsonify({
        'issue': current_draw.issue,
        'draw_date': current_draw.draw_date.strftime('%Y-%m-%d'),
        'red_balls': display_red_balls,
        'blue_balls': display_blue_balls,
        'red_balls_with_omission': red_balls_with_omission,
        'blue_balls_with_omission': blue_balls_with_omission,
        'all_red_omissions': all_red_omissions,
        'all_blue_omissions': all_blue_omissions,
        'max_offset': max_offset,
        'current_offset': offset
    })


@bp.route('/api/check_prizes', methods=['POST'])
def api_check_prizes():
    data = request.get_json()
    lottery_type = data.get('lottery_type')
    combinations = data.get('combinations') # [{red_balls: '1,2,3', blue_balls: '1'}, ...]
    
    if not lottery_type or lottery_type not in ['ssq', 'dlt']:
        return jsonify({'error': 'Invalid or missing lottery_type'}), 400

    if not isinstance(combinations, list) or not combinations:
        return jsonify({'error': 'Missing or invalid combinations data'}), 400

    # 获取追加投注选项（仅大乐透有效）
    is_addition = data.get('is_addition', False)

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

    # 获取最新一期用于判断福运奖状态和奖池金额
    latest_draw = recent_draws[0] if recent_draws else None
    pool_amount = latest_draw.prize_pool if latest_draw else None
    
    # 判断福运奖是否启用（双色球）
    fuyun_prize_active = False
    if lottery_type == 'ssq' and latest_draw:
        fuyun_prize_active = latest_draw.fuyun_prize_active if hasattr(latest_draw, 'fuyun_prize_active') else False

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

        # 计算该组合的投注花费（支持追加投注）
        cost_details = calculate_combination_cost(len(user_red_balls), len(user_blue_balls), lottery_type, is_addition)

        matches = []
        total_winning_bets_for_combo = 0
        total_winning_amount_for_combo = 0.0 # 使用浮点数进行金额计算

        for draw in recent_draws:
            draw_red_balls = draw.get_red_balls_list()
            draw_blue_balls = draw.get_blue_balls_list()

            # 获取该期奖池金额（大乐透用于固定奖联动判断）
            draw_pool_amount = draw.prize_pool if hasattr(draw, 'prize_pool') else pool_amount
            
            # 获取该期福运奖状态（双色球）
            draw_fuyun_active = False
            if lottery_type == 'ssq':
                draw_fuyun_active = draw.fuyun_prize_active if hasattr(draw, 'fuyun_prize_active') else fuyun_prize_active

            # 使用新的 calculate_prize_details 获取所有奖项的中奖注数
            prize_details_for_draw = calculate_prize_details(
                user_red_balls, user_blue_balls,
                draw_red_balls, draw_blue_balls,
                lottery_type,
                pool_amount=draw_pool_amount,
                is_addition=is_addition,
                fuyun_prize_active=draw_fuyun_active
            )
            
            if prize_details_for_draw: # 如果有任何奖项中奖
                # 遍历所有中奖的奖项和注数
                for prize_level, info in prize_details_for_draw.items():
                    prize_count = info['count']
                    if prize_count > 0:
                        # 获取该奖项的详细信息
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
                                # 追加投注额外增加
                                if is_addition and lottery_type == 'dlt':
                                    add_amount = prize_rule.get('max_single_add', 0)
                                    if current_prize_amount_numeric:
                                        current_prize_amount_numeric = min(current_prize_amount_numeric + add_amount, add_amount)
                                prize_amount_display = f"{current_prize_amount_numeric:,.0f}" if current_prize_amount_numeric else "浮动"
                            else:
                                current_prize_amount_numeric = info['amount'] / prize_count if prize_count > 0 else 0
                                prize_amount_display = f"{current_prize_amount_numeric:,.0f}"

                            # 累加总中奖注数和总中奖金额
                            total_winning_bets_for_combo += prize_count
                            total_winning_amount_for_combo += prize_count * current_prize_amount_numeric
                            
                            matches.append({
                                'issue': draw.issue,
                                'draw_date': draw.draw_date.strftime('%Y-%m-%d'),
                                'prize_level': prize_level,
                                'prize_count': prize_count, # 中奖注数
                                'prize_amount': prize_amount_display, # 用于显示的格式化字符串
                                'draw_red_balls': draw.get_red_balls_list(),
                                'draw_blue_balls': draw.get_blue_balls_list()
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
            'base_cost_per_draw': cost_details['base_cost'], # 基础投注花费
            'add_cost_per_draw': cost_details.get('add_cost', 0), # 追加投注花费
            'total_winning_bets': total_winning_bets_for_combo, # 总中奖注数
            'total_winning_amount': total_winning_amount_for_combo, # 总中奖金额
            'actual_checked_draws_count': actual_checked_draws_count, # 实际检查的期数
            'total_cost_for_range': total_cost_for_range, # 在此范围内的总花费
            'return_rate': round(return_rate, 1), # 新增：回报率，保留1位小数
            'matches': matches,
            'is_addition': is_addition, # 返回追加投注状态
            'fuyun_prize_active': fuyun_prize_active  # 返回福运奖状态
        })
    
    return jsonify({'results': all_results, 'fuyun_prize_active': fuyun_prize_active, 'is_addition': is_addition})

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


# ==================== 蓝球/后区遗漏 API ====================

@bp.route('/api/prediction/latest_blue_stats', methods=['GET'])
def api_latest_blue_stats():
    """
    获取上期蓝球/后区的属性信息，用于计算默认值
    返回：
    - last_blue_balls: 上期蓝球号码列表
    - last_blue_properties: 每个蓝球的属性（大小、奇偶）
    - recommended_balls: 根据相反属性推荐的号码列表
    - all_blue_omissions: 所有蓝球的遗漏数据
    - top_8_omissions: 遗漏最多的前8个蓝球
    - recent_10_freq: 最近10期出现最多的号码及其次数（SSQ返回前2，DLT返回前3）
    """
    lottery_type = request.args.get('lottery_type')
    if not lottery_type or lottery_type not in ['ssq', 'dlt']:
        return jsonify({'error': 'Invalid or missing lottery_type'}), 400

    model_class = SSQDraw if lottery_type == 'ssq' else DLTDraw
    blue_range = 16 if lottery_type == 'ssq' else 12
    
    # 获取上期开奖数据
    latest_draw = model_class.query.order_by(model_class.issue.desc()).first()
    if not latest_draw:
        # 如果没有历史数据，返回空推荐
        all_blue_omissions = [{'ball': b, 'omission': 0} for b in range(1, blue_range + 1)]
        return jsonify({
            'last_blue_balls': [],
            'last_blue_properties': {},
            'recommended_balls': [],
            'all_blue_omissions': all_blue_omissions,
            'top_8_omissions': all_blue_omissions[:8],
            'last_issue': None,
            'has_data': False,
            'recent_10_freq': []
        })
    
    last_blue_balls = latest_draw.get_blue_balls_list()
    
    # 计算所有蓝球的遗漏数据
    all_draws = model_class.query.order_by(model_class.issue.desc()).all()
    from utils import calculate_frequency_and_omissions_for_balls
    blue_stats_list, _ = calculate_frequency_and_omissions_for_balls(all_draws, blue_range, 'blue')
    blue_omissions = {item['ball']: item['current_omission'] for item in blue_stats_list}
    
    # 构建所有蓝球的遗漏数据（含频率百分比）
    all_blue_omissions = []
    for b in range(1, blue_range + 1):
        # 从 blue_stats_list 中查找对应的频率百分比
        freq_pct = 0
        for item in blue_stats_list:
            if item['ball'] == b:
                freq_pct = item['frequency_percentage']
                break
        all_blue_omissions.append({
            'ball': b,
            'omission': blue_omissions.get(b, 0),
            'frequency_percentage': freq_pct
        })
    
    # 遗漏最多的前8个（已包含 frequency_percentage）
    sorted_by_omission = sorted(all_blue_omissions, key=lambda x: x['omission'], reverse=True)
    top_8_omissions = sorted_by_omission[:8]
    
    # === 计算最近10期的蓝球出现频率 ===
    recent_10_draws = model_class.query.order_by(model_class.issue.desc()).limit(10).all()
    from collections import Counter
    recent_blue_counter = Counter()
    for d in recent_10_draws:
        recent_blue_counter.update(d.get_blue_balls_list())
    # SSQ取前2，DLT取前3，按照出现次数降序排列
    recent_10_freq = []
    # 确定要取的数量
    top_n = 2 if lottery_type == 'ssq' else 3
    for ball_num, count in recent_blue_counter.most_common(top_n):
        recent_10_freq.append({
            'ball': ball_num,
            'count': count
        })
    # 按号码排序以便显示
    recent_10_freq.sort(key=lambda x: x['ball'])
    
    # 判断每个蓝球的大小和奇偶属性
    def get_blue_properties(ball_num, lt):
        props = {}
        props['odd'] = ball_num % 2 == 1
        props['even'] = ball_num % 2 == 0
        if lt == 'ssq':
            props['big'] = ball_num >= 9
            props['small'] = ball_num <= 8
        else:  # dlt
            props['big'] = ball_num >= 7
            props['small'] = ball_num <= 6
        return props
    
    # 上期蓝球的属性
    last_blue_properties = {}
    for b in last_blue_balls:
        last_blue_properties[str(b)] = get_blue_properties(b, lottery_type)
    
    # 计算推荐号码（遗漏期数小于等于5期的号码作为默认值）
    recommended_balls = [item['ball'] for item in all_blue_omissions if item['omission'] <= 5]
    # 如果没有遗漏≤5期的号码（极端情况），取遗漏最小的1个作为保底
    if not recommended_balls:
        sorted_by_omission_asc = sorted(all_blue_omissions, key=lambda x: x['omission'])
        recommended_balls = [sorted_by_omission_asc[0]['ball']]
    
    return jsonify({
        'last_blue_balls': last_blue_balls,
        'last_blue_properties': last_blue_properties,
        'recommended_balls': recommended_balls,
        'all_blue_omissions': all_blue_omissions,
        'top_8_omissions': top_8_omissions,
        'recent_10_freq': recent_10_freq,
        'last_issue': latest_draw.issue,
        'has_data': True
    })


# ==================== 历史页面智能筛选核查 API ====================

@bp.route('/api/history/smart_filter_check', methods=['GET'])
def api_history_smart_filter_check():
    """
    检查一期开奖号码是否符合智能筛选规则排名
    前区红球用排名前2位的规则核查，后区蓝球用排名前5位的规则核查
    """
    lottery_type = request.args.get('lottery_type', 'ssq')
    issue = request.args.get('issue')
    
    if lottery_type not in ['ssq', 'dlt']:
        return jsonify({'error': 'Invalid lottery_type'}), 400
    
    if not issue:
        return jsonify({'error': 'Missing issue parameter'}), 400
    
    model_class = SSQDraw if lottery_type == 'ssq' else DLTDraw
    draw = model_class.query.filter_by(issue=issue).first()
    
    if not draw:
        return jsonify({'error': 'Draw not found'}), 404
    
    result = check_draw_against_smart_filter_rankings(lottery_type, draw, lookback_period=100)
    
    return jsonify(result)


# ==================== 智能筛选 API ====================

@bp.route('/api/prediction/smart_filter_check', methods=['POST'])
def api_smart_filter_check():
    """
    检查指定号码组合是否符合当前智能筛选规则
    返回每个规则的检查结果
    注意：与生成过程不同，检查时不忽略任何规则，所有用户选择的规则都会严格检查
    """
    data = request.get_json()
    lottery_type = data.get('lottery_type')
    red_balls_str = data.get('red_balls')
    blue_balls_str = data.get('blue_balls')
    options = data.get('options', {})

    if not lottery_type or lottery_type not in ['ssq', 'dlt']:
        return jsonify({'error': 'Invalid or missing lottery_type'}), 400

    if not red_balls_str or not blue_balls_str:
        return jsonify({'error': 'Missing red_balls or blue_balls data'}), 400

    try:
        red_balls = format_lottery_numbers(red_balls_str)
        blue_balls = format_lottery_numbers(blue_balls_str)
    except Exception as e:
        return jsonify({'error': f'Invalid lottery balls format: {e}'}), 400

    # 获取遗漏数据用于检查
    from smart_filter_engine import get_omission_data, get_latest_draws_for_smart
    all_draws = get_latest_draws_for_smart(lottery_type, 200)
    red_omission, blue_omission = get_omission_data(lottery_type, all_draws)

    from smart_filter_engine import (
        check_ssq_red_zone_distribution, check_dlt_front_zone_distribution,
        check_consecutive_balls, check_repeat_with_previous,
        check_omission_rule_ssq, check_omission_rule_dlt,
        check_odd_even_ratio, check_max_span, check_sum_range,
        check_same_tail, check_neighbor_numbers, check_ac_value,
        check_ssq_blue_omission, check_dlt_blue_omission,
        check_dlt_blue_odd_even, check_dlt_blue_size
    )

    def _run_single_check():
        """执行单次规则检查，返回(是否全部通过, 结果字典)"""
        # 注意：检查时不忽略任何规则，所有用户选择的规则都会严格检查
        # 生成号码时的随机忽略机制保留在 smart_filter_engine.py 中
        res = {}

        # 1. 分区原则
        zr = options.get('zone_ratio', [])
        if isinstance(zr, str): zr = [zr]
        if zr and 'disabled' not in zr:
            if lottery_type == 'ssq':
                passed = False; actual = ""
                for ratio in zr:
                    p, a = check_ssq_red_zone_distribution(red_balls, ratio)
                    if p: passed = True; actual = a; break
                    actual = a
                res['分区原则'] = {'passed': passed, 'message': f'通过, 分布: {actual}' if passed else f'实际分布: {actual}, 期望: {",".join(zr)}'}
            else:
                passed, actual = check_dlt_front_zone_distribution(red_balls, zr)
                res['分区原则'] = {'passed': passed, 'message': f'通过, 分布: {actual}' if passed else f'实际分布: {actual}, 期望: {",".join(zr)}'}

        # 2. 连号原则
        co = options.get('consecutive', [])
        if isinstance(co, str): co = [co]
        if co and 'disabled' not in co:
            passed = False
            for opt in co:
                if opt == 'no_consecutive':
                    p, cnt, _ = check_consecutive_balls(red_balls, max_groups=0, max_length=0)
                    if p and cnt == 0: passed = True; break
                elif opt == '1_group_2':
                    p, cnt, groups = check_consecutive_balls(red_balls, max_groups=1, max_length=2)
                    if p and cnt == 1:
                        for g in groups:
                            if len(g) == 2: passed = True; break
                    if passed: break
                elif opt == '2_group_2':
                    p, cnt, groups = check_consecutive_balls(red_balls, max_groups=2, max_length=2)
                    if p and cnt == 2 and all(len(g) == 2 for g in groups): passed = True; break
                elif opt == '1_group_3':
                    p, cnt, groups = check_consecutive_balls(red_balls, max_groups=1, max_length=3)
                    if p and cnt == 1:
                        for g in groups:
                            if len(g) == 3: passed = True; break
                    if passed: break
            res['连号原则'] = {'passed': passed, 'message': '通过' if passed else '不符合连号规则'}

        # 3. 与上期重号
        ro = options.get('repeat', [])
        if isinstance(ro, str): ro = [ro]
        if ro and 'disabled' not in ro:
            passed = False; cnt = 0
            for opt in ro:
                if opt == '1': p, cnt = check_repeat_with_previous(red_balls, lottery_type, 1, 1)
                elif opt == '2': p, cnt = check_repeat_with_previous(red_balls, lottery_type, 2, 2)
                elif opt == '1_or_2': p, cnt = check_repeat_with_previous(red_balls, lottery_type, 1, 2)
                elif opt == '0': p, cnt = check_repeat_with_previous(red_balls, lottery_type, 0, 0)
                else: continue
                if p: passed = True; break
            res['与上期重号'] = {'passed': passed, 'message': f'通过, 重号: {cnt}' if passed else f'重号数量: {cnt}'}

        # 4. 遗漏号原则
        op = options.get('omission_pattern', [])
        if isinstance(op, str): op = [op]
        if op and 'disabled' not in op:
            if lottery_type == 'ssq':
                passed = False; last = ""
                for pattern in op:
                    p, r = check_omission_rule_ssq(red_balls, red_omission, pattern)
                    if p: passed = True; last = r; break
                    last = r
                res['遗漏号原则'] = {'passed': passed, 'message': f'通过, 分布: {last}' if passed else f'不符合, 实际分布: {last}'}
            else:
                passed = False; last = ""
                for pattern in op:
                    conv = pattern.replace('+', ':')
                    p, r = check_omission_rule_dlt(red_balls, red_omission, conv)
                    if p: passed = True; last = r; break
                    last = r
                res['遗漏号原则'] = {'passed': passed, 'message': f'通过, 分布: {last}' if passed else f'不符合, 实际分布: {last}'}

        # 5. 奇偶比
        oe = options.get('odd_even', [])
        if isinstance(oe, str): oe = oe.split(',')
        if oe and 'disabled' not in oe:
            passed, actual = check_odd_even_ratio(red_balls, oe)
            res['奇偶比'] = {'passed': passed, 'message': f'通过, 奇偶比: {actual}' if passed else f'实际: {actual}, 期望: {",".join(oe)}'}

        # 6. 最大跨度
        sp = options.get('span', [])
        if isinstance(sp, str): sp = [sp]
        if sp and 'disabled' not in sp:
            passed = False; asp = 0
            for opt in sp:
                if opt.startswith('lt_'):
                    p, s = check_max_span(red_balls, max_span=int(opt.replace('lt_', '')))
                else:
                    p, s = check_max_span(red_balls, min_span=int(opt.replace('gt_', '')))
                asp = s
                if p: passed = True; break
            res['最大跨度'] = {'passed': passed, 'message': f'通过, 跨度: {asp}' if passed else f'实际跨度: {asp}'}

        # 7. 号码总和
        su = options.get('sum', [])
        if isinstance(su, str): su = [su]
        if su and 'disabled' not in su:
            passed = False; asum = 0
            for opt in su:
                if opt == 'lt_70': p, s = check_sum_range(red_balls, 1, 69)
                elif opt == 'gt_140': p, s = check_sum_range(red_balls, 141, 200)
                elif opt == 'gt_120': p, s = check_sum_range(red_balls, 121, 200)
                else:
                    parts = opt.split('-')
                    if len(parts) == 2: p, s = check_sum_range(red_balls, int(parts[0]), int(parts[1]))
                    else: continue
                asum = s
                if p: passed = True; break
            res['号码总和'] = {'passed': passed, 'message': f'通过, 和值: {asum}' if passed else f'实际和值: {asum}'}

        # 8. 同尾号
        ta = options.get('same_tail', [])
        if isinstance(ta, str): ta = [ta]
        if ta and 'disabled' not in ta:
            passed = False
            for opt in ta:
                p, _ = check_same_tail(red_balls, opt)
                if p: passed = True; break
            res['同尾号'] = {'passed': passed, 'message': '通过' if passed else '不符合同尾号规则'}

        # 9. 邻号(边号)
        nb = options.get('neighbor', [])
        if isinstance(nb, str): nb = [nb]
        if nb and 'disabled' not in nb:
            passed = False; cnt = 0
            for opt in nb:
                nc = int(opt) if opt.isdigit() else None
                if nc is not None:
                    p, cnt = check_neighbor_numbers(red_balls, lottery_type, nc, 'exactly')
                    if p: passed = True; break
            res['邻号(边号)'] = {'passed': passed, 'message': '通过' if passed else f'不符合规则, 实际邻号数: {cnt}'}

        # 10. AC值
        ac = options.get('ac_value', [])
        if isinstance(ac, str): ac = [ac]
        if ac and 'disabled' not in ac:
            passed = False; av = 0
            for opt in ac:
                if lottery_type == 'ssq':
                    if opt == 'lt_5': p, av = check_ac_value(red_balls, [0, 1, 2, 3, 4])
                    elif opt in ['5','6','7','8','9','10']: p, av = check_ac_value(red_balls, [int(opt)])
                    else: continue
                else:
                    if opt in ['0','1','2','3','4','5','6']: p, av = check_ac_value(red_balls, [int(opt)])
                    else: continue
                if p: passed = True; break
            res['AC值'] = {'passed': passed, 'message': f'通过, AC值: {av}' if passed else f'实际AC值: {av}'}

        # 11-12. 蓝球相关（不会被随机忽略）
        if lottery_type == 'ssq':
            blo = options.get('blue_omission', [])
            if isinstance(blo, str): blo = [blo]
            if blo and 'disabled' not in blo:
                passed = False
                for opt in blo:
                    if opt in ['6-12_primary','5-15_primary','0-2_primary','0-4_primary']:
                        p, _ = check_ssq_blue_omission(blue_balls, blue_omission, mode=opt)
                        if p: passed = True; break
                res['蓝球遗漏'] = {'passed': passed, 'message': '通过' if passed else '不符合蓝球遗漏规则'}
            bsel = options.get('blue_selected_balls', None)
            if bsel:
                ok = all(b in bsel for b in blue_balls)
                res['蓝球范围选择'] = {'passed': ok, 'message': '通过' if ok else f'蓝球不在选中范围内'}
        else:
            blo = options.get('blue_omission', [])
            if isinstance(blo, str): blo = [blo]
            if blo and 'disabled' not in blo:
                passed = False
                for opt in blo:
                    if opt in ['5-15_primary','0-2_primary','0-4_primary']:
                        p, _ = check_dlt_blue_omission(blue_balls, blue_omission, mode=opt)
                        if p: passed = True; break
                res['后区遗漏'] = {'passed': passed, 'message': '通过' if passed else '不符合后区遗漏规则'}
            boe = options.get('blue_odd_even', [])
            if isinstance(boe, str): boe = [boe]
            if boe and 'disabled' not in boe:
                passed = False
                for opt in boe:
                    tgt = '1:1' if opt == '1_odd_1_even' else ('2:0' if opt == '2_odd' else '0:2')
                    p, _ = check_dlt_blue_odd_even(blue_balls, tgt)
                    if p: passed = True; break
                res['后区奇偶'] = {'passed': passed, 'message': '通过' if passed else '不符合后区奇偶规则'}
            bsz = options.get('blue_size', [])
            if isinstance(bsz, str): bsz = [bsz]
            if bsz and 'disabled' not in bsz:
                passed = False
                for opt in bsz:
                    tgt = '1:1' if opt == '1_big_1_small' else ('2:0' if opt == '2_big' else '0:2')
                    p, _ = check_dlt_blue_size(blue_balls, tgt)
                    if p: passed = True; break
                res['后区大小'] = {'passed': passed, 'message': '通过' if passed else '不符合后区大小规则'}
            bsel = options.get('blue_selected_balls', None)
            if bsel:
                ok = all(b in bsel for b in blue_balls)
                res['后区范围选择'] = {'passed': ok, 'message': '通过' if ok else '后区号码不在选中范围内'}

        # 判断是否全部通过（只检查有值的规则，未激活的规则跳过）
        all_passed = all(r.get('passed', True) for r in res.values())
        return all_passed, res

    # 单次执行，不随机忽略任何规则，直接返回实际检查结果
    _, final_results = _run_single_check()
    return jsonify(final_results)


@bp.route('/api/prediction/smart_filter_stats', methods=['GET'])
def api_smart_filter_stats():
    """
    获取智能筛选规则统计排名数据
    返回指定彩票类型和回溯期数的规则排名（前3名，含次数和百分比）
    """
    from models import SmartFilterStatsRanking
    
    lottery_type = request.args.get('lottery_type', 'ssq')
    lookback_period = request.args.get('lookback_period', '100', type=int)
    
    if lottery_type not in ['ssq', 'dlt']:
        return jsonify({'error': 'Invalid lottery_type'}), 400
    
    # 获取该彩票类型和回溯期数的所有排名数据
    rankings = SmartFilterStatsRanking.query.filter_by(
        lottery_type=lottery_type,
        lookback_period=lookback_period
    ).order_by(SmartFilterStatsRanking.rule_name, SmartFilterStatsRanking.rank).all()
    
    # 按规则名称分组，返回前端期望的格式
    result = {}
    for r in rankings:
        if r.rule_name not in result:
            result[r.rule_name] = []
        result[r.rule_name].append({
            'rank': r.rank,
            'rule_value': r.rule_value,
            'frequency': r.frequency,
            'percentage': r.percentage
        })
    
    return jsonify(result)


@bp.route('/api/prediction/smart_filter', methods=['POST'])
def api_smart_filter():
    """
    智能筛选生成号码的API端点
    接收详细的筛选选项，返回符合所有规则的号码组合
    """
    data = request.get_json()
    lottery_type = data.get('lottery_type')
    count_str = data.get('count', '5')
    options = data.get('options', {})

    if not lottery_type or lottery_type not in ['ssq', 'dlt']:
        return jsonify({'error': 'Invalid or missing lottery_type'}), 400

    try:
        count = int(count_str)
        if count < 1 or count > 50:
            raise ValueError("Count must be between 1 and 50.")
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid count parameter, must be an integer between 1 and 50.'}), 400

    current_app.logger.info(f"API call: /api/prediction/smart_filter for {lottery_type}, count={count}")

    try:
        generated_numbers = generate_smart_filtered_numbers(lottery_type, count, options)
        
        if not generated_numbers:
            return jsonify({'error': '无法生成符合条件的号码组合，请放宽筛选条件后重试。'}), 500

        current_app.logger.info(f"API call: Successfully generated {len(generated_numbers)} smart filtered numbers for {lottery_type}.")
        return jsonify({'numbers': generated_numbers})
    
    except Exception as e:
        current_app.logger.error(f"API call: Error in smart filter for {lottery_type}: {e}")
        return jsonify({'error': f'智能筛选生成失败: {str(e)}'}), 500
