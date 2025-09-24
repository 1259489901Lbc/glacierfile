from flask import Flask, render_template, request, jsonify, session, redirect, url_for, abort, Response
from flask_socketio import SocketIO, emit, join_room, leave_room
import json
import uuid
from datetime import datetime
import os
from dotenv import load_dotenv
import time
import threading

# 加载环境变量
load_dotenv()

from models import CharacterRepository, ChatRepository, ChatSession, Message
from services import AIService, VoiceService, ChatService
from config import Config

app = Flask(__name__)
app.config.from_object(Config)

# 初始化SocketIO
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading', ping_timeout=60, ping_interval=25)

# 初始化服务
character_repo = CharacterRepository()
chat_repo = ChatRepository()
ai_service = AIService()
voice_service = VoiceService()
chat_service = ChatService(ai_service)

# 存储活跃的语音通话
active_calls = {}

# 确保上传目录存在
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


@app.route('/')
def index():
    """主页"""
    characters = character_repo.get_all()
    categories = character_repo.get_categories()
    return render_template('index.html',
                           characters=characters,
                           categories=categories,
                           ai_enabled=ai_service.is_configured())


@app.route('/character/<character_id>')
def character_detail(character_id):
    """角色详情页"""
    character = character_repo.get_by_id(character_id)
    if not character:
        abort(404)

    similar_characters = character_repo.get_similar_characters(character_id)

    return render_template('character.html',
                           character=character,
                           similar_characters=similar_characters,
                           ai_enabled=ai_service.is_configured())


@app.route('/chat/<character_id>')
def chat_page(character_id):
    """聊天页面"""
    character = character_repo.get_by_id(character_id)
    if not character:
        abort(404)

    # 生成或获取用户ID
    if 'user_id' not in session:
        session['user_id'] = str(uuid.uuid4())

    user_id = session['user_id']
    session_id = request.args.get('session_id')

    # 如果有会话ID，验证会话是否存在
    if session_id:
        chat_session = chat_repo.get_session(session_id)
        if chat_session:
            # 会话存在，直接显示聊天页面
            return render_template('chat.html',
                                   character=character,
                                   session_id=session_id,
                                   ai_enabled=ai_service.is_configured())

    # 创建新会话
    chat_session = chat_service.start_chat_session(user_id, character_id)
    return render_template('chat.html',
                           character=character,
                           session_id=chat_session.id,
                           ai_enabled=ai_service.is_configured())


@app.route('/about')
def about():
    """关于页面"""
    stats = {
        'total_characters': len(character_repo.get_all()),
        'categories': len(character_repo.get_categories()),
        'ai_models': ai_service.get_available_models()
    }
    return render_template('about.html', stats=stats)


# API路由
@app.route('/api/characters')
def get_characters():
    """获取所有角色"""
    characters = character_repo.get_all()
    return jsonify([char.to_dict() for char in characters])


@app.route('/api/characters/search')
def search_characters():
    """搜索角色"""
    query = request.args.get('q', '')
    category = request.args.get('category', '')

    results = character_repo.search(query, category)
    return jsonify([char.to_dict() for char in results])


@app.route('/api/chat/send', methods=['POST'])
def send_chat_message():
    """发送聊天消息"""
    data = request.get_json()
    session_id = data.get('session_id')
    message = data.get('message')

    if not session_id or not message:
        return jsonify({'error': '参数缺失'}), 400

    try:
        response = chat_service.send_message(session_id, message)

        if response is None:
            return jsonify({'error': '会话不存在'}), 404

        return jsonify({
            'response': response,
            'timestamp': datetime.now().isoformat(),
            'ai_model': ai_service.current_model
        })
    except Exception as e:
        app.logger.error(f"聊天错误: {str(e)}")
        return jsonify({'error': '服务暂时不可用，请稍后再试'}), 503


@app.route('/api/chat/stream', methods=['POST'])
def stream_chat_message():
    """流式发送聊天消息"""
    data = request.get_json()
    session_id = data.get('session_id')
    message = data.get('message')

    if not session_id or not message:
        return jsonify({'error': '参数缺失'}), 400

    def generate():
        try:
            for chunk in chat_service.send_message_stream(session_id, message):
                yield f"data: {json.dumps({'chunk': chunk})}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return Response(generate(), mimetype='text/event-stream')


@app.route('/api/voice/upload', methods=['POST'])
def upload_voice():
    """上传语音文件"""
    if 'audio' not in request.files:
        return jsonify({'error': '没有音频文件'}), 400

    try:
        audio_file = request.files['audio']
        # 保存临时文件
        temp_path = os.path.join(app.config['UPLOAD_FOLDER'], f'temp_{uuid.uuid4()}.webm')
        audio_file.save(temp_path)

        # 语音转文字
        text = voice_service.speech_to_text(temp_path)

        # 清理临时文件
        try:
            os.remove(temp_path)
        except:
            pass

        return jsonify({'text': text})
    except Exception as e:
        app.logger.error(f"语音处理错误: {str(e)}")
        return jsonify({'error': '语音处理失败'}), 500


