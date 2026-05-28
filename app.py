# app.py
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager, current_user
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import pytz # 用于处理时区
import os
import json
import time
import random
import string
from dotenv import load_dotenv
from utils import format_lottery_numbers # 导入 utils 中的函数
from prediction_engine import check_lottery_rules # 导入规则检查函数
from data_manager import save_draw_data, get_latest_draws, update_latest_draws

# 加载环境变量
load_dotenv()

# 从 config.py 导入配置
from config import (
    SQLALCHEMY_DATABASE_URI, SQLALCHEMY_TRACK_MODIFICATIONS,
    SITE_NAME, SITE_URL, PER_BET_PRICE,
    ADMIN_PASSWORD, ADMIN_ROUTE_PREFIX,
    CURRENT_SETTINGS, save_settings, DEFAULT_SETTINGS,
    __version__
)
from models import db, SSQDraw, DLTDraw, News, AdminSettings, initialize_admin_route_prefix, User

# 初始化 Flask 应用
app = Flask(__name__, instance_relative_config=True)
app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = SQLALCHEMY_TRACK_MODIFICATIONS
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'super_secret_key_for_dev') # 生产环境务必设置强密钥

# 初始化 SQLAlchemy
db.init_app(app)

# 初始化 Flask-Migrate
migrate = Migrate(app, db)

# 初始化 Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth_routes.login'
login_manager.login_message = '请先登录。'
login_manager.login_message_category = 'warning'

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# 初始化 APScheduler
scheduler = BackgroundScheduler(timezone=pytz.timezone('Asia/Shanghai'))

# ==================== 邮件配置 ====================
app.config['MAIL_SERVER'] = CURRENT_SETTINGS.get('smtp_server', '')
app.config['MAIL_PORT'] = int(CURRENT_SETTINGS.get('smtp_port', 587))
app.config['MAIL_USERNAME'] = CURRENT_SETTINGS.get('smtp_username', '')
app.config['MAIL_PASSWORD'] = CURRENT_SETTINGS.get('smtp_password', '')
app.config['MAIL_USE_TLS'] = CURRENT_SETTINGS.get('smtp_use_tls', True)
app.config['MAIL_DEFAULT_SENDER'] = (
    CURRENT_SETTINGS.get('smtp_from_name', 'iShoot 彩票助手'),
    CURRENT_SETTINGS.get('smtp_username', '')
)
# ================================================

def setup_scheduled_job(app_instance):
    """根据 CURRENT_SETTINGS 设置或更新定时任务"""
    global scheduler
    enabled = CURRENT_SETTINGS.get('scheduled_update_enabled', True)
    hour = int(CURRENT_SETTINGS.get('scheduled_update_hour', 3))
    minute = int(CURRENT_SETTINGS.get('scheduled_update_minute', 15))
    
    # 移除现有任务
    existing_jobs = scheduler.get_jobs()
    for job in existing_jobs:
        if job.id == 'scheduled_data_update':
            job.remove()
    
    if enabled:
        job = scheduler.add_job(
            func=update_latest_draws,
            trigger="cron",
            hour=hour,
            minute=minute,
            args=[app_instance],
            id='scheduled_data_update'
        )
        try:
            next_run = job.next_run_time
            print(f"定时更新已启用，下次运行时间: {next_run}")
        except AttributeError:
            print(f"定时更新已启用，运行时间: 每天 {hour:02d}:{minute:02d}")
    else:
        print("定时更新已禁用")

# 导入 Flask-Mail
from flask_mail import Mail

# 全局初始化 Flask-Mail（先不传 app）
mail = Mail()

# 在 app 配置之后初始化 Mail
mail.init_app(app)
app.mail = mail  # 附加到 app 便于其他模块访问

# 导入数据管理模块
from data_manager import save_draw_data, get_latest_draws, update_latest_draws

# ==================== 通知系统初始化 ====================
from notification import manager as notification_manager
from notification.in_app_notifier import InAppNotifier
from notification.email_notifier import EmailNotifier
from notification.synology_notifier import SynologyChatNotifier

def init_notification_system():
    """初始化并注册所有通知渠道"""
    notification_manager.register(InAppNotifier())
    notification_manager.register(EmailNotifier())
    notification_manager.register(SynologyChatNotifier())
    print("通知系统初始化完成，已注册渠道:")
    for n in notification_manager.get_all_notifiers():
        # 移除 emoji 避免 Windows 控制台编码问题
        import re
        label = re.sub(r'[^\u4e00-\u9fff\w\s\-]', '', n.channel_label).strip()
        print(f"  - {label}")

