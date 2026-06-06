"""多 Agent 协调架构模块。"""

from .base import BaseAgent, AgentMessage
from .orchestrator import Orchestrator, orchestrator
from .profiles import AgentProfile, get_default_profile, get_all_defaults, DEFAULT_PROFILES
from .search_agent import SearchAgent
from .scorer_agent import ScorerAgent
from .chat_agent import ChatAgent
from .apply_agent import ApplyAgent
from .resume_agent import ResumeAgent

__all__ = [
    "BaseAgent", "AgentMessage", "Orchestrator", "orchestrator",
    "AgentProfile", "get_default_profile", "get_all_defaults", "DEFAULT_PROFILES",
    "SearchAgent", "ScorerAgent", "ChatAgent", "ApplyAgent", "ResumeAgent",
]
