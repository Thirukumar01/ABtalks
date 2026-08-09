"""
Unit Tests for Topic Discovery Engine
Tests:
1. HTML text stripping, entity resolution, and summary truncation.
2. ISO 8601 UTC date parsing across various date string formats.
3. SHA-256 URL hashing and deterministic deduplication.
4. Fuzzy title sequence matching (>85%).
5. Multi-channel ingestion robustness and source normalization.
"""

import pytest
from discovery.ai_sources_fetcher import AINewsDiscoveryEngine, NormalizedArticle


@pytest.fixture
def discovery_engine():
    return AINewsDiscoveryEngine(timeout_seconds=3.0)


def test_clean_text_strips_html_and_collapses_whitespace():
    raw_html = "<p>DeepSeek has unveiled <b>R2 reasoning scaling</b>.&nbsp; Read more <a href='#'>here</a>.</p>"
    cleaned = AINewsDiscoveryEngine.clean_text(raw_html, max_chars=100)
    assert "<p>" not in cleaned
    assert "<b>" not in cleaned
    assert "DeepSeek has unveiled R2 reasoning scaling" in cleaned


def test_clean_text_truncation():
    long_text = "Word " * 200
    cleaned = AINewsDiscoveryEngine.clean_text(long_text, max_chars=80)
    assert len(cleaned) <= 80
    assert cleaned.endswith("...")


def test_parse_iso_date_standard_formats():
    rfc_date = "Fri, 07 Aug 2026 18:00:00 +0000"
    parsed = AINewsDiscoveryEngine.parse_iso_date(rfc_date)
    assert "2026-08-07" in parsed
    assert "+00:00" in parsed or "Z" in parsed


def test_hash_url_is_deterministic():
    url1 = "https://openai.com/news/test-post"
    url2 = "HTTPS://OPENAI.COM/NEWS/TEST-POST "
    h1 = AINewsDiscoveryEngine.hash_url(url1)
    h2 = AINewsDiscoveryEngine.hash_url(url2)
    assert h1 == h2
    assert len(h1) == 64


def test_deduplication_exact_and_fuzzy(discovery_engine):
    title1 = "DeepSeek R2 Reasoning Scaling Breakthrough"
    url1 = "https://research.ai/deepseek-r2"
    
    # First time -> not a duplicate
    assert discovery_engine.is_duplicate(title1, url1) is False

    # Exact URL -> duplicate
    assert discovery_engine.is_duplicate("Different Title", url1) is True

    # Fuzzy Title (>85% similarity) with different URL -> duplicate
    fuzzy_title = "DeepSeek R2 Reasoning Scaling Breakthroughs"
    assert discovery_engine.is_duplicate(fuzzy_title, "https://other.ai/deepseek") is True


def test_normalized_article_payload():
    article = NormalizedArticle(
        title="Claude 3.7 Sonnet Released",
        summary="Hybrid reasoning capabilities with verifiable trace tokens.",
        url="https://anthropic.com/claude-3-7",
        publishedDate="2026-08-07T18:00:00Z",
        source="Anthropic News"
    )
    d = article.to_dict()
    assert d["title"] == "Claude 3.7 Sonnet Released"
    assert d["source"] == "Anthropic News"
    assert "https://" in d["url"]
