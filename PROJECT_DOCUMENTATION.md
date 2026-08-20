# Project Overview — CARRER-AI (Talentlens branch)

## Summary

This repository implements a job-scraping and job-search pipeline that ingests job data, processes and enriches it with ML components, indexes it in a vector store/search service, and exposes APIs consumed by frontend apps. The codebase is split into small service components that communicate via Kafka and shared libraries.

Key capabilities:
- Ingest job postings (collector / scrapers)
- Deduplicate and verify listings (`services/deduplicator`, `services/verifier`)
- Embed job text, enrich metadata, and run ML models (`services/embedder`, `services/enrichment`, `ml/`)
- Index and search using a vector store (see `infra/qdrant`)
- Expose APIs and web frontends (`services/gateway`, `frontend/`)
- Observability and orchestration with Docker/Kubernetes manifests and Prometheus/Grafana

## High-level architecture and dataflow

1. Scrapers / ingestion write raw job messages into Kafka topics.
2. `services/collector` reads from Kafka, normalizes and writes canonical job messages.
3. `services/deduplicator` removes duplicates.
4. `services/embedder` computes embeddings (vector representations) and stores them in the vector DB (Qdrant).
5. `services/enrichment` augments jobs with metadata (salary estimates, skills) using models under `ml/`.
6. `services/verifier` may validate listings (fraud/scam checks).
7. `services/search` and `gateway` provide API access and query routing; frontends consume the gateway APIs.
8. `notifier` and `feedback` handle notifications and user feedback loops.

ASCII flow (simplified):

Scrapers -> Kafka -> collector -> deduplicator -> embedder -> enrichment -> vector DB / search -> gateway -> frontend

## Top-level layout (what each folder contains)

- `frontend/` — Web frontends
  - Admin UI: [frontend/admin](frontend/admin)
  - Jobboard UI: [frontend/jobboard](frontend/jobboard)

- `services/` — Microservices (each service is a small Python app)
  - API / Gateway: [services/gateway/main.py](services/gateway/main.py)
  - Collector: [services/collector/main.py](services/collector/main.py), [services/collector/agents.py](services/collector/agents.py)
  - Deduplicator: [services/deduplicator/main.py](services/deduplicator/main.py)
  - Embedder: [services/embedder/main.py](services/embedder/main.py)
  - Enrichment: [services/enrichment/main.py](services/enrichment/main.py)
  - Verifier: [services/verifier/main.py](services/verifier/main.py)
  - Notifier, Orchestrator, Search, Cleaner, Auth, Analytics, Feedback: respective folders under `services/`

- `shared/` — Shared utilities and database layer
  - DB models and session: [shared/database/models.py](shared/database/models.py), [shared/database/session.py](shared/database/session.py)
  - Shared requirements: [shared/requirements.txt](shared/requirements.txt)

- `models/` — Domain models used across services (`job`, `company`, `user`)
  - [models/job.py](models/job.py)

- `ml/` — Machine-learning modules
  - Salary estimator: [ml/salary_estimator](ml/salary_estimator)
  - Scam detector: [ml/scam_detector](ml/scam_detector)
  - Skill extractor pipeline: [ml/skill_extractor](ml/skill_extractor)

- `infra/` — Dockerfiles, k8s/helm manifests, and service-specific infra
  - Dockerfiles for workers, gateway, collector: [infra/docker](infra/docker)
  - Kubernetes manifests: [infra/k8s](infra/k8s)

- `observability/` — Prometheus and Grafana configs
  - [observability/prometheus.yml](observability/prometheus.yml)

- `scripts/` — Helpers, health checks, and dev utilities (e.g., `start_dev.ps1`)

- `tests/` — Unit and integration tests
  - Unit tests: [tests/unit](tests/unit)
  - Integration tests: [tests/integration/test_api.py](tests/integration/test_api.py)

## Key files and entry points

- `pyproject.toml` — project metadata and dependencies.
- `docker-compose.yml` & `docker-compose.prod.yml` — local and production compose stacks.
- Service entrypoints are typically `main.py` under each `services/<name>/main.py`.
- `shared/database/base.py` and `shared/database/session.py` — central ORM / DB session management.

## Communication & data contracts

- Services communicate via Kafka topics defined in `shared/kafka/topics.py`.
- Messages should use the shared domain models in `models/` or normalized DTOs defined in the service folders.

## ML components

- Models live under `ml/`. Each model module exposes a lightweight API the enrichment pipeline calls to compute attributes such as salary estimates, skills, or scam likelihood.
- Training code (when present) lives next to models (e.g., `ml/scam_detector/train.py`).

## How code is organized and typical patterns

- Language: Python packages with service-specific `requirements.txt` files and a top-level `pyproject.toml`.
- Each microservice is designed to be runnable independently; they follow a pattern:
  - `main.py` sets up config, logging, and starts the service loop (HTTP server or Kafka consumer/worker)
  - `__init__.py` exposes package-level imports
  - `requirements.txt` lists service dependencies
- Shared logic (DB, clients, utils) is placed in `shared/` to avoid duplication.

## Developer setup (quick start)

1. Create and activate Python virtual environment (optional for local dev):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Install dependencies (either globally for dev or per-service):

```powershell
pip install -r shared/requirements.txt
# and per-service when needed, e.g.
pip install -r services/gateway/requirements.txt
```

3. Run services locally using `docker-compose.yml`:

```powershell
docker compose up --build
```

4. Run tests:

```powershell
pytest tests/unit
pytest tests/integration
```

Note: Many services expect Kafka and Qdrant (vector DB). `docker-compose.yml` or `infra/` contains supporting service definitions.

## Running a single service for development

- From the repo root, run the service's `main.py` (example):

```powershell
python -m services.gateway.main
```

Adjust `PYTHONPATH` or install the repo in editable mode for imports:

```powershell
pip install -e .
```

## Testing notes

- Unit tests live in `tests/unit`. Use `pytest -q`.
- Integration tests assume dependencies (Kafka, DB) are up; run compose stack before executing integration tests.

## Code conventions and best practices used in this repo

- Prefer small single-purpose services that communicate asynchronously via Kafka.
- Keep domain models in `models/` and reuse them for serialization/deserialization.
- Put shared infrastructure (DB, Kafka clients, utils) under `shared/` to keep consistency.
- Use service-level `requirements.txt` to pin runtime deps; keep `pyproject.toml` for tooling.

## How to add a new service

1. Create `services/<new_service>/` with `__init__.py`, `main.py`, and `requirements.txt`.
2. If it consumes/produces Kafka messages, add topic names in `shared/kafka/topics.py` and document message schema.
3. Reuse `shared/` clients for DB/Kafka/Redis.
4. Add unit tests to `tests/unit` and, if needed, integration tests to `tests/integration`.

## Observability & deployment

- Use `observability/prometheus.yml` and `observability/grafana` for monitoring dashboards.
- `infra/k8s` and `helm/templates` provide Kubernetes deployment artifacts for production.

## Next steps / suggestions

- Add a short `CONTRIBUTING.md` describing how to run the repo locally, service-specific env vars, and message schemas.
- Add small sequence diagrams for critical flows (collector -> deduplicator -> embedder -> search).
- Add sample cURL requests for `gateway` endpoints in `README.md`.

---

File created: PROJECT_DOCUMENTATION.md

If you want, I can add a short `CONTRIBUTING.md`, update `README.md` with trimmed quickstart steps, or generate a sequence diagram in `docs/` next.
