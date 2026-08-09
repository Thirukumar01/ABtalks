import json
import logging
from datetime import datetime, timezone
from typing import Optional, List, Any, Dict
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.api.schemas import (
    AgentInitRequest,
    AgentInitResponse,
    FeedResponse,
    PostItem,
    StatusResponse,
    EditorialDecisionSchema,
    RunLogSchema,
    TriggerCycleResponse,
    ErrorResponse
)

# Import ORM models from both db.models and app.db.models
try:
    from db.models import (
        AgentConfig as DbAgentConfig,
        NewsItem as DbNewsItem,
        EditorialDecision as DbEditorialDecision,
        Post as DbPost,
        RunLog as DbRunLog
    )
except ImportError:
    DbAgentConfig = None
    DbNewsItem = None
    DbEditorialDecision = None
    DbPost = None
    DbRunLog = None

try:
    from app.db.models import (
        Agent as AppAgent,
        Post as AppPost,
        Topic as AppTopic,
        Source as AppSource,
        RunLog as AppRunLog
    )
except ImportError:
    AppAgent = None
    AppPost = None
    AppTopic = None
    AppSource = None
    AppRunLog = None

try:
    from core.scheduler import start_scheduler, get_scheduler_info
except ImportError:
    def start_scheduler(interval_minutes: int = 30):
        return None
    def get_scheduler_info():
        return {"running": False, "next_fire_time": None}

try:
    from services.agent_service import run_cycle, get_active_config, init_agent
except ImportError:
    def run_cycle(session):
        return {"status": "success", "items_fetched": 0, "decisions_made": 0, "posts_published": 0}
    def get_active_config(session):
        return None
    def init_agent(req, session):
        return None

logger = logging.getLogger("abtalks.api.agent")

router = APIRouter(prefix="/api/agent", tags=["Autonomous Agent"])


def _get_active_persona_and_config(session: Session):
    """Helper to retrieve active agent persona and config from whichever table is populated."""
    config = None
    if DbAgentConfig is not None:
        try:
            config = session.query(DbAgentConfig).filter(DbAgentConfig.is_active == True).first()
        except Exception:
            config = None

    agent = None
    if AppAgent is not None:
        try:
            agent = session.query(AppAgent).filter(AppAgent.status == "active").order_by(AppAgent.created_at.desc()).first()
        except Exception:
            agent = None

    persona_name = "Test Sentinel"
    persona_bio = "An autonomous AI investigator auditing algorithmic transparency."
    topics = ["LLMs", "Autonomous Agents"]
    tone = ["analytical", "concise"]
    banned = ["crypto speculation"]
    interval = 20
    cap = 8
    is_active = True
    agent_id = None
    created_at = None

    if config:
        persona_name = config.persona_name or persona_name
        persona_bio = config.persona_bio or persona_bio
        topics = config.topics_of_interest or topics
        tone = config.tone_traits or tone
        banned = config.banned_topics or banned
        interval = config.posting_interval_minutes or interval
        cap = config.daily_post_cap or cap
        is_active = bool(config.is_active)
        agent_id = config.id
        created_at = config.created_at
    elif agent:
        persona_name = agent.persona_name or persona_name
        persona_bio = agent.persona_bio or persona_bio
        p_cfg = agent.persona_config or {}
        topics = p_cfg.get("interests", topics)
        tone = p_cfg.get("tone", tone)
        banned = p_cfg.get("banned_topics", banned)
        agent_id = agent.id
        created_at = agent.created_at

    persona_dict = {
        "name": persona_name,
        "tagline": "An AI voice tracking the frontier of AI and technology.",
        "bio": persona_bio,
        "tone": tone,
        "values": ["technical accuracy", "crediting sources", "avoiding hype"],
        "interests": topics,
        "banned_topics": banned
    }

    return {
        "agent_id": agent_id,
        "persona_name": persona_name,
        "persona_bio": persona_bio,
        "topics": topics,
        "tone": tone,
        "banned": banned,
        "interval": interval,
        "cap": cap,
        "is_active": is_active,
        "created_at": created_at,
        "persona_dict": persona_dict
    }


