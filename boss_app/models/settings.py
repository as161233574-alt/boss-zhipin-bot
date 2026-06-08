"""
设置与每日统计数据层。
从 boss_state.py 提取的设置和每日统计相关函数。
"""

from datetime import date
from typing import Optional

from ..core.database import get_db


# ══════════════════════════════════════
#  Settings
# ══════════════════════════════════════


def get_setting(key: str, default: str = "") -> str:
    """获取设置值。空字符串视为未设置，回退到 default。"""
    row = get_db().execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    if not row:
        return default
    return row["value"] if row["value"] else default


def set_setting(key: str, value: str):
    """设置配置值。"""
    get_db().execute(
        "INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
        (key, value),
    )
    get_db().commit()


def set_settings_bulk(pairs: dict[str, str]):
    """批量设置配置值（单次事务提交）。"""
    db = get_db()
    for key, value in pairs.items():
        db.execute(
            "INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
            (key, value),
        )
    db.commit()


def get_all_settings() -> dict:
    """获取所有设置。"""
    rows = get_db().execute("SELECT key, value FROM settings").fetchall()
    return {r["key"]: r["value"] for r in rows}


# ── 所有设置项的默认值 ──
DEFAULT_SETTINGS = {
    # AI 配置
    "ai_platform": "deepseek",
    "ai_api_key": "",
    "ai_base_url": "https://api.deepseek.com/v1",
    "ai_model": "deepseek-chat",
    # 搜索配置
    "search_keywords": "",
    "default_city": "",
    "search_max_pages": "3",
    # 投递配置
    "auto_apply_enabled": "false",
    "auto_apply_threshold": "60",
    "auto_apply_hr_active_required": "true",
    "filter_inactive_hr": "true",
    "daily_apply_limit": "50",
    "batch_delay_min_sec": "30",
    "batch_delay_max_sec": "90",
    "experience_min": "",
    "experience_max": "",
    "salary_min": "",
    "salary_max": "",
    "salary_unit": "K",
    # 聊天配置
    "greeting_template": "",
    "greeting_enabled": "true",
    "greeting_type": "custom",
    "smart_greeting_enabled": "false",
    "auto_reply_enabled": "false",
    "reply_style": "热情友好",
    "min_reply_delay_sec": "3",
    "max_reply_delay_sec": "8",
    # 定时任务
    "auto_schedule_enabled": "false",
    "auto_schedule_cron": "09:00,14:00",
    # 简历
    "resume_summary": "",
    "resume_full_text": "",
    "resume_filename": "",
    "resume_text_length": "0",
    # 其他
    "wechat_id": "",
    "selector_overrides": "{}",
    "company_blacklist": "",
    "hr_blacklist": "",
}


def init_default_settings():
    """初始化所有设置的默认值（仅设置不存在的项，不覆盖已有值）。"""
    db = get_db()
    for key, value in DEFAULT_SETTINGS.items():
        db.execute(
            "INSERT OR IGNORE INTO settings (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
            (key, value),
        )
    db.commit()


# ══════════════════════════════════════
#  Daily Stats
# ══════════════════════════════════════


def _today() -> str:
    """获取今天的日期字符串。"""
    return date.today().isoformat()


def _ensure_today():
    """确保今日统计记录存在。"""
    get_db().execute("INSERT OR IGNORE INTO daily_stats (date) VALUES (?)", (_today(),))
    get_db().commit()


_ALLOWED_STAT_FIELDS = {"applications_sent", "messages_sent", "messages_received", "auto_replies_sent"}


def increment_daily_stat(field: str, amount: int = 1):
    """增加每日统计。

    包含 SQL 注入防护白名单：仅允许 _ALLOWED_STAT_FIELDS 中的字段。
    """
    if field not in _ALLOWED_STAT_FIELDS:
        raise ValueError(f"Invalid stat field: {field}")
    _ensure_today()
    get_db().execute(
        f"UPDATE daily_stats SET {field} = {field} + ? WHERE date=?",
        (amount, _today()),
    )
    get_db().commit()


def get_daily_stats(date_str: Optional[str] = None) -> dict:
    """获取指定日期的每日统计。默认返回今天的统计。"""
    d = date_str or _today()
    row = get_db().execute("SELECT * FROM daily_stats WHERE date=?", (d,)).fetchone()
    return dict(row) if row else {}


def get_today_auto_reply_count() -> int:
    """获取今日自动回复数量。"""
    row = (
        get_db()
        .execute(
            "SELECT COUNT(*) as cnt FROM messages WHERE ai_generated=1 AND date(created_at)=date('now','localtime')"
        )
        .fetchone()
    )
    return row["cnt"] if row else 0


def get_stats_range(days: int = 7) -> list:
    """获取最近 N 天的每日统计数组。"""
    rows = get_db().execute(
        """SELECT date, applications_sent, messages_sent, messages_received, auto_replies_sent
           FROM daily_stats
           WHERE date >= date('now','localtime',? || ' days')
           ORDER BY date ASC""",
        (f"-{days}",),
    ).fetchall()
    return [dict(r) for r in rows]


def get_funnel_stats() -> dict:
    """获取转化漏斗数据：pending → applied → replied → interview。"""
    db = get_db()
    # 合并 applications 统计为单条查询
    row = db.execute(
        "SELECT "
        "SUM(CASE WHEN status='pending' THEN 1 ELSE 0 END) as pending, "
        "SUM(CASE WHEN status='applied' THEN 1 ELSE 0 END) as applied "
        "FROM applications WHERE deleted_at IS NULL"
    ).fetchone()
    pending = row["pending"] or 0
    applied = row["applied"] or 0
    replied = db.execute(
        "SELECT COUNT(*) as cnt FROM conversations WHERE last_message_from='hr'"
    ).fetchone()["cnt"]
    interview = db.execute(
        "SELECT COUNT(*) as cnt FROM conversations WHERE interest_level='high'"
    ).fetchone()["cnt"]
    return {
        "pending": pending,
        "applied": applied,
        "replied": replied,
        "interview": interview,
        "apply_rate": min(round(applied / max(pending + applied, 1) * 100, 1), 100),
        "reply_rate": min(round(replied / max(applied, 1) * 100, 1), 100),
        "interview_rate": min(round(interview / max(replied, 1) * 100, 1), 100),
    }
