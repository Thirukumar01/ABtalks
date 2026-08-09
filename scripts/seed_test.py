import os
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import datetime, timezone
from sqlalchemy import text
from db.database import init_db, get_session
from db.models import AgentConfig, NewsItem, EditorialDecision, Post, MemorySummary, RunLog


def run_db_verification():
    print("Initializing Database...")
    init_db()
    
    test_id = str(uuid.uuid4())[:8]
    with get_session() as session:
        # 1. Verify PRAGMA journal_mode is WAL
        result = session.execute(text("PRAGMA journal_mode;")).scalar()
        print(f"PRAGMA journal_mode: {result}")
        assert str(result).lower() == "wal", f"Expected WAL mode, got {result}"

        # 2. Insert dummy rows into all 6 tables
        agent_cfg = AgentConfig(
            persona_name=f"Tech Sentinel {test_id}",
            persona_bio="Autonomous analyst tracking open weights AI models.",
            topics_of_interest=["LLMs", "Autonomous Agents", "Open Source AI"],
            posting_interval_minutes=30,
            tone_traits=["analytical", "concise", "evidence-driven"],
            banned_topics=["crypto speculation", "clickbait"],
            daily_post_cap=10
        )
        session.add(agent_cfg)
        session.flush()
        print(f"[OK] AgentConfig inserted with ID: {agent_cfg.id}")

        news_item = NewsItem(
            source="TechCrunch",
            source_url=f"https://techcrunch.com/2026/08/07/ai-agent-breakthrough-{test_id}",
            url_hash=f"hash_dummy_test_{test_id}",
            title="Next-Gen Autonomous Agent Architecture Released",
            summary="Researchers introduce a 24-hour self-healing autonomous pipeline.",
            topic_tags=["Autonomous Agents", "AI"],
            published_at=datetime.now(timezone.utc),
            processed=0
        )
        session.add(news_item)
        session.flush()
        print(f"[OK] NewsItem inserted with ID: {news_item.id}")

        decision = EditorialDecision(
            news_item_id=news_item.id,
            relevance_score=0.92,
            novelty_score=0.88,
            recency_score=0.95,
            composite_score=0.91,
            should_publish=True,
            rationale=["High relevance to Autonomous Agents", "Novel architectural pattern", "Published within last 2 hours"]
        )
        session.add(decision)
        session.flush()
        print(f"[OK] EditorialDecision inserted with ID: {decision.id}")

        post = Post(
            news_item_id=news_item.id,
            content="🚀 New autonomous agent architecture achieves full self-directed editorial synthesis with zero human in the loop.",
            rationale="Key milestone for agentic systems.",
            sources=["https://techcrunch.com/2026/08/07/ai-agent-breakthrough"],
            status="published"
        )
        session.add(post)
        session.flush()
        print(f"[OK] Post inserted with ID: {post.id}")

        summary = MemorySummary(
            summary_text="Autonomous AI creator pipelines and decentralized reasoning benchmarks gained high traction.",
            post_count_covered=1,
            start_date=datetime.now(timezone.utc),
            end_date=datetime.now(timezone.utc)
        )
        session.add(summary)
        session.flush()
        print(f"[OK] MemorySummary inserted with ID: {summary.id}")

        run_log = RunLog(
            status="success",
            items_fetched=5,
            decisions_made=5,
            posts_published=1
        )
        session.add(run_log)
        session.flush()
        print(f"[OK] RunLog inserted with ID: {run_log.id}")

    print("All 6 tables verified and functioning properly!")


if __name__ == "__main__":
    run_db_verification()