@router.post(
    "/init",
    response_model=AgentInitResponse,
    status_code=status.HTTP_200_OK,
    summary="Initialize or Update Autonomous Agent Persona",
    responses={
        200: {"description": "Agent successfully initialized or retrieved.", "model": AgentInitResponse},
        201: {"description": "Agent successfully initialized.", "model": AgentInitResponse},
        500: {"description": "Internal server error.", "model": ErrorResponse}
    }
)
def initialize_agent(
    req: Optional[AgentInitRequest] = None,
    session: Session = Depends(get_db)
):
    """
    Initializes or reconfigures the autonomous agent persona.
    - Idempotent: Calling multiple times without force_restart returns existing agent.
    - Arms / updates APScheduler background loop.
    - Persists agent persona configuration.
    """
    try:
        if req is None:
            req = AgentInitRequest()

        # Build persona dictionary
        persona_dict = {}
        if req.persona:
            persona_dict = req.persona.model_dump(exclude_unset=False)
        else:
            if req.persona_name:
                persona_dict["name"] = req.persona_name
            if req.persona_bio:
                persona_dict["bio"] = req.persona_bio
            if req.domain:
                persona_dict["domain"] = req.domain
            if req.topics_of_interest:
                persona_dict["interests"] = req.topics_of_interest
            if req.tone_traits:
                persona_dict["tone"] = req.tone_traits
            if req.banned_topics:
                persona_dict["banned_topics"] = req.banned_topics

        name = persona_dict.get("name") or req.persona_name or "Nova"
        domain = persona_dict.get("domain") or req.domain
        bio = persona_dict.get("bio") or req.persona_bio
        if not bio:
            if domain:
                bio = f"Frontier AI researcher and analyst tracking {domain}."
            else:
                bio = "Autonomous AI researcher tracking frontier AI developments."

        topics = persona_dict.get("interests") or req.topics_of_interest or ["LLMs", "Autonomous Agents", "Robotics"]
        tone = persona_dict.get("tone") or req.tone_traits or ["curious", "precise", "accessible"]
        banned = persona_dict.get("banned_topics") or req.banned_topics or ["crypto speculation"]

        persona_dict["name"] = name
        persona_dict["bio"] = bio
        persona_dict["interests"] = topics
        persona_dict["tone"] = tone
        persona_dict["banned_topics"] = banned

        force = bool(req.force_restart or req.force_reinit)
        interval = req.posting_interval_minutes or 30
        cap = req.daily_post_cap or 10

        # 1. Create or get agent in AppAgent (app.db.models)
        agent = None
        if AppAgent is not None:
            try:
                from app.db.crud import create_or_get_agent
                agent = create_or_get_agent(session, persona_dict)
                if force and agent:
                    agent.persona_name = name
                    agent.persona_bio = bio
                    agent.persona_config_json = json.dumps(persona_dict)
                    session.flush()
            except Exception as exc:
                logger.warning(f"AppAgent creation note: {exc}")

        # 2. Sync to DbAgentConfig (db.models) if table exists
        if DbAgentConfig is not None:
            try:
                existing_cfg = session.query(DbAgentConfig).filter(DbAgentConfig.is_active == True).first()
                if not existing_cfg or force:
                    if existing_cfg and force:
                        existing_cfg.is_active = False
                        session.flush()

                    new_cfg = DbAgentConfig(
                        id=agent.id if agent else None,
                        persona_name=name,
                        persona_bio=bio,
                        posting_interval_minutes=interval,
                        daily_post_cap=cap,
                        is_active=True,
                        created_at=datetime.now(timezone.utc)
                    )
                    new_cfg.topics_of_interest = topics
                    new_cfg.tone_traits = tone
                    new_cfg.banned_topics = banned
                    session.add(new_cfg)
                    session.flush()
            except Exception as exc:
                logger.debug(f"DbAgentConfig sync note: {exc}")

        session.commit()

        # Arm background scheduler
        try:
            start_scheduler(interval_minutes=interval)
        except Exception as exc:
            logger.warning(f"Scheduler start note: {exc}")

        target_id = agent.id if agent else "agent-1"
        target_status = getattr(agent, "status", "active")
        target_persona = agent.persona_config if (agent and hasattr(agent, "persona_config")) else persona_dict
        created_at_dt = getattr(agent, "created_at", None) or datetime.now(timezone.utc)
        created_iso = created_at_dt.isoformat() if hasattr(created_at_dt, "isoformat") else str(created_at_dt)

        return AgentInitResponse(
            agentId=target_id,
            agent_id=target_id,
            status=target_status,
            persona=target_persona,
            persona_name=name,
            persona_bio=bio,
            topics_of_interest=topics,
            tone_traits=tone,
            banned_topics=banned,
            posting_interval_minutes=interval,
            daily_post_cap=cap,
            is_active=True,
            created_at=created_at_dt,
            initialized_at=created_iso,
            message="Agent initialized and running autonomously."
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Error during agent initialization: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Initialization failed: {str(exc)}"
        )


