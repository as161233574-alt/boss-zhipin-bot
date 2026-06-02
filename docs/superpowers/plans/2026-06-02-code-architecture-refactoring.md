# 代码架构重构实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 BOSS 直聘自动化控制台的代码架构从单文件结构重构为模块化包结构

**Architecture:** 采用按职责分层拆分方案，创建 boss_app/ 包，包含 routes、services、models、core 四个子模块

**Tech Stack:** Python 3, FastAPI, SQLite, Playwright

---

## 文件结构

| 新文件 | 来源 | 职责 |
|--------|------|------|
| `boss_app/__init__.py` | 新建 | 包初始化 |
| `boss_app/main.py` | boss_app.py | FastAPI 应用入口 |
| `boss_app/config.py` | boss_app.py | 配置常量 |
| `boss_app/core/database.py` | boss_state.py | 数据库连接 |
| `boss_app/core/websocket.py` | boss_app.py | WebSocket 管理 |
| `boss_app/core/monitor.py` | boss_app.py | 监控循环 |
| `boss_app/models/application.py` | boss_state.py | 投递记录数据层 |
| `boss_app/models/conversation.py` | boss_state.py | 会话数据层 |
| `boss_app/models/message.py` | boss_state.py | 消息数据层 |
| `boss_app/models/settings.py` | boss_state.py | 设置数据层 |
| `boss_app/services/scraper.py` | boss_firefox.py | 爬虫基类 |
| `boss_app/services/automation.py` | boss_automation.py | 自动化服务 |
| `boss_app/services/replier.py` | boss_replier.py | AI 回复 |
| `boss_app/routes/jobs.py` | boss_app.py | 职位 API |
| `boss_app/routes/conversations.py` | boss_app.py | 会话 API |
| `boss_app/routes/settings.py` | boss_app.py | 设置 API |
| `boss_app/routes/system.py` | boss_app.py | 系统 API |
| `boss_app/routes/debug.py` | boss_app.py | 调试 API |
| `run.py` | 新建 | 新启动入口 |

---

## Task 1: 创建包结构和基础设施

**Files:**
- Create: `boss_app/__init__.py`
- Create: `boss_app/core/__init__.py`
- Create: `boss_app/core/database.py`

- [ ] **Step 1: 创建包目录结构**

```bash
mkdir -p boss_app/core boss_app/models boss_app/services boss_app/routes
```

- [ ] **Step 2: 创建 boss_app/__init__.py**

```python
"""BOSS直聘自动化控制台 - 模块化包结构"""
__version__ = "2.0.0"
```

- [ ] **Step 3: 创建 core/__init__.py**

```python
"""核心模块 - 数据库、WebSocket、监控"""
```

- [ ] **Step 4: 创建 core/database.py**

从 `boss_state.py` 提取数据库连接逻辑：

```python
"""数据库连接管理"""
import sqlite3
import threading
from pathlib import Path

DB_PATH = Path(__file__).parent.parent.parent / ".boss_profile" / "boss_state.db"

_local = threading.local()


def get_db() -> sqlite3.Connection:
    """获取线程本地数据库连接"""
    if not hasattr(_local, "conn") or _local.conn is None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _local.conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        _local.conn.row_factory = sqlite3.Row
        _local.conn.execute("PRAGMA journal_mode=WAL")
        _local.conn.execute("PRAGMA foreign_keys=ON")
    return _local.conn


def init_db():
    """初始化数据库表结构"""
    db = get_db()
    db.executescript("""
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_title TEXT NOT NULL,
            company TEXT,
            salary TEXT,
            job_url TEXT UNIQUE NOT NULL,
            city TEXT,
            experience TEXT,
            education TEXT,
            hr_name TEXT,
            hr_title TEXT,
            description TEXT,
            status TEXT DEFAULT 'pending',
            greeting_text TEXT,
            greeting_sent_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id INTEGER REFERENCES applications(id),
            hr_name TEXT NOT NULL,
            hr_company TEXT,
            job_title TEXT,
            last_message_text TEXT,
            last_message_from TEXT,
            last_message_at TIMESTAMP,
            unread_count INTEGER DEFAULT 0,
            status TEXT DEFAULT 'active',
            auto_reply_enabled INTEGER DEFAULT 1,
            interest_level TEXT,
            hr_wechat TEXT,
            wechat_shared_at TIMESTAMP,
            resume_sent INTEGER DEFAULT 0,
            phone_shared INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL REFERENCES conversations(id),
            sender TEXT NOT NULL,
            content TEXT NOT NULL,
            delivery_status TEXT,
            ai_generated INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS daily_stats (
            date TEXT PRIMARY KEY,
            applications_sent INTEGER DEFAULT 0,
            messages_sent INTEGER DEFAULT 0,
            messages_received INTEGER DEFAULT 0,
            auto_replies_sent INTEGER DEFAULT 0
        );
    """)
    # 兼容旧数据库的 ALTER TABLE
    try:
        db.execute("ALTER TABLE messages ADD COLUMN delivery_status TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        db.execute("ALTER TABLE conversations ADD COLUMN interest_level TEXT")
    except sqlite3.OperationalError:
        pass
    # ... 其他 ALTER TABLE
```

