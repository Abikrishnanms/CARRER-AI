# Graph Report - Job Scrapping  (2026-08-30)

## Corpus Check
- 118 files · ~96,329 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1571 nodes · 2606 edges · 117 communities (102 shown, 15 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 71 edges (avg confidence: 0.93)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `77cf1c50`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- job.py
- jobboard/app.js
- parse_salary
- auth.py
- extract_features
- asyncio
- admin/app.js
- ScamDetectionAgent
- users.py
- health_check.py
- admin.py
- OrchestratorService
- datetime
- 🧠 TalentLens Platform — Deployment Runbook & Status Report
- _NoopRedis
- get_personalized_recommendations
- LLMRouter
- user.py
- KafkaConsumerClient
- search_jobs
- CompanyTrustAgent
- KafkaProducerClient
- SalaryEstimator
- TestSalaryEstimatorRuleBased
- SalaryExtractionAgent
- SalaryEstimate
- Any
- logging.py
- Any
- BaseCollector
- get_mongo_client
- AuthenticityAgent
- models.py
- TestSalaryExtractionAgent
- auth/main.py
- collector/main.py
- NotifierService
- search/main.py
- verifier/main.py
- pipeline.py
- company.py
- JobCard.jsx
- SalaryModel
- AnalyticsService
- .__init__
- RawJob
- generate_fingerprint
- test_pipeline.py
- TestSalaryEstimatorEngine
- AdzunaCollector
- TalentLens — Complete Project Report
- 🧠 TalentLens — AI-Powered Job Intelligence Platform
- metrics.py
- Project Overview — CARRER-AI (Talentlens branch)
- CircuitBreaker
- PROJECT_CODE_EXPLANATIONS.md
- health_check
- models/resume.py
- PROJECT_DOCUMENTATION_AND_INTERVIEW_GUIDE.md
- deps.py
- IndeedScraper
- env.py
- 13. Complete Interview Question & Answer Bank
- client.py
- app
- agents.py
- EnrichmentService
- 1. Project Overview
- salary_estimator/__init__.py
- scam_detector/__init__.py
- skill_extractor/__init__.py
- job-intelligence-platform
- In-Depth Technology Breakdown
- Detailed Pipeline Stages
- change_password
- get_me
- init_kafka_topics.py
- base.py
- 10. Technology Decision Justifications
- 14. "What If" Scenario Defense
- CompanyCareersCollector
- RSSFeedCollector
- RemotiveCollector
- 6. Database Schema & Data Models
- 8. Security Implementation
- rules/graphify.md
- workflows/graphify.md
- collector_main.inline.md
- deduplicator_main.inline.md
- embedder_main.inline.md
- services_gateway_annotated.md

## God Nodes (most connected - your core abstractions)
1. `RawJob` - 41 edges
2. `get_mongo_client()` - 34 edges
3. `KafkaConsumerClient` - 34 edges
4. `KafkaProducerClient` - 29 edges
5. `BaseCollector` - 27 edges
6. `SalaryExtractionAgent` - 23 edges
7. `SalaryEstimator` - 22 edges
8. `ScamDetectionAgent` - 20 edges
9. `CollectionSource` - 20 edges
10. `OrchestratorService` - 18 edges

## Surprising Connections (you probably didn't know these)
- `EnrichmentService` --uses--> `SalaryEstimator`  [INFERRED]
  services/enrichment/main.py → ml/salary_estimator/estimator.py
- `TestBuildSalaryData` --uses--> `SalaryEstimator`  [INFERRED]
  tests/unit/test_pipeline.py → ml/salary_estimator/estimator.py
- `TestSalaryEstimatorRuleBased` --uses--> `SalaryEstimator`  [INFERRED]
  tests/unit/test_pipeline.py → ml/salary_estimator/estimator.py
- `TestSalaryEstimatorEngine` --uses--> `SalaryEstimator`  [INFERRED]
  tests/unit/test_salary_extractor.py → ml/salary_estimator/estimator.py
- `main()` --indirect_call--> `app()`  [INFERRED]
  services/auth/main.py → tests/integration/test_api.py

## Import Cycles
- None detected.

## Communities (117 total, 15 thin omitted)

### Community 0 - "job.py"
Cohesion: 0.05
Nodes (54): model_validator, Skill Extraction Agent — NLP-powered skill extraction from job descriptions.…, Skill Extraction Agent using multi-layer approach: 1. Taxonomy matching (fast,…, Load spaCy model if available., Extract skills from job title and description. Returns deduplicated, normalized…, Fast taxonomy-based skill extraction using regex., Extract entities using spaCy NER., Use LLM to extract skills not found by taxonomy. (+46 more)

### Community 1 - "jobboard/app.js"
Cohesion: 0.07
Nodes (56): animateAllRings(), animateCounter(), animateProgressBar(), apiGet(), apiPost(), authHeader(), buildJobCard(), clearFilters() (+48 more)

### Community 2 - "parse_salary"
Cohesion: 0.06
Nodes (26): detect_job_type(), detect_remote_type(), normalize_job_type(), normalize_location(), parse_salary(), Any, Normalize job type strings., Detect job type from arbitrary text (title, description, etc.) Returns… (+18 more)

### Community 3 - "auth.py"
Cohesion: 0.20
Nodes (21): create_access_token(), create_refresh_token(), Create a JWT access token., Create a longer-lived JWT refresh token., BootstrapAdminRequest, create_first_admin(), login(), LoginRequest (+13 more)

### Community 4 - "extract_features"
Cohesion: 0.07
Nodes (22): Any, ml/scam_detector/model.py — Inference-only wrapper for the trained scam…, Vectorised batch prediction (much faster for large datasets)., Lightweight rule-based scam score when no model is available. Uses the same…, True if a trained ML model is in use., Inference wrapper around the trained XGBoost scam detector. Falls back…, Return scam probability (0.0 → legitimate, 1.0 → scam). Uses ML model when…, Return a human-readable label: 'scam' | 'suspicious' | 'legitimate'. (+14 more)

### Community 5 - "asyncio"
Cohesion: 0.10
Nodes (28): asyncio, Integration tests for the gateway API endpoints. Requires a running MongoDB…, Authenticated /auth/me should return user info., Unauthenticated /auth/me should return 401., Jobs listing endpoint should return paginated results., Search endpoint should return results matching query., Filter by remote type should work., Analytics overview should return platform stats. (+20 more)

### Community 6 - "admin/app.js"
Cohesion: 0.14
Nodes (36): authHeaders(), checkApiStatus(), deactivateUser(), del(), doLogin(), esc(), fmt(), formatDate() (+28 more)

### Community 7 - "ScamDetectionAgent"
Cohesion: 0.09
Nodes (17): Scam Detection Agent — ML + rule-based ensemble for fraud detection. Uses…, Result of scam analysis., Scam Detection Agent with three detection layers: 1. Rule-based engine (YAML…, Load XGBoost model if available., Analyze a job for scam indicators. Returns probability 0.0 (safe) to 1.0…, Apply all scam detection rules and build positive trust vs warning reasons., Run ML model inference., Extract numerical features for ML model. (+9 more)

### Community 8 - "users.py"
Cohesion: 0.12
Nodes (33): create_saved_search(), deactivate_account(), delete_saved_search(), get_application_history(), get_preferences(), get_profile(), list_saved_searches(), NotificationPreferences (+25 more)

### Community 9 - "health_check.py"
Cohesion: 0.09
Nodes (31): AsyncIOMotorClient, Namespace, check_minio(), check_mongodb(), check_qdrant(), check_redis(), check_service(), main() (+23 more)

### Community 10 - "admin.py"
Cohesion: 0.06
Nodes (60): FastAPI dependency: require the current user to have the 'admin' role., require_admin(), admin_stats(), CollectionTrigger, deactivate_user(), get_pipeline_details(), get_scam_reports(), JobStatusUpdate (+52 more)

### Community 11 - "OrchestratorService"
Cohesion: 0.12
Nodes (11): OrchestratorService, Choose collection limit based on backlog pressure., Send a collection trigger to Kafka., Detect jobs stuck in intermediate states and re-queue them., Run daily maintenance tasks., Mark published jobs older than 60 days as expired., Expire old deduplication keys in Redis (>7 days)., Periodically log pipeline throughput stats for observability. (+3 more)

### Community 12 - "datetime"
Cohesion: 0.12
Nodes (22): datetime, middleware, add_process_time_header(), lifespan(), FastAPI, Request, FastAPI API Gateway — The single entry point for all external requests.…, Startup and shutdown events. (+14 more)

### Community 13 - "🧠 TalentLens Platform — Deployment Runbook & Status Report"
Cohesion: 0.05
Nodes (41): 🔁 Block 1: Start Docker Infrastructure, 🔁 Block 2: Start 10 Python Microservices, 🔁 Block 3: Start Job Board + Admin Frontend UIs, 🔁 Block 4: Quick Health Check, 🔧 Bugs Fixed During Initial Deployment, 📋 Contents, 🌟 Core User-Facing, 🐳 Docker Infrastructure (11/11 Running) (+33 more)

### Community 14 - "_NoopRedis"
Cohesion: 0.15
Nodes (3): _NoopRedis, Any, No-op Redis stub when redis package is not installed.

### Community 15 - "get_personalized_recommendations"
Cohesion: 0.08
Nodes (32): put, get_personalized_recommendations(), get_user_profile(), parse_resume_file(), parse_resume_text_endpoint(), Any, AsyncIOMotorDatabase, get (+24 more)

### Community 16 - "LLMRouter"
Cohesion: 0.13
Nodes (16): LLMProvider, LLMRouter, Any, Enum, str, LLM Router — Intelligently selects the optimal LLM for each task. Supports…, Return a ChatOllama client. Assumes availability was already confirmed., Return a ChatOpenAI client. Assumes availability was already confirmed. (+8 more)

### Community 17 - "user.py"
Cohesion: 0.14
Nodes (23): ApplicationRecord, Config, JobAlertFrequency, NotificationChannel, BaseModel, Enum, str, User, subscription, and preference models. (+15 more)

### Community 18 - "KafkaConsumerClient"
Cohesion: 0.12
Nodes (11): ConsumerRecord, CleanerService, main(), Cleaner Service — Data Cleaning Agent. Consumes from Kafka topic: job.raw…, Data Cleaning Agent — HIGH-THROUGHPUT BATCH MODE. - Consumes batches from…, KafkaConsumerClient, Any, Batch consumer for high-throughput processing. (+3 more)

### Community 19 - "search_jobs"
Cohesion: 0.17
Nodes (20): autocomplete(), _format_job_result(), _hybrid_search(), _mongodb_fts_search(), Any, AsyncIOMotorDatabase, BackgroundTasks, get (+12 more)

### Community 20 - "CompanyTrustAgent"
Cohesion: 0.14
Nodes (13): CompanyTrustAgent, CompanyTrustResult, Any, Result of a company trust analysis., Analyze trust for multiple companies at once., Company Trust Scoring Agent. Assigns a trust score (0–100) to a company based…, Compute trust score for a company. Args: company_name: Raw company name from…, Very short company name (<3 chars) should deduct 20 points → score below… (+5 more)

### Community 21 - "KafkaProducerClient"
Cohesion: 0.10
Nodes (13): DeduplicatorService, main(), Deduplicator Service — Duplicate Detection Agent. Consumes from Kafka topic:…, Duplicate Detection Agent — HIGH-THROUGHPUT BATCH MODE. Optimizations: - Batch…, _get_compression_type(), KafkaProducerClient, Any, Kafka producer and consumer abstractions with typed events. Uses aiokafka for… (+5 more)

### Community 22 - "SalaryEstimator"
Cohesion: 0.12
Nodes (20): _detect_company_type(), _detect_experience_level(), _detect_location_key(), _match_role(), Any, Salary Estimator — Rule-based + Gradient Boosting salary estimation pipeline.…, Detect experience level from text., Detect company type (FAANG, MNC, services, product, startup). (+12 more)

### Community 23 - "TestSalaryEstimatorRuleBased"
Cohesion: 0.09
Nodes (12): parametrize, Unit tests for the ML SalaryEstimator (rule-based mode, no model file)., Senior Python developer in Bangalore should return a salary > 10 LPA median., Entry-level salary should be lower than senior for the same role., Google engineer should earn more than a generic engineer., Bengaluru should command a higher salary than no location., LLM + LangChain skills should add a premium over plain Python., Completely unknown title should still return a non-zero range. (+4 more)

### Community 24 - "SalaryExtractionAgent"
Cohesion: 0.15
Nodes (10): Salary Extraction and Estimation Agent. Pipeline: 1. Rule-based regex…, SalaryExtractionAgent, Test salary extraction and normalization logic., ₹5L–10L PA should parse to min=500000, max=1000000, 5-10 LPA' should parse correctly, $50k-$80k' should parse to USD 50000-80000, None salary_raw should return None, Garbage salary string should return None (+2 more)

### Community 25 - "SalaryEstimate"
Cohesion: 0.13
Nodes (10): Any, Salary Extractor Agent — estimates salary ranges from job descriptions using…, Extract salary from a raw salary string (e.g., '₹5L-10L PA')., Extract salary from the job description using regex patterns. Less reliable…, Estimate salary based on experience level when no explicit data is found.…, Salary estimation result., Full extraction pipeline with fallback chain., Apply regex patterns to extract salary range from text. (+2 more)

### Community 26 - "Any"
Cohesion: 0.16
Nodes (18): clear_all_notifications(), delete_notification(), list_notifications(), mark_all_read(), mark_notification_read(), notification_stats(), Any, AsyncIOMotorDatabase (+10 more)

### Community 27 - "logging.py"
Cohesion: 0.10
Nodes (19): LogRecord, main(), Analytics Service — Aggregates job market data and generates platform insights.…, Enrichment Service — Skill Extraction + Salary Estimation (BATCH MODE).…, main(), Feedback Service — User Feedback Learning Agent. Collects user corrections and…, Notifier Service — Smart Notification Agent. Consumes from Kafka topic:…, main() (+11 more)

### Community 28 - "Any"
Cohesion: 0.21
Nodes (17): get_overview(), get_pipeline_stats(), get_remote_breakdown(), get_salary_benchmarks(), get_skill_demand(), get_top_companies(), get_trends(), Any (+9 more)

### Community 29 - "BaseCollector"
Cohesion: 0.15
Nodes (8): Response, ArbeitnowCollector, BaseCollector, Arbeitnow job board API (remote and European jobs, no auth required)., Abstract base for all job collectors with: - Per-source semaphore for…, Periodically rotate headers to avoid detection., Rate-limited HTTP GET with semaphore, circuit breaker, adaptive throttling., Rate-limited HTTP POST with semaphore, circuit breaker, adaptive throttling.

### Community 30 - "get_mongo_client"
Cohesion: 0.09
Nodes (14): EmbedderService, main(), Embedder Service — Vector Embedding Generator (BATCH MODE). Consumes from Kafka…, Embedding Generator Agent (batch mode). - Batched…, FeedbackService, Process quality rating feedback (thumbs up/down on job quality)., Process a user correction (e.g., wrong skill extraction)., Feedback Learning Agent. - Collects user scam reports and job quality feedback… (+6 more)

### Community 31 - "AuthenticityAgent"
Cohesion: 0.19
Nodes (8): AuthenticityAgent, AuthenticityResult, Score the apply URL for trustworthiness., Extract the base domain from a URL., Attempt to find the job on the company's official career page. Returns (found,…, Result of an authenticity check., Job Authenticity Verification Agent. Checks: 1. Whether the company has a…, Run the full authenticity check pipeline. Returns an AuthenticityResult with…

### Community 32 - "models.py"
Cohesion: 0.22
Nodes (15): CollectionRun, Company, Job, MongoBaseModel, NotificationLog, PipelineEvent, BaseModel, Pydantic models — MongoDB database schema. Designed for unstructured data… (+7 more)

### Community 33 - "TestSalaryExtractionAgent"
Cohesion: 0.12
Nodes (3): parametrize, Test the salary extraction agent used in the enrichment pipeline., TestSalaryExtractionAgent

### Community 34 - "auth/main.py"
Cohesion: 0.33
Nodes (6): health(), lifespan(), main(), FastAPI, get, Auth Service — Standalone JWT + OAuth2 authentication microservice. Handles…

### Community 35 - "collector/main.py"
Cohesion: 0.17
Nodes (11): get_all_sources(), CollectorService, main(), Any, Collector Service — Orchestrates all job collection activities. High-throughput…, Handle a collection trigger message., Run collection on schedule (every 90 minutes by default)., Run ALL sources concurrently, then batch-publish to Kafka. (+3 more)

### Community 36 - "NotifierService"
Cohesion: 0.19
Nodes (6): main(), NotifierService, Check if a job matches a saved search's criteria., Determine which notification channels a user has configured., Simulate sending a notification via the specified channel., Notification Agent. - Listens for verified jobs - Matches jobs against user…

### Community 37 - "search/main.py"
Cohesion: 0.22
Nodes (14): _format_job(), health(), lifespan(), _mongodb_search(), Any, FastAPI, get, Search Service — Standalone hybrid search microservice. Wraps Qdrant vector… (+6 more)

### Community 38 - "verifier/main.py"
Cohesion: 0.16
Nodes (8): main(), Verifier Service — Scam Detection + Authenticity Verification (BATCH MODE).…, Verification Agent (batch mode). - Runs ScamDetectionAgent on each job…, Verify a single job. Returns (job_id, updated_msg, verification_update,…, VerifierService, Any, Check if a URL is active and reachable via HTTP HEAD/GET request. Returns dict…, verify_live_url()

### Community 39 - "pipeline.py"
Cohesion: 0.16
Nodes (11): _cached_extract_skills(), extract_skills_from_text(), _normalize(), Any, Skill Extractor — spaCy-based NER pipeline for extracting skills from job…, Extract skills from text. Returns: { skills: list of unique skill strings,…, Categorize a list of skill strings., Normalize skill text to canonical form (O(1) lookup). (+3 more)

### Community 40 - "company.py"
Cohesion: 0.20
Nodes (13): Company, CompanySearchResult, CompanySize, CompanyTrustReport, CompanyVerificationStatus, Config, BaseModel, Enum (+5 more)

### Community 41 - "JobCard.jsx"
Cohesion: 0.22
Nodes (9): App(), MOCK_JOBS, EXP_LABELS, getCompanyColor(), getCompanyInitials(), JobCard(), REMOTE_LABELS, SCAM_RISK_CONFIG (+1 more)

### Community 42 - "SalaryModel"
Cohesion: 0.10
Nodes (9): Any, Predict salary for a list of job dicts (each with title, skills, etc.)., Return a human-readable salary range string., Thin inference wrapper around the trained GradientBoosting salary estimator.…, Predict salary range for a job. Returns a dict with both LPA and INR values: {…, SalaryModel, Unit tests for the Salary Extractor / Estimator stack: -…, Test the SalaryModel wrapper (no trained model file required). (+1 more)

### Community 43 - "AnalyticsService"
Cohesion: 0.27
Nodes (4): AnalyticsService, Any, Analytics Agent. - Runs scheduled aggregation queries - Caches results in a…, Run all aggregation pipelines and cache results.

### Community 44 - ".__init__"
Cohesion: 0.14
Nodes (6): GovernmentJobsCollector, LinkedInCollector, NaukriScraper, LinkedIn Jobs — scrapes live public job postings via guest API., Aggregates authentic Indian public sector job postings from live government RSS…, Naukri.com India — scrapes live Naukri Search API & Tech feeds.

### Community 45 - "RawJob"
Cohesion: 0.26
Nodes (6): GreenhouseCollector, LeverCollector, Greenhouse job board API — 50+ companies concurrently., Lever job board API — same style as Greenhouse, adds more volume., Job as collected from source — minimal validation, maximum preservation.…, RawJob

### Community 46 - "generate_fingerprint"
Cohesion: 0.22
Nodes (7): generate_fingerprint(), Generate a content-based fingerprint for similarity matching with normalized…, Test content fingerprinting for deduplication., Two identical jobs should produce the same fingerprint, Different jobs should produce different fingerprints, Fingerprinting should be case-insensitive, TestDeduplicator

### Community 47 - "test_pipeline.py"
Cohesion: 0.17
Nodes (10): _build_salary_data(), Any, Unit tests for the CleanerService — field normalization, salary parsing,…, Test the _build_salary_data enrichment helper logic., Return a mock SalaryEstimate-like object., High-confidence explicit result should not be overridden by ML., When SalaryExtractionAgent returns nothing, ML estimator should be used., A low-confidence salary estimate should be replaced by ML prediction. (+2 more)

### Community 48 - "TestSalaryEstimatorEngine"
Cohesion: 0.15
Nodes (3): Test the core rule-based estimation logic (no model file)., Even with many premium skills the bump should not exceed 8 LPA., TestSalaryEstimatorEngine

### Community 49 - "AdzunaCollector"
Cohesion: 0.21
Nodes (6): BaseException, AdzunaCollector, Any, Execute coro_fn with exponential backoff and optional circuit breaking., Adzuna Jobs API collector — concurrent per search term. Free tier: 250…, retry_with_backoff()

### Community 50 - "TalentLens — Complete Project Report"
Cohesion: 0.06
Nodes (35): 10. Service URLs After Startup, 11. Running Tests, 12. Key Configuration (`.env`), 13. Training ML Models, 14. Bugs Fixed During Development, 15. Kubernetes Deployment (Production), 1. What Is TalentLens?, 2. Architecture Overview (+27 more)

### Community 51 - "🧠 TalentLens — AI-Powered Job Intelligence Platform"
Cohesion: 0.08
Nodes (24): 1. Clone & configure, 2. Start everything (Windows), 3. Check service health, 🏗️ Architecture, Build a single service, 🤝 Contributing, 🔧 Development, Development (all services) (+16 more)

### Community 52 - "metrics.py"
Cohesion: 0.18
Nodes (10): increment(), observe(), Any, Prometheus metrics — optional, silently no-ops when prometheus_client not…, Observe a histogram/gauge value (no-op if metrics disabled)., Set a gauge metric value (no-op if metrics disabled)., Set up Prometheus metrics collection. If prometheus_client is not installed,…, Increment a counter metric (no-op if metrics disabled). (+2 more)

### Community 53 - "Project Overview — CARRER-AI (Talentlens branch)"
Cohesion: 0.12
Nodes (15): Code conventions and best practices used in this repo, Communication & data contracts, Developer setup (quick start), High-level architecture and dataflow, How code is organized and typical patterns, How to add a new service, Key files and entry points, ML components (+7 more)

### Community 55 - "PROJECT_CODE_EXPLANATIONS.md"
Cohesion: 0.14
Nodes (3): Batch 2 — Collector agents, Kafka clients, Line-by-line explanations (core files), Project Code Explanations — Core files

### Community 56 - "health_check"
Cohesion: 0.33
Nodes (7): health_check(), Any, get, Health check endpoint for load balancers and Kubernetes liveness probes.…, Kubernetes readiness probe., readiness_check(), root()

### Community 57 - "models/resume.py"
Cohesion: 0.43
Nodes (6): CandidateProfile, JobMatchExplanation, BaseModel, Resume & Candidate Profile Pydantic models for Job Intelligence Platform., RecommendedJobResult, SkillGapAnalysis

### Community 58 - "PROJECT_DOCUMENTATION_AND_INTERVIEW_GUIDE.md"
Cohesion: 0.15
Nodes (12): 11. Project Limitations & Critical Review, 12. Future Improvement Roadmap, 15. 5-Minute Technical Viva / Presentation Script, 16. Technical Interview Quick Cheat Sheet, 3. System Architecture & Component Interaction, 5. Resume Upload, Parsing & Multi-Factor Matching Algorithm, 7. Complete API Design & Endpoints, 9. Performance, Scalability & Bottleneck Analysis (+4 more)

### Community 59 - "deps.py"
Cohesion: 0.27
Nodes (11): HTTPAuthorizationCredentials, _decode_token(), get_current_user(), get_optional_user(), Any, FastAPI dependency injectors — auth, database, and permission guards., Decode and validate a JWT access token., FastAPI dependency: extract and validate the JWT bearer token. Returns the… (+3 more)

### Community 61 - "env.py"
Cohesion: 0.33
Nodes (5): Alembic migrations env.py — MongoDB-aware no-op stub. The platform uses MongoDB…, Run placeholder migration in offline mode., Run placeholder migration in online mode., run_migrations_offline(), run_migrations_online()

### Community 62 - "13. Complete Interview Question & Answer Bank"
Cohesion: 0.17
Nodes (12): 13. Complete Interview Question & Answer Bank, A. Project Overview & Architecture Questions, B. Fraud Detection & Machine Learning Questions, C. Deduplication & Vector Search Questions, D. Resume Parsing & Recommender Questions, Q1: "Can you describe your project in 60 seconds?", Q2: "Why did you design the backend as an event-driven pipeline rather than a monolith?", Q3: "How does your Scam Detection Agent work?" (+4 more)

### Community 63 - "client.py"
Cohesion: 0.17
Nodes (11): cache_delete(), cache_get(), cache_set(), close_redis(), rate_limit_check(), Redis client — async Redis connection with connection pooling and helpers., Delete a cached value., Simple sliding-window rate limiter. Returns (is_allowed, current_count). (+3 more)

### Community 65 - "app"
Cohesion: 0.22
Nodes (9): fixture, main(), app(), auth_headers(), client(), event_loop(), Create the FastAPI application for testing., Create an async test client. (+1 more)

### Community 66 - "agents.py"
Cohesion: 0.20
Nodes (6): get_collector(), ManualCollector, Job Collection Agents — Multi-source job aggregation. Sources: Adzuna API,…, Placeholder collector: manual uploads go through Gateway CRUD, not Kafka seeds., Workday ATS API — scrapes real job postings from enterprise Workday portals., WorkdayCollector

### Community 67 - "EnrichmentService"
Cohesion: 0.25
Nodes (4): EnrichmentService, main(), Enrichment Agent (batch mode). - Extracts skills from title and description…, Enrich a single job. Returns (job_id, updated_message, enrichment_update,…

### Community 68 - "1. Project Overview"
Cohesion: 0.22
Nodes (9): 1. Project Overview, 1. What real-world problem does the project solve?, 2. Who experiences this problem?, 3. Limitations of Existing Solutions, Key Features Implemented, One-Line Description, Problem Statement, Project Name (+1 more)

### Community 98 - "In-Depth Technology Breakdown"
Cohesion: 0.25
Nodes (8): 1. FastAPI & Python 3.12 (AsyncIO), 2. Complete Technology Stack & Justification, 2. MongoDB 7.0 (via Motor Async Driver), 3. Redpanda (Kafka-Compatible Streaming Broker), 4. Qdrant Vector Database, 5. SentenceTransformers (`all-MiniLM-L6-v2`), 6. XGBoost + Heuristic Rule Ensemble, In-Depth Technology Breakdown

### Community 99 - "Detailed Pipeline Stages"
Cohesion: 0.25
Nodes (8): 4. End-to-End Data Pipeline Flow, Detailed Pipeline Stages, Stage 1: Ingestion / Collection, Stage 2: Data Cleaning & Normalization, Stage 3: Deduplication & Fingerprinting, Stage 4: Enrichment & Skill Extraction, Stage 5: Fraud Verification & Trust Scoring, Stage 6: Vector Embedding Generation

### Community 100 - "change_password"
Cohesion: 0.33
Nodes (6): change_password(), _hash_password(), Change current user's password., Hash password using bcrypt., Verify bcrypt hashed password., _verify_password()

### Community 101 - "get_me"
Cohesion: 0.33
Nodes (6): get_me(), logout(), Any, get, Logout the current user by blacklisting their JWT token., Get current user info from token.

### Community 102 - "init_kafka_topics.py"
Cohesion: 0.50
Nodes (4): create_topics(), main(), Kafka Topic Initializer — Creates all required topics before services start.…, Create all platform Kafka topics with proper configuration.

### Community 103 - "base.py"
Cohesion: 0.40
Nodes (4): drop_all_collections(), Any, MongoDB collection schema definitions and index configuration. Centralizes all…, Drop all platform collections — USE WITH EXTREME CAUTION (testing only).

### Community 104 - "10. Technology Decision Justifications"
Cohesion: 0.50
Nodes (4): 10. Technology Decision Justifications, 1. Why FastAPI instead of Django or Flask?, 2. Why MongoDB instead of PostgreSQL?, 3. Why Redpanda / Kafka instead of synchronous processing?

### Community 105 - "14. "What If" Scenario Defense"
Cohesion: 0.50
Nodes (4): 14. "What If" Scenario Defense, Scenario 1: "What if the scraper gets blocked by target job boards with HTTP 429 / 403?", Scenario 2: "What if a user uploads a malicious or corrupt PDF file?", Scenario 3: "What if the primary MongoDB database goes down?"

### Community 109 - "6. Database Schema & Data Models"
Cohesion: 0.67
Nodes (3): 6. Database Schema & Data Models, Core Collections & Fields, Essential Database Indexes

### Community 110 - "8. Security Implementation"
Cohesion: 0.67
Nodes (3): 8. Security Implementation, Implemented Security Features, Recommended Future Security Enhancements

## Knowledge Gaps
- **160 isolated node(s):** `state`, `DEFAULT_SAMPLE_JOBS`, `state`, `MOCK_JOBS`, `REMOTE_LABELS` (+155 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **15 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `SalaryEstimator` connect `SalaryEstimator` to `EnrichmentService`, `SalaryModel`, `test_pipeline.py`, `TestSalaryEstimatorEngine`, `TestSalaryEstimatorRuleBased`, `logging.py`?**
  _High betweenness centrality (0.068) - this node is a cross-community bridge._
- **Why does `SalaryExtractionAgent` connect `SalaryExtractionAgent` to `TestSalaryExtractionAgent`, `EnrichmentService`, `SalaryModel`, `test_pipeline.py`, `SalaryEstimate`, `logging.py`?**
  _High betweenness centrality (0.055) - this node is a cross-community bridge._
- **Why does `get_mongo_client()` connect `get_mongo_client` to `EnrichmentService`, `NotifierService`, `search/main.py`, `verifier/main.py`, `health_check.py`, `AnalyticsService`, `datetime`, `OrchestratorService`, `generate_fingerprint`, `KafkaConsumerClient`, `KafkaProducerClient`, `health_check`, `logging.py`?**
  _High betweenness centrality (0.033) - this node is a cross-community bridge._
- **Are the 14 inferred relationships involving `RawJob` (e.g. with `AdzunaCollector` and `ArbeitnowCollector`) actually correct?**
  _`RawJob` has 14 INFERRED edges - model-reasoned connections that need verification._
- **Are the 8 inferred relationships involving `KafkaConsumerClient` (e.g. with `CleanerService` and `CollectorService`) actually correct?**
  _`KafkaConsumerClient` has 8 INFERRED edges - model-reasoned connections that need verification._
- **What connects `state`, `DEFAULT_SAMPLE_JOBS`, `state` to the rest of the system?**
  _160 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `job.py` be split into smaller, more focused modules?**
  _Cohesion score 0.052464947987336044 - nodes in this community are weakly interconnected._