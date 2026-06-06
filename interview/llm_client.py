"""
面试问答Agent - LLM客户端模块
- Embedding: Ollama nomic-embed-text
- 出题: Ollama qwen2.5:14b
- 批改: DeepSeek API
"""

import httpx
import numpy as np
import json
import re
import os
import sys
import time
from typing import List, Optional

# 确保 boss_app 可导入
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Ollama配置
OLLAMA_BASE = "http://localhost:11434"
EMBED_MODEL = "nomic-embed-text"
LLM_MODEL = "qwen2.5:14b"


# ── 连接池（复用 TCP 连接，避免每次调用都握手）──
_llm_client: Optional[httpx.Client] = None


def _get_client() -> httpx.Client:
    global _llm_client
    if _llm_client is None or _llm_client.is_closed:
        _llm_client = httpx.Client(
            timeout=180,
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        )
    return _llm_client


# ── AI 配置缓存（60 秒 TTL，避免每次调用都读 SQLite）──
_config_cache = {"data": None, "ts": 0.0}
_CONFIG_TTL = 60.0


# AI配置（从SQLite读取，带缓存）
def _load_ai_config():
    now = time.time()
    if _config_cache["data"] is not None and now - _config_cache["ts"] < _CONFIG_TTL:
        return _config_cache["data"]

    cfg = {
        "api_key": "",
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-chat",
    }
    try:
        from boss_app.models.settings import get_setting
        from boss_app.core.database import get_db

        get_db()
        key = get_setting("ai_api_key")
        if key:
            cfg["api_key"] = key
        url = get_setting("ai_base_url")
        if url:
            cfg["base_url"] = url
        model = get_setting("ai_model")
        if model:
            cfg["model"] = model
    except Exception:
        pass

    _config_cache["data"] = cfg
    _config_cache["ts"] = now
    return cfg


def get_embedding(text: str) -> List[float]:
    """获取文本的embedding向量（带连接池 + 重试）"""
    for attempt in range(3):
        try:
            resp = _get_client().post(
                f"{OLLAMA_BASE}/api/embed",
                json={"model": EMBED_MODEL, "input": text},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["embeddings"][0]
        except (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError):
            if attempt < 2:
                time.sleep(1)
                continue
            raise


def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """计算余弦相似度"""
    a = np.array(vec_a, dtype=np.float32)
    b = np.array(vec_b, dtype=np.float32)
    if np.linalg.norm(a) == 0 or np.linalg.norm(b) == 0:
        return 0.0
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def llm_chat_ollama(messages: list, system_prompt: Optional[str] = None, temperature: float = 0.7) -> str:
    """调用Ollama大模型（出题用，带连接池 + 重试）"""
    if system_prompt:
        messages = [{"role": "system", "content": system_prompt}] + messages

    payload = {
        "model": LLM_MODEL,
        "messages": messages,
        "temperature": temperature,
        "stream": False,
    }

    for attempt in range(3):
        try:
            resp = _get_client().post(f"{OLLAMA_BASE}/api/chat", json=payload, timeout=120)
            resp.raise_for_status()
            data = resp.json()
            return data["message"]["content"]
        except (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError):
            if attempt < 2:
                time.sleep(1)
                continue
            raise


def _is_anthropic_api(base_url: str) -> bool:
    """判断是否为 Anthropic 兼容 API（路径含 /anthropic）。"""
    return "/anthropic" in base_url


def _call_anthropic(cfg: dict, messages: list, system_prompt: Optional[str], temperature: float) -> str:
    """调用 Anthropic Messages API 格式（带重试）。"""
    # Anthropic 格式：system 单独传，messages 不能有 system role
    system_text = system_prompt or ""
    clean_messages = [m for m in messages if m.get("role") != "system"]

    payload = {
        "model": cfg["model"],
        "messages": clean_messages,
        "max_tokens": 8192,
        "temperature": temperature,
    }
    if system_text:
        payload["system"] = system_text

    client = _get_client()
    for attempt in range(3):
        try:
            resp = client.post(
                f"{cfg['base_url']}/v1/messages",
                json=payload,
                headers={
                    "x-api-key": cfg["api_key"],
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
            )
            if resp.status_code == 429 or resp.status_code >= 500:
                time.sleep(min(2 ** attempt, 8))
                continue
            resp.raise_for_status()
            data = resp.json()
            content = data.get("content", [])
            if content and isinstance(content, list):
                return content[0].get("text", "")
            return data.get("completion", "")
        except (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError):
            if attempt < 2:
                time.sleep(min(2 ** attempt, 8))
                continue
            raise


def _call_openai_compat(cfg: dict, messages: list, temperature: float) -> str:
    """调用 OpenAI 兼容 API 格式（带重试）。"""
    payload = {
        "model": cfg["model"],
        "messages": messages,
        "temperature": temperature,
        "stream": False,
    }

    client = _get_client()
    for attempt in range(3):
        try:
            resp = client.post(
                f"{cfg['base_url']}/chat/completions",
                json=payload,
                headers={
                    "Authorization": f"Bearer {cfg['api_key']}",
                    "Content-Type": "application/json",
                },
            )
            if resp.status_code == 429 or resp.status_code >= 500:
                time.sleep(min(2 ** attempt, 8))
                continue
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError):
            if attempt < 2:
                time.sleep(min(2 ** attempt, 8))
                continue
            raise


def llm_chat_deepseek(messages: list, system_prompt: Optional[str] = None, temperature: float = 0.3) -> str:
    """调用AI API（懒加载配置，每次从SQLite读取）。自动识别 Anthropic / OpenAI 兼容格式。"""
    cfg = _load_ai_config()
    if not cfg["api_key"]:
        raise RuntimeError("AI API Key未配置，请在设置页配置")

    if system_prompt:
        messages = [{"role": "system", "content": system_prompt}] + messages

    if _is_anthropic_api(cfg["base_url"]):
        return _call_anthropic(cfg, messages, system_prompt, temperature)
    else:
        return _call_openai_compat(cfg, messages, temperature)


def llm_call_with_config(cfg: dict, messages: list, system_prompt: Optional[str] = None, temperature: float = 0.3) -> str:
    """使用指定配置调用 LLM（Agent Profile 专用）。不从 SQLite 读取，直接使用传入的 cfg。"""
    if not cfg.get("api_key"):
        raise RuntimeError("AI API Key未配置")

    if system_prompt:
        messages = [{"role": "system", "content": system_prompt}] + messages

    if _is_anthropic_api(cfg.get("base_url", "")):
        return _call_anthropic(cfg, messages, system_prompt, temperature)
    else:
        return _call_openai_compat(cfg, messages, temperature)


def parse_json_from_llm(text: str) -> Optional[dict]:
    """从LLM返回文本中提取JSON"""
    json_match = re.search(r"\{.*\}", text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass
    return None
