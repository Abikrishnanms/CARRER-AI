"""
Resume & Candidate Profile Pydantic models for Job Intelligence Platform.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field


class CandidateProfile(BaseModel):
    user_id: str | None = None
    filename: str | None = None
    raw_text: str = ""
    skills: list[str] = Field(default_factory=list)
    experience_years: float = 0.0
    experience_level: str = "entry"  # entry, mid, senior, lead
    target_titles: list[str] = Field(default_factory=list)
    education_degrees: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    projects: list[str] = Field(default_factory=list)
    location_preference: str | None = None
    remote_preference: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class JobMatchExplanation(BaseModel):
    match_percentage: float = 0.0
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    positive_signals: list[str] = Field(default_factory=list)
    warning_signals: list[str] = Field(default_factory=list)


class RecommendedJobResult(BaseModel):
    job: dict[str, Any]
    match: JobMatchExplanation


class SkillGapAnalysis(BaseModel):
    total_skills_count: int = 0
    candidate_skills: list[str] = Field(default_factory=list)
    top_strengths: list[str] = Field(default_factory=list)
    missing_high_demand_skills: list[dict[str, Any]] = Field(default_factory=list)
    recommended_learning_path: list[str] = Field(default_factory=list)
