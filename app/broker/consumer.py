"""
RabbitMQ Consumer: Listens to a queue and processes messages asynchronously.
"""

import json
import asyncio
from typing import Optional, Callable, Awaitable

import aio_pika
from aio_pika import Message, ExchangeType

from app.broker.queues import EXCHANGE_NAME, EXCHANGE_TYPE, DLQ_ERRORS
from app.config.settings import settings
from app.models.messages import JobMessage
from app.utils.logging import get_logger

logger = get_logger(__name__)


class RabbitMQConsumer:
    """
    RabbitMQ consumer that listens to a specific queue and processes messages.
    """

    def __init__(
        self,
        queue_name: str,
        prefetch_count: int = 10,
        requeue_on_error: bool = False,
    ):
        self.queue_name = queue_name
        self.prefetch_count = prefetch_count
        self.requeue_on_error = requeue_on_error
        self._connection: Optional[aio_pika.Connection] = None
        self._channel: Optional[aio_pika.Channel] = None
        self._queue: Optional[aio_pika.Queue] = None

    async def connect(self) -> None:
        """Establish connection and declare the queue."""
        try:
            self._connection = await aio_pika.connect_robust(
                settings.rabbitmq_url,
                client_properties={"connection_name": "careerai-consumer"},
            )
            self._channel = await self._connection.channel()
            await self._channel.set_qos(prefetch_count=self.prefetch_count)

            # Declare exchange
            exchange = await self._channel.declare_exchange(
                name=EXCHANGE_NAME,
                type=ExchangeType.DIRECT,
                durable=True,
            )

            # Declare queue WITHOUT dead-letter arguments
            # (We handle DLQ programmatically in the consumer)
            self._queue = await self._channel.declare_queue(
                self.queue_name,
                durable=True,
                arguments={
                    "x-max-length": 50000,
                    "x-message-ttl": 86400000,  # 24 hours
                },
            )

            # Bind to the exchange
            await self._queue.bind(exchange, routing_key=self.queue_name)

            logger.info(
                "Consumer connected",
                queue=self.queue_name,
                prefetch=self.prefetch_count,
            )

        except Exception as e:
            logger.error(f"Failed to connect consumer: {e}")
            raise

    async def consume(self, callback: Callable[[JobMessage], Awaitable[None]]) -> None:
        """
        Start consuming messages from the queue.

        Args:
            callback: Async function that receives a JobMessage and processes it.
        """
        if not self._queue:
            raise RuntimeError("Consumer not connected. Call connect() first.")

        async def on_message(message: Message) -> None:
            async with message.process(requeue=self.requeue_on_error):
                try:
                    # Parse the incoming message
                    body = json.loads(message.body.decode())
                    job_message = JobMessage(**body)

                    logger.debug(
                        "Message received",
                        queue=self.queue_name,
                        job_id=job_message.job_id,
                        retry_count=job_message.retry_count,
                    )

                    # Process the job
                    await callback(job_message)

                except json.JSONDecodeError as e:
                    logger.error(f"Failed to decode JSON: {e}")
                    # Send to DLQ directly
                    await self._send_to_dlq(message, str(e))

                except Exception as e:
                    logger.error(f"Processing error: {e}", exc_info=True)
                    # If requeue_on_error is True, the message will be requeued automatically
                    # Otherwise, we manually handle retry or DLQ
                    if not self.requeue_on_error:
                        await self._send_to_dlq(message, str(e))
                    else:
                        # In requeue mode, we just re-raise so the message stays in the queue
                        raise

        await self._queue.consume(on_message)
        logger.info(f"Started consuming from queue: {self.queue_name}")

        # Keep the consumer running
        try:
            await asyncio.Future()  # Run forever
        finally:
            await self.close()

    async def _send_to_dlq(self, message: Message, error: str) -> None:
        """Send a failed message to the Dead Letter Queue."""
        try:
            # Parse original message to update retry count
            body = json.loads(message.body.decode())
            job_message = JobMessage(**body)
            job_message.retry_count = job_message.retry_count + 1
            job_message.error_message = error

            if job_message.retry_count < job_message.max_retries:
                # Re-publish with incremented retry count
                await self._republish_message(job_message)
            else:
                # Send to DLQ
                await self._publish_to_dlq(job_message)

        except Exception as e:
            logger.error(f"Failed to send message to DLQ: {e}")

    async def _republish_message(self, message: JobMessage) -> None:
        """Re-publish a message for retry."""
        if not self._channel:
            raise RuntimeError("Channel not available")
        from app.broker.producer import RabbitMQProducer
        producer = RabbitMQProducer()
        await producer.connect()
        await producer.publish(
            queue_name=self.queue_name,
            message=message,
        )
        await producer.close()

    async def _publish_to_dlq(self, message: JobMessage) -> None:
        """Publish a message to the Dead Letter Queue."""
        from app.broker.producer import RabbitMQProducer
        producer = RabbitMQProducer()
        await producer.connect()
        await producer.publish(
            queue_name=DLQ_ERRORS,
            message=message,
        )
        await producer.close()

    async def close(self) -> None:
        """Close the connection."""
        if self._connection and not self._connection.is_closed:
            await self._connection.close()
            logger.info(f"Consumer closed: {self.queue_name}")