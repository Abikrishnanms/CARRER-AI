# 🧠 JEXA-AI — AI-Powered Job Intelligence Platform

> An enterprise-grade, fully containerized microservices platform that scrapes, cleans, deduplicates, enriches, verifies, and indexes job listings — powered by ML-based salary estimation, scam detection, and semantic vector search.

[![Python](https://img.shields.io/badge/Python-3.12-blue)](https://python.org)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED)](https://docs.docker.com/compose/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688)](https://fastapi.tiangolo.com)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

---

## ✨ Features

- **8-Stage Real-Time Pipeline** — Collector → Cleaner → Deduplicator → Enrichment → Verifier → Embedder → Notifier, all connected via Kafka (Redpanda)
- **Web Scraping** — Collects real job data from Adzuna, Indeed, LinkedIn, Naukri, government portals, and company career pages
- **ML-Powered Intelligence** — XGBoost scam detection, gradient boosting salary estimation, spaCy NER skill extraction
- **Semantic Search** — SentenceTransformers (`all-MiniLM-L6-v2`) → Qdrant vector database for similarity search
- **Full-Text Search** — Elasticsearch 8 for keyword-based job search
- **Production Observability** — Prometheus metrics + Grafana dashboards + MLflow experiment tracking
- **Two Frontend UIs** — Public Job Board + Admin Dashboard
- **Single-Command Deployment** — `docker compose up -d` brings up the entire platform (19 containers)

---

## 🏗️ Architecture

```
                    ┌─────────────────────────────────────┐
                    │      API Gateway :8000 (FastAPI)     │
                    │   REST API + Swagger + Rate Limit    │
                    └──────────────┬──────────────────────┘
                                   │
        ┌──────────────────────────▼──────────────────────────┐
        │              Redpanda / Kafka (:9092)                │
        │  raw_jobs → cleaned_jobs → deduplicated_jobs         │
        │  → enriched_jobs → verified_jobs → (embedder)        │
        └──────────────────────────────────────────────────────┘
               │          │          │          │
        ┌──────▼──┐ ┌────▼────┐ ┌──▼──────┐ ┌▼──────────┐
        │Collector│ │ Cleaner │ │Deduplicat│ │ Enrichment│
        │  Web    │ │Normalize│ │  Redis   │ │Skills+ML  │
        │Scrapers │ │+ Parse  │ │Fingerprnt│ │+ Salary   │
        └─────────┘ └─────────┘ └──────────┘ └───────────┘
                                                    │
              ┌─────────────────────────────────────▼───────┐
              │  Verifier  — ML scam detection + trust score │
              │  Embedder  — SentenceTransformers → Qdrant   │
              │  Notifier  — Email / Webhook / In-App alerts  │
              └─────────────────────────────────────────────┘

        ┌───────────┐  ┌───────────┐
        │ Job Board │  │   Admin   │
        │  :3000    │  │  :3001    │
        └───────────┘  └───────────┘
```

---

## 🚀 Quick Start

### Prerequisites

| Tool | Version | Check |
|------|---------|-------|
| Docker Engine | 24.0+ | `docker version` |
| Docker Compose | v2.20+ | `docker compose version` |

> **No local Python, Node.js, or npm needed** — everything runs inside containers.

### 1. Clone & Configure

```bash
git clone https://github.com/Abikrishnanms/JEXA-AI.git
cd JEXA-AI
cp .env.example .env
# Edit .env with your API keys (ADZUNA_API_ID, ADZUNA_API_KEY, etc.)
```

### 2. Start Everything

```bash
docker compose up -d
```

This single command launches **19 containers**: 11 infrastructure + 8 microservices + 2 frontends.

### 3. Verify

```bash
# Check all services
docker compose ps

# Test API health
curl http://localhost:8000/health
# → {"status":"healthy","version":"1.0.0","dependencies":{"mongodb":"healthy","redis":"healthy"}}
```

### 4. Open the Platform

| Service | URL |
|---------|-----|
| **Job Board** 💼 | http://localhost:3000 |
| **Admin Dashboard** 🔧 | http://localhost:3001 |
| **API Docs (Swagger)** 📖 | http://localhost:8000/docs |
| Redpanda Console (Kafka) | http://localhost:8080 |
| Grafana Dashboards | http://localhost:3002 |
| Prometheus Metrics | http://localhost:9090 |
| Qdrant Dashboard | http://localhost:6333/dashboard |
| MinIO Console | http://localhost:9001 |
| MLflow | http://localhost:5000 |
| Elasticsearch | http://localhost:9200 |

---

## 📂 Project Structure

```
JEXA-AI/
├── services/                   # Microservices (each has its own Dockerfile)
│   ├── gateway/                # FastAPI API gateway (:8000)
│   ├── collector/              # Job scraping from web sources
│   ├── cleaner/                # Data normalization + salary parsing
│   ├── deduplicator/           # Redis-based content fingerprinting
│   ├── enrichment/             # Skill extraction + salary estimation (ML)
│   ├── verifier/               # Scam detection + company trust scoring
│   ├── embedder/               # SentenceTransformers → Qdrant embeddings
│   ├── notifier/               # Email / webhook / in-app job alerts
│   ├── search/                 # Elasticsearch semantic search
│   ├── analytics/              # Pipeline metrics aggregation
│   ├── auth/                   # JWT authentication
│   ├── feedback/               # User feedback collection
│   └── orchestrator/           # Pipeline orchestration
├── shared/                     # Shared Python library
│   ├── database/               # Motor/MongoDB session management
│   ├── kafka/                  # Async Kafka consumer/producer
│   ├── llm/                    # LLM router (OpenAI / Ollama)
│   ├── models/                 # Pydantic models (Job, User, Company)
│   ├── redis/                  # Redis client utilities
│   └── utils/                  # Logging, metrics, health checks
├── ml/                         # Machine learning modules
│   ├── salary_estimator/       # GradientBoosting salary prediction
│   ├── scam_detector/          # XGBoost scam detection
│   └── skill_extractor/        # spaCy NER skill pipeline
├── frontend/
│   ├── jobboard/               # Public job board UI (:3000)
│   └── admin/                  # Admin dashboard UI (:3001)
├── infra/
│   ├── docker/                 # Per-service Dockerfiles
│   ├── k8s/                    # Kubernetes manifests
│   └── observability/          # Prometheus + Grafana config
├── tests/
│   ├── unit/                   # Unit tests (no infrastructure needed)
│   └── integration/            # API tests (requires MongoDB)
├── scripts/                    # Utility scripts
├── docker-compose.yml          # Development orchestration
├── docker-compose.prod.yml     # Production orchestration
└── .env.example                # Environment variable template
```

---

## 🐳 Docker Services

### Infrastructure (11 Containers)

| Container | Image | Port | Purpose |
|-----------|-------|------|---------|
| `jip-mongodb` | `mongo:7.0` | 27017 | Primary database |
| `jip-redis` | `redis:7-alpine` | 6379 | Cache + dedup fingerprints |
| `jip-redpanda` | `redpandadata/redpanda` | 9092 | Kafka-compatible message broker |
| `jip-redpanda-console` | `redpandadata/console` | 8080 | Kafka management UI |
| `jip-qdrant` | `qdrant/qdrant` | 6333 | Vector database for semantic search |
| `jip-elasticsearch` | `elasticsearch:8.17.0` | 9200 | Full-text search engine |
| `jip-minio` | `minio/minio` | 9000/9001 | S3-compatible object storage |
| `jip-prometheus` | `prom/prometheus` | 9090 | Metrics collection |
| `jip-grafana` | `grafana/grafana` | 3002 | Monitoring dashboards |
| `jip-mlflow` | `ghcr.io/mlflow/mlflow` | 5000 | ML experiment tracking |
| `jip-kafka-init` | `redpandadata/redpanda` | — | Creates 24 Kafka topics |

### Application (8 Microservices + 2 Frontends)

| Container | Service | Type |
|-----------|---------|------|
| `jip-gateway` | API Gateway | FastAPI HTTP (:8000) |
| `jip-collector` | Job Collector | Kafka Worker — scrapes real jobs from the web |
| `jip-cleaner` | Data Cleaner | Kafka Worker — normalizes, strips HTML, parses salaries |
| `jip-deduplicator` | Deduplicator | Kafka Worker — Redis fingerprint-based dedup |
| `jip-verifier` | Verifier | Kafka Worker — ML scam detection + trust scoring |
| `jip-enrichment` | Enrichment | Kafka Worker — skill extraction + salary estimation |
| `jip-embedder` | Embedder | Kafka Worker — vector embeddings → Qdrant |
| `jip-notifier` | Notifier | Kafka Worker — email/webhook notifications |
| `jip-jobboard` | Job Board | Frontend UI (:3000) |
| `jip-admin` | Admin Dashboard | Frontend UI (:3001) |

---

## 🌊 Data Pipeline

```
1. Collector     → Scrapes real jobs from web (Adzuna, Indeed, etc.) → raw_jobs
2. Cleaner       → Strips HTML, parses salary/location               → cleaned_jobs
3. Deduplicator  → Redis fingerprint deduplication                    → deduplicated_jobs
4. Enrichment    → ML skill extraction + salary estimation            → enriched_jobs
5. Verifier      → XGBoost scam detection + trust scoring             → verified_jobs
6. Embedder      → SentenceTransformer embeddings → Qdrant            → published
7. Notifier      → Sends alerts via email/webhook/in-app              → notification_*
8. Gateway       → Serves everything via REST API                     → Frontend UIs
```

All stages are connected via **Kafka topics** (powered by Redpanda). Each stage is an independent microservice that can be scaled, restarted, or replaced independently.

---

## 🤖 ML Models

| Model | Algorithm | Input | Output |
|-------|-----------|-------|--------|
| Salary Estimator | Gradient Boosting + Rules | Title, skills, location, experience | Salary range |
| Scam Detector | XGBoost + Heuristics | Job text, URL, source metadata | Scam probability (0–1) |
| Skill Extractor | spaCy NER + Taxonomy | Job description text | Structured skill list |

All models degrade gracefully to rule-based fallbacks when no trained `.pkl` file exists.

### Training Models

```bash
# Salary estimator
python ml/salary_estimator/estimator.py --train --data data/labeled_salaries.csv

# Scam detector
python ml/scam_detector/train.py --data data/labeled_jobs.csv
```

---

## 🔧 Development

### Rebuild After Code Changes

```bash
# Rebuild specific service
docker compose up -d --build gateway

# Rebuild everything
docker compose up -d --build
```

### View Service Logs

```bash
# Follow logs for a specific service
docker compose logs -f collector

# View last 50 lines
docker logs jip-gateway --tail 50
```

### Run Tests

```bash
# Unit tests (no Docker needed)
pytest tests/unit/ -v

# Integration tests (requires running containers)
pytest tests/integration/ -v

# All tests with coverage
pytest --cov=services --cov=shared --cov-report=html
```

### Stop & Clean

```bash
# Stop (preserves data)
docker compose stop

# Stop and remove containers (preserves volumes)
docker compose down

# Full wipe (destroys ALL data)
docker compose down -v
```

---

## 📊 Observability

| Tool | URL | Purpose |
|------|-----|---------|
| **Prometheus** | http://localhost:9090 | Scrapes all services at `/metrics` |
| **Grafana** | http://localhost:3002 | Pre-built dashboards (login: `admin/admin`) |
| **Redpanda Console** | http://localhost:8080 | Kafka topic inspection & consumer groups |
| **MLflow** | http://localhost:5000 | ML experiment tracking & model registry |

---

## 🤝 Contributing

1. Fork the repo
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make changes and rebuild: `docker compose up -d --build`
4. Run tests: `pytest tests/unit/ -v`
5. Submit a PR

---

## 📄 License

MIT © JEXA-AI Team
