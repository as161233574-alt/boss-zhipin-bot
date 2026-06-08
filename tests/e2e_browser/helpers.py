"""Playwright E2E 浏览器测试共享工具。

提供 token 读取、API 调用、浏览器启动、截图等。
"""
import os
import json
import urllib.request
import urllib.error
from pathlib import Path

BASE_URL = "http://127.0.0.1:8010"
API_TOKEN_PATH = Path(__file__).parent.parent.parent / ".boss_profile" / ".api_token"
SCREENSHOT_DIR = Path(__file__).parent / "screenshots"
SCREENSHOT_DIR.mkdir(exist_ok=True)


def get_api_token() -> str:
    if not API_TOKEN_PATH.exists():
        raise FileNotFoundError(
            f"API token not found at {API_TOKEN_PATH}. "
            "Run the server first (python scripts/run.py) to generate it."
        )
    return API_TOKEN_PATH.read_text().strip()


def api(method: str, path: str, data: dict = None, timeout: int = 30) -> tuple:
    """API 调用封装，返回 (status_code, response_dict)。"""
    url = BASE_URL + path
    headers = {"Authorization": f"Bearer {get_api_token()}"}
    if data is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(data).encode("utf-8")
    else:
        body = None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8"))
        except Exception:
            return e.code, {"error": str(e)}
    except Exception as e:
        return 0, {"error": str(e)}


def api_get(path: str, timeout: int = 30):
    return api("GET", path, timeout=timeout)


def api_post(path: str, data: dict = None, timeout: int = 60):
    return api("POST", path, data, timeout=timeout)


def api_put(path: str, data: dict = None, timeout: int = 30):
    return api("PUT", path, data, timeout=timeout)


def api_delete(path: str, timeout: int = 30):
    return api("DELETE", path, timeout=timeout)


def screenshot(page, name: str):
    """保存截图。"""
    path = SCREENSHOT_DIR / f"{name}.png"
    page.screenshot(path=str(path), full_page=True)
    print(f"  [screenshot] {path}")
