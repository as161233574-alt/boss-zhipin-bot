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
        _local.conn.execute("PRAGMA busy_timeout=5000")
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
    # ALTER TABLE 语句用于兼容旧数据库（新增列）
    _migrations = [
        ("messages", "delivery_status", "TEXT"),
        ("conversations", "interest_level", "TEXT"),
        ("conversations", "hr_wechat", "TEXT"),
        ("conversations", "wechat_shared_at", "TIMESTAMP"),
        ("conversations", "resume_sent", "INTEGER DEFAULT 0"),
        ("conversations", "phone_shared", "INTEGER DEFAULT 0"),
        ("applications", "deleted_at", "TIMESTAMP"),
        ("applications", "dedup_key", "TEXT"),
        ("conversations", "emotion", "TEXT"),
        ("conversations", "dialogue_stage", "TEXT"),
        ("applications", "score", "INTEGER"),
        ("applications", "score_detail", "TEXT"),
        ("applications", "follow_up_at", "TIMESTAMP"),
        ("applications", "follow_up_count", "INTEGER DEFAULT 0"),
        ("conversations", "last_follow_up_at", "TIMESTAMP"),
        ("applications", "legitimacy", "TEXT DEFAULT 'unknown'"),
        ("applications", "legitimacy_signals", "TEXT"),
        ("applications", "hr_activity", "TEXT"),
        ("applications", "hr_activity_score", "INTEGER DEFAULT 0"),
        ("applications", "composite_score", "INTEGER"),
    ]
    for table, column, dtype in _migrations:
        try:
            db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {dtype}")
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
    db.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_app_dedup_key "
        "ON applications(dedup_key) WHERE dedup_key IS NOT NULL AND dedup_key != ''"
    )
    # 性能索引
    db.execute("CREATE INDEX IF NOT EXISTS idx_conv_app_id ON conversations(application_id)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_msg_conv_id ON messages(conversation_id)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_app_status ON applications(status, deleted_at)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_app_score ON applications(score) WHERE score IS NOT NULL")
    db.execute("CREATE INDEX IF NOT EXISTS idx_app_composite ON applications(composite_score) WHERE composite_score IS NOT NULL")
    db.execute("CREATE INDEX IF NOT EXISTS idx_app_deleted_at ON applications(deleted_at)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_conv_hr_name ON conversations(hr_name)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_msg_ai_created ON messages(ai_generated, created_at)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_conv_status_updated ON conversations(status, updated_at)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_msg_conv_sender_content ON messages(conversation_id, sender, content)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_app_follow_up ON applications(follow_up_at) WHERE follow_up_at IS NOT NULL")
    db.execute("CREATE INDEX IF NOT EXISTS idx_conv_hr_wechat ON conversations(hr_wechat) WHERE hr_wechat IS NOT NULL AND hr_wechat != ''")
    # 自动投递日志
    db.executescript("""
        CREATE TABLE IF NOT EXISTS auto_apply_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id INTEGER,
            composite_score INTEGER,
            hr_activity_score INTEGER,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            result TEXT
        );
    """)
    db.execute("CREATE INDEX IF NOT EXISTS idx_auto_apply_app_id ON auto_apply_log(application_id, result)")
    # Agent Profile 配置表
    db.executescript("""
        CREATE TABLE IF NOT EXISTS agent_profiles (
            name TEXT PRIMARY KEY,
            profile_json TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    # 简历优化历史
    db.executescript("""
        CREATE TABLE IF NOT EXISTS resume_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL,
            resume_hash TEXT NOT NULL,
            jd_hash TEXT,
            input_summary TEXT,
            result_json TEXT NOT NULL,
            duration_ms INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_resume_hist_action ON resume_history(action, created_at);
    """)
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
        "auto_apply_enabled": "false",
        "auto_apply_threshold": "80",
        "auto_apply_hr_active_required": "true",
        "filter_inactive_hr": "true",  # 过滤3天以上不活跃的HR岗位
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


# ── Agent Profile CRUD ──

def get_agent_profile(name: str) -> Optional[dict]:
    """从数据库读取 Agent Profile（返回 dict，None 表示未自定义）。"""
    db = get_db()
    row = db.execute("SELECT profile_json FROM agent_profiles WHERE name=?", (name,)).fetchone()
    if row:
        import json
        return json.loads(row["profile_json"])
    return None


def save_agent_profile(name: str, profile_dict: dict) -> None:
    """保存 Agent Profile 到数据库。"""
    import json
    db = get_db()
    db.execute(
        "INSERT OR REPLACE INTO agent_profiles (name, profile_json, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
        (name, json.dumps(profile_dict, ensure_ascii=False)),
    )
    db.commit()


def delete_agent_profile(name: str) -> None:
    """删除数据库中的 Agent Profile（恢复默认时使用）。"""
    db = get_db()
    db.execute("DELETE FROM agent_profiles WHERE name=?", (name,))
    db.commit()


def get_all_agent_profiles() -> dict:
    """读取所有自定义 Agent Profile（返回 {name: dict}）。"""
    import json
    db = get_db()
    rows = db.execute("SELECT name, profile_json FROM agent_profiles").fetchall()
    return {r["name"]: json.loads(r["profile_json"]) for r in rows}
