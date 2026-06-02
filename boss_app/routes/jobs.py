"""岗位相关 API 路由。

包含岗位搜索、管理、投递、删除/回收站、候选池、去重等全部接口。
"""

import re
import sys
from pathlib import Path
from typing import Optional, List
from urllib.parse import urljoin

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..core.database import get_db
from ..core.websocket import ws_manager
from ..core.monitor import chat_monitor
from ..models.application import (
    add_application,
    get_application,
    get_application_by_url,
    get_application_by_dedup_key,
    compute_dedup_key,
    update_application_from_job,
    list_applications,
    update_application_status,
    get_today_application_count,
    soft_delete_application,
    soft_delete_applications,
    clear_all_applications,
    get_trash_applications,
    restore_application,
    restore_applications,
    purge_old_trashes,
    get_delete_logs,
    get_trash_count,
    deduplicate_applications,
    get_duplicate_stats,
)
from ..models.settings import get_setting
from ..core import state
from boss_replier import generate_greeting
from boss_state import (
    add_to_shortlist,
    remove_from_shortlist,
    list_shortlists,
    is_in_shortlist,
)

router = APIRouter()

# ══════════════════════════════════════
#  BOSS直聘城市代码（按省份分组）
# ══════════════════════════════════════

CITY_MAP = {
    # 山东省
    "济南": "101120100",
    "青岛": "101120200",
    "淄博": "101120300",
    "德州": "101120400",
    "烟台": "101120500",
    "潍坊": "101120600",
    "济宁": "101120700",
    "泰安": "101120800",
    "临沂": "101120900",
    "菏泽": "101121000",
    "滨州": "101121100",
    "东营": "101121200",
    "威海": "101121300",
    "枣庄": "101121400",
    "日照": "101121500",
    "聊城": "101121700",
    # 一线城市
    "北京": "101010100",
    "上海": "101020100",
    "广州": "101280100",
    "深圳": "101280600",
    # 新一线城市
    "成都": "101270100",
    "杭州": "101210100",
    "武汉": "101200100",
    "南京": "101190100",
    "重庆": "101040100",
    "西安": "101110100",
    "长沙": "101250100",
    "天津": "101030100",
    "苏州": "101190400",
    "郑州": "101180100",
    "东莞": "101281600",
    "沈阳": "101070100",
    "宁波": "101210400",
    "昆明": "101290100",
    # 其他省会城市
    "合肥": "101220100",
    "福州": "101230100",
    "厦门": "101230200",
    "南昌": "101240100",
    "贵阳": "101260100",
    "南宁": "101300100",
    "太原": "101100100",
    "石家庄": "101090100",
    "哈尔滨": "101050100",
    "长春": "101060100",
    "兰州": "101160100",
    "乌鲁木齐": "101130100",
    "呼和浩特": "101080100",
    "拉萨": "101140100",
    "西宁": "101150100",
    "银川": "101170100",
    "海口": "101310100",
    "三亚": "101310200",
    # 特殊选项
    "全国": "100010000",
}


# ══════════════════════════════════════
#  Helpers
# ══════════════════════════════════════


def _normalize_job_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    return urljoin("https://www.zhipin.com", url)


def _deduplicate_jobs(jobs: list) -> list:
    """对爬取结果按 dedup_key 去重，同一页面内相同岗位只保留第一条。"""
    seen = set()
    result = []
    for j in jobs:
        key = compute_dedup_key(j)
        if not key:
            key = j.get("url", "") or id(j)
        if key not in seen:
            seen.add(key)
            result.append(j)
    return result


