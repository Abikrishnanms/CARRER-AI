# 🧠 Job Intelligence Platform — Deployment Runbook

> **Official Runbook** for deploying the AI-Powered Job Intelligence Platform.
> Last Updated: 2026-08-30 | Environment: Linux / Docker Compose / Python 3.12

---

## 📋 Contents

1. [Executive Summary](#-executive-summary)
2. [Platform Architecture](#-platform-architecture)
3. [Prerequisites](#-prerequisites)
4. [🚀 Quick Start — Single Command](#-quick-start--single-command)
5. [🔧 First-Time Setup — Fresh Install](#-first-time-setup--fresh-install)
6. [🔁 Subsequent Runs](#-subsequent-runs)
7. [🛑 How to Stop the Platform](#-how-to-stop-the-platform)
8. [✅ Post-Deployment Validation Checklist](#-post-deployment-validation-checklist)
9. [📊 Service Inventory](#-service-inventory)
10. [🌐 Live Endpoints Reference](#-live-endpoints-reference)
11. [📝 Troubleshooting Cheat Sheet](#-troubleshooting-cheat-sheet)

---

## 📊 Executive Summary

| Metric | Result |
|--------|--------|
| **Platform Status** | ✅ **FULLY OPERATIONAL** |
| **Total Containers** | **19 running** (11 infra + 8 microservices + 2 frontends) |
| **Deployment Method** | Single `docker compose up -d` — fully containerized |
| **API Gateway** | ✅ Healthy — `http://localhost:8000/health` |
| **Frontend UIs** | ✅ Job Board (:3000) + Admin Dashboard (:3001) |
| **Data Pipeline** | 8-stage Kafka pipeline (Collector → Embedder) |
| **Deployment Time** | ~5 min (first run with image builds: ~15 min) |

---

## 🏗️ Platform Architecture

```
                    ┌─────────────────────────────────────┐
                    │      API Gateway :8000 (FastAPI)     │
                    │   Serves jobs, search, analytics     │
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
        │(web     │ │Normalize│ │Fingerprnt│ │Skills+ML  │
        │scrapers)│ │ + clean │ │via Redis │ │+ Salary   │
        └─────────┘ └─────────┘ └──────────┘ └───────────┘
                                                    │
              ┌─────────────────────────────────────▼───────┐
              │  Verifier (Scam Detection + Trust Scoring)   │
              │  Embedder (SentenceTransformers → Qdrant)    │
              │  Notifier (Email / Webhook / In-App alerts)  │
              └─────────────────────────────────────────────┘

        ┌───────────┐  ┌───────────┐
        │ Job Board │  │   Admin   │
        │  :3000    │  │  :3001    │
        └───────────┘  └───────────┘
```

> **All services are fully containerized.** A single `docker compose up -d` starts the entire platform — no manual Python processes or separate terminal windows needed.

---

## ✅ Prerequisites

| Tool | Required Version | Check Command |
|------|------------------|---------------|
| Docker Engine | 24.0+ | `docker version` |
| Docker Compose | v2.20+ | `docker compose version` |
| `.env` file | Exists in project root | Copy `.env.example` → `.env` if missing |
| Disk Space | ~10 GB free | For Docker images + volumes |

> **Note:** No local Python, Node.js, or npm installation required — everything runs inside containers.

---

## 🚀 Quick Start — Single Command

```bash
cd "/path/to/Job Scrapping"
docker compose up -d
```

That's it. This single command:
1. Builds all microservice Docker images (if not already built)
2. Starts 11 infrastructure containers (MongoDB, Redis, Redpanda, etc.)
3. Creates Kafka topics via `kafka-init`
4. Starts 8 microservice containers (Gateway, Collector, Cleaner, etc.)
5. Starts 2 frontend containers (Job Board, Admin Dashboard)

**Wait ~30 seconds**, then verify:
```bash
curl -s http://localhost:8000/health | python3 -m json.tool
```

Expected output:
```json
{
    "status": "healthy",
    "version": "1.0.0",
    "environment": "development",
    "dependencies": {
        "mongodb": "healthy",
        "redis": "healthy"
    }
}
```

---

## 🔧 First-Time Setup — Fresh Install

> ⏱️ ~15 minutes (Docker image pulls + builds take time on first run)

### Step 1. Clone & Configure

```bash
cd "/path/to/Job Scrapping"

# Create .env file if it doesn't exist
cp .env.example .env   # Edit with your API keys (ADZUNA_API_ID, etc.)
```

### Step 2. Build & Start Everything

```bash
# Build all images and start all services
docker compose up -d --build
```

**What happens during first run:**
- Docker pulls base images (~5 min depending on internet)
- Builds 10 custom images (gateway, collector, cleaner, deduplicator, verifier, enrichment, embedder, notifier, jobboard, admin)
- The `embedder` image takes longest (~3 min) because it downloads the `all-MiniLM-L6-v2` sentence-transformer model
- Starts all 19+ containers

### Step 3. Verify Deployment

```bash
# Check all containers are running
docker compose ps

# Test API Gateway
curl -s http://localhost:8000/health

# Test frontends
curl -s -o /dev/null -w "JobBoard: %{http_code}\n" http://localhost:3000
curl -s -o /dev/null -w "Admin: %{http_code}\n" http://localhost:3001
```

**✅ Success criteria:**
- Gateway returns `{"status":"healthy"}`
- Job Board returns HTTP 200
- Admin Dashboard returns HTTP 200
- All containers show `Up` in `docker compose ps`

---

## 🔁 Subsequent Runs

> ⏱️ ~30 seconds (images are cached, volumes have data)

### Normal Start (after reboot / docker stop)

```bash
cd "/path/to/Job Scrapping"
docker compose up -d
```

### Rebuild After Code Changes

If you've modified service source code:
```bash
# Rebuild specific service(s) and restart
docker compose up -d --build gateway collector

# Or rebuild everything
docker compose up -d --build
```

---

## 🛑 How to Stop the Platform

### Graceful Shutdown (Preserves All Data)

```bash
docker compose stop
```

All data is preserved in Docker named volumes (MongoDB, Redis, Qdrant, etc.).

### Full Wipe (Destroys ALL Data — Fresh Start)

```bash
docker compose down -v
```

> ⚠️ This deletes all database contents, Kafka topics, and vector embeddings.

---

## ✅ Post-Deployment Validation Checklist

| # | Task | Command / URL | Pass? |
|---|------|---------------|-------|
| 1 | Docker engine running | `docker version` | ⬜ |
| 2 | All containers `Up` | `docker compose ps` | ⬜ |
| 3 | Gateway `/health` OK | `curl http://localhost:8000/health` → `{"status":"healthy"}` | ⬜ |
| 4 | Redis responds | `docker exec jip-redis redis-cli ping` → `PONG` | ⬜ |
| 5 | MongoDB responds | Gateway health shows `"mongodb":"healthy"` | ⬜ |
| 6 | Kafka topics exist | Open http://localhost:8080 → Topics tab | ⬜ |
| 7 | Prometheus scraping | http://localhost:9090 → Status → Targets | ⬜ |
| 8 | Qdrant accessible | `curl http://localhost:6333/collections` | ⬜ |
| 9 | Job Board loads | http://localhost:3000 → renders UI | ⬜ |
| 10 | Admin Dashboard loads | http://localhost:3001 → renders UI | ⬜ |
| 11 | API docs accessible | http://localhost:8000/docs → Swagger UI | ⬜ |

---

## 📊 Service Inventory

### 🐳 Infrastructure (11 Containers)

| Container | Image | Port(s) | Purpose | Healthcheck |
|-----------|-------|---------|---------|-------------|
| `jip-mongodb` | `mongo:7.0` | 27017 | Primary database | ✅ `mongosh ping` |
| `jip-redis` | `redis:7-alpine` | 6379 | Cache + dedup fingerprints | ✅ `redis-cli ping` |
| `jip-redpanda` | `redpandadata/redpanda` | 9092, 9644, 8081-8082 | Kafka-compatible broker | ✅ `rpk cluster info` |
| `jip-redpanda-console` | `redpandadata/console` | 8080 | Kafka management Web UI | — |
| `jip-kafka-init` | `redpandadata/redpanda` | — | Creates 24 Kafka topics (exit 0) | — |
| `jip-qdrant` | `qdrant/qdrant` | 6333, 6334 | Vector database (semantic search) | ✅ TCP 6333 |
| `jip-elasticsearch` | `elasticsearch:8.17.0` | 9200, 9300 | Full-text search | ✅ `curl :9200` |
| `jip-minio` | `minio/minio` | 9000, 9001 | S3-compatible object storage | ✅ `mc ready local` |
| `jip-minio-init` | `minio/mc` | — | Creates storage buckets (exit 0) | — |
| `jip-prometheus` | `prom/prometheus` | 9090 | Metrics collection | — |
| `jip-grafana` | `grafana/grafana` | 3002 | Monitoring dashboards | — |

### ⚙️ Microservices (8 Containers)

| Container | Service | Type | Description |
|-----------|---------|------|-------------|
| `jip-gateway` | API Gateway | FastAPI HTTP (:8000) | REST API, Swagger docs, serves all endpoints |
| `jip-collector` | Job Collector | Kafka Worker | Scrapes jobs from web sources (Adzuna, Indeed, LinkedIn, etc.) |
| `jip-cleaner` | Data Cleaner | Kafka Worker | Normalizes HTML, parses salaries, standardizes fields |
| `jip-deduplicator` | Deduplicator | Kafka Worker | Redis-based fingerprinting to eliminate duplicates |
| `jip-verifier` | Verifier | Kafka Worker | ML-powered scam detection + trust scoring |
| `jip-enrichment` | Enrichment | Kafka Worker | Skill extraction, salary estimation via ML |
| `jip-embedder` | Embedder | Kafka Worker | Generates vector embeddings → Qdrant |
| `jip-notifier` | Notifier | Kafka Worker | Email / webhook / in-app job alerts |

### 🌐 Frontend UIs (2 Containers)

| Container | App | URL | Description |
|-----------|-----|-----|-------------|
| `jip-jobboard` | Job Board | http://localhost:3000 | Public-facing job search UI |
| `jip-admin` | Admin Dashboard | http://localhost:3001 | Platform management console |

### 🔧 Supporting Services

| Container | Port | Purpose |
|-----------|------|---------|
| `jip-mlflow` | 5000 | ML experiment tracking |
| `jip-prometheus-init` | — | Bootstraps Prometheus config |

---

## 🌐 Live Endpoints Reference

### 🌟 Core User-Facing

| # | Service | URL | Description |
|---|---------|-----|-------------|
| 1 | **API Gateway (Swagger)** 🌟 | http://localhost:8000/docs | Interactive API docs — try `GET /api/v1/jobs` |
| 2 | **API Health Check** | http://localhost:8000/health | JSON health status |
| 3 | **Job Board UI** 💼 | http://localhost:3000 | Search jobs, filter, apply |
| 4 | **Admin Console** 🔧 | http://localhost:3001 | Pipeline status, analytics |

### 🛠️ Infrastructure UIs

| # | Service | URL | Login |
|---|---------|-----|-------|
| 5 | Redpanda Console (Kafka) | http://localhost:8080 | — |
| 6 | Qdrant Dashboard | http://localhost:6333/dashboard | — |
| 7 | MinIO Console | http://localhost:9001 | `minioadmin` / `minioadmin123` |
| 8 | Prometheus | http://localhost:9090 | — |
| 9 | Grafana | http://localhost:3002 | `admin` / `admin` |
| 10 | Elasticsearch | http://localhost:9200 | — (JSON response) |
| 11 | MLflow | http://localhost:5000 | — |

---

## 📝 Troubleshooting Cheat Sheet

### 🔴 Container shows `Restarting` or `Exited`

**Diagnose:**
```bash
docker logs <container-name> --tail 50
```

**Common causes:**
- Missing `.env` file → copy `.env.example` to `.env`
- Port conflict → check `sudo lsof -i :<port>` or `ss -tlnp | grep <port>`
- Out of memory (especially `jip-embedder`) → increase Docker memory limit

---

### 🔴 Gateway returns "Could not import module"

**Cause:** Docker image was not rebuilt after code changes.

**Fix:**
```bash
docker compose up -d --build gateway
```

---

### 🔴 Microservices fail to connect to Kafka

**Cause:** Redpanda hasn't finished starting, or Kafka topics don't exist.

**Fix:**
```bash
# Verify Redpanda is up
docker exec jip-redpanda rpk cluster info

# Verify topics exist
docker exec jip-redpanda rpk topic list

# Re-create topics if missing
docker compose run --rm kafka-init
```

---

### 🔴 MongoDB/Redpanda showing `(unhealthy)` but services still work

**Cause:** On NTFS-mounted partitions, healthcheck commands can be slow. The services are fine — Docker just hasn't received a healthy response within the timeout.

**Fix:** This is cosmetic. Services still function. If you need to force-refresh:
```bash
docker compose up -d --force-recreate mongodb redpanda
```

---

### 🔴 `jip-embedder` exits with code 137

**Cause:** Out of memory — the `all-MiniLM-L6-v2` model + PyTorch needs ~1.5 GB RAM.

**Fix:**
- Increase Docker Desktop memory limit to at least 8 GB
- Or restart the container: `docker restart jip-embedder`

---

### 🔴 Frontend shows "This site can't be reached"

**Cause:** Frontend containers haven't started yet.

**Fix:**
```bash
docker compose up -d jobboard admin
docker logs jip-jobboard --tail 10
docker logs jip-admin --tail 10
```

---

### 🔴 Kafka topics missing after restart

**Cause:** `kafka-init` only runs once during first deployment.

**Fix:**
```bash
docker compose run --rm kafka-init
```

---

### 🔴 Elasticsearch health: starting (for extended time)

**Cause:** Elasticsearch takes 30-60 seconds to fully initialize, especially on first boot.

**Fix:** Wait 60 seconds and check again:
```bash
curl http://localhost:9200/_cluster/health?pretty
```

---

## 📚 Quick Reference Card

```
╔══════════════════════════════════════════════════════════════╗
║      JOB INTELLIGENCE PLATFORM — CHEAT SHEET                ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  START EVERYTHING        STOP EVERYTHING                     ║
║  ─────────────────       ─────────────────                   ║
║  docker compose up -d    docker compose stop                 ║
║                                                              ║
║  REBUILD + START         FULL WIPE + RESTART                 ║
║  ─────────────────       ─────────────────                   ║
║  docker compose up       docker compose down -v              ║
║    -d --build            docker compose up -d --build        ║
║                                                              ║
║  CHECK STATUS            VIEW LOGS                           ║
║  ─────────────────       ─────────────────                   ║
║  docker compose ps       docker logs jip-gateway --tail 50   ║
║  curl localhost:8000     docker compose logs -f collector    ║
║    /health                                                   ║
║                                                              ║
║  KEY URLS:                                                   ║
║  ─────────────────                                           ║
║  Job Board:      http://localhost:3000                        ║
║  Admin Console:  http://localhost:3001                        ║
║  API Docs:       http://localhost:8000/docs                   ║
║  Kafka Console:  http://localhost:8080                        ║
║  Grafana:        http://localhost:3002                        ║
║  Prometheus:     http://localhost:9090                        ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
```

---

## 🏁 Summary

This platform is an **enterprise-grade, microservices-based AI job intelligence system** with:

- ✅ **Fully containerized** — single `docker compose up -d` deployment
- ✅ **FastAPI API Gateway** with auto-generated Swagger docs
- ✅ **8-stage Kafka pipeline** for real-time job processing
- ✅ **ML-powered** scam detection, salary estimation, and skill extraction
- ✅ **Semantic vector search** via Qdrant + full-text via Elasticsearch
- ✅ **Real-time web scraping** from multiple job sources
- ✅ **Prometheus + Grafana** observability stack
- ✅ **Job Board + Admin Dashboard** frontend applications

---

**Document:** `DEPLOYMENT_RUNBOOK.md`
**Last Updated:** 2026-08-30
**Platform Version:** 1.0.0