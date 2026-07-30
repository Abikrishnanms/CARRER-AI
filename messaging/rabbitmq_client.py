"""
database/rabbitmq_client.py

Thin wrapper around RabbitMQ for publishing and consuming messages
between agents.
"""

import json
import pika

from app.config.settings import settings
from app.utils.logger import get_logger


class RabbitMQClient:
    def __init__(self):
        self.logger = get_logger("rabbitmq_client")
        self.connection = pika.BlockingConnection(
            pika.URLParameters(settings.RABBITMQ_URL)
        )
        self.channel = self.connection.channel()

    def publish(self, queue_name: str, message: dict):
        self.channel.queue_declare(queue=queue_name, durable=True)
        self.channel.basic_publish(
            exchange="",
            routing_key=queue_name,
            body=json.dumps(message),
            properties=pika.BasicProperties(delivery_mode=2),  # persistent
        )
        self.logger.info(f"Published to {queue_name}: {message}")

    def consume(self, queue_name: str, callback):
        self.channel.queue_declare(queue=queue_name, durable=True)

        def wrapper(ch, method, properties, body):
            data = json.loads(body)
            callback(data)
            ch.basic_ack(delivery_tag=method.delivery_tag)

        self.channel.basic_qos(prefetch_count=1)
        self.channel.basic_consume(queue=queue_name, on_message_callback=wrapper)
        self.logger.info(f"Listening on {queue_name}...")
        self.channel.start_consuming()

    def close(self):
        self.connection.close()