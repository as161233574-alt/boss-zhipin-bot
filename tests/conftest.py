"""测试配置：提供临时数据库 fixture。"""
import os
import sys
import sqlite3
import tempfile
import pytest

# 确保项目根目录在 sys.path 中
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PROJECT_ROOT)
sys.path.insert(0, os.path.join(_PROJECT_ROOT, "interview"))


@pytest.fixture()
def test_db(tmp_path, monkeypatch):
    """每个测试使用独立的临时数据库（仅显式请求的测试才启用）。"""
    db_path = tmp_path / "test_boss.db"
    monkeypatch.setattr("boss_app.core.database.DB_PATH", db_path)

    # 重置线程本地连接缓存
    from boss_app.core.database import init_db, _local
    if hasattr(_local, "conn") and _local.conn:
        try:
            _local.conn.close()
        except Exception:
            pass
        _local.conn = None
    init_db()

    yield db_path

    # 清理
    if hasattr(_local, "conn") and _local.conn:
        try:
            _local.conn.close()
        except Exception:
            pass
        _local.conn = None
