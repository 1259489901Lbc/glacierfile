from flask import Flask, render_template, request, jsonify, session, redirect, url_for, abort, Response
from flask_socketio import SocketIO, emit, join_room, leave_room
import json
import uuid
from datetime import datetime
import os
from dotenv import load_dotenv
import time
import threading
import re
import secrets

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

# 初始化服务 - 修复：在应用级别创建单例服务
character_repo = CharacterRepository()
chat_repo = ChatRepository()
ai_service = AIService()
voice_service = VoiceService()
# 修复：传入所有需要的实例，确保使用同一个角色仓库
chat_service = ChatService(ai_service, character_repo, chat_repo)

# 存储活跃的语音通话
active_calls = {}

# 确保必要目录存在
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('static/images/characters', exist_ok=True)

# 扩展的中文名到拼音的映射表
CHINESE_NAME_TO_PINYIN = {
    # 神话传说人物
    '哪吒': 'nezha',
    '孙悟空': 'sun_wukong',
    '猪八戒': 'zhu_bajie',
    '沙僧': 'sha_seng',
    '唐僧': 'tang_seng',
    '嫦娥': 'chang_e',
    '玉兔': 'yu_tu',
    '龙王': 'long_wang',
    '观音': 'guanyin',
    '如来佛祖': 'rulai_fozu',

    # 历史人物
    '孔子': 'confucius',
    '老子': 'laozi',
    '庄子': 'zhuangzi',
    '孟子': 'mencius',
    '墨子': 'mozi',
    '韩非子': 'hanfeizi',
    '秦始皇': 'qin_shihuang',
    '汉武帝': 'han_wudi',
    '唐太宗': 'tang_taizong',
    '武则天': 'wu_zetian',
    '康熙': 'kangxi',
    '乾隆': 'qianlong',

    # 三国人物
    '刘备': 'liu_bei',
    '曹操': 'cao_cao',
    '孙权': 'sun_quan',
    '诸葛亮': 'zhuge_liang',
    '关羽': 'guan_yu',
    '张飞': 'zhang_fei',
    '赵云': 'zhao_yun',
    '马超': 'ma_chao',
    '黄忠': 'huang_zhong',
    '周瑜': 'zhou_yu',
    '司马懿': 'sima_yi',
    '吕布': 'lv_bu',
    '貂蝉': 'diao_chan',

    # 古代美女
    '西施': 'xi_shi',
    '王昭君': 'wang_zhaojun',
    '杨贵妃': 'yang_guifei',

    # 文学人物
    '花木兰': 'mulan',
    '梁山伯': 'liang_shanbo',
    '祝英台': 'zhu_yingtai',
    '白娘子': 'bai_niangzi',
    '许仙': 'xu_xian',
    '林黛玉': 'lin_daiyu',
    '贾宝玉': 'jia_baoyu',
    '薛宝钗': 'xue_baochai',
    '王熙凤': 'wang_xifeng',
    '史湘云': 'shi_xiangyun',

    # 文学家
    '李白': 'li_bai',
    '杜甫': 'du_fu',
    '白居易': 'bai_juyi',
    '苏轼': 'su_shi',
    '李清照': 'li_qingzhao',
    '辛弃疾': 'xin_qiji',
    '陆游': 'lu_you',
    '王维': 'wang_wei',
    '孟浩然': 'meng_haoran',

    # 军事家
    '岳飞': 'yue_fei',
    '韩信': 'han_xin',
    '霍去病': 'huo_qubing',
    '卫青': 'wei_qing',
    '李靖': 'li_jing',
    '郭子仪': 'guo_ziyi',

    # 科学家/发明家
    '张衡': 'zhang_heng',
    '祖冲之': 'zu_chongzhi',
    '沈括': 'shen_kuo',
    '郦道元': 'li_daoyuan',

    # 现代人物
    '毛泽东': 'mao_zedong',
    '周恩来': 'zhou_enlai',
    '邓小平': 'deng_xiaoping',
    '孙中山': 'sun_zhongshan',
    '鲁迅': 'lu_xun',
    '胡适': 'hu_shi',
    '梁启超': 'liang_qichao',
    '钱学森': 'qian_xuesen',
    '袁隆平': 'yuan_longping',

    # 武侠人物
    '令狐冲': 'linghu_chong',
    '郭靖': 'guo_jing',
    '黄蓉': 'huang_rong',
    '杨过': 'yang_guo',
    '小龙女': 'xiao_longnv',
    '韦小宝': 'wei_xiaobao',
    '张无忌': 'zhang_wuji',
    '赵敏': 'zhao_min',
    '周芷若': 'zhou_zhiruo',
    '任我行': 'ren_woxing',
    '东方不败': 'dongfang_bubai',

    # 动漫人物
    '孙悟饭': 'sun_wufan',
    '鸣人': 'ming_ren',
    '路飞': 'lu_fei',
    '柯南': 'ke_nan',
}


