# iShoot 项目阶段性回顾 & 下一阶段工作清单

> 生成时间: 2026-05-28
> 项目版本: 1.6.3
> 技术栈: Flask + SQLAlchemy + SQLite + Flask-Login + APScheduler

---

## 一、总体进度概览

| 模块 | 总任务数 | 已完成 | 部分完成 | 未开始 | 完成度 |
|------|---------|-------|---------|-------|-------|
| **多用户系统 Phase 1** (用户系统) | 20 | 16 | 3 | 1 | ~85% |
| **多用户系统 Phase 2** (心仪号码) | 12 | 9 | 2 | 1 | ~80% |
| **多用户系统 Phase 3** (购买记录/ROI) | 15 | 6 | 4 | 5 | ~45% |
| **多用户系统 Phase 4** (通知系统) | 18 | 0 | 1 | 17 | ~3% |
| **趋势计算 Phase 1** (基础架构) | 5 | 4 | 1 | 0 | ~90% |
| **趋势计算 Phase 2** (红球趋势) | 11 | 3 | 5 | 3 | ~40% |
| **趋势计算 Phase 3** (蓝球趋势) | 2 | 0 | 1 | 1 | ~30% |
| **趋势计算 Phase 4** (预计算缓存) | 6 | 0 | 1 | 5 | ~10% |
| **趋势计算 Phase 5** (前后端集成) | 3 | 0 | 2 | 1 | ~30% |
| **趋势计算 Phase 6** (性能测试) | 2 | 0 | 0 | 2 | 0% |
| **智能筛选规则修复** (task_progress.md) | 8 | 0 | 0 | 8 | 0% |

---

## 二、已完成工作详细清单

### ✅ 多用户系统 - Phase 1: 用户系统基础设施 (~85%)

| 任务 | 状态 | 说明 |
|------|------|------|
| User 模型 (models.py) | ✅ 完成 | id, username, email, password_hash, nickname, is_active, is_admin, created_at, last_login_at, notification_config, preferences |
| Flask-Login 集成 (app.py) | ✅ 完成 | LoginManager 初始化, login_view 设置, user_loader 回调 |
| current_user 注入模板 | ✅ 完成 | 已添加到 inject_global_data 上下文处理器 |
| auth_routes 蓝图注册 | ✅ 完成 | app.py 中已导入并注册 |
| 注册路由 /auth/register | ✅ 完成 | 含验证逻辑、注册开关检查 |
| 登录路由 /auth/login | ✅ 完成 | 含 remember me、next 重定向、管理员跳转后台 |
| 退出路由 /auth/logout | ✅ 完成 | 清除会话、flash 提示 |
| 个人资料 API | ✅ 完成 | /api/me, /api/update_profile, /api/change_password |
| 默认管理员创建 | ✅ 完成 | app.py 启动时自动创建 admin/admin123 |
| 登录页面模板 | ✅ 完成 | templates/user/login.html |
| 注册页面模板 | ✅ 完成 | templates/user/register.html |
| 个人中心页面模板 | ✅ 完成 | templates/user/profile.html |
| 后台用户管理页面 | ✅ 完成 | templates/admin/user_manage.html |
| 导航栏登录状态 | ✅ 完成 | base.html 含登录/退出/用户菜单 |
| 管理员路由前缀 | ✅ 完成 | initialize_admin_route_prefix 函数 |
| 配置项集成 | ✅ 完成 | config.py 导入 CURRENT_SETTINGS |
| **❌ 用户管理后台路由** | ⚠️ 需验证 | admin_routes.py 中是否已实现 admin_users 路由 |
| **❌ 注册开关配置** | ⚠️ 需验证 | config.py 中 allow_registration 是否已添加到 GENERAL_SETTINGS_KEYS 和 SETTING_LABELS_CHINESE |
| **❌ 重置密码 API** | ⚠️ 需验证 | admin_routes.py 中 admin_reset_user_password 路由 |
| **❌ 禁用/启用用户 API** | ⚠️ 需验证 | admin_routes.py 中 admin_toggle_user_active 路由 |

