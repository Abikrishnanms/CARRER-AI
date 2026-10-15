# Plan: Per-File Correctness Audit + Self-Healing Layer

## Goal
Two-part work on the TalentLens (JEXA-AI) repo:
1. **Audit each source file** to confirm it imports, type-checks, and runs without errors.
2. **Add a self-healing layer** that detects and recovers from common runtime failures in the 8-stage Kafka pipeline and Docker stack, with minimal new infrastructure.

---

## Part 1 — Per-File Correctness Audit

### 1.1 Inventory
Based on the repo layout, the Python surface is roughly:
- `services/<13 services>/main.py` (gateway, collector, cleaner, deduplicator, enrichment, verifier, embedder, search, analytics, feedback, notifier, auth, orchestrator)
- `services/<service>/agents.py`, `services/<service>/routers/*.py`
- `shared/database/{base,models,session}.py`
- `shared/kafka/{topics,producer,consumer}.py`
- `shared/redis/client.py`, `shared/utils/{recommender,resume_parser,metrics,health,logging,url}.py`
- `shared/models/*.py`
- `ml/salary_estimator/estimator.py`, `ml/scam_detector/{model,train}.py`, `ml/skill_extractor/pipeline.py`
- `tests/integration/test_api.py`

### 1.2 Static checks (run for every file)
- `python -m py_compile <file>` — syntax check.
- `ruff check <file>` — lint (if ruff is available; otherwise fall back to `flake8`).
- `mypy --ignore-missing-imports <file>` — type check, scoped per file so missing cross-service imports don't fail.
- Verify each `main.py` has a runnable entrypoint (`if __name__ == "__main__":` or FastAPI app).

### 1.3 Functional / smoke checks
- **Gateway**: `python -c "from services.gateway.main import app"` succeeds; `GET /health` returns JSON.
- **Other services**: `python -c "import services.<svc>.main"` succeeds after dependencies are installed. Each Kafka worker should expose a `start()` coroutine that can be invoked from a test.
- **ML modules**: `python -m ml.scam_detector.model --self-test` (lazy-load, dummy predict); `ml.skill_extractor.pipeline.SkillPipeline().run("sample job text")` returns a list.
- **Shared**: `get_mongo_client()` lazy-initializes; `KafkaTopics` dataclass loads; `redis.client` constructs without crashing.
- **Docker**: `docker compose config` validates all compose files; `docker compose build --no-cache --dry-run` (or actual build) for each service Dockerfile.

### 1.4 Test pass
- Run `pytest tests/integration/test_api.py` against a running stack (MongoDB + Redis). If infra is not available, document this in the audit output and mark integration tests as "skipped (infra required)" rather than failed.

### 1.5 Audit output
Produce `.kilo/audit-report.md` with one row per file:
| File | Syntax | Lint | Types | Import | Runtime | Notes |
Columns: `✓` / `✗` / `⚠ skipped` plus a free-form "notes" cell. Anything `✗` becomes a tracked fix in Part 1.6.

### 1.6 Fix-while-audit loop
- For each `✗`, file a small patch in the same commit (or a follow-up commit) and re-run the check.
- Do not silently rewrite semantics. If a failure is structural (e.g., a missing dependency that the user must install), record it in the audit and stop.

---

## Part 2 — Self-Healing Layer

### 2.1 What "self-healing" means here
A bundled runtime layer that:
- **Detects** failures in the data pipeline and Docker stack.
- **Recovers** automatically where safe, or **escalates** with a clear signal.
- **Logs and surfaces** every action so it is auditable.

It is **not** a code auto-patcher; it is an operational guard rail.

### 2.2 Failure modes we will cover

| Failure | Detector | Healer |
|---|---| |
| Kafka consumer lag growing | `lag > N` for `M` min, per topic in Redpanda | Restart consumer process; rebalance trigger via `rpk consumer group describe`; if still stuck, emit alert |
| A microservice container keeps restarting | `docker inspect --format '{{.RestartCount}}'` > 5 in 10 min | `docker compose restart <svc>` once; on second occurrence, capture logs, page |
| Mongo/Redis/Redpanda unhealthy but rest of stack running | `/health` returns `degraded` for > 60 s | `docker compose restart <dep>` once; on next failure, mark as persistent and alert |
| Dead-letter queue (DLQ) accumulation | `rpk topic list` shows `*.dlq` depth > threshold | Drain DLQ to `dlq_audit` Mongo collection, log sample, alert |
| Stuck jobs (status not advanced for > X) | Mongo query: `status in {raw, cleaned, deduplicated, enriched} and updated_at < now - 30m` | Republish to next-stage topic; mark `healed_at` |
| Embedder OOM (exit 137) | Docker exit code 137 on `jip-embedder` | Restart with reduced `EMBEDDER_BATCH_SIZE` (env override); re-trigger embedding for failed batch from Mongo `embedding_id IS NULL and status=verified` |
| Pipeline metric missing (e.g., a stage produced 0 for 1 h) | Prometheus `rate(jobs_processed_total[1h]) == 0` for stage | Run an ad-hoc collection for that source, then alert if still zero |

