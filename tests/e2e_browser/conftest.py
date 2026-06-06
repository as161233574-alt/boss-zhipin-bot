"""Playwright E2E 浏览器测试 fixtures。"""
import pytest
import time
import json
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from helpers import get_api_token, BASE_URL, screenshot, SCREENSHOT_DIR


@pytest.fixture(scope="session")
def base_url() -> str:
    return BASE_URL


@pytest.fixture(scope="session")
def api_token() -> str:
    return get_api_token()


@pytest.fixture(scope="session")
def browser():
    """启动 Playwright Chromium 浏览器。"""
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"]
        )
        yield browser
        browser.close()


@pytest.fixture()
def context(browser: Browser):
    """隔离的浏览器上下文，注入 API token。"""
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    # 注入 token
    ctx.add_init_script(f"window.__API_TOKEN__ = '{get_api_token()}';")
    yield ctx
    ctx.close()


@pytest.fixture()
def page(context: BrowserContext, request):
    """带截图功能的页面。"""
    page = context.new_page()
    page.set_default_timeout(15000)
    page.set_default_navigation_timeout(30000)

    # 监听错误
    errors = []
    page.on("pageerror", lambda exc: errors.append(f"PAGE ERROR: {exc}"))
    page.on("console", lambda msg: errors.append(f"CONSOLE {msg.type}: {msg.text}") if msg.type == "error" else None)

    yield page

    if errors:
        print(f"\n[Browser Errors in {request.node.name}]:")
        for e in errors[:5]:
            print(f"  {e}")

    page.close()