### ✅ 多用户系统 - Phase 2: 心仪号码功能 (~80%)

| 任务 | 状态 | 说明 |
|------|------|------|
| UserFavorite 模型 | ✅ 完成 | models.py 中有完整实现 |
| 心仪号码 API (GET) | ✅ 完成 | 支持分页和彩种筛选 |
| 心仪号码 API (POST 添加) | ✅ 完成 | 含校验逻辑 |
| 心仪号码 API (PUT 更新) | ✅ 完成 | 支持更新备注 |
| 心仪号码 API (DELETE) | ✅ 完成 | 单条和批量删除 |
| 心仪号码管理页面 | ✅ 完成 | templates/user/favorites.html |
| **❌ 收藏按钮组件** | ❌ 未创建 | templates/components/favorite_btn.html 未在文件列表中 |
| **❌ 预测页面嵌入收藏按钮** | ❌ 未实现 | 需修改 templates/prediction.html |
| **❌ 对奖页面嵌入收藏按钮** | ❌ 未实现 | 需修改 templates/prize_check.html |
| **❌ 历史页面嵌入收藏按钮** | ❌ 未实现 | 需修改 templates/history.html |
| **❌ 前端 user.js 收藏逻辑** | ⚠️ 需检查 | static/js/user.js 是否存在，但文件列表中显示已创建 |
| **❌ 检查重复收藏** | ⚠️ 需验证 | 当前实现没有唯一约束或重复检查 |

### ✅ 多用户系统 - Phase 3: 购买记录与ROI (~45%)

| 任务 | 状态 | 说明 |
|------|------|------|
| UserPurchasedTicket 模型 | ✅ 完成 | models.py 中有完整实现 |
| 已购号码 API (GET) | ✅ 完成 | 支持分页和彩种筛选 |
| 已购号码 API (POST 添加) | ✅ 完成 | 添加时自动对奖 |
| 已购号码 API (PUT 更新) | ✅ 完成 | 更新后重新对奖 |
| 已购号码 API (DELETE) | ✅ 完成 | 单条和批量删除 |
| 批量对奖 API | ✅ 完成 | /api/purchased/check_all |
| **❌ ROI 统计页面** | ❌ 未创建 | templates/user/roi_stats.html 不在文件列表中 |
| **❌ ROI 统计 API** | ❌ 未实现 | /api/purchased/stats 不存在 |
| **❌ 剪贴板批量导入** | ❌ 未实现 | /api/purchased/batch_add 不存在 |
| **❌ 从心仪号码导入** | ❌ 未实现 | /api/purchased/import_favorite 不存在 |
| **❌ 复式注数自动计算** | ❌ 未实现 | calculate_auto_cost 函数不存在 |
| **❌ 自动对奖增强** | ⚠️ 部分实现 | _check_ticket_prize 已实现基础逻辑，但缺少完整的中奖详情返回 |
| **❌ ROI 排行榜** | ❌ 未实现 | 排名和月度统计缺失 |
| **❌ 月度趋势图表** | ❌ 未实现 | 需要 Chart.js 集成 |
| **❌ 重新对奖 API** | ❌ 未实现 | /api/purchased/recheck 不存在 |

### ❌ 多用户系统 - Phase 4: 通知系统 (~3%)

