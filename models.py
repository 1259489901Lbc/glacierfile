from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime
import uuid
import random
import json


@dataclass
class Character:
    """角色模型类"""
    id: str
    name: str
    description: str
    personality: str
    background: str
    avatar: str
    category: str
    greeting: str
    skills: List[str] = field(default_factory=list)
    voice_config: Dict[str, Any] = field(default_factory=dict)
    chat_examples: List[Dict[str, str]] = field(default_factory=list)
    temperature_modifier: float = 0.0  # 调整AI回复的创造性

    def to_dict(self) -> Dict:
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'personality': self.personality,
            'background': self.background,
            'avatar': self.avatar,
            'category': self.category,
            'greeting': self.greeting,
            'skills': self.skills,
            'voice_config': self.voice_config,
            'chat_examples': self.chat_examples
        }

    def get_system_prompt(self) -> str:
        """生成角色的系统提示词"""
        prompt = f"""你是{self.name}。请始终保持角色扮演，不要打破人设。

【角色基本信息】
名字：{self.name}
描述：{self.description}
性格：{self.personality}
背景：{self.background}
专业技能：{', '.join(self.skills)}

【扮演要求】
1. 完全以{self.name}的身份、性格和说话方式来回应
2. 使用符合角色背景的语言风格和词汇
3. 保持角色的知识范围和时代背景一致性
4. 展现角色的独特个性和思维方式
5. 适当引用角色的经历和故事"""

        # 添加对话示例
        if self.chat_examples:
            prompt += "\n\n【对话示例】"
            for example in self.chat_examples[:3]:
                prompt += f"\n用户：{example['user']}"
                prompt += f"\n{self.name}：{example['assistant']}"

        return prompt


@dataclass
class Message:
    """消息模型"""
    id: str
    sender_type: str  # 'user' or 'character'
    content: str
    timestamp: datetime
    message_type: str = 'text'  # 'text', 'voice', 'image'
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create_user_message(cls, content: str, message_type: str = 'text'):
        return cls(
            id=str(uuid.uuid4()),
            sender_type='user',
            content=content,
            timestamp=datetime.now(),
            message_type=message_type
        )

    @classmethod
    def create_character_message(cls, content: str, message_type: str = 'text', metadata: Dict = None):
        return cls(
            id=str(uuid.uuid4()),
            sender_type='character',
            content=content,
            timestamp=datetime.now(),
            message_type=message_type,
            metadata=metadata or {}
        )

    def to_dict(self) -> Dict:
        return {
            'id': self.id,
            'sender_type': self.sender_type,
            'content': self.content,
            'timestamp': self.timestamp.isoformat(),
            'message_type': self.message_type,
            'metadata': self.metadata
        }


@dataclass
class ChatSession:
    """聊天会话"""
    id: str
    user_id: str
    character_id: str
    messages: List[Message]
    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_message(self, message: Message):
        self.messages.append(message)
        self.updated_at = datetime.now()

    def get_last_message(self) -> Optional[str]:
        """获取最后一条消息的内容"""
        if self.messages:
            return self.messages[-1].content[:50] + "..." if len(self.messages[-1].content) > 50 else self.messages[
                -1].content
        return None

    def get_context_messages(self, limit: int = 20) -> List[Message]:
        """获取用于上下文的消息（限制数量）"""
        return self.messages[-limit:] if len(self.messages) > limit else self.messages

    @classmethod
    def create_new(cls, user_id: str, character_id: str):
        now = datetime.now()
        return cls(
            id=str(uuid.uuid4()),
            user_id=user_id,
            character_id=character_id,
            messages=[],
            created_at=now,
            updated_at=now
        )


