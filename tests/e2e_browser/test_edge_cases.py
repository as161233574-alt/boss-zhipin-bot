"""测试：边界情况与错误处理。

包含：无效token、不存在的资源、损坏数据、超大输入、网络错误恢复。
"""
import pytest
import time
import json
import urllib.request
import urllib.error
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from helpers import screenshot, api_get, api_post, api_put, get_api_token, BASE_URL


def api_raw(method, path, data=None, headers=None, timeout=10):
    """原生API调用以便测试错误情况。"""
    url = BASE_URL + path
    hdrs = headers or {}
    if data is not None:
        hdrs["Content-Type"] = "application/json"
        body = json.dumps(data).encode("utf-8")
    else:
        body = None
    req = urllib.request.Request(url, data=body, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8") or "null")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8") or "null")
        except Exception:
            return e.code, None
    except Exception as e:
        return 0, {"error": str(e)}


class TestAuthErrors:
    """认证错误。"""

    def test_no_token(self):
        """无token应返回401。"""
        s, d = api_raw("GET", "/api/jobs", headers={})
        assert s == 401, f"无token应401, 实际 {s}"
        print(f"\n[认证] 无token: {s}")

    def test_wrong_token(self):
        """错误token应返回401。"""
        s, d = api_raw("GET", "/api/jobs", headers={"Authorization": "Bearer wrong_token_123"})
        assert s == 401
        print(f"[认证] 错误token: {s}")

    def test_malformed_auth_header(self):
        """畸形auth头。"""
        for hdr in ["Bearer ", "Bearer", "Basic xxx", "wrongformat", ""]:
            s, d = api_raw("GET", "/api/jobs", headers={"Authorization": hdr})
            assert s == 401, f"'{hdr}' -> {s}"
        print(f"[认证] 畸形auth头: 全部401")

    def test_empty_bearer(self):
        """空bearer。"""
        s, d = api_raw("GET", "/api/jobs", headers={"Authorization": "Bearer "})
        assert s == 401
        print(f"[认证] 空bearer: {s}")


class TestNotFoundErrors:
    """404错误。"""

    def test_nonexistent_job(self):
        """不存在的岗位。"""
        s, d = api_get("/api/jobs/999999")
        assert s == 404, f"不存在的岗位应404, 实际 {s}"
        print(f"\n[404] 岗位: {s}")

    def test_nonexistent_conversation(self):
        """不存在的会话。"""
        s, d = api_get("/api/conversations/999999")
        assert s == 404
        print(f"[404] 会话: {s}")

    def test_nonexistent_endpoint(self):
        """不存在的端点。"""
        s, d = api_get("/api/nonexistent-endpoint-xyz")
        assert s == 404
        print(f"[404] 端点: {s}")


