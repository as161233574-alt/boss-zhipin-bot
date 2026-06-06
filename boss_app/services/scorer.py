"""岗位评分与真实性检测服务。

- score_job: LLM 多维度加权评分 (0-100)
- check_legitimacy: 纯规则引擎检测可疑岗位
"""

import json
import re
import sys
from pathlib import Path

# 确保 interview 目录在 sys.path 中
_interview_dir = str(Path(__file__).resolve().parent.parent.parent / "interview")
if _interview_dir not in sys.path:
    sys.path.insert(0, _interview_dir)

from llm_client import llm_chat_deepseek, _load_ai_config


def _strip_code_fence(text: str) -> str:
    """去掉 LLM 返回的 ```json ... ``` 包裹，便于 json.loads。"""
    cleaned = text.strip()
    # 尝试提取 ```json ... ``` 块（大小写不敏感，允许前后有其他文本）
    m = re.search(r"```(?:json)?\s*(.*?)\s*```", cleaned, re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1).strip()
    # 去掉开头的 ```json 标记（无闭合的情况）
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    # 去掉结尾的 ``` 标记
    cleaned = re.sub(r"\s*```\s*$", "", cleaned)
    return cleaned.strip()


# ══════════════════════════════════════
#  岗位评分 (LLM)
# ══════════════════════════════════════


def score_job(
    job_title: str,
    company: str,
    description: str,
    salary: str,
    resume_summary: str = "",
) -> dict:
    """对岗位进行多维度评分，返回 {"score": 85, "key_skills": [...], "gap": "...", "advice": "..."}。

    有简历时做 CV 匹配加权评分；无简历时只评估客观维度。
    """
    cfg = _load_ai_config()
    if not cfg.get("api_key") or len(cfg["api_key"]) < 10:
        return {"score": None, "key_skills": [], "gap": "", "advice": "", "summary": "AI未配置", "has_resume": False}

    has_resume = bool(resume_summary and len(resume_summary.strip()) > 5)

    if has_resume:
        prompt = f"""你是求职辅导专家。请严格根据简历与岗位的匹配度进行 0-100 分评分。

## 求职者简历摘要
{resume_summary[:1500]}

## 岗位信息
- 职位: {job_title}
- 公司: {company}
- 薪资: {salary}
- JD: {description[:2000]}

## 评分规则（严格）
**核心原则：简历中的技能/经验与岗位要求不匹配时，必须给低分（<50分）。**

1. 技能匹配度 (40%): 简历中的核心技术栈与岗位要求的重合度。重合度低→低分。
2. 经验匹配度 (20%): 简历经验与岗位要求是否吻合。岗位要求的经验领域与简历不符→低分。
3. 薪资合理性 (15%): 薪资范围是否透明、合理
4. 公司信息 (10%): 公司是否有足够信息
5. 发展前景 (10%): 行业/技术方向前景
6. 其他因素 (5%): 工作地点、远程可能性等

## 关键判定
- 如果岗位的核心职责与简历技能领域不匹配（如简历写Linux运维，岗位是前端开发），直接给 20-40 分
- 如果岗位只是部分匹配（如简历写Linux/Docker，岗位提到了Linux但主要是网络运维），给 40-60 分
- 只有岗位核心职责与简历高度匹配时才给 70 分以上

## 输出格式（严格JSON）
{{
  "score": 85,
  "key_skills": ["Python", "LangChain", "RAG"],
  "gap": "缺少K8s部署经验",
  "advice": "建议强调Agent开发经验",
  "summary": "整体匹配度较高"
}}"""
    else:
        prompt = f"""你是求职辅导专家。对以下岗位进行客观评分（不对比简历）。

## 岗位信息
- 职位: {job_title}
- 公司: {company}
- 薪资: {salary}
- JD: {description[:2000]}

## 评分维度（仅客观维度）
1. 薪资透明度 (25%): 薪资范围是否明确、合理
2. 岗位描述质量 (25%): JD 是否详细、职责清晰
3. 技能要求合理性 (20%): 要求是否过高/过低
4. 公司信息 (15%): 公司是否有足够信息
5. 发展前景 (15%): 行业/技术方向前景

## 输出格式（严格JSON）
{{
  "score": 70,
  "key_skills": ["Python", "FastAPI"],
  "gap": "",
  "advice": "",
  "summary": "岗位描述清晰，薪资透明"
}}"""

    raw = ""
    try:
        raw = llm_chat_deepseek(
            [{"role": "user", "content": prompt}],
            system_prompt="你是求职辅导专家。输出严格JSON，不要输出任何其他内容。",
            temperature=0.3,
        )
        result = json.loads(_strip_code_fence(raw))
        result["has_resume"] = has_resume
        # 确保 score 在合理范围
        if result.get("score") is not None:
            result["score"] = max(0, min(100, int(result["score"])))
        return result
    except (json.JSONDecodeError, ValueError):
        return {"score": None, "key_skills": [], "gap": "", "advice": "", "summary": raw[:200] if raw else "评分失败", "has_resume": has_resume}
    except Exception as e:
        return {"score": None, "key_skills": [], "gap": "", "advice": "", "summary": f"评分异常: {str(e)[:100]}", "has_resume": has_resume}


