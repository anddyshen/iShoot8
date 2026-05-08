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

    @staticmethod
    def initialize_default_settings():
        # Default lookback periods for trend calculations, including 0 for all periods
        default_lookback_periods = "5,10,20,50,100,200,0"
        setting = AdminSettings.query.filter_by(key='lookback_periods').first()
        if not setting:
            new_setting = AdminSettings(
                key='lookback_periods',
                value=default_lookback_periods,
                description='Comma-separated list of lookback periods for trend calculations (e.g., 5,10,20,50,100,200,0 where 0 means all history)',
                data_type='string'
            )
            db.session.add(new_setting)
            db.session.commit()
            print(f"Initialized default lookback_periods setting: {default_lookback_periods}")

class TrendProbabilities(db.Model):
    __tablename__ = 'trend_probabilities'

    id = db.Column(db.Integer, primary_key=True)
    lottery_type = db.Column(db.String(10), nullable=False) # 彩种，例如 "SSQ", "DLT"
    lookback_period = db.Column(db.Integer, nullable=False) # 回溯期数，例如 5, 100
    trend_metric = db.Column(db.String(100), nullable=False) # 趋势指标类型，例如 "odd_even_ratio", "consecutive_numbers"
    metric_value = db.Column(db.String(100), nullable=False) # 具体指标值，例如 "3:3", "2_consecutive"
    probability = db.Column(db.Float, nullable=False) # 概率值，例如 0.25
    distribution_data = db.Column(db.JSON) # 分布区间或详细数据，JSON格式
    last_calculated_at = db.Column(db.DateTime, default=datetime.utcnow) # 最后计算时间戳

    __table_args__ = (db.UniqueConstraint('lottery_type', 'lookback_period', 'trend_metric', 'metric_value', name='_lottery_trend_uc'),)

    def __repr__(self):
        return f"<TrendProbabilities {self.lottery_type}-{self.lookback_period}-{self.trend_metric}-{self.metric_value}>"


class SmartFilterStats(db.Model):
    """
    智能筛选规则统计表
    记录每期开奖号码的智能筛选规则实际值，并统计各值出现的频率（取前3名）
    """
    __tablename__ = 'smart_filter_stats'

    id = db.Column(db.Integer, primary_key=True)
    lottery_type = db.Column(db.String(10), nullable=False)  # 'ssq' 或 'dlt'
    issue = db.Column(db.String(10), nullable=False)  # 期号
    draw_date = db.Column(db.Date, nullable=False)  # 开奖日期
    rule_name = db.Column(db.String(50), nullable=False)  # 规则名称，如 'zone_ratio', 'odd_even', 'sum' 等
    rule_value = db.Column(db.String(100), nullable=False)  # 该期该规则的实际值，如 '2:2:2', '3:3', '102' 等
    created_at = db.Column(db.DateTime, default=datetime.utcnow)  # 记录创建时间

    __table_args__ = (
        db.Index('idx_smart_filter_stats_lottery_issue', 'lottery_type', 'issue'),
        db.Index('idx_smart_filter_stats_rule', 'lottery_type', 'rule_name', 'rule_value'),
    )

    def __repr__(self):
        return f"<SmartFilterStats {self.lottery_type}-{self.issue}-{self.rule_name}={self.rule_value}>"


class SmartFilterStatsRanking(db.Model):
    """
    智能筛选规则值排名表
    记录每个规则各值出现的频率，取前3名，按频率降序排列
    每次更新数据时重新计算
    按不同回溯期数分别统计（50, 100, 200, 500, 0=全部）
    """
    __tablename__ = 'smart_filter_stats_ranking'

    id = db.Column(db.Integer, primary_key=True)
    lottery_type = db.Column(db.String(10), nullable=False)  # 'ssq' 或 'dlt'
    lookback_period = db.Column(db.Integer, nullable=False, default=100)  # 回溯期数: 50, 100, 200, 500, 0(全部)
    rule_name = db.Column(db.String(50), nullable=False)  # 规则名称
    rule_value = db.Column(db.String(100), nullable=False)  # 规则值
    frequency = db.Column(db.Integer, nullable=False)  # 出现次数
    percentage = db.Column(db.Float, nullable=False, default=0.0)  # 出现百分比 (0-100)
    rank = db.Column(db.Integer, nullable=False)  # 排名 (1, 2, 3)
    total_draws = db.Column(db.Integer, nullable=False)  # 统计的总期数
    last_updated_issue = db.Column(db.String(10), nullable=False)  # 最后更新时的期号
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)  # 更新时间

    __table_args__ = (
        db.UniqueConstraint('lottery_type', 'lookback_period', 'rule_name', 'rank', name='_smart_filter_ranking_uc'),
    )

    def __repr__(self):
        return f"<SmartFilterStatsRanking {self.lottery_type}-{self.lookback_period}-{self.rule_name} #{self.rank}: {self.rule_value}({self.frequency}/{self.percentage:.1f}%)>"


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
