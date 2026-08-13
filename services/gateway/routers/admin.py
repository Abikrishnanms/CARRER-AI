"""
Admin router — system management, pipeline control, user management, and reporting.
Requires admin role for all endpoints.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel

from services.gateway.deps import get_current_user, require_admin
from shared.database.session import get_db

logger = logging.getLogger(__name__)
router = APIRouter()


# ─── Schemas ──────────────────────────────────────────────────────────────────

class CollectionTrigger(BaseModel):
    sources: list[str] = ["adzuna", "greenhouse", "indeed", "rss"]
    search_terms: list[str] = ["software engineer", "data scientist", "python developer"]
    location: str | None = None
    limit: int = 500


class JobStatusUpdate(BaseModel):
    status: str  # published, rejected, expired
    reason: str | None = None


class UserRoleUpdate(BaseModel):
    role: str  # user, admin


# ─── System Overview ──────────────────────────────────────────────────────────

@router.get("/stats")
async def admin_stats(
    db: AsyncIOMotorDatabase = Depends(get_db),
    _: Any = Depends(require_admin),
) -> dict[str, Any]:
    """
    Full system statistics for admin dashboard.
    """
    # Job counts by status
    job_statuses = ["raw", "cleaned", "deduplicated", "enriched", "verified", "published", "rejected", "duplicate"]
    job_counts: dict[str, int] = {}
    for s in job_statuses:
        job_counts[s] = await db.jobs.count_documents({"status": s})

    # User stats
    total_users = await db.users.count_documents({})
    active_users = await db.users.count_documents({"is_active": True})
    admin_users = await db.users.count_documents({"role": "admin"})

    # Notification stats
    total_notifications = await db.notification_logs.count_documents({})
    pending_notifications = await db.notification_logs.count_documents({"status": "pending"})

    # Pipeline events last 24h
    cutoff = datetime.utcnow() - timedelta(hours=24)
    events_24h = await db.pipeline_events.count_documents({"created_at": {"$gte": cutoff}})
    failed_events = await db.pipeline_events.count_documents(
        {"created_at": {"$gte": cutoff}, "status": "failed"}
    )

    # Scam stats
    scam_rejected = await db.jobs.count_documents({"status": "rejected"})
    high_risk = await db.jobs.count_documents({"scam_probability": {"$gte": 0.4}})

    # Avg quality score of published jobs
    pipeline = [
        {"$match": {"status": "published"}},
        {"$group": {"_id": None, "avg_quality": {"$avg": "$quality_score"}}},
    ]
    quality_cursor = db.jobs.aggregate(pipeline)
    quality_raw = await quality_cursor.to_list(length=1)
    avg_quality = round((quality_raw[0].get("avg_quality") or 0) if quality_raw else 0, 1)

    return {
        "jobs": {**job_counts, "avg_quality_score": avg_quality},
        "users": {
            "total": total_users,
            "active": active_users,
            "admins": admin_users,
        },
        "notifications": {
            "total": total_notifications,
            "pending": pending_notifications,
        },
        "pipeline": {
            "events_24h": events_24h,
            "failed_24h": failed_events,
        },
        "trust": {
            "scam_rejected": scam_rejected,
            "high_risk_flagged": high_risk,
        },
        "generated_at": datetime.utcnow().isoformat(),
    }


# ─── Collection Control ───────────────────────────────────────────────────────

@router.post("/collect")
async def trigger_collection(
    body: CollectionTrigger,
    _: Any = Depends(require_admin),
) -> dict[str, Any]:
    """Manually trigger a job collection run across specified sources."""
    try:
        from shared.kafka.producer import get_producer
        from shared.kafka.topics import TOPICS

        producer = await get_producer()
        task = {
            "task_id": str(uuid.uuid4()),
            "sources": body.sources,
            "search_terms": body.search_terms,
            "location": body.location,
            "limit": body.limit,
            "triggered_by": "admin_api",
            "triggered_at": datetime.utcnow().isoformat(),
        }
        await producer.send(TOPICS.COLLECTION_TRIGGER, task)
        logger.info(f"Admin triggered collection: sources={body.sources}")

        return {
            "message": "Collection trigger sent successfully",
            "task": task,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to trigger collection: {e}")


# ─── Pipeline Management ──────────────────────────────────────────────────────

@router.get("/pipeline")
async def get_pipeline_details(
    limit: int = Query(50, ge=1, le=200),
    since_hours: int = Query(24, ge=1, le=168),
    db: AsyncIOMotorDatabase = Depends(get_db),
    _: Any = Depends(require_admin),
) -> dict[str, Any]:
    """Get detailed pipeline event log for monitoring."""
    cutoff = datetime.utcnow() - timedelta(hours=since_hours)

    cursor = (
        db.pipeline_events.find({"created_at": {"$gte": cutoff}})
        .sort("created_at", -1)
        .limit(limit)
    )
    events = await cursor.to_list(length=limit)

    results = []
    for e in events:
        created_at = e.get("created_at")
        results.append({
            "id": str(e.get("_id", "")),
            "job_id": e.get("job_id"),
            "event_type": e.get("event_type"),
            "agent": e.get("agent_name"),
            "status": e.get("status"),
            "duration_ms": e.get("duration_ms"),
            "payload": e.get("payload", {}),
            "error": e.get("error_message"),
            "created_at": created_at.isoformat() if isinstance(created_at, datetime) else created_at,
        })

    # Failure rate
    total = await db.pipeline_events.count_documents({"created_at": {"$gte": cutoff}})
    failed = await db.pipeline_events.count_documents({"created_at": {"$gte": cutoff}, "status": "failed"})

    return {
        "events": results,
        "total_in_window": total,
        "failures": failed,
        "failure_rate": round((failed / max(total, 1)) * 100, 1),
        "window_hours": since_hours,
    }


# ─── Job Management ───────────────────────────────────────────────────────────

@router.patch("/jobs/{job_id}/status")
async def update_job_status(
    job_id: str,
    body: JobStatusUpdate,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _: Any = Depends(require_admin),
) -> dict[str, str]:
    """Manually override a job's status (e.g., force-reject a scam)."""
    valid_statuses = {"published", "rejected", "expired", "pending_review"}
    if body.status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Must be one of: {valid_statuses}",
        )

    result = await db.jobs.update_one(
        {"_id": job_id},
        {"$set": {
            "status": body.status,
            "admin_override": True,
            "admin_override_reason": body.reason,
            "updated_at": datetime.utcnow(),
        }},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Job not found")

    # Log admin action
    await db.pipeline_events.insert_one({
        "_id": str(uuid.uuid4()),
        "job_id": job_id,
        "event_type": "admin.status_override",
        "agent_name": "admin",
        "status": body.status,
        "payload": {"reason": body.reason},
        "created_at": datetime.utcnow(),
    })

    logger.info(f"Admin updated job {job_id} status to {body.status}")
    return {"message": f"Job {job_id} status updated to '{body.status}'"}


@router.get("/jobs/scam-reports")
async def get_scam_reports(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    min_probability: float = Query(0.4, ge=0, le=1),
    db: AsyncIOMotorDatabase = Depends(get_db),
    _: Any = Depends(require_admin),
) -> dict[str, Any]:
    """Get jobs flagged as potential scams for admin review."""
    filters = {
        "scam_probability": {"$gte": min_probability},
        "status": {"$in": ["published", "rejected"]},
    }

    total = await db.jobs.count_documents(filters)
    skip = (page - 1) * page_size
    cursor = db.jobs.find(filters).sort("scam_probability", -1).skip(skip).limit(page_size)
    jobs = await cursor.to_list(length=page_size)

    results = []
    for job in jobs:
        created_at = job.get("created_at")
        results.append({
            "id": str(job.get("_id")),
            "title": job.get("title"),
            "company_name": job.get("company_name"),
            "source": job.get("source"),
            "scam_probability": job.get("scam_probability", 0),
            "scam_risk_level": job.get("scam_risk_level"),
            "triggered_rules": job.get("scam_triggered_rules", []),
            "status": job.get("status"),
            "apply_url": job.get("apply_url"),
            "created_at": created_at.isoformat() if isinstance(created_at, datetime) else created_at,
        })

    return {
        "scam_flagged": results,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


# ─── User Management ─────────────────────────────────────────────────────────

@router.get("/users")
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
    db: AsyncIOMotorDatabase = Depends(get_db),
    _: Any = Depends(require_admin),
) -> dict[str, Any]:
    """List all users (admin only)."""
    filters: dict[str, Any] = {}
    if search:
        filters["$or"] = [
            {"email": {"$regex": search, "$options": "i"}},
            {"full_name": {"$regex": search, "$options": "i"}},
        ]

    total = await db.users.count_documents(filters)
    skip = (page - 1) * page_size

    cursor = (
        db.users.find(filters, {"password_hash": 0})
        .sort("created_at", -1)
        .skip(skip)
        .limit(page_size)
    )
    users = await cursor.to_list(length=page_size)

    results = []
    for u in users:
        created_at = u.get("created_at")
        last_login = u.get("last_login")
        results.append({
            "id": str(u["_id"]),
            "email": u.get("email"),
            "full_name": u.get("full_name"),
            "role": u.get("role", "user"),
            "is_active": u.get("is_active", True),
            "created_at": created_at.isoformat() if isinstance(created_at, datetime) else created_at,
            "last_login": last_login.isoformat() if isinstance(last_login, datetime) else last_login,
        })

    return {"users": results, "total": total, "page": page, "page_size": page_size}


@router.patch("/users/{user_id}/role")
async def update_user_role(
    user_id: str,
    body: UserRoleUpdate,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _: Any = Depends(require_admin),
) -> dict[str, str]:
    """Update a user's role."""
    if body.role not in ("user", "admin"):
        raise HTTPException(status_code=400, detail="Role must be 'user' or 'admin'")

    result = await db.users.update_one(
        {"_id": user_id},
        {"$set": {"role": body.role, "updated_at": datetime.utcnow()}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")

    return {"message": f"User {user_id} role updated to '{body.role}'"}


@router.delete("/users/{user_id}")
async def deactivate_user(
    user_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _: Any = Depends(require_admin),
) -> dict[str, str]:
    """Deactivate a user account (admin override)."""
    result = await db.users.update_one(
        {"_id": user_id},
        {"$set": {"is_active": False, "updated_at": datetime.utcnow()}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")

    return {"message": f"User {user_id} deactivated"}