# ══════════════════════════════════════
#  岗位真实性检测 (规则引擎)
# ══════════════════════════════════════


def check_legitimacy(job: dict, existing_jobs: list = None) -> dict:
    """规则引擎检测可疑岗位，返回 {"level": "high/caution/suspicious", "signals": [...]}。

    信号:
    1. JD 过短 (<50 字)
    2. 薪资异常（范围过大或明显偏高）
    3. HR 信息缺失
    4. 同公司重复发布相同岗位
    """
    signals = []
    existing_jobs = existing_jobs or []

    description = (job.get("description") or "").strip()
    salary = (job.get("salary") or "").strip()
    hr_name = (job.get("hr_name") or "").strip()
    company = (job.get("company") or "").strip()
    title = (job.get("title") or job.get("job_title") or "").strip()

    # 1. JD 过短
    if len(description) < 50:
        signals.append({"type": "short_jd", "detail": f"岗位描述仅 {len(description)} 字"})

    # 2. 薪资异常
    if salary:
        # 提取数字（万/月 或 千/月）
        nums = re.findall(r"[\d.]+", salary)
        if len(nums) >= 2:
            try:
                low, high = float(nums[0]), float(nums[1])
                if high > 0 and (high / max(low, 0.1)) > 5:
                    signals.append({"type": "salary_range_wide", "detail": f"薪资范围过大: {salary}"})
                # 月薪超过 10 万可疑
                if high > 100 and "月" in salary:
                    signals.append({"type": "salary_too_high", "detail": f"薪资异常偏高: {salary}"})
            except ValueError:
                pass
        elif not nums and salary:
            signals.append({"type": "salary_unclear", "detail": f"薪资格式不明确: {salary}"})

    # 3. HR 信息缺失
    if not hr_name:
        signals.append({"type": "no_hr", "detail": "未显示HR信息"})

    # 4. 同公司重复发布
    if company and existing_jobs:
        same_company_jobs = [j for j in existing_jobs if (j.get("company") or "").strip() == company]
        if len(same_company_jobs) >= 3:
            same_title_jobs = [j for j in same_company_jobs if (j.get("job_title") or j.get("title") or "").strip() == title]
            if len(same_title_jobs) >= 2:
                signals.append({
                    "type": "duplicate_posting",
                    "detail": f"该公司近期发布了 {len(same_title_jobs)} 条相同岗位",
                })

    # 判定等级
    if len(signals) >= 3:
        level = "suspicious"
    elif len(signals) >= 1:
        level = "caution"
    else:
        level = "high"

    return {"level": level, "signals": signals}


