import logging
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from db.models import NewsItem, EditorialDecision, AgentConfig, Post
from core.persona import build_persona_prompt
from generation.prompt_templates import render_generation_prompt
from services.openai_client import call_completion
from generation.style_guard import validate
from memory.memory_store import get_recent_posts

logger = logging.getLogger("autonomous_creator.generator")


def create_post(
    item: NewsItem,
    decision: EditorialDecision,
    memory_context: str,
    persona_config: AgentConfig,
    session: Session
) -> Post:
    """
    Synthesizes a structured post for an approved NewsItem using persona guidelines,
    validates with StyleGuard, and returns a ready-to-persist Post model.
    """
    system_prompt = build_persona_prompt(persona_config)
    user_prompt = render_generation_prompt(
        item_title=item.title,
        item_source=item.source,
        item_source_url=item.source_url,
        item_summary=item.summary,
        editorial_rationale=decision.rationale,
        memory_context=memory_context
    )
    
    # Call completion
    generated_dict = call_completion(system_prompt, user_prompt, json_mode=True)
    
    # Ensure item source URL is in sources
    sources = generated_dict.get("sources", [])
    if item.source_url and item.source_url not in sources:
        sources.append(item.source_url)
    generated_dict["sources"] = sources
    
    # Validate via StyleGuard
    recent_posts = get_recent_posts(session, limit=10)
    is_valid, issues = validate(
        generated_dict,
        recent_posts=recent_posts,
        banned_topics=persona_config.banned_topics
    )
    
    status = "published" if is_valid else "rejected"
    if not is_valid:
        logger.warning(f"Post marked as HELD due to style guard violations: {issues}")
        
    post = Post(
        news_item_id=item.id,
        content=generated_dict.get("content", "").strip(),
        rationale=generated_dict.get("rationale", "").strip() or "Approved via autonomous editorial decision.",
        status=status,
        published_at=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc)
    )
    post.sources = sources
    
    session.add(post)
    session.flush()
    logger.info(f"Post created [Status={status}] ID={post.id}")
    return post
