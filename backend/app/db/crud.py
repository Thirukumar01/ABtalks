import json
from typing import Optional, List
from datetime import datetime
from sqlalchemy.orm import Session
from app.db.models import Agent, Post


def get_active_agent(session: Session) -> Optional[Agent]:
    """Retrieves the currently active Agent from SQLite."""
    return session.query(Agent).filter(Agent.status == "active").order_by(Agent.created_at.desc()).first()


def get_agent_by_id(session: Session, agent_id: str) -> Optional[Agent]:
    """Retrieves an Agent by its primary UUID key."""
    return session.query(Agent).filter(Agent.id == agent_id).first()


def create_or_get_agent(session: Session, persona_data: dict) -> Agent:
    """
    Idempotent agent initialization:
    - If an active agent already exists, returns the existing agent without duplicating.
    - If none exists, creates and persists a new agent.
    """
    existing = get_active_agent(session)
    if existing:
        return existing

    # Extract persona details from request payload
    persona_name = persona_data.get("name", "Nova")
    persona_bio = persona_data.get("bio", "")
    if not persona_bio and "domain" in persona_data:
        persona_bio = f"Frontier AI researcher and analyst tracking {persona_data.get('domain')}."

    agent = Agent(
        persona_name=persona_name,
        persona_bio=persona_bio,
        persona_config_json=json.dumps(persona_data),
        status="active"
    )
    session.add(agent)
    session.commit()
    session.refresh(agent)
    return agent


def get_posts(
    session: Session,
    agent_id: Optional[str] = None,
    limit: int = 20,
    since: Optional[datetime] = None
) -> List[Post]:
    """
    Pure read-only query fetching published posts ordered newest-first.
    Guaranteed zero side-effects.
    """
    query = session.query(Post)
    if agent_id:
        query = query.filter(Post.agent_id == agent_id)
    if since:
        query = query.filter(Post.published_at >= since)
    return query.order_by(Post.published_at.desc()).limit(limit).all()


def count_posts(session: Session, agent_id: Optional[str] = None) -> int:
    """Counts total published posts."""
    query = session.query(Post)
    if agent_id:
        query = query.filter(Post.agent_id == agent_id)
    return query.count()
