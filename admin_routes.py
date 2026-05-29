# admin_routes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, send_file, current_app
from flask_login import login_user, logout_user, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime, timedelta
import os
import json
import io
import random
import string

from config import ADMIN_PASSWORD, CURRENT_SETTINGS, save_settings, DEFAULT_SETTINGS, __version__, SETTING_LABELS_CHINESE, SSQ_SETTINGS_KEYS, DLT_SETTINGS_KEYS, GENERAL_SETTINGS_KEYS, TREND_SETTINGS_KEYS
from models import db, SSQDraw, DLTDraw, News, AdminSettings, User
from data_manager import update_latest_draws, add_manual_draw, validate_ssq_format, validate_dlt_format

# 版本号，每次生成文件时更新
__version__ = "1.0.1"

bp = Blueprint('admin_routes', __name__)

# 统一的 admin_required 装饰器：同时支持旧 session 和 Flask-Login
def admin_required(f):
    def decorated_function(*args, **kwargs):
        # 检查 Flask-Login 方式登录的管理员
        if current_user.is_authenticated and current_user.is_admin and current_user.is_active:
            return f(*args, **kwargs)
        # 检查旧 session 方式（兼容老用户）
        if session.get('logged_in_admin'):
            return f(*args, **kwargs)
        flash('请先登录后台管理。', 'warning')
        return redirect(url_for('auth_routes.login'))
    decorated_function.__name__ = f.__name__
    return decorated_function

@bp.route('/login', methods=['GET', 'POST'])
def admin_login():
    """后台登录 - 使用 User 表的管理员账号"""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        user = User.query.filter_by(username=username).first()
        
        if not user or not user.check_password(password):
            flash('用户名或密码错误。', 'danger')
            return render_template('admin/login.html')
        
        if not user.is_active:
            flash('账户已被禁用，请联系管理员。', 'danger')
            return render_template('admin/login.html')
        
        if not user.is_admin:
            flash('你不是管理员，无法登录后台。', 'danger')
            return render_template('admin/login.html')
        
        # 更新最后登录时间
        user.last_login_at = datetime.utcnow()
        db.session.commit()
        
        login_user(user)
        flash('登录成功！', 'success')
        return redirect(url_for('admin_routes.admin_dashboard'))
    
    return render_template('admin/login.html')

@bp.route('/logout')
def admin_logout():
    """退出后台"""
    # 清除旧 session 方式
    session.pop('logged_in_admin', None)
    # Flask-Login 退出
    logout_user()
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
                        if key in ['ssq_blue_consecutive_3_prob', 'ssq_blue_consecutive_5_prob', 'ssq_red_consecutive_3_prob', 'ssq_red_consecutive_3_second_prob', 'dlt_blue_consecutive_5_prob', 'ssq_red_omit_1_weight', 'ssq_red_omit_2_weight', 'ssq_red_omit_3_weight', 'ssq_red_omit_4_weight', 'ssq_red_omit_5_weight', 'ssq_red_omit_6_weight', 'ssq_red_omit_prob_threshold_1', 'ssq_red_omit_prob_threshold_2', 'ssq_red_omit_prob_threshold_3', 'dlt_blue_repeat_prob', 'dlt_red_omit_1_weight', 'dlt_red_omit_2_weight', 'dlt_red_omit_3_weight', 'dlt_red_omit_4_weight', 'dlt_red_omit_5_weight', 'dlt_red_omit_6_weight', 'dlt_red_consecutive_3_prob', 'dlt_red_omit_prob_threshold_1', 'dlt_red_omit_prob_threshold_2', 'dlt_red_omit_prob_threshold_3']:
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
                           trend_settings_keys=TREND_SETTINGS_KEYS,
                           default_settings=DEFAULT_SETTINGS
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


