# Project Code Explanations — Core files

This document contains detailed, block-by-block explanations for the repository's core service entrypoints and shared database modules. For readability the explanations are grouped by logical blocks (imports, constants, class definitions, main flows). If you want truly line-by-line annotations, I can produce per-line comments for each file in a follow-up, but starting with these annotated blocks speeds review.

---

**File:** [services/gateway/main.py](services/gateway/main.py)

- Lines 1–12: Module docstring and future annotations import — describes this file as the FastAPI gateway.
- Lines 14–24: Standard library imports (`logging`, `os`, `time`, `asynccontextmanager`) and typing; these provide instrumentation, environment access, and the lifespan helper.
- Lines 26–33: FastAPI and middleware imports plus rate-limiting from `slowapi` used for request throttling.
- Lines 35–38: Import application routers from `services.gateway.routers` and shared helpers for DB table creation, logging, and metrics setup.
- Lines 40–42: `logger` and `limiter` initialization. Rate limiter uses `get_remote_address` to key requests.
- Lines 45–59: `lifespan` asynccontextmanager — runs on startup/shutdown. In development it calls `create_tables()` to initialize MongoDB indexes.
- Lines 63–95: FastAPI app instantiation: sets title, description (API features and auth note), version, and OpenAPI/docs endpoints. Also wires the `lifespan` manager.
- Lines 99–119: Middleware configuration — attach rate limiter, gzip compression, and CORS. CORS origins are read from `CORS_ORIGINS` env var.
- Lines 122–132: Request timing middleware. Adds `X-Process-Time-Ms` and platform-version headers to each response.
- Lines 135–147: Router includes. Each router is mounted under `/api/v1/<service>` with tags for docs grouping.
- Lines 150–166: Root and health endpoints: `/` returns basic metadata; `/health` checks MongoDB and Redis connectivity and reports dependency health; `/ready` returns readiness for k8s probes.

**Why it matters / usage:** This file is the public API surface. Look here to add new routes, configure global middleware, or change startup behaviors.

---

**File:** [services/collector/main.py](services/collector/main.py)

- Lines 1–16: Docstring describing goals (high-throughput collection) and imports (asyncio, logging, env, datetime).
- Lines 18–28: Imports for shared Kafka clients, topics, collection source models, and collector registry helpers.
- Lines 31–53: `SOURCE_WEIGHTS` and `_scale_limits` — logic to split an overall fetch `limit` across multiple job sources proportionally. The helper ensures a minimum allocation and spreads leftovers.
- Lines 56–100: `CollectorService` class: constructor initialises Kafka producer/consumer, run state and locks.
- Lines 102–127: `start()` sets up producer/consumer, starts scheduled collection task, and begins consuming for manual triggers.
- Lines 129–152: `_handle_trigger()` responds to manual Kafka trigger messages, extracting `sources`, `search_terms`, `location`, and `limit`, then runs `_run_collection` inside a lock to avoid concurrency.
- Lines 154–205: `_scheduled_collection()` sleeps and runs a scheduled run every configurable minutes (default 90); uses `_scale_limits` to prepare per-source limits.
- Lines 207–330: `_run_collection()` executes collection concurrently across all sources:
  - Spawns `_run_one(source)` tasks for each source using the collector registry.
  - Gathers results, serializes jobs to JSON (via `job.model_dump(mode="json")`), constructs keyed tuples, and uses `producer.send_batch` to publish to `TOPICS.JOB_RAW`.
  - Builds a `summary` with timings and counts and returns it.
- Lines 332–347: `main()` entrypoint that setups logging and runs the service.

**Why it matters / usage:** This orchestrator coordinates scraping agents and ensures efficient, batched publishing to Kafka. Inspect `services/collector/agents.py` to see per-source collector implementations.

---

**File:** [services/embedder/main.py](services/embedder/main.py)

- Lines 1–20: Docstring and imports. This service consumes verified jobs and computes embeddings in batches.
- Lines 22–33: Configuration constants: embedding model name, Qdrant host/port/collection, vector size, batch size and DB concurrency limits.
- Lines 36–76: `EmbedderService` class init: sets up Kafka consumer (group `embedder-service`) and placeholders for model and qdrant client.
- Lines 78–110: `start()` attempts to load `sentence_transformers` model and initialize Qdrant collection if absent. If dependencies are missing it logs warnings but continues (graceful degradation). Then starts consumer and consumes in batch mode.
- Lines 112–224: `_handle_batch()` — core processing:
  - Build `embed_texts` by concatenating title, company, location, skills, and truncated description.
  - If the embedding model is present, runs `model.encode` in a thread executor to avoid blocking the event loop; converts vectors to lists.
  - If Qdrant client present, upserts vector points (ids are UUIDs) with payloads.
  - Prepares bulk MongoDB updates to set `embedding_id`, `embedding_model`, and `status` fields, and inserts pipeline event records.
  - Uses `pymongo`'s bulk operations when available; otherwise falls back to concurrent per-job updates with a semaphore.
  - Logs performance metrics (jobs processed, whether vectors/Qdrant used, time and j/s).

**Why it matters / usage:** This service transforms enriched jobs into vector representations and indexes them so semantic search works. You can change `EMBEDDING_MODEL` env var to use different models, or modify batch sizes to tune throughput.

---

**File:** [services/deduplicator/main.py](services/deduplicator/main.py)

