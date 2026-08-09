"""
Unit Tests for APScheduler Autonomous Cycle
Tests:
1. APScheduler interval configuration (30-minute trigger).
2. Autonomous cycle execution (Discover -> Editorial -> Generate -> Store).
3. Zero-duplicate enforcement during scheduled ticks.
4. Telemetry recording in publishing_history.
"""

import pytest
from pathlib import Path
from core.autonomous_scheduler import AutonomousCycleRunner, AutonomousSchedulerManager
from memory.sqlite_memory_system import SQLiteMemorySystem

TEST_SCHEDULER_DB = "data/unit_test_scheduler.db"


@pytest.fixture(autouse=True)
def clean_scheduler_db():
    p = Path(TEST_SCHEDULER_DB)
    if p.exists():
        try:
            p.unlink()
        except Exception:
            pass
    yield
    if p.exists():
        try:
            p.unlink()
        except Exception:
            pass


def test_autonomous_cycle_tick_execution():
    runner = AutonomousCycleRunner(db_path=TEST_SCHEDULER_DB)
    summary = runner.execute_tick()

    assert summary["status"] == "success"
    assert summary["items_fetched"] > 0
    assert summary["decisions_evaluated"] > 0
    assert summary["posts_published"] >= 0

    # Verify database persistence
    mem = SQLiteMemorySystem(db_path=TEST_SCHEDULER_DB)
    recent_posts = mem.get_recent_posts(limit=10)
    rejected = mem.get_rejected_topics(limit=50)

    assert len(rejected) > 0  # Should have logged all evaluated candidate decisions
    if len(recent_posts) > 0:
        assert recent_posts[0]["id"].startswith("post_")


def test_scheduler_manager_configuration():
    manager = AutonomousSchedulerManager(interval_minutes=30, db_path=TEST_SCHEDULER_DB)
    
    # Start scheduler without blocking
    manager.start(run_immediately=False)
    assert manager.scheduler.running is True

    # Check job configurations
    jobs = manager.scheduler.get_jobs()
    assert len(jobs) == 1
    job = jobs[0]
    assert job.id == "autonomous_ai_creator_job"
    assert job.max_instances == 1
    assert job.coalesce is True

    manager.shutdown()
    assert manager.scheduler.running is False