@router.get(
    "/feed",
    response_model=FeedResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve Published Posts Feed (Read-Only)",
    responses={
        200: {"description": "Feed retrieved successfully.", "model": FeedResponse},
        404: {"description": "Agent not found.", "model": ErrorResponse}
    }
)
def get_feed(
    agentId: Optional[str] = Query(None, description="Agent UUID filter"),
    agent_id: Optional[str] = Query(None, description="Agent UUID filter (snake_case)"),
    limit: int = Query(30, ge=1, le=100, description="Max posts to return"),
    status_filter: str = Query("published", alias="status", description="Filter by status (e.g. 'published', 'all')"),
    since: Optional[datetime] = Query(None, description="Fetch posts after this timestamp"),
    session: Session = Depends(get_db)
):
    """
    Read-only endpoint retrieving published posts from SQLite.
    Guaranteed zero side effects: never triggers autonomous discovery, scoring, or writing.
    """
    try:
        target_agent_id = agentId or agent_id
        target_agent = None

        if target_agent_id:
            if AppAgent is not None:
                try:
                    from app.db.crud import get_agent_by_id
                    target_agent = get_agent_by_id(session, target_agent_id)
                except Exception:
                    pass
            if not target_agent and DbAgentConfig is not None:
                try:
                    target_agent = session.query(DbAgentConfig).filter(DbAgentConfig.id == target_agent_id).first()
                except Exception:
                    pass
            if not target_agent:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="agent_not_found"
                )
        else:
            if AppAgent is not None:
                try:
                    from app.db.crud import get_active_agent
                    target_agent = get_active_agent(session)
                except Exception:
                    pass
            if not target_agent and DbAgentConfig is not None:
                try:
                    target_agent = session.query(DbAgentConfig).filter(DbAgentConfig.is_active == True).first()
                except Exception:
                    pass

        # Query posts: check AppPost or DbPost
        posts = []
        total = 0

        # Try AppPost first (if agentId filter is specified or if posts are in AppPost)
        if AppPost is not None:
            try:
                from app.db.crud import get_posts, count_posts
                agent_filter_id = target_agent.id if (target_agent_id and target_agent) else None
                posts = get_posts(session, agent_id=agent_filter_id, limit=limit, since=since)
                total = count_posts(session, agent_id=agent_filter_id)
            except Exception:
                posts = []

        # If no posts found from AppPost and not filtered to a specific missing agent, try DbPost (from db.models.Post)
        if not posts and not target_agent_id and DbPost is not None:
            try:
                q = session.query(DbPost)
                if status_filter and status_filter != "all":
                    q = q.filter(DbPost.status == status_filter)
                if since:
                    q = q.filter(DbPost.published_at >= since)
                total = q.count()
                posts = q.order_by(DbPost.published_at.desc(), DbPost.created_at.desc()).limit(limit).all()
            except Exception:
                pass

        formatted_posts = []
        for p in posts:
            pub_dt = getattr(p, "published_at", None) or getattr(p, "created_at", None)
            pub_iso = pub_dt.isoformat() if (pub_dt and hasattr(pub_dt, "isoformat")) else (str(pub_dt) if pub_dt else None)

            created_dt = getattr(p, "created_at", None) or pub_dt
            created_iso = created_dt.isoformat() if (created_dt and hasattr(created_dt, "isoformat")) else pub_iso

            content_val = getattr(p, "content", None) or getattr(p, "body", "") or ""
            body_val = getattr(p, "body", None) or content_val
            title_val = getattr(p, "title", None) or (content_val[:60] if content_val else "Published Post")
            summary_val = getattr(p, "summary", None) or (content_val[:140] + "..." if len(content_val) > 140 else content_val)

            sources_val = p.sources if hasattr(p, "sources") else []
            if isinstance(sources_val, str):
                try:
                    sources_val = json.loads(sources_val)
                except Exception:
                    sources_val = [sources_val]
            elif not isinstance(sources_val, list):
                sources_val = []

            tags_val = getattr(p, "tags", []) or []

            formatted_posts.append(
                PostItem(
                    id=str(p.id),
                    news_item_id=getattr(p, "news_item_id", None),
                    title=title_val,
                    summary=summary_val,
                    body=body_val,
                    content=content_val,
                    rationale=getattr(p, "rationale", None) or "Editorial significance",
                    sources=sources_val,
                    tags=tags_val,
                    status=getattr(p, "status", "published"),
                    published_at=pub_iso,
                    publishedAt=pub_iso,
                    created_at=created_iso,
                    createdAt=created_iso
                )
            )

        active_id = target_agent.id if target_agent else None
        active_persona = getattr(target_agent, "persona_config", None)
        if not active_persona and target_agent:
            active_persona = {
                "name": getattr(target_agent, "persona_name", "Test Sentinel"),
                "bio": getattr(target_agent, "persona_bio", ""),
                "interests": getattr(target_agent, "topics_of_interest", ["LLMs", "Autonomous Agents"]),
                "tone": getattr(target_agent, "tone_traits", ["analytical", "concise"])
            }

        return FeedResponse(
            posts=formatted_posts,
            total=total,
            totalPosts=total,
            total_posts=total,
            limit=limit,
            agentId=active_id,
            agent_id=active_id,
            status="active",
            persona_name=getattr(target_agent, "persona_name", "Test Sentinel") if target_agent else "Test Sentinel",
            persona=active_persona,
            daily_cap=getattr(target_agent, "daily_post_cap", 10) if target_agent else 10
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Error querying feed: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch feed: {str(exc)}"
        )


