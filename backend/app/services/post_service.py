from typing import List, Tuple, Optional, Dict, Any
from sqlalchemy.orm import Session
from app.models import Post, AgentConfig
from app.schemas import PostResponseItem
from app.services.agent_service import get_active_agent


def get_feed_data(
    session: Session,
    agent_id: Optional[str] = None,
    limit: int = 20,
    status_filter: str = "published"
) -> Tuple[Optional[str], str, str, Dict[str, Any], int, int, List[PostResponseItem]]:
    """
    Queries posts and agent state from SQLite.
    Returns (agent_id, status, persona_name, persona_dict, total_posts, daily_cap, formatted_posts).
    """
    active_agent = get_active_agent(session)
    agent_status = "active" if active_agent else "uninitialized"
    persona_name = active_agent.persona_name if active_agent else "Uninitialized Agent"
    daily_cap = active_agent.daily_post_cap if active_agent else 10
    agent_uuid = active_agent.id if active_agent else None

    persona_dict = {
        "name": persona_name,
        "tagline": "An AI voice tracking the frontier of AI and technology.",
        "bio": active_agent.persona_bio if active_agent else "",
        "tone": active_agent.tone_traits if active_agent else [],
        "values": ["technical accuracy", "crediting sources", "avoiding hype"],
        "interests": active_agent.topics_of_interest if active_agent else []
    }

    query = session.query(Post)
    if status_filter and status_filter != "all":
        query = query.filter(Post.status == status_filter)

    total_posts = query.count()
    posts = query.order_by(Post.published_at.desc(), Post.created_at.desc()).limit(limit).all()

    formatted_posts: List[PostResponseItem] = []
    for p in posts:
        pub_iso = p.published_at.isoformat() if p.published_at else p.created_at.isoformat()
        content_text = p.content
        summary_text = content_text[:140] + "..." if len(content_text) > 140 else content_text

        formatted_posts.append(
            PostResponseItem(
                id=p.id,
                title=p.title or "Frontier AI Update",
                summary=summary_text,
                body=content_text,
                content=content_text,
                rationale=p.rationale or "Editorial significance",
                sources=p.sources,
                tags=active_agent.topics_of_interest if active_agent else ["AI"],
                publishedAt=pub_iso,
                published_at=pub_iso
            )
        )

    return agent_uuid, agent_status, persona_name, persona_dict, total_posts, daily_cap, formatted_posts
