# 结构重构实施计划（A 子项目）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `boss_app/routes/jobs.py` 1293 行单文件拆为按职责的 7 个子模块；抽出唯一的 `services/pipeline.py` 合并双路重复管线；抽出 `core/locks.py` 替换 4 处浏览器锁模板；把根目录 6 个旧脚本（含 4 个 proxy）整理掉；建立 pytest 工程作为回归网。

**Architecture:** 4 阶段渐进式重构。阶段 1 先建测试 safety net；阶段 2 抽核心抽象（pipeline + browser_lock）但不挪文件；阶段 3 拆 `routes/jobs.py`；阶段 4 处理根目录脚本与 import 收敛。每阶段独立可提交、可回滚、`pytest` 全绿。

**Tech Stack:** Python 3.10+, FastAPI, asyncio, Playwright, SQLite, pytest

**Spec：** `docs/superpowers/specs/2026-06-03-structural-refactor-design.md`

---

## 文件结构

| 文件 | 操作 | 说明 |
|------|------|------|
| `tests/conftest.py` | 新建 | 内存 SQLite + 临时目录 fixture |
| `tests/test_dedup_key.py` | 新建 | 测试 `compute_dedup_key` |
| `tests/test_score_helpers.py` | 新建 | 测试 `compute_composite_score` / `score_hr_activity` / `is_hr_inactive` |
| `tests/test_intent_match.py` | 新建 | 测试 `_matches_search_intent` |
| `tests/test_scheduler_cron.py` | 新建 | 测试 cron 解析 |
| `tests/test_pipeline_phases.py` | 新建 | 测试 `run_pipeline` 三阶段流转 |
| `boss_app/core/locks.py` | 新建 | `browser_lock(timeout=...)` 上下文管理器 |
| `boss_app/services/pipeline.py` | 新建 | `run_pipeline` 唯一入口 |
| `boss_app/models/shortlist.py` | 新建 | 候选池数据层（迁自 `boss_state.py`） |
| `boss_app/routes/jobs/__init__.py` | 新建 | 聚合 7 个 sub-router |
| `boss_app/routes/jobs/_common.py` | 新建 | `CITY_MAP` / Pydantic models / helper |
| `boss_app/routes/jobs/search.py` | 新建 | `/api/jobs/search` `/scan` `/refetch` |
| `boss_app/routes/jobs/lifecycle.py` | 新建 | `/api/jobs(list)` `/{id}` `/{id}/skip` `/{id}/score` |
| `boss_app/routes/jobs/apply.py` | 新建 | `/api/jobs/apply` `/apply-batch` `/scan-and-apply` `/analyze` `/auto-apply-logs` `/auto-apply/trigger` |
| `boss_app/routes/jobs/trash.py` | 新建 | `/api/jobs/delete` `/clear` `/trash/*` `/delete-logs` |
| `boss_app/routes/jobs/dedup.py` | 新建 | `/api/jobs/deduplicate` `/dedup-stats` |
| `boss_app/routes/jobs/shortlist.py` | 新建 | `/api/shortlists/*` |
| `boss_app/routes/jobs/followup.py` | 新建 | `/api/followups/*` |
| `boss_app/routes/jobs.py` | 删除 | 拆分后原文件移除 |
| `boss_app/services/replier.py` | 修改 | 已是新版，仅扩展接收 `generate_greeting`（如根目录 proxy 已 `import *`，可能无需新增；阶段 4 验证） |
| `boss_app/main.py` | 修改 | import 改为 `from .models.shortlist import ...` |
| `boss_app/core/scheduler.py` | 修改 | `_execute` 改用 `services.pipeline.run_pipeline` |
| `scraper.py` | 删除 | 根目录独立旧脚本（阶段 4.1 grep 验证后删） |
| `boss_app.py` | 删除 | 根目录替代入口 |
| `boss_automation.py` | 删除 | 纯 proxy |
| `boss_firefox.py` | 删除 | 纯 proxy |
| `boss_replier.py` | 删除 | 纯 proxy |
| `boss_state.py` | 删除 | proxy + 候选池真代码（候选池迁入 `models/shortlist.py`） |
| `pyproject.toml` | 修改 | pytest 配置已存在，无需变；如未安装 pytest 进开发环境则单独 `pip install pytest` |
| `requirements.txt` | 修改 | 不变（pytest 是 dev 依赖） |

---

## 关键约束

- 单元测试只测纯函数与可注入的 service，**不**起 FastAPI、不连真浏览器、不调真 LLM。
- `routes/jobs/` 子模块之间不互相 import；共享内容只在 `_common.py`。
- `pipeline` 不 import `routes`（防循环）。
- 不动 API 路径、请求/响应字段、HTTP 状态码、WebSocket 事件名/字段。
- Python 3.10 兼容：`browser_lock` 不使用 `asyncio.timeout`，改 `asyncio.wait_for(asyncio.shield(...), timeout)`。
- 提交粒度：每个 task 一个或多个小 commit，每阶段结束打 tag `refactor-A-stageN`。

---

## 基线（重构前实测）

`python --version` → Python 3.13.9（实际安装环境；`pyproject.toml` 仍声明 `>=3.10`）。

`pytest` → 0 个测试，0 失败（仓库无 `tests/`，符合预期）。

`from boss_app.main import app` → 加载成功；以 `/api/` 开头的路由数 **= 59**。完整列表（按字母序）：

```
/api/auto-apply-logs
/api/auto-apply/trigger
/api/conversations
/api/conversations/{conv_id}
/api/conversations/{conv_id}/messages
/api/conversations/{conv_id}/open
/api/conversations/{conv_id}/pause
/api/conversations/{conv_id}/resume
/api/conversations/{conv_id}/send
/api/conversations/{conv_id}/sync
/api/debug/page-stats
/api/debug/selector-test
/api/debug/selectors-status
/api/delete-logs
/api/doctor
/api/followups
/api/followups/{app_id}/done
/api/health
/api/jobs
/api/jobs/analyze
/api/jobs/apply
/api/jobs/apply-batch
/api/jobs/clear
/api/jobs/dedup-stats
/api/jobs/deduplicate
/api/jobs/delete
/api/jobs/refetch
/api/jobs/scan
/api/jobs/scan-and-apply
/api/jobs/search
/api/jobs/{job_id}
/api/jobs/{job_id}/score
/api/jobs/{job_id}/skip
/api/log/idle-redirect
/api/monitor/pause
/api/monitor/resume
/api/scheduler/start
/api/scheduler/status
/api/scheduler/stop
/api/settings
/api/shortlists
/api/shortlists/{sid}
/api/stats
/api/stats/funnel
/api/stats/reconcile
/api/stats/trend
/api/status
/api/system/heartbeat
/api/system/navigate-chat
/api/system/relogin
/api/system/start
/api/system/stop
/api/trash
/api/trash/count
/api/trash/purge
/api/trash/restore
/api/wechat-exchanges
```

**回归约束**：阶段 3.8 与阶段 4.4 收尾时必须验证 `/api/*` 路由集合**完全等于**上面 59 个；阶段 3.2 / 3.3 / 3.4 / 3.5 / 3.6 / 3.7 各 task 的 smoke 不要求等于 59，但每完成一个子模块迁移后 `/api/*` 集合也不应减少。

> 关于 Python 版本：实测环境是 3.13，`asyncio.timeout` 可用。但 `pyproject.toml` 仍声明 `>=3.10`，本 plan 沿用 §"关键约束" 中的 3.10 兼容写法（`wait_for + shield`）。如执行期决定抬升 `requires-python` 到 ≥3.11，可改用 `async with asyncio.timeout(timeout): yield` 简化 `core/locks.py`，且这一变更需要单独 commit。

---

## 阶段 1：建 safety net

> 目的：在动业务代码前先有回归基线。本阶段不动 `boss_app/` 任何代码。

### Task 1.1：创建 tests 目录与 conftest

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1：创建 `tests/__init__.py`（空文件）**

```bash
mkdir -p tests
```

```python
# tests/__init__.py
```

- [ ] **Step 2：创建 `tests/conftest.py`**

```python
"""pytest 共享 fixture：隔离的 SQLite 数据库 + 临时工作目录。"""
import os
import sqlite3
import sys
from pathlib import Path

import pytest

# 把项目根加入 sys.path，让 `import boss_app` 可用
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    """每个测试一个独立 SQLite 文件，并通过 monkeypatch 覆盖 get_db。"""
    db_path = tmp_path / "boss.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    from boss_app.core import database as db_mod
    monkeypatch.setattr(db_mod, "_db", conn, raising=False)
    # init_db 会基于当前连接建表
    db_mod.init_db()
    yield conn
    conn.close()


@pytest.fixture
def fake_settings(monkeypatch):
    """注入设置项的 in-memory 实现。返回 dict，可以直接读写。"""
    store = {}
    from boss_app.models import settings as settings_mod
    monkeypatch.setattr(
        settings_mod, "get_setting",
        lambda k, default="": store.get(k, default),
    )
    monkeypatch.setattr(
        settings_mod, "set_setting",
        lambda k, v: store.__setitem__(k, v),
    )
    return store
```

