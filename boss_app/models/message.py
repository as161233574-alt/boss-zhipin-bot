"""
消息数据层。
从 boss_state.py 提取的消息相关函数。
"""

from typing import List, Optional

from ..core.database import get_db, _row_to_dict, _rows_to_list


# ══════════════════════════════════════
#  Messages
# ══════════════════════════════════════


def add_message(
    conversation_id: int, sender: str, content: str, ai_generated: bool = False, delivery_status: str = ""
) -> int:
    db = get_db()
    cur = db.execute(
        "INSERT INTO messages (conversation_id, sender, content, delivery_status, ai_generated) VALUES (?, ?, ?, ?, ?)",
        (conversation_id, sender, content, delivery_status, 1 if ai_generated else 0),
    )
    db.commit()
    return cur.lastrowid


def get_messages(conversation_id: int, limit: int = 50) -> List[dict]:
    return _rows_to_list(
        get_db()
        .execute(
            "SELECT * FROM messages WHERE conversation_id=? ORDER BY created_at ASC, id ASC LIMIT ?",
            (conversation_id, limit),
        )
        .fetchall()
    )


def get_recent_messages(conversation_id: int, limit: int = 5) -> List[dict]:
    return _rows_to_list(
        get_db()
        .execute(
            "SELECT * FROM messages WHERE conversation_id=? ORDER BY created_at DESC, id DESC LIMIT ?",
            (conversation_id, limit),
        )
        .fetchall()
    )


def replace_conversation_messages(conversation_id: int, messages: List[dict]):
    """用 BOSS 当前消息历史覆盖本地缓存，避免 Web 端展示过期或错会话内容。"""
    db = get_db()
    old_ai = {
        r["content"]
        for r in db.execute(
            "SELECT content FROM messages WHERE conversation_id=? AND ai_generated=1",
            (conversation_id,),
        ).fetchall()
    }
    # 收集要插入的数据，先构建再批量操作，避免 DELETE 后 INSERT 失败导致数据丢失
    rows = []
    for msg in messages:
        sender = msg.get("sender", "hr")
        content = (msg.get("content") or "").strip()
        delivery_status = (msg.get("status") or msg.get("delivery_status") or "").strip()
        sent_at = (msg.get("time") or "").strip()
        if not content:
            continue
        ai_generated = 1 if sender == "me" and content in old_ai else 0
        rows.append((conversation_id, sender, content, delivery_status, ai_generated, sent_at))

    try:
        db.execute("DELETE FROM messages WHERE conversation_id=?", (conversation_id,))
        db.executemany(
            "INSERT INTO messages (conversation_id, sender, content, delivery_status, ai_generated, sent_at) VALUES (?, ?, ?, ?, ?, ?)",
            rows,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise


def get_last_hr_message(conversation_id: int) -> Optional[dict]:
    return _row_to_dict(
        get_db()
        .execute(
            "SELECT * FROM messages WHERE conversation_id=? AND sender='hr' ORDER BY created_at DESC LIMIT 1",
            (conversation_id,),
        )
        .fetchone()
    )


def message_exists(conversation_id: int, content: str, sender: str) -> bool:
    row = (
        get_db()
        .execute(
            "SELECT id FROM messages WHERE conversation_id=? AND content=? AND sender=? ORDER BY created_at DESC LIMIT 1",
            (conversation_id, content, sender),
        )
        .fetchone()
    )
    return row is not None
