"""
Company Pydantic models — shared across services.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, HttpUrl


class CompanySize(str, Enum):
    STARTUP = "startup"       # 1-10 employees
    SMALL = "small"           # 11-50
    MEDIUM = "medium"         # 51-200
    LARGE = "large"           # 201-1000
    ENTERPRISE = "enterprise" # 1000+
    UNKNOWN = "unknown"


class CompanyVerificationStatus(str, Enum):
    UNVERIFIED = "unverified"
    PENDING = "pending"
    VERIFIED = "verified"
    FLAGGED = "flagged"       # Suspicious activity
    BLACKLISTED = "blacklisted"


class Company(BaseModel):
    """Full company profile stored in MongoDB."""
    id: UUID = Field(default_factory=uuid4)
    name: str
    normalized_name: str

    # Identity
    domain: str | None = None
    website: str | None = None
    linkedin_url: str | None = None
    glassdoor_url: str | None = None
    crunchbase_url: str | None = None

    # Branding
    logo_url: str | None = None
    description: str | None = None
    tagline: str | None = None

    # Classification
    size: CompanySize = CompanySize.UNKNOWN
    industry: str | None = None
    sub_industry: str | None = None
    founded_year: int | None = None
    headquarters: str | None = None
    country: str | None = None

    # Trust & Verification
    trust_score: float = 50.0          # 0–100
    verification_status: CompanyVerificationStatus = CompanyVerificationStatus.UNVERIFIED
    is_verified: bool = False
    scam_reports: int = 0
    verified_at: datetime | None = None
    blacklisted_at: datetime | None = None
    blacklist_reason: str | None = None

    # Social proof
    employee_count: int | None = None
    avg_rating: float | None = None    # Glassdoor/Ambitionbox rating
    total_reviews: int = 0

    # Stats
    active_job_count: int = 0
    total_jobs_posted: int = 0

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    data_sources: list[str] = Field(default_factory=list)
    raw_data: dict[str, Any] = Field(default_factory=dict)

    class Config:
        json_encoders = {UUID: str, datetime: lambda v: v.isoformat()}


class CompanySearchResult(BaseModel):
    """Lightweight company info for search results."""
    id: str
    name: str
    domain: str | None = None
    logo_url: str | None = None
    industry: str | None = None
    size: CompanySize = CompanySize.UNKNOWN
    trust_score: float = 50.0
    is_verified: bool = False
    active_job_count: int = 0


class CompanyTrustReport(BaseModel):
    """Trust analysis report for a company."""
    company_id: str
    company_name: str
    trust_score: float
    verification_status: CompanyVerificationStatus
    risk_factors: list[str] = Field(default_factory=list)
    positive_signals: list[str] = Field(default_factory=list)
    scam_reports: int = 0
    domain_age_days: int | None = None
    has_linkedin: bool = False
    has_glassdoor: bool = False
    employee_count_verified: bool = False
    analyzed_at: datetime = Field(default_factory=datetime.utcnow)