def is_chinese_name(name: str) -> bool:
    """检测是否为中文称谓"""
    # 检查是否包含中文字符
    chinese_char_pattern = re.compile(r'[\u4e00-\u9fff]+')
    return bool(chinese_char_pattern.search(name))


def generate_valid_character_id(name: str, character_repo, custom_id: str = None) -> str:
    """生成有效的角色ID - 支持自定义ID和智能拼音转换"""

    # 0. 如果用户提供了自定义ID，优先使用
    if custom_id and custom_id.strip():
        # 清理和验证自定义ID
        base_id = re.sub(r'[^a-zA-Z0-9_]', '_', custom_id.strip().lower())
        base_id = base_id.strip('_')
        base_id = re.sub(r'_+', '_', base_id)

        if base_id and base_id.replace('_', '') != '':
            app.logger.info(f"使用用户自定义ID: {name} -> {base_id}")
        else:
            app.logger.warning(f"自定义ID无效，将自动生成: {custom_id}")
            base_id = None

        if base_id:
            # 检查自定义ID是否已存在
            original_id = base_id
            counter = 1
            while character_repo.get_by_id(base_id):
                base_id = f"{original_id}_{counter}"
                counter += 1
            app.logger.info(f"最终自定义ID: {name} -> {base_id}")
            return base_id

    # 1. 优先检查预定义的中文名映射
    if name in CHINESE_NAME_TO_PINYIN:
        base_id = CHINESE_NAME_TO_PINYIN[name]
        app.logger.info(f"使用预定义拼音映射: {name} -> {base_id}")

    # 2. 如果是中文名但不在映射中
    elif is_chinese_name(name):
        # 尝试使用pypinyin库（如果已安装）
        try:
            from pypinyin import lazy_pinyin, Style
            # 使用不带声调的拼音，更适合做ID
            pinyin_list = lazy_pinyin(name, style=Style.NORMAL)
            base_id = '_'.join(pinyin_list).lower()

            # 清理可能的问题字符
            base_id = re.sub(r'[^a-zA-Z0-9_]', '_', base_id)
            base_id = re.sub(r'_+', '_', base_id).strip('_')

            app.logger.info(f"使用pypinyin转换: {name} -> {base_id}")

            # 如果pypinyin转换结果为空或无效，使用智能后备方案
            if not base_id or len(base_id) < 2:
                base_id = create_chinese_fallback_id(name)
                app.logger.info(f"pypinyin结果无效，使用后备方案: {name} -> {base_id}")

        except ImportError:
            # 如果没有安装pypinyin，使用智能后备方案
            base_id = create_chinese_fallback_id(name)
            app.logger.warning(f"pypinyin未安装，使用智能后备方案: {name} -> {base_id}")

    # 3. 对于英文或其他字符
    else:
        # 提取字母、数字和下划线
        base_id = re.sub(r'[^a-zA-Z0-9_]', '_', name.lower())
        base_id = base_id.strip('_')
        base_id = re.sub(r'_+', '_', base_id)

        # 如果结果为空，使用随机ID
        if not base_id or base_id.replace('_', '') == '':
            base_id = f"character_{secrets.token_hex(4)}"
            app.logger.warning(f"无法生成有效ID，使用随机ID: {name} -> {base_id}")

    # 限制长度
    base_id = base_id[:40]

    # 检查ID是否已存在，如果存在则添加后缀
    original_id = base_id
    counter = 1
    while character_repo.get_by_id(base_id):
        if counter > 100:
            base_id = f"{original_id}_{str(uuid.uuid4())[:8]}"
            break
        base_id = f"{original_id}_{counter}"
        counter += 1

    app.logger.info(f"最终生成的角色ID: {name} -> {base_id}")
    return base_id


