# Autonomous AI Creator — Technical Architecture Document

**Project:** ABTalks Hackathon — Autonomous AI Creator  
**Audience:** AI coding agent implementing this system  
**Status:** Architecture spec only — no application code included  

---

## 0. Design Philosophy & Non-Negotiable Constraints

1. **Single initialization, infinite autonomy.** `POST /api/agent/init` is called exactly once. From that moment, the system must run entirely on its own — topic discovery, editorial decisions, writing, and publishing — for the full ~48 hour evaluation window, driven only by an internal scheduler (APScheduler), never by inbound API traffic.
2. **`GET /api/agent/feed` is read-only.** It must never trigger generation, discovery, or scheduling side-effects. It only queries what already exists in the database. This is critical: if feed-polling accidentally becomes the trigger for work, the agent looks "autonomous" only when polled, which fails the spirit of the requirement and risks race conditions/duplicate posts under concurrent polling.
3. **Process durability > elegance.** A hackathon deployment will likely run as a single long-lived process (or a small number of processes) for 48 hours unattended. The architecture must tolerate: LLM API failures, RSS feed timeouts, rate limits, transient crashes, and DB locking — without a human touching it.
4. **Everything the agent publishes must be explainable.** Every post carries its rationale and its sources, stored as structured data, not just prose.
5. **Idempotent init.** Calling `init` a second time (evaluator retry, network hiccup) must not create a second competing scheduler or duplicate persona — it must detect existing state and no-op (or return the existing agent), never fork parallel autonomous loops.

---

## 1. Project Folder Structure

```
autonomous-ai-creator/
├── app/
│   ├── main.py                      # FastAPI app factory, startup/shutdown hooks
│   ├── config.py                    # Settings via pydantic-settings (.env driven)
│   ├── dependencies.py              # FastAPI dependency-injection helpers (DB session, etc.)
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── router.py                 # Aggregates routers, mounted in main.py
│   │   ├── routes_agent.py           # POST /api/agent/init, GET /api/agent/feed
│   │   └── schemas.py                # Pydantic request/response models (API contract only)
│   │
│   ├── db/
│   │   ├── __init__.py
│   │   ├── base.py                   # SQLAlchemy declarative base, engine, session factory
│   │   ├── models.py                 # ORM models (Agent, Topic, Post, Source, RunLog, etc.)
│   │   └── crud.py                   # DB access functions (no business logic)
│   │
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── lifecycle.py              # init_agent(), boot_scheduler(), shutdown handling
│   │   ├── persona.py                # Persona definition, persona prompt builder
│   │   ├── orchestrator.py           # The "tick" function run every scheduler cycle
│   │   ├── discovery/
│   │   │   ├── __init__.py
│   │   │   ├── base.py               # DiscoverySource interface (abstract)
│   │   │   ├── rss_source.py         # RSS feed fetcher/parser
│   │   │   ├── hackernews_source.py  # HN Firebase API client
│   │   │   ├── github_source.py      # GitHub trending / releases / search API client
│   │   │   ├── blogs_source.py       # Official AI company blogs (curated RSS/Atom list)
│   │   │   └── aggregator.py         # Merges + normalizes all sources into Topic candidates
│   │   ├── editorial/
│   │   │   ├── __init__.py
│   │   │   ├── scorer.py             # LLM-based relevance/quality/novelty scoring
│   │   │   ├── dedup.py              # Duplicate/near-duplicate detection
│   │   │   └── policy.py             # Publish/reject thresholds, rate limits, quotas
│   │   ├── writer/
│   │   │   ├── __init__.py
│   │   │   ├── prompts.py            # Prompt templates (persona + topic + sources -> post)
│   │   │   ├── generator.py          # Calls LLM, parses structured JSON output
│   │   │   └── validator.py          # Post-generation QA (length, banned content, JSON shape)
│   │   ├── memory/
│   │   │   ├── __init__.py
│   │   │   ├── store.py              # Read/write interface over Post/Topic history
│   │   │   └── embeddings.py         # Optional: embedding-based semantic similarity for memory
│   │   └── scheduler/
│   │       ├── __init__.py
│   │       └── jobs.py               # APScheduler job definitions & registration
│   │
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── client.py                 # Thin wrapper around LLM API (retries, timeouts)
│   │   └── json_mode.py              # Structured-output helpers, JSON schema validation
│   │
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── logging.py                # Structured logging config
│   │   ├── hashing.py                # Content hashing/fingerprinting for dedup
│   │   ├── retry.py                  # Generic retry/backoff decorator
│   │   └── time.py                   # Timezone-safe time helpers
│   │
│   └── static/                       # (only if serving a minimal bundled frontend)
│       ├── index.html
│       ├── app.js
│       └── styles.css
│
├── tests/
│   ├── conftest.py
│   ├── test_api_agent.py
│   ├── test_discovery.py
│   ├── test_editorial.py
│   ├── test_writer.py
│   ├── test_dedup.py
│   ├── test_scheduler.py
│   └── fixtures/
│       ├── sample_rss.xml
│       ├── sample_hn.json
│       └── sample_github.json
│
├── data/
│   └── agent.db                      # SQLite file (gitignored, created at runtime)
│
├── scripts/
│   ├── run_dev.sh                    # Uvicorn dev server launcher
│   ├── seed_sources.py                # Seed default RSS/blog source list into DB
│   └── simulate_48h.py                # Time-compressed local simulation for testing
│
├── .env.example
├── requirements.txt
├── pyproject.toml
├── README.md
└── ARCHITECTURE.md                    # This document
```

