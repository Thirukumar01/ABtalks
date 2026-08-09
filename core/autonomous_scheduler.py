"""
Production-Grade APScheduler Autonomous Workflow
Runs Every 30 Minutes:
1. Discover Topics (Multi-source AI ingestion)
2. Editorial Decision (0-100 multi-factor scoring & audit logging)
3. Generate Post (AI Product Analyst persona synthesis)
4. Store in Database (SQLite WAL mode + strict deduplication)
5. Log Every Decision (Transparent rejection/approval audit trail)
"""

import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

# Import our autonomous pipeline modules
from discovery.ai_sources_fetcher import AINewsDiscoveryEngine
from editorial.editorial_decision_engine import EditorialDecisionEngine
from generation.ai_writing_engine import AIProductAnalystEngine
from memory.sqlite_memory_system import SQLiteMemorySystem

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("AutonomousScheduler")


class AutonomousCycleRunner:
    """Orchestrates the 5-step autonomous cycle with full database persistence."""

    def __init__(self, db_path: str = "data/autonomous_agent.db"):
        self.memory = SQLiteMemorySystem(db_path=db_path)
        self.discovery = AINewsDiscoveryEngine(timeout_seconds=5.0)
        self.writing_engine = AIProductAnalystEngine()

        # Initialize Default Persona if not set
        self._ensure_persona_configured()

    def _ensure_persona_configured(self):
        """Ensures the AI Product Analyst persona preferences are active in SQLite."""
        existing = self.memory.get_active_persona()
        if not existing:
            self.memory.save_persona_preferences(
                persona_name="AI Product Analyst",
                persona_bio="Evaluates frontier AI models, agentic systems, and research through the lens of product strategy and unit economics.",
                topics_of_interest=["LLMs", "Autonomous Agents", "Robotics", "AI Safety", "Reasoning Models", "Open Source AI"],
                tone_traits=["professional", "educational", "opinionated"],
                writing_style_rules=["2-3 short paragraphs", "No emojis", "Cite primary source"],
                banned_topics=["crypto speculation", "token pump", "clickbait", "celebrity gossip"],
                daily_post_cap=10
            )

    def execute_tick(self) -> Dict:
        """
        Executes a single autonomous cycle:
        1. Discover Topics
        2. Editorial Decisions & Audit Logging
        3. Memory-Informed Post Generation
        4. Strict Deduplication & Storage
        """
        run_start = datetime.now(timezone.utc)
        logger.info(f"=== Starting Autonomous Cycle at {run_start.isoformat()} ===")

        persona = self.memory.get_active_persona()
        editorial = EditorialDecisionEngine(
            persona_interests=persona["topics_of_interest"],
            banned_topics=persona["banned_topics"]
        )

        items_fetched = 0
        decisions_evaluated = 0
        posts_published = 0
        error_log = None

        try:
            # ----------------------------------------------------
            # STEP 1: DISCOVER TOPICS
            # ----------------------------------------------------
            discovered_articles = self.discovery.discover_all()
            items_fetched = len(discovered_articles)
            logger.info(f"[Step 1] Ingested {items_fetched} candidate articles from all AI sources.")

            # Load recent publications for novelty comparison
            recent_posts = self.memory.get_recent_posts(limit=20)
            previously_published_titles = [p["title"] for p in recent_posts]

            # ----------------------------------------------------
            # STEP 2: EDITORIAL DECISION & LOG EVERY DECISION
            # ----------------------------------------------------
            for article in discovered_articles:
                eval_result = editorial.evaluate_article(article, previously_published_titles)
                decisions_evaluated += 1

                # If rejected, log immediately to SQLite with full explanation
                if eval_result.decision != "ACCEPT":
                    self.memory.record_rejected_topic(
                        article_title=eval_result.article_title,
                        article_url=eval_result.article_url,
                        reasons=eval_result.reasons,
                        composite_score=eval_result.score,
                        relevance_score=eval_result.breakdown["relevance"],
                        quality_score=eval_result.breakdown["quality"],
                        novelty_score=eval_result.breakdown["novelty"],
                        recency_score=eval_result.breakdown["recency"]
                    )
                    logger.info(f"[Rejected] ({eval_result.score}/100) '{eval_result.article_title[:45]}...': {eval_result.reasons[0]}")
                    continue

                # ----------------------------------------------------
                # STEP 3: GENERATE POST FOR APPROVED TOPIC
                # ----------------------------------------------------
                working_context = self.memory.build_working_memory_context(limit=8)
                analysis_payload = self.writing_engine.generate_analysis(
                    news_item=article,
                    working_memory_context=working_context
                )

                # ----------------------------------------------------
                # STEP 4: STORE IN DATABASE (NEVER PUBLISH DUPLICATES)
                # ----------------------------------------------------
                try:
                    stored_post = self.memory.record_published_post(
                        title=analysis_payload["title"],
                        content=analysis_payload["post"],
                        rationale=analysis_payload["rationale"],
                        source_urls=analysis_payload["sources"]
                    )
                    posts_published += 1
                    logger.info(f"[Published] Post ID [{stored_post['id']}]: '{stored_post['title']}'")
                    # Update local list so subsequent articles in this same cycle don't duplicate
                    previously_published_titles.append(stored_post["title"])
                except ValueError as dup_err:
                    logger.warning(f"[Deduplication Guard] Skipped duplicate post: {dup_err}")

        except Exception as e:
            error_log = str(e)
            logger.error(f"Error during autonomous cycle: {e}", exc_info=True)

        # ----------------------------------------------------
        # STEP 5: LOG CYCLE TELEMETRY
        # ----------------------------------------------------
        run_end = datetime.now(timezone.utc)
        self.memory.log_publishing_cycle(
            run_started_at=run_start,
            run_ended_at=run_end,
            status="error" if error_log else "success",
            items_fetched=items_fetched,
            decisions_evaluated=decisions_evaluated,
            posts_published=posts_published,
            error_log=error_log
        )

        cycle_summary = {
            "status": "error" if error_log else "success",
            "started_at": run_start.isoformat(),
            "duration_seconds": round((run_end - run_start).total_seconds(), 2),
            "items_fetched": items_fetched,
            "decisions_evaluated": decisions_evaluated,
            "posts_published": posts_published,
            "error": error_log
        }
        logger.info(f"=== Autonomous Cycle Complete: {json.dumps(cycle_summary)} ===")
        return cycle_summary


