"""
数据库连接与初始化模块。
从 boss_state.py 提取的数据库基础设施。
"""

import sqlite3
import threading
from pathlib import Path
from typing import List, Optional

DB_PATH = Path(__file__).resolve().parent.parent.parent / ".boss_profile" / "boss_state.db"

_local = threading.local()


def get_db() -> sqlite3.Connection:
    """获取线程本地数据库连接。"""
    if not hasattr(_local, "conn") or _local.conn is None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _local.conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        _local.conn.row_factory = sqlite3.Row
        _local.conn.execute("PRAGMA journal_mode=WAL")
        _local.conn.execute("PRAGMA foreign_keys=ON")
    return _local.conn


def init_db():
    """初始化数据库表结构。"""
    db = get_db()
    db.executescript("""
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_title TEXT NOT NULL,
            company TEXT,
            salary TEXT,
            job_url TEXT UNIQUE NOT NULL,
            city TEXT,
            experience TEXT,
            education TEXT,
            hr_name TEXT,
            hr_title TEXT,
            description TEXT,
            status TEXT DEFAULT 'pending',
            greeting_text TEXT,
            greeting_sent_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id INTEGER REFERENCES applications(id),
            hr_name TEXT NOT NULL,
            hr_company TEXT,
            job_title TEXT,
            last_message_text TEXT,
            last_message_from TEXT,
            last_message_at TIMESTAMP,
            unread_count INTEGER DEFAULT 0,
            status TEXT DEFAULT 'active',
            auto_reply_enabled INTEGER DEFAULT 1,
            interest_level TEXT,
            hr_wechat TEXT,
            wechat_shared_at TIMESTAMP,
            resume_sent INTEGER DEFAULT 0,
            phone_shared INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL REFERENCES conversations(id),
            sender TEXT NOT NULL,
            content TEXT NOT NULL,
            delivery_status TEXT,
            ai_generated INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS daily_stats (
            date TEXT PRIMARY KEY,
            applications_sent INTEGER DEFAULT 0,
            messages_sent INTEGER DEFAULT 0,
            messages_received INTEGER DEFAULT 0,
            auto_replies_sent INTEGER DEFAULT 0
        );
    """)
    # ALTER TABLE 语句用于兼容旧数据库
    try:
        db.execute("ALTER TABLE messages ADD COLUMN delivery_status TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        db.execute("ALTER TABLE conversations ADD COLUMN interest_level TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        db.execute("ALTER TABLE conversations ADD COLUMN hr_wechat TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        db.execute("ALTER TABLE conversations ADD COLUMN wechat_shared_at TIMESTAMP")
    except sqlite3.OperationalError:
        pass
    try:
        db.execute("ALTER TABLE conversations ADD COLUMN resume_sent INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    try:
        db.execute("ALTER TABLE conversations ADD COLUMN phone_shared INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    # 候选池表
    db.executescript("""
        CREATE TABLE IF NOT EXISTS shortlists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_url TEXT UNIQUE NOT NULL,
            job_title TEXT NOT NULL,
            company TEXT,
            salary TEXT,
            city TEXT,
            note TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS delete_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL,
            count INTEGER DEFAULT 0,
            job_ids TEXT,
            detail TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    # 软删除字段（兼容旧数据库）
    try:
        db.execute("ALTER TABLE applications ADD COLUMN deleted_at TIMESTAMP")
    except sqlite3.OperationalError:
        pass
    try:
        db.execute("ALTER TABLE applications ADD COLUMN dedup_key TEXT")
    except sqlite3.OperationalError:
        pass
    db.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_app_dedup_key "
        "ON applications(dedup_key) WHERE dedup_key IS NOT NULL AND dedup_key != ''"
    )
    try:
        db.execute("ALTER TABLE conversations ADD COLUMN emotion TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        db.execute("ALTER TABLE conversations ADD COLUMN dialogue_stage TEXT")
    except sqlite3.OperationalError:
        pass
    # 性能索引
    db.execute("CREATE INDEX IF NOT EXISTS idx_conv_app_id ON conversations(application_id)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_msg_conv_id ON messages(conversation_id)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_app_status ON applications(status, deleted_at)")
    # 默认设置
    defaults = {
        "greeting_template": "您好！看到贵司在招{job_title}，很感兴趣，希望有机会详细了解一下。",
        "greeting_enabled": "true",
        "ai_reply_style": "professional",
        "daily_apply_limit": "15",
        "auto_reply_enabled": "false",
        "min_reply_delay_sec": "15",
        "max_reply_delay_sec": "20",
        "batch_delay_min_sec": "30",
        "batch_delay_max_sec": "90",
        "resume_summary": "",
        "wechat_id": "",
        "search_keywords": "AI Agent,大模型开发,AI产品经理,RAG开发,大模型应用",
        "default_city": "成都",
    }
    for k, v in defaults.items():
        db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))
    db.commit()


def _row_to_dict(row) -> Optional[dict]:
    """将 sqlite3.Row 转换为字典。"""
    return dict(row) if row else None


def _rows_to_list(rows) -> List[dict]:
    """将 sqlite3.Row 列表转换为字典列表。"""
    return [dict(r) for r in rows]
