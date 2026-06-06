"""Models 层完整测试。"""
import json
import pytest
from boss_app.core.database import get_db


# ══════════════════════════════════════
#  application.py
# ══════════════════════════════════════

class TestApplication:
    @pytest.fixture(autouse=True)
    def _use_db(self, test_db):
        pass

    def test_add_and_get(self):
        from boss_app.models.application import add_application, get_application
        aid = add_application({"title": "Python开发", "company": "测试公司", "url": "https://zhipin.com/job/1", "salary": "15-25K"})
        assert aid > 0
        job = get_application(aid)
        assert job is not None
        assert job["job_title"] == "Python开发"
        assert job["company"] == "测试公司"
        assert job["status"] == "pending"

    def test_add_duplicate_url_recovers(self):
        from boss_app.models.application import add_application, get_application
        aid1 = add_application({"title": "A", "company": "C", "url": "https://zhipin.com/job/dup"})
        aid2 = add_application({"title": "B", "company": "D", "url": "https://zhipin.com/job/dup"})
        assert aid1 == aid2  # 同一 URL 返回同一 ID
        job = get_application(aid1)
        assert job["company"] == "D"  # 被更新

    def test_compute_dedup_key(self):
        from boss_app.models.application import compute_dedup_key
        key = compute_dedup_key({"title": "Python 开发", "company": "测试公司", "city": "成都", "salary": "15K"})
        assert key == "测试公司|python开发|成都|15k"
        assert compute_dedup_key({"title": "", "company": ""}) == ""

    def test_get_application_by_url(self):
        from boss_app.models.application import add_application, get_application_by_url
        add_application({"title": "T", "company": "C", "url": "https://zhipin.com/job/url1"})
        assert get_application_by_url("https://zhipin.com/job/url1") is not None
        assert get_application_by_url("https://zhipin.com/job/nonexist") is None

    def test_update_application_from_job(self):
        from boss_app.models.application import add_application, get_application, update_application_from_job
        aid = add_application({"title": "Old", "company": "C", "url": "https://zhipin.com/job/upd"})
        update_application_from_job(aid, {"title": "New", "company": "C"})
        job = get_application(aid)
        assert job["job_title"] == "New"

    def test_update_application_from_job_empty_not_overwrite(self):
        from boss_app.models.application import add_application, get_application, update_application_from_job
        aid = add_application({"title": "Original", "company": "C", "url": "https://zhipin.com/job/empty"})
        update_application_from_job(aid, {"title": "", "company": "NewCo"})
        job = get_application(aid)
        assert job["job_title"] == "Original"  # 空值不覆盖
        assert job["company"] == "NewCo"

    def test_list_applications(self):
        from boss_app.models.application import add_application, list_applications
        for i in range(5):
            add_application({"title": f"J{i}", "company": "C", "url": f"https://zhipin.com/job/l{i}"})
        jobs = list_applications(limit=3)
        assert len(jobs) == 3

    def test_list_applications_by_status(self):
        from boss_app.models.application import add_application, list_applications, update_application_status
        aid = add_application({"title": "S", "company": "C", "url": "https://zhipin.com/job/s1"})
        update_application_status(aid, "applied")
        applied = list_applications(status="applied")
        assert len(applied) >= 1
        assert applied[0]["status"] == "applied"

    def test_soft_delete_and_restore(self):
        from boss_app.models.application import add_application, get_application, soft_delete_application, restore_application
        aid = add_application({"title": "D", "company": "C", "url": "https://zhipin.com/job/del1"})
        assert soft_delete_application(aid) is True
        assert get_application(aid) is None  # 软删除后查不到
        assert restore_application(aid) is True
        assert get_application(aid) is not None

    def test_soft_delete_batch(self):
        from boss_app.models.application import add_application, soft_delete_applications, get_application
        ids = [add_application({"title": f"B{i}", "company": "C", "url": f"https://zhipin.com/job/b{i}"}) for i in range(3)]
        count = soft_delete_applications(ids)
        assert count == 3
        for aid in ids:
            assert get_application(aid) is None

    def test_clear_and_trash(self):
        from boss_app.models.application import add_application, clear_all_applications, get_trash_count, get_trash_applications
        for i in range(3):
            add_application({"title": f"T{i}", "company": "C", "url": f"https://zhipin.com/job/t{i}"})
        count = clear_all_applications()
        assert count == 3
        assert get_trash_count() == 3
        trash = get_trash_applications()
        assert len(trash) == 3

    def test_update_application_score(self):
        from boss_app.models.application import add_application, get_application, update_application_score
        aid = add_application({"title": "Sc", "company": "C", "url": "https://zhipin.com/job/sc1"})
        update_application_score(aid, 85, {"key_skills": ["Python"]})
        job = get_application(aid)
        assert job["score"] == 85
        assert "Python" in job["score_detail"]

    def test_update_application_legitimacy(self):
        from boss_app.models.application import add_application, get_application, update_application_legitimacy
        aid = add_application({"title": "L", "company": "C", "url": "https://zhipin.com/job/leg1"})
        update_application_legitimacy(aid, "high", [])
        job = get_application(aid)
        assert job["legitimacy"] == "high"

    def test_update_application_fields(self):
        from boss_app.models.application import add_application, get_application, update_application_fields
        aid = add_application({"title": "F", "company": "C", "url": "https://zhipin.com/job/f1"})
        update_application_fields(aid, {"hr_name": "张三", "hr_activity": "今日活跃"})
        job = get_application(aid)
        assert job["hr_name"] == "张三"
        assert job["hr_activity"] == "今日活跃"

    def test_update_composite_score(self):
        from boss_app.models.application import add_application, get_application, update_application_composite_score
        aid = add_application({"title": "CS", "company": "C", "url": "https://zhipin.com/job/cs1"})
        update_application_composite_score(aid, 78)
        job = get_application(aid)
        assert job["composite_score"] == 78

    def test_get_today_application_count(self):
        from boss_app.models.application import add_application, update_application_status, get_today_application_count
        aid = add_application({"title": "TC", "company": "C", "url": "https://zhipin.com/job/tc1"})
        update_application_status(aid, "applied", "你好")
        count = get_today_application_count()
        assert count >= 1

    def test_deduplicate_applications(self):
        from boss_app.models.application import add_application, deduplicate_applications, get_application
        # 两个不同的 dedup_key（不同 city）但同一 company+title
        add_application({"title": "Dup", "company": "C", "city": "成都", "salary": "10K", "url": "https://zhipin.com/job/dup1"})
        add_application({"title": "Dup", "company": "C", "city": "北京", "salary": "10K", "url": "https://zhipin.com/job/dup2"})
        result = deduplicate_applications()
        # 不同 dedup_key 不会被去重
        assert result["duplicates_removed"] == 0

    def test_get_auto_apply_candidates(self):
        from boss_app.models.application import add_application, update_application_composite_score, update_application_legitimacy, update_application_fields, get_auto_apply_candidates
        aid = add_application({"title": "AA", "company": "C", "url": "https://zhipin.com/job/aa1"})
        update_application_composite_score(aid, 80)
        update_application_legitimacy(aid, "high", [])
        update_application_fields(aid, {"score": 75, "hr_activity_score": 80})
        candidates = get_auto_apply_candidates(70)
        assert len(candidates) >= 1

    def test_log_auto_apply(self):
        from boss_app.models.application import add_application, log_auto_apply, get_auto_apply_logs
        aid = add_application({"title": "Log", "company": "C", "url": "https://zhipin.com/job/log1"})
        log_auto_apply(aid, 80, 60, "success")
        logs = get_auto_apply_logs()
        assert len(logs) >= 1
        assert logs[0]["result"] == "success"

    def test_get_application_for_scoring(self):
        from boss_app.models.application import add_application, get_application_for_scoring
        aid = add_application({"title": "Scor", "company": "C", "url": "https://zhipin.com/job/scor1", "description": "Python LLM"})
        job = get_application_for_scoring(aid)
        assert job is not None
        assert job["description"] == "Python LLM"

    def test_get_all_active_jobs_for_legitimacy(self):
        from boss_app.models.application import add_application, get_all_active_jobs_for_legitimacy
        add_application({"title": "LJ", "company": "C", "url": "https://zhipin.com/job/lj1"})
        jobs = get_all_active_jobs_for_legitimacy()
        assert len(jobs) >= 1
        # 只返回 company 和 job_title
        assert "company" in jobs[0]
        assert "job_title" in jobs[0]


