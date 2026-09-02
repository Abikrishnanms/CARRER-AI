"""
Shared Pydantic models for the Job Intelligence Platform.
These models flow through the entire pipeline: Raw → Cleaned → Enriched → Verified.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator


# ─── Enumerations ─────────────────────────────────────────────────────────────


class JobType(str, Enum):
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    FREELANCE = "freelance"
    INTERNSHIP = "internship"
    TEMPORARY = "temporary"
    VOLUNTEER = "volunteer"
    UNKNOWN = "unknown"


class RemoteType(str, Enum):
    REMOTE = "remote"
    HYBRID = "hybrid"
    ON_SITE = "on_site"
    UNKNOWN = "unknown"


class ExperienceLevel(str, Enum):
    ENTRY = "entry"          # 0-2 years
    MID = "mid"              # 2-5 years
    SENIOR = "senior"        # 5-10 years
    LEAD = "lead"            # 8+ years
    EXECUTIVE = "executive"  # C-level
    UNKNOWN = "unknown"


class JobStatus(str, Enum):
    RAW = "raw"
    CLEANED = "cleaned"
    DEDUPLICATED = "deduplicated"
    ENRICHED = "enriched"
    VERIFIED = "verified"
    PUBLISHED = "published"
    EXPIRED = "expired"
    REJECTED = "rejected"   # Scam or failed verification


class CollectionSource(str, Enum):
    ADZUNA = "adzuna"
    GREENHOUSE = "greenhouse"
    LEVER = "lever"
    WORKDAY = "workday"
    INDEED = "indeed"
    NAUKRI = "naukri"
    LINKEDIN = "linkedin"
    RSS = "rss"
    COMPANY_CAREERS = "company_careers"
    GOVERNMENT = "government"
    REMOTIVE = "remotive"
    ARBEITNOW = "arbeitnow"
    MANUAL = "manual"
    UNKNOWN = "unknown"


class SkillCategory(str, Enum):
    TECHNICAL = "technical"       # Python, SQL, AWS
    SOFT = "soft"                  # Communication, leadership
    DOMAIN = "domain"              # Finance, healthcare
    TOOL = "tool"                  # Jira, Figma, VS Code
    LANGUAGE = "language"          # English, Hindi (spoken)
    CERTIFICATION = "certification" # AWS Certified, PMP


class ScamRisk(str, Enum):
    VERY_LOW = "very_low"      # 0-20%
    LOW = "low"                 # 20-40%
    MEDIUM = "medium"           # 40-60%
    HIGH = "high"               # 60-80%
    VERY_HIGH = "very_high"     # 80-100%


# ─── Component Models ─────────────────────────────────────────────────────────


class SalaryRange(BaseModel):
    """Salary information with currency and period."""
    min_value: float | None = None
    max_value: float | None = None
    currency: str = "INR"
    period: str = "yearly"  # yearly, monthly, hourly, daily
    is_estimated: bool = False
    confidence: float = 0.0

    @model_validator(mode="after")
    def validate_salary(self) -> SalaryRange:
        if self.min_value and self.max_value and self.min_value > self.max_value:
            self.min_value, self.max_value = self.max_value, self.min_value
        return self

    @property
    def midpoint(self) -> float | None:
        if self.min_value and self.max_value:
            return (self.min_value + self.max_value) / 2
        return self.min_value or self.max_value


class Skill(BaseModel):
    """An extracted skill with metadata."""
    name: str
    normalized_name: str
    category: SkillCategory = SkillCategory.TECHNICAL
    level_required: ExperienceLevel = ExperienceLevel.UNKNOWN
    is_required: bool = True  # False = nice-to-have
    confidence: float = 1.0
    source: str = "extraction"  # extraction, llm, manual


class Location(BaseModel):
    """Job location with structured fields."""
    city: str | None = None
    state: str | None = None
    country: str | None = None
    country_code: str | None = None
    pincode: str | None = None
    raw: str | None = None  # Original unstructured string
    latitude: float | None = None
    longitude: float | None = None

    @property
    def display(self) -> str:
        parts = [p for p in [self.city, self.state, self.country] if p]
        return ", ".join(parts) if parts else self.raw or "Unknown"


class CompanyInfo(BaseModel):
    """Company information attached to a job."""
    name: str
    normalized_name: str | None = None
    domain: str | None = None
    website: str | None = None
    linkedin_url: str | None = None
    logo_url: str | None = None
    size: str | None = None           # startup, small, medium, large, enterprise
    industry: str | None = None
    founded_year: int | None = None
    headquarters: str | None = None
    trust_score: float | None = None  # 0-100, computed by CompanyTrustAgent
    is_verified: bool = False


class ScamAnalysis(BaseModel):
    """Result from the Scam Detection Agent."""
    scam_probability: float = 0.0     # 0.0 - 1.0
    risk_level: ScamRisk = ScamRisk.VERY_LOW
    triggered_rules: list[str] = Field(default_factory=list)
    risk_factors: dict[str, float] = Field(default_factory=dict)
    trust_reasons: list[str] = Field(default_factory=list)
    warning_signals: list[str] = Field(default_factory=list)
    is_url_reachable: bool = True
    model_version: str = "unknown"
    is_reviewed: bool = False          # Human review flag
    reviewer_verdict: bool | None = None


class AuthenticityAnalysis(BaseModel):
    """Result from the Job Authenticity Agent."""
    authenticity_score: float = 50.0  # 0-100
    is_verified: bool = False
    verification_method: str | None = None
    evidence_urls: list[str] = Field(default_factory=list)
    company_career_page_found: bool = False
    cross_platform_matches: int = 0
    last_verified_at: datetime | None = None


# ─── Core Job Models (Pipeline Stages) ────────────────────────────────────────


class RawJob(BaseModel):
    """
    Job as collected from source — minimal validation, maximum preservation.
    Published to Kafka topic: job.raw
    """
    id: UUID = Field(default_factory=uuid4)
    source: CollectionSource
    source_job_id: str             # Original ID from source
    source_url: str
    collection_timestamp: datetime = Field(default_factory=datetime.utcnow)
    collection_run_id: str | None = None

    # Raw fields — may contain HTML, inconsistent formatting
    title: str
    description: str | None = None
    company_name: str
    location_raw: str | None = None
    salary_raw: str | None = None
    job_type_raw: str | None = None
    experience_raw: str | None = None
    skills_raw: list[str] = Field(default_factory=list)
    apply_url: str | None = None
    posted_date_raw: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None

    # Source-specific metadata
    raw_data: dict[str, Any] = Field(default_factory=dict)

    class Config:
        json_encoders = {UUID: str, datetime: lambda v: v.isoformat()}


class CleanedJob(BaseModel):
    """
    Job after Data Cleaning Agent — normalized, HTML-stripped, validated.
    Published to Kafka topic: job.cleaned
    """
    id: UUID = Field(default_factory=uuid4)
    raw_job_id: UUID
    source: CollectionSource
    source_job_id: str
    source_url: str
    cleaned_at: datetime = Field(default_factory=datetime.utcnow)
    status: JobStatus = JobStatus.CLEANED

    # Cleaned & validated fields
    title: str
    description: str
    company: CompanyInfo
    location: Location
    salary: SalaryRange | None = None
    job_type: JobType = JobType.UNKNOWN
    remote_type: RemoteType = RemoteType.UNKNOWN
    experience_level: ExperienceLevel = ExperienceLevel.UNKNOWN
    experience_years_min: int | None = None
    experience_years_max: int | None = None
    apply_url: str | None = None
    posted_at: datetime | None = None
    expires_at: datetime | None = None

    # Quality metadata
    validation_errors: list[str] = Field(default_factory=list)
    null_fields: list[str] = Field(default_factory=list)
    language: str = "en"

    class Config:
        json_encoders = {UUID: str, datetime: lambda v: v.isoformat()}


class EnrichedJob(BaseModel):
    """
    Job after enrichment agents — skills extracted, salary estimated, embeddings ready.
    Published to Kafka topic: job.enriched
    """
    id: UUID = Field(default_factory=uuid4)
    cleaned_job_id: UUID
    source: CollectionSource
    source_job_id: str
    source_url: str
    enriched_at: datetime = Field(default_factory=datetime.utcnow)
    status: JobStatus = JobStatus.ENRICHED

    # From cleaned job
    title: str
    description: str
    company: CompanyInfo
    location: Location
    job_type: JobType
    remote_type: RemoteType
    experience_level: ExperienceLevel
    apply_url: str | None = None
    posted_at: datetime | None = None

    # Enriched fields
    skills: list[Skill] = Field(default_factory=list)
    required_skills: list[str] = Field(default_factory=list)   # Quick access
    nice_to_have_skills: list[str] = Field(default_factory=list)
    salary: SalaryRange | None = None                           # Estimated if missing
    seniority_tags: list[str] = Field(default_factory=list)
    domain_tags: list[str] = Field(default_factory=list)
    tech_stack: list[str] = Field(default_factory=list)

    # Embeddings (stored as metadata reference)
    embedding_id: str | None = None  # Qdrant point ID
    embedding_model: str | None = None

    # Extraction metadata
    skill_extraction_method: str = "rule_based"  # rule_based, llm, hybrid
    skill_confidence: float = 0.0

    class Config:
        json_encoders = {UUID: str, datetime: lambda v: v.isoformat()}


class VerifiedJob(BaseModel):
    """
    Final job model after verification — ready for indexing and serving.
    Published to Kafka topic: job.verified → indexed to Elasticsearch + PostgreSQL
    """
    id: UUID = Field(default_factory=uuid4)
    enriched_job_id: UUID
    source: CollectionSource
    source_job_id: str
    source_url: str
    verified_at: datetime = Field(default_factory=datetime.utcnow)
    status: JobStatus = JobStatus.VERIFIED

    # Full job data
    title: str
    description: str
    company: CompanyInfo
    location: Location
    salary: SalaryRange | None = None
    job_type: JobType
    remote_type: RemoteType
    experience_level: ExperienceLevel
    skills: list[Skill] = Field(default_factory=list)
    required_skills: list[str] = Field(default_factory=list)
    nice_to_have_skills: list[str] = Field(default_factory=list)
    tech_stack: list[str] = Field(default_factory=list)
    domain_tags: list[str] = Field(default_factory=list)
    apply_url: str | None = None
    posted_at: datetime | None = None
    expires_at: datetime | None = None

    # Verification results
    scam_analysis: ScamAnalysis = Field(default_factory=ScamAnalysis)
    authenticity: AuthenticityAnalysis = Field(default_factory=AuthenticityAnalysis)

    # Computed quality score (0-100)
    quality_score: float = 0.0

    # Search metadata
    embedding_id: str | None = None

    class Config:
        json_encoders = {UUID: str, datetime: lambda v: v.isoformat()}


# ─── API Response Models ───────────────────────────────────────────────────────


class JobSearchResult(BaseModel):
    """Job listing as returned by the Search API."""
    id: str
    title: str
    company_name: str
    company_logo: str | None = None
    location: str
    remote_type: RemoteType
    job_type: JobType
    experience_level: ExperienceLevel
    salary_display: str | None = None
    required_skills: list[str] = Field(default_factory=list)
    tech_stack: list[str] = Field(default_factory=list)
    posted_at: datetime | None = None
    apply_url: str | None = None
    source_url: str

    # Trust indicators
    trust_score: float | None = None
    scam_risk: ScamRisk = ScamRisk.VERY_LOW
    is_verified: bool = False
    trust_reasons: list[str] = Field(default_factory=list)
    warning_signals: list[str] = Field(default_factory=list)
    is_url_reachable: bool = True

    # Search relevance
    match_score: float = 0.0
    match_reasons: list[str] = Field(default_factory=list)


class JobSearchResponse(BaseModel):
    """Paginated search response."""
    results: list[JobSearchResult]
    total: int
    page: int
    page_size: int
    query: str
    filters: dict[str, Any] = Field(default_factory=dict)
    search_latency_ms: float = 0.0


class PipelineStatus(BaseModel):
    """Status of a job through the processing pipeline."""
    job_id: str
    source: str
    status: JobStatus
    raw_at: datetime | None = None
    cleaned_at: datetime | None = None
    enriched_at: datetime | None = None
    verified_at: datetime | None = None
    error_message: str | None = None
    retry_count: int = 0


# ─── Agent Input/Output Models ─────────────────────────────────────────────────


class CollectionTask(BaseModel):
    """Input for the Job Collection Agent."""
    task_id: str = Field(default_factory=lambda: str(uuid4()))
    source: CollectionSource
    search_terms: list[str] = Field(default_factory=list)
    location: str | None = None
    limit: int = 100
    priority: int = 1  # 0=highest, 5=lowest
    force_refresh: bool = False


class AgentResult(BaseModel):
    """Generic agent output wrapper."""
    task_id: str
    agent_name: str
    status: str  # success, partial, failed
    data: Any = None
    confidence: float = 1.0
    reasoning: str | None = None
    error: str | None = None
    duration_ms: float = 0.0
    model_used: str | None = None
    tokens_used: int = 0


class DuplicateCheckResult(BaseModel):
    """Result from the Duplicate Detection Agent."""
    job_id: str
    is_duplicate: bool
    duplicate_of: str | None = None
    similarity_score: float = 0.0
    match_type: str | None = None  # exact, semantic, fuzzy
