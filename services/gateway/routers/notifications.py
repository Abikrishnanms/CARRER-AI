"""
Notifications router — in-app notification log, preferences, mark-read.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from services.gateway.deps import get_current_user
from shared.database.session import get_db

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("")
async def list_notifications(
    unread_only: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict[str, Any]:
    """
    Get the current user's notification log.
    Ordered by newest first.
    """
    filters: dict[str, Any] = {"user_id": user["sub"]}
    if unread_only:
        filters["read_at"] = None

    total = await db.notification_logs.count_documents(filters)
    skip = (page - 1) * page_size

    cursor = (
        db.notification_logs.find(filters)
        .sort("created_at", -1)
        .skip(skip)
        .limit(page_size)
    )
    notifications = await cursor.to_list(length=page_size)

    results = []
    for n in notifications:
        created_at = n.get("created_at")
        sent_at = n.get("sent_at")
        read_at = n.get("read_at")
        results.append({
            "id": str(n["_id"]),
            "channel": n.get("channel"),
            "subject": n.get("subject"),
            "template_id": n.get("template_id"),
            "status": n.get("status"),
            "is_read": bool(n.get("read_at")),
            "job_id": n.get("job_id"),
            "created_at": created_at.isoformat() if isinstance(created_at, datetime) else created_at,
            "sent_at": sent_at.isoformat() if isinstance(sent_at, datetime) else sent_at,
            "read_at": read_at.isoformat() if isinstance(read_at, datetime) else read_at,
        })

    unread_count = await db.notification_logs.count_documents(
        {"user_id": user["sub"], "read_at": None}
    )

    return {
        "notifications": results,
        "total": total,
        "unread_count": unread_count,
        "page": page,
        "page_size": page_size,
    }


@router.patch("/{notification_id}/read")
async def mark_notification_read(
    notification_id: str,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict[str, str]:
    """Mark a single notification as read."""
    result = await db.notification_logs.update_one(
        {"_id": notification_id, "user_id": user["sub"]},
        {"$set": {"read_at": datetime.utcnow()}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"message": "Marked as read"}


@router.post("/read-all")
async def mark_all_read(
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict[str, Any]:
    """Mark all unread notifications as read."""
    result = await db.notification_logs.update_many(
        {"user_id": user["sub"], "read_at": None},
        {"$set": {"read_at": datetime.utcnow()}},
    )
    return {"message": f"Marked {result.modified_count} notifications as read"}


@router.delete("/{notification_id}")
async def delete_notification(
    notification_id: str,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict[str, str]:
    """Delete a notification."""
    result = await db.notification_logs.delete_one(
        {"_id": notification_id, "user_id": user["sub"]}
    )
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"message": "Notification deleted"}


@router.delete("")
async def clear_all_notifications(
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict[str, Any]:
    """Clear all notifications for the current user."""
    result = await db.notification_logs.delete_many({"user_id": user["sub"]})
    return {"message": f"Deleted {result.deleted_count} notifications"}


@router.get("/stats")
async def notification_stats(
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict[str, Any]:
    """Get notification statistics for the current user."""
    total = await db.notification_logs.count_documents({"user_id": user["sub"]})
    unread = await db.notification_logs.count_documents(
        {"user_id": user["sub"], "read_at": None}
    )

    # Channel breakdown
    pipeline = [
        {"$match": {"user_id": user["sub"]}},
        {"$group": {"_id": "$channel", "count": {"$sum": 1}}},
    ]
    channel_cursor = db.notification_logs.aggregate(pipeline)
    channel_result = await channel_cursor.to_list(length=10)
    by_channel = {r["_id"]: r["count"] for r in channel_result}

    return {
        "total": total,
        "unread": unread,
        "by_channel": by_channel,
    }
