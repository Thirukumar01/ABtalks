POST_JSON_SCHEMA = {
    "name": "autonomous_post",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "The complete synthesized social post text (150-400 characters, engaging hook, technical context, insightful commentary)."
            },
            "rationale": {
                "type": "string",
                "description": "A 1-2 sentence explanation of why this perspective was chosen and how it serves the audience."
            },
            "sources": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List containing the primary verified source URL of the article."
            }
        },
        "required": ["content", "rationale", "sources"],
        "additionalProperties": False
    }
}


GENERATION_PROMPT_TEMPLATE = """You are preparing a published post for your autonomous feed.

### NEW STORY TO COVER:
- **Title**: {title}
- **Source**: {source} ({source_url})
- **Summary**: {summary}
- **Editorial Rationale for Publication**:
{editorial_rationale}

### CONTEXT & WORKING MEMORY:
{memory_context}

### INSTRUCTIONS:
1. Synthesize an engaging, high-signal post about this news item in your authentic persona voice.
2. Structure: Start with a crisp hook/takeaway, followed by analytical depth, and cite the primary source URL.
3. Keep the content length between 120 and 450 characters (ideal for modern social feeds).
4. Provide a clear rationale explaining why this take was selected.
5. Return strictly the JSON matching the required schema.
"""


def render_generation_prompt(
    item_title: str,
    item_source: str,
    item_source_url: str,
    item_summary: str,
    editorial_rationale: list[str] | str,
    memory_context: str
) -> str:
    """Renders the generation prompt template with all placeholders populated."""
    if isinstance(editorial_rationale, list):
        rat_str = "\n".join(f"- {r}" for r in editorial_rationale)
    else:
        rat_str = str(editorial_rationale)
        
    return GENERATION_PROMPT_TEMPLATE.format(
        title=item_title,
        source=item_source,
        source_url=item_source_url,
        summary=item_summary,
        editorial_rationale=rat_str,
        memory_context=memory_context or "No previous posts in memory (fresh start)."
    )
