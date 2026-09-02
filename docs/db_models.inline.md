**Database Models — `shared/database/models.py` (Annotated copy)**

Summary: Pydantic models used as the canonical schema for documents stored in MongoDB. Models are permissive (extra fields allowed) and include timestamp and ID helpers.

---

```python
"""
Pydantic models — MongoDB database schema.
Designed for unstructured data storage while maintaining core schema validation.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class MongoBaseModel(BaseModel):
    """Base model with common timestamp fields and MongoDB ID handling."""
    model_config = ConfigDict(
        populate_by_name=True,
        extra="allow",  # Allow unstructured data fields
        json_encoders={datetime: lambda dt: dt.isoformat()}
    )
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), alias="_id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ─── Company ──────────────────────────────────────────────────────────────────

class Company(MongoBaseModel):
    name: str
    normalized_name: str
    domain: Optional[str] = None
    website: Optional[str] = None
    linkedin_url: Optional[str] = None
    logo_url: Optional[str] = None
    size: Optional[str] = None
    industry: Optional[str] = None
    founded_year: Optional[int] = None
    headquarters: Optional[str] = None

    # Trust metrics
    trust_score: Optional[float] = None
    ssl_valid: Optional[bool] = None
    domain_age_days: Optional[int] = None
    is_verified: bool = False
    trust_last_checked: Optional[datetime] = None


# ─── Job (Main table) ─────────────────────────────────────────────────────────

class Job(MongoBaseModel):
    source: str
    source_job_id: str
    source_url: str
    status: str = "raw"

    # Core fields
    title: str
    description: Optional[str] = None
    company_id: Optional[str] = None
    company_name: str

    # Location
    location_city: Optional[str] = None
    location_state: Optional[str] = None
    location_country: Optional[str] = None
    location_country_code: Optional[str] = None
    location_raw: Optional[str] = None

    # Classification
    job_type: str = "unknown"
    remote_type: str = "unknown"
    experience_level: str = "unknown"
    experience_years_min: Optional[int] = None
    experience_years_max: Optional[int] = None

    # Salary
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    salary_currency: Optional[str] = None
    salary_period: Optional[str] = None
    salary_is_estimated: bool = False

    # Skills (stored as lists/dicts)
    required_skills: List[Any] = Field(default_factory=list)
    nice_to_have_skills: List[Any] = Field(default_factory=list)
    tech_stack: List[Any] = Field(default_factory=list)
    domain_tags: List[Any] = Field(default_factory=list)
    skills_data: Dict[str, Any] = Field(default_factory=dict)

    # Application
    apply_url: Optional[str] = None
    posted_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    language: str = "en"

    # Quality & Trust
    quality_score: float = 0.0
    scam_probability: float = 0.0
    scam_risk_level: str = "very_low"
    scam_triggered_rules: List[Any] = Field(default_factory=list)
    authenticity_score: float = 50.0
    is_verified: bool = False
    is_duplicate: bool = False
    duplicate_of_id: Optional[str] = None

    # Vector embedding reference
    embedding_id: Optional[str] = None
    embedding_model: Optional[str] = None

    # Pipeline metadata
    collection_run_id: Optional[str] = None
    raw_data: Dict[str, Any] = Field(default_factory=dict)
    validation_errors: List[Any] = Field(default_factory=list)


# ─── Users ────────────────────────────────────────────────────────────────────

class User(MongoBaseModel):
    email: str
    username: Optional[str] = None
    full_name: Optional[str] = None
    role: str = "user"
    tier: str = "free"
    is_active: bool = True
    is_verified: bool = False

    # Auth
    hashed_password: Optional[str] = None
    oauth_provider: Optional[str] = None
    oauth_id: Optional[str] = None

    # Integrations
    telegram_chat_id: Optional[str] = None
    telegram_username: Optional[str] = None
    webhook_url: Optional[str] = None
    webhook_secret: Optional[str] = None

    # Preferences
    preferences: Dict[str, Any] = Field(default_factory=dict)
    last_login_at: Optional[datetime] = None


class UserProfile(MongoBaseModel):
    user_id: str
    headline: Optional[str] = None
    bio: Optional[str] = None
    current_title: Optional[str] = None
    current_company: Optional[str] = None
    years_of_experience: Optional[float] = None
    skills: List[Any] = Field(default_factory=list)
    certifications: List[Any] = Field(default_factory=list)
    education: List[Any] = Field(default_factory=list)

    linkedin_url: Optional[str] = None
    github_url: Optional[str] = None
    portfolio_url: Optional[str] = None
    current_location: Optional[str] = None
    willing_to_relocate: bool = False
    open_to_remote: bool = True

    resume_url: Optional[str] = None
    resume_text: Optional[str] = None
    embedding_id: Optional[str] = None
    last_active_at: Optional[datetime] = None


class SavedSearch(MongoBaseModel):
    user_id: str
    name: str
    query: str
    filters: Dict[str, Any] = Field(default_factory=dict)
    alert_enabled: bool = True
    alert_frequency: str = "daily"
    last_triggered_at: Optional[datetime] = None


class SavedJob(MongoBaseModel):
    user_id: str
    job_id: str
    notes: Optional[str] = None
    applied: bool = False
    applied_at: Optional[datetime] = None


# ─── Pipeline Audit ─────────────────────────────────────────────────────────--

class PipelineEvent(MongoBaseModel):
    job_id: Optional[str] = None
    event_type: str
    agent_name: Optional[str] = None
    status: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    error_message: Optional[str] = None
    duration_ms: Optional[float] = None


# ─── Notifications ───────────────────────────────────────────────────────────-

class NotificationLog(MongoBaseModel):
    user_id: str
    channel: str
    template_id: Optional[str] = None
    subject: Optional[str] = None
    status: str
    retry_count: int = 0
    error_message: Optional[str] = None
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None


# ─── Scam Rules ─────────────────────────────────────────────────────────────--

class ScamRule(MongoBaseModel):
    name: str
    description: Optional[str] = None
    rule_type: str
    pattern: Optional[str] = None
    field: Optional[str] = None
    weight: float = 1.0
    is_active: bool = True
    trigger_count: int = 0


# ─── Skill Taxonomy ─────────────────────────────────────────────────────────--

class SkillTaxonomy(MongoBaseModel):
    name: str
    normalized_name: str
    category: Optional[str] = None
    aliases: List[Any] = Field(default_factory=list)
    parent_skill: Optional[str] = None
    onet_code: Optional[str] = None


# ─── Collection Runs ─────────────────────────────────────────────────────────-

class CollectionRun(MongoBaseModel):
    source: str
    status: str = "running"
    jobs_collected: int = 0
    jobs_failed: int = 0
    search_terms: List[Any] = Field(default_factory=list)
    error_message: Optional[str] = None
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
```

---

Grouped explanations:

- `MongoBaseModel`: central base enabling `_id` aliasing, automatic `created_at`/`updated_at`, and permissive `extra='allow'` so documents can include fields beyond the schema.
- `Company`: company metadata + trust metrics (SSL, domain age, verified flag).
- `Job`: canonical job document shape — includes locations, classification, salary, skills lists, pipeline metadata, quality/trust scores, embedding references, and raw_data for the original payload.
- `User`, `UserProfile`, `SavedSearch`, `SavedJob`: user-related documents and preferences.
- `PipelineEvent`: event audit log used by services to record pipeline lifecycle events with payload + duration.
- `NotificationLog`: records notification attempts and statuses.
- `ScamRule` and `SkillTaxonomy`: domain-specific configuration documents used by verifier and skill extractor.
- `CollectionRun`: tracks collection job runs, counts and errors.

Notes / Next steps:
- These models are intended for Pydantic validation and easy serialization; collections are flexible because of `extra='allow'` so experiments can add fields without migration.
- Next: I'll add `docs/db_session.inline.md` documenting `shared/database/session.py` (connection management, index initialization, and test helpers).