# ══════════════════════════════════════
#  settings.py
# ══════════════════════════════════════

class TestSettings:
    @pytest.fixture(autouse=True)
    def _use_db(self, test_db):
        pass

    def test_get_setting_default(self):
        from boss_app.models.settings import get_setting
        assert get_setting("nonexist", "fallback") == "fallback"

    def test_set_and_get_setting(self):
        from boss_app.models.settings import set_setting, get_setting
        set_setting("test_key", "test_value")
        assert get_setting("test_key") == "test_value"

    def test_get_all_settings(self):
        from boss_app.models.settings import set_setting, get_all_settings
        set_setting("k1", "v1")
        set_setting("k2", "v2")
        all_s = get_all_settings()
        assert "k1" in all_s
        assert "k2" in all_s

    def test_increment_daily_stat(self):
        from boss_app.models.settings import increment_daily_stat, get_daily_stats
        increment_daily_stat("applications_sent")
        increment_daily_stat("applications_sent", 2)
        stats = get_daily_stats()
        assert stats.get("applications_sent", 0) >= 3

    def test_increment_invalid_field_raises(self):
        from boss_app.models.settings import increment_daily_stat
        with pytest.raises(ValueError, match="Invalid stat field"):
            increment_daily_stat("drop_table")

    def test_get_today_auto_reply_count(self):
        from boss_app.models.settings import get_today_auto_reply_count
        count = get_today_auto_reply_count()
        assert isinstance(count, int)

    def test_get_stats_range(self):
        from boss_app.models.settings import get_stats_range
        stats = get_stats_range(7)
        assert isinstance(stats, list)

    def test_get_funnel_stats(self):
        from boss_app.models.settings import get_funnel_stats
        funnel = get_funnel_stats()
        assert "pending" in funnel
        assert "applied" in funnel
        assert "apply_rate" in funnel

    def test_default_settings_populated(self):
        from boss_app.models.settings import get_setting
        assert get_setting("daily_apply_limit") == "15"
        assert get_setting("auto_apply_threshold") == "80"
        assert get_setting("search_keywords") != ""


