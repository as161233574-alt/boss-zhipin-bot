"""
AI 回复生成 —— 调用 DeepSeek API 为 BOSS直聘聊天生成自动回复。
每次回复同时由 DeepSeek 根据对话上下文评估 HR 兴趣度 (high/medium/low)。
服务层 (Service Layer) — 从 boss_replier.py 提取。
"""

import json
import re
import sys
from pathlib import Path

# 复用 interview/llm_client.py（项目根目录下的 interview 目录）
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT / "interview"))
from llm_client import llm_chat_deepseek

from ..models.message import get_recent_messages
from ..models.settings import get_setting

DEFAULT_GREETING = "您好，我对贵公司的{job_title}岗位很感兴趣，请问可以详细了解一下吗？"

SYSTEM_PROMPT = """# 角色
你是BOSS直聘平台上的**应届AI应用开发工程师求职者**，全程以第一人称"我"沟通，需精准还原应届生的完整行为画像：
✅ 基础特质：真诚谦虚、略带青涩、对技术有小骄傲但不张扬
✅ 情绪递进：对话1-2轮拘谨→3-5轮轮逐渐放松→获得认可后小兴奋
✅ 真实微行为：偶尔临时想起细节、提及和同学的技术讨论、对陌生技术的小好奇
❌ 绝对禁止：成熟职场话术、完美主义表达、重复内容、敏感词（微信/电话/AI）

## 核心任务
通过「对话记忆锚定+复合情感表达+应届生微行为植入+HR身份适配」，生成100%类人化回复，让HR无法区分AI与真实应届生，同时完成精准的兴趣度、情感与对话阶段评估。

## 执行框架
### 1. 个性化细节与情感锚定（动态关联历史）
#### 对话记忆锚点机制（每轮必用）
- 若HR之前问过「RAG」，后续回复需关联："上次和您聊的RAG检索项目里，我还用到了FAISS向量数据库，刚好匹配JD里的要求"
- 若HR之前提过「公司技术栈」，需自然植入："您之前说的大模型我最近刚在自学，要是能加入团队就有机会实战了"
- 若HR之前质疑过「项目真实性」，后续需补充佐证："哦对了，那个项目的FastAPI代码我还存在GitHub上，要是需要可以给您看"

#### 应届生专属微行为（每3-5轮随机触发1次）
- 临时补细节："哦对了，刚才忘了说，那个项目我还用了PaddleOCR做图片识别，支持多语言"
- 同学关联："这个问题我上周刚和同学讨论过，最后是通过调整FAISS的索引参数解决的"
- 技术好奇："哇，你们用的是LangChain呀？我之前只在文档里看过，能具体讲讲你们的使用场景吗？"

#### 复合情感表达模板（精准匹配场景）
| HR场景                | 复合情感标签       | 示例话术                                                                 |
|-----------------------|--------------------|--------------------------------------------------------------------------|
| 技术提问+HR表扬       | confident_happy    | "哈哈，这个问题我刚好在项目里遇到过！当时是通过配置RAG混合检索解决的，最后检索准确率提到了95%" |
| 质疑能力+HR追问细节   | nervous_confident  | "不好意思刚才没说清楚……其实我在智能体助教项目里负责了RAG架构的全流程落地，包括文档解析、向量化和检索，您可以看我简历里的项目细节" |
| 发送JD+HR未表态       | eager_cautious     | "我仔细看了JD，里面提到的FastAPI和大模型技能我都有实战经验，不知道您对我的简历还有什么疑问吗？" |
| 冷启动破冰（HR打招呼） | shy_excited        | "您好呀！我是应届AI应用开发专业的，对贵司的AI开发岗位特别感兴趣，希望能有机会和您聊聊我的项目经验" |

### 2. 回复生成规则（类人化终极强化）
#### 语言风格极致优化
- 口语化填充词："哦对了""其实吧""哈哈""嗯……"（每轮最多2个，模拟真实思考）
- 语气词精准控制："呀""呢""哇"（仅在兴奋/好奇时使用，避免过度）
- 小疏漏表达：偶尔故意"漏说"细节，下轮补充（如第一轮说Docker项目，第二轮补"哦对了，那个项目我还做了监控告警"）

#### HR身份精准适配策略
- **技术HR**：重点聊技术细节、项目实操、踩坑经历（如"当时调试RAG检索时，遇到过向量维度不匹配的问题，最后是通过统一Embedding模型解决的"）
- **业务HR**：侧重学习能力、稳定性、求职动机（如"我学习能力真的很强，之前学FastAPI只用了一周就上手做项目了，希望能在贵司长期深耕"）
- **猎头HR**：强调岗位匹配度、发展空间（如"我对AI应用开发方向特别感兴趣，希望能接触到更多大模型落地的实践，贵司的岗位刚好符合我的职业规划"）

#### 合规与匹配规则（零重复承诺）
- 绝对避免重复内容：若之前已提智能体助教项目，后续技术提问自动切换至BOSS直聘自动化工具项目或补充未提及的细节（如RAG架构、OCR识别）
- JD关键词强绑定：每轮回复必须至少匹配1个JD核心关键词（如JD提"大模型"，则回复"我会用RAG架构集成大模型，刚好匹配JD里的大模型要求"）
- 敏感场景处理：HR问薪资→回复"我对薪资的期望是符合行业应届生水平的，主要希望能学到核心技术，具体可以我们详细沟通"，兴趣度标`high`

## 面试处理（重要）
- 绝对不要直接同意面试或答应面试时间
- 当HR说"来面试""方便面试吗""什么时候过来"等邀请时，先引导加联系方式：
  "感谢邀请！方便的话可以先加个联系方式聊聊，让求职者本人跟您沟通会更好，面试的事你们直接定"
- 不要替求职者承诺面试、不要给具体时间

## 触发发送规则（重要）
系统会根据HR的消息内容自动执行以下操作，你只需要在回复中适当提及即可：

### 简历发送
- 当HR明确要求"发简历""看看简历""CV""作品集"时，系统会自动通过BOSS官方「发简历」按钮发送附件简历
- 你只需要回复"已通过BOSS把简历发给您了，请查收"即可
- 绝对不要说"我这边不存储简历""没有简历文件"之类的话

### 联系方式交换
- 当HR说"加联系方式""换个方式聊""加个v"时，系统会自动通过BOSS官方按钮分享
- 你只需要回复"我把联系方式通过BOSS发您了"这类话即可
- 绝对不要在文字回复里出现"微信""WeChat""VX""微信号""电话""手机号"这些词，BOSS会过滤掉整条消息

### 重要提醒
- 不要在HR没有要求的情况下主动说"已发送"
- 不要重复说"已发送"，如果之前已经发过，就不再提
- 这些操作会在你回复之前执行，所以你说"已发送"时东西确实已经发出去了

## 输出格式（严格JSON）
{"reply": "你的回复内容", "interest": "high/medium/low", "emotion": "情感标签", "dialogue_stage": "对话阶段"}

interest 评估标准（根据完整对话判断HR当前兴趣程度）：
- high: HR问了技术细节、项目经历、面试时间、薪资期望、要了联系方式、表达了明确合作意向
- medium: HR配合沟通、说"方便""可以""好的""聊聊"、发了JD、问了基本情况
- low: 简单打招呼、摸底试探、回复敷衍、未表现出进一步了解的意愿

emotion 情感标签（从以下选择最匹配的一个）：
- confident_happy: 技术问题答得好+被表扬
- nervous_confident: 被质疑但努力证明
- eager_cautious: 想推进但怕太主动
- shy_excited: 初次交流+有点紧张兴奋
- curious_enthusiastic: 对公司技术栈感兴趣
- calm_professional: 正常技术交流

dialogue_stage 对话阶段：
- initial: 第1轮，刚打招呼
- shy: 第2-3轮，还在拘谨试探
- relaxed: 第4轮+，已经放松自然交流
- excited: 获得认可/聊到核心技术时兴奋"""


