# app.py
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import pytz # 用于处理时区
import os
import json
import time
import random
import string
from dotenv import load_dotenv
from utils import format_lottery_numbers, calculate_odd_even_sum # 导入 utils 中的函数
from prediction_engine import check_lottery_rules # 导入规则检查函数


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
from models import db, SSQDraw, DLTDraw, News, initialize_admin_route_prefix

# 初始化 Flask 应用
app = Flask(__name__, instance_relative_config=True)
app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = SQLALCHEMY_TRACK_MODIFICATIONS
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'super_secret_key_for_dev') # 生产环境务必设置强密钥

# 初始化 SQLAlchemy
db.init_app(app)

# 初始化 APScheduler
scheduler = BackgroundScheduler(timezone=pytz.timezone('Asia/Shanghai'))

# 导入数据管理模块
from data_manager import save_draw_data, get_latest_draws, update_latest_draws

# 导入路由
import routes
import admin_routes

# 注册蓝图或直接注册路由
app.register_blueprint(routes.bp)
app.register_blueprint(admin_routes.bp, url_prefix=f'/{ADMIN_ROUTE_PREFIX}')

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
        'calculate_odd_even_sum': calculate_odd_even_sum # 将函数传递给模板
    }

# 数据库初始化和定时任务启动
with app.app_context():
    db.create_all()
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
    scheduler.add_job(func=update_latest_draws, trigger="cron", hour=3, minute=0)
    scheduler.start()
    print("APScheduler started.")

# 首页路由 (示例，实际由 routes.py 处理)
# @app.route('/')
# def index():
#     latest_ssq = get_latest_draws(SSQDraw, 1)
#     latest_dlt = get_latest_draws(DLTDraw, 1)
#     homepage_news = News.query.filter_by(is_homepage_display=True, is_public=True).order_by(News.created_at.desc()).limit(3).all()
#     return render_template('index.html', latest_ssq=latest_ssq, latest_dlt=latest_dlt, homepage_news=homepage_news)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000) # 生产环境请关闭 debug

