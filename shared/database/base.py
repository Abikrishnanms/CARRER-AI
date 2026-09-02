"""
MongoDB collection schema definitions and index configuration.
Centralizes all collection setup for the jobplatform database.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# ─── Index Definitions ────────────────────────────────────────────────────────
# Format: {collection: [(index_spec, options), ...]}

INDEXES: dict[str, list[tuple[Any, dict]]] = {
    "jobs": [
        ([("source", 1), ("source_job_id", 1)], {"unique": True, "name": "source_job_unique"}),
        ([("status", 1), ("posted_at", -1)], {"name": "status_posted"}),
        ([("status", 1), ("is_duplicate", 1), ("quality_score", -1)], {"name": "published_quality"}),
        ([("title", "text"), ("description", "text"), ("company_name", "text")], {"name": "jobs_text"}),
        ([("remote_type", 1), ("experience_level", 1)], {"name": "remote_exp"}),
        ([("salary_min", 1), ("salary_max", 1)], {"sparse": True, "name": "salary_range"}),
        ([("location_city", 1), ("location_country", 1)], {"name": "location"}),
        ([("required_skills", 1)], {"name": "skills"}),
        ([("scam_probability", 1)], {"name": "scam_prob"}),
        ([("content_fingerprint", 1)], {"sparse": True, "name": "fingerprint"}),
        ([("collection_run_id", 1)], {"name": "collection_run"}),
        ([("created_at", -1)], {"name": "created_desc"}),
        ([("updated_at", -1)], {"name": "updated_desc"}),
    ],
    "companies": [
        ([("normalized_name", 1)], {"unique": True, "name": "company_name_unique"}),
        ([("domain", 1)], {"sparse": True, "name": "company_domain"}),
        ([("trust_score", -1)], {"name": "trust_score"}),
        ([("verification_status", 1)], {"name": "verification_status"}),
        ([("industry", 1)], {"name": "industry"}),
    ],
    "users": [
        ([("email", 1)], {"unique": True, "name": "user_email_unique"}),
        ([("role", 1)], {"name": "user_role"}),
        ([("created_at", -1)], {"name": "user_created"}),
        ([("is_active", 1)], {"name": "user_active"}),
    ],
    "saved_searches": [
        ([("user_id", 1), ("created_at", -1)], {"name": "user_searches"}),
        ([("user_id", 1), ("alert_enabled", 1)], {"name": "user_alerts"}),
    ],
    "notification_logs": [
        ([("user_id", 1), ("created_at", -1)], {"name": "user_notifications"}),
        ([("user_id", 1), ("read_at", 1)], {"name": "user_unread"}),
        ([("status", 1)], {"name": "notification_status"}),
        ([("created_at", -1)], {"name": "notification_date"}),
    ],
    "pipeline_events": [
        ([("job_id", 1), ("created_at", 1)], {"name": "job_events"}),
        ([("agent_name", 1), ("status", 1)], {"name": "agent_status"}),
        ([("created_at", -1)], {"name": "event_date", "expireAfterSeconds": 7 * 24 * 3600}),  # TTL: 7 days
    ],
    "user_events": [
        ([("user_id", 1), ("event_type", 1), ("created_at", -1)], {"name": "user_event_type"}),
        ([("job_id", 1), ("event_type", 1)], {"name": "job_events_type"}),
        ([("created_at", -1)], {"name": "event_date", "expireAfterSeconds": 90 * 24 * 3600}),  # TTL: 90 days
    ],
    "feedback_records": [
        ([("feedback_type", 1), ("created_at", -1)], {"name": "feedback_type_date"}),
        ([("job_id", 1)], {"name": "feedback_job"}),
        ([("user_id", 1)], {"name": "feedback_user"}),
    ],
    "analytics_cache": [
        ([("updated_at", -1)], {"name": "analytics_updated"}),
    ],
}


async def create_all_indexes(db: Any) -> dict[str, int]:
    """
    Create all defined indexes in MongoDB.
    Returns a dict of {collection: indexes_created}.
    Safely skips indexes that already exist.
    """
    results: dict[str, int] = {}

    for collection_name, index_list in INDEXES.items():
        created = 0
        collection = db[collection_name]

        for index_spec, options in index_list:
            try:
                # Fetch existing index names
                existing_indexes = await collection.index_information()
                index_name = options.get("name")

                if index_name and index_name in existing_indexes:
                    logger.debug(f"Index {index_name} already exists on {collection_name}")
                    continue

                await collection.create_index(index_spec, **options)
                created += 1
                logger.debug(f"Created index '{options.get('name', '?')}' on {collection_name}")

            except Exception as e:
                logger.warning(f"Failed to create index on {collection_name}: {e}")

        results[collection_name] = created
        if created:
            logger.info(f"Created {created} indexes on '{collection_name}'")

    return results


async def drop_all_collections(db: Any) -> None:
    """Drop all platform collections — USE WITH EXTREME CAUTION (testing only)."""
    collections = list(INDEXES.keys()) + ["analytics_cache"]
    for name in collections:
        await db[name].drop()
        logger.warning(f"Dropped collection: {name}")


# ─── Collection Validators ────────────────────────────────────────────────────

JOB_VALIDATOR = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["title", "company_name", "source", "status"],
        "properties": {
            "title": {"bsonType": "string", "minLength": 1},
            "company_name": {"bsonType": "string", "minLength": 1},
            "source": {"bsonType": "string"},
            "status": {
                "bsonType": "string",
                "enum": ["raw", "cleaned", "deduplicated", "enriched", "verified", "published", "rejected", "expired", "duplicate"],
            },
            "scam_probability": {"bsonType": ["double", "null"], "minimum": 0, "maximum": 1},
            "quality_score": {"bsonType": ["double", "null"], "minimum": 0, "maximum": 100},
        },
    }
}

USER_VALIDATOR = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["email", "password_hash"],
        "properties": {
            "email": {"bsonType": "string"},
            "role": {"bsonType": "string", "enum": ["user", "admin"]},
            "is_active": {"bsonType": "bool"},
        },
    }
}
