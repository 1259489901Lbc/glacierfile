import os
from typing import Dict, List, Optional


class Config:
    """应用配置类"""

    # Flask 基础配置
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key-here-change-in-production'
    DEBUG = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'

    # 文件上传配置
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB

    # AI 服务配置 - 兼容两种环境变量命名
    AI_MODEL_PROVIDER = os.environ.get('AI_MODEL_PROVIDER') or os.environ.get('AI_PROVIDER', 'openai')
    AI_API_KEY = os.environ.get('AI_API_KEY') or os.environ.get('OPENAI_API_KEY', '')
    AI_API_BASE = os.environ.get('AI_API_BASE') or os.environ.get('OPENAI_API_BASE', 'https://api.openai.com/v1')
    AI_MODEL = os.environ.get('AI_MODEL') or os.environ.get('OPENAI_MODEL', 'gpt-3.5-turbo')

    # AI 参数配置
    DEFAULT_TEMPERATURE = float(os.environ.get('AI_TEMPERATURE', '0.7'))
    DEFAULT_MAX_TOKENS = int(os.environ.get('AI_MAX_TOKENS', '1000'))
    DEFAULT_TOP_P = float(os.environ.get('AI_TOP_P', '1.0'))
    DEFAULT_FREQUENCY_PENALTY = float(os.environ.get('AI_FREQUENCY_PENALTY', '0.0'))
    DEFAULT_PRESENCE_PENALTY = float(os.environ.get('AI_PRESENCE_PENALTY', '0.0'))

    # 语音通话专用参数
    VOICE_CALL_TEMPERATURE = float(os.environ.get('VOICE_CALL_TEMPERATURE', '0.6'))
    VOICE_CALL_MAX_TOKENS = int(os.environ.get('VOICE_CALL_MAX_TOKENS', '150'))
    VOICE_CALL_FREQUENCY_PENALTY = float(os.environ.get('VOICE_CALL_FREQUENCY_PENALTY', '0.3'))

    # 语音服务配置
    VOICE_SERVICE_PROVIDER = os.environ.get('VOICE_SERVICE_PROVIDER', 'browser')

    # 对话限制
    MAX_CONVERSATION_LENGTH = int(os.environ.get('MAX_CONVERSATION_LENGTH', '20'))
    MAX_MESSAGE_LENGTH = int(os.environ.get('MAX_MESSAGE_LENGTH', '1000'))

    # 超时设置 - 针对不同网络环境调整
    RESPONSE_TIMEOUT = int(os.environ.get('RESPONSE_TIMEOUT', '60'))
    CONNECTION_TIMEOUT = int(os.environ.get('CONNECTION_TIMEOUT', '10'))

    # 重试配置
    MAX_RETRIES = int(os.environ.get('MAX_RETRIES', '3'))
    RETRY_DELAY = int(os.environ.get('RETRY_DELAY', '2'))

    # 数据库配置 (如果将来需要)
    DATABASE_URL = os.environ.get('DATABASE_URL', '')

    # Redis 配置 (如果将来需要缓存)
    REDIS_URL = os.environ.get('REDIS_URL', '')

    # 日志级别
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_FILE = os.environ.get('LOG_FILE', '')

    @classmethod
    def get_ai_config(cls) -> Dict:
        """获取AI服务配置"""
        return {
            'provider': cls.AI_MODEL_PROVIDER,
            'api_key': cls.AI_API_KEY,
            'api_base': cls.AI_API_BASE,
            'model': cls.AI_MODEL,
            'temperature': cls.DEFAULT_TEMPERATURE,
            'max_tokens': cls.DEFAULT_MAX_TOKENS,
            'top_p': cls.DEFAULT_TOP_P,
            'frequency_penalty': cls.DEFAULT_FREQUENCY_PENALTY,
            'presence_penalty': cls.DEFAULT_PRESENCE_PENALTY,
        }

    @classmethod
    def get_voice_config(cls) -> Dict:
        """获取语音服务配置"""
        return {
            'provider': cls.VOICE_SERVICE_PROVIDER,
        }

    @classmethod
    def validate_config(cls) -> List[str]:
        """验证配置，返回错误列表"""
        errors = []

        # 检查AI服务配置
        if not cls.AI_API_KEY:
            errors.append("AI_API_KEY 或 OPENAI_API_KEY 未设置")

        if not cls.AI_API_BASE:
            errors.append("AI_API_BASE 或 OPENAI_API_BASE 未设置")

        if not cls.AI_MODEL:
            errors.append("AI_MODEL 或 OPENAI_MODEL 未设置")

        # 检查参数范围
        if not (0.0 <= cls.DEFAULT_TEMPERATURE <= 2.0):
            errors.append("AI_TEMPERATURE 应在 0.0-2.0 范围内")

        if cls.DEFAULT_MAX_TOKENS <= 0:
            errors.append("AI_MAX_TOKENS 应大于 0")

        if not (0.0 <= cls.DEFAULT_TOP_P <= 1.0):
            errors.append("AI_TOP_P 应在 0.0-1.0 范围内")

        # 检查语音通话参数
        if not (0.0 <= cls.VOICE_CALL_TEMPERATURE <= 2.0):
            errors.append("VOICE_CALL_TEMPERATURE 应在 0.0-2.0 范围内")

        if cls.VOICE_CALL_MAX_TOKENS <= 0:
            errors.append("VOICE_CALL_MAX_TOKENS 应大于 0")

        return errors

    @classmethod
    def is_production(cls) -> bool:
        """检查是否为生产环境"""
        return os.environ.get('FLASK_ENV') == 'production'

    @classmethod
    def get_supported_providers(cls) -> Dict[str, Dict]:
        """获取支持的服务提供商"""
        return {
            'ai_providers': {
                'openai': {
                    'name': 'OpenAI',
                    'api_base': 'https://api.openai.com/v1',
                    'models': ['gpt-4', 'gpt-4-turbo', 'gpt-3.5-turbo']
                },
                'azure': {
                    'name': 'Azure OpenAI',
                    'api_base': 'https://your-resource.openai.azure.com',
                    'models': ['gpt-4', 'gpt-35-turbo']
                },
                'anthropic': {
                    'name': 'Anthropic',
                    'api_base': 'https://api.anthropic.com',
                    'models': ['claude-3-opus', 'claude-3-sonnet', 'claude-3-haiku']
                },
                'x-ai': {
                    'name': 'xAI',
                    'api_base': 'https://api.x.ai/v1',
                    'models': ['grok-4-fast', 'grok-beta']
                },
                'qiniu': {
                    'name': '七牛云OpenAI兼容服务',
                    'api_base': 'https://openai.qiniu.com/v1',
                    'models': ['x-ai/grok-4-fast', 'gpt-4', 'gpt-3.5-turbo']
                }
            },
            'voice_providers': {
                'browser': {
                    'name': '浏览器内置语音',
                    'description': '使用浏览器的Web Speech API'
                },
                'openai': {
                    'name': 'OpenAI TTS',
                    'description': 'OpenAI的文字转语音服务'
                },
                'azure': {
                    'name': 'Azure Speech',
                    'description': 'Azure认知服务语音'
                }
            }
        }


class DevelopmentConfig(Config):
    """开发环境配置"""
    DEBUG = True
    LOG_LEVEL = 'DEBUG'


class ProductionConfig(Config):
    """生产环境配置"""
    DEBUG = False
    LOG_LEVEL = 'WARNING'

    # 生产环境的安全配置
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'


class TestingConfig(Config):
    """测试环境配置"""
    TESTING = True
    DEBUG = True
    LOG_LEVEL = 'DEBUG'

    # 测试环境使用内存数据库
    DATABASE_URL = 'sqlite:///:memory:'


# 配置字典
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
