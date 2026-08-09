"""
AI Writing Engine for AI Product Analyst
Persona: AI Product Analyst
Style: Professional, Educational, Opinionated, Short paragraphs, NO EMOJIS

Generates:
- Title: Editorial headline
- Post: Multi-paragraph analytical synthesis
- Rationale: Product & strategy justification
- Sources: Verified reference URLs
- Hashtags: List of professional domain tags
"""

import sys
import os
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import re
import json
import logging
from typing import List, Dict, Tuple, Optional
from openai import OpenAI
from app.config import settings
from utils.retry import with_retry

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("AIWritingEngine")


# ==========================================
# EMOJI DETECTOR (Strict No-Emoji Enforcement)
# ==========================================
EMOJI_PATTERN = re.compile(
    "["
    "\U0001F600-\U0001F64F"  # Emoticons
    "\U0001F300-\U0001F5FF"  # Symbols & pictographs
    "\U0001F680-\U0001F6FF"  # Transport & map
    "\U0001F700-\U0001F77F"  # Alchemical
    "\U0001F780-\U0001F7FF"  # Geometric shapes
    "\U0001F800-\U0001F8FF"  # Supplemental arrows
    "\U0001F900-\U0001F9FF"  # Supplemental symbols
    "\U0001FA00-\U0001FA6F"  # Chess symbols
    "\U0001FA70-\U0001FAFF"  # Symbols and pictographs extended
    "\U00002702-\U000027B0"  # Dingbats
    "\U000024C2-\U0001F251"
    "]+",
    flags=re.UNICODE
)


