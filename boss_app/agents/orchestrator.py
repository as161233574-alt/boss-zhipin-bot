"""Agent 协调器 — 管理所有 Agent 的生命周期和消息路由。"""

import asyncio
import time
from collections import deque
from typing import Dict, Optional

from .base import BaseAgent, AgentMessage


class Orchestrator:
    """Agent 协调器。"""

    def __init__(self):
        self.agents: Dict[str, BaseAgent] = {}
        self.message_log: deque = deque(maxlen=200)
        self.pending_futures: Dict[str, asyncio.Future] = {}
        self._started = False

    def register(self, agent: BaseAgent) -> None:
        self.agents[agent.name] = agent

    async def start_all(self) -> None:
        for agent in self.agents.values():
            await agent.start()
        self._started = True

    async def stop_all(self) -> None:
        for agent in self.agents.values():
            await agent.stop()
        self._started = False

    async def dispatch(self, msg: AgentMessage) -> None:
        self.message_log.append(msg.to_dict())
        # 如果有等待结果的 future，resolve 它
        if msg.type == "result" and msg.correlation_id in self.pending_futures:
            fut = self.pending_futures[msg.correlation_id]
            if not fut.done():
                fut.set_result(msg.payload)
            return
        # 路由消息
        if msg.target == "*":
            for name, agent in self.agents.items():
                if name != msg.source:
                    await agent.queue.put(msg)
        elif msg.target in self.agents:
            await self.agents[msg.target].queue.put(msg)

    async def run_pipeline(self, keyword: str, city: str, city_code: str = "") -> dict:
        """完整流水线: 搜索 → 评分 → (可选)投递。"""
        result = {"search": None, "score": None, "apply": None}
        # Step 1: 搜索
        search = self.agents.get("search")
        if search:
            result["search"] = await search.execute({
                "action": "search", "keyword": keyword,
                "city": city, "city_code": city_code,
            })
        # Step 2: 评分
        scorer = self.agents.get("scorer")
        if scorer and result["search"] and result["search"].get("new_ids"):
            result["score"] = await scorer.execute({
                "action": "batch_score",
                "job_ids": result["search"]["new_ids"],
            })
        return result

    def get_all_status(self) -> list:
        return [a.get_status() for a in self.agents.values()]

    def get_messages(self, limit: int = 50) -> list:
        msgs = list(self.message_log)
        return msgs[-limit:]


# 全局单例
orchestrator = Orchestrator()
