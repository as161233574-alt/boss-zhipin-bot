"""投递 Agent — 包装 automation 的投递功能。"""

import asyncio
from .base import BaseAgent, AgentMessage
from ..core import state
from ..models.application import get_application, get_today_application_count
from ..models.settings import get_setting


class ApplyAgent(BaseAgent):
    name = "apply"

    async def handle(self, msg: AgentMessage) -> None:
        action = msg.payload.get("action")
        if action == "apply_one":
            await self._handle_apply_one(msg)
        elif action == "batch_apply":
            await self._handle_batch_apply(msg)
        elif action == "auto_apply":
            await self._handle_auto_apply(msg)

    async def _handle_apply_one(self, msg: AgentMessage) -> None:
        job_id = msg.payload.get("job_id")
        job = get_application(job_id)
        if not job:
            await self.send(msg.source, "result", {
                "error": "岗位不存在", "correlation_id": msg.correlation_id,
            }, correlation_id=msg.correlation_id)
            return

        automation = state.automation
        if not automation or not automation.page:
            await self.send(msg.source, "result", {
                "error": "浏览器未启动", "correlation_id": msg.correlation_id,
            }, correlation_id=msg.correlation_id)
            return

        lock = state.browser_sync_lock
        greeting = msg.payload.get("greeting", "")
        async with lock:
            result = await automation.apply_to_job(
                job.get("job_url", ""), greeting, job,
            )

        await self.send(msg.source, "result", {
            "result": result, "correlation_id": msg.correlation_id,
        }, correlation_id=msg.correlation_id)
        await self.send("*", "event", {"event": "apply_complete", **result})

    async def _handle_batch_apply(self, msg: AgentMessage) -> None:
        job_ids = msg.payload.get("job_ids", [])
        results = []
        for aid in job_ids:
            r = await self._apply_single(aid)
            results.append(r)
            await asyncio.sleep(2)

        applied = sum(1 for r in results if r.get("success"))
        await self.send(msg.source, "result", {
            "applied": applied, "total": len(job_ids),
            "results": results, "correlation_id": msg.correlation_id,
        }, correlation_id=msg.correlation_id)

    async def _handle_auto_apply(self, msg: AgentMessage) -> None:
        candidates = msg.payload.get("candidates", [])
        if not candidates:
            return
        try:
            daily_limit = int(get_setting("daily_apply_limit", "15"))
        except (ValueError, TypeError):
            daily_limit = 15
        current = get_today_application_count()
        remaining = daily_limit - current
        if remaining <= 0:
            return

        to_apply = candidates[:remaining]
        await self._handle_batch_apply(AgentMessage(
            type="task", source=msg.source, target=self.name,
            payload={"job_ids": to_apply},
            correlation_id=msg.correlation_id,
        ))

    async def _apply_single(self, job_id: int) -> dict:
        job = get_application(job_id)
        if not job:
            return {"success": False, "message": "岗位不存在"}
        automation = state.automation
        if not automation or not automation.page:
            return {"success": False, "message": "浏览器未启动"}
        lock = state.browser_sync_lock
        async with lock:
            return await automation.apply_to_job(
                job.get("job_url", ""), "", job,
            )
