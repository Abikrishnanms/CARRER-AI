# TalentLens — Complete Project Report

> **Status:** ✅ 102 unit tests passing · 0 failures · Fully wired and runnable

---

## 1. What Is TalentLens?

TalentLens is an **AI-powered job intelligence platform** built for the Indian job market. It automatically:

1. **Scrapes** job listings from multiple sources (Adzuna API, Naukri RSS, company career pages)
2. **Cleans & deduplicates** the raw data
3. **Enriches** each job with structured skill extraction and ML salary estimation
4. **Verifies** authenticity using scam detection (XGBoost + rule-based ensemble)
5. **Embeds** jobs into a vector database for semantic search
6. **Serves** everything through a REST API gateway and two web frontends

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    External Sources                          │
│    Adzuna API    Naukri RSS    Company Career Pages          │
└──────────────────────┬──────────────────────────────────────┘
                       │ HTTP scraping
                       ▼
┌──────────────────────────────────┐
│     Collector Service :async     │ ── publishes ──► [job.raw]
└──────────────────────────────────┘
                       │
         ┌─────────────▼────────────┐
         │   Cleaner Service        │ ── [job.cleaned]
         │ HTML strip, salary parse │
         └─────────────┬────────────┘
                       │
         ┌─────────────▼────────────┐
         │  Deduplicator Service    │ ── [job.deduplicated]
         │  Redis fingerprinting    │
         └─────────────┬────────────┘
                       │
         ┌─────────────▼────────────┐
         │  Enrichment Service      │ ── [job.enriched]
         │  Skills + Salary ML      │
         └─────────────┬────────────┘
                       │
         ┌─────────────▼────────────┐
         │  Verifier Service        │ ── [job.verified]
         │  Scam detection + Trust  │
         └─────────────┬────────────┘
                       │
         ┌─────────────▼────────────┐
         │  Embedder Service        │ ── Qdrant vector DB
         │  sentence-transformers   │ ── MongoDB (published)
         └──────────────────────────┘
                       │
              ┌────────▼────────┐
              │   API Gateway   │ :8000
              │   FastAPI + JWT │
              └────────┬────────┘
                  ┌────┴─────┐
            ┌─────▼──┐  ┌────▼────┐
            │JobBoard│  │ Admin   │
            │  :3000 │  │  :3001  │
            └────────┘  └─────────┘
