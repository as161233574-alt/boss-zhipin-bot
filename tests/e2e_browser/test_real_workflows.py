"""测试 5: 真实工作流模拟 — 模拟用户实际操作并截图。

通过 Playwright 真实点击UI元素，模拟用户从打开应用到完成任务的完整流程。
"""
import pytest
import time
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from helpers import screenshot, api_get, api_post, api_put, get_api_token


class TestRealUserWorkflows:
    """模拟真实用户工作流。"""

    def test_workflow_1_search_and_view(self, page, base_url):
        """工作流1: 打开应用 → 搜索 → 查看结果。"""
        print("\n[工作流 1] 搜索并查看")
        page.goto(base_url)
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(500)
        screenshot(page, "wf1_01_homepage")

        # 切换到投递记录Tab看历史数据
        page.locator('.sidebar-nav a[data-tab="applications"]').click()
        page.wait_for_timeout(800)
        screenshot(page, "wf1_02_applications")

        # 切回搜索Tab
        page.locator('.sidebar-nav a[data-tab="search"]').click()
        page.wait_for_timeout(500)

        # 验证能看到统计
        stats = page.locator(".stat-card").all()
        print(f"  统计卡片: {len(stats)}")
        screenshot(page, "wf1_03_search")

    def test_workflow_2_browse_jobs(self, page, base_url):
        """工作流2: 浏览岗位列表 - 筛选/排序/分析。"""
        print("\n[工作流 2] 浏览岗位")
        page.goto(base_url)
        page.wait_for_load_state("networkidle")
        page.locator('.sidebar-nav a[data-tab="applications"]').click()
        page.wait_for_timeout(800)

        # 切到"待投递" 筛选
        page.locator("button:has-text('待投递')").first.click()
        page.wait_for_timeout(500)
        screenshot(page, "wf2_01_pending")

        # 切到"已投递" 筛选
        page.locator("button:has-text('已投递')").first.click()
        page.wait_for_timeout(500)
        screenshot(page, "wf2_02_applied")

        # 切回"全部"
        page.locator("button:has-text('全部')").first.click()
        page.wait_for_timeout(500)
        screenshot(page, "wf2_03_all")

    def test_workflow_3_chat_interaction(self, page, base_url):
        """工作流3: 查看聊天会话。"""
        print("\n[工作流 3] 聊天交互")
        page.goto(base_url)
        page.wait_for_load_state("networkidle")
        page.locator('.sidebar-nav a[data-tab="chat"]').click()
        page.wait_for_timeout(800)
        screenshot(page, "wf3_01_chat_list")

        # 点击第一个会话
        first_conv = page.locator(".chat-list-item").first
        if first_conv.count() > 0:
            first_conv.click()
            page.wait_for_timeout(800)
            screenshot(page, "wf3_02_chat_open")

            # 查看消息
            msgs = page.locator(".msg-bubble, .message-item").all()
            print(f"  消息数: {len(msgs)}")

            # 切换自动回复
            auto_reply_btn = page.locator("button:has-text('AI回复中'), button:has-text('暂停AI回复')").first
            if auto_reply_btn.count() > 0:
                old_text = auto_reply_btn.inner_text()
                auto_reply_btn.click()
                page.wait_for_timeout(500)
                new_text = auto_reply_btn.inner_text()
                print(f"  自动回复: {old_text} -> {new_text}")
                screenshot(page, "wf3_03_auto_reply_toggled")

    def test_workflow_4_settings_management(self, page, base_url):
        """工作流4: 设置管理。"""
        print("\n[工作流 4] 设置管理")
        page.goto(base_url)
        page.wait_for_load_state("networkidle")
        page.locator('.sidebar-nav a[data-tab="settings"]').click()
        page.wait_for_timeout(800)
        screenshot(page, "wf4_01_settings")

        # 找到所有input/textarea
        all_inputs = page.locator("input:visible, textarea:visible, select:visible").all()
        print(f"  可编辑元素: {len(all_inputs)}")

        # 列出所有可编辑项
        for i, inp in enumerate(all_inputs[:15]):
            tag = inp.evaluate("el => el.tagName")
            ph = inp.get_attribute("placeholder") or inp.get_attribute("id") or ""
            val = inp.input_value() if tag in ("INPUT", "TEXTAREA", "SELECT") else ""
            if ph and tag:
                print(f"    [{i}] {tag} '{ph[:30]}' = '{val[:30]}'")

    def test_workflow_5_complete_app_view(self, page, base_url):
        """工作流5: 全功能快照。"""
        print("\n[工作流 5] 全功能快照")
        tabs = ["search", "applications", "chat", "wechat", "settings"]
        for tab in tabs:
            page.goto(base_url)
            page.wait_for_load_state("networkidle")
            page.locator(f'.sidebar-nav a[data-tab="{tab}"]').click()
            page.wait_for_timeout(800)
            screenshot(page, f"wf5_{tab}")

    def test_workflow_6_responsive_check(self, page, base_url):
        """工作流6: 响应式布局检查。"""
        print("\n[工作流 6] 响应式")
        # 桌面尺寸
        page.set_viewport_size({"width": 1920, "height": 1080})
        page.goto(base_url)
        page.wait_for_load_state("networkidle")
        screenshot(page, "wf6_01_desktop")

        # 平板尺寸
        page.set_viewport_size({"width": 1024, "height": 768})
        page.goto(base_url)
        page.wait_for_load_state("networkidle")
        screenshot(page, "wf6_02_tablet")

        # 移动尺寸
        page.set_viewport_size({"width": 375, "height": 667})
        page.goto(base_url)
        page.wait_for_load_state("networkidle")
        screenshot(page, "wf6_03_mobile")

        # 恢复
        page.set_viewport_size({"width": 1440, "height": 900})


class TestErrorRecovery:
    """错误恢复能力测试。"""

    def test_recover_from_invalid_input(self, page, base_url):
        """错误输入恢复。"""
        print("\n[错误恢复] 错误输入")
        page.goto(base_url)
        page.wait_for_load_state("networkidle")
        page.locator('.sidebar-nav a[data-tab="settings"]').click()
        page.wait_for_timeout(500)

        # 找到数字输入
        number_input = page.locator("input[type='number']:visible").first
        if number_input.count() > 0:
            # 输入非法值
            number_input.fill("-1")
            print(f"  填入 -1: {number_input.input_value()}")

            # 输入超长值
            number_input.fill("999999999")
            print(f"  填入 999999999: {number_input.input_value()}")

            # 还原
            number_input.fill("15")
            print(f"  还原为 15: {number_input.input_value()}")

    def test_recover_from_api_error(self, page, base_url):
        """API错误恢复。"""
        print("\n[错误恢复] API错误")
        # 模拟API错误 - 触发不存在的端点
        response = page.evaluate("""async () => {
            try {
                const r = await fetch('/api/nonexistent');
                return {status: r.status, ok: r.ok};
            } catch (e) {
                return {error: e.message};
            }
        }""")
        print(f"  不存在端点响应: {response}")

        # 应用本身应该不受影响
        page.goto(base_url)
        page.wait_for_load_state("networkidle")
        title = page.title()
        print(f"  页面标题: {title}")
        assert "BOSS" in title or "控制台" in title