- Lines 1–16: Docstring and imports. This service consumes cleaned jobs and emits deduplicated jobs.
- Lines 18–27: `generate_fingerprint()` — normalizes title, company and location to a SHA-256 fingerprint used for near-duplicate detection.
- Lines 29–89: `DeduplicatorService` class: sets batch size, concurrency, kafka client setup, start/stop methods.
- Lines 91–220: `_handle_batch()` core logic:
  - Precompute fingerprints and gather source+source_job_id pairs.
  - Single DB query to find exact duplicates by source+source_job_id and a second query for fingerprint matches.
  - Classify messages as exact duplicate, near duplicate, batch-internal duplicate, or unique.
  - Prepare bulk upserts for jobs (marking `is_duplicate`, `duplicate_of_id`, `status`) and pipeline events.
  - Publish unique messages downstream to `TOPICS.JOB_DEDUPLICATED` in a single `send_batch` call.
  - Logs throughput and summary.

**Why it matters / usage:** Deduplication avoids storing and processing repeated jobs. The fingerprint and source id checks balance precision and recall when deciding duplicates.

---

**File:** [services/enrichment/main.py](services/enrichment/main.py)

- Lines 1–18: Docstring and imports. The enrichment service attaches skills, salary info, domain tags, etc.
- Lines 20–38: Constants and batch/concurrency configuration.
- Lines 40–88: `EnrichmentService` init and `start()`:
  - Initializes `SkillExtractionAgent`, `SalaryExtractionAgent` and optionally `SalaryEstimator` from `ml/`.
  - Starts producer and consumer and consumes in batch mode.
- Lines 90–168: `_enrich_one()` — enriches a single job:
  - Extracts title/description/company/salary fields.
  - Runs skill extraction and salary extraction concurrently using `asyncio.create_task` and `gather`.
  - Constructs lists of required/optional skills, tech stack and domain tags.
  - Attempts ML-based salary estimation using `salary_estimator` if available via `_build_salary_data`.
  - Updates the message with enrichment fields and returns an event doc.
- Lines 170–246: `_handle_batch()` — run enrichment across batch with a semaphore-limited concurrency, bulk-write updates and pipeline events, and publish enriched messages downstream.
- Lines 248–314: `_build_salary_data()` — merges LLM/rule-based salary extractor output with ML estimator output selecting one with higher confidence, or falls back to default estimated record.

**Why it matters / usage:** Enrichment improves search relevance and UX (skills, experience, salary). Tune `ENRICHER_BATCH_SIZE`/`ENRICHER_WORKERS` for throughput vs resource usage.

---

**File:** [services/verifier/main.py](services/verifier/main.py)

- Lines 1–16: Docstring and imports. The verifier classifies jobs as verified or rejected using a scam detection agent.
- Lines 18–40: Batch defaults and concurrency.
- Lines 42–88: `VerifierService.start()` loads `ScamDetectionAgent` and starts Kafka clients.
- Lines 90–139: `_verify_one()` — runs scam analysis and computes verification metadata (scam probability, risk level, authenticity/quality scores) and determines whether to reject a job based on `SCAM_THRESHOLD`.
- Lines 141–233: `_handle_batch()` — parallel verification with a semaphore, bulk writes to MongoDB, inserts pipeline events, and publishes verified and rejected jobs to their respective Kafka topics.
- Lines 235–258: `_compute_quality_score()` — heuristic scoring based on description length, number of skills, salary presence and apply URL; lowers the score proportionally to scam probability.

**Why it matters / usage:** This service is the safety gate for job quality. Adjust `SCAM_THRESHOLD` to change permissiveness, and update scam rules/agents to improve detection.

---

**File:** [shared/database/models.py](shared/database/models.py)

- Lines 1–12: Module docstring, imports from `pydantic` and standard libs.
- Lines 14–25: `MongoBaseModel` — Pydantic base model with `_id` alias, UTC timestamp defaults, and `extra='allow'` so documents may contain unstructured fields. JSON encoder ensures datetime is ISO-formatted.
- Lines 27–120: `Company`, `Job`, `User`, `UserProfile`, `SavedSearch`, `SavedJob` — Pydantic models define the common schema expectations for MongoDB documents. `Job` is the main schema with many fields used across the pipeline (title, description, location, salary, skills, embedding_id, status, etc.).
- Lines 122–220: Pipeline/audit and auxiliary models: `PipelineEvent`, `NotificationLog`, `ScamRule`, `SkillTaxonomy`, `CollectionRun` — used by services to store events, rules and job collection metadata.

**Why it matters / usage:** These models act as shared contracts describing fields stored in MongoDB. They are used for (de)serialization, validation, and developer understanding of persisted shape.

---

**File:** [shared/database/session.py](shared/database/session.py)

- Lines 1–22: Docstring and imports including `motor.motor_asyncio` for async Mongo.
- Lines 24–44: `MONGO_URI` resolution and logic to parse the DB name from the URI.
- Lines 46–62: `_client` singleton and `get_mongo_client()` to lazily create and reuse a Motor client with tuned pool sizes and timeouts.
- Lines 64–78: `get_db()` FastAPI dependency: yields a Motor database handle for request-scoped usage.
- Lines 80–106: `create_tables()` calls `shared.database.base.create_all_indexes` to build collection indexes; falls back to a minimal set if unavailable. This is called by the `gateway` under development start-up.
- Lines 108–127: `close_client()` to close the global client on shutdown and `drop_tables()` helper for dev/test to drop database (gated by environment check).

**Why it matters / usage:** Centralized Mongo client and index initialization help keep services consistent and avoid per-service connection duplication.

---

Next steps:

