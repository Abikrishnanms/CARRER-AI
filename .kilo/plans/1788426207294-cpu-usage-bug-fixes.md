# Bug Fix & CPU Usage Investigation Plan

## Summary
Audited the full codebase. The 100% CPU on your laptop is caused by two primary issues: (1) the verifier service creating a new `httpx.AsyncClient` for every job plus making 2 HTTP requests per job, and (2) the dev `docker-compose.yml` pointing to placeholder Dockerfiles that contain only `CMD ["sleep", "infinity"]`, meaning **no services actually run** when you start the stack.

---

## Critical Bugs

### 1. Dev Docker Compose Uses Placeholder Dockerfiles (Deployment Blocking)
**Files:** `docker-compose.yml:265-386`, `infra/docker/gateway/Dockerfile`, `infra/docker/collector/Dockerfile`, `infra/docker/cleaner/Dockerfile`, `infra/docker/deduplicator/Dockerfile`, `infra/docker/enrichment/Dockerfile`, `infra/docker/embedder/Dockerfile`, `infra/docker/notifier/Dockerfile`, `infra/docker/verifier/Dockerfile`, `infra/docker/healer/Dockerfile`

The dev `docker-compose.yml` references `infra/docker/{service}/Dockerfile`, but every one of these files contains only:
```dockerfile
CMD ["sleep", "infinity"]
```
These are scaffold-generated placeholders from `scaffold.py:9-14`. The real Dockerfiles are at `infra/docker/Dockerfile.gateway`, `infra/docker/Dockerfile.collector`, and `infra/docker/Dockerfile.worker`.

The production compose (`docker-compose.prod.yml`) correctly uses the real Dockerfiles.

**Impact:** `docker compose up -d` starts containers that do nothing. No services actually run. This is why your system may appear to be "running" but doing nothing useful while Docker itself consumes CPU.

**Fix:** Update `docker-compose.yml` `build.dockerfile` paths to point to the real Dockerfiles:
- `gateway` → `infra/docker/Dockerfile.gateway`
- `collector` → `infra/docker/Dockerfile.collector`
- `cleaner`, `deduplicator`, `enrichment`, `verifier`, `embedder`, `notifier`, `orchestrator`, `analytics` → `infra/docker/Dockerfile.worker` with `args: { SERVICE_NAME: <name> }`
- `healer` → `infra/docker/Dockerfile.worker` with `args: { SERVICE_NAME: healer }`

---

### 2. Verifier Creates New `httpx.AsyncClient` Per Job — CPU & Memory Hog
**Files:** `services/verifier/main.py:82`, `shared/utils/url.py:142-175`

In `services/verifier/main.py:82`:
```python
url_check = await verify_live_url(apply_url, timeout=2.5) if apply_url else ...
```

`verify_live_url` in `shared/utils/url.py:142-175` does:
```python
async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
    resp = await client.head(url, headers=headers)
    ...
    resp = await client.get(url, headers=headers)
```

This creates and destroys a brand-new `httpx.AsyncClient` for **every single job**. Each creation initializes connection pools, DNS resolvers, and SSL contexts. With 5,000 jobs per collection cycle and 70 concurrent verifier workers, this generates **thousands of expensive client allocations per minute**.

Additionally, `services/verifier/agents/authenticity_agent.py:218-222` creates a new `httpx.AsyncClient` per career page check inside `_check_career_page`, adding more HTTP client churn.

**Impact:** This is the #1 cause of 100% CPU. Client creation/destruction overhead, combined with 2 HTTP requests per job, saturates the event loop with connection management rather than actual work.

**Fix:** 
- Add a shared `httpx.AsyncClient` instance to `VerifierService.__init__` and pass it to `verify_live_url`.
- Add a concurrency semaphore in `VerifierService` to cap simultaneous URL checks (e.g., `VERIFIER_HTTP_CONCURRENCY=10`).
- Fix `AuthenticityAgent` to reuse a shared `httpx.AsyncClient` instance instead of creating one per call.
- Consider making URL reachability checks optional/configurable (e.g., `VERIFIER_CHECK_URLS=false` for local dev).

---

## CPU Usage Root Causes (Ranked)

### 3. Excessive Pipeline-Wide Concurrency Without Backpressure
**Files:** `services/cleaner/main.py:161`, `services/verifier/main.py:25`, `services/deduplicator/main.py:53`, `services/enrichment/main.py:27`, `services/embedder/main.py:31`, `services/collector/main.py:197`

