"""
Production-Grade SQLite Memory System
Persists and manages:
1. Persona Preferences & Writing Style
2. Published Posts (Working Memory & History)
3. Rejected Topics & Guardrail Violations
4. Publishing History & Cycle Telemetry

Features:
- SQLite WAL mode for high concurrency
- SHA-256 Content & URL Deduplication
- Fuzzy Title / Semantic Repetition Prevention
- LLM Working Context Builder
"""

import sqlite3
import hashlib
import difflib
import json
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("SQLiteMemorySystem")


class SQLiteMemorySystem:
    """Complete SQLite-backed memory store for autonomous AI agents."""

    def __init__(self, db_path: str = "data/agent_memory.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()

    def _get_connection(self) -> sqlite3.Connection:
        """Establishes SQLite connection with WAL mode, busy timeout, and row factory."""
        conn = sqlite3.connect(self.db_path, timeout=15.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA busy_timeout = 5000;")
        conn.execute("PRAGMA cache_size = -64000;")
        conn.execute("PRAGMA temp_store = MEMORY;")
        return conn

    # ==========================================
    # 1. DATABASE SCHEMA INITIALIZATION
    # ==========================================
    def _init_database(self):
        """Creates tables and indexes for all memory entities."""
        with self._get_connection() as conn:
            # Table 1: Persona Preferences & Writing Style
            conn.execute("""
            CREATE TABLE IF NOT EXISTS persona_preferences (
                id TEXT PRIMARY KEY,
                persona_name TEXT NOT NULL,
                persona_bio TEXT NOT NULL,
                topics_of_interest TEXT NOT NULL, -- JSON array
                tone_traits TEXT NOT NULL,         -- JSON array
                writing_style_rules TEXT NOT NULL, -- JSON array
                banned_topics TEXT NOT NULL,       -- JSON array
                daily_post_cap INTEGER NOT NULL DEFAULT 10,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """)

            # Table 2: Published Posts
            conn.execute("""
            CREATE TABLE IF NOT EXISTS published_posts (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                content_hash TEXT NOT NULL UNIQUE,
                rationale TEXT NOT NULL,
                source_urls TEXT NOT NULL,         -- JSON array
                status TEXT NOT NULL DEFAULT 'published',
                published_at TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_published_at ON published_posts (published_at DESC);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_content_hash ON published_posts (content_hash);")

            # Table 3: Rejected Topics & Candidate Stories
            conn.execute("""
            CREATE TABLE IF NOT EXISTS rejected_topics (
                id TEXT PRIMARY KEY,
                article_title TEXT NOT NULL,
                article_url TEXT NOT NULL,
                reasons TEXT NOT NULL,             -- JSON array
                composite_score INTEGER NOT NULL,
                relevance_score INTEGER NOT NULL,
                quality_score INTEGER NOT NULL,
                novelty_score INTEGER NOT NULL,
                recency_score INTEGER NOT NULL,
                rejected_at TEXT NOT NULL
            );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_rejected_at ON rejected_topics (rejected_at DESC);")

            # Table 4: Publishing History & Cycle Telemetry
            conn.execute("""
            CREATE TABLE IF NOT EXISTS publishing_history (
                id TEXT PRIMARY KEY,
                run_started_at TEXT NOT NULL,
                run_ended_at TEXT,
                status TEXT NOT NULL,
                items_fetched INTEGER NOT NULL DEFAULT 0,
                decisions_evaluated INTEGER NOT NULL DEFAULT 0,
                posts_published INTEGER NOT NULL DEFAULT 0,
                error_log TEXT
            );
            """)
            conn.commit()
            logger.info(f"SQLite Memory System initialized at {self.db_path} (WAL mode active).")

    # ==========================================
    # 2. DEDUPLICATION UTILITIES
    # ==========================================
    @staticmethod
    def compute_hash(text: str) -> str:
        """Computes deterministic SHA-256 hash of normalized text."""
        normalized = "".join(text.lower().split())
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def is_duplicate_post(self, title: str, content: str, lookback_limit: int = 30) -> Tuple[bool, Optional[str]]:
        """
        Checks if a post is a duplicate via:
        1. Exact content hash match.
        2. SequenceMatcher fuzzy similarity (>80%) against recent published posts.
        """
        c_hash = self.compute_hash(content)
        with self._get_connection() as conn:
            # 1. Exact hash check
            exact = conn.execute("SELECT id FROM published_posts WHERE content_hash = ?", (c_hash,)).fetchone()
            if exact:
                return True, f"Exact duplicate content hash exists (Post ID: {exact['id']})."

            # 2. Fuzzy Title & Content check over recent history
            rows = conn.execute(
                "SELECT id, title, content FROM published_posts ORDER BY published_at DESC LIMIT ?",
                (lookback_limit,)
            ).fetchall()

            for row in rows:
                title_sim = difflib.SequenceMatcher(None, title.lower(), row["title"].lower()).ratio()
                content_sim = difflib.SequenceMatcher(None, content.lower(), row["content"].lower()).ratio()
                
                if title_sim > 0.85:
                    return True, f"Fuzzy title repetition ({title_sim:.2f}) with post ID {row['id']} ('{row['title'][:40]}...')."
                if content_sim > 0.80:
                    return True, f"Fuzzy content repetition ({content_sim:.2f}) with post ID {row['id']}."

        return False, None

    # ==========================================
    # 3. PERSONA PREFERENCES & WRITING STYLE
    # ==========================================
    def save_persona_preferences(
        self,
        persona_name: str,
        persona_bio: str,
        topics_of_interest: List[str],
        tone_traits: List[str],
        writing_style_rules: List[str],
        banned_topics: List[str],
        daily_post_cap: int = 10,
        persona_id: str = "primary_persona"
    ):
        """Stores or updates the agent's persona preferences and writing style."""
        now_str = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            conn.execute("""
            INSERT INTO persona_preferences (
                id, persona_name, persona_bio, topics_of_interest, tone_traits,
                writing_style_rules, banned_topics, daily_post_cap, is_active, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                persona_name = excluded.persona_name,
                persona_bio = excluded.persona_bio,
                topics_of_interest = excluded.topics_of_interest,
                tone_traits = excluded.tone_traits,
                writing_style_rules = excluded.writing_style_rules,
                banned_topics = excluded.banned_topics,
                daily_post_cap = excluded.daily_post_cap,
                updated_at = excluded.updated_at;
            """, (
                persona_id,
                persona_name,
                persona_bio,
                json.dumps(topics_of_interest),
                json.dumps(tone_traits),
                json.dumps(writing_style_rules),
                json.dumps(banned_topics),
                daily_post_cap,
                now_str,
                now_str
            ))
            conn.commit()
            logger.info(f"Persona preferences saved: {persona_name}")

    def get_active_persona(self, persona_id: str = "primary_persona") -> Optional[Dict]:
        """Retrieves the active persona preferences and style configuration."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM persona_preferences WHERE id = ? AND is_active = 1", (persona_id,)).fetchone()
            if not row:
                return None
            return {
                "id": row["id"],
                "persona_name": row["persona_name"],
                "persona_bio": row["persona_bio"],
                "topics_of_interest": json.loads(row["topics_of_interest"]),
                "tone_traits": json.loads(row["tone_traits"]),
                "writing_style_rules": json.loads(row["writing_style_rules"]),
                "banned_topics": json.loads(row["banned_topics"]),
                "daily_post_cap": row["daily_post_cap"]
            }

    # ==========================================
    # 4. PUBLISHED POSTS STORE
    # ==========================================
    def record_published_post(
        self,
        title: str,
        content: str,
        rationale: str,
        source_urls: List[str],
        post_id: Optional[str] = None
    ) -> Dict:
        """
        Validates deduplication and stores a newly published post.
        Raises ValueError if duplicate.
        """
        is_dup, reason = self.is_duplicate_post(title, content)
        if is_dup:
            raise ValueError(f"Cannot save duplicate post: {reason}")

        c_hash = self.compute_hash(content)
        pid = post_id or f"post_{int(datetime.now(timezone.utc).timestamp())}_{c_hash[:8]}"
        now_str = datetime.now(timezone.utc).isoformat()

        with self._get_connection() as conn:
            conn.execute("""
            INSERT INTO published_posts (
                id, title, content, content_hash, rationale, source_urls, status, published_at, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'published', ?, ?);
            """, (
                pid,
                title,
                content,
                c_hash,
                rationale,
                json.dumps(source_urls),
                now_str,
                now_str
            ))
            conn.commit()
            logger.info(f"Published post stored: [{pid}] {title[:40]}...")

        return {
            "id": pid,
            "title": title,
            "content": content,
            "rationale": rationale,
            "sources": source_urls,
            "published_at": now_str
        }

    def get_recent_posts(self, limit: int = 10) -> List[Dict]:
        """Retrieves recent published posts in reverse chronological order."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM published_posts ORDER BY published_at DESC LIMIT ?",
                (limit,)
            ).fetchall()

            return [
                {
                    "id": r["id"],
                    "title": r["title"],
                    "content": r["content"],
                    "rationale": r["rationale"],
                    "sources": json.loads(r["source_urls"]),
                    "published_at": r["published_at"]
                }
                for r in rows
            ]

    # ==========================================
    # 5. REJECTED TOPICS & STORIES STORE
    # ==========================================
    def record_rejected_topic(
        self,
        article_title: str,
        article_url: str,
        reasons: List[str],
        composite_score: int,
        relevance_score: int,
        quality_score: int,
        novelty_score: int,
        recency_score: int,
        rejection_id: Optional[str] = None
    ):
        """Stores a rejected candidate story along with the explicit rationale."""
        rid = rejection_id or f"rej_{int(datetime.now(timezone.utc).timestamp())}_{self.compute_hash(article_url)[:8]}"
        now_str = datetime.now(timezone.utc).isoformat()

        with self._get_connection() as conn:
            conn.execute("""
            INSERT INTO rejected_topics (
                id, article_title, article_url, reasons, composite_score,
                relevance_score, quality_score, novelty_score, recency_score, rejected_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                rid,
                article_title,
                article_url,
                json.dumps(reasons),
                composite_score,
                relevance_score,
                quality_score,
                novelty_score,
                recency_score,
                now_str
            ))
            conn.commit()

    def get_rejected_topics(self, limit: int = 20) -> List[Dict]:
        """Retrieves rejected topic records."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM rejected_topics ORDER BY rejected_at DESC LIMIT ?",
                (limit,)
            ).fetchall()

            return [
                {
                    "id": r["id"],
                    "title": r["article_title"],
                    "url": r["article_url"],
                    "reasons": json.loads(r["reasons"]),
                    "composite_score": r["composite_score"],
                    "scores": {
                        "relevance": r["relevance_score"],
                        "quality": r["quality_score"],
                        "novelty": r["novelty_score"],
                        "recency": r["recency_score"]
                    },
                    "rejected_at": r["rejected_at"]
                }
                for r in rows
            ]

    # ==========================================
    # 6. PUBLISHING HISTORY & TELEMETRY
    # ==========================================
    def log_publishing_cycle(
        self,
        run_started_at: datetime,
        run_ended_at: datetime,
        status: str,
        items_fetched: int,
        decisions_evaluated: int,
        posts_published: int,
        error_log: Optional[str] = None
    ):
        """Records cycle telemetry for autonomous scheduling."""
        rid = f"run_{int(run_started_at.timestamp())}"
        with self._get_connection() as conn:
            conn.execute("""
            INSERT INTO publishing_history (
                id, run_started_at, run_ended_at, status, items_fetched,
                decisions_evaluated, posts_published, error_log
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                rid,
                run_started_at.isoformat(),
                run_ended_at.isoformat(),
                status,
                items_fetched,
                decisions_evaluated,
                posts_published,
                error_log
            ))
            conn.commit()

    # ==========================================
    # 7. LLM WORKING MEMORY & CONTEXT BUILDER
    # ==========================================
    def build_working_memory_context(self, limit: int = 8) -> str:
        """
        Formats recent posts, tone style rules, and persona constraints
        into a unified context block for LLM prompt ingestion.
        """
        persona = self.get_active_persona()
        recent_posts = self.get_recent_posts(limit=limit)

        context_lines = []

        if persona:
            context_lines.append(f"### PERSONA & STYLE GUIDE:")
            context_lines.append(f"Name: {persona['persona_name']}")
            context_lines.append(f"Bio: {persona['persona_bio']}")
            context_lines.append(f"Tone Traits: {', '.join(persona['tone_traits'])}")
            context_lines.append(f"Writing Rules: {', '.join(persona['writing_style_rules'])}")
            context_lines.append(f"Strictly Banned Topics: {', '.join(persona['banned_topics'])}\n")

        context_lines.append("### RECENTLY PUBLISHED POSTS (AVOID REPEATING THESE TAKES):")
        if recent_posts:
            for idx, p in enumerate(recent_posts, 1):
                context_lines.append(f"{idx}. [{p['published_at'][:16]}] {p['content']}")
        else:
            context_lines.append("No previous posts published yet (fresh start).")

        return "\n".join(context_lines)


# ==========================================
# TEST HARNESS & DEMONSTRATION
# ==========================================
if __name__ == "__main__":
    demo_db = Path("data/demo_agent_memory.db")
    if demo_db.exists():
        try:
            demo_db.unlink()
        except Exception:
            pass

    # Initialize Memory System
    memory = SQLiteMemorySystem(db_path=str(demo_db))

    # 1. Save Persona Preferences & Writing Style
    memory.save_persona_preferences(
        persona_name="Dr. Nova Sterling",
        persona_bio="Principal AI Researcher investigating reasoning scaling and agentic systems.",
        topics_of_interest=["LLMs", "Autonomous Agents", "Robotics", "AI Safety"],
        tone_traits=["analytical", "authoritative", "evidence-driven"],
        writing_style_rules=["Punchy 2-sentence hook", "Cite primary URL", "No robotic clichés"],
        banned_topics=["crypto speculation", "clickbait", "unverified rumors"],
        daily_post_cap=10
    )

    # 2. Store Published Posts
    post1 = memory.record_published_post(
        title="DeepSeek R2 Reasoning Scaling Breakthrough",
        content="Empirical scaling breakthrough: DeepSeek R2 proves test-time reasoning scaling enables smaller models to solve formal verification without human intervention.",
        rationale="High technical relevance to reasoning scaling.",
        source_urls=["https://research.ai/2026/08/deepseek-r2"]
    )
    print("\n[OK] Published Post 1 Saved:", post1["id"])

    # 3. Test Deduplication (Attempting Duplicate Post)
    try:
        memory.record_published_post(
            title="DeepSeek R2 Reasoning Scaling Breakthrough",
            content="Empirical scaling breakthrough: DeepSeek R2 proves test-time reasoning scaling enables smaller models to solve formal verification without human intervention.",
            rationale="Duplicate attempt",
            source_urls=["https://research.ai/2026/08/deepseek-r2"]
        )
    except ValueError as e:
        print("\n[OK] Deduplication Blocked Duplicate:", e)

    # 4. Store Rejected Topics
    memory.record_rejected_topic(
        article_title="Claim 50% Discount on AI SEO Tools",
        article_url="https://promo-deals.com/ai-discount",
        reasons=["REJECT: Detected advertisement/commercial promo pattern ('sponsored')."],
        composite_score=42,
        relevance_score=10,
        quality_score=0,
        novelty_score=95,
        recency_score=100
    )
    print("[OK] Rejected Topic Stored.")

    # 5. Build Unified Working Memory Context
    prompt_context = memory.build_working_memory_context()
    print("\n" + "=" * 80)
    print("GENERATED WORKING MEMORY CONTEXT FOR LLM PROMPT:")
    print("=" * 80)
    print(prompt_context)
