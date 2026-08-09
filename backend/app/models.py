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
    Index
)
from app.database import Base


def utc_now() -> datetime:
    """Returns current UTC datetime."""
    return datetime.now(timezone.utc)


def generate_uuid() -> str:
    """Generates string UUID4."""
    return str(uuid.uuid4())


class AgentConfig(Base):
    """Configuration and persona identity for the autonomous agent."""
    __tablename__ = "agent_configs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    persona_name = Column(String(100), nullable=False)
    persona_bio = Column(Text, nullable=False)
    topics_of_interest_json = Column(Text, nullable=False, default="[]")
    tone_traits_json = Column(Text, nullable=False, default="[]")
    writing_style_rules_json = Column(Text, nullable=False, default="[]")
    banned_topics_json = Column(Text, nullable=False, default="[]")
    posting_interval_minutes = Column(Integer, nullable=False, default=30)
    daily_post_cap = Column(Integer, nullable=False, default=10)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
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
        self.topics_of_interest_json = json.dumps(val or [])

    @property
    def tone_traits(self) -> list[str]:
        try:
            return json.loads(self.tone_traits_json)
        except Exception:
            return []

    @tone_traits.setter
    def tone_traits(self, val: list[str]) -> None:
        self.tone_traits_json = json.dumps(val or [])

    @property
    def writing_style_rules(self) -> list[str]:
        try:
            return json.loads(self.writing_style_rules_json)
        except Exception:
            return []

    @writing_style_rules.setter
    def writing_style_rules(self, val: list[str]) -> None:
        self.writing_style_rules_json = json.dumps(val or [])

    @property
    def banned_topics(self) -> list[str]:
        try:
            return json.loads(self.banned_topics_json)
        except Exception:
            return []

    @banned_topics.setter
    def banned_topics(self, val: list[str]) -> None:
        self.banned_topics_json = json.dumps(val or [])


class Post(Base):
    """Synthesized post ready for social feed publication."""
    __tablename__ = "posts"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    title = Column(String(255), nullable=True)
    content = Column(Text, nullable=False)
    rationale = Column(Text, nullable=True)
    sources_json = Column(Text, nullable=False, default="[]")
    status = Column(String(20), nullable=False, default="published", index=True)
    published_at = Column(DateTime, nullable=False, default=utc_now, index=True)
    created_at = Column(DateTime, nullable=False, default=utc_now)

    @property
    def sources(self) -> list[str]:
        try:
            return json.loads(self.sources_json)
        except Exception:
            return []

    @sources.setter
    def sources(self, val: list[str]) -> None:
        self.sources_json = json.dumps(val or [])
