"""
database/mongo_client.py

Thin wrapper around MongoDB for storing raw job postings.
"""

from pymongo import MongoClient as PyMongoClient
from app.config.settings import settings
from app.utils.logger import get_logger


class MongoClient:
    def __init__(self):
        self.logger = get_logger("mongo_client")
        self.client = PyMongoClient(settings.MONGO_URI, serverSelectionTimeoutMS=5000)
        self.db = self.client[settings.MONGO_DB_NAME]
        self.raw_postings = self.db["raw_postings"]

    def insert_raw_posting(self, posting: dict):
        result = self.raw_postings.update_one(
            {"url": posting["url"]},
            {"$set": posting},
            upsert=True,
        )
        self.logger.info(f"Upserted posting: {posting.get('url')}")
        return result

    def get_by_url(self, url: str):
        return self.raw_postings.find_one({"url": url})

    def close(self):
        self.client.close()