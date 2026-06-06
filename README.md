# BOSS直聘智能求职助手

AI 驱动的 BOSS 直聘自动化求职工具，支持岗位搜索、AI 智能评分、自动投递、HR 消息自动回复，实现求职全流程智能化。

## 功能特性

### 核心功能

- **智能搜索** — 支持多关键词并行搜索，60+ 城市覆盖，福利筛选（双休/五险一金等）
- **AI 三维评分** — 简历匹配度 × 55% + 招聘信息质量 × 25% + HR 活跃度 × 20% 综合评分
- **自动投递** — 高分岗位自动投递，支持意向匹配过滤、每日上限、HR 活跃度门槛
- **AI 自动回复** — 对接 DeepSeek/OpenRouter/MiMo 等多平台模型，自动回复 HR 消息
- **智能交换** — HR 要简历/微信/手机号时自动通过 BOSS 发送
- **简历解析** — 支持 PDF/TXT/MD 简历上传，自动提取技能、教育、项目经验，生成 AI 评分用摘要

### 评分体系

| 维度 | 权重 | 来源 | 说明 |
|------|------|------|------|
| 简历匹配 (CV Match) | 55% | LLM | 岗位 JD 与简历的技能/经验匹配度 |
| 招聘质量 (Quality) | 25% | LLM | JD 详细程度、薪资透明度、公司信息 |
| HR 活跃度 (HR Activity) | 20% | 规则 | 刚刚活跃=100, 今日=80, 3日内=60, 本周=40, 本月=30 |

### 自动化能力

- **定时调度** — 配置每日自动搜索+评分+投递时间点
- **会话监控** — 实时监听 HR 消息，自动回复
- **跟进管理** — 超期未跟进岗位提醒
- **投递漏斗** — 搜索 → 待投递 → 已投递 → HR回复 → 面试 可视化

## 技术栈

- **后端**: FastAPI + Playwright + SQLite (WAL模式)
- **前端**: 单页 HTML + WebSocket 实时推送
- **AI**: DeepSeek / OpenRouter / MiMo 多模型支持
- **自动化**: Firefox 浏览器 + Playwright 持久化上下文
- **CLI**: 14 条 Agent 友好命令，统一 JSON 输出

## 快速开始

### 环境要求

- Python 3.10+
- Firefox (Playwright 自动安装)

### 安装

```bash
git clone https://github.com/as161233574-alt/boss-zhipin-bot.git
cd boss-zhipin-bot
pip install -r requirements.txt
playwright install firefox
```

### 启动

```bash
python scripts/run.py
# 或
python -m uvicorn boss_app.main:app --host 0.0.0.0 --port 8010
```

打开浏览器访问 `http://127.0.0.1:8010`，在设置页配置后点击「启动浏览器」，扫码登录 BOSS 直聘即可使用。

### CLI 使用

```bash
python lakejob_cli/cli.py search "AI应用开发" --city 成都
python lakejob_cli/cli.py apply --url <job_url>
python lakejob_cli/cli.py doctor
```

## 项目结构

```
boss_app/
├── main.py                 # FastAPI 入口
├── config.py               # 城市代码、UA 等配置常量
├── core/
│   ├── database.py         # SQLite 数据库初始化
│   ├── scheduler.py        # 定时调度器
│   ├── monitor.py          # 会话监控
│   ├── state.py            # 全局状态
│   └── websocket.py        # WebSocket 管理
├── models/
│   ├── application.py      # 岗位数据模型 + 自动投递候选查询
│   ├── settings.py         # 配置管理
│   ├── followup.py         # 跟进节奏管理
│   ├── conversation.py     # 会话模型
│   ├── message.py          # 消息模型
│   └── shortlist.py        # 候选池管理
├── routes/
│   ├── jobs.py             # 岗位搜索/评分/投递 API
│   ├── settings.py         # 设置 API
│   ├── system.py           # 系统控制 API
│   ├── conversations.py    # 会话 API
│   └── debug.py            # 调试 API
├── services/
│   ├── scraper.py          # Playwright 页面抓取 + 详情提取
│   ├── automation.py       # 浏览器自动化（投递/回复/交换）
│   ├── replier.py          # AI 自动回复生成
│   └── scorer.py           # AI 评分（CV匹配/质量/HR活跃度/综合）
scripts/
├── run.py                  # 启动入口
├── batch_score.py          # 批量评分工具
└── setup_ai.py             # AI 模型配置工具
lakejob_cli/
├── cli.py                  # CLI 入口
├── client.py               # API 客户端
└── output.py               # JSON 信封输出
interview/                  # 面试问答模块
static/
└── dashboard.html          # 前端控制台
docs/                       # 项目文档
data/                       # 数据文件
legacy/                     # 旧版独立脚本
```

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/jobs/search` | 搜索岗位 |
| GET | `/api/jobs` | 岗位列表 |
| POST | `/api/jobs/{id}/score` | 重新评分 |
| POST | `/api/jobs/apply` | 手动投递 |
| POST | `/api/auto-apply/trigger` | 手动触发自动投递 |
| GET | `/api/auto-apply-logs` | 投递日志 |
| POST | `/api/jobs/scan` | 扫描当前页面 |
| POST | `/api/jobs/refetch` | 重新抓取详情 |
| GET | `/api/settings` | 获取设置 |
| POST | `/api/settings/resume/upload` | 上传简历（PDF/TXT/MD） |
| DELETE | `/api/settings/resume` | 清除简历 |
| POST | `/api/system/start` | 启动浏览器 |
| GET | `/api/status` | 系统状态 |
| WS | `/ws` | WebSocket 实时推送 |

## 配置说明

在 Web 控制台的设置页可配置：

- **搜索关键词** — 逗号分隔，如 `AI应用开发实习生,AI开发实习,大模型应用开发`
- **默认城市** — 支持 60+ 城市
- **简历摘要** — 用于 AI 评分匹配
- **自动投递** — 开关、综合分阈值、HR 活跃度要求
- **定时调度** — 开关、执行时间点
- **AI 模型** — API Key、Base URL、模型选择
- **招呼语模板** — 自动投递时发送的招呼语

## 开发与测试

### 测试套件

测试分三层，按覆盖范围从快到慢：

```bash
# 1. 单元测试（数据库模型 / 服务 / 路由 / LLM 客户端 / 配置）
PYTHONIOENCODING=utf-8 python -m pytest tests/test_models.py tests/test_services.py tests/test_routes.py tests/test_llm_client.py tests/test_config.py tests/test_dedup_endpoint.py -v

# 2. 用户体验测试（API 黑盒 + WebSocket + 调度器）
PYTHONIOENCODING=utf-8 python -m pytest tests/test_e2e_user_experience.py -v

# 3. 浏览器 E2E（Playwright 真实点击 + 截图）
PYTHONIOENCODING=utf-8 python -m pytest tests/e2e_browser/ -v
```

各层覆盖：

| 套件 | 数量 | 覆盖 |
|------|------|------|
| 单元测试 | ~120 | 数据库 / 评分算法 / 路由 / LLM / 评分合并 |
| 用户体验 | ~75 | 完整求职流程 / 错误恢复 / WebSocket |
| 浏览器 E2E | ~135 | 5 个 Tab / 智能投递 / 智能回复 / 设置 / 数据 / 边界 |

### 调试技巧

- 查看后台评分进度：搜索后控制台日志 `[详情] (N/30) ...` 和 `[评分] ...`
- 修复漏斗统计偏差：调用 `POST /api/stats/reconcile`
- 重置所有设置：删除 `.boss_profile/boss_state.db` 重启服务

## 许可

MIT License
