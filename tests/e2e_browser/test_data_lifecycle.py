"""测试 2: 模拟用户对系统进行实际操作 — 启动浏览器/搜索/评分/投递等。"""
import pytest
import time
import json
import sys
import urllib.request
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from helpers import screenshot, api_get, api_post, api_put, get_api_token


def auth_get(path):
    req = urllib.request.Request(
        f"http://127.0.0.1:8000{path}",
        headers={"Authorization": f"Bearer {get_api_token()}"}
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def auth_post(path, data=None, timeout=60):
    body = json.dumps(data or {}).encode("utf-8")
    req = urllib.request.Request(
        f"http://127.0.0.1:8000{path}",
        data=body,
        headers={
            "Authorization": f"Bearer {get_api_token()}",
            "Content-Type": "application/json",
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())
    except Exception as e:
        return 0, {"error": str(e)}


class TestBrowserStartStop:
    """浏览器启动/停止全流程。"""

    def test_01_start_button_in_ui(self, page, base_url):
        """在UI中检查启动/停止按钮状态。"""
        print("\n[测试 2.1] UI启动/停止按钮")
        page.goto(base_url)
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(500)

        start_btn = page.locator("#btnStart")
        stop_btn = page.locator("#btnStop")

        # 检查按钮状态（可能已启动或未启动）
        start_disabled = start_btn.is_disabled()
        stop_disabled = stop_btn.is_disabled()
        print(f"  启动按钮: 禁用={start_disabled}")
        print(f"  停止按钮: 禁用={stop_disabled}")

        # 两个按钮状态应该互斥
        assert start_disabled != stop_disabled, "启动和停止按钮状态应该互斥"

        if not start_disabled:
            start_btn.click()
            print("  [OK] 已点击启动按钮")
            time.sleep(3)
            screenshot(page, "10_browser_starting")
        else:
            print("  [信息] 浏览器已运行，停止按钮可点")
            assert not stop_disabled, "启动已禁用时停止按钮应可用"

    def test_02_status_after_start(self):
        """启动后检查状态。"""
        print("\n[测试 2.2] 检查启动后状态")
        status = auth_get("/api/status")
        print(f"  浏览器: {'运行中' if status.get('browser_running') else '未启动'}")
        print(f"  监控: {'运行中' if status.get('monitor_running') else '未启动'}")
        # 验证有这些字段
        assert "browser_running" in status
        assert "monitor_running" in status

    def test_03_system_status_api(self):
        """检查系统所有状态字段。"""
        print("\n[测试 2.3] 系统状态字段完整性")
        status = auth_get("/api/status")
        expected = ["browser_running", "monitor_running", "paused", "is_logged_in"]
        for key in expected:
            val = status.get(key)
            print(f"  {key}: {val}")


class TestSearchViaUI:
    """通过UI操作搜索。"""

    def test_04_fill_search_form(self, page, base_url):
        """填写搜索表单。"""
        print("\n[测试 2.4] 填写搜索表单")
        page.goto(base_url)
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(500)

        # 关键词
        kw_input = page.locator("#searchKeyword").first
        if kw_input.count() == 0:
            kw_input = page.locator("input[type='text']").first
        kw_input.fill("AI产品经理")
        print(f"  [OK] 关键词: {kw_input.input_value()}")

        # 城市
        city_sel = page.locator("#searchCity").first
        if city_sel.count() == 0:
            city_sel = page.locator("select").first
        try:
            city_sel.select_option(label="北京")
            print(f"  [OK] 城市: {city_sel.input_value()}")
        except Exception as e:
            print(f"  [!] 城市选择失败: {e}")

        # 翻页
        max_pages = page.locator("#maxPages, input[type='number']").first
        if max_pages.count() > 0:
            try:
                max_pages.fill("1")
                print(f"  [OK] 翻页: {max_pages.input_value()}")
            except Exception:
                pass

        screenshot(page, "11_search_filled")

    def test_05_click_search(self, page, base_url):
        """点击搜索按钮(不真正等待BOSS网站响应)。"""
        print("\n[测试 2.5] 点击搜索按钮")
        page.goto(base_url)
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(500)

        # 确认浏览器已启动
        status = auth_get("/api/status")
        if not status.get("browser_running"):
            print("  [!] 浏览器未启动，先启动")
            auth_post("/api/system/start")
            time.sleep(5)

        # 点击搜索按钮
        search_btn = page.locator("#btnSearch")
        if search_btn.count() == 0:
            search_btn = page.locator("button:has-text('搜索')").first
        if search_btn.is_visible():
            search_btn.click()
            print("  [OK] 已点击搜索按钮")
            # 等待2秒看是否有状态变化
            time.sleep(2)
            status_div = page.locator("#searchStatus")
            if status_div.count() > 0:
                print(f"  状态: {status_div.inner_text()[:100]}")
            screenshot(page, "12_search_clicked")
        else:
            print("  [!] 搜索按钮不可见")


class TestJobManagement:
    """岗位管理操作。"""

    def test_06_view_jobs(self):
        """查看岗位列表。"""
        print("\n[测试 2.6] 岗位列表")
        d = auth_get("/api/jobs?limit=5")
        jobs = d.get("jobs", [])
        total = d.get("total", 0)
        print(f"  总数: {total}")
        print(f"  返回: {len(jobs)}")
        if jobs:
            j = jobs[0]
            print(f"  示例: [{j['id']}] {j.get('job_title', '')[:30]}")
            print(f"  公司: {j.get('company', '')[:20]}")
            print(f"  状态: {j.get('status', '')}")
            print(f"  综合分: {j.get('composite_score')}")

    def test_07_filter_jobs(self):
        """按状态筛选岗位。"""
        print("\n[测试 2.7] 状态筛选")
        for status in ["pending", "applied", "replied", "skipped"]:
            d = auth_get(f"/api/jobs?status={status}&limit=100")
            print(f"  {status}: {d.get('total', 0)} 个")

    def test_08_dedup_stats(self):
        """去重统计。"""
        print("\n[测试 2.8] 去重统计")
        d = auth_get("/api/jobs/dedup-stats")
        print(f"  总岗位: {d.get('total_unique', 0)}")
        print(f"  重复: {d.get('duplicates', 0)}")


class TestSettings:
    """设置相关操作。"""

    def test_09_view_settings(self):
        """查看所有设置。"""
        print("\n[测试 2.9] 设置列表")
        d = auth_get("/api/settings")
        settings = d.get("settings", {})
        print(f"  设置项数: {len(settings)}")
        for k in list(settings.keys())[:10]:
            v = settings[k]
            if "key" in k.lower() or "token" in k.lower():
                v = (v[:8] + "...") if v else "(空)"
            try:
                print(f"    {k} = {v}")
            except UnicodeEncodeError:
                print(f"    {k} = (contains non-ASCII)")

    def test_10_update_settings(self):
        """更新设置。"""
        print("\n[测试 2.10] 更新设置")
        # 通过PUT修改每日投递上限
        import urllib.request
        body = json.dumps({"daily_apply_limit": "20"}).encode("utf-8")
        req = urllib.request.Request(
            "http://127.0.0.1:8000/api/settings",
            data=body,
            headers={
                "Authorization": f"Bearer {get_api_token()}",
                "Content-Type": "application/json",
            },
            method="PUT"
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            print(f"  [OK] 更新daily_apply_limit=20, 状态={r.status}")

        # 验证
        d = auth_get("/api/settings")
        new_val = d.get("settings", {}).get("daily_apply_limit")
        print(f"  验证: daily_apply_limit={new_val}")
        assert new_val == "20", f"更新失败，仍为{new_val}"


class TestStatistics:
    """统计与转化漏斗。"""

    def test_11_stats_overview(self):
        """总体统计。"""
        print("\n[测试 2.11] 总体统计")
        d = auth_get("/api/stats")
        for k, v in d.items():
            if k == "daily_stats":
                continue
            print(f"  {k}: {v}")

    def test_12_funnel_stats(self):
        """转化漏斗。"""
        print("\n[测试 2.12] 转化漏斗")
        d = auth_get("/api/stats/funnel")
        for k, v in d.items():
            print(f"  {k}: {v}")

    def test_13_trend(self):
        """趋势数据。"""
        print("\n[测试 2.13] 趋势数据")
        d = auth_get("/api/stats/trend?days=7")
        trend = d.get("trend", [])
        print(f"  趋势天数: {len(trend)}")
        for t in trend[:5]:
            print(f"    {t}")
