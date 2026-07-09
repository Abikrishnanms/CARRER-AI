# CareerAI Production Coding Standards

**Version:** 2.0.0  
**Last Updated:** 2026-07-08  
**Applies To:** All microservices, agents, shared libraries, and deployment scripts.

---

## 1. Core Philosophy

- **Correctness over cleverness:** Write code that is obviously correct. If a future engineer (or you in 6 months) cannot understand it instantly, rewrite it.
- **Fail explicitly:** Never swallow exceptions. If an agent cannot parse a job, log the exact failure and route the message to the Dead Letter Queue (DLQ)—do not guess or patch the data.
- **Observability is a feature:** If an event is not logged, traced, and metered, it did not happen in a production sense.
- **Statelessness is mandatory:** All agents and services must store their state externally (Redis, PostgreSQL, or Kafka offsets). Restarting a container must never cause data loss or duplicate processing.
- **Contract-First:** Every inter-agent communication (RabbitMQ/Kafka messages) must have a versioned JSON schema, strictly enforced by Pydantic v2.

---

## 2. Project Structure (Production-Ready)

```text
career-ai/
├── .github/
│   └── workflows/                 # CI/CD pipelines (lint, test, build, deploy)
├── app/
│   ├── api/                       # FastAPI route handlers (REST endpoints)
│   ├── agents/                    # LangGraph / AG2 Agent definitions
│   │   ├── base_agent.py          # Abstract BaseAgent class with lifecycle hooks
│   │   ├── orchestrator/          # Master coordination agent
│   │   ├── scraper/               # Platform-specific scraping logic
│   │   ├── fraud/                 # Fraud detection ensemble agent
│   │   └── validator/             # Company website validation agent
│   ├── broker/                    # RabbitMQ/Kafka producers & consumers
│   │   ├── producers.py
│   │   └── consumers.py
│   ├── config/                    # Pydantic Settings (env var loading)
│   │   ├── settings.py
│   │   └── logging_config.py
│   ├── database/                  # SQLAlchemy models + Alembic migrations
│   │   ├── models/
│   │   └── migrations/
│   ├── models/                    # Shared Pydantic schemas (Job, Company, Message)
│   │   ├── job.py
│   │   └── message_envelope.py
│   ├── prompts/                   # YAML files for LLM system prompts (versioned)
│   │   ├── fraud_detector_v1.yaml
│   │   └── self_healer_v1.yaml
│   ├── repositories/              # Data access layer (PostgreSQL/Redis CRUD)
│   │   ├── job_repository.py
│   │   └── cache_repository.py
│   ├── services/                  # Core business logic (orchestration, scoring)
│   │   └── decision_engine.py
│   ├── utils/                     # Shared helpers (retry, time, hashing)
│   │   ├── retry_decorator.py
│   │   └── correlation_id.py
│   └── main.py                    # FastAPI application entrypoint
├── scripts/                       # Maintenance scripts (backups, DB seeding)
├── tests/
│   ├── unit/                      # Isolated function tests (mocked LLMs/DBs)
│   ├── integration/               # Testcontainers (Postgres, Redis, RabbitMQ)
│   └── e2e/                       # Full pipeline tests (staging scrapers)
├── docker-compose.yml             # Local development orchestration
├── Dockerfile                     # Multi-stage production build
├── pyproject.toml                 # Dependencies + Ruff/Mypy configuration
├── uv.lock                        # Deterministic dependency locking (use uv/poetry)
├── .pre-commit-config.yaml        # Git hooks (enforce standards locally)
└── README.md
```
---
## 3. Python & Dependency Management

- **Python Version:** Must be Python 3.12+ (must match the slim Docker base image).

- **Package Manager:** Use `uv` (fastest) or `poetry`. Do not use `requirements.txt` for production—it lacks deterministic locking and causes "works on my machine" bugs.

- **Linting & Formatting:** Enforce using `ruff` (replaces Black, Flake8, isort, and pyupgrade).

  - Line length: **88 characters** (PEP 8).
  - The command `ruff check --fix .` must pass in CI/CD before merging.

- **Type Checking:** Strict `mypy` with `--strict` flag. Disallow the use of `Any` unless explicitly justified.

### `pyproject.toml` excerpt

```toml
[project]
name = "career-ai"
version = "2.0.0"
requires-python = ">=3.12"

[tool.ruff]
line-length = 88
target-version = "py312"
select = ["E", "F", "I", "N", "UP", "B", "C4", "SIM"]

[tool.mypy]
strict = true
disallow_any_unimported = true
warn_return_any = true
warn_unused_ignores = true
```
---
## 4. Async/Await Standards (Critical for Performance)

Since this system is heavily I/O-bound (network requests, database queries, message queues):

- All I/O-bound functions must be `async def`.

- Never use `time.sleep()`. Always use `await asyncio.sleep()`.

- Never call blocking libraries (e.g., `requests`) inside async functions. Use `httpx.AsyncClient` or `aio-pika` for brokers.

- Define explicit timeouts for every external call to prevent agent starvation:

