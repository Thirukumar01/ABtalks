"""
Comprehensive Editorial Decision Engine
Evaluates discovered articles against persona interests and historical publications.

Enforces strict rejections for:
1. Advertisements & Sponsored promos
2. Repeated news & Duplicates
3. Low quality / Clickbait content
4. Irrelevant topics
5. Old / Stale news

Outputs:
- Decision: ACCEPT or REJECT
- Score: 0 to 100
- Reason: Comprehensive, human-readable explanatory rationale
"""

import math
import re
import difflib
import json
from datetime import datetime, timezone
from typing import List, Dict, Tuple, Optional


# ==========================================
# REJECTION PATTERNS & HEURISTICS
# ==========================================
ADVERTISEMENT_PATTERNS = [
    r"\bsponsored\b",
    r"\baffiliate\b",
    r"\bdiscount\b",
    r"\bcoupon\b",
    r"\bpromo code\b",
    r"\bbuy now\b",
    r"\blimited time offer\b",
    r"\bpartner content\b",
    r"\bpaid post\b",
    r"\bcrypto pump\b",
    r"\bpresale\b",
    r"\btrading signals\b",
    r"\bcasino\b",
    r"\bbetting\b"
]

CLICKBAIT_PATTERNS = [
    r"you won't believe",
    r"shocking truth",
    r"number \d+ will blow your mind",
    r"secret trick",
    r"doctors hate him",
    r"miracle solution",
    r"viral sensation"
]


class EditorialEvaluationResult:
    """Standardized decision payload for an article."""
    def __init__(
        self,
        article_title: str,
        article_url: str,
        decision: str,  # 'ACCEPT' or 'REJECT'
        score: int,      # 0 to 100
        reasons: List[str],
        breakdown: Dict[str, int]
    ):
        self.article_title = article_title
        self.article_url = article_url
        self.decision = decision
        self.score = score
        self.reasons = reasons
        self.breakdown = breakdown

    def to_dict(self) -> Dict:
        return {
            "title": self.article_title,
            "url": self.article_url,
            "decision": self.decision,
            "score": self.score,
            "reasons": self.reasons,
            "score_breakdown": self.breakdown
        }