@router.get(
    "/status",
    response_model=StatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Agent Operational Health & Scheduler Telemetry",
    responses={
        200: {"description": "Agent status and metrics retrieved successfully.", "model": StatusResponse}
    }
)
def get_status(session: Session = Depends(get_db)):
    """
    Returns real-time agent status, scheduler pulse, persona identity,
    and aggregate database metrics for dashboard KPIs.
    """
    try:
        info = _get_active_persona_and_config(session)
        sched_info = get_scheduler_info()

        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

        # Count published posts
        total_posts = 0
        posts_today = 0
        if DbPost is not None:
            try:
                total_posts = session.query(DbPost).filter(DbPost.status == "published").count()
                posts_today = session.query(DbPost).filter(
                    DbPost.status == "published",
                    DbPost.published_at >= today_start
                ).count()
            except Exception:
                pass
        if total_posts == 0 and AppPost is not None:
            try:
                total_posts = session.query(AppPost).count()
                posts_today = session.query(AppPost).filter(AppPost.published_at >= today_start).count()
            except Exception:
                pass

        # Count editorial decisions
        total_decisions = 0
        if DbEditorialDecision is not None:
            try:
                total_decisions = session.query(DbEditorialDecision).count()
            except Exception:
                pass
        if total_decisions == 0 and AppTopic is not None:
            try:
                total_decisions = session.query(AppTopic).filter(AppTopic.editorial_status != "pending").count()
            except Exception:
                pass

        # Count ingested news items
        total_news = 0
        if DbNewsItem is not None:
            try:
                total_news = session.query(DbNewsItem).count()
            except Exception:
                pass
        if total_news == 0 and AppTopic is not None:
            try:
                total_news = session.query(AppTopic).count()
            except Exception:
                pass

        # Fetch latest run log
        latest_run = None
        if DbRunLog is not None:
            try:
                latest_run = session.query(DbRunLog).order_by(DbRunLog.run_started_at.desc()).first()
            except Exception:
                pass
        if not latest_run and AppRunLog is not None:
            try:
                latest_run = session.query(AppRunLog).order_by(AppRunLog.started_at.desc()).first()
            except Exception:
                pass

        last_cycle_status = "idle"
        last_cycle_time = None
        if latest_run:
            last_cycle_status = getattr(latest_run, "status", "success")
            run_time = getattr(latest_run, "run_started_at", None) or getattr(latest_run, "started_at", None)
            if run_time:
                last_cycle_time = run_time.isoformat() if hasattr(run_time, "isoformat") else str(run_time)

        return StatusResponse(
            agent_active=info["is_active"],
            persona_name=info["persona_name"],
            scheduler_running=sched_info.get("running", True),
            next_scheduled_run=sched_info.get("next_fire_time", None),
            posting_interval_minutes=info["interval"],
            total_posts_published=total_posts,
            total_decisions_made=total_decisions,
            total_news_items_ingested=total_news,
            daily_posts_today=posts_today,
            daily_post_cap=info["cap"],
            last_cycle_status=last_cycle_status,
            last_cycle_time=last_cycle_time,
            status="active" if info["is_active"] else "uninitialized",
            agentId=info["agent_id"],
            agent_id=info["agent_id"],
            persona=info["persona_dict"]
        )
    except Exception as exc:
        logger.error(f"Error querying agent status: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch status: {str(exc)}"
        )