def _save_job_with_dedup(job: dict) -> tuple:
    """保存岗位（dedup_key + URL 双重查重）。返回 (app_id, is_new)。is_new=True 表示首次入库。"""
    job["url"] = _normalize_job_url(job.get("url", ""))
    dedup_key = compute_dedup_key(job)
    # 优先用 dedup_key 查重
    if dedup_key:
        existing = get_application_by_dedup_key(dedup_key)
        if existing:
            # URL 变化时补更新
            if job["url"] and job["url"] != (existing.get("job_url") or ""):
                db = get_db()
                db.execute("UPDATE applications SET job_url=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                           (job["url"], existing["id"]))
                db.commit()
            update_application_from_job(existing["id"], job)
            return existing["id"], False
    # 再用 URL 查重
    if job["url"]:
        existing = get_application_by_url(job["url"])
        if existing:
            update_application_from_job(existing["id"], job)
            return existing["id"], False
    # 新记录
    aid = add_application(job)
    return (aid, True) if aid else (0, False)


def _search_job_payload(job: dict, application: Optional[dict] = None) -> dict:
    """统一搜索结果和数据库记录的字段名，方便前端直接渲染。"""
    application = application or {}
    return {
        "id": application.get("id"),
        "job_title": application.get("job_title") or job.get("title", ""),
        "company": application.get("company") or job.get("company", ""),
        "salary": application.get("salary") or job.get("salary", ""),
        "job_url": application.get("job_url") or _normalize_job_url(job.get("url", "")),
        "city": application.get("city") or job.get("city", ""),
        "experience": application.get("experience") or job.get("experience", ""),
        "education": application.get("education") or job.get("education", ""),
        "hr_name": application.get("hr_name") or job.get("hr_name", ""),
        "hr_title": application.get("hr_title") or job.get("hr_title", ""),
        "description": application.get("description") or job.get("description", ""),
        "status": application.get("status") or ("pending" if job.get("url") else "missing_url"),
    }


# ══════════════════════════════════════
#  Pydantic Models
# ══════════════════════════════════════


class SearchRequest(BaseModel):
    keyword: str = "AI Agent"
    city: str = ""
    welfare: Optional[str] = None
    limit: int = 60
    max_pages: int = 5


class ApplyRequest(BaseModel):
    job_url: str
    greeting: Optional[str] = None


class ApplyBatchRequest(BaseModel):
    job_urls: List[str]
    greeting: Optional[str] = None


class ScanAndApplyRequest(BaseModel):
    greeting: Optional[str] = None


class AnalyzeRequest(BaseModel):
    job_url: str
    job_title: Optional[str] = ""
    company: Optional[str] = ""
    description: Optional[str] = ""


class DeleteRequest(BaseModel):
    job_ids: List[int]


class RestoreRequest(BaseModel):
    job_ids: List[int]


class ClearRequest(BaseModel):
    confirm: str = ""


# ══════════════════════════════════════
#  岗位列表 & 搜索
# ══════════════════════════════════════


@router.get("/api/jobs")
def list_jobs(status: Optional[str] = None, limit: int = 100):
    jobs = list_applications(status, limit)
    return {"jobs": jobs, "total": len(jobs)}


@router.post("/api/jobs/search")
async def search_jobs(req: SearchRequest):
    if not state.automation or state.automation.page is None:
        raise HTTPException(status_code=503, detail="浏览器未启动，请先到设置Tab点击「启动浏览器」")
    was_paused = chat_monitor.paused
    chat_monitor.paused = True
    try:
        async with state.browser_sync_lock:
            city_code = CITY_MAP.get(req.city or get_setting("default_city", "全国"), "100010000")
            try:
                jobs = await state.automation.search(req.keyword, city_code, max_pages=req.max_pages)
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"搜索失败: {e}")

            # 福利筛选
            if req.welfare:
                welfare_kw = [w.strip() for w in req.welfare.split(",") if w.strip()]
                jobs = state.automation._filter_by_welfare(jobs, welfare_kw)

            raw_found = len(jobs)
            jobs = _deduplicate_jobs(jobs)
            page_dup = raw_found - len(jobs)

            new_ids = []
            result_jobs = []
            db_existing = 0
            for j in jobs:
                aid, is_new = _save_job_with_dedup(j)
                if is_new and aid:
                    new_ids.append(aid)
                    result_jobs.append(_search_job_payload(j, get_application(aid)))
                elif not is_new:
                    db_existing += 1

            print(f"[搜索] 页面 {raw_found} 条 → 去重 {len(jobs)} 条 → 新增 {len(new_ids)}，已有 {db_existing}")

            await ws_manager.broadcast(
                {
                    "type": "search_complete",
                    "keyword": req.keyword,
                    "city": req.city,
                    "found": len(jobs),
                    "new": len(new_ids),
                    "existing": db_existing,
                    "page_dup": page_dup,
                }
            )
            resp = {"jobs_found": len(jobs), "new_jobs": len(new_ids), "db_existing": db_existing, "page_duplicates": page_dup, "saved": len(new_ids), "jobs": result_jobs}
            return resp
    finally:
        chat_monitor.paused = was_paused


# ══════════════════════════════════════
#  去重
# ══════════════════════════════════════


@router.post("/api/jobs/deduplicate")
def deduplicate_jobs():
    """清理历史重复数据：按 公司+岗位+城市+薪资 联合去重，每组保留最早记录。"""
    result = deduplicate_applications()
    return result


@router.get("/api/jobs/dedup-stats")
def get_dedup_stats():
    """获取当前数据库去重统计信息。"""
    return get_duplicate_stats()


@router.get("/api/jobs/{job_id}")
def get_job(job_id: int):
    job = get_application(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="岗位不存在")
    return {"job": job}


@router.post("/api/jobs/{job_id}/skip")
async def skip_job(job_id: int):
    update_application_status(job_id, "skipped")
    await ws_manager.broadcast({"type": "job_updated", "job_id": job_id, "status": "skipped"})
    return {"status": "ok"}