- I can continue producing similar annotated sections for every remaining Python file (79 files total). This will be done in batches — I suggest the next batch include `services/*/agents.py`, `shared/kafka/*`, `ml/*` modules, and `frontend/*` static entrypoints.
- If you prefer, I can instead generate true line-by-line annotated versions of specific files you care about most.

Tell me which you prefer: "continue all in batches" or "line-by-line for specific files" and I will proceed.


## Batch 2 — Collector agents, Kafka clients

I inspected `services/collector/agents.py` and the shared Kafka clients (`shared/kafka/*`). Key findings and per-section explanations:

- `services/collector/agents.py` (overview):
  - Provides many concrete collectors (Adzuna, Greenhouse, Lever, Workday, Indeed, Naukri, LinkedIn, RSS, Government, CompanyCareers, Manual).
  - Core features implemented in `BaseCollector`:
    - Async HTTP session management with `httpx.AsyncClient`.
    - Semaphore-based concurrency control per source.
    - Rate limiting (token-bucket style) with adaptive multiplier adjusted on 429/503.
    - Header rotation to reduce fingerprinting and simple circuit breaker to avoid hammering failing sources.
    - `_rate_limited_get()` centralizes request timing, circuit-breaker updates, and raises on HTTP errors.
  - `retry_with_backoff()` helper wraps arbitrary coroutines with exponential backoff + jitter, honors `Retry-After` on 429, and integrates with circuit breaker.
  - Collector implementations follow a pattern: determine targets (terms/companies/feeds), spawn bounded concurrent subtasks, parse site responses to `RawJob` objects, deduplicate and return up to `limit` results.

- Notable collector behaviors:
  - Some collectors (Naukri, Workday, LinkedIn) return empty lists until official credentials or captcha solvers are configured — preserving platform data quality by ingesting only real, authentic job listings.
  - Parsers use `BeautifulSoup` or JSON APIs with resilient extraction and safe fallbacks.
  - `COLLECTOR_REGISTRY` maps `CollectionSource` enum values to collector classes; `get_collector()` instantiates the appropriate collector for the orchestrator.

- `shared/kafka/producer.py` (overview):
  - `KafkaProducerClient` wraps `aiokafka.AIOKafkaProducer` with JSON serialization and a `send_batch()` method that publishes many messages in parallel while bounding concurrency.
  - `send_batch()` normalizes messages to `(payload, key)` tuples, publishes in sub-batches, collects failures, and forwards failed records to a dead-letter queue (`<topic>.dlq`).
  - The producer sets `acks='all'` and `enable_idempotence=True` for safer delivery semantics and uses LZ4 compression and batching tuning for throughput.

- `shared/kafka/consumer.py` (overview):
  - `KafkaConsumerClient` wraps `AIOKafkaConsumer` and supports `consume()` for single-item handlers and `consume_batch()` for high-throughput batch handlers using `getmany()`.
  - The consumer uses manual commits (`enable_auto_commit=False`) so handlers control when offsets are committed (after successful processing).
  - `start()`/`stop()` manage lifecycle and `__aenter__/__aexit__` allow use with `async with`.

Operational notes and tuning:
- Tune environment variables for production: `KAFKA_BOOTSTRAP_SERVERS`, producer batch/linger settings, topic partition counts in `shared/kafka/topics.py`, and per-service `*_BATCH_SIZE` and worker counts.
- The collector agents prioritize resilient behavior over perfect scraping fidelity; you can enable/disable specific scrapers with environment variables (e.g., `INDEED_SCRAPING_ENABLED`).

---

Which next: (A) continue annotating the next batch (enrichment/verifier agent modules, ML model files, shared utils), or (B) generate per-line annotated source copies (e.g., `services/collector/agents.annotated.py`) for any of the files covered so far?


## Line-by-line explanations (core files)

Below are true, line-by-line explanations for the most important entrypoint and shared DB files. Each line shows the code (trimmed) followed by a short explanation.

**File:** `services/gateway/main.py`

1: """FastAPI API Gateway — The single entry point for all external requests.
  - Module docstring describing purpose.
2: Provides full CRUD APIs, search, auth, and orchestration control.
  - Extra description.
3: """
4: from __future__ import annotations
  - Enables postponed evaluation of annotations (PEP 563-like behavior).
6: import logging
  - Standard logging module.
7: import os
  - Access environment variables.
8: import time
  - Used for timing middleware.
9: from contextlib import asynccontextmanager
  - Helper to implement FastAPI lifespan (async startup/shutdown).
10: from typing import Any
  - Generic typing alias used for return types.
12: from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
  - FastAPI core imports for app and request handling.
13: from fastapi.middleware.cors import CORSMiddleware
  - CORS middleware to allow cross-origin requests.
14: from fastapi.middleware.gzip import GZipMiddleware
  - GZip responses to save bandwidth.
15: from fastapi.responses import JSONResponse
  - Used for custom JSON responses (not used heavily here).
16: from slowapi import Limiter, _rate_limit_exceeded_handler
  - Rate limiting library used to throttle clients.
17: from slowapi.errors import RateLimitExceeded
  - Exception type for rate limit hits.
18: from slowapi.util import get_remote_address
  - Helper to key rate limits by requester IP.
20: from services.gateway.routers import auth, jobs, search, users, admin, analytics, notifications
  - Importing modular routers that define API endpoints.
21: from shared.database.session import create_tables
  - Function to initialize DB indexes used on startup (dev only).
22: from shared.utils.logging import setup_logging
  - Standard logging setup helper (project-specific).
23: from shared.utils.metrics import setup_metrics
  - Metrics setup (e.g., Prometheus) helper.
25: logger = logging.getLogger(__name__)
  - Module logger.
