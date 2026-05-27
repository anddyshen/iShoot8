# iShoot 多用户模式 - Phase 4：通知系统

> 预估工时：3-4 天
> 前置依赖：Phase 1（用户系统已就绪）
> 当前阶段目标：实现邮件、Synology Chat、站内通知三个渠道，以及开奖后自动智能筛选推送

## 需要安装的依赖

```bash
pip install flask-mail requests
```

## 需要修改/新增的文件

### 1. models.py - 新增 NotificationLog 模型

在 models.py 文件末尾新增：

```python
class NotificationLog(db.Model):
    """通知记录表"""
    __tablename__ = 'notification_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    channel = db.Column(db.String(20), nullable=False)  # email, synology_chat, in_app
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text)
    status = db.Column(db.String(20), default='pending')  # pending, sent, failed
    error_message = db.Column(db.String(500))
    is_read = db.Column(db.Boolean, default=False)       # 站内通知是否已读
    sent_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'channel': self.channel,
            'title': self.title,
            'content': self.content,
            'status': self.status,
            'is_read': self.is_read,
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
    
    def __repr__(self):
        return f'<NotificationLog {self.id} - {self.channel} - {self.status}>'
```

### 2. 创建 notification/ 模块

#### notification/__init__.py
```python
from notification.manager import NotificationManager

# 全局通知管理器实例
manager = NotificationManager()
```

#### notification/base.py
```python
from abc import ABC, abstractmethod

class BaseNotifier(ABC):
    """通知渠道基类"""
    
    @abstractmethod
    def send(self, user, title, content):
        """
        发送通知
        :param user: User 对象
        :param title: 通知标题
        :param content: 通知内容
        :return: (success: bool, message: str)
        """
        pass
    
    @abstractmethod
    def get_config_fields(self):
        """
        返回配置字段列表，用于前端渲染配置表单
        格式: [{'key': 'field_name', 'label': '字段名', 'type': 'text|password|url', 'required': True}]
        """
        return []
    
    @property
    @abstractmethod
    def channel_name(self):
        """渠道名称，用于标识"""
        return ''
    
    @property
    @abstractmethod
    def channel_label(self):
        """渠道中文显示名称"""
        return ''
```

#### notification/email_notifier.py
```python
from notification.base import BaseNotifier
from flask import current_app
from threading import Thread

class EmailNotifier(BaseNotifier):
    """邮件通知"""
    
    @property
    def channel_name(self):
        return 'email'
    
    @property
    def channel_label(self):
        return '📧 邮件通知'
    
    def get_config_fields(self):
        return [
            {'key': 'email_address', 'label': '接收邮箱', 'type': 'email', 'required': True,
             'placeholder': 'your@email.com'},
        ]
    
    def send(self, user, title, content):
        """发送邮件"""
        config = user.notification_config.get('email', {})
        to_email = config.get('email_address', user.email)
        
        if not to_email:
            return False, '未配置邮箱地址'
        
        try:
            from flask_mail import Mail, Message
            
            mail = Mail(current_app)
            
            # 构建 HTML 内容
            html_content = f"""
            <html>
            <head><style>
                body {{ font-family: Arial, sans-serif; padding: 20px; color: #333; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                          color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }}
                .content {{ line-height: 1.6; }}
                .footer {{ margin-top: 20px; font-size: 12px; color: #999; }}
                .balls {{ display: inline-block; margin: 2px; }}
                .red-ball {{ background: #dc3545; color: white; border-radius: 50%; 
                            width: 30px; height: 30px; display: inline-flex; align-items: center; 
                            justify-content: center; font-weight: bold; }}
                .blue-ball {{ background: #0d6efd; color: white; border-radius: 50%;
                            width: 30px; height: 30px; display: inline-flex; align-items: center;
                            justify-content: center; font-weight: bold; }}
            </style></head>
            <body>
                <div class="header">
                    <h2>🎯 {title}</h2>
                </div>
                <div class="content">
                    {content}
                </div>
                <div class="footer">
                    <p>来自 iShoot 彩票助手 | {current_app.config.get('SITE_URL', 'ishoot.cc')}</p>
                    <p>如需退订通知，请登录网站修改通知设置。</p>
                </div>
            </body>
            </html>
            """
            
            msg = Message(
                subject=title,
                recipients=[to_email],
                html=html_content,
                sender=current_app.config.get('MAIL_DEFAULT_SENDER')
            )
            
            # 异步发送
            def send_async(app, msg):
                with app.app_context():
                    mail.send(msg)
            
            Thread(target=send_async, args=(current_app._get_current_object(), msg)).start()
            
            return True, '邮件已发送'
            
        except Exception as e:
            current_app.logger.error(f"邮件发送失败: {e}")
            return False, str(e)
```

