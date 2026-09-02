# TalentLens — AI-Powered Job Intelligence & Verification Platform
## Comprehensive Technical Documentation & Complete Interview Preparation Guide

---

# 1. Project Overview

### Project Name
**TalentLens** *(also referred to as AI-Powered Job Intelligence Platform)*

### One-Line Description
> "TalentLens is an end-to-end, event-driven distributed job intelligence platform that aggregates job postings across multiple ATS and aggregator sources, filters employment fraud via an ML/heuristic ensemble verifier, enriches unstructured descriptions with extracted skills and salary benchmarks, and provides transparent multi-factor resume matching and hybrid semantic search."

---

## Problem Statement

### 1. What real-world problem does the project solve?
The online job search market suffers from three critical vulnerabilities:
1. **Employment Scams & Phantom Postings**: High volumes of fraudulent job postings (advance-fee scams, data harvesting, MLM, crypto task schemes, fake telegram recruiters) prey on vulnerable job seekers.
2. **Extreme Data Fragmentation & Duplication**: The same job opening is scraped, reposted, and syndicated across dozens of boards with conflicting titles, stale dates, and mangled compensation figures.
3. **Black-Box ATS & Opaque Keyword Matching**: Existing job search engines rely on brittle keyword matching or proprietary black-box algorithms that provide zero visibility into why a candidate was ranked or what exact skill gaps prevent them from getting shortlisted.

### 2. Who experiences this problem?
- **Job Seekers & Fresh Graduates**: Fall victim to employment scams, waste time applying to expired/duplicate listings, and lack clear guidance on why their profile does or does not match a job.
- **Talent Acquisition Teams & Employers**: Suffer brand reputation damage when fraudulent actors impersonate their company names with fake listings.
- **Platform Administrators**: Need automated observability, fraud mitigation, and ingestion pipeline controls rather than manual review.

### 3. Limitations of Existing Solutions
- **General Job Aggregators (Indeed, Google Jobs, LinkedIn)**: Prioritize ad revenue and sponsored volume over verification; duplicate and expired listings persist for weeks; scam detection is predominantly reactive (post-report) rather than proactive (pre-publish).
- **Keyword Search Engines**: Fail on semantic synonyms (e.g., matching "FastAPI developer" to "Python backend engineer with REST experience") and produce irrelevant search results.
- **Traditional ATS Scanners**: Provide flat, unexplainable rejection scores without actionable skill-gap roadmaps.

---

## Proposed Solution & Core Architecture

TalentLens resolves these challenges through a **7-stage distributed pipeline** backed by microservices, Kafka event streaming, MongoDB document storage, and Qdrant vector search:

```
[ Job Sources: Adzuna, Greenhouse, Indeed, Lever, RSS ]
                         │
                         ▼
             [ 1. Collector Service ]
                         │ (Publishes to 'job.raw')
                         ▼
              [ 2. Cleaner Service ]
                         │ (Strips HTML, normalizes locations, parses salaries -> 'job.cleaned')
                         ▼
           [ 3. Deduplicator Service ]
                         │ (SHA-256 fingerprinting + source ID check -> 'job.deduplicated')
                         ▼
            [ 4. Enrichment Service ]
                         │ (Extracts skills, classifies experience, predicts salaries -> 'job.enriched')
                         ▼
             [ 5. Verifier Service ]
                         │ (XGBoost ML model + 50+ heuristic rules + domain SSL audit -> 'job.verified')
                         ▼
             [ 6. Embedder Service ]
                         │ (Generates 384-d vectors via SentenceTransformers -> Qdrant -> status='published')
                         ▼
             [ 7. Gateway & Search ]
                         │ (JWT Auth, Hybrid Semantic/FTS Search, Resume Matcher, Admin Console)
                         ▼
           [ User Interface / Admin UI ]
```

---

## Key Features Implemented

