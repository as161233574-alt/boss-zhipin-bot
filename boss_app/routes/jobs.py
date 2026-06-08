"""岗位相关 API 路由。

包含岗位搜索、管理、投递、删除/回收站、候选池、去重等全部接口。
"""

import asyncio
import json
import random
import re
import sqlite3
import sys
from pathlib import Path
from typing import Optional, List
from urllib.parse import urljoin

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

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
    update_application_fields,
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
from ..core.database import get_active_resume
from ..services.scorer import check_legitimacy, score_hr_activity, compute_composite_score, score_job_combined


def _get_resume_summary() -> str:
    """获取当前激活简历的摘要，如果没有则回退到旧的 settings。"""
    active = get_active_resume()
    if active and active.get("summary"):
        return active["summary"]
    return get_setting("resume_summary", "")
from ..services.scraper import BossScraper
from ..services.automation import check_job_match
from ..config import CITY_MAP
from boss_app.services.replier import generate_greeting
from boss_app.models.shortlist import (
    add_to_shortlist,
    remove_from_shortlist,
    list_shortlists,
    is_in_shortlist,
)

router = APIRouter()


def _safe_remove_task(task: asyncio.Task) -> None:
    try:
        state.background_tasks.remove(task)
    except ValueError:
        pass


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


def _save_job_with_dedup(job: dict, overrides: dict = None) -> tuple:
    """保存岗位（URL 优先查重）。返回 (app_id, is_new, app_dict)。

    保存前会检查岗位是否符合用户的经验要求和期望薪资条件。
    不符合条件的岗位不会保存到数据库。
    """
    job["url"] = _normalize_job_url(job.get("url", ""))

    # 检查岗位是否符合经验要求和期望薪资条件
    is_match, reason = check_job_match(job, overrides)
    if not is_match:
        print(f"  [跳过] {reason}: {job.get('title','')[:30]} | {job.get('salary','')} | {job.get('experience','')}")
        return 0, False, None

    # 优先用 URL 查重（同一 URL = 同一岗位）
    if job["url"]:
        existing = get_application_by_url(job["url"])
        if existing:
            update_application_from_job(existing["id"], job)
            return existing["id"], False, existing
    # 新记录（不再用 dedup_key 合并不同 URL 的岗位）
    aid = add_application(job)
    if aid:
        print(f"  [保存] 新岗位 ID={aid}: {job.get('title','')[:30]} → {job['url'][:60]}")
        # 构造 synthetic dict 避免额外 SELECT
        app_dict = {
            "id": aid, "job_title": job.get("title", ""), "company": job.get("company", ""),
            "salary": job.get("salary", ""), "job_url": job.get("url", ""), "city": job.get("city", ""),
            "experience": job.get("experience", ""), "education": job.get("education", ""),
            "hr_name": job.get("hr_name", ""), "hr_title": job.get("hr_title", ""),
            "description": job.get("description", ""), "status": "pending",
            "score": None, "composite_score": None, "hr_activity_score": None, "legitimacy": "unknown",
        }
        return aid, True, app_dict
    return 0, False, None


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


def _detail_score_and_autoapply(new_ids: list, all_jobs_for_legitimacy: list, job_cache: dict = None):
    """三阶段流水线：合法性检测 → 合并评分(并行) → 自动投递。返回评分成功数量。"""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    resume = _get_resume_summary()
    scored = 0

    # Phase 1: 合法性检测（纯规则，快，串行即可）
    jobs_data = []
    for aid in new_ids:
        job = (job_cache or {}).get(aid) or get_application_for_scoring(aid)
        if not job:
            continue
        try:
            leg = check_legitimacy(job, all_jobs_for_legitimacy)
            update_application_legitimacy(aid, leg["level"], leg["signals"])
        except Exception as e:
            print(f"[评分] 岗位 {aid} 合法性检测失败: {e}")
            update_application_legitimacy(aid, "unknown", [{"type": "check_error", "detail": f"检测异常: {str(e)[:50]}"}])
        jobs_data.append((aid, job))

    # Phase 2: 合并评分（LLM，并行，每个岗位只需 1 次 LLM 调用）
    def _score_one(aid, job):
        title = job.get("job_title", "")
        company = job.get("company", "")
        desc = job.get("description", "")
        salary = job.get("salary", "")
        hr_name = job.get("hr_name", "")
        hr_activity = job.get("hr_activity", "")

        try:
            result = score_job_combined(title, company, desc, salary, hr_name, resume)
            cv_score = result.get("cv_score")
            quality_score = result.get("quality_score")
            if cv_score is None:
                cv_score = 30
            if quality_score is None:
                quality_score = 40
            update_application_score(aid, cv_score, result)
        except Exception as e:
            print(f"[评分] 岗位 {aid} 评分失败: {e}")
            cv_score = 30
            quality_score = 40
            result = {"summary": f"评分异常: {str(e)[:50]}"}
            update_application_score(aid, cv_score, result)

        hr_score = score_hr_activity(hr_activity)
        update_application_hr_activity(aid, hr_score)

        composite = compute_composite_score(cv_score, quality_score, hr_score)
        update_application_composite_score(aid, composite)

        print(f"[评分] {title} @ {company} → CV={cv_score} 质量={quality_score} HR={hr_score} 综合={composite}")
        return 1 if cv_score != 30 else 0

    # 最多 3 个岗位并行评分
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(_score_one, aid, job): aid for aid, job in jobs_data}
        for future in as_completed(futures):
            try:
                scored += future.result()
            except Exception as e:
                print(f"[评分] 并行评分异常: {e}")

    print(f"[评分] 完成: {scored}/{len(new_ids)} 个岗位评分成功")
    return scored


