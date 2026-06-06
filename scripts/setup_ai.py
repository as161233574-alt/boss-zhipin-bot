#!/usr/bin/env python3
"""一键配置 AI 模型（写入 SQLite settings 表）。

API 密钥从环境变量 AI_API_KEY 读取，不再硬编码。
用法：AI_API_KEY=your-key python setup_ai.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from boss_app.models.settings import set_setting

CONFIG = {
    "ai_api_key": os.environ.get("AI_API_KEY", ""),
    "ai_base_url": os.environ.get("AI_BASE_URL", "https://token-plan-cn.xiaomimimo.com/v1"),
    "ai_model": os.environ.get("AI_MODEL", "mimo-v2.5-pro"),
}

def main():
    if not CONFIG["ai_api_key"]:
        print("错误：未设置 AI_API_KEY 环境变量")
        print("用法：AI_API_KEY=your-key python setup_ai.py")
        return
    for key, value in CONFIG.items():
        set_setting(key, value)
        print(f"  {key} = {value[:10]}..." if "key" in key else f"  {key} = {value}")
    print("\nDone. AI configured.")

if __name__ == "__main__":
    main()