```

### Message Broker
All inter-service communication flows through **Redpanda** (Kafka-compatible). Topics:

| Topic | From | To |
|-------|------|----|
| `job.raw` | Collector | Cleaner |
| `job.cleaned` | Cleaner | Deduplicator |
| `job.deduplicated` | Deduplicator | Enrichment |
| `job.enriched` | Enrichment | Verifier |
| `job.verified` | Verifier | Embedder |
| `job.embedded` | Embedder | — (final state in MongoDB) |

---

## 3. Full File Structure

```
Job Scrapping/
├── services/                   ← 13 Microservices
│   ├── gateway/                ← FastAPI API Gateway (port 8000)
│   ├── collector/              ← Job scraping agents
│   ├── cleaner/                ← Data normalization
│   ├── deduplicator/           ← Redis-based dedup
│   ├── enrichment/             ← Skills + Salary ML
│   ├── verifier/               ← Scam detection + trust
│   ├── embedder/               ← Vector embeddings → Qdrant
│   ├── search/                 ← Elasticsearch search API (8002)
│   ├── analytics/              ← Pipeline metrics API (8003)
│   ├── auth/                   ← JWT authentication service
│   ├── notifier/               ← Email/push job alerts
│   ├── feedback/               ← User feedback collection
│   └── orchestrator/           ← Pipeline orchestration
│
├── shared/                     ← Shared library (imported by all services)
│   ├── database/
│   │   ├── session.py          ← Motor/MongoDB client singleton + indexes
│   │   ├── base.py             ← Collection schema + index definitions
│   │   ├── models.py           ← MongoDB collection models
│   │   └── migrations/env.py   ← Alembic stub (MongoDB is schema-less)
│   ├── kafka/
│   │   ├── consumer.py         ← Async Kafka consumer wrapper
│   │   ├── producer.py         ← Async Kafka producer wrapper
│   │   └── topics.py           ← All topic names + configs
│   ├── llm/
│   │   └── router.py           ← LLM router (OpenAI / Ollama)
│   ├── models/
│   │   ├── job.py              ← Pydantic Job model (JobListing, SalaryRange)
│   │   ├── user.py             ← Pydantic User model
│   │   └── company.py          ← Pydantic Company model
│   ├── redis/client.py         ← Redis connection helper
│   └── utils/
│       ├── logging.py          ← Structured JSON logging
│       ├── metrics.py          ← Prometheus metrics helpers
│       └── health.py           ← Health check utilities
│
├── ml/                         ← Machine Learning modules
│   ├── salary_estimator/
│   │   ├── estimator.py        ← Rule-based + GradientBoosting engine
│   │   └── model.py            ← Inference wrapper (LPA output, batch)
│   ├── scam_detector/
│   │   ├── train.py            ← XGBoost training + feature extraction
│   │   └── model.py            ← Inference wrapper (rule-based fallback)
│   └── skill_extractor/
│       └── pipeline.py         ← spaCy NER skill extraction pipeline
│
├── frontend/
│   ├── jobboard/               ← Public job board (Vanilla JS SPA)
│   │   ├── index.html
│   │   ├── style.css           ← Glassmorphism dark design system
│   │   └── app.js              ← SPA routing + API client
│   └── admin/                  ← Admin console (Vanilla JS SPA)
│       ├── index.html
│       ├── style.css
│       └── app.js
│
├── infra/
│   ├── docker/                 ← Per-service Dockerfiles (all multi-stage)
│   │   ├── gateway/Dockerfile
│   │   ├── collector/Dockerfile
│   │   ├── cleaner/Dockerfile
│   │   ├── deduplicator/Dockerfile
│   │   ├── enrichment/Dockerfile
│   │   ├── verifier/Dockerfile
│   │   ├── embedder/Dockerfile
│   │   ├── notifier/Dockerfile
│   │   └── qdrant/config.yaml
│   ├── k8s/                    ← Kubernetes manifests
│   │   ├── namespace.yaml
│   │   ├── configmap.yaml
│   │   └── gateway-deployment.yaml (Deployment + Service + HPA)
│   └── observability/
│       ├── prometheus.yml
│       └── grafana/
│           ├── datasources/prometheus.yml
│           └── dashboards/platform_overview.json
│
├── tests/
│   ├── unit/                   ← 102 tests, no infrastructure needed
│   │   ├── test_cleaner.py     ← HTML stripping, salary parse, location
│   │   ├── test_pipeline.py    ← Scam rules, dedup, salary estimation
│   │   ├── test_salary_extractor.py ← Full salary stack tests
│   │   └── test_scam_detector.py    ← Scam ML model tests
│   └── integration/
│       └── test_api.py         ← Gateway API tests (requires MongoDB)
│
├── scripts/
│   ├── start_dev.ps1           ← Windows one-command dev startup
│   ├── init_kafka_topics.py    ← Creates all Kafka topics
│   ├── seed_data.py            ← Seeds 50 sample jobs to MongoDB
│   └── health_check.py         ← Checks all service health endpoints
│
├── docker-compose.yml          ← Full development stack
├── docker-compose.prod.yml     ← Production stack
├── pyproject.toml              ← Python project config + pytest settings
├── .env.example                ← Template for environment variables
└── README.md
```

---

## 4. How Each Service Works

### 4.1 Gateway (`services/gateway/`) — Port 8000
The single external entry point. Built with **FastAPI**.

- **Auth:** JWT tokens via `services/gateway/routers/auth.py` — signup, login, refresh
- **Jobs API:** `routers/jobs.py` — CRUD for job listings, saved jobs, applications
- **Search API:** `routers/search.py` — Elasticsearch full-text + Qdrant semantic search
- **Admin API:** `routers/admin.py` — pipeline control, user management
- **Analytics API:** `routers/analytics.py` — pipeline throughput metrics
- **Rate limiting:** slowapi (100 req/min default)
- **Health check:** `GET /health` → pings MongoDB + Redis

### 4.2 Collector (`services/collector/`) — Worker
Scrapes job listings on a schedule.

- **Adzuna agent** — calls Adzuna Jobs API, paginates results
- **RSS agent** — parses company RSS feeds (Naukri, LinkedIn, etc.)
- Each job is validated with Pydantic and published to `job.raw` Kafka topic

### 4.3 Cleaner (`services/cleaner/`) — Worker
Normalizes raw job data.

- `strip_html()` — removes HTML tags and entities from descriptions
- `normalize_location()` — extracts city/state/country, detects India automatically
- `parse_salary()` — regex-based salary string parser (handles LPA, monthly, USD)
- `detect_job_type()` — full_time / part_time / contract / internship / freelance
- Publishes cleaned jobs to `job.cleaned`

### 4.4 Deduplicator (`services/deduplicator/`) — Worker
Prevents the same job appearing twice.

- **Exact dedup:** checks `source + source_job_id` uniqueness in MongoDB
- **Near dedup:** `generate_fingerprint(title, company, location)` → SHA-256 → matches in MongoDB
- Duplicate jobs are marked `status: duplicate` and not forwarded
- Unique jobs proceed to `job.deduplicated`

### 4.5 Enrichment (`services/enrichment/`) — Worker
The intelligence layer — runs two agents **concurrently** via `asyncio.gather`:

**Skill Extraction:**
- `SkillExtractionAgent` — matches against a taxonomy of 500+ skills
- Optional spaCy NER enhancement (falls back to regex if spaCy not installed)
- Outputs: `required_skills`, `nice_to_have_skills`, `tech_stack`

**Salary Extraction + ML Estimation:**
- `SalaryExtractionAgent` — regex patterns for LPA, monthly, USD formats; description scanning
- `SalaryEstimator` (ML) — Gradient Boosting fallback when no explicit salary found
- Priority chain: explicit high-confidence → LLM-extracted → ML estimated → unknown
- Outputs: `salary.min`, `salary.max`, `salary.currency`, `salary.is_estimated`

### 4.6 Verifier (`services/verifier/`) — Worker
Scores every job for authenticity.

**Scam Detector (`agents/scam_detector.py`):**
- 12 SCAM_PATTERNS (regex) covering: fee requests, WhatsApp-only contact, unrealistic salary, WFH spam, data entry scams, MLM indicators, urgency tactics
- Structural checks: very short description, generic company name, personal email contact, excessive CAPS
- XGBoost ML model fallback (when `ml/scam_detector/model.pkl` exists)
- Score 0.0 = safe, 1.0 = certain scam

**Company Trust Agent (`agents/company_trust.py`):**
- Instant blacklist check (MLM patterns, earn-daily-guarantee phrases)
- 34-company verified whitelist (Google, Infosys, Accenture, etc.) → +30 pts
- Scam report history, company name quality, website/LinkedIn presence
- Score 0–100

### 4.7 Embedder (`services/embedder/`) — Worker
Creates semantic search capability.

- Model: `all-MiniLM-L6-v2` (384-dim embeddings via `sentence-transformers`)
- Embeds: `title + description + skills` concatenated
- Stores vector in **Qdrant** collection `jobs`
- Updates job `status: published` in MongoDB
- Model is pre-downloaded and cached inside Docker image at build time

### 4.8 Search (`services/search/`) — Port 8002
Dual-mode search API:
- **Full-text:** Elasticsearch for keyword/filter search
- **Semantic:** Qdrant for "find similar jobs" / natural language queries

### 4.9 Analytics (`services/analytics/`) — Port 8003
Tracks pipeline metrics: jobs collected/cleaned/enriched per hour, scam detection rates, salary distribution histograms.

### 4.10 Auth / Notifier / Feedback / Orchestrator
Supporting services for user management, email/push job alerts, feedback collection, and pipeline scheduling.

---

## 5. ML Models

### 5.1 Salary Estimator
**File:** `ml/salary_estimator/estimator.py`

Rule-based engine (always available) + optional trained Gradient Boosting model:

```
Title → role detection → base salary range (ROLE_SALARY_MAP)
     → experience multiplier (entry: 0.6×, senior: 1.4×, lead: 1.8×)
     → location multiplier (Bangalore/Hyderabad: 1.2×, Mumbai: 1.1×)
     → company type multiplier (FAANG: 1.5×, startup: 0.85×)
     → skill premium (+1–8 LPA for cloud/ML/blockchain skills)
     → output: {min_lpa, median_lpa, max_lpa, confidence}
