# models.py
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import random
import string

db = SQLAlchemy()

class LotteryDraw(db.Model):
    __abstract__ = True # 抽象基类，不创建表

    id = db.Column(db.Integer, primary_key=True)
    issue = db.Column(db.String(10), unique=True, nullable=False) # 期号
    draw_date = db.Column(db.Date, nullable=False) # 开奖日期
    red_balls = db.Column(db.String(50), nullable=False) # 红球，逗号分隔
    blue_balls = db.Column(db.String(20), nullable=False) # 蓝球，逗号分隔
    sales_amount = db.Column(db.BigInteger) # 销售额
    prize_pool = db.Column(db.BigInteger) # 奖池
    first_prize_count = db.Column(db.Integer)
    first_prize_amount = db.Column(db.BigInteger)
    # ... 其他奖项字段根据实际需求添加

    # 方便获取号码列表
    def get_red_balls_list(self):
        return sorted([int(x) for x in self.red_balls.split(',')])

    def get_blue_balls_list(self):
        return sorted([int(x) for x in self.blue_balls.split(',')])

    def __repr__(self):
        return f"<{self.__class__.__name__} {self.issue} - {self.draw_date}>"

class SSQDraw(LotteryDraw):
    __tablename__ = 'ssq_draws'
    # 双色球特有字段，如果需要可以添加，但目前LotteryDraw已包含主要信息
    # 红球出球顺序、销售额、奖池、各奖项数量和金额等都已在LotteryDraw中定义
    # 实际数据格式中还有红球出球顺序，这里简化为只存储开奖号码
    red_order = db.Column(db.String(50)) # 红球出球顺序
    second_prize_count = db.Column(db.Integer)
    second_prize_amount = db.Column(db.BigInteger)
    third_prize_count = db.Column(db.Integer)
    third_prize_amount = db.Column(db.BigInteger)
    fourth_prize_count = db.Column(db.Integer)
    fourth_prize_amount = db.Column(db.BigInteger)
    fifth_prize_count = db.Column(db.Integer)
    fifth_prize_amount = db.Column(db.BigInteger)
    sixth_prize_count = db.Column(db.Integer)
    sixth_prize_amount = db.Column(db.BigInteger)


class DLTDraw(LotteryDraw):
    __tablename__ = 'dlt_draws'
    # 大乐透特有字段
    red_order = db.Column(db.String(50)) # 红球出球顺序
    blue_order = db.Column(db.String(20)) # 蓝球出球顺序
    second_prize_count = db.Column(db.Integer)
    second_prize_amount = db.Column(db.BigInteger)
    third_prize_count = db.Column(db.Integer)
    third_prize_amount = db.Column(db.BigInteger)
    fourth_prize_count = db.Column(db.Integer)
    fourth_prize_amount = db.Column(db.BigInteger)
    fifth_prize_count = db.Column(db.Integer)
    fifth_prize_amount = db.Column(db.BigInteger)
    sixth_prize_count = db.Column(db.Integer)
    sixth_prize_amount = db.Column(db.BigInteger)
    seventh_prize_count = db.Column(db.Integer)
    seventh_prize_amount = db.Column(db.BigInteger)
    eighth_prize_count = db.Column(db.Integer)
    eighth_prize_amount = db.Column(db.BigInteger)
    ninth_prize_count = db.Column(db.Integer)
    ninth_prize_amount = db.Column(db.BigInteger)
    additional_first_prize_count = db.Column(db.Integer)
    additional_first_prize_amount = db.Column(db.BigInteger)
    additional_second_prize_count = db.Column(db.Integer)
    additional_second_prize_amount = db.Column(db.BigInteger)
    # 备用字段
    reserve1 = db.Column(db.String(100))
    reserve2 = db.Column(db.String(100))
    reserve3 = db.Column(db.String(100))
    reserve4 = db.Column(db.String(100))
    reserve5 = db.Column(db.String(100))


class News(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    image_url = db.Column(db.String(500))
    summary = db.Column(db.String(500))
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_homepage_display = db.Column(db.Boolean, default=False) # 是否在首页展示
    is_public = db.Column(db.Boolean, default=True) # 是否在公共区域展示 (后备)

class AdminSettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.Text)
    description = db.Column(db.String(255))
    data_type = db.Column(db.String(50), default='string') # 'string', 'integer', 'float', 'boolean', 'json'

# 首次运行生成随机管理路由前缀
def generate_admin_route_prefix():
    chars = string.ascii_lowercase + string.digits
    return ''.join(random.choice(chars) for _ in range(5))

# 在应用启动时检查并设置 ADMIN_ROUTE_PREFIX
def initialize_admin_route_prefix():
    from config import ADMIN_ROUTE_PREFIX
    if ADMIN_ROUTE_PREFIX == 'admin_xyz12': # 检查是否是默认值
        new_prefix = generate_admin_route_prefix()
        # 这里需要一种机制来持久化这个值，例如写入config.py或数据库
        # 简单起见，我们可以在第一次运行时打印出来，并提示用户更新环境变量或config.py
        print(f"首次运行，生成新的后台管理路由前缀: /{new_prefix}")
        print(f"请将 ADMIN_ROUTE_PREFIX 环境变量设置为 '{new_prefix}' 或手动修改 config.py")
        return new_prefix
    return ADMIN_ROUTE_PREFIX
