# Graph Report - Job Scrapping  (2026-08-30)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 1353 nodes · 2378 edges · 98 communities (89 shown, 9 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 68 edges (avg confidence: 0.93)
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
- get_mongo_client
- session.py
- jobs.py
- _NoopRedis
- routers/resume.py
- LLMRouter
- user.py
- KafkaConsumerClient
- search.py
- CompanyTrustAgent
- KafkaProducerClient
- estimator.py
- TestSalaryEstimatorRuleBased
- SalaryExtractionAgent
- SalaryEstimate
- Any
- logging.py
- Any
- BaseCollector
- feedback/main.py
- AuthenticityAgent
- models.py
- TestSalaryExtractionAgent
- setup_logging
- CollectorService
- notifier/main.py
- search/main.py
- verifier/main.py
- SkillExtractorPipeline
- company.py
- JobCard.jsx
- SalaryModel
- AnalyticsService
- .__init__
- RawJob
- test_pipeline.py
- TestBuildSalaryData
- TestSalaryEstimatorEngine
- AdzunaCollector
- embedder/main.py
- TestSalaryModel
- metrics.py
- cleaner/main.py
- CircuitBreaker
- resume_parser.py
- health_check
- models/resume.py
- datetime
- SalaryEstimator
- IndeedScraper
- env.py
- .test_experience_estimation
- _JsonFormatter
- NaukriScraper
- WorkdayCollector
- _build_salary_data
- ManualCollector
- salary_estimator/__init__.py
- scam_detector/__init__.py
- skill_extractor/__init__.py
- job-intelligence-platform

## God Nodes (most connected - your core abstractions)
1. `RawJob` - 37 edges
2. `KafkaConsumerClient` - 34 edges
3. `get_mongo_client()` - 34 edges
4. `KafkaProducerClient` - 29 edges
5. `BaseCollector` - 24 edges
6. `SalaryExtractionAgent` - 23 edges
7. `SalaryEstimator` - 21 edges
8. `ScamDetectionAgent` - 20 edges
9. `CollectionSource` - 18 edges
10. `OrchestratorService` - 18 edges

## Surprising Connections (you probably didn't know these)
- `AdzunaCollector` --uses--> `CollectionSource`  [INFERRED]
  services/collector/agents.py → shared/models/job.py
- `BaseCollector` --uses--> `CollectionSource`  [INFERRED]
  services/collector/agents.py → shared/models/job.py
- `CompanyCareersCollector` --uses--> `CollectionSource`  [INFERRED]
  services/collector/agents.py → shared/models/job.py
- `get_all_sources()` --uses--> `CollectionSource`  [INFERRED]
  services/collector/agents.py → shared/models/job.py
- `GovernmentJobsCollector` --uses--> `CollectionSource`  [INFERRED]
  services/collector/agents.py → shared/models/job.py

## Import Cycles
- None detected.

## Communities (98 total, 9 thin omitted)

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
Cohesion: 0.09
Nodes (43): HTTPAuthorizationCredentials, create_access_token(), create_refresh_token(), _decode_token(), get_current_user(), get_optional_user(), Any, FastAPI dependency injectors — auth, database, and permission guards. (+35 more)

### Community 4 - "extract_features"
Cohesion: 0.07
Nodes (22): Any, ml/scam_detector/model.py — Inference-only wrapper for the trained scam…, Vectorised batch prediction (much faster for large datasets)., Lightweight rule-based scam score when no model is available. Uses the same…, True if a trained ML model is in use., Inference wrapper around the trained XGBoost scam detector. Falls back…, Return scam probability (0.0 → legitimate, 1.0 → scam). Uses ML model when…, Return a human-readable label: 'scam' | 'suspicious' | 'legitimate'. (+14 more)

