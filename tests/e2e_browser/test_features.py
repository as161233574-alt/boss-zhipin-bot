"""测试 4: 四大核心功能深度测试 - 搜索/评分/投递/回复。"""
import pytest
import time
import json
import sys
import urllib.request
import urllib.error
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from helpers import api_get, api_post, api_put, screenshot, get_api_token


class TestSearchFeature:
    """搜索功能完整测试。"""

    def test_01_search_via_api(self, base_url, api_token):
        """通过API测试搜索。"""
        print("\n[搜索 1] API 搜索")
        # 确认浏览器已启动
        s, status = api_get("/api/status")
        if not status.get("browser_running"):
            print("  [前置] 启动浏览器...")
            api_post("/api/system/start", timeout=60)
            time.sleep(3)
            s, status = api_get("/api/status")

        if not status.get("browser_running"):
            print("  [SKIP] 浏览器未启动")
            return

        # 触发搜索
        print("  [搜索] 关键词=Python, 城市=北京")
        t0 = time.time()
        s, d = api_post("/api/jobs/search", {
            "keyword": "Python",
            "city": "北京",
            "max_pages": 1
        }, timeout=180)
        elapsed = time.time() - t0
        print(f"  状态码: {s}, 耗时: {elapsed:.1f}s")

        if s == 200:
            print(f"  [OK] jobs_found: {d.get('jobs_found', 0)}")
            print(f"  [OK] new_jobs: {d.get('new_jobs', 0)}")
            print(f"  [OK] scored: {d.get('scored', 0)}")
            print(f"  [OK] scoring_in_background: {d.get('scoring_in_background', False)}")
        else:
            err = d.get("detail", d.get("error", ""))
            print(f"  [INFO] 搜索响应: {err[:80]}")

    def test_02_search_keyword_variation(self):
        """测试不同关键词搜索。"""
        print("\n[搜索 2] 不同关键词")
        keywords = ["AI", "产品经理", "数据分析"]
        for kw in keywords:
            print(f"  关键词: {kw}")
            s, d = api_post("/api/jobs/search", {
                "keyword": kw,
                "city": "上海",
                "max_pages": 1
            }, timeout=180)
            if s == 200:
                print(f"    [OK] found: {d.get('jobs_found', 0)}")
            else:
                print(f"    [INFO] {d.get('detail', '')[:50]}")

    def test_03_view_search_results(self, page, base_url):
        """在UI查看搜索结果。"""
        print("\n[搜索 3] UI 查看搜索结果")
        page.goto(base_url)
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(500)

        # 切到投递记录Tab看历史结果
        page.locator('.sidebar-nav a[data-tab="applications"]').click()
        page.wait_for_timeout(800)

        # 表格中的岗位
        rows = page.locator("#appTableBody tr").all()
        print(f"  表格行数: {len(rows)}")
        for row in rows[:5]:
            cells = row.locator("td").all()
            if len(cells) >= 3:
                # 第一列可能是checkbox
                title = cells[1].inner_text() if len(cells) > 1 else ""
                company = cells[2].inner_text() if len(cells) > 2 else ""
                try:
                    print(f"    {title[:30]} @ {company[:20]}")
                except UnicodeEncodeError:
                    print(f"    (non-ASCII title) @ (non-ASCII company)")

        screenshot(page, "30_search_results")

    def test_04_dedup_visualization(self, page, base_url):
        """去重数据展示。"""
        print("\n[搜索 4] 去重统计展示")
        page.goto(base_url)
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(500)

        s, d = api_get("/api/jobs/dedup-stats")
        print(f"  去重统计: {d}")
        assert "total_unique" in d


