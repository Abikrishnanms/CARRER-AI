"""Jobs CRUD router — full job management API."""

from __future__ import annotations

import logging
from typing import Any
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from services.gateway.deps import get_current_user, require_admin
from shared.database.session import get_db

logger = logging.getLogger(__name__)
router = APIRouter()


# ─── List / Search Jobs ───────────────────────────────────────────────────────

@router.get("", response_model=dict[str, Any], summary="List jobs with filters")
async def list_jobs(
    request: Request,
    q: str | None = Query(None, description="Text search query"),
    location: str | None = Query(None, description="City, state, or country"),
    remote: str | None = Query(None, description="remote, hybrid, on_site"),
    job_type: str | None = Query(None, description="full_time, part_time, contract"),
    experience: str | None = Query(None, description="entry, mid, senior, lead"),
    salary_min: float | None = Query(None, description="Minimum salary (INR/year)"),
    salary_max: float | None = Query(None, description="Maximum salary (INR/year)"),
    skills: list[str] = Query(default=[], description="Required skills (comma-separated)"),
    company: str | None = Query(None, description="Company name filter"),
    min_trust_score: float = Query(30.0, description="Minimum company trust score"),
    max_scam_risk: str = Query("medium", description="Maximum scam risk level"),
    posted_within_days: int | None = Query(None, description="Jobs posted within N days"),
    status_filter: str = Query("published", description="Job status filter"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = Query("posted_at", description="Sort field"),
    sort_order: str = Query("desc", description="asc or desc"),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict[str, Any]:
    """
    List jobs with comprehensive filtering.
    Returns paginated results with trust indicators.
    """
    filters = {"status": status_filter, "is_duplicate": False}

    if q:
        filters["$or"] = [
            {"title": {"$regex": q, "$options": "i"}},
            {"description": {"$regex": q, "$options": "i"}},
            {"company_name": {"$regex": q, "$options": "i"}},
        ]

    if location:
        filters["$or"] = filters.get("$or", []) + [
            {"location_city": {"$regex": location, "$options": "i"}},
            {"location_state": {"$regex": location, "$options": "i"}},
            {"location_country": {"$regex": location, "$options": "i"}},
        ]

    if remote:
        filters["remote_type"] = remote
    if job_type:
        filters["job_type"] = job_type
    if experience:
        filters["experience_level"] = experience
    if salary_min is not None:
        filters["salary_max"] = {"$gte": salary_min}
    if salary_max is not None:
        filters["salary_min"] = {"$lte": salary_max}
    if company:
        filters["company_name"] = {"$regex": company, "$options": "i"}

    scam_risk_map = {
        "very_low": 0.2, "low": 0.4, "medium": 0.6, "high": 0.8, "very_high": 1.0
    }
    max_scam_prob = scam_risk_map.get(max_scam_risk, 0.6)
    filters["scam_probability"] = {"$lte": max_scam_prob}

    if posted_within_days:
        cutoff = datetime.utcnow() - timedelta(days=posted_within_days)
        filters["posted_at"] = {"$gte": cutoff}

    # Count total
    total = await db.jobs.count_documents(filters)

    # Sort
    sort_dir = -1 if sort_order == "desc" else 1
    sort_tuple = [(sort_by, sort_dir)]

    # Fetch Jobs
    skip = (page - 1) * page_size
    cursor = db.jobs.find(filters).sort(sort_tuple).skip(skip).limit(page_size)
    jobs = await cursor.to_list(length=page_size)

    # Fetch Companies
    company_ids = [j.get("company_id") for j in jobs if j.get("company_id")]
    companies = []
    if company_ids:
        companies = await db.companies.find({"_id": {"$in": company_ids}}).to_list(length=None)
    company_map = {str(c["_id"]): c for c in companies if "_id" in c}

    jobs_out = []
    for job in jobs:
        company_obj = company_map.get(str(job.get("company_id")))
        
        salary_min_val = job.get("salary_min")
        salary_max_val = job.get("salary_max")
        salary_display = None
        if salary_min_val and salary_max_val:
            salary_display = f"₹{salary_min_val/100000:.1f}L - ₹{salary_max_val/100000:.1f}L/year"
        elif salary_min_val:
            salary_display = f"₹{salary_min_val/100000:.1f}L+/year"

        sp = job.get("scam_probability", 0)
        if sp < 0.2: risk = "very_low"
        elif sp < 0.4: risk = "low"
        elif sp < 0.6: risk = "medium"
        elif sp < 0.8: risk = "high"
        else: risk = "very_high"
        
        posted_at = job.get("posted_at")

        jobs_out.append({
            "id": str(job.get("_id", job.get("id"))),
            "title": job.get("title"),
            "company_name": job.get("company_name"),
            "company_logo": company_obj.get("logo_url") if company_obj else None,
            "location": _format_location(job),
            "remote_type": job.get("remote_type"),
            "job_type": job.get("job_type"),
            "experience_level": job.get("experience_level"),
            "salary_display": salary_display,
            "required_skills": job.get("required_skills", []),
            "tech_stack": job.get("tech_stack", []),
            "posted_at": posted_at.isoformat() if isinstance(posted_at, datetime) else posted_at,
            "apply_url": job.get("apply_url"),
            "source_url": job.get("source_url"),
            "trust_score": company_obj.get("trust_score") if company_obj else None,
            "scam_risk": risk,
            "is_verified": job.get("is_verified", False),
            "quality_score": job.get("quality_score", 0),
        })

    return {
        "results": jobs_out,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
        "filters_applied": {
            "q": q, "location": location, "remote": remote,
            "job_type": job_type, "experience": experience
        }
    }


@router.get("/{job_id}", summary="Get job details")
async def get_job(
    job_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict[str, Any]:
    """Get full job details including verification and skill data."""
    job = await db.jobs.find_one({"_id": job_id})
    if not job:
        # Check by id if _id wasn't used or it's a string instead of UUID in db
        job = await db.jobs.find_one({"id": job_id})
    
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    company = None
    if job.get("company_id"):
        company = await db.companies.find_one({"_id": job.get("company_id")})

    salary_min_val = job.get("salary_min")
    salary_max_val = job.get("salary_max")
    salary_display = None
    if salary_min_val and salary_max_val:
        salary_display = f"₹{salary_min_val/100000:.1f}L - ₹{salary_max_val/100000:.1f}L/year"
        
    posted_at = job.get("posted_at")
    expires_at = job.get("expires_at")
    created_at = job.get("created_at")

    return {
        "id": str(job.get("_id", job.get("id"))),
        "title": job.get("title"),
        "description": job.get("description"),
        "company": {
            "name": job.get("company_name"),
            "domain": company.get("domain") if company else None,
            "website": company.get("website") if company else None,
            "logo_url": company.get("logo_url") if company else None,
            "trust_score": company.get("trust_score") if company else None,
            "is_verified": company.get("is_verified") if company else False,
            "size": company.get("size") if company else None,
            "industry": company.get("industry") if company else None,
        },
        "location": {
            "city": job.get("location_city"),
            "state": job.get("location_state"),
            "country": job.get("location_country"),
            "display": _format_location(job),
        },
        "job_type": job.get("job_type"),
        "remote_type": job.get("remote_type"),
        "experience_level": job.get("experience_level"),
        "experience_years": {
            "min": job.get("experience_years_min"),
            "max": job.get("experience_years_max"),
        },
        "salary": {
            "min": job.get("salary_min"),
            "max": job.get("salary_max"),
            "currency": job.get("salary_currency"),
            "period": job.get("salary_period"),
            "is_estimated": job.get("salary_is_estimated", False),
            "display": salary_display,
        },
        "skills": {
            "required": job.get("required_skills", []),
            "nice_to_have": job.get("nice_to_have_skills", []),
            "tech_stack": job.get("tech_stack", []),
            "full": job.get("skills_data", []),
        },
        "domain_tags": job.get("domain_tags", []),
        "apply_url": job.get("apply_url"),
        "source_url": job.get("source_url"),
        "source": job.get("source"),
        "posted_at": posted_at.isoformat() if isinstance(posted_at, datetime) else posted_at,
        "expires_at": expires_at.isoformat() if isinstance(expires_at, datetime) else expires_at,
        "verification": {
            "scam_probability": job.get("scam_probability", 0),
            "scam_risk_level": job.get("scam_risk_level", "very_low"),
            "scam_triggered_rules": job.get("scam_triggered_rules", []),
            "authenticity_score": job.get("authenticity_score", 50.0),
            "is_verified": job.get("is_verified", False),
            "quality_score": job.get("quality_score", 0),
        },
        "status": job.get("status"),
        "created_at": created_at.isoformat() if isinstance(created_at, datetime) else created_at,
    }


@router.get("/{job_id}/pipeline", summary="Get job pipeline status")
async def get_pipeline_status(
    job_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict[str, Any]:
    """Track a job's progress through the processing pipeline."""
    job = await db.jobs.find_one({"_id": job_id})
    if not job:
        job = await db.jobs.find_one({"id": job_id})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    events = await db.pipeline_events.find({"job_id": str(job_id)}).sort("created_at", 1).to_list(length=None)

    return {
        "job_id": str(job.get("_id", job.get("id"))),
        "current_status": job.get("status"),
        "source": job.get("source"),
        "events": [
            {
                "event_type": e.get("event_type"),
                "agent": e.get("agent_name"),
                "status": e.get("status"),
                "duration_ms": e.get("duration_ms"),
                "timestamp": e.get("created_at").isoformat() if isinstance(e.get("created_at"), datetime) else e.get("created_at"),
                "error": e.get("error_message"),
            }
            for e in events
        ]
    }


@router.delete("/{job_id}", summary="Delete a job (admin only)")
async def delete_job(
    job_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _: Any = Depends(require_admin),
) -> dict[str, str]:
    result = await db.jobs.delete_one({"_id": job_id})
    if result.deleted_count == 0:
        # Check by id if _id wasn't used
        result = await db.jobs.delete_one({"id": job_id})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Job not found")

    return {"message": f"Job {job_id} deleted"}


@router.post("/{job_id}/report", summary="Report a suspicious job")
async def report_job(
    job_id: str,
    reason: str,
    details: str | None = None,
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict[str, str]:
    """Allow users to report suspicious job postings."""
    job = await db.jobs.find_one({"_id": job_id})
    if not job:
        job = await db.jobs.find_one({"id": job_id})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Log the report as a pipeline event
    event = {
        "job_id": str(job_id),
        "event_type": "user.report",
        "agent_name": "user",
        "status": "pending_review",
        "payload": {"reason": reason, "details": details},
        "created_at": datetime.utcnow()
    }
    await db.pipeline_events.insert_one(event)

    return {"message": "Report submitted. Our team will review this job posting."}


# ─── Admin Job Management ─────────────────────────────────────────────────────

@router.post("/collect/trigger", summary="Trigger job collection (admin)", tags=["Admin"])
async def trigger_collection(
    sources: list[str] | None = None,
    search_terms: list[str] | None = None,
    _: Any = Depends(require_admin),
) -> dict[str, Any]:
    """Manually trigger a job collection run."""
    from shared.kafka.producer import get_producer
    from shared.kafka.topics import TOPICS

    producer = await get_producer()
    task = {
        "sources": sources or ["adzuna", "greenhouse"],
        "search_terms": search_terms or ["software engineer", "data scientist", "python developer"],
        "triggered_by": "admin_api",
    }
    await producer.send(TOPICS.COLLECTION_TRIGGER, task)

    return {
        "message": "Collection trigger sent",
        "task": task
    }


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _format_location(job: dict) -> str:
    parts = [p for p in [job.get("location_city"), job.get("location_state"), job.get("location_country")] if p]
    return ", ".join(parts) if parts else job.get("location_raw") or "Unknown"
