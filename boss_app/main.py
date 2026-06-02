"""FastAPI 应用入口"""
import asyncio
import json
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from .routes.jobs import router as jobs_router
from .routes.conversations import router as conversations_router
from .routes.settings import router as settings_router
from .routes.system import router as system_router
from .routes.debug import router as debug_router
from .core.websocket import ws_manager
from .core.monitor import chat_monitor
from .core.database import get_db, init_db
from .core import state
from boss_state import (
    reconcile_application_stats,
    deduplicate_applications,
    compute_dedup_key,
)

# ── FastAPI 应用 ──
app = FastAPI(title="BOSS直聘自动化控制台", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

static_dir = Path(__file__).parent.parent / "static"
static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Include routers
app.include_router(jobs_router)
app.include_router(conversations_router)
app.include_router(settings_router)
app.include_router(system_router)
app.include_router(debug_router)

# 初始化数据库
init_db()


@app.on_event("startup")
async def on_startup():
    state.browser_sync_lock = asyncio.Lock()
    # 数据一致性修复：applied 但 greeting_sent_at 为空的记录
    try:
        fixed = reconcile_application_stats()
        if fixed:
            print(f"[启动] 数据修复: {fixed} 条投递记录补全了时间戳")
    except Exception as e:
        print(f"[启动] 数据修复失败: {e}")
    # 补填 dedup_key（兼容旧数据）+ 清理历史重复
    try:
        db2 = get_db()
        missing = db2.execute(
            "SELECT id, job_title, company, city, salary FROM applications WHERE (dedup_key IS NULL OR dedup_key='') AND deleted_at IS NULL"
        ).fetchall()
        for row in missing:
            key = compute_dedup_key({"title": row[1], "company": row[2], "city": row[3], "salary": row[4]})
            if key:
                db2.execute("UPDATE applications SET dedup_key=? WHERE id=?", (key, row[0]))
        if missing:
            db2.commit()
            print(f"[启动] 补填 dedup_key: {len(missing)} 条记录")
        dup_result = deduplicate_applications()
        if dup_result.get("duplicates_removed", 0) > 0:
            print(f"[启动] 清理重复岗位: {dup_result['duplicates_removed']} 条")
    except Exception as e:
        print(f"[启动] dedup初始化失败: {e}")
    # 清理旧垃圾会话 + 合并同名重复会话
    try:
        db = get_db()
        junk_names = ["HR", "你好", "消息", "未知HR", "AI简历", "简历更新", "附件简历制作", "附件上传"]
        for name in junk_names:
            db.execute("DELETE FROM conversations WHERE hr_name = ?", (name,))
        db.execute("DELETE FROM conversations WHERE hr_name IS NULL OR length(hr_name) < 2")
        db.execute("""
            UPDATE conversations SET status = 'closed'
            WHERE id NOT IN (
                SELECT MIN(id) FROM conversations WHERE status != 'closed' GROUP BY hr_name
            ) AND status != 'closed'
        """)
        db.commit()
    except Exception as e:
        print(f"[启动] 会话清理失败: {e}")
    print(f"\n🚀 BOSS直聘自动化控制台: http://127.0.0.1:8010")


@app.get("/", response_class=HTMLResponse)
def index():
    index_path = static_dir / "dashboard.html"
    if index_path.exists():
        return index_path.read_text(encoding="utf-8")
    return "<h1>Dashboard not found</h1>"


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)