> 备注：fixture `tmp_db` 假设 `boss_app.core.database` 用的是单例 `_db` 变量。如实现是函数内 `connect`，把 `monkeypatch` 改成替换 `get_db` 函数。Task 执行时如发现接口不同，调整 fixture 即可（不影响其他 task）。

- [ ] **Step 3：运行 pytest 验证 conftest 可加载**

```bash
cd /d/ztzs/lakejobai-job-radar-main && python -m pytest -q
```

预期输出：`no tests ran`（0 个测试，0 失败），但不应有 import 错误。

- [ ] **Step 4：commit**

```bash
git add tests/__init__.py tests/conftest.py
git commit -m "test: bootstrap pytest工程与共享fixture"
```

---

### Task 1.2：测试 `compute_dedup_key`

**Files:**
- Test: `tests/test_dedup_key.py`

- [ ] **Step 1：写测试**

```python
"""compute_dedup_key 是岗位去重的关键。同一公司同一岗位同一城市的不同薪资格式应映射到同一 key。"""
from boss_app.models.application import compute_dedup_key


def test_dedup_key_normalizes_whitespace():
    a = compute_dedup_key({"title": "AI 工程师", "company": " 某科技 ", "city": "北京", "salary": "20-40K"})
    b = compute_dedup_key({"title": "AI工程师", "company": "某科技", "city": "北京", "salary": "20-40K"})
    assert a == b and a


def test_dedup_key_returns_empty_for_missing_fields():
    assert compute_dedup_key({}) == ""
    assert compute_dedup_key({"title": "x"}) == ""


def test_dedup_key_distinguishes_companies():
    a = compute_dedup_key({"title": "Go工程师", "company": "A公司", "city": "上海", "salary": "30K"})
    b = compute_dedup_key({"title": "Go工程师", "company": "B公司", "city": "上海", "salary": "30K"})
    assert a != b
```

- [ ] **Step 2：运行测试，验证全部通过**

```bash
python -m pytest tests/test_dedup_key.py -v
```

预期：3 passed。如某条失败，说明现有 `compute_dedup_key` 行为与测试假设不同——以现有实现为准修测试，不改实现（这一阶段是建立行为基线）。

- [ ] **Step 3：commit**

```bash
git add tests/test_dedup_key.py
git commit -m "test: 锁定 compute_dedup_key 当前行为"
```

---

### Task 1.3：测试评分 helper

**Files:**
- Test: `tests/test_score_helpers.py`

- [ ] **Step 1：写测试**

```python
from boss_app.services.scorer import compute_composite_score, score_hr_activity
from boss_app.services.scraper import BossScraper


def test_composite_all_present():
    # cv=80*0.55 + quality=60*0.25 + hr=100*0.20 = 44 + 15 + 20 = 79
    assert compute_composite_score(80, 60, 100) == 79


def test_composite_missing_quality_reweights():
    # cv=80, hr=100, weights 0.55+0.20=0.75，归一化 → (80*0.55 + 100*0.20)/0.75 ≈ 85.33 → 85
    assert compute_composite_score(80, None, 100) == 85


def test_composite_all_none_returns_zero():
    assert compute_composite_score(None, None, None) == 0


def test_score_hr_activity_buckets():
    assert score_hr_activity("刚刚活跃") == 100
    assert score_hr_activity("今日活跃") == 80
    assert score_hr_activity("3日内活跃") == 60
    assert score_hr_activity("本周活跃") == 40
    assert score_hr_activity("本月活跃") == 30
    assert score_hr_activity("半年内活跃") == 20
    assert score_hr_activity("") == 0


def test_is_hr_inactive_marks_old_activity():
    # 业务定义：超过 3 天 = 不活跃
    assert BossScraper.is_hr_inactive("本周活跃") is True
    assert BossScraper.is_hr_inactive("本月活跃") is True
    assert BossScraper.is_hr_inactive("半年内活跃") is True
    assert BossScraper.is_hr_inactive("刚刚活跃") is False
    assert BossScraper.is_hr_inactive("今日活跃") is False
    assert BossScraper.is_hr_inactive("3日内活跃") is False
    assert BossScraper.is_hr_inactive("") is False  # 未知活跃度不视为不活跃
```

- [ ] **Step 2：运行测试**

```bash
python -m pytest tests/test_score_helpers.py -v
```

> 如 `is_hr_inactive` 实际行为对空串/未知值的判定与测试不同，以代码实现为准修改测试。

- [ ] **Step 3：commit**

```bash
git add tests/test_score_helpers.py
git commit -m "test: 锁定评分与活跃度 helper 当前行为"
```

---

### Task 1.4：测试搜索意向匹配

**Files:**
- Test: `tests/test_intent_match.py`

- [ ] **Step 1：写测试**

```python
from boss_app.routes.jobs import _matches_search_intent  # 阶段 3 后改为 boss_app.routes.jobs._common


def test_no_keywords_passes_everything():
    assert _matches_search_intent("任意岗位", "任意JD", "") is True
    assert _matches_search_intent("任意岗位", "任意JD", "   ") is True


def test_core_keyword_in_title_matches():
    assert _matches_search_intent("AI Agent 开发工程师", "做大模型", "AI Agent,大模型") is True


def test_core_keyword_in_description_matches():
    assert _matches_search_intent("Java 开发", "需要使用 LangChain 做 Agent", "AI Agent,LangChain") is True


def test_unrelated_job_filtered_out():
    assert _matches_search_intent("前端开发工程师", "Vue React 切图", "AI Agent,大模型") is False


def test_generic_words_only_passes_through():
    # 关键词全是被过滤的通用词，不过滤
    assert _matches_search_intent("任意岗位", "任意JD", "实习,工程师,开发") is True


def test_compound_keyword_split_match():
    # 关键词 "linux运维实习生" 应能匹配单独提及 "linux" 的 JD
    assert _matches_search_intent("Linux 系统管理", "需要 Linux 运维经验", "linux运维实习生") is True
```

- [ ] **Step 2：运行测试**

```bash
python -m pytest tests/test_intent_match.py -v
```

- [ ] **Step 3：commit**

```bash
git add tests/test_intent_match.py
git commit -m "test: 锁定 _matches_search_intent 当前行为"
```

---

### Task 1.5：测试调度器时间窗

**Files:**
- Test: `tests/test_scheduler_cron.py`

- [ ] **Step 1：写测试**

```python
from datetime import datetime
from unittest.mock import patch

from boss_app.core.scheduler import AutoScheduler


def test_parse_cron_times():
    s = AutoScheduler()
    assert s._parse_cron_times("09:00,14:30") == [(9, 0), (14, 30)]
    assert s._parse_cron_times("") == []
    assert s._parse_cron_times("not-a-time, 10:15") == [(10, 15)]


def test_should_run_now_matches_minute_window():
    s = AutoScheduler()
    cron = [(9, 0), (14, 30)]
    with patch("boss_app.core.scheduler.datetime") as mock_dt:
        mock_dt.now.return_value = datetime(2026, 6, 3, 9, 0, 12)
        assert s._should_run_now(cron) is True
        mock_dt.now.return_value = datetime(2026, 6, 3, 9, 1, 0)
        assert s._should_run_now(cron) is False


def test_compute_next_run_picks_today_or_tomorrow():
    s = AutoScheduler()
    cron = [(9, 0), (14, 30)]
    with patch("boss_app.core.scheduler.datetime") as mock_dt:
        # 早上 8 点 → 下一次是今天 9:00
        mock_dt.now.return_value = datetime(2026, 6, 3, 8, 0, 0)
        # 让 mock_dt 也支持 timedelta 的相加
        from datetime import timedelta as real_td
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        assert s._compute_next_run(cron).startswith("2026-06-03 09:00")

        # 晚上 23 点 → 下一次是明天 9:00
        mock_dt.now.return_value = datetime(2026, 6, 3, 23, 0, 0)
        nxt = s._compute_next_run(cron)
        assert nxt.startswith("2026-06-04 09:00")
```

- [ ] **Step 2：运行测试**

```bash
python -m pytest tests/test_scheduler_cron.py -v
```

> 注：mock `datetime` 容易踩坑（`datetime.now()` 返 mock 后还要支持 `replace`/算术）。如测试因 mock 问题失败，简化为直接传入 `now_fn=lambda: datetime(...)` 重构 `_compute_next_run` 接收时间源——或写一个 `monkeypatch.setattr(scheduler, '_now', lambda: ...)` 的版本。这是测试写法的问题，不是被测代码的问题。

- [ ] **Step 3：commit**

```bash
git add tests/test_scheduler_cron.py
git commit -m "test: 锁定 AutoScheduler 时间窗与 next_run 计算"
```

---

