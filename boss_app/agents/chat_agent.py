"""聊天 Agent — 包装 monitor + replier 的聊天监控和自动回复。"""

import asyncio
import time
from .base import BaseAgent, AgentMessage
from ..core import state
from ..core.database import get_active_resume
from ..models.settings import get_setting
from ..models.conversation import update_conversation_interest
from ..models.message import add_message


def _get_resume_summary() -> str:
    """获取当前激活简历的摘要，如果没有则回退到旧的 settings。"""
    active = get_active_resume()
    if active and active.get("summary"):
        return active["summary"]
    return get_setting("resume_summary", "")


class ChatAgent(BaseAgent):
    name = "chat"

    def __init__(self, orchestrator):
        super().__init__(orchestrator)
        self._monitor_task = None
        self._monitor_running = False

    async def handle(self, msg: AgentMessage) -> None:
        action = msg.payload.get("action")
        if action == "start_monitor":
            await self._start_monitor(msg)
        elif action == "stop_monitor":
            self._monitor_running = False
        elif action == "reply":
            await self._handle_reply(msg)
        elif action == "scan_unread":
            await self._handle_scan(msg)

    async def _start_monitor(self, msg: AgentMessage) -> None:
        if self._monitor_task and not self._monitor_task.done():
            return
        self._monitor_running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())

    async def _monitor_loop(self) -> None:
        while self._monitor_running:
            try:
                auto_reply = get_setting("auto_reply_enabled", "false") == "true"
                automation = state.automation
                if automation and automation.page and auto_reply:
                    await self._run_chat_cycle()
            except Exception as e:
                await self.send("*", "error", {"error": f"chat monitor: {e}", "agent": self.name})
            await asyncio.sleep(15)

    async def _run_chat_cycle(self) -> None:
        automation = state.automation
        lock = state.browser_sync_lock
        if lock is None or lock.locked():
            return
        async with lock:
            result = await automation.run_chat_monitor_cycle()
        if result.get("new_messages", 0) > 0:
            await self.send("*", "event", {
                "event": "new_messages",
                "count": result["new_messages"],
                "replies_sent": result.get("replies_sent", 0),
            })

    async def _handle_reply(self, msg: AgentMessage) -> None:
        from ..services.replier import generate_reply
        conversation_id = msg.payload.get("conversation_id")
        hr_message = msg.payload.get("hr_message", "")
        job_info = msg.payload.get("job_info", {})
        wechat_id = msg.payload.get("wechat_id", "")

        loop = asyncio.get_event_loop()
        agent_cfg = self.get_llm_config()
        reply, interest, emotion, stage = await loop.run_in_executor(
            None, lambda: generate_reply(
                conversation_id, hr_message, job_info,
                resume_summary=_get_resume_summary(),
                wechat_id=wechat_id, cfg=agent_cfg,
            )
        )
        await self.send(msg.source, "result", {
            "reply": reply, "interest": interest,
            "emotion": emotion, "stage": stage,
            "correlation_id": msg.correlation_id,
        }, correlation_id=msg.correlation_id)

    async def _handle_scan(self, msg: AgentMessage) -> None:
        automation = state.automation
        if not automation or not automation.page:
            return
        lock = state.browser_sync_lock
        async with lock:
            unread = await automation.run_chat_monitor_cycle()
        await self.send(msg.source, "result", {
            "unread": unread, "correlation_id": msg.correlation_id,
        }, correlation_id=msg.correlation_id)
