"""
Verifier Service — Scam Detection + Authenticity Verification.
Consumes from Kafka topic: job.enriched
Publishes to Kafka topic: job.verified or job.rejected
"""

from __future__ import annotations

import asyncio
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


class VerifierService:
    """
    Verification Agent.
    - Runs ScamDetectionAgent on each job
    - Computes quality score
    - Routes safe jobs to job.verified
    - Routes risky jobs to job.rejected
    - Persists verification data to MongoDB
    """

    SCAM_THRESHOLD = 0.6  # Jobs above this probability are rejected

    def __init__(self) -> None:
        self.producer = KafkaProducerClient()
        self.consumer = KafkaConsumerClient(
            topics=[TOPICS.JOB_ENRICHED],
            group_id="verifier-service",
        )
        self.scam_agent = None
        self.running = False

    async def start(self) -> None:
        from services.verifier.agents.scam_detector import ScamDetectionAgent
        self.scam_agent = ScamDetectionAgent()

        await self.producer.start()
        await self.consumer.start()
        self.running = True
        logger.info("🛡️ Verifier service started")
        await self.consumer.consume(self._handle_message)

    async def stop(self) -> None:
        self.running = False
        await self.producer.stop()
        await self.consumer.stop()

    async def _handle_message(self, message: dict, *args) -> None:
        start = time.monotonic()
        job_id = message.get("_id", message.get("id", str(uuid.uuid4())))

        try:
            # Run scam detection
            result = await self.scam_agent.analyze(
                job_id=job_id,
                title=message.get("title", ""),
                description=message.get("description", ""),
                company_name=message.get("company_name", ""),
                salary_min=message.get("salary_min"),
                salary_max=message.get("salary_max"),
                apply_url=message.get("apply_url"),
            )

            # Compute a simple quality score
            quality_score = self._compute_quality_score(message, result.scam_probability)

            # Build verification data
            verification_data = {
                "scam_probability": result.scam_probability,
                "scam_risk_level": result.risk_level,
                "scam_triggered_rules": result.triggered_rules,
                "authenticity_score": max(0, 100 - result.scam_probability * 100),
                "quality_score": quality_score,
                "is_verified": result.scam_probability < 0.2,
                "updated_at": datetime.utcnow(),
            }

            is_rejected = result.scam_probability >= self.SCAM_THRESHOLD

            if is_rejected:
                verification_data["status"] = "rejected"
            else:
                verification_data["status"] = "verified"

            message.update(verification_data)

            # Persist to MongoDB
            client = get_mongo_client()
            db = client["jobplatform"]
            await db.jobs.update_one(
                {"_id": job_id},
                {"$set": verification_data},
                upsert=True,
            )

            # Log pipeline event
            duration_ms = (time.monotonic() - start) * 1000
            await db.pipeline_events.insert_one({
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
                "duration_ms": duration_ms,
                "created_at": datetime.utcnow(),
            })

            # Route to appropriate topic
            if is_rejected:
                await self.producer.send(TOPICS.JOB_REJECTED, message, key=job_id)
                logger.info(f"🚫 Job {job_id} rejected (scam_prob={result.scam_probability:.2f})")
            else:
                await self.producer.send(TOPICS.JOB_VERIFIED, message, key=job_id)
                logger.debug(f"✅ Job {job_id} verified (quality={quality_score:.1f})")

        except Exception as e:
            logger.exception(f"Verification failed for {job_id}: {e}")

    def _compute_quality_score(self, job: dict, scam_prob: float) -> float:
        """
        Compute a 0-100 quality score based on:
        - Description length
        - Skills extracted
        - Salary info present
        - Low scam probability
        """
        score = 50.0  # Baseline

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

        # Penalize for scam probability
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
