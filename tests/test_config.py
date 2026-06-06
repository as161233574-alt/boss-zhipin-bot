"""Config 和 Database 层测试。"""
import pytest
from boss_app.core.database import get_db


# ══════════════════════════════════════
#  config.py
# ══════════════════════════════════════

class TestConfig:
    def test_city_map_has_major_cities(self):
        from boss_app.config import CITY_MAP
        assert "北京" in CITY_MAP
        assert "上海" in CITY_MAP
        assert "成都" in CITY_MAP
        assert "全国" in CITY_MAP

    def test_city_map_values_are_strings(self):
        from boss_app.config import CITY_MAP
        for name, code in CITY_MAP.items():
            assert isinstance(code, str), f"{name} code should be str"
            assert len(code) == 9, f"{name} code should be 9 digits, got {code}"

    def test_city_map_count(self):
        from boss_app.config import CITY_MAP
        assert len(CITY_MAP) >= 50

    def test_ua_list(self):
        from boss_app.config import UA_LIST
        assert len(UA_LIST) >= 1
        for ua in UA_LIST:
            assert "Mozilla" in ua


# ══════════════════════════════════════
#  database.py
# ══════════════════════════════════════

class TestDatabase:
    def test_tables_created(self, test_db):
        db = get_db()
        tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        assert "applications" in tables
        assert "conversations" in tables
        assert "messages" in tables
        assert "settings" in tables
        assert "daily_stats" in tables
        assert "shortlists" in tables
        assert "delete_log" in tables
        assert "auto_apply_log" in tables

    def test_indexes_created(self, test_db):
        db = get_db()
        indexes = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='index'").fetchall()]
        assert "idx_conv_app_id" in indexes
        assert "idx_msg_conv_id" in indexes
        assert "idx_app_status" in indexes
        assert "idx_app_deleted_at" in indexes

    def test_wal_mode(self, test_db):
        db = get_db()
        mode = db.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode == "wal"

    def test_foreign_keys_on(self, test_db):
        db = get_db()
        fk = db.execute("PRAGMA foreign_keys").fetchone()[0]
        assert fk == 1

    def test_applications_columns(self, test_db):
        db = get_db()
        columns = [r[1] for r in db.execute("PRAGMA table_info(applications)").fetchall()]
        assert "job_title" in columns
        assert "company" in columns
        assert "salary" in columns
        assert "job_url" in columns
        assert "status" in columns
        assert "score" in columns
        assert "composite_score" in columns
        assert "hr_activity_score" in columns
        assert "legitimacy" in columns
        assert "deleted_at" in columns
        assert "dedup_key" in columns
        assert "follow_up_at" in columns
        assert "follow_up_count" in columns

    def test_conversations_columns(self, test_db):
        db = get_db()
        columns = [r[1] for r in db.execute("PRAGMA table_info(conversations)").fetchall()]
        assert "hr_name" in columns
        assert "hr_company" in columns
        assert "auto_reply_enabled" in columns
        assert "interest_level" in columns
        assert "hr_wechat" in columns
        assert "emotion" in columns
        assert "dialogue_stage" in columns

    def test_settings_defaults(self, test_db):
        db = get_db()
        rows = db.execute("SELECT key, value FROM settings").fetchall()
        settings = {r["key"]: r["value"] for r in rows}
        assert "daily_apply_limit" in settings
        assert "auto_apply_threshold" in settings
        assert "search_keywords" in settings
        assert "greeting_template" in settings


# ══════════════════════════════════════
#  scraper.py (纯函数)
# ══════════════════════════════════════

class TestScraperUtils:
    def test_decode_salary(self):
        from boss_app.services.scraper import decode_salary
        # 正常文本不变
        assert decode_salary("15-25K") == "15-25K"

    def test_salary_ok(self):
        from boss_app.services.scraper import salary_ok
        assert salary_ok("15-25K") is True
        assert salary_ok("5-8K") is False  # 低于 15
        assert salary_ok("") is False

    def test_parse_skills(self):
        from boss_app.services.scraper import parse_skills
        skills = parse_skills("需要 Python 和 Docker 经验，熟悉 FastAPI")
        assert "Python" in str(skills)
        assert "Docker" in str(skills)

    def test_is_hr_inactive(self):
        from boss_app.services.scraper import BossScraper
        assert BossScraper.is_hr_inactive("") is True
        assert BossScraper.is_hr_inactive("本月活跃") is True
        assert BossScraper.is_hr_inactive("刚刚活跃") is False
        assert BossScraper.is_hr_inactive("今日活跃") is False
        assert BossScraper.is_hr_inactive("3日内活跃") is False
        assert BossScraper.is_hr_inactive("本周活跃") is False
