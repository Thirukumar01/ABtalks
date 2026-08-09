"""
Unit Tests for SQLite Memory System
Tests:
1. Database initialization and SQLite WAL mode activation.
2. Persona preferences and writing style persistence.
3. Published post insertion and SHA-256 duplicate rejection (ValueError).
4. Fuzzy duplicate detection against recent publications.
5. Rejected topics audit log storage with multi-factor scores.
6. LLM working memory context builder.
"""

import pytest
import shutil
from pathlib import Path
from memory.sqlite_memory_system import SQLiteMemorySystem

TEST_DB_PATH = "data/unit_test_memory.db"


@pytest.fixture(autouse=True)
def clean_test_db():
    p = Path(TEST_DB_PATH)
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


@pytest.fixture
def memory_store():
    return SQLiteMemorySystem(db_path=TEST_DB_PATH)


def test_sqlite_wal_mode_and_init(memory_store):
    with memory_store._get_connection() as conn:
        row = conn.execute("PRAGMA journal_mode;").fetchone()
        assert row[0].lower() == "wal"


def test_save_and_get_persona_preferences(memory_store):
    memory_store.save_persona_preferences(
        persona_name="AI Product Analyst",
        persona_bio="Evaluates AI models through product strategy and unit economics.",
        topics_of_interest=["LLMs", "Autonomous Agents", "Robotics"],
        tone_traits=["professional", "educational", "opinionated"],
        writing_style_rules=["2-3 short paragraphs", "No emojis"],
        banned_topics=["crypto speculation", "clickbait"],
        daily_post_cap=8
    )

    persona = memory_store.get_active_persona()
    assert persona is not None
    assert persona["persona_name"] == "AI Product Analyst"
    assert "LLMs" in persona["topics_of_interest"]
    assert "No emojis" in persona["writing_style_rules"]
    assert persona["daily_post_cap"] == 8


def test_record_published_post_and_deduplication(memory_store):
    # Store first post
    post = memory_store.record_published_post(
        title="Anthropic Model Context Protocol Launch",
        content="Anthropic introduces MCP, an open standard connecting AI agents to enterprise tools.",
        rationale="Product analysis of developer ergonomics and agent interoperability.",
        source_urls=["https://anthropic.com/mcp"]
    )
    assert post["id"].startswith("post_")
    assert "Anthropic" in post["title"]

    # Verify retrieval
    recent = memory_store.get_recent_posts(limit=5)
    assert len(recent) == 1
    assert recent[0]["title"] == "Anthropic Model Context Protocol Launch"

    # Attempt exact duplicate -> MUST raise ValueError
    with pytest.raises(ValueError) as excinfo:
        memory_store.record_published_post(
            title="Anthropic Model Context Protocol Launch",
            content="Anthropic introduces MCP, an open standard connecting AI agents to enterprise tools.",
            rationale="Duplicate attempt",
            source_urls=["https://anthropic.com/mcp"]
        )
    assert "duplicate" in str(excinfo.value).lower()


def test_fuzzy_duplicate_post_rejection(memory_store):
    memory_store.record_published_post(
        title="DeepSeek Reasoning Breakthrough Released",
        content="DeepSeek releases new test-time reasoning scaling models for mathematical verification.",
        rationale="High technical impact.",
        source_urls=["https://research.ai/deepseek"]
    )

    # Similar title and content
    with pytest.raises(ValueError) as excinfo:
        memory_store.record_published_post(
            title="DeepSeek Reasoning Breakthrough Released",
            content="DeepSeek releases new test-time reasoning scaling models for verification.",
            rationale="Slightly altered copy",
            source_urls=["https://mirror.ai/deepseek"]
        )
    assert "duplicate" in str(excinfo.value).lower()


def test_record_rejected_topics(memory_store):
    memory_store.record_rejected_topic(
        article_title="Claim 50% Discount on AI Growth Hacks",
        article_url="https://promo.deals/ai",
        reasons=["REJECT: Detected advertisement/commercial promo pattern."],
        composite_score=42,
        relevance_score=10,
        quality_score=0,
        novelty_score=95,
        recency_score=100
    )

    rejected = memory_store.get_rejected_topics(limit=5)
    assert len(rejected) == 1
    assert "Claim 50% Discount" in rejected[0]["title"]
    assert rejected[0]["composite_score"] == 42
    assert "advertisement" in rejected[0]["reasons"][0].lower()


def test_build_working_memory_context(memory_store):
    memory_store.save_persona_preferences(
        persona_name="AI Product Analyst",
        persona_bio="Product strategy analyst.",
        topics_of_interest=["LLMs"],
        tone_traits=["professional"],
        writing_style_rules=["No emojis"],
        banned_topics=["crypto"]
    )
    memory_store.record_published_post(
        title="Post A",
        content="Sample analysis of LLM inference latency.",
        rationale="Product latency rationale.",
        source_urls=["https://example.com/a"]
    )

    ctx = memory_store.build_working_memory_context()
    assert "AI Product Analyst" in ctx
    assert "Sample analysis of LLM inference latency." in ctx
