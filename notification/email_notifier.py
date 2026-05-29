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
        # 邮箱通知使用用户注册的邮箱，无需额外配置字段
        return []
    
    def send(self, user, title, content):
        """发送邮件"""
        config = user.notification_config.get('channel_configs', {}).get('email', {})
        to_email = config.get('email_address') or user.email
        
        if not to_email:
            return False, '未配置邮箱地址且注册时未填写邮箱'
        
        try:
            from flask_mail import Message
            
            # 使用 app 全局初始化的 Mail 实例
            mail = current_app.mail
            
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
                    app.mail.send(msg)
            
            Thread(target=send_async, args=(current_app._get_current_object(), msg)).start()
            
            return True, '邮件已发送'
            
        except Exception as e:
            current_app.logger.error(f"邮件发送失败: {e}")
            return False, str(e)
