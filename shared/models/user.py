"""User, subscription, and preference models."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, EmailStr, Field


class UserRole(str, Enum):
    ADMIN = "admin"
    MODERATOR = "moderator"
    USER = "user"
    API_CLIENT = "api_client"


class SubscriptionTier(str, Enum):
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class NotificationChannel(str, Enum):
    EMAIL = "email"
    TELEGRAM = "telegram"
    WHATSAPP = "whatsapp"
    WEBHOOK = "webhook"
    IN_APP = "in_app"


class JobAlertFrequency(str, Enum):
    INSTANT = "instant"
    DAILY = "daily"
    WEEKLY = "weekly"
    DISABLED = "disabled"


class UserPreferences(BaseModel):
    """User notification and search preferences."""
    # Job preferences
    preferred_locations: list[str] = Field(default_factory=list)
    preferred_remote: list[str] = Field(default_factory=list)
    preferred_job_types: list[str] = Field(default_factory=list)
    preferred_experience_levels: list[str] = Field(default_factory=list)
    min_salary: float | None = None
    max_salary: float | None = None
    salary_currency: str = "INR"

    # Notification preferences
    email_alerts: bool = True
    telegram_alerts: bool = False
    whatsapp_alerts: bool = False
    alert_frequency: JobAlertFrequency = JobAlertFrequency.DAILY

    # Feed preferences
    language: str = "en"
    show_scam_risk: bool = True
    min_trust_score: float = 30.0

    # Privacy
    profile_visible: bool = False


class SavedSearch(BaseModel):
    """A saved job search / alert."""
    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    name: str
    query: str
    filters: dict[str, Any] = Field(default_factory=dict)
    alert_enabled: bool = True
    alert_frequency: JobAlertFrequency = JobAlertFrequency.DAILY
    last_triggered_at: datetime | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class UserProfile(BaseModel):
    """Extended user profile for job matching."""
    id: UUID = Field(default_factory=uuid4)
    user_id: UUID

    # Professional info
    headline: str | None = None
    bio: str | None = None
    current_title: str | None = None
    current_company: str | None = None
    years_of_experience: float | None = None
    skills: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    education: list[dict[str, str]] = Field(default_factory=list)

    # Contact
    linkedin_url: str | None = None
    github_url: str | None = None
    portfolio_url: str | None = None
    phone: str | None = None

    # Location
    current_location: str | None = None
    willing_to_relocate: bool = False
    open_to_remote: bool = True

    # Resume
    resume_url: str | None = None  # MinIO URL
    resume_text: str | None = None  # Extracted text

    # Matching
    embedding_id: str | None = None  # Qdrant point ID
    last_active_at: datetime | None = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class User(BaseModel):
    """Core user model."""
    id: UUID = Field(default_factory=uuid4)
    email: EmailStr
    username: str | None = None
    full_name: str | None = None
    role: UserRole = UserRole.USER
    tier: SubscriptionTier = SubscriptionTier.FREE
    is_active: bool = True
    is_verified: bool = False

    # Auth
    hashed_password: str | None = None
    oauth_provider: str | None = None  # google, linkedin
    oauth_id: str | None = None

    # Telegram integration
    telegram_chat_id: str | None = None
    telegram_username: str | None = None

    # Webhook
    webhook_url: str | None = None
    webhook_secret: str | None = None

    # Metadata
    preferences: UserPreferences = Field(default_factory=UserPreferences)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_login_at: datetime | None = None

    class Config:
        json_encoders = {UUID: str}


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str | None = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class SavedJob(BaseModel):
    """User's saved/bookmarked job."""
    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    job_id: str
    notes: str | None = None
    applied: bool = False
    applied_at: datetime | None = None
    saved_at: datetime = Field(default_factory=datetime.utcnow)


class ApplicationRecord(BaseModel):
    """Job application tracking."""
    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    job_id: str
    status: str = "applied"  # applied, screening, interview, offer, rejected
    applied_at: datetime = Field(default_factory=datetime.utcnow)
    notes: str | None = None
    next_step: str | None = None
