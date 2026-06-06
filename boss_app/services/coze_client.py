"""Coze API 客户端 — 调用 Coze 平台 Bot (如 ResumeAI Pro)。"""

import time
import httpx


class CozeClient:
    """调用 Coze 平台 Bot。"""

    def __init__(self, pat_token: str, base_url: str = "https://api.coze.cn"):
        self.token = pat_token
        self.base_url = base_url.rstrip("/")
        self.client = httpx.Client(timeout=120)

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    def chat(self, bot_id: str, user_id: str, message: str) -> str:
        """发起对话并轮询结果。"""
        # 1. 发起对话
        resp = self.client.post(
            f"{self.base_url}/v3/chat",
            headers=self._headers(),
            json={
                "bot_id": bot_id,
                "user_id": user_id,
                "stream": False,
                "auto_save_history": True,
                "additional_messages": [
                    {"role": "user", "content": message, "content_type": "text"}
                ],
            },
        )
        resp.raise_for_status()
        data = resp.json().get("data", {})
        chat_id = data.get("id", "")
        conversation_id = data.get("conversation_id", "")

        if not chat_id:
            raise ValueError(f"Coze API 返回异常: {resp.text[:200]}")

        # 2. 轮询等待完成
        for _ in range(60):  # 最多等 120 秒
            status_resp = self.client.get(
                f"{self.base_url}/v3/chat/retrieve",
                params={"chat_id": chat_id, "conversation_id": conversation_id},
                headers=self._headers(),
            )
            status_data = status_resp.json().get("data", {})
            status = status_data.get("status", "")
            if status == "completed":
                break
            if status == "failed":
                raise RuntimeError(f"Coze 对话失败: {status_data.get('last_error', {})}")
            time.sleep(2)
        else:
            raise TimeoutError("Coze 对话超时")

        # 3. 获取消息
        msgs_resp = self.client.get(
            f"{self.base_url}/v3/chat/message/list",
            params={"chat_id": chat_id, "conversation_id": conversation_id},
            headers=self._headers(),
        )
        messages = msgs_resp.json().get("data", [])

        for msg in messages:
            if msg.get("type") == "answer":
                return msg.get("content", "")
        return ""

    def optimize_resume(self, resume_text: str, jd_text: str) -> dict:
        """调用 ResumeAI Pro 优化简历。"""
        prompt = (
            "请根据以下岗位要求优化我的简历，输出优化后的简历内容、匹配分析和面试准备建议。\n\n"
            f"【简历】\n{resume_text}\n\n【岗位要求】\n{jd_text}"
        )
        from ..models.settings import get_setting
        bot_id = get_setting("coze_resume_bot_id", "")
        result = self.chat(bot_id=bot_id, user_id="boss_radar_user", message=prompt)
        return {"optimized_resume": result}