@app.route('/api/voice/synthesize', methods=['POST'])
def synthesize_voice():
    """文字转语音"""
    data = request.get_json()
    text = data.get('text', '')
    character_id = data.get('character_id')

    if not text:
        return jsonify({'error': '文本不能为空'}), 400

    try:
        # 获取角色信息以选择合适的语音
        character = character_repo.get_by_id(character_id) if character_id else None
        audio_url = voice_service.text_to_speech(text, character)

        return jsonify({'audio_url': audio_url})
    except Exception as e:
        app.logger.error(f"语音合成错误: {str(e)}")
        return jsonify({'error': '语音合成失败'}), 500


@app.route('/api/chat/history/<session_id>')
def get_chat_history(session_id):
    """获取聊天历史"""
    messages = chat_service.get_chat_history(session_id)

    return jsonify([{
        'id': msg.id,
        'sender_type': msg.sender_type,
        'content': msg.content,
        'timestamp': msg.timestamp.isoformat(),
        'message_type': msg.message_type
    } for msg in messages])


@app.route('/api/chat/sessions/<user_id>')
def get_user_sessions(user_id):
    """获取用户的所有会话"""
    sessions = chat_repo.get_user_sessions(user_id)

    return jsonify([{
        'id': s.id,
        'character_id': s.character_id,
        'created_at': s.created_at.isoformat(),
        'last_message': s.get_last_message(),
        'message_count': len(s.messages)
    } for s in sessions])


@app.route('/api/system/status')
def system_status():
    """获取系统状态"""
    return jsonify({
        'ai_service': {
            'configured': ai_service.is_configured(),
            'models': ai_service.get_available_models(),
            'current_model': ai_service.current_model
        },
        'voice_service': {
            'enabled': voice_service.is_configured()
        },
        'stats': {
            'total_characters': len(character_repo.get_all()),
            'active_sessions': chat_repo.get_active_session_count(),
            'active_calls': len(active_calls)
        }
    })


