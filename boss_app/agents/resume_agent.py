"""简历 Agent — 全功能简历优化、匹配分析、面试准备、求职信生成。

支持功能（13项）：
- parse: 解析简历文件（PDF/TXT）
- optimize: 证据约束简历优化（truth-boundary + evidence-contract）
- analyze_match: 简历-JD 匹配度分析（含角色类型检测）
- cover_letter: 生成求职信（避免套话）
- interview_prep: 生成面试题和参考答案（STAR 框架）
- skill_gap: 技能差距分析（免费资源优先）
- compare_jds: 对比多个 JD 找最优匹配
- improve_section: 针对性优化简历某一模块
- jd_analysis: JD 深度分析 + 角色类型检测（11种）
- materials_audit: 简历证据审计（strong/medium/weak/missing）
- interview_grilling: 5轮压力面试模拟
- answer_cards: 面试回答卡片（dangerous/passable/strong）
- upgrade_plan: 证据升级计划（时间分桶任务）

优化特性：
- OrderedDict LRU+TTL 结果缓存（O(1) 操作）
- SQLite 持久化优化历史
- 输入验证与预处理
- 操作统计（调用次数/耗时/成功率）
- LLMInternSkill 证据约束方法论
- 统一 _run_llm_action 消除 handler 重复代码
"""

import asyncio
import base64
import hashlib
import json
import logging
import re
import sys
import time
from collections import OrderedDict
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

from .base import BaseAgent, AgentMessage
from ..core.database import get_db

_interview_dir = str(Path(__file__).resolve().parent.parent.parent / "interview")
if _interview_dir not in sys.path:
    sys.path.insert(0, _interview_dir)


# ── 缓存配置 ──
_CACHE_MAX = 50
_CACHE_TTL = 300  # 5 分钟

# ── 输入限制 ──
_RESUME_MIN_LEN = 50
_JD_MIN_LEN = 20
_RESUME_MAX_LEN = 8000
_JD_MAX_LEN = 4000


# ── LLMInternSkill 证据约束方法论（公共模块） ──

TRUTH_BOUNDARY_RULES = """
## 真实性边界规则（Truth Boundary）

你必须严格区分以下层级，绝对不能帮用户编造经历：

### 声明等级（Claim Level）
- **C0 确认级**：用户亲自完成、有代码/PR/文档可证 → 可以直接写入简历
- **C1 参与级**：用户参与了部分工作 → 必须降级表述（"参与"而非"主导"）
- **C2 了解级**：用户只是学习/了解 → 只能写在"技术栈"或"学习"栏，不能写进项目经历
- **C3 听说过**：仅听说过概念 → 不能出现在简历中

### 危险词汇降级表
简历中出现以下词汇时，必须检查是否有 C0 级证据支撑，否则强制降级：

| 原始表述 | 需要的证据 | 无证据时降级为 |
|---------|-----------|-------------|
| 精通 | 大型项目核心开发 + 性能数据 | 熟练使用 |
| 深入理解 | 有源码级贡献或技术文章 | 了解原理 |
| 主导/负责 | 明确的 owner 角色 + 交付物 | 参与/协助 |
| 独立完成 | 完整的 git 记录 | 完成（去掉"独立"） |
| 优化了XX% | A/B 测试数据或监控截图 | 改进了XX方面 |
| 架构设计 | 系统设计文档 + 落地效果 | 参与架构讨论 |
| 核心贡献 | PR 被合入的记录 | 贡献了XX模块 |
"""

EVIDENCE_CONTRACT = """
## 证据契约（Evidence Contract）

每一条简历 bullet 必须满足：
**Action（做了什么）+ Technical Object（技术对象）+ Constraint/Bad Case（约束或边界情况）+ Evidence/Result（证据或结果）**

### 示例
- 差：「负责后端开发」→ 模糊、无技术对象、无结果
- 中：「使用 Python 开发了用户系统」→ 有技术对象但缺约束和结果
- 好：「用 FastAPI + Redis 实现用户认证模块，处理 10w+ 日活用户的 token 刷新，P99 延迟 < 50ms」→ 完整四要素

### 量化公式
尽量用「数字 + 比较基准 + 时间维度」：
- [FAIL] 提升了系统性能
- [OK] 将 API 响应时间从 800ms 优化到 200ms（降幅 75%），支撑日均 50w 请求
"""

ROLE_TYPE_DETECTION = """
## 角色类型检测（Role Type Detection）

根据 JD 内容自动判断岗位类型，针对性优化简历侧重：

| 角色类型 | 关键词特征 | 简历侧重 |
|---------|-----------|---------|
| rag | RAG、向量数据库、检索增强、embedding | 检索pipeline设计、向量索引优化、召回率指标 |
| agent | Agent、工具调用、规划、ReAct、function call | 多步推理、工具链设计、任务分解能力 |
| agentic-rl | RLHF、PPO、reward model、强化学习 | RL 算法理解、奖励建模、对齐实验 |
| posttraining | SFT、微调、LoRA、指令微调 | 数据清洗、训练流程、效果评估 |
| pretraining | 预训练、大规模训练、分布式训练 | 分布式框架、训练稳定性、数据工程 |
| llm-app | LLM应用、对话系统、prompt工程 | prompt 设计、应用架构、效果优化 |
| llm-algorithm | 模型算法、attention、transformer | 模型结构理解、训练优化、算法创新 |
| search-ranking | 搜索、推荐、排序、CTR | 召回/排序模型、特征工程、AB实验 |
| aigc | AIGC、生成、图像生成、文生图 | 生成模型、质量评估、创意应用 |
| multimodal | 多模态、视觉语言、CLIP | 跨模态对齐、多模态理解、模型融合 |
| backend-ai | AI基础设施、推理服务、模型部署 | 推理优化、服务架构、性能调优 |
"""

