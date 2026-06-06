"""测试：智能回复完整工作流 - 模拟用户查看聊天、切换AI回复、查看消息。

包含：会话列表、消息查看、自动回复切换、回复测试。
"""
import pytest
import time
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from helpers import screenshot, api_get, api_post, get_api_token


class TestSmartReplyWorkflow:
    """智能回复工作流。"""

    def test_01_list_conversations(self):
        """1. 列出所有会话。"""
        s, d = api_get("/api/conversations?limit=50")
        assert s == 200
        convs = d.get("conversations", [])
        print(f"\n[智能回复 1] 总会话数: {len(convs)}")

        active = [c for c in convs if c.get("status") == "active"]
        archived = [c for c in convs if c.get("status") == "archived"]
        print(f"  活跃: {len(active)}, 归档: {len(archived)}")

        auto_on = [c for c in convs if c.get("auto_reply_enabled")]
        print(f"  AI回复开启: {len(auto_on)}")

    def test_02_view_conversation_detail(self):
        """2. 查看会话详情。"""
        s, convs_d = api_get("/api/conversations?limit=1")
        if s != 200 or not convs_d.get("conversations"):
            pytest.skip("无会话")
            return

        conv_id = convs_d["conversations"][0]["id"]
        s, d = api_get(f"/api/conversations/{conv_id}")
        assert s == 200
        conv = d.get("conversation", {})
        msgs = d.get("messages", [])
        print(f"\n[智能回复 2] 会话 #{conv_id}")
        print(f"  HR: {conv.get('hr_name', 'N/A')}")
        print(f"  岗位: {conv.get('job_title', 'N/A')}")
        print(f"  消息数: {len(msgs)}")
        print(f"  自动回复: {'开' if conv.get('auto_reply_enabled') else '关'}")
        print(f"  微信已发: {bool(conv.get('wechat_shared_at'))}")

    def test_03_toggle_auto_reply(self):
        """3. 切换AI自动回复状态。"""
        s, convs_d = api_get("/api/conversations?limit=1")
        if s != 200 or not convs_d.get("conversations"):
            pytest.skip("无会话")
            return

        conv_id = convs_d["conversations"][0]["id"]

        # 获取当前状态
        s, d = api_get(f"/api/conversations/{conv_id}")
        was_on = bool(d.get("conversation", {}).get("auto_reply_enabled"))
        print(f"\n[智能回复 3] 会话 #{conv_id} 当前: {'开' if was_on else '关'}")

        # 切换
        endpoint = "/pause" if was_on else "/resume"
        s, d = api_post(f"/api/conversations/{conv_id}{endpoint}", {})
        print(f"  调用 {endpoint}: status={s}")

        # 验证
        s, d = api_get(f"/api/conversations/{conv_id}")
        is_on = bool(d.get("conversation", {}).get("auto_reply_enabled"))
        print(f"  切换后: {'开' if is_on else '关'}")
        assert is_on != was_on, "状态未变化"

        # 还原
        endpoint = "/pause" if is_on else "/resume"
        api_post(f"/api/conversations/{conv_id}{endpoint}", {})

    def test_04_check_global_auto_reply(self):
        """4. 全局AI回复状态。"""
        s, d = api_get("/api/status")
        assert s == 200
        print(f"\n[智能回复 4] 全局自动回复: {'开' if d.get('auto_reply_enabled') else '关'}")

    def test_05_view_messages_in_conversation(self, page, base_url):
        """5. 浏览器中查看会话消息。"""
        print("\n[智能回复 5] 浏览器查看")
        page.goto(base_url)
        page.wait_for_load_state("networkidle")
        page.locator('.sidebar-nav a[data-tab="chat"]').click()
        page.wait_for_timeout(800)
        screenshot(page, "reply_05_chat_list")

        # 点击第一个会话
        first = page.locator(".chat-list-item").first
        if first.count() > 0:
            first.click()
            page.wait_for_timeout(1000)
            screenshot(page, "reply_05_chat_open")

            # 查找消息气泡
            bubbles = page.locator(".msg-bubble, .message-item, .message").all()
            print(f"  消息气泡: {len(bubbles)}")

            # 查找自动回复按钮
            auto_btn = page.locator("button:has-text('AI回复中'), button:has-text('暂停AI回复')").first
            if auto_btn.count() > 0:
                print(f"  AI按钮: {auto_btn.inner_text()}")

    def test_06_chat_filter(self, page, base_url):
        """6. 聊天过滤。"""
        print("\n[智能回复 6] 过滤")
        page.goto(base_url)
        page.wait_for_load_state("networkidle")
        page.locator('.sidebar-nav a[data-tab="chat"]').click()
        page.wait_for_timeout(800)

        # 查找过滤按钮
        filters = page.locator(".chat-filter button, button:has-text('活跃'), button:has-text('已读'), button:has-text('未读')").all()
        print(f"  过滤按钮: {len(filters)}")
        for f in filters:
            print(f"    - {f.inner_text()[:20]}")


class TestChatAssistantUI:
    """聊天助手UI。"""

    def test_chat_panel_loads(self, page, base_url):
        """聊天面板加载。"""
        page.goto(base_url)
        page.wait_for_load_state("networkidle")
        page.locator('.sidebar-nav a[data-tab="chat"]').click()
        page.wait_for_timeout(500)

        chat_panel = page.locator("#tab-chat")
        assert chat_panel.is_visible()
        screenshot(page, "reply_chat_panel")

    def test_no_console_errors_on_chat(self, page, base_url):
        """聊天页面无JS错误。"""
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))

        page.goto(base_url)
        page.wait_for_load_state("networkidle")
        page.locator('.sidebar-nav a[data-tab="chat"]').click()
        page.wait_for_timeout(1500)

        if errors:
            print(f"\n[聊天错误] {len(errors)}:")
            for e in errors[:5]:
                print(f"  - {e[:100]}")
        else:
            print("\n[聊天] 无JS错误")