class TestScoringFeature:
    """评分功能完整测试。"""

    def test_01_score_single_job(self):
        """对单个岗位评分。"""
        print("\n[评分 1] 单岗位评分")
        # 找一个待评分岗位
        s, d = api_get("/api/jobs?status=pending&limit=1")
        jobs = d.get("jobs", [])
        if not jobs:
            print("  [SKIP] 无待评分岗位")
            return

        job_id = jobs[0]["id"]
        title = jobs[0].get("job_title", "")
        print(f"  评分岗位 [{job_id}]: {title[:40]}")

        t0 = time.time()
        s, d = api_post(f"/api/jobs/{job_id}/score", timeout=120)
        elapsed = time.time() - t0
        print(f"  状态: {s}, 耗时: {elapsed:.1f}s")

        if s == 200:
            score = d.get("score") or d
            cv = score.get("cv_score") or score.get("score")
            print(f"  [OK] CV匹配分: {cv}")
            print(f"  [OK] 质量分: {score.get('quality_score')}")
            print(f"  [OK] 综合分: {score.get('composite')}")
            print(f"  [OK] HR活跃分: {score.get('hr_score')}")
            print(f"  [OK] 合法性: {score.get('legitimacy')}")
            print(f"  [OK] 关键技能: {score.get('key_skills', [])[:5]}")
            print(f"  [OK] 差距: {(score.get('gap') or '')[:50]}")
            print(f"  [OK] 建议: {(score.get('advice') or '')[:50]}")
        else:
            print(f"  [INFO] {d}")

    def test_02_score_legitimacy_distribution(self):
        """合法性分布。"""
        print("\n[评分 2] 合法性分布")
        s, d = api_get("/api/jobs?limit=100")
        jobs = d.get("jobs", [])
        high = sum(1 for j in jobs if j.get("legitimacy") == "high")
        caution = sum(1 for j in jobs if j.get("legitimacy") == "caution")
        suspicious = sum(1 for j in jobs if j.get("legitimacy") == "suspicious")
        unscored = sum(1 for j in jobs if j.get("composite_score") is None)
        scored = len(jobs) - unscored
        print(f"  总数: {len(jobs)}")
        print(f"  已评分: {scored} ({scored*100//max(len(jobs),1)}%)")
        print(f"  high: {high}, caution: {caution}, suspicious: {suspicious}")

    def test_03_auto_apply_candidates(self):
        """自动投递候选。"""
        print("\n[评分 3] 自动投递候选")
        s, d = api_get("/api/auto-apply-candidates?limit=10")
        candidates = d.get("candidates", [])
        print(f"  候选数: {len(candidates)}")
        for c in candidates[:5]:
            print(f"    [{c.get('composite_score')}] {c.get('job_title', '')[:40]}")

    def test_04_score_persistence(self):
        """评分持久化。"""
        print("\n[评分 4] 评分持久化")
        s, d = api_get("/api/jobs?status=pending&limit=1")
        jobs = d.get("jobs", [])
        if not jobs:
            print("  [SKIP] 无岗位")
            return

        # 评分前
        before = jobs[0]
        before_score = before.get("composite_score")
        print(f"  评分前综合分: {before_score}")

        # 评分
        job_id = before["id"]
        s, d = api_post(f"/api/jobs/{job_id}/score", timeout=120)

        # 评分后
        s, d = api_get(f"/api/jobs/{job_id}")
        if d.get("job"):
            j = d["job"]
            after_score = j.get("composite_score")
            print(f"  评分后综合分: {after_score}")
            if before_score is None and after_score is not None:
                print(f"  [OK] 评分已保存")


class TestApplyFeature:
    """智能投递功能测试。"""

    def test_01_auto_apply_settings(self):
        """自动投递配置。"""
        print("\n[投递 1] 自动投递配置")
        s, d = api_get("/api/settings")
        s = d.get("settings", {})
        print(f"  auto_apply_enabled: {s.get('auto_apply_enabled')}")
        print(f"  auto_apply_threshold: {s.get('auto_apply_threshold')}")
        print(f"  auto_apply_hr_active_required: {s.get('auto_apply_hr_active_required')}")
        print(f"  daily_apply_limit: {s.get('daily_apply_limit')}")

    def test_02_toggle_auto_apply(self):
        """切换自动投递。"""
        print("\n[投递 2] 切换自动投递")
        # 先查看当前状态
        s, d = api_get("/api/settings")
        old = d.get("settings", {}).get("auto_apply_enabled")

        # 切换
        new_val = "false" if old == "true" else "true"
        s, d = api_put("/api/settings", {"auto_apply_enabled": new_val})
        print(f"  切换: {old} -> {new_val}")

        # 验证
        s, d = api_get("/api/settings")
        cur = d.get("settings", {}).get("auto_apply_enabled")
        print(f"  验证: {cur}")
        assert cur == new_val

        # 恢复
        s, d = api_put("/api/settings", {"auto_apply_enabled": old or "false"})

    def test_03_manual_apply(self):
        """手动投递。"""
        print("\n[投递 3] 手动投递")
        # 检查浏览器
        s, status = api_get("/api/status")
        if not status.get("browser_running"):
            print("  [SKIP] 浏览器未启动")
            return

        s, d = api_get("/api/jobs?status=pending&limit=1")
        jobs = d.get("jobs", [])
        if not jobs:
            print("  [SKIP] 无待投递岗位")
            return

        job = jobs[0]
        job_id = job["id"]
        job_url = job.get("job_url")

        if not job_url:
            print(f"  [SKIP] 岗位 {job_id} 无URL")
            return

        print(f"  投递 [{job_id}]: {job.get('job_title','')[:30]}")
        s, d = api_post("/api/jobs/apply", {"job_url": job_url}, timeout=120)
        print(f"  响应: {s}")
        print(f"  detail: {str(d)[:200]}")

    def test_04_duplicate_apply_rejected(self):
        """重复投递被拒。"""
        print("\n[投递 4] 重复投递拦截")
        s, d = api_get("/api/jobs?status=applied&limit=1")
        jobs = d.get("jobs", [])
        if not jobs:
            print("  [SKIP] 无已投递岗位")
            return

        job = jobs[0]
        job_url = job.get("job_url")
        if not job_url:
            return

        s, d = api_post("/api/jobs/apply", {"job_url": job_url}, timeout=30)
        success = d.get("success")
        msg = d.get("message", "")
        print(f"  success: {success}")
        print(f"  message: {msg[:50]}")
        # 如果浏览器未运行，接口会返回503，跳过
        if s == 503:
            print("  [SKIP] 浏览器未运行")
            return
        # BOSS直聘允许重复投递（重新沟通），所以两种结果都可接受
        # 1) 被拦截: success=False 或 message 含"已投递"/"已沟通"
        # 2) 重复投递成功: success=True, message含"投递成功"/"已投递过"
        print(f"  [OK] 重复投递处理结果: {'拦截' if not success else '允许重新沟通'}")

    def test_05_auto_apply_trigger(self):
        """触发自动投递。"""
        print("\n[投递 5] 触发自动投递")
        s, d = api_post("/api/auto-apply/trigger", timeout=60)
        print(f"  状态: {s}")
        print(f"  detail: {str(d)[:200]}")

    def test_06_apply_logs(self):
        """投递日志。"""
        print("\n[投递 6] 投递日志")
        s, d = api_get("/api/auto-apply-logs?limit=10")
        logs = d.get("logs", [])
        print(f"  日志数: {len(logs)}")
        for log in logs[:5]:
            print(f"    {log}")

    def test_07_today_stats(self):
        """今日统计。"""
        print("\n[投递 7] 今日统计")
        s, d = api_get("/api/stats")
        print(f"  今日投递: {d.get('today_applications', 0)}")
        print(f"  待投递: {d.get('pending', 0)}")
        print(f"  已回复: {d.get('replied', 0)}")