| Feature | Description | Implementation Module | Core Tech |
| :--- | :--- | :--- | :--- |
| **Multi-Source Collector** | Asynchronous, concurrent scraping across APIs (Adzuna), ATS platforms (Greenhouse, Lever), job boards (Indeed, Remotive, WeWorkRemotely), and RSS feeds with exponential backoff and circuit breakers. | [`services/collector/agents.py`](file:///c:/Users/Vivobook%20pro%2015/Desktop/Job%20Scrapping/services/collector/agents.py) | `httpx`, `asyncio`, `BeautifulSoup4` |
| **Data Cleaning & Normalization** | Strips dangerous HTML, normalizes geographic locations (city, state, country), and parses raw compensation strings into structured numerical ranges (`min`, `max`, `currency`, `period`). | [`services/cleaner/main.py`](file:///c:/Users/Vivobook%20pro%2015/Desktop/Job%20Scrapping/services/cleaner/main.py) | `Python regex`, `MongoDB` |
| **Cross-Platform Deduplication** | Generates SHA-256 content fingerprints (`normalized_title \| normalized_company \| normalized_location`) to merge duplicates from distinct job boards in batches. | [`services/deduplicator/main.py`](file:///c:/Users/Vivobook%20pro%2015/Desktop/Job%20Scrapping/services/deduplicator/main.py) | `hashlib`, `MongoDB bulk_write` |
| **Scam & Fraud Shield (Verifier)** | Dual-layer fraud detection combining an **XGBoost ML Classifier** (trained on the EMSCAD scam dataset) with **50+ regex heuristic rules** and **company domain SSL/age checks**. | [`services/verifier/agents/scam_detector.py`](file:///c:/Users/Vivobook%20pro%2015/Desktop/Job%20Scrapping/services/verifier/agents/scam_detector.py) | `xgboost`, `scikit-learn`, `httpx` |
| **Skill & Salary Enrichment** | Extracts required hard skills, nice-to-have skills, and tech stacks using taxonomy matching, spaCy NLP tokenization, and local Ollama LLM extraction. | [`services/enrichment/agents/skill_extractor.py`](file:///c:/Users/Vivobook%20pro%2015/Desktop/Job%20Scrapping/services/enrichment/agents/skill_extractor.py) | `spaCy`, `Ollama / LLM Router` |
| **Vector Embeddings & Hybrid Search**| Encodes job postings into 384-dimensional dense vectors using `all-MiniLM-L6-v2` and indexes them in Qdrant for semantic cosine similarity search with MongoDB full-text fallback. | [`services/embedder/main.py`](file:///c:/Users/Vivobook%20pro%2015/Desktop/Job%20Scrapping/services/embedder/main.py), [`services/search/main.py`](file:///c:/Users/Vivobook%20pro%2015/Desktop/Job%20Scrapping/services/search/main.py) | `sentence-transformers`, `Qdrant`, `MongoDB FTS` |
| **Explainable Resume Matching** | 4-step resume analyzer (PDF/DOCX/TXT) computing a **5-factor weighted score** (Skills 40%, Title 20%, Experience 15%, Location 15%, Education 10%) plus **Skill Gap Roadmaps**. | [`services/gateway/routers/resume.py`](file:///c:/Users/Vivobook%20pro%2015/Desktop/Job%20Scrapping/services/gateway/routers/resume.py), [`shared/utils/recommender.py`](file:///c:/Users/Vivobook%20pro%2015/Desktop/Job%20Scrapping/shared/utils/recommender.py) | `pdfplumber`, `docx2txt`, `pypdf` |
| **Admin Control Console** | Command-center SPA displaying real-time KPI cards, stage-by-stage pipeline flows, agent processing latencies (ms), scam audit logs, and 1-click collection triggers. | [`frontend/admin/app.js`](file:///c:/Users/Vivobook%20pro%2015/Desktop/Job%20Scrapping/frontend/admin/app.js), [`frontend/admin/index.html`](file:///c:/Users/Vivobook%20pro%2015/Desktop/Job%20Scrapping/frontend/admin/index.html) | Vanilla JS, HTML5, CSS3 Glassmorphism |
| **Public Job Discovery Portal** | High-performance candidate portal with live search autocomplete, multi-filter sidebars (Remote, Exp, Salary LPA slider, Trust badge), and slide-over job details drawer. | [`frontend/jobboard/app.js`](file:///c:/Users/Vivobook%20pro%2015/Desktop/Job%20Scrapping/frontend/jobboard/app.js), [`frontend/jobboard/index.html`](file:///c:/Users/Vivobook%20pro%2015/Desktop/Job%20Scrapping/frontend/jobboard/index.html) | Vanilla JS, CSS3 Aurora Dark System |

---

# 2. Complete Technology Stack & Justification

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                             TALENTLENS TECH STACK                                │
├────────────────────────┬─────────────────────────────┬───────────────────────────┤
│ LAYER                  │ PRIMARY TECHNOLOGY          │ IMPLEMENTED ROLE          │
├────────────────────────┼─────────────────────────────┼───────────────────────────┤
│ Language & Runtime     │ Python 3.12 (AsyncIO)       │ Microservices & Backend   │
│ Web & Gateway API      │ FastAPI (Uvicorn / Starlette)│ REST API & Auth Gateway   │
│ Primary Database       │ MongoDB 7.0 (Motor Async)   │ Flexible Document Store   │
│ Vector Database        │ Qdrant                      │ Semantic Embeddings (384d)│
│ Message Broker         │ Redpanda (Kafka-compatible) │ High-Throughput Streaming │
│ Caching & Sessions     │ Redis 7 (Alpine)            │ Query Cache & Rate Limits │
│ Object Storage         │ MinIO (S3-compatible)       │ Resumes, Logos, ML Models │
│ ML & Vector Models     │ SentenceTransformers, XGBoost│ Embeddings & Fraud Model │
│ NLP & Parsing          │ spaCy, pdfplumber, docx2txt │ Resume & Skill Extraction │
│ Observability & MLOps  │ Prometheus, Grafana, MLflow │ Metrics, Traces, Models   │
│ Containerization       │ Docker & Docker Compose     │ Multi-service Orchestration│
│ Frontend (Jobboard/Adm)│ Vanilla JS, HTML5, CSS3     │ Zero-build High Speed SPA │
└────────────────────────┴─────────────────────────────┴───────────────────────────┘
```

---

### In-Depth Technology Breakdown

#### 1. FastAPI & Python 3.12 (AsyncIO)
- **Where Used**: [`services/gateway/main.py`](file:///c:/Users/Vivobook%20pro%2015/Desktop/Job%20Scrapping/services/gateway/main.py) and all pipeline microservices.
- **Why Chosen**: Native `async`/`await` support for non-blocking I/O during heavy external web scraping and database calls; automated OpenAPI/Swagger documentation; Pydantic v2 data validation with zero boilerplate.
- **Why Not Flask/Django?**: Flask is synchronous by default and requires third-party plugins for validation; Django is monolithic and carries heavy ORM overhead ill-suited for microservice streaming pipelines.
- **Interview Response**: *"We chose FastAPI because our architecture is heavily I/O-bound—handling concurrent HTTP scrapers, Kafka consumer batches, and MongoDB queries. FastAPI's native async event loop gives us high concurrency with strict Pydantic type safety."*

#### 2. MongoDB 7.0 (via Motor Async Driver)
- **Where Used**: [`shared/database/session.py`](file:///c:/Users/Vivobook%20pro%2015/Desktop/Job%20Scrapping/shared/database/session.py), [`shared/database/models.py`](file:///c:/Users/Vivobook%20pro%2015/Desktop/Job%20Scrapping/shared/database/models.py).
- **Why Chosen**: Job postings across Adzuna, Greenhouse, Indeed, and RSS have highly variable, polymorphic schemas (different salary formats, custom metadata, varying skill tags). MongoDB's BSON document model allows flexible schema evolution without complex migration locks.
- **Why Not PostgreSQL?**: While Postgres with `jsonb` is viable, MongoDB natively excels at storing large, semi-structured document payloads, indexing embedded arrays (e.g. `required_skills`), and supporting non-blocking async operations via `motor`.
- **Interview Response**: *"Scraped job postings from different ATS engines have inconsistent structures. MongoDB gave us the document flexibility to store raw and enriched job metadata seamlessly while maintaining compound indexes on published status and location."*

#### 3. Redpanda (Kafka-Compatible Streaming Broker)
- **Where Used**: [`shared/kafka/producer.py`](file:///c:/Users/Vivobook%20pro%2015/Desktop/Job%20Scrapping/shared/kafka/producer.py), [`shared/kafka/consumer.py`](file:///c:/Users/Vivobook%20pro%2015/Desktop/Job%20Scrapping/shared/kafka/consumer.py).
- **Why Chosen**: Decouples the scraping ingestion rate from downstream ML inference and database writes. Redpanda provides 100% Kafka API compatibility written in C++ with zero JVM/Zookeeper memory overhead.
- **Why Not RabbitMQ or In-Memory Queues?**: In-memory queues lack disk persistence and partition scalability; RabbitMQ does not provide replayable distributed commit logs, which are essential for reprocessing historical jobs through updated ML models.
- **Interview Response**: *"We use Redpanda as an event streaming backbone. It buffers bursts of scraped jobs into partitioned topics, allowing services like cleaner, deduplicator, and verifier to consume and scale independently without overwhelming database connections."*

#### 4. Qdrant Vector Database
- **Where Used**: [`services/embedder/main.py`](file:///c:/Users/Vivobook%20pro%2015/Desktop/Job%20Scrapping/services/embedder/main.py), [`services/search/main.py`](file:///c:/Users/Vivobook%20pro%2015/Desktop/Job%20Scrapping/services/search/main.py).
- **Why Chosen**: Purpose-built Rust vector search engine supporting HNSW indexes and payload-based filtering (e.g. searching vectors only within `location == 'Remote'` and `status == 'published'`).
- **Why Not pgvector?**: Qdrant offers dedicated memory-mapped vector indexing, sub-millisecond cosine distance computation, and standalone Docker scalability without taxing the primary transactional database.
- **Interview Response**: *"Keyword matching misses semantic intent. Qdrant stores 384-dimensional dense vectors of job postings, allowing candidates to search conceptually (e.g., 'cloud infrastructure automation' retrieves 'DevOps/Terraform' roles) via sub-5ms cosine similarity."*

#### 5. SentenceTransformers (`all-MiniLM-L6-v2`)
- **Where Used**: [`services/embedder/main.py`](file:///c:/Users/Vivobook%20pro%2015/Desktop/Job%20Scrapping/services/embedder/main.py).
- **Why Chosen**: Generates high-quality 384-dimensional dense embeddings with an optimal balance of inference speed (~15ms per batch on CPU) and semantic clustering accuracy.
- **Why Not OpenAI `text-embedding-3-small`?**: Local models eliminate per-token API costs, remove external network latency dependencies, and preserve candidate resume data privacy.

#### 6. XGBoost + Heuristic Rule Ensemble
- **Where Used**: [`services/verifier/agents/scam_detector.py`](file:///c:/Users/Vivobook%20pro%2015/Desktop/Job%20Scrapping/services/verifier/agents/scam_detector.py), [`ml/scam_detector/`](file:///c:/Users/Vivobook%20pro%2015/Desktop/Job%20Scrapping/ml/scam_detector).
- **Why Chosen**: Fraud detection requires both deterministic rules (e.g. blocking upfront deposit requests, WhatsApp-only contacts, Telegram links) and statistical pattern recognition on job text features.
- **Interview Response**: *"Pure ML models can be fooled by adversarial phrasing, and pure regex rules miss subtle patterns. Our hybrid ensemble runs 50+ deterministic heuristic rules in parallel with a gradient-boosted decision tree to produce an explainable fraud risk score."*

---

# 3. System Architecture & Component Interaction

```
                                 [ CLIENT LAYER ]
                     ┌──────────────────────────────────────┐
                     │ • Jobboard UI (Port 3000)            │
                     │ • Admin Console UI (Port 3001)       │
                     └──────────────────┬───────────────────┘
                                        │ HTTP / REST API (JWT)
                                        ▼
                     ┌──────────────────────────────────────┐
                     │      API GATEWAY (Port 8000)         │
                     │ • /auth • /jobs • /resume • /admin   │
                     └───────┬──────────────────────┬───────┘
                             │                      │
       ┌─────────────────────┼──────────────────────┼────────────────────┐
       │ (Cache & Auth)      │ (Reads & State)      │ (Vector Query)     │ (Ingestion Trigger)
       ▼                     ▼                      ▼                    ▼
 ┌───────────┐         ┌───────────┐          ┌───────────┐        ┌───────────┐
 │  Redis 7  │         │  MongoDB  │          │  Qdrant   │        │ Collector │
 │ (Port6379)│         │ (Port27017│          │ (Port6333)│        │  Service  │
 └───────────┘         └───────────┘          └───────────┘        └─────┬─────┘
                                                                         │
 ════════════════════════════════════════════════════════════════════════╪═══════════════════
                      EVENT STREAMING BACKBONE (REDPANDA / KAFKA)        │
 ════════════════════════════════════════════════════════════════════════╪═══════════════════
                                                                         │
               ┌─────────────────────────────────────────────────────────┘
               │
               ├──► Topic: 'job.raw' ──────────► [ Cleaner Service ]
               │                                         │
               ├──► Topic: 'job.cleaned' ──────► [ Deduplicator Service ]
               │                                         │
               ├──► Topic: 'job.deduplicated' ─► [ Enrichment Service ]
               │                                         │
               ├──► Topic: 'job.enriched' ─────► [ Verifier Service ] (ML + Rules)
               │                                         │
               └──► Topic: 'job.verified' ─────► [ Embedder Service ] ──► (Qdrant & Published)
```

---

# 4. End-to-End Data Pipeline Flow

```
[External Sources]
       │
       ▼
 1. COLLECTOR    ──► Output: RawJob object with unparsed title, company, raw HTML description.
       │             Kafka: 'job.raw'
       ▼
 2. CLEANER      ──► Output: Stripped HTML, normalized city/state/country, parsed min/max salary.
       │             Kafka: 'job.cleaned'
       ▼
 3. DEDUPLICATOR ──► Output: SHA-256 fingerprint verified; duplicates flagged 'duplicate'.
       │             Kafka: 'job.deduplicated'
       ▼
 4. ENRICHMENT   ──► Output: Extracted skills list, experience level, predicted salary range.
       │             Kafka: 'job.enriched'
       ▼
 5. VERIFIER     ──► Output: Scam risk probability (0.0–1.0), triggered fraud rule list, trust score.
       │             Kafka: 'job.verified' (if score < 0.60) / status='rejected' (if >= 0.60)
       ▼
 6. EMBEDDER     ──► Output: 384-dimensional dense vector indexed in Qdrant; status='published'.
       │
       ▼
 7. GATEWAY/USER ──► Output: Search results, transparent ATS match explanations, skill gap reports.
```

### Detailed Pipeline Stages

#### Stage 1: Ingestion / Collection
- **File**: [`services/collector/agents.py`](file:///c:/Users/Vivobook%20pro%2015/Desktop/Job%20Scrapping/services/collector/agents.py)
- **Input**: Search query keywords and ATS company slugs.
- **Process**: Concurrently issues HTTP requests using `httpx.AsyncClient` across Adzuna REST API, Greenhouse/Lever public job APIs, Indeed/Remotive HTML scraping, and RSS XML feeds.
- **Output**: JSON payload conforming to [`RawJob`](file:///c:/Users/Vivobook%20pro%2015/Desktop/Job%20Scrapping/shared/models/job.py#L35) published to Kafka topic `job.raw`.
- **Failure Mitigation**: Exponential backoff with jitter and per-source circuit breakers prevent IP bans.

#### Stage 2: Data Cleaning & Normalization
- **File**: [`services/cleaner/main.py`](file:///c:/Users/Vivobook%20pro%2015/Desktop/Job%20Scrapping/services/cleaner/main.py)
- **Input**: Raw job JSON from `job.raw`.
- **Process**: Regex HTML tag stripping, HTML entity decoding, whitespace compaction, geographic entity parsing, and currency/compensation parsing (handles ₹ LPA, USD hourly/yearly formats).
- **Output**: Cleaned structured job payload published to `job.cleaned`.

#### Stage 3: Deduplication & Fingerprinting
- **File**: [`services/deduplicator/main.py`](file:///c:/Users/Vivobook%20pro%2015/Desktop/Job%20Scrapping/services/deduplicator/main.py)
- **Input**: Cleaned job messages from `job.cleaned`.
- **Process**: Computes SHA-256 hash on normalized string `f"{clean_title}|{clean_company}|{clean_location}"`. Queries MongoDB using single `$in` batch queries to check for existing active postings within a 30-day window.
- **Output**: Unique jobs published to `job.deduplicated`; duplicate jobs marked `status: "duplicate"` in MongoDB.

#### Stage 4: Enrichment & Skill Extraction
- **File**: [`services/enrichment/agents/skill_extractor.py`](file:///c:/Users/Vivobook%20pro%2015/Desktop/Job%20Scrapping/services/enrichment/agents/skill_extractor.py)
- **Input**: Unique job postings from `job.deduplicated`.
- **Process**: Matches text against a comprehensive technology taxonomy (Languages, Frameworks, Cloud, Databases, Methodologies), classifies seniority (`entry`, `mid`, `senior`, `lead`), and falls back to local Ollama LLM extraction for non-standard descriptions.
- **Output**: Enriched job document published to `job.enriched`.

#### Stage 5: Fraud Verification & Trust Scoring
- **File**: [`services/verifier/agents/scam_detector.py`](file:///c:/Users/Vivobook%20pro%2015/Desktop/Job%20Scrapping/services/verifier/agents/scam_detector.py)
- **Input**: Enriched job from `job.enriched`.
- **Process**: Evaluates job against 50+ heuristic scam regex patterns (advance payments, WhatsApp/Telegram recruiters, unrealistic daily income, sensitive document requests) alongside an XGBoost classification model. Checks hiring company domain SSL certificate validity and age.
- **Output**: Computes `scam_probability` (0.0 to 1.0) and `trust_score` (0 to 100). Jobs with `scam_probability < 0.60` publish to `job.verified`; high-risk jobs are set to `status: "rejected"`.

#### Stage 6: Vector Embedding Generation
- **File**: [`services/embedder/main.py`](file:///c:/Users/Vivobook%20pro%2015/Desktop/Job%20Scrapping/services/embedder/main.py)
- **Input**: Verified job payload from `job.verified`.
- **Process**: Batches job titles, requirements, and descriptions through `SentenceTransformer('all-MiniLM-L6-v2')`. Upserts 384-dimensional dense vectors into Qdrant collection `job_embeddings`.
- **Output**: Sets job `status = "published"` in MongoDB with `embedding_id`. The job is now instantly discoverable on the public board.

---

# 5. Resume Upload, Parsing & Multi-Factor Matching Algorithm

```
[ Resume File (PDF / DOCX / TXT) ]
                │
                ▼
   [ Text Extraction Layer ]
   (pdfplumber / docx2txt / pypdf)
                │
                ▼
   [ Profile Parser Engine ]
   • Skills Extractor (Regex + Taxonomy)
   • Target Titles & Seniority Classifier
   • Education Degrees & Certifications Extractor
   • Experience Years Calculation
                │
                ▼
   [ Multi-Factor Recommender Engine ]
   Scoring Weights:
   ├── 40% Skills Overlap (Jaccard / Set Intersection)
   ├── 20% Title Semantic Similarity
   ├── 15% Experience Level / Years Match
   ├── 15% Location & Remote Preference Alignment
   └── 10% Education Degree & Certification Match
                │
                ▼
   [ Output Generation ]
   • Ranked Recommended Job Cards (with SVG match donut rings)
   • 5-Factor Score Breakdown
   • Transparent Positive vs Warning Signals
   • Actionable Skill Gap Analysis & Sequential Learning Roadmap
```

### Exact Recommender Math & Weight Formulation
From [`shared/utils/recommender.py`](file:///c:/Users/Vivobook%20pro%2015/Desktop/Job%20Scrapping/shared/utils/recommender.py):

$$\text{Final Match Score} = (S_{\text{skills}} \times 0.40) + (S_{\text{title}} \times 0.20) + (S_{\text{exp}} \times 0.15) + (S_{\text{loc}} \times 0.15) + (S_{\text{edu}} \times 0.10)$$

Where:
1. **$S_{\text{skills}}$ (40%)**: Ratio of candidate skills matching the job's `required_skills` set ($|C_{\text{skills}} \cap J_{\text{skills}}| / |J_{\text{skills}}|$). Bonus weight added if candidate has `nice_to_have_skills`.
2. **$S_{\text{title}}$ (20%)**: Token overlap and substring alignment between candidate target titles and the job title.
3. **$S_{\text{exp}}$ (15%)**: Penalty incurred if candidate experience years fall below the required minimum.
4. **$S_{\text{loc}}$ (15%)**: Full score for remote roles matching candidate remote preference; geographic city/state match for on-site roles.
5. **$S_{\text{edu}}$ (10%)**: Degree level matching (Bachelor's, Master's, PhD) and professional certification presence.

---

# 6. Database Schema & Data Models

The platform uses **MongoDB 7.0** as its primary document store, modeled via Pydantic in [`shared/database/models.py`](file:///c:/Users/Vivobook%20pro%2015/Desktop/Job%20Scrapping/shared/database/models.py).

### Core Collections & Fields

```text
┌─────────────────────────────────────────┐         ┌─────────────────────────────────────────┐
│              COMPANIES                  │         │                  JOBS                   │
├─────────────────────────────────────────┤         ├─────────────────────────────────────────┤
│ _id: str (UUID)                         │◄────────┤ _id: str (UUID)                         │
│ name: str                               │ 1     N │ company_id: str (Ref -> Companies._id)  │
│ normalized_name: str (Indexed)          │         │ company_name: str                       │
│ domain: str                             │         │ title: str (Indexed)                    │
│ website: str                            │         │ description: str (Full-Text Indexed)    │
│ trust_score: float (0.0 - 100.0)        │         │ status: str ("raw".."published")        │
│ is_verified: bool                       │         │ source: str ("adzuna","indeed",etc.)    │
│ ssl_valid: bool                         │         │ source_job_id: str                      │
│ domain_age_days: int                    │         │ source_url: str                         │
│ created_at: datetime                    │         │ apply_url: str                          │
└─────────────────────────────────────────┘         │ location_city / state / country: str    │
                                                    │ job_type: str ("full_time","contract")  │
                                                    │ remote_type: str ("remote","hybrid")    │
┌─────────────────────────────────────────┐         │ experience_level: str ("entry".."lead") │
│                USERS                    │         │ salary_min / max: float                 │
├─────────────────────────────────────────┤         │ salary_currency: str ("INR", "USD")     │
│ _id: str (UUID)                         │         │ required_skills: list[str] (Indexed)    │
│ email: str (Unique Index)               │         │ nice_to_have_skills: list[str]          │
│ hashed_password: str                    │         │ tech_stack: list[str]                   │
│ full_name: str                          │         │ quality_score: float (0.0 - 100.0)      │
│ role: str ("user" | "admin")            │         │ scam_probability: float (0.0 - 1.0)     │
│ is_active: bool                         │         │ is_duplicate: bool                      │
│ created_at: datetime                    │         │ embedding_id: str (Ref -> Qdrant Point) │
└─────────────────────────────────────────┘         │ posted_at: datetime                     │
                                                    └─────────────────────────────────────────┘
```

### Essential Database Indexes
- `jobs.status` + `jobs.created_at`: For fast filtering of published jobs on the jobboard.
- `jobs.required_skills`: Multi-key index for fast taxonomy lookups.
- `jobs.source` + `jobs.source_job_id` (Unique Compound): Enforces source-level deduplication.
- `jobs.title` + `jobs.description` (Text Index): Powers full-text search fallback.
- `users.email` (Unique): Prevents duplicate account registrations.

---

# 7. Complete API Design & Endpoints

| Category | Method | Endpoint | Auth Required | Purpose / Description |
| :--- | :--- | :--- | :--- | :--- |
| **Authentication** | `POST` | `/api/v1/auth/register` | None | Register new user account (defaults to `role: user`). |
| | `POST` | `/api/v1/auth/login` | None | Verify credentials and return JWT Access + Refresh tokens. |
| | `GET` | `/api/v1/auth/me` | Bearer Token | Retrieve currently logged-in user profile & role. |
| | `POST` | `/api/v1/auth/refresh` | Bearer Token | Refresh an expired access token using refresh token. |
| **Job Discovery** | `GET` | `/api/v1/jobs` | None | Paginated search with filters (remote, exp, salary, scam risk). |
| | `GET` | `/api/v1/jobs/{id}` | None | Retrieve full job specification, company trust score, and skills. |
| **Resume & AI** | `POST` | `/api/v1/resume/parse` | None | Multipart upload (PDF/DOCX/TXT) returning extracted candidate profile. |
| | `POST` | `/api/v1/resume/parse-text` | None | Parse raw pasted resume text directly. |
| | `POST` | `/api/v1/resume/recommendations`| None | Match candidate profile against published jobs with skill gap report. |
| **Semantic Search** | `GET` | `/api/v1/search/hybrid` | None | Hybrid search combining Qdrant dense vectors with MongoDB text scores. |
| | `GET` | `/api/v1/search/autocomplete` | None | Real-time search query suggestions for titles, skills, and companies. |
| **Market Insights**| `GET` | `/api/v1/analytics/overview` | None | Platform-wide totals (live jobs, companies, verified safe %). |
| | `GET` | `/api/v1/analytics/skill-demand` | None | Top 15 in-demand skills ranked by frequency in active postings. |
| | `GET` | `/api/v1/analytics/salary-benchmarks`| None | Salary percentiles and averages grouped by engineering title. |
| **Admin Console** | `GET` | `/api/v1/admin/stats` | Admin Token | Pipeline stats, status distribution, user counts, and failure rates. |
| | `POST` | `/api/v1/admin/collect` | Admin Token | Trigger manual collection run across selected sources. |
| | `GET` | `/api/v1/admin/jobs/scam-reports`| Admin Token | Query flagged high-risk jobs with triggered heuristic rules. |
| | `PATCH`| `/api/v1/admin/jobs/{id}/status` | Admin Token | Admin override to reject or restore a job posting. |
| | `GET` | `/api/v1/admin/users` | Admin Token | Manage platform users and promote roles. |

---

# 8. Security Implementation

### Implemented Security Features
1. **Role-Based Access Control (RBAC)**: Enforced via FastAPI dependency injection [`require_admin`](file:///c:/Users/Vivobook%20pro%2015/Desktop/Job%20Scrapping/services/gateway/deps.py). Only authenticated JWT tokens with `role: "admin"` can access `/admin/*` routes.
2. **JWT Authentication**: Short-lived Access Tokens (60 min) signed with `HS256` secret + Long-lived Refresh Tokens (7 days).
3. **Password Security**: Salted SHA-256 cryptographic hashing (isolated via environment variable salts).
4. **File Upload Hardening**:
   - File size restricted to `10MB` max.
   - Whitelist validation on extensions (`.pdf`, `.docx`, `.txt`).
   - In-memory parsing via `io.BytesIO` without saving untrusted executable files to the host OS filesystem.
5. **CORS Configuration**: Restricts API access to explicit frontend origins (`http://localhost:3000`, `http://localhost:3001`).
6. **SQL/NoSQL Injection Mitigation**: Pydantic v2 type coercion and parameterized MongoDB Motor driver query dictionaries prevent injection vectors.

### Recommended Future Security Enhancements
- Upgrade password hashing from salted SHA-256 to `bcrypt` or `Argon2id` with automated work-factor scaling.
- Implement Redis-backed token revocation blacklists for instant logout invalidation.
- Add Web Application Firewall (WAF) and Cloudflare DDoS protection for public endpoints.

---

# 9. Performance, Scalability & Bottleneck Analysis

```text
SCALABILITY BOTTLENECK ANALYSIS:
┌──────────────────────────────────────────────────────────────────────────┐
│ Component           Current Throughput     Scale Bottleneck at 10k Users│
├─────────────────────┼──────────────────────┼─────────────────────────────┤
│ Ingestion/Scraping  │ ~500 jobs / min      │ External target rate limits │
│ Pipeline Processing │ ~1,200 jobs / min    │ SentenceTransformers on CPU │
│ Database Queries    │ ~4,500 req / sec     │ MongoDB Connection Pool     │
│ Vector Search       │ ~1,800 QPS (Qdrant)  │ RAM for HNSW Vector Graph   │
└─────────────────────┴──────────────────────┴─────────────────────────────┘
```

### What breaks first when scaling from 100 to 10,000 concurrent users?
1. **Vector Embedding Inference Latency**: Generating embeddings on CPU during heavy scraping bursts slows down the pipeline.
   - *Fix*: Decouple the embedder service onto GPU worker nodes (NVIDIA TensorRT / ONNX Runtime) and run batched inference.
2. **MongoDB Connection Limits**: High concurrent frontend traffic competing with background bulk writes.
   - *Fix*: Route read-heavy traffic to a MongoDB secondary replica set and cache hot search queries in Redis with a 5-minute TTL.
3. **External Job Source Rate Limits**: Scraping targets (Adzuna/Indeed) throttling requests with HTTP 429.
   - *Fix*: Deploy rotating residential proxy pools and stagger collection cron intervals.

---

# 10. Technology Decision Justifications

### 1. Why FastAPI instead of Django or Flask?
- **Problem**: Need to expose high-throughput asynchronous REST APIs that handle file uploads, Kafka triggers, and vector lookups.
- **Alternatives**: Django, Flask.
- **Why FastAPI**: Native Python `asyncio` event loop support; automatic Pydantic request validation; built-in Swagger UI documentation. Django's synchronous ORM adds unnecessary overhead for non-relational document streaming.
- **Trade-off**: Requires developers to be comfortable with asynchronous programming paradigms and non-blocking database drivers (`motor`).

### 2. Why MongoDB instead of PostgreSQL?
- **Problem**: Ingesting job postings from 10+ distinct sources where schemas, compensation fields, and skill arrays vary wildly.
- **Alternatives**: PostgreSQL with `jsonb`, MySQL.
- **Why MongoDB**: True document model allows seamless storage of raw and enriched job metadata without migration locking. Native support for multi-key indexing on skill arrays.
- **Trade-off**: No ACID multi-table joins; relationships (e.g. Job -> Company) must be resolved at the application level.

### 3. Why Redpanda / Kafka instead of synchronous processing?
- **Problem**: Scraping 5,000 jobs at once would freeze the API Gateway if processed synchronously.
- **Alternatives**: Celery with Redis, direct HTTP service calls.
- **Why Redpanda**: Distributed, replayable event log. If the Verifier or Embedder service crashes, messages remain safely stored in the topic partition and resume processing upon restart with zero data loss.
- **Trade-off**: Introduces eventual consistency—a scraped job takes 2–5 seconds to traverse all pipeline stages before appearing on the public job board.

---

# 11. Project Limitations & Critical Review

1. **Local Embedding Model Footprint**: Running `all-MiniLM-L6-v2` inside a Docker container without GPU acceleration consumes ~400MB RAM and increases latency during large batch embeddings.
2. **Scraper Brittleness on DOM Changes**: Scrapers targeting HTML structures (e.g. Indeed) require maintenance when third-party sites update their CSS selectors.
3. **Single-Node Docker Setup**: The current development environment runs MongoDB and Redpanda as single-node instances rather than clustered multi-broker setups.
4. **Synchronous Resume Extraction**: PDF text parsing occurs within the FastAPI request cycle; extremely large, scanned image-based PDFs will time out without OCR support.

---

# 12. Future Improvement Roadmap

```text
┌──────────────────────────────────────────────────────────────────────────┐
│                           DEVELOPMENT ROADMAP                            │
├───────────────────┬──────────────────────────────────────────────────────┤
│ Short-Term        │ • Integrate Tesseract OCR for scanned PDF resumes    │
│ (1–3 Months)      │ • Add Redis caching for top 50 popular search queries│
│                   │ • Upgrade password hashing to Argon2id               │
├───────────────────┼──────────────────────────────────────────────────────┤
│ Medium-Term       │ • Deploy distributed 3-node MongoDB replica set      │
│ (3–6 Months)      │ • Implement ONNX Runtime GPU acceleration for embedder│
│                   │ • Add user email notification dispatch via SendGrid  │
├───────────────────┼──────────────────────────────────────────────────────┤
│ Long-Term         │ • Launch 'Stitch AI' Live Resume Tailoring Studio    │
│ (6–12 Months)     │ • Multi-region Kubernetes deployment with Helm charts│
│                   │ • Automated employer verification via LinkedIn OAuth │
└───────────────────┴──────────────────────────────────────────────────────┘
```

---

# 13. Complete Interview Question & Answer Bank

## A. Project Overview & Architecture Questions

### Q1: "Can you describe your project in 60 seconds?"
> **Verbal Answer**: *"I built **TalentLens**, a distributed job intelligence and fraud-prevention platform. The core problem it solves is that online job boards are flooded with duplicate listings, black-box ATS algorithms, and employment scams. Our system uses an asynchronous event-driven pipeline powered by Redpanda and FastAPI. We scrape and ingest jobs across multiple sources, clean and normalize the data, deduplicate postings using SHA-256 fingerprinting, verify listing legitimacy using an XGBoost ML classifier combined with 50+ heuristic rules, and generate 384-dimensional vector embeddings in Qdrant. On the candidate side, job seekers can upload their resume to receive transparent, 5-factor match scores and actionable skill-gap roadmaps."*

### Q2: "Why did you design the backend as an event-driven pipeline rather than a monolith?"
> **Verbal Answer**: *"Job scraping and ML processing are bursty and computationally heavy. If our scrapers collect 2,000 jobs in 30 seconds, processing them synchronously would block web workers and degrade API responsiveness. By decoupling each stage—cleaning, deduplication, enrichment, verification, and embedding—into separate Kafka consumer topics, each service processes data at its own optimal pace. If downstream vector embedding is running on CPU, the upstream scraper can continue without dropping records."*

---

## B. Fraud Detection & Machine Learning Questions

### Q3: "How does your Scam Detection Agent work?"
> **Verbal Answer**: *"Our scam verifier operates as a hybrid ensemble. It combines a trained **XGBoost gradient-boosted decision tree** (trained on the EMSCAD employment scam dataset) with a deterministic rules engine containing **50+ regex heuristic patterns**. The rules immediately flag high-risk signals such as upfront training fee demands, WhatsApp-only contacts, Telegram channels, crypto task deposits, and requests for bank account details before hiring. In parallel, it verifies hiring company legitimacy by auditing domain SSL certificates and domain age. The combined model outputs an explainable risk score between 0.0 and 1.0; anything above 0.60 is automatically quarantined from publication."*

### Q4: "Why use an ensemble of ML + Rules instead of just an LLM or just ML?"
> **Verbal Answer**: *"Pure LLMs are expensive, introduce high latency (500ms–2s per job), and suffer from hallucinations. Pure ML models can fail on adversarial phrasing they haven't seen during training. Deterministic regex rules catch 95% of known scam archetypes in sub-millisecond time, while the ML model captures subtle statistical text features. This keeps our pipeline processing fast, explainable, and cost-free."*

---

## C. Deduplication & Vector Search Questions

### Q5: "How do you detect duplicate jobs scraped from different websites?"
> **Verbal Answer**: *"We use a two-tiered deduplication strategy. First, we check the unique `source_job_id` per aggregator. Second, we compute a normalized content fingerprint: we take the lowercased job title, strip developer/engineer aliases, strip punctuation, concatenate it with the cleaned company name and location, and generate a **SHA-256 hash**. Before publishing, the Deduplicator service queries MongoDB for any identical fingerprint created in the past 30 days. If found, the new listing is marked as a duplicate and merged to avoid cluttering search results."*

### Q6: "Why use Qdrant for semantic search instead of relying on standard database full-text search?"
> **Verbal Answer**: *"Keyword search fails when candidates use synonyms or conceptual descriptions. For example, a candidate searching for 'cloud deployment and infrastructure automation' wouldn't match a job titled 'DevOps Engineer' if the exact phrase isn't present. By encoding both the job description and candidate query into 384-dimensional dense vectors using SentenceTransformers and indexing them in Qdrant with HNSW graphs, we achieve true conceptual matching in under 5 milliseconds."*

---

## D. Resume Parsing & Recommender Questions

### Q7: "How does your resume parsing and recommendation algorithm work?"
> **Verbal Answer**: *"When a user uploads a PDF or DOCX resume, we extract raw text in memory using `pdfplumber` and parse structured candidate profiles—extracting hard skills, target titles, certifications, education, and years of experience. We then evaluate published verified jobs against a **5-factor weighted scoring model**: Skill Match carries 40%, Title Alignment 20%, Experience Level 15%, Location/Remote preference 15%, and Education/Certs 10%. We also provide full transparency by showing the candidate the exact score breakdown and generating an automated skill-gap analysis that identifies missing high-demand skills."*

---

# 14. "What If" Scenario Defense

### Scenario 1: "What if the scraper gets blocked by target job boards with HTTP 429 / 403?"
- **Immediate Response**: The circuit breaker triggers for that specific source, pausing requests for an exponential backoff window (30s → 60s → 300s) while other scrapers continue.
- **Architecture Fix**: Rotate through a pool of randomized user-agent browser headers, introduce request rate-limiters, and route outbound scraper traffic through rotating proxy gateways.

### Scenario 2: "What if a user uploads a malicious or corrupt PDF file?"
- **Immediate Response**: The upload endpoint validates file size (capped at 10MB) and whitelists file extensions. File contents are processed in-memory via `io.BytesIO` streams without executing host OS commands.
- **Architecture Fix**: If text extraction yields fewer than 20 readable characters or encounters corruption exceptions, the endpoint returns an HTTP 422 Unprocessable Entity with a safe user-facing error message.

### Scenario 3: "What if the primary MongoDB database goes down?"
- **Immediate Response**: Redpanda/Kafka continues buffering scraped job messages on disk partitions without data loss. The FastAPI Gateway returns healthy cached responses for hot queries from Redis.
- **Architecture Fix**: Upon MongoDB restart, Kafka consumer groups automatically resume offset commits from where they left off, ensuring zero pipeline data loss.

---

# 15. 5-Minute Technical Viva / Presentation Script

> **Slide 1: Problem & Motivation (1 min)**
> *"Good morning. Today I am presenting **TalentLens**, an AI-Powered Job Intelligence and Verification Platform. In today's job market, candidates face three major hurdles: rampant employment scams, massive job duplication across fragmented aggregators, and black-box ATS algorithms that give no feedback. TalentLens solves this by combining automated multi-source scraping, ML fraud detection, hybrid semantic search, and transparent resume matching."*
>
> **Slide 2: Architecture & Tech Stack (1.5 min)**
> *"Our architecture is a distributed, event-driven system. The backend is built with **FastAPI** in Python 3.12, utilizing **Redpanda** as our Kafka-compatible event streaming backbone, **MongoDB** for document storage, **Redis** for caching, and **Qdrant** for vector search. Scraped jobs pass through a 6-stage pipeline: ingestion, HTML cleaning, SHA-256 deduplication, skill extraction via NLP, ML-based scam verification using XGBoost and 50+ heuristic rules, and 384-dimensional vector embedding."*
>
> **Slide 3: Key Features & Demonstration (1.5 min)**
> *"We have implemented two complete user interfaces: a candidate-facing Job Board and an Admin Command Console. On the candidate portal, users can search jobs via hybrid semantic search or upload a resume to receive a transparent 5-factor match score and a sequential skill-gap roadmap. On the Admin console, administrators have full visibility over real-time pipeline event streams, processing latency per microservice, and flagged scam audit reports."*
>
> **Slide 4: Challenges, Limitations & Future Work (1 min)**
> *"Our biggest technical challenge was achieving high ingestion throughput while running ML inference locally. We solved this through batch Kafka consumption and vectorized SentenceTransformer batching. For future work, we plan to implement GPU-accelerated embedding inference and expand our 'Stitch AI' resume tailoring studio. Thank you, and I am now open to your questions."*

---

# 16. Technical Interview Quick Cheat Sheet

| Prompt | 10-Second Interview Response |
| :--- | :--- |
| **Project in one sentence** | An event-driven distributed job intelligence platform with ML scam detection and semantic resume matching. |
| **Primary Backend Framework** | FastAPI (Python 3.12) with asynchronous I/O and Pydantic v2 validation. |
| **Primary Database** | MongoDB 7.0 for flexible, unstructured document storage and array indexing. |
| **Message Broker** | Redpanda (C++ Kafka-compatible streaming) for decoupling pipeline stages. |
| **Vector Database** | Qdrant running HNSW cosine similarity indexes on 384-dimensional vectors. |
| **Scam Detection Model** | Hybrid ensemble: XGBoost classifier trained on EMSCAD + 50+ regex heuristic rules. |
| **Embedding Model** | `SentenceTransformer('all-MiniLM-L6-v2')` generating 384-dimensional dense vectors. |
| **Deduplication Method** | SHA-256 content fingerprinting on normalized title, company, and location. |
| **Resume Matching Formula** | Weighted score: Skills 40%, Title 20%, Experience 15%, Location 15%, Education 10%. |
| **Biggest Technical Achievement** | Building a fault-tolerant, 6-stage distributed streaming pipeline with zero data loss on service restart. |
