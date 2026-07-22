"""
SESSION 2: The "Bouncer" - Pydantic Data Models
These models define the exact shape of data allowed into our system.
Any job that doesn't match this shape is instantly rejected.
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any, Union

from pydantic import BaseModel, Field, field_validator


# ------------------------------------------------------------
# 1. ENUMS (Standardized Dropdowns)
# These prevent typos. Instead of writing "Full Time" vs "full-time",
# we force the system to use these exact values.
# ------------------------------------------------------------
class JobStatus(str, Enum):
    RAW = "raw"             # Just scraped, not processed yet
    CLEANED = "cleaned"     # Passed through the preprocessor
    PROCESSED = "processed" # Fully analyzed (fraud check, ML done)
    FAILED = "failed"       # Could not be processed

class EmploymentType(str, Enum):
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    INTERNSHIP = "internship"
    FREELANCE = "freelance"
    REMOTE = "remote"
    UNKNOWN = "unknown"


# ------------------------------------------------------------
# 1.5 VALID SOURCE PLATFORMS (Central Registry)
# Any new ATS or API source must be added here.
# This prevents typos like "greeenhouse" or "adzunna"
# ------------------------------------------------------------
VALID_SOURCES = [
    # ATS Platforms (New sources)
    "greenhouse",
    "lever",
    "workday",
    "ashby",
    "smartrecruiters",
    # Job Aggregators (Existing sources)
    "adzuna",
    "jooble",
    "jobspy",
    # Legacy/Backup (keeping them for any old data in MongoDB)
    "naukri",
    "indeed",
]


# ------------------------------------------------------------
# 2. NESTED MODELS (Salary, Location, Company)
# These make our code reusable and clean.
# ------------------------------------------------------------
class Salary(BaseModel):
    """Standardized salary model. Handles both numeric and text inputs."""
    min: Optional[float] = None
    max: Optional[float] = None
    currency: str = "INR"   # Default for our Indian focus
    period: str = "yearly"  # yearly, monthly, hourly
    is_negotiable: bool = False
    raw_text: Optional[str] = None  # Keep the original text for debugging

    # Validation: Salary cannot be negative
    @field_validator("min", "max")
    @classmethod
    def validate_positive(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and v < 0:
            raise ValueError("Salary cannot be negative")
        return v

    # Validation: Min must be <= Max
    @field_validator("max")
    @classmethod
    def validate_range(cls, v: Optional[float], info) -> Optional[float]:
        # Access the 'min' value from the instance being validated
        if v is not None and info.data.get('min') is not None:
            if info.data['min'] > v:
                raise ValueError("Minimum salary cannot be greater than maximum salary")
        return v


class Location(BaseModel):
    """Standardized location model."""
    city: Optional[str] = None
    state: Optional[str] = None
    country: str = "India"  # Default for our MVP
    pin_code: Optional[str] = None
    is_remote: bool = False
    full_address: Optional[str] = None  # The raw string from the API


class Company(BaseModel):
    """Standardized company model."""
    name: str  # This is REQUIRED!
    domain: Optional[str] = None  # e.g., google.com
    official_url: Optional[str] = None
    careers_page_url: Optional[str] = None
    industry: Optional[str] = None
    employee_count: Optional[str] = None


# ------------------------------------------------------------
# 3. THE MAIN RAW JOB (The core contract)
# This is what every scraper MUST output.
# ------------------------------------------------------------
class RawJob(BaseModel):
    """
    The main data contract for incoming jobs.
    Every adapter (Adzuna, Jooble, etc.) must convert its data into this format.
    """
    # --- REQUIRED FIELDS (Must be provided by the adapter) ---
    job_id: str = Field(..., description="Unique hash ID for deduplication")
    source_platform: str = Field(..., description="adzuna, jooble, naukri, etc.")
    source_url: str = Field(..., description="Direct link to the job posting")
    title: str = Field(..., description="Full job title")
    company: Company = Field(..., description="Company details")
    description: str = Field(..., description="Full job description text")

    # --- OPTIONAL FIELDS (May be None if the API doesn't provide them) ---
    salary: Optional[Salary] = None
    location: Optional[Location] = None
    employment_type: Optional[EmploymentType] = EmploymentType.UNKNOWN
    experience_required: Optional[str] = None  # e.g., "3-5 years"
    education_required: Optional[str] = None
    skills: Optional[List[str]] = None
    posted_date: Optional[datetime] = None
    application_deadline: Optional[datetime] = None

    # --- METADATA (Automatically filled by our system) ---
    scraped_at: datetime = Field(default_factory=datetime.utcnow)
    status: JobStatus = JobStatus.RAW

    # --- RAW DATA (Store the original API response for debugging) ---
    raw_data: Dict[str, Any] = Field(default_factory=dict)

    # --- VALIDATORS ---
    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Job title cannot be empty")
        return v.strip()

    @field_validator("source_platform")
    @classmethod
    def validate_source_platform(cls, v: str) -> str:
        """
        Ensure the source_platform is one of our known ATS or API sources.
        This prevents typos and ensures clean data in MongoDB.
        """
        if v not in VALID_SOURCES:
            raise ValueError(
                f"Invalid source_platform: '{v}'. "
                f"Must be one of: {', '.join(VALID_SOURCES)}"
            )
        return v


# ------------------------------------------------------------
# 4. THE CLEANED JOB (Used after the Preprocessor)
# This extends RawJob with fields added by our cleaning logic.
# ------------------------------------------------------------
class CleanedJob(RawJob):
    """The job after it has been cleaned by the Preprocessor."""
    # Cleaned versions of text
    cleaned_title: str = ""
    cleaned_description: str = ""

    # Extracted/enriched fields
    extracted_skills: List[str] = Field(default_factory=list)
    extracted_experience_years: Optional[float] = None

    # Duplicate detection
    is_duplicate: bool = False
    duplicate_of: Optional[str] = None  # Points to the original job_id

    # Data quality flags
    has_null_values: bool = False
    null_fields: List[str] = Field(default_factory=list)
    validation_errors: List[str] = Field(default_factory=list)

    # Statistics for EDA
    description_word_count: int = 0
    description_has_html: bool = False

    cleaned_at: datetime = Field(default_factory=datetime.utcnow)
    status: JobStatus = JobStatus.CLEANED


# ------------------------------------------------------------
# 5. THE FULL DOCUMENT (Stored in MongoDB)
# MongoDB will add its own `_id` field automatically.
# ------------------------------------------------------------
class JobDocument(BaseModel):
    """The full job document as stored in MongoDB."""
    raw: RawJob
    cleaned: Optional[CleanedJob] = None

    # Pipeline tracking
    pipeline_stage: str = "raw"  # raw -> cleaned -> processed

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        # Allows us to convert MongoDB BSON to/from this model easily
        populate_by_name = True