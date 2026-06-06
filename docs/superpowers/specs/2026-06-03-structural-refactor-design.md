# 结构重构设计（A 子项目）

**日期**：2026-06-03
**作者**：通过 superpowers brainstorming skill 与维护者协作产出
**目标范围**：仅 A 子项目（结构重构）。B（可靠性/可观测性）、C（性能）、D（前端 UX）作为后续独立 spec。

---

## 1. 背景

`lakejobai-job-radar` 当前结构上有几处明显的债：

- `boss_app/routes/jobs.py` 1293 行单文件，承担搜索/评分/投递/回收站/候选池/跟进/去重 7 类职责。
- `_fetch_details_and_score` 与 `search_jobs` 内联管线几乎是同一段「抓详情 → HR 过滤 → 评分」逻辑写了两遍；`_score_and_check_jobs` 已成死代码。
- 4 处「`acquire / wait_for / try-finally release`」浏览器锁模板代码重复。
- 项目根目录还残留 6 个脚本（`boss_app.py` 替代入口、`boss_automation.py` / `boss_firefox.py` / `boss_replier.py` 是纯 proxy `from boss_app... import *`、`boss_state.py` 部分 proxy + 候选池真代码与一个 `init_db()` 副作用、`scraper.py` 571 行独立旧脚本）。`boss_app/routes/jobs.py` 仍 `from boss_replier import generate_greeting` 与 `from boss_state import add_to_shortlist, remove_from_shortlist, list_shortlists, is_in_shortlist`，`boss_app/main.py` 仍 `from boss_state import reconcile_application_stats, deduplicate_applications, compute_dedup_key`。
- 仓库无 `tests/` 目录，重构时无回归网。

近期 `FIXES_SUMMARY.md` 解决了若干高/中优先级 bug，但结构性问题没动。在做可观测性/性能/前端之前，先把结构理顺，能让后续每一项改动都更安全。

## 2. 目标 / 非目标

### 目标

- `boss_app/routes/jobs.py` 拆为 `boss_app/routes/jobs/` 包，按职责分 7 个子模块，单文件不超过 ~250 行。
- 抽出唯一的 `boss_app/services/pipeline.py`，统一「详情抓取 → 评分 → 自动投递」三阶段流程；调用方仅一行 `await run_pipeline(...)`。
- 抽出 `boss_app/core/locks.py` 的 `browser_lock(timeout=...)` 上下文管理器，替换 4 处重复模板。
- 把根目录残留旧脚本里仍被引用的函数迁入 `boss_app/services/replier.py` 与 `boss_app/models/shortlist.py`；删除根目录 6 个旧脚本。
- 引入 `tests/` 工程（pytest），覆盖纯函数 helper 与 pipeline 三阶段流转，作为回归网。

### 非目标（显式不做，避免范围蔓延）

- 不动 `services/automation.py`、`services/scraper.py` 内部逻辑（C 子项目处理）。
- 不替换 `print` 为 `logging`、不加结构化日志/指标（B 子项目）。
- 不调整 LLM 评分并发/缓存/超时（C 子项目）。
- 不改任何 API 路径、请求/响应字段、HTTP 状态码、WebSocket 事件名/字段。
- 不动数据库 schema 或迁移。
- 不动前端 `static/dashboard.html`（D 子项目）。
- 不动 `lakejob_cli/`、`interview/`。

## 3. 目标文件结构

