# admin_routes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, send_file
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime
import os
import json
import io
import random
import string

from config import ADMIN_PASSWORD, CURRENT_SETTINGS, save_settings, DEFAULT_SETTINGS, __version__
from models import db, SSQDraw, DLTDraw, News
from data_manager import update_latest_draws, add_manual_draw, validate_ssq_format, validate_dlt_format

# 版本号，每次生成文件时更新
__version__ = "1.0.0"

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
@admin_required
def admin_settings():
    if request.method == 'POST':
        # 更新设置
        for key, value in request.form.items():
            if key in CURRENT_SETTINGS:
                # 尝试转换类型
                if isinstance(DEFAULT_SETTINGS.get(key), int):
                    CURRENT_SETTINGS[key] = int(value)
                elif isinstance(DEFAULT_SETTINGS.get(key), float):
                    CURRENT_SETTINGS[key] = float(value)
                elif isinstance(DEFAULT_SETTINGS.get(key), bool):
                    CURRENT_SETTINGS[key] = (value.lower() == 'true')
                elif isinstance(DEFAULT_SETTINGS.get(key), list): # 假设列表是逗号分隔的数字
                    try:
                        CURRENT_SETTINGS[key] = [int(x.strip()) for x in value.split(',') if x.strip()]
                    except ValueError:
                        flash(f"设置 '{key}' 的值 '{value}' 格式不正确，应为逗号分隔的数字。", 'danger')
                        return redirect(url_for('admin_routes.admin_settings'))
                else:
                    CURRENT_SETTINGS[key] = value
        save_settings(CURRENT_SETTINGS)
        flash('网站设置已更新！', 'success')
        return redirect(url_for('admin_routes.admin_settings'))
    return render_template('admin/settings.html', settings=CURRENT_SETTINGS, default_settings=DEFAULT_SETTINGS)

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
            ssq_count, dlt_count = update_latest_draws()
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


