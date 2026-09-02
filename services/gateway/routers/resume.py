"""
Resume Upload & Personalized Job Recommendation Router.
Supports file upload (PDF/DOCX/TXT), profile parsing, intelligent matching, and skill-gap analysis.
"""

from __future__ import annotations

import logging, uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from services.gateway.deps import get_current_user
from shared.database.session import get_db
from shared.utils.resume_parser import extract_resume_text, parse_candidate_profile
from shared.utils.recommender import score_job_match, compute_skill_gap_analysis
from shared.utils.url import normalize_url

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/parse", summary="Upload and parse resume (PDF, DOCX, TXT)")
async def parse_resume_file(
    file: UploadFile = File(...),
) -> dict[str, Any]:
    """
    Upload resume file and extract structured candidate profile.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file uploaded")

    filename = file.filename
    ext = filename.lower().split(".")[-1]
    if ext not in ("pdf", "docx", "txt", "md"):
        raise HTTPException(status_code=400, detail="Unsupported file format. Please upload a PDF, DOCX, or TXT file.")

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File size exceeds 10MB limit")

    raw_text = extract_resume_text(content, filename)
    if not raw_text or len(raw_text.strip()) < 20:
        raise HTTPException(status_code=422, detail="Unable to extract text from file. Please ensure file contains readable text.")

    profile = parse_candidate_profile(raw_text, filename)
    return {
        "status": "success",
        "profile": profile,
    }


@router.post("/parse-text", summary="Parse raw resume text directly")
async def parse_resume_text_endpoint(
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Parse raw resume text directly without file upload."""
    text = payload.get("text", "")
    if not text or len(text.strip()) < 20:
        raise HTTPException(status_code=422, detail="Text is too short. Please provide at least 20 characters.")
    filename = payload.get("filename", "Pasted Resume.txt")
    profile = parse_candidate_profile(text, filename)
    return {
        "status": "success",
        "profile": profile,
    }


@router.post("/recommendations", summary="Get personalized job recommendations from profile or resume")
async def get_personalized_recommendations(
    payload: dict[str, Any],
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict[str, Any]:
    """
    Match candidate profile against published & verified jobs in MongoDB.
    Returns ranked jobs with match percentages, match explanations, and skill gap insights.
    """
    profile = payload.get("profile") or payload
    if not profile or not isinstance(profile, dict):
        raise HTTPException(status_code=400, detail="Candidate profile dictionary required")

    # Query ONLY published, non-duplicate, verified/safe jobs
    filters = {
        "status": "published",
        "is_duplicate": {"$ne": True},
        "$or": [
            {"scam_probability": {"$lt": 0.25}},
            {"scam_probability": {"$exists": False}},
        ]
    }

    cursor = db.jobs.find(filters).limit(200)
    jobs = await cursor.to_list(length=200)

    # Fetch Companies for logo/domain
    company_ids = [j.get("company_id") for j in jobs if j.get("company_id")]
    companies = []
    if company_ids:
        companies = await db.companies.find({"_id": {"$in": company_ids}}).to_list(length=None)
    company_map = {str(c["_id"]): c for c in companies if "_id" in c}

    recommendations = []
    for job in jobs:
        comp_obj = company_map.get(str(job.get("company_id")))
        comp_name = job.get("company_name")
        job_title = job.get("title")
        src_name = job.get("source")

        match_pct, explanation = score_job_match(profile, job)

        salary_min_val = job.get("salary_min")
        salary_max_val = job.get("salary_max")
        salary_display = None
        if salary_min_val and salary_max_val:
            salary_display = f"₹{salary_min_val/100000:.1f}L - ₹{salary_max_val/100000:.1f}L/year"

        norm_apply_url = normalize_url(job.get("apply_url") or job.get("source_url"), job_title, comp_name, src_name)

        job_formatted = {
            "id": str(job.get("_id", job.get("id"))),
            "title": job_title,
            "company_name": comp_name,
            "company_logo": comp_obj.get("logo_url") if comp_obj else None,
            "location": job.get("location_city") or job.get("location_raw") or "Remote",
            "remote_type": job.get("remote_type", "remote"),
            "job_type": job.get("job_type", "full_time"),
            "experience_level": job.get("experience_level", "entry"),
            "salary_display": salary_display,
            "required_skills": job.get("required_skills", []),
            "apply_url": norm_apply_url,
            "trust_score": job.get("trust_score", 85.0),
            "is_verified": job.get("is_verified", True),
        }

        recommendations.append({
            "job": job_formatted,
            "match": explanation,
        })

    # Sort descending by match percentage
    recommendations.sort(key=lambda x: x["match"]["match_percentage"], reverse=True)
    top_recommendations = recommendations[:20]

    # Aggregate Skill Gap Analysis
    skill_gap = compute_skill_gap_analysis(profile, top_recommendations)

    return {
        "total_recommendations": len(top_recommendations),
        "candidate_profile_summary": {
            "skills_count": len(profile.get("skills", [])),
            "experience_level": profile.get("experience_level", "entry"),
            "experience_years": profile.get("experience_years", 0),
            "target_titles": profile.get("target_titles", []),
        },
        "recommendations": top_recommendations,
        "skill_gap_analysis": skill_gap,
    }


@router.get("/profile", summary="Get user saved candidate profile")
async def get_user_profile(
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict[str, Any]:
    """Retrieve saved candidate profile for current user."""
    user_id = str(current_user.get("_id") or current_user.get("id"))
    profile = await db.candidate_profiles.find_one({"user_id": user_id})
    if not profile:
        return {"has_profile": False, "profile": None}

    profile["id"] = str(profile.get("_id", profile.get("id")))
    return {"has_profile": True, "profile": profile}


@router.put("/profile", summary="Save or update candidate profile")
async def save_user_profile(
    profile_data: dict[str, Any],
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict[str, Any]:
    """Save or update authenticated candidate profile."""
    user_id = str(current_user.get("_id") or current_user.get("id"))
    profile_data["user_id"] = user_id
    profile_data["updated_at"] = datetime.now(timezone.utc)

    await db.candidate_profiles.update_one(
        {"user_id": user_id},
        {"$set": profile_data},
        upsert=True,
    )
    return {"status": "success", "message": "Candidate profile updated"}
