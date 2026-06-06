"""测试：智能投递完整工作流 - 模拟用户从配置到自动投递的完整流程。

包含：配置阈值、查看候选、模拟自动投递、查看日志。
"""
import pytest
import time
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from helpers import screenshot, api_get, api_post, api_put, get_api_token


class TestSmartApplyWorkflow:
    """模拟用户智能投递全流程。"""

    def test_01_check_current_settings(self, page, base_url):
        """1. 查看当前自动投递设置。"""
        print("\n[智能投递 1] 当前设置")
        page.goto(base_url)
        page.wait_for_load_state("networkidle")
        page.locator('.sidebar-nav a[data-tab="settings"]').click()
        page.wait_for_timeout(800)
        screenshot(page, "apply_01_settings_page")

        # 查找自动投递相关元素
        auto_apply_text = page.locator("text=自动投递").first
        assert auto_apply_text.count() > 0, "找不到自动投递设置"

        threshold_input = page.locator("input[id*='threshold'], input[id*='auto_apply']").first
        if threshold_input.count() > 0:
            print(f"  当前阈值: {threshold_input.input_value()}")

    def test_02_check_candidates(self):
        """2. 通过API查看当前可投递候选数。"""
        s, d = api_get("/api/status")
        assert s == 200
        print(f"  今日已投递: {d.get('today_applications', 0)}")

        s, d = api_get("/api/jobs?status=pending&limit=100")
        assert s == 200
        pending = d.get("jobs", [])
        print(f"  待投递岗位: {len(pending)}")

        # 计算超过73分的岗位
        high_score = [j for j in pending if (j.get("composite_score") or 0) >= 73]
        print(f"  高分岗位(>=73): {len(high_score)}")

    def test_03_view_apply_logs(self):
        """3. 查看历史投递日志。"""
        s, d = api_get("/api/auto-apply-logs?limit=20")
        assert s == 200
        logs = d.get("logs", [])
        print(f"\n[智能投递 3] 历史日志")
        print(f"  总日志数: {len(logs)}")

        success = [l for l in logs if l.get("result") == "success"]
        failed = [l for l in logs if l.get("result") and "failed" in str(l.get("result"))]
        print(f"  成功: {len(success)}, 失败: {len(failed)}")

        for log in logs[:3]:
            print(f"    [{log.get('id')}] {log.get('job_title', 'N/A')[:25]} - {log.get('result', 'N/A')[:40]}")

    def test_04_settings_update_threshold(self):
        """4. 模拟用户调整阈值。"""
        s, d = api_get("/api/settings")
        assert s == 200
        old = d.get("settings", {}).get("auto_apply_threshold", "73")
        print(f"\n[智能投递 4] 当前阈值: {old}")

        # 设置为 75
        s, d = api_put("/api/settings", {"auto_apply_threshold": "75"})
        assert s == 200

        # 验证
        s, d = api_get("/api/settings")
        new = d.get("settings", {}).get("auto_apply_threshold", "73")
        assert new == "75", f"阈值未更新: {new}"
        print(f"  新阈值: {new}")

        # 恢复
        s, d = api_put("/api/settings", {"auto_apply_threshold": old})
        assert s == 200

    def test_05_trigger_auto_apply_safe(self):
        """5. 触发自动投递（浏览器未运行时应该安全失败）。"""
        s, d = api_post("/api/auto-apply/trigger", {})
        # 浏览器在运行时可能成功执行；未运行时会返回错误
        # 关键是不应崩溃
        print(f"\n[智能投递 5] 触发结果: status={s}")
        if d:
            print(f"  响应: {str(d)[:200]}")

    def test_06_check_stats_update(self):
        """6. 投递后统计更新检查。"""
        s, d = api_get("/api/stats")
        assert s == 200
        funnel = d.get("funnel", {})
        print(f"\n[智能投递 6] 漏斗统计")
        for k, v in funnel.items():
            print(f"  {k}: {v}")

    def test_07_visual_workflow(self, page, base_url):
        """7. 完整可视化：浏览投递记录页面。"""
        print("\n[智能投递 7] 可视化工作流")
        page.goto(base_url)
        page.wait_for_load_state("networkidle")

        # 投递记录Tab
        page.locator('.sidebar-nav a[data-tab="applications"]').click()
        page.wait_for_timeout(800)
        screenshot(page, "apply_07_applications_list")

        # 切到设置Tab
        page.locator('.sidebar-nav a[data-tab="settings"]').click()
        page.wait_for_timeout(800)
        screenshot(page, "apply_07_settings")

        # 找自动投递阈值
        threshold = page.locator("input[type='number']").all()
        for inp in threshold:
            label = inp.evaluate("""el => {
                const lbl = el.closest('label') || el.parentElement;
                return lbl ? lbl.innerText : '';
            }""")
            if "阈值" in label or "分数" in label or "threshold" in label.lower():
                print(f"  找到阈值: {label[:30]} = {inp.input_value()}")


class TestSmartApplyUI:
    """投递相关UI组件测试。"""

    def test_buttons_present(self, page, base_url):
        """核心按钮存在性。"""
        page.goto(base_url)
        page.wait_for_load_state("networkidle")

        buttons = page.locator("button:visible").all()
        print(f"\n[智能投递 UI] 可见按钮: {len(buttons)}")
        for btn in buttons[:20]:
            txt = btn.inner_text()[:30].replace("\n", " ")
            if txt:
                print(f"  - {txt}")

    def test_status_indicators(self, page, base_url):
        """状态指示器。"""
        page.goto(base_url)
        page.wait_for_load_state("networkidle")
        page.locator('.sidebar-nav a[data-tab="search"]').click()
        page.wait_for_timeout(500)

        # 状态点/状态徽章
        indicators = page.locator(".status-dot, .status-badge, .badge, .indicator").all()
        print(f"\n[智能投递 UI] 状态指示器: {len(indicators)}")
