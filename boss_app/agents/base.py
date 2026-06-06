"""Agent 基类和通信消息定义。"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Optional
from uuid import uuid4


@dataclass
class AgentMessage:
    """Agent 间通信消息。"""
    type: str          # task / result / event / error
    source: str        # 发送方 agent 名
    target: str        # 接收方 ("*" = 广播)
    payload: dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    correlation_id: str = field(default_factory=lambda: str(uuid4())[:8])

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "source": self.source,
            "target": self.target,
            "payload": self.payload,
            "timestamp": self.timestamp,
            "correlation_id": self.correlation_id,
        }


class BaseAgent:
    """轻量级异步 Agent 基类。"""

    name: str = "base"

    def __init__(self, orchestrator):
        from .profiles import get_default_profile, AgentProfile
        self.orchestrator = orchestrator
        self.queue: asyncio.Queue[AgentMessage] = asyncio.Queue()
        self.status = "idle"       # idle / busy / paused / error
        self._task: Optional[asyncio.Task] = None
        self.stats = {"tasks_completed": 0, "errors": 0, "last_active": None}
        # Agent Profile（从 profiles.py 加载默认，可被数据库覆盖）
        self.profile: AgentProfile = get_default_profile(self.name) or AgentProfile(
            name=self.name, display_name=self.name, description="",
        )

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self.status = "idle"
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        self.status = "paused"
        if self._task and not self._task.done():
            self._task.cancel()

    async def _run(self) -> None:
        while True:
            try:
                msg = await self.queue.get()
                self.status = "busy"
                await self.handle(msg)
                self.stats["tasks_completed"] += 1
                self.stats["last_active"] = time.time()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.stats["errors"] += 1
                await self.send("*", "error", {"error": str(e), "agent": self.name})
            finally:
                if self.status != "paused":
                    self.status = "idle"

    async def handle(self, msg: AgentMessage) -> None:
        raise NotImplementedError

    async def execute(self, payload: dict, timeout: float = 120) -> dict:
        """同步执行：发送任务并等待结果。"""
        future = asyncio.get_event_loop().create_future()
        correlation_id = str(uuid4())[:8]
        self.orchestrator.pending_futures[correlation_id] = future
        await self.queue.put(AgentMessage(
            type="task", source="orchestrator", target=self.name,
            payload=payload, correlation_id=correlation_id,
        ))
        try:
            return await asyncio.wait_for(future, timeout=timeout)
        finally:
            self.orchestrator.pending_futures.pop(correlation_id, None)

    async def send(self, target: str, msg_type: str, payload: dict,
                   correlation_id: str = "") -> None:
        kwargs = dict(type=msg_type, source=self.name, target=target, payload=payload)
        if correlation_id:
            kwargs["correlation_id"] = correlation_id
        await self.orchestrator.dispatch(AgentMessage(**kwargs))

    def get_status(self) -> dict:
        return {
            "name": self.name,
            "status": self.status,
            "queue_size": self.queue.qsize(),
            "stats": self.stats,
        }

    def get_llm_config(self) -> dict:
        """返回该 Agent 的 LLM 配置，Agent 级配置优先于全局配置。"""
        import sys, os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'interview'))
        from llm_client import _load_ai_config
        global_cfg = _load_ai_config()
        return {
            "api_key": global_cfg["api_key"],
            "base_url": global_cfg["base_url"],
            "model": self.profile.model or global_cfg["model"],
            "temperature": self.profile.temperature,
            "max_tokens": self.profile.max_tokens,
        }

    async def llm_call(self, messages: list, system_prompt: str = None,
                       temperature: float = None) -> str:
        """Agent 级 LLM 调用，自动使用 profile 配置。"""
        import asyncio as _asyncio
        import sys, os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'interview'))
        from llm_client import llm_call_with_config
        cfg = self.get_llm_config()
        temp = temperature if temperature is not None else cfg["temperature"]
        loop = _asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, lambda: llm_call_with_config(cfg, messages, system_prompt, temp)
        )