```

**Known roles:** Data Scientist, Python/Java/Node Developer, DevOps, ML Engineer, Product Manager, etc.
**Fallback for unknown roles:** General Software Engineer bracket.

### 5.2 Scam Detector
**File:** `ml/scam_detector/train.py` + `model.py`

Feature engineering (19 features) → XGBoost classifier:
- Keyword density, WhatsApp/Telegram URL presence, suspicious domain
- Unrealistic salary per period, registration fee request, upfront payment
- Company name signals, trusted source flag, skill count

Training: `python ml/scam_detector/train.py --data data/labeled_jobs.csv`

### 5.3 Skill Extractor
**File:** `ml/skill_extractor/pipeline.py`

spaCy EntityRuler with a curated vocabulary of 500+ technical skills, organized into categories: programming languages, frameworks, cloud platforms, databases, DevOps tools, ML/AI libraries.

---

## 6. Shared Library

All services import from `shared/` via `PYTHONPATH`:

| Module | Purpose |
|--------|---------|
| `shared.database.session` | Motor async MongoDB client singleton, `create_tables()` index init |
| `shared.kafka.consumer` | `KafkaConsumerClient` — async consumer with auto-reconnect |
| `shared.kafka.producer` | `KafkaProducerClient` — async producer with backpressure |
| `shared.kafka.topics` | `TOPICS` enum with all topic names |
| `shared.models.job` | `JobListing`, `SalaryRange` Pydantic models |
| `shared.llm.router` | Routes LLM calls to OpenAI or local Ollama |
| `shared.redis.client` | Redis connection pool |
| `shared.utils.logging` | JSON structured logging |
| `shared.utils.metrics` | Prometheus Counter/Gauge helpers |

---

## 7. Frontend

Both frontends are **vanilla JS SPAs** (no framework) with a dark glassmorphism design:

**Job Board** (`frontend/jobboard/`) — Port 3000
- Browse and search job listings
- Filter by skills, salary, location, job type
- View job details, apply button
- Save jobs, set up job alerts

**Admin Console** (`frontend/admin/`) — Port 3001
- Pipeline monitoring dashboard
- Service health overview
- Job moderation (approve/reject)
- User management
- Analytics charts

---

## 8. Infrastructure

### Docker Compose Services

| Container | Image | Port(s) |
|-----------|-------|---------|
| `jip-mongodb` | mongo:7 | 27017 |
| `jip-redis` | redis:7-alpine | 6379 |
| `jip-redpanda` | redpanda | 9092, 8081, 8082 |
| `jip-redpanda-console` | redpanda console | 8080 |
| `jip-kafka-init` | python:3.12-slim | — (one-shot) |
| `jip-qdrant` | qdrant/qdrant | 6333, 6334 |
| `jip-elasticsearch` | elasticsearch:8.12 | 9200 |
| `jip-minio` | minio/minio | 9000, 9001 |
| `jip-prometheus` | prom/prometheus | 9090 |
| `jip-grafana` | grafana/grafana | 3002 |
| `jip-mlflow` | mlflow | 5000 |
| All Python services | custom builds | 8000–8003 |

---

## 9. How to Run

### Option A — Local Development (Recommended for development)

**Step 1: Prerequisites**
```powershell
# Ensure Docker Desktop is running
# Ensure Python 3.10+ is on PATH
python --version   # should say 3.10+
```

**Step 2: Configure environment**
```powershell
cd "c:\Users\Vivobook pro 15\Desktop\Job Scrapping"
copy .env.example .env
# Open .env and add your API keys (optional for basic testing)
```

**Step 3: Install Python dependencies locally**
```powershell
pip install -r shared/requirements.txt
pip install -r services/gateway/requirements.txt
# (repeat for whichever services you want to run locally)
```

**Step 4: Start everything with one command**
```powershell
.\scripts\start_dev.ps1
```

This script:
1. Starts all Docker infrastructure (MongoDB, Redis, Redpanda, Qdrant, etc.)
2. Waits for health checks to pass
3. Opens each Python service in a **separate terminal window**

**Step 5: Seed sample data**
```powershell
python scripts/seed_data.py
```

**Step 6: Check everything is healthy**
```powershell
python scripts/health_check.py
```

### Option B — Full Docker Compose

```powershell
cd "c:\Users\Vivobook pro 15\Desktop\Job Scrapping"
docker compose up -d
```

Wait ~60 seconds for all services to start, then seed data:
```powershell
docker compose exec gateway python scripts/seed_data.py
```

### Option C — Infrastructure Only + Manual Services

```powershell
# Start only Docker infra (no Python services)
.\scripts\start_dev.ps1 -InfraOnly

