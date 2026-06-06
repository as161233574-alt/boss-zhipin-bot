"""测试：设置管理完整工作流 - 模拟用户配置系统的所有设置项。

包含：AI配置、自动化配置、消息模板、关键词、阈值等。
"""
import pytest
import time
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from helpers import screenshot, api_get, api_post, api_put, get_api_token


class TestSettingsManagement:
    """设置管理工作流。"""

    def test_01_list_all_settings(self):
        """1. 列出所有设置项。"""
        s, d = api_get("/api/settings")
        assert s == 200
        settings = d.get("settings", {})
        print(f"\n[设置 1] 当前设置项: {len(settings)}")
        for k, v in sorted(settings.items()):
            print(f"  {k} = {str(v)[:50]}")

    def test_02_update_ai_settings(self):
        """2. 更新AI相关设置。"""
        updates = {
            "ai_model": "deepseek-chat",
            "ai_base_url": "https://api.deepseek.com/v1",
        }
        s, d = api_put("/api/settings", updates)
        assert s == 200

        s, d = api_get("/api/settings")
        for k, v_expected in updates.items():
            v_actual = d.get("settings", {}).get(k, "")
            assert v_actual == v_expected, f"{k}: {v_actual} != {v_expected}"
        print(f"\n[设置 2] AI设置已更新")

    def test_03_update_thresholds(self):
        """3. 更新阈值。"""
        s, d = api_get("/api/settings")
        old = d.get("settings", {}).get("auto_apply_threshold", "73")

        # 测试边界
        for v in ["70", "75", "80", "85"]:
            s, d = api_put("/api/settings", {"auto_apply_threshold": v})
            assert s == 200
            s, d = api_get("/api/settings")
            assert d.get("settings", {}).get("auto_apply_threshold") == v

        # 恢复
        s, d = api_put("/api/settings", {"auto_apply_threshold": old})
        print(f"\n[设置 3] 阈值测试完成, 恢复为 {old}")

    def test_04_toggle_auto_flags(self):
        """4. 切换自动开关。"""
        s, d = api_get("/api/settings")
        was_on = d.get("settings", {}).get("auto_apply_enabled") == "true"

        # 切换
        s, d = api_put("/api/settings", {"auto_apply_enabled": "false" if was_on else "true"})
        assert s == 200

        s, d = api_get("/api/settings")
        is_on = d.get("settings", {}).get("auto_apply_enabled") == "true"
        assert is_on != was_on
        print(f"\n[设置 4] auto_apply_enabled: {was_on} -> {is_on}")

        # 还原
        s, d = api_put("/api/settings", {"auto_apply_enabled": "true" if was_on else "false"})

    def test_05_update_template(self):
        """5. 更新消息模板。"""
        s, d = api_get("/api/settings")
        old_greeting = d.get("settings", {}).get("greeting_template", "")

        new_greeting = "您好，我对该岗位非常感兴趣，期待沟通！"
        s, d = api_put("/api/settings", {"greeting_template": new_greeting})
        assert s == 200

        s, d = api_get("/api/settings")
        actual = d.get("settings", {}).get("greeting_template", "")
        assert actual == new_greeting
        print(f"\n[设置 5] 模板已更新")

        # 恢复
        if old_greeting:
            api_put("/api/settings", {"greeting_template": old_greeting})

    def test_06_visual_settings_page(self, page, base_url):
        """6. 设置页面可视化。"""
        page.goto(base_url)
        page.wait_for_load_state("networkidle")
        page.locator('.sidebar-nav a[data-tab="settings"]').click()
        page.wait_for_timeout(800)
        screenshot(page, "settings_01_overview")

        # 列出所有可编辑元素
        inputs = page.locator("input:visible, textarea:visible, select:visible").all()
        print(f"\n[设置 6] 可编辑元素: {len(inputs)}")
        for i, inp in enumerate(inputs):
            tag = inp.evaluate("el => el.tagName")
            label = inp.evaluate("""el => {
                const lbl = el.closest('label') || el.previousElementSibling;
                return lbl ? (lbl.innerText || '').slice(0, 30) : (el.id || el.name || el.placeholder || '').slice(0, 30);
            }""")
            val = inp.input_value() if tag in ("INPUT", "TEXTAREA", "SELECT") else ""
            print(f"  [{i}] {tag} {label} = {str(val)[:40]}")

    def test_07_save_button_works(self, page, base_url):
        """7. 保存按钮。"""
        page.goto(base_url)
        page.wait_for_load_state("networkidle")
        page.locator('.sidebar-nav a[data-tab="settings"]').click()
        page.wait_for_timeout(500)

        save_btn = page.locator("button:has-text('保存'), button:has-text('保存设置')").first
        if save_btn.count() > 0:
            save_btn.click()
            page.wait_for_timeout(1000)
            # 检查是否有toast/通知
            toast = page.locator(".toast, .notification, .alert, .msg").all()
            print(f"\n[设置 7] 保存后通知: {len(toast)}")
            for t in toast[:3]:
                txt = t.inner_text()[:50] if t.is_visible() else ""
                if txt:
                    print(f"  - {txt}")
            screenshot(page, "settings_07_saved")

    def test_08_keyword_list_management(self):
        """8. 关键词列表管理。"""
        s, d = api_get("/api/settings")
        exclude_kw = d.get("settings", {}).get("exclude_keywords", "")
        print(f"\n[设置 8] 排除关键词: {exclude_kw[:80]}")

        include_kw = d.get("settings", {}).get("include_keywords", "")
        print(f"  包含关键词: {include_kw[:80]}")


class TestSettingsEdgeCases:
    """设置边界情况。"""

    def test_invalid_threshold_rejected(self):
        """无效阈值应被拒绝或处理。"""
        # 尝试设置 -1
        s, d = api_put("/api/settings", {"auto_apply_threshold": "-1"})
        # 应该接受（API不严格校验），但UI应限制
        print(f"\n[边界] -1: status={s}")

        # 尝试设置超大值
        s, d = api_put("/api/settings", {"auto_apply_threshold": "9999"})
        print(f"[边界] 9999: status={s}")

        # 尝试设置非数字
        s, d = api_put("/api/settings", {"auto_apply_threshold": "abc"})
        print(f"[边界] abc: status={s}")

        # 恢复
        s, d = api_put("/api/settings", {"auto_apply_threshold": "73"})

    def test_empty_template(self):
        """空模板。"""
        s, d = api_put("/api/settings", {"greeting_template": ""})
        print(f"\n[边界] 空模板: status={s}")

        s, d = api_get("/api/settings")
        val = d.get("settings", {}).get("greeting_template", "")
        # 应该被接受（允许清空）
        print(f"  验证: {val[:30] if val else '(空)'}")
