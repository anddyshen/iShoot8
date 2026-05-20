# config.py
import os
import json

# 项目版本号
__version__ = "1.5.8" # 更新版本号

# 网站基本信息
SITE_NAME = "iShoot"
SITE_URL = "ishoot.cc"
PER_BET_PRICE = 2 # 每注号码价格

# 数据源URL
SSQ_URL = "https://data.17500.cn/ssq_desc.txt"
DLT_URL = "https://data.17500.cn/dlt_desc.txt"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/76.0.3809.100 Safari/537.36"

# 数据库配置
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATABASE_PATH = os.path.join(BASE_DIR, 'instance', 'ishoot.db')
# 服务器上使用 MySQL（本地连接）
#SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://xmadmin:DPCLsDiFxnLDdHXw@localhost:3306/ishoot.cc?charset=utf8mb4'
SQLALCHEMY_DATABASE_URI = f'sqlite:///{DATABASE_PATH}'
SQLALCHEMY_TRACK_MODIFICATIONS = False

# 后台管理配置
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'default_admin_password') # 从环境变量获取，或使用默认值
ADMIN_ROUTE_PREFIX = os.environ.get('ADMIN_ROUTE_PREFIX', 'admin_xyz12') # 首次运行生成，可手动修改

# 网站设置参数 (可从后台修改)
DEFAULT_SETTINGS = {
    "history_page_size": 25,
    "prediction_latest_draws": 3, # 预测页面显示最新开奖期数
    "prediction_omitted_red_balls": 7, # 预测页面显示遗漏最多红球数量
    "prediction_omitted_blue_balls": 7, # 预测页面显示遗漏最多蓝球数量
    "prediction_generated_count": 5, # 预测页面默认生成号码组数
    "prediction_generation_mode": "rule_based", # 预测页面默认生成模式: "rule_based" 或 "random"
    "ssq_blue_omit_latest_draws": 2, # 蓝球如最新一期开出过的号码就不作为本期的预测候选号码
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
    "ssq_red_omit_prob_threshold_1": 0.015, # 遗漏降概率阈值1对应的概率
    "ssq_red_omit_prob_threshold_2": 0.0,   # 遗漏降概率阈值2对应的概率
    "ssq_red_omit_prob_threshold_3": 0.0,   # 遗漏降概率阈值3对应的概率
    "dlt_blue_repeat_prob": 0.035,
    "dlt_blue_consecutive_5_prob": 0.25,
    "dlt_red_omit_1_weight": 0.01,
    "dlt_red_omit_2_weight": 0.015,
    "dlt_red_omit_3_weight": 0.02,
    "dlt_red_omit_4_weight": 0.03,
    "dlt_red_omit_5_weight": 0.03,
    "dlt_red_omit_6_weight": 0.03, # 新增：大乐透红球遗漏6期权重
    "dlt_red_consecutive_3_prob": 0.35,
    "dlt_red_omit_prob_threshold_1": 0.015, # 遗漏降概率阈值1对应的概率
    "dlt_red_omit_prob_threshold_2": 0.0,   # 遗漏降概率阈值2对应的概率
    "dlt_red_omit_prob_threshold_3": 0.0,   # 遗漏降概率阈值3对应的概率
    # 新增：红球高遗漏降概率的阈值
    "ssq_red_omit_threshold_1": 12,
    "ssq_red_omit_threshold_2": 13,
    "ssq_red_omit_threshold_3": 14,
    "dlt_red_omit_threshold_1": 12,
    "dlt_red_omit_threshold_2": 13,
    "dlt_red_omit_threshold_3": 14,
    "prize_check_range": 10, # 对奖页面往前核对的期数范围，默认改为10期
    "fun_game_max_simulations": 20000000, # 趣味游戏最大模拟次数
    "fun_game_simulation_years": 500, # 趣味游戏模拟年份范围

    # 双色球红球趋势筛选规则
    'ssq_red_trend_rules': {
        'odd_even_ratio': {'enabled': False, 'params': {'target_ratio': '3:3'}, 'logic': 'AND'}, # 奇偶比
        'size_ratio': {'enabled': False, 'params': {'target_ratio': '3:3'}, 'logic': 'AND'}, # 大小比
        'prime_composite_ratio': {'enabled': False, 'params': {'target_ratio': '3:3'}, 'logic': 'AND'}, # 质合比
        'remainder_012_ratio': {'enabled': False, 'params': {'target_ratio': '2:2:2'}, 'logic': 'AND'}, # 012路比
        'consecutive_length': {'enabled': False, 'params': {'min_len': 2, 'max_len': 3, 'max_groups': 2}, 'logic': 'AND'}, # 连号长度和组数
        'sum_range': {'enabled': False, 'params': {'min_sum': 80, 'max_sum': 120}, 'logic': 'AND'}, # 和值范围
        'average_range': {'enabled': False, 'params': {'min_avg': 10, 'max_avg': 20}, 'logic': 'AND'}, # 均值范围
        'span_range': {'enabled': False, 'params': {'min_span': 15, 'max_span': 25}, 'logic': 'AND'}, # 跨度范围
        'ac_value_range': {'enabled': False, 'params': {'min_ac': 5, 'max_ac': 9}, 'logic': 'AND'}, # AC值范围
        'omission_range': {'enabled': False, 'params': {'min_omit': 0, 'max_omit': 5, 'omit_type': 'total'}, 'logic': 'AND'}, # 遗漏值范围 (total/individual)
        'prev_draw_repeat': {'enabled': False, 'params': {'min_repeat': 0, 'max_repeat': 1}, 'logic': 'AND'}, # 上期重复数
        'head_tail_range': {'enabled': False, 'params': {'min_head': 1, 'max_head': 5, 'min_tail': 28, 'max_tail': 33}, 'logic': 'AND'}, # 龙头凤尾
    },
    # 双色球蓝球趋势筛选规则
    'ssq_blue_trend_rules': {
        'odd_even_ratio': {'enabled': False, 'params': {'target_ratio': '1:0'}, 'logic': 'AND'}, # 奇偶比
        'size_ratio': {'enabled': False, 'params': {'target_ratio': '1:0'}, 'logic': 'AND'}, # 大小比
        'prime_composite_ratio': {'enabled': False, 'params': {'target_ratio': '1:0'}, 'logic': 'AND'}, # 质合比
        'remainder_012_ratio': {'enabled': False, 'params': {'target_ratio': '1:0:0'}, 'logic': 'AND'}, # 012路比
        'omission_range': {'enabled': False, 'params': {'min_omit': 0, 'max_omit': 5}, 'logic': 'AND'}, # 遗漏值范围
        'prev_draw_repeat': {'enabled': False, 'params': {'enabled': False}, 'logic': 'AND'}, # 上期重复数 (蓝球通常不重复，但可作为规则)
        'blue_strategy': {'enabled': False, 'params': {'strategy_type': 'recent_occurrence', 'threshold': 5, 'draws': 10}, 'logic': 'AND'}, # 蓝球策略
    },
    # 大乐透红球趋势筛选规则
    'dlt_red_trend_rules': {
        'odd_even_ratio': {'enabled': False, 'params': {'target_ratio': '3:2'}, 'logic': 'AND'}, # 奇偶比
        'size_ratio': {'enabled': False, 'params': {'target_ratio': '3:2'}, 'logic': 'AND'}, # 大小比
        'prime_composite_ratio': {'enabled': False, 'params': {'target_ratio': '3:2'}, 'logic': 'AND'}, # 质合比
        'remainder_012_ratio': {'enabled': False, 'params': {'target_ratio': '2:2:1'}, 'logic': 'AND'}, # 012路比
        'consecutive_length': {'enabled': False, 'params': {'min_len': 2, 'max_len': 3, 'max_groups': 2}, 'logic': 'AND'}, # 连号长度和组数
        'sum_range': {'enabled': False, 'params': {'min_sum': 90, 'max_sum': 140}, 'logic': 'AND'}, # 和值范围
        'average_range': {'enabled': False, 'params': {'min_avg': 15, 'max_avg': 25}, 'logic': 'AND'}, # 均值范围
        'span_range': {'enabled': False, 'params': {'min_span': 20, 'max_span': 30}, 'logic': 'AND'}, # 跨度范围
        'ac_value_range': {'enabled': False, 'params': {'min_ac': 6, 'max_ac': 10}, 'logic': 'AND'}, # AC值范围
        'omission_range': {'enabled': False, 'params': {'min_omit': 0, 'max_omit': 5, 'omit_type': 'total'}, 'logic': 'AND'}, # 遗漏值范围
        'prev_draw_repeat': {'enabled': False, 'params': {'min_repeat': 0, 'max_repeat': 1}, 'logic': 'AND'}, # 上期重复数
        'head_tail_range': {'enabled': False, 'params': {'min_head': 1, 'max_head': 5, 'min_tail': 30, 'max_tail': 35}, 'logic': 'AND'}, # 龙头凤尾
    },
    # 大乐透蓝球趋势筛选规则
    'dlt_blue_trend_rules': {
        'odd_even_ratio': {'enabled': False, 'params': {'target_ratio': '1:1'}, 'logic': 'AND'}, # 奇偶比
        'size_ratio': {'enabled': False, 'params': {'target_ratio': '1:1'}, 'logic': 'AND'}, # 大小比
        'prime_composite_ratio': {'enabled': False, 'params': {'target_ratio': '1:1'}, 'logic': 'AND'}, # 质合比
        'remainder_012_ratio': {'enabled': False, 'params': {'target_ratio': '1:1:0'}, 'logic': 'AND'}, # 012路比
        'omission_range': {'enabled': False, 'params': {'min_omit': 0, 'max_omit': 5}, 'logic': 'AND'}, # 遗漏值范围
        'prev_draw_repeat': {'enabled': False, 'params': {'enabled': False}, 'logic': 'AND'}, # 上期重复数
        'blue_strategy': {'enabled': False, 'params': {'strategy_type': 'recent_occurrence', 'threshold': 8, 'draws': 10}, 'logic': 'AND'}, # 蓝球策略
    },

    # 趣味游戏消息设置
    'fun_game_no_prize_message': "哇哦，看样子在这个世界里的未来{simulation_years}年没有命中一等奖了，让我们赶紧再次按动 大奖时光机 按钮，穿梭到其他的平行时空，看看能不能中到大奖。",
    'fun_game_prize_message': "恭喜你！在时光机中成功命中一等奖！预计在 {estimated_date} 左右中奖。",

    # 历史数据统计范围设置
    'history_stats_range_default': 100, # 默认统计最近100期
    'history_stats_range_options': [50, 100, 200, 500, 1000, 0], # 0 表示所有历史数据

    # 大小比划分界限
    'ssq_red_size_midpoint': 17, # 双色球红球 1-16 小，17-33 大
    'ssq_blue_size_midpoint': 9, # 双色球蓝球 1-8 小，9-16 大
    'dlt_front_size_midpoint': 18, # 大乐透前区 1-17 小，18-35 大
    'dlt_back_size_midpoint': 7, # 大乐透后区 1-6 小，7-12 大

    "lookback_periods": "50,100,200,500", # 趋势计算回溯期数选项

    # 定时更新设置
    "scheduled_update_enabled": True,
    "scheduled_update_hour": 3,
    "scheduled_update_minute": 15,
}

