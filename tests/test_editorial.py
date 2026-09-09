"""
Unit Tests for Editorial Decision Engine
Tests:
1. Rejection of Advertisements & Sponsored promo content (Quality = 0).
2. Rejection of sensationalist Clickbait phrasing (Quality = 15).
3. Rejection of Irrelevant Topics outside persona interests (Relevance = 10).
4. Immediate hard veto of Banned / Blacklisted topics (Relevance = 0).
5. Novelty scoring and rejection of repeated news (>75% similarity).
6. Recency decay and rejection of stale news (>72 hours old).
7. Acceptance of high-signal breaking articles (Score >= 60).
"""

import pytest
from datetime import datetime, timezone, timedelta
from editorial.editorial_decision_engine import EditorialDecisionEngine


@pytest.fixture
def editorial_engine():
    persona_topics = ["LLMs", "Autonomous Agents", "Reasoning Models", "Robotics", "AI Safety"]
    banned_keywords = ["crypto speculation", "token pump", "clickbait", "celebrity gossip"]
    return EditorialDecisionEngine(persona_interests=persona_topics, banned_topics=banned_keywords)


def test_rejects_advertisements_and_sponsored_content(editorial_engine):
    ad_article = {
        "title": "Exclusive 50% Discount on AI Agents — Limited Time Promo Code",
        "summary": "Sponsored partner content: buy now and get an affiliate coupon code.",
        "url": "https://deals.xyz/ai-promo",
        "publishedDate": "2026-08-07T18:00:00Z"
    }
    result = editorial_engine.evaluate_article(ad_article, previously_published=[])
    assert result.decision == "REJECT"
    assert result.breakdown["quality"] == 0
    assert any("advertisement" in r.lower() or "promo" in r.lower() for r in result.reasons)


def test_rejects_clickbait_sensationalism(editorial_engine):
    clickbait_article = {
        "title": "Shocking Secrets of AI Startups You Won't Believe!",
        "summary": "Doctors and tech CEOs hate this miracle solution that went viral overnight.",
        "url": "https://viral.news/clickbait",
        "publishedDate": "2026-08-07T18:00:00Z"
    }
    result = editorial_engine.evaluate_article(clickbait_article, previously_published=[])
    assert result.decision == "REJECT"
    assert result.breakdown["quality"] <= 15
    assert any("clickbait" in r.lower() for r in result.reasons)


def test_rejects_banned_topics_immediately(editorial_engine):
    banned_article = {
        "title": "How to Profit from 100x Crypto Speculation and Token Pump Bots",
        "summary": "Automated algorithmic trading for speculative meme tokens on decentralized exchanges.",
        "url": "https://cryptomoon.io/token-pump",
        "publishedDate": "2026-08-07T18:00:00Z"
    }
    result = editorial_engine.evaluate_article(banned_article, previously_published=[])
    assert result.decision == "REJECT"
    assert result.breakdown["relevance"] == 0
    assert any("prohibited" in r.lower() or "banned" in r.lower() for r in result.reasons)


def test_rejects_irrelevant_non_ai_topics(editorial_engine):
    pasta_article = {
        "title": "Authentic Handmade Italian Pasta Recipes for Family Dinner",
        "summary": "Mastering fettuccine alfredo with rich parmesan cheese and garlic butter sauce.",
        "url": "https://cooking.com/pasta",
        "publishedDate": "2026-08-07T18:00:00Z"
    }
    result = editorial_engine.evaluate_article(pasta_article, previously_published=[])
    assert result.decision == "REJECT"
    assert result.breakdown["relevance"] <= 10
    assert any("irrelevant" in r.lower() for r in result.reasons)


def test_rejects_repeated_news_against_memory(editorial_engine):
    published_history = [
        "Cloudflare launches Kitesurf, a cloud-hosted browser designed for autonomous AI agents."
    ]
    repeated_candidate = {
        "title": "Cloudflare launches Kitesurf browser for AI agents",
        "summary": "Cloudflare introduces Kitesurf, a browser built for autonomous AI agents.",
        "url": "https://mirror.com/cloudflare-kitesurf",
        "publishedDate": "2026-08-07T18:00:00Z"
    }
    result = editorial_engine.evaluate_article(repeated_candidate, previously_published=published_history)
    assert result.decision == "REJECT"
    assert result.breakdown["novelty"] <= 45
    assert any("repeated" in r.lower() or "similarity" in r.lower() or "novelty" in r.lower() for r in result.reasons)


def test_rejects_stale_old_news(editorial_engine):
    old_article = {
        "title": "Early Perceptron Neural Networks in Computer Vision",
        "summary": "Historical retrospective on convolutional filter optimization.",
        "url": "https://archives.org/perceptron-2015",
        "publishedDate": "2020-01-01T00:00:00Z"
    }
    result = editorial_engine.evaluate_article(old_article, previously_published=[])
    assert result.decision == "REJECT"
    assert result.breakdown["recency"] <= 15
    assert any("old news" in r.lower() or "stale" in r.lower() for r in result.reasons)


def test_accepts_high_signal_breaking_ai_article(editorial_engine):
    breaking_article = {
        "title": "DeepSeek R2 Breakthrough: Test-Time Reasoning Scaling for Formal Verification",
        "summary": "Empirical benchmarks demonstrate that compute scaling during inference allows 7B models to outperform prior monolithic frontiers.",
        "url": "https://research.ai/deepseek-r2",
        "publishedDate": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    }
    result = editorial_engine.evaluate_article(breaking_article, previously_published=[])
    assert result.decision == "ACCEPT"
    assert result.score >= 60
    assert any("accepted" in r.lower() for r in result.reasons)
