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

    from shared.database.base import create_all_indexes
    try:
        results = await create_all_indexes(db)
        total = sum(results.values())
        logger.info(f"Database initialized: {total} indexes created across {len(results)} collections")
    except Exception as e:
        logger.error(f"Index creation failed: {e}")
        if os.getenv("APP_ENV") == "production":
            raise RuntimeError(f"Critical failure creating database indexes: {e}") from e


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