```
boss_app/
├── __init__.py
├── main.py                       # 不变
├── config.py
├── core/
│   ├── database.py
│   ├── monitor.py
│   ├── scheduler.py              # 改：调用 services.pipeline
│   ├── state.py
│   ├── websocket.py
│   └── locks.py                  # 新：browser_lock 上下文管理器
├── routes/
│   ├── conversations.py
│   ├── debug.py
│   ├── settings.py
│   ├── system.py
│   └── jobs/                     # 新：从 1293 行拆为 8 个文件
│       ├── __init__.py           # 聚合 7 个 sub-router 暴露 router
│       ├── _common.py            # CITY_MAP / Pydantic models / helpers
│       ├── search.py             # /api/jobs/search /scan /refetch
│       ├── lifecycle.py          # /api/jobs(list) /{id} /{id}/skip /{id}/score
│       ├── apply.py              # /api/jobs/apply /apply-batch /scan-and-apply
│       │                         # /api/jobs/analyze /auto-apply-logs /auto-apply/trigger
│       ├── trash.py              # /api/jobs/delete /clear /trash/* /delete-logs
│       ├── shortlist.py          # /api/shortlists/*
│       ├── followup.py           # /api/followups/*
│       └── dedup.py              # /api/jobs/deduplicate /dedup-stats
├── services/
│   ├── automation.py             # 不动
│   ├── replier.py                # 扩展：吸收 boss_replier.py:generate_greeting
│   ├── scorer.py                 # 不动
│   ├── scraper.py                # 不动
│   └── pipeline.py               # 新：detail+score+apply 统一管线
└── models/
    ├── application.py
    ├── conversation.py
    ├── followup.py
    ├── message.py
    ├── settings.py
    └── shortlist.py              # 新：吸收 boss_state.py 的导出函数
tests/                            # 新
├── conftest.py
├── test_dedup_key.py
├── test_score_helpers.py
├── test_intent_match.py
├── test_scheduler_cron.py
└── test_pipeline_phases.py
```

**预计删除**（迁移完毕后）：根目录 `scraper.py`、`boss_app.py`、`boss_automation.py`、`boss_firefox.py`、`boss_replier.py`、`boss_state.py` 共 6 个文件。

**命名约定**：

- `routes/jobs/` 是包；对外仍是 `from boss_app.routes.jobs import router`。
- 子模块之间不互相 import，共享内容只放 `_common.py`。
- `pipeline` 不 import `routes`。

## 4. 核心抽象

### 4.1 `services/pipeline.py`

唯一入口：

```python
@dataclass
class PipelineResult:
    detail_ok: int       # 详情抓取成功数
    detail_failed: int
    filtered: int        # HR 不活跃过滤数
    scored: int          # CV 评分成功数
    applied: int         # 自动投递成功数

async def run_pipeline(
    new_ids: list[int],
    *,
    fetch_detail: bool = True,
    score: bool = True,
    auto_apply: bool = True,
    ws=None,
) -> PipelineResult: ...
```

**三阶段顺序**（与现有行为一致）：

1. `_phase_fetch_detail`：逐岗位 `async with browser_lock(timeout=30)` 抓详情 → 写 description/hr_name/hr_title/hr_activity → HR 不活跃软删（依据 `is_hr_inactive` 与 `filter_inactive_hr` 设置）。
2. `_phase_score`：通过 `asyncio.to_thread` 跑 CV/quality LLM、合法性、HR 活跃度，最后 `compute_composite_score` 入库。单条异常使用现有保守默认值（CV=30、quality=40、legitimacy=unknown）。
3. `_phase_auto_apply`：仅当 `auto_apply=True` 且 `auto_apply_enabled` 设置为 `true` 时执行。逻辑等价于现有 `_execute_auto_apply`：阈值过滤 → 意向匹配过滤 → 30-90 秒随机延迟逐个投递。

**调用方改造**：

- `routes/jobs/search.py:search_jobs`：搜索拿到 `new_ids` 后调 `await run_pipeline(new_ids, ws=ws_manager)`。
- `routes/jobs/search.py:scan_current_page`：保留原「后台 task」结构，task 内部一行 `await run_pipeline(new_ids, ws=ws_manager)`。
- `core/scheduler.py:_execute`：去掉 `from ..routes.jobs import _fetch_details_and_score`，改为 `from ..services.pipeline import run_pipeline`，并接收 `PipelineResult` 写入 `result["scored"]` 与 `result["applied"]`。

**事件契约**：`run_pipeline` 内部按现有事件名/字段广播 `score_complete`、`auto_apply_complete`、`auto_apply_batch_complete`，不变更 payload。

### 4.2 `core/locks.py`

