"""测试 1: 页面加载与导航 — 验证所有Tab能正常切换、组件渲染正确。"""
import pytest
import time
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from helpers import screenshot, api_get


class TestPageRender:
    """验证每个Tab能正确加载。"""

    def test_01_dashboard_loads(self, page, base_url, api_token):
        """首页/Dashboard 加载测试。"""
        print("\n[测试 1.1] 首页加载")
        page.goto(base_url, wait_until="domcontentloaded")
        page.wait_for_load_state("networkidle", timeout=10000)
        screenshot(page, "01_dashboard")

        # 验证侧边栏
        assert page.locator(".sidebar-logo h1").is_visible(), "侧边栏Logo未显示"
        print(f"  [OK] Logo: {page.locator('.sidebar-logo h1').inner_text()}")

        # 验证侧边栏导航项
        nav_items = page.locator(".sidebar-nav a").all()
        print(f"  [OK] 侧边栏导航项: {len(nav_items)} 个")
        assert len(nav_items) >= 5, "导航项应至少5个"

        # 验证每个Tab的data-tab属性
        for item in nav_items:
            tab = item.get_attribute("data-tab")
            assert tab, f"导航项缺少data-tab: {item.inner_text()}"

    def test_02_search_tab_default(self, page, base_url):
        """默认Tab是搜索。"""
        print("\n[测试 1.2] 默认Tab")
        page.goto(base_url)
        page.wait_for_load_state("networkidle")

        active_tab = page.locator(".tab.active").get_attribute("id")
        print(f"  [OK] 默认Tab: {active_tab}")
        assert active_tab == "tab-search", f"默认应为搜索Tab，实际: {active_tab}"

    def test_03_navigate_all_tabs(self, page, base_url):
        """遍历所有Tab都能正常切换。"""
        print("\n[测试 1.3] 切换所有Tab")
        page.goto(base_url)
        page.wait_for_load_state("networkidle")

        tabs = ["applications", "chat", "wechat", "settings", "search"]
        for tab in tabs:
            page.locator(f'.sidebar-nav a[data-tab="{tab}"]').click()
            page.wait_for_timeout(300)
            active = page.locator(".tab.active").get_attribute("id")
            expected = f"tab-{tab}"
            print(f"  [OK] 切换到 {tab} -> 激活 {active}")
            assert active == expected, f"切换 {tab} 失败，激活的是 {active}"
            screenshot(page, f"02_tab_{tab}")

    def test_04_status_indicator(self, page, base_url):
        """侧边栏状态指示器。"""
        print("\n[测试 1.4] 状态指示器")
        page.goto(base_url)
        page.wait_for_load_state("networkidle")

        dots = page.locator(".dot").all()
        print(f"  [OK] 状态点数量: {len(dots)}")
        for dot in dots:
            classes = dot.get_attribute("class") or ""
            is_on = "on" in classes
            try:
                print(f"    {'[ON]' if is_on else '[OFF]'} {dot.get_attribute('title') or ''}")
            except UnicodeEncodeError:
                print(f"    {'[ON]' if is_on else '[OFF]'} (non-ASCII title)")

        # 启动按钮可见
        start_btn = page.locator("#btnStart")
        assert start_btn.is_visible(), "启动按钮应可见"
        print(f"  [OK] 启动按钮: {start_btn.inner_text()}")


class TestSearchUI:
    """搜索Tab UI 测试。"""

    def test_05_search_form_elements(self, page, base_url):
        """搜索表单元素完整性。"""
        print("\n[测试 1.5] 搜索表单")
        page.goto(base_url)
        page.wait_for_load_state("networkidle")

        # 关键词输入
        kw = page.locator("#searchKeyword, input[placeholder*='关键词']").first
        assert kw.is_visible(), "关键词输入框不可见"
        kw.fill("Python开发")
        print(f"  [OK] 输入关键词: {kw.input_value()}")

        # 城市选择
        city = page.locator("#searchCity, select").first
        if city.is_visible():
            options = city.locator("option").all()
            print(f"  [OK] 城市选项: {len(options)} 个")
            for opt in options[:5]:
                print(f"    - {opt.inner_text()}")

        # 翻页数
        max_pages = page.locator("#maxPages, input[type='number']").first
        if max_pages.is_visible():
            print(f"  [OK] 翻页数: {max_pages.input_value()}")

        screenshot(page, "03_search_form")

    def test_06_search_buttons(self, page, base_url):
        """搜索相关按钮。"""
        print("\n[测试 1.6] 搜索按钮")
        page.goto(base_url)
        page.wait_for_load_state("networkidle")

        buttons = ["#btnSearch", "button:has-text('一键搜索')", "button:has-text('一键投递')"]
        for sel in buttons:
            btn = page.locator(sel).first
            if btn.count() > 0 and btn.is_visible():
                print(f"  [OK] {sel}: {btn.inner_text()}")