| 任务 | 状态 | 说明 |
|------|------|------|
| NotificationLog 模型 | ❌ 未实现 | models.py 中不存在 |
| notification/ 模块 | ❌ 未创建 | 整个目录不存在 |
| 通知管理器 | ❌ 未实现 | NotificationManager 类不存在 |
| 邮件通知器 | ❌ 未实现 | EmailNotifier 类不存在 |
| Synology Chat 通知器 | ❌ 未实现 | SynologyChatNotifier 类不存在 |
| 站内通知器 | ❌ 未实现 | InAppNotifier 类不存在 |
| 通知配置 API | ❌ 未实现 | GET/PUT /api/notifications/config 不存在 |
| 通知历史 API | ❌ 未实现 | /api/notifications 及相关端点不存在 |
| 通知设置页面 | ❌ 未创建 | templates/user/notification_settings.html 不存在 |
| 通知历史页面 | ❌ 未创建 | templates/user/notification_history.html 不存在 |
| 通知图标/下拉菜单 | ❌ 未实现 | base.html 中未添加 |
| 智能筛选推送定时任务 | ❌ 未实现 | run_smart_filter_notifications 不存在 |
| Flask-Mail 配置 | ❌ 未配置 | app.py 中 SMTP 配置缺失 |
| config.py SMTP 设置项 | ⚠️ 需检查 | 是否已添加到 DEFAULT_SETTINGS |
| 前端通知 JS 逻辑 | ❌ 未实现 | user.js 中未添加通知相关代码 |
| 测试通知 API | ❌ 未实现 | /api/notifications/test 不存在 |
| 未读通知计数 | ❌ 未实现 | unread_count 功能缺失 |
| 全部标记已读 | ❌ 未实现 | /api/notifications/read_all 不存在 |

### ✅ 趋势计算 - Phase 1: 基础架构与数据准备 (~90%)

| 任务 | 状态 | 说明 |
|------|------|------|
| TrendProbabilities 模型 | ✅ 完成 | models.py 中有完整实现 |
| SmartFilterStats 模型 | ✅ 完成 | 记录每期开奖号码的各规则实际值 |
| SmartFilterStatsRanking 模型 | ✅ 完成 | 各规则值频率排名（前3名），含不同回溯期数 |
| 回溯期数配置 | ✅ 完成 | AdminSettings.initialize_default_settings() 初始化 |
| **❌ 数据模型扩展** | ⚠️ 部分完成 | SSQDraw/DLTDraw 已有基础字段，但需要评估是否满足所有趋势计算需求 |

### ⚠️ 趋势计算 - Phase 2: 红球趋势计算 (~40%)

| 任务 | 状态 | 说明 |
|------|------|------|
| smart_filter_engine.py | ✅ 存在 | 文件中包含规则检查逻辑 |
| **❌ 奇偶比计算** | ⚠️ 需检查 | prediction_engine.py 中可能已实现 |
| **❌ 连号概率计算** | ⚠️ 需检查 | 同上 |
| **❌ 余数相同数量计算** | ⚠️ 需检查 | 同上 |
| **❌ 多期号码重复** | ⚠️ 需检查 | 同上 |
| **❌ 红球大小比** | ⚠️ 需检查 | 同上 |
| **❌ 红球质合比** | ⚠️ 需检查 | 同上 |
| **❌ 红球斜连号/跳号** | ⚠️ 需检查 | 同上 |
| **❌ 红球和值与均值** | ⚠️ 需检查 | 同上 |
| **❌ 红球跨度** | ⚠️ 需检查 | 同上 |
| **❌ 红球分区分布** | ⚠️ 需检查 | 同上 |
| **❌ 红球遗漏值分析** | ⚠️ 需检查 | 同上 |
> **注意**: 以上11个指标需要检查 prediction_engine.py 的实际实现情况

### ⚠️ 趋势计算 - Phase 3: 蓝球趋势计算 (~30%)

| 任务 | 状态 | 说明 |
|------|------|------|
| **❌ 双色球蓝球4种策略** | ⚠️ 需检查 | 热号、冷号回补、冷热平衡、遗漏值趋势 |
| **❌ 大乐透蓝球计算** | ⚠️ 需检查 | 奇偶比、大小比、质合比、遗漏值、4种策略 |

### ❌ 趋势计算 - Phase 4: 预计算与缓存 (~10%)

| 任务 | 状态 | 说明 |
|------|------|------|
| **❌ 4.1 预计算触发机制** | ❌ 未实现 | 数据更新后自动触发趋势计算 |
| **❌ 4.2 趋势数据存储** | ❌ 未实现 | TrendProbabilities 表读/写逻辑缺失 |
| **❌ 4.2 号码生成读取** | ❌ 未实现 | 优先从 TrendProbabilities 读取 |
| **❌ 4.3 缺失数据检测** | ❌ 未实现 | 即时计算触发条件 |
| **❌ 4.3 即时计算回填** | ❌ 未实现 | 按需计算并写入 |
| **❌ 异步任务处理** | ❌ 未实现 | 未使用 Celery 或类似方案 |

