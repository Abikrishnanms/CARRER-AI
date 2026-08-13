"""
Notifier Service — Smart Notification Agent.
Consumes from Kafka topic: job.verified
Matches verified jobs against user SavedSearches in MongoDB,
and logs notification events.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
import uuid
from datetime import datetime
from typing import Any

from shared.kafka.consumer import KafkaConsumerClient
from shared.kafka.topics import TOPICS
from shared.database.session import get_mongo_client

logger = logging.getLogger(__name__)


class NotifierService:
    """
    Notification Agent.
    - Listens for verified jobs
    - Matches jobs against user SavedSearch criteria in MongoDB
    - Creates NotificationLog entries in MongoDB
    - Supports email, telegram, webhook channels (simulation)
    """

    def __init__(self) -> None:
        self.consumer = KafkaConsumerClient(
            topics=[TOPICS.JOB_VERIFIED],
            group_id="notifier-service",
        )
        self.running = False

    async def start(self) -> None:
        await self.consumer.start()
        self.running = True
        logger.info("🔔 Notifier service started")
        await self.consumer.consume(self._handle_message)

    async def stop(self) -> None:
        self.running = False
        await self.consumer.stop()

    async def _handle_message(self, message: dict, *args) -> None:
        job_id = message.get("_id", message.get("id"))
        title = message.get("title", "")
        company = message.get("company_name", "")

        try:
            client = get_mongo_client()
            db = client["jobplatform"]

            # Find all active saved searches with alerts enabled
            cursor = db.saved_searches.find({
                "alert_enabled": True,
            })
            saved_searches = await cursor.to_list(length=500)

            matched_users = []

            for search in saved_searches:
                if self._job_matches_search(message, search):
                    user_id = search.get("user_id")
                    matched_users.append({
                        "user_id": user_id,
                        "search_id": str(search.get("_id")),
                        "search_name": search.get("name", ""),
                    })

            if not matched_users:
                return

            logger.info(f"Job '{title}' at {company} matches {len(matched_users)} saved searches")

            # Create notification logs
            for match in matched_users:
                user = await db.users.find_one({"_id": match["user_id"]})
                if not user:
                    continue

                channels = self._get_user_channels(user)

                for channel in channels:
                    notification = {
                        "_id": str(uuid.uuid4()),
                        "user_id": match["user_id"],
                        "channel": channel,
                        "template_id": "new_job_match",
                        "subject": f"New match: {title} at {company}",
                        "status": "sent",
                        "retry_count": 0,
                        "sent_at": datetime.utcnow(),
                        "created_at": datetime.utcnow(),
                    }
                    await db.notification_logs.insert_one(notification)

                    # Simulate sending
                    await self._send_notification(channel, user, message, match)

                # Update last_triggered_at on the saved search
                await db.saved_searches.update_one(
                    {"_id": search.get("_id")},
                    {"$set": {"last_triggered_at": datetime.utcnow()}},
                )

        except Exception as e:
            logger.exception(f"Notification processing failed for job {job_id}: {e}")

    def _job_matches_search(self, job: dict, search: dict) -> bool:
        """Check if a job matches a saved search's criteria."""
        query = search.get("query", "").lower()
        filters = search.get("filters", {})

        # Text query match
        if query:
            title = (job.get("title") or "").lower()
            desc = (job.get("description") or "").lower()
            company = (job.get("company_name") or "").lower()
            if not any(query in text for text in [title, desc, company]):
                return False

        # Location filter
        if filters.get("location"):
            loc_filter = filters["location"].lower()
            job_locations = [
                (job.get("location_city") or "").lower(),
                (job.get("location_state") or "").lower(),
                (job.get("location_country") or "").lower(),
            ]
            if not any(loc_filter in loc for loc in job_locations):
                return False

        # Remote type filter
        if filters.get("remote_type"):
            if job.get("remote_type") != filters["remote_type"]:
                return False

        # Experience level filter
        if filters.get("experience_level"):
            if job.get("experience_level") != filters["experience_level"]:
                return False

        # Salary filter
        if filters.get("salary_min"):
            if (job.get("salary_max") or 0) < filters["salary_min"]:
                return False

        return True

    def _get_user_channels(self, user: dict) -> list[str]:
        """Determine which notification channels a user has configured."""
        channels = ["in_app"]  # Always log in-app

        if user.get("email"):
            channels.append("email")
        if user.get("telegram_chat_id"):
            channels.append("telegram")
        if user.get("webhook_url"):
            channels.append("webhook")

        return channels

    async def _send_notification(
        self, channel: str, user: dict, job: dict, match: dict
    ) -> None:
        """Simulate sending a notification via the specified channel."""
        title = job.get("title", "")
        company = job.get("company_name", "")

        if channel == "email":
            logger.info(
                f"📧 [SIMULATED] Email to {user.get('email')}: "
                f"New match '{title}' at {company}"
            )
        elif channel == "telegram":
            logger.info(
                f"📱 [SIMULATED] Telegram to {user.get('telegram_chat_id')}: "
                f"New match '{title}' at {company}"
            )
        elif channel == "webhook":
            logger.info(
                f"🔗 [SIMULATED] Webhook to {user.get('webhook_url')}: "
                f"New match '{title}' at {company}"
            )
        elif channel == "in_app":
            logger.debug(f"📌 In-app notification for user {user.get('_id')}")


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    service = NotifierService()
    try:
        await service.start()
    except KeyboardInterrupt:
        await service.stop()


if __name__ == "__main__":
    asyncio.run(main())