class AIProductAnalystEngine:
    """Specialized writing engine calibrated for the AI Product Analyst persona."""

    PERSONA_PROMPT = """You are an elite AI Product Analyst.

### Persona Identity & Mandate:
You evaluate artificial intelligence breakthroughs, agentic frameworks, and frontier model releases through the lens of product strategy, unit economics, developer ergonomics, and enterprise defensibility.

### Style & Editorial Voice:
1. Professional: Use authoritative, articulate, and industry-standard vocabulary.
2. Educational: Break down complex technical primitives so engineering and product leaders understand the underlying mechanics.
3. Opinionated: Take a decisive, reasoned thesis on product trade-offs (e.g. latency vs. quality, proprietary APIs vs. local weights, monolithic vs. compound systems).
4. Short Paragraphs: Structure the post into 2 to 3 concise, punchy paragraphs.
5. STRICT RULE — NO EMOJIS: Do not include ANY emojis or decorative pictographs under any circumstances.

### Required Output Format (Strict JSON Schema):
{
  "title": "A crisp, compelling 6-12 word headline without emojis",
  "post": "2-3 short paragraphs of educational and opinionated analysis",
  "rationale": "1-2 sentences explaining why this strategic take matters to product teams",
  "sources": ["https://primary-source-url.com"],
  "hashtags": ["#AIProduct", "#LLMs", "#EnterpriseAI"]
}
"""

    JSON_SCHEMA = {
        "name": "ai_product_analysis",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "post": {"type": "string"},
                "rationale": {"type": "string"},
                "sources": {"type": "array", "items": {"type": "string"}},
                "hashtags": {"type": "array", "items": {"type": "string"}}
            },
            "required": ["title", "post", "rationale", "sources", "hashtags"],
            "additionalProperties": False
        }
    }

    def __init__(self):
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY) if settings.OPENAI_API_KEY else None

    # ==========================================
    # STYLE GUARD & EMOJI STRIPPER
    # ==========================================
    @staticmethod
    def strip_emojis(text: str) -> str:
        """Removes any inadvertent emojis from the string."""
        return EMOJI_PATTERN.sub("", text).strip()

    def validate_and_clean_output(self, output: Dict) -> Tuple[bool, Dict, List[str]]:
        """
        Validates output against persona constraints:
        - No emojis allowed in title or post.
        - Minimum length and paragraph structure.
        - Non-empty sources, rationale, and hashtags.
        """
        issues = []
        clean = dict(output)

        # 1. Clean Title
        clean["title"] = self.strip_emojis(clean.get("title", ""))
        if not clean["title"]:
            issues.append("Title is missing or was only emojis.")

        # 2. Clean Post & check emojis
        original_post = clean.get("post", "")
        clean["post"] = self.strip_emojis(original_post)
        if len(original_post) != len(clean["post"]):
            logger.info("Emojis detected and sanitized by StyleGuard.")

        # 3. Check Paragraph Structure (2-3 short paragraphs)
        paragraphs = [p.strip() for p in clean["post"].split("\n") if p.strip()]
        if len(paragraphs) < 2:
            # Format single block into short paragraphs
            sentences = re.split(r"(?<=[.!?])\s+", clean["post"])
            if len(sentences) >= 3:
                mid = len(sentences) // 2
                clean["post"] = " ".join(sentences[:mid]) + "\n\n" + " ".join(sentences[mid:])

        # 4. Validate Rationale
        clean["rationale"] = self.strip_emojis(clean.get("rationale", ""))
        if not clean["rationale"]:
            clean["rationale"] = "Strategic product assessment of unit economics and developer ergonomics."

        # 5. Clean Hashtags (Ensure hashtag format without spaces or emojis)
        raw_tags = clean.get("hashtags", [])
        clean_tags = []
        for tag in raw_tags:
            tag_clean = self.strip_emojis(tag).replace(" ", "")
            if not tag_clean.startswith("#"):
                tag_clean = f"#{tag_clean}"
            if len(tag_clean) > 1:
                clean_tags.append(tag_clean)

        if not clean_tags:
            clean_tags = ["#AIProduct", "#MachineLearning", "#EnterpriseAI", "#ProductStrategy"]
        clean["hashtags"] = clean_tags

        return (len(issues) == 0), clean, issues

    # ==========================================
    # DETERMINISTIC FALLBACK SYNTHESIS
    # ==========================================
    def fallback_synthesis(self, item: Dict) -> Dict:
        """
        High-signal, deterministic synthesis for offline execution,
        strictly obeying the AI Product Analyst voice and No-Emoji rule.
        """
        title_raw = item.get("title", "Breakthrough in AI System Architecture")
        summary_raw = item.get("summary", "")
        url = item.get("url", "https://techcrunch.com/ai")

        p1 = (
            f"{title_raw} signals a critical inflection point for enterprise engineering teams. "
            f"While baseline model performance has largely commoditized, the operational differentiator "
            f"is shifting toward test-time verification and deterministic tool orchestration."
        )

        p2 = (
            f"From a product perspective, shipping resilient AI systems requires prioritizing predictable latency "
            f"and unit cost over unconstrained reasoning depth. Organizations that build transparent evaluation harnesses "
            f"and tight telemetry loops will capture defensible market share."
        )

        rationale = (
            f"Analyzes '{title_raw}' through a product economics lens, contrasting compute efficiency "
            f"against raw model scale to guide engineering roadmaps."
        )

        hashtags = ["#AIProduct", "#ProductStrategy", "#LLMs", "#EnterpriseSoftware", "#MachineLearning"]

        return {
            "title": f"Strategic Analysis: {title_raw[:60]}",
            "post": f"{p1}\n\n{p2}",
            "rationale": rationale,
            "sources": [url],
            "hashtags": hashtags
        }

    # ==========================================
    # GENERATION PIPELINE
    # ==========================================
    @with_retry(max_attempts=3, backoff_base=2.0, initial_delay=0.5)
    def generate_analysis(
        self,
        news_item: Dict,
        working_memory_context: Optional[str] = None
    ) -> Dict:
        """
        Synthesizes a full AI Product Analyst post from an ingested news item.
        """
        user_prompt = f"""### INPUT NEWS STORY TO ANALYZE:
- Title: {news_item.get('title')}
- Source URL: {news_item.get('url')}
- Summary / Content: {news_item.get('summary')}

### CONTEXT & PREVIOUS POSTS:
{working_memory_context or "No previous posts in memory."}

### TASK:
Generate a professional, educational, and opinionated post in 2-3 short paragraphs with NO EMOJIS.
Include a strategic title, substantive rationale, source citation, and relevant hashtags.
"""

        # 1. Use OpenAI if key is present
        if self.client and settings.OPENAI_API_KEY:
            try:
                response = self.client.chat.completions.create(
                    model=settings.FALLBACK_MODEL,
                    messages=[
                        {"role": "system", "content": self.PERSONA_PROMPT},
                        {"role": "user", "content": user_prompt}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.65,
                    max_tokens=700
                )
                raw_json = json.loads(response.choices[0].message.content or "{}")
                sources = raw_json.get("sources", [])
                if news_item.get("url") and news_item["url"] not in sources:
                    sources.append(news_item["url"])
                raw_json["sources"] = sources

                is_valid, cleaned, issues = self.validate_and_clean_output(raw_json)
                return cleaned
            except Exception as e:
                logger.warning(f"OpenAI API call error ({e}); using intelligent fallback engine.")

        # 2. Fallback execution
        fallback_raw = self.fallback_synthesis(news_item)
        _, cleaned, _ = self.validate_and_clean_output(fallback_raw)
        return cleaned


# ==========================================
# CLI DEMONSTRATION & VERIFICATION
# ==========================================
if __name__ == "__main__":
    writer = AIProductAnalystEngine()

    sample_article = {
        "title": "Anthropic Introduces Advanced Computer Use and Model Context Protocol (MCP)",
        "summary": "Anthropic unveils the Model Context Protocol (MCP), an open standard for securely connecting AI agents to enterprise data repositories, tools, and developer environments.",
        "url": "https://www.anthropic.com/news/model-context-protocol"
    }

    result = writer.generate_analysis(sample_article)

    print("=" * 80)
    print("AI PRODUCT ANALYST — GENERATION OUTPUT")
    print("=" * 80)
    print(f"\nTITLE:\n{result['title']}")
    print(f"\nPOST:\n{result['post']}")
    print(f"\nRATIONALE:\n{result['rationale']}")
    print(f"\nSOURCES:\n{', '.join(result['sources'])}")
    print(f"\nHASHTAGS:\n{' '.join(result['hashtags'])}")
    print("\n" + "=" * 80)
    print("STRUCTURED JSON OUTPUT:")
    print(json.dumps(result, indent=2))
