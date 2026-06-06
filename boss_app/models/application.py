"""
投递记录数据层。
从 boss_state.py 提取的应用相关函数。
"""

import json
import sqlite3
from typing import List, Optional

from ..core.database import get_db


# ══════════════════════════════════════
#  Helpers
# ══════════════════════════════════════


def _log_delete(db, action: str, count: int, job_ids: str = "", detail: str = ""):
    db.execute(
        "INSERT INTO delete_log (action, count, job_ids, detail) VALUES (?,?,?,?)",
        (action, count, job_ids, detail),
    )


# ══════════════════════════════════════
#  Applications
# ══════════════════════════════════════


def compute_dedup_key(job: dict) -> str:
    """根据公司+岗位+城市+薪资生成联合去重键。"""
    company = (job.get("company") or job.get("company_name") or "").strip().lower().replace(" ", "")
    title = (job.get("title") or job.get("job_title") or "").strip().lower().replace(" ", "")
    city = (job.get("city") or "").strip().lower().replace(" ", "")
    salary = (job.get("salary") or "").strip().lower().replace(" ", "")
    if not company and not title:
        return ""
    return f"{company}|{title}|{city}|{salary}"


def get_application_by_dedup_key(key: str) -> Optional[dict]:
    if not key:
        return None
    row = get_db().execute(
        "SELECT * FROM applications WHERE dedup_key=? AND deleted_at IS NULL", (key,)
    ).fetchone()
    return dict(row) if row else None


