import hashlib
import difflib
import logging
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from db.models import NewsItem

logger = logging.getLogger("autonomous_creator.dedup")


def hash_url(url: str) -> str:
    """Generates a deterministic SHA-256 hash for a given URL string."""
    normalized_url = url.strip().lower().rstrip("/")
    return hashlib.sha256(normalized_url.encode("utf-8")).hexdigest()


def title_similarity(title_a: str, title_b: str) -> float:
    """Computes quick ratio similarity between two headline titles."""
    return difflib.SequenceMatcher(None, title_a.lower().strip(), title_b.lower().strip()).ratio()


def is_duplicate(item: dict, session: Session, lookback_hours: int = 48) -> bool:
    """
    Checks if a news item is a duplicate based on URL hash or title similarity
    against stories ingested within the last lookback_hours.
    """
    item_url = item.get("source_url", "")
    if not item_url:
        return True
    
    url_h = hash_url(item_url)
    
    # 1. Exact URL hash match check
    existing_by_hash = session.query(NewsItem).filter(NewsItem.url_hash == url_h).first()
    if existing_by_hash:
        return True
    
    # 2. Fuzzy Title Match over recent items
    cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
    recent_items = session.query(NewsItem).filter(NewsItem.discovered_at >= cutoff).all()
    
    target_title = item.get("title", "")
    for existing in recent_items:
        sim = title_similarity(target_title, existing.title)
        if sim > 0.85:
            logger.debug(f"Duplicate detected via title similarity ({sim:.2f}): '{target_title}' vs '{existing.title}'")
            return True
            
    return False


def store_new_items(items: list[dict], session: Session) -> int:
    """
    Iterates through normalized news items, filters duplicates,
    and stores new unprocessed rows into the news_items table.
    
    Returns:
        Count of newly stored items.
    """
    inserted_count = 0
    for item in items:
        if is_duplicate(item, session):
            continue
            
        url_h = hash_url(item["source_url"])
        news_model = NewsItem(
            source=item.get("source", "Web"),
            source_url=item["source_url"],
            url_hash=url_h,
            title=item["title"],
            summary=item["summary"],
            published_at=item.get("published_at"),
            discovered_at=datetime.now(timezone.utc),
            processed=0
        )
        news_model.topic_tags = item.get("topic_tags", [])
        session.add(news_model)
        inserted_count += 1
        
    session.flush()
    logger.info(f"Persisted {inserted_count} new distinct news items.")
    return inserted_count
