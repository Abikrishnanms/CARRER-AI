"""
database/qdrant_client.py

Thin wrapper around Qdrant for storing and querying job posting embeddings.
"""

import uuid
from qdrant_client import QdrantClient as PyQdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

from app.utils.logger import get_logger


class QdrantClient:
    COLLECTION_NAME = "job_embeddings"
    VECTOR_SIZE = 384  # matches all-MiniLM-L6-v2 output

    def __init__(self, host: str = "localhost", port: int = 6333):
        self.logger = get_logger("qdrant_client")
        self.client = PyQdrantClient(host=host, port=port)
        self._ensure_collection()

    def _ensure_collection(self):
        collections = [c.name for c in self.client.get_collections().collections]
        if self.COLLECTION_NAME not in collections:
            self.client.create_collection(
                collection_name=self.COLLECTION_NAME,
                vectors_config=VectorParams(size=self.VECTOR_SIZE, distance=Distance.COSINE),
            )
            self.logger.info(f"Created collection {self.COLLECTION_NAME}")

    def upsert_vector(self, job_url: str, vector: list, payload: dict):
        point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, job_url))
        self.client.upsert(
            collection_name=self.COLLECTION_NAME,
            points=[PointStruct(id=point_id, vector=vector, payload=payload)],
        )
        self.logger.info(f"Upserted vector for {job_url}")

    def search(self, vector: list, limit: int = 5):
        result = self.client.query_points(
            collection_name=self.COLLECTION_NAME,
            query=vector,
            limit=limit,
    )
        return result.points

    def close(self):
        pass