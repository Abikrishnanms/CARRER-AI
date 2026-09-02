"""
Analytics router — job market trends, salary benchmarks, skill demand, company stats.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from shared.database.session import get_db

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/overview")
async def get_overview(
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict[str, Any]:
    """
    High-level platform statistics — public endpoint.
    Returns total jobs, companies, verified count, etc.
    """
    total_jobs = await db.jobs.count_documents({"status": "published"})
    total_companies = await db.companies.count_documents({})
    verified_jobs = await db.jobs.count_documents({"status": "published", "is_verified": True})
    remote_jobs = await db.jobs.count_documents({"status": "published", "remote_type": "remote"})

    cutoff_24h = datetime.now(timezone.utc) - timedelta(hours=24)
    new_today = await db.jobs.count_documents({"created_at": {"$gte": cutoff_24h}})

    return {
        "total_jobs": total_jobs,
        "new_today": new_today,
        "verified_jobs": verified_jobs,
        "remote_jobs": remote_jobs,
        "total_companies": total_companies,
        "platform_trust_rate": round((verified_jobs / max(total_jobs, 1)) * 100, 1),
    }


@router.get("/trends")
async def get_trends(
    days: int = Query(30, ge=7, le=180),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict[str, Any]:
    """
    Job posting volume trend over the last N days.
    Returns daily counts grouped by date.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    pipeline = [
        {"$match": {"created_at": {"$gte": cutoff}, "status": "published"}},
        {
            "$group": {
                "_id": {
                    "year": {"$year": "$created_at"},
                    "month": {"$month": "$created_at"},
                    "day": {"$dayOfMonth": "$created_at"},
                },
                "count": {"$sum": 1},
            }
        },
        {"$sort": {"_id.year": 1, "_id.month": 1, "_id.day": 1}},
    ]

    cursor = db.jobs.aggregate(pipeline)
    raw = await cursor.to_list(length=days + 5)

    data = [
        {
            "date": f"{r['_id']['year']:04d}-{r['_id']['month']:02d}-{r['_id']['day']:02d}",
            "count": r["count"],
        }
        for r in raw
    ]

    # By source breakdown
    source_pipeline = [
        {"$match": {"created_at": {"$gte": cutoff}, "status": "published"}},
        {"$group": {"_id": "$source", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    source_cursor = db.jobs.aggregate(source_pipeline)
    sources_raw = await source_cursor.to_list(length=20)
    by_source = {r["_id"]: r["count"] for r in sources_raw if r.get("_id")}

    return {
        "period_days": days,
        "daily_counts": data,
        "by_source": by_source,
        "total": sum(d["count"] for d in data),
    }


@router.get("/salary-benchmarks")
async def get_salary_benchmarks(
    role: str | None = Query(None, description="Filter by job title keyword"),
    location: str | None = Query(None, description="Filter by city or country"),
    experience: str | None = Query(None, description="entry, mid, senior, lead"),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict[str, Any]:
    """
    Salary benchmark statistics aggregated by experience level.
    Only includes jobs with salary data.
    """
    match: dict[str, Any] = {
        "status": "published",
        "salary_min": {"$exists": True, "$ne": None},
        "salary_max": {"$exists": True, "$ne": None},
    }

    if role:
        match["title"] = {"$regex": role, "$options": "i"}
    if location:
        match["$or"] = [
            {"location_city": {"$regex": location, "$options": "i"}},
            {"location_country": {"$regex": location, "$options": "i"}},
        ]
    if experience:
        match["experience_level"] = experience

    pipeline = [
        {"$match": match},
        {
            "$group": {
                "_id": "$experience_level",
                "avg_min": {"$avg": "$salary_min"},
                "avg_max": {"$avg": "$salary_max"},
                "median_min": {"$avg": "$salary_min"},  # Simplified; use $percentile in MongoDB 7+
                "count": {"$sum": 1},
                "p25_min": {"$min": "$salary_min"},
                "p75_max": {"$max": "$salary_max"},
            }
        },
        {"$sort": {"_id": 1}},
    ]

    cursor = db.jobs.aggregate(pipeline)
    raw = await cursor.to_list(length=20)

    benchmarks = []
    for r in raw:
        benchmarks.append({
            "experience_level": r["_id"],
            "avg_salary_min": round(r.get("avg_min") or 0),
            "avg_salary_max": round(r.get("avg_max") or 0),
            "sample_count": r["count"],
            "currency": "INR",
            "period": "yearly",
        })

    return {
        "filters": {"role": role, "location": location, "experience": experience},
        "benchmarks": benchmarks,
        "currency": "INR",
    }


@router.get("/skill-demand")
async def get_skill_demand(
    limit: int = Query(30, ge=5, le=100),
    days: int = Query(30, ge=7, le=180),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict[str, Any]:
    """
    Most in-demand skills ranked by frequency across job postings.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    pipeline = [
        {"$match": {"created_at": {"$gte": cutoff}, "status": "published"}},
        {"$unwind": "$required_skills"},
        {"$group": {"_id": "$required_skills", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": limit},
    ]

    cursor = db.jobs.aggregate(pipeline)
    raw = await cursor.to_list(length=limit)
    total_jobs = await db.jobs.count_documents({"created_at": {"$gte": cutoff}, "status": "published"})

    skills = [
        {
            "skill": r["_id"],
            "job_count": r["count"],
            "demand_rate": round((r["count"] / max(total_jobs, 1)) * 100, 1),
        }
        for r in raw
        if r.get("_id")
    ]

    return {
        "period_days": days,
        "total_jobs_analyzed": total_jobs,
        "top_skills": skills,
    }


@router.get("/remote-breakdown")
async def get_remote_breakdown(
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict[str, Any]:
    """Breakdown of remote vs hybrid vs on-site job postings."""
    pipeline = [
        {"$match": {"status": "published"}},
        {"$group": {"_id": "$remote_type", "count": {"$sum": 1}}},
    ]
    cursor = db.jobs.aggregate(pipeline)
    raw = await cursor.to_list(length=10)
    total = sum(r["count"] for r in raw)

    breakdown = {
        r["_id"]: {
            "count": r["count"],
            "percentage": round((r["count"] / max(total, 1)) * 100, 1),
        }
        for r in raw
        if r.get("_id")
    }

    return {"total": total, "breakdown": breakdown}


@router.get("/top-companies")
async def get_top_companies(
    limit: int = Query(10, ge=5, le=50),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict[str, Any]:
    """Top hiring companies by job count."""
    pipeline = [
        {"$match": {"status": "published"}},
        {
            "$group": {
                "_id": "$company_name",
                "job_count": {"$sum": 1},
                "avg_quality": {"$avg": "$quality_score"},
            }
        },
        {"$sort": {"job_count": -1}},
        {"$limit": limit},
    ]
    cursor = db.jobs.aggregate(pipeline)
    raw = await cursor.to_list(length=limit)

    companies = [
        {
            "company_name": r["_id"],
            "job_count": r["job_count"],
            "avg_quality_score": round(r.get("avg_quality") or 0, 1),
        }
        for r in raw
        if r.get("_id")
    ]

    return {"top_companies": companies}


@router.get("/pipeline-stats")
async def get_pipeline_stats(
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict[str, Any]:
    """Internal pipeline stats — jobs at each processing stage."""
    stages = ["raw", "cleaned", "deduplicated", "enriched", "verified", "published", "rejected"]
    counts: dict[str, int] = {}
    for stage in stages:
        counts[stage] = await db.jobs.count_documents({"status": stage})

    # Recent pipeline events (last 1h)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
    recent_events = await db.pipeline_events.count_documents({"created_at": {"$gte": cutoff}})

    # Average processing times per stage
    duration_pipeline = [
        {"$match": {"created_at": {"$gte": datetime.now(timezone.utc) - timedelta(hours=24)}}},
        {"$group": {"_id": "$agent_name", "avg_duration_ms": {"$avg": "$duration_ms"}}},
    ]
    duration_cursor = db.pipeline_events.aggregate(duration_pipeline)
    duration_raw = await duration_cursor.to_list(length=20)
    avg_durations = {r["_id"]: round(r.get("avg_duration_ms") or 0, 1) for r in duration_raw if r.get("_id")}

    return {
        "jobs_by_status": counts,
        "events_last_hour": recent_events,
        "avg_processing_time_ms": avg_durations,
        "total_jobs": sum(counts.values()),
    }