### ⚠️ 趋势计算 - Phase 5: 前后端集成 (~30%)

| 任务 | 状态 | 说明 |
|------|------|------|
| 后台SSQ设置页面 | ✅ 存在 | templates/admin/settings_ssq.html |
| 后台DLT设置页面 | ✅ 存在 | templates/admin/settings_dlt.html |
| 后台趋势设置页面 | ✅ 存在 | templates/admin/settings_trend.html |
| **❌ 筛选规则配置项** | ⚠️ 需检查 | 各规则的启用/禁用开关、参数设置等 |
| **❌ 规则组合逻辑** | ❌ 未实现 | AND/OR/Disable 组合配置 |
| **❌ 前端预测页面集成** | ⚠️ 部分实现 | 页面存在但需要验证完整集成 |

### ❌ 趋势计算 - Phase 6: 性能测试 (0%)

| 任务 | 状态 | 说明 |
|------|------|------|
| 性能优化 | ❌ 未开始 | 索引优化、缓存策略 |
| 功能测试 | ❌ 未开始 | 单元测试、集成测试 |

### ⚠️ 智能筛选规则修复 - task_progress.md

| 任务 | 状态 | 说明 |
|------|------|------|
| 修复 check_repeat_with_previous | ❌ 未开始 | 支持传入上期开奖数据参数 |
| 修复 check_neighbor_numbers | ❌ 未开始 | 支持传入上期开奖数据参数 |
| 修复 calculate_smart_filter_stats_for_draw | ❌ 未开始 | 支持基于指定期之前的数据计算遗漏 |
| 新增 check_user_numbers_against_smart_filter_rankings | ❌ 未开始 | 检查用户号码符合规则排名 |
| 新增 /api/prize_check/smart_filter_check API | ❌ 未开始 | 接受用户号码和彩票类型 |
| 修改前端 checkSmartFilterRules | ❌ 未开始 | 获取用户选中的号码调用新 API |
| 修复蓝球遗漏排名逻辑 | ❌ 未开始 | 获取正确的排名数据 |
| 测试修复效果 | ❌ 未开始 | 验证所有修复 |

---

## 三、下一阶段工作优先级建议

### 🔴 P0 - 最高优先级 (立即处理)

| # | 任务 | 所属模块 | 预估工时 | 说明 |
|---|------|---------|---------|------|
| 1 | **智能筛选规则修复 (task_progress.md 8项)** | 智能筛选 | 2-3天 | 用户无法正常使用智能筛选功能，直接影响核心体验 |
| 2 | **通知系统 Phase 4 完整实现** | 多用户 | 3-4天 | 需要完整的通知模块，包括站内通知、通知设置页面、通知历史页面、通知图标 |
| 3 | **ROI 统计功能 (Phase 3 缺失部分)** | 多用户 | 1-2天 | ROI统计页面、月度图表、排行榜、剪贴板导入 |

### 🟡 P1 - 高优先级 (下一迭代)

| # | 任务 | 所属模块 | 预估工时 | 说明 |
|---|------|---------|---------|------|
| 4 | **验证红球11项趋势计算完整性** | 趋势Phase2 | 1天 | 检查 prediction_engine.py 所有指标是否全实现 |
| 5 | **验证蓝球趋势计算完整性** | 趋势Phase3 | 1天 | 检查4种策略和双色球/大乐透是否都实现 |
| 6 | **Phase 4 预计算触发与存储** | 趋势Phase4 | 2天 | 数据更新后自动触发趋势计算并存储 |
| 7 | **收藏按钮跨页面嵌入 (Phase 2 缺失)** | 多用户 | 1天 | 在预测/对奖/历史页面添加收藏按钮 |

### 🟢 P2 - 中等优先级 (功能完善)

