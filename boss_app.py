"""向后兼容入口 — 实际逻辑已迁移到 boss_app/ 包"""
from boss_app.main import app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8010)
