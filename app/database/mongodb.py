"""
MongoDB connection manager and client wrapper.
Handles connection, indexing, and health checks.
"""

from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.config.settings import settings
from app.utils.logging import get_logger

logger = get_logger(__name__)


class MongoDBClient:
    """
    MongoDB client wrapper with connection management.
    Singleton pattern to reuse connections.
    """

    _instance: Optional["MongoDBClient"] = None
    _client: Optional[AsyncIOMotorClient] = None
    _db: Optional[AsyncIOMotorDatabase] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def connect(self) -> None:
        """Connect to MongoDB and create indexes."""
        if self._client is not None:
            return

        try:
            self._client = AsyncIOMotorClient(
                settings.mongo_uri,
                maxPoolSize=20,
                minPoolSize=5,
                maxIdleTimeMS=60000,
                serverSelectionTimeoutMS=5000,
            )
            self._db = self._client[settings.mongo_db]

            # Test connection
            await self._client.admin.command("ping")
            logger.info(f"✅ Connected to MongoDB: {settings.mongo_db}")

            # Create indexes
            await self._create_indexes()

        except Exception as e:
            logger.error(f"❌ Failed to connect to MongoDB: {e}")
            raise

    async def _create_indexes(self) -> None:
        """Create necessary indexes for collections."""
        if self._db is None:
            raise RuntimeError("Database not initialized")

        # Jobs collection indexes
        jobs_collection = self._db["jobs"]

        # Unique index on job_id
        await jobs_collection.create_index("job_id", unique=True)

        # Compound index for duplicate detection
        await jobs_collection.create_index(
            [
                ("raw.title", 1),
                ("raw.company.name", 1),
                ("raw.source_platform", 1),
            ]
        )

        # Index for filtering
        await jobs_collection.create_index("pipeline_stage")
        await jobs_collection.create_index("created_at")

        # Companies collection indexes
        companies_collection = self._db["companies"]
        await companies_collection.create_index("name", unique=True)
        await companies_collection.create_index("ats_type")
        await companies_collection.create_index("is_active")

        logger.info("✅ MongoDB indexes created")

    @property
    def db(self) -> AsyncIOMotorDatabase:
        """Get the database instance."""
        if self._db is None:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self._db

    @property
    def client(self) -> AsyncIOMotorClient:
        """Get the client instance."""
        if self._client is None:
            raise RuntimeError("Client not connected. Call connect() first.")
        return self._client

    async def close(self) -> None:
        """Close the MongoDB connection."""
        if self._client is not None:
            self._client.close()
            logger.info("MongoDB connection closed")

    async def health_check(self) -> bool:
        """Check if MongoDB is healthy."""
        try:
            await self.client.admin.command("ping")
            return True
        except Exception:
            return False


# Global instance
mongodb = MongoDBClient()