```python
class BrowserLockTimeout(Exception):
    """browser_lock 范围内的协程超时。"""

@asynccontextmanager
async def browser_lock(timeout: float | None = None):
    """获取浏览器互斥锁。timeout 仅施加在 yield 出去的代码块上，不施加在 acquire 上。

    用法：
        async with browser_lock(timeout=30):
            await automation.fetch_detail(url)

    超时抛 BrowserLockTimeout；锁在退出时一定释放（正常/取消/异常）。
    """
    await state.browser_sync_lock.acquire()
    try:
        if timeout is None:
            yield
        else:
            async with asyncio.timeout(timeout):
                yield
    except asyncio.TimeoutError as e:
        raise BrowserLockTimeout(
            f"browser lock body timed out after {timeout}s"
        ) from e
    finally:
        state.browser_sync_lock.release()
```

**Python 版本依赖**：`asyncio.timeout` 需要 Python ≥ 3.11。`pyproject.toml` 当前 `requires-python = ">=3.10"`，本轮选 **不抬升 Python 下限**，使用 `await asyncio.wait_for(asyncio.shield(coro_or_task), timeout)` 等价封装；具体写法在 plan 中给出代码块。

**调用点替换**：4 处 12 行模板 → 2 行 `async with`。

### 4.3 模块迁移

- `services/replier.py`：从 `boss_replier.py` 迁入 `generate_greeting`。其它导出在执行阶段 4 grep 后再决定。
- `models/shortlist.py`：从 `boss_state.py` 迁入 `add_to_shortlist / remove_from_shortlist / list_shortlists / is_in_shortlist / compute_dedup_key / reconcile_application_stats / deduplicate_applications`。本轮**只换文件位置不改函数体**；跨模块归属调整（如 `compute_dedup_key` 是否更适合 `models/application.py`）留给后续 spec。

## 5. 执行阶段

每阶段独立可提交可回滚。任一阶段结束时仓库都能跑、`pytest` 全绿。

### 阶段 1：建 safety net（不动业务代码）

- 新增 `tests/conftest.py`：内存 SQLite + 临时目录 fixture。
- 新增以下 4 个测试文件，覆盖纯函数：
  - `tests/test_dedup_key.py` → `compute_dedup_key`
  - `tests/test_score_helpers.py` → `compute_composite_score`、`score_hr_activity`、`is_hr_inactive`
  - `tests/test_intent_match.py` → `_matches_search_intent`
  - `tests/test_scheduler_cron.py` → `_parse_cron_times`、`_compute_next_run`、`_should_run_now`
- `pyproject.toml` 加 pytest 配置；`requirements.txt` 加 `pytest>=8.0`。
- `pytest -q` 全绿后打 tag `refactor-A-stage1`。

### 阶段 2：抽象提取（不挪文件）

- 新增 `boss_app/core/locks.py`，替换 4 处模板。
- 新增 `boss_app/services/pipeline.py`，把 `_fetch_details_and_score` 改为薄壳调 `run_pipeline`；`search_jobs` 内联管线段也改调 `run_pipeline`。
- 改 `core/scheduler.py:_execute` 直接 `from ..services.pipeline import run_pipeline`。
- 删除死代码 `_score_and_check_jobs`。
- 新增 `tests/test_pipeline_phases.py`：用 monkeypatch 替换 `state.automation.fetch_detail`、`scorer.score_job`、`scorer.score_job_quality`、`scorer.check_legitimacy` 为 fake，验证三阶段流转、单条异常容错、`PipelineResult` 计数、WebSocket 事件名/字段。
- `pytest -q` 全绿后打 tag `refactor-A-stage2`。

### 阶段 3：路由按职责拆分

