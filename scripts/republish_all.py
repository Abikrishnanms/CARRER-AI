"""
scripts/republish_all.py

Re-publishes every raw posting already in Mongo back onto the
raw_postings_ready queue, so agents can re-process with a new strategy.
"""

from database.mongo_client import MongoClient
from messaging.rabbitmq_client import RabbitMQClient

mongo = MongoClient()
queue = RabbitMQClient()

count = 0
for doc in mongo.raw_postings.find({}):
    queue.publish(
        queue_name="raw_postings_ready",
        message={"url": doc.get("url"), "source": doc.get("source")},
    )
    count += 1

print(f"Republished {count} postings")
mongo.close()
queue.close()