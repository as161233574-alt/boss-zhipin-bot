"""岗位相关 API 路由。

包含岗位搜索、管理、投递、删除/回收站、候选池、去重等全部接口。
"""

import asyncio
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
    update_application_score,
    update_application_legitimacy,
    get_application_for_scoring,
    get_all_active_jobs_for_legitimacy,
    update_application_hr_activity,
    update_application_composite_score,
    get_auto_apply_candidates,
    log_auto_apply,
)
from ..models.settings import get_setting
from ..core import state
from ..services.scorer import score_job, check_legitimacy, score_hr_activity, score_job_quality, compute_composite_score
from ..services.scraper import BossScraper
from boss_replier import generate_greeting
from boss_state import (
    add_to_shortlist,
    remove_from_shortlist,
    list_shortlists,
    is_in_shortlist,
)

router = APIRouter()


# ══════════════════════════════════════
#  搜索意向匹配（自动投递前置过滤）
# ══════════════════════════════════════


def _matches_search_intent(job_title: str, description: str, search_keywords: str) -> bool:
    """检查岗位是否匹配搜索意向。不匹配的岗位不应自动投递。

    策略：从 search_keywords 提取核心技能词，岗位标题或 JD 中必须包含至少一个。
    """
    if not search_keywords or not search_keywords.strip():
        return True  # 无搜索关键词时不过滤

    title_lower = (job_title or "").lower()
    desc_lower = (description or "").lower()
    combined = title_lower + " " + desc_lower

    # 从搜索关键词中提取核心词
    # 先按逗号/顿号/空格分割多关键词（如 "AI Agent,大模型开发"）
    raw_keywords = [k.strip().lower() for k in re.split(r'[,，、\s]+', search_keywords) if k.strip()]
    # 过滤掉太短或太通用的词
    generic_words = {"实习", "实习生", "岗位", "招聘", "工程师", "开发", "应届", "兼职", "全职"}
    core_keywords = []
    for k in raw_keywords:
        if len(k) >= 2 and k not in generic_words:
            core_keywords.append(k)

    if not core_keywords:
        return True  # 没有有效核心词时不过滤

    # 核心关键词匹配：标题或 JD 中必须包含至少一个核心词
    for kw in core_keywords:
        if kw in combined:
            return True

    # 如果没有匹配，尝试拆分长关键词为子串再匹配
    # 例如 "linux运维实习生" → 检查 "linux" 和 "运维" 是否单独出现
    for kw in core_keywords:
        if len(kw) >= 4:
            # 拆分：英文单词 + 去掉通用后缀的中文片段
            parts = re.findall(r'[a-z]+', kw)
            # 去掉通用后缀再提取中文核心词
            cleaned = re.sub(r'实习|生|岗位|招聘|应届|兼职|全职', '', kw)
            cn_parts = re.findall(r'[一-鿿]{2,}', cleaned)
            parts.extend(cn_parts)
            for part in parts:
                if len(part) >= 2 and part not in generic_words and part in combined:
                    return True

    return False


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
    full = urljoin("https://www.zhipin.com", url)
    # 安全校验：只允许 zhipin.com 域名，防止 SSRF
    from urllib.parse import urlparse
    parsed = urlparse(full)
    if parsed.hostname and not parsed.hostname.endswith("zhipin.com"):
        return ""
    return full


def _deduplicate_jobs(jobs: list) -> list:
    """对爬取结果按 URL 去重，同一页面内相同 URL 只保留第一条。"""
    seen = set()
    result = []
    for j in jobs:
        key = j.get("url", "") or compute_dedup_key(j) or id(j)
        if key not in seen:
            seen.add(key)
            result.append(j)
    return result


def _save_job_with_dedup(job: dict) -> tuple:
    """保存岗位（URL 优先查重）。返回 (app_id, is_new)。is_new=True 表示首次入库。"""
    job["url"] = _normalize_job_url(job.get("url", ""))
    # 优先用 URL 查重（同一 URL = 同一岗位）
    if job["url"]:
        existing = get_application_by_url(job["url"])
        if existing:
            update_application_from_job(existing["id"], job)
            return existing["id"], False
    # 新记录（不再用 dedup_key 合并不同 URL 的岗位）
    aid = add_application(job)
    if aid:
        print(f"  [保存] 新岗位 ID={aid}: {job.get('title','')[:30]} → {job['url'][:60]}")
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
        "score": application.get("score"),
        "composite_score": application.get("composite_score"),
        "hr_activity_score": application.get("hr_activity_score"),
        "legitimacy": application.get("legitimacy", "unknown"),
    }


