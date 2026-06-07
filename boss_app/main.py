"""FastAPI 应用入口"""
import asyncio
import json
import secrets
import sys
from pathlib import Path

# Windows 兼容性：设置事件循环策略以支持 Playwright 子进程
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from .routes.jobs import router as jobs_router
from .routes.conversations import router as conversations_router
from .routes.settings import router as settings_router
from .routes.system import router as system_router
from .routes.debug import router as debug_router
from .routes.agents import router as agents_router
from .core.websocket import ws_manager
from .core.scheduler import auto_scheduler
from .core.database import get_db, init_db
from .core import state
from boss_app.models.application import (
    reconcile_application_stats,
    deduplicate_applications,
    compute_dedup_key,
)

# ── FastAPI 应用 ──
app = FastAPI(title="BOSS直聘自动化控制台", version="2.0.0")

# ── API 认证 Token ──
API_TOKEN_FILE = Path(__file__).parent.parent / ".boss_profile" / ".api_token"
API_TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
if API_TOKEN_FILE.exists():
    API_TOKEN = API_TOKEN_FILE.read_text(encoding="utf-8").strip()
else:
    API_TOKEN = secrets.token_urlsafe(32)
    API_TOKEN_FILE.write_text(API_TOKEN, encoding="utf-8")

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


_PUBLIC_PATHS = {"/", "/ws", "/api/health"}
_PUBLIC_PREFIXES = ("/static",)


class AuthMiddleware(BaseHTTPMiddleware):
    """API 接口认证中间件：所有 /api/* 请求需要携带有效 Token。"""
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path in _PUBLIC_PATHS or path.startswith(_PUBLIC_PREFIXES):
            return await call_next(request)
        if path.startswith("/api/"):
            auth = request.headers.get("Authorization", "")
            if auth.startswith("Bearer ") and secrets.compare_digest(auth[7:], API_TOKEN):
                return await call_next(request)
            # 也支持 query 参数传 token（用于 SSE 等场景）
            if secrets.compare_digest(request.query_params.get("token", ""), API_TOKEN):
                return await call_next(request)
            return JSONResponse({"error": "未授权访问，请在设置中配置 API Token"}, status_code=401)
        return await call_next(request)


app.add_middleware(AuthMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8010", "http://localhost:8010"],
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
app.include_router(agents_router)

# 初始化数据库
init_db()


@app.on_event("startup")
async def on_startup():
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
            def _s(v):
                if v is None:
                    return ""
                if isinstance(v, (list, tuple)):
                    return ",".join(str(x) for x in v)
                return str(v)
            key = compute_dedup_key({
                "title": _s(row[1]),
                "company": _s(row[2]),
                "city": _s(row[3]),
                "salary": _s(row[4]),
            })
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
    # 自动清理超过7天的回收站
    try:
        from .models.application import purge_old_trashes
        purged = purge_old_trashes(7)
        if purged > 0:
            print(f"[启动] 清理回收站: {purged} 条过期记录")
    except Exception as e:
        print(f"[启动] 回收站清理失败: {e}")
    # 启动定时调度器（如果已启用）
    try:
        from .models.settings import get_setting
        if get_setting("auto_schedule_enabled", "false") == "true":
            auto_scheduler.start(state.automation, ws_manager)
            print("[启动] 定时调度器已启动")
    except Exception as e:
        print(f"[启动] 调度器启动失败: {e}")
    # 初始化 Agent 系统
    try:
        from .agents import orchestrator, SearchAgent, ScorerAgent, ChatAgent, ApplyAgent, ResumeAgent
        orchestrator.register(SearchAgent(orchestrator))
        orchestrator.register(ScorerAgent(orchestrator))
        orchestrator.register(ChatAgent(orchestrator))
        orchestrator.register(ApplyAgent(orchestrator))
        orchestrator.register(ResumeAgent(orchestrator))
        # 从数据库加载 Agent Profile 覆盖默认值
        try:
            from .agents.profiles import AgentProfile
            from .core.database import get_all_agent_profiles
            overrides = get_all_agent_profiles()
            for name, profile_dict in overrides.items():
                agent = orchestrator.agents.get(name)
                if agent:
                    agent.profile = AgentProfile.from_dict(profile_dict)
                    print(f"  [Profile] {name}: 已加载自定义配置")
        except Exception as e:
            print(f"  [Profile] 加载自定义配置失败: {e}")
        await orchestrator.start_all()
        print(f"[启动] Agent 系统: {len(orchestrator.agents)} 个 Agent 已就绪")
    except Exception as e:
        print(f"[启动] Agent 系统初始化失败: {e}")
    print(f"\n[启动] BOSS直聘自动化控制台: http://127.0.0.1:8010")
    print(f"   API Token: {API_TOKEN[:6]}****")
    print(f"   Token 文件: {API_TOKEN_FILE}")


@app.get("/", response_class=HTMLResponse)
def index():
    index_path = static_dir / "dashboard.html"
    if index_path.exists():
        from fastapi.responses import Response
        content = index_path.read_text(encoding="utf-8")
        # 将 Token 直接注入 HTML，避免暴露 /api/auth/token 端点
        import json as _json
        inject = f"<script>window.__API_TOKEN__={_json.dumps(API_TOKEN)};</script>"
        content = content.replace("</head>", inject + "</head>", 1)
        return Response(
            content=content,
            media_type="text/html",
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
        )
    return "<h1>Dashboard not found</h1>"


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    # WebSocket 认证：验证 token query 参数
    token = websocket.query_params.get("token", "")
    if not token or not secrets.compare_digest(token, API_TOKEN):
        await websocket.close(code=4001, reason="未授权")
        return
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