# Then run individual services in separate terminals:
$env:PYTHONPATH = "c:\Users\Vivobook pro 15\Desktop\Job Scrapping"
uvicorn services.gateway.main:app --reload --port 8000
python -m services.cleaner.main
# ... etc
```

### Option D — Stop Everything

```powershell
.\scripts\start_dev.ps1 -Stop
```

---

## 10. Service URLs After Startup

| Service | URL | Purpose |
|---------|-----|---------|
| **API Gateway** | http://localhost:8000 | Main REST API |
| **API Docs** | http://localhost:8000/docs | Interactive Swagger UI |
| **API Health** | http://localhost:8000/health | MongoDB + Redis health |
| **Job Board** | http://localhost:3000 | Public job listings |
| **Admin Console** | http://localhost:3001 | Pipeline management |
| **Redpanda Console** | http://localhost:8080 | Kafka topic inspector |
| **Grafana** | http://localhost:3002 | Dashboards (admin/admin) |
| **Prometheus** | http://localhost:9090 | Raw metrics |
| **MLflow** | http://localhost:5000 | ML experiment tracking |
| **Qdrant** | http://localhost:6333 | Vector DB web UI |
| **MinIO Console** | http://localhost:9001 | Object storage (minioadmin/minioadmin123) |
| **Elasticsearch** | http://localhost:9200 | Search engine |

---

## 11. Running Tests

```powershell
cd "c:\Users\Vivobook pro 15\Desktop\Job Scrapping"
$env:PYTHONPATH = (Get-Location).Path