async def _fetch_details_and_score(new_ids: list, all_jobs_for_legitimacy: list):
    """Phase 1: 详情抓取 → Phase 2: 评分 → Phase 3: 自动投递。

    返回: (scored_count, applied_count) 元组
    """
    from ..services.scraper import BossScraper

    # 检查是否启用HR活跃度过滤
    filter_inactive = get_setting("filter_inactive_hr", "true") == "true"

    # Phase 1: 详情抓取 + HR活跃度过滤
    print(f"[详情] 开始抓取 {len(new_ids)} 个岗位详情...")
    filtered_ids = []  # 通过活跃度过滤的岗位ID
    filtered_count = 0
    _detail_cache = {}  # aid -> job dict, 传递给评分阶段避免重复查询

    for aid in new_ids:
        job = get_application_for_scoring(aid)
        _detail_cache[aid] = job
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
                    update_application_fields(aid, updates)

                # HR活跃度过滤：3天以上不活跃的岗位标记为"死岗位"
                hr_activity = detail.get("hr_activity", "")
                if filter_inactive and BossScraper.is_hr_inactive(hr_activity):
                    soft_delete_application(aid)
                    filtered_count += 1
                    print(f"[过滤] {job.get('job_title', '')} @ {job.get('company', '')} → HR不活跃({hr_activity})，已过滤")
                    continue

                filtered_ids.append(aid)
                print(f"[详情] {job.get('job_title', '')} → 抓取成功 (HR:{hr_activity})")
            else:
                # 无法获取详情的岗位保留
                filtered_ids.append(aid)
            await asyncio.sleep(1.5)  # 避免请求过快
        except Exception as e:
            filtered_ids.append(aid)
            print(f"[详情] 岗位 {aid} 详情抓取失败: {e}")

    if filtered_count > 0:
        print(f"[过滤] 共过滤 {filtered_count} 个不活跃岗位（HR超过3天未活跃）")

    if not filtered_ids:
        print("[评分] 所有岗位均被过滤，跳过评分")
        return 0, 0

    # Phase 2: 评分（在线程池中执行，不阻塞事件循环）
    scored = await asyncio.to_thread(_detail_score_and_autoapply, filtered_ids, all_jobs_for_legitimacy, _detail_cache)

    # Phase 3: 自动投递
    applied = 0
    auto_apply_enabled = get_setting("auto_apply_enabled", "false") == "true"
    if auto_apply_enabled and scored > 0:
        applied = await _execute_auto_apply()

    return scored, applied


_auto_apply_running = False


