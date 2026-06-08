# BOSS直聘智能求职助手

AI 驱动的 BOSS 直聘自动化求职工具，支持岗位搜索、AI 智能评分、自动投递、HR 消息自动回复，实现求职全流程智能化。

## 功能特性

### 核心功能

- **智能搜索** — 支持多关键词并行搜索，60+ 城市覆盖，福利筛选（双休/五险一金等），工作经验/期望薪资过滤
- **API 薪资提取** — 通过 BOSS 直聘 API 获取真实薪资数据，绕过 CSS 字体反爬机制
- **AI 三维评分** — 简历匹配度 × 55% + 招聘信息质量 × 25% + HR 活跃度 × 20% 综合评分
- **批量评分** — 5岗位/批 × 5路并行，337个岗位几分钟内完成，WebSocket 实时进度条
- **智能投递** — 高分岗位自动投递，支持意向匹配过滤、每日上限、HR 活跃度门槛，带超时保护和并发防护
- **AI 自动回复** — 对接 DeepSeek/OpenRouter/MiMo 等多平台模型，自动回复 HR 消息，支持简历/微信/电话自动交换
- **多简历管理** — 支持上传多份简历（如 AI 开发、运维方向），一键切换激活简历，评分时自动使用激活简历进行匹配

### Agent Profile 系统

5 个独立 Agent，每个拥有独立的模型、温度、系统提示词配置，通过 Dashboard 可视化管理：

| Agent | 职责 | 默认温度 |
|-------|------|----------|
| 搜索 Agent | 岗位搜索、关键词优化、去重 | 0.3 |
| 评分 Agent | 多维度加权评分、合法性检测 | 0.3 |
| 聊天 Agent | HR 消息自动回复、对话记忆 | 0.7 |
| 投递 Agent | 自动投递、打招呼生成、限额控制 | 0.3 |
| 简历 Agent | 简历解析/优化/匹配分析/面试准备 | 0.4 |

### 评分体系

| 维度 | 权重 | 来源 | 说明 |
|------|------|------|------|
| 简历匹配 (CV Match) | 55% | LLM | 岗位 JD 与**激活简历**的技能/经验匹配度 |
| 招聘质量 (Quality) | 25% | LLM | JD 详细程度、薪资透明度、公司信息 |
| HR 活跃度 (HR Activity) | 20% | 规则 | 刚刚活跃=100, 今日=80, 3日内=60, 本周=40, 本月=30 |

评分逻辑严格区分核心技能（Python/RAG/LLM/Agent/FastAPI）与辅助技能（Docker/MySQL/Linux），核心技能不匹配的岗位分数上限为 45 分。

**简历选择**：系统优先使用「简历管理」中激活的简历，如果没有激活简历则回退到旧的 settings 配置。支持针对不同求职方向（如 AI 开发、运维）准备不同简历，评分时一键切换。

### 自动化能力

- **定时调度** — 配置每日自动搜索+评分+投递时间点
- **会话监控** — 实时监听 HR 消息，自动回复
- **跟进管理** — 超期未跟进岗位提醒
- **投递漏斗** — 搜索 → 待投递 → 已投递 → HR回复 → 面试 可视化
- **浏览器持久化** — Playwright 持久化上下文，重启无需重新登录

## 技术栈

