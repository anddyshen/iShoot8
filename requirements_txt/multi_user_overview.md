# iShoot 多用户模式 - 实施总览

> 项目路径：d:\Projects\iShoot8
> 技术栈：Flask + SQLAlchemy + SQLite + Flask-Login + APScheduler
> 当前版本：1.6.3

## 实施阶段

| 阶段 | 内容 | 预估工时 | 前置依赖 |
|------|------|----------|----------|
| Phase 1 | 用户系统基础设施 | 2-3 天 | 无 |
| Phase 2 | 心仪号码功能 | 1-2 天 | Phase 1 |
| Phase 3 | 购买记录与ROI | 2-3 天 | Phase 2 |
| Phase 4 | 通知系统 | 3-4 天 | Phase 1 |

## 数据库新增表

| 表名 | 说明 |
|------|------|
| users | 用户表 |
| favorite_numbers | 心仪号码表 |
| purchased_numbers | 已购买号码表 |
| notification_logs | 通知记录表 |

## 新增文件

| 文件 | 说明 |
|------|------|
| auth_routes.py | 注册/登录/退出路由 |
| user_routes.py | 用户个人数据路由 |
| notification/__init__.py | 通知模块初始化 |
| notification/base.py | 通知基类 |
| notification/email_notifier.py | 邮件通知 |
| notification/synology_notifier.py | 群晖 Chat 通知 |
| notification/in_app_notifier.py | 站内通知 |
| notification/manager.py | 通知管理器 |
| templates/user/login.html | 用户登录页 |
| templates/user/register.html | 用户注册页 |
| templates/user/profile.html | 个人中心页 |
| templates/user/favorites.html | 心仪号码管理页 |
| templates/user/purchased.html | 购买记录页 |
| templates/user/roi_stats.html | ROI统计页 |
| templates/user/notification_settings.html | 通知配置页 |
| templates/user/notification_history.html | 通知历史页 |
| templates/admin/user_manage.html | 用户管理页（后台） |
| templates/components/favorite_btn.html | 收藏按钮组件 |
| static/js/user.js | 用户相关前端逻辑 |

## 修改文件

| 文件 | 修改内容 |
|------|----------|
| models.py | 新增 User、FavoriteNumbers、PurchasedNumbers、NotificationLog 模型 |
| app.py | 集成 Flask-Login，新增通知定时任务 |
| config.py | 新增注册开关、SMTP 等设置项 |
| admin_routes.py | 新增用户管理路由 |
| routes.py | 无需修改（新增的路由在独立文件中） |
| base.html | 导航栏增加登录/注册/用户菜单/通知图标 |

## 功能矩阵

| 功能 | 游客 | 注册用户 | 管理员 |
|------|------|----------|--------|
| 查看公开数据 | ✅ | ✅ | ✅ |
| 使用预测功能 | ✅ | ✅ | ✅ |
| 心仪号码收藏 | ❌ | ✅ | ✅ |
| 购买记录管理 | ❌ | ✅ | ✅ |
| ROI统计查看 | ❌ | ✅ | ✅ |
| 通知配置 | ❌ | ✅ | ✅ |
| 用户管理 | ❌ | ❌ | ✅ |
| 网站设置 | ❌ | ❌ | ✅ |
| 关闭注册开关 | ❌ | ❌ | ✅ |
