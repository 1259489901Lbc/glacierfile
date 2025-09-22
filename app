from flask import Flask, render_template, request, jsonify, session, redirect, url_for, abort
import json
import uuid
from datetime import datetime
from models import CharacterRepository, ChatRepository, ChatSession, Message
from services import AIService, VoiceService, ChatService

app = Flask(__name__)
app.secret_key = 'ai-roleplay-secret-key-2024'

# 初始化服务
character_repo = CharacterRepository()
chat_repo = ChatRepository()
ai_service = AIService()
voice_service = VoiceService()
chat_service = ChatService(ai_service)


@app.route('/')
def index():
    """主页"""
    characters = character_repo.get_all()
    categories = character_repo.get_categories()
    return render_template('index.html', characters=characters, categories=categories)


@app.route('/character/<character_id>')
def character_detail(character_id):
    """角色详情页"""
    character = character_repo.get_by_id(character_id)
    if not character:
        abort(404)

    similar_characters = character_repo.search('', character.category)
    similar_characters = [c for c in similar_characters if c.id != character_id][:3]

    return render_template('character.html',
                           character=character,
                           similar_characters=similar_characters)


@app.route('/chat/<character_id>')
def chat_page(character_id):
    """聊天页面"""
    character = character_repo.get_by_id(character_id)
    if not character:
        abort(404)

    user_id = session.get('user_id', 'anonymous')
    session_id = request.args.get('session_id')

    if not session_id:
        chat_session = chat_service.start_chat_session(user_id, character_id)
        return redirect(url_for('chat_page',
                                character_id=character_id,
                                session_id=chat_session.id))

    return render_template('chat.html',
                           character=character,
                           session_id=session_id)


@app.route('/about')
def about():
    """关于页面"""
    return render_template('about.html')


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

    response = chat_service.send_message(session_id, message)

    if response is None:
        return jsonify({'error': '会话不存在'}), 404

    return jsonify({
        'response': response,
        'timestamp': datetime.now().isoformat()
    })


@app.route('/api/voice/upload', methods=['POST'])
def upload_voice():
    """上传语音文件"""
    if 'audio' not in request.files:
        return jsonify({'error': '没有音频文件'}), 400

    audio_file = request.files['audio']
    text = voice_service.speech_to_text(audio_file)

    return jsonify({'text': text})


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


if __name__ == '__main__':
    app.run(debug=True)
