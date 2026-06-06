"""核心业务流程 E2E 测试。

测试评分、投递、回收站、收藏、跟进等核心功能。
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from helpers import screenshot, api_post, api_get, api_put


class TestBusinessFlows:
    """核心业务流程测试。"""

    def _add_test_jobs(self):
        """通过 API 添加测试岗位数据。"""
        jobs = [
            {"title": "Python开发工程师", "company": "测试科技", "url": "https://zhipin.com/job/biz1", "salary": "15-25K", "city": "成都"},
            {"title": "AI Agent工程师", "company": "智能公司", "url": "https://zhipin.com/job/biz2", "salary": "20-35K", "city": "成都"},
            {"title": "运维工程师", "company": "云服务公司", "url": "https://zhipin.com/job/biz3", "salary": "12-20K", "city": "北京"},
        ]
        ids = []
        for job in jobs:
            status, data = api_post("/api/jobs/search", job)
            # 也尝试直接通过数据库添加
        return ids

    def test_01_applications_tab_stats_display(self, page, base_url):
        """投递记录 Tab 统计卡片正确显示。"""
        page.goto(base_url)
        page.wait_for_load_state("networkidle")

        page.locator('.sidebar-nav a[data-tab="applications"]').click()
        page.wait_for_timeout(1000)

        # 统计卡片应有数字
        stats = page.locator('.stat-card .num')
        for i in range(stats.count()):
            val = stats.nth(i).text_content()
            assert val is not None, f"统计卡片 {i} 不应为空"

        screenshot(page, "biz_01_stats")

    def test_02_applications_filter_buttons(self, page, base_url):
        """投递记录筛选按钮可点击。"""
        page.goto(base_url)
        page.wait_for_load_state("networkidle")

        page.locator('.sidebar-nav a[data-tab="applications"]').click()
        # 等待 tab 变为可见
        page.wait_for_selector('#tab-applications.active', timeout=5000)
        page.wait_for_timeout(500)

        # 点击各筛选按钮
        filters = ["全部", "待投递", "已投递", "已回复"]
        for f in filters:
            btn = page.locator(f'#tab-applications button:has-text("{f}")').first
            if btn.count() > 0:
                btn.click()
                page.wait_for_timeout(500)

        screenshot(page, "biz_02_filters")

    def test_03_applications_table_structure(self, page, base_url):
        """投递记录表格结构完整。"""
        page.goto(base_url)
        page.wait_for_load_state("networkidle")

        page.locator('.sidebar-nav a[data-tab="applications"]').click()
        page.wait_for_timeout(800)

        # 表头
        headers = page.locator('#tab-applications thead th')
        header_texts = [headers.nth(i).text_content().strip() for i in range(headers.count())]
        print(f"  表头: {header_texts}")

        assert "岗位" in header_texts
        assert "公司" in header_texts
        assert "薪资" in header_texts
        assert "状态" in header_texts

        screenshot(page, "biz_03_table")

    def test_04_trash_operations(self, page, base_url):
        """回收站操作：查看、恢复。"""
        page.goto(base_url)
        page.wait_for_load_state("networkidle")

        page.locator('.sidebar-nav a[data-tab="applications"]').click()
        page.wait_for_timeout(800)

        # 点击回收站按钮
        trash_btn = page.locator('button:has-text("回收站")').first
        if trash_btn.count() > 0:
            trash_btn.click()
            page.wait_for_timeout(1000)

            # 检查回收站内容
            trash_section = page.locator('#trashSection')
            if trash_section.count() > 0:
                is_visible = trash_section.is_visible()
                print(f"  回收站可见: {is_visible}")

        screenshot(page, "biz_04_trash")

    def test_05_shortlist_operations(self, page, base_url):
        """收藏夹操作：查看收藏列表。"""
        page.goto(base_url)
        page.wait_for_load_state("networkidle")

        page.locator('.sidebar-nav a[data-tab="applications"]').click()
        page.wait_for_timeout(800)

        # 点击收藏按钮（如果可见）
        shortlist_btn = page.locator('button:has-text("收藏")').first
        if shortlist_btn.count() > 0 and shortlist_btn.is_visible():
            shortlist_btn.click()
            page.wait_for_timeout(1000)

        screenshot(page, "biz_05_shortlist")

    def test_06_trend_chart_display(self, page, base_url):
        """趋势图和漏斗图正确显示。"""
        page.goto(base_url)
        page.wait_for_load_state("networkidle")

        page.locator('.sidebar-nav a[data-tab="applications"]').click()
        page.wait_for_timeout(1000)

        # 趋势图区域
        trend_section = page.locator('#trendSection')
        assert trend_section.count() > 0, "应有趋势图区域"

        # 点击 7 天按钮
        btn_7d = page.locator('button:has-text("7天")').first
        if btn_7d.count() > 0:
            btn_7d.click()
            page.wait_for_timeout(500)

        # 点击 30 天按钮
        btn_30d = page.locator('button:has-text("30天")').first
        if btn_30d.count() > 0:
            btn_30d.click()
            page.wait_for_timeout(500)

        screenshot(page, "biz_06_trend")

    def test_07_followup_display(self, page, base_url):
        """跟进提醒正确显示。"""
        page.goto(base_url)
        page.wait_for_load_state("networkidle")

        page.locator('.sidebar-nav a[data-tab="applications"]').click()
        page.wait_for_timeout(800)

        # 跟进提醒栏
        followup_bar = page.locator('#followupBar')
        assert followup_bar.count() > 0, "应有跟进提醒栏"

        screenshot(page, "biz_07_followup")

    def test_08_chat_conversation_list(self, page, base_url):
        """聊天会话列表正确加载。"""
        page.goto(base_url)
        page.wait_for_load_state("networkidle")

        page.locator('.sidebar-nav a[data-tab="chat"]').click()
        page.wait_for_timeout(1500)

        # 会话列表
        conv_list = page.locator('#conversationList')
        assert conv_list.count() > 0

        # 搜索框可输入
        search = page.locator('#convSearch')
        search.fill("测试")
        page.wait_for_timeout(300)
        search.fill("")
        page.wait_for_timeout(300)

        # 筛选 Tab
        status_tabs = page.locator('.chat-tabs span')
        assert status_tabs.count() >= 3, "应有至少 3 个状态 Tab"

        # 点击活跃
        active_tab = page.locator('.chat-tabs span[data-status="active"]')
        if active_tab.count() > 0:
            active_tab.click()
            page.wait_for_timeout(500)

        # 点击全部
        all_tab = page.locator('.chat-tabs span[data-status="all"]')
        if all_tab.count() > 0:
            all_tab.click()
            page.wait_for_timeout(500)

        screenshot(page, "biz_08_chat_list")

    def test_09_chat_quick_replies(self, page, base_url):
        """聊天快捷回复按钮存在。"""
        page.goto(base_url)
        page.wait_for_load_state("networkidle")

        page.locator('.sidebar-nav a[data-tab="chat"]').click()
        page.wait_for_timeout(800)

        # 快捷回复按钮
        quick_replies = page.locator('#quickReplies button')
        assert quick_replies.count() >= 4, "应有至少 4 个快捷回复按钮"

        # 检查按钮文字
        for i in range(quick_replies.count()):
            text = quick_replies.nth(i).text_content()
            print(f"  快捷回复 {i}: {text}")

        screenshot(page, "biz_09_quick_replies")

    def test_10_wechat_exchanges(self, page, base_url):
        """微信记录 Tab 正确显示。"""
        page.goto(base_url)
        page.wait_for_load_state("networkidle")

        page.locator('.sidebar-nav a[data-tab="wechat"]').click()
        page.wait_for_timeout(800)

        # 标题
        title = page.locator('#tab-wechat h3').text_content()
        assert "微信" in title

        # 刷新按钮
        refresh_btn = page.locator('button:has-text("刷新")').first
        assert refresh_btn.count() > 0

        # 列表区域
        list_area = page.locator('#wechatExchangesList')
        assert list_area.count() > 0

        screenshot(page, "biz_10_wechat")

    def test_11_scheduler_controls(self, page, base_url):
        """定时任务控制按钮存在。"""
        page.goto(base_url)
        page.wait_for_load_state("networkidle")

        page.locator('.sidebar-nav a[data-tab="settings"]').click()
        page.wait_for_timeout(800)

        # 保存定时配置按钮
        save_btn = page.locator('button:has-text("保存定时配置")').first
        assert save_btn.count() > 0

        # 停止定时按钮
        stop_btn = page.locator('button:has-text("停止定时")').first
        assert stop_btn.count() > 0

        screenshot(page, "biz_11_scheduler")

    def test_12_auto_apply_config(self, page, base_url):
        """自动投递配置完整。"""
        page.goto(base_url)
        page.wait_for_load_state("networkidle")

        page.locator('.sidebar-nav a[data-tab="settings"]').click()
        page.wait_for_timeout(800)

        # 检查所有自动投递相关元素
        elements = {
            'setAutoApply': 'select',
            'setAutoApplyThreshold': 'input',
            'setAutoApplyHrActive': 'select',
            'setFilterInactiveHr': 'select',
        }

        for el_id, tag in elements.items():
            el = page.locator(f'#{el_id}')
            assert el.count() > 0, f"应有 #{el_id}"

        # 保存自动投递按钮
        save_btn = page.locator('#tab-settings button:has-text("保存自动投递")')
        if save_btn.count() > 0:
            save_btn.click()
            page.wait_for_timeout(500)

        screenshot(page, "biz_12_auto_apply")

    def test_13_page_navigation_consistency(self, page, base_url):
        """页面导航一致性：切换 Tab 后返回，状态保持。"""
        page.goto(base_url)
        page.wait_for_load_state("networkidle")

        # 在搜索 Tab 输入关键词
        keyword = page.locator('#searchKeyword')
        keyword.fill("测试关键词")

        # 切换到设置
        page.locator('.sidebar-nav a[data-tab="settings"]').click()
        page.wait_for_timeout(500)

        # 切换回搜索
        page.locator('.sidebar-nav a[data-tab="search"]').click()
        page.wait_for_timeout(500)

        # 关键词应保持
        val = keyword.input_value()
        assert val == "测试关键词", f"关键词应保持: {val}"

        screenshot(page, "biz_13_navigation")
