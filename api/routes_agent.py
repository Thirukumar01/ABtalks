import logging
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.orm import Session
from db.database import get_db
from db.models import AgentConfig, AgentLog, NewsItem, EditorialDecision, Post, RunLog
from app.config import settings
from api.schemas import (
    AgentConfigRequest,
    AgentConfigResponse,
    FeedResponse,
    PostSchema,
    StatusResponse,
    EditorialDecisionSchema,
    RunLogSchema,
    TriggerCycleResponse
)
from services.agent_service import init_agent, run_cycle, get_active_config
from core.scheduler import start_scheduler, stop_scheduler, get_scheduler_info
from utils.errors import ConfigConflictError

logger = logging.getLogger("autonomous_creator.api")

router = APIRouter(prefix="/api/agent", tags=["Autonomous Agent"])


@router.post(
    "/init",
    response_model=AgentConfigResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Initialize or update the persona and arm the autonomous scheduler."
)
def initialize_agent(
    config_req: AgentConfigRequest,
    session: Session = Depends(get_db)
):
    try:
        new_config = init_agent(config_req, session)
        # Start background scheduler automatically with the specified interval
        if settings.ENABLE_INTERNAL_SCHEDULER and new_config.is_active:
            start_scheduler(interval_minutes=new_config.posting_interval_minutes)
        
        return AgentConfigResponse(
            agent_id=new_config.id,
            persona_name=new_config.persona_name,
            persona_bio=new_config.persona_bio,
            topics_of_interest=new_config.topics_of_interest,
            posting_interval_minutes=new_config.posting_interval_minutes,
            tone_traits=new_config.tone_traits,
            banned_topics=new_config.banned_topics,
            daily_post_cap=new_config.daily_post_cap,
            is_active=new_config.is_active,
            created_at=new_config.created_at,
            updated_at=new_config.updated_at,
            message="Agent persona initialized and autonomous background scheduler armed."
        )
    except ConfigConflictError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e) + " Use force_restart=true in request to overwrite."
        )
    except Exception as e:
        logger.error(f"Error during agent init: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Initialization failed: {str(e)}"
        )


def _config_response(config: AgentConfig) -> AgentConfigResponse:
    return AgentConfigResponse(
        agent_id=config.id,
        persona_name=config.persona_name,
        persona_bio=config.persona_bio,
        topics_of_interest=config.topics_of_interest,
        posting_interval_minutes=config.posting_interval_minutes,
        tone_traits=config.tone_traits,
        banned_topics=config.banned_topics,
        daily_post_cap=config.daily_post_cap,
        is_active=config.is_active,
        created_at=config.created_at,
        updated_at=config.updated_at,
    )


@router.get("/config", response_model=AgentConfigResponse)
def get_agent_config(session: Session = Depends(get_db)):
    config = session.query(AgentConfig).order_by(AgentConfig.created_at.desc()).first()
    if not config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent persona is not configured.")
    return _config_response(config)


@router.put("/config", response_model=AgentConfigResponse)
def update_agent_config(config_req: AgentConfigRequest, session: Session = Depends(get_db)):
    config_req.force_restart = True
    new_config = init_agent(config_req, session)
    if new_config.is_active:
        if settings.ENABLE_INTERNAL_SCHEDULER:
            start_scheduler(interval_minutes=new_config.posting_interval_minutes)
    else:
        stop_scheduler()
    return _config_response(new_config)


@router.get(
    "/feed",
    response_model=FeedResponse,
    summary="Retrieve published or drafted posts (newest first)."
)
def get_feed(
    limit: int = Query(20, ge=1, le=100),
    status_filter: str = Query("published", alias="status"),
    since: Optional[datetime] = None,
    session: Session = Depends(get_db)
):
    query = session.query(Post)
    if status_filter != "all":
        query = query.filter(Post.status == status_filter)
    if since:
        query = query.filter(Post.created_at >= since)
        
    posts = query.order_by(Post.created_at.desc()).limit(limit).all()
    
    post_schemas = []
    for p in posts:
        post_schemas.append(PostSchema(
            id=p.id,
            news_item_id=p.news_item_id,
            content=p.content,
            rationale=p.rationale,
            sources=p.sources,
            status=p.status,
            published_at=p.published_at,
            created_at=p.created_at
        ))
        
    return FeedResponse(
        total=len(post_schemas),
        limit=limit,
        posts=post_schemas
    )