class EditorialDecisionEngine:
    """Evaluates candidate news stories and outputs auditable Accept/Reject decisions."""

    # Configurable Scoring Weights
    WEIGHT_RELEVANCE = 0.35
    WEIGHT_QUALITY = 0.25
    WEIGHT_NOVELTY = 0.25
    WEIGHT_RECENCY = 0.15

    ACCEPT_THRESHOLD = 60  # Minimum composite score (0-100) to publish

    def __init__(self, persona_interests: List[str], banned_topics: Optional[List[str]] = None):
        self.persona_interests = [p.lower().strip() for p in persona_interests]
        self.banned_topics = [b.lower().strip() for b in (banned_topics or [])]

    # ==========================================
    # 1. ADVERTISEMENT & QUALITY CHECK
    # ==========================================
    @staticmethod
    def evaluate_quality_and_ads(title: str, summary: str) -> Tuple[int, List[str]]:
        """
        Detects ads, sponsored keywords, clickbait, and stub content.
        Returns: (quality_score_0_to_100, issue_reasons)
        """
        combined = f"{title} {summary}".lower()
        issues = []

        # Check for advertisements & sponsored content
        for pattern in ADVERTISEMENT_PATTERNS:
            if re.search(pattern, combined):
                issues.append(f"REJECT: Detected advertisement/commercial promo pattern ('{pattern}').")
                return 0, issues

        # Check for sensationalist clickbait
        for pattern in CLICKBAIT_PATTERNS:
            if re.search(pattern, combined):
                issues.append("REJECT: Low quality clickbait phrasing detected.")
                return 15, issues

        # Length / Substantiveness check
        if len(summary.strip()) < 40:
            issues.append("REJECT: Low quality stub — summary lacks substantive information.")
            return 25, issues

        # Clean high quality content
        quality_score = 95
        return quality_score, ["High content quality: Substantive technical journalism with zero ad signals."]

    # ==========================================
    # 2. RELEVANCE TO PERSONA INTERESTS
    # ==========================================
    def evaluate_relevance(self, title: str, summary: str) -> Tuple[int, List[str]]:
        """
        Checks alignment against persona interests and flags irrelevant topics or banned keywords.
        Returns: (relevance_score_0_to_100, issue_reasons)
        """
        combined = f"{title} {summary}".lower()
        issues = []

        # Check banned topics first
        for banned in self.banned_topics:
            if banned in combined:
                issues.append(f"REJECT: Contains prohibited topic/keyword ('{banned}') violating persona safety policy.")
                return 0, issues

        # Check overlap with persona topics (including sub-words and root tokens)
        matched_topics = set()
        for interest in self.persona_interests:
            interest_tokens = [tok for tok in re.split(r"\W+", interest) if len(tok) > 2]
            for tok in interest_tokens:
                if tok in combined:
                    matched_topics.add(interest)
                    break

        if not matched_topics:
            issues.append("REJECT: Irrelevant topic — article does not align with persona's core areas of interest.")
            return 10, issues

        # Score based on topic match depth
        matched_list = sorted(list(matched_topics))
        match_ratio = min(1.0, len(matched_list) / max(1, len(self.persona_interests) * 0.4))
        score = int(35 + (65 * match_ratio))
        return score, [f"Strong topic relevance: Aligns with persona interests ({', '.join(matched_list)})."]

    # ==========================================
    # 3. NOVELTY & REPEATED NEWS CHECK
    # ==========================================
    @staticmethod
    def evaluate_novelty(title: str, summary: str, previously_published: List[str]) -> Tuple[int, List[str]]:
        """
        Compares candidate against previously published posts to prevent repeated coverage.
        Returns: (novelty_score_0_to_100, issue_reasons)
        """
        if not previously_published:
            return 100, ["High novelty: Fresh topic, zero prior overlap in publication memory."]

        title_lower = title.lower()
        max_similarity = 0.0

        for prev in previously_published:
            prev_lower = prev.lower()
            # Title sequence similarity
            sim = difflib.SequenceMatcher(None, title_lower, prev_lower).ratio()
            max_similarity = max(max_similarity, sim)

            # Word token overlap
            cand_tokens = set(title_lower.split())
            prev_tokens = set(prev_lower.split())
            if cand_tokens:
                overlap = len(cand_tokens.intersection(prev_tokens)) / len(cand_tokens)
                max_similarity = max(max_similarity, overlap)

        if max_similarity > 0.75:
            return 10, [f"REJECT: Repeated news — highly similar concept already published (similarity: {max_similarity:.2f})."]
        elif max_similarity > 0.50:
            return 45, [f"Moderate novelty: Partially overlaps with recent publication (similarity: {max_similarity:.2f})."]

        return 95, ["High novelty: Distinct story angle not previously covered."]

    # ==========================================
    # 4. RECENCY & AGE CHECK
    # ==========================================
    @staticmethod
    def evaluate_recency(published_date_str: Optional[str]) -> Tuple[int, List[str]]:
        """
        Evaluates article age and penalizes stale news (>48 hours old).
        Returns: (recency_score_0_to_100, issue_reasons)
        """
        if not published_date_str:
            return 70, ["Neutral recency: No publish timestamp provided, assumed recent."]

        try:
            pub_dt = datetime.fromisoformat(published_date_str.replace("Z", "+00:00"))
            if pub_dt.tzinfo is None:
                pub_dt = pub_dt.replace(tzinfo=timezone.utc)
            
            now = datetime.now(timezone.utc)
            age_hours = max(0.0, (now - pub_dt).total_seconds() / 3600.0)

            if age_hours > 72.0:
                return 15, [f"REJECT: Old news — published {age_hours/24:.1f} days ago (>72h stale threshold)."]
            elif age_hours > 48.0:
                return 40, [f"Marginal recency — published {age_hours/24:.1f} days ago."]

            # Exponential decay for breaking news (half-life of 24h)
            recency = int(100 * math.exp(-0.02 * age_hours))
            return max(50, recency), [f"Breaking recency: Published within the last {age_hours:.1f} hours."]
        except Exception:
            return 65, ["Acceptable recency: Standard publication timeframe."]

    # ==========================================
    # MASTER EVALUATION DISPATCHER
    # ==========================================
    def evaluate_article(self, article: Dict, previously_published: List[str]) -> EditorialEvaluationResult:
        """
        Evaluates a single discovered article across all 5 dimensions and returns
        the verdict (ACCEPT/REJECT), integer score (0-100), and explanatory reasons.
        """
        title = article.get("title", "").strip()
        summary = article.get("summary", "").strip()
        url = article.get("url", "")
        pub_date = article.get("publishedDate") or article.get("published_at")

        # 1. Quality & Ad Check
        quality_score, quality_reasons = self.evaluate_quality_and_ads(title, summary)
        
        # 2. Relevance Check
        relevance_score, relevance_reasons = self.evaluate_relevance(title, summary)
        
        # 3. Novelty Check
        novelty_score, novelty_reasons = self.evaluate_novelty(title, summary, previously_published)
        
        # 4. Recency Check
        recency_score, recency_reasons = self.evaluate_recency(pub_date)

        # Composite Score Calculation (0 - 100)
        composite = (
            (self.WEIGHT_RELEVANCE * relevance_score) +
            (self.WEIGHT_QUALITY * quality_score) +
            (self.WEIGHT_NOVELTY * novelty_score) +
            (self.WEIGHT_RECENCY * recency_score)
        )
        final_score = int(round(composite))

        # Check for hard vetoes
        is_advertisement = (quality_score == 0)
        is_clickbait_or_low_quality = (quality_score <= 25)
        is_banned_or_irrelevant = (relevance_score <= 10)
        is_duplicate = (novelty_score <= 45)
        is_old = (recency_score <= 15)

        should_accept = (
            final_score >= self.ACCEPT_THRESHOLD and 
            not is_advertisement and 
            not is_clickbait_or_low_quality and
            not is_banned_or_irrelevant and 
            not is_duplicate and 
            not is_old
        )

        decision = "ACCEPT" if should_accept else "REJECT"

        # Consolidate all explicit reasons
        reasons = []
        if not should_accept:
            if is_advertisement or is_clickbait_or_low_quality:
                reasons.extend(quality_reasons)
            if is_banned_or_irrelevant:
                reasons.extend(relevance_reasons)
            if is_duplicate:
                reasons.extend(novelty_reasons)
            if is_old:
                reasons.extend(recency_reasons)
            if not reasons:
                reasons.append(f"REJECT: Overall composite quality score ({final_score}/100) fell below publishing threshold ({self.ACCEPT_THRESHOLD}/100).")
        else:
            reasons.extend(relevance_reasons)
            reasons.extend(novelty_reasons)
            reasons.extend(quality_reasons)
            reasons.append(f"ACCEPTED: High-signal article scored {final_score}/100 (Threshold: {self.ACCEPT_THRESHOLD}).")

        breakdown = {
            "relevance": relevance_score,
            "quality": quality_score,
            "novelty": novelty_score,
            "recency": recency_score,
            "composite": final_score
        }

        return EditorialEvaluationResult(
            article_title=title,
            article_url=url,
            decision=decision,
            score=final_score,
            reasons=reasons,
            breakdown=breakdown
        )

    def evaluate_batch(self, articles: List[Dict], previously_published: List[str]) -> List[Dict]:
        """Evaluates a full batch of candidate stories and returns structured JSON-ready dictionaries."""
        results = []
        for art in articles:
            eval_res = self.evaluate_article(art, previously_published)
            results.append(eval_res.to_dict())
        return results