28: limiter = Limiter(key_func=get_remote_address)
  - Rate limiter configured to use remote address as key.
32: @asynccontextmanager
33: async def lifespan(app: FastAPI):
  - FastAPI lifespan manager runs on startup and shutdown.
34:     logger.info("🚀 Starting Job Intelligence Platform API Gateway")
  - Informational startup log.
37:     if os.getenv("APP_ENV", "development") == "development":
38:         await create_tables()
  - In development, initialize DB indexes to ease local runs.
39:         logger.info("✅ Database tables initialized")
41:     yield
  - Yield control to run the app; on shutdown the function resumes.
43:     logger.info("🛑 Shutting down API Gateway")
  - Shutdown log.
47: app = FastAPI(
48:     title="Job Intelligence Platform API",
49:     description="""
  - FastAPI instantiation with API metadata (docs, openapi).
66:     lifespan=lifespan,
  - Attach lifespan manager created earlier.
70: app.state.limiter = limiter
  - Store the limiter in app state for access in middleware.
71: app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
  - Use slowapi's handler when clients exceed rate limits.
73: app.add_middleware(GZipMiddleware, minimum_size=1000)
  - Add GZip middleware to compress large responses.
75: app.add_middleware(
76:     CORSMiddleware,
77:     allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:3001").split(","),
  - Read `CORS_ORIGINS` env var (comma-separated) to set allowed origins.
82: @app.middleware("http")
83: async def add_process_time_header(request: Request, call_next):
84:     start_time = time.perf_counter()
85:     response = await call_next(request)
86:     process_time = (time.perf_counter() - start_time) * 1000
87:     response.headers["X-Process-Time-Ms"] = f"{process_time:.2f}"
88:     response.headers["X-Platform-Version"] = "1.0.0"
89:     return response
  - Middleware that measures request duration and adds headers.
92: API_PREFIX = "/api/v1"
  - Base prefix for all API routers.
94: app.include_router(auth.router,          prefix=f"{API_PREFIX}/auth",          tags=["Authentication"])
  - Mount each router under a logical prefix.
107: @app.get("/", tags=["Root"])
108: async def root() -> dict[str, Any]:
109:     return {
110:         "name": "Job Intelligence Platform API",
111:         "version": "1.0.0",
112:         "status": "operational",
113:         "docs": "/docs",
114:         "health": "/health",
115:     }
  - Root endpoint returning basic metadata.
118: @app.get("/health", tags=["Health"])
119: async def health_check() -> dict[str, Any]:
  - Health check endpoint used by LB/k8s. Below it pings MongoDB and Redis.
120:     import redis.asyncio as aioredis
121:     from shared.database.session import get_mongo_client
  - Local imports to avoid importing redis unless endpoint hit.
123:     checks: dict[str, str] = {}
126:     try:
127:         mongo_client = get_mongo_client()
128:         await mongo_client.admin.command("ping")
129:         checks["mongodb"] = "healthy"
130:     except Exception:
131:         checks["mongodb"] = "unhealthy"
  - Ping MongoDB's admin command to verify connectivity.
134:     try:
135:         redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
136:         r = aioredis.from_url(redis_url)
137:         await r.ping()
138:         await r.aclose()
139:         checks["redis"] = "healthy"
140:     except Exception:
141:         checks["redis"] = "unhealthy"
  - Ping Redis, close connection, and report state.
144:     overall_status = "healthy" if all(v == "healthy" for v in checks.values()) else "degraded"
146:     return {
147:         "status": overall_status,
148:         "version": "1.0.0",
149:         "environment": os.getenv("APP_ENV", "development"),
150:         "dependencies": checks,
151:     }

**File:** `services/collector/main.py`

1: """Collector Service — Orchestrates all job collection activities.
  - Module docstring with high-level notes.
7: import asyncio
8: import logging
9: import os
10: from datetime import datetime
  - Standard imports for async work, logging and timestamps.
12: from shared.kafka.consumer import KafkaConsumerClient
13: from shared.kafka.producer import KafkaProducerClient
14: from shared.kafka.topics import TOPICS
15: from shared.models.job import CollectionSource
16: from shared.utils.logging import setup_logging
17: from services.collector.agents import (
18:     COLLECTOR_REGISTRY,
19:     get_collector,
20:     get_all_sources,
21:     DEFAULT_SEARCH_TERMS,
22: )
  - Imports collector registry helpers and Kafka clients.
25: SOURCE_WEIGHTS: dict[str, float] = { ... }
  - Mapping of source weights used to proportionally split limits.
46: def _scale_limits(total_limit: int, sources: list[str]) -> dict[str, int]:
  - Compute per-source allocation from a total limit.
52:     active_weights = {s: SOURCE_WEIGHTS.get(s, 1.0 / max(1, len(sources))) for s in sources}
  - Use default weight if source not found.
58:     allocated = {s: max(5, int(total_limit * w)) for s, w in normalized.items()}
  - Ensure each source gets at least 5 items.
66: class CollectorService:
67:     def __init__(self) -> None:
68:         self.producer = KafkaProducerClient()
69:         self.consumer = KafkaConsumerClient(topics=[TOPICS.COLLECTION_TRIGGER])
70:         self.running = False
71:         self._collection_lock = asyncio.Lock()
72:         self._last_collection_summary: dict[str, Any] = {}
  - Initialize producer, consumer, lock and state.
74:     async def start(self) -> None:
75:         await self.producer.start()
76:         await self.consumer.start()
77:         self.running = True
78:         asyncio.create_task(self._scheduled_collection())
79:         await self.consumer.consume(self._handle_trigger)
  - Start clients, schedule periodic collection, and consume manual triggers.
81:     async def _handle_trigger(self, message: dict, *args) -> None:
82:         if self._collection_lock.locked():
83:             logger.warning("Collection already in progress — skipping trigger")
84:             return
  - Ignore triggers while collection in progress.
87:         sources = message.get("sources") or get_all_sources()
88:         search_terms = message.get("search_terms") or None
89:         location = message.get("location") or None
90:         limit = int(message.get("limit") or os.getenv("COLLECTION_RUN_LIMIT", "5000"))
  - Extract trigger options with defaults.
99:         async with self._collection_lock:
100:             self._last_collection_summary = await self._run_collection(
101:                 sources, search_terms, location, limit
102:             )
  - Run collection under the lock to ensure single concurrent run.
104:     async def _scheduled_collection(self) -> None:
105:         interval_min = int(os.getenv("COLLECTION_INTERVAL_MINUTES", "90"))
106:         interval_seconds = interval_min * 60
107:         while self.running:
108:             await asyncio.sleep(5 if not self._last_collection_summary else interval_seconds)
  - Sleep a short initial period or the full interval thereafter.
116:     async def _run_collection(
117:         self,
118:         sources: list[str],
119:         search_terms: list[str] | None,
120:         location: str | None,
121:         limit: int,
122:     ) -> dict[str, Any]:
  - Run all collectors concurrently and batch-publish results.
126:         per_source_limits = _scale_limits(limit, sources)
  - Determine how many jobs to fetch per source.
133:         async def _run_one(source_name: str) -> tuple[str, list]:
134:             source_limit = per_source_limits.get(source_name, limit // max(1, len(sources)))
135:             collector = get_collector(source_name)
136:             async with collector:
137:                 jobs = await collector.collect(
138:                     search_terms=search_terms,
139:                     location=location,
140:                     limit=source_limit,
141:                 )
  - Each collector is used as an async context manager and asked to collect jobs.
150:         tasks = [asyncio.create_task(_run_one(s)) for s in sources]
151:         results = await asyncio.gather(*tasks, return_exceptions=False)
  - Run all collectors in parallel and gather results.
169:         for source_name, jobs in source_job_map.items():
170:             to_send: list[tuple[Any, str]] = []
171:             for job in jobs:
172:                 payload = job.model_dump(mode="json")
173:                 key = str(job.id)
174:                 to_send.append((payload, key))
176:             if to_send:
177:                 pub_count = await self.producer.send_batch(TOPICS.JOB_RAW, to_send)
  - Serialize job models to JSON and publish them in batches by key.

**File:** `services/embedder/main.py`

1: """Embedder Service — Vector Embedding Generator (BATCH MODE).
  - Docstring explains this service consumes verified jobs and produces vectors.
6: import asyncio
7: import logging
8: import os
9: import time
10: import uuid
11: from datetime import datetime
12: from typing import Any
14: from shared.kafka.consumer import KafkaConsumerClient
15: from shared.kafka.topics import TOPICS
16: from shared.database.session import get_mongo_client
18: logger = logging.getLogger(__name__)
20: EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
21: QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
22: QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
23: QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION_JOBS", "job_embeddings")
24: VECTOR_SIZE = 384
26: DEFAULT_BATCH_SIZE = int(os.getenv("EMBEDDER_BATCH_SIZE", "96"))
27: CONCURRENT_DB_WRITES = int(os.getenv("EMBEDDER_DB_WORKERS", "40"))
  - Configuration constants and defaults.
30: class EmbedderService:
31:     def __init__(self) -> None:
32:         self.batch_size = DEFAULT_BATCH_SIZE
33:         self.consumer = KafkaConsumerClient(
34:             topics=[TOPICS.JOB_VERIFIED],
35:             group_id="embedder-service",
36:             max_poll_records=max(150, self.batch_size * 2),
37:         )
38:         self.model = None
39:         self.qdrant_client = None
40:         self.running = False
  - Prepare consumer; model and qdrant client to be initialized in start().
42:     async def start(self) -> None:
43:         try:
44:             from sentence_transformers import SentenceTransformer
45:             self.model = SentenceTransformer(EMBEDDING_MODEL)
46:             logger.info(f"Loaded embedding model: {EMBEDDING_MODEL}")
47:         except ImportError:
48:             logger.warning("sentence-transformers not installed — embedder will skip vectorization")
  - Attempt to load embedding model, degrade if not installed.
50:         try:
51:             from qdrant_client import QdrantClient
52:             from qdrant_client.models import Distance, VectorParams
53:             self.qdrant_client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
54:             collections = self.qdrant_client.get_collections().collections
55:             existing_names = [c.name for c in collections]
56:             if QDRANT_COLLECTION not in existing_names:
57:                 self.qdrant_client.create_collection(
58:                     collection_name=QDRANT_COLLECTION,
59:                     vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
60:                 )
61:                 logger.info(f"Created Qdrant collection: {QDRANT_COLLECTION}")
62:         except Exception as e:
63:             logger.warning(f"Qdrant not available: {e} — embeddings will be stored but not indexed")
  - Try to connect to Qdrant and create collection if missing; otherwise continue.
65:         await self.consumer.start()
66:         self.running = True
67:         logger.info("🧬 Embedder service started (batch=%d)", self.batch_size)
68:         await self.consumer.consume_batch(self._handle_batch, batch_size=self.batch_size, timeout_ms=3000)
  - Start consuming batches and hand them to `_handle_batch`.
70:     async def _handle_batch(self, messages: list[dict]) -> None:
71:         start = time.monotonic()
72:         n = len(messages)
73:         if n == 0:
74:             return
  - Quick guards and timing.
76:         job_ids: list[str] = []
77:         embed_texts: list[str] = []
78:         payloads: list[dict[str, Any]] = []
79:         messages_by_id: dict[str, dict] = {}
  - Prepare lists for embedding input and payload metadata.
81:         for m in messages:
82:             job_id = m.get("_id", m.get("id", str(uuid.uuid4())))
83:             title = m.get("title", "")
84:             description = (m.get("description", "") or "")[:1000]
85:             skills = " ".join(m.get("required_skills", []) or [])
86:             company = m.get("company_name", "")
87:             location = m.get("location_city", "") or ""
88:             embed_texts.append(f"{title}. {company}. {location}. Skills: {skills}. {description}")
  - Build a short text that captures the job for semantic embedding.
95:         embedding_ids = [str(uuid.uuid4()) for _ in job_ids]
  - Assign stable UUIDs to embeddings that will be Qdrant point IDs.
97:         vectors_list: list[list[float]] | None = None
98:         if self.model is not None:
99:             try:
100:                loop = asyncio.get_event_loop()
101:                vectors_np = await loop.run_in_executor(
102:                    None,
103:                    lambda: self.model.encode(embed_texts, batch_size=min(64, len(embed_texts)), show_progress_bar=False),
104:                )
105:                vectors_list = [v.tolist() for v in vectors_np]
106:            except Exception as e:
107:                logger.exception("Batched embedding encode failed: %s", e)
  - Run the CPU-bound encode in executor, then convert numpy output to lists for JSON compatibility.
109:        if vectors_list is not None and self.qdrant_client is not None:
110:            try:
111:                from qdrant_client.models import PointStruct
112:                points = [
113:                    PointStruct(id=eid, vector=vec, payload=pl)
114:                    for eid, vec, pl in zip(embedding_ids, vectors_list, payloads)
115:                ]
116:                self.qdrant_client.upsert(collection_name=QDRANT_COLLECTION, points=points)
117:            except Exception as e:
118:                logger.exception("Qdrant batch upsert failed: %s", e)
  - If Qdrant available, upsert vectors in batch with payload metadata.
120:        now_utc = datetime.utcnow()
121:        job_updates = []
122:        event_inserts = []
  - Prepare MongoDB bulk operations and pipeline events.
128:        client = get_mongo_client()
129:        db = client["jobplatform"]
  - Obtain Motor client and select DB.
131:        try:
132:            from pymongo import UpdateOne, InsertOne
133:            bulk_ops = [UpdateOne(**u) for u in job_updates]
134:            if bulk_ops:
135:                await db.jobs.bulk_write(bulk_ops, ordered=False)
136:        except Exception as e:
137:            logger.warning("Embedder bulk_write jobs failed (%s), falling back per-job", e)
  - Attempt bulk update, and fallback to concurrent per-job updates using a semaphore if bulk write fails.

**File:** `services/deduplicator/main.py`

1: """Deduplicator Service — Duplicate Detection Agent.
5: import asyncio
6: import hashlib
7: import logging
8: import time
9: import uuid
10: from datetime import datetime
11: from typing import Any
13: from shared.kafka.consumer import KafkaConsumerClient
14: from shared.kafka.producer import KafkaProducerClient
15: from shared.kafka.topics import TOPICS
16: from shared.database.session import get_mongo_client
18: logger = logging.getLogger(__name__)
21: def generate_fingerprint(title: str, company: str, location: str | None) -> str:
22:     normalized = f"{title.lower().strip()}|{company.lower().strip()}|{(location or '').lower().strip()}"
23:     return hashlib.sha256(normalized.encode()).hexdigest()
  - Create deterministic content fingerprint used for near-duplicate checks.
26: class DeduplicatorService:
27:     DEFAULT_BATCH_SIZE = int(__import__("os").getenv("DEDUP_BATCH_SIZE", "200"))
28:     CONCURRENT_TASKS = int(__import__("os").getenv("DEDUP_WORKERS", "40"))
  - Configure batch size and concurrency from env.
36:     async def _handle_batch(self, messages: list[dict]) -> None:
37:         t0 = time.monotonic()
38:         if not messages:
39:             return
41:         client = get_mongo_client()
42:         db = client["jobplatform"]
  - Get DB handle for dedup checks and writes.
45:         prepared: list[dict] = []
46:         for msg in messages:
47:             job_id = msg.get("_id") or msg.get("id") or str(uuid.uuid4())
48:             fp = generate_fingerprint(...)
49:             prepared.append({...})
  - Prepare per-message fingerprint, source ids and store original message.
57:         source_pairs: list[tuple[str, str]] = [
58:             (p["source"], p["source_job_id"]) for p in prepared
59:             if p["source"] and p["source_job_id"]
60:         ]
  - Collect all (source, source_job_id) pairs to query exact duplicates in bulk.
66:         fps = [p["fingerprint"] for p in prepared]
67:         if fps:
68:             cursor = db.jobs.find({"content_fingerprint": {"$in": fps}}, {"_id": 1, "content_fingerprint": 1})
69:             async for existing in cursor:
70:                 near_duplicates[existing["content_fingerprint"]] = str(existing["_id"])
  - Find existing jobs whose fingerprint matches any in this batch.
78:         for p in prepared:
79:             jid = p["job_id"]
80:             msg = dict(p["msg"])
81:             msg["_id"] = jid
83:             if exact_key in exact_duplicates:
84:                 is_dup = True
85:                 dup_of = exact_duplicates[exact_key]
  - Classify messages as exact duplicate, near duplicate, batch-internal duplicate, or unique.
103:             msg["is_duplicate"] = is_dup
104:             msg["duplicate_of_id"] = dup_of
105:             msg["status"] = "deduplicated" if not is_dup else "duplicate"
106:             msg.setdefault("updated_at", datetime.utcnow())
  - Annotate message fields accordingly and prepare DB update ops.
118:         if update_ops:
119:             try:
120:                 await db.jobs.bulk_write(update_ops, ordered=False)
121:             except Exception as e:
122:                 logger.warning(f"Dedup bulk_write jobs failed: {e}")
  - Try bulk write, log and continue on failure.
126:         if unique_messages:
127:             published = await self.producer.send_batch(TOPICS.JOB_DEDUPLICATED, unique_messages)
  - Publish only unique jobs downstream.

**File:** `services/enrichment/main.py`

1: """Enrichment Service — Skill Extraction + Salary Estimation (BATCH MODE).
6: import asyncio
7: import logging
8: import os
9: import time
10: import uuid
11: from datetime import datetime
12: from typing import Any
14: from shared.kafka.consumer import KafkaConsumerClient
15: from shared.kafka.producer import KafkaProducerClient
16: from shared.kafka.topics import TOPICS
17: from shared.database.session import get_mongo_client
19: logger = logging.getLogger(__name__)
21: _MODEL_PATH = os.environ.get("SALARY_MODEL_PATH", "ml/salary_estimator/model.pkl")
23: DEFAULT_BATCH_SIZE = int(os.getenv("ENRICHER_BATCH_SIZE", "120"))
24: CONCURRENT_JOBS = int(os.getenv("ENRICHER_WORKERS", "50"))
  - Config and imports.
28:     async def start(self) -> None:
29:         from services.enrichment.agents.skill_extractor import SkillExtractionAgent
30:         self.skill_agent = SkillExtractionAgent()
32:         from services.enrichment.agents.salary_extractor import SalaryExtractionAgent
33:         self.salary_agent = SalaryExtractionAgent(use_llm=True)
  - Initialize enrichment agents; skill extractor and salary extractor use LLM when configured.
36:         try:
37:             from ml.salary_estimator.estimator import SalaryEstimator
38:             self.salary_estimator = SalaryEstimator(model_path=_MODEL_PATH)
39:             logger.info(...)
40:         except ImportError:
41:             logger.warning("ml.salary_estimator not on PYTHONPATH — salary ML disabled")
  - Optionally load ML-based salary estimator.
44:     async def _enrich_one(self, message: dict) -> tuple[str, dict, dict, dict] | None:
45:         job_id = message.get("_id", message.get("id", str(uuid.uuid4())))
46:         try:
47:             skill_task = asyncio.create_task(self.skill_agent.extract(title, description, use_llm=True))
48:             salary_task = asyncio.create_task(self.salary_agent.extract(...))
49:             skills, salary_result = await asyncio.gather(skill_task, salary_task)
  - Run skill extraction and salary extraction concurrently per job.
61:             required_skills = [s.normalized_name for s in skills if s.is_required]
62:             nice_to_have = [s.normalized_name for s in skills if not s.is_required]
63:             tech_stack = [s.normalized_name for s in skills if s.category.value == "technical"]
  - Partition skills into required, optional, and technical stacks.
72:             salary_data = _build_salary_data(...)
  - Merge rule-based/LLM salary result with ML estimator if available.
84:             message.update(enrichment_data)
  - Attach enrichment fields to job message.
96:     async def _handle_batch(self, messages: list[dict]) -> None:
97:         sem = asyncio.Semaphore(CONCURRENT_JOBS)
98:         tasks = [asyncio.create_task(_with_sem(m)) for m in messages]
99:         results = await asyncio.gather(*tasks)
  - Process batch items concurrently with semaphore-limited parallelism.
117:         try:
118:             await db.jobs.bulk_write(bulk_ops, ordered=False)
119:         except Exception as e:
120:             logger.warning("Enrichment bulk_write jobs failed (%s), falling back per-job", e)
  - Bulk write updates and events with fallbacks.

**File:** `services/verifier/main.py`

1: """Verifier Service — Scam Detection + Authenticity Verification (BATCH MODE).
6: import asyncio
7: import logging
8: import os
9: import time
10: import uuid
11: from datetime import datetime
12: from typing import Any
14: from shared.kafka.consumer import KafkaConsumerClient
15: from shared.kafka.producer import KafkaProducerClient
16: from shared.kafka.topics import TOPICS
17: from shared.database.session import get_mongo_client
19: logger = logging.getLogger(__name__)
21: DEFAULT_BATCH_SIZE = int(os.getenv("VERIFIER_BATCH_SIZE", "180"))
22: CONCURRENT_JOBS = int(os.getenv("VERIFIER_WORKERS", "70"))
  - Config constants.
31:     async def _verify_one(self, message: dict) -> tuple[str, dict, dict, dict, bool] | None:
32:         job_id = message.get("_id", message.get("id", str(uuid.uuid4())))
33:         try:
34:             result = await self.scam_agent.analyze(...)
35:             quality_score = self._compute_quality_score(message, result.scam_probability)
36:             is_rejected = result.scam_probability >= self.SCAM_THRESHOLD
  - Run scam detection agent, compute a quality score, and determine rejection.
48:             verification_data = {
49:                 "scam_probability": result.scam_probability,
50:                 "scam_risk_level": result.risk_level,
51:                 "scam_triggered_rules": result.triggered_rules,
52:                 "authenticity_score": max(0, 100 - result.scam_probability * 100),
53:                 "quality_score": quality_score,
54:                 "is_verified": result.scam_probability < 0.2,
55:                 "status": "rejected" if is_rejected else "verified",
56:                 "updated_at": datetime.utcnow(),
57:             }
  - Populate verification metadata to attach to job.
91:         tasks = [asyncio.create_task(_with_sem(m)) for m in messages]
92:         results = await asyncio.gather(*tasks)
  - Use semaphore bound concurrency.
113:         if verified_list:
114:             await self.producer.send_batch(TOPICS.JOB_VERIFIED, verified_list)
115:         if rejected_list:
116:             await self.producer.send_batch(TOPICS.JOB_REJECTED, rejected_list)
  - Route results to verified or rejected Kafka topics.
119:     def _compute_quality_score(self, job: dict, scam_prob: float) -> float:
120:         score = 50.0
121:         if len(desc) > 500: score += 15
122:         if len(skills) >= 5: score += 15
123:         if job.get("salary_min") and job.get("salary_max"): score += 10
124:         score -= scam_prob * 40
125:         return max(0.0, min(100.0, score))
  - Heuristic function combining content quality signals and penalizing scam probability.

**File:** `shared/database/models.py`

1: """Pydantic models — MongoDB database schema.
3: from __future__ import annotations
4: import uuid
5: from datetime import datetime
6: from typing import Any, Dict, List, Optional
8: from pydantic import BaseModel, ConfigDict, Field
10: class MongoBaseModel(BaseModel):
11:     model_config = ConfigDict(
12:         populate_by_name=True,
13:         extra="allow",
14:         json_encoders={datetime: lambda dt: dt.isoformat()}
15:     )
16:     id: str = Field(default_factory=lambda: str(uuid.uuid4()), alias="_id")
17:     created_at: datetime = Field(default_factory=datetime.utcnow)
18:     updated_at: datetime = Field(default_factory=datetime.utcnow)
  - Base Pydantic model with `_id` alias and default timestamps.
20: class Company(MongoBaseModel):
21:     name: str
22:     normalized_name: str
  - Company schema fields and optional trust indicators.
33: class Job(MongoBaseModel):
34:     source: str
35:     source_job_id: str
36:     source_url: str
37:     status: str = "raw"
38:     title: str
39:     description: Optional[str] = None
  - Job schema with fields used throughout pipeline (salary, skills, embedding references, status flags).

**File:** `shared/database/session.py`

1: """Async MongoDB session factory using Motor.
3: from __future__ import annotations
4: import logging
5: import os
6: from collections.abc import AsyncGenerator
8: from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
10: logger = logging.getLogger(__name__)
12: MONGO_URI = os.getenv(
13:     "MONGO_URI",
14:     "mongodb://admin:admin123@localhost:27017/jobplatform?authSource=admin",
15: )
  - Read Mongo URI from env or default to a local dev URI.
20: _client: AsyncIOMotorClient | None = None
  - Module-level client singleton placeholder.
23: def get_mongo_client() -> AsyncIOMotorClient:
24:     global _client
25:     if _client is None:
26:         _client = AsyncIOMotorClient(
27:             MONGO_URI,
28:             serverSelectionTimeoutMS=5000,
29:             connectTimeoutMS=5000,
30:             maxPoolSize=50,
31:             minPoolSize=5,
32:         )
33:     return _client
  - Lazy-initialize Motor client with tuned pool sizes and timeouts.
36: async def get_db() -> AsyncGenerator[AsyncIOMotorDatabase, None]:
37:     mongo_client = get_mongo_client()
38:     db = mongo_client[db_name]
39:     yield db
  - FastAPI dependency that yields a DB handle.
41: async def create_tables() -> None:
42:     mongo_client = get_mongo_client()
43:     db = mongo_client[db_name]
44:     try:
45:         from shared.database.base import create_all_indexes
46:         results = await create_all_indexes(db)
47:         total = sum(results.values())
48:         logger.info(f"Database initialized: {total} indexes created across {len(results)} collections")
49:     except ImportError:
50:         logger.warning("shared.database.base unavailable — using minimal indexes")
51:         await db.jobs.create_index([("source", 1), ("source_job_id", 1)], unique=True)
  - Create indexes using base helper or fallback to minimal set.

---

**Generated per-file annotated docs (index)**

- Enrichment service: [docs/enrichment_main.inline.md](docs/enrichment_main.inline.md)
- Verifier service: [docs/verifier_main.inline.md](docs/verifier_main.inline.md)
- Collector agents (many sources): [docs/collector_agents.inline.md](docs/collector_agents.inline.md)
- Kafka producer docs: [docs/kafka_producer.inline.md](docs/kafka_producer.inline.md)
- Kafka consumer docs: [docs/kafka_consumer.inline.md](docs/kafka_consumer.inline.md)
- Database models: [docs/db_models.inline.md](docs/db_models.inline.md)
- DB session & index init: [docs/db_session.inline.md](docs/db_session.inline.md)
- Salary estimator (ML + rules): [docs/salary_estimator.inline.md](docs/salary_estimator.inline.md)
- Scam detector (inference wrapper): [docs/scam_detector.inline.md](docs/scam_detector.inline.md)
- Skill extractor pipeline: [docs/skill_extractor.inline.md](docs/skill_extractor.inline.md)

You can use these files as entry points to understand implementation details and follow links to specific functions or classes when needed.
