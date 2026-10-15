# TALENTLENS — Beginner's Learning Roadmap

> A complete, step-by-step guide for someone who knows basic Python and wants to **get the project running, understand it, and start modifying it**. No prior knowledge of Docker, Kafka, FastAPI, async, or ML is assumed.

---

## Table of Contents

- [Part 0: The Big Picture (Read This First)](#part-0-the-big-picture)
- [Part 1: Prerequisites — Install What You Need](#part-1-prerequisites)
- [Part 2: Day 1 — Get It Running](#part-2-day-1-get-it-running)
- [Part 3: Day 2 — Understand the Project Structure](#part-3-day-2-understand-the-project-structure)
- [Part 4: Days 3-5 — Read the Code in the Right Order](#part-4-days-3-5-read-the-code-in-the-right-order)
- [Part 5: Week 2 — Make Your First Modifications](#part-5-week-2-make-your-first-modifications)
- [Part 6: Week 3+ — Deeper Topics (Only When You're Ready)](#part-6-week-3-deeper-topics)
- [Appendix A: Glossary of Every New Term You'll Meet](#appendix-a-glossary)
- [Appendix B: Common Errors and Fixes](#appendix-b-common-errors-and-fixes)

---

## Part 0: The Big Picture (Read This First)

Before touching any code, understand **what you're building**.

### What is TALENTLENS?

Imagine you want to find a job. Today you'd:
1. Go to LinkedIn / Indeed / Naukri
2. Search "Python developer in Bangalore"
3. See 500 results
4. Notice the same job is posted on 5 different sites
5. See some obvious scams
6. Click into each job to read details

TALENTLENS does all of that **automatically, 24/7**, for thousands of searches:
- It **scrapes** job sites every 90 minutes
- It **deduplicates** the same job posted twice
- It **enriches** each job with extracted skills + estimated salary
- It **filters out scams** using ML
- It indexes everything in a **vector database** so you can do "natural language" search like "remote junior ML jobs paying over 20 LPA"
- It serves the whole thing through a **REST API** that two websites (a public job board + an admin dashboard) talk to.

### What are microservices?

Instead of one giant program that does everything, TALENTLENS is split into **13 small programs** that each do one thing and talk to each other over Kafka (a messaging system).

```
   ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
   │Collector │ →  │ Cleaner  │ →  │  Dedup   │ →  │Enrichment│
   └──────────┘    └──────────┘    └──────────┘    └──────────┘
       scrapes       cleans         removes       adds skills +
       jobs from     HTML,          duplicates    estimates
       13 sites      parses         using hash    salary
                     salary
```

Each box is a separate program. They communicate by passing **messages** through Kafka.

### Full Architecture Diagram

```
┌────────────────────────────────────────────────────────────────────────────────┐
│                    INFRASTRUCTURE LAYER (13 containers)                         │
├────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌──────────────┐ ┌──────────┐ ┌──────────────┐ ┌──────────┐ ┌──────────────┐ │
│  │   MongoDB    │ │  Redis   │ │  Redpanda    │ │  Qdrant  │ │ Elasticsearch│ │
│  │  :27017      │ │  :6379   │ │  :9092       │ │  :6333   │ │  :9200       │ │
│  │  Primary DB  │ │  Cache   │ │  Kafka       │ │  Vector  │ │  Full-text   │ │
│  │  • Jobs      │ │  • Cache │ │  Broker      │ │  DB      │ │  Search      │ │
│  │  • Users     │ │  • Rate  │ │              │ │          │ │              │ │
│  │  • Events    │ │  limit   │ │              │ │          │ │              │ │
│  │  • Pipeline  │ │  • Token │ │              │ │          │ │              │ │
│  │  events      │ │  blacklist│ │              │ │          │ │              │ │
│  │  • Metrics   │ │  • Orches-│ │              │ │          │ │              │ │
│  │              │ │  trator  │ │              │ │          │ │              │ │
│  │              │ │  keyspace│ │              │ │          │ │              │ │
│  └──────┬───────┘ └────┬─────┘ └──────┬───────┘ └────┬─────┘ └─────┬────────┘ │
│         │              │              │              │             │          │
│  ┌──────┴───────┐ ┌─────┴─────┐ ┌──────┴─────┐ ┌─────┴─────┐ ┌────┴──────────┐│
│  │   MinIO      │ │ Prometheus│ │ Redpanda   │ │   Grafana │ │    MLflow    ││
│  │  :9000/:9001 │ │  :9090    │ │ Console    │ │  :3002    │ │  :5000       ││
│  │  S3 Object   │ │  Metrics  │ │ :8080      │ │  Dash-   │ │  ML tracking ││
│  │  Storage     │ │  Collector│ │ Kafka UI   │ │  boards   │ │              ││
│  │  • Resumes   │ │           │ │            │ │           │ │              ││
│  │  • Logos     │ │           │ │            │ │           │ │              ││
│  │  • Models    │ │           │ │            │ │           │ │              ││
│  └─────────────┘ └───────────┘ └────────────┘ └───────────┘ └────────────────┘│
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │  kafka-init — Bootstraps 24 Kafka topics (one-shot at startup)           │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
│                                                                                 │
└────────────────────────────────────────────────────────────────────────────────┘


┌────────────────────────────────────────────────────────────────────────────────┐
│             KAFKA DATA PIPELINE (Redis marked with ★)                          │
├────────────────────────────────────────────────────────────────────────────────┤
│                                                                                │
│  Orchestrator ★                                                              │
│       │  (collection.trigger)                                                   │
│       ▼                                                                       │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  COLLECTOR — Web scrapers (Adzuna, Indeed, LinkedIn, 13 sources)        │   │
│  └──────┬──────────────────┬───────────────────────────────────────────┘   │
│         │                  │                                                    │
│         ▼                  ▼                                                    │
│  raw_jobs ──→ ┌───────────────────────────────────────────────────┐           │
│               │ COLLECTOR → (Kafka producer) → Cleaner           │            │
│  job.cleaned ──→ ┌──────────────────────────────────────────┐      │            │
│               │ CLEANER — Normalize HTML, parse salary/location │                │
│  job.deduplicated ──→ ┌────────────────────────────────────┐ │                │
│               │ DEDUPLICATOR — Fingerprint + duplicate removal│ │                │
│               │  ★ Redis DB 1 (reserved); actual dedup uses │ │                │
│               │    MongoDB content_fingerprint field       │ │                │
│  job.enriched ──→ ┌────────────────────────────────────┐   │                │
│               │ ENRICHMENT — Skill extraction (spaCy) + │   │                │
│               │  salary estimation (XGBoost)           │   │                │
│  job.verified ──→ ┌──────────────────────────────────┐ │   │                │
│               │ VERIFIER — Scam detection + trust     │ │   │                │
│               │ scoring (XGBoost)                    │ │   │                │
│  job.rejected ──→                                  │ │   │                │
│               └──────────────────────────────────┘ │   │                │
│                        │                             │   │                │
│                        ▼                             │   │                │
│  ┌──────────────────────────────────────────────────┐ │   │                │
│  │ EMBEDDER — SentenceTransformers → Qdrant         │ │   │                │
│  │ embedding.job → embedding.complete               │ │   │                │
│  └──────────────────────────────────────────────────┘ │   │                │
│                        │                              │   │                │
│                        ▼                              │   │                │
  │  ┌──────────────────────────────────────────────────┐ │   │                │
  │  │ NOTIFIER — Email/webhook/in-app alerts           │ │   │                │
  │  │ notification.* topics                            │ │   │                │
  │  └──────────────────────────────────────────────────┘ │   │                │
  │                                                                                │
  │  ┌──────────────────────────────────────────────────┐   │                │
  │  │ API GATEWAY (FastAPI :8000)                    │   │                │
  │  │ ★ Redis DB 0: cache, rate limit, token blacklist│  │                │
  │  │ ★ MongoDB: persistent user data, jobs            │  │                │
  │  │ ★ Qdrant: vector/semantic search               │  │                │
  │  │ ★ Elasticsearch: full-text search              │  │                │
  │  │ ★ Kafka producer: triggers, search queries    │  │                │
  │  └──────────────┬──────────────────────────────────┘  │                │
  │                 │                                     │                │
  │         ┌───────┴────────┐                            │                │
  │         ▼                ▼                            │                │
  │  ┌────────────┐   ┌────────────┐                     │                │
  │  │ Job Board  │   │ Admin Dash │                     │                │
  │  │ :3000 (UI) │   │ :3001 (UI) │                     │                │
  │  └────────────┘   └────────────┘                     │                │
  │                                                                               │
  └────────────────────────────────────────────────────────────────────────────────┘

### Redis vs. Kafka — Why Both?

| Aspect | Kafka (Redpanda) | Redis |
|---|---|---|
| **Role** | Inter-service message streaming backbone | In-memory cache, rate limiting, token revocation |
| **Used by** | All 8 microservices + orchestrator | Gateway (auth cache, rate limit, JWT blacklist), Orchestrator (keyspace stats) |
| **Data flow** | Job messages flow through 24 topics between pipeline stages | Short-lived cached values (TTL), ephemeral auth state |
| **Criticality** | Essential — without it, microservices can't communicate | Secondary — can be replaced but degrades performance/functionality |
```

### What's Docker / Docker Compose?

A way to package each program + its dependencies into an isolated "container" and run all 13 + the databases together with one command.

You don't need to "install" Python, MongoDB, Kafka, Redis, Qdrant, etc. on your machine. Docker runs them all in containers.

### What are the 4 things you'll learn?

| Topic | Why |
|---|---|
| **Python async (`asyncio`)** | Every worker is async. Without this you can't read the code. |
| **FastAPI** | The web framework for the API gateway. |
| **Kafka (Redpanda)** | How the workers talk to each other. |
| **Docker Compose** | How you run all 13 services + databases. |

That's it. Everything else in this project is built on these four things.

### The 3 rules that make everything else easier

1. **Read in this order**: shared library → gateway → one worker → ML models → other workers. Don't jump around.
2. **Run before you read**: Get the project running first. Seeing it work helps you understand the code.
3. **Modify one tiny thing first**: Change a log message, add a print, then rebuild. Seeing your change appear is the best teacher.

---

## Part 1: Prerequisites — Install What You Need

### 1.1 Required software

| Software | Why | Install |
|---|---|---|
| **Docker Desktop** | Runs all 18 containers | https://www.docker.com/products/docker-desktop/ |
| **VS Code** | Best code editor for Python | https://code.visualstudio.com/ |
| **MongoDB Compass** | GUI to look at your database | https://www.mongodb.com/try/download/compass |
| **Git** | Version control | Already installed if you cloned the repo |

### 1.2 Recommended VS Code extensions

After installing VS Code, install these:

- **Python** (Microsoft)
- **Docker** (Microsoft)
- **MongoDB for VS Code** (MongoDB)
- **REST Client** (Huachao Mao) — for testing the API
- **Markdown All in One** — for viewing the docs

### 1.3 Check that Docker works

Open a terminal and run:

```bash
docker --version
docker compose version
```

You should see something like `Docker version 24.0+` and `Docker Compose version v2.20+`.

If you get "command not found", Docker Desktop isn't installed properly. Reinstall and restart your computer.

### 1.4 Get the project

```bash
cd "/run/media/rehan/AC868F2D868EF75C/Users/Vivobook pro 15/Desktop/Job Scrapping"
ls
```

You should see `docker-compose.yml`, `README.md`, `services/`, `shared/`, etc. You're already in the right place.

### 1.5 Get free API keys (optional but recommended)

The project works without these, but you'll get many more jobs if you have them:

- **Adzuna** (free): https://developer.adzuna.com/ — sign up, get `app_id` and `app_key`
- Other sources (Indeed, LinkedIn, etc.) work without keys but return fewer results

Skip this step for now. You can add keys later.

---

## Part 2: Day 1 — Get It Running

**Goal:** See the entire system work on your machine. Don't read any code yet.

### Step 1: Create your `.env` file

```bash
cd "/run/media/rehan/AC868F2D868EF75C/Users/Vivobook pro 15/Desktop/Job Scrapping"
cp .env.example .env
```

Open `.env` in VS Code. For now, **leave everything as default**. You don't need any API keys to start.

### Step 2: Start everything

```bash
docker compose up -d
```

This command:
- Pulls 19 Docker images
- Starts MongoDB, Redis, Kafka, Qdrant, Elasticsearch, MinIO, Prometheus, Grafana, MLflow
- Builds the 8 Python microservices
- Builds the 2 React frontends
- Creates 24 Kafka topics
- Initializes MinIO buckets

**First time takes 5-15 minutes** depending on your internet speed. Go make tea. ☕

### Step 3: Verify it's running

```bash
docker compose ps
```

You should see all 18 containers with status "Up" or "healthy".

### Step 4: Open the web interfaces

Put these URLs in your browser:

| URL | What you'll see |
|---|---|
| http://localhost:8000/docs | API documentation (Swagger UI) |
| http://localhost:3000 | Public job board |
| http://localhost:3001 | Admin dashboard |
| http://localhost:8080 | Kafka topic viewer |
| http://localhost:3002 | Grafana dashboards (admin/admin) |

If you see the Job Board and API docs, **congratulations** — the whole system is running.

### Step 5: Trigger your first job collection

The system only collects jobs every 90 minutes by default. To force a collection now:

1. Go to http://localhost:8000/docs
2. Find `POST /api/v1/jobs/collect/trigger`
3. Click "Try it out"
4. Leave the default parameters
5. Click "Execute"

You should see `"message": "Collection trigger sent"`.

### Step 6: Watch jobs flow through

1. Go to http://localhost:8080 (Redpanda Console)
2. Click "Topics"
3. Click "raw_jobs"
4. Click "Messages" tab → "Start consuming"

You'll see JSON messages appearing as the collector scrapes jobs. Each message = one job.

### Step 7: See jobs in the database

1. Open MongoDB Compass
2. Connect to: `mongodb://admin:admin123@localhost:27017`
3. Database: `jobplatform`
4. Collection: `jobs`

You'll see jobs with statuses like `raw`, `cleaned`, `enriched`, `verified`. They're moving through the 8-stage pipeline.

### Step 8: See jobs on the UI

Wait ~5 minutes after triggering collection, then refresh http://localhost:3000. You should see real jobs from Adzuna and Greenhouse.

**You did it.** The system is running and processing real data.

### Useful commands for Day 1

```bash
# See logs for a service (Ctrl+C to exit)
docker compose logs -f collector

# Restart a service after changing its code
docker compose up -d --build collector

# Stop everything but keep data
docker compose down

# Stop everything AND delete all data
docker compose down -v

# Check resource usage
docker stats
```

---

## Part 3: Day 2 — Understand the Project Structure

**Goal:** Open every folder and know what it does. Read NO code yet.

### Step 1: Open the project in VS Code

```bash
cd "/run/media/rehan/AC868F2D868EF75C/Users/Vivobook pro 15/Desktop/Job Scrapping"
code .
```

VS Code will open with all the files visible.

### Step 2: The 4 most important folders

Ignore everything else for now. Focus on these:

```
.
├── services/gateway/      # ← The web API you'll modify first
├── shared/database/       # ← How to connect to MongoDB
├── shared/kafka/          # ← How to send/receive messages
└── docker-compose.yml     # ← How to run everything
```

### Step 3: Open each in VS Code

For each of the 4 things above:
1. Click to expand the folder
2. Look at the file names
3. Don't read the contents — just the names

**What you should notice:**
- `services/gateway/main.py` is small (~150 lines)
- `services/gateway/routers/` has 8 files (auth, jobs, search, etc.) — each one is a group of API endpoints
- `shared/database/session.py` is very short (~80 lines)
- `shared/kafka/` has `producer.py` and `consumer.py`
- `docker-compose.yml` is huge (557 lines) — that's expected, it configures 19 services

### Step 4: Map folders to roles

Print this or write it on a sticky note:

| Folder | Role | Analogy |
|---|---|---|
| `services/gateway/` | Receives HTTP requests from the browser, returns JSON | The restaurant's waiter |
| `services/collector/` | Scrapes job websites | The fisherman |
| `services/cleaner/` | Removes HTML, parses salary | The prep cook |
| `services/deduplicator/` | Removes duplicate jobs | The quality inspector |
| `services/enrichment/` | Adds skills + salary estimate | The chef who adds spices |
| `services/verifier/` | Filters out scams | The bouncer |
| `services/embedder/` | Converts text to numbers for AI search | The translator |
| `services/notifier/` | Sends emails/webhooks | The messenger |
| `shared/` | Code reused by every service | The restaurant's recipe book |
| `ml/` | Trained ML models | The chef's special sauces |
| `frontend/` | React websites | The dining room |
| `infra/` | Dockerfiles, Kubernetes configs | The kitchen layout |

### Step 5: Understand the 8-stage pipeline visually

Open `README.md` and scroll to the "Data Pipeline" section. Read the architecture diagram. You'll see:

```
collector → raw_jobs → cleaner → cleaned_jobs → dedup → deduplicated_jobs
                                                                  ↓
                  verified_jobs ← verifier ← enriched_jobs ← enrichment
                         ↓
                  embedder → Qdrant (vector DB)
                  notifier → email/webhook
```

Each arrow = a Kafka topic. Each box = a service.

### Step 6: Make a tiny change (the "Hello World" of dev)

Goal: change a log message, see it in the logs, prove you can modify the system.

1. Open `services/gateway/main.py`
2. Find the `lifespan` function
3. Change `logger.info("🚀 Starting...")` to `logger.info("🚀 HELLO FROM REHAN!")`
4. Save the file
5. Run: `docker compose up -d --build gateway`
6. Run: `docker compose logs gateway | head -20`

You should see your custom message in the logs.

**You just rebuilt a service from scratch. You are now a TALENTLENS developer.** 🎉

---

## Part 4: Days 3-5 — Read the Code in the Right Order

**The most important rule of this project:** read the code in the order below. Each file builds on concepts from the previous one.

### Day 3: The shared library (1-2 hours)

| Order | File | What you'll learn |
|---|---|---|
| 1 | `shared/database/session.py` | How to connect to MongoDB; the singleton pattern |
| 2 | `shared/database/models.py` | What "Job", "User", "Company" look like as Python classes |
| 3 | `shared/kafka/producer.py` | How to send a message |
| 4 | `shared/kafka/consumer.py` | How to read a message |
| 5 | `shared/kafka/topics.py` | The list of all 24 Kafka topics |
| 6 | `shared/utils/logging.py` | Logging helpers |
| 7 | `shared/utils/url.py` | URL normalization and reachability check |

**Reading strategy:** For each file:
1. Read the first 20 lines to understand imports and setup
2. Skim — don't read every function
3. Open MongoDB Compass, run a query, see what's in the database
4. Try changing a log message in the file, rebuild, see it

### Day 4: The gateway (2-3 hours)

| Order | File | What you'll learn |
|---|---|---|
| 1 | `services/gateway/main.py` | The FastAPI app, lifespan, middleware |
| 2 | `services/gateway/deps.py` | How JWT auth works (`create_access_token`, `get_current_user`) |
| 3 | `services/gateway/routers/auth.py` | Register, login, refresh, logout |
| 4 | `services/gateway/routers/jobs.py` | The main CRUD API (most-used endpoints) |
| 5 | `services/gateway/routers/search.py` | Vector search |
| 6 | Browse the others (users, admin, analytics, notifications, resume) | Know they exist |

**Reading strategy:**
1. Open http://localhost:8000/docs in your browser
2. Click each endpoint in Swagger UI to see what it does
3. Then read the Python file
4. Use the **REST Client** VS Code extension to send test requests

### Day 5: One worker end-to-end (3-4 hours)

Pick **the collector** because it's the entry point and has 1,534 lines of great examples:

| Order | File | What you'll learn |
|---|---|---|
| 1 | `services/collector/main.py` | How to run a Kafka consumer, schedule tasks, send messages |
| 2 | `services/collector/agents.py` | The 13 web scrapers; circuit breaker; adaptive rate limiting |
| 3 | `docs/collector_main.inline.md` and `docs/collector_agents.inline.md` | Line-by-line walkthrough of the above |

Then read ONE worker file and its inline doc:

| Order | File | What you'll learn |
|---|---|---|
| 4 | `services/deduplicator/main.py` + `docs/deduplicator_main.inline.md` | How to detect duplicates |
| 5 | `services/enrichment/main.py` + `docs/enrichment_main.inline.md` | How to run ML models on each job |
| 6 | `services/verifier/main.py` + `docs/verifier_main.inline.md` | How to score jobs as scam/legit |
| 7 | `services/embedder/main.py` + `docs/embedder_main.inline.md` | How to convert text to vectors |
| 8 | `services/notifier/main.py` (no inline doc) | How to send notifications |

By the end of Day 5, you should be able to explain **in your own words** what each worker does.

### Day 5 Bonus: ML models (1 hour skim)

These are independent of the workers. Read them after you understand the workers.

| Order | File |
|---|---|
| 1 | `ml/salary_estimator/estimator.py` |
| 2 | `ml/scam_detector/model.py` |
| 3 | `ml/skill_extractor/pipeline.py` |

---

## Part 5: Week 2 — Make Your First Modifications

The best way to learn is to modify. Start with safe, easy changes. Each one builds your confidence.

### Project 1: Add a new search term (15 minutes)

The collector has a hardcoded list of search terms. Add one:

1. Open `services/collector/agents.py`
2. Find `DEFAULT_SEARCH_TERMS` (around line 39)
3. Add `"your favorite job title"` to the list
4. Rebuild: `docker compose up -d --build collector`
5. Trigger a collection (use the API or wait 90 min)
6. Watch logs: `docker compose logs -f collector`
7. See your new search term produce jobs

### Project 2: Add a new API endpoint (30 minutes)

The gateway serves the website. Add a new endpoint:

1. Open `services/gateway/routers/jobs.py`
2. Find the `list_jobs` function
3. Add a new function below it:

```python
@router.get("/stats/summary")
async def get_job_stats(db = Depends(get_db)):
    """Return counts of jobs by status."""
    pipeline = [
        {"$group": {"_id": "$status", "count": {"$sum": 1}}}
    ]
    return await db.jobs.aggregate(pipeline).to_list(length=None)
```

4. Save and rebuild: `docker compose up -d --build gateway`
5. Open http://localhost:8000/docs
6. Find your new endpoint under "Jobs"
7. Click "Try it out" → "Execute"
8. See the JSON response with job counts

### Project 3: Change the scam threshold (15 minutes)

The verifier uses a 0.6 threshold to mark jobs as scams. Try changing it:

1. Open `services/verifier/main.py`
2. Find `SCAM_THRESHOLD = 0.6`
3. Change to `SCAM_THRESHOLD = 0.4` (more aggressive — flags more as scam)
4. Rebuild: `docker compose up -d --build verifier`
5. Trigger a collection
6. Compare how many jobs are now rejected

### Project 4: Add a new scraper (1-2 hours)

This is the holy grail. Add a new job source:

1. Open `services/collector/agents.py`
2. Find the `RemotiveCollector` class — it's the simplest one (~60 lines)
3. Copy it as `MyNewCollector`
4. Change the API URL, parsing logic, etc.
5. Add it to `COLLECTOR_REGISTRY` at the bottom
6. Add it to `shared/models/job.py` `CollectionSource` enum
7. Rebuild: `docker compose up -d --build collector`
8. Trigger a collection
9. See your new source's jobs in MongoDB

### Project 5: Add a new field to Job (2-3 hours)

Add a "remote_ok" boolean field to every job:

1. Open `shared/database/models.py`
2. Add `"remote_ok: bool = False"` to the `Job` model
3. Open `services/cleaner/main.py` and parse this field
4. Rebuild cleaner: `docker compose up -d --build cleaner`
5. Trigger collection → wait → see new field in MongoDB

### Project 6: Deploy to a real server (1 day)

Once you're comfortable locally:

1. Get a cheap VPS (DigitalOcean, Hetzner, AWS Lightsail)
2. Copy your project to the server
3. Install Docker on the server
4. Run `docker compose up -d` on the server
5. Open the ports in your firewall
6. Set up a domain name (optional)

See `DEPLOYMENT_RUNBOOK.md` for the full deployment guide.

---

## Part 6: Week 3+ — Deeper Topics (Only When You're Ready)

Once you've read all the workers and made your first modifications, you can tackle:

| Topic | Where to learn |
|---|---|
| **Async Python in depth** | https://docs.python.org/3/library/asyncio.html + the FastAPI tutorial |
| **Kafka in depth** | https://kafka.apache.org/quickstart + run `rpk topic` commands |
| **MongoDB aggregations** | https://docs.mongodb.com/manual/aggregation/ |
| **Kubernetes** | https://kubernetes.io/docs/tutorials/ + the manifests in `infra/k8s/` |
| **Production deployment** | Read `DEPLOYMENT_RUNBOOK.md` |
| **ML training** | Run the training scripts: `python ml/scam_detector/train.py --data your_data.csv` |
| **Frontend (React + Vite)** | Open `frontend/jobboard/` and start with `src/App.tsx` |
| **Tests** | Look at `tests/unit/` for pytest examples |

---

## Appendix A: Glossary

Every new term you'll encounter, in the order you'll meet them.

### Infrastructure terms

| Term | Meaning | Example |
|---|---|---|
| **Container** | An isolated environment that runs one program. Like a lightweight VM. | `jip-mongodb` container runs MongoDB |
| **Docker** | The tool that creates and runs containers | `docker run nginx` |
| **Docker Compose** | Runs many containers together from one YAML file | `docker compose up -d` |
| **Image** | A packaged snapshot of a program + its dependencies | `python:3.11-slim` is an image |
| **Volume** | Persistent disk space for a container | `mongodb_data` volume keeps your data |
| **Network** | A virtual LAN for containers | All containers share the `platform` network |
| **Port** | A numbered door into a container | Port 8000 = the gateway API |

### Backend terms

| Term | Meaning | Example |
|---|---|---|
| **API** | A way for programs to talk to each other over HTTP | `GET /api/v1/jobs` returns a list of jobs |
| **REST** | A style for designing APIs | GET = read, POST = create, PUT = update |
| **JSON** | A text format for data, like Python's dict | `{"name": "John", "age": 30}` |
| **Endpoint** | A single URL in an API | `/api/v1/jobs` is one endpoint |
| **Router** | A group of related endpoints | `auth.py` is a router with login/register/logout |
| **Middleware** | Code that runs before/after every request | CORS middleware adds headers |
| **Dependency injection** | FastAPI feature: auto-provide things like DB connections | `db = Depends(get_db)` |

### Async Python terms

| Term | Meaning | Example |
|---|---|---|
| **`async def`** | Defines a coroutine (async function) | `async def fetch_jobs():` |
| **`await`** | Wait for an async operation | `result = await db.find()` |
| **`asyncio.gather(*tasks)`** | Run many coroutines in parallel | `await asyncio.gather(*[fetch_one(t) for t in terms])` |
| **`asyncio.Semaphore(N)`** | Allow at most N concurrent operations | `sem = asyncio.Semaphore(50)` |
| **`run_in_executor()`** | Run CPU-heavy code in a background thread | Used for ML model inference |

### Kafka terms

| Term | Meaning | Example |
|---|---|---|
| **Topic** | A named stream of messages | `raw_jobs` topic |
| **Producer** | Something that writes messages to a topic | The collector is a producer |
| **Consumer** | Something that reads messages from a topic | The cleaner is a consumer |
| **Offset** | "I've processed up to message #1234" | Tracked per consumer group |
| **Consumer group** | A group of consumers sharing the work | `enrichment-service` group |
| **Partition** | A topic is split into N partitions for parallelism | Default: 1 partition per topic |
| **Redpanda** | A drop-in replacement for Kafka (faster, simpler) | What this project uses |

### Database terms

| Term | Meaning | Example |
|---|---|---|
| **Document** | A JSON-like record | One job = one document |
| **Collection** | A group of documents | `jobs`, `users`, `companies` |
| **Index** | A data structure that makes queries fast | Index on `(source, source_job_id)` |
| **`_id`** | The unique identifier of a document | We use UUIDs like `"abc-123"` |
| **`$in`** | Match any value in a list | `{"_id": {"$in": [id1, id2, id3]}}` |
| **`$regex`** | Pattern match (case-insensitive with `"i"`) | `{"title": {"$regex": "python", "$options": "i"}}` |
| **`upsert`** | Insert if not exists, update if exists | Idempotent operation |
| **`bulk_write`** | Execute many operations in one round-trip | 100× faster than per-record |

### ML terms

| Term | Meaning | Example |
|---|---|---|
| **Feature** | A number extracted from raw input | `n_scam_keywords = 3` |
| **XGBoost** | A powerful ML algorithm for tabular data | Used for scam detection |
| **Gradient Boosting** | Similar to XGBoost, slightly different | Used for salary estimation |
| **Vector** | A list of numbers representing meaning | `[0.12, -0.34, 0.56, ...]` (384 numbers) |
| **Embedding** | Another word for vector | "Python developer" → 384-dim vector |
| **Qdrant** | A database that stores vectors and finds similar ones | "Find jobs similar to this one" |
| **NER** | Named Entity Recognition — finding skills in text | "Python, AWS, Kubernetes" → list of skills |
| **spaCy** | A Python NLP library | Used for skill extraction |
| **`@lru_cache`** | Memoization — cache results based on inputs | Same job asked twice = instant |
| **Graceful degradation** | If ML is missing, use hand-coded rules | Always works, less accurate |

### Web scraping terms

| Term | Meaning | Example |
|---|---|---|
| **User-Agent** | A header that identifies your client | Rotating 3 different browsers |
| **Rate limit** | The website's "max N requests per minute" | Hitting it = 429 error |
| **Circuit breaker** | A pattern: stop trying a failing site | 5 failures → wait 60s |
| **Exponential backoff** | Wait 1s, 2s, 4s, 8s before retry | With random jitter |
| **Semaphore** | Limit how many parallel requests | Max 10 at a time |
| **`async with`** | Async context manager (open/close resources) | `async with collector:` |

---

## Appendix B: Common Errors and Fixes

### Error: "port is already allocated"

**Cause:** Another program (or another Docker setup) is using the same port.

**Fix:**
```bash
# Find what's using port 8000
lsof -i :8000        # macOS/Linux
netstat -ano | findstr :8000    # Windows
# Either kill that process, or change the port in docker-compose.yml
```

### Error: "no space left on device"

**Cause:** Docker is using all your disk.

**Fix:**
```bash
# Remove stopped containers, unused images, unused volumes
docker system prune -a --volumes
# WARNING: this wipes all Docker data. Re-run `docker compose up -d` after.
```

### Error: "Connection refused" when calling the API

**Cause:** The gateway container isn't running.

**Fix:**
```bash
docker compose ps           # check status
docker compose logs gateway  # see why it crashed
docker compose up -d --build gateway  # rebuild
```

### Error: "MongoServerSelectionTimeoutError"

**Cause:** MongoDB isn't ready yet, or the gateway started before MongoDB.

**Fix:**
```bash
# Wait for mongo to be healthy, then restart gateway
docker compose restart gateway
```

### Error: "Cannot connect to the Docker daemon"

**Cause:** Docker Desktop isn't running.

**Fix:** Open Docker Desktop application and wait for it to say "Docker is running".

### Error: My code change isn't showing up

**Cause:** You forgot to rebuild.

**Fix:**
```bash
docker compose up -d --build <service-name>
```

### Error: "ModuleNotFoundError: No module named 'X'"

**Cause:** The Docker image is missing a dependency.

**Fix:**
1. Add the dependency to the relevant `Dockerfile` or `pyproject.toml`
2. Rebuild: `docker compose up -d --build <service>`

### Error: Jobs aren't appearing on the website

**Cause:** The pipeline hasn't finished yet, OR the job got rejected as scam.

**Fix:**
```bash
# Check the pipeline status
docker compose logs enrichment
docker compose logs verifier

# Check MongoDB
mongosh "mongodb://admin:admin123@localhost:27017/jobplatform" --eval \
  "db.jobs.aggregate([{\$group: {_id: '\$status', count: {\$sum: 1}}}]).toArray()"
```

If jobs are stuck in `enriched` but not `verified`, check the verifier logs for errors.

### Error: I edited code but nothing happens

**Cause 1:** You didn't save the file.
**Cause 2:** You didn't rebuild.
**Cause 3:** You edited the wrong file (there's a copy somewhere else).

**Fix:** Save → `docker compose up -d --build <service>` → check logs.

---

## Your 2-week schedule at a glance

| Day | Task | Time |
|---|---|---|
| 1 | Install Docker, run `docker compose up -d`, open the UIs | 2 hours |
| 1 | Trigger a collection, watch the pipeline, see jobs in DB | 1 hour |
| 2 | Browse the project structure, understand the layout | 1 hour |
| 2 | Make a "Hello World" change in gateway/main.py | 30 min |
| 3 | Read `shared/database/session.py` and `shared/kafka/*.py` | 2 hours |
| 4 | Read `services/gateway/main.py` and the routers | 3 hours |
| 5 | Read `services/collector/main.py` and `agents.py` | 4 hours |
| 6-7 | Read the worker files (dedup, enrichment, verifier, embedder, notifier) | 4 hours |
| 8 | Skim the ML model files | 1 hour |
| 9-10 | Project 1 + 2: add a search term, add an endpoint | 2 hours |
| 11-12 | Project 3 + 4: change scam threshold, add a scraper | 3 hours |
| 13-14 | Project 5 + 6: add a Job field, deploy to a server | 6 hours |

**Total time: ~ 26 hours of focused learning.**

After this, you'll be able to:
- Explain every folder and file's purpose
- Modify any existing service
- Add new scrapers, endpoints, or workers
- Deploy the whole system to a server
- Read and write Kafka-based microservices

---

## The single most important tip

If you get stuck, **read the inline docs**:

```
docs/db_models.inline.md          # MongoDB schema explained
docs/collector_agents.inline.md   # All 13 scrapers explained
docs/kafka_producer.inline.md     # How sending works
docs/enrichment_main.inline.md    # ML enrichment explained
```

These were written specifically to help people like you learn the code. Use them.

And remember: **running the system first makes reading the code 10× easier.** Seeing real jobs move through real Kafka topics turns abstract concepts into concrete understanding.

Good luck. You've got this. 🚀