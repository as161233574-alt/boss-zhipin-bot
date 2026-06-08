"""设置相关 API 路由。

包含设置读写、投递转化漏斗统计、数据一致性修复、简历上传等接口。
"""

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel

from ..core.websocket import ws_manager
from ..models.application import (
    get_today_application_count,
    get_today_pending_count,
    count_hours_replied_in_range,
    count_interest_level,
    reconcile_application_stats,
)
from ..models.conversation import list_active_conversations
from ..models.settings import (
    get_setting,
    set_setting,
    set_settings_bulk,
    get_all_settings,
    get_daily_stats,
    get_stats_range,
    get_funnel_stats,
    DEFAULT_SETTINGS,
)
from ..services.resume_parser import parse_resume_file

router = APIRouter()


# ══════════════════════════════════════
#  Pydantic Models
# ══════════════════════════════════════


class SettingsUpdate(BaseModel):
    greeting_template: Optional[str] = None
    greeting_enabled: Optional[str] = None
    greeting_type: Optional[str] = None
    ai_reply_style: Optional[str] = None
    ai_platform: Optional[str] = None
    daily_apply_limit: Optional[str] = None
    auto_reply_enabled: Optional[str] = None
    min_reply_delay_sec: Optional[str] = None
    max_reply_delay_sec: Optional[str] = None
    reply_delay_min: Optional[str] = None  # 前端别名
    reply_delay_max: Optional[str] = None  # 前端别名
    batch_delay_min_sec: Optional[str] = None
    batch_delay_max_sec: Optional[str] = None
    resume_summary: Optional[str] = None
    wechat_id: Optional[str] = None
    search_keywords: Optional[str] = None
    default_city: Optional[str] = None
    search_city: Optional[str] = None  # 前端别名
    search_max_pages: Optional[str] = None
    selector_overrides: Optional[str] = None
    ai_api_key: Optional[str] = None
    ai_base_url: Optional[str] = None
    ai_model: Optional[str] = None
    auto_schedule_enabled: Optional[str] = None
    auto_schedule_cron: Optional[str] = None
    auto_apply_enabled: Optional[str] = None
    auto_apply_threshold: Optional[str] = None
    auto_apply_min_score: Optional[str] = None  # 前端别名
    auto_apply_hr_active_required: Optional[str] = None
    filter_inactive_hr: Optional[str] = None
    smart_greeting_enabled: Optional[str] = None
    experience_min: Optional[str] = None
    experience_max: Optional[str] = None
    salary_min: Optional[str] = None
    salary_max: Optional[str] = None
    salary_unit: Optional[str] = None
    company_blacklist: Optional[str] = None
    hr_blacklist: Optional[str] = None


# ══════════════════════════════════════
#  设置
# ══════════════════════════════════════


@router.get("/api/settings")
def read_settings():
    # 合并默认值 + 数据库值
    settings = {**DEFAULT_SETTINGS, **get_all_settings()}
    # 检查AI Key是否已配置
    ai_key = settings.get("ai_api_key", "")
    settings["ai_key_configured"] = "true" if ai_key and len(ai_key) > 10 else "false"
    settings.pop("ai_api_key", None)  # 不泄露完整密钥
    # 字段别名：后端key → 前端key
    settings["search_city"] = settings.get("default_city", "")
    settings["auto_apply_min_score"] = settings.get("auto_apply_threshold", "60")
    settings["reply_delay_min"] = settings.get("min_reply_delay_sec", "3")
    settings["reply_delay_max"] = settings.get("max_reply_delay_sec", "8")
    return {"settings": settings}


@router.put("/api/settings")
async def update_settings(req: SettingsUpdate):
    # 前端字段名 → 后端字段名 映射
    FIELD_ALIASES = {
        "search_city": "default_city",
        "auto_apply_min_score": "auto_apply_threshold",
        "reply_delay_min": "min_reply_delay_sec",
        "reply_delay_max": "max_reply_delay_sec",
    }
    updates = {}
    for k, v in req.model_dump().items():
        if k == "ai_api_key" and v:
            set_setting("ai_api_key", str(v))
            updates["ai_key_configured"] = "true"
            continue
        if v is not None:
            # 写入时使用后端真实字段名
            real_key = FIELD_ALIASES.get(k, k)
            set_setting(real_key, str(v))
            updates[k] = str(v)
    await ws_manager.broadcast({"type": "settings_updated", "updates": updates})
    return {"status": "ok", "updated": updates}


