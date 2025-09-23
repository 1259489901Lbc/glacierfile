import os
import random
import time
import json
import requests
import logging
from typing import List, Optional, Dict, Any, Generator
from datetime import datetime
from models import Character, Message, ChatSession, CharacterRepository, ChatRepository
from config import Config
import base64

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AIService:
    """AI服务类 - OpenAI兼容API"""

    def __init__(self):
        self.provider = Config.AI_MODEL_PROVIDER
        self.config = Config.get_ai_config()
        self.current_model = self.config.get('model', 'unknown')
        self.timeout = Config.RESPONSE_TIMEOUT

        # 验证配置
        config_errors = Config.validate_config()
        if config_errors:
            logger.warning(f"AI服务配置警告: {', '.join(config_errors)}")

    def is_configured(self) -> bool:
        """检查AI服务是否已配置"""
        return not bool(Config.validate_config())

    def get_available_models(self) -> List[str]:
        """获取可用的AI模型列表"""
        return [
            'x-ai/grok-4-fast',
            'gpt-4',
            'gpt-4-turbo',
            'gpt-3.5-turbo',
            'claude-3-opus',
            'claude-3-sonnet'
        ]

    def generate_response(self, character: Character, user_message: str,
                          conversation_history: List[Message] = None) -> str:
        """生成角色回复"""
        # 构建消息
        messages = self._build_messages(character, user_message, conversation_history)

        try:
            return self._call_openai_compatible(messages, character)
        except Exception as e:
            logger.error(f"AI服务错误: {str(e)}")
            return self._generate_fallback_response(character, user_message)

    def generate_response_stream(self, character: Character, user_message: str,
                                 conversation_history: List[Message] = None) -> Generator[str, None, None]:
        """流式生成角色回复"""
        messages = self._build_messages(character, user_message, conversation_history)

        try:
            yield from self._stream_openai_compatible(messages, character)
        except Exception as e:
            logger.error(f"流式生成错误: {str(e)}")
            yield f"抱歉，我遇到了一些问题: {str(e)}"

    def _build_messages(self, character: Character, user_message: str,
                        conversation_history: List[Message] = None) -> List[Dict[str, str]]:
        """构建API消息格式"""
        messages = [
            {"role": "system", "content": character.get_system_prompt()}
        ]

        # 添加历史消息
        if conversation_history:
            # 限制上下文长度
            max_context = Config.MAX_CONVERSATION_LENGTH
            recent_messages = conversation_history[-max_context:] if len(
                conversation_history) > max_context else conversation_history

            for msg in recent_messages:
                role = "user" if msg.sender_type == "user" else "assistant"
                messages.append({"role": role, "content": msg.content})

        # 添加当前消息
        messages.append({"role": "user", "content": user_message})

        return messages

    def _call_openai_compatible(self, messages: List[Dict], character: Character) -> str:
        """调用OpenAI兼容API"""
        try:
            logger.info(f"正在调用API，模型: {self.config['model']}")

            headers = {
                "Authorization": f"Bearer {self.config['api_key']}",
                "Content-Type": "application/json"
            }

            data = {
                "model": self.config['model'],
                "messages": messages,
                "temperature": max(0.0, min(1.0, self.config['temperature'] + character.temperature_modifier)),
                "max_tokens": self.config['max_tokens'],
                "top_p": self.config['top_p'],
                "frequency_penalty": self.config.get('frequency_penalty', 0.0),
                "presence_penalty": self.config.get('presence_penalty', 0.0),
                "stream": False
            }

            logger.info(f"请求URL: {self.config['api_base']}/chat/completions")
            logger.info(f"请求数据: {json.dumps(data, ensure_ascii=False, indent=2)}")

            response = requests.post(
                f"{self.config['api_base']}/chat/completions",
                headers=headers,
                json=data,
                timeout=self.timeout
            )

            logger.info(f"响应状态码: {response.status_code}")

            if response.status_code == 200:
                result = response.json()
                logger.info(f"响应: {json.dumps(result, ensure_ascii=False, indent=2)}")

                if 'choices' in result and result['choices']:
                    content = result['choices'][0]['message']['content']
                    logger.info(f"成功获取回复: {content[:100]}...")
                    return content
                else:
                    logger.error(f"响应格式错误: {result}")
                    raise Exception("API响应格式错误")
            else:
                error_msg = f"API请求失败: {response.status_code} - {response.text}"
                logger.error(error_msg)

                # 尝试解析错误信息
                try:
                    error_data = response.json()
                    if 'error' in error_data:
                        error_detail = error_data['error'].get('message', '未知错误')
                        raise Exception(f"API错误: {error_detail}")
                except json.JSONDecodeError:
                    pass

                raise Exception(error_msg)

        except requests.exceptions.RequestException as e:
            logger.error(f"网络请求失败: {str(e)}")
            raise Exception(f"网络连接失败: {str(e)}")
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析失败: {str(e)}")
            raise Exception(f"响应解析失败: {str(e)}")
        except Exception as e:
            logger.error(f"API调用失败: {str(e)}")
            raise

    def _stream_openai_compatible(self, messages: List[Dict], character: Character) -> Generator[str, None, None]:
        """OpenAI兼容API流式调用"""
        try:
            headers = {
                "Authorization": f"Bearer {self.config['api_key']}",
                "Content-Type": "application/json"
            }

            data = {
                "model": self.config['model'],
                "messages": messages,
                "temperature": max(0.0, min(1.0, self.config['temperature'] + character.temperature_modifier)),
                "max_tokens": self.config['max_tokens'],
                "stream": True
            }

            response = requests.post(
                f"{self.config['api_base']}/chat/completions",
                headers=headers,
                json=data,
                stream=True,
                timeout=self.timeout
            )

            if response.status_code == 200:
                for line in response.iter_lines():
                    if line:
                        line = line.decode('utf-8')
                        if line.startswith('data: '):
                            if line.strip() == 'data: [DONE]':
                                break
                            try:
                                data = json.loads(line[6:])
                                if 'choices' in data and data['choices']:
                                    delta = data['choices'][0].get('delta', {})
                                    if 'content' in delta:
                                        yield delta['content']
                            except json.JSONDecodeError:
                                continue
            else:
                error_msg = f"流式请求失败: {response.status_code} - {response.text}"
                logger.error(error_msg)
                yield error_msg

        except Exception as e:
            logger.error(f"流式API调用失败: {str(e)}")
            yield f"流式调用失败: {str(e)}"

    def _generate_fallback_response(self, character: Character, user_message: str) -> str:
        """生成备用回复（当API不可用时）"""
        templates = {
            "default": [
                f"关于'{user_message}'，这是个很有意思的话题。让我想想...",
                f"你提到的'{user_message}'很有深度，我需要仔细思考一下。",
                f"'{user_message}'这个问题很好，让我们一起探讨。"
            ]
        }

        # 根据角色特点生成更个性化的回复
        character_responses = {
            "harry_potter": [
                f"关于'{user_message}'，这让我想起了在霍格沃茨的一些经历...",
                f"'{user_message}'？这就像魔法一样神奇！让我告诉你...",
                f"邓布利多教授曾经说过类似的话题，关于'{user_message}'..."
            ],
            "sherlock_holmes": [
                f"有趣...'{user_message}'这个问题需要仔细的分析。",
                f"从你的问题'{user_message}'中，我可以推断出几个可能性。",
                f"基本的演绎法告诉我，'{user_message}'背后有更深的含义。"
            ],
            "confucius": [
                f"子曰：关于'{user_message}'，吾当三思而后言。",
                f"'{user_message}'涉及到做人的道理，让我慢慢道来。",
                f"这让我想起《论语》中的一段话，与'{user_message}'相关..."
            ]
        }

        responses = character_responses.get(character.id, templates["default"])
        selected = random.choice(responses)

        # 添加一些通用的扩展内容
        extensions = [
            "虽然我现在无法给出完整的回答，但我们可以一起探讨这个话题的不同角度。",
            "每个人对此都可能有不同的理解，你是怎么看的呢？",
            "这个话题确实值得深入思考，也许我们可以从另一个角度来看。"
        ]

        return f"{selected} {random.choice(extensions)}"


