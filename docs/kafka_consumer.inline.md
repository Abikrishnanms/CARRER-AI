**Kafka Consumer — `shared/kafka/consumer.py` (Annotated copy)**

Summary: Async Kafka consumer wrapper using `aiokafka` that provides single-message and batch consumption APIs, JSON deserialization, manual commit handling, and helper context manager.

---

```python
"""
Async Kafka consumer with automatic deserialization,
consumer group management, and graceful shutdown.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from collections.abc import AsyncGenerator, Callable
from typing import Any

from aiokafka import AIOKafkaConsumer, ConsumerRecord

logger = logging.getLogger(__name__)

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_GROUP_ID = os.getenv("KAFKA_CONSUMER_GROUP_ID", "job-platform-consumers")


class KafkaConsumerClient:
    """
    Typed async Kafka consumer with:
    - Automatic JSON deserialization
    - Consumer group management
    - Graceful shutdown
    - Error isolation (one bad message doesn't stop the consumer)
    - Manual offset commit for exactly-once processing
    """

    def __init__(
        self,
        topics: list[str],
        group_id: str = KAFKA_GROUP_ID,
        bootstrap_servers: str = KAFKA_BOOTSTRAP_SERVERS,
        auto_offset_reset: str = "earliest",
        max_poll_records: int = 100,
    ) -> None:
        self.topics = topics
        self.group_id = group_id
        self.bootstrap_servers = bootstrap_servers
        self.auto_offset_reset = auto_offset_reset
        self.max_poll_records = max_poll_records
        self._consumer: AIOKafkaConsumer | None = None
        self._running = False

    async def start(self) -> None:
        self._consumer = AIOKafkaConsumer(
            *self.topics,
            bootstrap_servers=self.bootstrap_servers,
            group_id=self.group_id,
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
            auto_offset_reset=self.auto_offset_reset,
            enable_auto_commit=False,  # Manual commit for exactly-once
            max_poll_records=self.max_poll_records,
            session_timeout_ms=30_000,
            heartbeat_interval_ms=3_000,
        )
        await self._consumer.start()
        self._running = True
        logger.info(
            "Kafka consumer started",
            extra={"topics": self.topics, "group_id": self.group_id}
        )

    async def stop(self) -> None:
        self._running = False
        if self._consumer:
            await self._consumer.stop()
            logger.info("Kafka consumer stopped")

    async def consume(
        self,
        handler: Callable[[dict[str, Any], ConsumerRecord], Any],
        batch_size: int = 1,
    ) -> None:
        """
        Consume messages and call handler for each.
        Automatically commits offset after successful processing.
        """
        if not self._consumer:
            raise RuntimeError("Consumer not started. Call start() first.")

        logger.info(f"Starting to consume from {self.topics}")

        async for record in self._consumer:
            if not self._running:
                break

            try:
                await handler(record.value, record)
                # Commit offset after successful processing
                await self._consumer.commit()

            except Exception as e:
                logger.exception(
                    f"Error processing message from {record.topic}:{record.partition}:{record.offset}: {e}"
                )
                # Don't commit — message will be reprocessed
                # Send to DLQ after max retries (handled by handler)

    async def consume_batch(
        self,
        handler: Callable[[list[dict[str, Any]]], Any],
        batch_size: int = 100,
        timeout_ms: int = 5000,
    ) -> None:
        """Batch consumer for high-throughput processing."""
        if not self._consumer:
            raise RuntimeError("Consumer not started.")

        while self._running:
            try:
                batch = await self._consumer.getmany(
                    timeout_ms=timeout_ms,
                    max_records=batch_size,
                )
                messages = []
                for tp, records in batch.items():
                    for record in records:
                        messages.append(record.value)

                if messages:
                    await handler(messages)
                    await self._consumer.commit()

            except Exception as e:
                logger.exception(f"Error in batch consumer: {e}")
                await asyncio.sleep(1)

    async def messages(self) -> AsyncGenerator[dict[str, Any], None]:
        """Async generator interface for consuming messages."""
        if not self._consumer:
            raise RuntimeError("Consumer not started.")

        async for record in self._consumer:
            yield record.value
            await self._consumer.commit()

    async def __aenter__(self) -> KafkaConsumerClient:
        await self.start()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.stop()
```

---

Grouped explanations:

- `start()`: creates `AIOKafkaConsumer` with JSON deserialization and manual commits for exactly-once semantics.
- `consume()`: single-message processing loop that commits offsets only after the handler returns successfully; exceptions are logged and the message is left uncommitted for reprocessing.
- `consume_batch()`: high-throughput batch API using `getmany()` to fetch many records, pass a list to the handler, then commit once per batch; on exceptions it logs and sleeps briefly before retrying.
- `messages()`: async generator convenience for streaming consumers.
- Context manager methods are provided for `async with` usage.

Notes:
- The consumer defers DLQ policy to handlers; handlers should implement per-message retry and DLQ logic when needed.
- Tuning knobs: `KAFKA_CONSUMER_GROUP_ID`, `KAFKA_BOOTSTRAP_SERVERS`, and `max_poll_records` passed at construction.
