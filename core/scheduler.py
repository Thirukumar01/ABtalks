import logging
from datetime import datetime, timezone
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from db.database import get_session
from services.agent_service import run_cycle, get_active_config

logger = logging.getLogger("autonomous_creator.scheduler")

_scheduler: BackgroundScheduler | None = None


def safe_run_cycle() -> dict:
    """
    Isolated execution wrapper for scheduled ticks.
    Catches all unexpected exceptions and logs them without crashing the scheduler.
    """
    logger.info("Autonomous scheduler tick executing safe_run_cycle()...")
    try:
        with get_session() as session:
            result = run_cycle(session)
            logger.info(f"Scheduled tick finished with result: {result}")
            return result
    except Exception as e:
        logger.error(f"Scheduler tick exception caught: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}


def start_scheduler(interval_minutes: int = 30) -> BackgroundScheduler:
    """
    Initializes and starts the BackgroundScheduler with an IntervalTrigger.
    """
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        logger.info("Scheduler is already running; updating trigger interval.")
        _scheduler.reschedule_job("agent_cycle_job", trigger=IntervalTrigger(minutes=interval_minutes))
        return _scheduler
        
    _scheduler = BackgroundScheduler(daemon=True)
    _scheduler.add_job(
        func=safe_run_cycle,
        trigger=IntervalTrigger(minutes=interval_minutes),
        id="agent_cycle_job",
        name="Autonomous Agent Content & Editorial Cycle",
        replace_existing=True,
        max_instances=1
    )
    _scheduler.start()
    logger.info(f"APScheduler started successfully (Interval: {interval_minutes} min).")
    return _scheduler


def stop_scheduler() -> None:
    """Gracefully shuts down the background scheduler."""
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("APScheduler stopped.")
        _scheduler = None


def get_scheduler_info() -> dict:
    """Returns runtime scheduler state and next execution timestamp."""
    global _scheduler
    if _scheduler is None or not _scheduler.running:
        return {"running": False, "next_fire_time": None}
        
    job = _scheduler.get_job("agent_cycle_job")
    next_time = job.next_run_time.isoformat() if job and job.next_run_time else None
    return {
        "running": True,
        "next_fire_time": next_time
    }