class VoiceService:
    """增强的语音服务类"""

    def __init__(self):
        self.provider = Config.VOICE_SERVICE_PROVIDER
        self.configured = self._check_configuration()

    def is_configured(self) -> bool:
        """检查语音服务是否已配置"""
        return self.configured

    def _check_configuration(self) -> bool:
        """检查配置完整性"""
        if self.provider == 'browser':
            return True  # 浏览器内置，始终可用
        return False

    def speech_to_text(self, audio_file_path: str) -> str:
        """语音转文字 - 浏览器端处理"""
        try:
            # 浏览器端处理，这里只做文件验证
            if os.path.exists(audio_file_path):
                return "语音文件已接收，请使用浏览器端语音识别"
            return "语音文件不存在"
        except Exception as e:
            logger.error(f"语音识别错误: {str(e)}")
            return "语音识别失败，请重试"

    def text_to_speech(self, text: str, character: Character = None) -> Optional[Dict]:
        """文字转语音 - 返回浏览器配置"""
        try:
            return self._get_browser_voice_config(character)
        except Exception as e:
            logger.error(f"语音合成错误: {str(e)}")
            return None

    def _get_browser_voice_config(self, character: Character = None) -> Dict[str, Any]:
        """获取浏览器端语音配置"""
        if not character or not character.voice_config:
            return {
                'type': 'browser',
                'lang': 'zh-CN',
                'rate': 0.9,
                'pitch': 1.0,
                'volume': 1.0,
                'voice_name': None
            }

        config = character.voice_config
        return {
            'type': 'browser',
            'lang': self._map_language(config.get('accent', 'chinese')),
            'rate': config.get('rate', 0.9),
            'pitch': config.get('pitch', 1.0),
            'volume': config.get('volume', 1.0),
            'voice_name': config.get('voice_name'),
            'gender': config.get('gender', 'female'),
            'age': config.get('age', 'adult')
        }

    def _map_language(self, accent: str) -> str:
        """映射语言代码"""
        language_map = {
            'chinese': 'zh-CN',
            'english': 'en-US',
            'british': 'en-GB',
            'british_posh': 'en-GB',
            'british_refined': 'en-GB',
            'american': 'en-US',
            'japanese': 'ja-JP',
            'french': 'fr-FR',
            'german': 'de-DE'
        }
        return language_map.get(accent, 'zh-CN')

    def get_voice_settings_for_character(self, character: Character) -> Dict[str, Any]:
        """获取指定角色的语音设置"""
        return self._get_browser_voice_config(character)

    def _mock_speech_to_text(self, audio_file_path: str) -> str:
        """模拟语音识别（用于测试）"""
        responses = [
            "你好，很高兴认识你",
            "能告诉我更多关于你的故事吗",
            "这真是太有趣了",
            "我想了解更多细节"
        ]
        return random.choice(responses)