def _score_and_check_jobs(new_ids: list, all_jobs_for_legitimacy: list):
    """对新入库的岗位异步评分 + 同步合法性检测。返回成功评分数量。"""
    resume = get_setting("resume_summary", "")
    scored = 0
    for aid in new_ids:
        job = get_application_for_scoring(aid)
        if not job:
            continue
        # 合法性检测（纯规则，同步即可）
        leg = check_legitimacy(job, all_jobs_for_legitimacy)
        update_application_legitimacy(aid, leg["level"], leg["signals"])
        # 评分（LLM，同步调用）
        title = job.get("job_title", "")
        company = job.get("company", "")
        desc = job.get("description", "")
        salary = job.get("salary", "")
        try:
            result = score_job(title, company, desc, salary, resume)
            if result.get("score") is not None:
                update_application_score(aid, result["score"], result)
                scored += 1
                print(f"[评分] {title} @ {company} → {result['score']}分")
        except Exception as e:
            print(f"[评分] 岗位 {aid} 评分失败: {e}")
    print(f"[评分] 完成: {scored}/{len(new_ids)} 个岗位评分成功")
    return scored


def _detail_score_and_autoapply(new_ids: list, all_jobs_for_legitimacy: list):
    """三阶段流水线：详情抓取 → 评分 → 自动投递。返回评分成功数量。"""
    resume = get_setting("resume_summary", "")
    scored = 0

    # Phase 1: 详情抓取（需要浏览器，通过 asyncio 在调用方处理）
    # 详情抓取在 async wrapper 中完成，这里只做评分

    # Phase 2: 评分（综合多维度）
    for aid in new_ids:
        job = get_application_for_scoring(aid)
        if not job:
            continue

        # 2a. 合法性检测（纯规则）- 增加异常处理防止单条失败影响整批
        try:
            leg = check_legitimacy(job, all_jobs_for_legitimacy)
            update_application_legitimacy(aid, leg["level"], leg["signals"])
        except Exception as e:
            print(f"[评分] 岗位 {aid} 合法性检测失败: {e}")
            # 合法性检测失败时，使用安全默认值
            update_application_legitimacy(aid, "unknown", [{"type": "check_error", "detail": f"检测异常: {str(e)[:50]}"}])

        title = job.get("job_title", "")
        company = job.get("company", "")
        desc = job.get("description", "")
        salary = job.get("salary", "")
        hr_name = job.get("hr_name", "")
        hr_activity = job.get("hr_activity", "")

        # 2b. 简历匹配评分（LLM）
        cv_score = None
        try:
            result = score_job(title, company, desc, salary, resume)
            cv_score = result.get("score")
            if cv_score is not None:
                update_application_score(aid, cv_score, result)
                scored += 1
            else:
                # LLM返回None时，使用保守默认分数
                cv_score = 30
                result = {"score": 30, "key_skills": [], "gap": "", "advice": "", "summary": "LLM评分失败，使用保守默认分", "has_resume": bool(resume)}
                update_application_score(aid, cv_score, result)
                print(f"[评分] 岗位 {aid} LLM返回None，使用保守默认分30")
        except Exception as e:
            print(f"[评分] 岗位 {aid} CV匹配评分失败: {e}")
            # 异常时使用保守默认分数
            cv_score = 30
            result = {"score": 30, "key_skills": [], "gap": "", "advice": "", "summary": f"评分异常: {str(e)[:50]}", "has_resume": bool(resume)}
            update_application_score(aid, cv_score, result)

        # 2c. 招聘信息质量评分（LLM）
        quality_score = None
        try:
            q_result = score_job_quality(title, company, desc, salary, hr_name)
            quality_score = q_result.get("quality_score")
            if quality_score is None or quality_score == 0:
                quality_score = 40  # LLM返回None或0时使用保守默认分
                print(f"[评分] 岗位 {aid} 质量评分返回{q_result.get('quality_score')}，使用保守默认分40")
        except Exception as e:
            print(f"[评分] 岗位 {aid} 质量评分失败: {e}")
            quality_score = 40  # 异常时使用保守默认分

        # 2d. HR活跃度评分（纯规则）
        hr_score = score_hr_activity(hr_activity)
        update_application_hr_activity(aid, hr_score)

        # 2e. 综合评分
        composite = compute_composite_score(cv_score, quality_score, hr_score)
        update_application_composite_score(aid, composite)

        print(f"[评分] {title} @ {company} → CV={cv_score} 质量={quality_score} HR={hr_score} 综合={composite}")

    print(f"[评分] 完成: {scored}/{len(new_ids)} 个岗位评分成功")
    return scored


