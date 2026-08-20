"""
Collector Service — Orchestrates all job collection activities.

High-throughput improvements:
- Runs ALL collectors CONCURRENTLY via asyncio.gather (not serial for-loop)
- Publishes jobs using producer.send_batch() instead of one-at-a-time
- Scheduled interval shortened to every 90 minutes (4x more frequent)
- Default limit raised to 5,000 per run (was 1,000)
- Each collector's limit is proportional to source strength (scaled per source)
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime
from typing import Any

from shared.kafka.consumer import KafkaConsumerClient
from shared.kafka.producer import KafkaProducerClient
from shared.kafka.topics import TOPICS
from shared.models.job import CollectionSource
from shared.utils.logging import setup_logging
from services.collector.agents import (
    COLLECTOR_REGISTRY,
    get_collector,
    get_all_sources,
    DEFAULT_SEARCH_TERMS,
)

logger = logging.getLogger(__name__)

# ─── Per-source scaling weights (proportion of total limit) ──────────────────
SOURCE_WEIGHTS: dict[str, float] = {
    CollectionSource.ADZUNA: 0.15,
    CollectionSource.GREENHOUSE: 0.12,
    CollectionSource.LEVER: 0.10,
    CollectionSource.WORKDAY: 0.05,
    CollectionSource.INDEED: 0.08,
    CollectionSource.NAUKRI: 0.15,
    CollectionSource.LINKEDIN: 0.12,
    CollectionSource.RSS: 0.10,
    CollectionSource.GOVERNMENT: 0.03,
    CollectionSource.COMPANY_CAREERS: 0.10,
}


def _scale_limits(total_limit: int, sources: list[str]) -> dict[str, int]:
    """Distribute total limit across sources using proportional weights."""
    active_weights = {s: SOURCE_WEIGHTS.get(s, 1.0 / max(1, len(sources))) for s in sources}
    total_w = sum(active_weights.values())
    normalized = {s: w / total_w for s, w in active_weights.items()}
    # First pass: floor allocation
    allocated = {s: max(5, int(total_limit * w)) for s, w in normalized.items()}
    used = sum(allocated.values())
    leftover = total_limit - used
    # Distribute leftover proportionally
    if leftover > 0:
        ordered = sorted(allocated.keys(), key=lambda s: normalized[s], reverse=True)
        for s in ordered:
            add = min(leftover, max(1, int(leftover * normalized[s])))
            allocated[s] += add
            leftover -= add
            if leftover <= 0:
                break
    return allocated


class CollectorService:
    """
    Master collection orchestrator — runs collectors concurrently
    and publishes results in big Kafka batches.
    """

    def __init__(self) -> None:
        self.producer = KafkaProducerClient()
        self.consumer = KafkaConsumerClient(topics=[TOPICS.COLLECTION_TRIGGER])
        self.running = False
        self._collection_lock = asyncio.Lock()
        self._last_collection_summary: dict[str, Any] = {}

    async def start(self) -> None:
        await self.producer.start()
        await self.consumer.start()
        self.running = True
        logger.info("🚀 Collector service started (high-throughput mode)")

        asyncio.create_task(self._scheduled_collection())
        await self.consumer.consume(self._handle_trigger)

    async def stop(self) -> None:
        self.running = False
        await self.producer.stop()
        await self.consumer.stop()

    async def _handle_trigger(self, message: dict, *args) -> None:
        """Handle a collection trigger message."""
        triggered_by = message.get("triggered_by", "")
        is_search = triggered_by == "search_auto_trigger"

        if not is_search and self._collection_lock.locked():
            logger.warning("Collection already in progress — skipping trigger")
            return

        sources = message.get("sources") or get_all_sources()
        search_terms = message.get("search_terms") or None
        location = message.get("location") or None
        limit = int(message.get("limit") or os.getenv("COLLECTION_RUN_LIMIT", "5000"))

        logger.info(
            f"📥 Collection triggered by {triggered_by}: "
            f"sources={len(sources)}, terms={len(search_terms or DEFAULT_SEARCH_TERMS)}, limit={limit}"
        )
        
        if is_search:
            # Run search collections concurrently without locking global scheduled runs
            asyncio.create_task(self._run_collection(
                sources, search_terms, location, limit
            ))
        else:
            async with self._collection_lock:
                self._last_collection_summary = await self._run_collection(
                    sources, search_terms, location, limit
                )

    async def _scheduled_collection(self) -> None:
        """Run collection on schedule (every 90 minutes by default)."""
        interval_min = int(os.getenv("COLLECTION_INTERVAL_MINUTES", "90"))
        interval_seconds = interval_min * 60
        logger.info(f"⏰ Scheduled collection every {interval_min} minutes")

        while self.running:
            # Stagger initial start slightly (5 seconds) so services come up
            await asyncio.sleep(5 if not self._last_collection_summary else interval_seconds)
            if not self.running:
                break

            if self._collection_lock.locked():
                logger.info("Previous collection still running — skipping this cycle")
                continue

            logger.info(f"⏰ Scheduled collection starting (every {interval_min}m)")
            all_sources = get_all_sources()
            limit = int(os.getenv("COLLECTION_RUN_LIMIT", "5000"))

            async with self._collection_lock:
                summary = await self._run_collection(
                    all_sources, None, None, limit
                )
                self._last_collection_summary = summary

            total = summary.get("total_published", 0)
            logger.info(
                f"✅ Scheduled collection complete: {total} jobs published. "
                f"Next run in {interval_min}m"
            )

    async def _run_collection(
        self,
        sources: list[str],
        search_terms: list[str] | None,
        location: str | None,
        limit: int,
    ) -> dict[str, Any]:
        """Run ALL sources concurrently, then batch-publish to Kafka."""
        t0 = asyncio.get_event_loop().time()
        per_source_limits = _scale_limits(limit, sources)

        summary: dict[str, Any] = {
            "started_at": datetime.utcnow().isoformat(),
            "sources_requested": list(sources),
            "total_limit": limit,
            "per_source_limits": per_source_limits,
        }

        async def _run_one(source_name: str) -> tuple[str, list]:
            source_limit = per_source_limits.get(source_name, limit // max(1, len(sources)))
            try:
                collector = get_collector(source_name)
                logger.info(f"  ▶ Collecting {source_name} (up to {source_limit} jobs)...")
                async with collector:
                    jobs = await collector.collect(
                        search_terms=search_terms,
                        location=location,
                        limit=source_limit,
                    )
                logger.info(f"  ✔ {source_name}: collected {len(jobs)} jobs")
                return source_name, list(jobs)
            except Exception as e:
                logger.exception(f"  ❌ Collection failed for {source_name}: {e}")
                return source_name, []

        # Run every source concurrently
        tasks = [asyncio.create_task(_run_one(s)) for s in sources]
        results = await asyncio.gather(*tasks, return_exceptions=False)

        source_job_map: dict[str, list] = {s: j for s, j in results}
        summary["collected_per_source"] = {s: len(j) for s, j in source_job_map.items()}
        total_collected = sum(len(j) for j in source_job_map.values())

        logger.info(f"📦 Collected {total_collected} raw jobs across {len(results)} sources")

        # ─── Batch publish to Kafka ─────────────────────────────────────────
        published_per_source: dict[str, int] = {}
        total_published = 0

        for source_name, jobs in source_job_map.items():
            if not jobs:
                published_per_source[source_name] = 0
                continue

            # Build (payload, key) tuples for send_batch
            to_send: list[tuple[Any, str]] = []
            for job in jobs:
                try:
                    payload = job.model_dump(mode="json")
                    key = str(job.id)
                    to_send.append((payload, key))
                except Exception as e:
                    logger.debug(f"Skip serialize {source_name} job: {e}")

            if to_send:
                pub_count = await self.producer.send_batch(TOPICS.JOB_RAW, to_send)
            else:
                pub_count = 0

            published_per_source[source_name] = pub_count
            total_published += pub_count
            logger.info(f"📨 {source_name}: published {pub_count}/{len(jobs)} to {TOPICS.JOB_RAW}")

        duration_s = asyncio.get_event_loop().time() - t0
        summary["published_per_source"] = published_per_source
        summary["total_collected"] = total_collected
        summary["total_published"] = total_published
        summary["duration_seconds"] = round(duration_s, 2)
        summary["jobs_per_second"] = round(total_published / max(0.1, duration_s), 1)
        summary["finished_at"] = datetime.utcnow().isoformat()

        logger.info(
            f"🏁 Collection complete: {total_published}/{total_collected} "
            f"jobs published to Kafka in {duration_s:.1f}s "
            f"({summary['jobs_per_second']} j/s)"
        )
        return summary


async def main() -> None:
    setup_logging()
    service = CollectorService()
    try:
        await service.start()
    except KeyboardInterrupt:
        await service.stop()


if __name__ == "__main__":
    asyncio.run(main())
