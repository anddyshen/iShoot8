# admin_routes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, send_file, current_app
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime
import os
import json
import io
import random
import string

from config import ADMIN_PASSWORD, CURRENT_SETTINGS, save_settings, DEFAULT_SETTINGS, __version__, SETTING_LABELS_CHINESE, SSQ_SETTINGS_KEYS, DLT_SETTINGS_KEYS, GENERAL_SETTINGS_KEYS, TREND_SETTINGS_KEYS
from models import db, SSQDraw, DLTDraw, News, AdminSettings
from data_manager import update_latest_draws, add_manual_draw, validate_ssq_format, validate_dlt_format

# 版本号，每次生成文件时更新
__version__ = "1.0.1"

bp = Blueprint('admin_routes', __name__)

# 简单的登录装饰器
def admin_required(f):
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in_admin'):
            flash('请先登录后台管理。', 'warning')
            return redirect(url_for('admin_routes.admin_login'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__ # 保持函数名
    return decorated_function

@bp.route('/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        password = request.form.get('password')
        # 生产环境应使用哈希密码，这里简化
        if password == ADMIN_PASSWORD: # 假设 ADMIN_PASSWORD 是明文，实际应是哈希值
            session['logged_in_admin'] = True
            flash('登录成功！', 'success')
            return redirect(url_for('admin_routes.admin_dashboard'))
        else:
            flash('密码错误。', 'danger')
    return render_template('admin/login.html') # 需要创建这个模板

@bp.route('/logout')
@admin_required
def admin_logout():
    session.pop('logged_in_admin', None)
    flash('已退出登录。', 'info')
    return redirect(url_for('routes.index'))

@bp.route('/')
@admin_required
def admin_dashboard():
    return render_template('admin/dashboard.html')

@bp.route('/settings', methods=['GET', 'POST'])
@bp.route('/settings')
@admin_required
def admin_settings():
    # 重定向到综合参数设置页面作为默认设置页面
    return redirect(url_for('admin_routes.admin_settings_general'))

def _get_admin_setting(key, default_value=None, data_type='string'):
    """从AdminSettings表中获取设置值"""
    setting = AdminSettings.query.filter_by(key=key).first()
    if setting:
        if setting.data_type == 'integer':
            return int(setting.value)
        elif setting.data_type == 'float':
            return float(setting.value)
        elif setting.data_type == 'boolean':
            return setting.value.lower() == 'true'
        elif setting.data_type == 'json':
            return json.loads(setting.value)
        return setting.value
    return default_value

def _update_admin_setting(key, value, description=None, data_type='string'):
    """更新或创建AdminSettings表中的设置值"""
    setting = AdminSettings.query.filter_by(key=key).first()
    if setting:
        setting.value = str(value)
        setting.data_type = data_type
        if description:
            setting.description = description
    else:
        setting = AdminSettings(key=key, value=str(value), description=description, data_type=data_type)
        db.session.add(setting)
    db.session.commit()

def _process_trend_rules_form(lottery_type, ball_type, redirect_route):
    """
    处理趋势规则表单提交的通用逻辑。
    :param lottery_type: 彩票类型 ('ssq' 或 'dlt')。
    :param ball_type: 球类型 ('red' 或 'blue')。
    :param redirect_route: 处理完成后重定向的路由名称。
    """
    rules_key = f'{lottery_type}_{ball_type}_trend_rules'
    if rules_key not in CURRENT_SETTINGS:
        current_app.logger.error(f"Trend rules key '{rules_key}' not found in CURRENT_SETTINGS.")
        return None

    # 复制一份当前设置，以便在处理过程中修改
    updated_rules = CURRENT_SETTINGS[rules_key].copy()

    for rule_name, rule_config in DEFAULT_SETTINGS[rules_key].items():
        # 处理启用/禁用开关
        enabled_key = f'{rules_key}_{rule_name}_enabled'
        updated_rules[rule_name]['enabled'] = (request.form.get(enabled_key) == 'true')

        # 处理组合逻辑
        logic_key = f'{rules_key}_{rule_name}_logic'
        logic_value = request.form.get(logic_key)
        if logic_value in ['AND', 'OR', 'DISABLE']:
            updated_rules[rule_name]['logic'] = logic_value
        else:
            flash(f"规则 '{SETTING_LABELS_CHINESE.get(rule_name, rule_name)}' 的组合逻辑无效。", 'danger')
            return redirect(url_for(redirect_route))

        # 处理参数
        for param_key, default_param_value in rule_config['params'].items():
            form_param_key = f'{rules_key}_{rule_name}_param_{param_key}'
            param_value = request.form.get(form_param_key)

            if param_value is None:
                # 如果是checkbox，未选中则为False
                if isinstance(default_param_value, bool):
                    updated_rules[rule_name]['params'][param_key] = False
                continue

            try:
                if isinstance(default_param_value, int):
                    updated_rules[rule_name]['params'][param_key] = int(param_value)
                elif isinstance(default_param_value, float):
                    updated_rules[rule_name]['params'][param_key] = float(param_value)
                elif isinstance(default_param_value, bool):
                    updated_rules[rule_name]['params'][param_key] = (param_value.lower() == 'true')
                elif isinstance(default_param_value, list): # 假设列表是逗号分隔的数字
                    updated_rules[rule_name]['params'][param_key] = [int(x.strip()) for x in param_value.split(',') if x.strip()]
                else: # 字符串类型
                    updated_rules[rule_name]['params'][param_key] = param_value
            except ValueError:
                flash(f"规则 '{SETTING_LABELS_CHINESE.get(rule_name, rule_name)}' 的参数 '{param_key}' 值 '{param_value}' 格式不正确。", 'danger')
                return redirect(url_for(redirect_route))
    
    CURRENT_SETTINGS[rules_key] = updated_rules
    return None # 成功处理，返回None

def _process_config_settings_form(settings_keys, redirect_route):
    """
    处理来自 config.py 的设置表单提交的通用逻辑。
    :param settings_keys: 当前页面需要处理的设置键列表。
    :param redirect_route: 处理完成后重定向的路由名称。
    """
    if request.method == 'POST':
        for key in settings_keys: # 只处理当前页面相关的设置
            # 检查是否是趋势规则的顶层键
            if key in ['ssq_red_trend_rules', 'ssq_blue_trend_rules', 'dlt_red_trend_rules', 'dlt_blue_trend_rules']:
                lottery_type = key.split('_')[0]
                ball_type = key.split('_')[1]
                response = _process_trend_rules_form(lottery_type, ball_type, redirect_route)
                if response:
                    return response
                continue # 处理完趋势规则后跳过当前key，处理下一个

            value = request.form.get(key)
            if value is None: # 如果表单中没有这个key，可能是checkbox未选中
                if isinstance(DEFAULT_SETTINGS.get(key), bool):
                    CURRENT_SETTINGS[key] = False
                continue

            current_app.logger.debug(f"Processing config setting: key='{key}', value='{value}', type(value)='{type(value)}'")
            default_type = type(DEFAULT_SETTINGS.get(key))
            current_app.logger.debug(f"  Default config setting type for '{key}': '{default_type}'")
            
            if key in CURRENT_SETTINGS:
                # 特殊处理 admin_password：如果输入框为空，则不更新密码
                if key == 'admin_password':
                    if value: # 只有当用户输入了新密码时才更新
                        CURRENT_SETTINGS[key] = value # 假设这里存储的是明文密码
                    continue # 跳过当前设置项，处理下一个
                
                # 尝试转换类型
                if isinstance(DEFAULT_SETTINGS.get(key), int):
                    try:
                        CURRENT_SETTINGS[key] = int(value)
                    except (ValueError, TypeError):
                        flash(f"设置 '{SETTING_LABELS_CHINESE.get(key, key)}' 的值必须是整数。", 'danger')
                        return redirect(url_for(redirect_route))
                elif isinstance(DEFAULT_SETTINGS.get(key), float):
                    try:
                        # 检查是否是百分比相关的key，如果是，则除以100
                        if key in ['ssq_blue_consecutive_3_prob', 'ssq_blue_consecutive_5_prob', 'ssq_red_consecutive_3_prob', 'ssq_red_consecutive_3_second_prob', 'dlt_blue_consecutive_5_prob', 'ssq_red_omit_1_weight', 'ssq_red_omit_2_weight', 'ssq_red_omit_3_weight', 'ssq_red_omit_4_weight', 'ssq_red_omit_5_weight', 'ssq_red_omit_6_weight', 'ssq_red_omit_12_prob', 'ssq_red_omit_13_prob', 'ssq_red_omit_14_prob', 'ssq_red_omit_prob_threshold_1', 'ssq_red_omit_prob_threshold_2', 'ssq_red_omit_prob_threshold_3', 'dlt_blue_repeat_prob', 'dlt_red_omit_1_weight', 'dlt_red_omit_2_weight', 'dlt_red_omit_3_weight', 'dlt_red_omit_4_weight', 'dlt_red_omit_5_weight', 'dlt_red_omit_6_weight', 'dlt_red_consecutive_3_prob', 'dlt_red_omit_prob_threshold_1', 'dlt_red_omit_prob_threshold_2', 'dlt_red_omit_prob_threshold_3', 'ssq_blue_recent_occurrence_weight', 'dlt_blue_recent_occurrence_weight']:
                            processed_value = float(value) / 100
                            CURRENT_SETTINGS[key] = processed_value
                            current_app.logger.debug(f"  Processed percentage value for '{key}': '{processed_value}'")
                        else:
                            processed_value = float(value)
                            CURRENT_SETTINGS[key] = processed_value
                            current_app.logger.debug(f"  Processed float value for '{key}': '{processed_value}'")
                    except (ValueError, TypeError):
                        flash(f"设置 '{SETTING_LABELS_CHINESE.get(key, key)}' 的值必须是浮点数。", 'danger')
                        return redirect(url_for(redirect_route))
                elif isinstance(DEFAULT_SETTINGS.get(key), bool):
                    CURRENT_SETTINGS[key] = (value.lower() == 'true')
                elif isinstance(DEFAULT_SETTINGS.get(key), list): # 假设列表是逗号分隔的数字
                    try:
                        CURRENT_SETTINGS[key] = [int(x.strip()) for x in value.split(',') if x.strip()]
                    except ValueError:
                        flash(f"设置 '{SETTING_LABELS_CHINESE.get(key, key)}' 的值 '{value}' 格式不正确，应为逗号分隔的数字。", 'danger')
                        return redirect(url_for(redirect_route))
                else:
                    CURRENT_SETTINGS[key] = value
        
        save_settings(CURRENT_SETTINGS)
        flash('网站设置已更新！', 'success')
        return redirect(url_for(redirect_route))
    return None # GET请求时返回None

@bp.route('/settings/ssq', methods=['GET', 'POST'])
@admin_required
def admin_settings_ssq():
    response = _process_config_settings_form(SSQ_SETTINGS_KEYS, 'admin_routes.admin_settings_ssq')
    if response:
        return response
    
    ssq_settings = {key: CURRENT_SETTINGS[key] for key in SSQ_SETTINGS_KEYS if key in CURRENT_SETTINGS}
    return render_template('admin/settings_ssq.html', 
                           settings=ssq_settings, 
                           default_settings=DEFAULT_SETTINGS,
                           setting_labels=SETTING_LABELS_CHINESE,
                           ssq_settings_keys=SSQ_SETTINGS_KEYS
                           )

@bp.route('/settings/dlt', methods=['GET', 'POST'])
@admin_required
def admin_settings_dlt():
    response = _process_config_settings_form(DLT_SETTINGS_KEYS, 'admin_routes.admin_settings_dlt')
    if response:
        return response
    
    dlt_settings = {key: CURRENT_SETTINGS[key] for key in DLT_SETTINGS_KEYS if key in CURRENT_SETTINGS}
    return render_template('admin/settings_dlt.html', 
                           settings=dlt_settings, 
                           default_settings=DEFAULT_SETTINGS,
                           setting_labels=SETTING_LABELS_CHINESE,
                           dlt_settings_keys=DLT_SETTINGS_KEYS
                           )

@bp.route('/settings/general', methods=['GET', 'POST'])
@admin_required
def admin_settings_general():
    response = _process_config_settings_form(GENERAL_SETTINGS_KEYS, 'admin_routes.admin_settings_general')
    if response:
        return response
    
    general_settings = {key: CURRENT_SETTINGS[key] for key in GENERAL_SETTINGS_KEYS if key in CURRENT_SETTINGS}
    return render_template('admin/settings_general.html', 
                           settings=general_settings, 
                           default_settings=DEFAULT_SETTINGS,
                           setting_labels=SETTING_LABELS_CHINESE,
                           general_settings_keys=GENERAL_SETTINGS_KEYS
                           )

@bp.route('/settings/trend', methods=['GET', 'POST'])
@admin_required
def admin_settings_trend():
    if request.method == 'POST':
        lookback_periods_str = request.form.get('lookback_periods')
        if lookback_periods_str:
            try:
                # Validate input: ensure it's a comma-separated list of integers
                periods = [int(x.strip()) for x in lookback_periods_str.split(',') if x.strip()]
                _update_admin_setting('lookback_periods', lookback_periods_str, 'Comma-separated list of lookback periods for trend calculations', 'string')
                flash('回溯期数设置已更新！', 'success')
            except ValueError:
                flash('回溯期数格式不正确，请输入逗号分隔的整数列表。', 'danger')
        else:
            flash('回溯期数不能为空。', 'danger')
        return redirect(url_for('admin_routes.admin_settings_trend'))
    
    lookback_periods = _get_admin_setting('lookback_periods', default_value="5,10,20,50,100,200")
    
    return render_template('admin/settings_trend.html', 
                           lookback_periods=lookback_periods,
                           setting_labels=SETTING_LABELS_CHINESE,
                           trend_settings_keys=TREND_SETTINGS_KEYS
                           )

@bp.route('/settings/download')
@admin_required
def download_settings():
    settings_data = json.dumps(CURRENT_SETTINGS, indent=4, ensure_ascii=False)
    buffer = io.BytesIO(settings_data.encode('utf-8'))
    return send_file(buffer,
                     mimetype='application/json',
                     as_attachment=True,
                     download_name='ishoot_settings_backup.json')

@bp.route('/settings/restore_default')
@admin_required
def restore_default_settings():
    global CURRENT_SETTINGS
    CURRENT_SETTINGS = DEFAULT_SETTINGS.copy() # 恢复默认值
    save_settings(CURRENT_SETTINGS)
    flash('网站设置已恢复为默认值！', 'success')
    return redirect(url_for('admin_routes.admin_settings'))


# @bp.route('/data_update', methods=['GET', 'POST'])
# @admin_required
# def admin_data_update():
#     if request.method == 'POST':
#         action = request.form.get('action')
#         if action == 'manual_update':
#             ssq_count, dlt_count = update_latest_draws()
#             flash(f'手动更新完成！双色球新增 {ssq_count} 条，大乐透新增 {dlt_count} 条。', 'success')
#         elif action == 'manual_add':
#             lottery_type = request.form.get('lottery_type')
#             data_string = request.form.get('data_string').strip()
#             if lottery_type == 'ssq':
#                 is_valid, msg = validate_ssq_format(data_string)
#             elif lottery_type == 'dlt':
#                 is_valid, msg = validate_dlt_format(data_string)
#             else:
#                 is_valid, msg = False, "未知彩票类型"

#             if is_valid:
#                 new_count = add_manual_draw(lottery_type, data_string)
#                 if new_count > 0:
#                     flash(f'手动添加 {lottery_type.upper()} 数据成功！新增 {new_count} 条。', 'success')
#                 else:
#                     flash(f'手动添加 {lottery_type.upper()} 数据失败，可能期号已存在或数据格式有误。', 'warning')
#             else:
#                 flash(f'手动添加 {lottery_type.upper()} 数据格式校验失败: {msg}', 'danger')
#         # TODO: 添加定时任务控制逻辑
#         return redirect(url_for('admin_routes.admin_data_update'))
#     return render_template('admin/data_update.html')

@bp.route('/data_update', methods=['GET', 'POST'])
@admin_required
def admin_data_update():
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'manual_update':
            # 2. 修改这一行，传入 current_app
            ssq_count, dlt_count = update_latest_draws(current_app)
            flash(f'手动更新完成！双色球新增 {ssq_count} 条，大乐透新增 {dlt_count} 条。', 'success')
        elif action == 'manual_add':
            lottery_type = request.form.get('lottery_type')
            data_string = request.form.get('data_string').strip()
            if lottery_type == 'ssq':
                is_valid, msg = validate_ssq_format(data_string)
            elif lottery_type == 'dlt':
                is_valid, msg = validate_dlt_format(data_string)
            else:
                is_valid, msg = False, "未知彩票类型"

            if is_valid:
                # 注意：add_manual_draw 如果也需要 app 上下文，也需要类似修改
                new_count = add_manual_draw(lottery_type, data_string)
                if new_count > 0:
                    flash(f'手动添加 {lottery_type.upper()} 数据成功！新增 {new_count} 条。', 'success')
                else:
                    flash(f'手动添加 {lottery_type.upper()} 数据失败，可能期号已存在或数据格式有误。', 'warning')
            else:
                flash(f'手动添加 {lottery_type.upper()} 数据格式校验失败: {msg}', 'danger')
        # TODO: 添加定时任务控制逻辑
        return redirect(url_for('admin_routes.admin_data_update'))
    return render_template('admin/data_update.html')

@bp.route('/news_manage', methods=['GET', 'POST'])
@admin_required
def admin_news_manage():
    news_list = News.query.order_by(News.created_at.desc()).all()
    if request.method == 'POST':
        action = request.form.get('action')
        news_id = request.form.get('news_id', type=int)

        if action == 'add' or action == 'edit':
            title = request.form.get('title')
            image_url = request.form.get('image_url')
            summary = request.form.get('summary')
            content = request.form.get('content')
            is_homepage_display = 'is_homepage_display' in request.form
            is_public = 'is_public' in request.form

            if action == 'add':
                new_news = News(title=title, image_url=image_url, summary=summary, content=content,
                                is_homepage_display=is_homepage_display, is_public=is_public)
                db.session.add(new_news)
                flash('新闻添加成功！', 'success')
            elif action == 'edit':
                news_item = News.query.get_or_404(news_id)
                news_item.title = title
                news_item.image_url = image_url
                news_item.summary = summary
                news_item.content = content
                news_item.is_homepage_display = is_homepage_display
                news_item.is_public = is_public
                flash('新闻更新成功！', 'success')
            db.session.commit()
        elif action == 'delete':
            news_item = News.query.get_or_404(news_id)
            db.session.delete(news_item)
            db.session.commit()
            flash('新闻删除成功！', 'success')
        return redirect(url_for('admin_routes.admin_news_manage'))
    return render_template('admin/news_manage.html', news_list=news_list)
