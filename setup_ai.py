#!/usr/bin/env python3
"""一键配置 AI 模型（写入 SQLite settings 表）。"""

from boss_state import set_setting

CONFIG = {
    "ai_api_key": "tp-c0b1e14o8mtfjlcq8709d2ykdfdq9qgi3a084yputhgf9bwo",
    "ai_base_url": "https://token-plan-cn.xiaomimimo.com/v1",
    "ai_model": "mimo-v2.5-pro",
}

def main():
    for key, value in CONFIG.items():
        set_setting(key, value)
        print(f"  {key} = {value[:10]}..." if "key" in key else f"  {key} = {value}")
    print("\nDone. AI configured: MiMo V2.5 Pro (Anthropic API)")

if __name__ == "__main__":
    main()