@router.get(
    "/status",
    response_model=StatusResponse,
    summary="Check agent operational status, scheduler pulse, and aggregate metrics."
)
def get_status(session: Session = Depends(get_db)):
    config = get_active_config(session)
    scheduler_info = get_scheduler_info()
    
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    
    posts_today = session.query(Post).filter(
        Post.status == "published",
        Post.published_at >= today_start
    ).count()
    
    total_posts = session.query(Post).filter(Post.status == "published").count()
    total_decisions = session.query(EditorialDecision).count()
    total_news = session.query(NewsItem).count()
    
    latest_run = session.query(RunLog).order_by(RunLog.run_started_at.desc()).first()
    
    return StatusResponse(
        agent_active=bool(config and config.is_active),
        persona_name=config.persona_name if config else None,
        scheduler_running=scheduler_info["running"],
        next_scheduled_run=scheduler_info["next_fire_time"],
        posting_interval_minutes=config.posting_interval_minutes if config else 30,
        total_posts_published=total_posts,
        total_decisions_made=total_decisions,
        total_news_items_ingested=total_news,
        daily_posts_today=posts_today,
        daily_post_cap=config.daily_post_cap if config else 10,
        last_cycle_status=latest_run.status if latest_run else "idle",
        last_cycle_time=latest_run.run_started_at if latest_run else None
    )


@router.get(
    "/decisions",
    response_model=List[EditorialDecisionSchema],
    summary="Auditable log of editorial decisions with acceptance/rejection rationale."
)
def get_decisions(
    limit: int = Query(30, ge=1, le=100),
    session: Session = Depends(get_db)
):
    decisions = (
        session.query(EditorialDecision)
        .order_by(EditorialDecision.decided_at.desc())
        .limit(limit)
        .all()
    )
    
    out: List[EditorialDecisionSchema] = []
    for d in decisions:
        item = d.news_item
        out.append(EditorialDecisionSchema(
            id=d.id,
            news_item_id=d.news_item_id,
            title=item.title if item else "Unknown Title",
            source_url=item.source_url if item else "",
            relevance_score=d.relevance_score,
            novelty_score=d.novelty_score,
            recency_score=d.recency_score,
            composite_score=d.composite_score,
            should_publish=d.should_publish,
            rationale=d.rationale,
            decided_at=d.decided_at
        ))
    return out


@router.post(
    "/trigger",
    response_model=TriggerCycleResponse,
    summary="Instantly triggers one autonomous execution cycle."
)
def trigger_cycle(session: Session = Depends(get_db)):
    result = run_cycle(session)
    success = (result.get("status") == "success")
    return TriggerCycleResponse(
        success=success,
        status=result.get("status", "unknown"),
        items_fetched=result.get("items_fetched", 0),
        decisions_made=result.get("decisions_made", 0),
        posts_published=result.get("posts_published", 0),
        message="Autonomous cycle executed successfully." if success else f"Cycle status: {result.get('status')}",
        details=result
    )


@router.post("/run", response_model=TriggerCycleResponse, summary="Run one protected autonomous cycle")
def run_agent(session: Session = Depends(get_db), x_agent_trigger_secret: str | None = Header(default=None)):
    if settings.AGENT_TRIGGER_SECRET and x_agent_trigger_secret != settings.AGENT_TRIGGER_SECRET:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid agent trigger secret.")
    result = run_cycle(session)
    if result.get("status") == "running":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Agent cycle already running")
    success = result.get("status") in {"success", "capped", "skipped", "degraded"}
    return TriggerCycleResponse(
        success=success,
        status=result.get("status", "unknown"),
        items_fetched=result.get("items_fetched", 0),
        decisions_made=result.get("decisions_made", 0),
        posts_published=result.get("posts_published", 0),
        message=result.get("message", "Autonomous cycle completed."),
        details=result,
    )


@router.get("/runs", response_model=List[RunLogSchema], summary="Telemetry history of cycle runs.")
def get_run_logs(
    limit: int = Query(15, ge=1, le=50),
    session: Session = Depends(get_db)
):
    runs = session.query(RunLog).order_by(RunLog.run_started_at.desc()).limit(limit).all()
    return [RunLogSchema.model_validate(r) for r in runs]


@router.get("/logs")
def get_agent_logs(limit: int = Query(50, ge=1, le=200), session: Session = Depends(get_db)):
    logs = session.query(AgentLog).order_by(AgentLog.created_at.desc()).limit(limit).all()
    return [
        {
            "id": log.id,
            "agent_run_id": log.agent_run_id,
            "level": log.level,
            "message": log.message,
            "created_at": log.created_at,
        }
        for log in logs
    ]


@router.get("/analytics")
def get_analytics(session: Session = Depends(get_db)):
    runs = session.query(RunLog).all()
    durations = [
        (run.run_ended_at - run.run_started_at).total_seconds()
        for run in runs
        if run.run_ended_at and run.run_started_at
    ]
    return {
        "total_agent_runs": len(runs),
        "successful_runs": sum(run.status == "success" for run in runs),
        "failed_runs": sum(run.status in {"failed", "degraded"} for run in runs),
        "average_run_time_seconds": round(sum(durations) / len(durations), 2) if durations else 0,
        "news_processed": sum(run.items_fetched for run in runs),
        "posts_generated": sum(run.posts_published for run in runs),
        "posts_published": session.query(Post).filter(Post.status == "published").count(),
    }
