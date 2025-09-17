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
    "prize_check_range": 10, # 对奖页面往前核对的期数范围，默认改为10期
    "fun_game_max_simulations": 20000000, # 趣味游戏最大模拟次数
    "ssq_draw_days": [2, 4, 7], # 周二、周四、周日
    "dlt_draw_days": [1, 3, 6], # 周一、周三、周六
    # "annual_holidays": [ # 默认春节和国庆后一周休息
        # {"start": "01-28", "duration_weeks": 1}, # 假设1月28日春节开始
        # {"start": "10-01", "duration_weeks": 1}  # 国庆
    # ],
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

# --- 统计维度解释文本 ---
STAT_EXPLANATIONS = {
    'red_frequency': "统计每个红球号码在指定范围内的出现次数和频率百分比。",
    'red_omission': "统计每个红球号码当前的遗漏期数和历史最大遗漏期数。",
    'red_size_ratio': "将红球号码范围划分为“大”和“小”两个区域，统计开奖号码中大小号的比例。双色球红球通常以17为界（1-16小，17-33大），大乐透前区以18为界（1-17小，18-35大）。",
    'red_prime_composite_ratio': "统计红球开奖号码中质数和合数的比例。质数：只能被1和自身整除的数（如2,3,5,7,11,13,17,19,23,29,31）。合数：除了1和自身外，还能被其他数整除的数（如4,6,8,9,10,12,14,15,16...）。1既非质数也非合数。",
    'red_012_way_ratio': "将红球号码除以3，根据余数分为0路、1路、2路。统计开奖号码中0路、1路、2路号码的比例。",
    'red_consecutive_groups': "统计红球开奖号码中连续数字的组数（例如：1,2,3 算一组）。",
    'red_max_consecutive_length': "统计红球开奖号码中最长连号的长度（例如：1,2,3,4 最长连号为4）。",
    'red_repeated_counts': "统计当前红球开奖号码与前一期红球开奖号码中重复出现的数字数量。",
    'red_span': "红球开奖号码中最大数字与最小数字之差。",
    'red_head': "红球开奖号码中最小的数字（龙头）。",
    'red_tail': "红球开奖号码中最大的数字（凤尾）。",
    'red_ac_value': "红球AC值是彩票号码组合中任意两个号码差值的绝对值，然后统计这些差值中不重复的个数，再减去 (N-1) (N为开奖号码个数)。AC值反映了号码的离散程度。",

    'blue_frequency': "统计每个蓝球号码在指定范围内的出现次数和频率百分比。",
    'blue_omission': "统计每个蓝球号码当前的遗漏期数和历史最大遗漏期数。",
    'blue_size_ratio': "将蓝球号码范围划分为“大”和“小”两个区域，统计开奖号码中大小号的比例。双色球蓝球通常以9为界（1-8小，9-16大），大乐透后区以7为界（1-6小，7-12大）。",
    'blue_prime_composite_ratio': "统计蓝球开奖号码中质数和合数的比例。质数：只能被1和自身整除的数。合数：除了1和自身外，还能被其他数整除的数。1既非质数也非合数。",
    'blue_012_way_ratio': "将蓝球号码除以3，根据余数分为0路、1路、2路。统计开奖号码中0路、1路、2路号码的比例。",
    'blue_repeated_counts': "统计当前蓝球开奖号码与前一期蓝球开奖号码中重复出现的数字数量。",
    'blue_head': "蓝球开奖号码中最小的数字（龙头）。",
    'blue_tail': "蓝球开奖号码中最大的数字（凤尾）。",
}

