import difflib
import logging
from typing import Tuple, List

logger = logging.getLogger("autonomous_creator.style_guard")


def validate(
    post_dict: dict,
    recent_posts: list = None,
    banned_topics: list = None
) -> Tuple[bool, List[str]]:
    """
    Validates a generated post against quality, length, safety, and novelty guardrails.
    
    Returns:
        (is_valid, list_of_issues)
    """
    issues: List[str] = []
    content = post_dict.get("content", "").strip()
    rationale = post_dict.get("rationale", "").strip()
    sources = post_dict.get("sources", [])
    
    # 1. Length bounds check (50 - 600 characters)
    if len(content) < 50:
        issues.append(f"Content too short ({len(content)} chars; min 50 required).")
    elif len(content) > 600:
        issues.append(f"Content too long ({len(content)} chars; max 600 permitted).")
        
    # 2. Non-empty rationale
    if not rationale or len(rationale) < 10:
        issues.append("Post must include a non-empty, substantive editorial rationale.")
        
    # 3. Sources check
    if not sources or not isinstance(sources, list) or len(sources) == 0:
        issues.append("Post must contain at least one verifiable source citation.")
        
    # 4. Banned topics check
    if banned_topics:
        content_lower = content.lower()
        for banned in banned_topics:
            if banned.lower() in content_lower:
                issues.append(f"Post contains banned topic or phrase: '{banned}'.")
                
    # 5. Repetition / Overlap check against recent posts
    if recent_posts:
        for prev in recent_posts:
            prev_content = getattr(prev, "content", "")
            ratio = difflib.SequenceMatcher(None, content.lower(), prev_content.lower()).ratio()
            if ratio > 0.80:
                issues.append(f"Post content is too similar ({ratio:.2f}) to recent post ID {getattr(prev, 'id', 'unknown')}.")
                break

    is_valid = (len(issues) == 0)
    if not is_valid:
        logger.warning(f"StyleGuard failed with issues: {issues}")
    else:
        logger.debug("StyleGuard passed all checks successfully.")
        
    return is_valid, issues
