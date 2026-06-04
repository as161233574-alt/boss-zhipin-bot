"""会话 & 聊天相关 API 路由。

包含会话列表、消息查看/同步/发送、自动回复开关、微信号交换记录等接口。
"""

import asyncio
from typing import List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..core.websocket import ws_manager
from ..models.conversation import (
    get_or_create_conversation,
    get_conversation,
    list_active_conversations,
    update_conversation_last_message,
    update_conversation_status,
    set_auto_reply,
    get_wechat_exchanges,
)
from ..models.message import (
    add_message,
    get_messages,
    replace_conversation_messages,
)
from ..core import state

router = APIRouter()


# ══════════════════════════════════════
#  Helpers
# ══════════════════════════════════════


def _clean_messages_for_web(messages: List[dict]) -> List[dict]:
    """清理 BOSS DOM 里混入的已读/送达状态，保持 Web 端只展示聊天正文。"""
    cleaned = []
    status_words = ("已读", "未读", "送达", "发送失败", "已发送")
    for msg in messages:
        item = dict(msg)
        content = (item.get("content") or "").strip()
        for word in status_words:
            if content.startswith(word):
                content = content[len(word) :].strip()
            if content.endswith(word):
                content = content[: -len(word)].strip()
        item["content"] = content
        if content:
            cleaned.append(item)
    return cleaned


# ══════════════════════════════════════
#  Pydantic Models
# ══════════════════════════════════════


class SendMessageRequest(BaseModel):
    content: str


# ══════════════════════════════════════
#  会话列表 & 详情
# ══════════════════════════════════════


@router.get("/api/wechat-exchanges")
def list_wechat_exchanges():
    """返回所有已获取到 HR 微信号的会话。"""
    records = get_wechat_exchanges()
    return {"exchanges": records}


@router.get("/api/conversations")
def list_conversations():
    convs = list_active_conversations()
    return {"conversations": convs}


@router.get("/api/conversations/{conv_id}")
def get_conversation_detail(conv_id: int):
    conv = get_conversation(conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="会话不存在")
    messages = _clean_messages_for_web(get_messages(conv_id, 100))
    return {"conversation": conv, "messages": messages}


@router.get("/api/conversations/{conv_id}/messages")
def get_conversation_messages(conv_id: int, limit: int = 50):
    # 这个接口被前端频繁轮询，必须只读本地缓存，不能每次都控制浏览器。
    return {"messages": _clean_messages_for_web(get_messages(conv_id, limit))}


@router.post("/api/conversations/{conv_id}/sync")
async def sync_conversation_messages(conv_id: int):
    """按需从当前 BOSS 浏览器会话同步一次消息。"""
    conv = get_conversation(conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="会话不存在")
    if not state.automation or state.automation.page is None:
        return {
            "success": False,
            "message": "浏览器未启动",
            "messages": _clean_messages_for_web(get_messages(conv_id, 100)),
        }

    hr_name = conv.get("hr_name", "")
    if not hr_name:
        raise HTTPException(status_code=400, detail="会话缺少HR姓名")

    sync_lock = state.browser_sync_lock
    if sync_lock is None:
        sync_lock = asyncio.Lock()
    if sync_lock.locked():
        return {
            "success": False,
            "message": "浏览器正忙，先显示缓存",
            "messages": _clean_messages_for_web(get_messages(conv_id, 100)),
        }

    try:
        async with sync_lock:
            opened = await asyncio.wait_for(state.automation.open_conversation_by_name(hr_name), timeout=8)
            if not opened:
                return {
                    "success": False,
                    "message": f"无法打开 {hr_name} 的会话",
                    "messages": _clean_messages_for_web(get_messages(conv_id, 100)),
                }

            live_messages = await asyncio.wait_for(state.automation.read_visible_messages(), timeout=5)
            if live_messages:
                replace_conversation_messages(conv_id, live_messages)
                last = live_messages[-1]
                update_conversation_last_message(conv_id, last.get("content", ""), last.get("sender", "hr"))
    except asyncio.TimeoutError:
        return {
            "success": False,
            "message": "同步超时，先显示缓存",
            "messages": _clean_messages_for_web(get_messages(conv_id, 100)),
        }

    return {
        "success": True,
        "messages": _clean_messages_for_web(get_messages(conv_id, 100)),
    }


@router.post("/api/conversations/{conv_id}/send")
async def send_manual_message(conv_id: int, req: SendMessageRequest):
    if not state.automation:
        raise HTTPException(status_code=503, detail="浏览器未启动")
    conv = get_conversation(conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="会话不存在")
    hr_name = conv.get("hr_name", "")
    if not hr_name:
        raise HTTPException(status_code=400, detail="会话缺少HR姓名")

    # 先打开对应会话
    opened = await state.automation.open_conversation_by_name(hr_name)
    if not opened:
        raise HTTPException(status_code=500, detail=f"无法在浏览器中打开 {hr_name} 的会话")

    browser_ok = await state.automation.send_message(req.content, False)
    if not browser_ok:
        raise HTTPException(status_code=500, detail="浏览器发送失败，本地不会写入这条消息")

    add_message(conv_id, "me", req.content, ai_generated=False)
    update_conversation_last_message(conv_id, req.content, "me")
    await ws_manager.broadcast(
        {
            "type": "manual_message_sent",
            "conversation_id": conv_id,
        }
    )
    return {"success": True, "browser_sent": browser_ok}


@router.post("/api/conversations/{conv_id}/open")
async def open_conversation_in_browser(conv_id: int):
    """在浏览器中打开对应会话。"""
    if not state.automation:
        raise HTTPException(status_code=503, detail="浏览器未启动")
    conv = get_conversation(conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="会话不存在")
    hr_name = conv.get("hr_name", "")
    if not hr_name:
        raise HTTPException(status_code=400, detail="会话缺少HR姓名")
    success = await state.automation.open_conversation_by_name(hr_name)
    return {
        "success": success,
        "message": f"已在浏览器中打开 {hr_name} 的会话" if success else "打开失败",
    }


@router.post("/api/conversations/{conv_id}/pause")
async def pause_auto_reply(conv_id: int):
    set_auto_reply(conv_id, False)
    await ws_manager.broadcast(
        {
            "type": "auto_reply_toggled",
            "conversation_id": conv_id,
            "enabled": False,
        }
    )
    return {"status": "ok"}


@router.post("/api/conversations/{conv_id}/resume")
async def resume_auto_reply(conv_id: int):
    set_auto_reply(conv_id, True)
    update_conversation_status(conv_id, "active")
    await ws_manager.broadcast(
        {
            "type": "auto_reply_toggled",
            "conversation_id": conv_id,
            "enabled": True,
        }
    )
    return {"status": "ok"}
