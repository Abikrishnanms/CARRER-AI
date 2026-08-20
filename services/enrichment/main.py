"""
Enrichment Service — Skill Extraction + Salary Estimation (BATCH MODE).
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

_MODEL_PATH = os.environ.get("SALARY_MODEL_PATH", "ml/salary_estimator/model.pkl")

DEFAULT_BATCH_SIZE = int(os.getenv("ENRICHER_BATCH_SIZE", "120"))
CONCURRENT_JOBS = int(os.getenv("ENRICHER_WORKERS", "50"))


class EnrichmentService:
    """
    Enrichment Agent (batch mode).
    - Extracts skills from title and description using SkillExtractionAgent
    - Detects experience level
    - Persists enrichment data to MongoDB (bulk_write)
    - Publishes enriched jobs to job.enriched (send_batch)
    """

    def __init__(self) -> None:
        self.producer = KafkaProducerClient()
        self.batch_size = DEFAULT_BATCH_SIZE
        self.consumer = KafkaConsumerClient(
            topics=[TOPICS.JOB_DEDUPLICATED],
            group_id="enrichment-service",
            max_poll_records=max(200, self.batch_size * 2),
        )
        self.skill_agent = None
        self.salary_agent = None
        self.salary_estimator = None
        self.running = False

    async def start(self) -> None:
        from services.enrichment.agents.skill_extractor import SkillExtractionAgent
        self.skill_agent = SkillExtractionAgent()

        from services.enrichment.agents.salary_extractor import SalaryExtractionAgent
        self.salary_agent = SalaryExtractionAgent(use_llm=True)

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
        logger.info("🧠 Enrichment service started (batch=%d, workers=%d)", self.batch_size, CONCURRENT_JOBS)
        await self.consumer.consume_batch(self._handle_batch, batch_size=self.batch_size, timeout_ms=2500)

    async def stop(self) -> None:
        self.running = False
        await self.producer.stop()
        await self.consumer.stop()

    async def _enrich_one(self, message: dict) -> tuple[str, dict, dict, dict] | None:
        """Enrich a single job. Returns (job_id, updated_message, enrichment_update, event_doc) or None on failure."""
        job_id = message.get("_id", message.get("id", str(uuid.uuid4())))
        try:
            title = message.get("title", "")
            description = message.get("description", "")
            location_raw = message.get("location_raw") or message.get("location")
            company_name = message.get("company_name", "")
            salary_raw = message.get("salary_raw")
            job_type = message.get("job_type", "full_time")

            skill_task = asyncio.create_task(
                self.skill_agent.extract(title, description, use_llm=True)
            )
            salary_task = asyncio.create_task(
                self.salary_agent.extract(
                    salary_raw=salary_raw,
                    description=description,
                    experience_level=None,
                    job_type=job_type,
                )
            )
            skills, salary_result = await asyncio.gather(skill_task, salary_task)

            required_skills = [s.normalized_name for s in skills if s.is_required]
            nice_to_have = [s.normalized_name for s in skills if not s.is_required]
            tech_stack = [s.normalized_name for s in skills if s.category.value == "technical"]
            skills_data = [s.model_dump() if hasattr(s, "model_dump") else vars(s) for s in skills]

            experience_level = self.skill_agent.detect_experience_level(f"{title} {description}")
            exp_level_str = experience_level.value if hasattr(experience_level, "value") else str(experience_level)

            categories: set[str] = set()
            for s in skills:
                cat = s.category.value if hasattr(s.category, "value") else str(s.category)
                categories.add(cat)
            domain_tags = list(categories)

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

            event_doc = {
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
                "duration_ms": 0,
                "created_at": datetime.utcnow(),
            }

            return (job_id, message, enrichment_data, event_doc)

        except Exception as e:
            logger.exception(f"Enrichment failed for {job_id}: {e}")
            return None

    async def _handle_batch(self, messages: list[dict]) -> None:
        start = time.monotonic()
        n = len(messages)
        if n == 0:
            return

        sem = asyncio.Semaphore(CONCURRENT_JOBS)

        async def _with_sem(msg: dict) -> tuple[str, dict, dict, dict] | None:
            async with sem:
                t0 = time.monotonic()
                result = await self._enrich_one(msg)
                if result is not None:
                    job_id, updated_msg, enrich_data, event_doc = result
                    dur = (time.monotonic() - t0) * 1000
                    event_doc["duration_ms"] = dur
                    return (job_id, updated_msg, enrich_data, event_doc)
                return None

        tasks = [asyncio.create_task(_with_sem(m)) for m in messages]
        results = await asyncio.gather(*tasks)
        results = [r for r in results if r is not None]

        if not results:
            logger.warning("Enrichment batch: 0/%d succeeded", n)
            return

        job_updates = []
        event_inserts = []
        publish_list: list[tuple[dict, str]] = []

        for job_id, updated_msg, enrich_data, event_doc in results:
            job_updates.append({
                "filter": {"_id": job_id},
                "update": {"$set": enrich_data},
                "upsert": True,
            })
            event_inserts.append(event_doc)
            publish_list.append((updated_msg, job_id))

        client = get_mongo_client()
        db = client["jobplatform"]

        try:
            from pymongo import UpdateOne, InsertOne
            bulk_ops = [UpdateOne(**u) for u in job_updates]
            if bulk_ops:
                await db.jobs.bulk_write(bulk_ops, ordered=False)
        except Exception as e:
            logger.warning("Enrichment bulk_write jobs failed (%s), falling back per-job", e)
            for job_id, _msg, enrich_data, _ev in results:
                try:
                    await db.jobs.update_one({"_id": job_id}, {"$set": enrich_data}, upsert=True)
                except Exception:
                    pass

        try:
            from pymongo import InsertOne
            bulk_events = [InsertOne(e) for e in event_inserts]
            if bulk_events:
                await db.pipeline_events.bulk_write(bulk_events, ordered=False)
        except Exception as e:
            logger.warning("Enrichment bulk_write events failed: %s", e)

        try:
            await self.producer.send_batch(TOPICS.JOB_ENRICHED, publish_list)
        except Exception as e:
            logger.exception("Enrichment send_batch failed: %s", e)

        elapsed_ms = (time.monotonic() - start) * 1000
        jps = (len(results) / elapsed_ms * 1000) if elapsed_ms > 0 else 0
        logger.info(
            "🧠 Enrichment: %d/%d jobs in %.0fms (%.1f j/s)",
            len(results), n, elapsed_ms, jps,
        )


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
    if salary_result is not None:
        data = salary_result.to_dict() if hasattr(salary_result, "to_dict") else dict(vars(salary_result))
        if not data.get("is_estimated") and data.get("confidence", 0) >= 0.6:
            return data
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
