# 代码架构重构设计文档

## 概述

本设计文档针对 BOSS 直聘自动化控制台的代码架构进行重构，采用渐进式重构方案，将大文件按职责分层拆分为模块化结构。

**重构范围**：
- `boss_app.py`（1476 行）→ 路由模块 + 核心模块
- `boss_automation.py`（1396 行）→ 服务模块
- `boss_state.py`（917 行）→ 数据模型模块

**设计原则**：
- 渐进式重构，每步可运行
- 向后兼容，保留旧入口
- 不改变业务逻辑，只调整代码组织

---

## 第一部分：目录结构设计

### 目标结构

```
D:\ztzs\lakejobai-job-radar-main\
├── boss_app/                    # 主应用包
│   ├── __init__.py
│   ├── main.py                  # FastAPI 应用入口 + 启动逻辑
│   ├── config.py                # 配置常量（CITY_MAP 等）
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── jobs.py              # 职位搜索、投递、扫描 API
│   │   ├── conversations.py     # 会话、消息 API
│   │   ├── settings.py          # 设置 API
│   │   ├── system.py            # 系统管理 API（启动、停止、登录）
│   │   └── debug.py             # 调试 API
│   ├── services/
│   │   ├── __init__.py
│   │   ├── automation.py        # BossAutomation 类
│   │   ├── scraper.py           # BossScraper 基类
│   │   └── replier.py           # AI 回复生成
│   ├── models/
│   │   ├── __init__.py
│   │   ├── application.py       # 投递记录数据层
│   │   ├── conversation.py      # 会话数据层
│   │   ├── message.py           # 消息数据层
│   │   └── settings.py          # 设置数据层
│   └── core/
│       ├── __init__.py
│       ├── database.py          # 数据库连接管理
│       ├── websocket.py         # WebSocket 管理
│       └── monitor.py           # 聊天监控循环
├── static/
│   └── dashboard.html           # 前端 SPA
├── config.yaml                  # 配置文件
├── requirements.txt
└── run.py                       # 新的启动入口
```

### 模块职责划分

| 模块 | 职责 | 预估行数 |
|------|------|----------|
| `main.py` | FastAPI 应用创建、中间件、启动事件 | ~100 |
| `config.py` | 常量配置（CITY_MAP、选择器等） | ~100 |
| `routes/jobs.py` | 职位相关 API 端点 | ~300 |
| `routes/conversations.py` | 会话和消息 API | ~200 |
| `routes/settings.py` | 设置 API | ~50 |
| `routes/system.py` | 系统管理 API | ~150 |
| `routes/debug.py` | 调试 API | ~100 |
| `services/automation.py` | BossAutomation 类 | ~800 |
| `services/scraper.py` | BossScraper 基类 | ~600 |
| `services/replier.py` | AI 回复生成 | ~300 |
| `models/application.py` | 投递记录 CRUD | ~300 |
| `models/conversation.py` | 会话 CRUD | ~200 |
| `models/message.py` | 消息 CRUD | ~150 |
| `models/settings.py` | 设置 CRUD | ~100 |
| `core/database.py` | 数据库连接 | ~50 |
| `core/websocket.py` | WebSocket 管理 | ~80 |
| `core/monitor.py` | 监控循环 | ~100 |

---

## 第二部分：模块拆分细节

### 2.1 boss_state.py 拆分

**当前**：917 行，40+ 函数混杂

**拆分为 4 个模块**：

**`models/application.py`**（~300 行）：
- `compute_dedup_key()`
- `get_application_by_dedup_key()`
- `add_application()`
- `get_application()`
- `get_application_by_url()`
- `update_application_from_job()`
- `list_applications()`
- `update_application_status()`
- `get_today_application_count()`
- `get_today_pending_count()`
- `count_hours_replied_in_range()`
- `count_interest_level()`
- `get_pending_applications()`
- `soft_delete_application()`
- `soft_delete_applications()`
- `clear_all_applications()`
- `get_trash_applications()`
- `restore_application()`
- `restore_applications()`
- `purge_old_trashes()`
- `get_delete_logs()`
- `get_trash_count()`
- `deduplicate_applications()`
- `get_duplicate_stats()`
- `reconcile_application_stats()`

**`models/conversation.py`**（~200 行）：
- `get_or_create_conversation()`
- `get_conversation()`
- `list_active_conversations()`
- `find_conversation_by_hr_name()`
- `update_conversation_last_message()`
- `update_conversation_status()`
- `update_conversation_interest()`
- `update_conversation_wechat()`
- `mark_resume_sent()`
- `mark_phone_shared()`
- `get_wechat_exchanges()`
- `set_auto_reply()`

**`models/message.py`**（~150 行）：
- `add_message()`
- `get_messages()`
- `get_recent_messages()`
- `replace_conversation_messages()`
- `get_last_hr_message()`
- `message_exists()`

**`models/settings.py`**（~100 行）：
- `get_setting()`
- `set_setting()`
- `get_all_settings()`
- `get_daily_stats()`
- `increment_daily_stat()`

**`core/database.py`**（~50 行）：
- `get_db()`
- `init_db()`

### 2.2 boss_app.py 拆分

**当前**：1476 行，所有 API 混杂

**拆分为 5 个路由模块 + 3 个核心模块**：

