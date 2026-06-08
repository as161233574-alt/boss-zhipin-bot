"""Playwright 端到端冒烟测试 — 测试所有前端页面和核心功能。"""

import asyncio
import json
import os
import sys
import io
from pathlib import Path

# 修复 Windows 控制台编码
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

# 从文件读取 API Token，避免硬编码泄露
_token_file = Path(__file__).parent.parent / ".boss_profile" / ".api_token"
if _token_file.exists():
    API_TOKEN = _token_file.read_text(encoding="utf-8").strip()
else:
    API_TOKEN = os.environ.get("BOSS_API_TOKEN", "")
    if not API_TOKEN:
        print("警告: 未找到 API Token，请设置环境变量 BOSS_API_TOKEN 或启动服务生成 .boss_profile/.api_token")
BASE_URL = "http://127.0.0.1:5173"
# 通过 Vite 代理访问 API，避免 CORS 问题
API_URL = ""

async def main():
    from playwright.async_api import async_playwright

    results = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1280, "height": 800})
        page = await context.new_page()

        # 注入 API token 到 localStorage
        await page.goto(BASE_URL)
        await page.evaluate(f"""() => {{
            localStorage.setItem('api_token', '{API_TOKEN}');
        }}""")

        # ========== 1. 首页/搜索页 ==========
        print("\n=== 测试 1: 搜索页加载 ===")
        try:
            await page.goto(f"{BASE_URL}/search", wait_until="networkidle", timeout=15000)
            await page.wait_for_timeout(2000)

            # 检查搜索栏
            search_input = page.locator('input[placeholder*="搜索"], input[placeholder*="岗位"], input[placeholder*="关键词"]').first
            if await search_input.is_visible(timeout=5000):
                print("  [OK] 搜索输入框可见")
                results.append(("搜索页", "搜索输入框", "PASS"))
            else:
                print("  [FAIL] 搜索输入框不可见")
                results.append(("搜索页", "搜索输入框", "FAIL"))

            # 检查搜索按钮
            search_btn = page.locator('button:has-text("搜索"), button:has-text("Search")').first
            if await search_btn.is_visible(timeout=3000):
                print("  [OK] 搜索按钮可见")
                results.append(("搜索页", "搜索按钮", "PASS"))
            else:
                print("  [FAIL] 搜索按钮不可见")
                results.append(("搜索页", "搜索按钮", "FAIL"))

            # 检查批量评分按钮
            score_btn = page.locator('button:has-text("批量评分")').first
            if await score_btn.is_visible(timeout=3000):
                print("  [OK] 批量评分按钮可见")
                results.append(("搜索页", "批量评分按钮", "PASS"))
            else:
                print("  [WARN] 批量评分按钮不可见")
                results.append(("搜索页", "批量评分按钮", "WARN"))

            # 检查智能投递按钮
            apply_btn = page.locator('button:has-text("智能投递")').first
            if await apply_btn.is_visible(timeout=3000):
                print("  [OK] 智能投递按钮可见")
                results.append(("搜索页", "智能投递按钮", "PASS"))
            else:
                print("  [WARN] 智能投递按钮不可见")
                results.append(("搜索页", "智能投递按钮", "WARN"))

            # 截图
            await page.screenshot(path="tests/screenshots/01_search_page.png", full_page=True)
            print("  [OK] 截图已保存")
        except Exception as e:
            print(f"  [FAIL] 搜索页测试异常: {e}")
            results.append(("搜索页", "页面加载", f"FAIL: {e}"))

        # ========== 2. 设置页 ==========
        print("\n=== 测试 2: 设置页加载 ===")
        try:
            await page.goto(f"{BASE_URL}/settings", wait_until="networkidle", timeout=15000)
            await page.wait_for_timeout(2000)

            # 检查设置项
            settings_items = [
                ("AI 配置", "AI 配置"),
                ("搜索配置", "搜索配置"),
                ("投递配置", "投递配置"),
                ("聊天配置", "聊天配置"),
            ]
            for label, desc in settings_items:
                item = page.locator(f'text="{label}"').first
                if await item.is_visible(timeout=3000):
                    print(f"  [OK] {desc} 区块可见")
                    results.append(("设置页", f"{desc} 区块", "PASS"))
                else:
                    print(f"  [WARN] {desc} 区块不可见")
                    results.append(("设置页", f"{desc} 区块", "WARN"))

            # 检查自动回复开关
            auto_reply_toggle = page.locator('text="自动回复"').first
            if await auto_reply_toggle.is_visible(timeout=3000):
                print("  [OK] 自动回复开关可见")
                results.append(("设置页", "自动回复开关", "PASS"))
            else:
                print("  [WARN] 自动回复开关不可见")
                results.append(("设置页", "自动回复开关", "WARN"))

            # 检查保存按钮
            save_btn = page.locator('button:has-text("保存")').first
            if await save_btn.is_visible(timeout=3000):
                print("  [OK] 保存按钮可见")
                results.append(("设置页", "保存按钮", "PASS"))
            else:
                print("  [WARN] 保存按钮不可见")
                results.append(("设置页", "保存按钮", "WARN"))

            await page.screenshot(path="tests/screenshots/02_settings_page.png", full_page=True)
        except Exception as e:
            print(f"  [FAIL] 设置页测试异常: {e}")
            results.append(("设置页", "页面加载", f"FAIL: {e}"))

        # ========== 3. 聊天页 ==========
        print("\n=== 测试 3: 聊天页加载 ===")
        try:
            await page.goto(f"{BASE_URL}/chat", wait_until="networkidle", timeout=15000)
            await page.wait_for_timeout(2000)

            # 检查会话列表
            conv_list = page.locator('[class*="conversation"], [class*="chat-list"], [class*="sidebar"]').first
            if await conv_list.is_visible(timeout=5000):
                print("  [OK] 会话列表区域可见")
                results.append(("聊天页", "会话列表", "PASS"))
            else:
                print("  [WARN] 会话列表区域不可见")
                results.append(("聊天页", "会话列表", "WARN"))

            # 检查页面标题或关键文字
            chat_title = page.locator('text="聊天", text="会话", text="消息"').first
            if await chat_title.is_visible(timeout=3000):
                print("  [OK] 聊天页标题可见")
                results.append(("聊天页", "页面标题", "PASS"))
            else:
                print("  [WARN] 聊天页标题不可见")
                results.append(("聊天页", "页面标题", "WARN"))

            await page.screenshot(path="tests/screenshots/03_chat_page.png", full_page=True)
        except Exception as e:
            print(f"  [FAIL] 聊天页测试异常: {e}")
            results.append(("聊天页", "页面加载", f"FAIL: {e}"))

        # ========== 4. Agent 页 ==========
        print("\n=== 测试 4: Agent 页加载 ===")
        try:
            await page.goto(f"{BASE_URL}/agents", wait_until="networkidle", timeout=15000)
            await page.wait_for_timeout(2000)

            # 检查 Agent 列表
            agent_items = page.locator('[class*="agent"], [class*="card"]').all()
            count = len(await agent_items)
            if count > 0:
                print(f"  [OK] 找到 {count} 个 Agent 卡片")
                results.append(("Agent页", "Agent 卡片", f"PASS ({count}个)"))
            else:
                print("  [WARN] 未找到 Agent 卡片")
                results.append(("Agent页", "Agent 卡片", "WARN"))

            await page.screenshot(path="tests/screenshots/04_agents_page.png", full_page=True)
        except Exception as e:
            print(f"  [FAIL] Agent 页测试异常: {e}")
            results.append(("Agent页", "页面加载", f"FAIL: {e}"))

        # ========== 5. 导航测试 ==========
        print("\n=== 测试 5: 页面导航 ===")
        try:
            nav_links = await page.locator('a[href]').all()
            nav_count = len(nav_links)
            if nav_count >= 3:
                print(f"  [OK] 页面有 {nav_count} 个链接")
                results.append(("导航", "页面链接", f"PASS ({nav_count}个)"))
            else:
                print(f"  [WARN] 页面只有 {nav_count} 个链接")
                results.append(("导航", "页面链接", f"WARN ({nav_count}个)"))
        except Exception as e:
            print(f"  [FAIL] 导航测试异常: {e}")
            results.append(("导航", "导航测试", f"FAIL: {e}"))

        # ========== 6. API 健康检查（通过 Vite 代理） ==========
        print("\n=== 测试 6: API 健康检查 ===")
        api_endpoints = [
            ("/api/status", "系统状态"),
            ("/api/settings", "设置"),
            ("/api/jobs?limit=5", "岗位列表"),
            ("/api/auto-apply-logs?limit=5", "投递日志"),
        ]
        for endpoint, desc in api_endpoints:
            try:
                resp = await page.evaluate(f"""async () => {{
                    const res = await fetch('{endpoint}', {{
                        headers: {{ 'Authorization': 'Bearer {API_TOKEN}' }}
                    }});
                    return {{ status: res.status, ok: res.ok }};
                }}""")
                if resp["ok"]:
                    print(f"  [OK] {desc} ({endpoint}) -> {resp['status']}")
                    results.append(("API", desc, "PASS"))
                else:
                    print(f"  [FAIL] {desc} ({endpoint}) -> {resp['status']}")
                    results.append(("API", desc, f"FAIL ({resp['status']})"))
            except Exception as e:
                print(f"  [FAIL] {desc} ({endpoint}) -> {e}")
                results.append(("API", desc, f"FAIL: {e}"))

        # ========== 7. WebSocket 连接测试 ==========
        print("\n=== 测试 7: WebSocket 连接 ===")
        try:
            ws_result = await page.evaluate(f"""() => {{
                return new Promise((resolve) => {{
                    const ws = new WebSocket('ws://127.0.0.1:8000/ws?token={API_TOKEN}');
                    ws.onopen = () => {{
                        ws.close();
                        resolve({{ success: true }});
                    }};
                    ws.onerror = (e) => {{
                        resolve({{ success: false, error: '连接失败' }});
                    }};
                    setTimeout(() => resolve({{ success: false, error: '超时' }}), 5000);
                }});
            }}""")
            if ws_result["success"]:
                print("  [OK] WebSocket 连接成功")
                results.append(("WebSocket", "连接", "PASS"))
            else:
                print(f"  [FAIL] WebSocket 连接失败: {ws_result.get('error')}")
                results.append(("WebSocket", "连接", f"FAIL: {ws_result.get('error')}"))
        except Exception as e:
            print(f"  [FAIL] WebSocket 测试异常: {e}")
            results.append(("WebSocket", "连接", f"FAIL: {e}"))

        await browser.close()

    # ========== 汇总 ==========
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    pass_count = sum(1 for _, _, r in results if r.startswith("PASS"))
    fail_count = sum(1 for _, _, r in results if r.startswith("FAIL"))
    warn_count = sum(1 for _, _, r in results if r.startswith("WARN"))
    total = len(results)

    for page_name, item, result in results:
        status = "PASS" if result.startswith("PASS") else "FAIL" if result.startswith("FAIL") else "WARN"
        print(f"  [{status}] {page_name} - {item}: {result}")

    print(f"\n总计: {total} 项 | 通过: {pass_count} | 失败: {fail_count} | 警告: {warn_count}")
    print(f"通过率: {pass_count/total*100:.1f}%")

    return fail_count == 0

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