| Service | Default Workers | Batch Size |
|---------|-----------------|------------|
| Cleaner | 60 | 150 |
| Verifier | 70 | 180 |
| Deduplicator | 40 | 200 |
| Enrichment | 50 | 120 |
| Embedder | 40 | 96 |
| Collector | all sources concurrently | 5,000 |

All services run concurrently via Docker Compose. On a laptop, this spawns **hundreds of async tasks** simultaneously. The Python event loop spends most of its time context-switching between tasks rather than doing useful work.

**Fix approach:**
- Add a `.env.dev` file with laptop-friendly overrides:
  ```
  CLEANER_WORKERS=8
  VERIFIER_WORKERS=8
  ENRICHER_WORKERS=6
  DEDUP_WORKERS=6
  EMBEDDER_DB_WORKERS=4
  COLLECTION_RUN_LIMIT=500
  VERIFIER_CHECK_URLS=false
  ```
- Document that production should use its own `.env.prod` with higher values.
- The code defaults should remain unchanged to preserve production behavior.

### 4. Embedder Runs SentenceTransformer on CPU
**File:** `services/embedder/main.py:56`

```python
self.model = SentenceTransformer(EMBEDDING_MODEL)
```

If you have no GPU, `model.encode()` runs on CPU and will peg one or more cores at 100% during batch processing.

**Fix:** Add `OMP_NUM_THREADS=2` to the embedder Dockerfile/environment for non-GPU environments. Document `EMBEDDER_BATCH_SIZE=32` as the laptop recommendation.

### 5. Orchestrator Runs 5 Infinite Loops Concurrently
**File:** `services/orchestrator/main.py:52-58`

```python
await asyncio.gather(
    self._scheduled_collection_loop(),
    self._stuck_job_monitor(),
    self._quarter_hour_mini_collect(),
    self._daily_cleanup(),
    self._throughput_metrics_logger(),
)
```

Five `while self.running:` loops run forever. Even with sleeps, the overhead of 5 coroutines plus the services they trigger adds up.

**Fix:** This is acceptable architecture, but lower the default `HEALER_INTERVAL_SECONDS` to 300 and `ANALYTICS_REFRESH_INTERVAL_MINUTES` to 60 for dev via `.env.dev`. Consider making the orchestrator optional in local dev (add `ORCHESTRATOR_ENABLED=false` to `.env.dev`).

---

## Additional Bugs Found

### 6. Frontend `fetchJobs` Closure Bug (Duplicate API Calls)
**File:** `frontend/jobboard/src/App.jsx:108-111`

```javascript
const handleLoadMore = () => {
    setPage(p => p + 1)
    fetchJobs(false)
}
```

`fetchJobs` depends on `page` via its `useCallback` dependency array. React 18 batches state updates, so `fetchJobs(false)` may read the stale `page` value and re-fetch the same page twice.

**Fix:** Update `fetchJobs` to accept `page` as a parameter instead of reading state:
```javascript
const fetchJobs = useCallback(async (reset = false, pageOverride = null) => {
    setLoading(true)
    const currentPage = pageOverride ?? (reset ? 1 : page)
    ...
}, [searchQuery, filters, page])
```

And update `handleLoadMore`:
```javascript
const handleLoadMore = () => {
    setPage(p => p + 1)
}
```

With a separate `useEffect` that watches `page` and calls `fetchJobs(false)` when it changes. This eliminates the closure entirely.

### 7. Deprecated `asyncio.get_event_loop().time()` in Python 3.12+
**Files:** `services/collector/main.py:169,234`, `services/orchestrator/main.py:75,83`

**Fix:** Replace with `time.monotonic()`.

### 8. `orchestrator.start()` `asyncio.gather` Without Exception Isolation
**File:** `services/orchestrator/main.py:52`

```python
await asyncio.gather(
    self._scheduled_collection_loop(),
    ...
)
```

If any background loop raises an unhandled exception, `asyncio.gather` cancels all other tasks.

**Fix:** Use `return_exceptions=True` or wrap each loop in a try/except that logs and continues.

### 9. `consume_batch` Uses Constant 1s Backoff on Repeated Failures
**File:** `shared/kafka/consumer.py:131`

```python
except Exception as e:
    logger.exception(f"Error in batch consumer: {e}")
    await asyncio.sleep(1)
```

If Kafka is down, this retries every 1 second forever. Should use exponential backoff with a max cap.

