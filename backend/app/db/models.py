import json
import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    Integer,
    Boolean,
    Text,
    DateTime,
    ForeignKey,
    Index
)
from sqlalchemy.orm import relationship, synonym
from app.db.base import Base


def utc_now() -> datetime:
    """Returns current timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


def generate_uuid() -> str:
    """Generates a UUID4 string."""
    return str(uuid.uuid4())


class Agent(Base):
    """Configuration and persona identity for the autonomous agent."""
    __tablename__ = "agents"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    persona_name = Column(String(100), nullable=False)
    persona_bio = Column(Text, nullable=True, default="")
    persona_config_json = Column(Text, nullable=False, default="{}")
    status = Column(String(20), nullable=False, default="active")  # initializing, active, paused, error
    created_at = Column(DateTime, nullable=False, default=utc_now)
    last_discovery_at = Column(DateTime, nullable=True)
    last_publish_at = Column(DateTime, nullable=True)
    posts_published_count = Column(Integer, nullable=False, default=0)

    # Relationships
    posts = relationship("Post", back_populates="agent", cascade="all, delete-orphan")
    topics = relationship("Topic", back_populates="agent", cascade="all, delete-orphan")

    @property
    def persona_config(self) -> dict:
        try:
            return json.loads(self.persona_config_json or "{}")
        except Exception:
            return {}

    @persona_config.setter
    def persona_config(self, val: dict) -> None:
        self.persona_config_json = json.dumps(val or {})


class Source(Base):
    """Discovered sources registry (RSS, HN, GitHub, official blogs)."""
    __tablename__ = "sources"

    id = Column(Integer, primary_key=True, autoincrement=True)
    type = Column(String(50), nullable=False)  # rss, hackernews, github, blog
    name = Column(String(100), nullable=False)
    url = Column(Text, nullable=False)
    enabled = Column(Boolean, nullable=False, default=True, index=True)
    last_fetched_at = Column(DateTime, nullable=True)
    last_fetch_status = Column(String(20), nullable=True)  # ok, error, empty
    last_error = Column(Text, nullable=True)

    # Relationships
    topics = relationship("Topic", back_populates="source", cascade="all, delete-orphan")


class Topic(Base):
    """Raw and normalized discovery candidates before/after editorial review."""
    __tablename__ = "topics"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    agent_id = Column(String(36), ForeignKey("agents.id", ondelete="CASCADE"), nullable=True, index=True)
    source_id = Column(Integer, ForeignKey("sources.id", ondelete="SET NULL"), nullable=True, index=True)
    title = Column(Text, nullable=False)
    summary = Column(Text, nullable=True)
    url = Column(Text, nullable=False)
    content_hash = Column(String(64), nullable=False, index=True)
    discovered_at = Column(DateTime, nullable=False, default=utc_now)
    raw_metadata_json = Column(Text, nullable=True, default="{}")
    editorial_status = Column(String(20), nullable=False, default="pending", index=True)  # pending, scored, approved, rejected, published, expired
    editorial_score_json = Column(Text, nullable=True)
    rejection_reason = Column(Text, nullable=True)

    # Relationships
    agent = relationship("Agent", back_populates="topics")
    source = relationship("Source", back_populates="topics")
    post = relationship("Post", back_populates="topic", uselist=False)


class Post(Base):
    """Published post content — the feed's payload."""
    __tablename__ = "posts"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    agent_id = Column(String(36), ForeignKey("agents.id", ondelete="CASCADE"), nullable=True, index=True)
    topic_id = Column(String(36), ForeignKey("topics.id", ondelete="SET NULL"), nullable=True)
    title = Column(Text, nullable=True)
    body = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    rationale = Column(Text, nullable=True)
    sources_json = Column(Text, nullable=False, default="[]")
    tags_json = Column(Text, nullable=False, default="[]")
    content_hash = Column(String(64), nullable=True, index=True)
    published_at = Column(DateTime, nullable=False, default=utc_now, index=True)
    generation_meta_json = Column(Text, nullable=True, default="{}")

    # Relationships
    agent = relationship("Agent", back_populates="posts")
    topic = relationship("Topic", back_populates="post")

    @property
    def content(self) -> str:
        return self.body or ""

    @content.setter
    def content(self, val: str) -> None:
        self.body = val

    @property
    def sources(self) -> list:
        try:
            return json.loads(self.sources_json or "[]")
        except Exception:
            return []

    @sources.setter
    def sources(self, val: list) -> None:
        self.sources_json = json.dumps(val or [])

    @property
    def tags(self) -> list:
        try:
            return json.loads(self.tags_json or "[]")
        except Exception:
            return []

    @tags.setter
    def tags(self, val: list) -> None:
        self.tags_json = json.dumps(val or [])


class RunLog(Base):
    """Operational audit trail for unattended durability and error tracking."""
    __tablename__ = "run_logs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    agent_id = Column(String(36), ForeignKey("agents.id", ondelete="CASCADE"), nullable=True, index=True)
    run_type = Column(String(50), nullable=True, default="publish_cycle")
    started_at = Column(DateTime, nullable=True, default=utc_now)
    run_started_at = Column(DateTime, nullable=False, default=utc_now)
    finished_at = Column(DateTime, nullable=True)
    run_ended_at = Column(DateTime, nullable=True)
    status = Column(String(20), nullable=False, default="success")  # success, partial, failed
    items_fetched = Column(Integer, nullable=False, default=0)
    decisions_made = Column(Integer, nullable=False, default=0)
    posts_published = Column(Integer, nullable=False, default=0)
    error_message = Column(Text, nullable=True)
    detail_json = Column(Text, nullable=True, default="{}")