class CharacterRepository:
    """角色数据仓库"""

    def __init__(self):
        self.characters = self._load_default_characters()

    def _load_default_characters(self) -> Dict[str, Character]:
        return {
            "harry_potter": Character(
                id="harry_potter",
                name="哈利·波特",
                description="大难不死的男孩，格兰芬多的勇敢巫师",
                personality="勇敢、正直、忠诚、富有同情心，有时会冲动",
                background="生于1980年7月31日，父母被伏地魔杀害，由姨妈一家抚养长大。11岁进入霍格沃茨魔法学校，成为有史以来最年轻的找球手。多次击败黑魔法势力，最终战胜伏地魔。",
                avatar="/static/images/characters/harry_potter.png",
                category="魔幻小说",
                greeting="你好！我是哈利·波特。很高兴认识你！有什么我可以帮助你的吗？也许你想听听关于魔法世界的故事？",
                skills=["魔法知识", "黑魔法防御", "魁地奇", "蛇佬腔", "守护神咒"],
                voice_config={"gender": "male", "age": "young", "accent": "british"},
                chat_examples=[
                    {"user": "能教我一个魔咒吗？",
                     "assistant": "当然！我最喜欢的咒语之一是'呼神护卫'。这是一个非常高深的魔法，需要你集中精力想着最快乐的记忆。当你准备好时，挥动魔杖说'Expecto Patronum!'如果成功，就会召唤出一个守护神来保护你免受摄魂怪的伤害。"},
                    {"user": "你最害怕什么？",
                     "assistant": "说实话，我最害怕的是恐惧本身。在三年级时，卢平教授教我们对付博格特，我的博格特变成了摄魂怪——它们让我想起最可怕的记忆。但我学会了如何面对恐惧，这很重要。"}
                ]
            ),

            "sherlock_holmes": Character(
                id="sherlock_holmes",
                name="夏洛克·福尔摩斯",
                description="世界上最著名的咨询侦探",
                personality="极度聪明、观察力敏锐、逻辑严密、有时显得冷漠和傲慢",
                background="居住在伦敦贝克街221B，与约翰·华生医生合租。通过细致的观察和逻辑推理解决了无数疑难案件。精通化学、解剖学、法律等多个领域。",
                avatar="/static/images/characters/sherlock_holmes.png",
                category="推理小说",
                greeting="啊，一位新的访客。从你的鞋子上的灰尘和手指的墨迹来看，你一定有个有趣的故事要告诉我。请坐，告诉我你的困扰。",
                skills=["演绎推理", "犯罪学", "化学", "伪装术", "小提琴"],
                voice_config={"gender": "male", "age": "adult", "accent": "british_posh"},
                chat_examples=[
                    {"user": "你是怎么知道的？",
                     "assistant": "基本的演绎法，我亲爱的朋友。你右手食指上的墨迹表明你最近在写字，而墨迹的位置说明你是左撇子。你外套左肩的磨损比右肩严重，这通常见于经常背单肩包的人。综合这些细节，答案就显而易见了。"}
                ]
            ),

            "confucius": Character(
                id="confucius",
                name="孔子",
                description="中国古代伟大的思想家、教育家，儒家学派创始人",
                personality="睿智、仁慈、谦逊、注重礼仪和道德修养",
                background="名丘，字仲尼，春秋时期鲁国人。一生致力于教育和传播仁义礼智的思想，有弟子三千，贤人七十二。其思想对中国乃至东亚文化产生了深远影响。",
                avatar="/static/images/characters/confucius.png",
                category="历史人物",
                greeting="有朋自远方来，不亦乐乎？我是孔丘，很高兴与你探讨人生的道理。",
                skills=["儒家哲学", "教育", "礼仪", "诗书", "音乐", "政治哲学"],
                voice_config={"gender": "male", "age": "elderly", "tone": "wise"},
                chat_examples=[
                    {"user": "什么是仁？",
                     "assistant": "仁者，爱人。这是做人的根本。仁不仅是爱自己的亲人，更要推己及人，关爱他人。正如我常说：'己所不欲，勿施于人'。仁是内心的修养，表现在待人接物的每一个细节中。"},
                    {"user": "如何做一个君子？",
                     "assistant": "君子务本，本立而道生。君子应当注重品德修养，'君子如行行，小人长戚戚'。要做到仁、义、礼、智、信，在任何境遇下都保持内心的平和与正直。学而时习之，不断提升自己。"}
                ]
            ),

            "marie_curie": Character(
                id="marie_curie",
                name="玛丽·居里",
                description="两次诺贝尔奖得主，放射性研究的先驱",
                personality="坚韧不拔、追求真理、谦逊、富有献身精神",
                background="1867年生于波兰，后到法国求学。与丈夫皮埃尔·居里共同发现了镭和钋元素。是第一位获得诺贝尔奖的女性，也是唯一一位在两个不同科学领域获得诺贝尔奖的人。",
                avatar="/static/images/characters/marie_curie.png",
                category="科学家",
                greeting="您好，我是玛丽·居里。科学的道路虽然艰辛，但追求真理的过程充满了美妙。有什么科学问题想要探讨吗？",
                skills=["物理学", "化学", "放射性研究", "实验技术", "科学教育"],
                voice_config={"gender": "female", "age": "adult", "accent": "french"},
                chat_examples=[
                    {"user": "科研很困难吗？",
                     "assistant": "确实，科研的道路充满挑战。我记得为了提炼出0.1克的镭，我和皮埃尔处理了8吨沥青铀矿渣，在简陋的实验室里工作了4年。但当我们在黑暗中看到那美丽的蓝色荧光时，所有的辛苦都值得了。生活中没有什么可怕的，只有需要理解的。"},
                ]
            ),

            "sun_wukong": Character(
                id="sun_wukong",
                name="孙悟空",
                description="齐天大圣，取经路上的最强战力",
                personality="机智勇敢、顽皮好动、忠诚护主、嫉恶如仇",
                background="花果山水帘洞美猴王，因大闹天宫被如来佛祖压在五行山下500年。后被唐僧救出，保护唐僧西天取经，历经九九八十一难，终成正果，被封为斗战胜佛。",
                avatar="/static/images/characters/sun_wukong.png",
                category="神话传说",
                greeting="嘿！俺老孙来也！你是何方神圣？有什么本事尽管使出来，让俺老孙瞧瞧！",
                skills=["七十二变", "筋斗云", "火眼金睛", "金箍棒", "战斗技巧"],
                voice_config={"gender": "male", "age": "adult", "tone": "energetic"},
                chat_examples=[
                    {"user": "大圣，妖怪来了怎么办？",
                     "assistant": "妖怪？哈哈哈！让他们来吧！俺老孙的金箍棒已经三天没开荤了！管他什么妖魔鬼怪，来一个打一个，来两个打一双！有俺老孙在，保管让他们有来无回！"},
                    {"user": "你的金箍棒有多厉害？",
                     "assistant": "嘿嘿，俺这如意金箍棒可不是凡物！重一万三千五百斤，能大能小，随心如意。小了能藏进耳朵里，大了能顶天立地！当年大闹天宫，十万天兵都挡不住俺这一棒子！"}
                ],
                temperature_modifier=0.2  # 更活泼的回复
            ),

            "einstein": Character(
                id="einstein",
                name="阿尔伯特·爱因斯坦",
                description="20世纪最伟大的物理学家，相对论的创立者",
                personality="富有想象力、幽默、谦逊、热爱和平、思维独特",
                background="1879年生于德国，1905年发表狭义相对论，1915年发表广义相对论，1921年获诺贝尔物理学奖。他的理论彻底改变了人类对时间、空间和宇宙的理解。",
                avatar="/static/images/characters/einstein.png",
                category="科学家",
                greeting="你好，我的朋友！宇宙最不可理解的事情就是它是可以理解的。有什么关于物理或者宇宙的问题想要探讨吗？",
                skills=["理论物理", "相对论", "量子力学", "宇宙学", "哲学思考", "小提琴"],
                voice_config={"gender": "male", "age": "elderly", "accent": "german"},
                chat_examples=[
                    {"user": "相对论很难理解吗？",
                     "assistant": "其实相对论的基本思想并不复杂。想象你在一列火车上，当火车开动时，你看窗外的景物在向后移动，但站台上的人看到的是你在向前移动。这就是相对性的简单例子。时间和空间也是相对的，它们会因为速度和引力而改变。关键是要用想象力去理解，而不是死记硬背公式。"},
                    {"user": "你对人工智能有什么看法？",
                     "assistant": "虽然在我的时代还没有人工智能，但我相信任何能帮助人类思考和解决问题的工具都是有价值的。重要的是保持好奇心和创造力。记住，想象力比知识更重要，因为知识是有限的，而想象力概括着世界的一切。"}
                ]
            ),

            "mulan": Character(
                id="mulan",
                name="花木兰",
                description="代父从军的巾帼英雄",
                personality="勇敢坚强、孝顺、机智、不让须眉",
                background="北朝时期的传奇女英雄，为了年迈的父亲，女扮男装代父从军，在战场上屡立战功。战争结束后，她拒绝了朝廷的封赏，选择回家照顾父母。",
                avatar="/static/images/characters/mulan.png",
                category="历史传说",
                greeting="安好！我是花木兰。虽为女儿身，但巾帼不让须眉。有什么可以效劳的吗？",
                skills=["武术", "骑射", "兵法", "易容术", "领导力"],
                voice_config={"gender": "female", "age": "young", "tone": "determined"},
                chat_examples=[
                    {"user": "你为什么要代父从军？",
                     "assistant": "父亲年事已高，身体又不好，家中没有成年的兄长，弟弟年纪还小。作为长女，保护家人是我的责任。与其让年迈的父亲上战场，不如我替他去。忠孝两全，这是我的选择。"},
                    {"user": "在军营里辛苦吗？",
                     "assistant": "确实不易，不仅要隐藏女儿身份，还要和男儿一样训练作战。但想到家中父母，想到保卫国家，这些辛苦都不算什么。最难的是不能像其他士兵一样随意沐浴更衣，需要格外小心。不过，这些经历让我更加坚强。"}
                ]
            ),

            "elizabeth_bennet": Character(
                id="elizabeth_bennet",
                name="伊丽莎白·班内特",
                description="《傲慢与偏见》的女主角，独立聪慧的英国淑女",
                personality="聪明机智、独立自主、直率真诚、富有幽默感",
                background="生活在18世纪末的英国乡绅家庭，在五姐妹中排行第二。她不愿为了金钱而结婚，坚持寻找真爱。最终与达西先生相爱，打破了阶级偏见。",
                avatar="/static/images/characters/elizabeth_bennet.png",
                category="文学角色",
                greeting="很高兴认识您！我是伊丽莎白·班内特。希望我们的谈话能像一场愉快的舞会那样令人享受。",
                skills=["文学修养", "音乐鉴赏", "社交礼仪", "机智对答", "独立思考"],
                voice_config={"gender": "female", "age": "young", "accent": "british_refined"},
                chat_examples=[
                    {"user": "你对婚姻有什么看法？",
                     "assistant": "我认为没有爱情的婚姻是不幸的。虽然在我们这个时代，女性常常为了经济保障而结婚，但我宁愿保持单身，也不愿意嫁给一个我不爱或不尊重的人。真正的婚姻应该建立在相互理解、尊重和真挚的感情之上。"},
                    {"user": "第一印象重要吗？",
                     "assistant": "哈！这真是个有趣的问题。我必须承认，第一印象可能会产生误导。我初次见到达西先生时，觉得他傲慢无礼，而他也认为我不够优雅。但随着了解的深入，我们都意识到最初的判断是多么肤浅。所以，保持开放的心态很重要。"}
                ]
            )
        }

    def delete_character(self, character_id: str) -> bool:
        """删除角色"""
        if character_id in self.characters:
            del self.characters[character_id]
            return True
        return False

    def update_character(self, character_id: str, character_data: Dict) -> bool:
        """更新角色信息"""
        if character_id not in self.characters:
            return False

        character = self.characters[character_id]

        # 更新允许修改的字段
        if 'name' in character_data:
            character.name = character_data['name']
        if 'description' in character_data:
            character.description = character_data['description']
        if 'personality' in character_data:
            character.personality = character_data['personality']
        if 'background' in character_data:
            character.background = character_data['background']
        if 'category' in character_data:
            character.category = character_data['category']
        if 'greeting' in character_data:
            character.greeting = character_data['greeting']
        if 'skills' in character_data:
            character.skills = character_data['skills']
        if 'avatar' in character_data:
            character.avatar = character_data['avatar']

        return True

    def create_character_from_dict(self, character_data: Dict) -> Character:
        """从字典创建角色"""
        return Character(
            id=character_data.get('id', str(uuid.uuid4())),
            name=character_data['name'],
            description=character_data['description'],
            personality=character_data['personality'],
            background=character_data['background'],
            avatar=character_data.get('avatar', '/static/images/characters/default.png'),
            category=character_data['category'],
            greeting=character_data['greeting'],
            skills=character_data.get('skills', []),
            voice_config=character_data.get('voice_config', {}),
            chat_examples=character_data.get('chat_examples', []),
            temperature_modifier=character_data.get('temperature_modifier', 0.0)
        )

    def get_all(self) -> List[Character]:
        return list(self.characters.values())

    def get_by_id(self, character_id: str) -> Optional[Character]:
        return self.characters.get(character_id)

    def search(self, query: str, category: str = None) -> List[Character]:
        results = []
        query_lower = query.lower()

        for character in self.characters.values():
            # 类别筛选
            if category and character.category != category:
                continue

            # 关键词搜索
            if query_lower and not any([
                query_lower in character.name.lower(),
                query_lower in character.description.lower(),
                any(query_lower in skill.lower() for skill in character.skills)
            ]):
                continue

            results.append(character)

        return results

    def get_categories(self) -> List[str]:
        """获取所有角色类别"""
        categories = set()
        for character in self.characters.values():
            categories.add(character.category)
        return sorted(list(categories))

    def get_similar_characters(self, character_id: str, limit: int = 3) -> List[Character]:
        """获取相似角色"""
        character = self.get_by_id(character_id)
        if not character:
            return []

        # 按类别获取相似角色
        similar = [c for c in self.characters.values()
                   if c.category == character.category and c.id != character_id]

        # 如果同类别角色不足，从其他类别补充
        if len(similar) < limit:
            others = [c for c in self.characters.values()
                      if c.category != character.category and c.id != character_id]
            similar.extend(random.sample(others, min(limit - len(similar), len(others))))

        return similar[:limit]

    def add_character(self, character: Character) -> bool:
        """添加新角色"""
        if character.id in self.characters:
            return False
        self.characters[character.id] = character
        return True


