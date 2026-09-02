**DB Session — `shared/database/session.py` (Annotated copy)**

Summary: Motor-based MongoDB client singleton, FastAPI dependency, index initialization helper, and test utilities for dropping/closing the DB.

---

```python
"""
Async MongoDB session factory using Motor.
Provides client singleton, FastAPI dependencies, and full index initialization.
"""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncGenerator

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

logger = logging.getLogger(__name__)

MONGO_URI = os.getenv(
    "MONGO_URI",
    "mongodb://admin:admin123@localhost:27017/jobplatform?authSource=admin",
)

# Parse DB name from URI or fallback
db_name = "jobplatform"
try:
    _uri_path = MONGO_URI.split("?")[0]
    if "/" in _uri_path.replace("mongodb://", "").replace("mongodb+srv://", ""):
        _candidate = _uri_path.split("/")[-1]
        if _candidate:
            db_name = _candidate
except Exception:
    pass

# Global client singleton
_client: AsyncIOMotorClient | None = None


def get_mongo_client() -> AsyncIOMotorClient:
    """Get or create the global MongoDB client singleton."""
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(
            MONGO_URI,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000,
            maxPoolSize=50,
            minPoolSize=5,
        )
    return _client


async def get_db() -> AsyncGenerator[AsyncIOMotorDatabase, None]:
    """FastAPI dependency — yields a Motor database handle."""
    mongo_client = get_mongo_client()
    db = mongo_client[db_name]
    yield db


async def create_tables() -> None:
    """
    Initialize all MongoDB collections with indexes.
    Uses the comprehensive index definitions from shared.database.base.
    """
    mongo_client = get_mongo_client()
    db = mongo_client[db_name]

    try:
        from shared.database.base import create_all_indexes
        results = await create_all_indexes(db)
        total = sum(results.values())
        logger.info(f"Database initialized: {total} indexes created across {len(results)} collections")
    except ImportError:
        # Fallback minimal indexes if base module unavailable
        logger.warning("shared.database.base unavailable — using minimal indexes")
        await db.jobs.create_index([("source", 1), ("source_job_id", 1)], unique=True)
        await db.companies.create_index("normalized_name", unique=True, sparse=True)
        await db.users.create_index("email", unique=True)
        await db.notification_logs.create_index([("user_id", 1), ("created_at", -1)])
        await db.saved_searches.create_index([("user_id", 1)])
        await db.pipeline_events.create_index([("job_id", 1)])
    except Exception as e:
        logger.error(f"Index creation failed: {e}")


async def close_client() -> None:
    """Close the MongoDB client (call on service shutdown)."""
    global _client
    if _client is not None:
        _client.close()
        _client = None
        logger.info("MongoDB client closed")


async def drop_tables() -> None:
    """Drop all collections — ONLY for testing environments."""
    env = os.getenv("APP_ENV", "development")
    if env not in ("test", "development"):
        raise RuntimeError("drop_tables() is only allowed in test/development environments")
    mongo_client = get_mongo_client()
    await mongo_client.drop_database(db_name)
    logger.warning(f"Database '{db_name}' dropped")
```

---

Grouped explanations:

- `MONGO_URI` and `db_name`: reads from env and attempts to derive the DB name from the URI; falls back to `jobplatform`.
- `_client` singleton: ensures a single `AsyncIOMotorClient` is reused across the process to avoid connection storms.
- `get_mongo_client()`: builds the Motor client with connection timeouts and pool sizing tuned for service workloads.
- `get_db()`: FastAPI dependency that yields a DB handle for route handlers.
- `create_tables()`: preferred index initialization path uses `shared.database.base.create_all_indexes(db)`; falls back to a minimal set of useful indexes if that module is missing.
- `close_client()` and `drop_tables()`: lifecycle helpers for graceful shutdown and test cleanup (drop guarded by `APP_ENV`).

Notes / Next steps:
- The `create_tables()` helper delegates to `shared.database.base` for comprehensive index management; if you want, I can open that file next to document all index choices.
- Next planned docs: `shared/kafka/producer.py` and `shared/kafka/consumer.py` to explain Kafka wrappers. Proceed? 
