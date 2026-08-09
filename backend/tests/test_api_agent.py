import pytest
from datetime import datetime, timezone
from app.db.models import Post, Agent


def test_init_agent_exact_spec(client):
    """
    POST /api/agent/init
    Request: { "persona": { "name": "Ada", "domain": "AI Security" } }
    Response: { "agentId": "..." }
    """
    payload = {
        "persona": {
            "name": "Ada",
            "domain": "AI Security"
        }
    }
    response = client.post("/api/agent/init", json=payload)
    assert response.status_code == 200, response.text
    data = response.json()
    assert "agentId" in data
    assert len(data["agentId"]) > 0


def test_init_agent_idempotence(client):
    """
    Calling POST /api/agent/init multiple times must return the existing agentId without duplicating.
    """
    payload = {
        "persona": {
            "name": "Ada",
            "domain": "AI Security"
        }
    }
    res1 = client.post("/api/agent/init", json=payload)
    assert res1.status_code == 200
    agent_id_1 = res1.json()["agentId"]

    res2 = client.post("/api/agent/init", json=payload)
    assert res2.status_code == 200
    agent_id_2 = res2.json()["agentId"]

    assert agent_id_1 == agent_id_2


def test_get_feed_exact_spec(client):
    """
    GET /api/agent/feed?agentId=abc-123
    Response: { "posts": [] }
    """
    # 1. Initialize agent
    init_res = client.post("/api/agent/init", json={"persona": {"name": "Ada", "domain": "AI Security"}})
    agent_id = init_res.json()["agentId"]

    # 2. Query feed
    feed_res = client.get(f"/api/agent/feed?agentId={agent_id}")
    assert feed_res.status_code == 200, feed_res.text
    feed_data = feed_res.json()
    assert "posts" in feed_data
    assert isinstance(feed_data["posts"], list)
    assert len(feed_data["posts"]) == 0


def test_get_feed_agent_not_found(client):
    """
    GET /api/agent/feed with unknown agentId returns 404.
    """
    res = client.get("/api/agent/feed?agentId=non-existent-agent-id-12345")
    assert res.status_code == 404
    data = res.json()
    assert "error" in data or "detail" in data


def test_feed_is_strictly_read_only(client, db_session):
    """
    GET /api/agent/feed must be read-only and never trigger autonomous discovery or create posts.
    """
    init_res = client.post("/api/agent/init", json={"persona": {"name": "Ada", "domain": "AI Security"}})
    agent_id = init_res.json()["agentId"]

    # Query feed multiple times
    for _ in range(5):
        res = client.get(f"/api/agent/feed?agentId={agent_id}")
        assert res.status_code == 200
        assert len(res.json()["posts"]) == 0

    # Ensure DB still has 0 posts
    assert db_session.query(Post).count() == 0


def test_get_feed_with_persisted_post(client, db_session):
    """
    Verifies that when a post exists in SQLite, GET /api/agent/feed returns it accurately.
    """
    init_res = client.post("/api/agent/init", json={"persona": {"name": "Ada", "domain": "AI Security"}})
    agent_id = init_res.json()["agentId"]

    post = Post(
        agent_id=agent_id,
        title="Zero-Trust Architecture for Autonomous Agent Tool Use",
        body="Tool-calling agents require deterministic boundary verification to prevent prompt injection and credential exfiltration.",
        summary="Security analysis of agent tool use.",
        rationale="Critical infrastructure risk mitigation.",
        published_at=datetime.now(timezone.utc)
    )
    post.sources = [{"title": "OWASP Top 10 for LLM", "url": "https://owasp.org/llm", "source_type": "web"}]
    post.tags = ["AI Security", "Agents"]
    db_session.add(post)
    db_session.commit()

    feed_res = client.get(f"/api/agent/feed?agentId={agent_id}")
    assert feed_res.status_code == 200
    feed_data = feed_res.json()
    assert len(feed_data["posts"]) == 1
    p = feed_data["posts"][0]
    assert p["title"] == "Zero-Trust Architecture for Autonomous Agent Tool Use"
    assert p["body"] == "Tool-calling agents require deterministic boundary verification to prevent prompt injection and credential exfiltration."
    assert p["sources"][0]["url"] == "https://owasp.org/llm"


def test_get_status_endpoint(client):
    """
    GET /api/agent/status
    Verifies returned fields match frontend AgentStatus schema.
    """
    res = client.get("/api/agent/status")
    assert res.status_code == 200
    data = res.json()
    assert "agent_active" in data
    assert "persona_name" in data
    assert "scheduler_running" in data
    assert "posting_interval_minutes" in data
    assert "total_posts_published" in data
    assert "total_decisions_made" in data
    assert "total_news_items_ingested" in data
    assert "daily_posts_today" in data
    assert "daily_post_cap" in data


def test_get_decisions_endpoint(client):
    """
    GET /api/agent/decisions?limit=40
    Verifies returned list of editorial decisions.
    """
    res = client.get("/api/agent/decisions?limit=40")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)


def test_get_runs_endpoint(client):
    """
    GET /api/agent/runs?limit=15
    Verifies returned list of execution run logs.
    """
    res = client.get("/api/agent/runs?limit=15")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)


def test_trigger_cycle_endpoint(client):
    """
    POST /api/agent/trigger
    Verifies execution response.
    """
    res = client.post("/api/agent/trigger")
    assert res.status_code == 200
    data = res.json()
    assert "success" in data
    assert "message" in data


def test_health_check(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "healthy"
