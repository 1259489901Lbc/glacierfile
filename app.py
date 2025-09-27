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

# 创建Flask应用，明确指定静态文件配置
app = Flask(__name__,
            static_folder='static',
            static_url_path='/static')
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

# 确保必要目录存在
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('static/images/characters', exist_ok=True)


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


# 静态文件路由（确保静态文件可以正常访问）
@app.route('/static/<path:filename>')
def static_files(filename):
    """静态文件服务"""
    return app.send_static_file(filename)


# 调试路由
@app.route('/debug/avatars')
def debug_avatars():
    """调试头像显示问题"""
    import os

    debug_info = {
        'static_folder': app.static_folder,
        'static_url_path': app.static_url_path,
        'files_check': {}
    }

    characters = ['harry_potter', 'sherlock_holmes', 'confucius', 'marie_curie',
                  'sun_wukong', 'einstein', 'mulan', 'elizabeth_bennet']

    for char_id in characters:
        file_path = f"static/images/characters/{char_id}.png"
        debug_info['files_check'][char_id] = {
            'expected_path': file_path,
            'absolute_path': os.path.abspath(file_path),
            'exists': os.path.exists(file_path),
            'url': f"/static/images/characters/{char_id}.png"
        }

        if os.path.exists(file_path):
            debug_info['files_check'][char_id]['size'] = os.path.getsize(file_path)

    # 检查目录是否存在
    debug_info['directories'] = {
        'static': os.path.exists('static'),
        'static/images': os.path.exists('static/images'),
        'static/images/characters': os.path.exists('static/images/characters')
    }

    # 构建文件检查表格行
    check_mark = '✓'
    cross_mark = '✗'
    table_rows = []

    for char_id, info in debug_info['files_check'].items():
        exists_symbol = check_mark if info['exists'] else cross_mark
        exists_color = 'green' if info['exists'] else 'red'
        size_text = f"{info.get('size', 'N/A')} bytes"

        row = f"""
            <tr>
                <td style="padding: 8px;">{char_id}</td>
                <td style="padding: 8px; font-family: monospace;">{info['expected_path']}</td>
                <td style="padding: 8px; color: {exists_color};">{exists_symbol}</td>
                <td style="padding: 8px;">{size_text}</td>
                <td style="padding: 8px; font-family: monospace;">{info['url']}</td>
                <td style="padding: 8px;"><a href="{info['url']}" target="_blank">测试</a></td>
            </tr>"""
        table_rows.append(row)

    # 构建测试图片
    test_images = []
    for char_id, info in debug_info['files_check'].items():
        img_tag = f'<img src="{info["url"]}" width="100" height="100" style="margin:5px; border:1px solid #ccc;" alt="{char_id}" onerror="this.style.border=&quot;3px solid red&quot;" onload="this.style.border=&quot;3px solid green&quot;">'
        test_images.append(img_tag)

    return f"""
    <html>
    <head><title>头像调试信息</title></head>
    <body style="font-family: Arial, sans-serif; padding: 20px;">
        <h1>头像调试信息</h1>
        <h2>Flask配置</h2>
        <p><strong>Static Folder:</strong> {debug_info['static_folder']}</p>
        <p><strong>Static URL Path:</strong> {debug_info['static_url_path']}</p>

        <h2>目录检查</h2>
        <ul>
            <li>static/ 存在: {check_mark if debug_info['directories']['static'] else cross_mark}</li>
            <li>static/images/ 存在: {check_mark if debug_info['directories']['static/images'] else cross_mark}</li>
            <li>static/images/characters/ 存在: {check_mark if debug_info['directories']['static/images/characters'] else cross_mark}</li>
        </ul>

        <h2>文件检查</h2>
        <table border="1" style="border-collapse: collapse; width: 100%;">
            <tr style="background: #f0f0f0;">
                <th style="padding: 8px;">角色ID</th>
                <th style="padding: 8px;">预期路径</th>
                <th style="padding: 8px;">文件存在</th>
                <th style="padding: 8px;">文件大小</th>
                <th style="padding: 8px;">访问URL</th>
                <th style="padding: 8px;">测试链接</th>
            </tr>
            {''.join(table_rows)}
        </table>

        <h2>直接测试图片显示</h2>
        <div style="margin: 20px 0;">
            {''.join(test_images)}
        </div>

        <h2>解决方案</h2>
        <ol>
            <li>确保 static/images/characters/ 目录存在</li>
            <li>确保图片文件名与角色ID完全匹配（小写+下划线）</li>
            <li>确保图片文件为有效的PNG格式</li>
            <li>检查文件权限，确保Web服务器可以读取</li>
        </ol>

        <p><a href="/debug/avatar-test" style="background: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">完整测试页面</a></p>
        <p><a href="/" style="background: #28a745; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">返回主页</a></p>
    </body>
    </html>
    """