# ══════════════════════════════════════
#  shortlist.py
# ══════════════════════════════════════

class TestShortlist:
    @pytest.fixture(autouse=True)
    def _use_db(self, test_db):
        pass

    def test_add_and_list(self):
        from boss_app.models.shortlist import add_to_shortlist, list_shortlists
        sid = add_to_shortlist("https://zhipin.com/job/sl1", "Python开发", "测试公司")
        assert sid > 0
        sl = list_shortlists()
        assert len(sl) >= 1

    def test_add_duplicate_returns_zero(self):
        from boss_app.models.shortlist import add_to_shortlist
        add_to_shortlist("https://zhipin.com/job/dup", "A")
        sid = add_to_shortlist("https://zhipin.com/job/dup", "B")
        assert sid == 0

    def test_is_in_shortlist(self):
        from boss_app.models.shortlist import add_to_shortlist, is_in_shortlist
        add_to_shortlist("https://zhipin.com/job/chk", "T")
        assert is_in_shortlist("https://zhipin.com/job/chk") is True
        assert is_in_shortlist("https://zhipin.com/job/nope") is False

    def test_remove_from_shortlist(self):
        from boss_app.models.shortlist import add_to_shortlist, remove_from_shortlist, list_shortlists
        sid = add_to_shortlist("https://zhipin.com/job/rm", "T")
        remove_from_shortlist(sid)
        sl = list_shortlists()
        assert all(s["id"] != sid for s in sl)


# ══════════════════════════════════════
#  followup.py
# ══════════════════════════════════════

class TestFollowup:
    @pytest.fixture(autouse=True)
    def _use_db(self, test_db):
        pass

    def test_compute_next_followup_applied(self):
        from boss_app.models.followup import compute_next_followup
        t = compute_next_followup("applied", 0)
        assert t is not None

    def test_compute_next_followup_replied(self):
        from boss_app.models.followup import compute_next_followup
        t = compute_next_followup("replied", 0)
        assert t is not None

    def test_compute_next_followup_with_count(self):
        from boss_app.models.followup import compute_next_followup
        t0 = compute_next_followup("applied", 0)
        t2 = compute_next_followup("applied", 2)
        assert t2 is not None

    def test_set_initial_followup(self):
        from boss_app.models.application import add_application, get_application
        from boss_app.models.followup import set_initial_followup
        aid = add_application({"title": "FU", "company": "C", "url": "https://zhipin.com/job/fu1"})
        set_initial_followup(aid, "applied")
        job = get_application(aid)
        assert job["follow_up_at"] is not None

    def test_record_followup(self):
        from boss_app.models.application import add_application, get_application
        from boss_app.models.followup import record_followup
        aid = add_application({"title": "RF", "company": "C", "url": "https://zhipin.com/job/rf1"})
        assert record_followup(aid) is True
        job = get_application(aid)
        assert job["follow_up_count"] == 1

    def test_record_followup_nonexist(self):
        from boss_app.models.followup import record_followup
        assert record_followup(99999) is False

    def test_get_followup_stats(self):
        from boss_app.models.followup import get_followup_stats
        stats = get_followup_stats()
        assert "overdue" in stats
        assert "upcoming_3days" in stats

    def test_get_overdue_followups(self):
        from boss_app.models.followup import get_overdue_followups
        overdue = get_overdue_followups()
        assert isinstance(overdue, list)
