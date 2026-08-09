import re
import html
from datetime import datetime, timezone
from bs4 import BeautifulSoup


KEYWORD_TOPIC_MAP = {
    "llm": "LLMs",
    "llms": "LLMs",
    "language model": "LLMs",
    "language models": "LLMs",
    "gpt": "LLMs",
    "transformer": "LLMs",
    "transformers": "LLMs",
    "claude": "LLMs",
    "gemini": "LLMs",
    "deepseek": "LLMs",
    "agent": "Autonomous Agents",
    "agents": "Autonomous Agents",
    "agentic": "Autonomous Agents",
    "autonomous": "Autonomous Agents",
    "multimodal": "Multimodal AI",
    "vision": "Computer Vision",
    "robotics": "Robotics",
    "robot": "Robotics",
    "robots": "Robotics",
    "reinforcement learning": "Reinforcement Learning",
    "safety": "AI Safety",
    "alignment": "AI Safety",
    "governance": "AI Safety",
    "open source": "Open Source AI",
    "open weights": "Open Source AI",
    "hardware": "AI Hardware",
    "gpu": "AI Hardware",
    "gpus": "AI Hardware",
    "chip": "AI Hardware",
    "chips": "AI Hardware",
    "nvidia": "AI Hardware"
}


def clean_html(text_content: str) -> str:
    """Strips HTML tags, resolves entities, and collapses redundant whitespace."""
    if not text_content:
        return ""
    # Use BeautifulSoup or regex fallback
    try:
        soup = BeautifulSoup(text_content, "html.parser")
        cleaned = soup.get_text(separator=" ")
    except Exception:
        cleaned = re.sub(r"<[^>]+>", " ", text_content)
    
    cleaned = html.unescape(cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def extract_topic_tags(title: str, summary: str) -> list[str]:
    """Derives structured topic tags from title and summary content."""
    combined_text = f"{title.lower()} {summary.lower()}"
    tags = set()
    for keyword, tag_name in KEYWORD_TOPIC_MAP.items():
        if re.search(rf"\b{re.escape(keyword)}\b", combined_text):
            tags.add(tag_name)
    
    if not tags:
        tags.add("General AI & Tech")
    return sorted(list(tags))


def parse_datetime(date_str: str | datetime | None) -> datetime:
    """Safely converts various date string representations to UTC datetime."""
    if isinstance(date_str, datetime):
        if date_str.tzinfo is None:
            return date_str.replace(tzinfo=timezone.utc)
        return date_str.astimezone(timezone.utc)
    
    if not date_str:
        return datetime.now(timezone.utc)
    
    formats = [
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S %Z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d"
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(str(date_str).strip(), fmt)
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            continue
    
    return datetime.now(timezone.utc)


def normalize(raw_item: dict) -> dict:
    """
    Normalizes a raw news dictionary into a uniform schema.
    
    Args:
        raw_item: dict with raw source keys (title, link/url, summary/description, published, etc.)
    
    Returns:
        Clean normalized dictionary ready for dedup and persistence.
    """
    title = clean_html(raw_item.get("title", ""))
    summary = clean_html(
        raw_item.get("summary") or 
        raw_item.get("description") or 
        raw_item.get("content") or 
        title
    )
    
    # Truncate summary to max 600 chars for efficient processing
    if len(summary) > 600:
        summary = summary[:597].rsplit(" ", 1)[0] + "..."
    
    source_url = raw_item.get("url") or raw_item.get("link") or ""
    source = raw_item.get("source") or "Web Discovery"
    published_at = parse_datetime(raw_item.get("published_at") or raw_item.get("published"))
    topic_tags = extract_topic_tags(title, summary)
    
    return {
        "source": source,
        "source_url": source_url,
        "title": title,
        "summary": summary,
        "topic_tags": topic_tags,
        "published_at": published_at
    }
