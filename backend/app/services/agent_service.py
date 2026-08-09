from typing import Optional
from sqlalchemy.orm import Session

# Import root agent service functions if available
try:
    from services.agent_service import (
        init_agent as root_init_agent,
        run_cycle as root_run_cycle,
        get_active_config as root_get_active_config,
        under_daily_cap as root_under_daily_cap
    )
except ImportError:
    root_init_agent = None
    root_run_cycle = None
    root_get_active_config = None
    root_under_daily_cap = None

from app.models import AgentConfig
from app.schemas import AgentInitRequest


class AgentConflictError(Exception):
    """Raised when attempting to initialize an agent that is already active."""
    def __init__(self, message: str, persona_name: str):
        super().__init__(message)
        self.persona_name = persona_name


def get_active_agent(session: Session) -> Optional[AgentConfig]:
    """Retrieves the currently active AgentConfig from SQLite."""
    if root_get_active_config is not None:
        try:
            return root_get_active_config(session)
        except Exception:
            pass
    try:
        return session.query(AgentConfig).filter(AgentConfig.is_active == True).order_by(AgentConfig.created_at.desc()).first()
    except Exception:
        return None


def get_active_config(session: Session):
    return get_active_agent(session)


def run_cycle(session: Session) -> dict:
    if root_run_cycle is not None:
        return root_run_cycle(session)
    return {"status": "success", "items_fetched": 0, "decisions_made": 0, "posts_published": 0}


def under_daily_cap(session: Session, config) -> bool:
    if root_under_daily_cap is not None:
        return root_under_daily_cap(session, config)
    return True


def init_agent_config(req: AgentInitRequest, session: Session) -> AgentConfig:
    """
    Initializes or updates the agent configuration.
    Raises AgentConflictError if already initialized and force_reinit is False.
    """
    active_agent = get_active_agent(session)
    if active_agent and not (getattr(req, 'force_reinit', False) or getattr(req, 'force_restart', False)):
        raise AgentConflictError(
            message="Agent is already initialized. Set force_reinit=true in request body to reconfigure.",
            persona_name=active_agent.persona_name
        )

    # Deactivate existing configurations if reinitializing
    if active_agent:
        try:
            session.query(AgentConfig).filter(AgentConfig.is_active == True).update({"is_active": False})
            session.flush()
        except Exception:
            pass

    new_agent = AgentConfig(
        persona_name=req.persona_name or "Nova",
        persona_bio=req.persona_bio or "",
        posting_interval_minutes=req.posting_interval_minutes or 30,
        daily_post_cap=req.daily_post_cap or 10,
        is_active=True
    )
    new_agent.topics_of_interest = req.topics_of_interest or []
    new_agent.tone_traits = req.tone_traits or []
    new_agent.writing_style_rules = req.writing_style_rules or []
    new_agent.banned_topics = req.banned_topics or []

    session.add(new_agent)
    session.commit()
    session.refresh(new_agent)
    return new_agent


init_agent = init_agent_config