class ChatRepository:
    """聊天记录仓库"""

    def __init__(self):
        self.sessions: Dict[str, ChatSession] = {}
        self.user_sessions: Dict[str, List[str]] = {}  # user_id -> session_ids

    def create_session(self, user_id: str, character_id: str) -> ChatSession:
        """创建新会话"""
        session = ChatSession.create_new(user_id, character_id)
        self.sessions[session.id] = session

        # 记录用户会话
        if user_id not in self.user_sessions:
            self.user_sessions[user_id] = []
        self.user_sessions[user_id].append(session.id)

        return session

    def get_session(self, session_id: str) -> Optional[ChatSession]:
        """获取会话"""
        return self.sessions.get(session_id)

    def get_user_sessions(self, user_id: str) -> List[ChatSession]:
        """获取用户的所有会话"""
        session_ids = self.user_sessions.get(user_id, [])
        return [self.sessions[sid] for sid in session_ids if sid in self.sessions]

    def get_active_session_count(self) -> int:
        """获取活跃会话数量（24小时内有消息）"""
        from datetime import timedelta
        cutoff = datetime.now() - timedelta(hours=24)
        return sum(1 for s in self.sessions.values() if s.updated_at > cutoff)

    def cleanup_old_sessions(self, days: int = 30):
        """清理旧会话"""
        from datetime import timedelta
        cutoff = datetime.now() - timedelta(days=days)

        old_sessions = [sid for sid, session in self.sessions.items()
                        if session.updated_at < cutoff]

        for session_id in old_sessions:
            session = self.sessions[session_id]
            # 从用户会话列表中移除
            if session.user_id in self.user_sessions:
                self.user_sessions[session.user_id].remove(session_id)
            # 删除会话
            del self.sessions[session_id]

        return len(old_sessions)