async def _fetch_details_and_score(new_ids: list, all_jobs_for_legitimacy: list):
    """Phase 1: 详情抓取 → Phase 2: 评分 → Phase 3: 自动投递。

    返回: (scored_count, applied_count) 元组
    """
    import time
    from ..services.scraper import BossScraper

    # 检查是否启用HR活跃度过滤
    filter_inactive = get_setting("filter_inactive_hr", "true") == "true"

    # Phase 1: 详情抓取 + HR活跃度过滤
    print(f"[详情] 开始抓取 {len(new_ids)} 个岗位详情...")
    filtered_ids = []  # 通过活跃度过滤的岗位ID
    filtered_count = 0

    for aid in new_ids:
        job = get_application_for_scoring(aid)
        if not job or not job.get("job_url"):
            continue
        try:
            # 先获取锁（不包含在 wait_for 内部，避免取消时锁泄漏）
            await state.browser_sync_lock.acquire()
            try:
                # 在持有锁的情况下执行抓取，带超时保护
                detail = await asyncio.wait_for(
                    state.automation.fetch_detail(job["job_url"]),
                    timeout=30
                )
            finally:
                # 确保锁一定被释放，即使超时也能执行
                state.browser_sync_lock.release()
            if detail:
                updates = {}
                if detail.get("description") and not job.get("description"):
                    updates["description"] = detail["description"]
                if detail.get("hr_name") and not job.get("hr_name"):
                    updates["hr_name"] = detail["hr_name"]
                if detail.get("hr_title") and not job.get("hr_title"):
                    updates["hr_title"] = detail["hr_title"]
                if detail.get("hr_activity"):
                    updates["hr_activity"] = detail["hr_activity"]
                if updates:
                    # 直接用 SQL 更新详情字段
                    db = get_db()
                    sets = ", ".join(f"{k}=?" for k in updates)
                    vals = list(updates.values()) + [aid]
                    db.execute(f"UPDATE applications SET {sets}, updated_at=CURRENT_TIMESTAMP WHERE id=?", vals)
                    db.commit()

                # HR活跃度过滤：3天以上不活跃的岗位标记为"死岗位"
                hr_activity = detail.get("hr_activity", "")
                if filter_inactive and BossScraper.is_hr_inactive(hr_activity):
                    # 软删除不活跃岗位（不展示给用户）
                    db = get_db()
                    db.execute(
                        "UPDATE applications SET deleted_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                        (aid,)
                    )
                    db.commit()
                    filtered_count += 1
                    print(f"[过滤] {job.get('job_title', '')} @ {job.get('company', '')} → HR不活跃({hr_activity})，已过滤")
                    continue

                filtered_ids.append(aid)
                print(f"[详情] {job.get('job_title', '')} → 抓取成功 (HR:{hr_activity})")
            else:
                # 无法获取详情的岗位保留
                filtered_ids.append(aid)
            await asyncio.sleep(3)  # 避免请求过快
        except Exception as e:
            filtered_ids.append(aid)
            print(f"[详情] 岗位 {aid} 详情抓取失败: {e}")

    if filtered_count > 0:
        print(f"[过滤] 共过滤 {filtered_count} 个不活跃岗位（HR超过3天未活跃）")

    if not filtered_ids:
        print("[评分] 所有岗位均被过滤，跳过评分")
        return 0, 0

    # Phase 2: 评分（在线程池中执行，不阻塞事件循环）
    scored = await asyncio.to_thread(_detail_score_and_autoapply, filtered_ids, all_jobs_for_legitimacy)

    # Phase 3: 自动投递
    applied = 0
    auto_apply_enabled = get_setting("auto_apply_enabled", "false") == "true"
    if auto_apply_enabled and scored > 0:
        applied = await _execute_auto_apply()

    return scored, applied


