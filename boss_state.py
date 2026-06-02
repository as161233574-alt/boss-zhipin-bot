#!/usr/bin/env python3
"""向后兼容入口 - 实际逻辑已迁移到 boss_app/models/"""
from boss_app.core.database import get_db, init_db
from boss_app.models.application import (
    compute_dedup_key, get_application_by_dedup_key, add_application,
    get_application, get_application_by_url, update_application_from_job,
    list_applications, update_application_status,
    get_today_application_count, get_today_pending_count,
    count_hours_replied_in_range, count_interest_level,
    get_pending_applications,
    soft_delete_application, soft_delete_applications, clear_all_applications,
    get_trash_applications, restore_application, restore_applications,
    purge_old_trashes, get_delete_logs, get_trash_count,
    deduplicate_applications, get_duplicate_stats, reconcile_application_stats,
)
from boss_app.models.conversation import (
    get_or_create_conversation, get_conversation, list_active_conversations,
    find_conversation_by_hr_name, update_conversation_last_message,
    update_conversation_status, update_conversation_interest,
    update_conversation_wechat, mark_resume_sent, mark_phone_shared,
    get_wechat_exchanges, set_auto_reply,
)
from boss_app.models.message import (
    add_message, get_messages, get_recent_messages,
    replace_conversation_messages, get_last_hr_message, message_exists,
)
from boss_app.models.settings import (
    get_setting, set_setting, get_all_settings, get_daily_stats,
    increment_daily_stat, get_today_auto_reply_count,
)

# ══════════════════════════════════════
#  候选池（尚未迁移到新模块，保留在此）
# ══════════════════════════════════════


def add_to_shortlist(
    job_url: str, title: str, company: str = "", salary: str = "", city: str = "", note: str = ""
) -> int:
    import sqlite3
    db = get_db()
    try:
        cur = db.execute(
            "INSERT INTO shortlists (job_url, job_title, company, salary, city, note) VALUES (?,?,?,?,?,?)",
            (job_url, title, company, salary, city, note),
        )
        db.commit()
        return cur.lastrowid
    except sqlite3.IntegrityError:
        return 0


def remove_from_shortlist(shortlist_id: int):
    get_db().execute("DELETE FROM shortlists WHERE id=?", (shortlist_id,))
    get_db().commit()


def list_shortlists(limit: int = 100) -> list:
    rows = get_db().execute("SELECT * FROM shortlists ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


def is_in_shortlist(job_url: str) -> bool:
    row = get_db().execute("SELECT COUNT(*) as cnt FROM shortlists WHERE job_url=?", (job_url,)).fetchone()
    return row["cnt"] > 0 if row else False


# 启动时初始化
init_db()