- [ ] **Step 5: 提交代码**

```bash
git add boss_app/
git commit -m "refactor: create package structure and database module"
```

---

## Task 2: 提取 WebSocket 管理模块

**Files:**
- Create: `boss_app/core/__init__.py`
- Create: `boss_app/core/websocket.py`

- [ ] **Step 1: 创建 core/websocket.py**

从 `boss_app.py` 提取 WebSocket 相关逻辑：

```python
"""WebSocket 连接管理"""
from typing import List
from fastapi import WebSocket


class WebSocketManager:
    """WebSocket 连接管理器"""

    def __init__(self):
        self.clients: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        """接受新的 WebSocket 连接"""
        await websocket.accept()
        self.clients.append(websocket)

    def disconnect(self, websocket: WebSocket):
        """断开 WebSocket 连接"""
        if websocket in self.clients:
            self.clients.remove(websocket)

    async def broadcast(self, message: dict):
        """向所有连接广播消息"""
        disconnected = []
        for client in self.clients:
            try:
                await client.send_json(message)
            except Exception:
                disconnected.append(client)
        for client in disconnected:
            self.disconnect(client)


# 全局 WebSocket 管理器实例
ws_manager = WebSocketManager()
```

- [ ] **Step 2: 提交代码**

```bash
git add boss_app/core/websocket.py
git commit -m "refactor: extract WebSocket manager module"
```

---

## Task 3: 提取监控循环模块

**Files:**
- Create: `boss_app/core/monitor.py`

- [ ] **Step 1: 创建 core/monitor.py**

从 `boss_app.py` 提取监控循环逻辑：

```python
"""聊天监控循环"""
import asyncio
from typing import Optional


class ChatMonitor:
    """聊天监控器"""

    def __init__(self):
        self.task: Optional[asyncio.Task] = None
        self.paused: bool = False

    async def start(self, automation, ws_manager):
        """启动监控循环"""
        if self.task and not self.task.done():
            return
        self.paused = False
        self.task = asyncio.create_task(self._loop(automation, ws_manager))

    async def stop(self):
        """停止监控循环"""
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
            self.task = None

    def pause(self):
        """暂停监控"""
        self.paused = True

    def resume(self):
        """恢复监控"""
        self.paused = False

    async def _loop(self, automation, ws_manager):
        """监控循环主逻辑"""
        while True:
            if self.paused:
                await asyncio.sleep(1)
                continue
            try:
                # 执行监控逻辑
                await automation.run_chat_monitor_cycle()
                await ws_manager.broadcast({"type": "monitor_tick"})
            except Exception as e:
                print(f"[监控] 错误: {e}")
            await asyncio.sleep(30)


# 全局监控器实例
chat_monitor = ChatMonitor()
```

- [ ] **Step 2: 提交代码**

```bash
git add boss_app/core/monitor.py
git commit -m "refactor: extract chat monitor module"
```

---

## Task 4: 提取投递记录数据层

**Files:**
- Create: `boss_app/models/__init__.py`
- Create: `boss_app/models/application.py`

- [ ] **Step 1: 创建 models/__init__.py**

```python
"""数据模型模块"""
```

- [ ] **Step 2: 创建 models/application.py**

从 `boss_state.py` 提取投递记录相关函数：