def create_chinese_fallback_id(name: str) -> str:
    """为中文名创建智能后备ID"""
    # 简单的字符映射表
    char_map = {
        '小': 'xiao', '大': 'da', '老': 'lao', '新': 'xin', '古': 'gu',
        '东': 'dong', '西': 'xi', '南': 'nan', '北': 'bei', '中': 'zhong',
        '天': 'tian', '地': 'di', '人': 'ren', '王': 'wang', '李': 'li',
        '张': 'zhang', '刘': 'liu', '陈': 'chen', '杨': 'yang', '黄': 'huang',
        '赵': 'zhao', '吴': 'wu', '周': 'zhou', '徐': 'xu', '孙': 'sun',
        '马': 'ma', '朱': 'zhu', '胡': 'hu', '林': 'lin', '郭': 'guo',
        '何': 'he', '高': 'gao', '罗': 'luo', '郑': 'zheng', '梁': 'liang',
        '谢': 'xie', '宋': 'song', '唐': 'tang', '许': 'xu', '韩': 'han',
        '白': 'bai', '红': 'hong', '金': 'jin', '木': 'mu', '水': 'shui',
        '火': 'huo', '土': 'tu', '山': 'shan', '川': 'chuan', '风': 'feng',
        '云': 'yun', '雨': 'yu', '雪': 'xue', '花': 'hua', '草': 'cao',
        '树': 'shu', '石': 'shi', '月': 'yue', '日': 'ri', '星': 'xing',
        '春': 'chun', '夏': 'xia', '秋': 'qiu', '冬': 'dong', '年': 'nian',
        '明': 'ming', '亮': 'liang', '强': 'qiang', '伟': 'wei', '华': 'hua',
        '建': 'jian', '国': 'guo', '军': 'jun', '民': 'min', '文': 'wen',
        '学': 'xue', '生': 'sheng', '长': 'zhang', '成': 'cheng', '功': 'gong',
        '美': 'mei', '丽': 'li', '爱': 'ai', '心': 'xin', '情': 'qing',
        '梦': 'meng', '想': 'xiang', '希': 'xi', '望': 'wang', '来': 'lai',
        '去': 'qu', '上': 'shang', '下': 'xia', '左': 'zuo', '右': 'you',
        '前': 'qian', '后': 'hou', '内': 'nei', '外': 'wai', '好': 'hao',
        '坏': 'huai', '多': 'duo', '少': 'shao', '高': 'gao', '低': 'di',
        '快': 'kuai', '慢': 'man', '早': 'zao', '晚': 'wan', '今': 'jin',
        '昨': 'zuo', '明': 'ming', '青': 'qing', '蓝': 'lan', '绿': 'lv',
        '紫': 'zi', '粉': 'fen', '灰': 'hui', '黑': 'hei', '白': 'bai'
    }

    # 尝试映射每个字符
    mapped_chars = []
    for char in name:
        if char in char_map:
            mapped_chars.append(char_map[char])
        else:
            # 对于未知字符，使用unicode值生成简短标识
            unicode_val = ord(char)
            mapped_chars.append(f"u{unicode_val % 1000}")

    if mapped_chars:
        result = '_'.join(mapped_chars)
        # 如果结果太长，取前几个字符
        if len(result) > 30:
            result = '_'.join(mapped_chars[:3])
        return result
    else:
        # 最后的后备方案
        return f"chinese_{hash(name) % 10000}"


