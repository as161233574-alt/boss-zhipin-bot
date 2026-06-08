"""系统管理相关 API 路由。

包含浏览器启动/停止、重新登录、心跳保活、监控暂停/恢复、
健康检查、诊断、状态查询、空闲跳转日志、定时任务等接口。
"""

import os
import sys as _sys
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..core.websocket import ws_manager
from ..core.monitor import chat_monitor
from ..core.scheduler import auto_scheduler
from ..models.application import (
    get_today_application_count,
    get_today_pending_count,
)
from ..models.conversation import list_active_conversations
from ..models.settings import (
    get_setting,
    set_setting,
    get_daily_stats,
)
from ..core import state
from boss_app.services.automation import BossAutomation

router = APIRouter()


# ══════════════════════════════════════
#  系统状态
# ══════════════════════════════════════


@router.get("/api/status")
def get_status():
    browser_ok = state.automation is not None and state.automation.page is not None
    return {
        "browser_running": browser_ok,
        "auto_reply_enabled": get_setting("auto_reply_enabled", "false") == "true",
        "monitor_running": chat_monitor.running,
        "monitor_paused": chat_monitor.paused,
        "today_applications": get_today_application_count(),
        "active_conversations": len(list_active_conversations()),
        "daily_stats": get_daily_stats(),
    }


@router.get("/api/doctor")
def doctor():
    """诊断环境：Python版本、浏览器状态、登录态、AI配置等。"""
    try:
        _sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "interview"))
        from llm_client import _load_ai_config

        cfg = _load_ai_config()
        ai_key_ok = bool(cfg.get("api_key") and len(cfg["api_key"]) > 10)
    except Exception:
        ai_key_ok = False

    browser_ok = state.automation is not None and state.automation.page is not None
    checks = {
        "python": {"ok": True, "detail": _sys.version.split()[0]},
        "browser": {"ok": browser_ok, "detail": "运行中" if browser_ok else "未启动"},
        "boss_login": {"ok": browser_ok, "detail": "已登录" if browser_ok else "未登录"},
        "ai_key": {"ok": ai_key_ok, "detail": "已配置" if ai_key_ok else "未配置"},
        "today_applications": get_today_application_count(),
        "pending_jobs": get_today_pending_count(),
    }
    all_ok = all(v.get("ok", True) for v in checks.values() if isinstance(v, dict))
    return {"ok": all_ok, "checks": checks}


@router.get("/api/health")
def health():
    return {"status": "ok", "browser": state.automation is not None}


# ══════════════════════════════════════
#  浏览器控制
# ══════════════════════════════════════


@router.post("/api/system/start")
async def start_automation():
    if state.automation is not None and state.automation.page is not None:
        return {"status": "already_started"}

    try:
        a = BossAutomation(headless=False)
        await a.start()
        state.automation = a
    except Exception as e:
        import traceback
        detail = str(e) or type(e).__name__
        traceback.print_exc()
        print(f"[系统] 浏览器启动失败: {detail}")
        state.automation = None
        return {"status": "error", "message": f"浏览器启动失败: {detail}"}

    if state.automation is None or state.automation.page is None:
        state.automation = None
        return {"status": "error", "message": "浏览器启动后页面为空，请重试"}

    chat_monitor.start(state.automation, ws_manager)
    # 如果定时任务已启用，启动调度器
    if get_setting("auto_schedule_enabled", "false") == "true":
        auto_scheduler.start(state.automation, ws_manager)
    await ws_manager.broadcast({"type": "system", "event": "started"})
    return {"status": "started"}


@router.post("/api/system/stop")
async def stop_automation():
    chat_monitor.stop()
    auto_scheduler.stop()
    if state.automation:
        try:
            await state.automation._save_state()  # 正常关闭时保存登录态
        except Exception:
            pass
        try:
            await state.automation.close()
        except Exception:
            pass
        state.automation = None
    await ws_manager.broadcast({"type": "system", "event": "stopped"})
    return {"status": "stopped"}


