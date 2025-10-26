# 阶段一：基础架构与数据准备

## 目标
建立支持趋势数据计算和存储的基础架构，确保数据模型能够高效处理历史开奖数据。

## 任务

### 1.1 数据模型扩展 (`models.py`, `data_manager.py`)
*   **行动：** 评估并修改现有数据模型，以支持存储和高效查询双色球和大乐透的详细历史开奖数据。
*   **输出：** 更新 `models.py` 和 `data_manager.py`，确保数据结构能够容纳所有必要的历史开奖数据。

### 1.2 趋势概率数据表设计与实现
*   **行动：** 设计并创建一张新的数据库表 `trend_probabilities`，用于存储预计算的各项趋势概率数据。
    *   **考虑字段：** `id`, `lottery_type` (彩种，例如 "SSQ", "DLT"), `lookback_period` (回溯期数，例如 5, 100), `trend_metric` (趋势指标类型，例如 "odd_even_ratio", "consecutive_numbers"), `metric_value` (具体指标值，例如 "3:3", "2_consecutive"), `probability` (概率值，例如 0.25), `distribution_data` (分布区间或详细数据，JSON格式), `last_calculated_at` (最后计算时间戳)。
*   **输出：** `models.py` 中新增 `TrendProbabilities` 模型，以及必要的数据库迁移脚本。

### 1.3 回溯期数配置管理
*   **行动：** 在后台管理界面 (`templates/admin/settings_ssq.html`, `templates/admin/settings_dlt.html`, `admin_routes.py`) 实现回溯期数选项的配置功能。
*   **输出：** 后台设置页面可配置回溯期数，并能动态生成前端下拉列表选项。