# ── Prompt 模板 ──

OPTIMIZE_PROMPT = f"""你是 ResumeAI Pro，专业简历优化专家，严格遵循「证据约束方法论」。

{TRUTH_BOUNDARY_RULES}

{EVIDENCE_CONTRACT}

## 优化流程

### 第一步：证据审计
逐条检查简历内容，标记每条的声明等级（C0/C1/C2/C3）。
C2 及以下的内容必须降级或移除。

### 第二步：8 项核心优化
1. 关键词匹配 — 提取 JD 核心关键词，确保简历覆盖
2. STAR 原则重构 — 模糊描述 → 情境-任务-行动-结果
3. 量化数据强化 — 用「数字+比较基准+时间维度」公式
4. 动词升级 — 但必须与证据等级匹配（C1 不能用"主导"）
5. 胜任力呈现 — 突出与岗位匹配的核心能力
6. 结构逻辑优化 — 重要信息前置
7. ATS 友好格式 — 兼容招聘系统解析
8. 真实性校验 — 每条优化后的内容必须可被证据支撑

### 第三步：危险词汇扫描
检查优化后的简历是否包含未被证据支撑的危险词汇。

输出严格 JSON：
{{
  "claim_levels": {{"C0": [], "C1": [], "C2": [], "C3": []}},
  "dangerous_words_found": [{{"word": "", "context": "", "action": "降级/移除/保留"}}],
  "match_score": 85,
  "keyword_analysis": {{"matched": [], "missing": [], "suggestions": []}},
  "optimized_resume": "优化后的完整简历...",
  "changes": [{{"section": "", "before": "", "after": "", "reason": ""}}],
  "evidence_check": [{{"bullet": "", "claim_level": "C0", "evidence_type": "代码/PR/数据"}}],
  "summary": "整体评估..."
}}"""

ANALYZE_PROMPT = f"""你是简历分析专家，严格遵循「证据约束方法论」。

{TRUTH_BOUNDARY_RULES}

{ROLE_TYPE_DETECTION}

## 分析维度

1. **角色类型检测** — 根据 JD 判断岗位属于哪种角色类型
2. **关键词覆盖率** — JD 核心技能在简历中的出现情况
3. **证据等级分布** — 简历中 C0/C1/C2/C3 各占多少
4. **经验匹配度** — 工作经历与岗位要求的关联程度
5. **技能深度** — 技术栈匹配的深度和广度
6. **危险词汇** — 是否存在无证据支撑的夸大表述
7. **ATS 兼容性** — 格式是否能被招聘系统正确解析

## 适配判定
- **strong_fit**: 核心技能覆盖率 > 80%，有 C0 级相关项目经验
- **weak_fit**: 核心技能覆盖率 50-80%，有部分相关经验
- **risky_fit**: 核心技能覆盖率 < 50%，但有可迁移技能
- **not_recommended**: 关键技能大面积缺失，不建议投递

严格输出 JSON：
{{
  "role_type": "agent",
  "role_type_confidence": 0.9,
  "fit_verdict": "strong_fit",
  "match_score": 0-100,
  "keyword_coverage": 0-100,
  "evidence_distribution": {{"C0": 5, "C1": 3, "C2": 1, "C3": 0}},
  "strengths": [],
  "weaknesses": [],
  "dangerous_words": [{{"word": "", "context": "", "suggestion": ""}}],
  "ats_compatibility": "good/fair/poor",
  "suggestions": []
}}"""

INTERVIEW_PROMPT = f"""你是资深技术面试官。根据求职者简历和目标岗位，生成面试题和参考答案。

{EVIDENCE_CONTRACT}

## 出题要求

### 技术题（5道，由浅入深）
- 基础概念 → 原理理解 → 实战应用 → 深度优化 → 系统设计
- 每题考察简历中提到的具体技术点

### 项目题（3道，考察实战深度）
- 使用「证据追问法」：你说做了XX → 具体怎么做的 → 遇到什么问题 → 如何解决 → 为什么选这个方案
- 关注边界情况和 bad case 处理

### 行为题（2道，STAR 框架）
- 提供 STAR 框架的优秀回答示例
- 区分"背诵型"和"真实型"回答的特征

### 每题附带
- 期望回答要点（key_points）
- 追问方向（follow_up）
- 红旗信号（red_flags）— 回答中暴露问题的信号
- 评分标准（scoring_rubric）

输出 JSON：
{{
  "technical_questions": [
    {{"question": "...", "difficulty": "easy/medium/hard", "key_points": [], "follow_up": "...", "scoring_rubric": "..."}}
  ],
  "project_questions": [
    {{"question": "...", "what_to_listen_for": "...", "red_flags": [], "follow_up_sequence": ["追问1", "追问2"]}}
  ],
  "behavioral_questions": [
    {{"question": "...", "star_framework": "用STAR法则回答", "good_answer_example": "...", "bad_answer_signals": []}}
  ],
  "preparation_tips": []
}}"""