@bp.route('/data_update', methods=['GET', 'POST'])
@admin_required
def admin_data_update():
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'manual_update':
            import logging
            logger = logging.getLogger(__name__)
            ssq_count, dlt_count, total_trend, total_smart = update_latest_draws(current_app)
            logger.info(f"数据更新完成: SSQ={ssq_count}, DLT={dlt_count}, 趋势={total_trend}, 智能={total_smart}")
            msg_parts = [f'手动更新完成！双色球新增 {ssq_count} 条，大乐透新增 {dlt_count} 条。']
            msg_parts.append(f'趋势数据预计算 {total_trend} 条。')
            msg_parts.append(f'智能筛选规则统计新增 {total_smart} 条。')
            flash(' '.join(msg_parts), 'success')
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
                new_count = add_manual_draw(lottery_type, data_string)
                if new_count > 0:
                    flash(f'手动添加 {lottery_type.upper()} 数据成功！新增 {new_count} 条。', 'success')
                else:
                    flash(f'手动添加 {lottery_type.upper()} 数据失败，可能期号已存在或数据格式有误。', 'warning')
            else:
                flash(f'手动添加 {lottery_type.upper()} 数据格式校验失败: {msg}', 'danger')
        elif action == 'update_schedule':
            enabled = request.form.get('scheduled_update_enabled') == 'true'
            hour = int(request.form.get('scheduled_update_hour', 3))
            minute = int(request.form.get('scheduled_update_minute', 15))
            
            if hour < 0 or hour > 23:
                flash('小时值必须在 0-23 之间。', 'danger')
                return redirect(url_for('admin_routes.admin_data_update'))
            if minute < 0 or minute > 59:
                flash('分钟值必须在 0-59 之间。', 'danger')
                return redirect(url_for('admin_routes.admin_data_update'))
            
            CURRENT_SETTINGS['scheduled_update_enabled'] = enabled
            CURRENT_SETTINGS['scheduled_update_hour'] = hour
            CURRENT_SETTINGS['scheduled_update_minute'] = minute
            save_settings(CURRENT_SETTINGS)
            
            try:
                scheduler = current_app.scheduler
                setup_fn = current_app.setup_scheduled_job
                setup_fn(current_app)
                flash(f'定时更新设置已保存！' + (f' 下次定时更新: {hour:02d}:{minute:02d}' if enabled else ' 定时更新已禁用。'), 'success')
            except AttributeError as e:
                flash(f'定时更新设置已保存，但无法更新调度器（应用重启后生效）。错误: {e}', 'warning')
            
            return redirect(url_for('admin_routes.admin_data_update'))
        
        return redirect(url_for('admin_routes.admin_data_update'))
    return render_template('admin/data_update.html')

@bp.route('/change_password', methods=['GET', 'POST'])
@admin_required
def admin_change_password():
    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        if not current_user.check_password(current_password):
            flash('当前密码错误。', 'danger')
            return redirect(url_for('admin_routes.admin_change_password'))

        if len(new_password) < 6:
            flash('新密码长度至少6位。', 'danger')
            return redirect(url_for('admin_routes.admin_change_password'))

        if new_password != confirm_password:
            flash('两次输入的新密码不一致。', 'danger')
            return redirect(url_for('admin_routes.admin_change_password'))

        current_user.set_password(new_password)
        db.session.commit()

        flash('密码修改成功！', 'success')
        return redirect(url_for('admin_routes.admin_dashboard'))

    return render_template('admin/change_password.html')


@bp.route('/users')
@admin_required
def admin_users():
    """用户列表管理"""
    users = User.query.order_by(User.created_at.desc()).all()
    allow_registration = CURRENT_SETTINGS.get('allow_registration', False)
    return render_template('admin/user_manage.html', users=users, allow_registration=allow_registration)


@bp.route('/users/toggle_registration', methods=['POST'])
@admin_required
def admin_toggle_registration():
    """切换是否允许用户注册"""
    data = request.get_json()
    if data is None:
        return {'error': '无效的请求数据'}, 400
    
    enabled = data.get('enabled', False)
    CURRENT_SETTINGS['allow_registration'] = bool(enabled)
    save_settings(CURRENT_SETTINGS)
    return {'message': '设置已更新', 'allow_registration': bool(enabled)}

@bp.route('/users/<int:user_id>/toggle_active', methods=['POST'])
@admin_required
def admin_toggle_user_active(user_id):
    """启用/禁用用户"""
    user = db.session.get(User, user_id)
    if not user:
        flash('用户不存在。', 'danger')
        return redirect(url_for('admin_routes.admin_users'))
    
    user.is_active = not user.is_active
    db.session.commit()
    status = '启用' if user.is_active else '禁用'
    flash(f'用户 {user.username} 已{status}。', 'success')
    return redirect(url_for('admin_routes.admin_users'))

@bp.route('/users/<int:user_id>/toggle_admin', methods=['POST'])
@admin_required
def admin_toggle_user_admin(user_id):
    """设为/取消管理员"""
    user = db.session.get(User, user_id)
    if not user:
        flash('用户不存在。', 'danger')
        return redirect(url_for('admin_routes.admin_users'))
    
    # 不能取消自己的管理员权限
    if user.id == current_user.id:
        flash('不能取消自己的管理员权限。', 'danger')
        return redirect(url_for('admin_routes.admin_users'))
    
    user.is_admin = not user.is_admin
    db.session.commit()
    status = '管理员' if user.is_admin else '普通用户'
    flash(f'用户 {user.username} 已设为{status}。', 'success')
    return redirect(url_for('admin_routes.admin_users'))