# ══════════════════════════════════════
#  删除 & 回收站
# ══════════════════════════════════════


@router.post("/api/jobs/delete")
async def delete_job(req: DeleteRequest):
    if not req.job_ids:
        raise HTTPException(status_code=400, detail="缺少 job_ids")
    count = soft_delete_applications(req.job_ids)
    await ws_manager.broadcast({"type": "jobs_deleted", "count": count})
    return {"status": "ok", "deleted": count}


@router.post("/api/jobs/clear")
async def clear_jobs(req: ClearRequest):
    if req.confirm != "确认清空":
        raise HTTPException(status_code=400, detail='请输入"确认清空"以验证操作')
    count = clear_all_applications()
    await ws_manager.broadcast({"type": "jobs_cleared", "count": count})
    return {"status": "ok", "deleted": count}


@router.get("/api/trash")
def list_trash():
    return {"trash": get_trash_applications(), "count": get_trash_count()}


@router.post("/api/trash/restore")
async def restore_trash(req: RestoreRequest):
    if not req.job_ids:
        raise HTTPException(status_code=400, detail="缺少 job_ids")
    count = restore_applications(req.job_ids)
    return {"status": "ok", "restored": count}


@router.post("/api/trash/purge")
def purge_trash():
    count = purge_old_trashes(7)
    return {"status": "ok", "purged": count}


@router.get("/api/delete-logs")
def list_delete_logs():
    return {"logs": get_delete_logs()}


@router.get("/api/trash/count")
def trash_count():
    return {"count": get_trash_count()}


# ══════════════════════════════════════
#  投递
# ══════════════════════════════════════


@router.post("/api/jobs/apply")
async def apply_to_job(req: ApplyRequest):
    if not state.automation:
        raise HTTPException(status_code=503, detail="浏览器未启动")

    daily_limit = int(get_setting("daily_apply_limit", "15"))
    if get_today_application_count() >= daily_limit:
        raise HTTPException(status_code=429, detail="已达到今日投递上限")

    greeting = req.greeting
    if not greeting:
        job = get_application_by_url(req.job_url)
        title = job["job_title"] if job else "相关岗位"
        company = job["company"] if job else "贵公司"
        style = get_setting("ai_reply_style", "professional")
        greeting = generate_greeting(title, company, style=style)

    result = await state.automation.apply_to_job(req.job_url, greeting)
    if result.get("success"):
        await ws_manager.broadcast(
            {
                "type": "apply_complete",
                "job_url": req.job_url,
                "job_id": result.get("application_id"),
            }
        )
    return result


@router.post("/api/jobs/apply-batch")
async def apply_batch(req: ApplyBatchRequest):
    if not state.automation:
        raise HTTPException(status_code=503, detail="浏览器未启动")

    daily_limit = int(get_setting("daily_apply_limit", "15"))
    remaining = daily_limit - get_today_application_count()
    urls = req.job_urls[: max(1, remaining)]

    results = await state.automation.apply_batch(urls, req.greeting)
    await ws_manager.broadcast(
        {
            "type": "batch_complete",
            "total": len(results),
            "success": sum(1 for r in results if r.get("success")),
        }
    )
    return {"results": results}


@router.post("/api/jobs/scan")
async def scan_current_page():
    """扫描当前BOSS搜索结果页面，提取所有可见岗位，保存到数据库并返回。"""
    if not state.automation or state.automation.page is None:
        raise HTTPException(status_code=503, detail="浏览器未启动，请先到设置Tab点击「启动浏览器」")

    try:
        async with state.browser_sync_lock:
            jobs = await state.automation.scan_current_page()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"扫描失败: {e}")

    raw_found = len(jobs)
    jobs = _deduplicate_jobs(jobs)
    page_dup = raw_found - len(jobs)

    new_ids = []
    result_jobs = []
    db_existing = 0
    for j in jobs:
        aid, is_new = _save_job_with_dedup(j)
        if is_new and aid:
            new_ids.append(aid)
            result_jobs.append(_search_job_payload(j, get_application(aid)))
        elif not is_new:
            db_existing += 1

    print(f"[扫描] 页面 {raw_found} 条 → 去重 {len(jobs)} 条 → 新增 {len(new_ids)}，已有 {db_existing}")

    await ws_manager.broadcast(
        {
            "type": "scan_complete",
            "found": len(jobs),
            "new": len(new_ids),
            "existing": db_existing,
            "page_dup": page_dup,
        }
    )
    resp = {"jobs_found": len(jobs), "new_jobs": len(new_ids), "db_existing": db_existing, "page_duplicates": page_dup, "saved": len(new_ids), "jobs": result_jobs}
    return resp