# ══════════════════════════════════════
#  HR 活跃度评分 (规则引擎)
# ══════════════════════════════════════


def score_hr_activity(activity_text: str) -> int:
    """将 HR 活跃度文本转换为 0-100 分。"""
    if not activity_text:
        return 0
    if "刚刚活跃" in activity_text:
        return 100
    if "今日活跃" in activity_text:
        return 80
    # 匹配 "3日内活跃"、"三天内活跃" 等，避免误中"半年内"
    if re.search(r'\d+日内活跃|三天内活跃', activity_text):
        return 60
    if "本周活跃" in activity_text:
        return 40
    if "本月活跃" in activity_text:
        return 30
    if "半年" in activity_text and "活跃" in activity_text:
        return 20
    if "活跃" in activity_text:
        return 10
    return 0


# ══════════════════════════════════════
#  招聘信息质量评估 (LLM)
# ══════════════════════════════════════


def score_job_quality(
    job_title: str,
    company: str,
    description: str,
    salary: str,
    hr_name: str,
) -> dict:
    """评估招聘信息质量，返回 {"quality_score": 75, "quality_notes": "..."}。"""
    cfg = _load_ai_config()
    if not cfg.get("api_key") or len(cfg["api_key"]) < 10:
        return {"quality_score": None, "quality_notes": "AI未配置"}

    prompt = f"""你是求职顾问。请评估以下岗位招聘信息的完整度和质量，返回0-100分。

## 岗位信息
- 职位: {job_title}
- 公司: {company}
- 薪资: {salary}
- JD: {description[:1500]}
- HR信息: {'有（' + hr_name + '）' if hr_name else '无'}

## 评分维度
1. JD详细程度 (30%): 职责描述是否清晰、具体、有条理
2. 薪资透明度 (25%): 薪资范围是否明确、合理
3. 公司信息 (20%): 公司是否有足够可查信息
4. 技术要求合理性 (15%): 要求是否过高/过低/模糊
5. HR可信度 (10%): HR是否有名字/职位等可信信息

## 输出格式（严格JSON）
{{"quality_score": 75, "quality_notes": "JD较详细，薪资明确"}}"""

    raw = ""
    try:
        raw = llm_chat_deepseek(
            [{"role": "user", "content": prompt}],
            system_prompt="你是求职顾问。输出严格JSON，不要输出任何其他内容。",
            temperature=0.3,
        )
        result = json.loads(_strip_code_fence(raw))
        if result.get("quality_score") is not None:
            result["quality_score"] = max(0, min(100, int(result["quality_score"])))
        return result
    except (json.JSONDecodeError, ValueError):
        return {"quality_score": None, "quality_notes": raw[:200] if raw else "评分失败"}
    except Exception as e:
        return {"quality_score": None, "quality_notes": f"异常: {str(e)[:100]}"}


# ══════════════════════════════════════
#  综合评分
# ══════════════════════════════════════


def compute_composite_score(cv_match_score, quality_score, hr_activity_score) -> int:
    """加权综合分：简历匹配 55% + 招聘质量 25% + HR活跃度 20%。

    缺失维度的权重按比例重分配到其他维度。
    """
    scores = []
    weights = []
    if cv_match_score is not None:
        scores.append(cv_match_score)
        weights.append(0.55)
    if quality_score is not None:
        scores.append(quality_score)
        weights.append(0.25)
    if hr_activity_score is not None:
        scores.append(hr_activity_score)
        weights.append(0.20)

    if not weights:
        return 0

    total_w = sum(weights)
    composite = sum(s * w for s, w in zip(scores, weights)) / total_w
    return max(0, min(100, int(round(composite))))


# ══════════════════════════════════════
#  合并评分（一次 LLM 调用返回 CV + 质量分）
# ══════════════════════════════════════