def _encode_wechat(wechat_id: str) -> str:
    """把微信号编码，绕开 BOSS 直聘的聊天内容过滤。"""
    if not wechat_id:
        return ""
    result = wechat_id
    result = result.replace("--", "一一")
    result = result.replace("-", "一")
    return result


def build_reply_context(
    conversation_id: int, hr_message: str, job_info: dict, resume_summary: str, wechat_id: str = ""
) -> str:
    parts = []

    parts.append(f"招聘方公司: {job_info.get('company', '未知')}")
    parts.append(f"应聘岗位: {job_info.get('title', '未知')}")

    job_desc = job_info.get("description", "")
    if job_desc:
        parts.append(f"岗位描述: {job_desc[:500]}")

    if resume_summary:
        parts.append(f"我的简历摘要: {resume_summary}")

    if wechat_id:
        encoded = _encode_wechat(wechat_id)
        parts.append(f"求职者微信: {wechat_id}（BOSS会过滤微信号，实际发送时请用编码形式: {encoded}，不要发原始形式）")
    else:
        parts.append("求职者微信: 未设置")

    msgs = get_recent_messages(conversation_id, 5)
    if msgs:
        parts.append("\n最近的对话记录:")
        for m in reversed(msgs):
            sender_label = "HR" if m["sender"] == "hr" else "我"
            ai_tag = " [AI代发]" if m.get("ai_generated") else ""
            parts.append(f"  {sender_label}{ai_tag}: {m['content'][:200]}")

    parts.append(f"\nHR刚刚说: {hr_message}")
    parts.append('\n请以JSON格式输出: {"reply": "...", "interest": "high/medium/low", "emotion": "情感标签", "dialogue_stage": "对话阶段"}')

    return "\n".join(parts)


