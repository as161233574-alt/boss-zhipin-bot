"""真实用户操作流程 E2E 测试。

模拟真实用户从打开页面到完成一系列操作的完整流程。
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from helpers import screenshot, api_post, api_get


class TestRealUserFlow:
    """模拟真实用户操作流程。"""

    def test_01_user_opens_page_and_checks_status(self, page, base_url):
        """用户打开页面，检查系统状态。"""
        page.goto(base_url)
        page.wait_for_load_state("networkidle")

        # 检查页面标题
        title = page.title()
        assert "BOSS" in title, f"页面标题应含 BOSS: {title}"

        # 检查侧边栏状态
        status = page.locator('.sidebar-status').text_content()
        assert status, "应显示状态信息"

        # 检查主标题
        header = page.locator('.main-header h2').text_content()
        assert header == "岗位搜索", f"默认主标题应为岗位搜索: {header}"

        screenshot(page, "01_user_opens_page")

    def test_02_user_switches_all_tabs(self, page, base_url):
        """用户逐个切换所有 Tab，确认每个 Tab 内容加载。"""
        page.goto(base_url)
        page.wait_for_load_state("networkidle")

        tabs = ["applications", "chat", "wechat", "settings", "search"]
        for tab in tabs:
            page.locator(f'.sidebar-nav a[data-tab="{tab}"]').click()
            page.wait_for_timeout(500)
            tab_el = page.locator(f'#tab-{tab}')
            assert tab_el.is_visible(), f"Tab {tab} 应可见"

            # 检查 active 状态
            link = page.locator(f'.sidebar-nav a[data-tab="{tab}"]')
            assert "active" in link.get_attribute("class"), f"Tab {tab} 应有 active class"

        screenshot(page, "02_all_tabs_switched")

    def test_03_user_views_search_tab(self, page, base_url):
        """用户查看搜索 Tab，检查所有元素。"""
        page.goto(base_url)
        page.wait_for_load_state("networkidle")

        # 搜索输入框
        keyword = page.locator('#searchKeyword')
        assert keyword.count() > 0

        # 城市选择
        city = page.locator('#searchCity')
        assert city.count() > 0

        # 搜索按钮
        search_btn = page.locator('#btnSearch')
        assert search_btn.count() > 0

        # 一键搜索按钮
        batch_btn = page.locator('button:has-text("一键搜索")')
        assert batch_btn.count() > 0

        # 一键投递按钮
        apply_btn = page.locator('button:has-text("一键投递")')
        assert apply_btn.count() > 0

        # 福利筛选
        welfare = page.locator('#searchWelfare')
        assert welfare.count() > 0

        # 页数
        max_pages = page.locator('#searchMaxPages')
        assert max_pages.count() > 0

        screenshot(page, "03_search_tab")

    def test_04_user_views_applications_tab(self, page, base_url):
        """用户查看投递记录 Tab，检查统计卡片和筛选按钮。"""
        page.goto(base_url)
        page.wait_for_load_state("networkidle")

        page.locator('.sidebar-nav a[data-tab="applications"]').click()
        page.wait_for_timeout(800)

        # 统计卡片
        stats = page.locator('.stat-card')
        assert stats.count() >= 4, "应有至少 4 个统计卡片"

        # 筛选按钮
        filter_btns = page.locator('#tab-applications .btn')
        assert filter_btns.count() > 0, "应有筛选按钮"

        # 表格
        table = page.locator('#tab-applications table')
        assert table.count() > 0, "应有岗位表格"

        # 趋势图区域
        trend = page.locator('#trendSection')
        assert trend.count() > 0, "应有趋势图区域"

        screenshot(page, "04_applications_tab")

    def test_05_user_views_chat_tab(self, page, base_url):
        """用户查看聊天 Tab，检查会话列表和消息区域。"""
        page.goto(base_url)
        page.wait_for_load_state("networkidle")

        page.locator('.sidebar-nav a[data-tab="chat"]').click()
        page.wait_for_timeout(800)

        # 会话列表
        conv_list = page.locator('#conversationList')
        assert conv_list.count() > 0, "应有会话列表"

        # 搜索框
        conv_search = page.locator('#convSearch')
        assert conv_search.count() > 0, "应有会话搜索框"

        # 消息区域
        messages = page.locator('#chatMessages')
        assert messages.count() > 0, "应有消息区域"

        # 输入框
        chat_input = page.locator('#chatInput')
        assert chat_input.count() > 0, "应有消息输入框"

        screenshot(page, "05_chat_tab")

    def test_06_user_views_settings_tab(self, page, base_url):
        """用户查看设置 Tab，检查所有设置区域。"""
        page.goto(base_url)
        page.wait_for_load_state("networkidle")

        page.locator('.sidebar-nav a[data-tab="settings"]').click()
        page.wait_for_timeout(800)

        # 检查所有设置区域
        sections = page.locator('#tab-settings .section h3')
        section_texts = [sections.nth(i).text_content() for i in range(sections.count())]
        print(f"  设置区域: {section_texts}")

        assert "招呼语设置" in section_texts
        assert "个人资料" in section_texts
        assert "搜索关键词" in section_texts
        assert "AI模型配置" in section_texts
        assert "定时任务" in section_texts
        assert "自动投递" in section_texts

        screenshot(page, "06_settings_tab")

    def test_07_user_modifies_and_saves_settings(self, page, base_url):
        """用户修改设置并保存。"""
        page.goto(base_url)
        page.wait_for_load_state("networkidle")

        page.locator('.sidebar-nav a[data-tab="settings"]').click()
        page.wait_for_timeout(800)

        # 修改招呼语
        greeting = page.locator('#setGreeting')
        greeting.fill("你好，我对这个岗位很感兴趣！")

        # 修改每日投递上限
        daily_limit = page.locator('#setDailyLimit')
        daily_limit.fill("20")

        # 修改微信号
        wechat = page.locator('#setWechat')
        wechat.fill("test_wechat_123")

        # Mock alert
        alerts = []
        page.on("dialog", lambda d: (alerts.append(d.message), d.accept()))

        # 保存设置
        save_btn = page.locator('button:has-text("保存设置")').first
        save_btn.click()
        page.wait_for_timeout(1500)

        screenshot(page, "07_settings_saved")

    def test_08_user_configures_ai_model(self, page, base_url):
        """用户配置 AI 模型。"""
        page.goto(base_url)
        page.wait_for_load_state("networkidle")

        page.locator('.sidebar-nav a[data-tab="settings"]').click()
        page.wait_for_timeout(800)

        # 选择 DeepSeek 平台
        platform = page.locator('#setAIPlatform')
        platform.select_option("deepseek")
        page.wait_for_timeout(500)

        # 检查 Base URL 自动填充
        base_url_input = page.locator('#setAIBaseUrl')
        url_val = base_url_input.input_value()
        assert "deepseek" in url_val.lower(), f"Base URL 应含 deepseek: {url_val}"

        # 检查模型列表
        model_input = page.locator('#setAIModel')
        assert model_input.count() > 0

        screenshot(page, "08_ai_config")

    def test_09_user_toggles_auto_apply(self, page, base_url):
        """用户切换自动投递开关。"""
        page.goto(base_url)
        page.wait_for_load_state("networkidle")

        page.locator('.sidebar-nav a[data-tab="settings"]').click()
        page.wait_for_timeout(800)

        # 切换自动投递
        auto_apply = page.locator('#setAutoApply')
        auto_apply.select_option("true")
        page.wait_for_timeout(300)

        # 设置阈值
        threshold = page.locator('#setAutoApplyThreshold')
        threshold.fill("75")

        # 检查 HR 活跃度要求
        hr_active = page.locator('#setAutoApplyHrActive')
        assert hr_active.count() > 0

        screenshot(page, "09_auto_apply")

    def test_10_user_uploads_resume(self, page, base_url):
        """用户上传简历文件。"""
        page.goto(base_url)
        page.wait_for_load_state("networkidle")

        page.locator('.sidebar-nav a[data-tab="settings"]').click()
        page.wait_for_timeout(800)

        # 检查文件上传区域
        file_input = page.locator('#resumeFile')
        assert file_input.count() > 0

        upload_btn = page.locator('button:has-text("上传解析")')
        assert upload_btn.count() > 0

        # 检查查看完整简历按钮
        full_btn = page.locator('button:has-text("查看完整简历")')
        assert full_btn.count() > 0

        # 点击查看完整简历
        full_btn.click()
        page.wait_for_timeout(1000)

        # 检查 textarea 可见
        full_ta = page.locator('#setResumeFull')
        assert full_ta.is_visible(), "完整简历 textarea 应可见"

        # 再次点击收起
        toggle_btn = page.locator('#resumeFullToggle button')
        toggle_btn.click()
        page.wait_for_timeout(500)
        assert not full_ta.is_visible(), "应收起完整简历"

        screenshot(page, "10_resume_upload")

    def test_11_user_views_wechat_tab(self, page, base_url):
        """用户查看微信记录 Tab。"""
        page.goto(base_url)
        page.wait_for_load_state("networkidle")

        page.locator('.sidebar-nav a[data-tab="wechat"]').click()
        page.wait_for_timeout(800)

        # 检查标题
        title = page.locator('#tab-wechat h3').text_content()
        assert "微信" in title

        # 检查刷新按钮
        refresh_btn = page.locator('button:has-text("刷新")')
        assert refresh_btn.count() > 0

        screenshot(page, "11_wechat_tab")

    def test_12_user_checks_system_controls(self, page, base_url):
        """用户检查系统控制按钮。"""
        page.goto(base_url)
        page.wait_for_load_state("networkidle")

        # 启动浏览器按钮
        start_btn = page.locator('#btnStart')
        assert start_btn.count() > 0
        assert start_btn.is_visible()

        # 停止按钮
        stop_btn = page.locator('#btnStop')
        assert stop_btn.count() > 0

        screenshot(page, "12_system_controls")

    def test_13_user_no_js_errors_across_all_tabs(self, page, base_url):
        """用户浏览所有 Tab，确认无 JS 错误。"""
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))

        page.goto(base_url)
        page.wait_for_load_state("networkidle")

        # 切换所有 Tab
        for tab in ["applications", "chat", "wechat", "settings", "search"]:
            page.locator(f'.sidebar-nav a[data-tab="{tab}"]').click()
            page.wait_for_timeout(800)

        # 在设置页做一些操作
        page.locator('.sidebar-nav a[data-tab="settings"]').click()
        page.wait_for_timeout(500)

        # 切换 AI 平台
        page.locator('#setAIPlatform').select_option("openrouter")
        page.wait_for_timeout(300)
        page.locator('#setAIPlatform').select_option("mimo")
        page.wait_for_timeout(300)

        # 过滤已知无害错误
        real_errors = [e for e in errors if "WebSocket" not in e and "net::" not in e]
        assert not real_errors, f"有 JS 错误: {real_errors}"

        screenshot(page, "13_no_js_errors")
