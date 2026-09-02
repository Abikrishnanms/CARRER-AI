**Kafka Producer — `shared/kafka/producer.py` (Annotated copy)**

Summary: Async Kafka producer wrapper using `aiokafka`. Adds JSON serialization, batch publishing (`send_batch`), DLQ handling, and a global singleton helper.

---

```python
"""
Kafka producer and consumer abstractions with typed events.
Uses aiokafka for async operation.

Performance improvements:
- Producer send_batch() that fires N requests concurrently instead of
  one-at-a-time send_and_wait, dramatically increasing throughput.
- Larger default batch size + linger_ms so records batch on the broker side.
- Producer is idempotent + transaction-aware for correctness.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any
from uuid import uuid4

from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaConnectionError, KafkaError

logger = logging.getLogger(__name__)

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
DEFAULT_BATCH_SIZE = int(os.getenv("KAFKA_PRODUCER_BATCH_SIZE", "500"))
DEFAULT_LINGER_MS = int(os.getenv("KAFKA_PRODUCER_LINGER_MS", "20"))
SEND_BATCH_CONCURRENCY = int(os.getenv("KAFKA_SEND_CONCURRENCY", "50"))


class KafkaProducerClient:
    """
    Typed async Kafka producer with automatic serialization,
    error handling, dead-letter queue support, and BATCH publishes.
    """

    def __init__(self, bootstrap_servers: str = KAFKA_BOOTSTRAP_SERVERS) -> None:
        self.bootstrap_servers = bootstrap_servers
        self._producer: AIOKafkaProducer | None = None

    async def start(self) -> None:
        self._producer = AIOKafkaProducer(
            bootstrap_servers=self.bootstrap_servers,
            value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
            key_serializer=lambda k: k.encode("utf-8") if k else None,
            acks="all",
            enable_idempotence=True,
            compression_type="lz4",          # LZ4 is faster than gzip on high volume
            max_batch_size=2_000_000,
            linger_ms=DEFAULT_LINGER_MS,
            request_timeout_ms=30_000,
            retry_backoff_ms=250,
        )
        await self._producer.start()
        logger.info("Kafka producer started", extra={"servers": self.bootstrap_servers})

    async def stop(self) -> None:
        if self._producer:
            try:
                await self._producer.flush()
            finally:
                await self._producer.stop()
            logger.info("Kafka producer stopped")

    async def send(
        self,
        topic: str,
        value: dict[str, Any] | Any,
        key: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> bool:
        """Send a single message to a Kafka topic."""
        if not self._producer:
            raise RuntimeError("Producer not started. Call start() first.")

        try:
            if hasattr(value, "model_dump"):
                value = value.model_dump(mode="json")

            kafka_headers: list[tuple[str, bytes]] = []
            if headers:
                kafka_headers = [(k, v.encode("utf-8")) for k, v in headers.items()]

            await self._producer.send_and_wait(
                topic,
                value=value,
                key=key,
                headers=kafka_headers,
            )
            logger.debug(f"Sent message to {topic}", extra={"key": key})
            return True

        except KafkaConnectionError as e:
            logger.error(f"Kafka connection error sending to {topic}: {e}")
            return False
        except Exception as e:
            logger.exception(f"Failed to send message to {topic}: {e}")
            await self._send_to_dlq(topic, value, str(e))
            return False

    async def send_batch(
        self,
        topic: str,
        messages: list[tuple[Any, str | None] | Any],
        batch_size: int | None = None,
    ) -> int:
        """
        Send messages in parallel batches with concurrency control.

        `messages` can be:
          - list of raw payloads (no keys):  [d1, d2, d3]
          - list of (payload, key) tuples:   [(d1, k1), (d2, k2)]

        Returns the count of successfully published messages.
        """
        if not self._producer:
            raise RuntimeError("Producer not started. Call start() first.")

        if not messages:
            return 0

        batch_size = batch_size or DEFAULT_BATCH_SIZE
        sem = asyncio.Semaphore(SEND_BATCH_CONCURRENCY)

        # Normalize to (payload, key) tuples
        normalized: list[tuple[Any, str | None]] = []
        for m in messages:
            if isinstance(m, tuple):
                normalized.append(m)
            else:
                normalized.append((m, None))

        successes = 0
        failures: list[tuple[Any, str | None, str]] = []

        async def _publish_one(payload: Any, key: str | None) -> None:
            nonlocal successes
            async with sem:
                try:
                    if hasattr(payload, "model_dump"):
                        payload = payload.model_dump(mode="json")
                    # Fire & forget but await the Future (we want flush)
                    fut = await self._producer.send(topic, value=payload, key=key)
                    try:
                        await asyncio.wait_for(fut, timeout=20.0)
                        successes += 1
                    except asyncio.TimeoutError:
                        failures.append((payload, key, "publish_timeout"))
                    except KafkaError as ke:
                        failures.append((payload, key, f"kafka_error:{ke}"))
                except Exception as e:
                    failures.append((payload, key, str(e)))

        # Process in sub-batches to keep memory bounded
        total = len(normalized)
        for start in range(0, total, batch_size):
            chunk = normalized[start:start + batch_size]
            tasks = [asyncio.create_task(_publish_one(p, k)) for (p, k) in chunk]
            await asyncio.gather(*tasks)

        # Dead-letter any failed messages from this batch
        for payload, key, err in failures:
            await self._send_to_dlq(topic, payload, err, key=key)

        if failures:
            logger.warning(
                f"Batch publish to '{topic}': {successes}/{len(normalized)} ok, "
                f"{len(failures)} sent to DLQ"
            )
        return successes

    async def _send_to_dlq(
        self,
        original_topic: str,
        value: Any,
        error: str,
        key: str | None = None,
    ) -> None:
        """Send failed message to dead-letter queue."""
        if not self._producer:
            return
        try:
            dlq_topic = f"{original_topic}.dlq"
            dlq_message = {
                "original_topic": original_topic,
                "original_key": key,
                "error": error,
                "message_id": str(uuid4()),
                "failed_at": __import__("datetime").datetime.utcnow().isoformat(),
                "payload": value,
            }
            await self._producer.send_and_wait(dlq_topic, value=dlq_message)
        except Exception:
            logger.exception("Failed to send to DLQ")

    async def __aenter__(self) -> "KafkaProducerClient":
        await self.start()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.stop()


_global_producer: KafkaProducerClient | None = None


async def get_producer() -> KafkaProducerClient:
    """Get or create global producer instance."""
    global _global_producer
    if _global_producer is None:
        _global_producer = KafkaProducerClient()
        await _global_producer.start()
    return _global_producer
```

---

Grouped explanations:

- `start()` config: producer uses `acks='all'`, `enable_idempotence=True`, LZ4 compression, `linger_ms` to encourage broker-side batching, and increased `max_batch_size` for throughput.
- `send()`: single-message send with JSON serialization (supports Pydantic `model_dump`), header encoding, and DLQ fallback on unexpected errors.
- `send_batch()`: key function — normalizes messages, publishes them concurrently with a semaphore-limited concurrency, awaits futures per message, collects failures and routes them to DLQ, and returns successful count. It processes messages in sub-batches to limit memory.
- `_send_to_dlq()`: posts failed payloads to `<topic>.dlq` with metadata for debugging and retries.
- `get_producer()`: convenience global singleton to reuse producer across services.

Notes:
- `send_batch()` trades off eventual consistency for throughput by firing many concurrent `send()` futures but still awaits their results to know success vs failure and to send failed records to DLQ.
- Tuning knobs: `KAFKA_PRODUCER_BATCH_SIZE`, `KAFKA_PRODUCER_LINGER_MS`, and `KAFKA_SEND_CONCURRENCY` in env.