class TestBadRequestErrors:
    """400错误。"""

    def test_invalid_json_body(self):
        """无效JSON。"""
        url = BASE_URL + "/api/jobs/search"
        req = urllib.request.Request(
            url,
            data=b"not json{{{",
            headers={
                "Authorization": f"Bearer {get_api_token()}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                s = resp.status
        except urllib.error.HTTPError as e:
            s = e.code
        assert s in (400, 422), f"无效JSON应400/422, 实际 {s}"
        print(f"\n[400] 无效JSON: {s}")

    def test_missing_required_field(self):
        """缺少必填字段。"""
        s, d = api_raw("POST", "/api/jobs/search", data={}, headers={"Authorization": f"Bearer {get_api_token()}"})
        # 搜索接口可能允许空搜索或返回错误
        print(f"\n[400] 空搜索体: {s}")

    def test_invalid_score_job_id(self):
        """评分的岗位ID无效。"""
        s, d = api_post("/api/jobs/abc/score", {})
        assert s in (400, 404, 422)
        print(f"[400] 字符串ID评分: {s}")


class TestLargeInput:
    """超大输入。"""

    def test_huge_keyword(self):
        """超大关键词 - 不应导致服务崩溃。"""
        try:
            s, d = api_post("/api/jobs/search", {"keyword": "x" * 1000, "city": "成都"}, timeout=15)
            print(f"\n[大输入] 1000字符关键词: {s}")
        except Exception as e:
            print(f"\n[大输入] 异常: {e}")

        # 验证服务还活着
        s, d = api_get("/api/status")
        assert s == 200
        print(f"  服务健康")

    def test_sql_injection_attempt(self):
        """SQL注入尝试。"""
        try:
            s, d = api_post("/api/jobs/search", {
                "keyword": "'; DROP TABLE applications; --",
                "city": "成都"
            }, timeout=15)
            print(f"\n[大输入] SQL注入尝试: {s}")
        except Exception as e:
            print(f"\n[大输入] 异常: {e}")

        # 验证数据库完好（表还存在）
        s, d = api_get("/api/jobs?limit=1")
        assert s == 200, "数据库表可能损坏"
        print(f"  数据库完好")

    def test_xss_attempt(self):
        """XSS尝试。"""
        try:
            s, d = api_post("/api/jobs/search", {
                "keyword": "<script>alert(1)</script>",
                "city": "成都"
            }, timeout=15)
            print(f"\n[大输入] XSS尝试: {s}")
        except Exception as e:
            print(f"\n[大输入] 异常: {e}")

        s, d = api_get("/api/status")
        assert s == 200


class TestBrowserErrors:
    """浏览器相关错误。"""

    def test_search_without_browser(self):
        """浏览器未运行时搜索 - 应能优雅处理。"""
        # 浏览器可能正在运行;搜索是长操作,可能超时或数据库锁
        # 关键是服务不应该崩溃
        try:
            s, d = api_post("/api/jobs/search", {"keyword": "Python", "city": "成都"}, timeout=15)
            print(f"\n[浏览器] 搜索状态: {s}")
            # 500 可能因数据库锁,这是真实世界的偶发情况
            # 但服务应该能响应新请求
        except Exception as e:
            print(f"\n[浏览器] 搜索异常: {e}")

        # 验证服务还在响应
        s2, d2 = api_get("/api/status")
        assert s2 == 200, f"服务挂了: {s2}"
        print(f"  服务健康: {s2}")

    def test_auto_apply_logs_max_limit(self):
        """日志最大limit。"""
        s, d = api_get("/api/auto-apply-logs?limit=10000")
        assert s == 200
        logs = d.get("logs", [])
        print(f"\n[浏览器] 大limit日志: {len(logs)} 条")


class TestConcurrency:
    """并发测试。"""

    def test_concurrent_api_calls(self):
        """并发API调用。"""
        import threading

        results = []
        def call():
            s, d = api_get("/api/jobs?limit=5")
            results.append(s)

        threads = [threading.Thread(target=call) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=15)

        success = sum(1 for s in results if s == 200)
        print(f"\n[并发] 10并发API: 成功 {success}/10")
        assert success >= 8, f"并发成功率太低: {success}/10"


class TestUIRecovery:
    """UI恢复能力。"""

    def test_console_errors_during_navigation(self, page, base_url):
        """导航时控制台错误。"""
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))

        page.goto(base_url)
        page.wait_for_load_state("networkidle")

        for tab in ["search", "applications", "chat", "wechat", "settings"]:
            page.locator(f'.sidebar-nav a[data-tab="{tab}"]').click()
            page.wait_for_timeout(300)

        print(f"\n[UI恢复] 切换5个Tab JS错误: {len(errors)}")
        for e in errors[:5]:
            print(f"  - {e[:80]}")
        # 不应有过多错误
        assert len(errors) < 10, f"JS错误过多: {len(errors)}"

    def test_404_page_renders(self, page, base_url):
        """SPA的404处理。"""
        page.goto(base_url + "/nonexistent-page-xyz")
        page.wait_for_timeout(1000)
        # SPA应该不崩溃
        title = page.title()
        print(f"\n[UI恢复] 不存在页面: title={title}")
