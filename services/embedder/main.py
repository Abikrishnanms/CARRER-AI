"""
Embedder Service — Vector Embedding Generator (BATCH MODE).
Consumes from Kafka topic: job.verified
Generates embeddings with batched SentenceTransformers.encode(),
batch-upserts to Qdrant, bulk-updates MongoDB with embedding_id + status="published".
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
import uuid
from datetime import datetime
from typing import Any

from shared.kafka.consumer import KafkaConsumerClient
from shared.kafka.topics import TOPICS
from shared.database.session import get_mongo_client

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION_JOBS", "job_embeddings")
VECTOR_SIZE = 384

DEFAULT_BATCH_SIZE = int(os.getenv("EMBEDDER_BATCH_SIZE", "96"))
CONCURRENT_DB_WRITES = int(os.getenv("EMBEDDER_DB_WORKERS", "40"))


class EmbedderService:
    """
    Embedding Generator Agent (batch mode).
    - Batched SentenceTransformer.encode(list_of_texts) → 10–100× faster than per-job
    - Batched Qdrant upsert (one call per batch)
    - bulk_write MongoDB status=published updates
    """

    def __init__(self) -> None:
        self.batch_size = DEFAULT_BATCH_SIZE
        self.consumer = KafkaConsumerClient(
            topics=[TOPICS.JOB_VERIFIED],
            group_id="embedder-service",
            max_poll_records=max(150, self.batch_size * 2),
        )
        self.model = None
        self.qdrant_client = None
        self.running = False

    async def start(self) -> None:
        try:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(EMBEDDING_MODEL)
            logger.info(f"Loaded embedding model: {EMBEDDING_MODEL}")
        except ImportError:
            logger.warning("sentence-transformers not installed — embedder will skip vectorization")

        try:
            from qdrant_client import QdrantClient
            from qdrant_client.models import Distance, VectorParams

            self.qdrant_client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
            collections = self.qdrant_client.get_collections().collections
            existing_names = [c.name for c in collections]
            if QDRANT_COLLECTION not in existing_names:
                self.qdrant_client.create_collection(
                    collection_name=QDRANT_COLLECTION,
                    vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
                )
                logger.info(f"Created Qdrant collection: {QDRANT_COLLECTION}")
        except Exception as e:
            logger.warning(f"Qdrant not available: {e} — embeddings will be stored but not indexed")

        await self.consumer.start()
        self.running = True
        logger.info("🧬 Embedder service started (batch=%d)", self.batch_size)
        await self.consumer.consume_batch(self._handle_batch, batch_size=self.batch_size, timeout_ms=3000)

    async def stop(self) -> None:
        self.running = False
        await self.consumer.stop()

    async def _handle_batch(self, messages: list[dict]) -> None:
        start = time.monotonic()
        n = len(messages)
        if n == 0:
            return

        job_ids: list[str] = []
        embed_texts: list[str] = []
        payloads: list[dict[str, Any]] = []
        messages_by_id: dict[str, dict] = {}

        for m in messages:
            job_id = m.get("_id", m.get("id", str(uuid.uuid4())))
            job_ids.append(job_id)
            messages_by_id[job_id] = m

            title = m.get("title", "")
            description = (m.get("description", "") or "")[:1000]
            skills = " ".join(m.get("required_skills", []) or [])
            company = m.get("company_name", "")
            location = m.get("location_city", "") or ""
            embed_texts.append(f"{title}. {company}. {location}. Skills: {skills}. {description}")

            payloads.append({
                "job_id": job_id,
                "title": title,
                "company_name": company,
                "location": location,
                "remote_type": m.get("remote_type", "unknown"),
                "experience_level": m.get("experience_level", "unknown"),
                "job_type": m.get("job_type", "unknown"),
                "salary_min": m.get("salary", {}).get("min_value") if isinstance(m.get("salary"), dict) else m.get("salary_min"),
                "salary_max": m.get("salary", {}).get("max_value") if isinstance(m.get("salary"), dict) else m.get("salary_max"),
            })

        embedding_ids = [str(uuid.uuid4()) for _ in job_ids]

        vectors_list: list[list[float]] | None = None
        if self.model is not None:
            try:
                loop = asyncio.get_event_loop()
                vectors_np = await loop.run_in_executor(
                    None,
                    lambda: self.model.encode(embed_texts, batch_size=min(64, len(embed_texts)), show_progress_bar=False),
                )
                vectors_list = [v.tolist() for v in vectors_np]
            except Exception as e:
                logger.exception("Batched embedding encode failed: %s", e)
                vectors_list = None

        if vectors_list is not None and self.qdrant_client is not None:
            try:
                from qdrant_client.models import PointStruct
                points = [
                    PointStruct(id=eid, vector=vec, payload=pl)
                    for eid, vec, pl in zip(embedding_ids, vectors_list, payloads)
                ]
                self.qdrant_client.upsert(collection_name=QDRANT_COLLECTION, points=points)
            except Exception as e:
                logger.exception("Qdrant batch upsert failed: %s", e)

        now_utc = datetime.utcnow()
        job_updates = []
        event_inserts = []

        for job_id, embedding_id in zip(job_ids, embedding_ids):
            set_doc = {
                "embedding_id": embedding_id,
                "embedding_model": EMBEDDING_MODEL,
                "status": "published",
                "updated_at": now_utc,
            }
            job_updates.append({"filter": {"_id": job_id}, "update": {"$set": set_doc}})
            event_inserts.append({
                "_id": str(uuid.uuid4()),
                "job_id": job_id,
                "event_type": "job.embedded",
                "agent_name": "embedder",
                "status": "success",
                "payload": {"embedding_id": embedding_id, "model": EMBEDDING_MODEL},
                "duration_ms": 0,
                "created_at": now_utc,
            })

        client = get_mongo_client()
        db = client["jobplatform"]

        try:
            from pymongo import UpdateOne, InsertOne
            bulk_ops = [UpdateOne(**u) for u in job_updates]
            if bulk_ops:
                await db.jobs.bulk_write(bulk_ops, ordered=False)
        except Exception as e:
            logger.warning("Embedder bulk_write jobs failed (%s), falling back per-job", e)
            sem = asyncio.Semaphore(CONCURRENT_DB_WRITES)

            async def _update_one(job_id: str, embedding_id: str) -> None:
                async with sem:
                    try:
                        await db.jobs.update_one(
                            {"_id": job_id},
                            {"$set": {
                                "embedding_id": embedding_id,
                                "embedding_model": EMBEDDING_MODEL,
                                "status": "published",
                                "updated_at": now_utc,
                            }},
                        )
                    except Exception:
                        pass

            await asyncio.gather(*[
                asyncio.create_task(_update_one(jid, eid))
                for jid, eid in zip(job_ids, embedding_ids)
            ])

        try:
            from pymongo import InsertOne
            bulk_events = [InsertOne(e) for e in event_inserts]
            if bulk_events:
                await db.pipeline_events.bulk_write(bulk_events, ordered=False)
        except Exception as e:
            logger.warning("Embedder bulk_write events failed: %s", e)

        elapsed_ms = (time.monotonic() - start) * 1000
        jps = (len(job_ids) / elapsed_ms * 1000) if elapsed_ms > 0 else 0
        logger.info(
            "🧬 Embedder: %d jobs, vectors=%s, qdrant=%s in %.0fms (%.1f j/s)",
            len(job_ids),
            "yes" if vectors_list is not None else "no",
            "yes" if vectors_list is not None and self.qdrant_client is not None else "no",
            elapsed_ms, jps,
        )


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    service = EmbedderService()
    try:
        await service.start()
    except KeyboardInterrupt:
        await service.stop()


if __name__ == "__main__":
    asyncio.run(main())
