"""
Kafka Topic Initializer — Creates all required topics before services start.
Run this once at platform startup or via the kafka-init Docker service.

Usage:
    python scripts/init_kafka_topics.py
    python scripts/init_kafka_topics.py --bootstrap-servers localhost:9092
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import time

logger = logging.getLogger(__name__)


async def create_topics(bootstrap_servers: str, max_retries: int = 10) -> None:
    """Create all platform Kafka topics with proper configuration."""

    # Wait for Redpanda/Kafka to be ready
    for attempt in range(max_retries):
        try:
            from aiokafka.admin import AIOKafkaAdminClient, NewTopic

            admin = AIOKafkaAdminClient(bootstrap_servers=bootstrap_servers)
            await admin.start()
            logger.info(f"Connected to Kafka at {bootstrap_servers}")
            break
        except Exception as e:
            if attempt < max_retries - 1:
                wait = 3 * (attempt + 1)
                logger.warning(f"Kafka not ready (attempt {attempt+1}/{max_retries}): {e}. Retrying in {wait}s...")
                await asyncio.sleep(wait)
            else:
                logger.error(f"Could not connect to Kafka after {max_retries} attempts. Exiting.")
                sys.exit(1)

    # Build topic list from shared definitions
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from shared.kafka.topics import TOPIC_CONFIGS, TOPICS

    topics_to_create = []

    # All platform topics with explicit configs
    for topic_attr in [
        "JOB_RAW", "JOB_CLEANED", "JOB_DEDUPLICATED", "JOB_ENRICHED",
        "JOB_VERIFIED", "JOB_REJECTED", "JOB_EXPIRED",
        "JOB_RAW_DLQ", "JOB_CLEANED_DLQ", "JOB_ENRICHED_DLQ",
        "NOTIFICATION_EMAIL", "NOTIFICATION_TELEGRAM", "NOTIFICATION_WHATSAPP",
        "NOTIFICATION_WEBHOOK", "NOTIFICATION_IN_APP",
        "EMBEDDING_JOB", "EMBEDDING_USER", "EMBEDDING_COMPLETE",
        "USER_EVENT", "SEARCH_QUERY", "FEEDBACK_RECEIVED",
        "COLLECTION_TRIGGER", "VERIFICATION_REQUEST", "ENRICHMENT_REQUEST",
    ]:
        topic_name = getattr(TOPICS, topic_attr)
        config = TOPIC_CONFIGS.get(topic_name, {})

        # Use conservative settings for dev (replication_factor=1)
        num_partitions = config.get("num_partitions", 3)
        replication_factor = min(config.get("replication_factor", 1), 1)  # Dev: always 1 replica

        topic_config = {}
        if "retention_ms" in config:
            topic_config["retention.ms"] = str(config["retention_ms"])

        topics_to_create.append(
            NewTopic(
                name=topic_name,
                num_partitions=num_partitions,
                replication_factor=replication_factor,
                topic_configs=topic_config,
            )
        )

    logger.info(f"Creating {len(topics_to_create)} Kafka topics...")

    # Get existing topics to skip
    try:
        existing = set(await admin.list_topics())
    except Exception:
        existing = set()

    new_topics = [t for t in topics_to_create if t.name not in existing]
    skipped = len(topics_to_create) - len(new_topics)

    if not new_topics:
        logger.info(f"All {len(topics_to_create)} topics already exist. Nothing to do.")
        await admin.close()
        return

    if skipped:
        logger.info(f"Skipping {skipped} existing topics.")

    try:
        results = await admin.create_topics(new_topics, validate_only=False)
        created = 0
        for topic, error in results.items():
            if error is None:
                logger.info(f"  ✅ Created topic: {topic}")
                created += 1
            else:
                logger.warning(f"  ⚠️  Topic {topic}: {error}")
        logger.info(f"Done — {created} topics created, {skipped} already existed.")
    except Exception as e:
        logger.error(f"Topic creation failed: {e}")
        raise
    finally:
        await admin.close()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser(description="Initialize Kafka topics for TalentLens")
    parser.add_argument(
        "--bootstrap-servers",
        default=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
        help="Kafka/Redpanda bootstrap servers",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=10,
        help="Max retries waiting for Kafka to be ready",
    )
    args = parser.parse_args()

    asyncio.run(create_topics(args.bootstrap_servers, args.max_retries))


if __name__ == "__main__":
    main()
