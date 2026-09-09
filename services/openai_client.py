import json
import logging
import re
from openai import OpenAI
from app.config import settings
from utils.retry import with_retry

logger = logging.getLogger("autonomous_creator.llm")

_client: OpenAI | None = None


def get_openai_client() -> OpenAI | None:
    """Returns singleton OpenAI client instance if API key is present."""
    global _client
    if _client is None and settings.OPENAI_API_KEY:
        _client = OpenAI(api_key=settings.OPENAI_API_KEY)
    return _client


def fallback_synthesizer(system_prompt: str, user_prompt: str, item_title: str = "", item_url: str = "") -> dict:
    """
    Deterministic synthesis fallback for when no OpenAI key is configured
    or when external LLM endpoints are unreachable.
    """
    logger.info("Using grounded local synthesis because no LLM provider is configured.")
    # Extract title from user prompt if available
    title = item_title
    title_match = re.search(r"\*\*Title\*\*:\s*(.+)", user_prompt)
    if title_match:
        title = title_match.group(1).strip()

    source_url = item_url
    source_match = re.search(r"\*\*Source\*\*:\s*.+?\((https?://[^)]+)\)", user_prompt)
    if source_match:
        source_url = source_match.group(1).strip()

    summary_match = re.search(r"\*\*Summary\*\*:\s*(.+)", user_prompt)
    summary = summary_match.group(1).strip() if summary_match else ""

    if not title or not source_url or not summary:
        raise RuntimeError("Cannot synthesize content without verified title, summary, and source.")

    content = f"{title}. {summary} Source: {source_url}"
    
    rationale = (
        f"Grounded only in the discovered source and requires no unsupported factual additions."
    )
    
    return {
        "content": content,
        "rationale": rationale,
        "sources": [source_url]
    }


@with_retry(max_attempts=3, backoff_base=2.0, initial_delay=0.5)
def call_completion(system_prompt: str, user_prompt: str, json_mode: bool = True) -> dict:
    """
    Calls OpenAI Chat Completions API with structured output and fallback resilience.
    """
    client = get_openai_client()
    if not client or not settings.OPENAI_API_KEY:
        return fallback_synthesizer(system_prompt, user_prompt)
        
    try:
        response = client.chat.completions.create(
            model=settings.FALLBACK_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"} if json_mode else None,
            temperature=0.7,
            max_tokens=600
        )
        
        raw_text = response.choices[0].message.content or "{}"
        parsed = json.loads(raw_text)
        
        # Ensure required keys exist
        if "content" not in parsed:
            parsed["content"] = raw_text
        if "rationale" not in parsed:
            parsed["rationale"] = "Synthesized to match persona guidelines."
        if "sources" not in parsed or not isinstance(parsed["sources"], list):
            parsed["sources"] = []
            
        return parsed
    except Exception as e:
        logger.error("OpenAI API call failed: %s", e, exc_info=True)
        raise
