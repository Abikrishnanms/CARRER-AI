"""
database/qdrant_client.py
"""

import uuid
from qdrant_client import QdrantClient as PyQdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

from app.utils.logger import get_logger


class QdrantClient:
    COLLECTION_NAME = "job_embeddings"
    RESUME_COLLECTION_NAME = "resume_embeddings"
    VECTOR_SIZE = 384

    def __init__(self, host: str = "localhost", port: int = 6333):
        self.logger = get_logger("qdrant_client")
        self.client = PyQdrantClient(host=host, port=port)
        self._ensure_collection(self.COLLECTION_NAME)
        self._ensure_collection(self.RESUME_COLLECTION_NAME)

    def _ensure_collection(self, name: str):
        collections = [c.name for c in self.client.get_collections().collections]
        if name not in collections:
            self.client.create_collection(
                collection_name=name,
                vectors_config=VectorParams(size=self.VECTOR_SIZE, distance=Distance.COSINE),
            )
            self.logger.info(f"Created collection {name}")

    def upsert_vector(self, job_url: str, vector: list, payload: dict):
        point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, job_url))
        self.client.upsert(
            collection_name=self.COLLECTION_NAME,
            points=[PointStruct(id=point_id, vector=vector, payload=payload)],
        )
        self.logger.info(f"Upserted vector for {job_url}")

    def upsert_resume_vector(self, user_id: int, vector: list, payload: dict):
        point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"resume_{user_id}"))
        self.client.upsert(
            collection_name=self.RESUME_COLLECTION_NAME,
            points=[PointStruct(id=point_id, vector=vector, payload=payload)],
        )
        self.logger.info(f"Upserted resume vector for user {user_id}")

    def search(self, vector: list, limit: int = 5):
        result = self.client.query_points(
            collection_name=self.COLLECTION_NAME,
            query=vector,
            limit=limit,
        )
        return result.points

    def recommend_jobs(self, resume_vector: list, limit: int = 10):
        result = self.client.query_points(
            collection_name=self.COLLECTION_NAME,
            query=resume_vector,
            limit=limit,
        )
        return result.points

    def close(self):
        pass