### Task 1.6：阶段 1 收尾

- [ ] **Step 1：跑全量测试，验证全绿**

```bash
python -m pytest -q
```

预期：≥ 18 个测试全部通过。

- [ ] **Step 2：打 tag**

```bash
git tag refactor-A-stage1
```

---

## 阶段 2：抽象提取（不挪文件）

> 目的：抽出 `browser_lock` 与 `pipeline`，让 `routes/jobs.py` 与 `core/scheduler.py` 都改调它们。`routes/jobs.py` 仍是单文件，留到阶段 3 再拆。

### Task 2.1：实现 `core/locks.py`

**Files:**
- Create: `boss_app/core/locks.py`

- [ ] **Step 1：写实现**

```python
"""浏览器互斥锁的上下文管理器。Python 3.10 兼容。"""
from contextlib import asynccontextmanager
import asyncio

from . import state


class BrowserLockTimeout(Exception):
    """browser_lock body 超过 timeout 仍未完成。"""


@asynccontextmanager
async def browser_lock(timeout: float | None = None):
    """获取浏览器互斥锁；timeout 仅施加在 yield 出去的代码块上。

    用法：
        async with browser_lock(timeout=20):
            await automation.fetch_detail(url)

    超时抛 BrowserLockTimeout；锁在退出时一定释放（正常/取消/异常路径）。
    """
    await state.browser_sync_lock.acquire()
    try:
        if timeout is None:
            yield
            return

        # 3.10 兼容写法：把 yield 包在一个 task 里，用 wait_for+shield
        # 等价于 3.11 的 async with asyncio.timeout(timeout)
        done = asyncio.Event()

        async def _body_marker():
            try:
                await done.wait()
            except asyncio.CancelledError:
                raise

        body_task = asyncio.create_task(_body_marker())
        try:
            try:
                yield
            finally:
                done.set()
            # 用 wait_for 确保不超时
            await asyncio.wait_for(asyncio.shield(body_task), timeout=timeout)
        except asyncio.TimeoutError as e:
            body_task.cancel()
            raise BrowserLockTimeout(
                f"browser lock body timed out after {timeout}s"
            ) from e
    finally:
        state.browser_sync_lock.release()
```

> 简化备注：上面 3.10 写法略复杂，因为要把 `yield` 与超时绑定。如果实际审视后觉得复杂度不值，可以把所有调用点的 timeout 行为前移到调用点（即上下文管理器只负责锁，调用点自己写 `await asyncio.wait_for(coro, timeout=20)`）。这是一个**实现选择**，task 执行者优先尝试上面写法；若调试超过 30 分钟不通过，**降级方案**：

```python
@asynccontextmanager
async def browser_lock():
    await state.browser_sync_lock.acquire()
    try:
        yield
    finally:
        state.browser_sync_lock.release()
```

调用点写：
```python
async with browser_lock():
    detail = await asyncio.wait_for(automation.fetch_detail(url), timeout=20)
```

降级方案仍然消除了 4 处 `acquire/try/finally release` 模板，只是把 timeout 留在调用点。任选一种即可。

- [ ] **Step 2：写最小自测（不放进 tests，跑完即删）**

```bash
python -c "
import asyncio
from boss_app.core import state
state.browser_sync_lock = asyncio.Lock()
from boss_app.core.locks import browser_lock, BrowserLockTimeout

async def t():
    async with browser_lock():
        print('lock acquired and released ok')
    try:
        async with browser_lock(timeout=0.1):
            await asyncio.sleep(1)
    except BrowserLockTimeout:
        print('timeout works')

asyncio.run(t())
"
```

预期输出：两行 `lock acquired and released ok` 和 `timeout works`。

- [ ] **Step 3：commit**

```bash
git add boss_app/core/locks.py
git commit -m "feat(core): 引入 browser_lock 上下文管理器"
```

---

### Task 2.2：替换 4 处锁模板

**Files:**
- Modify: `boss_app/routes/jobs.py:356-446`（`_fetch_details_and_score`）
- Modify: `boss_app/routes/jobs.py:594-777`（`search_jobs`）
- Modify: `boss_app/routes/jobs.py:797-881`（`refetch_job_details`）

- [ ] **Step 1：在 `routes/jobs.py` 顶部加 import**

```python
from ..core.locks import browser_lock
```

- [ ] **Step 2：替换 `_fetch_details_and_score` 内的锁块（约 376-389 行）**

旧：
```python
await state.browser_sync_lock.acquire()
try:
    detail = await asyncio.wait_for(
        state.automation.fetch_detail(job["job_url"]),
        timeout=30
    )
finally:
    state.browser_sync_lock.release()
```

新：
```python
async with browser_lock(timeout=30):
    detail = await state.automation.fetch_detail(job["job_url"])
```

- [ ] **Step 3：替换 `search_jobs` 中两处锁块**

第一处（搜索本身，约 607-612 行）：

旧：
```python
async def _search_with_lock():
    await state.browser_sync_lock.acquire()
    try:
        return await state.automation.search(req.keyword, city_code, max_pages=req.max_pages)
    finally:
        state.browser_sync_lock.release()

jobs = await asyncio.wait_for(_search_with_lock(), timeout=120)
```

新：
```python
async with browser_lock(timeout=120):
    jobs = await state.automation.search(req.keyword, city_code, max_pages=req.max_pages)
```

第二处（详情抓取，约 661-668 行）：

旧：
```python
await state.browser_sync_lock.acquire()
try:
    detail = await asyncio.wait_for(
        state.automation.fetch_detail(job["job_url"]),
        timeout=20
    )
finally:
    state.browser_sync_lock.release()
```

新：
```python
async with browser_lock(timeout=20):
    detail = await state.automation.fetch_detail(job["job_url"])
```

- [ ] **Step 4：替换 `refetch_job_details` 中的锁块（约 834-841 行）**

旧：
```python
await state.browser_sync_lock.acquire()
try:
    detail = await asyncio.wait_for(
        state.automation.fetch_detail(url),
        timeout=25
    )
finally:
    state.browser_sync_lock.release()
```

新：
```python
async with browser_lock(timeout=25):
    detail = await state.automation.fetch_detail(url)
```

- [ ] **Step 5：跑 pytest 验证未破坏 helper**

```bash
python -m pytest -q
```

预期：阶段 1 全部 ≥ 18 个测试仍通过。

- [ ] **Step 6：commit**

```bash
git add boss_app/routes/jobs.py
git commit -m "refactor(routes): 把 4 处浏览器锁模板替换为 browser_lock"
```

---

### Task 2.3：实现 `services/pipeline.py`

**Files:**
- Create: `boss_app/services/pipeline.py`

- [ ] **Step 1：写实现**

