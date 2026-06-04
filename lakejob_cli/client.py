"""HTTP client for lakejob FastAPI backend."""

import os
from pathlib import Path

import httpx

BASE_URL = os.environ.get("LAKEJOB_API", "http://127.0.0.1:8010")


def _load_token() -> str:
    """Token resolution order: env LAKEJOB_TOKEN -> .boss_profile/.api_token -> ''."""
    env = os.environ.get("LAKEJOB_TOKEN", "").strip()
    if env:
        return env
    # 项目根 .boss_profile/.api_token（CLI 与 server 共用约定）
    here = Path(__file__).resolve()
    for parent in [here.parent.parent, *here.parents]:
        candidate = parent / ".boss_profile" / ".api_token"
        if candidate.exists():
            try:
                return candidate.read_text(encoding="utf-8").strip()
            except OSError:
                pass
    # cwd 兜底
    cwd_candidate = Path.cwd() / ".boss_profile" / ".api_token"
    if cwd_candidate.exists():
        try:
            return cwd_candidate.read_text(encoding="utf-8").strip()
        except OSError:
            pass
    return ""


_TOKEN = _load_token()


def _headers() -> dict:
    return {"Authorization": f"Bearer {_TOKEN}"} if _TOKEN else {}


def _post(path: str, json=None, timeout=120):
    try:
        resp = httpx.post(
            f"{BASE_URL}{path}", json=json, timeout=timeout, headers=_headers()
        )
    except httpx.ConnectError:
        resp = httpx.Response(503, text="Cannot connect to lakejob server. Run `lakejob server --start` first.")
    return resp


def _get(path: str, timeout=30):
    try:
        resp = httpx.get(f"{BASE_URL}{path}", timeout=timeout, headers=_headers())
    except httpx.ConnectError:
        resp = httpx.Response(503, text="Cannot connect to lakejob server. Run `lakejob server --start` first.")
    return resp


def search(keyword: str, city: str = "", limit: int = 60):
    return _post("/api/jobs/search", {"keyword": keyword, "city": city or "", "limit": limit})


def status():
    return _get("/api/status")


def stats():
    return _get("/api/stats")


def jobs(status_filter=None, limit=50):
    q = f"?limit={limit}"
    if status_filter:
        q += f"&status={status_filter}"
    return _get(f"/api/jobs{q}")


def apply_one(job_url: str):
    return _post("/api/jobs/apply", {"job_url": job_url})


def apply_batch(job_urls: list):
    return _post("/api/jobs/apply-batch", {"job_urls": job_urls})


def scan():
    return _post("/api/jobs/scan", timeout=120)


def scan_and_apply():
    return _post("/api/jobs/scan-and-apply", timeout=300)


def conversations():
    return _get("/api/conversations")


def chat_messages(conv_id: int):
    return _get(f"/api/conversations/{conv_id}/messages")


def send_message(conv_id: int, content: str):
    return _post(f"/api/conversations/{conv_id}/send", {"content": content})


def doctor():
    return _get("/api/doctor")


def relogin():
    return _post("/api/system/relogin")


def analyze(job_url: str, title: str = "", company: str = "", desc: str = ""):
    return _post("/api/jobs/analyze", {"job_url": job_url, "job_title": title, "company": company, "description": desc})


def get_shortlists():
    return _get("/api/shortlists")


def add_shortlist(job_url: str, title: str = "", company: str = "", salary: str = "", city: str = ""):
    return _post(
        "/api/shortlists", {"job_url": job_url, "title": title, "company": company, "salary": salary, "city": city}
    )


def remove_shortlist(sid: int):
    resp = httpx.delete(f"{BASE_URL}/api/shortlists/{sid}", timeout=30, headers=_headers())
    return resp