### Community 5 - "asyncio"
Cohesion: 0.07
Nodes (38): asyncio, fixture, create_topics(), main(), Kafka Topic Initializer — Creates all required topics before services start.…, Create all platform Kafka topics with proper configuration., auth_headers(), client() (+30 more)

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
Cohesion: 0.11
Nodes (31): admin_stats(), CollectionTrigger, deactivate_user(), get_pipeline_details(), get_scam_reports(), JobStatusUpdate, list_users(), Any (+23 more)

### Community 11 - "get_mongo_client"
Cohesion: 0.10
Nodes (17): main(), OrchestratorService, Orchestrator Service — Master workflow coordinator. High-throughput…, Choose collection limit based on backlog pressure., Send a collection trigger to Kafka., Detect jobs stuck in intermediate states and re-queue them., Run daily maintenance tasks., Mark published jobs older than 60 days as expired. (+9 more)

### Community 12 - "session.py"
Cohesion: 0.09
Nodes (23): middleware, add_process_time_header(), lifespan(), FastAPI, Request, FastAPI API Gateway — The single entry point for all external requests.…, Startup and shutdown events., Analytics router — job market trends, salary benchmarks, skill demand, company… (+15 more)

### Community 13 - "jobs.py"
Cohesion: 0.11
Nodes (27): delete_job(), _format_location(), get_job(), get_pipeline_status(), list_jobs(), Any, AsyncIOMotorDatabase, BackgroundTasks (+19 more)

### Community 14 - "_NoopRedis"
Cohesion: 0.09
Nodes (16): cache_delete(), cache_get(), cache_set(), close_redis(), get_redis_client(), _NoopRedis, Any, rate_limit_check() (+8 more)

### Community 15 - "routers/resume.py"
Cohesion: 0.11
Nodes (26): put, get_personalized_recommendations(), get_user_profile(), parse_resume_file(), parse_resume_text_endpoint(), Any, AsyncIOMotorDatabase, get (+18 more)

### Community 16 - "LLMRouter"
Cohesion: 0.13
Nodes (16): LLMProvider, LLMRouter, Any, Enum, str, LLM Router — Intelligently selects the optimal LLM for each task. Supports…, Return a ChatOllama client. Assumes availability was already confirmed., Return a ChatOpenAI client. Assumes availability was already confirmed. (+8 more)

### Community 17 - "user.py"
Cohesion: 0.14
Nodes (23): ApplicationRecord, Config, JobAlertFrequency, NotificationChannel, BaseModel, Enum, str, User, subscription, and preference models. (+15 more)

### Community 18 - "KafkaConsumerClient"
Cohesion: 0.12
Nodes (11): ConsumerRecord, DeduplicatorService, main(), Deduplicator Service — Duplicate Detection Agent. Consumes from Kafka topic:…, Duplicate Detection Agent — HIGH-THROUGHPUT BATCH MODE. Optimizations: - Batch…, KafkaConsumerClient, Any, Batch consumer for high-throughput processing. (+3 more)

### Community 19 - "search.py"
Cohesion: 0.18
Nodes (21): autocomplete(), _format_job_result(), _hybrid_search(), _mongodb_fts_search(), Any, AsyncIOMotorDatabase, BackgroundTasks, get (+13 more)

### Community 20 - "CompanyTrustAgent"
Cohesion: 0.13
Nodes (14): CompanyTrustAgent, CompanyTrustResult, Any, Company Trust Agent — scores companies based on web presence, employee data,…, Result of a company trust analysis., Analyze trust for multiple companies at once., Company Trust Scoring Agent. Assigns a trust score (0–100) to a company based…, Compute trust score for a company. Args: company_name: Raw company name from… (+6 more)

### Community 21 - "KafkaProducerClient"
Cohesion: 0.13
Nodes (8): EnrichmentService, Enrichment Agent (batch mode). - Extracts skills from title and description…, KafkaProducerClient, Any, Send a single message to a Kafka topic., Send messages in parallel batches with concurrency control. `messages` can be:…, Send failed message to dead-letter queue., Typed async Kafka producer with automatic serialization, error handling, dead-…

