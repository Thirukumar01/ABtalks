"""
FastAPI Endpoints for Autonomous AI Creator Hackathon Specification
Endpoints:
- POST /api/agent/init (201 Created / 409 Conflict / 422 Unprocessable Entity)
- GET /api/agent/feed (200 OK with formatted published posts)
- GET /api/agent/status (Current agent status, cap, and scheduler state)
- GET /api/agent/decisions (Editorial audit log with rejection rationales)
- POST /api/agent/trigger (Instant manual cycle execution)
"""

import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import json
from datetime import datetime, timezone
from typing import List, Dict, Optional
from fastapi import FastAPI, APIRouter, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from memory.sqlite_memory_system import SQLiteMemorySystem
from core.autonomous_scheduler import AutonomousCycleRunner

router = APIRouter(prefix="/api/agent", tags=["Autonomous Agent"])
db_store = SQLiteMemorySystem(db_path="data/autonomous_agent.db")
cycle_runner = AutonomousCycleRunner(db_path="data/autonomous_agent.db")


# ==========================================
# 1. PYDANTIC SCHEMAS WITH STRICT VALIDATION
# ==========================================
class AgentInitRequest(BaseModel):
    persona_name: str = Field(..., min_length=2, max_length=100, description="Name of the AI persona")
    persona_bio: str = Field(..., min_length=10, max_length=1000, description="Detailed background and identity")
    topics_of_interest: List[str] = Field(..., min_length=1, description="List of core domains to track")
    tone_traits: List[str] = Field(..., min_length=1, description="Personality and editorial tone guidelines")
    writing_style_rules: List[str] = Field(default_factory=lambda: ["2-3 short paragraphs", "No emojis", "Cite primary sources"])
    banned_topics: List[str] = Field(default_factory=list, description="Strictly blacklisted topics and keywords")
    posting_interval_minutes: int = Field(default=30, ge=1, le=1440, description="Interval between discovery ticks in minutes")
    daily_post_cap: int = Field(default=10, ge=1, le=100, description="Maximum posts published per day")
    force_reinit: bool = Field(default=False, description="Override 409 conflict and reinitialize")

    @field_validator("topics_of_interest", "tone_traits")
    @classmethod
    def validate_non_empty_strings(cls, v: List[str]) -> List[str]:
        cleaned = [item.strip() for item in v if item.strip()]
        if not cleaned:
            raise ValueError("Must contain at least one non-empty string entry.")
        return cleaned


class PostResponse(BaseModel):
    id: str
    title: str
    content: str
    rationale: str
    sources: List[str]
    published_at: str


class FeedResponse(BaseModel):
    status: str
    persona_name: str
    total_posts: int
    daily_cap: int
    posts: List[PostResponse]


# ==========================================
# 2. FASTAPI ENDPOINTS
# ==========================================

@router.post(
    "/init",
    status_code=status.HTTP_201_CREATED,
    summary="Initialize Agent Persona & Pipeline",
    response_description="Returns the configured agent persona and armed status"
)
async def init_agent(config: AgentInitRequest):
    """
    Initializes the autonomous agent with persona preferences and style constraints.
    - Returns **201 Created** on initial configuration.
    - Returns **409 Conflict** if already initialized (unless force_reinit=True).
    - Returns **422 Unprocessable Entity** on validation failure.
    """
    try:
        existing_persona = db_store.get_active_persona()
        if existing_persona and not config.force_reinit:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": "Agent is already initialized.",
                    "existing_persona": existing_persona["persona_name"],
                    "hint": "Set force_reinit=true in the request body to reconfigure existing persona."
                }
            )

        # Save to SQLite
        db_store.save_persona_preferences(
            persona_name=config.persona_name,
            persona_bio=config.persona_bio,
            topics_of_interest=config.topics_of_interest,
            tone_traits=config.tone_traits,
            writing_style_rules=config.writing_style_rules,
            banned_topics=config.banned_topics,
            daily_post_cap=config.daily_post_cap
        )

        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content={
                "message": "Autonomous AI Creator successfully initialized.",
                "persona_name": config.persona_name,
                "daily_post_cap": config.daily_post_cap,
                "posting_interval_minutes": config.posting_interval_minutes,
                "initialized_at": datetime.now(timezone.utc).isoformat()
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Initialization failed: {str(e)}"
        )


@router.get(
    "/feed",
    response_model=FeedResponse,
    status_code=status.HTTP_200_OK,
    summary="Fetch Published Posts Feed",
    response_description="Returns the chronologically ordered published posts feed"
)
async def get_feed(limit: int = Query(default=20, ge=1, le=100, description="Max posts to retrieve")):
    """
    Retrieves the published posts feed in reverse chronological order.
    Matches the exact hackathon payload specification with full source links and rationales.
    """
    try:
        persona = db_store.get_active_persona()
        persona_name = persona["persona_name"] if persona else "Default AI Analyst"
        daily_cap = persona["daily_post_cap"] if persona else 10

        posts = db_store.get_recent_posts(limit=limit)

        return FeedResponse(
            status="active",
            persona_name=persona_name,
            total_posts=len(posts),
            daily_cap=daily_cap,
            posts=[
                PostResponse(
                    id=p["id"],
                    title=p["title"],
                    content=p["content"],
                    rationale=p["rationale"],
                    sources=p["sources"],
                    published_at=p["published_at"]
                )
                for p in posts
            ]
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch feed: {str(e)}"
        )


@router.get("/status", status_code=status.HTTP_200_OK, summary="Get Agent Operational Health")
async def get_status():
    """Returns real-time agent status, active persona, and database counts."""
    persona = db_store.get_active_persona()
    posts = db_store.get_recent_posts(limit=100)
    rejected = db_store.get_rejected_topics(limit=100)

    return {
        "status": "active" if persona else "uninitialized",
        "persona": persona,
        "total_posts_published": len(posts),
        "total_rejected_topics": len(rejected),
        "server_time_utc": datetime.now(timezone.utc).isoformat()
    }


@router.get("/decisions", status_code=status.HTTP_200_OK, summary="Audit Log of Rejected & Evaluated Topics")
async def get_decisions(limit: int = Query(default=30, ge=1, le=100)):
    """Returns the transparent editorial decision audit log with full rejection explanations."""
    rejected = db_store.get_rejected_topics(limit=limit)
    return {
        "total_rejected_audited": len(rejected),
        "decisions": rejected
    }


@router.post("/trigger", status_code=status.HTTP_200_OK, summary="Manually Trigger One Autonomous Cycle")
async def trigger_cycle():
    """Executes a single autonomous tick immediately and returns the summary."""
    summary = cycle_runner.execute_tick()
    return {
        "message": "Autonomous cycle executed successfully.",
        "summary": summary
    }


# ==========================================
# 3. ROOT APP FACTORY
# ==========================================
app = FastAPI(
    title="Autonomous AI Creator API",
    description="Production FastAPI application powering autonomous AI discovery, editorial judgment, and social publishing.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}