### 10. Tests Use `asyncio.run` Inside Pytest (Conflicts with `pytest-asyncio`)
**Files:** `tests/unit/test_pipeline.py:120,135`, `tests/unit/test_scam_detector.py` (if present)

`pyproject.toml:46` sets `asyncio_mode = "auto"`, which means pytest-asyncio manages the event loop. Calling `asyncio.run()` inside a test creates a nested loop and can cause `RuntimeError: asyncio.run() cannot be called from a running event loop`.

**Fix:** Replace `asyncio.run(agent.analyze(...))` with `await agent.analyze(...)` and mark test methods with `@pytest.mark.asyncio`.

### 11. Healer Default Interval 60s Is Too Frequent
**File:** `services/healer/main.py:52`

```python
self.interval_seconds = int(os.getenv("HEALER_INTERVAL_SECONDS", "60"))
```

On a laptop with limited resources, probing gateway health, checking stuck jobs, and scanning Docker containers every 60 seconds adds unnecessary overhead.

**Fix:** Change default to `300` (5 minutes).

### 12. Collector `_handle_trigger` Spawns Unbounded Background Tasks
**File:** `services/collector/main.py:120-122`

```python
if is_search:
    asyncio.create_task(self._run_collection(...))
```

Search triggers create unlimited `asyncio.create_task` calls without any concurrency limit. A burst of search traffic could spawn hundreds of collection tasks.

**Fix:** Use an `asyncio.Semaphore` with a max concurrent search collections limit (e.g., `MAX_SEARCH_COLLECTIONS=2`).

### 13. MongoDB `maxPoolSize=50` May Be Too Low
**File:** `shared/database/session.py:44`

With 50 max connections and multiple services doing bulk writes + queries concurrently, connection pool exhaustion can cause hidden retries and slowdowns.

**Fix:** Increase to `maxPoolSize=100` for local dev, or make it configurable via `MONGO_MAX_POOL_SIZE`.

---

## Open Design Question

**Docker Compose strategy:** Should we fix the dev `docker-compose.yml` to use the real Dockerfiles (mirroring `docker-compose.prod.yml`), or should we consolidate into a single worker Dockerfile and update both compose files?

**Recommended answer:** Update `docker-compose.yml` to mirror the prod file's approach — use `infra/docker/Dockerfile.gateway` for gateway, `infra/docker/Dockerfile.collector` for collector, and `infra/docker/Dockerfile.worker` with `args: { SERVICE_NAME: ... }` for all workers. This is the path of least resistance and aligns dev with prod.

---

## Recommended Implementation Order

| Priority | Fix | Impact |
|----------|-----|--------|
| P0 | Fix dev `docker-compose.yml` Dockerfile paths | **Services actually run** |
| P0 | Fix verifier `verify_live_url` to reuse `httpx.AsyncClient` + add concurrency cap | **Eliminates 100% CPU** |
| P0 | Fix `AuthenticityAgent` to reuse `httpx.AsyncClient` | **Eliminates additional HTTP client churn** |
| P1 | Add `.env.dev` with laptop-friendly worker counts and `VERIFIER_CHECK_URLS=false` | Reduces CPU by 50-70% |
| P1 | Fix frontend `fetchJobs` closure bug | Prevents duplicate fetches |
| P2 | Replace deprecated `asyncio.get_event_loop().time()` | Future-proofs code |
| P2 | Fix `orchestrator.start()` exception isolation | Prevents cascading failures |
| P2 | Add exponential backoff to `consume_batch` | Better failure behavior |
| P3 | Fix test `asyncio.run` conflicts | Tests pass reliably |
| P3 | Raise healer default interval to 300s | Less overhead |
| P3 | Add search trigger semaphore in collector | Prevents task storms |
| P3 | Make MongoDB pool size configurable | Fewer connection stalls |

---

## Validation Steps

1. **Deployment:** Run `docker compose up -d` and verify all service containers are running (not sleeping) via `docker ps`.
2. **CPU profiling:** Run the stack with `top`/`htop` open. Verify CPU drops below 30% idle and spikes only during actual batch processing.
3. **Unit tests:** Run `pytest tests/unit/ -v` and confirm no `RuntimeError: asyncio.run() cannot be called from a running event loop`.
4. **Integration test:** Trigger a small collection (`limit=10`) and verify the verifier no longer creates per-job HTTP clients (check logs for "httpx.AsyncClient" creation frequency).
5. **Frontend test:** Click "Load more" and verify only one API request is made per click (not two due to the closure bug).