```python
async with httpx.AsyncClient(timeout=30.0) as client:
    response = await client.get(url)
```

- Use `asyncio.gather()` for parallel scraping of independent platforms, but enforce semaphore-based rate limiting per platform to avoid IP bans.

```python
sem = asyncio.Semaphore(5)  # Max 5 concurrent requests per platform

async with sem:
    await scrape_platform()
```

---

## 5. Configuration (Strictly 12-Factor)

- **Zero hardcoded values.** No API keys, database URLs, or secrets may appear in the source code.

- Use `pydantic-settings` for all configuration. Group configs by domain (e.g., `RedisSettings`, `OpenAISettings`).

- Environment variables must have a clear prefix (e.g., `REDIS_HOST`, `RABBITMQ_PORT`).

```python
from pydantic_settings import BaseSettings

class RabbitMQSettings(BaseSettings):
    host: str = "localhost"
    port: int = 5672
    vhost: str = "/"
    username: str
    password: str

    @property
    def dsn(self) -> str:
        return (
            f"amqp://{self.username}:{self.password}"
            f"@{self.host}:{self.port}/{self.vhost}"
        )

    class Config:
        env_prefix = "RABBITMQ_"
        env_file = ".env"
```

---

## 6. Data Contracts (Pydantic v2 Strict)

- Every message published to RabbitMQ/Kafka must contain a top-level `version: str` field for schema evolution.

- Use **Pydantic** models for all JSON serialization/deserialization. Never use plain Python dictionaries for internal state passing between agents.

```python
from datetime import datetime
from enum import Enum
import uuid

from pydantic import BaseModel, Field


class ProcessingStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"


class MessageEnvelope(BaseModel):
    version: str = "1.0"
    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    correlation_id: str  # Distributed tracing across all agents
    source_agent: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    payload: dict  # Validated nested Pydantic model
```

---

## 7. AI / LLM Agent Standards

- **Prompt Management:** System prompts must be stored in `app/prompts/` as YAML files. Hardcoding multi-line prompts inside Python functions is strictly forbidden.

```yaml
# fraud_detector_v1.yaml

role: "Senior Fraud Detection Analyst"
task: "Analyze the job description for scam indicators (urgent wire transfers, free email domains, unrealistic salary)."
output_format: "Return a JSON with 'fraud_score' (0–1) and 'reasoning'."
```

- **Token Budgeting:** Every LLM call must log `input_tokens` and `output_tokens` to Prometheus. Implement a circuit-breaker if token costs exceed a defined threshold per job.

- **Retry Logic:** All LLM calls must be wrapped with `tenacity` (retry on **429 Rate Limit**, **500 Internal Server Error**, or **504 Gateway Timeout**) using exponential backoff.

- **Temperature Management:** Use `temperature=0.0` for extraction/classification tasks (deterministic). Use `temperature=0.7` only for creative re-planning (e.g., Self-Healing agents).

---

## 8. Error Handling & Dead Letter Queue (DLQ) Strategy

- Catch specific exceptions, never a bare `except:`.

- If an agent fails after **3 retries**, it must publish the failing message to a `dlq_errors` queue with the full stack trace attached in the payload for manual inspection.

- **Idempotency is mandatory:** Every message processed must check Redis for a `processed:{message_id}` flag to prevent duplicate processing if the broker redelivers a message (At-Least-Once semantics).

```python
async def process_job(message: MessageEnvelope):
    # 1. Idempotency check
    if await redis.exists(f"processed:{message.message_id}"):
        logger.info("Duplicate message detected, acknowledging.")
        return

    # 2. Process
    try:
        await handle_payload(message.payload)

    except Exception:
        logger.exception(
            "Processing failed",
            message_id=message.message_id,
        )
        raise  # Let the consumer retry or route to DLQ

    # 3. Mark as done
    await redis.setex(
        f"processed:{message.message_id}",
        86400,
        "done",
    )
```
---
## 9. Structured Logging & Observability

- Never use `print()`. Use `structlog` to output JSON logs to stdout (which gets ingested by ELK/Loki).

- Every log entry must contain:

  - `correlation_id` (traces a single job across all agents).
  - `service_name` (e.g., `fraud-detector`).
  - `timestamp` (ISO 8601).
  - `level` (`INFO`, `WARNING`, `ERROR`).

```python
import structlog

logger = structlog.get_logger()


async def check_fraud(job_id: str):
    logger.info("Fraud check started", job_id=job_id)

    # ... logic ...

    logger.info(
        "Fraud check completed",
        job_id=job_id,
        fraud_score=0.92,
        latency_ms=150,
    )
```

- **Metrics (Prometheus):** Expose counters for:

  - `jobs_processed_total{agent}`
  - `agent_errors_total{type}`
  - `llm_token_usage{model}`

---

## 10. Database (SQLAlchemy) Standards

- **Naming Convention:** Use singular nouns for table names (e.g., `job`, `company`, `agent_heartbeat`).

- **Migrations:** Use `alembic`. Never manually alter tables in production. Every migration file must have a `downgrade` function defined to allow rollbacks.