# 将通知管理器附加到 app 便于访问（初始化在下方 app_context 中执行）
app.notification_manager = notification_manager
# =======================================================

# 导入路由
import routes
import admin_routes
import auth_routes

# 注册蓝图或直接注册路由
app.register_blueprint(routes.bp)
app.register_blueprint(admin_routes.bp, url_prefix=f'/{ADMIN_ROUTE_PREFIX}')
app.register_blueprint(auth_routes.bp)

# 上下文处理器：在所有模板中可用
@app.context_processor
def inject_global_data():
    return {
        'site_name': SITE_NAME,
        'site_url': SITE_URL,
        'current_datetime': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'app_version': __version__,
        'per_bet_price': PER_BET_PRICE,
        'settings': CURRENT_SETTINGS, # 将网站设置注入模板
        'format_lottery_numbers': format_lottery_numbers, # 确保这个也在这里，或者在routes.py中传递
        # 'calculate_odd_even_sum': calculate_odd_even_sum # 将函数传递给模板
    }

# 数据库初始化和定时任务启动
# with app.app_context():
#     db.create_all()
    # 检查并初始化 ADMIN_ROUTE_PREFIX
    # 注意：这里只是打印提示，实际持久化需要手动修改config.py或环境变量
    # 或者在AdminSettings表中存储
    # current_admin_prefix = initialize_admin_route_prefix()

    # print(f"\n*** 后台管理页面入口 (Admin Panel URL): http://127.0.0.1:5000/{current_admin_prefix} ***\n")
    # if current_admin_prefix != ADMIN_ROUTE_PREFIX:
    #     # 更新 config.py 中的 ADMIN_ROUTE_PREFIX，但这通常不推荐在运行时修改代码文件
    #     # 更好的方式是将其存储在数据库中，并在应用启动时加载
    #     pass

    # 启动定时任务 (例如，每天凌晨3点更新数据)
    # job = scheduler.add_job(func=update_latest_draws, trigger="cron", hour=23, minute=14)
    # scheduler.start()
    # print("APScheduler started.")

# 首页路由 (示例，实际由 routes.py 处理)
# @app.route('/')
# def index():
#     latest_ssq = get_latest_draws(SSQDraw, 1)
#     latest_dlt = get_latest_draws(DLTDraw, 1)
#     homepage_news = News.query.filter_by(is_homepage_display=True, is_public=True).order_by(News.created_at.desc()).limit(3).all()
#     return render_template('index.html', latest_ssq=latest_ssq, latest_dlt=latest_dlt, homepage_news=homepage_news)

# 数据库初始化和定时任务启动
with app.app_context():
    db.create_all()
    AdminSettings.initialize_default_settings() # Initialize default settings, including lookback periods

    # 初始化通知系统
    init_notification_system()

    # 将调度器附加到 app 上，便于 admin_routes 访问
    app.scheduler = scheduler
    app.setup_scheduled_job = setup_scheduled_job
    
    # 使用动态设置启动定时任务
    setup_scheduled_job(app)
    
    # 第一次启动时创建默认管理员（如果不存在）
    # 密码固定为 admin123，之后用户自行修改
    admin_user = User.query.filter_by(username='admin').first()
    if not admin_user:
        admin_user = User(
            username='admin',
            nickname='管理员',
            is_active=True,
            is_admin=True
        )
        admin_user.set_password('admin123')
        db.session.add(admin_user)
        db.session.commit()
        print('默认管理员账号已创建 (username: admin / password: admin123)')
        print('请登录后立即修改密码！')
    
    scheduler.start()
    print("APScheduler started.")


if __name__ == '__main__':
    # 查找现有任务获取下次运行时间
    jobs = scheduler.get_jobs()
    next_run = "N/A"
    for j in jobs:
        if j.id == 'scheduled_data_update':
            try:
                next_run = str(j.next_run_time)
            except AttributeError:
                next_run = "已设置 (查看日志获取具体时间)"
            break
    print(f"下一次数据更新时间:  {next_run}")
    app.run(debug=True, host='0.0.0.0', port=5000) # 生产环境请关闭 debug
