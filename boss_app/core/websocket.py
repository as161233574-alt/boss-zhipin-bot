"""WebSocket 连接管理模块。

提供 WebSocketManager 类，负责管理所有 WebSocket 客户端连接，
包括接受新连接、断开连接、向所有客户端广播消息。
当所有客户端断开后自动关闭服务器。
"""

import asyncio
import os
from typing import List

from fastapi import WebSocket

MAX_WS_CLIENTS = 10
AUTO_SHUTDOWN_DELAY = 30  # 所有客户端断开后等待秒数


class WebSocketManager:
    """管理所有 WebSocket 客户端连接。"""

    def __init__(self) -> None:
        self.clients: List[WebSocket] = []
        self._had_clients: bool = False
        self._shutdown_task: asyncio.Task = None

    async def connect(self, websocket: WebSocket) -> None:
        """接受并注册一个新的 WebSocket 连接。超过上限时拒绝。"""
        if len(self.clients) >= MAX_WS_CLIENTS:
            await websocket.close(code=4003, reason="连接数已达上限")
            return
        await websocket.accept()
        self.clients.append(websocket)
        self._had_clients = True
        # 有新客户端连接，取消待执行的关闭任务
        if self._shutdown_task and not self._shutdown_task.done():
            self._shutdown_task.cancel()
            self._shutdown_task = None

    def disconnect(self, websocket: WebSocket) -> None:
        """移除一个已断开的 WebSocket 连接。"""
        if websocket in self.clients:
            self.clients.remove(websocket)
        # 所有客户端都断开且曾经有过连接，启动关闭倒计时
        if not self.clients and self._had_clients:
            self._schedule_shutdown()

    def _schedule_shutdown(self) -> None:
        """安排延迟关闭服务器。"""
        if self._shutdown_task and not self._shutdown_task.done():
            return
        try:
            loop = asyncio.get_running_loop()
            self._shutdown_task = loop.create_task(self._delayed_shutdown())
        except RuntimeError:
            pass

    async def _delayed_shutdown(self) -> None:
        """等待指定时间后，如果仍无客户端连接则关闭进程。"""
        await asyncio.sleep(AUTO_SHUTDOWN_DELAY)
        if not self.clients:
            print(f"\n[自动关闭] 前端已断开 {AUTO_SHUTDOWN_DELAY} 秒，自动停止服务器...")
            os._exit(0)

    async def broadcast(self, message: dict) -> None:
        """向所有已连接的客户端广播 JSON 消息。

        自动清理发送失败的死连接。
        """
        dead: List[WebSocket] = []
        for ws in self.clients:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            if ws in self.clients:
                self.clients.remove(ws)
        # 广播后检查是否所有客户端都已断开
        if not self.clients and self._had_clients:
            self._schedule_shutdown()


ws_manager = WebSocketManager()