# ==========================================
# DEMONSTRATION & TEST HARNESS
# ==========================================
if __name__ == "__main__":
    persona_topics = ["LLMs", "Reasoning Models", "Autonomous Agents", "Robotics", "AI Safety", "Open Source AI"]
    banned_keywords = ["crypto speculation", "token pump", "clickbait", "celebrity gossip"]

    engine = EditorialDecisionEngine(
        persona_interests=persona_topics,
        banned_topics=banned_keywords
    )

    # Historical Memory of Published Posts
    history = [
        "Cloudflare launches Kitesurf, a cloud-hosted browser designed for autonomous AI agents."
    ]

    # Test Candidate Articles (Testing All 6 Acceptance & Rejection Cases)
    test_articles = [
        {
            "title": "DeepSeek R2 Breakthrough: Test-Time Reasoning Scaling Outperforms Monolithic Models",
            "summary": "Researchers demonstrate empirical compute scaling laws during inference that allow 7B models to solve formal mathematical verification problems.",
            "url": "https://research.ai/2026/08/deepseek-r2",
            "publishedDate": "2026-08-07T22:00:00Z"
        },
        {
            "title": "Claim 50% Discount on AI SEO Tools — Limited Time Promo Code Inside!",
            "summary": "Sponsored partner content: Buy now and get exclusive coupon deals on automated social growth bots.",
            "url": "https://promo-deals.com/ai-discount",
            "publishedDate": "2026-08-07T23:00:00Z"
        },
        {
            "title": "Cloudflare Unveils Kitesurf AI Agent Browser",
            "summary": "Cloudflare launches Kitesurf, a cloud-hosted browser designed for autonomous AI agents instead of humans.",
            "url": "https://tech-mirror.com/cloudflare-kitesurf",
            "publishedDate": "2026-08-07T21:00:00Z"
        },
        {
            "title": "Shocking Secrets of Hollywood Celebrities You Won't Believe!",
            "summary": "Short gossip note.",
            "url": "https://gossip-buzz.com/celebrities",
            "publishedDate": "2026-08-07T20:00:00Z"
        },
        {
            "title": "Best Italian Pasta Recipes for Weekend Family Dinners",
            "summary": "A step-by-step culinary guide for cooking authentic handmade fettuccine and marinara sauce.",
            "url": "https://cooking-daily.com/pasta",
            "publishedDate": "2026-08-07T19:00:00Z"
        },
        {
            "title": "Early Neural Network Perceptron Research from 2014",
            "summary": "An archival look at convolutional filter optimization in early computer vision datasets.",
            "url": "https://archives.org/paper-2014",
            "publishedDate": "2024-01-10T12:00:00Z"
        }
    ]

    evaluations = engine.evaluate_batch(test_articles, history)

    print("=" * 80)
    print("EDITORIAL DECISION ENGINE AUDIT REPORT")
    print("=" * 80)

    for idx, res in enumerate(evaluations, 1):
        status_symbol = "[APPROVED]" if res["decision"] == "ACCEPT" else "[REJECTED]"
        print(f"\n[{idx}] {status_symbol} {res['decision']} | Score: {res['score']}/100")
        print(f"    TITLE: {res['title']}")
        print(f"    URL:   {res['url']}")
        print(f"    BREAKDOWN: Rel={res['score_breakdown']['relevance']} | Qual={res['score_breakdown']['quality']} | Nov={res['score_breakdown']['novelty']} | Rec={res['score_breakdown']['recency']}")
        print("    REASONS:")
        for r in res["reasons"]:
            print(f"      - {r}")

    print("\n" + "=" * 80)
    print("Sample Output JSON for First Evaluation:")
    print(json.dumps(evaluations[0], indent=2))
