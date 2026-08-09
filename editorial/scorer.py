import math
import logging
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from db.models import NewsItem, Post

logger = logging.getLogger("autonomous_creator.scorer")


def relevance_score(item: NewsItem, topics_of_interest: list[str], banned_topics: list[str]) -> float:
    """
    Scores how well a news item matches the persona's core topics while severely
    penalizing any banned themes.
    
    Returns:
        float between 0.0 and 1.0.
    """
    text_content = f"{item.title} {item.summary}".lower()
    
    # 1. Check banned topics first (instant rejection if present)
    for banned in banned_topics:
        if banned.lower() in text_content:
            logger.info(f"Banned topic '{banned}' detected in news item '{item.title}'.")
            return 0.0
            
    # 2. Topic match overlap
    if not topics_of_interest:
        return 0.70  # Default neutral score
        
    matched_count = 0
    for topic in topics_of_interest:
        topic_lower = topic.lower()
        # Direct word or tag match
        if topic_lower in text_content or any(topic_lower in t.lower() for t in item.topic_tags):
            matched_count += 1
            
    # Compute normalized score based on matches
    ratio = min(1.0, (matched_count / max(1, len(topics_of_interest) * 0.4)))
    # Base minimum of 0.30 if AI/tech keywords exist, scaled by match ratio
    score = 0.30 + (0.70 * ratio)
    return round(min(1.0, max(0.0, score)), 3)


def novelty_score(item: NewsItem, session: Session, lookback_limit: int = 15) -> float:
    """
    Scores the novelty of an item relative to recently published posts.
    If the agent has already published very similar stories, novelty drops.
    
    Returns:
        float between 0.0 and 1.0.
    """
    recent_posts = session.query(Post).order_by(Post.created_at.desc()).limit(lookback_limit).all()
    if not recent_posts:
        return 1.0  # Fresh database, max novelty
        
    item_tokens = set(item.title.lower().split())
    max_overlap = 0.0
    
    for p in recent_posts:
        post_tokens = set(p.content.lower().split())
        intersection = item_tokens.intersection(post_tokens)
        if item_tokens:
            overlap = len(intersection) / len(item_tokens)
            if overlap > max_overlap:
                max_overlap = overlap
                
    # If overlap is high (e.g. >0.6), novelty is low
    novelty = 1.0 - (max_overlap * 0.8)
    return round(min(1.0, max(0.1, novelty)), 3)


def recency_score(item: NewsItem) -> float:
    """
    Exponential decay score prioritizing items published within the last 12-24 hours.
    
    Returns:
        float between 0.0 and 1.0.
    """
    pub_time = item.published_at or item.discovered_at
    if pub_time.tzinfo is None:
        pub_time = pub_time.replace(tzinfo=timezone.utc)
        
    now = datetime.now(timezone.utc)
    age_hours = max(0.0, (now - pub_time).total_seconds() / 3600.0)
    
    # Half-life of 24 hours
    decay = math.exp(-0.03 * age_hours)
    return round(min(1.0, max(0.2, decay)), 3)