- **后端**: FastAPI + Playwright + SQLite (WAL模式)
- **前端**: Vue 3 + Vite + Pinia + Tailwind CSS + WebSocket 实时推送
- **AI**: DeepSeek / OpenRouter / Xiaomi MiMo 多模型支持（Anthropic Messages API 兼容）
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
python -m uvicorn boss_app.main:app --host 0.0.0.0 --port 8000
```

打开浏览器访问 `http://127.0.0.1:8000`，在设置页配置 AI 模型后点击「启动浏览器」，扫码登录 BOSS 直聘即可使用。

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
├── agents/
│   ├── base.py             # Agent 基类（Profile 集成、LLM 调用）
│   ├── profiles.py         # 5 个 Agent 的默认 Profile 定义
│   ├── chat_agent.py       # 聊天 Agent
│   └── resume_agent.py     # 简历 Agent
├── core/
│   ├── database.py         # SQLite 数据库初始化 + Agent Profile 存储
│   ├── scheduler.py        # 定时调度器
│   ├── monitor.py          # 会话监控（自动回复循环）
│   ├── state.py            # 全局状态 + 浏览器同步锁
│   └── websocket.py        # WebSocket 管理
├── models/
│   ├── application.py      # 岗位数据模型 + 自动投递候选查询
│   ├── settings.py         # 配置管理
│   ├── conversation.py     # 会话模型
│   └── message.py          # 消息模型
├── routes/
│   ├── jobs.py             # 岗位搜索/评分/投递 API + 智能投递
│   ├── agents.py           # Agent Profile CRUD + 简历解析 API
│   ├── settings.py         # 设置 API
│   ├── system.py           # 系统控制 API
│   └── conversations.py    # 会话 API
├── services/
│   ├── scraper.py          # Playwright 页面抓取 + API 薪资提取
│   ├── automation.py       # 浏览器自动化（投递/回复/交换）
│   ├── replier.py          # AI 自动回复生成
│   └── scorer.py           # AI 评分（CV匹配/质量/HR活跃度/综合/批量）
frontend/                   # Vue 3 前端
├── src/
│   ├── views/              # 页面组件（Search/Chat/Settings/Agents）
│   ├── components/         # 通用组件（SearchBar/JobList/ChatMessage）
│   ├── stores/             # Pinia 状态管理（jobs/conversations/settings）
│   ├── composables/        # 组合式函数（useApi/useWebSocket/useJobActions）
│   └── types/              # TypeScript 类型定义
├── vite.config.ts          # Vite 构建配置 + API 代理
└── package.json
scripts/
├── run.py                  # 启动入口
└── batch_score.py          # 批量评分工具
lakejob_cli/
├── cli.py                  # CLI 入口
├── client.py               # API 客户端
└── output.py               # JSON 信封输出
static/
└── dist/                   # Vite 构建产物（前端静态文件）
docs/                       # 项目文档
data/                       # 数据文件
```

## API 接口

### 岗位管理

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/jobs/search` | 搜索岗位 |
| GET | `/api/jobs` | 岗位列表 |
| POST | `/api/jobs/{id}/score` | 重新评分单个岗位 |
| POST | `/api/jobs/batch-score` | 批量评分（支持 `mode=unscored` 或 `mode=all`） |
| POST | `/api/jobs/apply` | 手动投递 |
| POST | `/api/auto-apply/trigger` | 手动触发自动投递 |
| GET | `/api/auto-apply-logs` | 投递日志 |
| POST | `/api/jobs/scan` | 扫描当前页面 |
| POST | `/api/jobs/refetch` | 重新抓取详情 |

### Agent Profile

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/agents/profiles` | 获取所有 Agent Profile |
| GET | `/api/agents/profiles/{name}` | 获取单个 Agent Profile |
| PUT | `/api/agents/profiles/{name}` | 更新 Agent Profile |
| POST | `/api/agents/profiles/{name}/reset` | 恢复默认 Profile |

### 简历与设置

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/resumes` | 获取所有简历列表 |
| GET | `/api/resumes/active` | 获取当前激活的简历 |
| POST | `/api/resumes` | 上传新简历（PDF/TXT/MD） |
| PUT | `/api/resumes/{id}/activate` | 设置激活简历 |
| PUT | `/api/resumes/{id}` | 更新简历名称/摘要 |
| DELETE | `/api/resumes/{id}` | 删除简历 |
| GET | `/api/settings` | 获取设置 |
| POST | `/api/settings/resume/upload` | 上传简历（旧接口，兼容） |

### 系统控制

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/system/start` | 启动浏览器 |
| GET | `/api/status` | 系统状态 |
| WS | `/ws` | WebSocket 实时推送（评分进度等） |

## 配置说明

### 简历管理（简历 Tab）

- **多简历上传** — 支持 PDF/TXT/MD 格式，可上传多份针对不同方向的简历
- **激活切换** — 点击「激活」按钮切换当前使用的简历，评分时自动使用激活简历
- **编辑名称** — 为简历命名便于识别（如「AI开发简历」「运维简历」）
- **摘要查看** — 查看简历提取的技能、教育、项目经验摘要

### 系统设置（设置 Tab）

- **搜索关键词** — 逗号分隔，如 `AI应用开发实习生,AI开发实习,大模型应用开发`
- **默认城市** — 支持 60+ 城市
- **工作经验** — 搜索时筛选经验范围（应届/1-3年/3-5年等）
- **期望薪资** — 搜索时筛选薪资范围（月薪K/日薪元/天）
- **自动投递** — 开关、综合分阈值、HR 活跃度门槛、每日上限
- **自动回复** — 开关、回复风格、回复延迟、AI 模型配置
- **定时调度** — 开关、执行时间点
- **AI 模型** — API Key、Base URL、模型选择（支持 DeepSeek / OpenRouter / MiMo）
- **招呼语模板** — 自动投递时发送的招呼语
- **Agent 配置** — 每个 Agent 独立的模型、温度、系统提示词（Agent Tab）

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
- 批量评分进度：Dashboard 进度条通过 WebSocket 实时更新
- 修复漏斗统计偏差：调用 `POST /api/stats/reconcile`
- 重置所有设置：删除 `.boss_profile/boss_state.db` 重启服务

## 免责声明

⚠️ **免责声明**

本项目仅用于学习交流和本地辅助，使用时请遵守相关法律法规、BOSS 直聘平台用户协议和隐私政策。默认低风险模式会阻断自动触达、批量操作、规避风控和候选人个人信息处理链路；任何投递、沟通、联系方式交换、招聘者候选人处理都应回到平台官网由用户手动完成。因不当使用产生的一切后果由使用者自行承担，与本项目作者无关。

## 许可

MIT License