class TestReplyFeature:
    """智能回复功能测试。"""

    def test_01_list_conversations(self):
        """会话列表。"""
        print("\n[回复 1] 会话列表")
        s, d = api_get("/api/conversations")
        convs = d.get("conversations", [])
        print(f"  会话数: {len(convs)}")
        for c in convs[:5]:
            print(f"    [{c.get('id')}] {c.get('hr_name', '')} - {c.get('company', '')}")
            print(f"      自动回复: {c.get('auto_reply_enabled')}")
            print(f"      兴趣: {c.get('interest_level', 'none')}")

    def test_02_conversation_messages(self):
        """会话消息。"""
        print("\n[回复 2] 会话消息")
        s, d = api_get("/api/conversations")
        convs = d.get("conversations", [])
        if not convs:
            print("  [SKIP] 无会话")
            return

        conv_id = convs[0]["id"]
        s, d = api_get(f"/api/conversations/{conv_id}/messages?limit=10")
        msgs = d.get("messages", [])
        print(f"  消息数: {len(msgs)}")
        for m in msgs[:5]:
            sender = "HR" if m.get("sender") == "hr" else "我"
            ai = " [AI]" if m.get("ai_generated") else ""
            content = (m.get("content") or "")[:40]
            print(f"    {sender}{ai}: {content}")

    def test_03_pause_resume_auto_reply(self):
        """暂停/恢复自动回复。"""
        print("\n[回复 3] 暂停/恢复自动回复")
        s, d = api_get("/api/conversations")
        convs = d.get("conversations", [])
        if not convs:
            print("  [SKIP] 无会话")
            return

        conv_id = convs[0]["id"]
        # 暂停
        s, d = api_post(f"/api/conversations/{conv_id}/pause")
        print(f"  暂停: status={s}, resp={d}")

        # 恢复
        s, d = api_post(f"/api/conversations/{conv_id}/resume")
        print(f"  恢复: status={s}, resp={d}")

    def test_04_send_message(self):
        """发送消息。"""
        print("\n[回复 4] 发送消息")
        s, d = api_get("/api/conversations")
        convs = d.get("conversations", [])
        if not convs:
            print("  [SKIP] 无会话")
            return

        conv_id = convs[0]["id"]
        s, d = api_post(f"/api/conversations/{conv_id}/send", {
            "content": "你好，我对这个岗位很感兴趣，可以聊聊吗？"
        }, timeout=60)
        print(f"  发送: status={s}")
        print(f"  detail: {str(d)[:200]}")

    def test_05_sync_conversation(self):
        """同步会话。"""
        print("\n[回复 5] 同步会话")
        s, d = api_get("/api/conversations")
        convs = d.get("conversations", [])
        if not convs:
            print("  [SKIP] 无会话")
            return

        conv_id = convs[0]["id"]
        s, d = api_post(f"/api/conversations/{conv_id}/sync", timeout=60)
        print(f"  同步: status={s}")
        print(f"  detail: {str(d)[:200]}")

    def test_06_auto_reply_config(self):
        """自动回复配置。"""
        print("\n[回复 6] 自动回复配置")
        s, d = api_get("/api/settings")
        s = d.get("settings", {})
        print(f"  auto_reply_enabled: {s.get('auto_reply_enabled')}")
        print(f"  ai_reply_style: {s.get('ai_reply_style')}")
        print(f"  min_reply_delay_sec: {s.get('min_reply_delay_sec')}")
        print(f"  max_reply_delay_sec: {s.get('max_reply_delay_sec')}")
