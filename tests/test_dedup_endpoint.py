"""回归测试: dedupe 端点必须返回合法 JSON + 函数行为。

之前 dedupe 抛异常时 FastAPI 返回 'Internal Server Error' 纯文本，
前端 fetch().json() 解析失败：Unexpected token 'I', "Internal S"...
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def client_and_db(test_db):
    """复用 tests/test_routes.py 的 client 模式。"""
    import boss_app.core.state as state
    state.automation = None
    from boss_app.main import app, API_TOKEN
    from fastapi.testclient import TestClient

    with TestClient(app) as c:
        yield c, {"Authorization": f"Bearer {API_TOKEN}"}


class TestDedupeEndpoint:
    """dedupe 端点回归测试。"""

    def test_dedupe_returns_valid_json(self, client_and_db):
        """dedupe 必须返回 application/json 格式。"""
        c, headers = client_and_db
        response = c.post("/api/jobs/deduplicate", headers=headers)

        assert response.headers.get("content-type", "").startswith("application/json"), \
            f"Content-Type 不是 JSON: {response.headers.get('content-type')}"

        data = response.json()
        assert "total" in data
        assert "duplicates_found" in data
        assert "duplicates_removed" in data

    def test_dedupe_stats_returns_valid_json(self, client_and_db):
        """dedupe 统计端点。"""
        c, headers = client_and_db
        response = c.get("/api/jobs/dedup-stats", headers=headers)
        assert response.headers.get("content-type", "").startswith("application/json")
        data = response.json()
        assert "total_unique" in data


class TestDedupeFunction:
    """dedupe 函数行为测试 - 不经过 HTTP。"""

    def test_dedupe_empty_db(self, test_db):
        """空数据库上 dedupe 应正常返回。"""
        from boss_app.models.application import deduplicate_applications
        result = deduplicate_applications()
        assert result["total"] == 0
        assert result["duplicates_removed"] == 0
