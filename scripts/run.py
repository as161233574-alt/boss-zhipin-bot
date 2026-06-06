"""启动入口"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import uvicorn

if __name__ == "__main__":
    # reload=False 因为 Windows + reload 会触发 uvicorn 用 SelectorEventLoop，
    # 而 Python 3.13 的 SelectorEventLoop 不支持 create_subprocess_exec，
    # 导致 Playwright 无法启动 Firefox 浏览器
    uvicorn.run("boss_app.main:app", host="127.0.0.1", port=8010, reload=False)