#### notification/synology_notifier.py
```python
from notification.base import BaseNotifier
import requests
from flask import current_app
import json

class SynologyChatNotifier(BaseNotifier):
    """群晖 Synology Chat 通知"""
    
    @property
    def channel_name(self):
        return 'synology_chat'
    
    @property
    def channel_label(self):
        return '💬 Synology Chat'
    
    def get_config_fields(self):
        return [
            {'key': 'webhook_url', 'label': 'Webhook URL', 'type': 'url', 'required': True,
             'placeholder': 'https://your-nas:5001/webapi/entry.cgi?api=SYNO...'},
            {'key': 'bot_name', 'label': '机器人名称', 'type': 'text', 'required': False,
             'placeholder': 'iShoot 彩票助手'},
        ]
    
    def send(self, user, title, content):
        """通过 Synology Chat Webhook 发送消息"""
        config = user.notification_config.get('synology_chat', {})
        webhook_url = config.get('webhook_url', '')
        
        if not webhook_url:
            return False, '未配置 Webhook URL'
        
        try:
            # 构建消息（支持 Markdown）
            message = f"**{title}**\n\n{content}\n\n---\n*来自 iShoot 彩票助手*"
            
            payload = {
                'text': message,
            }
            
            if config.get('bot_name'):
                payload['username'] = config['bot_name']
            
            headers = {'Content-Type': 'application/json'}
            
            response = requests.post(
                webhook_url,
                data=json.dumps(payload),
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                return True, '消息已发送到 Synology Chat'
            else:
                return False, f'Synology Chat 返回错误: {response.status_code}'
                
        except requests.exceptions.Timeout:
            return False, '连接 Synology Chat 超时'
        except requests.exceptions.ConnectionError:
            return False, '无法连接 Synology Chat，请检查网络和地址'
        except Exception as e:
            current_app.logger.error(f"Synology Chat 发送失败: {e}")
            return False, str(e)
```

#### notification/in_app_notifier.py
```python
from notification.base import BaseNotifier
from models import db, NotificationLog
from datetime import datetime
from flask import current_app

class InAppNotifier(BaseNotifier):
    """站内通知"""
    
    @property
    def channel_name(self):
        return 'in_app'
    
    @property
    def channel_label(self):
        return '🔔 站内通知'
    
    def get_config_fields(self):
        return []  # 站内通知无需额外配置
    
    def send(self, user, title, content):
        """保存站内通知到数据库"""
        try:
            notification = NotificationLog(
                user_id=user.id,
                channel='in_app',
                title=title,
                content=content,
                status='sent',
                sent_at=datetime.utcnow(),
            )
            db.session.add(notification)
            db.session.commit()
            return True, '站内通知已发送'
        except Exception as e:
            current_app.logger.error(f"站内通知保存失败: {e}")
            return False, str(e)
```