```python
"""投递记录数据层"""
from datetime import datetime
from typing import Optional, List
from ..core.database import get_db


def compute_dedup_key(job: dict) -> str:
    """计算去重键"""
    company = (job.get("company") or "").strip().lower()
    title = (job.get("title") or job.get("job_title") or "").strip().lower()
    city = (job.get("city") or "").strip().lower()
    salary = (job.get("salary") or "").strip().lower()
    if not company and not title:
        return ""
    return f"{company}|{title}|{city}|{salary}"


def get_application_by_dedup_key(key: str) -> Optional[dict]:
    """通过去重键查询投递记录"""
    if not key:
        return None
    db = get_db()
    row = db.execute(
        "SELECT * FROM applications WHERE dedup_key=? AND deleted_at IS NULL",
        (key,)
    ).fetchone()
    return dict(row) if row else None


def add_application(job: dict) -> int:
    """添加投递记录，返回 ID（0 表示重复）"""
    db = get_db()
    dedup_key = compute_dedup_key(job)

    # 先用 dedup_key 查重
    if dedup_key:
        existing = get_application_by_dedup_key(dedup_key)
        if existing:
            update_application_from_job(existing["id"], job)
            return 0

    # 再用 URL 查重
    url = job.get("url") or job.get("job_url") or ""
    if url:
        existing = get_application_by_url(url)
        if existing:
            update_application_from_job(existing["id"], job)
            return 0

    # 插入新记录
    cursor = db.execute(
        """INSERT INTO applications
           (job_title, company, salary, job_url, city, experience, education,
            hr_name, hr_title, description, dedup_key)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            job.get("title") or job.get("job_title") or "",
            job.get("company") or "",
            job.get("salary") or "",
            url,
            job.get("city") or "",
            job.get("experience") or "",
            job.get("education") or "",
            job.get("hr_name") or "",
            job.get("hr_title") or "",
            job.get("description") or "",
            dedup_key,
        )
    )
    db.commit()
    return cursor.lastrowid


# ... 其他投递记录相关函数
```

- [ ] **Step 3: 提交代码**

```bash
git add boss_app/models/
git commit -m "refactor: extract application data layer"
```

---

## Task 5: 提取会话和消息数据层

**Files:**
- Create: `boss_app/models/conversation.py`
- Create: `boss_app/models/message.py`

- [ ] **Step 1: 创建 models/conversation.py**

从 `boss_state.py` 提取会话相关函数：

```python
"""会话数据层"""
from typing import Optional, List
from ..core.database import get_db


def get_or_create_conversation(application_id: int, hr_name: str, hr_company: str, job_title: str) -> int:
    """获取或创建会话"""
    db = get_db()
    row = db.execute(
        "SELECT id FROM conversations WHERE application_id=? AND hr_name=?",
        (application_id, hr_name)
    ).fetchone()
    if row:
        return row[0]
    cursor = db.execute(
        """INSERT INTO conversations (application_id, hr_name, hr_company, job_title)
           VALUES (?, ?, ?, ?)""",
        (application_id, hr_name, hr_company, job_title)
    )
    db.commit()
    return cursor.lastrowid


# ... 其他会话相关函数
```

- [ ] **Step 2: 创建 models/message.py**

从 `boss_state.py` 提取消息相关函数：

```python
"""消息数据层"""
from typing import Optional, List
from ..core.database import get_db


def add_message(conversation_id: int, sender: str, content: str,
                delivery_status: str = None, ai_generated: bool = False) -> int:
    """添加消息"""
    db = get_db()
    cursor = db.execute(
        """INSERT INTO messages (conversation_id, sender, content, delivery_status, ai_generated)
           VALUES (?, ?, ?, ?, ?)""",
        (conversation_id, sender, content, delivery_status, 1 if ai_generated else 0)
    )
    db.commit()
    return cursor.lastrowid


# ... 其他消息相关函数
```

- [ ] **Step 3: 提交代码**

```bash
git add boss_app/models/
git commit -m "refactor: extract conversation and message data layers"
```

---

## Task 6: 提取设置数据层

**Files:**
- Create: `boss_app/models/settings.py`

- [ ] **Step 1: 创建 models/settings.py**

从 `boss_state.py` 提取设置相关函数：

