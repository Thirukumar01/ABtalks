from datetime import datetime, timezone
from sqlalchemy.orm import Session
from db.models import Post, MemorySummary


def get_recent_posts(session: Session, limit: int = 10) -> list[Post]:
    """Retrieves the most recent published or held posts."""
    return session.query(Post).order_by(Post.created_at.desc()).limit(limit).all()


def save_post(post: Post, session: Session) -> Post:
    """Persists a new post to the database."""
    session.add(post)
    session.flush()
    return post


def get_latest_summary(session: Session) -> MemorySummary | None:
    """Fetches the latest compacted historical memory summary."""
    return session.query(MemorySummary).order_by(MemorySummary.created_at.desc()).first()


def save_summary(
    summary_text: str,
    post_count_covered: int,
    start_date: datetime,
    end_date: datetime,
    session: Session
) -> MemorySummary:
    """Persists a new compacted memory summary."""
    summary = MemorySummary(
        summary_text=summary_text,
        post_count_covered=post_count_covered,
        start_date=start_date,
        end_date=end_date,
        created_at=datetime.now(timezone.utc)
    )
    session.add(summary)
    session.flush()
    return summary