#### notification/manager.py
```python
"""通知管理器 - 统一管理各通知渠道的注册和发送"""
from flask import current_app
from models import db, NotificationLog
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class NotificationManager:
    """通知管理器"""
    
    def __init__(self):
        self._notifiers = {}
    
    def register(self, notifier):
        """注册通知渠道"""
        self._notifiers[notifier.channel_name] = notifier
        logger.info(f"通知渠道已注册: {notifier.channel_label}")
    
    def get_notifier(self, channel_name):
        """获取指定渠道的通知器"""
        return self._notifiers.get(channel_name)
    
    def get_all_notifiers(self):
        """获取所有注册的通知渠道"""
        return list(self._notifiers.values())
    
    def get_available_channels(self):
        """获取所有可用渠道的列表"""
        return [
            {
                'name': n.channel_name,
                'label': n.channel_label,
                'config_fields': n.get_config_fields(),
            }
            for n in self._notifiers.values()
        ]
    
    def send_to_user(self, user, title, content, channels=None):
        """
        根据用户配置的渠道发送通知
        
        :param user: User 对象
        :param title: 通知标题
        :param content: 通知内容 (支持 HTML/Markdown)
        :param channels: 指定渠道列表，为 None 时使用用户配置
        :return: [(channel, success, message), ...]
        """
        if channels is None:
            # 从用户配置中获取启用的渠道
            channels = user.notification_config.get('enabled_channels', ['in_app'])
        
        if not channels:
            channels = ['in_app']  # 至少使用站内通知
        
        results = []
        
        for channel_name in channels:
            notifier = self._notifiers.get(channel_name)
            if not notifier:
                results.append((channel_name, False, f'未知的渠道: {channel_name}'))
                continue
            
            # 发送通知
            success, message = notifier.send(user, title, content)
            
            # 记录日志
            self._log_notification(user.id, channel_name, title, content, success, message)
            
            results.append((channel_name, success, message))
        
        return results
    
    def send_smart_filter_result(self, user, lottery_type, numbers, rules_summary=None):
        """
        发送智能筛选结果通知
        
        :param user: User 对象
        :param lottery_type: 'ssq' 或 'dlt'
        :param numbers: 生成的号码列表 [(red_balls, blue_balls), ...]
        :param rules_summary: 使用的规则摘要
        """
        type_label = '双色球' if lottery_type == 'ssq' else '大乐透'
        
        # 构建号码文本
        numbers_text = ''
        for i, (red, blue) in enumerate(numbers[:5], 1):  # 最多显示5组
            red_str = ', '.join(map(str, red)) if isinstance(red, list) else red
            blue_str = ', '.join(map(str, blue)) if isinstance(blue, list) else blue
            numbers_text += f"\n{i}. 🔴 {red_str}  🔵 {blue_str}"
        
        if len(numbers) > 5:
            numbers_text += f"\n... 及其他 {len(numbers) - 5} 组"
        
        # 构建内容
        title = f"🎯 iShoot 智能筛选推荐 - {type_label}"
        
        content = f"""
        <h3>📊 {type_label} 智能筛选结果</h3>
        <p>根据您的筛选偏好，为您推荐以下号码组合：</p>
        <pre style="background:#f5f5f5; padding:15px; border-radius:5px; font-size:16px;">
{numbers_text}
        </pre>
        """
        
        if rules_summary:
            content += f"\n<p><strong>📋 筛选依据：</strong>{rules_summary}</p>"
        
        content += "\n<p>💡 请理性投注，量力而行。</p>"
        
        return self.send_to_user(user, title, content)
    
    def _log_notification(self, user_id, channel, title, content, success, message):
        """记录通知发送日志"""
        try:
            log = NotificationLog(
                user_id=user_id,
                channel=channel,
                title=title,
                content=content,
                status='sent' if success else 'failed',
                error_message=None if success else message,
                sent_at=datetime.utcnow(),
            )
            db.session.add(log)
            db.session.commit()
        except Exception as e:
            logger.error(f"通知日志记录失败: {e}")
```

### 3. 在 user_routes.py 中添加通知相关 API

追加以下路由：