### Community 22 - "estimator.py"
Cohesion: 0.16
Nodes (15): _detect_company_type(), _detect_experience_level(), _detect_location_key(), _match_role(), Any, Salary Estimator — Rule-based + Gradient Boosting salary estimation pipeline.…, Detect experience level from text., Detect company type (FAANG, MNC, services, product, startup). (+7 more)

### Community 23 - "TestSalaryEstimatorRuleBased"
Cohesion: 0.11
Nodes (10): Unit tests for the ML SalaryEstimator (rule-based mode, no model file)., Senior Python developer in Bangalore should return a salary > 10 LPA median., Entry-level salary should be lower than senior for the same role., Google engineer should earn more than a generic engineer., Bengaluru should command a higher salary than no location., LLM + LangChain skills should add a premium over plain Python., Completely unknown title should still return a non-zero range., Without a trained model file the method should be 'rule_based'. (+2 more)

### Community 24 - "SalaryExtractionAgent"
Cohesion: 0.14
Nodes (10): Salary Extractor Agent — estimates salary ranges from job descriptions using…, Salary Extraction and Estimation Agent. Pipeline: 1. Rule-based regex…, SalaryExtractionAgent, Test salary extraction and normalization logic., ₹5L–10L PA should parse to min=500000, max=1000000, 5-10 LPA' should parse correctly, $50k-$80k' should parse to USD 50000-80000, None salary_raw should return None (+2 more)

### Community 25 - "SalaryEstimate"
Cohesion: 0.15
Nodes (9): Any, Extract salary from a raw salary string (e.g., '₹5L-10L PA')., Extract salary from the job description using regex patterns. Less reliable…, Estimate salary based on experience level when no explicit data is found.…, Salary estimation result., Full extraction pipeline with fallback chain., Apply regex patterns to extract salary range from text., Use LLM to extract salary information from job description. (+1 more)

### Community 26 - "Any"
Cohesion: 0.16
Nodes (18): clear_all_notifications(), delete_notification(), list_notifications(), mark_all_read(), mark_notification_read(), notification_stats(), Any, AsyncIOMotorDatabase (+10 more)

### Community 27 - "logging.py"
Cohesion: 0.16
Nodes (11): get_collector(), Job Collection Agents — Multi-source job aggregation. Sources: Adzuna API,…, main(), Collector Service — Orchestrates all job collection activities. High-throughput…, main(), Enrichment Service — Skill Extraction + Salary Estimation (BATCH MODE).…, Async Kafka consumer with automatic deserialization, consumer group management,…, _get_compression_type() (+3 more)

### Community 28 - "Any"
Cohesion: 0.21
Nodes (17): get_overview(), get_pipeline_stats(), get_remote_breakdown(), get_salary_benchmarks(), get_skill_demand(), get_top_companies(), get_trends(), Any (+9 more)

### Community 29 - "BaseCollector"
Cohesion: 0.15
Nodes (7): Response, BaseCollector, High-volume RSS/Atom feed aggregation (global + India-specific)., Abstract base for all job collectors with: - Per-source semaphore for…, Periodically rotate headers to avoid detection., Rate-limited HTTP GET with semaphore, circuit breaker, adaptive throttling., RSSFeedCollector

### Community 30 - "feedback/main.py"
Cohesion: 0.16
Nodes (8): FeedbackService, main(), Feedback Service — User Feedback Learning Agent. Collects user corrections and…, Process quality rating feedback (thumbs up/down on job quality)., Process a user correction (e.g., wrong skill extraction)., Feedback Learning Agent. - Collects user scam reports and job quality feedback…, Process a feedback event., Process a user scam report — update job & company scam counters.

### Community 31 - "AuthenticityAgent"
Cohesion: 0.17
Nodes (9): AuthenticityAgent, AuthenticityResult, Authenticity Agent — verifies job listings by checking company career pages and…, Score the apply URL for trustworthiness., Extract the base domain from a URL., Attempt to find the job on the company's official career page. Returns (found,…, Result of an authenticity check., Job Authenticity Verification Agent. Checks: 1. Whether the company has a… (+1 more)

