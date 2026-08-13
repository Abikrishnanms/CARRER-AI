"""
Embedder Service — Vector Embedding Generator.
Consumes from Kafka topic: job.verified
Generates embeddings with SentenceTransformers, uploads to Qdrant,
updates MongoDB with embedding_id, and sets status to "published".
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
import uuid
from datetime import datetime
from typing import Any

from shared.kafka.consumer import KafkaConsumerClient
from shared.kafka.topics import TOPICS
from shared.database.session import get_mongo_client

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION_JOBS", "job_embeddings")
VECTOR_SIZE = 384  # all-MiniLM-L6-v2 produces 384-dim vectors


class EmbedderService:
    """
    Embedding Generator Agent.
    - Loads SentenceTransformer model
    - Generates dense embeddings for job title + description + skills
    - Upserts the vector into Qdrant
    - Updates MongoDB with embedding_id and sets status = "published"
    """

    def __init__(self) -> None:
        self.consumer = KafkaConsumerClient(
            topics=[TOPICS.JOB_VERIFIED],
            group_id="embedder-service",
        )
        self.model = None
        self.qdrant_client = None
        self.running = False

    async def start(self) -> None:
        # Load embedding model
        try:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(EMBEDDING_MODEL)
            logger.info(f"Loaded embedding model: {EMBEDDING_MODEL}")
        except ImportError:
            logger.warning("sentence-transformers not installed — embedder will skip vectorization")

        # Connect to Qdrant
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.models import Distance, VectorParams

            self.qdrant_client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)

            # Ensure collection exists
            collections = self.qdrant_client.get_collections().collections
            existing_names = [c.name for c in collections]
            if QDRANT_COLLECTION not in existing_names:
                self.qdrant_client.create_collection(
                    collection_name=QDRANT_COLLECTION,
                    vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
                )
                logger.info(f"Created Qdrant collection: {QDRANT_COLLECTION}")
        except Exception as e:
            logger.warning(f"Qdrant not available: {e} — embeddings will be stored but not indexed")

        await self.consumer.start()
        self.running = True
        logger.info("🧬 Embedder service started")
        await self.consumer.consume(self._handle_message)

    async def stop(self) -> None:
        self.running = False
        await self.consumer.stop()

    async def _handle_message(self, message: dict, *args) -> None:
        start = time.monotonic()
        job_id = message.get("_id", message.get("id", str(uuid.uuid4())))

        try:
            # Build text for embedding
            title = message.get("title", "")
            description = message.get("description", "")[:1000]  # Limit description length
            skills = " ".join(message.get("required_skills", []))
            company = message.get("company_name", "")
            location = message.get("location_city", "") or ""

            embed_text = f"{title}. {company}. {location}. Skills: {skills}. {description}"

            embedding_id = str(uuid.uuid4())

            # Generate embedding
            if self.model:
                vector = self.model.encode(embed_text).tolist()

                # Upload to Qdrant
                if self.qdrant_client:
                    from qdrant_client.models import PointStruct
                    self.qdrant_client.upsert(
                        collection_name=QDRANT_COLLECTION,
                        points=[
                            PointStruct(
                                id=embedding_id,
                                vector=vector,
                                payload={
                                    "job_id": job_id,
                                    "title": title,
                                    "company_name": company,
                                    "location": location,
                                    "remote_type": message.get("remote_type", "unknown"),
                                    "experience_level": message.get("experience_level", "unknown"),
                                    "job_type": message.get("job_type", "unknown"),
                                    "salary_min": message.get("salary_min"),
                                    "salary_max": message.get("salary_max"),
                                },
                            )
                        ],
                    )

            # Update MongoDB: mark as published
            client = get_mongo_client()
            db = client["jobplatform"]
            await db.jobs.update_one(
                {"_id": job_id},
                {"$set": {
                    "embedding_id": embedding_id,
                    "embedding_model": EMBEDDING_MODEL,
                    "status": "published",
                    "updated_at": datetime.utcnow(),
                }},
            )

            # Log pipeline event
            duration_ms = (time.monotonic() - start) * 1000
            await db.pipeline_events.insert_one({
                "_id": str(uuid.uuid4()),
                "job_id": job_id,
                "event_type": "job.embedded",
                "agent_name": "embedder",
                "status": "success",
                "payload": {"embedding_id": embedding_id, "model": EMBEDDING_MODEL},
                "duration_ms": duration_ms,
                "created_at": datetime.utcnow(),
            })

            logger.debug(f"Embedded job {job_id} in {duration_ms:.1f}ms")

        except Exception as e:
            logger.exception(f"Embedding failed for {job_id}: {e}")
            # Still mark as published even without embedding
            try:
                client = get_mongo_client()
                db = client["jobplatform"]
                await db.jobs.update_one(
                    {"_id": job_id},
                    {"$set": {"status": "published", "updated_at": datetime.utcnow()}},
                )
            except Exception:
                pass


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    service = EmbedderService()
    try:
        await service.start()
    except KeyboardInterrupt:
        await service.stop()


if __name__ == "__main__":
    asyncio.run(main())