async def _execute_auto_apply():
    """执行自动投递：查询高分岗位 → 逐个投递。

    返回: 成功投递数量
    """
    threshold = int(get_setting("auto_apply_threshold", "73"))
    hr_active_required = get_setting("auto_apply_hr_active_required", "true") == "true"
    daily_limit = int(get_setting("daily_apply_limit", "15"))
    search_keywords = get_setting("search_keywords", "")

    today_count = get_today_application_count()
    if today_count >= daily_limit:
        print(f"[自动投递] 今日已投递 {today_count} 份，达到上限 {daily_limit}")
        return 0

    candidates = get_auto_apply_candidates(threshold, hr_active_required)
    if not candidates:
        print(f"[自动投递] 无符合条件的岗位（阈值={threshold}, HR活跃要求={hr_active_required}）")
        return 0

    # 意向匹配过滤：排除与搜索关键词不匹配的岗位
    intent_matched = []
    for job in candidates:
        if _matches_search_intent(job.get("job_title", ""), job.get("description", ""), search_keywords):
            intent_matched.append(job)
        else:
            print(f"[自动投递] 意向不匹配，跳过: {job.get('job_title', '')} @ {job.get('company', '')}")
    candidates = intent_matched
    if not candidates:
        print(f"[自动投递] 意向匹配后无候选岗位")
        return 0

    remaining = daily_limit - today_count
    to_apply = candidates[:remaining]
    print(f"[自动投递] 找到 {len(candidates)} 个候选，本次投递 {len(to_apply)} 个")

    applied = 0
    import random
    for job in to_apply:
        app_id = job["id"]
        title = job.get("job_title", "")
        company = job.get("company", "")
        url = job.get("job_url", "")

        try:
            greeting = get_setting("greeting_template", "").replace("{job_title}", title)
            if not greeting:
                greeting = f"您好！看到贵司在招{title}，很感兴趣，希望有机会详细了解一下。"

            async with state.browser_sync_lock:
                result = await state.automation.apply_to_job(url, greeting)

            if result.get("success"):
                update_application_status(app_id, "applied", greeting)
                log_auto_apply(app_id, job.get("composite_score", 0), job.get("hr_activity_score", 0), "success")
                applied += 1
                print(f"[自动投递] {title} @ {company} → 投递成功")

                await ws_manager.broadcast({
                    "type": "auto_apply_complete",
                    "job_id": app_id,
                    "title": title,
                    "company": company,
                    "success": True,
                })
            else:
                msg = result.get("message", "未知原因")
                log_auto_apply(app_id, job.get("composite_score", 0), job.get("hr_activity_score", 0), f"failed: {msg}")
                print(f"[自动投递] {title} @ {company} → 投递失败: {msg}")

            # 随机延迟 30-90 秒
            delay = random.uniform(30, 90)
            await asyncio.sleep(delay)

        except Exception as e:
            log_auto_apply(app_id, job.get("composite_score", 0), job.get("hr_activity_score", 0), f"error: {e}")
            print(f"[自动投递] {title} @ {company} → 异常: {e}")

    print(f"[自动投递] 批次完成: {applied}/{len(to_apply)} 投递成功")
    await ws_manager.broadcast({
        "type": "auto_apply_batch_complete",
        "total": len(to_apply),
        "applied": applied,
    })

    return applied


# ══════════════════════════════════════
#  Pydantic Models
# ══════════════════════════════════════


class SearchRequest(BaseModel):
    keyword: str = "AI Agent"
    city: str = ""
    welfare: Optional[str] = None
    limit: int = 60
    max_pages: int = 10


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
def list_jobs(status: Optional[str] = None, limit: int = 100, sort_by: str = "composite_score"):
    jobs = list_applications(status, limit, sort_by=sort_by)
    return {"jobs": jobs, "total": len(jobs)}


