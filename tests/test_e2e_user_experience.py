"""
端到端用户模拟测试：以真实用户视角逐一测试所有功能模块。
测试覆盖：首页加载、岗位CRUD、搜索、收藏、回收站、设置、统计、
跟进提醒、自动投递、系统控制、认证、WebSocket、AI分析等。
"""
import json
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(test_db):
    """创建测试客户端，模拟真实用户访问。"""
    import boss_app.core.state as state
    state.automation = None

    from boss_app.main import app, API_TOKEN
    headers = {"Authorization": f"Bearer {API_TOKEN}"}
    c = TestClient(app, raise_server_exceptions=False)
    return c, headers, API_TOKEN


# ══════════════════════════════════════
#  1. 首页 & 静态资源
# ══════════════════════════════════════

class TestHomepage:
    """用户打开浏览器访问首页的体验。"""

    def test首页可访问(self, client):
        c, headers, _ = client
        resp = c.get("/")
        assert resp.status_code == 200
        assert "BOSS" in resp.text
        assert "控制台" in resp.text

    def test首页注入token(self, client):
        """首页HTML应注入API Token供前端JS使用。"""
        c, headers, token = client
        resp = c.get("/")
        assert f"window.__API_TOKEN__='{token}'" in resp.text

    def test首页不缓存(self, client):
        """首页应设置no-cache避免浏览器缓存旧版本。"""
        c, _, _ = client
        resp = c.get("/")
        assert "no-cache" in resp.headers.get("cache-control", "")


# ══════════════════════════════════════
#  2. 认证安全
# ══════════════════════════════════════

class TestAuth:
    """用户未登录或Token错误时的行为。"""

    def test无token返回401(self, client):
        c, _, _ = client
        resp = c.get("/api/jobs")
        assert resp.status_code == 401
        assert "未授权" in resp.json().get("error", "") or "error" in resp.json()

    def test错误token返回401(self, client):
        c, _, _ = client
        resp = c.get("/api/jobs", headers={"Authorization": "Bearer wrong_token_123"})
        assert resp.status_code == 401

    def test首页不需要认证(self, client):
        c, _, _ = client
        resp = c.get("/")
        assert resp.status_code == 200

    def test静态资源不需要认证(self, client):
        c, _, _ = client
        resp = c.get("/static/dashboard.html")
        assert resp.status_code == 200


# ══════════════════════════════════════
#  3. 系统状态 & 健康检查
# ══════════════════════════════════════

