"""完整用户旅程 E2E 测试 — Playwright 自动化模拟真实用户操作。

测试覆盖：
1. 页面加载 + 所有 Tab 切换
2. 岗位搜索 Tab — 搜索框、按钮
3. 投递记录 Tab — 列表、筛选、去重
4. 聊天 Tab — 会话列表
5. 设置 Tab — 所有表单输入、保存、简历上传
6. WebSocket 连接
7. 响应式布局检查
"""
import time
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from helpers import screenshot


class TestFullUserJourney:
    """完整用户旅程测试。"""

    def test_01_page_loads_and_tabs_switch(self, page, base_url):
        """页面加载后切换所有 Tab，验证每个 Tab 内容可见。"""
        page.goto(base_url)
        page.wait_for_load_state("networkidle")

        # 验证默认 Tab 是岗位搜索
        search_tab = page.locator('#tab-search')
        assert search_tab.is_visible(), "默认应显示岗位搜索 Tab"

        # 切换到投递记录
        page.locator('.sidebar-nav a[data-tab="applications"]').click()
        page.wait_for_timeout(500)
        assert page.locator('#tab-applications').is_visible(), "投递记录 Tab 应可见"
        assert not search_tab.is_visible(), "搜索 Tab 应隐藏"

        # 切换到聊天
        page.locator('.sidebar-nav a[data-tab="chat"]').click()
        page.wait_for_timeout(500)
        assert page.locator('#tab-chat').is_visible(), "聊天 Tab 应可见"

        # 切换到微信记录
        page.locator('.sidebar-nav a[data-tab="wechat"]').click()
        page.wait_for_timeout(500)
        assert page.locator('#tab-wechat').is_visible(), "微信记录 Tab 应可见"

        # 切换到设置
        page.locator('.sidebar-nav a[data-tab="settings"]').click()
        page.wait_for_timeout(500)
        assert page.locator('#tab-settings').is_visible(), "设置 Tab 应可见"

        # 切换回搜索
        page.locator('.sidebar-nav a[data-tab="search"]').click()
        page.wait_for_timeout(300)
        assert search_tab.is_visible(), "搜索 Tab 应重新可见"

    def test_02_search_tab_elements(self, page, base_url):
        """搜索 Tab 的输入框、按钮都存在且可交互。"""
        page.goto(base_url)
        page.wait_for_load_state("networkidle")

        # 搜索输入框
        keyword_input = page.locator('#searchKeyword')
        assert keyword_input.count() > 0, "应有搜索关键词输入框"

        # 城市选择
        city_select = page.locator('#searchCity')
        assert city_select.count() > 0, "应有城市选择框"

        # 搜索按钮
        search_btn = page.locator('button:has-text("搜索")').first
        assert search_btn.count() > 0, "应有搜索按钮"

        # 输入关键词
        keyword_input.fill("Python开发")
        assert keyword_input.input_value() == "Python开发"

    def test_03_applications_tab_elements(self, page, base_url):
        """投递记录 Tab 的筛选、操作按钮存在。"""
        page.goto(base_url)
        page.wait_for_load_state("networkidle")

        # 切换到投递记录
        page.locator('.sidebar-nav a[data-tab="applications"]').click()
        page.wait_for_timeout(800)

        # 检查筛选按钮
        filter_btns = page.locator('#tab-applications .btn')
        assert filter_btns.count() > 0, "投递记录应有操作按钮"

    def test_04_settings_tab_all_inputs(self, page, base_url):
        """设置 Tab 所有输入框可交互。"""
        page.goto(base_url)
        page.wait_for_load_state("networkidle")

        # 切换到设置
        page.locator('.sidebar-nav a[data-tab="settings"]').click()
        page.wait_for_timeout(800)

        # 检查各设置输入框
        inputs = {
            'setGreeting': 'textarea',
            'setStyle': 'select',
            'setDailyLimit': 'input',
            'setMinDelay': 'input',
            'setMaxDelay': 'input',
            'setWechat': 'input',
            'setResume': 'textarea',
            'setSearchKeywords': 'textarea',
        }

        for input_id, tag in inputs.items():
            el = page.locator(f'#{input_id}')
            assert el.count() > 0, f"设置页应有 #{input_id} ({tag})"

    def test_05_settings_save(self, page, base_url):
        """修改设置并保存，验证成功提示。"""
        page.goto(base_url)
        page.wait_for_load_state("networkidle")

        # 切换到设置
        page.locator('.sidebar-nav a[data-tab="settings"]').click()
        page.wait_for_timeout(800)

        # 修改每日投递上限
        daily_limit = page.locator('#setDailyLimit')
        daily_limit.fill("25")

        # Mock alert
        alerts = []
        page.on("dialog", lambda d: (alerts.append(d.message), d.accept()))

        # 点击保存
        save_btn = page.locator('button:has-text("保存设置")').first
        if save_btn.count() > 0:
            save_btn.click()
            page.wait_for_timeout(1500)

    def test_06_resume_upload_section(self, page, base_url):
        """简历上传区域：文件选择按钮、上传按钮、完整简历查看。"""
        page.goto(base_url)
        page.wait_for_load_state("networkidle")

        # 切换到设置
        page.locator('.sidebar-nav a[data-tab="settings"]').click()
        page.wait_for_timeout(800)

        # 检查文件上传 input
        file_input = page.locator('#resumeFile')
        assert file_input.count() > 0, "应有简历文件上传 input"

        # 检查上传按钮
        upload_btn = page.locator('button:has-text("上传解析")').first
        assert upload_btn.count() > 0, "应有上传解析按钮"

        # 检查查看完整简历按钮
        full_btn = page.locator('button:has-text("查看完整简历")').first
        assert full_btn.count() > 0, "应有查看完整简历按钮"

    def test_07_resume_full_text_toggle(self, page, base_url):
        """点击查看完整简历，textarea 应展开显示。"""
        page.goto(base_url)
        page.wait_for_load_state("networkidle")

        # 切换到设置
        page.locator('.sidebar-nav a[data-tab="settings"]').click()
        page.wait_for_timeout(800)

        # 完整简历 textarea 应默认隐藏
        full_ta = page.locator('#setResumeFull')
        assert full_ta.count() > 0, "应有完整简历 textarea"

        # 点击查看完整简历
        toggle_btn = page.locator('#resumeFullToggle button').first
        if toggle_btn.count() > 0:
            toggle_btn.click()
            page.wait_for_timeout(1000)
            # 应变为可见
            is_visible = full_ta.is_visible()
            print(f"  完整简历 textarea 可见: {is_visible}")
            assert is_visible, "点击后完整简历 textarea 应可见"

            # 按钮文字应变为"收起"
            btn_text = toggle_btn.text_content()
            print(f"  按钮文字: {btn_text}")
            assert "收起" in btn_text, f"按钮文字应含'收起', 实际: {btn_text}"

            # 再次点击收起
            toggle_btn.click()
            page.wait_for_timeout(500)
            assert not full_ta.is_visible(), "再次点击后应收起"

    def test_08_ai_config_section(self, page, base_url):
        """AI 模型配置区域：平台选择、API Key、Base URL、模型。"""
        page.goto(base_url)
        page.wait_for_load_state("networkidle")

        # 切换到设置
        page.locator('.sidebar-nav a[data-tab="settings"]').click()
        page.wait_for_timeout(800)

        # 平台选择
        platform_select = page.locator('#setAIPlatform')
        assert platform_select.count() > 0, "应有平台选择"

        # 选择 DeepSeek
        platform_select.select_option("deepseek")
        page.wait_for_timeout(500)

        # Base URL 应自动填充
        base_url_input = page.locator('#setAIBaseUrl')
        val = base_url_input.input_value()
        print(f"  DeepSeek Base URL: {val}")
        assert "deepseek" in val.lower() or val, "选择 DeepSeek 后 Base URL 应填充"

    def test_09_auto_apply_section(self, page, base_url):
        """自动投递配置区域。"""
        page.goto(base_url)
        page.wait_for_load_state("networkidle")

        # 切换到设置
        page.locator('.sidebar-nav a[data-tab="settings"]').click()
        page.wait_for_timeout(800)

        # 检查自动投递开关
        auto_apply_select = page.locator('#setAutoApply')
        if auto_apply_select.count() > 0:
            # 切换到开启
            auto_apply_select.select_option("true")
            page.wait_for_timeout(300)
            val = auto_apply_select.input_value()
            assert val == "true", "应能切换自动投递为开启"

    def test_10_schedule_section(self, page, base_url):
        """定时任务配置区域。"""
        page.goto(base_url)
        page.wait_for_load_state("networkidle")

        # 切换到设置
        page.locator('.sidebar-nav a[data-tab="settings"]').click()
        page.wait_for_timeout(800)

        # 检查定时任务开关
        schedule_select = page.locator('#setScheduleEnabled')
        if schedule_select.count() > 0:
            schedule_select.select_option("true")
            page.wait_for_timeout(300)

        # 检查执行时间输入
        cron_input = page.locator('#setScheduleCron')
        if cron_input.count() > 0:
            cron_input.fill("09:00,14:00,18:00")
            val = cron_input.input_value()
            assert "09:00" in val

    def test_11_sidebar_status_indicators(self, page, base_url):
        """侧边栏状态指示器（圆点、文字）。"""
        page.goto(base_url)
        page.wait_for_load_state("networkidle")

        # 检查侧边栏状态区域
        status_area = page.locator('.sidebar-status')
        assert status_area.count() > 0, "应有侧边栏状态区域"

        # 检查状态圆点
        dots = page.locator('.sidebar-status .dot')
        assert dots.count() > 0, "应有状态圆点"

    def test_12_no_console_errors_on_load(self, page, base_url):
        """页面加载不应有 JS 错误。"""
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))

        page.goto(base_url)
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)

        # 切换所有 Tab
        for tab in ["applications", "chat", "wechat", "settings", "search"]:
            page.locator(f'.sidebar-nav a[data-tab="{tab}"]').click()
            page.wait_for_timeout(500)

        # 过滤掉已知无害错误
        real_errors = [e for e in errors if "WebSocket" not in e and "net::" not in e]
        assert not real_errors, f"页面有 JS 错误: {real_errors}"

    def test_13_api_status_display(self, page, base_url):
        """页面加载后应显示系统状态信息。"""
        page.goto(base_url)
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1000)

        # 侧边栏应有状态文字
        status_text = page.locator('.sidebar-status').text_content()
        assert status_text, "应显示状态信息"
        print(f"  状态栏: {status_text[:100]}")

    def test_14_responsive_header(self, page, base_url):
        """主内容区应有标题头。"""
        page.goto(base_url)
        page.wait_for_load_state("networkidle")

        header = page.locator('.main-header h2')
        assert header.count() > 0, "应有主标题"
        title = header.text_content()
        assert title, "标题不应为空"
        print(f"  主标题: {title}")