- **Connection Pooling:** Enforce a pool size (e.g., `pool_size=20`, `max_overflow=10`) to avoid exhausting PostgreSQL connections under load.

- **Indexes:** All foreign keys and columns used in `WHERE` or `JOIN` clauses must have explicit database indexes defined in the model.

---

## 11. Testing Standards (Non-Negotiable)

- **Unit Tests:** Must run in **< 1 second**. Mock all external dependencies (HTTPX clients, LLM API calls).

- **Integration Tests:** Use `testcontainers` to spin up real PostgreSQL, Redis, and RabbitMQ instances inside Docker.

- **Coverage:** Minimum **80%** code coverage. The CI/CD pipeline must fail if coverage drops below this threshold.

- **Test Data:** Use `factory-boy` to generate consistent test fixtures.

```python
# Example: Mocking an LLM response

def test_fraud_agent_detects_scam(mocker):
    mock_llm = mocker.patch(
        "app.agents.fraud.llm_client.generate"
    )

    mock_llm.return_value = {
        "score": 0.95,
        "reasoning": "Contains wire transfer request.",
    }

    result = await fraud_agent.execute(scam_job_input)

    assert result.status == "suspicious"
```

---

## 12. Git Workflow & CI/CD

- **Branch Strategy:**

  - `main` → Production (tagged releases).
  - `develop` → Staging environment.
  - `feature/xxx` → Feature branches branched off `develop`.

- **Pre-commit Hooks:** Must run `ruff`, `mypy`, and `pytest --fail-fast` locally before pushing.

- **Commit Messages:** Follow Conventional Commits:

  - `feat:` new feature for a user/agent.
  - `fix:` bug fix.
  - `refactor:` code restructuring without behavior change.
  - `docs:` documentation updates.
  - `test:` adding or refactoring tests.

### CI/CD Pipeline (GitHub Actions)

1. Lint & Type Check (`ruff` + `mypy`).
2. Run Unit & Integration Tests (with Testcontainers).
3. Build Docker image with tags `:latest` and `:$GITHUB_SHA`.
4. Deploy to Kubernetes staging environment (if push to `develop`).
5. Deploy to production (if push to `main`).

---

## 13. Containerization (Docker) Standards

- **Base Image:** Use `python:3.12-slim-bookworm` to minimize the attack surface and image size.

- **Non-Root User:** Create a dedicated `appuser` (UID 1000) in the Dockerfile. The application must run as this user, never as `root`.

- **Layer Caching:** Copy dependency files (`pyproject.toml` and `uv.lock`) before copying the source code to cache the heavy dependency layer.

- **Healthchecks:** Define a `HEALTHCHECK` command for all long-running services (FastAPI, Consumers) to allow Kubernetes to restart unresponsive pods.

```dockerfile
FROM python:3.12-slim AS builder

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN uv sync --frozen --no-dev


FROM python:3.12-slim

RUN addgroup --system --gid 1000 appuser && \
    adduser --system --uid 1000 --gid 1000 appuser

USER appuser

WORKDIR /app

COPY --from=builder /app /app

HEALTHCHECK --interval=30s --timeout=3s \
CMD python -c "import requests; requests.get('http://localhost:8000/health')" || exit 1

CMD [
  "uv",
  "run",
  "uvicorn",
  "app.main:app",
  "--host",
  "0.0.0.0",
  "--port",
  "8000"
]
```

---
## 14. Code Review Checklist

Before requesting a Pull Request review, the author must verify:

- The code passes `ruff` and `mypy` locally without warnings.

- All new public functions and classes have docstrings and full type hints.

- There are zero `print()` statements; all logs use `structlog`.

- LLM prompts are stored in `app/prompts/` YAML files, not hardcoded.

- Database queries use appropriate indexes (verified via `EXPLAIN`).

- All external API calls (HTTP, LLM, DB) have explicit timeouts.

- Unit tests cover the new logic with at least **80%** coverage.

- The `docker-compose up --build` command runs successfully without errors.

- The `.env.example` file has been updated with any new environment variables.

---

## 15. Definition of Done (DoD)

A feature, agent, or bugfix is considered **Complete** only when:

1. The code is merged into the `develop` branch via a Pull Request with at least one approval.

2. All CI/CD pipeline checks have passed (Linting, Type Checking, Tests, Build).

3. The feature has been manually smoke-tested against the staging environment.

4. The relevant sections of the `README.md` or `/docs` have been updated.

5. The deployment to production has been confirmed (if applicable) and no error rate spikes are observed in Grafana.

---

## 16. References & Tools

- **PEP 8** – Python Style Guide

- **Pydantic v2** – Data Validation Documentation

- **structlog** – Structured Logging

- **LangGraph** – Agent Orchestration Patterns

- **Testcontainers** – Integration Testing with Real Dependencies

- **Ruff** – Fast Python Linter & Formatter
---
```text
---

**Copy the entire block above, save it as `Coding_standards.md`, and commit it to your repository.**

This file is now a self-contained, production-grade document with zero external commentary.
```