# Unit tests (no Docker/infrastructure needed)
python -m pytest tests/unit/ -v

# Run specific test file
python -m pytest tests/unit/test_salary_extractor.py -v

# Integration tests (requires MongoDB running)
python -m pytest tests/integration/ -v

# With coverage report
python -m pytest tests/unit/ --cov=services --cov=shared --cov-report=html
```

**Current test results:** `102 passed, 5 skipped, 0 failed`

| Test File | Tests | Covers |
|-----------|-------|--------|
| `test_cleaner.py` | 22 | HTML stripping, location normalization, salary parsing |
| `test_pipeline.py` | 35 | Scam rules, dedup fingerprinting, salary data assembly |
| `test_salary_extractor.py` | 34 | Regex patterns, ML estimator, SalaryModel wrapper |
| `test_scam_detector.py` | 16 | Feature extraction, ScamDetectionAgent, ScamDetectorModel |

---

## 12. Key Configuration (`.env`)

```bash
# MongoDB
MONGO_URI=mongodb://admin:admin123@localhost:27017/jobplatform?authSource=admin
MONGO_USER=admin
MONGO_PASSWORD=admin123

# Redis
REDIS_URL=redis://localhost:6379/0

# Kafka
KAFKA_BOOTSTRAP_SERVERS=localhost:9092

# API Keys (optional — services degrade gracefully without them)
ADZUNA_API_ID=your_id_here
ADZUNA_API_KEY=your_key_here
OPENAI_API_KEY=sk-...          # For LLM salary/skill extraction
OLLAMA_BASE_URL=http://localhost:11434  # Alternative: local Ollama

# Auth
JWT_SECRET_KEY=change-me-in-production
JWT_ALGORITHM=HS256

# Email (for Notifier service)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your@email.com
SMTP_PASSWORD=your_app_password
```

---

## 13. Training ML Models

```powershell
# Salary Estimator (requires labeled CSV with title, skills, location, salary columns)
python ml/salary_estimator/estimator.py --train --data data/labeled_salaries.csv

# Scam Detector (requires labeled CSV with is_scam column: 0=legit, 1=scam)
python ml/scam_detector/train.py --data data/labeled_jobs.csv --output ml/scam_detector/model.pkl
```

Without trained models, both use the rule-based fallback automatically — the platform works out-of-the-box.

---

## 14. Bugs Fixed During Development

| Bug | File | Impact |
|-----|------|--------|
| `apply_url` not included in scam rule scanning | `scam_detector.py` | WhatsApp/Telegram URL patterns never fired |
| Compact lakh format `₹5L-10L` not parsed | `salary_extractor.py` | Common Indian salary format returned `None` |
| `analyze_sync()` doesn't exist — method is async | Tests | All scam detection tests were failing |
| `_compute_fingerprint` not on class — it's module-level | Tests | All dedup tests were failing |
| Unicode `✓ →` in PowerShell script | `start_dev.ps1` | Script couldn't run at all |

---

## 15. Kubernetes Deployment (Production)

```powershell
# Apply namespace and config
kubectl apply -f infra/k8s/namespace.yaml
kubectl apply -f infra/k8s/configmap.yaml

# Create secrets (replace values)
kubectl create secret generic platform-secrets \
  --from-literal=MONGO_URI="mongodb://..." \
  --from-literal=JWT_SECRET_KEY="your-secret" \
  -n talentlens

# Deploy gateway
kubectl apply -f infra/k8s/gateway-deployment.yaml

# Check status
kubectl get pods -n talentlens
kubectl get hpa -n talentlens   # HPA auto-scales 2→10 pods on CPU/memory
```