# 双色球参数键
SSQ_SETTINGS_KEYS = [
    'ssq_blue_omit_latest_draws',
    'ssq_blue_consecutive_3_prob',
    'ssq_blue_consecutive_5_prob',
    'ssq_red_omit_1_weight',
    'ssq_red_omit_2_weight',
    'ssq_red_omit_3_weight',
    'ssq_red_omit_4_weight',
    'ssq_red_omit_5_weight',
    'ssq_red_omit_6_weight',
    'ssq_red_consecutive_3_prob',
    'ssq_red_consecutive_3_second_prob',
    'ssq_red_omit_prob_threshold_1',
    'ssq_red_omit_prob_threshold_2',
    'ssq_red_omit_prob_threshold_3',
    'ssq_red_omit_threshold_1',
    'ssq_red_omit_threshold_2',
    'ssq_red_omit_threshold_3',
    'ssq_red_size_midpoint',
    'ssq_blue_size_midpoint',
    'ssq_red_trend_rules',
    'ssq_blue_trend_rules',
]

# 大乐透参数键
DLT_SETTINGS_KEYS = [
    'dlt_blue_repeat_prob',
    'dlt_blue_consecutive_5_prob',
    'dlt_red_omit_1_weight',
    'dlt_red_omit_2_weight',
    'dlt_red_omit_3_weight',
    'dlt_red_omit_4_weight',
    'dlt_red_omit_5_weight',
    'dlt_red_omit_6_weight',
    'dlt_red_consecutive_3_prob',
    'dlt_red_omit_prob_threshold_1',
    'dlt_red_omit_prob_threshold_2',
    'dlt_red_omit_prob_threshold_3',
    'dlt_red_omit_threshold_1',
    'dlt_red_omit_threshold_2',
    'dlt_red_omit_threshold_3',
    'dlt_front_size_midpoint',
    'dlt_back_size_midpoint',
    'dlt_red_trend_rules',
    'dlt_blue_trend_rules',
]