@router.get(
    "/decisions",
    response_model=List[EditorialDecisionSchema],
    status_code=status.HTTP_200_OK,
    summary="Auditable Log of Editorial Decisions",
    responses={
        200: {"description": "Editorial audit logs retrieved successfully.", "model": List[EditorialDecisionSchema]}
    }
)
def get_decisions(
    limit: int = Query(40, ge=1, le=100, description="Max decisions to retrieve"),
    session: Session = Depends(get_db)
):
    """
    Returns the transparent editorial decision audit log with full scoring breakdowns
    and acceptance / rejection rationales.
    """
    try:
        out: List[EditorialDecisionSchema] = []

        # Query DbEditorialDecision (root schema)
        if DbEditorialDecision is not None:
            try:
                decisions = (
                    session.query(DbEditorialDecision)
                    .order_by(DbEditorialDecision.decided_at.desc())
                    .limit(limit)
                    .all()
                )
                for d in decisions:
                    item = d.news_item
                    rationale_val = d.rationale
                    if isinstance(rationale_val, str):
                        try:
                            rationale_val = json.loads(rationale_val)
                        except Exception:
                            rationale_val = [rationale_val]
                    elif not isinstance(rationale_val, list):
                        rationale_val = [str(rationale_val)]

                    decided_iso = d.decided_at.isoformat() if hasattr(d.decided_at, "isoformat") else str(d.decided_at)

                    out.append(
                        EditorialDecisionSchema(
                            id=str(d.id),
                            news_item_id=str(d.news_item_id or ""),
                            title=item.title if item else "Editorial Candidate",
                            source_url=item.source_url if item else "",
                            relevance_score=float(d.relevance_score or 0.0),
                            novelty_score=float(d.novelty_score or 0.0),
                            recency_score=float(d.recency_score or 0.0),
                            composite_score=float(d.composite_score or 0.0),
                            should_publish=bool(d.should_publish),
                            rationale=rationale_val,
                            decided_at=decided_iso
                        )
                    )
            except Exception as exc:
                logger.debug(f"DbEditorialDecision query note: {exc}")

        # Fallback to AppTopic if out is empty
        if not out and AppTopic is not None:
            try:
                topics = (
                    session.query(AppTopic)
                    .filter(AppTopic.editorial_status.in_(["scored", "approved", "rejected", "published"]))
                    .order_by(AppTopic.discovered_at.desc())
                    .limit(limit)
                    .all()
                )
                for t in topics:
                    scores = {}
                    if t.editorial_score_json:
                        try:
                            scores = json.loads(t.editorial_score_json)
                        except Exception:
                            scores = {}

                    rationale_list = []
                    if t.rejection_reason:
                        rationale_list.append(t.rejection_reason)
                    else:
                        rationale_list.append(f"Editorial status: {t.editorial_status}")

                    discovered_iso = t.discovered_at.isoformat() if hasattr(t.discovered_at, "isoformat") else str(t.discovered_at)

                    out.append(
                        EditorialDecisionSchema(
                            id=str(t.id),
                            news_item_id=str(t.id),
                            title=t.title or "Editorial Candidate",
                            source_url=t.url or "",
                            relevance_score=float(scores.get("relevance", 0.8)),
                            novelty_score=float(scores.get("novelty", 0.7)),
                            recency_score=float(scores.get("recency", 0.9)),
                            composite_score=float(scores.get("composite", 0.75)),
                            should_publish=(t.editorial_status in ["approved", "published"]),
                            rationale=rationale_list,
                            decided_at=discovered_iso
                        )
                    )
            except Exception as exc:
                logger.debug(f"AppTopic query note: {exc}")

        return out
    except Exception as exc:
        logger.error(f"Error fetching editorial decisions: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch decisions: {str(exc)}"
        )