### Community 32 - "models.py"
Cohesion: 0.22
Nodes (15): CollectionRun, Company, Job, MongoBaseModel, NotificationLog, PipelineEvent, BaseModel, Pydantic models — MongoDB database schema. Designed for unstructured data… (+7 more)

### Community 33 - "TestSalaryExtractionAgent"
Cohesion: 0.12
Nodes (3): parametrize, Test the salary extraction agent used in the enrichment pipeline., TestSalaryExtractionAgent

### Community 34 - "setup_logging"
Cohesion: 0.17
Nodes (13): main(), Analytics Service — Aggregates job market data and generates platform insights.…, health(), lifespan(), main(), FastAPI, get, Auth Service — Standalone JWT + OAuth2 authentication microservice. Handles… (+5 more)

### Community 35 - "CollectorService"
Cohesion: 0.17
Nodes (9): get_all_sources(), CollectorService, Any, Run collection on schedule (every 90 minutes by default)., Run ALL sources concurrently, then batch-publish to Kafka., Distribute total limit across sources using proportional weights., Master collection orchestrator — runs collectors concurrently and publishes…, Handle a collection trigger message. (+1 more)

### Community 36 - "notifier/main.py"
Cohesion: 0.17
Nodes (7): main(), NotifierService, Notifier Service — Smart Notification Agent. Consumes from Kafka topic:…, Check if a job matches a saved search's criteria., Determine which notification channels a user has configured., Simulate sending a notification via the specified channel., Notification Agent. - Listens for verified jobs - Matches jobs against user…

### Community 37 - "search/main.py"
Cohesion: 0.22
Nodes (14): _format_job(), health(), lifespan(), _mongodb_search(), Any, FastAPI, get, Search Service — Standalone hybrid search microservice. Wraps Qdrant vector… (+6 more)