# --- 后台设置项的中文标题映射 ---
SETTING_LABELS_CHINESE = {
    'site_name': "网站名称",
    'site_description': "网站描述",
    'admin_username': "管理员用户名",
    'admin_password': "管理员密码",
    'ssq_data_source_url': "双色球数据源URL",
    'dlt_data_source_url': "大乐透数据源URL",
    'news_data_source_url': "新闻数据源URL",
    'history_page_size': "历史数据每页显示数量",
    'history_stats_range_default': "统计数据默认范围",
    
    # 大小号分界点
    'ssq_red_size_midpoint': "双色球红球大小号分界点",
    'ssq_blue_size_midpoint': "双色球蓝球大小号分界点",
    'dlt_front_size_midpoint': "大乐透前区大小号分界点",
    'dlt_back_size_midpoint': "大乐透后区大小号分界点",

    # 预测相关设置
    'prediction_latest_draws': "预测分析期数",
    'prediction_omitted_red_balls': "预测红球遗漏期数",
    'prediction_omitted_blue_balls': "预测蓝球遗漏期数",
    'prediction_generated_count': "预测生成号码组数",

    # 双色球预测规则权重/概率
    'ssq_blue_omit_latest_draws': "双色球蓝球遗漏分析期数",
    'ssq_blue_consecutive_3_prob': "双色球蓝球连号3期概率",
    'ssq_blue_consecutive_5_prob': "双色球蓝球连号5期概率",
    'ssq_red_omit_1_weight': "双色球红球遗漏1期权重",
    'ssq_red_omit_2_weight': "双色球红球遗漏2期权重",
    'ssq_red_omit_3_weight': "双色球红球遗漏3期权重",
    'ssq_red_omit_4_weight': "双色球红球遗漏4期权重",
    'ssq_red_omit_5_weight': "双色球红球遗漏5期权重",
    'ssq_red_omit_6_weight': "双色球红球遗漏6期权重",
    'ssq_red_consecutive_3_prob': "双色球红球连号3期概率",
    'ssq_red_consecutive_3_second_prob': "双色球红球连号3期第二次概率",
    'ssq_red_area_min_count': "双色球红球分区最小数量",
    'ssq_red_prev_2_draws_max_repeat': "双色球红球近2期最大重复数",
    'ssq_red_max_consecutive_balls': "双色球红球最大连号数量",
    'ssq_red_omit_12_prob': "双色球红球遗漏12期概率",
    'ssq_red_omit_13_prob': "双色球红球遗漏13期概率",
    'ssq_red_omit_14_prob': "双色球红球遗漏14期概率",
    
    # 大乐透预测规则权重/概率
    'dlt_blue_repeat_prob': "大乐透蓝球重复概率",
    'dlt_blue_consecutive_5_prob': "大乐透蓝球连号5期概率",
    'dlt_red_omit_1_weight': "大乐透红球遗漏1期权重",
    'dlt_red_omit_2_weight': "大乐透红球遗漏2期权重",
    'dlt_red_omit_3_weight': "大乐透红球遗漏3期权重",
    'dlt_red_omit_4_weight': "大乐透红球遗漏4期权重",
    'dlt_red_omit_5_weight': "大乐透红球遗漏5期权重",
    'dlt_red_consecutive_3_prob': "大乐透红球连号3期概率",
    'dlt_red_area_min_count': "大乐透红球分区最小数量",
    'dlt_red_prev_2_draws_max_repeat': "大乐透红球近2期最大重复数",
    'dlt_red_max_consecutive_balls': "大乐透红球最大连号数量",
    'dlt_red_omit_12_prob': "大乐透红球遗漏12期概率",
    'dlt_red_omit_13_prob': "大乐透红球遗漏13期概率",
    'dlt_red_omit_14_prob': "大乐透红球遗漏14期概率",

    # 对奖中心设置
    'prize_check_range': "对奖中心检查范围",
    'fun_game_max_simulations': "趣味游戏最大模拟次数",

    # 开奖日期设置
    'ssq_draw_days': "双色球开奖日 (周几)",
    'dlt_draw_days': "大乐透开奖日 (周几)",
    'annual_holidays': "年度节假日 (不更新数据)",

    # 蓝球近期出现频率规则
    'ssq_blue_recent_occurrence_draws': "双色球蓝球近期出现分析期数",
    'ssq_blue_recent_occurrence_threshold': "双色球蓝球近期出现频率阈值",
    'ssq_blue_recent_occurrence_weight': "双色球蓝球近期出现频率权重",
    'dlt_blue_recent_occurrence_draws': "大乐透蓝球近期出现分析期数",
    'dlt_blue_recent_occurrence_threshold': "大乐透蓝球近期出现频率阈值",
    'dlt_blue_recent_occurrence_weight': "大乐透蓝球近期出现频率权重",
}

# --- 中奖规则定义 ---
PRIZE_RULES = {
    'ssq': {
        'red_range': 33, # 红球范围 1-33
        'blue_range': 16, # 蓝球范围 1-16
        'prizes': [
            {'level': '一等奖', 'match_red': 6, 'match_blue': 1, 'amount': '浮动'},
            {'level': '二等奖', 'match_red': 6, 'match_blue': 0, 'amount': '浮动'},
            {'level': '三等奖', 'match_red': 5, 'match_blue': 1, 'amount': 3000},
            {'level': '四等奖', 'match_red': 5, 'match_blue': 0, 'amount': 200},
            {'level': '四等奖', 'match_red': 4, 'match_blue': 1, 'amount': 200},
            {'level': '五等奖', 'match_red': 4, 'match_blue': 0, 'amount': 10},
            {'level': '五等奖', 'match_red': 3, 'match_blue': 1, 'amount': 10},
            {'level': '六等奖', 'match_red': 2, 'match_blue': 1, 'amount': 5},
            {'level': '六等奖', 'match_red': 1, 'match_blue': 1, 'amount': 5},
            {'level': '六等奖', 'match_red': 0, 'match_blue': 1, 'amount': 5},
        ]
    },
    'dlt': {
        'red_range': 35, # 红球范围 1-35
        'blue_range': 12, # 蓝球范围 1-12
        'prizes': [
            {'level': '一等奖', 'match_red': 5, 'match_blue': 2, 'amount': '浮动'},
            {'level': '二等奖', 'match_red': 5, 'match_blue': 1, 'amount': '浮动'},
            {'level': '三等奖', 'match_red': 5, 'match_blue': 0, 'amount': 10000},
            {'level': '四等奖', 'match_red': 4, 'match_blue': 2, 'amount': 3000},
            {'level': '五等奖', 'match_red': 4, 'match_blue': 1, 'amount': 300},
            {'level': '六等奖', 'match_red': 3, 'match_blue': 2, 'amount': 200},
            {'level': '七等奖', 'match_red': 4, 'match_blue': 0, 'amount': 100},
            {'level': '八等奖', 'match_red': 3, 'match_blue': 1, 'amount': 15},
            {'level': '八等奖', 'match_red': 2, 'match_blue': 2, 'amount': 15},
            {'level': '九等奖', 'match_red': 3, 'match_blue': 0, 'amount': 5},
            {'level': '九等奖', 'match_red': 1, 'match_blue': 2, 'amount': 5},
            {'level': '九等奖', 'match_red': 2, 'match_blue': 1, 'amount': 5},
            {'level': '九等奖', 'match_red': 0, 'match_blue': 2, 'amount': 5},
        ]
    }
}