@router.post("/api/system/relogin")
async def relogin():
    """重新登录 BOSS直聘。会打开浏览器让用户扫码。"""
    chat_monitor.stop()
    if state.automation:
        try:
            await state.automation.close()
        except Exception:
            pass
        state.automation = None

    try:
        a = BossAutomation(headless=False)
        await a.start()
        await a.login()
        state.automation = a
    except Exception as e:
        state.automation = None
        return {"status": "error", "message": f"登录失败: {e}"}

    if state.automation is None or state.automation.page is None:
        state.automation = None
        return {"status": "error", "message": "登录后页面异常，请重试"}

    chat_monitor.start(state.automation, ws_manager)
    await ws_manager.broadcast({"type": "system", "event": "relogin_ok"})
    return {"status": "ok", "message": "扫码登录成功"}


@router.post("/api/system/heartbeat")
async def manual_heartbeat():
    """手动心跳保活。"""
    if not state.automation or state.automation.page is None:
        raise HTTPException(status_code=503, detail="浏览器未启动")
    alive = await state.automation.heartbeat()
    if not alive:
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")
    return {"status": "ok", "alive": True}


@router.post("/api/system/navigate-chat")
async def navigate_to_chat_page():
    """在浏览器中打开 BOSS 直聘聊天页。"""
    if not state.automation or state.automation.page is None:
        raise HTTPException(status_code=503, detail="浏览器未启动")
    success = await state.automation.navigate_to_chat()
    return {
        "status": "ok" if success else "error",
        "message": "已跳转到聊天页" if success else "跳转失败，请检查登录状态",
    }


# ══════════════════════════════════════
#  监控控制
# ══════════════════════════════════════


@router.post("/api/monitor/pause")
async def pause_monitor():
    chat_monitor.pause()
    await ws_manager.broadcast({"type": "monitor_paused"})
    return {"status": "paused"}


@router.post("/api/monitor/resume")
async def resume_monitor():
    chat_monitor.resume()
    await ws_manager.broadcast({"type": "monitor_resumed"})
    return {"status": "resumed"}


# ══════════════════════════════════════
#  用户行为日志
# ══════════════════════════════════════


class IdleRedirectLog(BaseModel):
    timestamp: str = ""
    from_url: str = ""
    idle_duration: str = ""


@router.post("/api/log/idle-redirect")
async def log_idle_redirect(req: IdleRedirectLog):
    """记录空闲超时跳转日志"""
    from datetime import datetime
    log_entry = {
        "event": "idle_redirect",
        "timestamp": req.timestamp or datetime.now().isoformat(),
        "from_url": req.from_url,
        "idle_duration": req.idle_duration,
    }
    print(f"[行为日志] 空闲跳转: {log_entry}")
    return {"status": "ok"}


# ══════════════════════════════════════
#  定时任务
# ══════════════════════════════════════


class SchedulerConfig(BaseModel):
    enabled: bool = False
    cron: str = "09:00,14:00"


@router.post("/api/scheduler/start")
async def start_scheduler(req: SchedulerConfig):
    """启用/配置定时任务。"""
    set_setting("auto_schedule_enabled", "true" if req.enabled else "false")
    if req.cron:
        set_setting("auto_schedule_cron", req.cron)
    if req.enabled and state.automation:
        auto_scheduler.start(state.automation, ws_manager)
    return {
        "status": "ok",
        "enabled": req.enabled,
        "cron": req.cron,
        "running": auto_scheduler.running,
    }


@router.post("/api/scheduler/stop")
async def stop_scheduler():
    """停用定时任务。"""
    set_setting("auto_schedule_enabled", "false")
    auto_scheduler.stop()
    return {"status": "ok", "running": False}


@router.get("/api/scheduler/status")
def scheduler_status():
    """返回定时任务状态。"""
    return {
        "enabled": get_setting("auto_schedule_enabled", "false") == "true",
        "running": auto_scheduler.running,
        "cron": get_setting("auto_schedule_cron", "09:00,14:00"),
        "next_run": auto_scheduler.next_run,
        "last_run": auto_scheduler.last_run,
        "last_result": auto_scheduler.last_result,
    }