@app.route('/api/characters/<character_id>/delete', methods=['POST'])
def delete_character_form(character_id):
    """处理表单删除请求"""
    # 检查是否为默认角色
    protected_characters = ['harry_potter', 'sherlock_holmes', 'confucius',
                            'marie_curie', 'sun_wukong', 'einstein',
                            'mulan', 'elizabeth_bennet']

    if character_id in protected_characters:
        return redirect(url_for('character_management'))

    # 删除角色
    character_repo.delete_character(character_id)

    return redirect(url_for('character_management'))


@app.route('/api/characters/create', methods=['POST'])
def create_character_form():
    """处理表单创建请求"""
    try:
        # 获取表单数据
        name = request.form.get('name')
        description = request.form.get('description')
        personality = request.form.get('personality')
        background = request.form.get('background')
        category = request.form.get('category')
        greeting = request.form.get('greeting')
        skills = request.form.get('skills', '')
        gender = request.form.get('gender', 'female')
        age = request.form.get('age', 'adult')
        temperature_modifier = float(request.form.get('temperature_modifier', 0))

        # 新增：获取用户自定义的角色ID（可选）
        custom_id = request.form.get('custom_id', '').strip()

        app.logger.info(f"开始创建角色: {name}, 自定义ID: {custom_id}")

        # 使用改进的ID生成函数，支持自定义ID
        character_id = generate_valid_character_id(name, character_repo, custom_id)
        app.logger.info(f"生成角色ID: {character_id}")

        # 处理文件上传 - 修复：使用角色ID作为文件名
        avatar_url = '/static/images/characters/default.png'
        if 'avatar_file' in request.files:
            file = request.files['avatar_file']
            if file and file.filename:
                # 验证文件类型
                allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
                filename = file.filename.lower()

                if any(filename.endswith(ext) for ext in allowed_extensions):
                    # 使用角色ID作为文件名
                    ext = filename.split('.')[-1]
                    safe_filename = f"{character_id}.{ext}"

                    # 保存文件
                    avatar_path = os.path.join('static/images/characters', safe_filename)

                    # 如果文件已存在，先删除旧文件
                    if os.path.exists(avatar_path):
                        try:
                            os.remove(avatar_path)
                            app.logger.info(f"删除旧头像文件: {avatar_path}")
                        except:
                            pass

                    file.save(avatar_path)

                    # 更新URL
                    avatar_url = f"/static/images/characters/{safe_filename}"
                    app.logger.info(f"头像已保存: {avatar_url}")

        # 处理技能列表
        if skills:
            skills_list = [s.strip() for s in skills.split(',') if s.strip()]
        else:
            skills_list = []

        # 创建角色数据
        character_data = {
            'id': character_id,
            'name': name,
            'description': description,
            'personality': personality,
            'background': background,
            'avatar': avatar_url,
            'category': category,
            'greeting': greeting,
            'skills': skills_list,
            'voice_config': {
                'gender': gender,
                'age': age,
                'accent': 'chinese'
            },
            'temperature_modifier': temperature_modifier
        }

        # 创建角色对象
        character = character_repo.create_character_from_dict(character_data)

        if character is None:
            app.logger.error(f"创建角色对象失败: {name}")
            return render_template('character_management.html',
                                   characters=character_repo.get_all(),
                                   categories=character_repo.get_categories(),
                                   error_message='创建角色失败,请重试'), 400

        app.logger.info(f"角色对象已创建: {character.id}, {character.name}")

        # 添加到仓库
        success = character_repo.add_character(character)

        if not success:
            app.logger.error(f"角色添加到仓库失败: {character_id}")
            return render_template('character_management.html',
                                   characters=character_repo.get_all(),
                                   categories=character_repo.get_categories(),
                                   error_message='保存角色失败,请重试'), 400

        app.logger.info(f"角色已成功添加到仓库: {character_id}")

        # 验证角色是否真的被保存了
        saved_character = character_repo.get_by_id(character_id)
        if saved_character:
            app.logger.info(f"验证成功: 角色 {character_id} 已存在于仓库中")
        else:
            app.logger.error(f"验证失败: 角色 {character_id} 不在仓库中!")

        return redirect(url_for('character_management'))

    except Exception as e:
        app.logger.error(f"创建角色时出错: {str(e)}")
        import traceback
        app.logger.error(traceback.format_exc())
        return render_template('character_management.html',
                               characters=character_repo.get_all(),
                               categories=character_repo.get_categories(),
                               error_message=f'创建角色失败: {str(e)}'), 500


