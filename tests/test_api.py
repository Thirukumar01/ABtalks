"""
Unit Tests for FastAPI REST Endpoints
Tests:
1. POST /api/agent/init -> 201 Created on fresh persona configuration.
2. POST /api/agent/init -> 409 Conflict if already active without force_restart.
3. POST /api/agent/init -> 422 Validation Error on invalid payload.
4. GET /api/agent/feed -> 200 OK with formatted published posts.
5. GET /api/agent/status -> 200 OK with agent health metrics.
6. GET /api/agent/decisions -> 200 OK with audited rejection logs.
7. POST /api/agent/trigger -> 200 OK on manual execution.
"""

import pytest
from fastapi.testclient import TestClient
from api.hackathon_api import app

client = TestClient(app)


def test_init_agent_201_created():
    payload = {
        "persona_name": "AI Product Analyst",
        "persona_bio": "Evaluates frontier AI models and reasoning architectures.",
        "topics_of_interest": ["LLMs", "Autonomous Agents", "Robotics"],
        "tone_traits": ["professional", "educational", "opinionated"],
        "writing_style_rules": ["2-3 short paragraphs", "No emojis"],
        "banned_topics": ["crypto speculation", "clickbait"],
        "posting_interval_minutes": 30,
        "daily_post_cap": 10,
        "force_reinit": True
    }
    resp = client.post("/api/agent/init", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["persona_name"] == "AI Product Analyst"
    assert "initialized_at" in data


def test_init_agent_409_conflict():
    payload = {
        "persona_name": "AI Product Analyst",
        "persona_bio": "Evaluates frontier AI models and reasoning architectures.",
        "topics_of_interest": ["LLMs"],
        "tone_traits": ["professional"],
        "force_reinit": False
    }
    resp = client.post("/api/agent/init", json=payload)
    assert resp.status_code == 409


def test_init_agent_422_validation_error():
    # Empty topics_of_interest
    payload = {
        "persona_name": "AI Product Analyst",
        "persona_bio": "Too short",
        "topics_of_interest": [],
        "tone_traits": ["professional"]
    }
    resp = client.post("/api/agent/init", json=payload)
    assert resp.status_code == 422


def test_get_feed_200_ok():
    resp = client.get("/api/agent/feed?limit=10")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "active"
    assert "total_posts" in data
    assert isinstance(data["posts"], list)


def test_get_status_200_ok():
    resp = client.get("/api/agent/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "active"
    assert "total_posts_published" in data


def test_get_decisions_200_ok():
    resp = client.get("/api/agent/decisions")
    assert resp.status_code == 200
    data = resp.json()
    assert "decisions" in data
    assert isinstance(data["decisions"], list)


def test_trigger_cycle_200_ok():
    resp = client.post("/api/agent/trigger")
    assert resp.status_code == 200
    data = resp.json()
    assert "summary" in data
    assert data["summary"]["status"] == "success"
