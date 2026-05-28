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
