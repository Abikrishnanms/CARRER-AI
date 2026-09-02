"""
Verifier Service — Scam Detection + Authenticity Verification (BATCH MODE).
Consumes from Kafka topic: job.enriched
Publishes to Kafka topic: job.verified or job.rejected
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
from shared.kafka.producer import KafkaProducerClient
from shared.kafka.topics import TOPICS
from shared.database.session import get_mongo_client

logger = logging.getLogger(__name__)

DEFAULT_BATCH_SIZE = int(os.getenv("VERIFIER_BATCH_SIZE", "180"))
CONCURRENT_JOBS = int(os.getenv("VERIFIER_WORKERS", "70"))


class VerifierService:
    """
    Verification Agent (batch mode).
    - Runs ScamDetectionAgent on each job (parallel via semaphore)
    - Computes quality score
    - Routes safe jobs to job.verified, risky to job.rejected (send_batch)
    - Persists verification data to MongoDB (bulk_write)
    """

    SCAM_THRESHOLD = 0.6

    def __init__(self) -> None:
        self.producer = KafkaProducerClient()
        self.batch_size = DEFAULT_BATCH_SIZE
        self.consumer = KafkaConsumerClient(
            topics=[TOPICS.JOB_ENRICHED],
            group_id="verifier-service",
            max_poll_records=max(250, self.batch_size * 2),
        )
        self.scam_agent = None
        self.running = False

    async def start(self) -> None:
        from services.verifier.agents.scam_detector import ScamDetectionAgent
        self.scam_agent = ScamDetectionAgent()

        await self.producer.start()
        await self.consumer.start()
        self.running = True
        logger.info("🛡️ Verifier service started (batch=%d, workers=%d)", self.batch_size, CONCURRENT_JOBS)
        await self.consumer.consume_batch(self._handle_batch, batch_size=self.batch_size, timeout_ms=2000)

    async def stop(self) -> None:
        self.running = False
        await self.producer.stop()
        await self.consumer.stop()

    async def _verify_one(self, message: dict) -> tuple[str, dict, dict, dict, bool] | None:
        """Verify a single job. Returns (job_id, updated_msg, verification_update, event_doc, is_rejected) or None."""
        job_id = message.get("_id", message.get("id", str(uuid.uuid4())))
        try:
            result = await self.scam_agent.analyze(
                job_id=job_id,
                title=message.get("title", ""),
                description=message.get("description", ""),
                company_name=message.get("company_name", ""),
                salary_min=message.get("salary_min"),
                salary_max=message.get("salary_max"),
                apply_url=message.get("apply_url"),
            )

            from shared.utils.url import verify_live_url

            apply_url = message.get("apply_url")
            url_check = await verify_live_url(apply_url, timeout=2.5) if apply_url else {"is_reachable": False}
            is_reachable = url_check.get("is_reachable", True)

            quality_score = self._compute_quality_score(message, result.scam_probability)
            is_rejected = result.scam_probability >= self.SCAM_THRESHOLD

            # Composite Trust Score (0-100)
            base_trust = (1.0 - result.scam_probability) * 70.0 + (quality_score / 100.0) * 20.0
            if is_reachable:
                base_trust += 10.0
            trust_score = round(min(100.0, max(0.0, base_trust)), 1)

            trust_reasons = list(result.trust_reasons)
            if is_reachable:
                trust_reasons.append("Active and reachable application URL")
            warning_signals = list(result.warning_signals)
            if not is_reachable and apply_url:
                warning_signals.append("Application URL failed HTTP ping check")

            verification_data = {
                "scam_probability": result.scam_probability,
                "scam_risk_level": result.risk_level,
                "scam_triggered_rules": result.triggered_rules,
                "authenticity_score": max(0, 100 - result.scam_probability * 100),
                "quality_score": quality_score,
                "trust_score": trust_score,
                "trust_reasons": trust_reasons,
                "warning_signals": warning_signals,
                "is_url_reachable": is_reachable,
                "is_verified": result.scam_probability < 0.2 and trust_score >= 60,
                "status": "rejected" if is_rejected else "published",
                "updated_at": datetime.utcnow(),
            }

            message.update(verification_data)

            event_doc = {
                "_id": str(uuid.uuid4()),
                "job_id": job_id,
                "event_type": "job.verified",
                "agent_name": "verifier",
                "status": "rejected" if is_rejected else "passed",
                "payload": {
                    "scam_probability": result.scam_probability,
                    "risk_level": result.risk_level,
                    "triggered_rules": result.triggered_rules[:5],
                    "quality_score": quality_score,
                },
                "duration_ms": 0,
                "created_at": datetime.utcnow(),
            }

            return (job_id, message, verification_data, event_doc, is_rejected)

        except Exception as e:
            logger.exception(f"Verification failed for {job_id}: {e}")
            return None

    async def _handle_batch(self, messages: list[dict]) -> None:
        start = time.monotonic()
        n = len(messages)
        if n == 0:
            return

        sem = asyncio.Semaphore(CONCURRENT_JOBS)

        async def _with_sem(msg: dict) -> tuple[str, dict, dict, dict, bool] | None:
            async with sem:
                t0 = time.monotonic()
                result = await self._verify_one(msg)
                if result is not None:
                    jid, upd, vdata, ev, rej = result
                    ev["duration_ms"] = (time.monotonic() - t0) * 1000
                    return (jid, upd, vdata, ev, rej)
                return None

        tasks = [asyncio.create_task(_with_sem(m)) for m in messages]
        results = await asyncio.gather(*tasks)
        results = [r for r in results if r is not None]

        if not results:
            logger.warning("Verifier batch: 0/%d succeeded", n)
            return

        job_updates = []
        event_inserts = []
        verified_list: list[tuple[dict, str]] = []
        rejected_list: list[tuple[dict, str]] = []
        rejected_count = 0

        for job_id, updated_msg, verif_data, event_doc, is_rejected in results:
            job_updates.append({
                "filter": {"_id": job_id},
                "update": {"$set": verif_data},
                "upsert": True,
            })
            event_inserts.append(event_doc)
            if is_rejected:
                rejected_list.append((updated_msg, job_id))
                rejected_count += 1
            else:
                verified_list.append((updated_msg, job_id))

        client = get_mongo_client()
        db = client["jobplatform"]

        try:
            from pymongo import UpdateOne, InsertOne
            bulk_ops = [UpdateOne(**u) for u in job_updates]
            if bulk_ops:
                await db.jobs.bulk_write(bulk_ops, ordered=False)
        except Exception as e:
            logger.warning("Verifier bulk_write jobs failed (%s), falling back per-job", e)
            for job_id, _m, verif_data, _e, _r in results:
                try:
                    await db.jobs.update_one({"_id": job_id}, {"$set": verif_data}, upsert=True)
                except Exception:
                    pass

        try:
            from pymongo import InsertOne
            bulk_events = [InsertOne(e) for e in event_inserts]
            if bulk_events:
                await db.pipeline_events.bulk_write(bulk_events, ordered=False)
        except Exception as e:
            logger.warning("Verifier bulk_write events failed: %s", e)

        if verified_list:
            try:
                await self.producer.send_batch(TOPICS.JOB_VERIFIED, verified_list)
            except Exception as e:
                logger.exception("Verifier send_batch (verified) failed: %s", e)

        if rejected_list:
            try:
                await self.producer.send_batch(TOPICS.JOB_REJECTED, rejected_list)
            except Exception as e:
                logger.exception("Verifier send_batch (rejected) failed: %s", e)

        elapsed_ms = (time.monotonic() - start) * 1000
        jps = (len(results) / elapsed_ms * 1000) if elapsed_ms > 0 else 0
        logger.info(
            "🛡️ Verifier: %d/%d (rej=%d) in %.0fms (%.1f j/s)",
            len(results), n, rejected_count, elapsed_ms, jps,
        )

    def _compute_quality_score(self, job: dict, scam_prob: float) -> float:
        score = 50.0
        desc = job.get("description", "")
        if len(desc) > 500:
            score += 15
        elif len(desc) > 200:
            score += 10
        elif len(desc) > 50:
            score += 5
        skills = job.get("required_skills", [])
        if len(skills) >= 5:
            score += 15
        elif len(skills) >= 2:
            score += 10
        elif len(skills) >= 1:
            score += 5
        if job.get("salary_min") and job.get("salary_max"):
            score += 10
        if job.get("apply_url"):
            score += 5
        score -= scam_prob * 40
        return max(0.0, min(100.0, score))


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    service = VerifierService()
    try:
        await service.start()
    except KeyboardInterrupt:
        await service.stop()


if __name__ == "__main__":
    asyncio.run(main())
