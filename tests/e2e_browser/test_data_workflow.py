"""测试：数据管理完整工作流 - 模拟用户查看、筛选、删除、恢复数据。

包含：岗位列表、筛选排序、删除回收、统计查看、批量操作。
"""
import pytest
import time
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from helpers import screenshot, api_get, api_post, api_delete, get_api_token


class TestDataManagement:
    """数据管理工作流。"""

    def test_01_list_all_jobs(self):
        """1. 列出所有岗位。"""
        s, d = api_get("/api/jobs?limit=10")
        assert s == 200
        jobs = d.get("jobs", [])
        total = d.get("total", 0)
        print(f"\n[数据 1] 总岗位数: {total}, 列表返回: {len(jobs)}")

        # 状态分布
        statuses = {}
        for j in jobs:
            st = j.get("status", "unknown")
            statuses[st] = statuses.get(st, 0) + 1
        print(f"  状态分布: {statuses}")

    def test_02_filter_jobs(self):
        """2. 按状态筛选。"""
        for status in ["pending", "applied", "replied", "trash"]:
            s, d = api_get(f"/api/jobs?status={status}&limit=5")
            if s == 200:
                count = d.get("total", 0)
                print(f"\n[数据 2] status={status}: {count}")

    def test_03_pagination(self):
        """3. 限制数量。"""
        s, d = api_get("/api/jobs?limit=5")
        first = d.get("jobs", [])
        assert len(first) <= 5, f"limit未生效: {len(first)}"
        print(f"\n[数据 3] limit=5: 返回 {len(first)} 个岗位")
        for j in first[:3]:
            print(f"  - #{j.get('id')} {j.get('title', 'N/A')[:30]}")

    def test_04_get_single_job(self):
        """4. 查看单个岗位。"""
        s, d = api_get("/api/jobs?limit=1")
        if s != 200 or not d.get("jobs"):
            pytest.skip("无岗位")
            return

        job_id = d["jobs"][0]["id"]
        s, d = api_get(f"/api/jobs/{job_id}")
        assert s == 200
        job = d.get("job", {})
        print(f"\n[数据 4] 岗位 #{job_id}")
        print(f"  标题: {job.get('title', 'N/A')}")
        print(f"  公司: {job.get('company', 'N/A')}")
        print(f"  城市: {job.get('city', 'N/A')}")
        print(f"  状态: {job.get('status', 'N/A')}")
        print(f"  综合分: {job.get('composite_score', 'N/A')}")

    def test_05_skip_job(self):
        """5. 跳过岗位（移到回收站）。"""
        s, d = api_get("/api/jobs?status=pending&limit=1")
        if s != 200 or not d.get("jobs"):
            pytest.skip("无待处理岗位")
            return

        job_id = d["jobs"][0]["id"]
        s, d = api_post(f"/api/jobs/{job_id}/skip", {})
        print(f"\n[数据 5] 跳过 #{job_id}: status={s}")

    def test_06_trash_count(self):
        """6. 回收站统计。"""
        s, d = api_get("/api/jobs?status=trash&limit=1")
        assert s == 200
        trash_count = d.get("total", 0)
        print(f"\n[数据 6] 回收站: {trash_count}")

    def test_07_dedup_stats(self):
        """7. 去重统计。"""
        s, d = api_get("/api/jobs/dedup-stats")
        if s == 200:
            print(f"\n[数据 7] 去重统计: {d}")
        else:
            print(f"\n[数据 7] 端点状态: {s}")

    def test_08_followups(self):
        """8. 跟进任务。"""
        s, d = api_get("/api/jobs/followups")
        if s == 200:
            followups = d.get("followups", [])
            print(f"\n[数据 8] 跟进任务: {len(followups)}")
            for f in followups[:3]:
                print(f"  - #{f.get('id')} {f.get('title', 'N/A')[:30]}")
        else:
            print(f"\n[数据 8] 端点状态: {s}")

    def test_09_shortlist(self):
        """9. 短名单。"""
        s, d = api_get("/api/jobs/shortlist")
        if s == 200:
            items = d.get("shortlist", [])
            print(f"\n[数据 9] 短名单: {len(items)}")
        else:
            print(f"\n[数据 9] 端点状态: {s}")


class TestDataVisualization:
    """数据可视化。"""

    def test_view_applications_page(self, page, base_url):
        """浏览投递记录页面。"""
        page.goto(base_url)
        page.wait_for_load_state("networkidle")
        page.locator('.sidebar-nav a[data-tab="applications"]').click()
        page.wait_for_timeout(800)
        screenshot(page, "data_01_applications")

        # 统计卡片
        cards = page.locator(".stat-card").all()
        print(f"\n[数据可视化] 统计卡片: {len(cards)}")
        for c in cards:
            txt = c.inner_text().replace("\n", " ")[:50]
            if txt:
                print(f"  - {txt}")

    def test_view_search_page(self, page, base_url):
        """浏览搜索页面。"""
        page.goto(base_url)
        page.wait_for_load_state("networkidle")
        page.locator('.sidebar-nav a[data-tab="search"]').click()
        page.wait_for_timeout(800)
        screenshot(page, "data_02_search")

    def test_view_stats_trend(self):
        """统计趋势。"""
        for days in [7, 30]:
            s, d = api_get(f"/api/stats/trend?days={days}")
            if s == 200:
                trend = d.get("trend", [])
                print(f"\n[数据可视化] 趋势 ({days}天): {len(trend)} 个数据点")
                for t in trend[-3:]:
                    print(f"  - {t}")

    def test_funnel_stats(self):
        """漏斗统计。"""
        s, d = api_get("/api/stats/funnel")
        if s == 200:
            print(f"\n[数据可视化] 漏斗: {d}")
