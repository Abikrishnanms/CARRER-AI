"""
Orchestrator Service — Master workflow coordinator.
Manages the full job pipeline, handles failures, and provides system-wide control.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timedelta
from typing import Any

from shared.database.session import get_mongo_client
from shared.kafka.producer import KafkaProducerClient
from shared.kafka.topics import TOPICS
from shared.utils.logging import setup_logging

logger = logging.getLogger(__name__)


class OrchestratorService:
    """
    Master Orchestrator Agent.
    - Triggers scheduled collection runs
    - Monitors pipeline health and handles stuck jobs
    - Re-queues failed jobs for retry
    - Manages system-wide rate limits and quotas
    """

    def __init__(self) -> None:
        self.producer = KafkaProducerClient()
        self.running = False
        self.collection_interval_hours = int(os.getenv("COLLECTION_INTERVAL_HOURS", "6"))
        self.stuck_job_threshold_hours = int(os.getenv("STUCK_JOB_THRESHOLD_HOURS", "2"))
        self.max_retries = int(os.getenv("MAX_JOB_RETRIES", "3"))

    async def start(self) -> None:
        await self.producer.start()
        self.running = True
        logger.info("🎯 Orchestrator service started")

        # Run all background tasks concurrently
        await asyncio.gather(
            self._scheduled_collection_loop(),
            self._stuck_job_monitor(),
            self._daily_cleanup(),
        )

    async def stop(self) -> None:
        self.running = False
        await self.producer.stop()

    # ─── Scheduled Collection ─────────────────────────────────────────────────

    async def _scheduled_collection_loop(self) -> None:
        """Trigger collection runs every N hours."""
        interval_seconds = self.collection_interval_hours * 3600

        while self.running:
            logger.info(f"⏰ Triggering scheduled collection (every {self.collection_interval_hours}h)")
            await self._trigger_collection()
            await asyncio.sleep(interval_seconds)

    async def _trigger_collection(
        self,
        sources: list[str] | None = None,
        search_terms: list[str] | None = None,
    ) -> None:
        """Send a collection trigger to Kafka."""
        try:
            default_sources = ["adzuna", "greenhouse", "indeed", "rss"]
            default_terms = [
                "software engineer", "data scientist", "python developer",
                "machine learning engineer", "backend developer", "devops engineer",
                "product manager", "data analyst", "full stack developer",
            ]

            task = {
                "sources": sources or default_sources,
                "search_terms": search_terms or default_terms,
                "limit": 1000,
                "triggered_by": "orchestrator",
                "triggered_at": datetime.utcnow().isoformat(),
            }

            await self.producer.send(TOPICS.COLLECTION_TRIGGER, task)
            logger.info(f"Collection triggered: {len(task['sources'])} sources")

        except Exception as e:
            logger.exception(f"Failed to trigger collection: {e}")

    # ─── Stuck Job Monitor ────────────────────────────────────────────────────

    async def _stuck_job_monitor(self) -> None:
        """Detect jobs stuck in intermediate states and re-queue them."""
        check_interval = 30 * 60  # 30 minutes

        while self.running:
            await asyncio.sleep(check_interval)
            try:
                await self._find_and_requeue_stuck_jobs()
            except Exception as e:
                logger.exception(f"Stuck job monitor error: {e}")

    async def _find_and_requeue_stuck_jobs(self) -> None:
        """Find jobs stuck in non-final states and re-queue them."""
        client = get_mongo_client()
        db = client["jobplatform"]

        cutoff = datetime.utcnow() - timedelta(hours=self.stuck_job_threshold_hours)
        stuck_statuses = ["raw", "cleaned", "deduplicated", "enriched"]

        for status_val in stuck_statuses:
            cursor = db.jobs.find({
                "status": status_val,
                "updated_at": {"$lte": cutoff},
                "retry_count": {"$lt": self.max_retries},
            }).limit(50)
            stuck_jobs = await cursor.to_list(length=50)

            if stuck_jobs:
                logger.warning(f"Found {len(stuck_jobs)} stuck jobs in status '{status_val}'")

                # Map status to which topic to re-send to
                topic_map = {
                    "raw": TOPICS.JOB_RAW,
                    "cleaned": TOPICS.JOB_CLEANED,
                    "deduplicated": TOPICS.JOB_DEDUPLICATED,
                    "enriched": TOPICS.JOB_ENRICHED,
                }
                topic = topic_map.get(status_val)

                for job in stuck_jobs:
                    job_id = str(job.get("_id", ""))
                    retry_count = job.get("retry_count", 0)

                    # Increment retry count
                    await db.jobs.update_one(
                        {"_id": job["_id"]},
                        {"$inc": {"retry_count": 1}, "$set": {"updated_at": datetime.utcnow()}},
                    )

                    if topic:
                        await self.producer.send(topic, job, key=job_id)
                        logger.info(f"Re-queued stuck job {job_id} (retry {retry_count + 1})")

    # ─── Daily Cleanup ────────────────────────────────────────────────────────

    async def _daily_cleanup(self) -> None:
        """Run daily maintenance tasks."""
        while self.running:
            await asyncio.sleep(24 * 3600)  # Every 24 hours
            try:
                await self._expire_old_jobs()
                await self._cleanup_pipeline_events()
                logger.info("✅ Daily cleanup complete")
            except Exception as e:
                logger.exception(f"Daily cleanup error: {e}")

    async def _expire_old_jobs(self) -> None:
        """Mark jobs older than 60 days as expired."""
        client = get_mongo_client()
        db = client["jobplatform"]

        cutoff = datetime.utcnow() - timedelta(days=60)
        result = await db.jobs.update_many(
            {
                "status": "published",
                "posted_at": {"$lte": cutoff},
            },
            {"$set": {"status": "expired", "updated_at": datetime.utcnow()}},
        )
        if result.modified_count:
            logger.info(f"Expired {result.modified_count} old jobs")

    async def _cleanup_pipeline_events(self) -> None:
        """Delete pipeline events older than 7 days to save storage."""
        client = get_mongo_client()
        db = client["jobplatform"]

        cutoff = datetime.utcnow() - timedelta(days=7)
        result = await db.pipeline_events.delete_many({"created_at": {"$lte": cutoff}})
        if result.deleted_count:
            logger.info(f"Cleaned up {result.deleted_count} old pipeline events")


async def main() -> None:
    setup_logging()
    service = OrchestratorService()
    try:
        await service.start()
    except KeyboardInterrupt:
        await service.stop()


if __name__ == "__main__":
    asyncio.run(main())