```python
"""设置数据层"""
from datetime import date
from typing import Optional, List, Dict
from ..core.database import get_db


def get_setting(key: str, default: str = "") -> str:
    """获取设置值"""
    db = get_db()
    row = db.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row[0] if row else default


def set_setting(key: str, value: str):
    """设置配置值"""
    db = get_db()
    db.execute(
        "INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
        (key, value)
    )
    db.commit()


def get_all_settings() -> dict:
    """获取所有设置"""
    db = get_db()
    rows = db.execute("SELECT key, value FROM settings").fetchall()
    return {row[0]: row[1] for row in rows}


def get_daily_stats(date_str: str = None) -> dict:
    """获取每日统计"""
    if date_str is None:
        date_str = str(date.today())
    db = get_db()
    row = db.execute("SELECT * FROM daily_stats WHERE date=?", (date_str,)).fetchone()
    if row:
        return dict(row)
    return {
        "date": date_str,
        "applications_sent": 0,
        "messages_sent": 0,
        "messages_received": 0,
        "auto_replies_sent": 0,
    }


def increment_daily_stat(field: str, amount: int = 1):
    """增加每日统计"""
    _ALLOWED_FIELDS = {"applications_sent", "messages_sent", "messages_received", "auto_replies_sent"}
    if field not in _ALLOWED_FIELDS:
        raise ValueError(f"Invalid stat field: {field}")
    db = get_db()
    today = str(date.today())
    db.execute(
        f"INSERT INTO daily_stats (date, {field}) VALUES (?, ?) ON CONFLICT(date) DO UPDATE SET {field} = {field} + ?",
        (today, amount, amount)
    )
    db.commit()
```

- [ ] **Step 2: 提交代码**

```bash
git add boss_app/models/settings.py
git commit -m "refactor: extract settings data layer"
```

---

## Task 7: 创建向后兼容的数据层入口

**Files:**
- Modify: `boss_state.py`

- [ ] **Step 1: 更新 boss_state.py 为代理入口**

```python
"""向后兼容入口 - 实际逻辑已迁移到 boss_app/models/"""
from boss_app.core.database import get_db, init_db
from boss_app.models.application import *
from boss_app.models.conversation import *
from boss_app.models.message import *
from boss_app.models.settings import *

# 保持原有导入路径不变
__all__ = [
    "get_db", "init_db",
    "compute_dedup_key", "get_application_by_dedup_key", "add_application",
    # ... 其他导出
]
```

- [ ] **Step 2: 验证导入正常**

```bash
python -c "from boss_state import get_db, init_db; print('OK')"
```

- [ ] **Step 3: 提交代码**

```bash
git add boss_state.py
git commit -m "refactor: make boss_state.py a backward-compatible proxy"
```

---

## Task 8: 提取服务层

**Files:**
- Create: `boss_app/services/__init__.py`
- Create: `boss_app/services/scraper.py`
- Create: `boss_app/services/automation.py`
- Create: `boss_app/services/replier.py`

- [ ] **Step 1: 创建 services/__init__.py**

```python
"""服务层模块"""
```

- [ ] **Step 2: 创建 services/scraper.py**

从 `boss_firefox.py` 提取 `BossScraper` 类：

```python
"""爬虫基类"""
# 将 BossScraper 类完整迁移到此处
# 保持原有功能不变
```

- [ ] **Step 3: 创建 services/automation.py**

从 `boss_automation.py` 提取 `BossAutomation` 类：

```python
"""自动化服务"""
from .scraper import BossScraper
# 将 BossAutomation 类完整迁移到此处
# 保持原有功能不变
```

- [ ] **Step 4: 创建 services/replier.py**

从 `boss_replier.py` 提取 AI 回复逻辑：

```python
"""AI 回复生成"""
# 将 boss_replier.py 内容完整迁移到此处
# 保持原有功能不变
```

- [ ] **Step 5: 更新原有文件为代理入口**

```python
# boss_firefox.py（重构后）
"""向后兼容入口"""
from boss_app.services.scraper import BossScraper
```

```python
# boss_automation.py（重构后）
"""向后兼容入口"""
from boss_app.services.automation import BossAutomation
```

```python
# boss_replier.py（重构后）
"""向后兼容入口"""
from boss_app.services.replier import *
```

- [ ] **Step 6: 提交代码**

```bash
git add boss_app/services/ boss_firefox.py boss_automation.py boss_replier.py
git commit -m "refactor: extract service layer modules"
```

---

## Task 9: 提取路由层

**Files:**
- Create: `boss_app/routes/__init__.py`
- Create: `boss_app/routes/jobs.py`
- Create: `boss_app/routes/conversations.py`
- Create: `boss_app/routes/settings.py`
- Create: `boss_app/routes/system.py`
- Create: `boss_app/routes/debug.py`

- [ ] **Step 1: 创建 routes/__init__.py**

