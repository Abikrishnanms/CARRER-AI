"""
Collector Service — Orchestrates all job collection activities.
Consumes from Kafka topic: collection.trigger
Publishes to Kafka topic: job.raw
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime

from shared.kafka.consumer import KafkaConsumerClient
from shared.kafka.producer import KafkaProducerClient
from shared.kafka.topics import TOPICS
from shared.models.job import CollectionSource
from shared.utils.logging import setup_logging
from services.collector.agents import COLLECTOR_REGISTRY, get_collector

logger = logging.getLogger(__name__)


class CollectorService:
    """
    Master collection orchestrator.
    - Listens for collection triggers via Kafka
    - Runs all configured collectors
    - Publishes raw jobs to job.raw topic
    """

    def __init__(self) -> None:
        self.producer = KafkaProducerClient()
        self.consumer = KafkaConsumerClient(topics=[TOPICS.COLLECTION_TRIGGER])
        self.running = False

    async def start(self) -> None:
        await self.producer.start()
        await self.consumer.start()
        self.running = True
        logger.info("🚀 Collector service started")

        # Start background scheduled collection
        asyncio.create_task(self._scheduled_collection())

        # Listen for manual triggers
        await self.consumer.consume(self._handle_trigger)

    async def stop(self) -> None:
        self.running = False
        await self.producer.stop()
        await self.consumer.stop()

    async def _handle_trigger(self, message: dict, *args) -> None:
        """Handle a collection trigger message."""
        sources = message.get("sources", list(COLLECTOR_REGISTRY.keys()))
        search_terms = message.get("search_terms")
        location = message.get("location")
        limit = message.get("limit", 500)

        logger.info(f"Collection triggered: sources={sources}, terms={len(search_terms or [])}")
        await self._run_collection(sources, search_terms, location, limit)

    async def _scheduled_collection(self) -> None:
        """Run collection on schedule (every 6 hours by default)."""
        interval_hours = int(os.getenv("COLLECTION_INTERVAL_HOURS", "6"))
        interval_seconds = interval_hours * 3600

        while self.running:
            logger.info(f"⏰ Scheduled collection starting")
            all_sources = list(COLLECTOR_REGISTRY.keys())
            await self._run_collection(all_sources, None, None, 1000)
            logger.info(f"✅ Scheduled collection complete. Next run in {interval_hours}h")
            await asyncio.sleep(interval_seconds)

    async def _run_collection(
        self,
        sources: list[str],
        search_terms: list[str] | None,
        location: str | None,
        limit: int,
    ) -> dict[str, int]:
        """Run collection for all specified sources."""
        total_collected = 0
        results = {}

        for source_name in sources:
            try:
                collector = get_collector(source_name)
                logger.info(f"Collecting from {source_name}...")

                async with collector:
                    jobs = await collector.collect(
                        search_terms=search_terms,
                        location=location,
                        limit=limit // len(sources),
                    )

                # Publish to Kafka
                published = 0
                for job in jobs:
                    success = await self.producer.send(
                        TOPICS.JOB_RAW,
                        job.model_dump(mode="json"),
                        key=str(job.id),
                    )
                    if success:
                        published += 1

                results[source_name] = published
                total_collected += published
                logger.info(f"✅ {source_name}: published {published}/{len(jobs)} jobs")

            except Exception as e:
                logger.exception(f"❌ Collection failed for {source_name}: {e}")
                results[source_name] = -1

        logger.info(f"Collection complete: {total_collected} total jobs published")
        return results


async def main() -> None:
    setup_logging()
    service = CollectorService()
    try:
        await service.start()
    except KeyboardInterrupt:
        await service.stop()


if __name__ == "__main__":
    asyncio.run(main())
