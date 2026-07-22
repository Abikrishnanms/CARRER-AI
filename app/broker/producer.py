"""
Session 4: RabbitMQ Producer.
Responsible for publishing messages to the queue.
"""

import json
from typing import Optional

import aio_pika
from aio_pika import ExchangeType, Message

from app.broker.queues import EXCHANGE_NAME, EXCHANGE_TYPE, RAW_JOBS_QUEUE, ROUTING_KEYS
from app.config.settings import settings
from app.models.job import RawJob
from app.models.messages import JobMessage
from app.utils.logging import get_logger

logger = get_logger(__name__)


class RabbitMQProducer:
    """Producer for publishing jobs to RabbitMQ."""

    def __init__(self):
        self._connection: Optional[aio_pika.Connection] = None
        self._channel: Optional[aio_pika.Channel] = None
        self._exchange: Optional[aio_pika.Exchange] = None

    async def connect(self) -> None:
        """Establish connection to RabbitMQ and declare exchange/queue."""
        try:
            self._connection = await aio_pika.connect_robust(
                settings.rabbitmq_url,
                client_properties={"connection_name": "careerai-producer"},
            )
            self._channel = await self._connection.channel()
            await self._channel.set_qos(prefetch_count=1)

            # Declare the exchange
            self._exchange = await self._channel.declare_exchange(
                name=EXCHANGE_NAME,
                type=ExchangeType.DIRECT,
                durable=True,
            )

            # Declare the raw jobs queue (durable = survives RabbitMQ restarts)
            queue = await self._channel.declare_queue(
                RAW_JOBS_QUEUE,
                durable=True,
                arguments={
                    "x-max-length": 50000,          # Max 50,000 messages
                    "x-message-ttl": 86400000,      # Auto-delete after 24 hours (ms)
                },
            )

            # Bind the queue to the exchange with the routing key
            await queue.bind(self._exchange, routing_key=ROUTING_KEYS["raw"])

            logger.info(f"RabbitMQ Producer connected. Queue: {RAW_JOBS_QUEUE}")

        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")
            raise

    async def publish_raw_job(self, job: RawJob, source_agent: str) -> None:
        """
        Publish a raw job to the queue.

        Args:
            job: The RawJob object
            source_agent: Name of the adapter (e.g., 'adzuna_adapter')
        """
        if not self._channel or not self._exchange:
            raise RuntimeError("Producer not connected. Call connect() first.")

        # 1. Create the message envelope
        message = JobMessage(
            source_agent=source_agent,
            source_platform=job.source_platform,
            job_id=job.job_id,
            payload=job.model_dump(mode="json"),  # Convert Pydantic model to dict
        )

        # 2. Serialize to JSON
        body = json.dumps(message.model_dump(mode="json"), default=str).encode()

        # 3. Create the RabbitMQ message
        aio_message = Message(
            body=body,
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,  # Save to disk
            headers={
                "message_id": message.message_id,
                "correlation_id": message.correlation_id,
                "source_agent": message.source_agent,
            },
        )

        # 4. Publish to the exchange with the routing key
        await self._exchange.publish(
            aio_message,
            routing_key=ROUTING_KEYS["raw"],
        )

        logger.debug(
            "Job published to RabbitMQ",
            job_id=job.job_id,
            title=job.title,
            platform=job.source_platform,
        )

    async def close(self) -> None:
        """Gracefully close the connection."""
        if self._connection and not self._connection.is_closed:
            await self._connection.close()
            logger.info("RabbitMQ Producer closed")