async def _execute_auto_apply():
    """执行自动投递：查询高分岗位 → 逐个投递。

    返回: 成功投递数量
    """
    global _auto_apply_running
    if _auto_apply_running:
        print("[自动投递] 已有智能投递任务在运行，跳过")
        return 0
    _auto_apply_running = True

    threshold = int(get_setting("auto_apply_threshold", "80"))
    hr_active_required = get_setting("auto_apply_hr_active_required", "true") == "true"
    daily_limit = int(get_setting("daily_apply_limit", "15"))
    search_keywords = get_setting("search_keywords", "")

    today_count = get_today_application_count()
    if today_count >= daily_limit:
        msg = f"今日已投递 {today_count} 份，达到上限 {daily_limit}"
        print(f"[自动投递] {msg}")
        await ws_manager.broadcast({"type": "auto_apply_batch_complete", "total": 0, "applied": 0, "message": msg})
        return 0

    candidates = get_auto_apply_candidates(threshold, hr_active_required)
    if not candidates:
        msg = f"无符合条件的岗位（综合分>={threshold}, HR活跃要求={hr_active_required}）。请先搜索岗位并等待评分完成。"
        print(f"[自动投递] {msg}")
        await ws_manager.broadcast({"type": "auto_apply_batch_complete", "total": 0, "applied": 0, "message": msg})
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
        msg = "意向匹配后无候选岗位，请检查搜索关键词设置"
        print(f"[自动投递] {msg}")
        await ws_manager.broadcast({"type": "auto_apply_batch_complete", "total": 0, "applied": 0, "message": msg})
        return 0

    remaining = daily_limit - today_count
    to_apply = candidates[:remaining]
    print(f"[自动投递] 找到 {len(candidates)} 个候选，本次投递 {len(to_apply)} 个")

    # 暂停聊天监控，防止监控循环抢夺浏览器锁导致页面被导航走
    chat_monitor.pause()

    try:
        applied = 0
        for i, job in enumerate(to_apply):
            app_id = job["id"]
            title = job.get("job_title", "")
            company = job.get("company", "")
            url = job.get("job_url", "")

            try:
                greeting = get_setting("greeting_template", "").replace("{job_title}", title)
                if not greeting:
                    greeting = f"您好！看到贵司在招{title}，很感兴趣，希望有机会详细了解一下。"

                # 构造 job_data 用于薪资/经验过滤
                job_data = {
                    "title": title,
                    "job_title": title,
                    "company": company,
                    "salary": job.get("salary", ""),
                    "experience": job.get("experience", ""),
                    "education": job.get("education", ""),
                    "description": (job.get("description") or "")[:500],
                }

                print(f"[自动投递] ({i+1}/{len(to_apply)}) 开始投递: {title} @ {company}")

                async with state.browser_sync_lock:
                    # 单个岗位投递超时 120 秒，防止卡死
                    try:
                        result = await asyncio.wait_for(
                            state.automation.apply_to_job(url, greeting, job_data),
                            timeout=120,
                        )
                    except asyncio.TimeoutError:
                        print(f"[自动投递] {title} @ {company} → 投递超时(120s)")
                        log_auto_apply(app_id, job.get("composite_score", 0), job.get("hr_activity_score", 0), "timeout")
                        continue

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
                elif result.get("skipped"):
                    msg = result.get("message", "已跳过")
                    log_auto_apply(app_id, job.get("composite_score", 0), job.get("hr_activity_score", 0), f"skipped: {msg}")
                    print(f"[自动投递] {title} @ {company} → 跳过: {msg}")
                else:
                    msg = result.get("message", "未知原因")
                    log_auto_apply(app_id, job.get("composite_score", 0), job.get("hr_activity_score", 0), f"failed: {msg}")
                    print(f"[自动投递] {title} @ {company} → 投递失败: {msg}")

                # 随机延迟 30-90 秒
                if i < len(to_apply) - 1:
                    delay = random.uniform(30, 90)
                    print(f"[自动投递] 等待 {delay:.0f}s 后投递下一条...")
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
    finally:
        chat_monitor.resume()
        _auto_apply_running = False


# ══════════════════════════════════════
#  Pydantic Models
# ══════════════════════════════════════


class SearchRequest(BaseModel):
    keyword: str = "AI Agent"
    city: str = ""
    welfare: Optional[str] = None
    limit: int = Field(default=60, ge=1, le=200)
    max_pages: int = Field(default=10, ge=1, le=30)
    experience: Optional[str] = None
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None


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
    job_ids: List[int] = Field(..., min_length=1, max_length=500)


class RestoreRequest(BaseModel):
    job_ids: List[int] = Field(..., min_length=1, max_length=500)


class ClearRequest(BaseModel):
    confirm: str = ""


# ══════════════════════════════════════
#  岗位列表 & 搜索
# ══════════════════════════════════════


