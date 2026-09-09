import logging
import threading
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from db.models import AgentConfig, NewsItem, EditorialDecision, Post, RunLog
from discovery.news_fetcher import fetch_all
from discovery.dedup import store_new_items
from editorial.decision_engine import evaluate
from core.persona import get_active_persona_snapshot
from memory.retrieval import get_memory_context
from memory.summarizer import compact_memory_if_needed
from generation.content_generator import create_post
from api.schemas import AgentConfigRequest
from utils.errors import ConfigConflictError

logger = logging.getLogger("autonomous_creator.service")
_cycle_lock = threading.Lock()


def _log_run_event(session: Session, run_id: str, message: str, level: str = "INFO") -> None:
    from db.models import AgentLog
    session.add(AgentLog(agent_run_id=run_id, level=level, message=message))


def get_active_config(session: Session) -> AgentConfig | None:
    """Fetches the active persona configuration."""
    return session.query(AgentConfig).filter(AgentConfig.is_active == True).first()


def under_daily_cap(session: Session, config: AgentConfig) -> bool:
    """Checks if the agent is still under its daily post publication limit."""
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    published_today = session.query(Post).filter(
        Post.status == "published",
        Post.published_at >= today_start
    ).count()
    
    cap = config.daily_post_cap or 10
    return published_today < cap


def init_agent(config_req: AgentConfigRequest, session: Session) -> AgentConfig:
    """
    Initializes a new persona config. If one exists and force_restart is False,
    raises ConfigConflictError (maps to 409 in API).
    """
    existing = get_active_config(session)
    force = config_req.force_restart or config_req.force_reinit
    if existing and not force:
        raise ConfigConflictError("An active agent persona is already configured.")
        
    if existing and force:
        existing.is_active = False
        session.flush()
        
    new_config = AgentConfig(
        persona_name=config_req.persona_name,
        persona_bio=config_req.persona_bio,
        posting_interval_minutes=config_req.posting_interval_minutes,
        daily_post_cap=config_req.daily_post_cap,
        is_active=config_req.is_active,
        created_at=datetime.now(timezone.utc)
    )
    new_config.topics_of_interest = config_req.topics_of_interest
    new_config.tone_traits = config_req.tone_traits
    new_config.banned_topics = config_req.banned_topics
    
    session.add(new_config)
    session.flush()
    logger.info(f"Agent initialized successfully: {new_config.persona_name} (ID={new_config.id})")
    return new_config


def run_cycle(session: Session) -> dict:
    """
    Executes one complete autonomous tick:
    1. Verify active config & daily cap.
    2. Discovery: Fetch & deduplicate news items.
    3. Editorial: Evaluate unprocessed items and log decisions.
    4. Generation: Synthesize posts for approved items.
    5. Memory: Compact old memory if needed.
    6. Telemetry: Record run stats in RunLog.
    """
    if not _cycle_lock.acquire(blocking=False):
        return {"status": "running", "message": "Agent cycle already running"}

    run_start = datetime.now(timezone.utc)
    config = get_active_config(session)
    
    run_record = RunLog(
        run_started_at=run_start,
        status="in_progress",
        items_fetched=0,
        decisions_made=0,
        posts_published=0
    )
    session.add(run_record)
    session.flush()
    _log_run_event(session, run_record.id, "Agent started")
    
    if not config:
        run_record.status = "skipped_no_config"
        run_record.run_ended_at = datetime.now(timezone.utc)
        _log_run_event(session, run_record.id, "No active persona configured", "WARNING")
        session.flush()
        _cycle_lock.release()
        return {
            "status": "skipped",
            "message": "No active agent configuration found.",
            "items_fetched": 0,
            "decisions_made": 0,
            "posts_published": 0
        }
        
    if not under_daily_cap(session, config):
        logger.info("Daily publication cap reached. Skipping generation this cycle.")
        run_record.status = "capped"
        run_record.run_ended_at = datetime.now(timezone.utc)
        _log_run_event(session, run_record.id, "Daily publication cap reached", "WARNING")
        session.flush()
        _cycle_lock.release()
        return {
            "status": "capped",
            "message": f"Daily post cap of {config.daily_post_cap} reached for today.",
            "items_fetched": 0,
            "decisions_made": 0,
            "posts_published": 0
        }
        
    try:
        # Step 1: Discovery
        raw_items = fetch_all()
        new_stored_count = store_new_items(raw_items, session)
        run_record.items_fetched = len(raw_items)
        _log_run_event(session, run_record.id, f"Discovery found {len(raw_items)} live candidates")
        if not raw_items:
            run_record.status = "degraded"
            run_record.run_ended_at = datetime.now(timezone.utc)
            run_record.error_message = "No live stories were available from configured sources."
            _log_run_event(session, run_record.id, run_record.error_message, "WARNING")
            session.flush()
            _cycle_lock.release()
            return {
                "status": "degraded",
                "message": run_record.error_message,
                "items_fetched": 0,
                "decisions_made": 0,
                "posts_published": 0
            }
        
        # Step 2: Editorial Judgment on unprocessed items
        unprocessed_items = session.query(NewsItem).filter(NewsItem.processed == 0).all()
        decisions_count = 0
        posts_count = 0
        
        for item in unprocessed_items:
            decision = evaluate(item, config, session)
            decisions_count += 1
            
            # Step 3: Synthesis for approved items if still under cap
            if decision.should_publish and under_daily_cap(session, config):
                memory_ctx = get_memory_context(session)
                post = create_post(item, decision, memory_ctx, config, session)
                if post.status == "published":
                    posts_count += 1
                    
            # Mark news item as processed
            item.processed = 1
            session.flush()
            
        # Step 4: Memory compaction
        compact_memory_if_needed(session)
        
        # Step 5: Finalize telemetry
        run_record.decisions_made = decisions_count
        run_record.posts_published = posts_count
        run_record.status = "success"
        run_record.run_ended_at = datetime.now(timezone.utc)
        session.flush()
        _log_run_event(session, run_record.id, "Agent completed")
        _cycle_lock.release()
        
        logger.info(
            f"Autonomous cycle completed: {new_stored_count} new items stored, "
            f"{decisions_count} decisions, {posts_count} posts published."
        )
        
        return {
            "status": "success",
            "items_fetched": run_record.items_fetched,
            "new_items_stored": new_stored_count,
            "decisions_made": decisions_count,
            "posts_published": posts_count,
            "duration_seconds": (run_record.run_ended_at - run_start).total_seconds()
        }
    except Exception as e:
        logger.error(f"Error during autonomous cycle: {e}", exc_info=True)
        run_record.status = "failed"
        run_record.error_message = str(e)
        run_record.run_ended_at = datetime.now(timezone.utc)
        session.flush()
        _log_run_event(session, run_record.id, f"Agent failed: {e}", "ERROR")
        _cycle_lock.release()
        return {
            "status": "failed",
            "error": str(e),
            "items_fetched": run_record.items_fetched,
            "decisions_made": run_record.decisions_made,
            "posts_published": run_record.posts_published
        }