```python
# ==============================
# 通知系统 API
# ==============================

@bp.route('/notification_settings')
@login_required
def notification_settings():
    """通知设置页面"""
    return render_template('user/notification_settings.html')

@bp.route('/notification_history')
@login_required
def notification_history():
    """通知历史页面"""
    return render_template('user/notification_history.html')


@bp.route('/api/notifications', methods=['GET'])
@login_required
def api_get_notifications():
    """获取通知列表"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    channel = request.args.get('channel')  # 可选筛选
    
    query = NotificationLog.query.filter_by(user_id=current_user.id)
    
    if channel:
        query = query.filter_by(channel=channel)
    
    query = query.order_by(NotificationLog.created_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    
    return jsonify({
        'notifications': [n.to_dict() for n in pagination.items],
        'total': pagination.total,
        'page': pagination.page,
        'pages': pagination.pages,
        'unread_count': NotificationLog.query.filter_by(
            user_id=current_user.id, 
            is_read=False,
            channel='in_app'
        ).count(),
    })


@bp.route('/api/notifications/unread_count', methods=['GET'])
@login_required
def api_unread_count():
    """获取未读站内通知数"""
    count = NotificationLog.query.filter_by(
        user_id=current_user.id,
        is_read=False,
        channel='in_app'
    ).count()
    return jsonify({'unread_count': count})


@bp.route('/api/notifications/<int:notif_id>/read', methods=['POST'])
@login_required
def api_mark_notification_read(notif_id):
    """标记通知为已读"""
    notification = NotificationLog.query.filter_by(
        id=notif_id, 
        user_id=current_user.id
    ).first()
    
    if not notification:
        return jsonify({'error': '通知不存在'}), 404
    
    notification.is_read = True
    db.session.commit()
    return jsonify({'message': '已标记为已读'})


@bp.route('/api/notifications/read_all', methods=['POST'])
@login_required
def api_read_all_notifications():
    """全部标记为已读"""
    NotificationLog.query.filter_by(
        user_id=current_user.id,
        is_read=False,
        channel='in_app'
    ).update({'is_read': True})
    
    db.session.commit()
    return jsonify({'message': '已全部标记为已读'})


@bp.route('/api/notifications/config', methods=['GET'])
@login_required
def api_get_notification_config():
    """获取用户的通知配置"""
    from notification.manager import manager as notif_manager
    
    config = current_user.notification_config or {}
    available_channels = notif_manager.get_available_channels()
    
    return jsonify({
        'enabled': config.get('enabled', False),
        'enabled_channels': config.get('enabled_channels', ['in_app']),
        'channel_configs': config.get('channel_configs', {}),
        'smart_filter_prefs': config.get('smart_filter_prefs', {
            'lottery_types': ['ssq', 'dlt'],
            'count': 5,
        }),
        'frequency': config.get('frequency', 'after_draw'),  # after_draw, daily, weekly
        'available_channels': available_channels,
    })


@bp.route('/api/notifications/config', methods=['PUT'])
@login_required
def api_update_notification_config():
    """更新用户的通知配置"""
    data = request.get_json()
    
    if not current_user.notification_config:
        current_user.notification_config = {}
    
    config = current_user.notification_config
    
    if 'enabled' in data:
        config['enabled'] = data['enabled']
    if 'enabled_channels' in data:
        config['enabled_channels'] = data['enabled_channels']
    if 'channel_configs' in data:
        if 'channel_configs' not in config:
            config['channel_configs'] = {}
        for channel, cfg in data['channel_configs'].items():
            config['channel_configs'][channel] = cfg
    if 'smart_filter_prefs' in data:
        config['smart_filter_prefs'] = data['smart_filter_prefs']
    if 'frequency' in data:
        config['frequency'] = data['frequency']
    
    db.session.commit()
    return jsonify({'message': '通知配置已更新'})


@bp.route('/api/notifications/test', methods=['POST'])
@login_required
def api_test_notification():
    """发送测试通知"""
    from notification.manager import manager as notif_manager
    
    data = request.get_json()
    channel = data.get('channel', 'in_app')
    
    title = "🔔 iShoot 测试通知"
    content = """
    <h4>✅ 通知渠道测试成功！</h4>
    <p>如果您收到这条消息，说明通知配置正确。</p>
    <p>您将可以正常接收智能筛选推荐通知。</p>
    <hr>
    <p style="color:#999; font-size:12px;">iShoot 彩票助手</p>
    """
    
    results = notif_manager.send_to_user(current_user, title, content, channels=[channel])
    
    return jsonify({
        'results': [
            {'channel': r[0], 'success': r[1], 'message': r[2]}
            for r in results
        ]
    })
```

### 4. 通知设置页面

**templates/user/notification_settings.html** 主要内容：
- **总开关**：启用/禁用通知
- **通知渠道选择**：
  - ✅ 站内通知（默认开启，不可关闭）
  - ✅ 邮件通知（需配置邮箱地址）
  - ✅ Synology Chat（需配置 Webhook URL）
- **各渠道配置表单**（根据 get_config_fields 动态渲染）：
  - 邮件：输入接收邮箱
  - Synology Chat：输入 Webhook URL、机器人名称
  - 每个渠道都有"测试"按钮
- **筛选偏好**：
  - 彩种选择（SSQ / DLT / 两者）
  - 生成组数（1-20）
- **通知频率**：
  - 每期开奖后（默认）
  - 每日汇总
  - 每周汇总

### 5. 通知历史页面

**templates/user/notification_history.html** 主要内容：
- **筛选**：按渠道、按状态
- **通知列表**：时间、渠道、标题、内容、状态
- 支持全部标记已读
- 分页

### 6. 在 app.py 中初始化通知模块

在 app.py 的启动初始化区域添加：

```python
# 在 with app.app_context(): 块中
with app.app_context():
    db.create_all()
    # ... 现有初始化代码 ...
    
    # 初始化通知管理器
    from notification import manager as notif_manager
    from notification.email_notifier import EmailNotifier
    from notification.synology_notifier import SynologyChatNotifier
    from notification.in_app_notifier import InAppNotifier
    
    notif_manager.register(EmailNotifier())
    notif_manager.register(SynologyChatNotifier())
    notif_manager.register(InAppNotifier())
    
    print("通知系统已初始化 (邮件/Synology Chat/站内通知)")
```

