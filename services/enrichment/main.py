"""
Enrichment Service — Skill Extraction + Salary Estimation.
Consumes from Kafka topic: job.deduplicated
Publishes to Kafka topic: job.enriched
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

# Path to the trained ML salary model (optional — service works without it)
_MODEL_PATH = os.environ.get(
    "SALARY_MODEL_PATH",
    "ml/salary_estimator/model.pkl",
)


class EnrichmentService:
    """
    Enrichment Agent.
    - Extracts skills from title and description using SkillExtractionAgent
    - Detects experience level
    - Persists enrichment data to MongoDB
    - Publishes enriched job to job.enriched
    """

    def __init__(self) -> None:
        self.producer = KafkaProducerClient()
        self.consumer = KafkaConsumerClient(
            topics=[TOPICS.JOB_DEDUPLICATED],
            group_id="enrichment-service",
        )
        self.skill_agent = None
        self.salary_agent = None
        self.salary_estimator = None
        self.running = False

    async def start(self) -> None:
        # Initialize skill extraction agent
        from services.enrichment.agents.skill_extractor import SkillExtractionAgent
        self.skill_agent = SkillExtractionAgent()

        # Initialize rule-based salary extraction agent
        from services.enrichment.agents.salary_extractor import SalaryExtractionAgent
        self.salary_agent = SalaryExtractionAgent(use_llm=True)

        # Initialize ML salary estimator (optional — graceful fallback if model missing)
        try:
            from ml.salary_estimator.estimator import SalaryEstimator
            self.salary_estimator = SalaryEstimator(model_path=_MODEL_PATH)
            logger.info(
                "💰 ML salary estimator loaded%s",
                f" (model: {_MODEL_PATH})" if self.salary_estimator.model else " (rule-based only)",
            )
        except ImportError:
            logger.warning("ml.salary_estimator not on PYTHONPATH — salary ML disabled")

        await self.producer.start()
        await self.consumer.start()
        self.running = True
        logger.info("🧠 Enrichment service started")
        await self.consumer.consume(self._handle_message)

    async def stop(self) -> None:
        self.running = False
        await self.producer.stop()
        await self.consumer.stop()

    async def _handle_message(self, message: dict, *args) -> None:
        start = time.monotonic()
        job_id = message.get("_id", message.get("id", str(uuid.uuid4())))

        try:
            title = message.get("title", "")
            description = message.get("description", "")
            location_raw = message.get("location_raw") or message.get("location")
            company_name = message.get("company_name", "")
            salary_raw = message.get("salary_raw")
            job_type = message.get("job_type", "full_time")

            # ── Run skill extraction + salary estimation concurrently ────────
            skill_task = asyncio.create_task(
                self.skill_agent.extract(title, description, use_llm=True)
            )
            salary_task = asyncio.create_task(
                self.salary_agent.extract(
                    salary_raw=salary_raw,
                    description=description,
                    experience_level=None,   # filled in after skill extraction
                    job_type=job_type,
                )
            )
            skills, salary_result = await asyncio.gather(skill_task, salary_task)

            # ── Skill data ───────────────────────────────────────────────────
            required_skills = [s.normalized_name for s in skills if s.is_required]
            nice_to_have = [s.normalized_name for s in skills if not s.is_required]
            tech_stack = [s.normalized_name for s in skills if s.category.value == "technical"]
            skills_data = [s.model_dump() if hasattr(s, "model_dump") else vars(s) for s in skills]

            # Detect experience level
            experience_level = self.skill_agent.detect_experience_level(f"{title} {description}")
            exp_level_str = experience_level.value if hasattr(experience_level, "value") else str(experience_level)

            # Build domain tags from skill categories
            categories: set[str] = set()
            for s in skills:
                cat = s.category.value if hasattr(s.category, "value") else str(s.category)
                categories.add(cat)
            domain_tags = list(categories)

            # ── Salary data ──────────────────────────────────────────────────
            salary_data = _build_salary_data(
                salary_result=salary_result,
                salary_estimator=self.salary_estimator,
                title=title,
                description=description,
                skills=required_skills + nice_to_have,
                company_name=company_name,
                location=location_raw,
                experience_level=exp_level_str,
            )

            # ── Assemble enrichment payload ──────────────────────────────────
            enrichment_data: dict[str, Any] = {
                "required_skills": required_skills,
                "nice_to_have_skills": nice_to_have,
                "tech_stack": tech_stack,
                "skills_data": skills_data,
                "domain_tags": domain_tags,
                "experience_level": exp_level_str,
                "salary": salary_data,
                "status": "enriched",
                "updated_at": datetime.utcnow(),
            }

            message.update(enrichment_data)

            # ── Persist to MongoDB ───────────────────────────────────────────
            client = get_mongo_client()
            db = client["jobplatform"]
            await db.jobs.update_one(
                {"_id": job_id},
                {"$set": enrichment_data},
                upsert=True,
            )

            # ── Log pipeline event ───────────────────────────────────────────
            duration_ms = (time.monotonic() - start) * 1000
            await db.pipeline_events.insert_one({
                "_id": str(uuid.uuid4()),
                "job_id": job_id,
                "event_type": "job.enriched",
                "agent_name": "enrichment",
                "status": "success",
                "payload": {
                    "skills_count": len(skills),
                    "experience_level": exp_level_str,
                    "salary_source": salary_data.get("source"),
                    "salary_confidence": salary_data.get("confidence"),
                },
                "duration_ms": duration_ms,
                "created_at": datetime.utcnow(),
            })

            # ── Publish downstream ───────────────────────────────────────────
            await self.producer.send(TOPICS.JOB_ENRICHED, message, key=job_id)
            logger.debug(
                "Enriched job %s: %d skills, salary %s–%s %s (source=%s) in %.1fms",
                job_id,
                len(skills),
                salary_data.get("min_value"),
                salary_data.get("max_value"),
                salary_data.get("currency", "INR"),
                salary_data.get("source", "unknown"),
                duration_ms,
            )

        except Exception as e:
            logger.exception(f"Enrichment failed for {job_id}: {e}")


# ─── Salary Assembly Helper ───────────────────────────────────────────────────

def _build_salary_data(
    salary_result: Any,
    salary_estimator: Any | None,
    title: str,
    description: str,
    skills: list[str],
    company_name: str,
    location: str | None,
    experience_level: str,
) -> dict[str, Any]:
    """
    Merge rule-based extraction with ML estimation.

    Priority:
      1. Explicit value from raw salary field  → source="explicit"
      2. Extracted from description text       → source="description_extracted"
      3. LLM extracted                         → source="llm_extracted"
      4. ML estimator prediction               → source="ml_estimated"
      5. Experience-level heuristic            → source="experience_estimation"
    """
    # salary_result comes from SalaryExtractionAgent.extract()
    if salary_result is not None:
        data = salary_result.to_dict() if hasattr(salary_result, "to_dict") else dict(vars(salary_result))

        # If already explicitly found with decent confidence, return as-is
        if not data.get("is_estimated") and data.get("confidence", 0) >= 0.6:
            return data

        # Try to improve low-confidence estimates with ML
        if salary_estimator is not None:
            try:
                ml = salary_estimator.estimate(
                    title=title,
                    description=description,
                    skills=skills,
                    company_name=company_name,
                    location=location,
                    experience_level=experience_level,
                )
                # Blend if ML confidence is higher or rule-based gave an estimate
                if ml["confidence"] > data.get("confidence", 0) or data.get("is_estimated"):
                    return {
                        "min_value": ml["salary_min"],
                        "max_value": ml["salary_max"],
                        "currency": ml["salary_currency"],
                        "period": ml["salary_period"],
                        "is_estimated": True,
                        "confidence": ml["confidence"],
                        "source": ml["estimation_method"],
                    }
            except Exception as exc:
                logger.debug("ML salary estimation failed: %s", exc)

        return data

    # No salary at all — fall back entirely to ML estimator
    if salary_estimator is not None:
        try:
            ml = salary_estimator.estimate(
                title=title,
                description=description,
                skills=skills,
                company_name=company_name,
                location=location,
                experience_level=experience_level,
            )
            return {
                "min_value": ml["salary_min"],
                "max_value": ml["salary_max"],
                "currency": ml["salary_currency"],
                "period": ml["salary_period"],
                "is_estimated": True,
                "confidence": ml["confidence"],
                "source": ml["estimation_method"],
            }
        except Exception as exc:
            logger.debug("ML salary estimation failed: %s", exc)

    # Absolute fallback — no data
    return {
        "min_value": None,
        "max_value": None,
        "currency": "INR",
        "period": "yearly",
        "is_estimated": True,
        "confidence": 0.0,
        "source": "unknown",
    }


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    service = EnrichmentService()
    try:
        await service.start()
    except KeyboardInterrupt:
        await service.stop()


if __name__ == "__main__":
    asyncio.run(main())
