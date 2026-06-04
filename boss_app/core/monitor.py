"""聊天监控循环模块。

提供 ChatMonitor 类，负责后台轮询 BOSS 直聘聊天消息并自动回复，
包括 session 心跳保活、暂停/恢复控制等。
"""

import asyncio
import random
import sys
from pathlib import Path
from typing import Optional

from boss_state import get_setting


class ChatMonitor:
    """后台聊天监控循环管理器。"""

    def __init__(self) -> None:
        self.task: Optional[asyncio.Task] = None
        self.paused: bool = False

    def start(self, automation, ws_manager) -> None:
        """启动监控后台任务。

        Parameters
        ----------
        automation : BossAutomation
            浏览器自动化实例。
        ws_manager : WebSocketManager
            WebSocket 广播管理器。
        """
        if self.task is not None and not self.task.done():
            return
        self.task = asyncio.create_task(self._loop(automation, ws_manager))

    def stop(self) -> None:
        """停止监控后台任务。"""
        if self.task is not None and not self.task.done():
            self.task.cancel()
            self.task = None

    def pause(self) -> None:
        """暂停监控循环（不取消任务）。"""
        self.paused = True

    def resume(self) -> None:
        """恢复监控循环。"""
        self.paused = False

    @property
    def running(self) -> bool:
        """监控任务是否正在运行。"""
        return self.task is not None and not self.task.done()

    # ------------------------------------------------------------------
    #  内部监控循环
    # ------------------------------------------------------------------

    async def _loop(self, automation, ws_manager) -> None:
        """后台轮询聊天消息 + 自动回复。带 session 心跳保活。"""
        await asyncio.sleep(3)  # 启动后简短等待

        if automation:
            print("[监控] 后台监控任务已启动")
            await automation.keep_alive()

        # 验证 AI 回复系统
        try:
            sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "interview"))
            from llm_client import _load_ai_config

            cfg = _load_ai_config()
            if cfg["api_key"] and len(cfg["api_key"]) > 10:
                print(f"[监控] AI API 已配置（{cfg['model']}），自动回复就绪")
            else:
                print("[监控] ⚠️ AI API Key 未配置，请在前端设置页配置")
        except Exception as e:
            print(f"[监控] ⚠️ AI 回复系统加载失败: {e}")

        # 首次立即跑一轮监控，不等延迟
        if automation:
            print("[监控] 执行首次会话扫描...")
            try:
                result = await automation.run_chat_monitor_cycle()
                if result.get("new_messages", 0) > 0:
                    await ws_manager.broadcast({"type": "new_messages", "summary": result})
                if result.get("replies_sent", 0) > 0:
                    await ws_manager.broadcast({"type": "auto_reply_sent", "summary": result})
                if result.get("new_conversations"):
                    await ws_manager.broadcast({"type": "new_messages"})
            except Exception as e:
                print(f"  [监控] 首次扫描异常: {e}")

        _heartbeat_count = 0
        _heartbeat_misses = 0
        while True:
            try:
                min_delay = int(get_setting("min_reply_delay_sec", "15"))
                max_delay = int(get_setting("max_reply_delay_sec", "20"))
                delay = random.randint(min(min_delay, max_delay), max(min_delay, max_delay) + 5)
                await asyncio.sleep(delay)

                if self.paused:
                    continue

                if not automation:
                    continue

                # 每轮轻量检查登录态（不导航，不触发BOSS反爬）
                _heartbeat_count += 1
                alive = await automation.heartbeat()
                if not alive:
                    await asyncio.sleep(5)
                    alive = await automation.heartbeat()

                if not alive:
                    _heartbeat_misses += 1
                else:
                    _heartbeat_misses = 0

                if _heartbeat_misses >= 2:
                    await ws_manager.broadcast(
                        {
                            "type": "session_expired",
                            "message": "BOSS直聘登录已过期，请点击设置Tab的「重新扫码登录」",
                        }
                    )
                    break

                # 每5轮轻量保活，避免 BOSS session 超时
                if _heartbeat_count % 5 == 0:
                    await automation.keep_alive()

                if get_setting("auto_reply_enabled", "false") != "true":
                    continue

                result = await automation.run_chat_monitor_cycle()

                if result.get("new_messages", 0) > 0:
                    await ws_manager.broadcast(
                        {
                            "type": "new_messages",
                            "summary": result,
                        }
                    )
                if result.get("replies_sent", 0) > 0:
                    await ws_manager.broadcast(
                        {
                            "type": "auto_reply_sent",
                            "summary": result,
                        }
                    )
                if result.get("new_conversations"):
                    await ws_manager.broadcast({"type": "new_messages"})
                if result.get("wechat_exchanged"):
                    await ws_manager.broadcast({"type": "wechat_exchanged"})

                safety_ok = await automation.check_page_safety()
                if not safety_ok:
                    await ws_manager.broadcast(
                        {
                            "type": "safety_warning",
                            "message": "检测到页面异常(验证码/登录失效/账号限制)，已暂停自动操作。请手动检查浏览器。",
                        }
                    )
                    break

            except asyncio.CancelledError:
                break
            except Exception as e:
                await ws_manager.broadcast(
                    {
                        "type": "error",
                        "message": f"监控循环异常: {e}",
                    }
                )
                await asyncio.sleep(60)

        # 循环退出后通知前端
        await ws_manager.broadcast({"type": "monitor_stopped", "reason": "loop_exited"})


chat_monitor = ChatMonitor()
