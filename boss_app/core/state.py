"""全局共享状态 — automation, monitor, lock 等"""
import asyncio
from typing import List, Optional

# 自动化实例
automation = None

# 监控任务
monitor_task: Optional[asyncio.Task] = None

# 监控暂停标志
monitor_paused: bool = False

# 浏览器同步锁（防止并发操作页面）
browser_sync_lock: asyncio.Lock = asyncio.Lock()

# 后台任务引用（防止被 GC 回收，以及异常丢失）
background_tasks: List[asyncio.Task] = []