COVER_LETTER_PROMPT = """你是专业求职顾问。根据简历和岗位 JD 生成一封求职信。

## 真实性约束
- 所有引用的经历必须来自简历，不能编造
- 量化数据必须与简历一致
- 技能描述的熟练度必须与简历匹配

## 要求
- 开头：表明对岗位的兴趣，用具体细节说明为什么关注这家公司/产品
- 中段：匹配 JD 关键要求，用「Action + 技术对象 + 约束 + 结果」格式证明能力
- 结尾：表达加入意愿，呼应公司具体产品或技术方向
- 语气：专业真诚，展现个人特色，避免套话
- 长度：300-500 字
- 禁止使用"贵公司"等生硬称谓，改用公司实际名称

## 禁止套话清单
以下表述禁止出现，必须替换为具体内容：
- "我一直关注贵公司的发展" → 说明具体关注了什么
- "我相信我的能力能够胜任" → 用具体经历证明
- "我对这个岗位充满热情" → 说明为什么感兴趣
- "希望有机会加入贵公司" → 说明能为团队带来什么

输出 JSON：
{"cover_letter": "求职信正文...", "highlights": ["重点突出的3个匹配点"], "avoided_cliches": ["避免了哪些套话"]}"""

SKILL_GAP_PROMPT = """你是职业规划师。分析简历技能与岗位要求的差距，给出学习建议。

分析要求：
- 精确匹配已有技能和缺失技能
- 对每个已有技能评估真实水平（有项目证据 vs 仅学过）
- 优先推荐免费学习资源（官方文档、开源项目、免费课程）
- 学习时间估算要现实可行
- 标注可迁移技能（已有技能如何迁移到新领域）

输出 JSON：
{
  "match_rate": 75,
  "matched_skills": [{"skill": "Python", "level": "熟练", "evidence": "3个项目使用", "confidence": "C0"}],
  "missing_skills": [{"skill": "K8s", "importance": "必要/加分", "learn_time": "2-4周", "resources": ["官方文档", "freeCodeCamp"], "practice_project": "建议练手项目"}],
  "transferable_skills": [{"from": "...", "to": "...", "how": "..."}],
  "learning_roadmap": [{"priority": 1, "skill": "...", "action": "...", "deadline": "...", "milestone": "验证标准"}]
}"""

COMPARE_JDS_PROMPT = f"""你是求职匹配专家。根据求职者简历，对比多个 JD 的匹配度，给出排名和建议。

{ROLE_TYPE_DETECTION}

评估维度：
- 技能匹配度（权重 35%）
- 经验匹配度（权重 25%）
- 角色类型匹配（权重 20%）— 简历强项与岗位类型的契合度
- 发展潜力（权重 10%）
- 薪资竞争力（权重 10%）

严格输出 JSON：
{{"rankings": [{{"index": 1, "title": "", "company": "", "role_type": "", "match_score": 85, "reason": "", "risk": ""}}], "best_match": {{"index": 1, "why": "..."}}, "advice": "..."}}"""

IMPROVE_SECTION_PROMPT = f"""你是简历优化专家。针对简历中的特定模块进行深度优化。

{EVIDENCE_CONTRACT}

优化方法：
1. 检查每条 bullet 的证据等级（C0/C1/C2/C3）
2. 用「Action + 技术对象 + 约束/bad case + 结果」公式重构
3. 补充量化数据（但必须有证据支撑，不能编造）
4. 升级动词（但必须与证据等级匹配）
5. 突出成果导向
6. 与目标 JD 的关键词对齐

严格输出 JSON：
{{
  "original": "原文",
  "improved": "优化后",
  "changes": [
    {{"before": "", "after": "", "claim_level": "C0", "reason": ""}}
  ],
  "evidence_gaps": ["需要补充证据的地方"]
}}"""

JD_ANALYSIS_PROMPT = f"""你是 JD 分析专家。深度解析岗位描述，识别角色类型和关键要求。

{ROLE_TYPE_DETECTION}

## 分析维度

1. **角色类型判定** — 根据关键词判断属于 11 种角色类型中的哪一种
2. **硬性要求提取** — 必须满足的条件（学历、年限、技术栈）
3. **软性要求提取** — 加分项（项目经验、论文、开源贡献）
4. **隐含需求推断** — JD 没有明说但暗示的要求
5. **团队阶段判断** — 根据 JD 用词推断团队处于什么阶段（0→1/快速迭代/稳定维护）
6. **薪资分析** — 薪资范围的竞争力和隐含信息

严格输出 JSON：
{{
  "role_type": "agent",
  "role_type_confidence": 0.9,
  "role_type_evidence": ["JD中哪些关键词指向该类型"],
  "hard_requirements": [{{"item": "", "importance": "必须/强烈偏好"}}],
  "soft_requirements": [{{"item": "", "importance": "加分"}}],
  "hidden_signals": ["隐含需求1", "隐含需求2"],
  "team_stage": "0→1/快速迭代/稳定维护",
  "team_stage_evidence": ["判断依据"],
  "salary_analysis": {{"range": "", "competitiveness": "高/中/低", "notes": ""}},
  "resume_focus": ["针对此JD简历应重点突出的3个方面"],
  "interview_focus": ["面试可能重点考察的3个方面"]
}}"""

