"""评分 Agent — 包装 scorer 的评分和合法性检测。"""

import asyncio
from concurrent.futures import ThreadPoolExecutor

from .base import BaseAgent, AgentMessage
from ..services.scorer import score_job_combined, check_legitimacy, score_hr_activity, compute_composite_score
from ..models.application import get_application_for_scoring, update_application_score
from ..models.settings import get_setting
from ..core.database import get_active_resume

_score_pool = ThreadPoolExecutor(max_workers=3)


def _get_resume_summary() -> str:
    """获取当前激活简历的摘要，如果没有则回退到旧的 settings。"""
    active = get_active_resume()
    if active and active.get("summary"):
        return active["summary"]
    return get_setting("resume_summary", "")


class ScorerAgent(BaseAgent):
    name = "scorer"

    async def handle(self, msg: AgentMessage) -> None:
        action = msg.payload.get("action")
        if action == "batch_score":
            await self._handle_batch_score(msg)
        elif action == "score_one":
            await self._handle_score_one(msg)

    async def _handle_batch_score(self, msg: AgentMessage) -> None:
        job_ids = msg.payload.get("job_ids", [])
        if not job_ids:
            await self.send(msg.source, "result", {
                "scored": 0, "correlation_id": msg.correlation_id,
            }, correlation_id=msg.correlation_id)
            return

        resume = _get_resume_summary()
        loop = asyncio.get_event_loop()
        agent_cfg = self.get_llm_config()

        scored = 0
        qualified = []

        def score_one(aid):
            job = get_application_for_scoring(aid)
            if not job:
                return None
            title = job.get("job_title", "")
            company = job.get("company", "")
            desc = job.get("description", "") or ""
            salary = job.get("salary", "")
            hr_name = job.get("hr_name", "")
            hr_activity = job.get("hr_activity", "")

            result = score_job_combined(title, company, desc[:1000], salary, hr_name, resume, cfg=agent_cfg)
            cv_score = result.get("cv_score", 0)
            quality_score = result.get("quality_score", 0)
            activity_score = score_hr_activity(hr_activity)
            composite = compute_composite_score(cv_score, quality_score, activity_score)

            update_application_score(aid, cv_score, quality_score, activity_score, composite, result)
            return {"id": aid, "composite": composite, **result}

        futures = [_score_pool.submit(score_one, aid) for aid in job_ids]
        for f in futures:
            r = await loop.run_in_executor(None, f.result)
            if r:
                scored += 1
                min_score = int(get_setting("auto_apply_min_score", "60") or "60")
                if r.get("composite", 0) >= min_score:
                    qualified.append(r["id"])

        result = {
            "scored": scored, "total": len(job_ids),
            "qualified_ids": qualified,
            "correlation_id": msg.correlation_id,
        }
        await self.send(msg.source, "result", result, correlation_id=msg.correlation_id)
        await self.send("*", "event", {"event": "batch_score_complete", **result})

    async def _handle_score_one(self, msg: AgentMessage) -> None:
        aid = msg.payload.get("job_id")
        resume = _get_resume_summary()
        job = get_application_for_scoring(aid)
        if not job:
            return
        loop = asyncio.get_event_loop()
        agent_cfg = self.get_llm_config()
        r = await loop.run_in_executor(None, lambda: score_job_combined(
            job.get("job_title", ""), job.get("company", ""),
            (job.get("description", "") or "")[:1000],
            job.get("salary", ""), job.get("hr_name", ""), resume, cfg=agent_cfg,
        ))
        await self.send(msg.source, "result", {
            "job_id": aid, "result": r, "correlation_id": msg.correlation_id,
        }, correlation_id=msg.correlation_id)
