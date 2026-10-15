# AGENTS.md — Project Configuration

## Service Management

### Diagnostic Script
**Command:** `python scripts/diagnose.py`

Discover and verify the health of all platform services (infrastructure, API services, frontends, and Kafka topics). Checks each service's TCP/HTTP endpoint with timeout and latency measurement. The diagnostic script uses `127.0.0.1` (not `localhost`) to avoid IPv6 resolution issues, and extended timeouts (30-40s) for known-slow services under system load (Prometheus, Grafana, Redpanda Console, Gateway API). All HTTP endpoints are checked with `httpx` (falls back to `urllib` if unavailable).

**Note:** Prometheus and Grafana respond slowly under heavy system load (QEMU 1314% CPU). The script uses 40s timeouts for these services. Grafana may report HTTP 503 (database failing) under extreme load.

#### Options
- `--json` — Output structured JSON for programmatic use
- `--exit-on-fail` — Return exit code 1 if any service is unhealthy
- `--check-kafka` — Also verify Kafka topic existence (requires `confluent_kafka`)
- `--check-containers` — Also check Docker container running status

#### Service Inventory
The diagnostic script checks 15 services across three groups:

**Infrastructure (Docker Compose):**
- MongoDB (port 27017) — TCP connect
- Redis (port 6379) — TCP connect
- Redpanda/Kafka (port 9092) — TCP connect
- Qdrant (port 6333) — TCP connect
- Elasticsearch (port 9200) — TCP connect
- MinIO (port 9000) — TCP connect
- Prometheus (port 9090) — HTTP `/-/healthy` (40s timeout under load)
- Grafana (port 3002) — HTTP `/api/health` (40s timeout under load)
- MLflow (port 5000) — HTTP `/health`
- Redpanda Console (port 8080) — HTTP `/healthz`

**API Services:**
- Gateway API (port 8000) — HTTP `/health` (includes MongoDB/Redis dependency check)
- Search API (port 8002) — HTTP `/health` (run locally via `uvicorn`; not a Docker container)
- Auth API (port 8000) — HTTP `/docs`

**Frontend:**
- Job Board UI (port 3000) — HTTP `/`
- Admin Console (port 3001) — HTTP `/`

**Background Workers (no HTTP — monitored via Kafka/Docker):**
- Collector, Cleaner, Deduplicator, Verifier, Enrichment, Embedder, Notifier, Orchestrator, Analytics

### Health Check Script
**Command:** `python scripts/health_check.py`

Lighter-weight check focusing on HTTP + database connectivity. Supports `--json`, `--exit-on-fail`, and `--with-throughput` flags.

### Development Startup
**Command:** `.\scripts\start_dev.ps1` (Windows PowerShell)

Starts Docker infrastructure, then launches each Python micro-service in separate windows. Supports `-InfraOnly`, `-ServicesOnly`, and `-Stop` switches.

#### Service Port Map
| Service      | Port | Protocol | Description                  |
|-------------|------|----------|------------------------------|
| Gateway      | 8000 | HTTP     | Main API entry point         |
| Search       | 8002 | HTTP     | Semantic search             |
| Auth         | 8000 | HTTP     | (via Gateway)               |
| MongoDB      | 27017| TCP      | Primary database           |
| Redis        | 6379 | TCP      | Cache, sessions            |
| Redpanda     | 9092 | TCP      | Kafka-compatible broker    |
| Qdrant       | 6333 | TCP      | Vector database            |
| Elasticsearch| 9200 | TCP      | Full-text search           |
| MinIO        | 9000 | TCP      | S3-compatible storage      |
| Prometheus   | 9090 | HTTP     | Metrics collection         |
| Grafana      | 3002 | HTTP     | Dashboards                 |
| MLflow       | 5000 | HTTP     | Model registry             |
| Job Board    | 3000 | HTTP     | Public UI                  |
| Admin        | 3001 | HTTP     | Admin console              |