MATERIALS_AUDIT_PROMPT = f"""你是简历审计专家。对简历中的每一条经历进行证据等级审计。

{TRUTH_BOUNDARY_RULES}

## 审计标准

对简历中每一条 bullet point / 项目经历 / 技能描述，评估其证据等级：

### 证据等级定义
- **strong（强证据）**：有可验证的产出（代码仓库、PR、论文、数据指标、上线产品）
- **medium（中等证据）**：有间接证据（同事证言、内部文档、参与记录）
- **weak（弱证据）**：仅有自我描述，无法外部验证
- **missing（无证据）**：疑似编造或过度包装

### 审计维度
1. 每条经历的证据等级
2. 危险词汇检测（精通/深入理解/主导/独立完成 等）
3. 量化数据的可信度
4. 技能描述与项目经历的一致性

输出严格 JSON：
{{
  "overall_trust_score": 0-100,
  "audit_results": [
    {{
      "item": "简历中的具体条目",
      "evidence_level": "strong/medium/weak/missing",
      "dangerous_words": ["精通"],
      "claim_level": "C0/C1/C2/C3",
      "suggestion": "具体修改建议",
      "downgrade_to": "如果需要降级，降级后的表述"
    }}
  ],
  "summary": {{
    "strong_count": 0,
    "medium_count": 0,
    "weak_count": 0,
    "missing_count": 0,
    "dangerous_words_total": 0,
    "top_risks": ["最大的3个风险点"]
  }},
  "improvement_priority": [
    {{"item": "", "current_level": "weak", "target_level": "medium", "action": "如何提升证据等级"}}
  ]
}}"""

INTERVIEW_GRILLING_PROMPT = """你是严格的资深技术面试官。对求职者进行 5 轮递进式压力面试。

## 面试方法论

### 5 轮递进结构
1. **第一轮：真实性边界探测** — 从简历细节入手，验证经历真实性
   - 问具体数字的来源："你说提升了 50%，这个数据是怎么测的？"
   - 问时间线："这个项目是哪年做的？当时团队几个人？"
   - 问选择原因："为什么选 Redis 而不是 Memcached？"

2. **第二轮：技术深度追问** — 沿着简历中的技术点深挖
   - 原理层："Transformer 的 attention 计算复杂度是多少？为什么？"
   - 实践层："你遇到过 OOM 吗？怎么排查的？"
   - 优化层："如果让你重新设计，你会改什么？"

3. **第三轮：JD 相关深度提问** — 针对目标岗位的技术栈深入提问
   - 岗位核心技能的深度问题
   - 实际场景设计题："给你一个XX需求，你怎么设计？"

4. **第四轮：场景题 & 压力测试** — 模拟真实工作场景
   - 故意提出模糊需求，观察候选人如何澄清
   - 提出不可能的时间线，观察候选人如何应对
   - 连续追问"为什么"，测试思维深度

5. **第五轮：风险总结** — 总结候选人的风险点和优势

输出严格 JSON：
{{
  "rounds": [
    {{
      "round": 1,
      "theme": "真实性边界探测",
      "questions": [
        {{
          "question": "具体问题",
          "target": "验证什么",
          "good_answer_signal": "好的回答特征",
          "bad_answer_signal": "差的回答特征",
          "follow_up": "如果回答不好，追问什么"
        }}
      ]
    }}
  ],
  "risk_summary": {{
    "strengths": [],
    "risks": [],
    "red_flags": [],
    "overall_assessment": "综合评价",
    "hire_recommendation": "strong_yes/yes/lean_no/no"
  }}
}}"""

ANSWER_CARDS_PROMPT = """你是面试教练。针对每个面试问题，提供三种水平的回答卡片。

## 回答卡片分类

### dangerous（危险回答）
- 包含无法验证的夸大声明
- 使用了危险词汇（精通/深入理解）但无证据
- 回答过于笼统，没有具体细节
- 暴露了知识盲区

### passable（及格回答）
- 基本回答了问题，但缺乏深度
- 有具体例子但不够生动
- 技术描述正确但没有个人见解

### strong（优秀回答）
- 有具体数据和案例支撑
- 展示了深度思考和个人见解
- 主动提及了边界情况和取舍
- 体现了学习能力和成长思维

## 要求
针对每个面试题，生成三种水平的示例回答，帮助候选人理解回答的差距。

输出严格 JSON：
{{
  "cards": [
    {{
      "question": "面试题",
      "dangerous": {{
        "answer": "危险回答示例",
        "problems": ["问题1", "问题2"],
        "what_interviewer_thinks": "面试官会想什么"
      }},
      "passable": {{
        "answer": "及格回答示例",
        "strengths": ["优点"],
        "improvements": ["可以改进的地方"]
      }},
      "strong": {{
        "answer": "优秀回答示例",
        "why_effective": ["为什么有效"],
        "techniques_used": ["使用了什么技巧"]
      }}
    }}
  ]
}}"""