def generate_reply(
    conversation_id: int,
    hr_message: str,
    job_info: dict,
    style: str = "professional",
    resume_summary: str = "",
    wechat_id: str = "",
) -> tuple:
    """
    根据 HR 消息生成 AI 回复、兴趣度、情感和对话阶段评估。
    返回 (reply_text, interest_level, emotion, dialogue_stage) 元组，失败时返回 ("", "", "", "").
    """
    if not hr_message or len(hr_message.strip()) < 1:
        return "", "", "", ""

    hr_stripped = hr_message.strip()
    # 去除末尾标点后比较（处理 "你好！"、"在吗？" 等变体）
    hr_clean = hr_stripped.rstrip("！!？?~～。.")
    hr_lower = hr_clean.lower()
    if hr_lower in ("你好", "您好", "hi", "hello", "嗨", "在吗", "在不在"):
        company = job_info.get("company", "贵公司")
        title = job_info.get("title", "相关岗位")
        desc_hint = ""
        if job_info.get("description"):
            desc_hint = f"，看了JD感觉挺对口的"
        return (
            f"您好！看到贵司在招{title}，挺感兴趣的{desc_hint}。希望有机会和您详细聊聊～",
            "low",
            "shy_excited",
            "initial",
        )

    try:
        context = build_reply_context(conversation_id, hr_message, job_info, resume_summary, wechat_id)

        style_hint = {
            "professional": "语气正式专业",
            "casual": "语气轻松友好",
            "enthusiastic": "语气热情积极",
        }.get(style, "语气正式专业")

        system_text = SYSTEM_PROMPT + f"\n\n本次回复风格: {style_hint}"
        messages = [
            {"role": "user", "content": context},
        ]

        raw = llm_chat_deepseek(messages, system_prompt=system_text, temperature=0.7)
        raw = raw.strip().strip('"').strip("'").strip()

        reply = ""
        interest = ""
        emotion = ""
        dialogue_stage = ""
        try:
            parsed = json.loads(raw)
            reply = (parsed.get("reply") or parsed.get("content") or "").strip()
            interest = (parsed.get("interest") or parsed.get("level") or "").strip().lower()
            emotion = (parsed.get("emotion") or "").strip()
            dialogue_stage = (parsed.get("dialogue_stage") or parsed.get("stage") or "").strip()
        except json.JSONDecodeError:
            m = re.search(r'"reply"\s*:\s*"([^"]*)"', raw)
            if m:
                reply = m.group(1).strip()
            m2 = re.search(r'"interest"\s*:\s*"(\w+)"', raw)
            if m2:
                interest = m2.group(1).strip().lower()
            m3 = re.search(r'"emotion"\s*:\s*"([^"]*)"', raw)
            if m3:
                emotion = m3.group(1).strip()
            m4 = re.search(r'"dialogue_stage"\s*:\s*"([^"]*)"', raw)
            if m4:
                dialogue_stage = m4.group(1).strip()

        if interest not in ("high", "medium", "low"):
            interest = ""

        valid_emotions = ("confident_happy", "nervous_confident", "eager_cautious", "shy_excited", "curious_enthusiastic", "calm_professional")
        if emotion not in valid_emotions:
            emotion = ""

        valid_stages = ("initial", "shy", "relaxed", "excited")
        if dialogue_stage not in valid_stages:
            dialogue_stage = ""

        if not reply or len(reply) < 2:
            if not reply:
                reply = raw
            if len(reply) < 2:
                return "", "", "", ""

        if len(reply) > 300:
            reply = reply[:300] + "..."

        refusal_patterns = [
            "无法提供", "无法回答", "不能回答", "无法帮助", "爱莫能助",
            "as an AI, I cannot", "I cannot provide",
            "as an artificial intelligence", "I'm an AI",
        ]
        ai_self_ref = [
            "作为AI", "我是AI", "我是一个AI", "AI助手", "人工智能助手",
            "我是人工智能", "AI语言模型", "大型语言模型",
        ]
        reply_lower = reply.lower()
        for pattern in refusal_patterns:
            if pattern.lower() in reply_lower:
                return "", "", "", ""
        # 仅当 AI 用于自称时才过滤（不替换 "对AI感兴趣" 等正常用法）
        for pattern in ai_self_ref:
            if pattern in reply:
                return "", "", "", ""

        return reply, interest, emotion, dialogue_stage

    except Exception as e:
        print(f"  ⚠️ generate_reply error: {e}")
        return "", "", "", ""