@app.route('/debug/avatar-test')
def avatar_test():
    """返回头像测试页面"""
    html_template = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>头像测试页面</title>
    <style>
        body { font-family: Arial, sans-serif; padding: 20px; background: #f5f5f5; }
        .test-container { background: white; padding: 20px; border-radius: 10px; margin-bottom: 20px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
        .avatar-test { display: inline-block; margin: 10px; text-align: center; padding: 15px; border: 1px solid #ddd; border-radius: 8px; width: 150px; }
        .avatar-test img { width: 100px; height: 100px; border-radius: 50%; border: 2px solid #ccc; object-fit: cover; }
        .status { margin-top: 10px; padding: 8px; border-radius: 5px; font-size: 12px; font-weight: bold; }
        .success { background: #d4edda; color: #155724; }
        .error { background: #f8d7da; color: #721c24; }
        .info { background: #d1ecf1; color: #0c5460; }
        .btn { background: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; margin: 10px; display: inline-block; }
    </style>
</head>
<body>
    <h1>头像显示测试</h1>
    <div class="test-container">
        <h2>静态路径测试</h2>
        <p>测试所有角色头像是否能正常加载：</p>

        <div class="avatar-test">
            <img src="/static/images/characters/harry_potter.png" alt="哈利·波特" onload="showStatus(this, 'success')" onerror="showStatus(this, 'error')">
            <div>哈利·波特</div><div class="status info" id="status_0">检测中...</div>
        </div>
        <div class="avatar-test">
            <img src="/static/images/characters/sherlock_holmes.png" alt="福尔摩斯" onload="showStatus(this, 'success')" onerror="showStatus(this, 'error')">
            <div>福尔摩斯</div><div class="status info" id="status_1">检测中...</div>
        </div>
        <div class="avatar-test">
            <img src="/static/images/characters/confucius.png" alt="孔子" onload="showStatus(this, 'success')" onerror="showStatus(this, 'error')">
            <div>孔子</div><div class="status info" id="status_2">检测中...</div>
        </div>
        <div class="avatar-test">
            <img src="/static/images/characters/marie_curie.png" alt="居里夫人" onload="showStatus(this, 'success')" onerror="showStatus(this, 'error')">
            <div>居里夫人</div><div class="status info" id="status_3">检测中...</div>
        </div>
        <div class="avatar-test">
            <img src="/static/images/characters/sun_wukong.png" alt="孙悟空" onload="showStatus(this, 'success')" onerror="showStatus(this, 'error')">
            <div>孙悟空</div><div class="status info" id="status_4">检测中...</div>
        </div>
        <div class="avatar-test">
            <img src="/static/images/characters/einstein.png" alt="爱因斯坦" onload="showStatus(this, 'success')" onerror="showStatus(this, 'error')">
            <div>爱因斯坦</div><div class="status info" id="status_5">检测中...</div>
        </div>
        <div class="avatar-test">
            <img src="/static/images/characters/mulan.png" alt="花木兰" onload="showStatus(this, 'success')" onerror="showStatus(this, 'error')">
            <div>花木兰</div><div class="status info" id="status_6">检测中...</div>
        </div>
        <div class="avatar-test">
            <img src="/static/images/characters/elizabeth_bennet.png" alt="伊丽莎白" onload="showStatus(this, 'success')" onerror="showStatus(this, 'error')">
            <div>伊丽莎白</div><div class="status info" id="status_7">检测中...</div>
        </div>
    </div>

    <div class="test-container">
        <h2>检查清单</h2>
        <ul>
            <li>确保项目根目录下有 static/images/characters/ 文件夹</li>
            <li>确保图片文件名格式正确（小写+下划线+.png）</li>
            <li>确保图片文件有效且不损坏</li>
            <li>确保文件权限允许Web服务器读取</li>
        </ul>

        <a href="/debug/avatars" class="btn">查看详细调试信息</a>
        <a href="/" class="btn">返回主页</a>
    </div>

    <script>
        function showStatus(img, result) {
            const index = Array.from(document.querySelectorAll('.avatar-test img')).indexOf(img);
            const statusEl = document.getElementById('status_' + index);
            if (result === 'success') {
                statusEl.textContent = '✓ 加载成功';
                statusEl.className = 'status success';
            } else {
                statusEl.textContent = '✗ 加载失败';
                statusEl.className = 'status error';
            }
        }

        // 3秒后检查还没加载的图片
        setTimeout(() => {
            const allStatusElements = document.querySelectorAll('.status.info');
            allStatusElements.forEach(element => {
                if (element.textContent === '检测中...') {
                    element.textContent = '⏱ 加载超时';
                    element.className = 'status error';
                }
            });
        }, 3000);
    </script>
</body>
</html>'''
    return html_template


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
    # 新增：检查是否来自语音通话
    is_voice_call = data.get('is_voice_call', False)

    if not session_id or not message:
        return jsonify({'error': '参数缺失'}), 400

    try:
        # 获取AI回复 - 传递 is_voice_call 参数
        response = chat_service.send_message(session_id, message, is_voice_call=is_voice_call)

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

        # 保存客户端socket ID
        client_sid = request.sid

        # 在新线程中处理AI响应（使用流式响应）
        def process_ai_response_stream():
            try:
                app.logger.info(f"Processing voice call message: {transcript}")

                # 先发送用户消息确认
                socketio.emit('user_transcript_confirmed', {
                    'transcript': transcript
                }, to=client_sid)

                # 获取角色
                character = character_repo.get_by_id(character_id)
                if not character:
                    app.logger.error("Character not found")
                    return

                # 使用流式生成 - 注意这里传递了 is_voice_call=True
                full_response = ""
                sentence_buffer = ""
                sentence_count = 0

                app.logger.info("Starting stream generation...")

                # 关键修改：传递 is_voice_call=True
                for chunk in chat_service.send_message_stream(session_id, transcript, is_voice_call=True):
                    full_response += chunk
                    sentence_buffer += chunk

                    # 检测句子结束（中文句号、问号、感叹号或英文句号）
                    sentence_endings = ['。', '！', '？', '.', '!', '?']

                    # 查找句子结束符
                    for ending in sentence_endings:
                        if ending in sentence_buffer:
                            # 分割句子
                            parts = sentence_buffer.split(ending, 1)
                            if len(parts) > 1:
                                complete_sentence = parts[0] + ending
                                sentence_buffer = parts[1]

                                # 发送完整的句子用于语音播放
                                sentence_count += 1
                                app.logger.info(f"Sending sentence {sentence_count}: {complete_sentence}")

                                socketio.emit('ai_sentence_ready', {
                                    'sentence': complete_sentence,
                                    'sentence_number': sentence_count,
                                    'is_final': False
                                }, to=client_sid)

                                # 同时发送文本片段用于显示
                                socketio.emit('ai_response_chunk', {
                                    'chunk': complete_sentence,
                                    'is_complete': False
                                }, to=client_sid)

                                break

                # 处理剩余的内容
                if sentence_buffer.strip():
                    sentence_count += 1
                    app.logger.info(f"Sending final sentence {sentence_count}: {sentence_buffer}")

                    socketio.emit('ai_sentence_ready', {
                        'sentence': sentence_buffer,
                        'sentence_number': sentence_count,
                        'is_final': True
                    }, to=client_sid)

                    socketio.emit('ai_response_chunk', {
                        'chunk': sentence_buffer,
                        'is_complete': True
                    }, to=client_sid)

                # 发送完整响应（用于记录）
                app.logger.info(f"Sending complete response to {client_sid}: {full_response[:50]}...")

                socketio.emit('ai_response_complete', {
                    'text': full_response,
                    'transcript': transcript,
                    'total_sentences': sentence_count
                }, to=client_sid)

                # 发送语音配置
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


@socketio.on('interrupt_ai_response')
def handle_interrupt_ai_response(data):
    """处理AI响应被打断"""
    session_id = data.get('session_id')
    app.logger.info(f"AI response interrupted for session {session_id}")

    # 这里可以添加额外的清理逻辑
    # 例如：停止正在进行的AI生成等


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