# 综合参数键
GENERAL_SETTINGS_KEYS = [
    'history_page_size',
    'prediction_latest_draws',
    'prediction_omitted_red_balls',
    'prediction_omitted_blue_balls',
    'prediction_generated_count',
    'prize_check_range',
    'fun_game_max_simulations',
    'fun_game_simulation_years',
    'fun_game_no_prize_message',
    'fun_game_prize_message',
    'history_stats_range_default',
    'history_stats_range_options',
    'site_name',
    'site_description',
    'admin_username',
    'admin_password',
    'news_data_source_url',
    'prediction_generation_mode', # 新增预测生成模式
]

# 趋势设置参数键
TREND_SETTINGS_KEYS = [
    'lookback_periods',
]

# 后台设置项的中文标题映射
SETTING_LABELS_CHINESE = {
    'site_name': "网站名称",
    'site_description': "网站描述",
    'admin_username': "管理员用户名",
    'admin_password': "管理员密码",
    'news_data_source_url': "新闻数据源URL",
    'history_page_size': "历史数据每页显示数量",
    'history_stats_range_default': "统计数据默认范围",
    
    # 大小号分界点
    'ssq_red_size_midpoint': "双色球红球大小号分界点",
    'ssq_blue_size_midpoint': "双色球蓝球大小号分界点",
    'dlt_front_size_midpoint': "大乐透前区大小号分界点",
    'dlt_back_size_midpoint': "大乐透后区大小号分界点",

    # 预测相关设置
    'prediction_latest_draws': "预测页面：显示最新开奖期数",
    'prediction_omitted_red_balls': "预测页面：显示遗漏最多红球数量",
    'prediction_omitted_blue_balls': "预测页面：显示遗漏最多蓝球数量",
    'prediction_generated_count': "预测页面：默认生成号码组数",
    'prediction_generation_mode': "预测页面：默认生成模式", # 新增预测生成模式

    # 双色球预测规则权重/概率
    'ssq_blue_omit_latest_draws': "双色球蓝球：遗漏分析期数",
    'ssq_blue_consecutive_3_prob': "双色球蓝球：连号3期概率",
    'ssq_blue_consecutive_5_prob': "双色球蓝球：连号5期概率",
    'ssq_red_omit_1_weight': "双色球红球：遗漏1期权重，每球平均概率 3.03%",
    'ssq_red_omit_2_weight': "双色球红球：遗漏2期权重",
    'ssq_red_omit_3_weight': "双色球红球：遗漏3期权重",
    'ssq_red_omit_4_weight': "双色球红球：遗漏4期权重",
    'ssq_red_omit_5_weight': "双色球红球：遗漏5期权重",
    'ssq_red_omit_6_weight': "双色球红球：遗漏6期权重",
    'ssq_red_consecutive_3_prob': "双色球红球：连号3期概率",
    'ssq_red_consecutive_3_second_prob': "双色球红球：连号3期第二次概率",
    'ssq_red_omit_prob_threshold_1': "双色球红球：遗漏降概率阈值1对应的概率",
    'ssq_red_omit_prob_threshold_2': "双色球红球：遗漏降概率阈值2对应的概率",
    'ssq_red_omit_prob_threshold_3': "双色球红球：遗漏降概率阈值3对应的概率",
    'ssq_red_omit_threshold_1': "双色球红球：遗漏降概率阈值1",
    'ssq_red_omit_threshold_2': "双色球红球：遗漏降概率阈值2",
    'ssq_red_omit_threshold_3': "双色球红球：遗漏降概率阈值3",
    
    'dlt_blue_repeat_prob': "大乐透蓝球：重复概率",
    'dlt_blue_consecutive_5_prob': "大乐透蓝球：连号5期概率",
    'dlt_red_omit_1_weight': "大乐透红球：遗漏1期权重，每球平均概率 2.857%",
    'dlt_red_omit_2_weight': "大乐透红球：遗漏2期权重",
    'dlt_red_omit_3_weight': "大乐透红球：遗漏3期权重",
    'dlt_red_omit_4_weight': "大乐透红球：遗漏4期权重",
    'dlt_red_omit_5_weight': "大乐透红球：遗漏5期权重",
    'dlt_red_omit_6_weight': "大乐透红球：遗漏6期权重",
    'dlt_red_consecutive_3_prob': "大乐透红球：连号3期概率",
    'dlt_red_omit_prob_threshold_1': "大乐透红球：遗漏降概率阈值1对应的概率",
    'dlt_red_omit_prob_threshold_2': "大乐透红球：遗漏降概率阈值2对应的概率",
    'dlt_red_omit_prob_threshold_3': "大乐透红球：遗漏降概率阈值3对应的概率",
    'dlt_red_omit_threshold_1': "大乐透红球：遗漏降概率阈值1",
    'dlt_red_omit_threshold_2': "大乐透红球：遗漏降概率阈值2",
    'dlt_red_omit_threshold_3': "大乐透红球：遗漏降概率阈值3",

    # 对奖中心设置
    'prize_check_range': "对奖中心：检查范围",
    'fun_game_max_simulations': "趣味游戏：最大模拟次数",

    # 开奖日期设置
    'fun_game_simulation_years': "趣味游戏：模拟年份范围",

    # 趣味游戏消息中文标签
    'fun_game_no_prize_message': "趣味游戏：未中奖消息",
    'fun_game_prize_message': "趣味游戏：中奖消息",

    # 趋势设置
    'lookback_periods': "趋势计算回溯期数",

    # 定时更新设置
    'scheduled_update_enabled': "启用定时更新",
    'scheduled_update_hour': "定时更新 - 小时(0-23)",
    'scheduled_update_minute': "定时更新 - 分钟(0-59)",

    # 新增趋势规则中文标签
    'ssq_red_trend_rules': "双色球红球趋势规则",
    'ssq_blue_trend_rules': "双色球蓝球趋势规则",
    'dlt_red_trend_rules': "大乐透红球趋势规则",
    'dlt_blue_trend_rules': "大乐透蓝球趋势规则",

    # 趋势规则名称中文标签
    'odd_even_ratio': "奇偶比",
    'size_ratio': "大小比",
    'prime_composite_ratio': "质合比",
    'remainder_012_ratio': "012路比",
    'consecutive_length': "连号长度和组数",
    'sum_range': "和值范围",
    'average_range': "均值范围",
    'span_range': "跨度范围",
    'ac_value_range': "AC值范围",
    'omission_range': "遗漏值范围",
    'prev_draw_repeat': "上期重复数",
    'head_tail_range': "龙头凤尾",
    'blue_strategy': "蓝球策略",

    # 趋势规则参数中文标签
    'target_ratio': "目标比例",
    'min_sum': "最小和值",
    'max_sum': "最大和值",
    'min_avg': "最小均值",
    'max_avg': "最大均值",
    'min_span': "最小跨度",
    'max_span': "最大跨度",
    'min_ac': "最小AC值",
    'max_ac': "最大AC值",
    'min_omit': "最小遗漏值",
    'max_omit': "最大遗漏值",
    'omit_type': "遗漏类型",
    'min_repeat': "最小重复数",
    'max_repeat': "最大重复数",
    'min_head': "最小龙头",
    'max_head': "最大龙头",
    'min_tail': "最小凤尾",
    'max_tail': "最大凤尾",
    'min_len': "最小连号长度",
    'max_len': "最大连号长度",
    'max_groups': "最大连号组数",
    'strategy_type': "策略类型",
    'threshold': "阈值",
    'draws': "分析期数",
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
        
        # 确保所有百分比相关的设置项在加载时都转换为小数形式
        percentage_keys = ['ssq_blue_consecutive_3_prob', 'ssq_blue_consecutive_5_prob', 'ssq_red_omit_1_weight', 'ssq_red_omit_2_weight', 'ssq_red_omit_3_weight', 'ssq_red_omit_4_weight', 'ssq_red_omit_5_weight', 'ssq_red_omit_6_weight', 'ssq_red_omit_prob_threshold_1', 'ssq_red_omit_prob_threshold_2', 'ssq_red_omit_prob_threshold_3', 'dlt_blue_repeat_prob', 'dlt_blue_consecutive_5_prob', 'dlt_red_omit_1_weight', 'dlt_red_omit_2_weight', 'dlt_red_omit_3_weight', 'dlt_red_omit_4_weight', 'dlt_red_omit_5_weight', 'dlt_red_omit_6_weight', 'dlt_red_consecutive_3_prob', 'dlt_red_omit_prob_threshold_1', 'dlt_red_omit_prob_threshold_2', 'dlt_red_omit_prob_threshold_3']
        for key in percentage_keys:
            if key in settings and isinstance(settings[key], (int, float)) and settings[key] > 1:
                settings[key] = settings[key] / 100
        
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
