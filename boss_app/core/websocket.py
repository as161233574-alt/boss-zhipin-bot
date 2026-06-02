"""WebSocket 连接管理模块。

提供 WebSocketManager 类，负责管理所有 WebSocket 客户端连接，
包括接受新连接、断开连接、向所有客户端广播消息。
"""

from typing import List

from fastapi import WebSocket


class WebSocketManager:
    """管理所有 WebSocket 客户端连接。"""

    def __init__(self) -> None:
        self.clients: List[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        """接受并注册一个新的 WebSocket 连接。"""
        await websocket.accept()
        self.clients.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        """移除一个已断开的 WebSocket 连接。"""
        if websocket in self.clients:
            self.clients.remove(websocket)

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


ws_manager = WebSocketManager()
