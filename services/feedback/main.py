"""
Feedback Service — User Feedback Learning Agent.
Collects user corrections and feedback on job classifications to improve model accuracy.
Consumes user feedback events and updates ML training datasets.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Any

from shared.database.session import get_mongo_client
from shared.kafka.consumer import KafkaConsumerClient
from shared.kafka.topics import TOPICS
from shared.utils.logging import setup_logging

logger = logging.getLogger(__name__)


class FeedbackService:
    """
    Feedback Learning Agent.
    - Collects user scam reports and job quality feedback
    - Updates job trust scores based on community feedback
    - Aggregates feedback for model retraining datasets
    - Flags companies with repeated negative feedback
    """

    def __init__(self) -> None:
        self.consumer = KafkaConsumerClient(
            topics=[TOPICS.FEEDBACK_RECEIVED],
            group_id="feedback-service",
        )
        self.running = False

    async def start(self) -> None:
        await self.consumer.start()
        self.running = True
        logger.info("💬 Feedback service started")
        await self.consumer.consume(self._handle_message)

    async def stop(self) -> None:
        self.running = False
        await self.consumer.stop()

    async def _handle_message(self, message: dict, *args) -> None:
        """Process a feedback event."""
        feedback_type = message.get("feedback_type")  # scam_report, quality, correction

        try:
            if feedback_type == "scam_report":
                await self._handle_scam_report(message)
            elif feedback_type == "quality":
                await self._handle_quality_feedback(message)
            elif feedback_type == "correction":
                await self._handle_correction(message)
            else:
                logger.warning(f"Unknown feedback type: {feedback_type}")
        except Exception as e:
            logger.exception(f"Feedback processing failed: {e}")

    async def _handle_scam_report(self, feedback: dict) -> None:
        """Process a user scam report — update job & company scam counters."""
        client = get_mongo_client()
        db = client["jobplatform"]

        job_id = feedback.get("job_id")
        company_name = feedback.get("company_name", "")

        if job_id:
            # Increment scam report count and potentially re-flag job
            job = await db.jobs.find_one({"_id": job_id})
            if job:
                new_reports = job.get("scam_report_count", 0) + 1
                update: dict[str, Any] = {
                    "scam_report_count": new_reports,
                    "updated_at": datetime.utcnow(),
                }

                # Auto-reject if too many reports
                if new_reports >= 5:
                    update["status"] = "rejected"
                    update["scam_probability"] = max(job.get("scam_probability", 0), 0.8)
                    logger.warning(f"Job {job_id} auto-rejected after {new_reports} scam reports")

                await db.jobs.update_one({"_id": job_id}, {"$set": update})

        # Increment company scam report counter
        if company_name:
            await db.companies.update_one(
                {"normalized_name": company_name.lower().strip()},
                {"$inc": {"scam_reports": 1}, "$set": {"updated_at": datetime.utcnow()}},
                upsert=False,
            )

        # Store feedback record
        await db.feedback_records.insert_one({
            "_id": str(uuid.uuid4()),
            "feedback_type": "scam_report",
            "job_id": job_id,
            "company_name": company_name,
            "reported_by": feedback.get("user_id"),
            "reason": feedback.get("reason"),
            "details": feedback.get("details"),
            "created_at": datetime.utcnow(),
        })

        logger.info(f"Scam report processed for job {job_id}")

    async def _handle_quality_feedback(self, feedback: dict) -> None:
        """Process quality rating feedback (thumbs up/down on job quality)."""
        client = get_mongo_client()
        db = client["jobplatform"]

        job_id = feedback.get("job_id")
        rating = feedback.get("rating")  # 1-5

        if job_id and rating:
            await db.feedback_records.insert_one({
                "_id": str(uuid.uuid4()),
                "feedback_type": "quality",
                "job_id": job_id,
                "rating": rating,
                "user_id": feedback.get("user_id"),
                "created_at": datetime.utcnow(),
            })

            # Update job's user rating aggregate
            await db.jobs.update_one(
                {"_id": job_id},
                {
                    "$inc": {"user_rating_count": 1, "user_rating_sum": rating},
                    "$set": {"updated_at": datetime.utcnow()},
                },
            )

    async def _handle_correction(self, feedback: dict) -> None:
        """Process a user correction (e.g., wrong skill extraction)."""
        client = get_mongo_client()
        db = client["jobplatform"]

        await db.feedback_records.insert_one({
            "_id": str(uuid.uuid4()),
            "feedback_type": "correction",
            "job_id": feedback.get("job_id"),
            "field": feedback.get("field"),       # "skills", "salary", "experience_level"
            "original_value": feedback.get("original_value"),
            "corrected_value": feedback.get("corrected_value"),
            "user_id": feedback.get("user_id"),
            "created_at": datetime.utcnow(),
        })

        logger.debug(f"Correction recorded for field '{feedback.get('field')}'")


async def main() -> None:
    setup_logging()
    service = FeedbackService()
    try:
        await service.start()
    except KeyboardInterrupt:
        await service.stop()


if __name__ == "__main__":
    asyncio.run(main())
