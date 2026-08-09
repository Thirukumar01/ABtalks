import pytest
import uuid
from datetime import datetime, timezone, timedelta
from sqlalchemy import text
from fastapi.testclient import TestClient

from app.main import create_app
from db.database import init_db, get_session
from db.models import AgentConfig, NewsItem, EditorialDecision, Post
from api.schemas import AgentConfigRequest
from discovery.normalizer import normalize
from discovery.dedup import hash_url, is_duplicate, store_new_items
from editorial.scorer import relevance_score, novelty_score, recency_score
from editorial.decision_engine import evaluate
from core.persona import build_persona_prompt
from generation.style_guard import validate
from services.agent_service import init_agent, run_cycle, under_daily_cap


@pytest.fixture(scope="module")
def client():
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


def test_db_init_and_wal():
    """Milestone 2 test: database initialization & WAL mode verification."""
    init_db()
    with get_session() as session:
        mode = session.execute(text("PRAGMA journal_mode;")).scalar()
        assert str(mode).lower() == "wal"


def test_agent_init_and_conflict(client):
    """Milestone 3 test: agent config init and 409 conflict detection."""
    init_db()
    
    payload = {
        "persona_name": "Test Sentinel",
        "persona_bio": "An autonomous AI investigator auditing algorithmic transparency.",
        "topics_of_interest": ["LLMs", "Autonomous Agents"],
        "posting_interval_minutes": 20,
        "tone_traits": ["analytical", "concise"],
        "banned_topics": ["crypto speculation"],
        "daily_post_cap": 8,
        "force_restart": True
    }
    
    # 1. First init should succeed (201)
    res = client.post("/api/agent/init", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert data["persona_name"] == "Test Sentinel"
    assert data["is_active"] is True
    
    # 2. Duplicate init without force_restart should return 409 Conflict
    payload_duplicate = dict(payload)
    payload_duplicate["force_restart"] = False
    res2 = client.post("/api/agent/init", json=payload_duplicate)
    assert res2.status_code == 409


def test_discovery_and_dedup():
    """Milestone 4 & 5 test: normalization and hash deduplication."""
    init_db()
    with get_session() as s:
        s.query(NewsItem).delete()
        s.commit()

    test_id = str(uuid.uuid4())
    raw = {
        "title": f"Novel Investigation of LLMs and Reasoning Transformers in Alpha-Zero Regime {test_id}",
        "url": f"https://techcrunch.com/2026/08/alpha-regime-{test_id}",
        "summary": "<p>A deep dive into <b>reasoning-time</b> compute scaling.</p>",
        "published": "Fri, 07 Aug 2026 12:00:00 GMT"
    }
    
    norm = normalize(raw)
    assert "<p>" not in norm["summary"]
    assert "LLMs" in norm["topic_tags"]
    
    with get_session() as session:
        stored = store_new_items([norm], session)
        session.commit()
        assert stored >= 1
        
        # Second attempt must insert 0 (dedup)
        stored_second = store_new_items([norm], session)
        assert stored_second == 0


def test_editorial_decision_cases():
    """
    Milestone 6 test: 3 fixed cases
    (a) highly relevant + novel -> publish
    (b) duplicate topic to recent post -> reject on novelty
    (c) banned topic -> reject on relevance
    """
    init_db()
    test_id = str(uuid.uuid4())[:8]
    with get_session() as session:
        cfg = AgentConfig(
            persona_name=f"Scorer Persona {test_id}",
            persona_bio="Analytical researcher.",
            topics_of_interest=["LLMs", "Autonomous Agents"],
            banned_topics=["crypto pump", "clickbait"],
            posting_interval_minutes=15,
            is_active=True
        )
        session.add(cfg)
        session.flush()
        
        # Case A: Highly relevant + novel
        url_a = f"https://arxiv.org/abs/2608.{test_id}"
        item_a = NewsItem(
            source="Arxiv",
            source_url=url_a,
            url_hash=hash_url(url_a),
            title=f"Self-Correction in Autonomous Agents via Search Trees {test_id}",
            summary="Novel framework improving autonomous coding agents by 40%.",
            published_at=datetime.now(timezone.utc),
            processed=0
        )
        item_a.topic_tags = ["Autonomous Agents", "LLMs"]
        session.add(item_a)
        session.flush()
        
        dec_a = evaluate(item_a, cfg, session)
        assert dec_a.should_publish is True
        assert dec_a.composite_score >= 0.60
        
        # Seed a post matching item A
        post_a = Post(
            news_item_id=item_a.id,
            content=f"Self-Correction in Autonomous Agents via Search Trees {test_id} published.",
            rationale="Key benchmark.",
            sources=[item_a.source_url],
            status="published"
        )
        session.add(post_a)
        session.flush()
        
        # Case B: Duplicate topic/title to seeded post (reject on novelty)
        url_b = f"https://blog.tech/repeat-story-{test_id}"
        item_b = NewsItem(
            source="Tech Blog",
            source_url=url_b,
            url_hash=hash_url(url_b),
            title=f"Self-Correction in Autonomous Agents via Search Trees {test_id}",
            summary="A repetition of the exact same autonomous coding agent search tree.",
            published_at=datetime.now(timezone.utc),
            processed=0
        )
        item_b.topic_tags = ["Autonomous Agents"]
        session.add(item_b)
        session.flush()
        
        dec_b = evaluate(item_b, cfg, session)
        assert dec_b.novelty_score < 0.50
        
        # Case C: Banned topic (instant reject on relevance = 0.0)
        url_c = f"https://cryptobuzz.xyz/token-pump-{test_id}"
        item_c = NewsItem(
            source="Crypto Buzz",
            source_url=url_c,
            url_hash=hash_url(url_c),
            title=f"Major Crypto Pump and Speculation Opportunities {test_id}",
            summary="Get 100x returns with this viral crypto pump coin.",
            published_at=datetime.now(timezone.utc),
            processed=0
        )
        item_c.topic_tags = ["Finance"]
        session.add(item_c)
        session.flush()
        
        dec_c = evaluate(item_c, cfg, session)
        assert dec_c.relevance_score == 0.0
        assert dec_c.should_publish is False


def test_prompt_rendering():
    """Milestone 7 test: persona prompt rendering verification."""
    cfg = AgentConfig(
        persona_name="Atlas Vance",
        persona_bio="Principal researcher analyzing autonomous systems.",
        topics_of_interest=["Autonomous Agents", "Robotics"],
        tone_traits=["lucid", "evidence-grounded"],
        banned_topics=["crypto speculation"]
    )
    prompt = build_persona_prompt(cfg)
    assert "Atlas Vance" in prompt
    assert "evidence-grounded" in prompt
    assert "crypto speculation" in prompt


def test_generation_and_style_guard():
    """Milestone 9 test: StyleGuard validation & length checks."""
    valid_post = {
        "content": "⚡ New breakthrough: Autonomous coding agents now resolve 88% of repo-level bugs without human intervention. Verified source: https://autosystems.io",
        "rationale": "High-impact developer milestone for agentic systems.",
        "sources": ["https://autosystems.io"]
    }
    is_valid, issues = validate(valid_post)
    assert is_valid is True
    assert len(issues) == 0
    
    # Invalid: Too short
    invalid_post = {
        "content": "Too short.",
        "rationale": "None.",
        "sources": []
    }
    is_valid2, issues2 = validate(invalid_post)
    assert is_valid2 is False


def test_agent_service_cycle():
    """Milestone 10 test: End-to-end run_cycle execution."""
    init_db()
    with get_session() as session:
        result = run_cycle(session)
        assert result["status"] in ["success", "capped", "skipped"]
        assert "items_fetched" in result


def test_api_endpoints(client):
    """Milestone 12 test: /health, /feed, /status, /decisions."""
    # Health check
    res_health = client.get("/health")
    assert res_health.status_code == 200
    assert res_health.json()["status"] == "ok"
    
    # Status endpoint
    res_status = client.get("/api/agent/status")
    assert res_status.status_code == 200
    status_data = res_status.json()
    assert "total_posts_published" in status_data
    
    # Feed endpoint
    res_feed = client.get("/api/agent/feed")
    assert res_feed.status_code == 200
    feed_data = res_feed.json()
    assert "posts" in feed_data
    
    # Decisions endpoint
    res_decisions = client.get("/api/agent/decisions")
    assert res_decisions.status_code == 200
    assert isinstance(res_decisions.json(), list)