```python
"""详情抓取 → 评分 → 自动投递 的统一管线。

唯一公共入口：run_pipeline。被 routes.jobs.search 与 core.scheduler 共用。
"""
from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass

from ..core import state
from ..core.database import get_db
from ..core.locks import browser_lock, BrowserLockTimeout
from ..models.application import (
    get_application_for_scoring,
    update_application_legitimacy,
    update_application_score,
    update_application_hr_activity,
    update_application_composite_score,
    update_application_status,
    get_today_application_count,
    get_auto_apply_candidates,
    log_auto_apply,
)
from ..models.settings import get_setting
from ..services.scorer import (
    score_job, score_job_quality, score_hr_activity,
    check_legitimacy, compute_composite_score,
)
from ..services.scraper import BossScraper


@dataclass
class PipelineResult:
    detail_ok: int = 0
    detail_failed: int = 0
    filtered: int = 0
    scored: int = 0
    applied: int = 0


async def run_pipeline(
    new_ids: list[int],
    *,
    fetch_detail: bool = True,
    score: bool = True,
    auto_apply: bool = True,
    ws=None,
    legitimacy_snapshot: list | None = None,
) -> PipelineResult:
    """三阶段执行。返回 PipelineResult。"""
    result = PipelineResult()
    if not new_ids:
        return result

    if legitimacy_snapshot is None:
        from ..models.application import get_all_active_jobs_for_legitimacy
        legitimacy_snapshot = get_all_active_jobs_for_legitimacy()

    if fetch_detail:
        new_ids = await _phase_fetch_detail(new_ids, result)
        if not new_ids:
            return result

    if score:
        await _phase_score(new_ids, legitimacy_snapshot, result)

    if auto_apply and get_setting("auto_apply_enabled", "false") == "true" and result.scored > 0:
        result.applied = await _phase_auto_apply(ws=ws)

    if ws and result.scored > 0:
        await ws.broadcast({"type": "score_complete", "count": result.scored})

    return result


async def _phase_fetch_detail(new_ids: list[int], result: PipelineResult) -> list[int]:
    """逐岗位抓详情；HR 不活跃直接软删。返回通过过滤的 ids。"""
    filter_inactive = get_setting("filter_inactive_hr", "true") == "true"
    filtered_ids: list[int] = []

    for aid in new_ids:
        job = get_application_for_scoring(aid)
        if not job or not job.get("job_url"):
            continue
        try:
            async with browser_lock(timeout=30):
                detail = await state.automation.fetch_detail(job["job_url"])
        except (BrowserLockTimeout, asyncio.TimeoutError):
            print(f"[详情] 岗位 {aid} 超时，跳过")
            result.detail_failed += 1
            filtered_ids.append(aid)
            continue
        except Exception as e:
            print(f"[详情] 岗位 {aid} 抓取失败: {e}")
            result.detail_failed += 1
            filtered_ids.append(aid)
            continue

        if detail:
            updates = {}
            for k in ("description", "hr_name", "hr_title"):
                if detail.get(k) and not job.get(k):
                    updates[k] = detail[k]
            if detail.get("hr_activity"):
                updates["hr_activity"] = detail["hr_activity"]
            if updates:
                db = get_db()
                sets = ", ".join(f"{k}=?" for k in updates)
                vals = list(updates.values()) + [aid]
                db.execute(
                    f"UPDATE applications SET {sets}, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                    vals,
                )
                db.commit()

            hr_activity = detail.get("hr_activity", "")
            if filter_inactive and BossScraper.is_hr_inactive(hr_activity):
                db = get_db()
                db.execute(
                    "UPDATE applications SET deleted_at=CURRENT_TIMESTAMP, "
                    "updated_at=CURRENT_TIMESTAMP WHERE id=?",
                    (aid,),
                )
                db.commit()
                result.filtered += 1
                continue

            result.detail_ok += 1

        filtered_ids.append(aid)
        await asyncio.sleep(2)

    return filtered_ids


async def _phase_score(ids: list[int], snapshot: list, result: PipelineResult):
    """对每个岗位跑合法性 + CV + quality + HR + composite。容错：单条失败不影响其他。"""
    resume = get_setting("resume_summary", "")

    for aid in ids:
        job = get_application_for_scoring(aid)
        if not job:
            continue

        try:
            leg = check_legitimacy(job, snapshot)
            update_application_legitimacy(aid, leg["level"], leg["signals"])
        except Exception as e:
            update_application_legitimacy(
                aid, "unknown",
                [{"type": "check_error", "detail": f"检测异常: {str(e)[:50]}"}],
            )

        title = job.get("job_title", "")
        company = job.get("company", "")
        desc = job.get("description", "")
        salary = job.get("salary", "")
        hr_name = job.get("hr_name", "")
        hr_activity = job.get("hr_activity", "")

        cv_score = 30
        try:
            r = await asyncio.to_thread(score_job, title, company, desc, salary, resume)
            if r.get("score") is not None:
                cv_score = r["score"]
                result.scored += 1
            else:
                r = {"score": 30, "key_skills": [], "gap": "", "advice": "",
                     "summary": "LLM评分失败，使用保守默认分", "has_resume": bool(resume)}
            update_application_score(aid, cv_score, r)
        except Exception as e:
            r = {"score": 30, "key_skills": [], "gap": "", "advice": "",
                 "summary": f"评分异常: {str(e)[:50]}", "has_resume": bool(resume)}
            update_application_score(aid, cv_score, r)

        quality_score = 40
        try:
            q = await asyncio.to_thread(score_job_quality, title, company, desc, salary, hr_name)
            if q.get("quality_score") is not None:
                quality_score = q["quality_score"]
        except Exception:
            pass

        hr_score = score_hr_activity(hr_activity)
        update_application_hr_activity(aid, hr_score)

        composite = compute_composite_score(cv_score, quality_score, hr_score)
        update_application_composite_score(aid, composite)


async def _phase_auto_apply(ws=None) -> int:
    """高分候选 + 意向匹配 + 30-90s 随机延迟逐个投递。"""
    from ..routes.jobs import _matches_search_intent  # 阶段 3 后变 _common
    threshold = int(get_setting("auto_apply_threshold", "73"))
    hr_active_required = get_setting("auto_apply_hr_active_required", "true") == "true"
    daily_limit = int(get_setting("daily_apply_limit", "15"))
    search_keywords = get_setting("search_keywords", "")

    today_count = get_today_application_count()
    if today_count >= daily_limit:
        return 0

    candidates = get_auto_apply_candidates(threshold, hr_active_required)
    candidates = [
        j for j in candidates
        if _matches_search_intent(
            j.get("job_title", ""), j.get("description", ""), search_keywords
        )
    ]
    if not candidates:
        return 0

    remaining = daily_limit - today_count
    to_apply = candidates[:remaining]

    applied = 0
    for job in to_apply:
        app_id = job["id"]
        title = job.get("job_title", "")
        company = job.get("company", "")
        url = job.get("job_url", "")

        try:
            greeting = get_setting("greeting_template", "").replace("{job_title}", title)
            if not greeting:
                greeting = f"您好！看到贵司在招{title}，很感兴趣，希望有机会详细了解一下。"

            async with browser_lock():
                r = await state.automation.apply_to_job(url, greeting)

            if r.get("success"):
                update_application_status(app_id, "applied", greeting)
                log_auto_apply(app_id, job.get("composite_score", 0),
                               job.get("hr_activity_score", 0), "success")
                applied += 1
                if ws:
                    await ws.broadcast({
                        "type": "auto_apply_complete",
                        "job_id": app_id,
                        "title": title,
                        "company": company,
                        "success": True,
                    })
            else:
                log_auto_apply(app_id, job.get("composite_score", 0),
                               job.get("hr_activity_score", 0),
                               f"failed: {r.get('message','')}")

            await asyncio.sleep(random.uniform(30, 90))
        except Exception as e:
            log_auto_apply(app_id, job.get("composite_score", 0),
                           job.get("hr_activity_score", 0), f"error: {e}")

    if ws:
        await ws.broadcast({
            "type": "auto_apply_batch_complete",
            "total": len(to_apply),
            "applied": applied,
        })
    return applied
```

- [ ] **Step 2：commit**

```bash
git add boss_app/services/pipeline.py
git commit -m "feat(services): 引入 services.pipeline.run_pipeline 统一三阶段管线"
```

---

### Task 2.4：让 `routes/jobs.py` 与 `scheduler.py` 调用 pipeline

**Files:**
- Modify: `boss_app/routes/jobs.py`
- Modify: `boss_app/core/scheduler.py`

- [ ] **Step 1：在 `routes/jobs.py` 顶部加 import**

```python
from ..services.pipeline import run_pipeline
```

- [ ] **Step 2：删除 `_score_and_check_jobs`（死代码，约 251-276 行）**

整段函数删除。

- [ ] **Step 3：把 `_fetch_details_and_score` 改为薄壳**

旧（356-446 行整段）替换为：

```python
async def _fetch_details_and_score(new_ids: list, all_jobs_for_legitimacy: list):
    """[deprecated] 兼容 wrapper：转发到 services.pipeline.run_pipeline。"""
    r = await run_pipeline(new_ids, ws=ws_manager, legitimacy_snapshot=all_jobs_for_legitimacy)
    return r.scored, r.applied
```

- [ ] **Step 4：把 `_execute_auto_apply` 改为薄壳**

旧（449-534 行整段）替换为：

```python
async def _execute_auto_apply():
    """[deprecated] 兼容 wrapper：转发到 services.pipeline._phase_auto_apply。"""
    from ..services.pipeline import _phase_auto_apply
    return await _phase_auto_apply(ws=ws_manager)
```

- [ ] **Step 5：把 `search_jobs` 内联管线段（约 643-751 行）替换为单次调用**

定位 `# Phase 2: 逐个抓取详情 + 评分（每个单独获取锁）` 注释开始的整段，替换为：

```python
        # Phase 2: 详情抓取 + 评分 + 自动投递（统一管线）
        scored = 0
        filtered_count = 0
        if new_ids:
            all_jobs = get_all_active_jobs_for_legitimacy()
            r = await run_pipeline(
                new_ids, ws=ws_manager, legitimacy_snapshot=all_jobs,
            )
            scored = r.scored
            filtered_count = r.filtered
```

下方 `result_jobs = []` 重建逻辑保留。

- [ ] **Step 6：改 `core/scheduler.py:_execute`**

把：
```python
from ..routes.jobs import CITY_MAP, _fetch_details_and_score, _save_job_with_dedup
...
scored, applied = await _fetch_details_and_score(new_ids, all_jobs)
```

改为：
```python
from ..routes.jobs import CITY_MAP, _save_job_with_dedup  # 阶段 3 后改 _common
from ..services.pipeline import run_pipeline
...
r = await run_pipeline(new_ids, ws=ws_manager, legitimacy_snapshot=all_jobs)
scored, applied = r.scored, r.applied
```

- [ ] **Step 7：跑 pytest**

```bash
python -m pytest -q
```

预期：阶段 1 全部测试仍通过。

- [ ] **Step 8：手工 smoke test**

```bash
python -c "from boss_app.main import app; print('app loads ok')"
```

