# 🧠 TalentLens — AI-Powered Job Intelligence Platform

> An enterprise-grade, microservices job scraping and intelligence platform for the Indian market. Collects, cleans, deduplicates, enriches, and verifies job listings with ML-powered salary estimation, scam detection, and semantic search.

[![CI](https://github.com/your-org/talentlens/actions/workflows/ci.yml/badge.svg)](https://github.com/your-org/talentlens/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/Python-3.12-blue)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

---

## 🏗️ Architecture

```
                          ┌─────────────────────────────────────┐
                          │          API Gateway :8000           │
                          │       FastAPI + JWT + Rate Limit     │
                          └──────────────┬──────────────────────┘
                                         │
              ┌──────────────────────────▼──────────────────────────┐
              │                  Kafka (Redpanda)                     │
              │  job.raw → job.cleaned → job.deduplicated             │
              │  → job.enriched → job.verified → job.embedded         │
              └──────────────────────────────────────────────────────┘
                     │          │          │          │
              ┌──────▼──┐ ┌────▼────┐ ┌──▼──────┐ ┌▼──────────┐
              │Collector│ │ Cleaner │ │Deduplicat│ │ Enrichment│
              │(Adzuna  │ │ HTML+   │ │ Redis    │ │ Skills +  │
              │ Naukri  │ │ Salary  │ │ Fingerpr.│ │ Salary ML │
              │ RSS)    │ │ Parse   │ │          │ │           │
              └─────────┘ └─────────┘ └──────────┘ └───────────┘
                                                          │
                    ┌─────────────────────────────────────▼───────┐
                    │  Verifier (XGBoost Scam Detector + Trust)    │
                    │  Embedder (sentence-transformers → Qdrant)   │
                    └─────────────────────────────────────────────┘
```

## 🚀 Quick Start

### Prerequisites

- Docker Desktop
- Python 3.12+
- PowerShell 7+ (Windows) or Bash (Linux/macOS)

### 1. Clone & configure

```bash
git clone https://github.com/your-org/talentlens.git
cd talentlens
cp .env.example .env
# Edit .env with your API keys (Adzuna, OpenAI, SMTP, etc.)
```

### 2. Start everything (Windows)

```powershell
.\scripts\start_dev.ps1
```

This will:
1. Pull and start Docker infrastructure (MongoDB, Redis, Redpanda, Qdrant, Elasticsearch)
2. Wait for health checks
3. Launch each Python service in a separate terminal window

### 3. Seed sample data

```bash
python scripts/seed_data.py
```

### 4. Check service health

```bash
python scripts/health_check.py
```

### Service URLs

| Service | URL |
|---------|-----|
| API Gateway | http://localhost:8000/docs |
| Job Board UI | http://localhost:3000 |
| Admin Console | http://localhost:3001 |
| Redpanda Console | http://localhost:8080 |
| Grafana | http://localhost:3002 |
| MLflow | http://localhost:5000 |
| Prometheus | http://localhost:9090 |
| Qdrant | http://localhost:6333 |
| MinIO Console | http://localhost:9001 |

---

## 📂 Project Structure

```
talentlens/
├── services/               # Microservices
│   ├── gateway/            # FastAPI API gateway (port 8000)
│   ├── collector/          # Job scraping agents (Adzuna, Naukri, RSS)
│   ├── cleaner/            # Data normalization + salary parsing
│   ├── deduplicator/       # Redis-based content fingerprinting
│   ├── enrichment/         # Skill extraction + salary estimation
│   ├── verifier/           # Scam detection + company trust scoring
│   ├── embedder/           # Sentence embeddings → Qdrant
│   ├── search/             # Elasticsearch semantic search
│   ├── auth/               # JWT authentication
│   ├── notifier/           # Email/push job alerts
│   ├── analytics/          # Pipeline metrics API
│   ├── feedback/           # User feedback collection
│   └── orchestrator/       # Pipeline orchestration
├── shared/                 # Shared library
│   ├── database/           # Motor/MongoDB session + indexes
│   ├── kafka/              # Async consumer/producer
│   ├── llm/                # LLM router (OpenAI / Ollama)
│   ├── models/             # Pydantic models (Job, User, Company)
│   ├── redis/              # Redis client
│   └── utils/              # Logging, metrics, health
├── ml/                     # Machine learning modules
│   ├── salary_estimator/   # GradientBoosting salary prediction
│   ├── scam_detector/      # XGBoost scam detection
│   └── skill_extractor/    # spaCy NER skill pipeline
├── frontend/
│   ├── jobboard/           # Public job board (Vanilla JS SPA)
│   └── admin/              # Admin console (Vanilla JS SPA)
├── infra/
│   ├── docker/             # Per-service Dockerfiles
│   ├── k8s/                # Kubernetes manifests
│   └── observability/      # Prometheus + Grafana config
├── tests/
│   ├── unit/               # Fast unit tests (no infrastructure needed)
│   └── integration/        # API tests (requires MongoDB)
└── scripts/
    ├── start_dev.ps1       # Windows dev startup
    ├── init_kafka_topics.py
    ├── seed_data.py
    └── health_check.py
```

---

## 🔧 Development

### Install dependencies

```bash
# Shared + gateway (as example)
pip install -r shared/requirements.txt
pip install -r services/gateway/requirements.txt

# Or install all at once
pip install $(Get-ChildItem services/*/requirements.txt | % { "-r $_" })
```

### Run a single service locally

```bash
# API Gateway
PYTHONPATH=. uvicorn services.gateway.main:app --reload --port 8000
#correct command
$env:PYTHONPATH = "."; uvicorn services.gateway.main:app --reload --port 8000

# Any worker service
PYTHONPATH=. python -m services.cleaner.main
```

### Run tests

```bash
# Unit tests (no Docker needed)
pytest tests/unit/ -v

# Integration tests (requires running MongoDB)
pytest tests/integration/ -v

# All tests with coverage
pytest --cov=services --cov=shared --cov-report=html
```

### Train ML models

```bash
# Salary estimator (requires labeled CSV)
python ml/salary_estimator/estimator.py --train --data data/labeled_salaries.csv

# Scam detector (requires labeled CSV)
python ml/scam_detector/train.py --data data/labeled_jobs.csv
```

---

## 🐳 Docker

### Development (all services)

```bash
docker compose up -d
```

### Production

```bash
docker compose -f docker-compose.prod.yml up -d
```

### Build a single service

```bash
docker build -f infra/docker/gateway/Dockerfile -t talentlens/gateway:latest .
```

---

## ☸️ Kubernetes

```bash
# Create namespace
kubectl apply -f infra/k8s/namespace.yaml

# Apply config
kubectl apply -f infra/k8s/configmap.yaml

# Deploy gateway
kubectl apply -f infra/k8s/gateway-deployment.yaml

# Check pods
kubectl get pods -n talentlens
```

---

## 🤖 ML Models

| Model | Algorithm | Input | Output |
|-------|-----------|-------|--------|
| Salary Estimator | Gradient Boosting + Rules | Title, skills, location, experience | Salary range (INR) |
| Scam Detector | XGBoost + Rules | Job text, URL, source | Scam probability (0–1) |
| Skill Extractor | spaCy NER + Taxonomy | Job description | Structured skill list |

All models degrade gracefully to rule-based fallbacks when no trained `.pkl` file exists.

---

## 🌊 Pipeline Flow

```
1. Collector     → scrapes jobs from Adzuna, Naukri, RSS → publishes to job.raw
2. Cleaner       → strips HTML, parses salary/location   → job.cleaned
3. Deduplicator  → Redis fingerprint check               → job.deduplicated
4. Enrichment    → extracts skills + estimates salary    → job.enriched
5. Verifier      → scam detection + company trust        → job.verified
6. Embedder      → generates embeddings → Qdrant         → job.embedded
7. Gateway       → serves via REST API                   → Frontend
```

---

## 📊 Observability

- **Prometheus** → scrapes all services at `/metrics`
- **Grafana** → pre-built dashboard at http://localhost:3002 (admin/admin)
- **Redpanda Console** → Kafka topic inspection at http://localhost:8080
- **MLflow** → experiment tracking at http://localhost:5000

---

## 🤝 Contributing

1. Fork the repo
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Run tests: `pytest tests/unit/ -v`
4. Submit a PR

---

## 📄 License

MIT © TalentLens Team