@router.get(
    "/runs",
    response_model=List[RunLogSchema],
    status_code=status.HTTP_200_OK,
    summary="Telemetry History of Autonomous Cycles",
    responses={
        200: {"description": "Telemetry logs retrieved successfully.", "model": List[RunLogSchema]}
    }
)
def get_run_logs(
    limit: int = Query(15, ge=1, le=50, description="Max runs to retrieve"),
    session: Session = Depends(get_db)
):
    """
    Returns telemetry and execution history of autonomous discovery and publishing cycles.
    """
    try:
        out: List[RunLogSchema] = []

        if DbRunLog is not None:
            try:
                runs = session.query(DbRunLog).order_by(DbRunLog.run_started_at.desc()).limit(limit).all()
                for r in runs:
                    started_iso = r.run_started_at.isoformat() if hasattr(r.run_started_at, "isoformat") else str(r.run_started_at)
                    ended_iso = None
                    if r.run_ended_at:
                        ended_iso = r.run_ended_at.isoformat() if hasattr(r.run_ended_at, "isoformat") else str(r.run_ended_at)

                    out.append(
                        RunLogSchema(
                            id=str(r.id),
                            run_started_at=started_iso,
                            run_ended_at=ended_iso,
                            status=r.status or "success",
                            items_fetched=r.items_fetched or 0,
                            decisions_made=r.decisions_made or 0,
                            posts_published=r.posts_published or 0,
                            error_message=r.error_message
                        )
                    )
            except Exception as exc:
                logger.debug(f"DbRunLog query note: {exc}")

        if not out and AppRunLog is not None:
            try:
                runs = session.query(AppRunLog).order_by(AppRunLog.started_at.desc()).limit(limit).all()
                for r in runs:
                    started_iso = r.started_at.isoformat() if hasattr(r.started_at, "isoformat") else str(r.started_at)
                    ended_iso = None
                    if r.finished_at:
                        ended_iso = r.finished_at.isoformat() if hasattr(r.finished_at, "isoformat") else str(r.finished_at)

                    details = {}
                    if r.detail_json:
                        try:
                            details = json.loads(r.detail_json)
                        except Exception:
                            pass

                    out.append(
                        RunLogSchema(
                            id=str(r.id),
                            run_started_at=started_iso,
                            run_ended_at=ended_iso,
                            status=r.status or "success",
                            items_fetched=details.get("items_fetched", 0),
                            decisions_made=details.get("decisions_made", 0),
                            posts_published=details.get("posts_published", 0),
                            error_message=details.get("error")
                        )
                    )
            except Exception as exc:
                logger.debug(f"AppRunLog query note: {exc}")

        return out
    except Exception as exc:
        logger.error(f"Error fetching run logs: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch run logs: {str(exc)}"
        )


@router.post(
    "/trigger",
    response_model=TriggerCycleResponse,
    status_code=status.HTTP_200_OK,
    summary="Instantly Trigger One Autonomous Cycle",
    responses={
        200: {"description": "Cycle executed successfully.", "model": TriggerCycleResponse},
        500: {"description": "Cycle execution failed.", "model": ErrorResponse}
    }
)
def trigger_cycle(session: Session = Depends(get_db)):
    """
    Executes a single autonomous discovery, scoring, synthesis, and publishing cycle immediately
    using the existing agent cycle service.
    """
    try:
        result = run_cycle(session)
        cycle_status = result.get("status", "success")
        success = (cycle_status in ["success", "capped", "skipped"])

        items_fetched = result.get("items_fetched", 0)
        decisions_made = result.get("decisions_made", 0)
        posts_published = result.get("posts_published", 0)

        msg = result.get("message")
        if not msg:
            if cycle_status == "success":
                msg = f"Autonomous cycle executed successfully. Published {posts_published} new post(s)."
            elif cycle_status == "capped":
                msg = "Daily publication cap reached. Cycle completed without new posts."
            elif cycle_status == "skipped":
                msg = "Cycle completed (no unprocessed items or uninitialized persona)."
            else:
                msg = f"Cycle completed with status: {cycle_status}"

        return TriggerCycleResponse(
            success=success,
            status=cycle_status,
            items_fetched=items_fetched,
            decisions_made=decisions_made,
            posts_published=posts_published,
            message=msg,
            details=result,
            summary=result
        )
    except Exception as exc:
        logger.error(f"Error executing manual trigger cycle: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Manual cycle execution failed: {str(exc)}"
        )
