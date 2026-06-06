"""前端回归测试：dedupe 按钮点击后无 JSON 解析错误。

之前 bug: dedupe 后端抛异常时返回 "Internal Server Error" 纯文本，
前端 fetch().json() 解析失败：Unexpected token 'I', "Internal S"...
"""
import pytest
import time
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from helpers import screenshot, api_get, api_post


class TestDashboardDedupe:
    """dashboard 端到端 dedupe 测试。"""

    def test_dedup_button_no_json_error(self, page, base_url):
        """点击清理重复按钮不应触发 JSON 解析错误。"""
        # 收集 console 错误
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))

        # Mock confirm/alert
        page.evaluate("""() => {
            window._alerts = [];
            window._originalAlert = window.alert;
            window.alert = (msg) => window._alerts.push(msg);
            window.confirm = () => true;  // 自动确认
        }""")

        page.goto(base_url)
        page.wait_for_load_state("networkidle")

        # 切到投递记录 Tab
        page.locator('.sidebar-nav a[data-tab="applications"]').click()
        page.wait_for_timeout(800)

        # 找清理重复按钮
        dedup_btn = page.locator("button:has-text('清理重复')").first
        if dedup_btn.count() == 0:
            pytest.skip("找不到清理重复按钮")
            return

        # 点击
        dedup_btn.click()
        page.wait_for_timeout(2000)  # 等待请求完成

        # 检查 alert 内容
        alerts = page.evaluate("() => window._alerts || []")
        print(f"\n[前端 dedupe] 触发的 alert 数: {len(alerts)}")
        for a in alerts:
            print(f"  - {a[:100]}")

        # 关键：不应有 "Unexpected token" 错误
        for a in alerts:
            assert "Unexpected token" not in a, f"JSON 解析错误: {a}"
            assert "Internal S" not in a, f"Internal Server Error 泄漏: {a}"

        # 也应无 JS 错误
        json_errors = [e for e in errors if "JSON" in e or "token" in e]
        assert not json_errors, f"JS 错误: {json_errors}"
        print(f"  [OK] 无 JSON 解析错误")
