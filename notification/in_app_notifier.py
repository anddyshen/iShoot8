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