class TestApplicationsUI:
    """投递记录Tab。"""

    def test_07_applications_tab(self, page, base_url):
        """投递记录Tab内容。"""
        print("\n[测试 1.7] 投递记录Tab")
        page.goto(base_url)
        page.wait_for_load_state("networkidle")
        page.locator('.sidebar-nav a[data-tab="applications"]').click()
        page.wait_for_timeout(500)

        # 统计卡片
        stat_cards = page.locator(".stat-card").all()
        print(f"  [OK] 统计卡片: {len(stat_cards)} 个")
        for card in stat_cards:
            num = card.locator(".num").inner_text()
            lbl = card.locator(".lbl").inner_text()
            print(f"    {num} - {lbl}")

        # 筛选按钮
        filter_btns = page.locator("button:has-text('全部'), button:has-text('待投递'), button:has-text('已投递'), button:has-text('已回复')").all()
        print(f"  [OK] 筛选按钮: {len(filter_btns)} 个")

        # 表格
        table = page.locator("table").first
        assert table.is_visible(), "表格不可见"
        headers = table.locator("th").all()
        print(f"  [OK] 表格列: {[h.inner_text() for h in headers]}")

        screenshot(page, "04_applications")


class TestChatUI:
    """聊天Tab。"""

    def test_08_chat_layout(self, page, base_url):
        """聊天界面布局。"""
        print("\n[测试 1.8] 聊天Tab布局")
        page.goto(base_url)
        page.wait_for_load_state("networkidle")
        page.locator('.sidebar-nav a[data-tab="chat"]').click()
        page.wait_for_timeout(500)

        # 聊天容器
        chat_container = page.locator(".chat-container")
        assert chat_container.is_visible(), "聊天容器不可见"
        print("  [OK] 聊天容器可见")

        # 聊天列表
        chat_list = page.locator(".chat-list")
        assert chat_list.is_visible(), "聊天列表不可见"
        print("  [OK] 聊天列表可见")

        # 聊天面板
        chat_pane = page.locator(".chat-pane")
        assert chat_pane.is_visible(), "聊天面板不可见"
        print("  [OK] 聊天面板可见")

        # 输入区
        textarea = page.locator(".input-wrapper textarea").first
        assert textarea.is_visible(), "聊天输入框不可见"
        print("  [OK] 聊天输入框可见")

        screenshot(page, "05_chat")

    def test_09_chat_quick_replies(self, page, base_url):
        """快捷回复按钮。"""
        print("\n[测试 1.9] 快捷回复")
        page.goto(base_url)
        page.wait_for_load_state("networkidle")
        page.locator('.sidebar-nav a[data-tab="chat"]').click()
        page.wait_for_timeout(500)

        quick_replies = page.locator(".quick-replies button, .quick-replies .qr-chip").all()
        print(f"  [OK] 快捷回复: {len(quick_replies)} 个")
        for qr in quick_replies[:5]:
            text = qr.inner_text()[:30]
            print(f"    - {text}")


class TestSettingsUI:
    """设置Tab。"""

    def test_10_settings_sections(self, page, base_url):
        """设置Tab的所有section。"""
        print("\n[测试 1.10] 设置Tab sections")
        page.goto(base_url)
        page.wait_for_load_state("networkidle")
        page.locator('.sidebar-nav a[data-tab="settings"]').click()
        page.wait_for_timeout(500)

        sections = page.locator(".section").all()
        print(f"  [OK] 设置分组: {len(sections)}")
        for sec in sections:
            h3 = sec.locator("h3").first
            if h3.count() > 0:
                print(f"    - {h3.inner_text()}")

        # 设置项
        setting_rows = page.locator(".setting-row").all()
        print(f"  [OK] 设置项: {len(setting_rows)}")

        screenshot(page, "06_settings")

    def test_11_ai_config_section(self, page, base_url):
        """AI 配置区域。"""
        print("\n[测试 1.11] AI配置")
        page.goto(base_url)
        page.wait_for_load_state("networkidle")
        page.locator('.sidebar-nav a[data-tab="settings"]').click()
        page.wait_for_timeout(500)

        # 查找 AI 相关输入
        ai_inputs = page.locator("input[placeholder*='API'], input[placeholder*='key'], input[placeholder*='URL'], input[placeholder*='模型']").all()
        print(f"  [OK] AI配置输入框: {len(ai_inputs)}")
        for inp in ai_inputs:
            ph = inp.get_attribute("placeholder") or ""
            val = inp.input_value() or ""
            masked = val[:8] + "..." if len(val) > 8 else "(空)"
            print(f"    [{ph}] = {masked}")