| # | 任务 | 所属模块 | 预估工时 | 说明 |
|---|------|---------|---------|------|
| 8 | **Phase 5 前后端集成** | 趋势Phase5 | 2天 | 筛选规则配置、规则组合逻辑 |
| 9 | **Phase 4 即时计算回填** | 趋势Phase4 | 2天 | 缺失数据检测与即时计算 |
| 10 | **遗漏项配置项检查** | 多用户Phase1 | 0.5天 | 确认 allow_registration、用户管理路由等已完善 |
| 11 | **后台用户管理路由完善** | 多用户Phase1 | 0.5天 | admin_users、toggle_active、reset_password 路由 |

### 🔵 P3 - 低优先级 (未来迭代)

| # | 任务 | 所属模块 | 预估工时 | 说明 |
|---|------|---------|---------|------|
| 12 | **Phase 6 性能测试** | 趋势Phase6 | 2天 | 压力测试、索引优化、缓存 |
| 13 | **从心仪号码导入到购买记录** | 多用户Phase3 | 0.5天 | 快捷导入功能 |
| 14 | **复式注数自动计算** | 多用户Phase3 | 0.5天 | 基于号码数量自动计算注数和花费 |
| 15 | **浮动奖金处理** | 多用户Phase3 | 1天 | 一等奖/二等奖的浮动奖金展示 |

---

## 四、依赖关系提醒

```
智能筛选修复 (P0) ───────────── 独立，可优先处理
       │
       ▼
通知系统 (P0) ──────────────── 依赖 Phase 1 (已就绪)
       │
       ▼
ROI统计 (P0) ────────────────── 依赖 Phase 1 (已就绪)，基础和 API 已部分实现
       │
       ▼
趋势计算验证 (P1) ───────────── 独立，检查现有代码
       │
       ▼
预计算缓存 (P1) ─────────────── 依赖 Phase 2&3 (需先验证完整性)
       │
       ▼
前后端集成 (P2) ─────────────── 依赖 Phase 2&3&4
```

---

## 五、文件状态清单

### 需要创建的新文件

| 文件 | 优先级 | 所属阶段 |
|------|--------|---------|
| notification/__init__.py | P0 | 多用户Phase4 |
| notification/base.py | P0 | 多用户Phase4 |
| notification/email_notifier.py | P0 | 多用户Phase4 |
| notification/synology_notifier.py | P0 | 多用户Phase4 |
| notification/in_app_notifier.py | P0 | 多用户Phase4 |
| notification/manager.py | P0 | 多用户Phase4 |
| templates/user/notification_settings.html | P0 | 多用户Phase4 |
| templates/user/notification_history.html | P0 | 多用户Phase4 |
| templates/user/roi_stats.html | P0 | 多用户Phase3 |
| templates/components/favorite_btn.html | P1 | 多用户Phase2 |

### 需要修改的现有文件

| 文件 | 修改内容 | 优先级 |
|------|---------|--------|
| models.py | 新增 NotificationLog 模型 | P0 |
| app.py | 通知管理器初始化、Flask-Mail配置 | P0 |
| config.py | SMTP设置项、注册开关配置检查 | P1 |
| auth_routes.py | 通知相关API（或新建user_routes.py） | P0 |
| admin_routes.py | 用户管理路由完善、筛选规则配置 | P1 |
| base.html | 通知图标/下拉菜单 | P0 |
| templates/prediction.html | 嵌入收藏按钮 | P1 |
| templates/prize_check.html | 嵌入收藏按钮、修复智能筛选检查 | P0 |
| templates/history.html | 嵌入收藏按钮 | P1 |
| static/js/user.js | 通知逻辑、收藏按钮逻辑 | P0 |
| static/js/script.js | 智能筛选检查修复 | P0 |
| prediction_engine.py | 智能筛选规则修复 | P0 |
| smart_filter_engine.py | 智能筛选规则修复 | P0 |

---

## 六、建议的开始步骤

1. **先修复智能筛选规则** (task_progress.md 的 8 项) - 这是当前最影响用户使用的功能
2. **实现通知系统** (Phase 4) - 这是多用户系统的"最后一公里"，让用户能收到开奖通知
3. **完成ROI统计** (Phase 3 缺失部分) - 让用户能看到投资回报数据
4. 然后逐步完善趋势计算的预计算缓存和前后端集成