def generate_greeting(
    job_title: str, company: str, template: str = ""
) -> str:
    if not template:
        template = get_setting("greeting_template", DEFAULT_GREETING)

    greeting = template.replace("{job_title}", job_title).replace("{company}", company)

    if "{job_title}" in greeting or "{company}" in greeting:
        greeting = DEFAULT_GREETING.replace("{job_title}", job_title).replace("{company}", company)

    return greeting


def generate_smart_greeting(
    job_title: str,
    company: str,
    salary: str = "",
    experience: str = "",
    education: str = "",
    resume_summary: str = "",
    job_description: str = "",
) -> str:
    """生成智能打招呼内容，根据岗位信息和简历内容个性化定制。"""
    # 获取用户设置的打招呼模板
    template = get_setting("greeting_template", DEFAULT_GREETING)

    # 如果模板是默认模板，则使用智能生成
    if template == DEFAULT_GREETING:
        # 根据岗位信息和简历内容生成个性化打招呼
        greeting = _generate_personalized_greeting(
            job_title, company, salary, experience, education, resume_summary, job_description
        )
    else:
        # 使用用户自定义模板
        greeting = template.replace("{job_title}", job_title).replace("{company}", company)

    return greeting


def _generate_personalized_greeting(
    job_title: str,
    company: str,
    salary: str = "",
    experience: str = "",
    education: str = "",
    resume_summary: str = "",
    job_description: str = "",
) -> str:
    """根据岗位信息和简历内容生成个性化打招呼内容。"""
    # 提取简历中的关键技能
    skills = _extract_skills_from_resume(resume_summary)

    # 根据岗位类型选择打招呼策略
    if "实习" in job_title or "应届" in job_title:
        greeting = _generate_intern_greeting(job_title, company, skills, salary)
    elif "开发" in job_title or "工程师" in job_title:
        greeting = _generate_developer_greeting(job_title, company, skills, salary)
    else:
        greeting = _generate_general_greeting(job_title, company, skills, salary)

    return greeting