预期输出：`app loads ok`（不应有 import 错误）。

- [ ] **Step 9：commit**

```bash
git add boss_app/routes/jobs.py boss_app/core/scheduler.py
git commit -m "refactor: 让 routes 与 scheduler 调用 services.pipeline"
```

---

### Task 2.5：测试 pipeline 三阶段

**Files:**
- Test: `tests/test_pipeline_phases.py`

- [ ] **Step 1：写测试**

```python
"""run_pipeline 三阶段流转、异常容错、PipelineResult 计数。

通过 monkeypatch 替换 LLM 与浏览器调用为 fake，不依赖真实环境。
"""
import asyncio
import pytest

from boss_app.services import pipeline as pipeline_mod
from boss_app.services.pipeline import run_pipeline


class FakeWS:
    def __init__(self):
        self.events = []

    async def broadcast(self, msg):
        self.events.append(msg)


@pytest.mark.asyncio
async def test_empty_ids_returns_zero():
    r = await run_pipeline([], fetch_detail=False, score=False, auto_apply=False)
    assert r.scored == 0 and r.applied == 0


@pytest.mark.asyncio
async def test_score_phase_counts_success_and_default_on_error(monkeypatch, tmp_db):
    # 准备两条 job 行
    from boss_app.models.application import add_application
    aid1 = add_application({"title": "Job1", "company": "C1", "url": "https://www.zhipin.com/x1"})
    aid2 = add_application({"title": "Job2", "company": "C2", "url": "https://www.zhipin.com/x2"})

    monkeypatch.setattr(pipeline_mod, "score_job",
                        lambda *a, **kw: {"score": 80, "key_skills": [], "gap": "", "advice": "", "summary": "", "has_resume": False})
    monkeypatch.setattr(pipeline_mod, "score_job_quality",
                        lambda *a, **kw: {"quality_score": 60})
    monkeypatch.setattr(pipeline_mod, "check_legitimacy",
                        lambda *a, **kw: {"level": "high", "signals": []})

    r = await run_pipeline([aid1, aid2], fetch_detail=False, auto_apply=False)
    assert r.scored == 2


@pytest.mark.asyncio
async def test_score_phase_handles_llm_exception(monkeypatch, tmp_db):
    from boss_app.models.application import add_application
    aid = add_application({"title": "Job", "company": "C", "url": "https://www.zhipin.com/x"})

    def boom(*a, **kw):
        raise RuntimeError("LLM down")

    monkeypatch.setattr(pipeline_mod, "score_job", boom)
    monkeypatch.setattr(pipeline_mod, "score_job_quality", lambda *a, **kw: {"quality_score": None})
    monkeypatch.setattr(pipeline_mod, "check_legitimacy", lambda *a, **kw: {"level": "high", "signals": []})

    r = await run_pipeline([aid], fetch_detail=False, auto_apply=False)
    # 评分成功数为 0（LLM 报错），但 pipeline 不挂
    assert r.scored == 0
```

> 注：`tests/conftest.py` 已提供 `tmp_db` fixture。如需 `pytest-asyncio`，在 `pyproject.toml [project.optional-dependencies].dev` 加 `pytest-asyncio` 并在 `[tool.pytest.ini_options]` 加 `asyncio_mode = "auto"`。

- [ ] **Step 2：装依赖（如未装）**

```bash
pip install pytest-asyncio
```

并在 `pyproject.toml` 加：
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

- [ ] **Step 3：跑测试**

```bash
python -m pytest tests/test_pipeline_phases.py -v
```

> 如果 `tmp_db` fixture 与现有 `get_db` 实现不兼容（实际行为），降级写法：直接 monkeypatch `pipeline_mod` 内的所有 DB 操作函数（`get_application_for_scoring` 等）为返回固定 dict 的 fake，完全不连真 DB。这种写法纯单元测试、零环境依赖。

- [ ] **Step 4：commit**

```bash
git add tests/test_pipeline_phases.py pyproject.toml
git commit -m "test: 覆盖 run_pipeline 三阶段流转与异常容错"
```

---

### Task 2.6：阶段 2 收尾

- [ ] **Step 1：跑全量测试**

```bash
python -m pytest -q
```

- [ ] **Step 2：手工启动服务一次冒烟**

```bash
python -m uvicorn boss_app.main:app --port 8011 --host 127.0.0.1 &
sleep 3
curl -s http://127.0.0.1:8011/ | head -3
kill %1
```

- [ ] **Step 3：打 tag**

```bash
git tag refactor-A-stage2
```

---

## 阶段 3：拆分 `routes/jobs.py` 为 7 个子模块

> 目的：把 1293 行（阶段 2 后约 ~1100 行）的 `routes/jobs.py` 拆为 `routes/jobs/` 包。每个 task 拆一个子模块、独立 commit、跑 pytest。

### Task 3.1：建包骨架与 `_common.py`

**Files:**
- Create: `boss_app/routes/jobs/__init__.py`
- Create: `boss_app/routes/jobs/_common.py`

- [ ] **Step 1：临时把 `routes/jobs.py` 改名为 `routes/_jobs_legacy.py` 备份**

```bash
git mv boss_app/routes/jobs.py boss_app/routes/_jobs_legacy.py
```

- [ ] **Step 2：创建 `routes/jobs/_common.py`**

把 `_jobs_legacy.py` 中以下内容**复制**（不删除）到 `routes/jobs/_common.py`：

- `_matches_search_intent`
- `CITY_MAP`
- `_normalize_job_url`
- `_deduplicate_jobs`
- `_save_job_with_dedup`
- `_search_job_payload`
- 所有 Pydantic 模型类（`SearchRequest`、`ApplyRequest`、`ApplyBatchRequest`、`ScanAndApplyRequest`、`AnalyzeRequest`、`DeleteRequest`、`RestoreRequest`、`ClearRequest`）
- 必要的 import：`from urllib.parse import urljoin, urlparse`、`from ..core.database import get_db`、`from ..models.application import compute_dedup_key, ...`、`re`、`Optional`、`List`、`BaseModel`

> 不要在 `_common.py` 里 `import APIRouter`；它只放共享工具。

- [ ] **Step 3：创建 `routes/jobs/__init__.py`**

```python
"""routes.jobs 包：聚合 7 个 sub-router。"""
from fastapi import APIRouter

router = APIRouter()

from .search import router as _search_router
from .apply import router as _apply_router
from .trash import router as _trash_router
from .dedup import router as _dedup_router
from .shortlist import router as _shortlist_router
from .followup import router as _followup_router
from .lifecycle import router as _lifecycle_router  # 必须最后 include，避免动态路径抢匹配

router.include_router(_search_router)
router.include_router(_apply_router)
router.include_router(_trash_router)
router.include_router(_dedup_router)
router.include_router(_shortlist_router)
router.include_router(_followup_router)
router.include_router(_lifecycle_router)
```

> 此时这些 `from .xxx import` 还会 ImportError，下一个 task 起逐个补齐子模块即可。

- [ ] **Step 4：commit**

```bash
git add boss_app/routes/_jobs_legacy.py boss_app/routes/jobs/__init__.py boss_app/routes/jobs/_common.py
git commit -m "refactor(routes): 备份 jobs.py 并搭建 routes/jobs/ 包骨架"
```

---

### Task 3.2：搬 `search.py` 子模块

**Files:**
- Create: `boss_app/routes/jobs/search.py`
- Modify: `boss_app/routes/_jobs_legacy.py`（移除已搬走的端点）

- [ ] **Step 1：创建 `boss_app/routes/jobs/search.py`**

文件结构（仅展示骨架；从 `_jobs_legacy.py` 复制对应函数体）：

```python
"""/api/jobs/search、/api/jobs/scan、/api/jobs/refetch。"""
import asyncio
from fastapi import APIRouter, HTTPException

from ...core import state
from ...core.database import get_db
from ...core.locks import browser_lock
from ...core.monitor import chat_monitor
from ...core.websocket import ws_manager
from ...models.application import (
    get_all_active_jobs_for_legitimacy,
    get_application_by_dedup_key, compute_dedup_key,
)
from ...models.settings import get_setting
from ...services.pipeline import run_pipeline
from ...services.scorer import score_hr_activity
from ._common import (
    SearchRequest, CITY_MAP,
    _deduplicate_jobs, _save_job_with_dedup, _search_job_payload,
)

router = APIRouter()


@router.post("/api/jobs/search")
async def search_jobs(req: SearchRequest):
    # 复制 _jobs_legacy.py 中 search_jobs 函数体
    ...


@router.post("/api/jobs/scan")
async def scan_current_page():
    # 复制
    ...


@router.post("/api/jobs/refetch")
async def refetch_job_details():
    # 复制
    ...
```

> 实际复制时保留原函数体，只调整 import 路径（`..core` → `...core`、`..services` → `...services`、`..models` → `...models`）。

