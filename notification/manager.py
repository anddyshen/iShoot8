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
