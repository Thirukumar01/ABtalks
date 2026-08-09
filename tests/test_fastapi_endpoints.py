"""
Automated Test Suite for FastAPI Hackathon Endpoints
Tests:
1. POST /api/agent/init -> 201 Created on fresh initialization
2. POST /api/agent/init -> 409 Conflict if already initialized without force_reinit
3. POST /api/agent/init -> 422 Unprocessable Entity on validation failure
4. GET /api/agent/feed -> 200 OK matching hackathon payload schema
5. GET /api/agent/status & /api/agent/decisions -> 200 OK
"""

import pytest
from fastapi.testclient import TestClient
from api.hackathon_api import app

client = TestClient(app)


def test_init_agent_success():
    payload = {
        "persona_name": "AI Product Analyst",
        "persona_bio": "Evaluates frontier AI models, agentic systems, and research through the lens of product strategy.",
        "topics_of_interest": ["LLMs", "Autonomous Agents", "Robotics", "AI Safety"],
        "tone_traits": ["professional", "educational", "opinionated"],
        "writing_style_rules": ["2-3 short paragraphs", "No emojis"],
        "banned_topics": ["crypto speculation", "clickbait"],
        "posting_interval_minutes": 30,
        "daily_post_cap": 10,
        "force_reinit": True
    }
    response = client.post("/api/agent/init", json=payload)
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["persona_name"] == "AI Product Analyst"
    assert "initialized_at" in data


def test_init_agent_conflict_without_force():
    payload = {
        "persona_name": "AI Product Analyst",
        "persona_bio": "Evaluates frontier AI models and research through the lens of product strategy.",
        "topics_of_interest": ["LLMs", "Robotics"],
        "tone_traits": ["professional"],
        "force_reinit": False
    }
    response = client.post("/api/agent/init", json=payload)
    assert response.status_code == 409, response.text


def test_init_agent_validation_error():
    # Empty topics_of_interest list
    payload = {
        "persona_name": "AI Product Analyst",
        "persona_bio": "Too short",
        "topics_of_interest": [],
        "tone_traits": ["professional"]
    }
    response = client.post("/api/agent/init", json=payload)
    assert response.status_code == 422


def test_get_feed_success():
    response = client.get("/api/agent/feed?limit=10")
    assert response.status_code == 200, response.text
    data = response.json()
    assert "status" in data
    assert "total_posts" in data
    assert "posts" in data
    assert isinstance(data["posts"], list)


def test_get_status_and_decisions():
    status_resp = client.get("/api/agent/status")
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == "active"

    decisions_resp = client.get("/api/agent/decisions")
    assert decisions_resp.status_code == 200
    assert "decisions" in decisions_resp.json()
