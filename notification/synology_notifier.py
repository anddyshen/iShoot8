from notification.base import BaseNotifier
import requests
from flask import current_app
import json
import urllib3

# 抑制自签名证书的 SSL 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class SynologyChatNotifier(BaseNotifier):
    """群晖 Synology Chat 通知"""
    
    @property
    def channel_name(self):
        return 'synology_chat'
    
    @property
    def channel_label(self):
        return 'Synology Chat'
    
    def get_config_fields(self):
        return [
            {'key': 'webhook_url', 'label': 'Webhook URL', 'type': 'url', 'required': True,
             'placeholder': 'https://your-nas:5001/webapi/entry.cgi?api=SYNO...'},
            {'key': 'bot_name', 'label': '机器人名称', 'type': 'text', 'required': False,
             'placeholder': 'iShoot'},
        ]
    
    def send(self, user, title, content):
        """通过 Synology Chat Webhook 发送消息"""
        config = user.notification_config.get('channel_configs', {}).get('synology_chat', {})
        webhook_url = config.get('webhook_url', '')
        
        if not webhook_url:
            return False, '未配置 Webhook URL'
        
        try:
            # 构建消息
            message = f"**{title}**\n\n{content}\n\n---\n*来自 iShoot*"
            
            # Synology Chat 的 payload 格式：使用 payload 参数
            payload = {'payload': json.dumps({'text': message})}
            
            if config.get('bot_name'):
                payload['username'] = config['bot_name']
            
            response = requests.post(
                webhook_url,
                data=payload,
                verify=False,  # 跳过自签名证书验证
                timeout=15
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    return True, '消息已发送到 Synology Chat'
                else:
                    error_code = result.get('error', {}).get('code')
                    if error_code == 800:
                        return False, '机器人未配置目标用户/频道，请在 Synology Chat 中将机器人添加到频道或为机器人指定目标用户'
                    else:
                        return False, f'Synology Chat 返回错误: {result}'
            else:
                return False, f'Synology Chat 返回错误: HTTP {response.status_code}'
                
        except requests.exceptions.Timeout:
            return False, '连接 Synology Chat 超时'
        except requests.exceptions.ConnectionError as e:
            return False, f'无法连接 Synology Chat: {e}'
        except Exception as e:
            current_app.logger.error(f"Synology Chat 发送失败: {e}")
            return False, str(e)