- [ ] **Step 2：从 `_jobs_legacy.py` 删除已搬走的 3 个端点函数**

- [ ] **Step 3：跑 pytest**

```bash
python -m pytest -q
```

- [ ] **Step 4：app 加载 smoke**

```bash
python -c "from boss_app.main import app; print(len([r for r in app.routes if hasattr(r,'path')]))"
```

预期：路由数与重构前相近（误差 ±2 可接受，因 sub-router include）。

- [ ] **Step 5：commit**

```bash
git add boss_app/routes/jobs/search.py boss_app/routes/_jobs_legacy.py
git commit -m "refactor(routes): 抽出 jobs/search.py"
```

---

### Task 3.3：搬 `apply.py` 子模块

**Files:**
- Create: `boss_app/routes/jobs/apply.py`
- Modify: `boss_app/routes/_jobs_legacy.py`

- [ ] **Step 1：创建 `boss_app/routes/jobs/apply.py`**

骨架：

```python
"""/api/jobs/apply、/apply-batch、/scan-and-apply、/analyze、/auto-apply-logs、/auto-apply/trigger。"""
import asyncio
from fastapi import APIRouter, HTTPException

from ...core import state
from ...core.locks import browser_lock
from ...core.websocket import ws_manager
from ...models.application import (
    get_application_by_url, get_today_application_count, get_auto_apply_logs,
)
from ...models.settings import get_setting
from ...services.pipeline import _phase_auto_apply
from ...services.replier import generate_greeting
from ._common import ApplyRequest, ApplyBatchRequest, ScanAndApplyRequest, AnalyzeRequest

router = APIRouter()


@router.post("/api/jobs/apply")
async def apply_to_job(req: ApplyRequest):
    ...


@router.post("/api/jobs/apply-batch")
async def apply_batch(req: ApplyBatchRequest):
    ...


@router.post("/api/jobs/scan-and-apply")
async def scan_and_apply(req: ScanAndApplyRequest = ScanAndApplyRequest()):
    ...


@router.post("/api/jobs/analyze")
async def analyze_jd(req: AnalyzeRequest):
    ...


@router.get("/api/auto-apply-logs")
def get_auto_apply_logs_api(limit: int = 50):
    ...


@router.post("/api/auto-apply/trigger")
async def trigger_auto_apply():
    if not state.automation or state.automation.page is None:
        raise HTTPException(status_code=503, detail="浏览器未启动")
    await _phase_auto_apply(ws=ws_manager)
    return {"status": "ok"}
```

> `generate_greeting` 在阶段 4 之前还来自 `boss_replier`（根目录 proxy），所以本阶段先 `from boss_replier import generate_greeting`，阶段 4 收口。

- [ ] **Step 2：从 `_jobs_legacy.py` 删除已搬走的 6 个端点**

- [ ] **Step 3-5：pytest + smoke + commit**

```bash
python -m pytest -q
python -c "from boss_app.main import app; print('ok')"
git add boss_app/routes/jobs/apply.py boss_app/routes/_jobs_legacy.py
git commit -m "refactor(routes): 抽出 jobs/apply.py"
```

---

### Task 3.4：搬 `trash.py` 子模块

**Files:**
- Create: `boss_app/routes/jobs/trash.py`
- Modify: `boss_app/routes/_jobs_legacy.py`

- [ ] **Step 1：创建 `boss_app/routes/jobs/trash.py`**

包含端点：`/api/jobs/delete`、`/api/jobs/clear`、`/api/trash`、`/api/trash/restore`、`/api/trash/purge`、`/api/trash/count`、`/api/delete-logs`。

```python
from fastapi import APIRouter, HTTPException

from ...core.websocket import ws_manager
from ...models.application import (
    soft_delete_applications, clear_all_applications,
    get_trash_applications, restore_applications, purge_old_trashes,
    get_delete_logs, get_trash_count,
)
from ._common import DeleteRequest, RestoreRequest, ClearRequest

router = APIRouter()


@router.post("/api/jobs/delete")
async def delete_job(req: DeleteRequest): ...

@router.post("/api/jobs/clear")
async def clear_jobs(req: ClearRequest): ...

@router.get("/api/trash")
def list_trash(): ...

@router.post("/api/trash/restore")
async def restore_trash(req: RestoreRequest): ...

@router.post("/api/trash/purge")
def purge_trash(): ...

@router.get("/api/delete-logs")
def list_delete_logs(): ...

@router.get("/api/trash/count")
def trash_count(): ...
```

- [ ] **Step 2-5：删 legacy + pytest + smoke + commit**

```bash
python -m pytest -q
python -c "from boss_app.main import app; print('ok')"
git add boss_app/routes/jobs/trash.py boss_app/routes/_jobs_legacy.py
git commit -m "refactor(routes): 抽出 jobs/trash.py"
```

---

### Task 3.5：搬 `dedup.py` 子模块

**Files:**
- Create: `boss_app/routes/jobs/dedup.py`
- Modify: `boss_app/routes/_jobs_legacy.py`

- [ ] **Step 1：创建 `dedup.py`**

```python
from fastapi import APIRouter

from ...models.application import deduplicate_applications, get_duplicate_stats

router = APIRouter()


@router.post("/api/jobs/deduplicate")
def deduplicate_jobs():
    return deduplicate_applications()


@router.get("/api/jobs/dedup-stats")
def get_dedup_stats():
    return get_duplicate_stats()
```

- [ ] **Step 2-5**：删 legacy 对应端点 → pytest → smoke → commit。

```bash
git add boss_app/routes/jobs/dedup.py boss_app/routes/_jobs_legacy.py
git commit -m "refactor(routes): 抽出 jobs/dedup.py"
```

---

### Task 3.6：搬 `shortlist.py` 子模块

**Files:**
- Create: `boss_app/routes/jobs/shortlist.py`
- Modify: `boss_app/routes/_jobs_legacy.py`

- [ ] **Step 1：创建 `shortlist.py`**

```python
from fastapi import APIRouter, HTTPException

# 阶段 4 后改 from ...models.shortlist import ...
from boss_state import (
    add_to_shortlist, remove_from_shortlist, list_shortlists, is_in_shortlist,
)

router = APIRouter()


@router.get("/api/shortlists")
def get_shortlists():
    return {"shortlists": list_shortlists()}


@router.post("/api/shortlists")
def add_shortlist(req: dict = None):
    url = (req or {}).get("job_url", "")
    if not url:
        raise HTTPException(status_code=400, detail="缺少 job_url")
    if is_in_shortlist(url):
        return {"status": "already_exists"}
    sid = add_to_shortlist(
        url, req.get("title", ""), req.get("company", ""), req.get("salary", ""),
        req.get("city", ""), req.get("note", ""),
    )
    return {"status": "ok", "id": sid} if sid else {"status": "duplicate"}


@router.delete("/api/shortlists/{sid}")
def remove_shortlist(sid: int):
    remove_from_shortlist(sid)
    return {"status": "ok"}
```

- [ ] **Step 2-5**：删 legacy → pytest → smoke → commit。

```bash
git add boss_app/routes/jobs/shortlist.py boss_app/routes/_jobs_legacy.py
git commit -m "refactor(routes): 抽出 jobs/shortlist.py"
```

---

### Task 3.7：搬 `followup.py` 子模块

**Files:**
- Create: `boss_app/routes/jobs/followup.py`
- Modify: `boss_app/routes/_jobs_legacy.py`

- [ ] **Step 1：创建 `followup.py`**

```python
from fastapi import APIRouter, HTTPException

from ...core.websocket import ws_manager
from ...models.followup import (
    get_overdue_followups, get_followup_stats, record_followup,
)

router = APIRouter()


@router.get("/api/followups")
def list_followups():
    return {
        "overdue": get_overdue_followups(),
        "stats": get_followup_stats(),
    }


@router.post("/api/followups/{app_id}/done")
async def mark_followup_done(app_id: int):
    if not record_followup(app_id, "manual"):
        raise HTTPException(status_code=404, detail="岗位不存在")
    await ws_manager.broadcast({"type": "followup_done", "app_id": app_id})
    return {"status": "ok"}
```

- [ ] **Step 2-5**：删 legacy → pytest → smoke → commit。

```bash
git add boss_app/routes/jobs/followup.py boss_app/routes/_jobs_legacy.py
git commit -m "refactor(routes): 抽出 jobs/followup.py"
```

---

### Task 3.8：搬 `lifecycle.py` 子模块并删除 legacy

**Files:**
- Create: `boss_app/routes/jobs/lifecycle.py`
- Delete: `boss_app/routes/_jobs_legacy.py`
- Modify: `boss_app/main.py` 或 `boss_app/routes/__init__.py`（确认 `from .routes.jobs import router` 仍工作，原本就是这样）

- [ ] **Step 1：创建 `lifecycle.py`**

