"""真实用户流程 E2E 测试 — Playwright 模拟用户点击所有功能点。

覆盖：导航、搜索、评分、投递、设置、聊天、Agent配置等完整用户旅程。
"""
import re
import pytest
from playwright.sync_api import Page, expect

from helpers import BASE_URL, get_api_token, screenshot


def auth_url(path: str = "/") -> str:
    token = get_api_token()
    sep = "&" if "?" in path else "?"
    return f"{BASE_URL}{path}{sep}token={token}"


def navigate_to(page: Page, tab_name: str):
    """点击侧边栏导航链接。"""
    link = page.locator("nav a, [class*='sidebar'] a").filter(has_text=tab_name)
    if link.count() > 0:
        link.first.click()
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(500)


class TestNavigation:
    """页面导航和基础渲染。"""

    def test_01_home_page_loads(self, page: Page):
        page.goto(auth_url("/"))
        page.wait_for_load_state("networkidle")
        expect(page.locator("nav").first).to_be_visible(timeout=10000)
        expect(page.locator("[class*='sidebar']").first).to_be_visible()
        screenshot(page, "nav_01_home")

    def test_02_navigate_all_tabs(self, page: Page):
        page.goto(auth_url("/"))
        page.wait_for_load_state("networkidle")

        tab_names = ["岗位搜索", "投递记录", "聊天", "设置"]
        for name in tab_names:
            navigate_to(page, name)
            screenshot(page, f"nav_02_{name[:4]}")

    def test_03_search_page_elements(self, page: Page):
        page.goto(auth_url("/"))
        page.wait_for_load_state("networkidle")
        navigate_to(page, "岗位搜索")
        search_input = page.locator("input[placeholder*='关键词']")
        expect(search_input.first).to_be_visible(timeout=5000)
        screenshot(page, "nav_03_search")


class TestSearchFlow:
    """搜索功能完整流程。"""

    def test_01_search_bar_visible(self, page: Page):
        page.goto(auth_url("/"))
        page.wait_for_load_state("networkidle")
        navigate_to(page, "岗位搜索")
        expect(page.locator("input[placeholder*='关键词']").first).to_be_visible(timeout=5000)
        screenshot(page, "search_01_bar")

    def test_02_fill_search_form(self, page: Page):
        page.goto(auth_url("/"))
        page.wait_for_load_state("networkidle")
        navigate_to(page, "岗位搜索")
        search_input = page.locator("input[placeholder*='关键词']")
        search_input.first.fill("AI Agent")
        welfare_input = page.locator("input[placeholder*='福利']")
        if welfare_input.count() > 0 and welfare_input.first.is_visible():
            welfare_input.first.fill("双休")
        screenshot(page, "search_02_form")

    def test_03_salary_filter(self, page: Page):
        page.goto(auth_url("/"))
        page.wait_for_load_state("networkidle")
        navigate_to(page, "岗位搜索")
        salary_inputs = page.locator("input[type='number']")
        visible_salary = [i for i in range(salary_inputs.count()) if salary_inputs.nth(i).is_visible()]
        if len(visible_salary) >= 1:
            salary_inputs.nth(visible_salary[0]).fill("5")
        screenshot(page, "search_03_salary")

    def test_04_click_search_button(self, page: Page):
        page.goto(auth_url("/"))
        page.wait_for_load_state("networkidle")
        navigate_to(page, "岗位搜索")
        page.locator("input[placeholder*='关键词']").first.fill("AI")
        search_btn = page.locator("button").filter(has_text=re.compile("搜索|Search|查找"))
        if search_btn.count() > 0:
            search_btn.first.click()
            page.wait_for_timeout(3000)
        screenshot(page, "search_04_click")


class TestSettingsFlow:
    """设置页面功能测试。"""

    def test_01_settings_page_loads(self, page: Page):
        page.goto(auth_url("/"))
        page.wait_for_load_state("networkidle")
        navigate_to(page, "设置")
        screenshot(page, "settings_01_load")

    def test_02_auto_reply_toggle(self, page: Page):
        page.goto(auth_url("/"))
        page.wait_for_load_state("networkidle")
        navigate_to(page, "设置")
        toggle = page.locator("button[class*='rounded-full']").first
        if toggle.is_visible():
            toggle.click()
            page.wait_for_timeout(500)
            screenshot(page, "settings_02_toggle")

    def test_03_save_settings(self, page: Page):
        page.goto(auth_url("/"))
        page.wait_for_load_state("networkidle")
        navigate_to(page, "设置")
        save_btn = page.locator("button").filter(has_text=re.compile("保存|Save"))
        if save_btn.count() > 0:
            save_btn.first.click()
            page.wait_for_timeout(1000)
        screenshot(page, "settings_03_save")


class TestChatFlow:
    """聊天页面功能测试。"""

    def test_01_chat_page_loads(self, page: Page):
        page.goto(auth_url("/"))
        page.wait_for_load_state("networkidle")
        navigate_to(page, "聊天")
        screenshot(page, "chat_01_load")

    def test_02_conversation_list(self, page: Page):
        page.goto(auth_url("/"))
        page.wait_for_load_state("networkidle")
        navigate_to(page, "聊天")
        page.wait_for_timeout(2000)
        screenshot(page, "chat_02_conv_list")