### 2.3 Components

**A. New microservice: `services/healer/`** (Kafka consumer + scheduled task runner)
- Consumes `health.events` and `dlq.audit` topics.
- On each tick (default 60 s):
  1. Probe `/health` on the gateway.
  2. Query Prometheus for lag/depth metrics via PromQL (or scrape `/metrics` of each worker directly).
  3. Inspect Docker via the Docker socket (`/var/run/docker.sock`) using the `docker` Python SDK.
  4. Run stuck-job query in Mongo.
- Action handlers live in `services/healer/actions/`:
  - `restart_container.py` — wraps `docker compose restart <svc>`.
  - `drain_dlq.py` — moves DLQ messages to Mongo `dlq_audit` collection.
  - `replay_jobs.py` — republishes stuck jobs to their next topic.
  - `throttle_embedder.py` — sets `EMBEDDER_BATCH_SIZE` and restarts.
- All actions write a `HealingEvent` doc to Mongo with `{action, target, reason, before, after, ts, success}`.

**B. Prometheus alerts (`infra/observability/alerts.yml`)**
- `ContainerRestarting`: `rate(container_last_seen[5m]) == 0` for a named service.
- `KafkaConsumerLagHigh`: `kafka_consumergroup_lag > 5000` for 10 min.
- `DLQDepthHigh`: `kafka_topic_partition_current_offset{topic=~".*\\.dlq"}` delta > 100 in 10 min.
- `StuckJobs`: `mongo_jobs_stuck_count > 50`.
- `ServiceUnhealthy`: `probe_success{job="gateway"} == 0` for 2 min.

**C. Admin Dashboard surface**
- A new tab "Self-Healing" in `frontend/admin/` showing the last 50 `HealingEvent` records, with a "Pause healing" toggle per action class.
- API: `GET /api/v1/admin/healing/events`, `POST /api/v1/admin/healing/pause`, `POST /api/v1/admin/healing/resume` (gated behind `require_admin`).

**D. Config knobs (env)**
- `HEALER_ENABLED=true`
- `HEALER_INTERVAL_SECONDS=60`
- `HEALER_MAX_RESTARTS_PER_HOUR=3` (circuit breaker per service)
- `HEALER_DRY_RUN=true|false` (if true, log actions but do not execute)
- `HEALER_DLQ_DEPTH_THRESHOLD=100`
- `HEALER_STUCK_JOB_MINUTES=30`

### 2.4 Out of scope (explicit)
- Auto-updating application code (no self-modifying Python).
- ML model retraining triggers.
- Cross-host remediation (this is a single-host Docker Compose stack).

### 2.5 Rollout
1. Land Part 1 audit report and fixes on a branch.
2. Add `services/healer/`, alert rules, admin tab, env defaults in a second commit.
3. `docker compose up -d --build healer` to deploy.
4. `HEALER_DRY_RUN=true` for 24 h in dev, observe the action log.
5. Flip to `HEALER_DRY_RUN=false`.

### 2.6 Validation
- **Unit tests** in `tests/unit/healer/`:
  - Mocked Docker client: `restart_container` only fires when `RestartCount > threshold` and below per-hour cap.
  - Mocked Mongo: stuck-job query returns the expected `replay_jobs` payloads.
  - DLQ drain: Kafka mock feeds 3 messages, assert Mongo insert count and topic offset advance.
- **Integration test**: bring up `mongodb` + `redpanda` + `healer`, inject a stuck job, assert it gets republished within one tick.
- **Manual drill**: `docker kill jip-cleaner`, wait 60 s, assert `HealingEvent` row exists, container is `Up`, no further restarts after cap.

### 2.7 Risks
- Docker socket in a container is a privilege escalation surface. Mitigate by running the healer with the minimal set of capabilities and document the threat model in `docs/healer.md`.
- Repeated restarts can mask real bugs. The per-hour cap and the admin "pause" toggle are the kill switches.
- Prometheus is a hard dependency for some checks. The healer must fall back to direct `/metrics` scraping and Docker inspection if Prometheus is down.

---

## Open questions to confirm with the user before implementation
1. **Healer as a new service vs. inside `orchestrator`.** Recommend: new `services/healer/` so the orchestrator stays focused on the collection cadence and the healer has its own scaling/observability story. OK?
2. **Healer scope.** Should it touch only the 8-stage pipeline + DLQ + container restarts, or also include the frontends (jobboard, admin)? Recommend: backend only for v1; frontends are stateless and can rely on Docker's own restart policy. OK?
3. **Audit depth.** Do you want me to actually fix every failure I find, or only produce the audit report and let you decide? Recommend: produce the report, then fix only `✗` items that are safe (typos, missing imports already implied by other files). Anything structural gets flagged. OK?
4. **Where to put the audit report.** Recommend `.kilo/audit-report.md` (gitignored as a generated artifact). OK?

After these are confirmed I will switch to an implementation-capable agent to execute.