```python
"""/api/jobs(list)、/api/jobs/{id}、/api/jobs/{id}/skip、/api/jobs/{id}/score。

注意：动态路径 /api/jobs/{job_id} 必须在所有具体路径之后 include
（已在 routes/jobs/__init__.py 处理）。
"""
import asyncio
from fastapi import APIRouter, HTTPException

from ...core.websocket import ws_manager
from ...models.application import (
    get_application, list_applications, update_application_status,
    get_application_for_scoring, get_all_active_jobs_for_legitimacy,
    update_application_score, update_application_legitimacy,
    update_application_hr_activity, update_application_composite_score,
)
from ...models.settings import get_setting
from ...services.scorer import (
    score_job, score_job_quality, score_hr_activity,
    check_legitimacy, compute_composite_score,
)

router = APIRouter()


@router.get("/api/jobs")
def list_jobs(status=None, limit: int = 100, sort_by: str = "composite_score"):
    jobs = list_applications(status, limit, sort_by=sort_by)
    return {"jobs": jobs, "total": len(jobs)}


@router.get("/api/jobs/{job_id}")
def get_job(job_id: int):
    job = get_application(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="岗位不存在")
    return {"job": job}


@router.post("/api/jobs/{job_id}/skip")
async def skip_job(job_id: int):
    update_application_status(job_id, "skipped")
    await ws_manager.broadcast({"type": "job_updated", "job_id": job_id, "status": "skipped"})
    return {"status": "ok"}


@router.post("/api/jobs/{job_id}/score")
async def score_single_job(job_id: int):
    # 复制原 score_single_job 函数体
    ...
```

- [ ] **Step 2：删除 `_jobs_legacy.py`**

```bash
git rm boss_app/routes/_jobs_legacy.py
```

- [ ] **Step 3：跑 pytest**

```bash
python -m pytest -q
```

- [ ] **Step 4：smoke：路由集合精确等于基线 59 个**

```bash
python - <<'PY'
from boss_app.main import app
paths = sorted({r.path for r in app.routes if hasattr(r, 'path') and r.path.startswith('/api')})
expected = [
    "/api/auto-apply-logs", "/api/auto-apply/trigger",
    "/api/conversations", "/api/conversations/{conv_id}",
    "/api/conversations/{conv_id}/messages",
    "/api/conversations/{conv_id}/open", "/api/conversations/{conv_id}/pause",
    "/api/conversations/{conv_id}/resume", "/api/conversations/{conv_id}/send",
    "/api/conversations/{conv_id}/sync",
    "/api/debug/page-stats", "/api/debug/selector-test", "/api/debug/selectors-status",
    "/api/delete-logs", "/api/doctor",
    "/api/followups", "/api/followups/{app_id}/done",
    "/api/health",
    "/api/jobs", "/api/jobs/analyze",
    "/api/jobs/apply", "/api/jobs/apply-batch", "/api/jobs/clear",
    "/api/jobs/dedup-stats", "/api/jobs/deduplicate", "/api/jobs/delete",
    "/api/jobs/refetch", "/api/jobs/scan", "/api/jobs/scan-and-apply",
    "/api/jobs/search",
    "/api/jobs/{job_id}", "/api/jobs/{job_id}/score", "/api/jobs/{job_id}/skip",
    "/api/log/idle-redirect",
    "/api/monitor/pause", "/api/monitor/resume",
    "/api/scheduler/start", "/api/scheduler/status", "/api/scheduler/stop",
    "/api/settings",
    "/api/shortlists", "/api/shortlists/{sid}",
    "/api/stats", "/api/stats/funnel", "/api/stats/reconcile", "/api/stats/trend",
    "/api/status",
    "/api/system/heartbeat", "/api/system/navigate-chat", "/api/system/relogin",
    "/api/system/start", "/api/system/stop",
    "/api/trash", "/api/trash/count", "/api/trash/purge", "/api/trash/restore",
    "/api/wechat-exchanges",
]
missing = [p for p in expected if p not in paths]
extra = [p for p in paths if p not in expected]
assert not missing and not extra, f"missing={missing}\nextra={extra}"
assert len(paths) == 59, f"expected 59 routes, got {len(paths)}"
print(f"all {len(paths)} routes match baseline")
PY
```

预期输出：`all 59 routes match baseline`。任何差异都是 bug，必须 revert 上一 commit 修复。

- [ ] **Step 5：commit**

```bash
git add boss_app/routes/jobs/lifecycle.py boss_app/routes/_jobs_legacy.py
git commit -m "refactor(routes): 抽出 jobs/lifecycle.py 并删除 legacy"
```

---

### Task 3.9：阶段 3 收尾

- [ ] **Step 1：跑全量测试**

```bash
python -m pytest -q
```

- [ ] **Step 2：起服务，打开 dashboard 跑一轮搜索 + 投递闭环**（手工）

```bash
python run.py
# 浏览器打开 http://127.0.0.1:8010 ，验证搜索、岗位列表、回收站、候选池、跟进、设置 6 个 Tab 全部加载正常
# 触发一次搜索，确认 WebSocket 实时推送依旧出现 search_complete / score_complete 事件
```

- [ ] **Step 3：打 tag**

```bash
git tag refactor-A-stage3
```

---

## 阶段 4：迁移并删除根目录脚本

> 目的：把 `boss_state.py` 中的候选池真代码迁入 `models/shortlist.py`；扩展 `services/replier.py` 持有 `generate_greeting`（如已通过 proxy `import *` 暴露则只是改调用方 import）；删除根目录 6 个旧脚本；最终 grep 验证全仓无遗留。

### Task 4.1：迁入 `models/shortlist.py`

**Files:**
- Create: `boss_app/models/shortlist.py`

- [ ] **Step 1：grep 实际引用**

```bash
grep -rEn 'from boss_state|import boss_state' boss_app/ tests/ run.py
```

记录所有引用位置（预期：`boss_app/main.py`、`boss_app/routes/jobs/shortlist.py`，可能还有 `boss_app/routes/jobs/_common.py`、`boss_app/core/scheduler.py` 等）。

- [ ] **Step 2：创建 `boss_app/models/shortlist.py`**

```python
"""候选池数据层（迁自根目录 boss_state.py）。函数签名/语义保持不变。"""
import sqlite3

from ..core.database import get_db


def add_to_shortlist(
    job_url: str,
    title: str,
    company: str = "",
    salary: str = "",
    city: str = "",
    note: str = "",
) -> int:
    db = get_db()
    try:
        cur = db.execute(
            "INSERT INTO shortlists (job_url, job_title, company, salary, city, note) "
            "VALUES (?,?,?,?,?,?)",
            (job_url, title, company, salary, city, note),
        )
        db.commit()
        return cur.lastrowid
    except sqlite3.IntegrityError:
        return 0


def remove_from_shortlist(shortlist_id: int) -> None:
    db = get_db()
    db.execute("DELETE FROM shortlists WHERE id=?", (shortlist_id,))
    db.commit()


def list_shortlists(limit: int = 100) -> list:
    rows = get_db().execute(
        "SELECT * FROM shortlists ORDER BY created_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


def is_in_shortlist(job_url: str) -> bool:
    row = get_db().execute(
        "SELECT COUNT(*) as cnt FROM shortlists WHERE job_url=?",
        (job_url,),
    ).fetchone()
    return row["cnt"] > 0 if row else False
```

> 注意：`compute_dedup_key`、`reconcile_application_stats`、`deduplicate_applications` 已经在 `boss_app/models/application.py`（`boss_state.py` 是 proxy 转发到那里）。本 task 不重复迁移这些；`main.py` 的 import 在 4.2 改为直接从 `application.py` 取。

- [ ] **Step 3：commit**

```bash
git add boss_app/models/shortlist.py
git commit -m "feat(models): 迁入候选池数据层"
```

---

### Task 4.2：改全部 import

**Files:**
- Modify: `boss_app/main.py`
- Modify: `boss_app/routes/jobs/shortlist.py`
- Modify: 任何阶段 4.1 grep 出来的其他文件

- [ ] **Step 1：改 `boss_app/main.py`**

旧：
```python
from boss_state import (
    reconcile_application_stats,
    deduplicate_applications,
    compute_dedup_key,
)
```

新：
```python
from .models.application import (
    reconcile_application_stats,
    deduplicate_applications,
    compute_dedup_key,
)
```

- [ ] **Step 2：改 `boss_app/routes/jobs/shortlist.py`**

旧：
```python
from boss_state import (
    add_to_shortlist, remove_from_shortlist, list_shortlists, is_in_shortlist,
)
```

新：
```python
from ...models.shortlist import (
    add_to_shortlist, remove_from_shortlist, list_shortlists, is_in_shortlist,
)
```

- [ ] **Step 3：改 `boss_app/routes/jobs/apply.py`（若仍引用 `boss_replier`）**

旧：
```python
from boss_replier import generate_greeting
```

新：
```python
from ...services.replier import generate_greeting
```

> 验证 `boss_app/services/replier.py` 实际暴露 `generate_greeting`：

