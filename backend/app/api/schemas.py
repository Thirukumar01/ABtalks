from datetime import datetime
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field, ConfigDict


class PersonaInput(BaseModel):
    """Persona configuration object."""
    name: Optional[str] = Field(default="Nova", description="Agent persona name")
    domain: Optional[str] = Field(default=None, description="Domain focus, e.g. AI Security")
    tagline: Optional[str] = Field(default="An AI voice tracking the frontier of AI and technology.")
    bio: Optional[str] = Field(default=None, description="Persona background and voice")
    tone: Optional[List[str]] = Field(default_factory=lambda: ["curious", "precise", "accessible"])
    values: Optional[List[str]] = Field(default_factory=lambda: ["technical accuracy", "crediting sources"])
    interests: Optional[List[str]] = Field(default_factory=lambda: ["LLMs", "AI infrastructure", "open-source AI"])

    model_config = ConfigDict(extra="allow")


class AgentInitRequest(BaseModel):
    """
    Request schema for POST /api/agent/init.
    Supports both nested {"persona": {...}} and flat payload configurations.
    """
    persona: Optional[PersonaInput] = Field(
        default=None,
        description="Persona definition object"
    )
    # Backward compatibility with flat properties
    persona_name: Optional[str] = None
    persona_bio: Optional[str] = None
    domain: Optional[str] = None
    topics_of_interest: Optional[List[str]] = None
    posting_interval_minutes: Optional[int] = 30
    tone_traits: Optional[List[str]] = None
    writing_style_rules: Optional[List[str]] = None
    banned_topics: Optional[List[str]] = None
    daily_post_cap: Optional[int] = 10
    force_restart: Optional[bool] = False
    force_reinit: Optional[bool] = False

    model_config = ConfigDict(extra="allow")


class AgentInitResponse(BaseModel):
    """
    Response schema for POST /api/agent/init.
    Guarantees exact contract { "agentId": "..." } with additive optional metadata.
    """
    agentId: str = Field(..., description="Unique agent identifier")
    agent_id: Optional[str] = None
    status: Optional[str] = Field(default="active", description="Agent operational status")
    persona: Optional[Dict[str, Any]] = None
    persona_name: Optional[str] = None
    persona_bio: Optional[str] = None
    topics_of_interest: Optional[List[str]] = None
    tone_traits: Optional[List[str]] = None
    writing_style_rules: Optional[List[str]] = None
    banned_topics: Optional[List[str]] = None
    posting_interval_minutes: Optional[int] = None
    daily_post_cap: Optional[int] = None
    is_active: Optional[bool] = True
    created_at: Optional[Union[datetime, str]] = None
    initialized_at: Optional[str] = None
    message: Optional[str] = Field(default="Agent initialized and running autonomously.")

    model_config = ConfigDict(from_attributes=True, extra="allow")


class PostSourceItem(BaseModel):
    """Structured primary source citation."""
    title: Optional[str] = "Primary Source"
    url: str
    source_type: Optional[str] = "web"
    sourceType: Optional[str] = "web"

    model_config = ConfigDict(extra="allow")


class PostItem(BaseModel):
    """Individual post schema returned inside the feed."""
    id: str
    news_item_id: Optional[str] = None
    title: Optional[str] = None
    summary: Optional[str] = None
    body: Optional[str] = None
    content: Optional[str] = None
    publishedAt: Optional[str] = None
    published_at: Optional[str] = None
    createdAt: Optional[str] = None
    created_at: Optional[str] = None
    rationale: Optional[str] = None
    sources: List[Any] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    status: Optional[str] = "published"

    model_config = ConfigDict(from_attributes=True, extra="allow")


# Aliases for compatibility
PostSchema = PostItem
PostResponseItem = PostItem


class FeedResponse(BaseModel):
    """
    Response schema for GET /api/agent/feed.
    Guarantees exact contract { "posts": [] } with additive optional metadata.
    """
    posts: List[PostItem] = Field(default_factory=list)
    total: Optional[int] = 0
    totalPosts: Optional[int] = 0
    total_posts: Optional[int] = 0
    limit: Optional[int] = None
    agentId: Optional[str] = None
    agent_id: Optional[str] = None
    status: Optional[str] = "active"
    persona_name: Optional[str] = None
    persona: Optional[Dict[str, Any]] = None
    daily_cap: Optional[int] = 10

    model_config = ConfigDict(from_attributes=True, extra="allow")


class EditorialDecisionSchema(BaseModel):
    """Editorial decision item for transparent auditing."""
    id: str
    news_item_id: Optional[str] = ""
    title: str
    source_url: str
    relevance_score: float
    novelty_score: float
    recency_score: float
    composite_score: float
    should_publish: bool
    rationale: List[str] = Field(default_factory=list)
    decided_at: str

    model_config = ConfigDict(from_attributes=True, extra="allow")


class RunLogSchema(BaseModel):
    """Operational telemetry history item."""
    id: str
    run_started_at: str
    run_ended_at: Optional[str] = None
    status: str
    items_fetched: int = 0
    decisions_made: int = 0
    posts_published: int = 0
    error_message: Optional[str] = None

    model_config = ConfigDict(from_attributes=True, extra="allow")


class StatusResponse(BaseModel):
    """Current agent health, metrics, and scheduler state."""
    agent_active: bool = True
    persona_name: Optional[str] = None
    scheduler_running: bool = True
    next_scheduled_run: Optional[str] = None
    posting_interval_minutes: int = 30
    total_posts_published: int = 0
    total_decisions_made: int = 0
    total_news_items_ingested: int = 0
    daily_posts_today: int = 0
    daily_post_cap: int = 10
    last_cycle_status: Optional[str] = "idle"
    last_cycle_time: Optional[str] = None
    status: Optional[str] = "active"
    agentId: Optional[str] = None
    agent_id: Optional[str] = None
    persona: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True, extra="allow")


# Alias for compatibility
AgentStatus = StatusResponse


class TriggerCycleResponse(BaseModel):
    """Result of manual autonomous cycle trigger."""
    success: bool = True
    status: str = "success"
    items_fetched: int = 0
    decisions_made: int = 0
    posts_published: int = 0
    message: str = "Autonomous cycle executed successfully."
    details: Optional[Dict[str, Any]] = None
    summary: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True, extra="allow")


class ErrorResponse(BaseModel):
    """Standard error response."""
    error: Optional[str] = "error"
    detail: Optional[Union[str, dict, list]] = None

    model_config = ConfigDict(extra="allow")


ErrorDetail = ErrorResponse
