"""
Users router — user profile, saved searches, preferences, and job applications.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

from services.gateway.deps import get_current_user
from shared.database.session import get_db

logger = logging.getLogger(__name__)
router = APIRouter()


# ─── Schemas ──────────────────────────────────────────────────────────────────

class ProfileUpdate(BaseModel):
    full_name: str | None = None
    headline: str | None = None
    skills: list[str] | None = None
    experience_years: int | None = None
    preferred_locations: list[str] | None = None
    preferred_remote_type: str | None = None
    preferred_salary_min: float | None = None
    telegram_chat_id: str | None = None
    webhook_url: str | None = None


class SavedSearchCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    query: str = Field(default="")
    filters: dict[str, Any] = Field(default_factory=dict)
    alert_enabled: bool = True


class NotificationPreferences(BaseModel):
    email: bool = True
    in_app: bool = True
    telegram: bool = False
    webhook: bool = False
    alert_frequency: str = "instant"  # instant, daily, weekly


# ─── Profile Endpoints ────────────────────────────────────────────────────────

@router.get("/me")
async def get_profile(
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict[str, Any]:
    """Get the current user's full profile."""
    user_doc = await db.users.find_one({"_id": user["sub"]}, {"password_hash": 0})
    if not user_doc:
        raise HTTPException(status_code=404, detail="User not found")

    created_at = user_doc.get("created_at")
    last_login = user_doc.get("last_login")

    return {
        "id": str(user_doc["_id"]),
        "email": user_doc.get("email"),
        "full_name": user_doc.get("full_name"),
        "role": user_doc.get("role", "user"),
        "is_active": user_doc.get("is_active", True),
        "telegram_chat_id": user_doc.get("telegram_chat_id"),
        "webhook_url": user_doc.get("webhook_url"),
        "profile": user_doc.get("profile", {}),
        "notification_preferences": user_doc.get("notification_preferences", {}),
        "created_at": created_at.isoformat() if isinstance(created_at, datetime) else created_at,
        "last_login": last_login.isoformat() if isinstance(last_login, datetime) else last_login,
    }