@app.route('/admin/characters')
def character_management():
    """角色管理页面"""
    characters = character_repo.get_all()
    categories = character_repo.get_categories()

    # 调试信息
    app.logger.info(f"角色管理页面 - 当前角色数量: {len(characters)}")
    for char in characters:
        app.logger.debug(f"角色: {char.id} - {char.name}")

    return render_template('character_management.html',
                           characters=characters,
                           categories=categories)


@app.route('/api/characters/<character_id>', methods=['DELETE'])
def delete_character(character_id):
    """删除角色API"""
    # 检查是否为默认角色(可选保护)
    protected_characters = ['harry_potter', 'sherlock_holmes', 'confucius',
                            'marie_curie', 'sun_wukong', 'einstein',
                            'mulan', 'elizabeth_bennet']

    if character_id in protected_characters:
        return jsonify({'error': '默认角色不能删除'}), 403

    # 删除角色
    if character_repo.delete_character(character_id):
        return jsonify({'success': True, 'message': '角色删除成功'})
    else:
        return jsonify({'error': '角色不存在'}), 404


@app.route('/api/characters', methods=['POST'])
def create_character():
    """创建新角色API"""
    data = request.get_json()

    # 验证必填字段
    required_fields = ['name', 'description', 'personality', 'background',
                       'category', 'greeting']

    for field in required_fields:
        if field not in data or not data[field].strip():
            return jsonify({'error': f'缺少必填字段: {field}'}), 400

    # 获取用户自定义ID（可选）
    custom_id = data.get('custom_id', '').strip()

    # 使用改进的ID生成函数，支持自定义ID
    character_id = generate_valid_character_id(data['name'], character_repo, custom_id)

    # 处理技能列表
    skills = data.get('skills', [])
    if isinstance(skills, str):
        skills = [s.strip() for s in skills.split(',') if s.strip()]

    # 创建角色数据
    character_data = {
        'id': character_id,
        'name': data['name'],
        'description': data['description'],
        'personality': data['personality'],
        'background': data['background'],
        'avatar': data.get('avatar', '/static/images/characters/default.png'),
        'category': data['category'],
        'greeting': data['greeting'],
        'skills': skills,
        'voice_config': {
            'gender': data.get('gender', 'female'),
            'age': data.get('age', 'adult'),
            'accent': 'chinese'
        },
        'chat_examples': data.get('chat_examples', []),
        'temperature_modifier': float(data.get('temperature_modifier', 0.0))
    }

    try:
        # 创建角色
        character = character_repo.create_character_from_dict(character_data)

        if character is None:
            return jsonify({'error': '创建角色对象失败'}), 500

        # 添加到仓库
        if character_repo.add_character(character):
            return jsonify({
                'success': True,
                'character': character.to_dict(),
                'message': '角色创建成功',
                'generated_id': character_id  # 返回生成的ID供参考
            }), 201
        else:
            return jsonify({'error': '角色保存失败'}), 500

    except Exception as e:
        app.logger.error(f"创建角色API错误: {str(e)}")
        return jsonify({'error': f'创建角色时出错: {str(e)}'}), 500


@app.route('/api/characters/<character_id>', methods=['PUT'])
def update_character(character_id):
    """更新角色信息API"""
    data = request.get_json()

    # 检查角色是否存在
    if not character_repo.get_by_id(character_id):
        return jsonify({'error': '角色不存在'}), 404

    # 处理技能列表
    if 'skills' in data and isinstance(data['skills'], str):
        data['skills'] = [s.strip() for s in data['skills'].split(',') if s.strip()]

    # 更新角色
    if character_repo.update_character(character_id, data):
        character = character_repo.get_by_id(character_id)
        return jsonify({
            'success': True,
            'character': character.to_dict(),
            'message': '角色更新成功'
        })
    else:
        return jsonify({'error': '角色更新失败'}), 500


