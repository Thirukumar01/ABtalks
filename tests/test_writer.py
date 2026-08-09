"""
Unit Tests for AI Writing Engine
Tests:
1. AI Product Analyst persona voice and formatting.
2. Strict NO-EMOJI enforcement and regex stripping.
3. 2-3 Short paragraph structure.
4. Structured payload fields: title, post, rationale, sources, hashtags.
5. Fallback synthesis for offline or zero-API-key execution.
"""

import pytest
from generation.ai_writing_engine import AIProductAnalystEngine, EMOJI_PATTERN


@pytest.fixture
def writer_engine():
    return AIProductAnalystEngine()


def test_emoji_detector_pattern():
    text_with_emojis = "⚡ Breakthrough in AI Agents! 🚀 Great news 🤖"
    assert EMOJI_PATTERN.search(text_with_emojis) is not None

    cleaned = AIProductAnalystEngine.strip_emojis(text_with_emojis)
    assert "⚡" not in cleaned
    assert "🚀" not in cleaned
    assert "🤖" not in cleaned
    assert cleaned == "Breakthrough in AI Agents!  Great news"


def test_validate_and_clean_output_enforces_no_emojis(writer_engine):
    raw_payload = {
        "title": "🚀 Strategic Analysis: Autonomous MCP Primitives",
        "post": "Anthropic unveils the Model Context Protocol. ⚡ This establishes deterministic tool interoperability.\n\nFrom a product perspective, shipping resilient agents requires verifiable execution.",
        "rationale": "Product analysis of developer ergonomics. 💡",
        "sources": ["https://anthropic.com/mcp"],
        "hashtags": ["#AIProduct", "#LLMs 🤖"]
    }

    is_valid, cleaned, issues = writer_engine.validate_and_clean_output(raw_payload)
    assert is_valid is True
    assert "🚀" not in cleaned["title"]
    assert "⚡" not in cleaned["post"]
    assert "💡" not in cleaned["rationale"]
    assert "#LLMs" in cleaned["hashtags"]
    assert "🤖" not in cleaned["hashtags"][1]


def test_short_paragraphs_enforcement(writer_engine):
    single_block_text = (
        "Model Context Protocol represents an open standard for tool orchestration. "
        "Engineering teams can now decouple agent logic from proprietary SDK bindings. "
        "From an enterprise product perspective, this drastically reduces switching costs. "
        "Organizations building compound AI architectures will capture defensible market share."
    )
    raw_payload = {
        "title": "Analysis of Model Context Protocol",
        "post": single_block_text,
        "rationale": "Enterprise architecture analysis.",
        "sources": ["https://anthropic.com/mcp"],
        "hashtags": ["#AIProduct"]
    }

    _, cleaned, _ = writer_engine.validate_and_clean_output(raw_payload)
    paragraphs = [p for p in cleaned["post"].split("\n") if p.strip()]
    assert len(paragraphs) >= 2


def test_fallback_synthesis_structure(writer_engine):
    sample_article = {
        "title": "DeepSeek R2 Reasoning Scaling Analysis",
        "summary": "Evaluation of test-time compute scaling for formal verification.",
        "url": "https://research.ai/deepseek-r2"
    }

    result = writer_engine.fallback_synthesis(sample_article)
    assert "title" in result
    assert "post" in result
    assert "rationale" in result
    assert "sources" in result
    assert "hashtags" in result

    # Check zero emojis in entire output
    full_output_str = f"{result['title']} {result['post']} {result['rationale']} {' '.join(result['hashtags'])}"
    assert EMOJI_PATTERN.search(full_output_str) is None
    assert result["sources"] == ["https://research.ai/deepseek-r2"]