@router.post("/api/jobs/scan-and-apply")
async def scan_and_apply(req: ScanAndApplyRequest = ScanAndApplyRequest()):
    """扫描当前页面全部岗位 → 一键批量投递。"""
    if not state.automation:
        raise HTTPException(status_code=503, detail="浏览器未启动")

    daily_limit = int(get_setting("daily_apply_limit", "15"))
    if get_today_application_count() >= daily_limit:
        raise HTTPException(status_code=429, detail="已达到今日投递上限")

    result = await state.automation.scan_and_apply_current_page(req.greeting)
    await ws_manager.broadcast(
        {
            "type": "scan_apply_complete",
            "scanned": result.get("scanned", 0),
            "applied": result.get("applied", 0),
        }
    )
    return result


@router.post("/api/jobs/analyze")
async def analyze_jd(req: AnalyzeRequest):
    """AI分析岗位JD，返回匹配度、关键技能、差距、建议。"""
    resume = get_setting("resume_summary", "")
    desc = req.description or ""
    title = req.job_title or ""
    company = req.company or ""

    if resume and len(resume.strip()) > 5:
        prompt = f"""你是求职辅导专家。分析以下岗位JD，对比求职者简历，输出JSON。

## 求职者简历
{resume}

## 岗位信息
- 公司: {company}
- 职位: {title}
- JD: {desc[:2000]}

## 输出格式（严格JSON）
{{
  "match_score": 85,
  "key_skills": ["Python", "LangChain", "RAG"],
  "gap": "缺少K8s部署经验",
  "advice": "建议强调Agent开发经验，问对方技术栈",
  "summary": "整体匹配度较高，注意补充部署相关经验"
}}"""
    else:
        # 无简历时只做岗位解读，不返回 match_score（避免误导为"匹配度"）
        prompt = f"""你是求职辅导专家。分析以下岗位JD，提取关键信息，输出JSON。

## 岗位信息
- 公司: {company}
- 职位: {title}
- JD: {desc[:2000]}

## 输出格式（严格JSON）
{{
  "match_score": null,
  "key_skills": ["Python", "LangChain", "RAG"],
  "gap": "",
  "advice": "",
  "summary": "该岗位的核心要求是..."
}}

注意：match_score 必须输出 null，不要猜测数值。summary 用一两句总结这个岗位的核心要求即可。"""

    raw = ""
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "interview"))
        from llm_client import llm_chat_deepseek, _load_ai_config

        cfg = _load_ai_config()
        if not cfg.get("api_key") or len(cfg["api_key"]) < 10:
            return {"error": "AI API Key 未配置，请先在设置页配置", "match_score": 0, "summary": "请检查AI配置"}

        raw = llm_chat_deepseek(
            [{"role": "user", "content": prompt}],
            system_prompt="你是求职辅导专家，输出严格JSON。",
            temperature=0.3,
        )

        import json

        cleaned = raw.strip()
        # 去掉 markdown 代码块包裹
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)
            cleaned = cleaned.strip()

        result = json.loads(cleaned)
        result["has_resume"] = bool(resume and len(resume.strip()) > 5)
        # AI 可能忽略指令仍返回数值，无简历时强制置空
        if not result["has_resume"]:
            result["match_score"] = None
        return result
    except json.JSONDecodeError:
        return {"error": "AI 返回的内容不是有效JSON，请重试", "match_score": 0, "summary": raw[:200] if raw else "无响应"}
    except Exception as e:
        err_msg = str(e)
        if "401" in err_msg or "403" in err_msg:
            return {"error": "AI API Key 无效，请在设置页重新配置", "match_score": 0, "summary": "认证失败"}
        if "timeout" in err_msg.lower() or "connect" in err_msg.lower():
            return {"error": "AI 服务连接超时，请检查网络或稍后重试", "match_score": 0, "summary": "网络异常"}
        return {"error": f"AI分析失败: {err_msg[:200]}", "match_score": 0, "summary": "请检查AI配置"}


# ══════════════════════════════════════
#  候选池
# ══════════════════════════════════════


@router.get("/api/shortlists")
def get_shortlists():
    return {"shortlists": list_shortlists()}


@router.post("/api/shortlists")
def add_shortlist(req: dict = {}):
    url = req.get("job_url", "")
    if not url:
        raise HTTPException(status_code=400, detail="缺少 job_url")
    if is_in_shortlist(url):
        return {"status": "already_exists"}
    sid = add_to_shortlist(
        url,
        req.get("title", ""),
        req.get("company", ""),
        req.get("salary", ""),
        req.get("city", ""),
        req.get("note", ""),
    )
    if sid:
        return {"status": "ok", "id": sid}
    return {"status": "duplicate"}


@router.delete("/api/shortlists/{sid}")
def remove_shortlist(sid: int):
    remove_from_shortlist(sid)
    return {"status": "ok"}