**Rationale for structure:** `agent/` is intentionally separated from `api/` — the API layer is a thin, mostly-read surface, while `agent/` contains all autonomous logic. This mirrors the constraint that the API must not be the thing driving behavior.

---

## 2. Backend Architecture

### 2.1 Process Model
- Single FastAPI process (Uvicorn) hosts both the HTTP API **and** an in-process APScheduler instance (`AsyncIOScheduler` or `BackgroundScheduler` running in a thread pool).
- On process startup (`@app.on_event("startup")` / lifespan handler), the app checks the DB: if an agent already exists and was previously initialized, it **re-attaches** the scheduler to that agent (recovers from a crash/restart mid-evaluation) rather than waiting for another `init` call. This is essential for 48-hour reliability — a restart must not require human re-initialization.
- `init` is the only thing that can *create* an agent + start the scheduler for the first time; subsequent process restarts *resume* it automatically from persisted state.

### 2.2 Layering
```
HTTP Layer (FastAPI routes, Pydantic schemas)
        ↓
Orchestration Layer (agent/orchestrator.py — the "tick")
        ↓
Domain Services (discovery, editorial, writer, memory, persona)
        ↓
Data Access Layer (db/crud.py)
        ↓
SQLite (via SQLAlchemy ORM)
```
- Routes never talk to SQLAlchemy directly — always through `crud.py`. This keeps the read-only feed endpoint provably free of side effects (easy to audit: it only calls `crud.get_*` functions).
- The orchestrator is the only module allowed to call discovery, editorial, and writer services in sequence — it's the "brain loop."

### 2.3 Configuration
- `pydantic-settings` reads from `.env`: `LLM_API_KEY`, `LLM_MODEL`, `DATABASE_URL`, `PUBLISH_INTERVAL_MINUTES`, `MAX_POSTS_PER_DAY`, `MIN_POSTS_PER_DAY`, `DISCOVERY_INTERVAL_MINUTES`, `TIMEZONE`, `LOG_LEVEL`.
- No secrets hardcoded; `.env.example` documents every variable with safe defaults so the evaluator (or grader) can run it with minimal setup.