class SmartGreetingRequest(BaseModel):
    job_title: str
    company: str
    salary: Optional[str] = ""
    experience: Optional[str] = ""
    education: Optional[str] = ""
    job_description: Optional[str] = ""


@router.post("/api/settings/smart-greeting")
def generate_smart_greeting(req: SmartGreetingRequest):
    """生成智能打招呼内容。"""
    from ..services.replier import generate_smart_greeting

    resume_summary = get_setting("resume_summary", "")
    greeting = generate_smart_greeting(
        job_title=req.job_title,
        company=req.company,
        salary=req.salary,
        experience=req.experience,
        education=req.education,
        resume_summary=resume_summary,
        job_description=req.job_description,
    )
    return {"greeting": greeting}


# ══════════════════════════════════════
#  统计
# ══════════════════════════════════════


@router.get("/api/stats")
def get_stats():
    """投递转化漏斗统计。"""
    today = get_daily_stats()
    return {
        "today_applications": get_today_application_count(),
        "pending": get_today_pending_count(),
        "replied": count_hours_replied_in_range(24),
        "interview": count_interest_level("high"),
        "active_conversations": len(list_active_conversations()),
        "daily_stats": today,
    }


@router.post("/api/stats/reconcile")
def reconcile_stats():
    """手动触发数据一致性校验，修复统计偏差。"""
    fixed = reconcile_application_stats()
    return {
        "fixed": fixed,
        "today_applications": get_today_application_count(),
        "pending": get_today_pending_count(),
    }


@router.get("/api/stats/trend")
def get_trend(days: int = 7):
    """返回最近 N 天的每日统计数据数组。"""
    return {"trend": get_stats_range(days)}


@router.get("/api/stats/funnel")
def get_funnel():
    """返回转化漏斗数据。"""
    return get_funnel_stats()


# ══════════════════════════════════════
#  简历上传
# ══════════════════════════════════════

# 简历文件大小限制：5MB
MAX_RESUME_SIZE = 5 * 1024 * 1024
ALLOWED_RESUME_EXT = {".pdf", ".txt", ".md"}


@router.post("/api/settings/resume/upload")
async def upload_resume(file: UploadFile = File(...)):
    """上传简历文件（PDF/TXT/MD），自动解析并写入 resume_summary。"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="缺少文件名")

    suffix = Path(file.filename).suffix.lower()
    if suffix not in ALLOWED_RESUME_EXT:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型 {suffix}, 仅支持 {', '.join(ALLOWED_RESUME_EXT)}",
        )

    content = await file.read()
    if len(content) > MAX_RESUME_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"文件过大 ({len(content)//1024}KB), 上限 {MAX_RESUME_SIZE//1024//1024}MB",
        )
    if not content:
        raise HTTPException(status_code=400, detail="文件为空")

    try:
        result = parse_resume_file(content, file.filename)
    except Exception as e:
        print(f"[简历] 解析失败: {e}")
        raise HTTPException(status_code=422, detail="简历解析失败，请检查文件格式后重试")

    if not result["summary"]:
        raise HTTPException(
            status_code=422,
            detail=f"未能从简历中提取关键信息 (文本长度 {result['text_length']})",
        )

    set_settings_bulk({
        "resume_summary": result["summary"],
        "resume_full_text": result["full_text"],
        "resume_filename": file.filename,
        "resume_text_length": str(result["text_length"]),
    })

    return {
        "status": "ok",
        "filename": file.filename,
        "text_length": result["text_length"],
        "summary_length": len(result["summary"]),
        "summary_preview": result["summary"][:200],
        "full_text_length": len(result["full_text"]),
    }


@router.delete("/api/settings/resume")
def delete_resume():
    """清除已上传的简历。"""
    set_settings_bulk({
        "resume_summary": "",
        "resume_full_text": "",
        "resume_filename": "",
        "resume_text_length": "0",
    })
    return {"status": "ok"}