### Community 38 - "verifier/main.py"
Cohesion: 0.16
Nodes (8): main(), Verifier Service — Scam Detection + Authenticity Verification (BATCH MODE).…, Verification Agent (batch mode). - Runs ScamDetectionAgent on each job…, Verify a single job. Returns (job_id, updated_msg, verification_update,…, VerifierService, Any, Check if a URL is active and reachable via HTTP HEAD/GET request. Returns dict…, verify_live_url()

### Community 39 - "SkillExtractorPipeline"
Cohesion: 0.16
Nodes (10): extract_skills_from_text(), _normalize(), Any, Skill Extractor — spaCy-based NER pipeline for extracting skills from job…, Extract skills from text. Returns: { skills: list of unique skill strings,…, Categorize a list of skill strings., Normalize skill text to canonical form., Simple function wrapper — returns list of unique extracted skills. (+2 more)

### Community 40 - "company.py"
Cohesion: 0.20
Nodes (13): Company, CompanySearchResult, CompanySize, CompanyTrustReport, CompanyVerificationStatus, Config, BaseModel, Enum (+5 more)

### Community 41 - "JobCard.jsx"
Cohesion: 0.22
Nodes (9): App(), MOCK_JOBS, EXP_LABELS, getCompanyColor(), getCompanyInitials(), JobCard(), REMOTE_LABELS, SCAM_RISK_CONFIG (+1 more)

### Community 42 - "SalaryModel"
Cohesion: 0.19
Nodes (6): Any, Predict salary for a list of job dicts (each with title, skills, etc.)., Return a human-readable salary range string., Thin inference wrapper around the trained GradientBoosting salary estimator.…, Predict salary range for a job. Returns a dict with both LPA and INR values: {…, SalaryModel

### Community 43 - "AnalyticsService"
Cohesion: 0.27
Nodes (4): AnalyticsService, Any, Analytics Agent. - Runs scheduled aggregation queries - Caches results in a…, Run all aggregation pipelines and cache results.

### Community 44 - ".__init__"
Cohesion: 0.15
Nodes (6): CompanyCareersCollector, GovernmentJobsCollector, LinkedInCollector, Seeds Indian government-style jobs (Sarkari Naukri) for public sector volume., Aggregates direct company career pages via structured seed + RSS fallback., LinkedIn Jobs — produces high-fidelity structured records via metadata.

### Community 45 - "RawJob"
Cohesion: 0.23
Nodes (6): GreenhouseCollector, LeverCollector, Greenhouse job board API — 50+ companies concurrently., Lever job board API — same style as Greenhouse, adds more volume., Job as collected from source — minimal validation, maximum preservation.…, RawJob

### Community 46 - "test_pipeline.py"
Cohesion: 0.19
Nodes (8): generate_fingerprint(), Generate a content-based fingerprint for similarity matching with normalized…, Unit tests for the CleanerService — field normalization, salary parsing,…, Test content fingerprinting for deduplication., Two identical jobs should produce the same fingerprint, Different jobs should produce different fingerprints, Fingerprinting should be case-insensitive, TestDeduplicator

### Community 47 - "TestBuildSalaryData"
Cohesion: 0.23
Nodes (7): Test the _build_salary_data enrichment helper logic., Return a mock SalaryEstimate-like object., High-confidence explicit result should not be overridden by ML., When SalaryExtractionAgent returns nothing, ML estimator should be used., A low-confidence salary estimate should be replaced by ML prediction., When both salary result and ML estimator are None, return unknown fallback., TestBuildSalaryData

### Community 48 - "TestSalaryEstimatorEngine"
Cohesion: 0.15
Nodes (3): Test the core rule-based estimation logic (no model file)., Even with many premium skills the bump should not exceed 8 LPA., TestSalaryEstimatorEngine

### Community 49 - "AdzunaCollector"
Cohesion: 0.23
Nodes (6): BaseException, AdzunaCollector, Any, Execute coro_fn with exponential backoff and optional circuit breaking., Adzuna Jobs API collector — concurrent per search term. Free tier: 250…, retry_with_backoff()

### Community 50 - "embedder/main.py"
Cohesion: 0.18
Nodes (6): EmbedderService, main(), Embedder Service — Vector Embedding Generator (BATCH MODE). Consumes from Kafka…, Embedding Generator Agent (batch mode). - Batched…, KafkaTopics, Kafka topic definitions — single source of truth for all topic names. Capacity-…

### Community 51 - "TestSalaryModel"
Cohesion: 0.17
Nodes (3): Unit tests for the Salary Extractor / Estimator stack: -…, Test the SalaryModel wrapper (no trained model file required)., TestSalaryModel

### Community 52 - "metrics.py"
Cohesion: 0.18
Nodes (10): increment(), observe(), Any, Prometheus metrics — optional, silently no-ops when prometheus_client not…, Observe a histogram/gauge value (no-op if metrics disabled)., Set a gauge metric value (no-op if metrics disabled)., Set up Prometheus metrics collection. If prometheus_client is not installed,…, Increment a counter metric (no-op if metrics disabled). (+2 more)

### Community 53 - "cleaner/main.py"
Cohesion: 0.25
Nodes (4): CleanerService, main(), Cleaner Service — Data Cleaning Agent. Consumes from Kafka topic: job.raw…, Data Cleaning Agent — HIGH-THROUGHPUT BATCH MODE. - Consumes batches from…

### Community 55 - "resume_parser.py"
Cohesion: 0.32
Nodes (7): _extract_docx(), _extract_pdf(), extract_resume_text(), Resume text extractor and candidate profile parser. Supports PDF (.pdf),…, Extract raw text from PDF, DOCX, or TXT file bytes., Extract text from PDF bytes using pdfminer., Extract paragraph text from Word DOCX bytes via zipfile XML parsing.

### Community 56 - "health_check"
Cohesion: 0.33
Nodes (7): health_check(), Any, get, Health check endpoint for load balancers and Kubernetes liveness probes.…, Kubernetes readiness probe., readiness_check(), root()

### Community 57 - "models/resume.py"
Cohesion: 0.43
Nodes (6): CandidateProfile, JobMatchExplanation, BaseModel, Resume & Candidate Profile Pydantic models for Job Intelligence Platform., RecommendedJobResult, SkillGapAnalysis

### Community 58 - "datetime"
Cohesion: 0.40
Nodes (5): datetime, make_sample_job(), Any, Seed script — populates the database with sample jobs for development/testing.…, seed()

### Community 59 - "SalaryEstimator"
Cohesion: 0.33
Nodes (4): Rule-based salary estimator for the Indian job market. Estimates salary range…, Train a gradient boosting salary estimator from labeled CSV data., SalaryEstimator, train()

### Community 61 - "env.py"
Cohesion: 0.33
Nodes (5): Alembic migrations env.py — MongoDB-aware no-op stub. The platform uses MongoDB…, Run placeholder migration in offline mode., Run placeholder migration in online mode., run_migrations_offline(), run_migrations_online()

### Community 62 - ".test_experience_estimation"
Cohesion: 0.40
Nodes (3): parametrize, Higher experience levels should always yield higher salaries., Experience-level estimation should return valid ranges

### Community 63 - "_JsonFormatter"
Cohesion: 0.50
Nodes (3): LogRecord, _JsonFormatter, Emit log records as single-line JSON objects.

### Community 67 - "_build_salary_data"
Cohesion: 0.50
Nodes (3): _build_salary_data(), Any, Enrich a single job. Returns (job_id, updated_message, enrichment_update,…

## Knowledge Gaps
- **11 isolated node(s):** `Config`, `Config`, `KafkaTopics`, `DEFAULT_SAMPLE_JOBS`, `state` (+6 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **9 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `get_mongo_client()` connect `get_mongo_client` to `setup_logging`, `notifier/main.py`, `search/main.py`, `verifier/main.py`, `health_check.py`, `AnalyticsService`, `session.py`, `test_pipeline.py`, `KafkaConsumerClient`, `embedder/main.py`, `cleaner/main.py`, `KafkaProducerClient`, `health_check`, `logging.py`, `feedback/main.py`?**
  _High betweenness centrality (0.065) - this node is a cross-community bridge._
- **Why does `SalaryEstimator` connect `SalaryEstimator` to `SalaryModel`, `test_pipeline.py`, `TestBuildSalaryData`, `TestSalaryEstimatorEngine`, `TestSalaryModel`, `KafkaProducerClient`, `estimator.py`, `TestSalaryEstimatorRuleBased`, `logging.py`?**
  _High betweenness centrality (0.057) - this node is a cross-community bridge._
- **Why does `SalaryExtractionAgent` connect `SalaryExtractionAgent` to `TestSalaryExtractionAgent`, `test_pipeline.py`, `TestSalaryModel`, `KafkaProducerClient`, `SalaryEstimate`, `logging.py`, `.test_experience_estimation`?**
  _High betweenness centrality (0.055) - this node is a cross-community bridge._
- **Are the 12 inferred relationships involving `RawJob` (e.g. with `AdzunaCollector` and `BaseCollector`) actually correct?**
  _`RawJob` has 12 INFERRED edges - model-reasoned connections that need verification._
- **Are the 8 inferred relationships involving `KafkaConsumerClient` (e.g. with `CleanerService` and `CollectorService`) actually correct?**
  _`KafkaConsumerClient` has 8 INFERRED edges - model-reasoned connections that need verification._
- **Are the 6 inferred relationships involving `KafkaProducerClient` (e.g. with `CleanerService` and `CollectorService`) actually correct?**
  _`KafkaProducerClient` has 6 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Config`, `Config`, `KafkaTopics` to the rest of the system?**
  _11 weakly-connected nodes found - possible documentation gaps or missing edges._