@router.get("/api/jobs")
def list_jobs(status: Optional[str] = None, limit: int = 100, sort_by: str = "composite_score"):
    jobs = list_applications(status, limit, sort_by=sort_by)
    return {"jobs": jobs, "total": len(jobs)}


async def _background_score_and_apply(new_ids, keyword, city, found, db_existing, page_dup):
    """后台评分：搜索完成后异步执行详情抓取+评分，不阻塞搜索响应。"""
    from concurrent.futures import ThreadPoolExecutor
    scored = 0
    filtered_count = 0
    try:
        filter_inactive = get_setting("filter_inactive_hr", "true") == "true"
        resume = _get_resume_summary()
        all_jobs = get_all_active_jobs_for_legitimacy()

        # Phase 1: 串行抓取详情（需要浏览器锁）
        _scoring_cache = {}  # aid -> job dict, 避免重复 SELECT
        for idx, aid in enumerate(new_ids):
            job = get_application_for_scoring(aid)
            _scoring_cache[aid] = job
            if not job or not job.get("job_url"):
                continue

            print(f"[详情] ({idx+1}/{len(new_ids)}) 开始处理: {job.get('job_title', '')}")

            try:
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
                        update_application_fields(aid, updates)

                    hr_activity = detail.get("hr_activity", "")
                    if filter_inactive and BossScraper.is_hr_inactive(hr_activity):
                        soft_delete_application(aid)
                        filtered_count += 1
                        print(f"[过滤] {job.get('job_title', '')} → HR不活跃({hr_activity})")
                        continue
            except asyncio.TimeoutError:
                print(f"[详情] 岗位 {aid} 超时(20s)，跳过详情")
            except Exception as e:
                print(f"[详情] 岗位 {aid} 抓取失败: {e}")

        # Phase 2: 并行评分（LLM调用，不需要浏览器锁）
        scoreable_ids = []
        for aid in new_ids:
            job = _scoring_cache.get(aid) or get_application_for_scoring(aid)
            if job:
                leg = check_legitimacy(job, all_jobs)
                update_application_legitimacy(aid, leg["level"], leg["signals"])
                scoreable_ids.append(aid)

        def _score_one(aid):
            job = _scoring_cache.get(aid) or get_application_for_scoring(aid)
            if not job:
                return 0
            title = job.get("job_title", "")
            company = job.get("company", "")
            desc = job.get("description", "")
            salary = job.get("salary", "")
            hr_name = job.get("hr_name", "")
            hr_activity = job.get("hr_activity", "")

            cv_score = None
            quality_score = None
            try:
                result = score_job_combined(title, company, desc, salary, hr_name, resume)
                cv_score = result.get("cv_score")
                quality_score = result.get("quality_score")
                if cv_score is not None:
                    update_application_score(aid, cv_score, result)
                else:
                    cv_score = 30
                if quality_score is None:
                    quality_score = 40
            except Exception as e:
                print(f"[评分] 合并评分失败: {e}")
                cv_score = 30
                quality_score = 40

            hr_score = score_hr_activity(hr_activity)
            update_application_hr_activity(aid, hr_score)
            composite = compute_composite_score(cv_score, quality_score, hr_score)
            update_application_composite_score(aid, composite)
            print(f"[评分] {title} → 综合:{composite}")
            return 1

        with ThreadPoolExecutor(max_workers=3) as pool:
            results = list(pool.map(_score_one, scoreable_ids))
        scored = sum(results)

        print(f"[后台评分] 完成: {scored}/{len(new_ids)} 评分成功, 过滤 {filtered_count}")
        await ws_manager.broadcast({
            "type": "search_complete",
            "keyword": keyword,
            "city": city,
            "found": found,
            "new": len(new_ids),
            "existing": db_existing,
            "page_dup": page_dup,
            "scored": scored,
            "filtered": filtered_count,
        })
    except Exception as e:
        print(f"[后台评分] 异常: {e}")
        import traceback
        traceback.print_exc()


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
            print(f"[搜索] 搜索异常: {e}")
            raise HTTPException(status_code=500, detail="搜索失败，请检查浏览器状态后重试")

        # 福利筛选
        if req.welfare:
            welfare_kw = [w.strip() for w in req.welfare.split(",") if w.strip()]
            jobs = state.automation._filter_by_welfare(jobs, welfare_kw)

        raw_found = len(jobs)
        jobs = _deduplicate_jobs(jobs)
        page_dup = raw_found - len(jobs)

        # 构建搜索参数覆盖（前端传入的经验/薪资优先于设置）
        overrides = {}
        if req.experience:
            parts = req.experience.split("-")
            if len(parts) == 2:
                overrides["experience_min"] = parts[0]
                overrides["experience_max"] = parts[1]
        if req.salary_min:
            overrides["salary_min"] = req.salary_min
        if req.salary_max:
            overrides["salary_max"] = req.salary_max

        new_ids = []
        result_jobs = []
        db_existing = 0
        filtered_count = 0
        for j in jobs:
            aid, is_new, app_dict = _save_job_with_dedup(j, overrides)
            if aid == 0 and not is_new:
                # 被过滤掉的岗位（不符合经验要求或期望薪资）
                filtered_count += 1
            elif is_new and aid:
                new_ids.append(aid)
                result_jobs.append(_search_job_payload(j, app_dict))
            elif not is_new:
                db_existing += 1

        print(f"[搜索] 页面 {raw_found} 条 → 去重 {len(jobs)} 条 → 新增 {len(new_ids)}，已有 {db_existing}，过滤 {filtered_count}")

        # 立即返回搜索结果，评分在后台执行
        if new_ids:
            asyncio.create_task(_background_score_and_apply(new_ids, req.keyword, req.city, len(jobs), db_existing, page_dup))

        resp = {"jobs_found": len(jobs), "new_jobs": len(new_ids), "db_existing": db_existing, "page_duplicates": page_dup, "saved": len(new_ids), "scored": 0, "filtered": filtered_count, "jobs": result_jobs, "scoring_in_background": bool(new_ids)}
        return resp
    except HTTPException:
        raise
    except Exception as e:
        print(f"[搜索] 未预期的错误: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="搜索过程出错，请重试")
    finally:
        chat_monitor.paused = was_paused


# ══════════════════════════════════════
#  去重
# ══════════════════════════════════════


@router.post("/api/jobs/deduplicate")
def deduplicate_jobs():
    """清理历史重复数据：按 公司+岗位+城市+薪资 联合去重，每组保留最早记录。"""
    try:
        return deduplicate_applications()
    except sqlite3.OperationalError as e:
        print(f"[去重] 数据库繁忙: {e}")
        raise HTTPException(status_code=503, detail="数据库繁忙，请稍后重试")
    except Exception as e:
        print(f"[去重] 去重失败: {e}")
        raise HTTPException(status_code=500, detail="去重操作失败，请重试")


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
                    update_application_fields(aid, updates)

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
    """手动重新评分单个岗位（合并评分，一次 LLM 调用）。"""
    job = get_application_for_scoring(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="岗位不存在")
    resume = _get_resume_summary()
    title = job.get("job_title", "")
    company = job.get("company", "")
    desc = job.get("description", "")
    salary = job.get("salary", "")
    hr_name = job.get("hr_name", "")
    hr_activity = job.get("hr_activity", "")

    # 合并评分（一次 LLM 调用同时返回 CV + 质量分）
    result = await asyncio.to_thread(score_job_combined, title, company, desc, salary, hr_name, resume)
    cv_score = result.get("cv_score")
    quality_score = result.get("quality_score")
    if cv_score is None:
        # 评分失败时仅填充分数，保留 LLM 已返回的 key_skills/gap/advice 等字段
        cv_score = 30
        result["cv_score"] = 30
        result.setdefault("quality_score", 40)
        result.setdefault("summary", "LLM评分失败，使用保守默认分")
    if quality_score is None:
        quality_score = 40
        result["quality_score"] = 40
    update_application_score(job_id, cv_score, result)

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

    return {
        "cv_score": cv_score,
        "quality_score": quality_score,
        "hr_score": hr_score,
        "composite": composite,
        "legitimacy": leg,
        "key_skills": result.get("key_skills", []),
        "gap": result.get("gap", ""),
        "advice": result.get("advice", ""),
        "summary": result.get("summary", ""),
    }


@router.post("/api/jobs/batch-score")
async def batch_score_jobs(mode: str = "unscored"):
    """批量评分岗位（后台执行，不阻塞）。
    mode: "unscored" = 仅未评分岗位, "all" = 所有岗位重新评分
    使用批量 prompt + 5 路并行加速。
    """
    from ..services.scorer import score_jobs_batch
    db = get_db()
    if mode == "all":
        rows = db.execute(
            "SELECT id FROM applications WHERE deleted_at IS NULL"
        ).fetchall()
        if not rows:
            return {"message": "没有岗位可评分", "count": 0}
    else:
        rows = db.execute(
            "SELECT id FROM applications WHERE score IS NULL AND deleted_at IS NULL"
        ).fetchall()
        if not rows:
            return {"message": "没有待评分的岗位", "count": 0}
    ids = [r["id"] for r in rows]
    resume = _get_resume_summary()
    all_jobs = get_all_active_jobs_for_legitimacy()

    BATCH_SIZE = 5
    MAX_WORKERS = 5

    def _apply_result(aid, result):
        """将评分结果写入数据库（必须在主线程调用）。"""
        cv = result.get("cv_score")
        if cv is not None:
            update_application_score(aid, cv, result)
        else:
            cv = 30
        qs = result.get("quality_score") or 40
        job = get_application_for_scoring(aid)
        hr_act = job.get("hr_activity", "") if job else ""
        hr_s = score_hr_activity(hr_act)
        update_application_hr_activity(aid, hr_s)
        if job:
            leg = check_legitimacy(job, all_jobs)
            update_application_legitimacy(aid, leg["level"], leg["signals"])
        comp = compute_composite_score(cv, qs, hr_s)
        update_application_composite_score(aid, comp)

    def _llm_score_batch(batch_ids):
        """仅做 LLM 评分，不写数据库（可并行）。返回 (jobs, results)。"""
        batch_jobs = []
        for aid in batch_ids:
            job = get_application_for_scoring(aid)
            if job:
                job["id"] = aid
                batch_jobs.append(job)
        if not batch_jobs:
            return [], []
        results = score_jobs_batch(batch_jobs, resume)
        return batch_jobs, results

    async def _batch_bg():
        total = len(ids)
        scored = 0
        failed = 0
        batches = [ids[i:i+BATCH_SIZE] for i in range(0, len(ids), BATCH_SIZE)]
        await ws_manager.broadcast({"type": "score_progress", "current": 0, "total": total, "scored": 0, "failed": 0, "status": "running"})
        loop = asyncio.get_running_loop()
        for batch_group_start in range(0, len(batches), MAX_WORKERS):
            group = batches[batch_group_start:batch_group_start+MAX_WORKERS]
            # 并行 LLM 评分（不写数据库）
            tasks = [loop.run_in_executor(None, _llm_score_batch, b) for b in group]
            llm_results = await asyncio.gather(*tasks, return_exceptions=True)
            # 串行写入数据库
            for r in llm_results:
                if isinstance(r, Exception):
                    print(f"[批量评分] LLM批次异常: {r}")
                    failed += BATCH_SIZE
                    continue
                jobs, results = r
                if not jobs:
                    continue
                for job, result in zip(jobs, results):
                    try:
                        _apply_result(job["id"], result)
                        scored += 1
                    except Exception as e:
                        print(f"[批量评分] 岗位 {job['id']} 写入失败: {e}")
                        failed += 1
            processed = min(batch_group_start + MAX_WORKERS, len(batches)) * BATCH_SIZE
            processed = min(processed, total)
            await ws_manager.broadcast({
                "type": "score_progress",
                "current": processed,
                "total": total,
                "scored": scored,
                "failed": failed,
                "status": "running"
            })
        print(f"[批量评分] 完成: {scored}/{total}")
        await ws_manager.broadcast({
            "type": "score_progress",
            "current": total,
            "total": total,
            "scored": scored,
            "failed": failed,
            "status": "done"
        })

    task = asyncio.create_task(_batch_bg())
    state.background_tasks.append(task)
    task.add_done_callback(_safe_remove_task)
    label = "重新评分" if mode == "all" else "批量评分"
    return {"message": f"开始{label} {len(ids)} 个岗位", "count": len(ids)}


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

    # 获取岗位数据用于匹配检查
    job = get_application_by_url(req.job_url)
    job_data = None
    if job:
        job_data = {
            "title": job.get("job_title", ""),
            "company": job.get("company", ""),
            "salary": job.get("salary", ""),
            "experience": job.get("experience", ""),
            "education": job.get("education", ""),
        }

    greeting = req.greeting
    if not greeting:
        title = job["job_title"] if job else "相关岗位"
        company = job["company"] if job else "贵公司"
        greeting = generate_greeting(title, company)

    async with state.browser_sync_lock:
        result = await state.automation.apply_to_job(req.job_url, greeting, job_data)
    if result.get("success"):
        await ws_manager.broadcast(
            {
                "type": "apply_complete",
                "job_url": req.job_url,
                "job_id": result.get("application_id"),
            }
        )
    elif result.get("skipped"):
        await ws_manager.broadcast(
            {
                "type": "apply_complete",
                "job_url": req.job_url,
                "skipped": True,
                "reason": result.get("message", ""),
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
        print(f"[扫描] 扫描失败: {e}")
        raise HTTPException(status_code=500, detail="页面扫描失败，请检查浏览器状态后重试")

    raw_found = len(jobs)
    jobs = _deduplicate_jobs(jobs)
    page_dup = raw_found - len(jobs)

    new_ids = []
    result_jobs = []
    db_existing = 0
    for j in jobs:
        aid, is_new, app_dict = _save_job_with_dedup(j)
        if is_new and aid:
            new_ids.append(aid)
            result_jobs.append(_search_job_payload(j, app_dict))
        elif not is_new:
            db_existing += 1

    print(f"[扫描] 页面 {raw_found} 条 → 去重 {len(jobs)} 条 → 新增 {len(new_ids)}，已有 {db_existing}")

    # 异步详情抓取 + 评分 + 自动投递（不阻塞返回）
    if new_ids:
        all_jobs = get_all_active_jobs_for_legitimacy()

        async def _pipeline_bg():
            scored, applied = await _fetch_details_and_score(new_ids, all_jobs)
            if scored > 0:
                await ws_manager.broadcast({"type": "score_complete", "count": scored})

        task = asyncio.create_task(_pipeline_bg())
        state.background_tasks.append(task)
        task.add_done_callback(_safe_remove_task)

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
    resume = _get_resume_summary()
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
        _interview_path = str(Path(__file__).resolve().parent.parent.parent / "interview")
        if _interview_path not in sys.path:
            sys.path.insert(0, _interview_path)
        from llm_client import llm_chat_deepseek, _load_ai_config

        cfg = _load_ai_config()
        if not cfg.get("api_key") or len(cfg["api_key"]) < 10:
            return {"error": "AI API Key 未配置，请先在设置页配置", "match_score": 0, "summary": "请检查AI配置"}

        raw = llm_chat_deepseek(
            [{"role": "user", "content": prompt}],
            system_prompt="你是求职辅导专家，输出严格JSON。",
            temperature=0.3,
        )

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
        print(f"[分析] AI返回非JSON: {raw[:200] if raw else '无响应'}")
        return {"error": "AI 返回的内容不是有效JSON，请重试", "match_score": 0, "summary": "AI响应异常"}
    except Exception as e:
        err_msg = str(e)
        print(f"[分析] AI分析异常: {err_msg}")
        if "401" in err_msg or "403" in err_msg:
            return {"error": "AI API Key 无效，请在设置页重新配置", "match_score": 0, "summary": "认证失败"}
        if "timeout" in err_msg.lower() or "connect" in err_msg.lower():
            return {"error": "AI 服务连接超时，请检查网络或稍后重试", "match_score": 0, "summary": "网络异常"}
        return {"error": "AI分析失败，请检查AI配置后重试", "match_score": 0, "summary": "请检查AI配置"}


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


class ShortlistRequest(BaseModel):
    job_url: str
    title: str = ""
    company: str = ""
    salary: str = ""
    city: str = ""
    note: str = ""


@router.post("/api/shortlists")
def add_shortlist(req: ShortlistRequest):
    if is_in_shortlist(req.job_url):
        return {"status": "already_exists"}
    sid = add_to_shortlist(
        req.job_url, req.title, req.company, req.salary, req.city, req.note,
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
    """手动触发自动投递（后台运行，立即返回）。"""
    if not state.automation or state.automation.page is None:
        raise HTTPException(status_code=503, detail="浏览器未启动")

    # 防止重复触发
    for t in state.background_tasks:
        if not t.done() and "智能投递" in (t.get_name() or ""):
            raise HTTPException(status_code=409, detail="智能投递已在运行中")

    async def _run():
        try:
            await _execute_auto_apply()
        except Exception as e:
            print(f"[智能投递] 后台执行异常: {e}")
            import traceback
            traceback.print_exc()

    task = asyncio.create_task(_run(), name="智能投递")
    task.add_done_callback(_safe_remove_task)
    state.background_tasks.append(task)
    return {"status": "ok", "message": "智能投递已启动"}