@bp.route('/users/<int:user_id>/reset_password', methods=['POST'])
@admin_required
def admin_reset_user_password(user_id):
    """管理员重置用户密码"""
    user = db.session.get(User, user_id)
    if not user:
        flash('用户不存在。', 'danger')
        return redirect(url_for('admin_routes.admin_users'))
    
    new_password = request.form.get('new_password', '')
    if len(new_password) < 6:
        flash('密码至少6个字符。', 'danger')
        return redirect(url_for('admin_routes.admin_users'))
    
    user.set_password(new_password)
    db.session.commit()
    flash(f'用户 {user.username} 的密码已重置。', 'success')
    return redirect(url_for('admin_routes.admin_users'))


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


@bp.route('/notifications')
@admin_required
def admin_notifications():
    """通知管理页面（全局通知）"""
    return render_template('admin/notifications.html')


@bp.route('/api/recent_broadcasts', methods=['GET'])
@admin_required
def admin_recent_broadcasts():
    """获取最近发送的全局通知记录（最近20条）"""
    from models import NotificationLog
    
    # 找到所有标题包含"【系统公告】"的通知，按发送时间倒序排列
    logs = NotificationLog.query.filter(
        NotificationLog.title.like('%【系统公告】%')
    ).order_by(NotificationLog.sent_at.desc()).limit(20).all()
    
    # 去重 - 按标题+内容分组，取最早一条（显示操作人）
    seen = {}
    result_logs = []
    for log in logs:
        key = f"{log.title}|{log.content}"
        if key not in seen:
            seen[key] = log
            # 统计接收人数：同标题+内容的通知记录数（含失败）
            recipient_count = NotificationLog.query.filter_by(
                title=log.title, content=log.content
            ).count()
            
            result_logs.append({
                'id': log.id,
                'title': log.title.replace('【系统公告】', '').strip(),
                'content': log.content[:100] if log.content else '',
                'admin_name': '管理员',
                'recipient_count': recipient_count,
                'sent_at': (log.sent_at + timedelta(hours=8)).strftime('%Y-%m-%d %H:%M') if log.sent_at else None,
            })
    
    return {'logs': result_logs}


@bp.route('/api/broadcast_notification', methods=['POST'])
@admin_required
def admin_broadcast_notification():
    """向所有用户发送全局通知（站内消息）"""
    from models import User, NotificationLog
    from datetime import datetime
    
    data = request.get_json()
    if not data:
        return {'error': '无效的请求数据'}, 400
    
    title = data.get('title', '').strip()
    content = data.get('content', '').strip()
    
    if not title or not content:
        return {'error': '标题和内容不能为空'}, 400
    
    if len(title) > 200:
        return {'error': '标题长度不能超过200个字符'}, 400
    
    # 获取所有活跃用户
    users = User.query.filter_by(is_active=True).all()
    
    if not users:
        return {'error': '没有活跃用户可发送通知'}, 400
    
    # 添加系统公告前缀
    full_title = f'【系统公告】{title}'
    
    # 向每个用户发送站内通知
    success_count = 0
    now = datetime.utcnow()
    
    for user in users:
        try:
            notification = NotificationLog(
                user_id=user.id,
                channel='in_app',
                title=full_title,
                content=content,
                status='sent',
                sent_at=now,
            )
            db.session.add(notification)
            success_count += 1
        except Exception as e:
            current_app.logger.error(f"发送通知给用户 {user.id} 失败: {e}")
    
    db.session.commit()
    
    current_app.logger.info(f"管理员 {current_user.username} 发送全局通知「{title}」给 {success_count} 个用户")
    
    return {'message': f'通知已成功发送给 {success_count} 个用户！'}


@bp.route('/api/test_email', methods=['POST'])
@admin_required
def admin_test_email():
    """管理员发送测试邮件（无冷却限制）"""
    import json
    data = request.get_json()
    if not data:
        return {'error': '无效的请求数据'}, 400
    
    to_email = data.get('email', '').strip()
    if not to_email:
        return {'error': '请输入接收测试邮件的邮箱地址'}, 400
    
    from notification.email_notifier import EmailNotifier
    
    # 创建一个临时用户对象用于发送测试邮件
    class TempUser:
        email = to_email
        notification_config = {
            'channel_configs': {
                'email': {
                    'email_address': to_email,
                }
            }
        }
    
    notifier = EmailNotifier()
    success, message = notifier.send(TempUser(), '🧪 iShoot 后台邮件测试', '这是一封来自 iShoot 管理后台的测试邮件，如果您收到此邮件，说明邮件配置正确。')
    
    if success:
        return {'message': f'测试邮件已成功发送至 {to_email}'}
    else:
        return {'error': f'发送失败: {message}'}, 500