@app.route('/api/upload/avatar', methods=['POST'])
def upload_avatar():
    """上传角色头像"""
    if 'avatar' not in request.files:
        return jsonify({'error': '没有上传文件'}), 400

    file = request.files['avatar']
    if file.filename == '':
        return jsonify({'error': '没有选择文件'}), 400

    # 验证文件类型
    allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    filename = file.filename.lower()

    if not any(filename.endswith(ext) for ext in allowed_extensions):
        return jsonify({'error': '不支持的文件格式'}), 400

    # 获取角色ID（从表单或请求参数）
    character_id = request.form.get('character_id')
    if not character_id:
        # 如果没有提供角色ID，使用随机名称
        character_id = f"avatar_{secrets.token_hex(4)}"

    # 生成文件名
    ext = filename.split('.')[-1]
    safe_filename = f"{character_id}.{ext}"

    # 保存文件
    avatar_path = os.path.join('static/images/characters', safe_filename)

    # 如果文件已存在，先删除旧文件
    if os.path.exists(avatar_path):
        try:
            os.remove(avatar_path)
        except:
            pass

    file.save(avatar_path)

    # 返回URL
    avatar_url = f"/static/images/characters/{safe_filename}"

    return jsonify({
        'success': True,
        'avatar_url': avatar_url
    })


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
        app.logger.error(f"Character not found: {character_id}")
        abort(404)

    similar_characters = character_repo.get_similar_characters(character_id)

    return render_template('character.html',
                           character=character,
                           similar_characters=similar_characters,
                           ai_enabled=ai_service.is_configured())


