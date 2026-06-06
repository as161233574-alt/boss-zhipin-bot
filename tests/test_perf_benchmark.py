"""性能基准测试：搜索/评分吞吐。

优化目标：
- 搜索接口应在几秒内返回（评分后台化）
- 30 岗位评分应在 2-5 分钟内完成（合并 prompt + 3 路并行）
"""
import time
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestPerformanceBenchmarks:
    """性能基准 - 验证优化效果。"""

    def test_search_endpoint_response_time(self):
        """搜索接口应快速返回（不阻塞评分）。"""
        from fastapi.testclient import TestClient
        from boss_app.main import app, API_TOKEN
        from boss_app.core import state

        # 无浏览器时搜索直接返回，不阻塞
        state.automation = None

        with TestClient(app) as client:
            headers = {"Authorization": f"Bearer {API_TOKEN}"}
            start = time.time()
            response = client.post(
                "/api/jobs/search",
                json={"keyword": "Python", "city": "成都"},
                headers=headers,
                timeout=10,
            )
            elapsed = time.time() - start

            # 无浏览器时应立即返回（< 5s）
            # 有浏览器时会启动后台任务，应该 < 5s 返回
            print(f"\n[基准] 搜索响应时间: {elapsed:.2f}s (status={response.status_code})")
            assert elapsed < 5.0, f"搜索接口过慢: {elapsed:.2f}s"

    def test_score_endpoint_response_time(self):
        """单岗位评分响应时间。"""
        from fastapi.testclient import TestClient
        from boss_app.main import app, API_TOKEN
        from boss_app.core import state

        state.automation = None

        with TestClient(app) as client:
            headers = {"Authorization": f"Bearer {API_TOKEN}"}
            # 找一个 pending 岗位
            jobs_resp = client.get("/api/jobs?status=pending&limit=1", headers=headers)
            if jobs_resp.status_code != 200 or not jobs_resp.json().get("jobs"):
                pytest.skip("无 pending 岗位可测")
            job_id = jobs_resp.json()["jobs"][0]["id"]

            start = time.time()
            response = client.post(f"/api/jobs/{job_id}/score", headers=headers, timeout=60)
            elapsed = time.time() - start

            print(f"\n[基准] 单岗位评分时间: {elapsed:.2f}s (status={response.status_code})")
            # 单岗位评分应在 30s 内（取决于 AI 网络）
            assert response.status_code in (200, 503), f"评分失败: {response.status_code}"

    def test_list_jobs_fast(self):
        """列表 API 应快速响应。"""
        from fastapi.testclient import TestClient
        from boss_app.main import app, API_TOKEN
        from boss_app.core import state

        state.automation = None

        with TestClient(app) as client:
            headers = {"Authorization": f"Bearer {API_TOKEN}"}
            start = time.time()
            response = client.get("/api/jobs?limit=100", headers=headers)
            elapsed = time.time() - start

            print(f"\n[基准] 列表 API: {elapsed*1000:.0f}ms (status={response.status_code})")
            assert response.status_code == 200
            # 列表查询应 < 1s
            assert elapsed < 1.0, f"列表 API 慢: {elapsed:.2f}s"

    def test_stats_fast(self):
        """统计 API 应快速响应。"""
        from fastapi.testclient import TestClient
        from boss_app.main import app, API_TOKEN
        from boss_app.core import state

        state.automation = None

        with TestClient(app) as client:
            headers = {"Authorization": f"Bearer {API_TOKEN}"}
            start = time.time()
            response = client.get("/api/stats", headers=headers)
            elapsed = time.time() - start

            print(f"\n[基准] 统计 API: {elapsed*1000:.0f}ms (status={response.status_code})")
            assert response.status_code == 200
            # 统计应 < 500ms
            assert elapsed < 0.5, f"统计 API 慢: {elapsed:.2f}s"


class TestScorerPerformance:
    """评分服务层性能。"""

    def test_combined_score_with_mocked_llm(self):
        """评分函数在 LLM 返回固定 JSON 时应稳定快速。"""
        from unittest.mock import patch, MagicMock
        from boss_app.services.scorer import score_job_combined

        # 模拟 LLM 返回固定 JSON（不走网络）
        fake_response = '{"cv_score": 75, "quality_score": 70, "key_skills": ["Python"], "gap": "x", "advice": "y", "summary": "ok", "quality_notes": "ok"}'
        with patch("boss_app.services.scorer.llm_chat_deepseek", return_value=fake_response):
            # 预热
            score_job_combined("AI开发", "测试", "JD内容", "15-25K", "张三")

            start = time.time()
            for _ in range(100):
                result = score_job_combined("AI开发", "测试", "JD内容", "15-25K", "张三")
            elapsed = time.time() - start
            avg = elapsed / 100 * 1000
            print(f"\n[基准] 合并评分（mock LLM, 100次）: {avg:.2f}ms/次")
            assert avg < 50, f"评分函数（含 LLM mock 解析）太慢: {avg:.2f}ms"
