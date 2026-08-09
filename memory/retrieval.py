from sqlalchemy.orm import Session
from memory.memory_store import get_recent_posts, get_latest_summary


def get_memory_context(session: Session) -> str:
    """
    Constructs a unified, human-readable memory context block containing:
    1. Long-Term Digest (from MemorySummary if present).
    2. Working Memory of the last 5-10 published posts.
    
    Returns a clean string formatted for LLM prompts, even if database is empty.
    """
    recent_posts = get_recent_posts(session, limit=8)
    latest_summary = get_latest_summary(session)
    
    context_parts: list[str] = []
    
    if latest_summary:
        context_parts.append(
            f"### LONG-TERM THEMATIC DIGEST:\n{latest_summary.summary_text.strip()}"
        )
        
    if recent_posts:
        posts_text = []
        for idx, p in enumerate(recent_posts, 1):
            time_str = p.created_at.strftime("%Y-%m-%d %H:%M") if p.created_at else "recent"
            posts_text.append(f"{idx}. [{time_str}] {p.content} (Rationale: {p.rationale})")
        context_parts.append("### RECENTLY PUBLISHED POSTS (DO NOT DUPLICATE):\n" + "\n".join(posts_text))
    else:
        context_parts.append("### RECENT MEMORY:\nNo previous posts published yet (fresh agent start).")
        
    return "\n\n".join(context_parts)
