# BOSS直聘智能求职助手 — Claude Code 指令

## 项目路径
`D:/ztzs/lakejobai-job-radar`

## 快速启动
```bash
cd D:/ztzs/lakejobai-job-radar
python -m uvicorn boss_app.main:app --host 0.0.0.0 --port 8000   # 后端
cd frontend && npx vite                                            # 前端
```

## 架构概览
- **后端**: FastAPI + Playwright + SQLite (WAL)，端口 8000
- **前端**: Vue 3 + Vite + Pinia + Tailwind CSS，端口 5173
- **AI**: DeepSeek / OpenRouter / MiMo 多模型支持
- **自动化**: Firefox + Playwright 持久化上下文
- **API Token**: `.boss_profile/.api_token`

## 关键文件
| 文件 | 职责 |
|------|------|
| `boss_app/main.py` | FastAPI 入口、AuthMiddleware、WebSocket |
| `boss_app/routes/jobs.py` | 岗位搜索/评分/投递 API、智能投递 `_execute_auto_apply()` |
| `boss_app/services/automation.py` | 浏览器自动化（投递/回复/交换） |
| `boss_app/core/monitor.py` | 会话监控，`paused` 标志控制暂停 |
| `boss_app/core/state.py` | 全局状态 + `browser_sync_lock` |
| `frontend/src/views/SearchView.vue` | 搜索页（批量评分、智能投递按钮） |
| `frontend/src/views/SettingsView.vue` | 设置页（含布尔值修复 `normalizeBooleans()`） |
| `frontend/src/views/ChatView.vue` | 聊天页（虚拟滚动、markdown） |
| `frontend/src/views/AgentsView.vue` | Agent 管理页 |
| `frontend/src/stores/jobs.ts` | Pinia store |
| `frontend/src/composables/useJobActions.ts` | 岗位操作 composable |

## 5 个 Agent
| Agent | 职责 | 温度 |
|-------|------|------|
| 搜索 Agent | 岗位搜索、关键词优化、去重 | 0.3 |
| 评分 Agent | 多维度加权评分、合法性检测 | 0.3 |
| 聊天 Agent | HR 消息自动回复、对话记忆 | 0.7 |
| 投递 Agent | 自动投递、打招呼生成、限额控制 | 0.3 |
| 简历 Agent | 简历解析/优化/匹配分析 | 0.4 |

## 已知修复（不要回退）
1. 智能投递并发防护: `_auto_apply_running` 全局标志 + `browser_sync_lock` + monitor `pause()/resume()`
2. 布尔值字符串 bug: SettingsView 用 `normalizeBooleans()` 转换后端返回的 `"false"` 字符串
3. Windows 编码: 测试文件需要 `sys.stdout = io.TextIOWrapper(..., encoding='utf-8')`
4. CORS: 前端测试通过 Vite 代理访问 API，不要直接调用 `127.0.0.1:8000`

## 测试
```bash
# 单元测试
PYTHONIOENCODING=utf-8 python -m pytest tests/test_models.py tests/test_services.py tests/test_routes.py -v

# 用户体验测试
PYTHONIOENCODING=utf-8 python -m pytest tests/test_e2e_user_experience.py -v

# 浏览器 E2E（Playwright）
PYTHONIOENCODING=utf-8 python -m pytest tests/e2e_browser/ -v

# 冒烟测试（全页面截图 + API + WebSocket）
python tests/playwright_smoke.py
```

## 自主迭代工作进度
详细记录见 memory 文件（`C:\Users\26022\.claude\projects\C--Users-26022\memory\work-progress.md`）

**截止时间**: 2026-06-08 20:00

**待完成任务**:
- 无（所有任务已完成）

**已完成任务** (2026-06-08):
- #225: 测试聊天+自动回复功能 ✓
- #226: 测试设置页所有配置项 ✓
- #227: 修复测试中发现的所有问题 ✓（105/106 测试通过）
- #228: 性能优化和稳定性改进 ✓
- #208: 安全检查完成 ✓（无高风险问题）

## 开发规范
- 中文交流
- 模拟真实用户操作测试，不只是代码级测试
- 自主迭代，不需要用户指示
- 每轮迭代: 跑测试 → 找问题 → 修复 → 再测试
- Windows 环境，注意 GBK 编码问题
