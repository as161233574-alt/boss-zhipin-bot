"""Routes API 接口测试。"""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(test_db):
    """创建测试客户端（跳过启动事件中的浏览器相关逻辑）。"""
    import boss_app.core.state as state
    state.automation = None  # 确保不触发浏览器

    from boss_app.main import app, API_TOKEN
    headers = {"Authorization": f"Bearer {API_TOKEN}"}
    return TestClient(app, raise_server_exceptions=False), headers


class TestJobsAPI:
    def test_list_jobs_empty(self, client):
        c, headers = client
        resp = c.get("/api/jobs", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "jobs" in data
        assert "total" in data

    def test_list_jobs_with_data(self, client):
        c, headers = client
        from boss_app.models.application import add_application
        add_application({"title": "API测试", "company": "C", "url": "https://zhipin.com/job/api1"})
        resp = c.get("/api/jobs", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1

    def test_get_job(self, client):
        c, headers = client
        from boss_app.models.application import add_application
        aid = add_application({"title": "Get", "company": "C", "url": "https://zhipin.com/job/get1"})
        resp = c.get(f"/api/jobs/{aid}", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["job"]["job_title"] == "Get"

    def test_get_job_not_found(self, client):
        c, headers = client
        resp = c.get("/api/jobs/99999", headers=headers)
        assert resp.status_code == 404

    def test_delete_jobs(self, client):
        c, headers = client
        from boss_app.models.application import add_application
        aid = add_application({"title": "Del", "company": "C", "url": "https://zhipin.com/job/del1"})
        resp = c.post("/api/jobs/delete", json={"job_ids": [aid]}, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["deleted"] == 1

    def test_trash_flow(self, client):
        c, headers = client
        from boss_app.models.application import add_application
        aid = add_application({"title": "Trash", "company": "C", "url": "https://zhipin.com/job/trash1"})
        # 删除
        c.post("/api/jobs/delete", json={"job_ids": [aid]}, headers=headers)
        # 查看回收站
        resp = c.get("/api/trash", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["count"] >= 1
        # 恢复
        resp = c.post("/api/trash/restore", json={"job_ids": [aid]}, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["restored"] == 1

    def test_dedup_stats(self, client):
        c, headers = client
        resp = c.get("/api/jobs/dedup-stats", headers=headers)
        assert resp.status_code == 200
        assert "total_unique" in resp.json()

    def test_score_job_not_found(self, client):
        c, headers = client
        resp = c.post("/api/jobs/99999/score", headers=headers)
        assert resp.status_code == 404

    def test_skip_job(self, client):
        c, headers = client
        from boss_app.models.application import add_application, get_application
        aid = add_application({"title": "Skip", "company": "C", "url": "https://zhipin.com/job/skip1"})
        resp = c.post(f"/api/jobs/{aid}/skip", headers=headers)
        assert resp.status_code == 200
        assert get_application(aid)["status"] == "skipped"

    def test_search_no_browser(self, client):
        c, headers = client
        resp = c.post("/api/jobs/search", json={"keyword": "Python"}, headers=headers)
        assert resp.status_code == 503  # 浏览器未启动

    def test_shortlist_flow(self, client):
        c, headers = client
        # 添加候选
        resp = c.post("/api/shortlists", json={"job_url": "https://zhipin.com/job/sl1", "title": "T"}, headers=headers)
        assert resp.status_code == 200
        # 列表
        resp = c.get("/api/shortlists", headers=headers)
        assert resp.status_code == 200
        assert len(resp.json()["shortlists"]) >= 1
        # 删除
        sid = resp.json()["shortlists"][0]["id"]
        resp = c.delete(f"/api/shortlists/{sid}", headers=headers)
        assert resp.status_code == 200

    def test_followups(self, client):
        c, headers = client
        resp = c.get("/api/followups", headers=headers)
        assert resp.status_code == 200
        assert "overdue" in resp.json()
        assert "stats" in resp.json()

    def test_auto_apply_logs(self, client):
        c, headers = client
        resp = c.get("/api/auto-apply-logs", headers=headers)
        assert resp.status_code == 200
        assert "logs" in resp.json()

    def test_delete_logs(self, client):
        c, headers = client
        resp = c.get("/api/delete-logs", headers=headers)
        assert resp.status_code == 200
        assert "logs" in resp.json()

    def test_trash_count(self, client):
        c, headers = client
        resp = c.get("/api/trash/count", headers=headers)
        assert resp.status_code == 200
        assert "count" in resp.json()

    def test_clear_jobs_requires_confirm(self, client):
        c, headers = client
        resp = c.post("/api/jobs/clear", json={"confirm": "wrong"}, headers=headers)
        assert resp.status_code == 400

    def test_apply_no_browser(self, client):
        c, headers = client
        resp = c.post("/api/jobs/apply", json={"job_url": "https://zhipin.com/job/x"}, headers=headers)
        assert resp.status_code == 503


class TestSettingsAPI:
    def test_get_settings(self, client):
        c, headers = client
        resp = c.get("/api/settings", headers=headers)
        assert resp.status_code == 200

    def test_update_settings(self, client):
        c, headers = client
        resp = c.put("/api/settings", json={"daily_apply_limit": "20"}, headers=headers)
        assert resp.status_code == 200

    def test_resume_upload_txt(self, client):
        c, headers = client
        content = "张三\nPython开发工程师\n5年经验\n熟练Docker、K8s".encode("utf-8")
        resp = c.post(
            "/api/settings/resume/upload",
            files={"file": ("resume.txt", content, "text/plain")},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["text_length"] > 0
        assert "Python" in data["summary_preview"]

    def test_resume_upload_unsupported_ext(self, client):
        c, headers = client
        resp = c.post(
            "/api/settings/resume/upload",
            files={"file": ("resume.docx", b"content", "application/octet-stream")},
            headers=headers,
        )
        assert resp.status_code == 400

    def test_resume_upload_empty_file(self, client):
        c, headers = client
        resp = c.post(
            "/api/settings/resume/upload",
            files={"file": ("resume.txt", b"", "text/plain")},
            headers=headers,
        )
        assert resp.status_code == 400

    def test_resume_delete(self, client):
        c, headers = client
        resp = c.delete("/api/settings/resume", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


class TestSystemAPI:
    def test_status(self, client):
        c, headers = client
        resp = c.get("/api/status", headers=headers)
        assert resp.status_code == 200

    def test_auto_apply_trigger_no_browser(self, client):
        c, headers = client
        resp = c.post("/api/auto-apply/trigger", headers=headers)
        assert resp.status_code == 503


class TestAuth:
    def test_no_token_returns_401(self, client):
        c, _ = client
        resp = c.get("/api/jobs")
        assert resp.status_code == 401

    def test_wrong_token_returns_401(self, client):
        c, _ = client
        resp = c.get("/api/jobs", headers={"Authorization": "Bearer wrong_token"})
        assert resp.status_code == 401

    def test_static_accessible(self, client):
        c, _ = client
        resp = c.get("/")
        assert resp.status_code == 200