@router.patch("/me")
async def update_profile(
    body: ProfileUpdate,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict[str, Any]:
    """Update the current user's profile."""
    update: dict[str, Any] = {"updated_at": datetime.now(timezone.utc)}

    if body.full_name is not None:
        update["full_name"] = body.full_name
    if body.telegram_chat_id is not None:
        update["telegram_chat_id"] = body.telegram_chat_id
    if body.webhook_url is not None:
        update["webhook_url"] = body.webhook_url

    # Nested profile fields
    profile_update: dict[str, Any] = {}
    if body.headline is not None:
        profile_update["profile.headline"] = body.headline
    if body.skills is not None:
        profile_update["profile.skills"] = body.skills
    if body.experience_years is not None:
        profile_update["profile.experience_years"] = body.experience_years
    if body.preferred_locations is not None:
        profile_update["profile.preferred_locations"] = body.preferred_locations
    if body.preferred_remote_type is not None:
        profile_update["profile.preferred_remote_type"] = body.preferred_remote_type
    if body.preferred_salary_min is not None:
        profile_update["profile.preferred_salary_min"] = body.preferred_salary_min

    update.update(profile_update)

    await db.users.update_one({"_id": user["sub"]}, {"$set": update})
    return {"message": "Profile updated successfully"}


@router.delete("/me")
async def deactivate_account(
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict[str, str]:
    """Deactivate the current user's account (soft delete)."""
    await db.users.update_one(
        {"_id": user["sub"]},
        {"$set": {"is_active": False, "updated_at": datetime.now(timezone.utc)}},
    )
    return {"message": "Account deactivated"}


# ─── Saved Searches ───────────────────────────────────────────────────────────

@router.get("/me/saved-searches")
async def list_saved_searches(
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict[str, Any]:
    """List all saved searches for the current user."""
    cursor = db.saved_searches.find({"user_id": user["sub"]}).sort("created_at", -1)
    searches = await cursor.to_list(length=50)

    results = []
    for s in searches:
        created_at = s.get("created_at")
        triggered_at = s.get("last_triggered_at")
        results.append({
            "id": str(s["_id"]),
            "name": s.get("name"),
            "query": s.get("query", ""),
            "filters": s.get("filters", {}),
            "alert_enabled": s.get("alert_enabled", True),
            "created_at": created_at.isoformat() if isinstance(created_at, datetime) else created_at,
            "last_triggered_at": triggered_at.isoformat() if isinstance(triggered_at, datetime) else triggered_at,
        })

    return {"saved_searches": results, "total": len(results)}


@router.post("/me/saved-searches", status_code=status.HTTP_201_CREATED)
async def create_saved_search(
    body: SavedSearchCreate,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict[str, Any]:
    """Create a new saved search with optional job alerts."""
    # Limit: 20 saved searches per user
    count = await db.saved_searches.count_documents({"user_id": user["sub"]})
    if count >= 20:
        raise HTTPException(status_code=400, detail="Maximum of 20 saved searches allowed")

    search_id = str(uuid.uuid4())
    doc = {
        "_id": search_id,
        "user_id": user["sub"],
        "name": body.name,
        "query": body.query,
        "filters": body.filters,
        "alert_enabled": body.alert_enabled,
        "created_at": datetime.now(timezone.utc),
        "last_triggered_at": None,
    }
    await db.saved_searches.insert_one(doc)

    return {"id": search_id, "message": "Saved search created", **body.model_dump()}


@router.patch("/me/saved-searches/{search_id}")
async def update_saved_search(
    search_id: str,
    body: SavedSearchCreate,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict[str, str]:
    """Update a saved search."""
    result = await db.saved_searches.update_one(
        {"_id": search_id, "user_id": user["sub"]},
        {"$set": {**body.model_dump(), "updated_at": datetime.now(timezone.utc)}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Saved search not found")
    return {"message": "Saved search updated"}


@router.delete("/me/saved-searches/{search_id}")
async def delete_saved_search(
    search_id: str,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict[str, str]:
    """Delete a saved search."""
    result = await db.saved_searches.delete_one({"_id": search_id, "user_id": user["sub"]})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Saved search not found")
    return {"message": "Saved search deleted"}


# ─── Notification Preferences ─────────────────────────────────────────────────

@router.get("/me/preferences")
async def get_preferences(
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict[str, Any]:
    """Get notification and display preferences."""
    user_doc = await db.users.find_one({"_id": user["sub"]}, {"notification_preferences": 1})
    if not user_doc:
        raise HTTPException(status_code=404, detail="User not found")
    return user_doc.get("notification_preferences", {})


@router.patch("/me/preferences")
async def update_preferences(
    body: NotificationPreferences,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict[str, str]:
    """Update notification preferences."""
    await db.users.update_one(
        {"_id": user["sub"]},
        {"$set": {
            "notification_preferences": body.model_dump(),
            "updated_at": datetime.now(timezone.utc),
        }},
    )
    return {"message": "Preferences updated"}


# ─── Application History ──────────────────────────────────────────────────────

@router.get("/me/applications")
async def get_application_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict[str, Any]:
    """Get the user's job application history (tracked via user events)."""
    filters = {"user_id": user["sub"], "event_type": "apply"}
    total = await db.user_events.count_documents(filters)
    skip = (page - 1) * page_size

    cursor = db.user_events.find(filters).sort("created_at", -1).skip(skip).limit(page_size)
    events = await cursor.to_list(length=page_size)

    results = []
    for e in events:
        created_at = e.get("created_at")
        results.append({
            "job_id": e.get("job_id"),
            "job_title": e.get("metadata", {}).get("title"),
            "company_name": e.get("metadata", {}).get("company"),
            "applied_at": created_at.isoformat() if isinstance(created_at, datetime) else created_at,
        })

    return {
        "applications": results,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/me/track")
async def track_event(
    job_id: str,
    event_type: str,  # view, apply, save, share
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict[str, str]:
    """Track a user interaction event (view/apply/save) for a job."""
    valid_events = {"view", "apply", "save", "unsave", "share"}
    if event_type not in valid_events:
        raise HTTPException(status_code=400, detail=f"Invalid event type. Must be one of: {valid_events}")

    job = await db.jobs.find_one({"_id": job_id}, {"title": 1, "company_name": 1})

    await db.user_events.insert_one({
        "_id": str(uuid.uuid4()),
        "user_id": user["sub"],
        "job_id": job_id,
        "event_type": event_type,
        "metadata": {
            "title": job.get("title") if job else None,
            "company": job.get("company_name") if job else None,
        },
        "created_at": datetime.now(timezone.utc),
    })

    return {"message": f"Event '{event_type}' tracked for job {job_id}"}
