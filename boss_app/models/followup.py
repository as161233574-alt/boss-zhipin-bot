"""跟进节奏数据层。

管理投递后的跟进提醒：记录跟进动作、计算下次跟进时间、查询超期列表。
"""

import sqlite3
from datetime import datetime, timedelta
from typing import List, Optional

from ..core.database import get_db


def compute_next_followup(status: str, count: int) -> str:
    """根据当前状态和已跟进次数，计算下次跟进时间。

    规则：
    - 首次跟进按状态：applied → 7天, replied → 3天, interview → 1天
    - 后续跟进按倍数递增，但 interview 始终保持较短间隔
    """
    base_days = {"applied": 7, "replied": 3, "interview": 1}
    days = base_days.get(status, 7)

    if count > 0:
        # 面试状态保持短间隔，其他状态递增
        if status == "interview":
            days = min(1 + count, 3)  # 最多3天
        else:
            days = min(days * (count + 1), 14)  # 最多14天

    next_time = datetime.now() + timedelta(days=days)
    return next_time.strftime("%Y-%m-%d %H:%M:%S")


def get_overdue_followups() -> List[dict]:
    """查询所有超期未跟进的投递记录。"""
    rows = get_db().execute(
        """SELECT a.id, a.job_title, a.company, a.salary, a.job_url, a.status,
                  a.follow_up_at, a.follow_up_count, a.created_at
           FROM applications a
           WHERE a.deleted_at IS NULL
             AND a.follow_up_at IS NOT NULL
             AND a.follow_up_at < datetime('now','localtime')
             AND a.status IN ('applied', 'replied', 'interview')
           ORDER BY a.follow_up_at ASC
           LIMIT 50"""
    ).fetchall()
    return [dict(r) for r in rows]


def get_followup_stats() -> dict:
    """返回跟进统计信息。"""
    db = get_db()
    overdue = db.execute(
        """SELECT COUNT(*) as cnt FROM applications
           WHERE deleted_at IS NULL AND follow_up_at IS NOT NULL
             AND follow_up_at < datetime('now','localtime')
             AND status IN ('applied', 'replied', 'interview')"""
    ).fetchone()["cnt"]
    upcoming = db.execute(
        """SELECT COUNT(*) as cnt FROM applications
           WHERE deleted_at IS NULL AND follow_up_at IS NOT NULL
             AND follow_up_at >= datetime('now','localtime')
             AND follow_up_at < datetime('now','localtime','+3 days')
             AND status IN ('applied', 'replied', 'interview')"""
    ).fetchone()["cnt"]
    total_followups = db.execute(
        """SELECT COALESCE(SUM(follow_up_count), 0) as cnt FROM applications
           WHERE deleted_at IS NULL AND follow_up_count > 0"""
    ).fetchone()["cnt"]
    return {"overdue": overdue, "upcoming_3days": upcoming, "total_followups": total_followups}


def record_followup(app_id: int, method: str = "manual") -> bool:
    """记录一次跟进动作，更新 follow_up_count 和下次跟进时间。"""
    db = get_db()
    row = db.execute(
        "SELECT id, status, follow_up_count FROM applications WHERE id=? AND deleted_at IS NULL",
        (app_id,),
    ).fetchone()
    if not row:
        return False

    count = (row["follow_up_count"] or 0) + 1
    next_time = compute_next_followup(row["status"] or "applied", count)

    db.execute(
        """UPDATE applications SET follow_up_count=?, follow_up_at=?,
           updated_at=CURRENT_TIMESTAMP WHERE id=?""",
        (count, next_time, app_id),
    )
    db.commit()
    return True


def set_initial_followup(app_id: int, status: str = "applied"):
    """投递成功时自动设置首次跟进时间。"""
    db = get_db()
    next_time = compute_next_followup(status, 0)
    db.execute(
        "UPDATE applications SET follow_up_at=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
        (next_time, app_id),
    )
    db.commit()
