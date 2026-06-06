"""搜索 Agent — 包装 BossScraper 的搜索和详情抓取。"""

import asyncio
from .base import BaseAgent, AgentMessage
from ..core import state
from ..models.application import add_application, get_application_by_url


class SearchAgent(BaseAgent):
    name = "search"

    async def handle(self, msg: AgentMessage) -> None:
        action = msg.payload.get("action")
        if action == "search":
            await self._handle_search(msg)
        elif action == "fetch_detail":
            await self._handle_fetch_detail(msg)

    async def _handle_search(self, msg: AgentMessage) -> None:
        keyword = msg.payload.get("keyword", "")
        city_code = msg.payload.get("city_code", "100010000")
        max_pages = msg.payload.get("max_pages", 2)

        automation = state.automation
        if not automation or not automation.page:
            await self.send(msg.source, "result", {
                "error": "浏览器未启动", "correlation_id": msg.correlation_id,
            }, correlation_id=msg.correlation_id)
            return

        lock = state.browser_sync_lock
        async with lock:
            jobs = await automation.search(keyword, city_code, max_pages=max_pages)

        new_ids = []
        for job in jobs:
            existing = get_application_by_url(job.get("url", ""))
            if not existing:
                app_id = add_application(job)
                if app_id:
                    new_ids.append(app_id)

        result = {
            "total_found": len(jobs),
            "new_count": len(new_ids),
            "new_ids": new_ids,
            "correlation_id": msg.correlation_id,
        }

        # 回复调用方
        await self.send(msg.source, "result", result, correlation_id=msg.correlation_id)
        # 广播搜索完成事件
        await self.send("*", "event", {"event": "search_complete", **result})

    async def _handle_fetch_detail(self, msg: AgentMessage) -> None:
        url = msg.payload.get("url", "")
        automation = state.automation
        if not automation or not automation.page:
            return
        lock = state.browser_sync_lock
        async with lock:
            detail = await automation.fetch_detail(url)
        await self.send(msg.source, "result", {
            "detail": detail, "correlation_id": msg.correlation_id,
        }, correlation_id=msg.correlation_id)
