from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


class AgentConfigRequest(BaseModel):
    """Request schema for configuring and initializing the autonomous agent."""
    persona_name: str = Field(..., min_length=2, max_length=100, json_schema_extra={"example": "Aria Vance"})
    persona_bio: str = Field(..., min_length=10, json_schema_extra={"example": "Senior AI researcher and technology critic providing sharp, nuance-rich analysis on machine intelligence."})
    topics_of_interest: List[str] = Field(default_factory=lambda: ["LLMs", "Autonomous Agents", "Robotics", "AI Safety", "Open Source AI"])
    posting_interval_minutes: int = Field(default=30, ge=1, le=1440, description="Autonomous scheduler tick frequency")
    tone_traits: List[str] = Field(default_factory=lambda: ["analytical", "insightful", "objective", "tech-forward"])
    banned_topics: List[str] = Field(default_factory=lambda: ["crypto shilling", "clickbait", "unverified rumors", "celebrity gossip"])
    daily_post_cap: int = Field(default=10, ge=1, le=100)
    force_restart: bool = Field(default=False, description="If true, overwrites existing active persona")


class AgentConfigResponse(BaseModel):
    """Response schema returned after persona initialization."""
    agent_id: str
    persona_name: str
    persona_bio: str
    topics_of_interest: List[str]
    posting_interval_minutes: int
    tone_traits: List[str]
    banned_topics: List[str]
    daily_post_cap: int
    is_active: bool
    created_at: datetime
    message: str = "Agent successfully configured and autonomous scheduler armed."

    model_config = ConfigDict(from_attributes=True)


class NewsItemSchema(BaseModel):
    """Schema representing an ingested and normalized news story."""
    id: str
    source: str
    source_url: str
    title: str
    summary: str
    topic_tags: List[str]
    published_at: Optional[datetime] = None
    discovered_at: datetime
    processed: int

    model_config = ConfigDict(from_attributes=True)


class EditorialDecisionSchema(BaseModel):
    """Schema representing an editorial evaluation and transparency audit."""
    id: str
    news_item_id: str
    title: Optional[str] = None
    source_url: Optional[str] = None
    relevance_score: float
    novelty_score: float
    recency_score: float
    composite_score: float
    should_publish: bool
    rationale: List[str]
    decided_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PostSchema(BaseModel):
    """Schema representing a synthesized and published or held post."""
    id: str
    news_item_id: Optional[str] = None
    content: str
    rationale: str
    sources: List[str]
    status: str
    published_at: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FeedResponse(BaseModel):
    """Paginated response containing published posts."""
    total: int
    limit: int
    posts: List[PostSchema]


class StatusResponse(BaseModel):
    """System health, scheduler status, and telemetry overview."""
    agent_active: bool
    persona_name: Optional[str] = None
    scheduler_running: bool
    next_scheduled_run: Optional[str] = None
    posting_interval_minutes: int
    total_posts_published: int
    total_decisions_made: int
    total_news_items_ingested: int
    daily_posts_today: int
    daily_post_cap: int
    last_cycle_status: Optional[str] = None
    last_cycle_time: Optional[datetime] = None


class RunLogSchema(BaseModel):
    """Schema for individual cycle telemetry log."""
    id: str
    run_started_at: datetime
    run_ended_at: Optional[datetime] = None
    status: str
    items_fetched: int
    decisions_made: int
    posts_published: int
    error_message: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class TriggerCycleResponse(BaseModel):
    """Response returned when manually triggering an agent execution cycle."""
    success: bool
    status: str
    items_fetched: int
    decisions_made: int
    posts_published: int
    message: str
    details: Optional[dict] = None