def add_application(job: dict) -> int:
    db = get_db()
    dedup_key = compute_dedup_key(job)
    try:
        cur = db.execute(
            """INSERT INTO applications
               (job_title, company, salary, job_url, city, experience, education, hr_name, hr_title, description, dedup_key)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                job.get("title", ""),
                job.get("company", ""),
                job.get("salary", ""),
                job.get("url", ""),
                job.get("city", ""),
                job.get("experience", ""),
                job.get("education", ""),
                job.get("hr_name", ""),
                job.get("hr_title", ""),
                job.get("description", ""),
                dedup_key,
            ),
        )
        db.commit()
        return cur.lastrowid if cur.lastrowid else 0
    except sqlite3.IntegrityError as e:
        # UNIQUE constraint failed - URL already exists (including soft-deleted records)
        if "UNIQUE" in str(e) and job.get("url"):
            url = job["url"]
            # 查找已存在的记录（包括已软删除的）
            row = db.execute("SELECT id, deleted_at FROM applications WHERE job_url=?", (url,)).fetchone()
            if row:
                aid = row["id"]
                if row["deleted_at"]:
                    # 已软删除的记录：恢复并更新
                    db.execute("UPDATE applications SET deleted_at=NULL, updated_at=CURRENT_TIMESTAMP WHERE id=?", (aid,))
                update_application_from_job(aid, job)
                db.commit()
                return aid
        # Other error or no URL - re-raise
        raise


def get_application(app_id: int) -> Optional[dict]:
    row = get_db().execute(
        "SELECT * FROM applications WHERE id=? AND deleted_at IS NULL", (app_id,)
    ).fetchone()
    return dict(row) if row else None


def get_application_by_url(url: str) -> Optional[dict]:
    row = get_db().execute(
        "SELECT * FROM applications WHERE job_url=? AND deleted_at IS NULL", (url,)
    ).fetchone()
    return dict(row) if row else None


def update_application_from_job(app_id: int, job: dict) -> None:
    """用本次搜索结果刷新已有岗位；空值不覆盖旧值。"""
    fields = {
        "job_title": job.get("title", ""),
        "company": job.get("company", ""),
        "salary": job.get("salary", ""),
        "city": job.get("city", ""),
        "experience": job.get("experience", ""),
        "education": job.get("education", ""),
        "hr_name": job.get("hr_name", ""),
        "hr_title": job.get("hr_title", ""),
        "description": job.get("description", ""),
    }
    params = []
    assignments = []
    for column, value in fields.items():
        value = (value or "").strip()
        assignments.append(f"{column}=CASE WHEN ?!='' THEN ? ELSE {column} END")
        params.extend([value, value])
    params.append(app_id)

    db = get_db()
    db.execute(
        f"""UPDATE applications SET {", ".join(assignments)},
            updated_at=CURRENT_TIMESTAMP WHERE id=?""",
        params,
    )
    # 用 job 数据计算 dedup_key（新值非空则用新值，否则保持旧值由 CASE WHEN 处理）
    final_key = compute_dedup_key({
        "title": job.get("title", ""),
        "company": job.get("company", ""),
        "city": job.get("city", ""),
        "salary": job.get("salary", ""),
    })
    if final_key:
        try:
            db.execute("UPDATE applications SET dedup_key=? WHERE id=?", (final_key, app_id))
        except sqlite3.IntegrityError:
            pass  # 唯一索引冲突说明已有相同key的记录，保持当前key不变
    db.commit()


def list_applications(
    status: Optional[str] = None,
    limit: int = 50,
    include_deleted: bool = False,
    unique: bool = True,
    sort_by: str = "updated_at",
) -> List[dict]:
    """查询岗位列表。unique=True 时按 dedup_key 去重，每组返回最新一条。"""
    db = get_db()
    conds = [] if include_deleted else ["deleted_at IS NULL"]
    params: list = []
    if status:
        conds.append("status=?")
        params.append(status)
    where = ("WHERE " + " AND ".join(conds)) if conds else ""

    # 确定排序字段
    valid_sort_fields = {"updated_at", "composite_score", "score", "created_at"}
    if sort_by not in valid_sort_fields:
        sort_by = "updated_at"
    # SQLite不支持NULLS LAST，使用CASE WHEN处理NULL值
    if sort_by in ("composite_score", "score"):
        sort_expr = f"CASE WHEN a.{sort_by} IS NULL THEN 1 ELSE 0 END, a.{sort_by} DESC"
    else:
        sort_expr = f"a.{sort_by} DESC"

    if unique:
        # 子查询：按 dedup_key 分组取最新 id，dedup_key 为空的记录各自独立
        inner_conds = [] if include_deleted else ["deleted_at IS NULL"]
        if status:
            inner_conds.append("status=?")
        inner_where = ("WHERE " + " AND ".join(inner_conds)) if inner_conds else ""
        inner_params = list(params)  # copy

        sql = f"""SELECT a.* FROM applications a
            INNER JOIN (
                SELECT MAX(id) as mid FROM applications {inner_where}
                GROUP BY CASE WHEN dedup_key IS NULL OR dedup_key='' THEN '_row_'||id ELSE dedup_key END
            ) u ON a.id = u.mid
            ORDER BY {sort_expr} LIMIT ?"""
        inner_params.append(limit)
        rows = db.execute(sql, inner_params).fetchall()
    else:
        params.append(limit)
        rows = db.execute(
            f"SELECT * FROM applications {where} ORDER BY {sort_expr} LIMIT ?", params
        ).fetchall()

    return [dict(r) for r in rows]


def update_application_status(app_id: int, status: str, greeting_text: Optional[str] = None):
    db = get_db()
    if greeting_text:
        db.execute(
            """UPDATE applications SET status=?, greeting_text=?, greeting_sent_at=CURRENT_TIMESTAMP,
               updated_at=CURRENT_TIMESTAMP WHERE id=?""",
            (status, greeting_text, app_id),
        )
    elif status == "applied":
        # 投递成功但无招呼语时，仍记录时间戳（用于今日投递计数）
        db.execute(
            """UPDATE applications SET status=?, greeting_sent_at=CURRENT_TIMESTAMP,
               updated_at=CURRENT_TIMESTAMP WHERE id=?""",
            (status, app_id),
        )
    else:
        db.execute(
            "UPDATE applications SET status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (status, app_id),
        )
    # 投递成功时自动设置跟进提醒（在 commit 之前，保证原子性）
    if status == "applied":
        try:
            from .followup import set_initial_followup
            set_initial_followup(app_id, status)
        except Exception as e:
            print(f"[警告] 设置跟进提醒失败 (app_id={app_id}): {e}")
    db.commit()


def get_today_application_count() -> int:
    """今日投递数（按 dedup_key 去重后计数）。"""
    row = (
        get_db()
        .execute("""SELECT COUNT(*) as cnt FROM (
                SELECT MAX(id) as mid FROM applications
                WHERE deleted_at IS NULL AND date(greeting_sent_at)=date('now','localtime')
                GROUP BY CASE WHEN dedup_key IS NULL OR dedup_key='' THEN '_row_'||id ELSE dedup_key END
            )""")
        .fetchone()
    )
    return row["cnt"] if row else 0


def get_today_pending_count() -> int:
    """待投递数（按 dedup_key 去重后计数）。"""
    row = get_db().execute("""SELECT COUNT(*) as cnt FROM (
            SELECT MAX(id) as mid FROM applications
            WHERE deleted_at IS NULL AND status='pending'
            GROUP BY CASE WHEN dedup_key IS NULL OR dedup_key='' THEN '_row_'||id ELSE dedup_key END
        )""").fetchone()
    return row["cnt"] if row else 0


def count_hours_replied_in_range(hours: int) -> int:
    row = (
        get_db()
        .execute(
            "SELECT COUNT(*) as cnt FROM conversations WHERE last_message_from='hr' AND datetime(last_message_at) > datetime('now','localtime',? || ' hours')",
            (f"-{hours}",),
        )
        .fetchone()
    )
    return row["cnt"] if row else 0


def count_interest_level(level: str) -> int:
    row = get_db().execute(
        "SELECT COUNT(*) as cnt FROM conversations WHERE interest_level=?", (level,)
    ).fetchone()
    return row["cnt"] if row else 0


def get_pending_applications(limit: int = 50) -> List[dict]:
    """获取待投递岗位（按 dedup_key 去重，每组仅取最新一条）。"""
    rows = (
        get_db()
        .execute(
            """SELECT a.* FROM applications a
               INNER JOIN (
                   SELECT MAX(id) as mid FROM applications
                   WHERE deleted_at IS NULL AND status='pending' AND job_url!=''
                   GROUP BY CASE WHEN dedup_key IS NULL OR dedup_key='' THEN '_row_'||id ELSE dedup_key END
               ) u ON a.id = u.mid
               ORDER BY a.id LIMIT ?""",
            (limit,),
        )
        .fetchall()
    )
    return [dict(r) for r in rows]


# ══════════════════════════════════════
#  软删除 & 回收站
# ══════════════════════════════════════


def soft_delete_application(app_id: int) -> bool:
    db = get_db()
    row = db.execute(
        "UPDATE applications SET deleted_at=CURRENT_TIMESTAMP WHERE id=? AND deleted_at IS NULL",
        (app_id,),
    )
    if row.rowcount > 0:
        # 同步删除关联收藏
        url_row = db.execute("SELECT job_url FROM applications WHERE id=?", (app_id,)).fetchone()
        if url_row:
            db.execute("DELETE FROM shortlists WHERE job_url=?", (url_row["job_url"],))
        _log_delete(db, "single", 1, str(app_id))
        db.commit()
        return True
    return False


def soft_delete_applications(app_ids: List[int]) -> int:
    db = get_db()
    placeholders = ",".join("?" * len(app_ids))
    row = db.execute(
        f"UPDATE applications SET deleted_at=CURRENT_TIMESTAMP WHERE id IN ({placeholders}) AND deleted_at IS NULL",
        app_ids,
    )
    count = row.rowcount
    if count > 0:
        # 同步删除关联收藏（批量）
        urls = db.execute(
            f"SELECT job_url FROM applications WHERE id IN ({placeholders})", app_ids
        ).fetchall()
        if urls:
            url_list = [r["job_url"] for r in urls]
            ph = ",".join("?" * len(url_list))
            db.execute(f"DELETE FROM shortlists WHERE job_url IN ({ph})", url_list)
        _log_delete(db, "batch", count, ",".join(str(i) for i in app_ids))
        db.commit()
    return count


def clear_all_applications() -> int:
    db = get_db()
    row = db.execute("UPDATE applications SET deleted_at=CURRENT_TIMESTAMP WHERE deleted_at IS NULL")
    count = row.rowcount
    if count > 0:
        db.execute("DELETE FROM shortlists")
        _log_delete(db, "clear_all", count, detail="清空所有岗位")
        db.commit()
    return count


def get_trash_applications(limit: int = 100) -> List[dict]:
    rows = (
        get_db()
        .execute(
            "SELECT * FROM applications WHERE deleted_at IS NOT NULL ORDER BY deleted_at DESC LIMIT ?",
            (limit,),
        )
        .fetchall()
    )
    return [dict(r) for r in rows]


def restore_application(app_id: int) -> bool:
    db = get_db()
    row = db.execute(
        "UPDATE applications SET deleted_at=NULL WHERE id=? AND deleted_at IS NOT NULL", (app_id,)
    )
    if row.rowcount > 0:
        _log_delete(db, "restore", 1, str(app_id))
        db.commit()
        return True
    return False


def restore_applications(app_ids: List[int]) -> int:
    db = get_db()
    placeholders = ",".join("?" * len(app_ids))
    row = db.execute(
        f"UPDATE applications SET deleted_at=NULL WHERE id IN ({placeholders}) AND deleted_at IS NOT NULL",
        app_ids,
    )
    count = row.rowcount
    if count > 0:
        _log_delete(db, "restore_batch", count, ",".join(str(i) for i in app_ids))
        db.commit()
    return count


def purge_old_trashes(days: int = 7) -> int:
    """永久删除超过指定天数的回收站记录。"""
    db = get_db()
    row = db.execute(
        "DELETE FROM applications WHERE deleted_at IS NOT NULL AND deleted_at < datetime('now','localtime',? || ' days')",
        (f"-{days}",),
    )
    count = row.rowcount
    if count > 0:
        _log_delete(db, "purge", count, detail=f"自动清理{days}天前的回收站")
        db.commit()
    return count


def get_delete_logs(limit: int = 50) -> List[dict]:
    rows = get_db().execute(
        "SELECT * FROM delete_log ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    return [dict(r) for r in rows]


def get_trash_count() -> int:
    row = get_db().execute(
        "SELECT COUNT(*) as cnt FROM applications WHERE deleted_at IS NOT NULL"
    ).fetchone()
    return row["cnt"] if row else 0


# ══════════════════════════════════════
#  去重 & 统计修复
# ══════════════════════════════════════


def deduplicate_applications() -> dict:
    """清理历史重复数据：按 dedup_key 分组，每组保留 id 最小的记录，其余软删除。"""
    db = get_db()
    # 该操作可能耗时较长，提升本连接的 busy_timeout 避免被锁住
    db.execute("PRAGMA busy_timeout=30000")
    total = db.execute("SELECT COUNT(*) FROM applications WHERE deleted_at IS NULL").fetchone()[0]
    # 找出所有重复组中需要删除的 id
    dup_rows = db.execute(
        """SELECT id FROM applications
           WHERE deleted_at IS NULL AND dedup_key != '' AND dedup_key IN (
               SELECT dedup_key FROM applications WHERE deleted_at IS NULL AND dedup_key != ''
               GROUP BY dedup_key HAVING COUNT(*) > 1
           )
           AND id NOT IN (
               SELECT MIN(id) FROM applications WHERE deleted_at IS NULL AND dedup_key != ''
               GROUP BY dedup_key
           )"""
    ).fetchall()
    dup_ids = [r[0] for r in dup_rows]
    removed = 0
    if dup_ids:
        placeholders = ",".join("?" * len(dup_ids))
        db.execute(
            f"UPDATE applications SET deleted_at=CURRENT_TIMESTAMP WHERE id IN ({placeholders})",
            dup_ids,
        )
        _log_delete(db, "deduplicate", len(dup_ids), ",".join(str(i) for i in dup_ids), f"清理重复岗位 {len(dup_ids)} 条")
        db.commit()
        removed = len(dup_ids)
    # 为缺少 dedup_key 的记录补填（批量 executemany，避免 N+1）
    missing = db.execute(
        "SELECT id, job_title, company, city, salary FROM applications WHERE (dedup_key IS NULL OR dedup_key='') AND deleted_at IS NULL"
    ).fetchall()
    updates = []
    for row in missing:
        key = compute_dedup_key({"title": row[1], "company": row[2], "city": row[3], "salary": row[4]})
        if key:
            updates.append((key, row[0]))
    if updates:
        db.executemany("UPDATE applications SET dedup_key=? WHERE id=?", updates)
    db.commit()
    return {"total": total, "duplicates_found": removed, "duplicates_removed": removed}


def get_duplicate_stats() -> dict:
    """统计当前数据库中的重复数据情况。"""
    db = get_db()
    total = db.execute("SELECT COUNT(*) FROM applications WHERE deleted_at IS NULL").fetchone()[0]
    # 有 dedup_key 的去重岗位数
    unique_with_key = db.execute(
        "SELECT COUNT(DISTINCT dedup_key) FROM applications WHERE deleted_at IS NULL AND dedup_key != ''"
    ).fetchone()[0]
    # 无 dedup_key 的独立记录数
    no_key_count = db.execute(
        "SELECT COUNT(*) FROM applications WHERE deleted_at IS NULL AND (dedup_key IS NULL OR dedup_key='')"
    ).fetchone()[0]
    dup_groups = db.execute(
        """SELECT COUNT(*) FROM (
               SELECT dedup_key FROM applications WHERE deleted_at IS NULL AND dedup_key != ''
               GROUP BY dedup_key HAVING COUNT(*) > 1
           )"""
    ).fetchone()[0]
    # 去重后总岗位数 = 有key的去重数 + 无key的独立数
    total_unique = unique_with_key + no_key_count
    dup_records = total - total_unique if total > total_unique else 0
    return {
        "total_unique": total_unique,
        "total_records": total,
        "duplicates": dup_records,
        "duplicate_groups": dup_groups,
    }


def reconcile_application_stats() -> int:
    """修复数据一致性：status='applied' 但 greeting_sent_at 为空的记录。
    用 updated_at 回填 greeting_sent_at，返回修复的记录数。"""
    db = get_db()
    row = db.execute(
        """UPDATE applications SET greeting_sent_at=updated_at
           WHERE status='applied' AND greeting_sent_at IS NULL"""
    )
    db.commit()
    return row.rowcount if row else 0


# ══════════════════════════════════════
#  评分 & 真实性
# ══════════════════════════════════════


def update_application_score(app_id: int, score: int, detail: dict):
    """更新岗位评分。"""
    db = get_db()
    db.execute(
        "UPDATE applications SET score=?, score_detail=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
        (score, json.dumps(detail, ensure_ascii=False), app_id),
    )
    db.commit()


def update_application_legitimacy(app_id: int, level: str, signals: list):
    """更新岗位真实性标记。"""
    db = get_db()
    db.execute(
        "UPDATE applications SET legitimacy=?, legitimacy_signals=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
        (level, json.dumps(signals, ensure_ascii=False), app_id),
    )
    db.commit()


def get_application_for_scoring(app_id: int) -> Optional[dict]:
    """获取岗位信息用于评分（包含 deleted_at 的也能查到）。"""
    row = get_db().execute("SELECT * FROM applications WHERE id=?", (app_id,)).fetchone()
    return dict(row) if row else None


_legitimacy_cache = {"data": None, "ts": 0.0}
_LEGITIMACY_TTL = 30.0

def get_all_active_jobs_for_legitimacy() -> List[dict]:
    """获取所有活跃岗位用于真实性检测（去重后，只取必要列，30秒缓存）。"""
    import time
    now = time.time()
    if _legitimacy_cache["data"] is not None and now - _legitimacy_cache["ts"] < _LEGITIMACY_TTL:
        return _legitimacy_cache["data"]
    rows = get_db().execute(
        """SELECT a.company, a.job_title FROM applications a
           INNER JOIN (
               SELECT MAX(id) as mid FROM applications
               WHERE deleted_at IS NULL
               GROUP BY CASE WHEN dedup_key IS NULL OR dedup_key='' THEN '_row_'||id ELSE dedup_key END
           ) u ON a.id = u.mid"""
    ).fetchall()
    result = [dict(r) for r in rows]
    _legitimacy_cache["data"] = result
    _legitimacy_cache["ts"] = now
    return result


def update_application_fields(app_id: int, fields: dict):
    """通用字段更新：UPDATE applications SET k1=v1, k2=v2, ... WHERE id=?。"""
    if not fields:
        return
    db = get_db()
    sets = ", ".join(f"{k}=?" for k in fields)
    vals = list(fields.values()) + [app_id]
    db.execute(f"UPDATE applications SET {sets}, updated_at=CURRENT_TIMESTAMP WHERE id=?", vals)
    db.commit()


def update_application_hr_activity(app_id: int, hr_activity_score: int):
    """更新 HR 活跃度分数。"""
    db = get_db()
    db.execute(
        "UPDATE applications SET hr_activity_score=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
        (hr_activity_score, app_id),
    )
    db.commit()


def update_application_composite_score(app_id: int, composite_score: int):
    """更新综合评分。"""
    db = get_db()
    db.execute(
        "UPDATE applications SET composite_score=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
        (composite_score, app_id),
    )
    db.commit()


def get_auto_apply_candidates(threshold: int, hr_active_required: bool = True) -> List[dict]:
    """查询符合自动投递条件的岗位：综合分>=阈值、未被标记为可疑、未投递过。"""
    db = get_db()
    sql = """SELECT a.* FROM applications a
             WHERE a.deleted_at IS NULL
               AND a.status = 'pending'
               AND a.composite_score >= ?
               AND (a.legitimacy IS NULL OR a.legitimacy != 'suspicious')
               AND a.score IS NOT NULL AND a.score >= 30
               AND a.id NOT IN (SELECT application_id FROM auto_apply_log WHERE application_id IS NOT NULL AND result = 'success')"""
    params: list = [threshold]
    if hr_active_required:
        sql += " AND a.hr_activity_score > 0"
    sql += " ORDER BY a.composite_score DESC"
    rows = db.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def log_auto_apply(app_id: int, composite_score: int, hr_activity_score: int, result: str):
    """记录自动投递日志。"""
    db = get_db()
    db.execute(
        "INSERT INTO auto_apply_log (application_id, composite_score, hr_activity_score, result) VALUES (?,?,?,?)",
        (app_id, composite_score, hr_activity_score, result),
    )
    db.commit()


def get_auto_apply_logs(limit: int = 50) -> List[dict]:
    """获取自动投递日志。"""
    rows = get_db().execute(
        """SELECT l.*, a.job_title, a.company
           FROM auto_apply_log l
           LEFT JOIN applications a ON l.application_id = a.id
           ORDER BY l.applied_at DESC LIMIT ?""",
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]
