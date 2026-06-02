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
    """获取设置值。"""
    row = get_db().execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(key: str, value: str):
    """设置配置值。"""
    get_db().execute(
        "INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
        (key, value),
    )
    get_db().commit()


def get_all_settings() -> dict:
    """获取所有设置。"""
    rows = get_db().execute("SELECT key, value FROM settings").fetchall()
    return {r["key"]: r["value"] for r in rows}


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