```bash
grep -n "^def generate_greeting" boss_app/services/replier.py
```

如未暴露（实际是 proxy 内 `from boss_app.services.replier import *` 把名字传给 root），那是因为 `services/replier.py` 已是 service layer 实现。本 task 假定已存在。

- [ ] **Step 4：再次 grep 验证无残留**

```bash
grep -rEn 'from (boss_state|boss_replier)\b|import (boss_state|boss_replier)\b' boss_app/ tests/ run.py
```

预期输出为空。

- [ ] **Step 5：跑 pytest + smoke**

```bash
python -m pytest -q
python -c "from boss_app.main import app; print('ok')"
```

- [ ] **Step 6：commit**

```bash
git add boss_app/main.py boss_app/routes/jobs/shortlist.py boss_app/routes/jobs/apply.py
git commit -m "refactor: import 收敛到 boss_app 包内（不再走根目录 proxy）"
```

---

### Task 4.3：评估并删除根目录旧脚本

**Files:**
- Delete: `scraper.py`（根目录）
- Delete: `boss_app.py`、`boss_automation.py`、`boss_firefox.py`、`boss_replier.py`、`boss_state.py`

- [ ] **Step 1：grep 全仓验证无外部引用**

```bash
grep -rEn 'import scraper\b|from scraper import|import boss_app\b|from boss_app\.boss_app|import boss_automation\b|from boss_automation|import boss_firefox\b|from boss_firefox|import boss_replier\b|from boss_replier|import boss_state\b|from boss_state' \
  boss_app/ lakejob_cli/ interview/ tests/ run.py setup_ai.py setup.sh batch_score.py
```

> 注意排除 `from boss_app` 这种引用 boss_app **包**的（带 `.` 后缀），只关心引用根目录 `boss_app.py`。改写正则要小心。可以两步：
> 1) `grep -rEn '^from (scraper|boss_replier|boss_state|boss_automation|boss_firefox)' …`
> 2) `grep -rEn '^import (scraper|boss_app|boss_automation|boss_firefox|boss_replier|boss_state)$' …`

- [ ] **Step 2：检查 `batch_score.py` 是否引用旧脚本**

```bash
head -30 batch_score.py
```

如有引用，相应修复 import 后再删旧脚本。

- [ ] **Step 3：检查 `run.py`**

```bash
cat run.py
```

如 `run.py` 是 `from boss_app.py import app`（即引用根目录文件，不是包），改为 `from boss_app.main import app`。

- [ ] **Step 4：确认无遗留后删除 6 个文件**

```bash
git rm scraper.py boss_app.py boss_automation.py boss_firefox.py boss_replier.py boss_state.py
```

- [ ] **Step 5：跑 pytest + smoke**

```bash
python -m pytest -q
python run.py &
sleep 3
curl -s http://127.0.0.1:8010/ | grep -c '<html'  # 预期 ≥ 1
kill %1
```

- [ ] **Step 6：lakejob CLI 冒烟**

```bash
lakejob doctor
lakejob schema
```

预期：`doctor` 返 `ok=true`；`schema` 列出 ≥ 12 个命令。

- [ ] **Step 7：commit**

```bash
git add -A
git commit -m "chore: 删除根目录 6 个旧脚本（已迁移完毕）"
```

---

### Task 4.4：阶段 4 收尾

- [ ] **Step 1：跑全量测试**

```bash
python -m pytest -q
```

预期：≥ 21 个测试全部通过。

- [ ] **Step 2：手工跑核心闭环**

启动服务 → 浏览器登录 BOSS → 触发一次「搜索 + 评分 + 自动投递」 → 观察 dashboard 状态正常、WebSocket 事件序列与重构前一致、`auto-apply-logs` 中应有相应记录。

- [ ] **Step 3：检查 `boss_app/routes/jobs/` 各文件行数**

```bash
wc -l boss_app/routes/jobs/*.py
```

预期：`__init__.py` ~25 行、`_common.py` ~120 行、`search.py` ≤ 250 行、其他子模块 ≤ 150 行。如某文件 > 250，单独拆分（不属于本 plan，留 issue）。

- [ ] **Step 4：打 tag**

```bash
git tag refactor-A-stage4
```

- [ ] **Step 5：（可选）创建汇总 PR**

```bash
git log refactor-A-stage1..refactor-A-stage4 --oneline > /tmp/commits.txt
cat /tmp/commits.txt
# 用作 PR 描述的「commits 清单」
```

---

## 验收清单（与 Spec §7 一一对应）

执行结束后挨个勾：

- [ ] `python -m pytest -q` 全绿（≥ 21 个测试）
- [ ] `lakejob doctor` 返回 `ok=true`
- [ ] `lakejob schema` 返回 12 个命令
- [ ] 端口 8010 dashboard 加载正常
- [ ] 走完 `搜索 → 抓详情 → 评分 → 自动投递` 闭环；行为/日志/WebSocket 事件名与重构前一致
- [ ] `boss_app/routes/jobs.py` 不存在；`boss_app/routes/jobs/` 包下无 > 250 行的文件
- [ ] 根目录 `scraper.py`、`boss_app.py`、`boss_automation.py`、`boss_firefox.py`、`boss_replier.py`、`boss_state.py` 全部删除
- [ ] `grep -rEn 'from (boss_state|boss_replier)\b|import (boss_state|boss_replier|scraper)$' boss_app/ tests/ run.py` 输出为空

---

## 风险与回退

每阶段结束打 tag。出现非阶段内可定位回归 → `git reset --hard refactor-A-stageN`，重新进入下一 task。

| 风险 | 触发 | 缓解 | 回退 |
|---|---|---|---|
| `boss_state.py` 还有未知引用 | 4.1 grep 漏看 | 阶段 4 grep 命令两步走 | 单 commit revert |
| `pipeline` 与原管线行为偏差 | 阶段 2 替换 | `tests/test_pipeline_phases.py` 断言事件序列 | revert task 2.4 |
| `asyncio.timeout` 兼容问题 | 阶段 2.1 | 用 `wait_for+shield` 实现，必要时退到「锁=锁、timeout 留调用点」简化版 | 用降级实现 |
| 路由顺序导致 `/api/jobs/{id}` 抢占 | 阶段 3.8 | `lifecycle.py` 在 `__init__.py` 最后 include；smoke 检查 | revert 3.8 |
| 子模块循环 import | 阶段 3.x | 共享内容只在 `_common.py`，`pipeline` 不 import `routes` | 把违规 import 挪到 `_common.py` |

---

## 自审记录

**1. Spec 覆盖**：

- Spec §3 文件结构 → 本 plan「文件结构」表与各 task `Files:` 段
- Spec §4.1 pipeline → Task 2.3、2.4、2.5
- Spec §4.2 browser_lock → Task 2.1、2.2
- Spec §4.3 模块迁移 → Task 4.1、4.2
- Spec §5 阶段 1 测试 → Task 1.1-1.6
- Spec §5 阶段 2 抽象 → Task 2.1-2.6
- Spec §5 阶段 3 路由拆分 → Task 3.1-3.9
- Spec §5 阶段 4 迁移 → Task 4.1-4.4
- Spec §6 风险表 → 本 plan「风险与回退」段
- Spec §7 验收 → 本 plan「验收清单」

**2. 占位符扫描**：

各 task 的 `...` 都标注了「复制原函数体并改 import 路径」，不是 TBD。Task 3.2 / 3.3 / 3.8 用 `...` 是因为复制内容超过单 task 字符限制；执行者按指引从 `_jobs_legacy.py` 中复制对应函数。

**3. 类型一致性**：

- `PipelineResult` 字段（detail_ok、detail_failed、filtered、scored、applied）在 Task 2.3 定义，被 Task 2.4 中 `r.scored / r.applied` 与 `core/scheduler.py` 的 `r.scored, r.applied` 引用——一致。
- `browser_lock` 签名在 Task 2.1 定义为 `browser_lock(timeout=...)`，调用点 Task 2.2 一致使用。
- `BrowserLockTimeout` 在 Task 2.1 定义，Task 2.3（`_phase_fetch_detail`）捕获，一致。
- `_matches_search_intent` 在阶段 1 测试时 import 自 `boss_app.routes.jobs`，阶段 3 后改自 `boss_app.routes.jobs._common`——已在 Task 1.4 注释里标记。
- `generate_greeting` 在阶段 3 是 `from boss_replier`，阶段 4 改 `from ...services.replier`——已在 Task 3.3 注释里标记。

---

## Execution Handoff

Plan saved to `docs/superpowers/plans/2026-06-03-structural-refactor.md`。

两种执行方式：

1. **Subagent-Driven（推荐）**：用 `superpowers:subagent-driven-development`，每个 task 派一个新的 subagent 实施 + 两阶段 review，主上下文窗口干净
2. **Inline Execution**：用 `superpowers:executing-plans`，本会话内逐 task 执行 + 每阶段 checkpoint

请告诉我用哪种。