### 7. 配置 Flask-Mail

在 app.py 中配置邮件服务（在 app.config 中）：

```python
# 邮件配置
app.config['MAIL_SERVER'] = CURRENT_SETTINGS.get('smtp_server', '')
app.config['MAIL_PORT'] = CURRENT_SETTINGS.get('smtp_port', 587)
app.config['MAIL_USERNAME'] = CURRENT_SETTINGS.get('smtp_username', '')
app.config['MAIL_PASSWORD'] = CURRENT_SETTINGS.get('smtp_password', '')
app.config['MAIL_USE_TLS'] = CURRENT_SETTINGS.get('smtp_use_tls', True)
app.config['MAIL_DEFAULT_SENDER'] = (
    CURRENT_SETTINGS.get('smtp_from_name', 'iShoot 彩票助手'),
    CURRENT_SETTINGS.get('smtp_username', '')
)
```

### 8. 智能筛选通知定时任务

在 app.py 的定时任务区域（或 run_update.py）添加：

```python
def run_smart_filter_notifications(app_instance):
    """
    开奖后智能筛选通知任务
    在数据更新完成后触发，为每个启用通知的用户生成筛选结果并推送
    """
    with app_instance.app_context():
        from notification import manager as notif_manager
        from models import User, SSQDraw, DLTDraw
        from smart_filter_engine import generate_smart_filtered_numbers
        from config import CURRENT_SETTINGS
        
        logger = app_instance.logger
        logger.info("开始执行智能筛选通知任务...")
        
        # 获取最新期号信息
        latest_ssq = SSQDraw.query.order_by(SSQDraw.issue.desc()).first()
        latest_dlt = DLTDraw.query.order_by(DLTDraw.issue.desc()).first()
        
        # 查询所有启用通知且开启智能筛选的用户
        users = User.query.filter_by(is_active=True).all()
        sent_count = 0
        
        for user in users:
            config = user.notification_config or {}
            if not config.get('enabled', False):
                continue
            
            prefs = config.get('smart_filter_prefs', {})
            lottery_types = prefs.get('lottery_types', ['ssq', 'dlt'])
            count = prefs.get('count', 5)
            
            for lt in lottery_types:
                try:
                    # 生成智能筛选号码
                    # 注意：这里需要根据用户的筛选偏好来生成
                    # 简化处理：使用默认选项生成
                    options = {}  # 可以从 user.preferences 中读取用户自定义的筛选规则
                    numbers = generate_smart_filtered_numbers(lt, count, options)
                    
                    if not numbers:
                        continue
                    
                    # 提取号码对
                    number_pairs = []
                    for n in numbers:
                        red = n.get('red_balls', '')
                        blue = n.get('blue_balls', '')
                        number_pairs.append((red, blue))
                    
                    # 发送通知
                    results = notif_manager.send_smart_filter_result(
                        user, lt, number_pairs,
                        rules_summary='基于智能筛选规则'
                    )
                    
                    sent_count += 1
                    
                    for channel, success, msg in results:
                        logger.info(
                            f"通知 [{channel}] 发送给用户 {user.username}: "
                            f"{'成功' if success else '失败'} - {msg}"
                        )
                        
                except Exception as e:
                    logger.error(f"为用户 {user.username} 生成 {lt} 筛选结果时出错: {e}")
        
        logger.info(f"智能筛选通知任务完成，共发送 {sent_count} 条通知")
        return sent_count
```

将此函数添加到 APScheduler 中，在数据更新完成后触发：

```python
# 在 scheduler 中添加任务（在 setup_scheduled_job 函数中或单独添加）
def setup_scheduled_job(app_instance):
    """设置或更新定时任务"""
    global scheduler
    
    # 移除现有任务
    for job in scheduler.get_jobs():
        if job.id in ('scheduled_data_update', 'smart_filter_notification'):
            job.remove()
    
    # ... 现有数据更新任务设置 ...
    
    # 添加智能筛选通知任务（在数据更新后30分钟执行）
    if enabled:
        scheduler.add_job(
            func=run_smart_filter_notifications,
            trigger="cron",
            hour=hour,
            minute=(minute + 30) % 60,  # 数据更新后30分钟
            args=[app_instance],
            id='smart_filter_notification'
        )
```