- 创建 `routes/jobs/__init__.py`，聚合 7 个 sub-router。
- 创建 `routes/jobs/_common.py`、`search.py`、`lifecycle.py`、`apply.py`、`trash.py`、`dedup.py`、`shortlist.py`、`followup.py`，逐个独立提交。
- 删除原 `routes/jobs.py`。
- 路由顺序约束：`lifecycle.py` 的 `/api/jobs/{job_id}` 必须在 `search.py` 的 `/api/jobs/refetch` 等具体路径之后 include，避免动态路径抢先匹配。
- `pytest -q` + 启动 `uvicorn` 后做 smoke：`/api/jobs/refetch`、`/api/jobs/search`、`/api/jobs/scan` 路径全部可路由（具体行为可能因为浏览器未启动返 503/401，但不能是 404）。
- 打 tag `refactor-A-stage3`。

### 阶段 4：迁移并删除根目录脚本

- 创建 `boss_app/models/shortlist.py`，迁入 7 个函数（保持函数签名不变）。
- 扩展 `boss_app/services/replier.py` 接收 `generate_greeting`。
- 改全部 import：`routes/jobs/_common.py`、`routes/jobs/shortlist.py`、`main.py`、`apply.py` 等。
- grep 验证：`grep -rE "from (boss_state|boss_replier)|^import (boss_state|boss_replier|scraper)\\b"` 全仓无残留。
- 删除根目录 `scraper.py`、`boss_app.py`、`boss_automation.py`、`boss_firefox.py`、`boss_replier.py`、`boss_state.py`。
- `pytest -q` + 手工跑 `lakejob doctor` / `schema` / 浏览器登录 / 一轮搜索-评分-投递闭环。
- 打 tag `refactor-A-stage4`。

预计总 commit 数 ~22。

## 6. 风险与回退

| # | 风险 | 缓解 | 回退 |
|---|---|---|---|
| 1 | `boss_state.py` 还有未知引用 | 阶段 4.3 前 grep 全仓 | 单 commit revert |
| 2 | `pipeline` 与原内联管线行为偏差（事件名/字段） | 测试断言事件序列；事件名严格复刻 | 单 commit revert |
| 3 | `asyncio.timeout` 在 3.10 不可用 | 阶段 2.1 前先确认 `python_requires`，按版本写死 | 在 plan 阶段定稿 |
| 4 | 路由顺序导致 `/api/jobs/{id}` 抢先匹配具体路径 | `lifecycle.py` 最后 include；smoke 测试断言 | 单 commit revert |
| 5 | 子模块循环 import | 共享内容只在 `_common.py`；`pipeline` 不 import `routes` | 把违规 import 挪到 `_common.py` |
| 6 | LLM/浏览器 fake 漏盖路径 | conftest 默认替换；调用真 LLM 报错 | 收紧 fixture |
| 7 | `on_startup` 数据修复函数迁移后行为变化 | 只换文件位置不改函数体 | 单 commit revert |

**整体回退**：每阶段打 tag；非阶段内可定位回归 → `git reset --hard refactor-A-stageN`。

## 7. 验收标准

- `pytest -q` 全绿，至少覆盖：`compute_dedup_key`、`compute_composite_score`、`score_hr_activity`、`is_hr_inactive`、`_matches_search_intent`、`_parse_cron_times` 等 6 个纯函数 + pipeline 三阶段流转 + 异常容错 + 事件广播。
- `lakejob doctor` 返回 `ok=true`。
- `lakejob schema` 返回 12 个可用命令（与重构前一致）。
- 启动后端口 8010 可访问，Dashboard 加载正常。
- 走一遍 `搜索 → 抓详情 → 评分 → 自动投递`：行为、日志输出、WebSocket 事件序列与重构前一致。
- `boss_app/routes/jobs.py` 不再存在；`boss_app/routes/jobs/` 包下没有 > 250 行的文件。
- 根目录 6 个旧脚本均已删除；全仓不再有 `from boss_state` / `import boss_state` / `from boss_replier` / `import boss_replier` / `import scraper`（指根目录 scraper）的残留。

## 8. 后续 spec（不在本范围）

- B：结构化日志 + 指标 + 扩展测试覆盖（基于 A 的 pipeline 与 router 拆分）。
- C：详情抓取自适应延迟、LLM 并发与缓存、合法性快照复用。
- D：阈值默认值统一、自动投递日志分页/筛选、quality_score 维度展示、搜索进度细化。