@app.route('/chat/<character_id>')
def chat_page(character_id):
    """聊天页面"""
    app.logger.info(f"访问聊天页面 - Character ID: {character_id}")

    character = character_repo.get_by_id(character_id)
    if not character:
        app.logger.error(f"Character not found: {character_id}")
        app.logger.info(f"当前仓库中的角色: {[c.id for c in character_repo.get_all()]}")
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
    try:
        app.logger.info(f"Creating chat session for user {user_id} and character {character_id}")
        app.logger.info(f"Character details: {character.name}, {character.id}")
        app.logger.info(f"AI Service configured: {ai_service.is_configured()}")
        app.logger.info(f"ChatService instance: {chat_service}")

        # 修复：添加更详细的调试信息
        app.logger.info(f"ChatService AI服务状态: {chat_service.ai_service.is_configured()}")
        app.logger.info(f"ChatService 角色仓库角色数: {len(chat_service.character_repo.get_all())}")

        chat_session = chat_service.start_chat_session(user_id, character_id)

        if chat_session is None:
            app.logger.error(f"Failed to create chat session for user {user_id} and character {character_id}")
            app.logger.error(f"ChatService returned None")

            # 额外调试信息
            test_char = character_repo.get_by_id(character_id)
            app.logger.error(f"再次验证角色是否存在: {test_char is not None}")
            if test_char:
                app.logger.info(f"角色存在，详情: {test_char.name}, {test_char.greeting[:50]}")

            # 检查可能的原因
            if not ai_service.is_configured():
                error_msg = "AI服务未配置。请检查环境变量中的API密钥设置。"
            else:
                error_msg = "无法创建聊天会话。请检查日志以获取更多信息。"

            # 尝试返回错误页面，如果没有则返回简单的错误信息
            try:
                return render_template('error.html',
                                       error_message=error_msg,
                                       character=character), 500
            except:
                return f"""
                <html>
                <head>
                    <title>错误</title>
                    <meta charset="UTF-8">
                    <style>
                        body {{ font-family: Arial, sans-serif; padding: 20px; background: #f5f5f5; }}
                        .error-container {{ background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); max-width: 600px; margin: 0 auto; }}
                        h1 {{ color: #d32f2f; }}
                        .info {{ background: #f5f5f5; padding: 15px; border-radius: 5px; margin: 15px 0; }}
                        .actions a {{ display: inline-block; padding: 10px 20px; margin: 10px 5px; background: #007bff; color: white; text-decoration: none; border-radius: 5px; }}
                        .actions a:hover {{ background: #0056b3; }}
                    </style>
                </head>
                <body>
                    <div class="error-container">
                        <h1>出错了</h1>
                        <p>{error_msg}</p>
                        <div class="info">
                            <p><strong>角色:</strong> {character.name}</p>
                            <p><strong>角色ID:</strong> {character_id}</p>
                            <p><strong>AI服务状态:</strong> {'已配置' if ai_service.is_configured() else '未配置'}</p>
                        </div>
                        <div class="actions">
                            <a href="/character/{character_id}">返回角色页面</a>
                            <a href="/">返回主页</a>
                        </div>
                    </div>
                </body>
                </html>
                """, 500

        app.logger.info(f"Chat session created successfully: {chat_session.id}")

        return render_template('chat.html',
                               character=character,
                               session_id=chat_session.id,
                               ai_enabled=ai_service.is_configured())

    except Exception as e:
        app.logger.error(f"Error creating chat session: {str(e)}")
        import traceback
        app.logger.error(traceback.format_exc())

        # 尝试返回错误页面，如果没有则返回简单的错误信息
        try:
            return render_template('error.html',
                                   error_message=f"创建聊天会话时出错: {str(e)}",
                                   character=character), 500
        except:
            return f"""
            <html>
            <head>
                <title>错误</title>
                <meta charset="UTF-8">
                <style>
                    body {{ font-family: Arial, sans-serif; padding: 20px; background: #f5f5f5; }}
                    .error-container {{ background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); max-width: 600px; margin: 0 auto; }}
                    h1 {{ color: #d32f2f; }}
                    .error-details {{ background: #ffebee; padding: 15px; border-radius: 5px; margin: 15px 0; font-family: monospace; }}
                    .actions a {{ display: inline-block; padding: 10px 20px; margin: 10px 5px; background: #007bff; color: white; text-decoration: none; border-radius: 5px; }}
                    .actions a:hover {{ background: #0056b3; }}
                </style>
            </head>
            <body>
                <div class="error-container">
                    <h1>系统错误</h1>
                    <p>创建聊天会话时发生错误。</p>
                    <div class="error-details">
                        {str(e)}
                    </div>
                    <div class="actions">
                        <a href="/character/{character_id}">返回角色页面</a>
                        <a href="/">返回主页</a>
                    </div>
                </div>
            </body>
            </html>
            """, 500


@app.route('/about')
def about():
    """关于页面"""
    stats = {
        'total_characters': len(character_repo.get_all()),
        'categories': len(character_repo.get_categories()),
        'ai_models': ai_service.get_available_models()
    }
    return render_template('about.html', stats=stats)


# 静态文件路由(确保静态文件可以正常访问)
@app.route('/static/<path:filename>')
def static_files(filename):
    """静态文件服务"""
    return app.send_static_file(filename)


# 调试路由
@app.route('/debug/characters')
def debug_characters():
    """调试角色列表"""
    characters = character_repo.get_all()

    char_list = []
    for char in characters:
        char_list.append({
            'id': char.id,
            'name': char.name,
            'description': char.description[:50] + '...' if len(char.description) > 50 else char.description
        })

    return jsonify({
        'total': len(characters),
        'characters': char_list
    })


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
        return jsonify({'error': '服务暂时不可用,请稍后再试'}), 503


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
        # 直接在这里获取角色信息,而不是在VoiceService中
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
    # 新增:检查是否来自语音通话
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
        return jsonify({'error': '服务暂时不可用,请稍后再试'}), 503


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

        # 在新线程中处理AI响应(使用流式响应)
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

                # 关键修改:传递 is_voice_call=True
                for chunk in chat_service.send_message_stream(session_id, transcript, is_voice_call=True):
                    full_response += chunk
                    sentence_buffer += chunk

                    # 检测句子结束(中文句号、问号、感叹号或英文句号)
                    sentence_endings = ['。', '!', '?', '.', '!', '?']

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

                # 发送完整响应(用于记录)
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