### 9. 在 base.html 添加通知图标

在导航栏的用户菜单旁添加通知图标：

```html
{% if current_user.is_authenticated %}
<li class="nav-item dropdown">
    <a class="nav-link position-relative" href="#" role="button" data-bs-toggle="dropdown" id="notificationDropdown">
        🔔
        <span class="position-absolute top-0 start-100 translate-middle badge rounded-pill bg-danger" 
              id="unread-badge" style="font-size:10px; display:none;">0</span>
    </a>
    <ul class="dropdown-menu dropdown-menu-end" id="notification-menu" style="width:350px; max-height:500px; overflow-y:auto;">
        <li><h6 class="dropdown-header">通知</h6></li>
        <li><div id="notification-list"><p class="text-center text-muted py-3">加载中...</p></div></li>
        <li><hr class="dropdown-divider"></li>
        <li><a class="dropdown-item text-center" href="{{ url_for('user_routes.notification_history') }}">查看全部通知</a></li>
    </ul>
</li>
{% endif %}
```

### 10. 前端 JavaScript 补充

在 **static/js/user.js** 中追加通知相关逻辑：

```javascript
// ===== 通知功能 =====

// 加载未读通知数
function loadUnreadCount() {
    $.ajax({
        url: '/user/api/notifications/unread_count',
        method: 'GET',
        success: function(resp) {
            const badge = $('#unread-badge');
            if (resp.unread_count > 0) {
                badge.text(resp.unread_count).show();
            } else {
                badge.hide();
            }
        }
    });
}

// 加载最近通知列表
function loadRecentNotifications() {
    $.ajax({
        url: '/user/api/notifications',
        method: 'GET',
        data: { per_page: 5, page: 1 },
        success: function(resp) {
            const list = $('#notification-list');
            if (resp.notifications.length === 0) {
                list.html('<p class="text-center text-muted py-3">暂无通知</p>');
                return;
            }
            
            let html = '';
            resp.notifications.forEach(function(n) {
                const icon = n.channel === 'email' ? '📧' : 
                           n.channel === 'synology_chat' ? '💬' : '🔔';
                const isRead = n.is_read ? '' : 'fw-bold';
                const time = new Date(n.created_at).toLocaleString('zh-CN');
                html += `
                    <li>
                        <a class="dropdown-item ${isRead}" href="#" style="white-space:normal;">
                            <small class="text-muted">${icon} ${time}</small><br>
                            ${n.title}
                        </a>
                    </li>
                `;
            });
            list.html(html);
        }
    });
}

// 初始化通知
$(document).ready(function() {
    if ($('#unread-badge').length) {
        loadUnreadCount();
        // 每60秒刷新未读计数
        setInterval(loadUnreadCount, 60000);
        
        // 点击通知下拉时加载列表
        $('#notificationDropdown').on('click', function() {
            loadRecentNotifications();
        });
    }
});
```

### 11. config.py - 新增 SMTP 设置项

在 DEFAULT_SETTINGS 中添加：
```python
# 邮件服务设置
"smtp_server": "",
"smtp_port": 587,
"smtp_username": "",
"smtp_password": "",
"smtp_use_tls": True,
"smtp_from_name": "iShoot 彩票助手",
```

在 GENERAL_SETTINGS_KEYS 中添加：
```python
'smtp_server',
'smtp_port',
'smtp_username',
'smtp_password',
'smtp_use_tls',
'smtp_from_name',
```

在 SETTING_LABELS_CHINESE 中添加：
```python
'smtp_server': 'SMTP 服务器',
'smtp_port': 'SMTP 端口',
'smtp_username': 'SMTP 用户名',
'smtp_password': 'SMTP 密码',
'smtp_use_tls': 'SMTP 使用 TLS',
'smtp_from_name': '邮件发件人名称',
```

## 测试清单

- [ ] 站内通知可以正常发送和显示
- [ ] 通知图标显示未读数量
- [ ] 点击通知下拉查看最近通知
- [ ] 全部标记已读功能正常
- [ ] 通知配置页面可正常查看和修改
- [ ] 邮件通知测试发送成功
- [ ] Synology Chat 通知测试发送成功
- [ ] 用户禁用通知后不再接收
- [ ] 通知历史页面正常显示所有记录
- [ ] 定时任务可正常触发智能筛选并推送
- [ ] 不同用户的通知相互隔离
