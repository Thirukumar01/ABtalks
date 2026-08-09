import json
import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    Boolean,
    Text,
    DateTime,
    ForeignKey,
    Index
)
from sqlalchemy.orm import relationship
from db.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def generate_uuid() -> str:
    return str(uuid.uuid4())


class AgentConfig(Base):
    """Configuration and persona identity for the autonomous agent."""
    __tablename__ = "agent_config"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    persona_name = Column(String(100), nullable=False)
    persona_bio = Column(Text, nullable=False)
    topics_of_interest_json = Column(Text, nullable=False, default="[]")
    posting_interval_minutes = Column(Integer, nullable=False, default=30)
    tone_traits_json = Column(Text, nullable=False, default="[]")
    banned_topics_json = Column(Text, nullable=False, default="[]")
    daily_post_cap = Column(Integer, nullable=False, default=10)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=utc_now)
    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)

    @property
    def topics_of_interest(self) -> list[str]:
        try:
            return json.loads(self.topics_of_interest_json)
        except Exception:
            return []

    @topics_of_interest.setter
    def topics_of_interest(self, val: list[str]) -> None:
        self.topics_of_interest_json = json.dumps(val)

    @property
    def tone_traits(self) -> list[str]:
        try:
            return json.loads(self.tone_traits_json)
        except Exception:
            return []

    @tone_traits.setter
    def tone_traits(self, val: list[str]) -> None:
        self.tone_traits_json = json.dumps(val)

    @property
    def banned_topics(self) -> list[str]:
        try:
            return json.loads(self.banned_topics_json)
        except Exception:
            return []

    @banned_topics.setter
    def banned_topics(self, val: list[str]) -> None:
        self.banned_topics_json = json.dumps(val)


class NewsItem(Base):
    """Raw discovered news story/trend from RSS or NewsAPI."""
    __tablename__ = "news_items"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    source = Column(String(100), nullable=False)
    source_url = Column(Text, nullable=False)
    url_hash = Column(String(64), nullable=False, unique=True, index=True)
    title = Column(Text, nullable=False)
    summary = Column(Text, nullable=False)
    topic_tags_json = Column(Text, nullable=False, default="[]")
    published_at = Column(DateTime, nullable=True)
    discovered_at = Column(DateTime, nullable=False, default=utc_now)
    processed = Column(Integer, nullable=False, default=0, index=True)

    # Relationships
    decisions = relationship("EditorialDecision", back_populates="news_item", cascade="all, delete-orphan")
    posts = relationship("Post", back_populates="news_item", cascade="all, delete-orphan")

    @property
    def topic_tags(self) -> list[str]:
        try:
            return json.loads(self.topic_tags_json)
        except Exception:
            return []

    @topic_tags.setter
    def topic_tags(self, val: list[str]) -> None:
        self.topic_tags_json = json.dumps(val)


class EditorialDecision(Base):
    """Auditable editorial judgment record for a news story."""
    __tablename__ = "editorial_decisions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    news_item_id = Column(String(36), ForeignKey("news_items.id", ondelete="CASCADE"), nullable=False, index=True)
    relevance_score = Column(Float, nullable=False)
    novelty_score = Column(Float, nullable=False)
    recency_score = Column(Float, nullable=False)
    composite_score = Column(Float, nullable=False, default=0.0)
    should_publish = Column(Boolean, nullable=False)
    rationale_json = Column(Text, nullable=False, default="[]")
    decided_at = Column(DateTime, nullable=False, default=utc_now)

    # Relationship
    news_item = relationship("NewsItem", back_populates="decisions")

    @property
    def rationale(self) -> list[str]:
        try:
            return json.loads(self.rationale_json)
        except Exception:
            return []

    @rationale.setter
    def rationale(self, val: list[str]) -> None:
        self.rationale_json = json.dumps(val)


class Post(Base):
    """Synthesized post ready for social feed publication."""
    __tablename__ = "posts"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    news_item_id = Column(String(36), ForeignKey("news_items.id", ondelete="SET NULL"), nullable=True, index=True)
    content = Column(Text, nullable=False)
    rationale = Column(Text, nullable=False)
    sources_json = Column(Text, nullable=False, default="[]")
    status = Column(String(20), nullable=False, default="published", index=True)  # published, draft, held, failed
    scheduled_for = Column(DateTime, nullable=True)
    published_at = Column(DateTime, nullable=False, default=utc_now)
    created_at = Column(DateTime, nullable=False, default=utc_now)

    # Relationship
    news_item = relationship("NewsItem", back_populates="posts")

    @property
    def sources(self) -> list[str]:
        try:
            return json.loads(self.sources_json)
        except Exception:
            return []

    @sources.setter
    def sources(self, val: list[str]) -> None:
        self.sources_json = json.dumps(val)


class MemorySummary(Base):
    """Compacted summary digest of older published posts to bound context length."""
    __tablename__ = "memory_summaries"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    summary_text = Column(Text, nullable=False)
    post_count_covered = Column(Integer, nullable=False, default=0)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False, default=utc_now)


class RunLog(Base):
    """Telemetry and execution metrics recorded after every autonomous cycle."""
    __tablename__ = "run_logs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    run_started_at = Column(DateTime, nullable=False, default=utc_now)
    run_ended_at = Column(DateTime, nullable=True)
    status = Column(String(20), nullable=False, default="success")  # success, partial, failed
    items_fetched = Column(Integer, nullable=False, default=0)
    decisions_made = Column(Integer, nullable=False, default=0)
    posts_published = Column(Integer, nullable=False, default=0)
    error_message = Column(Text, nullable=True)