# 语音功能API端点
@app.route('/api/voice/config/<character_id>')
def get_voice_config(character_id):
    """获取角色语音配置"""
    try:
        # 直接在这里获取角色信息，而不是在VoiceService中
        character = character_repo.get_by_id(character_id)
        if not character:
            return jsonify({'success': False, 'error': '角色不存在'}), 404

        # 使用VoiceService的新方法
        voice_config = voice_service.get_voice_settings_for_character(character)
        return jsonify({
            'success': True,
            'config': voice_config
        })
    except Exception as e:
        app.logger.error(f"获取语音配置失败: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/chat/voice', methods=['POST'])
def voice_chat():
    """处理语音聊天请求"""
    data = request.get_json()
    session_id = data.get('session_id')
    message = data.get('message')
    use_voice_response = data.get('use_voice_response', False)

    if not session_id or not message:
        return jsonify({'error': '参数缺失'}), 400

    try:
        # 获取AI回复
        response = chat_service.send_message(session_id, message)

        if response is None:
            return jsonify({'error': '会话不存在'}), 404

        result = {
            'response': response,
            'timestamp': datetime.now().isoformat(),
            'ai_model': ai_service.current_model
        }

        # 如果需要语音回复
        if use_voice_response:
            session = chat_repo.get_session(session_id)
            if session:
                character = character_repo.get_by_id(session.character_id)
                if character:
                    voice_result = voice_service.text_to_speech(response, character)
                    result['voice_config'] = voice_result

        return jsonify(result)

    except Exception as e:
        app.logger.error(f"语音聊天错误: {str(e)}")
        return jsonify({'error': '服务暂时不可用，请稍后再试'}), 503


# WebSocket事件处理
@socketio.on('connect')
def handle_connect():
    """处理WebSocket连接"""
    print(f"Client connected: {request.sid}")
    emit('connected', {'status': 'success'})


@socketio.on('disconnect')
def handle_disconnect():
    """处理WebSocket断开"""
    print(f"Client disconnected: {request.sid}")
    # 清理可能存在的通话
    if request.sid in active_calls:
        call_info = active_calls.pop(request.sid)
        leave_room(call_info['room'])
        emit('call_ended', {'reason': 'disconnect'}, room=call_info['room'])


@socketio.on('start_voice_call')
def handle_start_voice_call(data):
    """开始语音通话"""
    session_id = data.get('session_id')
    character_id = data.get('character_id')

    app.logger.info(f"Starting voice call - Session: {session_id}, Character: {character_id}, Client: {request.sid}")

    if not session_id or not character_id:
        emit('error', {'message': '参数缺失'})
        return

    # 创建通话房间
    room = f"call_{session_id}_{request.sid}"
    join_room(room)

    # 记录活跃通话
    active_calls[request.sid] = {
        'session_id': session_id,
        'character_id': character_id,
        'room': room,
        'start_time': datetime.now(),
        'status': 'active'
    }

    app.logger.info(f"Voice call started in room: {room}")

    emit('call_started', {
        'room': room,
        'status': 'active'
    })


@socketio.on('end_voice_call')
def handle_end_voice_call(data):
    """结束语音通话"""
    if request.sid in active_calls:
        call_info = active_calls.pop(request.sid)
        leave_room(call_info['room'])

        # 计算通话时长
        duration = (datetime.now() - call_info['start_time']).total_seconds()

        emit('call_ended', {
            'duration': duration,
            'status': 'ended'
        })


@socketio.on('voice_stream')
def handle_voice_stream(data):
    """处理语音流数据"""
    app.logger.info(f"Received voice stream from {request.sid}")

    if request.sid not in active_calls:
        app.logger.error(f"No active call for {request.sid}")
        emit('error', {'message': '通话未开始'})
        return

    call_info = active_calls[request.sid]
    transcript = data.get('transcript')
    is_final = data.get('is_final', False)

    app.logger.info(f"Voice stream - Transcript: '{transcript}', Final: {is_final}")

    if transcript and is_final:
        # 获取AI响应
        session_id = call_info['session_id']
        character_id = call_info['character_id']

        app.logger.info(f"Processing final transcript: '{transcript}'")

        # 立即发送正在处理的状态
        emit('processing', {'status': 'thinking'}, room=call_info['room'])

        # 保存客户端socket ID（重要！在线程中需要使用）
        client_sid = request.sid

        # 在新线程中处理AI响应（使用流式响应）
        def process_ai_response_stream():
            try:
                app.logger.info(f"Processing voice call message: {transcript}")

                # 先发送用户消息确认 - 直接发送到客户端，不使用room
                socketio.emit('user_transcript_confirmed', {
                    'transcript': transcript
                }, to=client_sid)

                # 获取角色
                character = character_repo.get_by_id(character_id)
                if not character:
                    app.logger.error("Character not found")
                    return

                # 使用流式生成
                full_response = ""
                chunk_buffer = ""

                app.logger.info("Starting stream generation...")

                for chunk in chat_service.send_message_stream(session_id, transcript):
                    full_response += chunk
                    chunk_buffer += chunk

                    # 每积累一定字符就发送 - 直接发送到客户端
                    if len(chunk_buffer) >= 20 or '。' in chunk_buffer or '！' in chunk_buffer or '？' in chunk_buffer:
                        app.logger.info(f"Sending chunk to {client_sid}: {chunk_buffer}")
                        socketio.emit('ai_response_chunk', {
                            'chunk': chunk_buffer,
                            'is_complete': False
                        }, to=client_sid)
                        chunk_buffer = ""

                # 发送剩余内容和完整响应 - 直接发送到客户端
                if chunk_buffer:
                    app.logger.info(f"Sending final chunk to {client_sid}: {chunk_buffer}")
                    socketio.emit('ai_response_chunk', {
                        'chunk': chunk_buffer,
                        'is_complete': True
                    }, to=client_sid)

                app.logger.info(f"Sending complete response to {client_sid}: {full_response[:50]}...")

                # 发送完整响应（用于语音播放）- 直接发送到客户端
                socketio.emit('ai_response', {
                    'text': full_response,
                    'transcript': transcript
                }, to=client_sid)

                # 发送语音配置 - 直接发送到客户端
                voice_config = voice_service.get_voice_settings_for_character(character)
                socketio.emit('ai_voice_config', voice_config, to=client_sid)

                app.logger.info(f"Voice call response sent successfully to {client_sid}")

            except Exception as e:
                app.logger.error(f"Voice call AI response error: {str(e)}")
                import traceback
                app.logger.error(traceback.format_exc())
                socketio.emit('error', {'message': '处理响应时出错'}, to=client_sid)

        # 启动新线程处理
        threading.Thread(target=process_ai_response_stream).start()

    # 转发实时转录
    emit('voice_transcript', {
        'transcript': transcript,
        'is_final': is_final
    }, room=call_info['room'])


@socketio.on('update_call_status')
def handle_update_call_status(data):
    """更新通话状态"""
    if request.sid in active_calls:
        status = data.get('status')
        if status:
            active_calls[request.sid]['status'] = status
            emit('call_status_updated', {'status': status})


# 错误处理器
@app.errorhandler(404)
def not_found_error(error):
    if request.path.startswith('/api/'):
        return jsonify({'error': '资源不存在'}), 404
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_error(error):
    app.logger.error(f"内部错误: {error}")
    if request.path.startswith('/api/'):
        return jsonify({'error': '服务器内部错误'}), 500
    return render_template('500.html'), 500


if __name__ == '__main__':
    # 开发模式配置 - 使用SocketIO运行
    socketio.run(
        app,
        host='0.0.0.0',
        port=5000,
        debug=app.config['DEBUG'],
        allow_unsafe_werkzeug=True  # 仅用于开发环境
    )