class ChatService:
    """聊天服务类"""

    def __init__(self, ai_service: AIService):
        self.character_repo = CharacterRepository()
        self.chat_repo = ChatRepository()
        self.ai_service = ai_service

    def start_chat_session(self, user_id: str, character_id: str) -> Optional[ChatSession]:
        """开始聊天会话"""
        character = self.character_repo.get_by_id(character_id)
        if not character:
            return None

        # 创建新会话
        session = self.chat_repo.create_session(user_id, character_id)

        # 添加角色的问候消息
        greeting_msg = Message.create_character_message(
            character.greeting,
            metadata={'ai_generated': False}
        )
        session.add_message(greeting_msg)

        return session

    def send_message(self, session_id: str, user_message: str) -> Optional[str]:
        """发送消息并获取回复"""
        session = self.chat_repo.get_session(session_id)
        if not session:
            return None

        character = self.character_repo.get_by_id(session.character_id)
        if not character:
            return None

        # 检查消息长度
        if len(user_message) > Config.MAX_MESSAGE_LENGTH:
            return f"消息太长了，请限制在{Config.MAX_MESSAGE_LENGTH}字以内"

        # 添加用户消息
        user_msg = Message.create_user_message(user_message)
        session.add_message(user_msg)

        # 获取上下文消息
        context_messages = session.get_context_messages()

        # 生成AI回复
        try:
            ai_response = self.ai_service.generate_response(
                character, user_message, context_messages[:-1]  # 不包括刚添加的用户消息
            )

            # 添加AI回复
            ai_msg = Message.create_character_message(
                ai_response,
                metadata={
                    'ai_generated': True,
                    'model': self.ai_service.current_model,
                    'timestamp': datetime.now().isoformat()
                }
            )
            session.add_message(ai_msg)

            return ai_response

        except Exception as e:
            logger.error(f"生成回复失败: {str(e)}")
            error_msg = "抱歉，我现在有点困惑。让我们换个话题吧？"

            # 添加错误回复
            error_msg_obj = Message.create_character_message(
                error_msg,
                metadata={'error': str(e), 'ai_generated': True}
            )
            session.add_message(error_msg_obj)

            return error_msg

    def send_message_stream(self, session_id: str, user_message: str) -> Generator[str, None, None]:
        """流式发送消息"""
        session = self.chat_repo.get_session(session_id)
        if not session:
            yield "会话不存在"
            return

        character = self.character_repo.get_by_id(session.character_id)
        if not character:
            yield "角色不存在"
            return

        # 检查消息长度
        if len(user_message) > Config.MAX_MESSAGE_LENGTH:
            yield f"消息太长了，请限制在{Config.MAX_MESSAGE_LENGTH}字以内"
            return

        # 添加用户消息
        user_msg = Message.create_user_message(user_message)
        session.add_message(user_msg)

        # 获取上下文
        context_messages = session.get_context_messages()

        # 收集完整响应
        full_response = ""

        try:
            # 流式生成回复
            for chunk in self.ai_service.generate_response_stream(
                    character, user_message, context_messages[:-1]
            ):
                full_response += chunk
                yield chunk

            # 保存完整的回复
            ai_msg = Message.create_character_message(
                full_response,
                metadata={
                    'ai_generated': True,
                    'model': self.ai_service.current_model,
                    'timestamp': datetime.now().isoformat(),
                    'streamed': True
                }
            )
            session.add_message(ai_msg)

        except Exception as e:
            logger.error(f"流式生成失败: {str(e)}")
            error_msg = "抱歉，出现了一些问题..."
            yield error_msg

            # 保存错误消息
            error_msg_obj = Message.create_character_message(
                full_response + error_msg if full_response else error_msg,
                metadata={'error': str(e), 'ai_generated': True}
            )
            session.add_message(error_msg_obj)

    def get_chat_history(self, session_id: str) -> List[Message]:
        """获取聊天历史"""
        session = self.chat_repo.get_session(session_id)
        return session.messages if session else []

    def clear_session(self, session_id: str) -> bool:
        """清空会话消息"""
        session = self.chat_repo.get_session(session_id)
        if not session:
            return False

        # 保留第一条问候消息
        if session.messages:
            greeting = session.messages[0]
            session.messages = [greeting]
            session.updated_at = datetime.now()

        return True

    def export_chat_history(self, session_id: str) -> Optional[Dict]:
        """导出聊天记录"""
        session = self.chat_repo.get_session(session_id)
        if not session:
            return None

        character = self.character_repo.get_by_id(session.character_id)

        return {
            'session_id': session.id,
            'character': character.name if character else 'Unknown',
            'created_at': session.created_at.isoformat(),
            'messages': [
                {
                    'sender': 'user' if msg.sender_type == 'user' else character.name,
                    'content': msg.content,
                    'timestamp': msg.timestamp.isoformat()
                } for msg in session.messages
            ]
        }