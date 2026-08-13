"""
Kafka producer and consumer abstractions with typed events.
Uses aiokafka for async operation.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any
from uuid import uuid4

from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaConnectionError

logger = logging.getLogger(__name__)

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")


class KafkaProducerClient:
    """
    Typed async Kafka producer with automatic serialization,
    error handling, and dead-letter queue support.
    """

    def __init__(self, bootstrap_servers: str = KAFKA_BOOTSTRAP_SERVERS) -> None:
        self.bootstrap_servers = bootstrap_servers
        self._producer: AIOKafkaProducer | None = None

    async def start(self) -> None:
        self._producer = AIOKafkaProducer(
            bootstrap_servers=self.bootstrap_servers,
            value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
            key_serializer=lambda k: k.encode("utf-8") if k else None,
            acks="all",                    # Wait for all replicas
            enable_idempotence=True,       # Exactly-once semantics
            compression_type="gzip",
            max_batch_size=1_000_000,
            linger_ms=5,
        )
        await self._producer.start()
        logger.info("Kafka producer started", extra={"servers": self.bootstrap_servers})

    async def stop(self) -> None:
        if self._producer:
            await self._producer.stop()
            logger.info("Kafka producer stopped")

    async def send(
        self,
        topic: str,
        value: dict[str, Any] | Any,
        key: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> bool:
        """Send a message to a Kafka topic."""
        if not self._producer:
            raise RuntimeError("Producer not started. Call start() first.")

        try:
            # Serialize Pydantic models
            if hasattr(value, "model_dump"):
                value = value.model_dump(mode="json")

            kafka_headers = []
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
            # Attempt to send to DLQ
            await self._send_to_dlq(topic, value, str(e))
            return False

    async def send_batch(
        self,
        topic: str,
        messages: list[dict[str, Any]],
    ) -> int:
        """Send a batch of messages. Returns count of successful sends."""
        success_count = 0
        for msg in messages:
            if await self.send(topic, msg):
                success_count += 1
        return success_count

    async def _send_to_dlq(
        self,
        original_topic: str,
        value: Any,
        error: str,
    ) -> None:
        """Send failed message to dead-letter queue."""
        try:
            dlq_topic = f"{original_topic}.dlq"
            dlq_message = {
                "original_topic": original_topic,
                "error": error,
                "message_id": str(uuid4()),
                "payload": value,
            }
            await self._producer.send_and_wait(dlq_topic, value=dlq_message)
        except Exception:
            logger.exception("Failed to send to DLQ")

    async def __aenter__(self) -> KafkaProducerClient:
        await self.start()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.stop()


# Global producer instance (initialized at service startup)
_global_producer: KafkaProducerClient | None = None


async def get_producer() -> KafkaProducerClient:
    """Get or create global producer instance."""
    global _global_producer
    if _global_producer is None:
        _global_producer = KafkaProducerClient()
        await _global_producer.start()
    return _global_producer