@router.post("/api/jobs/search")
async def search_jobs(req: SearchRequest):
    if not state.automation or state.automation.page is None:
        raise HTTPException(status_code=503, detail="浏览器未启动，请先到设置Tab点击「启动浏览器」")
    # 检查登录状态
    if not await state.automation.is_logged_in_page():
        raise HTTPException(status_code=401, detail="未登录BOSS直聘，请先在浏览器中扫码登录")
    was_paused = chat_monitor.paused
    chat_monitor.paused = True
    try:
        # Phase 1: 搜索（持有锁，总超时120秒）
        city_code = CITY_MAP.get(req.city or get_setting("default_city", "全国"), "100010000")
        try:
            async def _search_with_lock():
                await state.browser_sync_lock.acquire()
                try:
                    return await state.automation.search(req.keyword, city_code, max_pages=req.max_pages)
                finally:
                    state.browser_sync_lock.release()

            jobs = await asyncio.wait_for(_search_with_lock(), timeout=120)
            print(f"[搜索] 搜索完成: 找到 {len(jobs)} 条岗位")
        except asyncio.TimeoutError:
            raise HTTPException(status_code=500, detail="搜索超时(120s)，请重试")
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

        # Phase 2: 逐个抓取详情 + 评分（每个单独获取锁）
        scored = 0
        filtered_count = 0
        if new_ids:
            filter_inactive = get_setting("filter_inactive_hr", "true") == "true"
            resume = get_setting("resume_summary", "")
            all_jobs = get_all_active_jobs_for_legitimacy()

            for idx, aid in enumerate(new_ids):
                job = get_application_for_scoring(aid)
                if not job or not job.get("job_url"):
                    continue

                print(f"[详情] ({idx+1}/{len(new_ids)}) 开始处理: {job.get('job_title', '')} → {job.get('job_url', '')}")

                # 1. 抓取详情（单独获取锁，有超时）
                try:
                    # 先获取锁，避免在 wait_for 内部获取导致锁泄漏
                    await state.browser_sync_lock.acquire()
                    try:
                        detail = await asyncio.wait_for(
                            state.automation.fetch_detail(job["job_url"]),
                            timeout=20
                        )
                    finally:
                        state.browser_sync_lock.release()

                    if detail:
                        updates = {}
                        if detail.get("description") and not job.get("description"):
                            updates["description"] = detail["description"]
                        if detail.get("hr_name") and not job.get("hr_name"):
                            updates["hr_name"] = detail["hr_name"]
                        if detail.get("hr_title") and not job.get("hr_title"):
                            updates["hr_title"] = detail["hr_title"]
                        if detail.get("hr_activity"):
                            updates["hr_activity"] = detail["hr_activity"]
                        if updates:
                            db = get_db()
                            sets = ", ".join(f"{k}=?" for k in updates)
                            vals = list(updates.values()) + [aid]
                            db.execute(f"UPDATE applications SET {sets}, updated_at=CURRENT_TIMESTAMP WHERE id=?", vals)
                            db.commit()

                        # 2. HR活跃度过滤
                        hr_activity = detail.get("hr_activity", "")
                        if filter_inactive and BossScraper.is_hr_inactive(hr_activity):
                            db = get_db()
                            db.execute("UPDATE applications SET deleted_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP WHERE id=?", (aid,))
                            db.commit()
                            filtered_count += 1
                            print(f"[过滤] {job.get('job_title', '')} → HR不活跃({hr_activity})")
                            continue
                except asyncio.TimeoutError:
                    print(f"[详情] 岗位 {aid} 超时(30s)，跳过")
                except Exception as e:
                    print(f"[详情] 岗位 {aid} 抓取失败: {e}")

                # 3. 重新从数据库读取（详情抓取可能更新了 description/hr_name/hr_activity）
                job = get_application_for_scoring(aid)
                if not job:
                    continue

                # 4. 合法性检测
                leg = check_legitimacy(job, all_jobs)
                update_application_legitimacy(aid, leg["level"], leg["signals"])

                # 5. 综合评分（LLM 调用放到线程池，不阻塞事件循环）
                title = job.get("job_title", "")
                company = job.get("company", "")
                desc = job.get("description", "")
                salary = job.get("salary", "")
                hr_name = job.get("hr_name", "")
                hr_activity = job.get("hr_activity", "")

                cv_score = None
                try:
                    result = await asyncio.to_thread(score_job, title, company, desc, salary, resume)
                    cv_score = result.get("score")
                    if cv_score is not None:
                        update_application_score(aid, cv_score, result)
                        scored += 1
                except Exception as e:
                    print(f"[评分] CV评分失败: {e}")

                quality_score = None
                try:
                    q_result = await asyncio.to_thread(score_job_quality, title, company, desc, salary, hr_name)
                    quality_score = q_result.get("quality_score")
                    if quality_score is None or quality_score == 0:
                        quality_score = 40
                except Exception:
                    quality_score = 40

                hr_score = score_hr_activity(hr_activity)
                update_application_hr_activity(aid, hr_score)

                composite = compute_composite_score(cv_score, quality_score, hr_score)
                update_application_composite_score(aid, composite)

                print(f"[评分] ({idx+1}/{len(new_ids)}) {title} → 综合:{composite} (CV:{cv_score} 质量:{quality_score} HR:{hr_score})")

                # 岗位间延迟（避免触发反爬）
                await asyncio.sleep(2)

        # 重新获取结果（包含评分数据）
        result_jobs = []
        for j in jobs:
            existing = get_application_by_dedup_key(compute_dedup_key(j))
            if existing:
                if not existing.get("deleted_at"):
                    result_jobs.append(_search_job_payload(j, existing))

        if filtered_count > 0:
            print(f"[过滤] 共过滤 {filtered_count} 个不活跃岗位")
        print(f"[搜索] 完成: {scored}/{len(new_ids)} 评分成功")

        await ws_manager.broadcast(
            {
                "type": "search_complete",
                "keyword": req.keyword,
                "city": req.city,
                "found": len(jobs),
                "new": len(new_ids),
                "existing": db_existing,
                "page_dup": page_dup,
                "scored": scored,
                "filtered": filtered_count,
            }
        )
        resp = {"jobs_found": len(jobs), "new_jobs": len(new_ids), "db_existing": db_existing, "page_duplicates": page_dup, "saved": len(new_ids), "scored": scored, "filtered": filtered_count, "jobs": result_jobs}
        return resp
    except HTTPException:
        raise
    except Exception as e:
        print(f"[搜索] 未预期的错误: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"搜索过程出错: {e}")
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


@router.post("/api/jobs/refetch")
async def refetch_job_details():
    """重新抓取所有缺少详情或描述不完整的岗位。"""
    if not state.automation or state.automation.page is None:
        raise HTTPException(status_code=503, detail="浏览器未启动")
    # 检查登录状态
    if not await state.automation.is_logged_in_page():
        raise HTTPException(status_code=401, detail="未登录BOSS直聘，请先在浏览器中扫码登录")

    # 获取缺少详情的岗位（描述为空或描述中包含HR活跃信息的）
    db = get_db()
    rows = db.execute(
        """SELECT id, job_title, job_url FROM applications
           WHERE deleted_at IS NULL
           AND job_url IS NOT NULL AND job_url != ''
           AND (description IS NULL OR description = ''
                OR description LIKE '%刚刚活跃%'
                OR description LIKE '%今日活跃%'
                OR description LIKE '%日内活跃%'
                OR description LIKE '%本周活跃%'
                OR description LIKE '%本月活跃%'
                OR description LIKE '%半年前活跃%')
           ORDER BY id DESC LIMIT 50"""
    ).fetchall()

    if not rows:
        return {"message": "没有需要重新抓取的岗位", "count": 0}

    refetched = 0
    failed = 0
    for row in rows:
        aid = row["id"]
        url = row["job_url"]
        title = row["job_title"]

        try:
            # 获取锁并抓取详情（先获取锁，避免锁泄漏）
            await state.browser_sync_lock.acquire()
            try:
                detail = await asyncio.wait_for(
                    state.automation.fetch_detail(url),
                    timeout=25
                )
            finally:
                state.browser_sync_lock.release()

            if detail and (detail.get("description") or detail.get("hr_name")):
                updates = {}
                if detail.get("description"):
                    updates["description"] = detail["description"]
                if detail.get("hr_name"):
                    updates["hr_name"] = detail["hr_name"]
                if detail.get("hr_title"):
                    updates["hr_title"] = detail["hr_title"]
                if detail.get("hr_activity"):
                    updates["hr_activity"] = detail["hr_activity"]

                if updates:
                    sets = ", ".join(f"{k}=?" for k in updates)
                    vals = list(updates.values()) + [aid]
                    db.execute(f"UPDATE applications SET {sets}, updated_at=CURRENT_TIMESTAMP WHERE id=?", vals)
                    db.commit()

                    # 更新HR活跃度分数
                    hr_activity = detail.get("hr_activity", "")
                    hr_score = score_hr_activity(hr_activity)
                    update_application_hr_activity(aid, hr_score)

                    refetched += 1
                    print(f"[重新抓取] {title} → 描述:{len(detail.get('description',''))}字 HR:{detail.get('hr_name','')}")
            else:
                failed += 1
                print(f"[重新抓取] {title} → 未获取到详情")

        except asyncio.TimeoutError:
            failed += 1
            print(f"[重新抓取] {title} → 超时")
        except Exception as e:
            failed += 1
            print(f"[重新抓取] {title} → 失败: {e}")

        # 岗位间延迟
        await asyncio.sleep(2)

    return {"message": f"重新抓取完成: {refetched}成功, {failed}失败", "refetched": refetched, "failed": failed}


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


@router.post("/api/jobs/{job_id}/score")
async def score_single_job(job_id: int):
    """手动重新评分单个岗位。"""
    job = get_application_for_scoring(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="岗位不存在")
    resume = get_setting("resume_summary", "")
    title = job.get("job_title", "")
    company = job.get("company", "")
    desc = job.get("description", "")
    salary = job.get("salary", "")
    hr_name = job.get("hr_name", "")
    hr_activity = job.get("hr_activity", "")

    # CV匹配评分
    cv_result = await asyncio.to_thread(score_job, title, company, desc, salary, resume)
    cv_score = cv_result.get("score")
    if cv_score is None:
        cv_score = 30
        cv_result = {"score": 30, "key_skills": [], "gap": "", "advice": "", "summary": "LLM评分失败，使用保守默认分", "has_resume": bool(resume)}
    update_application_score(job_id, cv_score, cv_result)

    # 招聘质量评分
    quality_result = await asyncio.to_thread(score_job_quality, title, company, desc, salary, hr_name)
    quality_score = quality_result.get("quality_score")
    if quality_score is None or quality_score == 0:
        quality_score = 40

    # HR活跃度评分
    hr_score = score_hr_activity(hr_activity)
    update_application_hr_activity(job_id, hr_score)

    # 综合评分
    composite = compute_composite_score(cv_score, quality_score, hr_score)
    update_application_composite_score(job_id, composite)

    # 合法性检测
    all_jobs = get_all_active_jobs_for_legitimacy()
    leg = check_legitimacy(job, all_jobs)
    update_application_legitimacy(job_id, leg["level"], leg["signals"])

    return {"cv_score": cv_score, "quality_score": quality_score, "hr_score": hr_score, "composite": composite, "legitimacy": leg}


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
    urls = req.job_urls[: max(0, remaining)]

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

    # 异步详情抓取 + 评分 + 自动投递（不阻塞返回）
    if new_ids:
        all_jobs = get_all_active_jobs_for_legitimacy()

        async def _pipeline_bg():
            scored = await _fetch_details_and_score(new_ids, all_jobs)
            if scored > 0:
                await ws_manager.broadcast({"type": "score_complete", "count": scored})

        task = asyncio.create_task(_pipeline_bg())
        state.background_tasks.append(task)
        task.add_done_callback(lambda t: state.background_tasks.remove(t) if t in state.background_tasks else None)

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
#  跟进节奏
# ══════════════════════════════════════


@router.get("/api/followups")
def list_followups():
    """返回超期跟进列表和统计信息。"""
    from ..models.followup import get_overdue_followups, get_followup_stats
    return {
        "overdue": get_overdue_followups(),
        "stats": get_followup_stats(),
    }


@router.post("/api/followups/{app_id}/done")
async def mark_followup_done(app_id: int):
    """标记已跟进。"""
    from ..models.followup import record_followup
    ok = record_followup(app_id, "manual")
    if not ok:
        raise HTTPException(status_code=404, detail="岗位不存在")
    await ws_manager.broadcast({"type": "followup_done", "app_id": app_id})
    return {"status": "ok"}


# ══════════════════════════════════════
#  候选池
# ══════════════════════════════════════


@router.get("/api/shortlists")
def get_shortlists():
    return {"shortlists": list_shortlists()}


@router.post("/api/shortlists")
def add_shortlist(req: dict = None):
    url = (req or {}).get("job_url", "")
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


# ══════════════════════════════════════
#  自动投递日志
# ══════════════════════════════════════


@router.get("/api/auto-apply-logs")
def get_auto_apply_logs_api(limit: int = 50):
    """获取自动投递日志。"""
    from ..models.application import get_auto_apply_logs
    return {"logs": get_auto_apply_logs(limit)}


@router.post("/api/auto-apply/trigger")
async def trigger_auto_apply():
    """手动触发自动投递。"""
    if not state.automation or state.automation.page is None:
        raise HTTPException(status_code=503, detail="浏览器未启动")
    await _execute_auto_apply()
    return {"status": "ok"}