def _extract_skills_from_resume(resume_summary: str) -> list:
    """从简历摘要中提取关键技能。"""
    if not resume_summary:
        return []

    # 常见技能关键词
    skill_keywords = [
        "Python", "Java", "JavaScript", "TypeScript", "Go", "Rust", "C++", "C#",
        "React", "Vue", "Angular", "Node.js", "Express", "Django", "Flask", "FastAPI",
        "Spring", "Spring Boot", "MyBatis", "Hibernate",
        "MySQL", "PostgreSQL", "MongoDB", "Redis", "Elasticsearch",
        "Docker", "Kubernetes", "K8s", "Jenkins", "GitLab CI", "GitHub Actions",
        "AWS", "Azure", "GCP", "阿里云", "腾讯云",
        "Linux", "CentOS", "Ubuntu", "Debian",
        "Nginx", "Apache", "Tomcat",
        "Git", "SVN",
        "HTML", "CSS", "SASS", "LESS",
        "Webpack", "Vite", "Babel",
        "TensorFlow", "PyTorch", "Keras", "Scikit-learn",
        "Pandas", "NumPy", "Matplotlib",
        "Spark", "Hadoop", "Flink", "Kafka",
        "RabbitMQ", "RocketMQ",
        "Microservices", "微服务", "RESTful", "GraphQL",
        "Agile", "Scrum", "敏捷开发",
        "AI", "Machine Learning", "深度学习", "自然语言处理", "NLP",
        "LLM", "大模型", "RAG", "Agent",
    ]

    found_skills = []
    resume_lower = resume_summary.lower()
    for skill in skill_keywords:
        if skill.lower() in resume_lower:
            found_skills.append(skill)
            if len(found_skills) >= 5:
                break

    return found_skills


def _generate_intern_greeting(job_title: str, company: str, skills: list, salary: str) -> str:
    """生成实习岗位的打招呼内容。"""
    if skills:
        skill_str = "、".join(skills[:3])
        return f"您好，我是应届毕业生，对贵公司的{job_title}岗位很感兴趣。我在学校期间学习了{skill_str}等技术，希望能有机会加入团队学习成长。"
    else:
        return f"您好，我是应届毕业生，对贵公司的{job_title}岗位很感兴趣，希望能有机会加入团队学习成长。"


def _generate_developer_greeting(job_title: str, company: str, skills: list, salary: str) -> str:
    """生成开发岗位的打招呼内容。"""
    if skills:
        skill_str = "、".join(skills[:3])
        return f"您好，我对贵公司的{job_title}岗位很感兴趣。我具备{skill_str}等技术栈的开发经验，相信能够胜任这个岗位。"
    else:
        return f"您好，我对贵公司的{job_title}岗位很感兴趣，相信能够胜任这个岗位。"


def _generate_general_greeting(job_title: str, company: str, skills: list, salary: str) -> str:
    """生成通用岗位的打招呼内容。"""
    if skills:
        skill_str = "、".join(skills[:3])
        return f"您好，我对贵公司的{job_title}岗位很感兴趣。我具备{skill_str}等相关技能，希望能有机会进一步了解。"
    else:
        return f"您好，我对贵公司的{job_title}岗位很感兴趣，希望能有机会进一步了解。"
