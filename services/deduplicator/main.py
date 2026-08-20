"""
Deduplicator Service — Duplicate Detection Agent.
Consumes from Kafka topic: job.cleaned
Publishes to Kafka topic: job.deduplicated
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
import uuid
from datetime import datetime
from typing import Any

from shared.kafka.consumer import KafkaConsumerClient
from shared.kafka.producer import KafkaProducerClient
from shared.kafka.topics import TOPICS
from shared.database.session import get_mongo_client

logger = logging.getLogger(__name__)


def generate_fingerprint(title: str, company: str, location: str | None) -> str:
    """Generate a content-based fingerprint for similarity matching with normalized title/company aliases."""
    import re
    clean_title = title.lower().strip()
    clean_title = re.sub(r"\b(dev|developer)\b", "developer", clean_title)
    clean_title = re.sub(r"\b(eng|engineer)\b", "engineer", clean_title)
    clean_title = re.sub(r"[^\w\s]", "", clean_title)

    clean_company = re.sub(r"[^\w\s]", "", company.lower().strip())
    clean_loc = re.sub(r"[^\w\s]", "", (location or "").lower().strip())

    normalized = f"{clean_title}|{clean_company}|{clean_loc}"
    return hashlib.sha256(normalized.encode()).hexdigest()


class DeduplicatorService:
    """
    Duplicate Detection Agent — HIGH-THROUGHPUT BATCH MODE.

    Optimizations:
    - Batch consumption from job.cleaned (100+ msgs)
    - Bulk content-fingerprint + source_job_id dedup using ONE $in query
      (N DB round-trips → 3 total DB calls per batch)
    - MongoDB bulk_write for updates
    - Kafka send_batch for job.deduplicated
    """

    DEFAULT_BATCH_SIZE = int(__import__("os").getenv("DEDUP_BATCH_SIZE", "200"))
    CONCURRENT_TASKS = int(__import__("os").getenv("DEDUP_WORKERS", "40"))

    def __init__(self) -> None:
        self.producer = KafkaProducerClient()
        self.consumer = KafkaConsumerClient(
            topics=[TOPICS.JOB_CLEANED],
            group_id="deduplicator-service",
            max_poll_records=max(400, self.DEFAULT_BATCH_SIZE * 2),
        )
        self.running = False
        self._sem = asyncio.Semaphore(self.CONCURRENT_TASKS)

    async def start(self) -> None:
        await self.producer.start()
        await self.consumer.start()
        self.running = True
        logger.info(
            f"🔍 Deduplicator service started (batch={self.DEFAULT_BATCH_SIZE}, "
            f"workers={self.CONCURRENT_TASKS})"
        )
        await self.consumer.consume_batch(
            self._handle_batch,
            batch_size=self.DEFAULT_BATCH_SIZE,
            timeout_ms=2000,
        )

    async def stop(self) -> None:
        self.running = False
        await self.producer.stop()
        await self.consumer.stop()

    async def _handle_batch(self, messages: list[dict]) -> None:
        t0 = time.monotonic()
        if not messages:
            return

        client = get_mongo_client()
        db = client["jobplatform"]

        # Step 1: Pre-compute fingerprints for all messages
        prepared: list[dict] = []
        for msg in messages:
            job_id = msg.get("_id") or msg.get("id") or str(uuid.uuid4())
            fp = generate_fingerprint(
                msg.get("title", ""),
                msg.get("company_name", ""),
                msg.get("location_city"),
            )
            prepared.append({
                "job_id": job_id,
                "source": msg.get("source", ""),
                "source_job_id": msg.get("source_job_id", ""),
                "fingerprint": fp,
                "msg": msg,
            })

        # Step 2: ONE DB query for all exact source+source_job_id matches
        source_pairs: list[tuple[str, str]] = [
            (p["source"], p["source_job_id"]) for p in prepared
            if p["source"] and p["source_job_id"]
        ]
        exact_duplicates: dict[str, set[str]] = {}
        if source_pairs:
            or_clauses = [
                {"source": s, "source_job_id": sjid}
                for (s, sjid) in source_pairs
            ]
            cursor = db.jobs.find(
                {"$or": or_clauses},
                {"_id": 1, "source": 1, "source_job_id": 1},
            )
            async for existing in cursor:
                key = f"{existing['source']}|{existing['source_job_id']}"
                exact_duplicates.setdefault(key, set()).add(str(existing["_id"]))

        # Step 3: ONE DB query for all fingerprint near-duplicates
        fps = [p["fingerprint"] for p in prepared]
        near_duplicates: dict[str, set[str]] = {}
        if fps:
            cursor = db.jobs.find(
                {"content_fingerprint": {"$in": fps}},
                {"_id": 1, "content_fingerprint": 1},
            )
            async for existing in cursor:
                fp_val = existing.get("content_fingerprint")
                if fp_val:
                    near_duplicates.setdefault(fp_val, set()).add(str(existing["_id"]))

        # Step 4: Classify each job (exact → near → unique) ignoring self-matches
        seen_in_batch_source_keys: dict[str, str] = {}
        seen_in_batch_fps: dict[str, str] = {}
        unique_messages: list[tuple[dict, str]] = []
        update_ops: list = []
        event_inserts: list = []

        try:
            from pymongo import UpdateOne, InsertOne
        except ImportError:
            UpdateOne = InsertOne = None

        for p in prepared:
            jid = str(p["job_id"])
            msg = dict(p["msg"])
            msg["_id"] = jid

            is_dup = False
            dup_of = None
            exact_key = f"{p['source']}|{p['source_job_id']}"

            # Check DB exact matches (exclude self)
            other_exact = [eid for eid in exact_duplicates.get(exact_key, set()) if eid != jid]
            if other_exact:
                is_dup = True
                dup_of = other_exact[0]
            elif exact_key in seen_in_batch_source_keys and seen_in_batch_source_keys[exact_key] != jid:
                is_dup = True
                dup_of = seen_in_batch_source_keys[exact_key]
            else:
                fp = p["fingerprint"]
                other_near = [eid for eid in near_duplicates.get(fp, set()) if eid != jid]
                if other_near:
                    is_dup = True
                    dup_of = other_near[0]
                elif fp in seen_in_batch_fps and seen_in_batch_fps[fp] != jid:
                    is_dup = True
                    dup_of = seen_in_batch_fps[fp]
                else:
                    msg["content_fingerprint"] = fp

            if not is_dup:
                seen_in_batch_source_keys[exact_key] = jid
                seen_in_batch_fps[p["fingerprint"]] = jid

            msg["is_duplicate"] = is_dup
            msg["duplicate_of_id"] = dup_of
            msg["status"] = "deduplicated" if not is_dup else "duplicate"
            msg.setdefault("updated_at", datetime.utcnow())

            if UpdateOne is not None:
                update_ops.append(UpdateOne({"_id": jid}, {"$set": msg}, upsert=True))
            else:
                await db.jobs.update_one({"_id": jid}, {"$set": msg}, upsert=True)

            if InsertOne is not None:
                event_inserts.append(InsertOne({
                    "_id": str(uuid.uuid4()),
                    "job_id": jid,
                    "event_type": "job.deduplicated",
                    "agent_name": "deduplicator",
                    "status": "duplicate" if is_dup else "unique",
                    "payload": {"duplicate_of": dup_of} if is_dup else {},
                    "duration_ms": 0.0,
                    "created_at": datetime.utcnow(),
                }))

            if not is_dup:
                unique_messages.append((msg, jid))

        # Step 5: Bulk upsert jobs + bulk insert events
        if update_ops:
            try:
                await db.jobs.bulk_write(update_ops, ordered=False)
            except Exception as e:
                logger.warning(f"Dedup bulk_write jobs failed: {e}")
        if event_inserts:
            try:
                await db.pipeline_events.bulk_write(event_inserts, ordered=False)
            except Exception:
                pass

        # Step 6: Batch publish unique jobs downstream
        published = 0
        if unique_messages:
            published = await self.producer.send_batch(TOPICS.JOB_DEDUPLICATED, unique_messages)

        elapsed = time.monotonic() - t0
        total = len(messages)
        duplicates = total - len(unique_messages)
        logger.info(
            f"🔍 Dedup batch: {total} in → {published} unique, {duplicates} dupes "
            f"in {elapsed*1000:.0f}ms ({total/max(0.001, elapsed):.0f} j/s)"
        )


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    service = DeduplicatorService()
    try:
        await service.start()
    except KeyboardInterrupt:
        await service.stop()


if __name__ == "__main__":
    asyncio.run(main())
