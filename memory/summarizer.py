import logging
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from db.models import Post
from memory.memory_store import save_summary

logger = logging.getLogger("autonomous_creator.summarizer")


def compact_memory_if_needed(session: Session, threshold_count: int = 20) -> bool:
    """
    Checks if post count exceeds threshold. If so, creates a compacted summary
    to keep context window lean.
    """
    total_posts = session.query(Post).count()
    if total_posts < threshold_count:
        return False
        
    posts = session.query(Post).order_by(Post.created_at.asc()).limit(10).all()
    if not posts:
        return False
        
    topics_covered = []
    for p in posts:
        snippet = p.content[:80].replace("\n", " ")
        topics_covered.append(f"- {snippet}...")
        
    summary_text = (
        f"Historical digest covering {len(posts)} publications from "
        f"{posts[0].created_at.strftime('%Y-%m-%d')} to {posts[-1].created_at.strftime('%Y-%m-%d')}:\n" +
        "\n".join(topics_covered)
    )
    
    save_summary(
        summary_text=summary_text,
        post_count_covered=len(posts),
        start_date=posts[0].created_at,
        end_date=posts[-1].created_at,
        session=session
    )
    logger.info(f"Compacted {len(posts)} posts into long-term MemorySummary.")
    return True
