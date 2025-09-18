# routes.py
from flask import Blueprint, render_template, request, flash, redirect, url_for, session, jsonify
from datetime import datetime, date
from models import SSQDraw, DLTDraw, News, db
from data_manager import get_latest_draws
from config import CURRENT_SETTINGS, STAT_EXPLANATIONS, PRIZE_RULES, PER_BET_PRICE # PRIZE_RULES 已经导入
from utils import (
    format_lottery_numbers, calculate_odd_even_sum, 
    get_aggregated_stats, calculate_frequency_and_omissions_for_balls,
    calculate_combination_cost, calculate_prize_details, simulate_fun_game
)
from prediction_engine import check_lottery_rules

bp = Blueprint('routes', __name__)

@bp.route('/')
def index():
    latest_ssq = get_latest_draws(SSQDraw, 1)
    latest_dlt = get_latest_draws(DLTDraw, 1)
    homepage_news = News.query.filter_by(is_homepage_display=True, is_public=True).order_by(News.created_at.desc()).limit(3).all()
    return render_template('index.html',
                           latest_ssq=latest_ssq[0] if latest_ssq else None,
                           latest_dlt=latest_dlt[0] if latest_dlt else None,
                           homepage_news=homepage_news)

@bp.route('/history')
def history():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', CURRENT_SETTINGS['history_page_size'], type=int)
    lottery_type = request.args.get('lottery_type', 'ssq')

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
                           end_date=end_date_str
                           )

@bp.route('/statistics')
def statistics():
    lottery_type = request.args.get('lottery_type', 'ssq')

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
    # 号码预测页面
    # TODO: 实现预测逻辑、随机号码生成、规则展示、筛选饼状图
    return render_template('prediction.html')

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
                           prize_rules=PRIZE_RULES # <--- 新增：将 PRIZE_RULES 传递给模板
                           )

@bp.route('/api/check_prizes', methods=['POST'])
def api_check_prizes():
    data = request.get_json()
    lottery_type = data.get('lottery_type')
    combinations = data.get('combinations') # [{red_balls: '1,2,3', blue_balls: '1'}, ...]
    
    check_range_val = data.get('check_range', CURRENT_SETTINGS.get('prize_check_range', 10))
    try:
        check_range = int(check_range_val)
    except (ValueError, TypeError):
        check_range = CURRENT_SETTINGS.get('prize_check_range', 10) # Fallback to default if conversion fails

    if not lottery_type or not combinations:
        return jsonify({'error': '缺少彩票类型或号码组合'}), 400

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

        user_red_balls = format_lottery_numbers(user_red_balls_str)
        user_blue_balls = format_lottery_numbers(user_blue_balls_str)

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

@bp.route('/api/fun_game', methods=['POST'])
def api_fun_game():
    data = request.get_json()
    lottery_type = data.get('lottery_type')
    combinations = data.get('combinations') # [{red_balls: '1,2,3', blue_balls: '1'}, ...]

    if not lottery_type or not combinations:
        return jsonify({'error': '缺少彩票类型或号码组合'}), 400

    # 趣味游戏只处理第一个号码组合
    first_combo = combinations[0]
    user_red_balls_str = first_combo.get('red_balls')
    user_blue_balls_str = first_combo.get('blue_balls')

    user_red_balls = format_lottery_numbers(user_red_balls_str)
    user_blue_balls = format_lottery_numbers(user_blue_balls_str)

    max_simulations_val = data.get('max_simulations', CURRENT_SETTINGS.get('fun_game_max_simulations', 1000000))
    try:
        max_simulations = int(max_simulations_val)
    except (ValueError, TypeError):
        max_simulations = CURRENT_SETTINGS.get('fun_game_max_simulations', 1000000) # Fallback to default

    # 调用 simulate_fun_game，只传递一个组合
    sim_result = simulate_fun_game(user_red_balls, user_blue_balls, lottery_type, max_simulations)
    
    # 返回结果，因为只模拟了一个组合，所以直接返回其结果
    return jsonify({'results': [sim_result]})


@bp.route('/news/<int:news_id>')
def news_detail(news_id):
    news_item = News.query.get_or_404(news_id)
    if not news_item.is_public and not session.get('logged_in_admin'):
        flash('该文章不公开或您没有权限访问。', 'danger')
        return redirect(url_for('routes.index'))

    prev_news = News.query.filter(News.id < news_id, News.is_public == True).order_by(News.id.desc()).first()
    next_news = News.query.filter(News.id > news_id, News.is_public == True).order_by(News.id.asc()).first()

    return render_template('news_detail.html', news_item=news_item, prev_news=prev_news, next_news=next_news)

@bp.route('/api/check_rules', methods=['GET'])
def api_check_rules():
    lottery_type = request.args.get('lottery_type')
    issue = request.args.get('issue')

    if not lottery_type or not issue:
        return jsonify({'error': 'Missing lottery_type or issue'}), 400

    results = check_lottery_rules(lottery_type, issue)

    if 'error' in results:
        if results.get('error') in ['SSQDraw not found', 'DLTDraw not found']:
            return jsonify(results), 404
        return jsonify(results), 500

    return jsonify(results)

