"""
Deduplicator Service — Duplicate Detection Agent.
Consumes from Kafka topic: job.cleaned
Publishes to Kafka topic: job.deduplicated
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
import uuid
from datetime import datetime
from typing import Any

from shared.kafka.consumer import KafkaConsumerClient
from shared.kafka.producer import KafkaProducerClient
from shared.kafka.topics import TOPICS
from shared.database.session import get_mongo_client

logger = logging.getLogger(__name__)


def generate_fingerprint(title: str, company: str, location: str | None) -> str:
    """Generate a content-based fingerprint for similarity matching."""
    normalized = f"{title.lower().strip()}|{company.lower().strip()}|{(location or '').lower().strip()}"
    return hashlib.sha256(normalized.encode()).hexdigest()


class DeduplicatorService:
    """
    Duplicate Detection Agent.
    - Checks source_job_id uniqueness (exact duplicate)
    - Generates content fingerprints (near-duplicate)
    - Marks duplicates in MongoDB
    - Only passes unique jobs downstream
    """

    def __init__(self) -> None:
        self.producer = KafkaProducerClient()
        self.consumer = KafkaConsumerClient(
            topics=[TOPICS.JOB_CLEANED],
            group_id="deduplicator-service",
        )
        self.running = False

    async def start(self) -> None:
        await self.producer.start()
        await self.consumer.start()
        self.running = True
        logger.info("🔍 Deduplicator service started")
        await self.consumer.consume(self._handle_message)

    async def stop(self) -> None:
        self.running = False
        await self.producer.stop()
        await self.consumer.stop()

    async def _handle_message(self, message: dict, *args) -> None:
        start = time.monotonic()
        job_id = message.get("_id", message.get("id", str(uuid.uuid4())))
        source = message.get("source", "")
        source_job_id = message.get("source_job_id", "")

        try:
            client = get_mongo_client()
            db = client["jobplatform"]

            # Check 1: Exact duplicate by source + source_job_id
            existing = await db.jobs.find_one({
                "source": source,
                "source_job_id": source_job_id,
                "_id": {"$ne": job_id},
            })

            is_duplicate = False
            duplicate_of = None

            if existing:
                is_duplicate = True
                duplicate_of = str(existing["_id"])
                logger.info(f"Exact duplicate found: {job_id} duplicates {duplicate_of}")
            else:
                # Check 2: Content fingerprint (near-duplicate)
                fingerprint = generate_fingerprint(
                    message.get("title", ""),
                    message.get("company_name", ""),
                    message.get("location_city"),
                )
                near_match = await db.jobs.find_one({
                    "content_fingerprint": fingerprint,
                    "_id": {"$ne": job_id},
                })
                if near_match:
                    is_duplicate = True
                    duplicate_of = str(near_match["_id"])
                    logger.info(f"Near-duplicate found: {job_id} ~ {duplicate_of}")

                # Store the fingerprint for future checks
                message["content_fingerprint"] = fingerprint

            # Update MongoDB
            message["is_duplicate"] = is_duplicate
            message["duplicate_of_id"] = duplicate_of
            message["status"] = "deduplicated" if not is_duplicate else "duplicate"

            await db.jobs.update_one(
                {"_id": job_id},
                {"$set": message},
                upsert=True,
            )

            # Log pipeline event
            duration_ms = (time.monotonic() - start) * 1000
            await db.pipeline_events.insert_one({
                "_id": str(uuid.uuid4()),
                "job_id": job_id,
                "event_type": "job.deduplicated",
                "agent_name": "deduplicator",
                "status": "duplicate" if is_duplicate else "unique",
                "payload": {"duplicate_of": duplicate_of} if is_duplicate else {},
                "duration_ms": duration_ms,
                "created_at": datetime.utcnow(),
            })

            # Only pass unique jobs downstream
            if not is_duplicate:
                await self.producer.send(TOPICS.JOB_DEDUPLICATED, message, key=job_id)
                logger.debug(f"Unique job {job_id} passed to enrichment")

        except Exception as e:
            logger.exception(f"Deduplication failed for {job_id}: {e}")


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    service = DeduplicatorService()
    try:
        await service.start()
    except KeyboardInterrupt:
        await service.stop()


if __name__ == "__main__":
    asyncio.run(main())
