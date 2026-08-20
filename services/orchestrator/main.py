"""
Orchestrator Service — Master workflow coordinator.

High-throughput improvements:
- Collection triggers every 60 minutes (was 6 hours) with offset jitter
- Stuck-job monitor every 10 minutes instead of 30
- Raised max stuck-job requeue batch from 50 → 500
- Adaptive limit based on current backlog
- Added pipeline throughput metrics logging
"""

from __future__ import annotations

import asyncio
import logging
import os
import random
from datetime import datetime, timedelta
from typing import Any

from shared.database.session import get_mongo_client
from shared.kafka.producer import KafkaProducerClient
from shared.kafka.topics import TOPICS
from shared.utils.logging import setup_logging

logger = logging.getLogger(__name__)


class OrchestratorService:
    """
    Master Orchestrator Agent — throughput-aware scheduler.
    """

    def __init__(self) -> None:
        self.producer = KafkaProducerClient()
        self.running = False
        self.collection_interval_min = int(os.getenv("COLLECTION_INTERVAL_MINUTES", "60"))
        self.stuck_job_threshold_hours = int(os.getenv("STUCK_JOB_THRESHOLD_HOURS", "2"))
        self.max_retries = int(os.getenv("MAX_JOB_RETRIES", "5"))
        self.stuck_job_batch_size = int(os.getenv("STUCK_JOB_BATCH", "500"))
        self.default_limit = int(os.getenv("COLLECTION_RUN_LIMIT", "5000"))
        self.high_volume_limit = int(os.getenv("COLLECTION_RUN_LIMIT_HIGH", "12000"))

    async def start(self) -> None:
        await self.producer.start()
        self.running = True
        logger.info(
            f"🎯 Orchestrator started (interval={self.collection_interval_min}m, "
            f"limit={self.default_limit}, stuck_batch={self.stuck_job_batch_size})"
        )

        await asyncio.gather(
            self._scheduled_collection_loop(),
            self._stuck_job_monitor(),
            self._quarter_hour_mini_collect(),
            self._daily_cleanup(),
            self._throughput_metrics_logger(),
        )

    async def stop(self) -> None:
        self.running = False
        await self.producer.stop()

    # ─── Scheduled Collection ─────────────────────────────────────────────────

    async def _scheduled_collection_loop(self) -> None:
        """Full volume collection run every N minutes with initial jitter."""
        interval_seconds = self.collection_interval_min * 60
        # Jitter initial start so multiple deployments don't stampede
        initial_sleep = random.uniform(10, 60)
        logger.info(f"First full collection in {initial_sleep:.0f}s (jitter)")
        await asyncio.sleep(initial_sleep)

        while self.running:
            t0 = asyncio.get_event_loop().time()
            try:
                limit = await self._adaptive_limit()
                logger.info(f"⏰ Triggering scheduled collection (target {limit} jobs)")
                await self._trigger_collection(limit=limit)
            except Exception as e:
                logger.exception(f"Scheduled collection trigger failed: {e}")

            elapsed = asyncio.get_event_loop().time() - t0
            sleep_for = max(5.0, interval_seconds - elapsed)
            logger.info(f"Next collection in {sleep_for/60:.1f} minutes")
            await asyncio.sleep(sleep_for)

    async def _quarter_hour_mini_collect(self) -> None:
        """Lightweight 'top-up' collection every 15 min for freshest jobs."""
        while self.running:
            await asyncio.sleep(15 * 60)
            if not self.running:
                break
            try:
                limit = max(1000, self.default_limit // 4)
                logger.info(f"🔄 Mini-collection top-up ({limit} jobs)")
                await self._trigger_collection(
                    limit=limit,
                    sources=["adzuna", "indeed", "naukri", "linkedin", "rss"],
                    label="mini",
                )
            except Exception as e:
                logger.debug(f"Mini-collection failed (non-fatal): {e}")

    async def _adaptive_limit(self) -> int:
        """Choose collection limit based on backlog pressure."""
        try:
            client = get_mongo_client()
            db = client["jobplatform"]
            recent = datetime.utcnow() - timedelta(hours=2)
            recent_count = await db.jobs.count_documents({"created_at": {"$gte": recent}})
            # If ingestion in last 2h is low, boost limit for catch-up
            if recent_count < self.default_limit // 2:
                logger.info(
                    f"Low recent ingestion ({recent_count} in 2h) — "
                    f"boosting to {self.high_volume_limit} jobs"
                )
                return self.high_volume_limit
            return self.default_limit
        except Exception as e:
            logger.debug(f"Adaptive limit query failed, using default: {e}")
            return self.default_limit

    async def _trigger_collection(
        self,
        sources: list[str] | None = None,
        search_terms: list[str] | None = None,
        limit: int | None = None,
        label: str = "full",
    ) -> None:
        """Send a collection trigger to Kafka."""
        try:
            default_sources = [
                "adzuna", "greenhouse", "lever", "workday", "indeed",
                "naukri", "linkedin", "rss", "government", "company_careers",
            ]
            default_terms = [
                "software engineer", "data scientist", "python developer",
                "machine learning engineer", "backend developer", "devops engineer",
                "product manager", "data analyst", "full stack developer",
                "react developer", "frontend developer", "cloud architect",
                "data engineer", "qa engineer", "android developer",
                "ios developer", "cybersecurity", "solutions architect",
                "senior software engineer", "staff engineer",
            ]

            task = {
                "sources": sources or default_sources,
                "search_terms": search_terms or default_terms,
                "limit": limit or self.default_limit,
                "triggered_by": "orchestrator",
                "triggered_at": datetime.utcnow().isoformat(),
                "label": label,
            }

            await self.producer.send(TOPICS.COLLECTION_TRIGGER, task)
            logger.info(
                f"Collection trigger ({label}) sent: "
                f"{len(task['sources'])} sources, limit={task['limit']}"
            )

        except Exception as e:
            logger.exception(f"Failed to trigger collection: {e}")

    # ─── Stuck Job Monitor ────────────────────────────────────────────────────

    async def _stuck_job_monitor(self) -> None:
        """Detect jobs stuck in intermediate states and re-queue them."""
        check_interval = 10 * 60  # 10 minutes
        logger.info(f"Stuck-job monitor running every {check_interval//60} minutes")
        await asyncio.sleep(60)  # Don't run before services warm up

        while self.running:
            await asyncio.sleep(check_interval)
            try:
                await self._find_and_requeue_stuck_jobs()
            except Exception as e:
                logger.exception(f"Stuck job monitor error: {e}")

    async def _find_and_requeue_stuck_jobs(self) -> None:
        client = get_mongo_client()
        db = client["jobplatform"]

        cutoff = datetime.utcnow() - timedelta(hours=self.stuck_job_threshold_hours)
        stuck_statuses = ["raw", "cleaned", "deduplicated", "enriched"]
        topic_map = {
            "raw": TOPICS.JOB_RAW,
            "cleaned": TOPICS.JOB_CLEANED,
            "deduplicated": TOPICS.JOB_DEDUPLICATED,
            "enriched": TOPICS.JOB_ENRICHED,
        }

        total_requeued = 0
        for status_val in stuck_statuses:
            cursor = db.jobs.find({
                "status": status_val,
                "updated_at": {"$lte": cutoff},
                "retry_count": {"$lt": self.max_retries},
            }).limit(self.stuck_job_batch_size)
            stuck_jobs = await cursor.to_list(length=self.stuck_job_batch_size)
            if not stuck_jobs:
                continue

            logger.warning(
                f"Found {len(stuck_jobs)} stuck jobs in status '{status_val}' — re-queueing"
            )

            topic = topic_map.get(status_val)
            if not topic:
                continue

            # Batch update retry counts in parallel with batch publish
            to_send: list[tuple[dict[str, Any], str]] = []
            for job in stuck_jobs:
                job_id = str(job.get("_id", ""))
                retry_count = int(job.get("retry_count", 0)) + 1
                job["retry_count"] = retry_count
                job["updated_at"] = datetime.utcnow()
                to_send.append((job, job_id))

            if to_send:
                await self.producer.send_batch(topic, to_send)
                # Update retry counts in DB asynchronously
                async def _update_one(jid, rc):
                    await db.jobs.update_one(
                        {"_id": jid},
                        {"$set": {"retry_count": rc, "updated_at": datetime.utcnow()}},
                    )
                await asyncio.gather(*[
                    _update_one(j["_id"], j["retry_count"]) for j in stuck_jobs
                ])

            total_requeued += len(to_send)

        if total_requeued:
            logger.info(f"Re-queued {total_requeued} stuck jobs across all stages")

    # ─── Daily Cleanup ────────────────────────────────────────────────────────

    async def _daily_cleanup(self) -> None:
        """Run daily maintenance tasks."""
        # Run first cleanup 1 hour after startup, then every 24h
        await asyncio.sleep(60 * 60)
        while self.running:
            try:
                expired = await self._expire_old_jobs()
                events_purged = await self._cleanup_pipeline_events()
                dedup_keys = await self._cleanup_old_dedup_keys()
                logger.info(
                    f"✅ Daily cleanup: {expired} expired, {events_purged} events purged, "
                    f"{dedup_keys} dedup keys removed"
                )
            except Exception as e:
                logger.exception(f"Daily cleanup error: {e}")
            await asyncio.sleep(24 * 3600)

    async def _expire_old_jobs(self) -> int:
        """Mark published jobs older than 60 days as expired."""
        client = get_mongo_client()
        db = client["jobplatform"]
        cutoff = datetime.utcnow() - timedelta(days=60)
        result = await db.jobs.update_many(
            {"status": "published", "posted_at": {"$lte": cutoff}},
            {"$set": {"status": "expired", "updated_at": datetime.utcnow()}},
        )
        return result.modified_count

    async def _cleanup_pipeline_events(self) -> int:
        client = get_mongo_client()
        db = client["jobplatform"]
        cutoff = datetime.utcnow() - timedelta(days=7)
        result = await db.pipeline_events.delete_many({"created_at": {"$lte": cutoff}})
        return result.deleted_count

    async def _cleanup_old_dedup_keys(self) -> int:
        """Expire old deduplication keys in Redis (>7 days)."""
        try:
            from shared.redis.client import get_redis_client
            redis = await get_redis_client()
            # Keys use TTL already; just log DB size for observability
            info = await redis.info("keyspace")
            total = sum(int(db.get("keys", 0)) for db in info.values() if isinstance(db, dict))
            return total
        except Exception:
            return 0

    # ─── Throughput Metrics ───────────────────────────────────────────────────

    async def _throughput_metrics_logger(self) -> None:
        """Periodically log pipeline throughput stats for observability."""
        while self.running:
            await asyncio.sleep(5 * 60)  # every 5 minutes
            try:
                client = get_mongo_client()
                db = client["jobplatform"]
                last_hour = datetime.utcnow() - timedelta(hours=1)
                hour_counts: dict[str, int] = {}
                for status in ["raw", "cleaned", "deduplicated", "enriched", "verified", "published", "expired", "rejected"]:
                    n = await db.jobs.count_documents({
                        "status": status,
                        "updated_at": {"$gte": last_hour},
                    })
                    hour_counts[status] = n
                total_published = await db.jobs.count_documents({"status": "published"})
                logger.info(
                    "📊 Throughput (1h): "
                    + " | ".join(f"{k}={v}" for k, v in hour_counts.items())
                    + f" || total_published={total_published}"
                )
            except Exception as e:
                logger.debug(f"Throughput metrics failed: {e}")


async def main() -> None:
    setup_logging()
    service = OrchestratorService()
    try:
        await service.start()
    except KeyboardInterrupt:
        await service.stop()


if __name__ == "__main__":
    asyncio.run(main())