class TestSystemStatus:
    """用户查看系统运行状态。"""

    def test获取系统状态(self, client):
        c, headers, _ = client
        resp = c.get("/api/status", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "browser_running" in data
        assert "monitor_running" in data

    def test健康检查(self, client):
        c, headers, _ = client
        resp = c.get("/api/health", headers=headers)
        assert resp.status_code == 200

    def test环境诊断(self, client):
        c, headers, _ = client
        resp = c.get("/api/doctor", headers=headers)
        assert resp.status_code == 200

    def test启动浏览器无浏览器时返回提示(self, client):
        c, headers, _ = client
        resp = c.post("/api/system/start", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        # 没有Playwright环境时应返回失败提示
        assert "status" in data or "message" in data

    def test停止浏览器(self, client):
        c, headers, _ = client
        resp = c.post("/api/system/stop", headers=headers)
        assert resp.status_code == 200

    def test心跳检测(self, client):
        c, headers, _ = client
        resp = c.post("/api/system/heartbeat", headers=headers)
        assert resp.status_code in (200, 503)  # 无浏览器时503
        assert "alive" in resp.json() or "detail" in resp.json()

    def test空闲重定向日志(self, client):
        c, headers, _ = client
        resp = c.post("/api/log/idle-redirect",
                       json={"timestamp": "2026-06-05T10:00:00", "from_url": "/", "idle_duration": "30s"},
                       headers=headers)
        assert resp.status_code == 200


# ══════════════════════════════════════
#  4. 岗位管理 CRUD
# ══════════════════════════════════════

class TestJobManagement:
    """用户管理岗位的完整流程。"""

    def test查看空列表(self, client):
        c, headers, _ = client
        resp = c.get("/api/jobs", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "jobs" in data
        assert "total" in data
        assert data["total"] == 0

    def test添加岗位后列表不为空(self, client):
        c, headers, _ = client
        from boss_app.models.application import add_application
        add_application({"title": "Python开发", "company": "测试公司", "url": "https://zhipin.com/job/e2e1", "salary": "15-25K", "city": "成都"})
        resp = c.get("/api/jobs", headers=headers)
        data = resp.json()
        assert data["total"] >= 1
        job = data["jobs"][0]
        assert job["job_title"] == "Python开发"
        assert job["company"] == "测试公司"

    def test查看单个岗位详情(self, client):
        c, headers, _ = client
        from boss_app.models.application import add_application
        aid = add_application({"title": "详情测试", "company": "C", "url": "https://zhipin.com/job/detail1", "description": "Python LLM开发"})
        resp = c.get(f"/api/jobs/{aid}", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["job"]["job_title"] == "详情测试"

    def test查看不存在的岗位返回404(self, client):
        c, headers, _ = client
        resp = c.get("/api/jobs/99999", headers=headers)
        assert resp.status_code == 404

    def test跳过岗位(self, client):
        c, headers, _ = client
        from boss_app.models.application import add_application, get_application
        aid = add_application({"title": "跳过测试", "company": "C", "url": "https://zhipin.com/job/skip1"})
        resp = c.post(f"/api/jobs/{aid}/skip", headers=headers)
        assert resp.status_code == 200
        assert get_application(aid)["status"] == "skipped"

    def test按状态筛选(self, client):
        c, headers, _ = client
        from boss_app.models.application import add_application, update_application_status
        aid = add_application({"title": "筛选测试", "company": "C", "url": "https://zhipin.com/job/filter1"})
        update_application_status(aid, "applied", "你好")
        resp = c.get("/api/jobs?status=applied", headers=headers)
        data = resp.json()
        assert data["total"] >= 1
        assert all(j["status"] == "applied" for j in data["jobs"])

    def test评分不存在的岗位(self, client):
        c, headers, _ = client
        resp = c.post("/api/jobs/99999/score", headers=headers)
        assert resp.status_code == 404


# ══════════════════════════════════════
#  5. 删除 & 回收站
# ══════════════════════════════════════

class TestTrashFlow:
    """用户删除岗位、查看回收站、恢复的完整流程。"""

    def test删除后进入回收站(self, client):
        c, headers, _ = client
        from boss_app.models.application import add_application, get_application
        aid = add_application({"title": "删除测试", "company": "C", "url": "https://zhipin.com/job/del1"})
        # 删除
        resp = c.post("/api/jobs/delete", json={"job_ids": [aid]}, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["deleted"] == 1
        # 主列表查不到
        assert get_application(aid) is None

    def test回收站可见(self, client):
        c, headers, _ = client
        from boss_app.models.application import add_application
        aid = add_application({"title": "回收站测试", "company": "C", "url": "https://zhipin.com/job/trash1"})
        c.post("/api/jobs/delete", json={"job_ids": [aid]}, headers=headers)
        resp = c.get("/api/trash", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["count"] >= 1

    def test回收站计数(self, client):
        c, headers, _ = client
        from boss_app.models.application import add_application
        aid = add_application({"title": "计数测试", "company": "C", "url": "https://zhipin.com/job/count1"})
        c.post("/api/jobs/delete", json={"job_ids": [aid]}, headers=headers)
        resp = c.get("/api/trash/count", headers=headers)
        assert resp.json()["count"] >= 1

    def test从回收站恢复(self, client):
        c, headers, _ = client
        from boss_app.models.application import add_application, get_application
        aid = add_application({"title": "恢复测试", "company": "C", "url": "https://zhipin.com/job/restore1"})
        c.post("/api/jobs/delete", json={"job_ids": [aid]}, headers=headers)
        # 恢复
        resp = c.post("/api/trash/restore", json={"job_ids": [aid]}, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["restored"] == 1
        # 主列表可查
        assert get_application(aid) is not None

    def test批量删除(self, client):
        c, headers, _ = client
        from boss_app.models.application import add_application, get_application
        ids = [add_application({"title": f"批量{i}", "company": "C", "url": f"https://zhipin.com/job/batch{i}"}) for i in range(3)]
        resp = c.post("/api/jobs/delete", json={"job_ids": ids}, headers=headers)
        assert resp.json()["deleted"] == 3
        for aid in ids:
            assert get_application(aid) is None

    def test清空所有需要确认(self, client):
        c, headers, _ = client
        resp = c.post("/api/jobs/clear", json={"confirm": "wrong"}, headers=headers)
        assert resp.status_code == 400

    def test清空所有(self, client):
        c, headers, _ = client
        from boss_app.models.application import add_application
        for i in range(3):
            add_application({"title": f"清空{i}", "company": "C", "url": f"https://zhipin.com/job/clear{i}"})
        resp = c.post("/api/jobs/clear", json={"confirm": "确认清空"}, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["deleted"] == 3

    def test删除日志记录(self, client):
        c, headers, _ = client
        from boss_app.models.application import add_application
        aid = add_application({"title": "日志测试", "company": "C", "url": "https://zhipin.com/job/log1"})
        c.post("/api/jobs/delete", json={"job_ids": [aid]}, headers=headers)
        resp = c.get("/api/delete-logs", headers=headers)
        assert resp.status_code == 200
        assert "logs" in resp.json()


# ══════════════════════════════════════
#  6. 收藏夹
# ══════════════════════════════════════

class TestShortlist:
    """用户收藏/取消收藏岗位的流程。"""

    def test添加收藏(self, client):
        c, headers, _ = client
        resp = c.post("/api/shortlists",
                       json={"job_url": "https://zhipin.com/job/sl1", "title": "收藏测试", "company": "C", "salary": "20K"},
                       headers=headers)
        assert resp.status_code == 200
        assert resp.json()["id"] > 0

    def test收藏列表(self, client):
        c, headers, _ = client
        c.post("/api/shortlists", json={"job_url": "https://zhipin.com/job/sl2", "title": "T"}, headers=headers)
        resp = c.get("/api/shortlists", headers=headers)
        assert resp.status_code == 200
        assert len(resp.json()["shortlists"]) >= 1

    def test重复收藏返回提示(self, client):
        c, headers, _ = client
        c.post("/api/shortlists", json={"job_url": "https://zhipin.com/job/sl3", "title": "T"}, headers=headers)
        resp = c.post("/api/shortlists", json={"job_url": "https://zhipin.com/job/sl3", "title": "T"}, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["status"] in ("already_exists", "duplicate")

    def test取消收藏(self, client):
        c, headers, _ = client
        resp = c.post("/api/shortlists", json={"job_url": "https://zhipin.com/job/sl4", "title": "T"}, headers=headers)
        sid = resp.json()["id"]
        resp = c.delete(f"/api/shortlists/{sid}", headers=headers)
        assert resp.status_code == 200
        # 列表中不再有
        resp = c.get("/api/shortlists", headers=headers)
        assert all(s["id"] != sid for s in resp.json()["shortlists"])


# ══════════════════════════════════════
#  7. 设置管理
# ══════════════════════════════════════

class TestSettings:
    """用户查看和修改设置的体验。"""

    def test查看默认设置(self, client):
        c, headers, _ = client
        resp = c.get("/api/settings", headers=headers)
        assert resp.status_code == 200
        settings = resp.json()["settings"]
        assert "daily_apply_limit" in settings
        assert "greeting_template" in settings
        assert "search_keywords" in settings

    def test修改每日投递上限(self, client):
        c, headers, _ = client
        resp = c.put("/api/settings", json={"daily_apply_limit": "25"}, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["updated"]["daily_apply_limit"] == "25"

    def test修改招呼语模板(self, client):
        c, headers, _ = client
        new_greeting = "您好，我对贵公司的{job_title}岗位非常感兴趣！"
        resp = c.put("/api/settings", json={"greeting_template": new_greeting}, headers=headers)
        assert resp.status_code == 200
        # 验证已保存
        resp = c.get("/api/settings", headers=headers)
        assert resp.json()["settings"]["greeting_template"] == new_greeting

    def test修改AI回复风格(self, client):
        c, headers, _ = client
        c.put("/api/settings", json={"ai_reply_style": "casual"}, headers=headers)
        resp = c.get("/api/settings", headers=headers)
        assert resp.json()["settings"]["ai_reply_style"] == "casual"

    def test修改搜索关键词(self, client):
        c, headers, _ = client
        c.put("/api/settings", json={"search_keywords": "AI Agent,大模型开发,RAG"}, headers=headers)
        resp = c.get("/api/settings", headers=headers)
        assert "AI Agent" in resp.json()["settings"]["search_keywords"]

    def test修改简历摘要(self, client):
        c, headers, _ = client
        c.put("/api/settings", json={"resume_summary": "5年Python开发经验"}, headers=headers)
        resp = c.get("/api/settings", headers=headers)
        assert "5年Python" in resp.json()["settings"]["resume_summary"]

    def testAI平台配置(self, client):
        c, headers, _ = client
        c.put("/api/settings", json={"ai_base_url": "https://api.deepseek.com/v1", "ai_model": "deepseek-chat"}, headers=headers)
        resp = c.get("/api/settings", headers=headers)
        s = resp.json()["settings"]
        assert s["ai_base_url"] == "https://api.deepseek.com/v1"
        assert s["ai_model"] == "deepseek-chat"

    def testAPIKey不泄露(self, client):
        """设置API Key后，GET接口不应返回完整密钥。"""
        c, headers, _ = client
        c.put("/api/settings", json={"ai_api_key": "sk-1234567890abcdefghijklmnop"}, headers=headers)
        resp = c.get("/api/settings", headers=headers)
        settings = resp.json()["settings"]
        assert "sk-1234567890abcdefghijklmnop" not in json.dumps(settings)
        assert settings.get("ai_key_configured") == "true"

    def test自动投递配置(self, client):
        c, headers, _ = client
        c.put("/api/settings", json={
            "auto_apply_enabled": "true",
            "auto_apply_threshold": "80",
            "auto_apply_hr_active_required": "true",
            "filter_inactive_hr": "true"
        }, headers=headers)
        resp = c.get("/api/settings", headers=headers)
        s = resp.json()["settings"]
        assert s["auto_apply_enabled"] == "true"
        assert s["auto_apply_threshold"] == "80"

    def test微信ID配置(self, client):
        c, headers, _ = client
        c.put("/api/settings", json={"wechat_id": "test_wechat_123"}, headers=headers)
        resp = c.get("/api/settings", headers=headers)
        assert resp.json()["settings"]["wechat_id"] == "test_wechat_123"


# ══════════════════════════════════════
#  8. 统计 & 趋势 & 漏斗
# ══════════════════════════════════════

class TestStatistics:
    """用户查看统计数据的体验。"""

    def test漏斗统计(self, client):
        c, headers, _ = client
        resp = c.get("/api/stats", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "today_applications" in data
        assert "pending" in data

    def test趋势数据(self, client):
        c, headers, _ = client
        resp = c.get("/api/stats/trend?days=7", headers=headers)
        assert resp.status_code == 200
        assert "trend" in resp.json()

    def test漏斗图数据(self, client):
        c, headers, _ = client
        resp = c.get("/api/stats/funnel", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "pending" in data
        assert "applied" in data
        assert "replied" in data

    def test去重统计(self, client):
        c, headers, _ = client
        resp = c.get("/api/jobs/dedup-stats", headers=headers)
        assert resp.status_code == 200
        assert "total_unique" in resp.json()

    def test数据修复(self, client):
        c, headers, _ = client
        resp = c.post("/api/stats/reconcile", headers=headers)
        assert resp.status_code == 200


# ══════════════════════════════════════
#  9. 跟进提醒
# ══════════════════════════════════════

class TestFollowup:
    """用户查看和处理跟进提醒。"""

    def test查看跟进列表(self, client):
        c, headers, _ = client
        resp = c.get("/api/followups", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "overdue" in data
        assert "stats" in data

    def test标记跟进完成(self, client):
        c, headers, _ = client
        from boss_app.models.application import add_application
        from boss_app.models.followup import set_initial_followup
        aid = add_application({"title": "跟进测试", "company": "C", "url": "https://zhipin.com/job/fu1"})
        set_initial_followup(aid, "applied")
        resp = c.post(f"/api/followups/{aid}/done", headers=headers)
        assert resp.status_code == 200

    def test标记不存在的岗位(self, client):
        c, headers, _ = client
        resp = c.post("/api/followups/99999/done", headers=headers)
        assert resp.status_code in (200, 404)  # 不存在返回404


# ══════════════════════════════════════
#  10. 自动投递
# ══════════════════════════════════════

class TestAutoApply:
    """用户触发自动投递的体验。"""

    def test手动触发无浏览器(self, client):
        c, headers, _ = client
        resp = c.post("/api/auto-apply/trigger", headers=headers)
        assert resp.status_code == 503  # 浏览器未启动

    def test查看投递日志(self, client):
        c, headers, _ = client
        resp = c.get("/api/auto-apply-logs", headers=headers)
        assert resp.status_code == 200
        assert "logs" in resp.json()

    def test投递日志带分页(self, client):
        c, headers, _ = client
        resp = c.get("/api/auto-apply-logs?limit=5", headers=headers)
        assert resp.status_code == 200


# ══════════════════════════════════════
#  11. 搜索功能
# ══════════════════════════════════════

class TestSearch:
    """用户搜索岗位的体验。"""

    def test搜索无浏览器返回503(self, client):
        c, headers, _ = client
        resp = c.post("/api/jobs/search",
                       json={"keyword": "Python", "city": "成都"},
                       headers=headers)
        assert resp.status_code == 503
        assert "浏览器" in resp.json().get("detail", "") or "未启动" in resp.json().get("detail", "")

    def test投递无浏览器返回503(self, client):
        c, headers, _ = client
        resp = c.post("/api/jobs/apply",
                       json={"job_url": "https://zhipin.com/job/x"},
                       headers=headers)
        assert resp.status_code == 503


# ══════════════════════════════════════
#  12. 聊天 & 会话
# ══════════════════════════════════════

class TestConversations:
    """用户查看聊天记录的体验。"""

    def test会话列表(self, client):
        c, headers, _ = client
        resp = c.get("/api/conversations", headers=headers)
        assert resp.status_code == 200
        assert "conversations" in resp.json()

    def test不存在的会话(self, client):
        c, headers, _ = client
        resp = c.get("/api/conversations/99999", headers=headers)
        assert resp.status_code == 404

    def test微信记录(self, client):
        c, headers, _ = client
        resp = c.get("/api/wechat-exchanges", headers=headers)
        assert resp.status_code == 200
        assert "exchanges" in resp.json()


# ══════════════════════════════════════
#  13. 定时任务
# ══════════════════════════════════════

class TestScheduler:
    """用户配置定时任务的体验。"""

    def test查看调度器状态(self, client):
        c, headers, _ = client
        resp = c.get("/api/scheduler/status", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "enabled" in data
        assert "running" in data

    def test启动调度器(self, client):
        c, headers, _ = client
        resp = c.post("/api/scheduler/start",
                       json={"enabled": True, "cron": "09:00,14:00"},
                       headers=headers)
        assert resp.status_code == 200

    def test停止调度器(self, client):
        c, headers, _ = client
        resp = c.post("/api/scheduler/stop", headers=headers)
        assert resp.status_code == 200


# ══════════════════════════════════════
#  14. 去重功能
# ══════════════════════════════════════

class TestDeduplication:
    """用户清理重复岗位的体验。"""

    def test去重操作(self, client):
        c, headers, _ = client
        from boss_app.models.application import add_application
        add_application({"title": "去重测试", "company": "A", "city": "成都", "salary": "10K", "url": "https://zhipin.com/job/dedup1"})
        add_application({"title": "去重测试", "company": "B", "city": "北京", "salary": "20K", "url": "https://zhipin.com/job/dedup2"})
        resp = c.post("/api/jobs/deduplicate", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "duplicates_found" in data
        assert "duplicates_removed" in data

    def test补全详情(self, client):
        c, headers, _ = client
        resp = c.post("/api/jobs/refetch", headers=headers)
        assert resp.status_code in (200, 503)  # 无浏览器时503


# ══════════════════════════════════════
#  15. 调试工具
# ══════════════════════════════════════

class TestDebug:
    """开发者调试工具。"""

    def test选择器测试(self, client):
        c, headers, _ = client
        resp = c.post("/api/debug/selector-test",
                       json={"selector": "div.job-card"},
                       headers=headers)
        assert resp.status_code in (200, 503)  # 无浏览器时503

    def test页面统计(self, client):
        c, headers, _ = client
        resp = c.get("/api/debug/page-stats", headers=headers)
        assert resp.status_code in (200, 503)

    def test选择器状态(self, client):
        c, headers, _ = client
        resp = c.get("/api/debug/selectors-status", headers=headers)
        assert resp.status_code in (200, 503)


# ══════════════════════════════════════
#  16. WebSocket
# ══════════════════════════════════════

class TestWebSocket:
    """WebSocket连接体验。"""

    def test无token连接被拒绝(self, client):
        c, _, _ = client
        with pytest.raises(Exception):
            with c.websocket_connect("/ws"):
                pass

    def test错误token连接被拒绝(self, client):
        c, _, _ = client
        with pytest.raises(Exception):
            with c.websocket_connect("/ws?token=wrong"):
                pass

    def test正确token可连接(self, client):
        c, _, token = client
        with c.websocket_connect(f"/ws?token={token}") as ws:
            # 发送ping
            ws.send_text('{"type":"ping"}')
            data = ws.receive_text()
            assert '"pong"' in data


# ══════════════════════════════════════
#  17. 完整用户旅程
# ══════════════════════════════════════

class TestUserJourney:
    """模拟一个完整用户的使用流程。"""

    def test完整求职流程(self, client):
        """
        模拟用户完整流程:
        1. 查看首页
        2. 检查系统状态
        3. 查看设置
        4. 添加岗位到数据库
        5. 查看岗位列表
        6. 收藏感兴趣的岗位
        7. 查看收藏列表
        8. 投递岗位
        9. 查看投递记录
        10. 删除不想要的岗位
        11. 查看回收站
        12. 恢复误删的岗位
        13. 查看统计数据
        14. 修改设置
        15. 查看跟进提醒
        """
        c, headers, token = client

        # 1. 首页
        resp = c.get("/")
        assert resp.status_code == 200
        assert "BOSS" in resp.text

        # 2. 系统状态
        resp = c.get("/api/status", headers=headers)
        assert resp.status_code == 200

        # 3. 查看设置
        resp = c.get("/api/settings", headers=headers)
        assert resp.status_code == 200
        old_limit = resp.json()["settings"].get("daily_apply_limit", "15")

        # 4. 添加岗位
        from boss_app.models.application import add_application
        aid1 = add_application({"title": "AI工程师", "company": "科技公司A", "url": "https://zhipin.com/job/journey1", "salary": "25-40K", "city": "成都"})
        aid2 = add_application({"title": "Python开发", "company": "科技公司B", "url": "https://zhipin.com/job/journey2", "salary": "20-30K", "city": "北京"})
        aid3 = add_application({"title": "大模型工程师", "company": "科技公司C", "url": "https://zhipin.com/job/journey3", "salary": "30-50K", "city": "上海"})

        # 5. 查看岗位列表
        resp = c.get("/api/jobs", headers=headers)
        assert resp.json()["total"] == 3

        # 6. 收藏
        c.post("/api/shortlists", json={"job_url": "https://zhipin.com/job/journey1", "title": "AI工程师", "company": "科技公司A", "salary": "25-40K"}, headers=headers)

        # 7. 收藏列表
        resp = c.get("/api/shortlists", headers=headers)
        assert len(resp.json()["shortlists"]) >= 1

        # 8. 投递（无浏览器，返回503）
        resp = c.post("/api/jobs/apply", json={"job_url": "https://zhipin.com/job/journey1"}, headers=headers)
        assert resp.status_code == 503

        # 9. 手动更新状态模拟投递
        from boss_app.models.application import update_application_status
        update_application_status(aid1, "applied", "您好，我对岗位感兴趣")
        resp = c.get("/api/jobs?status=applied", headers=headers)
        assert resp.json()["total"] >= 1

        # 10. 删除
        resp = c.post("/api/jobs/delete", json={"job_ids": [aid2]}, headers=headers)
        assert resp.json()["deleted"] == 1

        # 11. 回收站
        resp = c.get("/api/trash", headers=headers)
        assert resp.json()["count"] >= 1

        # 12. 恢复
        resp = c.post("/api/trash/restore", json={"job_ids": [aid2]}, headers=headers)
        assert resp.json()["restored"] == 1

        # 13. 统计
        resp = c.get("/api/stats", headers=headers)
        assert resp.status_code == 200
        resp = c.get("/api/stats/trend?days=7", headers=headers)
        assert resp.status_code == 200
        resp = c.get("/api/stats/funnel", headers=headers)
        assert resp.status_code == 200

        # 14. 修改设置
        resp = c.put("/api/settings", json={"daily_apply_limit": "20"}, headers=headers)
        assert resp.status_code == 200
        resp = c.get("/api/settings", headers=headers)
        assert resp.json()["settings"]["daily_apply_limit"] == "20"

        # 15. 跟进提醒
        resp = c.get("/api/followups", headers=headers)
        assert resp.status_code == 200
        assert "overdue" in resp.json()

        # 完成！
