# config.py
import os
import json

# 项目版本号
__version__ = "1.0.0" # 每次生成文件时更新此版本号

# 网站基本信息
SITE_NAME = "iShoot"
SITE_URL = "ishoot.fm787.uk"
PER_BET_PRICE = 2 # 每注号码价格

# 数据源URL
SSQ_URL = "https://data.17500.cn/ssq_desc.txt"
DLT_URL = "https://data.17500.cn/dlt_desc.txt"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/76.0.3809.100 Safari/537.36"

# 数据库配置
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATABASE_PATH = os.path.join(BASE_DIR, 'instance', 'ishoot.db')
SQLALCHEMY_DATABASE_URI = f'sqlite:///{DATABASE_PATH}'
SQLALCHEMY_TRACK_MODIFICATIONS = False

# 后台管理配置
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'default_admin_password') # 从环境变量获取，或使用默认值
ADMIN_ROUTE_PREFIX = os.environ.get('ADMIN_ROUTE_PREFIX', 'admin_xyz12') # 首次运行生成，可手动修改

# 网站设置参数 (可从后台修改)
DEFAULT_SETTINGS = {
    "history_page_size": 25,
    "prediction_latest_draws": 3,
    "prediction_omitted_red_balls": 7,
    "prediction_omitted_blue_balls": 7,
    "prediction_generated_count": 10,
    "ssq_blue_omit_latest_draws": 1, # 蓝球如最新一期开出过的号码就不作为本期的预测候选号码
    "ssq_blue_consecutive_3_prob": 0.08,
    "ssq_blue_consecutive_5_prob": 0.35,
    "ssq_red_omit_1_weight": 0.01,
    "ssq_red_omit_2_weight": 0.015,
    "ssq_red_omit_3_weight": 0.02,
    "ssq_red_omit_4_weight": 0.03,
    "ssq_red_omit_5_weight": 0.03,
    "ssq_red_omit_6_weight": 0.03,
    "ssq_red_consecutive_3_prob": 0.35,
    "ssq_red_consecutive_3_second_prob": 0.0,
    "ssq_red_area_min_count": 2,
    "ssq_red_prev_2_draws_max_repeat": 2,
    "ssq_red_max_consecutive_balls": 3, # 不出现连续4个及以上数字
    "ssq_red_omit_12_prob": 0.015,
    "ssq_red_omit_13_prob": 0.0,
    "ssq_red_omit_14_prob": 0.0,
    "dlt_blue_repeat_prob": 0.035,
    "dlt_blue_consecutive_5_prob": 0.25,
    "dlt_red_omit_1_weight": 0.01,
    "dlt_red_omit_2_weight": 0.015,
    "dlt_red_omit_3_weight": 0.02,
    "dlt_red_omit_4_weight": 0.03,
    "dlt_red_omit_5_weight": 0.03,
    "dlt_red_consecutive_3_prob": 0.35,
    "dlt_red_area_min_count": 2,
    "dlt_red_prev_2_draws_max_repeat": 2,
    "dlt_red_max_consecutive_balls": 3,
    "dlt_red_omit_12_prob": 0.015,
    "dlt_red_omit_13_prob": 0.0,
    "dlt_red_omit_14_prob": 0.0,
    "prize_check_range": 1, # 兑奖页面往前核对的期数范围
    "ssq_draw_days": [2, 4, 7], # 周二、周四、周日
    "dlt_draw_days": [1, 3, 6], # 周一、周三、周六 (原需求是1,2,6，但双色球周二，大乐透周二会冲突，改为周三)
    "annual_holidays": [ # 默认春节和国庆后一周休息
        {"start": "01-28", "duration_weeks": 1}, # 假设1月28日春节开始
        {"start": "10-01", "duration_weeks": 1}  # 国庆
    ],
    # 双色球蓝球最新出现频率规则 (4.1.11)
    'ssq_blue_recent_occurrence_draws': 10,      # 检查前10期
    'ssq_blue_recent_occurrence_threshold': 5,   # 出现5次以上
    'ssq_blue_recent_occurrence_weight': 0.40,   # 概率变为40%

    # 大乐透蓝球最新出现频率规则 (4.2.11)
    'dlt_blue_recent_occurrence_draws': 10,      # 检查前10期
    'dlt_blue_recent_occurrence_threshold': 8,   # 出现8次以上
    'dlt_blue_recent_occurrence_weight': 0.40,   # 概率变为40%

    # 历史数据统计范围设置
    'history_stats_range_default': 100, # 默认统计最近100期
    'history_stats_range_options': [50, 100, 200, 500, 1000, 0], # 0 表示所有历史数据

    # 历史数据统计范围设置
    'history_stats_range_default': 100, # 默认统计最近100期
    'history_stats_range_options': [50, 100, 200, 500, 1000, 0], # 0 表示所有历史数据

    # 大小比划分界限
    'ssq_red_size_midpoint': 17, # 双色球红球 1-16 小，17-33 大
    'ssq_blue_size_midpoint': 9, # 双色球蓝球 1-8 小，9-16 大
    'dlt_front_size_midpoint': 18, # 大乐透前区 1-17 小，18-35 大
    'dlt_back_size_midpoint': 7, # 大乐透后区 1-6 小，7-12 大

}

SETTINGS_FILE = os.path.join(BASE_DIR, 'instance', 'settings.json')

def load_settings():
    if not os.path.exists(SETTINGS_FILE):
        os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(DEFAULT_SETTINGS, f, indent=4, ensure_ascii=False)
        return DEFAULT_SETTINGS
    with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
        settings = json.load(f)
        # 合并默认设置，确保新参数有默认值
        for key, value in DEFAULT_SETTINGS.items():
            if key not in settings:
                settings[key] = value
        return settings

def save_settings(settings):
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(settings, f, indent=4, ensure_ascii=False)

# 加载初始设置
CURRENT_SETTINGS = load_settings()

# 确保 instance 目录存在
os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
