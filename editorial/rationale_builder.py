from db.models import NewsItem


def build_reasons(
    scores: dict,
    item: NewsItem,
    should_publish: bool,
    banned_detected: bool = False
) -> list[str]:
    """
    Constructs a list of human-readable rationale bullet points explaining the editorial decision.
    """
    reasons: list[str] = []
    rel = scores.get("relevance", 0.0)
    nov = scores.get("novelty", 0.0)
    rec = scores.get("recency", 0.0)
    composite = scores.get("composite", 0.0)

    if banned_detected or rel == 0.0:
        reasons.append("REJECTED: Contains blacklisted keywords or banned topics violating persona safety policy.")
        return reasons

    if should_publish:
        if rel >= 0.70:
            reasons.append(f"High topic relevance ({rel:.2f}) aligning with core persona focus areas: {', '.join(item.topic_tags or ['AI'])}.")
        else:
            reasons.append(f"Sufficient topic alignment ({rel:.2f}) across broader AI & technology themes.")

        if nov >= 0.70:
            reasons.append(f"High novelty ({nov:.2f}): Distinct angle not recently covered in previous publications.")
        else:
            reasons.append(f"Moderate novelty ({nov:.2f}) providing valuable ongoing coverage of this topic.")

        if rec >= 0.70:
            reasons.append(f"Breaking recency ({rec:.2f}): Fresh development discovered within recent hours.")
        else:
            reasons.append(f"Acceptable recency ({rec:.2f}) with evergreen analytical value.")

        reasons.append(f"Approved for synthesis (Composite Score: {composite:.2f} >= threshold 0.60).")
    else:
        # Rejection reasons
        if rel < 0.50:
            reasons.append(f"Low topic relevance ({rel:.2f}): Does not strongly intersect with agent's core topics of interest.")
        if nov < 0.50:
            reasons.append(f"Redundant novelty ({nov:.2f}): Similar stories or concepts have already been published in recent memory.")
        if rec < 0.40:
            reasons.append(f"Stale recency ({rec:.2f}): Item published too long ago to serve as breaking insights.")
        
        reasons.append(f"Rejected: Composite score ({composite:.2f}) fell below minimum publishing threshold (0.60).")

    return reasons
