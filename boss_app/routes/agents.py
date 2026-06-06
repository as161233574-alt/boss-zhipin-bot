"""Agent 管理 API 路由。"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, List

router = APIRouter(prefix="/api/agents", tags=["agents"])


def _get_orchestrator():
    from ..agents import orchestrator
    return orchestrator


def _get_resume_agent():
    orch = _get_orchestrator()
    agent = orch.agents.get("resume")
    if not agent:
        raise HTTPException(404, "ResumeAgent 不存在")
    return agent


# ── Agent 管理 ──

@router.get("/status")
async def agent_status():
    orch = _get_orchestrator()
    agents_status = []
    for a in orch.agents.values():
        s = a.get_status()
        s["profile"] = {
            "display_name": a.profile.display_name,
            "model": a.profile.model or "(全局默认)",
            "temperature": a.profile.temperature,
            "enabled": a.profile.enabled,
        }
        agents_status.append(s)
    return {"agents": agents_status, "started": orch._started}


@router.get("/messages")
async def agent_messages(limit: int = Query(default=50, ge=1, le=500)):
    orch = _get_orchestrator()
    return {"messages": orch.get_messages(limit)}


@router.post("/{name}/start")
async def start_agent(name: str):
    orch = _get_orchestrator()
    agent = orch.agents.get(name)
    if not agent:
        raise HTTPException(404, f"Agent '{name}' 不存在")
    await agent.start()
    return {"status": "started", "agent": name}


@router.post("/{name}/stop")
async def stop_agent(name: str):
    orch = _get_orchestrator()
    agent = orch.agents.get(name)
    if not agent:
        raise HTTPException(404, f"Agent '{name}' 不存在")
    await agent.stop()
    return {"status": "stopped", "agent": name}


@router.post("/start-all")
async def start_all():
    orch = _get_orchestrator()
    await orch.start_all()
    return {"status": "all_started"}


@router.post("/stop-all")
async def stop_all():
    orch = _get_orchestrator()
    await orch.stop_all()
    return {"status": "all_stopped"}


# ── 流水线 ──

class PipelineRequest(BaseModel):
    keyword: str
    city: str = "全国"
    city_code: str = "100010000"


@router.post("/pipeline")
async def run_pipeline(req: PipelineRequest):
    orch = _get_orchestrator()
    result = await orch.run_pipeline(req.keyword, req.city, req.city_code)
    return result


# ── 简历 Agent API ──

class ResumeRequest(BaseModel):
    resume_text: str = Field(..., max_length=10000)
    jd_text: str = Field("", max_length=5000)


class OptimizeRequest(BaseModel):
    resume_text: str = Field(..., max_length=10000)
    jd_text: str = Field(..., max_length=5000)


class CoverLetterRequest(BaseModel):
    resume_text: str = Field(..., max_length=10000)
    jd_text: str = Field(..., max_length=5000)
    company: str = Field("", max_length=50)


class CompareJDsRequest(BaseModel):
    resume_text: str = Field(..., max_length=10000)
    jds: List[dict] = Field(..., min_length=2, max_length=5)


class ImproveSectionRequest(BaseModel):
    resume_text: str = Field(..., max_length=10000)
    section: str = Field(..., max_length=20)
    jd_text: str = Field("", max_length=5000)


# ── 简历历史 & 统计 ──

@router.get("/resume/history")
async def resume_history(action: Optional[str] = None, limit: int = Query(default=20, ge=1, le=200)):
    from ..core.database import get_db
    db = get_db()
    if action:
        rows = db.execute(
            "SELECT id, action, resume_hash, jd_hash, input_summary, duration_ms, created_at "
            "FROM resume_history WHERE action=? ORDER BY created_at DESC LIMIT ?",
            (action, limit),
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT id, action, resume_hash, jd_hash, input_summary, duration_ms, created_at "
            "FROM resume_history ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return {"history": [dict(r) for r in rows]}


@router.get("/resume/stats")
async def resume_stats():
    agent = _get_resume_agent()
    agent_stats = {k: dict(v) for k, v in agent._action_stats.items()}
    # 从数据库补充历史统计
    from ..core.database import get_db
    db = get_db()
    db_stats = {}
    try:
        rows = db.execute(
            "SELECT action, COUNT(*) as cnt, AVG(duration_ms) as avg_ms "
            "FROM resume_history GROUP BY action"
        ).fetchall()
        for r in rows:
            db_stats[r["action"]] = {"total_count": r["cnt"], "avg_ms": round(r["avg_ms"])}
    except Exception:
        pass
    return {"runtime_stats": agent_stats, "db_stats": db_stats, "cache_size": len(agent._cache)}


class ParseRequest(BaseModel):
    content: str = Field(..., description="Base64 encoded file content")
    filename: str = Field("resume.pdf", max_length=100)


@router.post("/resume/parse")
async def resume_parse(req: ParseRequest):
    result = await _get_resume_agent().execute({
        "action": "parse", "content": req.content, "filename": req.filename,
    })
    return result


@router.post("/resume/optimize")
async def resume_optimize(req: OptimizeRequest):
    result = await _get_resume_agent().execute({
        "action": "optimize", "resume_text": req.resume_text, "jd_text": req.jd_text,
    })
    return result


@router.post("/resume/analyze")
async def resume_analyze(req: OptimizeRequest):
    result = await _get_resume_agent().execute({
        "action": "analyze_match", "resume_text": req.resume_text, "jd_text": req.jd_text,
    })
    return result


@router.post("/resume/cover-letter")
async def resume_cover_letter(req: CoverLetterRequest):
    result = await _get_resume_agent().execute({
        "action": "cover_letter",
        "resume_text": req.resume_text, "jd_text": req.jd_text, "company": req.company,
    })
    return result


@router.post("/resume/interview-prep")
async def resume_interview_prep(req: OptimizeRequest):
    result = await _get_resume_agent().execute({
        "action": "interview_prep", "resume_text": req.resume_text, "jd_text": req.jd_text,
    })
    return result


@router.post("/resume/skill-gap")
async def resume_skill_gap(req: OptimizeRequest):
    result = await _get_resume_agent().execute({
        "action": "skill_gap", "resume_text": req.resume_text, "jd_text": req.jd_text,
    })
    return result


@router.post("/resume/compare-jds")
async def resume_compare_jds(req: CompareJDsRequest):
    result = await _get_resume_agent().execute({
        "action": "compare_jds", "resume_text": req.resume_text, "jds": req.jds,
    })
    return result


@router.post("/resume/improve-section")
async def resume_improve_section(req: ImproveSectionRequest):
    result = await _get_resume_agent().execute({
        "action": "improve_section",
        "resume_text": req.resume_text, "section": req.section, "jd_text": req.jd_text,
    })
    return result


class JDAnalysisRequest(BaseModel):
    jd_text: str = Field(..., max_length=5000)


class AnswerCardsRequest(BaseModel):
    resume_text: str = Field(..., max_length=10000)
    jd_text: str = Field(..., max_length=5000)
    questions: List[str] = Field(default=[], max_length=10)


class UpgradePlanRequest(BaseModel):
    resume_text: str = Field(..., max_length=10000)
    audit_result: dict = Field(default_factory=dict)


@router.post("/resume/jd-analysis")
async def resume_jd_analysis(req: JDAnalysisRequest):
    result = await _get_resume_agent().execute({
        "action": "jd_analysis", "jd_text": req.jd_text,
    })
    return result


@router.post("/resume/materials-audit")
async def resume_materials_audit(req: ResumeRequest):
    result = await _get_resume_agent().execute({
        "action": "materials_audit", "resume_text": req.resume_text,
    })
    return result


@router.post("/resume/interview-grilling")
async def resume_interview_grilling(req: OptimizeRequest):
    result = await _get_resume_agent().execute({
        "action": "interview_grilling", "resume_text": req.resume_text, "jd_text": req.jd_text,
    })
    return result


@router.post("/resume/answer-cards")
async def resume_answer_cards(req: AnswerCardsRequest):
    result = await _get_resume_agent().execute({
        "action": "answer_cards", "resume_text": req.resume_text,
        "jd_text": req.jd_text, "questions": req.questions,
    })
    return result


@router.post("/resume/upgrade-plan")
async def resume_upgrade_plan(req: UpgradePlanRequest):
    result = await _get_resume_agent().execute({
        "action": "upgrade_plan", "resume_text": req.resume_text,
        "audit_result": req.audit_result,
    })
    return result


# ── Agent Profile 管理 ──

class ProfileUpdateRequest(BaseModel):
    model: Optional[str] = None
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, ge=64, le=16384)
    system_prompt: Optional[str] = Field(None, max_length=50000)
    enabled: Optional[bool] = None


@router.get("/profiles")
async def get_all_profiles():
    from ..agents.profiles import get_all_defaults, AgentProfile
    from ..core.database import get_all_agent_profiles
    defaults = get_all_defaults()
    overrides = get_all_agent_profiles()
    result = {}
    for name, default_profile in defaults.items():
        if name in overrides:
            merged = {**default_profile.to_dict(), **overrides[name]}
            result[name] = merged
        else:
            result[name] = default_profile.to_dict()
    return {"profiles": result}


@router.get("/profiles/{name}")
async def get_profile(name: str):
    from ..agents.profiles import get_default_profile
    from ..core.database import get_agent_profile
    default = get_default_profile(name)
    if not default:
        raise HTTPException(404, f"Agent '{name}' 不存在")
    override = get_agent_profile(name)
    if override:
        merged = {**default.to_dict(), **override}
        return {"profile": merged}
    return {"profile": default.to_dict()}


@router.put("/profiles/{name}")
async def update_profile(name: str, req: ProfileUpdateRequest):
    from ..agents.profiles import get_default_profile, AgentProfile
    from ..core.database import get_agent_profile, save_agent_profile
    default = get_default_profile(name)
    if not default:
        raise HTTPException(404, f"Agent '{name}' 不存在")
    # 合并：数据库已有 + 本次更新
    current = get_agent_profile(name) or default.to_dict()
    updates = req.model_dump(exclude_none=True)
    current.update(updates)
    save_agent_profile(name, current)
    # 更新内存中的 Agent profile
    orch = _get_orchestrator()
    agent = orch.agents.get(name)
    if agent:
        agent.profile = AgentProfile.from_dict(current)
    return {"profile": current, "updated": list(updates.keys())}


@router.post("/profiles/{name}/reset")
async def reset_profile(name: str):
    from ..agents.profiles import get_default_profile, AgentProfile
    from ..core.database import delete_agent_profile
    default = get_default_profile(name)
    if not default:
        raise HTTPException(404, f"Agent '{name}' 不存在")
    delete_agent_profile(name)
    # 恢复内存中的默认 profile
    orch = _get_orchestrator()
    agent = orch.agents.get(name)
    if agent:
        agent.profile = default
    return {"profile": default.to_dict(), "reset": True}
