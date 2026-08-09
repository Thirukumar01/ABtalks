import logging
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from db.models import NewsItem, AgentConfig, EditorialDecision
from editorial.scorer import relevance_score, novelty_score, recency_score
from editorial.rationale_builder import build_reasons

logger = logging.getLogger("autonomous_creator.editorial")

# Weights for composite score calculation
WEIGHT_RELEVANCE = 0.45
WEIGHT_NOVELTY = 0.35
WEIGHT_RECENCY = 0.20
PUBLISH_THRESHOLD = 0.60


def evaluate(item: NewsItem, config: AgentConfig, session: Session) -> EditorialDecision:
    """
    Evaluates a NewsItem against the current AgentConfig and historical posts.
    Calculates relevance, novelty, and recency, determines publish/reject verdict,
    and returns a persisted EditorialDecision object.
    """
    rel = relevance_score(item, config.topics_of_interest, config.banned_topics)
    nov = novelty_score(item, session)
    rec = recency_score(item)
    
    banned_detected = (rel == 0.0)
    
    composite = (WEIGHT_RELEVANCE * rel) + (WEIGHT_NOVELTY * nov) + (WEIGHT_RECENCY * rec)
    composite = round(composite, 3)
    
    should_pub = bool(composite >= PUBLISH_THRESHOLD and not banned_detected)
    
    scores = {
        "relevance": rel,
        "novelty": nov,
        "recency": rec,
        "composite": composite
    }
    
    rationale_bullets = build_reasons(scores, item, should_pub, banned_detected)
    
    decision = EditorialDecision(
        news_item_id=item.id,
        relevance_score=rel,
        novelty_score=nov,
        recency_score=rec,
        composite_score=composite,
        should_publish=should_pub,
        decided_at=datetime.now(timezone.utc)
    )
    decision.rationale = rationale_bullets
    
    session.add(decision)
    session.flush()
    
    logger.info(
        f"Editorial Decision for '{item.title[:40]}...': "
        f"Publish={should_pub} (Composite={composite:.2f})"
    )
    return decision