UPGRADE_PLAN_PROMPT = """你是职业规划师。根据简历审计结果，制定证据升级计划。

## 时间分桶规划

将升级任务按时间分桶，每个任务有明确的产出物和验证标准：

### 1 周内可完成（快速胜出）
- 完善已有项目文档
- 补充性能数据
- 整理代码仓库 README

### 1 个月内可完成（短期提升）
- 为已有项目写技术博客
- 贡献开源项目（哪怕是小 PR）
- 完成一个小型 side project

### 3 个月内可完成（中期积累）
- 完成一个有深度的技术项目
- 发表技术文章
- 获得可量化的成果

### 6 个月内可完成（长期建设）
- 成为某个领域的 go-to 人选
- 建立技术影响力

## 要求
- 每个任务必须有明确的「产出物」和「证据类型」
- 优先推荐能快速提升证据等级的任务
- 考虑候选人的现有基础，不要推荐过于超出能力范围的任务

输出严格 JSON：
{{
  "current_trust_score": 0-100,
  "target_trust_score": 0-100,
  "upgrade_plan": {{
    "1_week": [
      {{
        "task": "具体任务",
        "output": "产出物",
        "evidence_type": "strong/medium",
        "target_claim_level": "C0",
        "effort": "低/中/高"
      }}
    ],
    "1_month": [],
    "3_months": [],
    "6_months": []
  }},
  "priority_order": ["按重要性排序的任务列表"],
  "quick_wins": ["最快能提升信任分的3个动作"]
}}"""


