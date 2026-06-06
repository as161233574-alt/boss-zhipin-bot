"""综合功能测试 - 一次跑完所有功能。

包含：页面渲染、状态管理、API调用、交互、错误处理、响应式。
"""
import pytest
import time
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from helpers import screenshot, api_get, api_post, api_put, get_api_token


class TestComprehensive:
    """综合测试。"""

    def test_01_app_loads(self, page, base_url):
        """应用加载。"""
        page.goto(base_url)
        page.wait_for_load_state("networkidle")
        assert "BOSS" in page.title() or "控制台" in page.title()
        screenshot(page, "final_01_app_loads")

    def test_02_all_pages(self, page, base_url):
        """所有Tab页面。"""
        for tab in ["search", "applications", "chat", "wechat", "settings"]:
            page.goto(base_url)
            page.wait_for_load_state("networkidle")
            page.locator(f'.sidebar-nav a[data-tab="{tab}"]').click()
            page.wait_for_timeout(500)
            assert page.locator(f"#tab-{tab}").is_visible(), f"{tab} Tab不可见"
            screenshot(page, f"final_{tab}")

    def test_03_api_health(self):
        """API 健康检查。"""
        s, d = api_get("/api/status")
        assert s == 200
        assert "browser_running" in d

    def test_04_data_integrity(self):
        """数据完整性。"""
        # 岗位
        s, d = api_get("/api/jobs?limit=10")
        assert s == 200
        assert "jobs" in d
        assert "total" in d

        # 会话
        s, d = api_get("/api/conversations")
        assert s == 200
        assert "conversations" in d

        # 设置
        s, d = api_get("/api/settings")
        assert s == 200
        assert "settings" in d

        # 统计
        s, d = api_get("/api/stats")
        assert s == 200

    def test_05_websocket(self, page, base_url):
        """WebSocket 连接。"""
        page.goto(base_url)
        page.wait_for_load_state("networkidle")
        # 验证页面有 WebSocket 客户端初始化
        has_ws = page.evaluate("() => typeof WebSocket !== 'undefined'")
        assert has_ws, "浏览器不支持 WebSocket"
        # 等待连接建立
        time.sleep(2)
        screenshot(page, "final_websocket")

    def test_06_responsive(self, page, base_url):
        """响应式。"""
        for w, h, name in [(1920, 1080, "desktop"), (768, 1024, "tablet"), (375, 667, "mobile")]:
            page.set_viewport_size({"width": w, "height": h})
            page.goto(base_url)
            page.wait_for_load_state("networkidle")
            screenshot(page, f"final_responsive_{name}")
        page.set_viewport_size({"width": 1440, "height": 900})