### 2.4 Concurrency Safety
- SQLite is single-writer. Use `check_same_thread=False` + a single SQLAlchemy `sessionmaker` with `expire_on_commit=False`, and wrap scheduler job bodies in short-lived sessions (open, do work, commit, close) to avoid long-held locks.
- Enable `PRAGMA journal_mode=WAL` at startup for better read/write concurrency (feed reads shouldn't block while a post is being written).
- A simple in-process lock (`asyncio.Lock` or `threading.Lock`) around the orchestrator "tick" ensures only one publishing cycle runs at a time, even if scheduler misfires overlap.

---

## 3. Frontend Architecture

The hackathon problem statement centers on the API contract; a frontend is optional polish, not the deliverable being graded. Keep it minimal and decoupled.

- **Type:** A single static HTML/JS/CSS bundle served by FastAPI at `/` (via `StaticFiles`), or a tiny separate Vite/React app — either is fine since it's non-critical.
- **Purpose:** A read-only dashboard that:
  - Calls `GET /api/agent/feed?agentId=...` and renders the persona name/bio + a reverse-chronological feed of posts.
  - Displays, per post: title, body, publish timestamp, rationale, and source links.
  - Optionally shows a live "agent status" panel (last discovery run, last publish, next scheduled check) by adding a *non-required, additive* `GET /api/agent/status` endpoint (does not replace the two mandated endpoints, purely for demo visibility).
- **No write actions from the frontend.** It never triggers discovery/writing — consistent with the "no further human prompts" requirement. This keeps a human operator from being tempted to "help" the agent during the 48-hour window, which would undermine the demo.
- **Polling:** simple `setInterval` re-fetch of the feed every N seconds, purely presentational.

Keep this thin — most implementation effort should go into the agent core, since that's what's actually being evaluated.

---

## 4. Database Schema (SQLite via SQLAlchemy)

### 4.1 Tables

**`agents`**
| Column | Type | Notes |
|---|---|---|
| id | UUID/TEXT PK | Returned from `init`, used as `agentId` |
| persona_name | TEXT | e.g. "Nova" |
| persona_bio | TEXT | Short persona description |
| persona_config_json | TEXT (JSON) | Full persona spec (tone, values, topics of interest, style rules) |
| status | TEXT | `initializing` \| `active` \| `paused` \| `error` |
| created_at | DATETIME | |
| last_discovery_at | DATETIME NULL | |
| last_publish_at | DATETIME NULL | |
| posts_published_count | INTEGER | denormalized counter for quota checks |

**`sources`** (registry of feeds/APIs the agent watches)
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| type | TEXT | `rss` \| `hackernews` \| `github` \| `blog` |
| name | TEXT | e.g. "OpenAI Blog", "Hacker News Front Page" |
| url | TEXT | feed/API endpoint |
| enabled | BOOLEAN | |
| last_fetched_at | DATETIME NULL | |
| last_fetch_status | TEXT | `ok` \| `error` \| `empty` |
| last_error | TEXT NULL | |

**`topics`** (raw + normalized discovery candidates, before/after editorial review)
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| agent_id | FK → agents.id | |
| source_id | FK → sources.id | |
| title | TEXT | |
| summary | TEXT | short excerpt/description from source |
| url | TEXT | canonical link |
| content_hash | TEXT | normalized hash for dedup (see §14) |
| discovered_at | DATETIME | |
| raw_metadata_json | TEXT (JSON) | source-specific fields (HN points, GitHub stars, etc.) |
| editorial_status | TEXT | `pending` \| `scored` \| `approved` \| `rejected` \| `published` \| `expired` |
| editorial_score_json | TEXT (JSON) NULL | see §7 |
| rejection_reason | TEXT NULL | |

**`posts`** (published content — the feed's payload)
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| agent_id | FK → agents.id | |
| topic_id | FK → topics.id | |
| title | TEXT | |
| body | TEXT | full post content (persona voice) |
| summary | TEXT | short teaser, for feed previews |
| rationale | TEXT | why this was deemed worth publishing (human-readable) |
| sources_json | TEXT (JSON) | list of `{title, url, source_type}` |
| tags_json | TEXT (JSON) | topic tags (e.g. ["LLM","open-source"]) |
| content_hash | TEXT | for duplicate-post detection across time |
| published_at | DATETIME | |
| generation_meta_json | TEXT (JSON) | model used, prompt version, token counts (debug/audit) |

**`run_logs`** (operational audit trail — critical for a "reliable for 48h unattended" system)
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| agent_id | FK → agents.id | |
| run_type | TEXT | `discovery` \| `editorial` \| `writing` \| `publish_cycle` |
| started_at | DATETIME | |
| finished_at | DATETIME NULL | |
| status | TEXT | `success` \| `partial` \| `failed` |
| detail_json | TEXT (JSON) | counts, errors, decisions made |

### 4.2 Indexing
- `topics(content_hash)`, `posts(content_hash)` — unique-ish lookups for dedup.
- `posts(published_at DESC)` — feed ordering.
- `topics(editorial_status)` — quick pull of pending queue.
- `sources(enabled)`.

### 4.3 Why SQLite is sufficient here
Single-writer, embedded, zero-ops — ideal for a 48-hour hackathon deployment with one agent instance. WAL mode gives adequate read concurrency for feed polling during writes.

---

## 5. Agent Lifecycle

```
 [POST /api/agent/init]
          │
          ▼
 1. Check DB for existing agent
    ├─ exists & active → return existing agentId (idempotent, no new scheduler)
    └─ none exists:
          ▼
 2. Generate persona (persona.py) — LLM call or config-driven, persisted to `agents`
          ▼
 3. Seed default source list into `sources` table (RSS/HN/GitHub/blogs)
          ▼
 4. Create agent row, status = 'initializing'
          ▼
 5. Register APScheduler jobs (discovery job, publish-cycle job, cleanup job)
          ▼
 6. Run one immediate "bootstrap" discovery + publish cycle synchronously
    (guarantees the feed is non-empty almost immediately, not only after
    the first scheduled interval — important since evaluator may poll early)
          ▼
 7. status = 'active'; return {agentId, persona, status}
          │
          ▼
 [Scheduler now runs autonomously every N minutes for ~48h]
          │
          ├── Discovery Job ──► fetch sources ──► normalize ──► store as `topics`
          │
          ├── Editorial Job ──► score pending topics ──► approve/reject
          │
          ├── Writing Job ──► for approved topics not yet published,
          │                    generate post ──► validate ──► store as `posts`
          │
          └── Housekeeping Job ──► expire stale topics, rotate logs, health check
```

- The four "jobs" above are conceptually distinct but can be composed into a single **orchestrator tick** function called on one scheduler interval (simplest, fewer moving parts for a hackathon) — see §11 for interval design.
- Every tick is wrapped in a top-level try/except that logs to `run_logs` and never lets an unhandled exception kill the scheduler thread.

---

## 6. Topic Discovery System

### 6.1 Interface
`DiscoverySource` (abstract base in `discovery/base.py`) defines:
```python
fetch() -> List[RawTopicCandidate]
```
Each concrete source (RSS, HN, GitHub, Blogs) implements `fetch()` independently, so a failure in one source never blocks the others. `aggregator.py` calls each source, catches exceptions per-source, logs them, and merges successful results.

### 6.2 Sources

**RSS Feeds (`rss_source.py`)**
- Uses `feedparser` against a configurable list of feed URLs stored in `sources`.
- Extracts: title, link, published date, summary.
- Recommended seed list: general AI/tech RSS feeds (e.g., MIT Technology Review AI, VentureBeat AI, ArXiv cs.AI recent, TechCrunch AI) — configurable, not hardcoded in logic.

**Hacker News (`hackernews_source.py`)**
- Uses the free HN Firebase API (`/v0/topstories.json`, `/v0/item/{id}.json`) — no key required.
- Filters top/new stories by simple keyword match against an AI/tech keyword list (title/URL contains "AI", "LLM", "GPU", "model", framework names, etc.) before passing to editorial scoring — cheap pre-filter to avoid wasting LLM calls on irrelevant stories.
- Captures HN points + comment count into `raw_metadata_json` as a discovery-time popularity signal.

**GitHub (`github_source.py`)**
- Uses GitHub REST/Search API (unauthenticated within rate limits, or with a token from `.env` for higher limits): trending-style query via `search/repositories?q=topic:llm+created:>DATE&sort=stars`, plus optionally watching specific orgs' `releases` endpoints (openai, anthropics, huggingface, google-deepmind, meta-llama, etc.).
- Captures stars, language, description.

**Official AI Company Blogs (`blogs_source.py`)**
- Curated list of official blog RSS/Atom endpoints (OpenAI, Anthropic, Google AI/DeepMind, Meta AI, Microsoft AI, Hugging Face, Mistral, etc.) stored as `sources` rows with `type='blog'`.
- Reuses the RSS parsing logic (blogs are just RSS/Atom under the hood) but tagged separately for editorial weighting (official announcements score higher on credibility).

### 6.3 Normalization
All sources map into a common `RawTopicCandidate` shape before persistence:
```json
{ "title": "...", "summary": "...", "url": "...", "source_type": "...", "source_name": "...", "published_at": "...", "raw_metadata": {} }
```
This is written to `topics` with `editorial_status='pending'` and a computed `content_hash` (see §14) checked against existing rows **before insert**, so exact repeats from re-polling the same feed are dropped at discovery time already (cheap, before any LLM cost is spent).

### 6.4 Resilience
- Per-source timeout (e.g. 10s) via `httpx` with `timeout=`.
- Per-source retry with exponential backoff (2 attempts) via `utils/retry.py`.
- A source failing 100% of the time still lets discovery for other sources proceed; failures logged to `sources.last_error` and `run_logs`.

---

## 7. Editorial Judgment System

Purpose: decide, per topic, whether it's worth publishing — not everything discovered should become a post.

### 7.1 Pipeline
1. **Pre-filter (cheap, non-LLM):** keyword relevance, recency window (reject topics older than e.g. 72h), minimum source credibility, drop items already near-duplicate to a published post (see §14) — all before spending an LLM call.
2. **LLM Scoring (`scorer.py`):** For topics surviving the pre-filter, call the LLM with structured JSON output:
```json
{
  "relevance_score": 0,
  "novelty_score": 0,
  "credibility_score": 0,
  "persona_fit_score": 0,
  "overall_recommendation": "publish",
  "reasoning": "short explanation"
}
```
   Scored against the persona's stated interests/values (persona.py feeds its own config into this prompt) — this is what makes editorial judgment persona-consistent rather than generic.
3. **Policy Layer (`policy.py`):** Deterministic rules layered on top of the LLM's opinion so the system doesn't purely trust the model:
   - Minimum `overall_recommendation == "publish"` **and** `relevance_score >= 6` **and** `novelty_score >= 5`.
   - **Rate limiting / quota:** won't approve more than `MAX_POSTS_PER_DAY` topics in a rolling 24h window, and enforces `MIN_POSTS_PER_DAY` by lowering thresholds slightly if the queue is starved late in a day (see §15).
   - **Diversity rule:** avoid approving 3+ topics on the same narrow subtopic within a short window (checked via tag overlap) to keep the feed varied.
4. Approved topics: `editorial_status='approved'`, scores saved to `editorial_score_json`. Rejected: `editorial_status='rejected'`, `rejection_reason` set to the LLM's reasoning (kept for transparency/debuggability, not shown externally).

### 7.2 Why store rejection reasoning too
Even though only published posts are exposed via the feed, keeping rejected topics + reasoning in the DB is valuable for demoing "editorial judgment" to evaluators/judges if they inspect the DB or if a `/status`-style debug view is added later.

---

## 8. Persona System

### 8.1 Persona Definition
Generated once at `init` time (or loaded from a fixed config if you want full determinism for grading) and stored in `agents.persona_config_json`:
```json
{
  "name": "Nova",
  "tagline": "An AI voice tracking the frontier of AI and technology.",
  "bio": "...",
  "tone": ["curious", "precise", "slightly opinionated", "accessible"],
  "values": ["technical accuracy", "crediting sources", "avoiding hype"],
  "interests": ["LLMs", "AI infrastructure", "open-source AI", "developer tools", "AI policy"],
  "writing_style_rules": [
    "Always explain why a development matters, not just what happened.",
    "Never claim certainty about unverified claims.",
    "Keep an consistent first-person voice as 'Nova'."
  ],
  "avoid": ["clickbait phrasing", "unverified rumors as fact", "political opinions unrelated to tech policy"]
}
```

### 8.2 Consistency Mechanism
- The persona config is **immutable after init** (not regenerated per post) — this is what guarantees "consistent" persona across 48 hours.
- Every writing prompt (§10) injects the full persona config verbatim, so voice/tone is anchored identically on every generation call rather than re-derived.
- Editorial scoring also uses persona `interests`/`values` as scoring criteria (§7), so persona consistency governs *what* gets published, not just *how* it's written.

### 8.3 Originality
- `writing_style_rules` explicitly forbid copying source text; the writer prompt (§10) instructs synthesis + original commentary, with sources cited separately in structured `sources_json` rather than quoted at length in the body.

---

## 9. Memory System

Purpose: the agent must "remember previously published content" — used both to avoid repetition and to let new posts reference/build on prior coverage where relevant.

### 9.1 What Memory Consists Of
- **Structured memory:** the `posts` table itself is the memory store — no separate cache needed. `memory/store.py` exposes query functions: `get_recent_posts(n)`, `get_posts_by_tag(tag)`, `get_post_titles_since(datetime)`.
- **Working memory injected into prompts:** before writing a new post, the writer pulls the last N (e.g. 10–15) published post titles + summaries and includes them in the generation prompt as "Previously covered" context, with an explicit instruction: don't repeat, and reference prior coverage only if genuinely relevant (e.g. "a follow-up to yesterday's coverage of X").
- **Semantic memory (optional, if time permits — `embeddings.py`):** store an embedding vector per post (via the LLM provider's embedding endpoint) and compute cosine similarity against candidate topics as an additional novelty signal feeding into §7 scoring and §14 dedup. This is a stretch feature, not required for MVP — a text-hash + LLM-judgment approach (below) is sufficient for a hackathon.

### 9.2 Memory in Editorial Judgment
Recent post summaries are also passed into the editorial scorer prompt (§7.2) so `novelty_score` is computed relative to what's actually been published, not just relative to the raw topic pool.

---

## 10. AI Writing System

### 10.1 Generation Flow (`writer/generator.py`)
Input: an approved `Topic` row + persona config + recent-posts memory context.
Output: strict JSON matching a schema (validated in `writer/validator.py`):
```json
{
  "title": "string",
  "body": "string (markdown, 150-400 words)",
  "summary": "string (<= 40 words)",
  "rationale": "string — why this deserved publishing, in plain language",
  "tags": ["string", "..."],
  "sources": [{"title": "string", "url": "string", "source_type": "string"}]
}
```
- Uses the LLM API's structured/JSON-mode output to avoid brittle parsing.
- `rationale` is written by the model but should be grounded in the actual editorial scores computed in §7 — the prompt includes those scores/reasoning as input so the rationale is consistent with why it was actually approved, not an unrelated post-hoc justification.
- `sources` always includes at minimum the originating topic's URL; may include additional links only if present in the source metadata (never fabricated).

### 10.2 Validation Layer (`writer/validator.py`)
Before saving as a `post`:
- JSON schema conformance check (reject/retry on malformed output, max 2 retries).
- Length bounds check.
- Banned-content / safety check (basic keyword + optional moderation call).
- Source URL sanity check (must match a real discovered topic URL, not hallucinated).
- Duplicate-content check against existing posts (§14) — if too similar, discard and mark topic `rejected` rather than publish a near-clone.
- On repeated validation failure, log to `run_logs` with status `failed`, mark topic `editorial_status='expired'`, move on — never let a bad generation crash the cycle.

### 10.3 Prompt Versioning
`prompts.py` keeps prompt templates as versioned constants (`WRITER_PROMPT_V1`); `generation_meta_json` on each post records which prompt version + model produced it, for reproducibility/debugging.

---

## 11. Autonomous Scheduler

### 11.1 Technology
APScheduler (`AsyncIOScheduler` if the app is async end-to-end, otherwise `BackgroundScheduler` in a daemon thread) started during FastAPI's lifespan/startup event, stopped on shutdown.

### 11.2 Jobs

| Job | Interval | Purpose |
|---|---|---|
| `discovery_job` | every `DISCOVERY_INTERVAL_MINUTES` (e.g. 30 min) | Pull from all sources, store new `topics` |
| `editorial_job` | every 15–20 min (offset from discovery) | Score+approve/reject pending topics |
| `writing_job` | every `PUBLISH_INTERVAL_MINUTES` (see §15 pacing logic) | Generate & publish next approved topic |
| `housekeeping_job` | every 60 min | Expire stale pending topics (>72h old, never scored), trim old `run_logs`, verify source health |

- Simpler alternative for hackathon reliability: **one combined `orchestrator_tick` job every 20–30 minutes** that runs discovery → editorial → writing → housekeeping in sequence, guarded by the lock from §2.4. Fewer jobs = fewer interleaving bugs = more reliable for an unattended 48h run. **This is the recommended MVP approach**; splitting into separate jobs is an enhancement if time allows.
- `misfire_grace_time` set generously (e.g. 300s) so a slow LLM call doesn't cause APScheduler to skip the next run entirely.
- `max_instances=1` per job to prevent overlapping ticks.

### 11.3 Startup Recovery
On process (re)start, before scheduling new jobs, check `agents.status == 'active'`: if so, just re-register jobs against the existing agent (don't re-run `init` logic, don't duplicate persona). This makes the system resilient to hosting platform restarts during the 48-hour window.

---

## 12. API Design

Only two endpoints are contractually required. Keep the contract exact; anything else (status/debug endpoints) is additive and optional.

### `POST /api/agent/init`
**Request:** empty body, or optional `{}` (no required input — agent is self-configuring per the persona system).
**Behavior:** idempotent (§5).
**Response `200`:**
```json
{
  "agentId": "uuid-string",
  "status": "active",
  "persona": {
    "name": "Nova",
    "tagline": "...",
    "bio": "..."
  },
  "message": "Agent initialized and running autonomously."
}
```

### `GET /api/agent/feed?agentId=...`
**Behavior:** pure read from `posts` table, ordered `published_at DESC`. No side effects, no generation triggered.
**Query params:** `agentId` (required), optionally `limit` (default e.g. 20, additive/optional), `since` (optional ISO timestamp, additive).
**Response `200`:**
```json
{
  "agentId": "uuid-string",
  "persona": { "name": "Nova", "tagline": "...", "bio": "..." },
  "posts": [
    {
      "id": "uuid",
      "title": "...",
      "summary": "...",
      "body": "...",
      "publishedAt": "2026-08-08T12:00:00Z",
      "rationale": "...",
      "sources": [{"title": "...", "url": "...", "sourceType": "rss"}],
      "tags": ["LLM", "open-source"]
    }
  ],
  "totalPosts": 12
}
```
**Errors:** `404` with `{"error": "agent_not_found"}` if `agentId` doesn't match any row.

### 12.1 Schema Contracts (`api/schemas.py`)
All request/response shapes defined as Pydantic models so FastAPI auto-generates OpenAPI docs at `/docs`.

---

## 13. Error Handling

### 13.1 Principles
- **No unhandled exception may ever reach the scheduler's top level** — every job wraps its body in try/except, logs full traceback to `run_logs.detail_json`, and returns cleanly so the *next* scheduled tick still fires.
- **Partial failure is success, not failure.** If 2 of 4 discovery sources fail, the cycle still proceeds with the 2 that succeeded, and the run is logged `status='partial'`.
- **LLM call failures:** wrapped with retry+backoff (`utils/retry.py`, e.g. 3 attempts, exponential: 2s/4s/8s). If all retries fail, that specific topic is skipped this cycle (stays `pending`/`approved`, retried next cycle) — never crashes the tick.
- **Feed endpoint failure isolation:** `GET /feed` only touches read queries; a DB read error returns a clean `500` with a generic error body, never leaks stack traces.

### 13.2 Circuit-Breaker-Style Guard
If the LLM API fails N consecutive times across ticks (e.g. 5), the orchestrator flips `agents.status = 'error'` internally and pauses *writing* (but keeps discovery running so topics accumulate) — then a subsequent successful health-check call resumes writing automatically.

### 13.3 Logging
Structured logs (`utils/logging.py`, JSON-lines to stdout + optionally a rotating file) at INFO for normal cycle summaries, WARNING for per-source failures, ERROR for cycle-level failures.

---

## 14. Duplicate Detection

Two layers, applied at two different stages:

### 14.1 Topic-level (discovery-time, cheap)
- **Exact/near-exact:** normalize `title + url` (lowercase, strip punctuation/whitespace, strip tracking query params from URL) → SHA-256 → `content_hash`. Before inserting a new `topics` row, check for existing hash match (any status) within a lookback window (e.g. 7 days) — skip insert if found.
- **Fuzzy title similarity:** for topics not exact-hash matches, compute a cheap string similarity (e.g. `rapidfuzz.fuzz.token_set_ratio`) against recent topic titles (last 48–72h); if similarity > threshold (e.g. 90), treat as duplicate and skip.

### 14.2 Post-level (pre-publish, semantic)
- Before saving a generated post, compare its `content_hash` (normalized title+summary) against all existing `posts.content_hash`.
- Additionally run a cheap similarity check of the new summary against the last ~20 published summaries. If too similar, discard the generated post, mark the topic `rejected` with `rejection_reason='duplicate_of_published'`, and move to the next candidate.

### 14.3 Cross-source duplicates
The same underlying story often appears via RSS *and* HN *and* a blog simultaneously. Because normalization strips to `title`+canonical `url` domain+path, and because editorial scoring runs after aggregation, near-simultaneous cross-source duplicates are caught by the topic-level fuzzy check before ever reaching the writer.

---

## 15. Publishing Strategy Over 48 Hours

### 15.1 Pacing Model
- Target: **`MIN_POSTS_PER_DAY` to `MAX_POSTS_PER_DAY`** (suggested defaults: min 4, max 10 posts/24h → roughly one every 2.5–6 hours) — configurable via `.env`.
- The **immediate bootstrap cycle at `init`** (§5 step 6) guarantees at least 1 post exists within the first couple of minutes.
- Publishing interval is **not perfectly fixed** — add small jitter (± a few minutes) around each scheduled writing slot.

### 15.2 Adaptive Quota Logic (in `policy.py`)
Track `posts_published_count` in a rolling 24h window:
- If well below the daily minimum with few hours left in the current 24h window → **loosen** editorial thresholds slightly.
- If at/above the daily maximum → **hold** approved-but-unpublished topics for the next window rather than dropping them.

### 15.3 Handling Quiet News Periods
If discovery yields nothing new for several cycles (e.g. overnight), the agent does not force low-quality posts.

---

## 16. Security Considerations

- **API keys** (`LLM_API_KEY`, optional `GITHUB_TOKEN`) only in `.env`, never committed, never returned in any API response or log line.
- **Input validation:** `agentId` on `/feed` validated as a well-formed UUID before querying.
- **No arbitrary code execution paths:** discovery sources are read-only HTTP fetches with strict timeouts.
- **Prompt injection awareness:** untrusted external text is always clearly delimited in prompts and constrained via output JSON-schema validation.
- **Rate limiting on public endpoints:** idempotent `init` guards against repeated creation loops.
- **No PII collected.**

---

## 17. Deployment Architecture

### 17.1 Recommended Hackathon Deployment
- **Single container / single VM process**, e.g. a `Dockerfile` running `uvicorn app.main:app --host 0.0.0.0 --port 8000` with `--workers 1`.
- Persistent volume/disk for `data/agent.db` so the SQLite file survives restarts.
- **Process supervision:** use a restart policy (`Docker --restart unless-stopped`).

---

## 18. Testing Strategy

### 18.1 Unit Tests
- `test_discovery.py`: each source's `fetch()` against saved fixture responses.
- `test_dedup.py`: hash normalization, fuzzy-match thresholding.
- `test_editorial.py`: policy layer logic with mocked LLM scores.
- `test_writer.py`: validator logic against mock LLM JSON outputs.

### 18.2 Integration Tests
- `test_api_agent.py`: spins up FastAPI app with temp SQLite DB, calls `init`, asserts idempotency, calls `feed` and asserts schema conformance and read-only behavior.
- `test_scheduler.py`: triggers simulated fast-forward ticks.

### 18.3 End-to-End Simulation
- `scripts/simulate_48h.py`: time-compressed local simulation script.

---

## 19. Development Milestones

- **Milestone 1 — Skeleton & Contract (Current Phase)**: Backend project structure, FastAPI app, SQLite database, Agent model, Post model, `POST /api/agent/init`, `GET /api/agent/feed`, environment configuration, `requirements.txt`, error handling.
- **Milestone 2 — Discovery Layer**
- **Milestone 3 — Editorial + Dedup**
- **Milestone 4 — Writer + Persona + Memory**
- **Milestone 5 — Autonomous Scheduler Integration**
- **Milestone 6 — Pacing, Error Handling, Hardening**
- **Milestone 7 — Frontend + Deployment**
- **Milestone 8 — Testing & Submission Polish**