```python
"""路由模块"""
from fastapi import APIRouter

router = APIRouter()

from . import jobs, conversations, settings, system, debug

router.include_router(jobs.router, prefix="/api", tags=["jobs"])
router.include_router(conversations.router, prefix="/api", tags=["conversations"])
router.include_router(settings.router, prefix="/api", tags=["settings"])
router.include_router(system.router, prefix="/api", tags=["system"])
router.include_router(debug.router, prefix="/api", tags=["debug"])
```

- [ ] **Step 2: 创建 routes/jobs.py**

从 `boss_app.py` 提取职位相关 API：

```python
"""职位相关 API"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

router = APIRouter()


class SearchRequest(BaseModel):
    keyword: str
    city: Optional[str] = None
    experience: Optional[str] = None
    education: Optional[str] = None
    salary: Optional[str] = None


@router.get("/jobs")
def list_jobs(status: Optional[str] = None, limit: int = 100):
    """获取职位列表"""
    # ... 实现
    pass


@router.post("/jobs/search")
async def search_jobs(req: SearchRequest):
    """搜索职位"""
    # ... 实现
    pass


# ... 其他职位相关端点
```

- [ ] **Step 3: 创建 routes/conversations.py**

从 `boss_app.py` 提取会话相关 API：

```python
"""会话相关 API"""
from fastapi import APIRouter
from typing import Optional

router = APIRouter()


@router.get("/conversations")
def list_conversations():
    """获取会话列表"""
    # ... 实现
    pass


# ... 其他会话相关端点
```

- [ ] **Step 4: 创建其他路由模块**

类似地创建 `settings.py`、`system.py`、`debug.py`

- [ ] **Step 5: 提交代码**

```bash
git add boss_app/routes/
git commit -m "refactor: extract route modules"
```

---

## Task 10: 创建应用入口

**Files:**
- Create: `boss_app/main.py`
- Create: `boss_app/config.py`
- Create: `run.py`

- [ ] **Step 1: 创建 boss_app/config.py**

从 `boss_app.py` 提取配置常量：

```python
"""配置常量"""
# BOSS直聘城市代码
CITY_MAP = {
    "济南": "101120100",
    "青岛": "101120200",
    # ... 其他城市
    "北京": "101010100",
    "上海": "101020100",
    # ...
}
```

- [ ] **Step 2: 创建 boss_app/main.py**

整合 FastAPI 应用：

```python
"""FastAPI 应用入口"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from .routes import router
from .core.database import init_db
from .core.websocket import ws_manager
from .core.monitor import chat_monitor

app = FastAPI(title="BOSS直聘自动化控制台", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

static_dir = Path(__file__).parent.parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

app.include_router(router)


@app.on_event("startup")
async def on_startup():
    """应用启动事件"""
    init_db()
    # ... 其他启动逻辑
```

- [ ] **Step 3: 创建 run.py**

```python
"""启动入口"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run("boss_app.main:app", host="127.0.0.1", port=8010, reload=True)
```

- [ ] **Step 4: 更新 boss_app.py 为代理入口**

```python
"""向后兼容入口"""
from boss_app.main import app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8010)
```

- [ ] **Step 5: 提交代码**

```bash
git add boss_app/main.py boss_app/config.py run.py boss_app.py
git commit -m "refactor: create main app entry and backward-compatible proxy"
```

---

## Task 11: 验证和测试

- [ ] **Step 1: 验证所有导入正常**

```bash
python -c "from boss_app.main import app; print('App loaded OK')"
python -c "from boss_state import get_db; print('State proxy OK')"
python -c "from boss_automation import BossAutomation; print('Automation proxy OK')"
```

- [ ] **Step 2: 启动服务测试**

```bash
python run.py
# 或
python boss_app.py
```

- [ ] **Step 3: 测试 API 端点**

```bash
curl http://127.0.0.1:8010/api/health
curl http://127.0.0.1:8010/api/status
```

- [ ] **Step 4: 运行现有测试**

```bash
python -m pytest tests/ -v
```

- [ ] **Step 5: 最终提交**

```bash
git add .
git commit -m "refactor: complete architecture refactoring with backward compatibility"
```

---

## 验证清单

- [ ] 所有模块导入正常
- [ ] 新入口 `run.py` 可启动服务
- [ ] 旧入口 `boss_app.py` 可启动服务
- [ ] 所有 API 端点正常工作
- [ ] WebSocket 连接正常
- [ ] 数据库操作正常
- [ ] 现有测试全部通过
- [ ] 无循环导入问题