class ResumeAgent(BaseAgent):
    name = "resume"

    def __init__(self, orchestrator):
        super().__init__(orchestrator)
        self._cache: OrderedDict = OrderedDict()  # O(1) LRU
        self._action_stats: dict = {}

    def get_status(self) -> dict:
        status = super().get_status()
        status["stats"]["action_stats"] = self._action_stats
        status["stats"]["cache_size"] = len(self._cache)
        return status

    # ── 消息分发 ──

    async def handle(self, msg: AgentMessage) -> None:
        dispatch = {
            "parse": self._handle_parse,
            "optimize": self._handle_optimize,
            "analyze_match": self._handle_analyze_match,
            "cover_letter": self._handle_cover_letter,
            "interview_prep": self._handle_interview_prep,
            "skill_gap": self._handle_skill_gap,
            "compare_jds": self._handle_compare_jds,
            "improve_section": self._handle_improve_section,
            "jd_analysis": self._handle_jd_analysis,
            "materials_audit": self._handle_materials_audit,
            "interview_grilling": self._handle_interview_grilling,
            "answer_cards": self._handle_answer_cards,
            "upgrade_plan": self._handle_upgrade_plan,
        }
        action = msg.payload.get("action")
        handler = dispatch.get(action)
        if handler:
            await handler(msg)
        else:
            await self.send(msg.source, "result", {
                "error": f"未知操作: {action}",
                "available": list(dispatch.keys()),
                "correlation_id": msg.correlation_id,
            })

    # ── 缓存（OrderedDict，O(1)） ──

    def _cache_key(self, action: str, *parts: str) -> str:
        # 用长度前缀避免分隔符碰撞: "action:5:hello3:bye"
        segments = [action]
        for p in parts:
            segments.append(f"{len(p)}:{p}")
        return hashlib.md5("\x00".join(segments).encode()).hexdigest()

    def _cache_get(self, key: str) -> Optional[dict]:
        entry = self._cache.get(key)
        if not entry:
            return None
        if time.time() - entry["ts"] > _CACHE_TTL:
            self._cache.pop(key, None)
            return None
        self._cache.move_to_end(key)
        return entry["data"].copy()  # 返回副本，防止调用方修改缓存

    def _cache_set(self, key: str, data: dict) -> None:
        if key in self._cache:
            self._cache.move_to_end(key)
        self._cache[key] = {"data": data, "ts": time.time()}
        while len(self._cache) > _CACHE_MAX:
            self._cache.popitem(last=False)

    # ── 统计 ──

    def _record_stat(self, action: str, duration_ms: float, is_error: bool = False) -> None:
        if action not in self._action_stats:
            self._action_stats[action] = {
                "call_count": 0, "error_count": 0,
                "total_duration_ms": 0, "avg_duration_ms": 0,
                "last_called_at": None,
            }
        s = self._action_stats[action]
        s["call_count"] += 1
        if is_error:
            s["error_count"] += 1
        s["total_duration_ms"] += duration_ms
        s["avg_duration_ms"] = s["total_duration_ms"] / s["call_count"]
        s["last_called_at"] = time.time()

    # ── 持久化 ──

    def _save_history(self, action: str, resume_hash: str, jd_hash: str,
                      input_summary: str, result: dict, duration_ms: float) -> None:
        try:
            clean = {k: v for k, v in result.items() if not k.startswith("_")}
            result_json = json.dumps(clean, ensure_ascii=False)
            if len(result_json) > 50000:
                logger.warning("resume_history result_json truncated from %d to 50000 chars", len(result_json))
                result_json = result_json[:50000]
            db = get_db()
            db.execute(
                "INSERT INTO resume_history (action, resume_hash, jd_hash, input_summary, result_json, duration_ms) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (action, resume_hash, jd_hash, input_summary, result_json, int(duration_ms)),
            )
            db.commit()
        except Exception:
            logger.exception("Failed to save resume history (action=%s)", action)

    # ── 输入验证 ──

    def _validate_texts(self, resume_text: str, jd_text: str,
                        need_resume: bool = True, need_jd: bool = True) -> Tuple[bool, str]:
        if need_resume:
            if not resume_text or not resume_text.strip():
                return False, "请提供简历文本"
            if len(resume_text.strip()) < _RESUME_MIN_LEN:
                return False, f"简历文本过短（至少 {_RESUME_MIN_LEN} 字，当前 {len(resume_text.strip())} 字）"
        if need_jd:
            if not jd_text or not jd_text.strip():
                return False, "请提供岗位描述（JD）"
            if len(jd_text.strip()) < _JD_MIN_LEN:
                return False, f"岗位描述过短（至少 {_JD_MIN_LEN} 字，当前 {len(jd_text.strip())} 字）"
        return True, ""

    def _sanitize_texts(self, resume_text: str, jd_text: str) -> Tuple[str, str]:
        resume_text = (resume_text or "").strip()
        jd_text = (jd_text or "").strip()
        if len(resume_text) > _RESUME_MAX_LEN:
            resume_text = resume_text[:_RESUME_MAX_LEN]
        if len(jd_text) > _JD_MAX_LEN:
            jd_text = jd_text[:_JD_MAX_LEN]
        return resume_text, jd_text

    # ── 核心执行引擎 ──

    async def _run_llm_action(self, msg: AgentMessage, action: str,
                              system_prompt: str, user_msg: str,
                              resume_text: str = "", jd_text: str = "",
                              temperature: float = 0.4) -> None:
        """统一的 LLM action 执行流程：缓存检查 → LLM 调用 → 缓存写入 → 历史保存 → 响应。"""
        resume_text = (resume_text or "").strip()
        jd_text = (jd_text or "").strip()
        ck = self._cache_key(action, resume_text, jd_text)
        cached = self._cache_get(ck)
        if cached:
            cached["from_cache"] = True
            return await self._ok(msg, cached)

        t0 = time.time()
        loop = asyncio.get_running_loop()
        try:
            result = await asyncio.wait_for(
                loop.run_in_executor(None, self._llm_call, system_prompt, user_msg, temperature),
                timeout=300,
            )
            duration_ms = (time.time() - t0) * 1000
            self._record_stat(action, duration_ms)
            result["from_cache"] = False
            self._cache_set(ck, result)
            self._save_history(
                action,
                hashlib.md5(resume_text.encode()).hexdigest()[:12] if resume_text else "",
                hashlib.md5(jd_text.encode()).hexdigest()[:12] if jd_text else "",
                self._build_summary(action, resume_text, jd_text),
                result, duration_ms,
            )
            await self._ok(msg, result)
        except asyncio.TimeoutError:
            self._record_stat(action, (time.time() - t0) * 1000, True)
            await self._err(msg, f"{action} 超时（5分钟），请稍后重试")
        except Exception as e:
            self._record_stat(action, (time.time() - t0) * 1000, True)
            await self._err(msg, f"{action} 失败: {e}")

    def _build_summary(self, action: str, resume_text: str, jd_text: str) -> str:
        parts = []
        if resume_text:
            parts.append(f"{len(resume_text)}字简历")
        if jd_text:
            parts.append(f"{len(jd_text)}字JD")
        return " vs ".join(parts) if parts else action

    # ── 解析简历 ──

    async def _handle_parse(self, msg: AgentMessage) -> None:
        from ..services.resume_parser import parse_resume_file
        content = msg.payload.get("content")
        filename = msg.payload.get("filename", "resume.pdf")
        if not content:
            return await self._err(msg, "无文件内容")
        try:
            file_bytes = base64.b64decode(content)
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(None, parse_resume_file, file_bytes, filename)
            await self._ok(msg, {"parsed": result})
        except Exception as e:
            await self._err(msg, f"简历解析失败: {e}")

    # ── 简历优化 ──

    async def _handle_optimize(self, msg: AgentMessage) -> None:
        resume_text, jd_text = self._extract_texts(msg)
        ok, err = self._validate_texts(resume_text, jd_text)
        if not ok:
            return await self._err(msg, err)
        resume_text, jd_text = self._sanitize_texts(resume_text, jd_text)
        await self._run_llm_action(msg, "optimize", OPTIMIZE_PROMPT,
                                   f"【简历】\n{resume_text}\n\n【JD】\n{jd_text}",
                                   resume_text, jd_text, 0.4)

    # ── 匹配分析 ──

    async def _handle_analyze_match(self, msg: AgentMessage) -> None:
        resume_text, jd_text = self._extract_texts(msg)
        ok, err = self._validate_texts(resume_text, jd_text)
        if not ok:
            return await self._err(msg, err)
        resume_text, jd_text = self._sanitize_texts(resume_text, jd_text)
        await self._run_llm_action(msg, "analyze_match", ANALYZE_PROMPT,
                                   f"【简历】\n{resume_text}\n\n【JD】\n{jd_text}",
                                   resume_text, jd_text, 0.3)

    # ── 求职信 ──

    async def _handle_cover_letter(self, msg: AgentMessage) -> None:
        resume_text, jd_text = self._extract_texts(msg)
        company = re.sub(r'[^\w\s一-鿿\-]', '', msg.payload.get("company", ""))[:50]
        ok, err = self._validate_texts(resume_text, jd_text)
        if not ok:
            return await self._err(msg, err)
        resume_text, jd_text = self._sanitize_texts(resume_text, jd_text)
        user_msg = f"目标公司：{company}\n\n【简历】\n{resume_text}\n\n【JD】\n{jd_text}"
        await self._run_llm_action(msg, "cover_letter", COVER_LETTER_PROMPT,
                                   user_msg, resume_text, jd_text, 0.5)

    # ── 面试准备 ──

    async def _handle_interview_prep(self, msg: AgentMessage) -> None:
        resume_text, jd_text = self._extract_texts(msg)
        ok, err = self._validate_texts(resume_text, jd_text)
        if not ok:
            return await self._err(msg, err)
        resume_text, jd_text = self._sanitize_texts(resume_text, jd_text)
        await self._run_llm_action(msg, "interview_prep", INTERVIEW_PROMPT,
                                   f"【简历】\n{resume_text}\n\n【JD】\n{jd_text}",
                                   resume_text, jd_text, 0.5)

    # ── 技能差距 ──

    async def _handle_skill_gap(self, msg: AgentMessage) -> None:
        resume_text, jd_text = self._extract_texts(msg)
        ok, err = self._validate_texts(resume_text, jd_text)
        if not ok:
            return await self._err(msg, err)
        resume_text, jd_text = self._sanitize_texts(resume_text, jd_text)
        await self._run_llm_action(msg, "skill_gap", SKILL_GAP_PROMPT,
                                   f"【简历】\n{resume_text}\n\n【JD】\n{jd_text}",
                                   resume_text, jd_text, 0.3)

    # ── 对比多个 JD ──

    async def _handle_compare_jds(self, msg: AgentMessage) -> None:
        resume_text = msg.payload.get("resume_text", "")
        jds = msg.payload.get("jds", [])
        if not resume_text or not resume_text.strip():
            return await self._err(msg, "请提供简历文本")
        if len(jds) < 2:
            return await self._err(msg, "需要至少 2 个 JD 进行对比")

        resume_text = resume_text.strip()[:_RESUME_MAX_LEN]
        jd_list = "\n---\n".join(
            f"【JD {i+1}】{jd.get('title', '未知')} - {jd.get('company', '未知')}\n{jd.get('text', '')[:800]}"
            for i, jd in enumerate(jds[:5])
        )
        jd_key = "|".join(jd.get("text", "")[:200] for jd in jds[:5])
        await self._run_llm_action(msg, "compare_jds", COMPARE_JDS_PROMPT,
                                   f"【简历】\n{resume_text}\n\n{jd_list}",
                                   resume_text, jd_key, 0.3)

    # ── 针对性优化某模块 ──

    _ALLOWED_SECTIONS = {"工作经历", "项目经验", "教育背景", "技能", "自我评价", "实习经历",
                         "获奖荣誉", "证书", "论文", "开源贡献", "个人简介", "求职意向"}

    async def _handle_improve_section(self, msg: AgentMessage) -> None:
        resume_text = msg.payload.get("resume_text", "")
        section = msg.payload.get("section", "").strip()
        jd_text = msg.payload.get("jd_text", "")

        ok, err = self._validate_texts(resume_text, "", need_resume=True, need_jd=False)
        if not ok:
            return await self._err(msg, err)
        if not section:
            return await self._err(msg, "请指定要优化的简历模块名称（如：工作经历、项目经验、教育背景）")
        if section not in self._ALLOWED_SECTIONS:
            return await self._err(msg, f"不支持的模块「{section}」，可选: {', '.join(sorted(self._ALLOWED_SECTIONS))}")

        resume_text = resume_text.strip()[:_RESUME_MAX_LEN]
        jd_text = jd_text.strip()[:_JD_MAX_LEN] if jd_text else ""

        user_msg = f"目标模块：「{section}」\n\n【简历】\n{resume_text}"
        if jd_text:
            user_msg += f"\n\n【JD 参考】\n{jd_text}"

        await self._run_llm_action(msg, "improve_section", IMPROVE_SECTION_PROMPT,
                                   user_msg, resume_text, jd_text, 0.4)

    # ── JD 深度分析 ──

    async def _handle_jd_analysis(self, msg: AgentMessage) -> None:
        jd_text = msg.payload.get("jd_text", "")
        if not jd_text or not jd_text.strip():
            return await self._err(msg, "请提供岗位描述（JD）")
        jd_text = jd_text.strip()[:_JD_MAX_LEN]
        await self._run_llm_action(msg, "jd_analysis", JD_ANALYSIS_PROMPT,
                                   f"【JD】\n{jd_text}", "", jd_text, 0.3)

    # ── 简历证据审计 ──

    async def _handle_materials_audit(self, msg: AgentMessage) -> None:
        resume_text = msg.payload.get("resume_text", "")
        ok, err = self._validate_texts(resume_text, "", need_resume=True, need_jd=False)
        if not ok:
            return await self._err(msg, err)
        resume_text = resume_text.strip()[:_RESUME_MAX_LEN]
        await self._run_llm_action(msg, "materials_audit", MATERIALS_AUDIT_PROMPT,
                                   f"【简历】\n{resume_text}", resume_text, "", 0.3)

    # ── 5 轮压力面试 ──

    async def _handle_interview_grilling(self, msg: AgentMessage) -> None:
        resume_text, jd_text = self._extract_texts(msg)
        ok, err = self._validate_texts(resume_text, jd_text)
        if not ok:
            return await self._err(msg, err)
        resume_text, jd_text = self._sanitize_texts(resume_text, jd_text)
        await self._run_llm_action(msg, "interview_grilling", INTERVIEW_GRILLING_PROMPT,
                                   f"【简历】\n{resume_text}\n\n【JD】\n{jd_text}",
                                   resume_text, jd_text, 0.5)

    # ── 面试回答卡片 ──

    async def _handle_answer_cards(self, msg: AgentMessage) -> None:
        resume_text, jd_text = self._extract_texts(msg)
        questions = msg.payload.get("questions", [])
        ok, err = self._validate_texts(resume_text, jd_text)
        if not ok:
            return await self._err(msg, err)
        resume_text, jd_text = self._sanitize_texts(resume_text, jd_text)

        user_msg = f"【简历】\n{resume_text}\n\n【JD】\n{jd_text}"
        questions_key = ""
        if questions:
            questions = questions[:10]
            questions_text = "\n".join(f"{i+1}. {q}" for i, q in enumerate(questions))
            user_msg += f"\n\n【指定面试题】\n{questions_text}"
            questions_key = json.dumps(questions, ensure_ascii=False)
        else:
            user_msg += "\n\n请根据简历和 JD 自动生成 5 个高频面试题，并为每题生成三种水平的回答卡片。"

        # questions 也参与缓存 key
        ck = self._cache_key("answer_cards", resume_text, jd_text, questions_key)
        cached = self._cache_get(ck)
        if cached:
            cached["from_cache"] = True
            return await self._ok(msg, cached)

        await self._run_llm_action(msg, "answer_cards", ANSWER_CARDS_PROMPT,
                                   user_msg, resume_text, jd_text, 0.5)

    # ── 证据升级计划 ──

    async def _handle_upgrade_plan(self, msg: AgentMessage) -> None:
        resume_text = msg.payload.get("resume_text", "")
        audit_result = msg.payload.get("audit_result", {})
        ok, err = self._validate_texts(resume_text, "", need_resume=True, need_jd=False)
        if not ok:
            return await self._err(msg, err)
        resume_text = resume_text.strip()[:_RESUME_MAX_LEN]

        user_msg = f"【简历】\n{resume_text}"
        if audit_result:
            user_msg += f"\n\n【审计结果】\n{json.dumps(audit_result, ensure_ascii=False)[:3000]}"
        else:
            user_msg += "\n\n（未提供审计结果，请先对简历进行证据审计，再制定升级计划）"

        audit_key = json.dumps(audit_result, ensure_ascii=False)[:500] if audit_result else ""
        await self._run_llm_action(msg, "upgrade_plan", UPGRADE_PLAN_PROMPT,
                                   user_msg, resume_text, audit_key, 0.4)

    # ── 工具方法 ──

    def _extract_texts(self, msg: AgentMessage) -> Tuple[str, str]:
        return msg.payload.get("resume_text", ""), msg.payload.get("jd_text", "")

    async def _ok(self, msg: AgentMessage, data: dict) -> None:
        data["correlation_id"] = msg.correlation_id
        await self.send(msg.source, "result", data, correlation_id=msg.correlation_id)

    async def _err(self, msg: AgentMessage, error: str) -> None:
        await self.send(msg.source, "result", {
            "error": error, "correlation_id": msg.correlation_id,
        }, correlation_id=msg.correlation_id)

    def _llm_call(self, system_prompt: str, user_msg: str, temperature: float = 0.4) -> dict:
        from llm_client import llm_call_with_config
        cfg = self.get_llm_config()
        raw = llm_call_with_config(
            cfg,
            [{"role": "user", "content": user_msg}],
            system_prompt=system_prompt,
            temperature=temperature,
        )
        return self._parse_json(raw)

    def _parse_json(self, raw: str) -> dict:
        raw = raw.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            m = re.search(r"\{.*\}", raw, re.DOTALL)
            if m:
                try:
                    return json.loads(m.group())
                except json.JSONDecodeError:
                    pass
            raise ValueError(f"LLM 返回了无法解析的内容: {raw[:200]}")