def score_job_combined(
    job_title: str,
    company: str,
    description: str,
    salary: str,
    hr_name: str,
    resume_summary: str = "",
) -> dict:
    """一次 LLM 调用同时返回 CV 匹配分和招聘质量分，节省 50% LLM 时间。"""
    cfg = _load_ai_config()
    if not cfg.get("api_key") or len(cfg["api_key"]) < 10:
        return {"cv_score": None, "quality_score": None, "key_skills": [], "gap": "", "advice": "", "summary": "AI未配置", "quality_notes": "AI未配置", "has_resume": False}

    has_resume = bool(resume_summary and len(resume_summary.strip()) > 5)

    resume_section = ""
    if has_resume:
        resume_section = f"""
## 求职者简历摘要
{resume_summary[:1500]}"""

    prompt = f"""你是求职辅导专家。请对以下岗位同时进行两项评分，返回严格JSON。
{resume_section}

## 岗位信息
- 职位: {job_title}
- 公司: {company}
- 薪资: {salary}
- JD: {description[:2000]}
- HR信息: {'有（' + hr_name + '）' if hr_name else '无'}

## 评分任务

### 任务1: CV匹配度评分 (cv_score, 0-100)
{'根据简历与岗位的匹配度评分。技能不匹配→低分(<50)，高度匹配→70+。\n评估维度: 技能匹配(40%)、经验匹配(20%)、薪资合理性(15%)、公司信息(10%)、发展前景(10%)、其他(5%)' if has_resume else '无简历，仅评估客观维度：薪资透明度25%、JD质量25%、技能要求合理性20%、公司信息15%、发展前景15%。'}

### 任务2: 招聘信息质量评分 (quality_score, 0-100)
评估JD的完整度和质量。
评估维度: JD详细程度(30%)、薪资透明度(25%)、公司信息(20%)、技术要求合理性(15%)、HR可信度(10%)

## 输出格式（严格JSON，不要输出任何其他内容）
{{
  "cv_score": 75,
  "quality_score": 70,
  "key_skills": ["Python", "FastAPI", "Docker"],
  "gap": "缺少K8s和微服务经验",
  "advice": "建议在简历中强调项目经验和技术栈匹配度",
  "summary": "整体匹配度中等，技术栈基本吻合",
  "quality_notes": "JD较详细，薪资明确，公司信息完整"
}}

注意：
- key_skills: 必须列出至少2个岗位要求的核心技能
- gap: 必须说明求职者与岗位之间的主要差距
- advice: 必须给出至少一条具体建议
- summary: 必须用一句话概括匹配度
- quality_notes: 必须说明JD质量的优缺点"""

    raw = ""
    try:
        raw = llm_chat_deepseek(
            [{"role": "user", "content": prompt}],
            system_prompt="你是求职辅导专家。输出严格JSON，不要输出任何其他内容。",
            temperature=0.3,
        )
        result = json.loads(_strip_code_fence(raw))
        result["has_resume"] = has_resume
        if result.get("cv_score") is not None:
            result["cv_score"] = max(0, min(100, int(result["cv_score"])))
        if result.get("quality_score") is not None:
            result["quality_score"] = max(0, min(100, int(result["quality_score"])))
        # 确保关键字段非空
        if not result.get("key_skills"):
            result["key_skills"] = []
        if not result.get("gap"):
            result["gap"] = "待分析"
        if not result.get("advice"):
            result["advice"] = "建议进一步了解岗位详情"
        if not result.get("summary"):
            result["summary"] = "评分完成"
        if not result.get("quality_notes"):
            result["quality_notes"] = "评分完成"
        return result
    except (json.JSONDecodeError, ValueError):
        return {"cv_score": None, "quality_score": None, "key_skills": [], "gap": "", "advice": "", "summary": raw[:200] if raw else "评分失败", "quality_notes": "解析失败", "has_resume": has_resume}
    except Exception as e:
        return {"cv_score": None, "quality_score": None, "key_skills": [], "gap": "", "advice": "", "summary": f"评分异常: {str(e)[:100]}", "quality_notes": f"异常: {str(e)[:50]}", "has_resume": has_resume}
