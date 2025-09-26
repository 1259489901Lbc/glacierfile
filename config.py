import os
from datetime import timedelta


class Config:
    """应用配置类"""
    # Flask配置
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'ai-roleplay-secret-key-2024-enhanced'
    DEBUG = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'

    # Session配置
    PERMANENT_SESSION_LIFETIME = timedelta(days=30)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE = False  # 开发环境设为False

    # 文件上传配置
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    UPLOAD_FOLDER = 'uploads'
    ALLOWED_AUDIO_EXTENSIONS = {'wav', 'mp3', 'webm', 'ogg', 'm4a'}

    # AI模型配置 - 使用OpenAI兼容API
    AI_MODEL_PROVIDER = os.environ.get('AI_MODEL_PROVIDER', 'openai')

    # OpenAI兼容API配置
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
    OPENAI_API_BASE = os.environ.get('OPENAI_API_BASE', 'https://openai.qinlu.com/v1')
    OPENAI_MODEL = os.environ.get('OPENAI_MODEL', 'x-ai/grok-4-fast')

    # AI生成配置
    AI_TEMPERATURE = float(os.environ.get('AI_TEMPERATURE', '0.8'))
    AI_MAX_TOKENS = int(os.environ.get('AI_MAX_TOKENS', '800'))
    AI_TOP_P = float(os.environ.get('AI_TOP_P', '0.9'))
    AI_FREQUENCY_PENALTY = float(os.environ.get('AI_FREQUENCY_PENALTY', '0.5'))
    AI_PRESENCE_PENALTY = float(os.environ.get('AI_PRESENCE_PENALTY', '0.5'))

    # 语音通话专用配置
    VOICE_CALL_TEMPERATURE = float(os.environ.get('VOICE_CALL_TEMPERATURE', '0.7'))
    VOICE_CALL_MAX_TOKENS = int(os.environ.get('VOICE_CALL_MAX_TOKENS', '150'))  # 限制更短
    VOICE_CALL_FREQUENCY_PENALTY = float(os.environ.get('VOICE_CALL_FREQUENCY_PENALTY', '0.8'))  # 避免重复

    # 语音服务配置
    VOICE_SERVICE_PROVIDER = os.environ.get('VOICE_SERVICE_PROVIDER', 'browser')

    # Azure语音服务配置（可选）
    AZURE_SPEECH_KEY = os.environ.get('AZURE_SPEECH_KEY')
    AZURE_SPEECH_REGION = os.environ.get('AZURE_SPEECH_REGION', 'eastasia')

    # Google语音服务配置（可选）
    GOOGLE_CLOUD_CREDENTIALS = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')

    # 缓存配置
    CACHE_TYPE = 'simple'
    CACHE_DEFAULT_TIMEOUT = 300

    # 速率限制
    RATELIMIT_ENABLED = True
    RATELIMIT_DEFAULT = "100/hour"
    RATELIMIT_CHAT = "30/minute"

    # 日志配置
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_FILE = os.environ.get('LOG_FILE', 'app.log')

    # 性能优化配置
    RESPONSE_TIMEOUT = int(os.environ.get('RESPONSE_TIMEOUT', '30'))
    MAX_CONVERSATION_LENGTH = int(os.environ.get('MAX_CONVERSATION_LENGTH', '50'))
    MAX_MESSAGE_LENGTH = int(os.environ.get('MAX_MESSAGE_LENGTH', '2000'))

    # 数据库配置（未来扩展）
    DATABASE_URI = os.environ.get('DATABASE_URI', 'sqlite:///roleplay.db')

    @classmethod
    def get_ai_config(cls, provider=None):
        """获取特定AI服务商的配置"""
        provider = provider or cls.AI_MODEL_PROVIDER

        configs = {
            'openai': {
                'api_key': cls.OPENAI_API_KEY,
                'api_base': cls.OPENAI_API_BASE,
                'model': cls.OPENAI_MODEL,
                'temperature': cls.AI_TEMPERATURE,
                'max_tokens': cls.AI_MAX_TOKENS,
                'top_p': cls.AI_TOP_P,
                'frequency_penalty': cls.AI_FREQUENCY_PENALTY,
                'presence_penalty': cls.AI_PRESENCE_PENALTY
            }
        }

        return configs.get(provider, configs['openai'])

    @classmethod
    def validate_config(cls):
        """验证配置的完整性"""
        errors = []

        # 检查OpenAI兼容API配置
        if cls.AI_MODEL_PROVIDER == 'openai':
            if not cls.OPENAI_API_KEY:
                errors.append("API密钥未配置")
            elif not cls.OPENAI_API_KEY.startswith('sk-'):
                errors.append("API密钥格式不正确（应以sk-开头）")

            if not cls.OPENAI_API_BASE:
                errors.append("API基础URL未配置")
            elif not cls.OPENAI_API_BASE.startswith('http'):
                errors.append("API基础URL格式不正确")

            if not cls.OPENAI_MODEL:
                errors.append("模型名称未配置")

        # 检查语音服务配置
        if cls.VOICE_SERVICE_PROVIDER == 'azure' and not cls.AZURE_SPEECH_KEY:
            errors.append("Azure语音服务密钥未配置")
        elif cls.VOICE_SERVICE_PROVIDER == 'google' and not cls.GOOGLE_CLOUD_CREDENTIALS:
            errors.append("Google Cloud凭证未配置")

        return errors

    @classmethod
    def get_model_info(cls):
        """获取模型信息"""
        model_info = {
            'x-ai/grok-4-fast': {
                'name': 'Grok-4-Fast',
                'description': '快速响应的Grok模型',
                'max_tokens': 4096,
                'supports_stream': True
            },
            'gpt-4': {
                'name': 'GPT-4',
                'description': 'OpenAI GPT-4模型',
                'max_tokens': 8192,
                'supports_stream': True
            },
            'gpt-3.5-turbo': {
                'name': 'GPT-3.5 Turbo',
                'description': 'OpenAI GPT-3.5 Turbo模型',
                'max_tokens': 4096,
                'supports_stream': True
            }
        }
        return model_info.get(cls.OPENAI_MODEL, {
            'name': cls.OPENAI_MODEL,
            'description': '自定义模型',
            'max_tokens': 4096,
            'supports_stream': True
        })