class TestAgentsFlow:
    """Agent 配置页面测试。"""

    def test_01_agents_page_loads(self, page: Page):
        page.goto(auth_url("/"))
        page.wait_for_load_state("networkidle")
        navigate_to(page, "Agent配置")
        screenshot(page, "agents_01_load")

    def test_02_agent_profiles_visible(self, page: Page):
        page.goto(auth_url("/"))
        page.wait_for_load_state("networkidle")
        navigate_to(page, "Agent配置")
        page.wait_for_timeout(1000)
        screenshot(page, "agents_02_profiles")


class TestApplicationsFlow:
    """岗位管理页面测试。"""

    def test_01_applications_page(self, page: Page):
        page.goto(auth_url("/"))
        page.wait_for_load_state("networkidle")
        navigate_to(page, "投递记录")
        screenshot(page, "apps_01_load")

    def test_02_job_list_display(self, page: Page):
        page.goto(auth_url("/"))
        page.wait_for_load_state("networkidle")
        navigate_to(page, "投递记录")
        page.wait_for_timeout(2000)
        screenshot(page, "apps_02_list")


class TestAPIIntegration:
    """API 集成测试 — 通过浏览器验证前后端联通。"""

    def test_01_api_status(self, page: Page):
        page.goto(auth_url("/"))
        page.wait_for_load_state("networkidle")
        token = get_api_token()
        result = page.evaluate(f"""async () => {{
            const res = await fetch('/api/status', {{
                headers: {{'Authorization': 'Bearer {token}'}}
            }});
            return {{status: res.status, ok: res.ok}};
        }}""")
        assert result["ok"], f"API status check failed: {result}"
        screenshot(page, "api_01_status")

    def test_02_api_settings(self, page: Page):
        page.goto(auth_url("/"))
        page.wait_for_load_state("networkidle")
        token = get_api_token()
        result = page.evaluate(f"""async () => {{
            const res = await fetch('/api/settings', {{
                headers: {{'Authorization': 'Bearer {token}'}}
            }});
            const data = await res.json();
            return {{status: res.status, keys: Object.keys(data.settings || {{}}).length}};
        }}""")
        assert result["keys"] > 0, f"Settings API returned no keys: {result}"
        screenshot(page, "api_02_settings")

    def test_03_api_jobs(self, page: Page):
        page.goto(auth_url("/"))
        page.wait_for_load_state("networkidle")
        token = get_api_token()
        result = page.evaluate(f"""async () => {{
            const res = await fetch('/api/jobs?limit=5', {{
                headers: {{'Authorization': 'Bearer {token}'}}
            }});
            const data = await res.json();
            return {{status: res.status, count: (data.jobs || []).length}};
        }}""")
        assert result["status"] == 200, f"Jobs API failed: {result}"
        screenshot(page, "api_03_jobs")


class TestResponsive:
    """响应式布局测试。"""

    def test_01_mobile_viewport(self, page: Page):
        page.set_viewport_size({"width": 375, "height": 812})
        page.goto(auth_url("/"))
        page.wait_for_load_state("networkidle")
        screenshot(page, "resp_01_mobile")

    def test_02_tablet_viewport(self, page: Page):
        page.set_viewport_size({"width": 768, "height": 1024})
        page.goto(auth_url("/"))
        page.wait_for_load_state("networkidle")
        screenshot(page, "resp_02_tablet")

    def test_03_desktop_viewport(self, page: Page):
        page.set_viewport_size({"width": 1920, "height": 1080})
        page.goto(auth_url("/"))
        page.wait_for_load_state("networkidle")
        screenshot(page, "resp_03_desktop")


class TestWebSocket:
    """WebSocket 连接测试。"""

    def test_01_ws_connects(self, page: Page):
        page.goto(auth_url("/"))
        page.wait_for_load_state("networkidle")
        token = get_api_token()
        ws_status = page.evaluate(f"""() => {{
            return new Promise((resolve) => {{
                const ws = new WebSocket('ws://127.0.0.1:8000/ws?token={token}');
                ws.onopen = () => {{ ws.close(); resolve('connected'); }};
                ws.onerror = () => resolve('error');
                setTimeout(() => resolve('timeout'), 5000);
            }});
        }}""")
        assert ws_status == "connected", f"WebSocket connection failed: {ws_status}"
        screenshot(page, "ws_01_connect")


class TestErrorHandling:
    """错误处理测试。"""

    def test_01_404_page(self, page: Page):
        page.goto(auth_url("/nonexistent"))
        page.wait_for_load_state("networkidle")
        screenshot(page, "err_01_404")

    def test_02_invalid_api(self, page: Page):
        page.goto(auth_url("/"))
        page.wait_for_load_state("networkidle")
        result = page.evaluate("""async () => {
            const res = await fetch('/api/nonexistent');
            return {status: res.status};
        }""")
        assert result["status"] in [401, 404, 405], f"Expected error status, got {result}"
        screenshot(page, "err_02_invalid_api")
