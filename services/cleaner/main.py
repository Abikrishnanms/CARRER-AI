"""
Cleaner Service — Data Cleaning Agent.
Consumes from Kafka topic: job.raw
Publishes to Kafka topic: job.cleaned
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
from shared.kafka.producer import KafkaProducerClient
from shared.kafka.topics import TOPICS
from shared.database.session import get_mongo_client

logger = logging.getLogger(__name__)


# ─── HTML / Text Cleaning ─────────────────────────────────────────────────────

def strip_html(text: str | None) -> str:
    """Remove HTML tags and excessive whitespace."""
    if not text:
        return ""
    clean = re.sub(r"<[^>]+>", " ", text)
    clean = re.sub(r"&[a-zA-Z]+;", " ", clean)  # HTML entities
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean


def normalize_location(raw: str | None) -> dict[str, str | None]:
    """Extract city, state, country from a raw location string."""
    if not raw:
        return {"city": None, "state": None, "country": None, "raw": raw}

    parts = [p.strip() for p in raw.split(",")]
    city = parts[0] if len(parts) >= 1 else None
    state = parts[1] if len(parts) >= 2 else None
    country = parts[-1] if len(parts) >= 3 else parts[1] if len(parts) == 2 else None

    # Common Indian state abbreviations
    india_indicators = {"india", "in", "bangalore", "bengaluru", "mumbai", "delhi",
                        "hyderabad", "pune", "chennai", "kolkata", "noida", "gurugram",
                        "gurgaon", "ahmedabad", "jaipur", "kochi", "thiruvananthapuram"}
    if any(ind in (raw or "").lower() for ind in india_indicators):
        country = country or "India"

    return {"city": city, "state": state, "country": country, "raw": raw}


def parse_salary(raw: str | None) -> dict[str, Any]:
    """Parse salary string into structured min/max/currency/period."""
    result = {"min": None, "max": None, "currency": "INR", "period": "yearly", "is_estimated": False}
    if not raw:
        return result

    raw_lower = raw.lower().replace(",", "").replace(" ", "")

    # Detect currency
    if "₹" in raw or "inr" in raw_lower or "rs" in raw_lower:
        result["currency"] = "INR"
    elif "$" in raw or "usd" in raw_lower:
        result["currency"] = "USD"
    elif "€" in raw or "eur" in raw_lower:
        result["currency"] = "EUR"

    # Detect period
    if any(p in raw_lower for p in ["permonth", "/month", "monthly", "pm", "pcm"]):
        result["period"] = "monthly"
    elif any(p in raw_lower for p in ["perday", "/day", "daily", "pd"]):
        result["period"] = "daily"
    elif any(p in raw_lower for p in ["perhour", "/hour", "hourly", "ph"]):
        result["period"] = "hourly"

    # Extract numbers
    numbers = re.findall(r"[\d]+\.?\d*", raw.replace(",", ""))
    floats = [float(n) for n in numbers]

    # Handle lakh/crore notation
    if "lakh" in raw_lower or "lac" in raw_lower or "lpa" in raw_lower:
        floats = [n * 100_000 for n in floats]
    elif "crore" in raw_lower or "cr" in raw_lower:
        floats = [n * 10_000_000 for n in floats]
    elif "k" in raw_lower:
        floats = [n * 1000 for n in floats]

    if len(floats) >= 2:
        result["min"] = min(floats[0], floats[1])
        result["max"] = max(floats[0], floats[1])
    elif len(floats) == 1:
        result["min"] = floats[0]
        result["max"] = floats[0]

    return result


def normalize_job_type(raw: str | None) -> str:
    """Normalize job type strings."""
    if not raw:
        return "unknown"
    raw_lower = raw.lower()
    if any(t in raw_lower for t in ["full_time", "full-time", "fulltime", "permanent"]):
        return "full_time"
    if any(t in raw_lower for t in ["part_time", "part-time", "parttime"]):
        return "part_time"
    if any(t in raw_lower for t in ["contract", "freelance", "consultant"]):
        return "contract"
    if any(t in raw_lower for t in ["intern", "internship"]):
        return "internship"
    return "unknown"


def detect_remote_type(title: str, description: str, location: str | None) -> str:
    """Detect if a job is remote, hybrid, or on-site."""
    text = f"{title} {description} {location or ''}".lower()
    if any(w in text for w in ["remote", "work from home", "wfh", "work from anywhere"]):
        if any(w in text for w in ["hybrid", "partial remote", "flexible"]):
            return "hybrid"
        return "remote"
    return "on_site"


class CleanerService:
    """
    Data Cleaning Agent.
    - Strips HTML from descriptions
    - Normalizes locations, salaries, job types
    - Detects remote type
    - Persists cleaned data to MongoDB
    - Publishes cleaned job to job.cleaned
    """

    def __init__(self) -> None:
        self.producer = KafkaProducerClient()
        self.consumer = KafkaConsumerClient(
            topics=[TOPICS.JOB_RAW],
            group_id="cleaner-service",
        )
        self.running = False

    async def start(self) -> None:
        await self.producer.start()
        await self.consumer.start()
        self.running = True
        logger.info("🧹 Cleaner service started")
        await self.consumer.consume(self._handle_message)

    async def stop(self) -> None:
        self.running = False
        await self.producer.stop()
        await self.consumer.stop()

    async def _handle_message(self, message: dict, *args) -> None:
        start = time.monotonic()
        job_id = message.get("id", str(uuid.uuid4()))

        try:
            cleaned = self._clean_job(message)
            cleaned["status"] = "cleaned"
            cleaned["_id"] = job_id

            # Persist to MongoDB
            client = get_mongo_client()
            db = client["jobplatform"]
            await db.jobs.update_one(
                {"_id": job_id},
                {"$set": cleaned},
                upsert=True,
            )

            # Log pipeline event
            duration_ms = (time.monotonic() - start) * 1000
            await db.pipeline_events.insert_one({
                "_id": str(uuid.uuid4()),
                "job_id": job_id,
                "event_type": "job.cleaned",
                "agent_name": "cleaner",
                "status": "success",
                "duration_ms": duration_ms,
                "created_at": datetime.utcnow(),
            })

            # Publish downstream
            await self.producer.send(TOPICS.JOB_CLEANED, cleaned, key=job_id)
            logger.debug(f"Cleaned job {job_id} in {duration_ms:.1f}ms")

        except Exception as e:
            logger.exception(f"Failed to clean job {job_id}: {e}")

    def _clean_job(self, raw: dict) -> dict:
        """Apply all cleaning transformations."""
        title = strip_html(raw.get("title", ""))
        description = strip_html(raw.get("description", ""))
        company_name = strip_html(raw.get("company_name", "Unknown"))
        location_raw = raw.get("location_raw")

        location = normalize_location(location_raw)
        salary = parse_salary(raw.get("salary_raw"))
        job_type = normalize_job_type(raw.get("job_type_raw"))
        remote_type = detect_remote_type(title, description, location_raw)

        return {
            "source": raw.get("source", "unknown"),
            "source_job_id": raw.get("source_job_id", ""),
            "source_url": raw.get("source_url", ""),
            "title": title,
            "description": description,
            "company_name": company_name,
            "location_city": location["city"],
            "location_state": location["state"],
            "location_country": location["country"],
            "location_raw": location["raw"],
            "salary_min": salary["min"],
            "salary_max": salary["max"],
            "salary_currency": salary["currency"],
            "salary_period": salary["period"],
            "salary_is_estimated": salary["is_estimated"],
            "job_type": job_type,
            "remote_type": remote_type,
            "apply_url": raw.get("apply_url"),
            "posted_at": raw.get("posted_date_raw"),
            "collection_run_id": raw.get("collection_run_id"),
            "raw_data": raw.get("raw_data", {}),
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    service = CleanerService()
    try:
        await service.start()
    except KeyboardInterrupt:
        await service.stop()


if __name__ == "__main__":
    asyncio.run(main())