class AutonomousSchedulerManager:
    """Manages the background APScheduler loop configured for 30-minute intervals."""

    def __init__(self, interval_minutes: int = 30, db_path: str = "data/autonomous_agent.db"):
        self.interval_minutes = interval_minutes
        self.runner = AutonomousCycleRunner(db_path=db_path)
        self.scheduler = BackgroundScheduler(timezone="UTC")

    def start(self, run_immediately: bool = True):
        """Starts the background scheduler."""
        trigger = IntervalTrigger(
            minutes=self.interval_minutes,
            timezone="UTC"
        )
        self.scheduler.add_job(
            func=self.runner.execute_tick,
            trigger=trigger,
            id="autonomous_ai_creator_job",
            name="Autonomous 30-Minute AI Creation Loop",
            replace_existing=True,
            max_instances=1,     # Prevent overlapping runs
            coalesce=True,       # Combine missed ticks
            misfire_grace_time=300
        )
        self.scheduler.start()
        logger.info(f"APScheduler armed and running every {self.interval_minutes} minutes.")

        if run_immediately:
            logger.info("Executing initial tick immediately on startup...")
            return self.runner.execute_tick()

    def shutdown(self):
        """Gracefully stops the scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            logger.info("APScheduler stopped.")


# ==========================================
# CLI DEMONSTRATION & TEST HARNESS
# ==========================================
if __name__ == "__main__":
    # Test DB file
    test_db = "data/test_scheduler_memory.db"
    if Path(test_db).exists():
        try:
            Path(test_db).unlink()
        except Exception:
            pass

    print("=" * 80)
    print("TESTING APSCHEDULER 30-MINUTE AUTONOMOUS PIPELINE")
    print("=" * 80)

    # Initialize manager and run 1 tick
    manager = AutonomousSchedulerManager(interval_minutes=30, db_path=test_db)
    summary = manager.start(run_immediately=True)

    # Inspect SQLite database records
    memory_store = SQLiteMemorySystem(db_path=test_db)
    recent_posts = memory_store.get_recent_posts(limit=5)
    rejected = memory_store.get_rejected_topics(limit=5)

    print("\n" + "=" * 80)
    print(f"DATABASE VERIFICATION: {len(recent_posts)} PUBLISHED POSTS STORED")
    print("=" * 80)
    for p in recent_posts:
        print(f"\n[POST ID: {p['id']}] {p['title']}")
        print(f"Content:\n{p['content']}")
        print(f"Rationale: {p['rationale']}")
        print(f"Sources: {p['sources']}")

    print("\n" + "=" * 80)
    print(f"DATABASE VERIFICATION: {len(rejected)} REJECTED AUDIT LOGS STORED")
    print("=" * 80)
    for r in rejected[:3]:
        print(f"\n[REJECTED: {r['composite_score']}/100] {r['title']}")
        print(f"Reason: {r['reasons'][0]}")

    manager.shutdown()