**`routes/jobs.py`**（~300 行）：
- `GET /api/jobs` — 列表
- `POST /api/jobs/search` — 搜索
- `GET /api/jobs/{id}` — 详情
- `POST /api/jobs/{id}/skip` — 跳过
- `POST /api/jobs/delete` — 删除
- `POST /api/jobs/clear` — 清空
- `POST /api/jobs/apply` — 投递
- `POST /api/jobs/apply-batch` — 批量投递
- `POST /api/jobs/scan` — 扫描
- `POST /api/jobs/scan-and-apply` — 扫描并投递
- `POST /api/jobs/analyze` — 分析
- `POST /api/jobs/deduplicate` — 去重
- `GET /api/jobs/dedup-stats` — 去重统计

**`routes/conversations.py`**（~200 行）：
- `GET /api/conversations` — 列表
- `GET /api/conversations/{id}` — 详情
- `GET /api/conversations/{id}/messages` — 消息
- `POST /api/conversations/{id}/sync` — 同步
- `POST /api/conversations/{id}/send` — 发送
- `POST /api/conversations/{id}/open` — 打开
- `POST /api/conversations/{id}/pause` — 暂停
- `POST /api/conversations/{id}/resume` — 恢复
- `GET /api/wechat-exchanges` — 微信记录

**`routes/settings.py`**（~50 行）：
- `GET /api/settings` — 获取设置
- `PUT /api/settings` — 更新设置
- `GET /api/stats` — 统计
- `POST /api/stats/reconcile` — 修复统计

**`routes/system.py`**（~150 行）：
- `POST /api/system/start` — 启动
- `POST /api/system/stop` — 停止
- `POST /api/system/relogin` — 重新登录
- `POST /api/system/heartbeat` — 心跳
- `POST /api/monitor/pause` — 暂停监控
- `POST /api/monitor/resume` — 恢复监控
- `POST /api/system/navigate-chat` — 导航到聊天
- `GET /api/health` — 健康检查
- `GET /api/doctor` — 诊断

**`routes/debug.py`**（~100 行）：
- `POST /api/debug/selector-test` — 选择器测试
- `GET /api/debug/page-stats` — 页面统计
- `GET /api/debug/selectors-status` — 选择器状态

**`core/websocket.py`**（~80 行）：
- WebSocket 连接管理
- 广播函数

**`core/monitor.py`**（~100 行）：
- `chat_monitor_loop()` — 监控循环

### 2.3 boss_automation.py 拆分

**当前**：1396 行，单类 `BossAutomation`

**拆分为 3 个服务模块**：

**`services/scraper.py`**（~600 行）：
- `BossScraper` 基类
- 搜索、详情获取、列表解析

**`services/automation.py`**（~800 行）：
- `BossAutomation` 类（继承 BossScraper）
- 投递、聊天、简历、微信等交互

**`services/replier.py`**（~300 行）：
- AI 回复生成
- 消息分类
- 关键词过滤

---

## 第三部分：迁移策略

### 3.1 迁移原则

1. **渐进式**：每次只拆分一个模块，确保系统可运行
2. **向后兼容**：保留旧入口文件作为代理，逐步迁移
3. **测试验证**：每步完成后验证功能正常
4. **最小改动**：不改变业务逻辑，只调整代码组织

### 3.2 迁移顺序

**Phase 1：基础设施**（优先级最高）
1. 创建 `boss_app/` 包结构
2. 创建 `core/database.py` — 提取数据库连接
3. 创建 `core/websocket.py` — 提取 WebSocket 管理
4. 创建 `core/monitor.py` — 提取监控循环

**Phase 2：数据层拆分**
1. 创建 `models/application.py` — 提取投递记录函数
2. 创建 `models/conversation.py` — 提取会话函数
3. 创建 `models/message.py` — 提取消息函数
4. 创建 `models/settings.py` — 提取设置函数

**Phase 3：服务层拆分**
1. 创建 `services/scraper.py` — 提取 BossScraper
2. 创建 `services/automation.py` — 提取 BossAutomation
3. 创建 `services/replier.py` — 提取 AI 回复

**Phase 4：路由层拆分**
1. 创建 `routes/jobs.py` — 提取职位 API
2. 创建 `routes/conversations.py` — 提取会话 API
3. 创建 `routes/settings.py` — 提取设置 API
4. 创建 `routes/system.py` — 提取系统 API
5. 创建 `routes/debug.py` — 提取调试 API

**Phase 5：入口整合**
1. 创建 `boss_app/main.py` — 整合应用入口
2. 创建 `boss_app/config.py` — 提取配置常量
3. 创建 `run.py` — 新的启动入口
4. 更新 `boss_app.py` 为代理入口（向后兼容）

### 3.3 向后兼容策略

**保留旧入口文件**：
```python
# boss_app.py（重构后）
"""向后兼容入口，实际逻辑已迁移到 boss_app/main.py"""
from boss_app.main import app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8010)
```

**导入路径兼容**：
```python
# boss_state.py（重构后）
"""向后兼容入口，实际逻辑已迁移到 boss_app/models/"""
from boss_app.models.application import *
from boss_app.models.conversation import *
from boss_app.models.message import *
from boss_app.models.settings import *
```

---

## 验证标准

1. **功能完整性**：所有 API 端点正常工作
2. **向后兼容**：旧入口文件仍可启动服务
3. **导入正确**：所有模块导入无错误
4. **测试通过**：现有测试全部通过
5. **性能无退化**：响应时间无明显变化

---

## 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 循环导入 | 高 | 使用依赖注入，避免模块间直接导入 |
| 命名冲突 | 中 | 使用明确的模块命名，避免函数名重复 |
| 导入路径错误 | 中 | 逐步迁移，每步验证 |
| 功能回归 | 高 | 保留旧入口，逐步切换 |
