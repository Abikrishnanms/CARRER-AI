**Enrichment Service — `services/enrichment/main.py` (Line-by-line annotations)**

Summary: Batch enrichment service that extracts skills and estimates salary for jobs, persists enrichment to MongoDB, and publishes enriched jobs to Kafka.

---

```python
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
```

---

Line-by-line explanations (grouped for readability):

- Lines 1-6: Module docstring — describes purpose and Kafka topics used.
- Line 8: `from __future__ import annotations` — postpones evaluation of annotations (PEP 563 style), keeps type hints as strings.
- Lines 10-17: Standard library imports used for async, logging, env, timing, ids, and typing.
- Lines 19-22: Import shared infra: Kafka consumer/producer clients, topic constants, and Mongo session helper.
- Line 24: Set up logger for module.
- Line 26: Read salary estimator model path from `SALARY_MODEL_PATH` env var or default path.
- Lines 28-29: Batch size and concurrency come from environment with sensible defaults.

- Lines 32-51: `EnrichmentService` class docstring and `__init__`:
  - Instantiate Kafka producer and consumer configured to read `JOB_DEDUPLICATED` and group `enrichment-service`.
  - Keep slots for `skill_agent`, `salary_agent`, and `salary_estimator` to be lazily loaded in `start()`.

- Lines 53-78: `start()` method:
  - Dynamically import and initialize `SkillExtractionAgent` and `SalaryExtractionAgent` (LLM-enabled).
  - Attempt to load ML `SalaryEstimator` (if available) and log whether ML model loaded.
  - Start producer and consumer and kick off `consume_batch` which calls `_handle_batch` repeatedly.

- Lines 80-85: `stop()` gracefully stops producer and consumer and flips running flag.

- Lines 87-141: `_enrich_one()` — enrich a single job message:
  - Determine job id; pull title, description, location, company, salary_raw, job_type.
  - Run skill extraction and salary extraction concurrently with `asyncio.create_task` + `gather`.
  - Build lists: required skills, nice-to-have, tech stack, and a serializable `skills_data` entry.
  - Detect experience level via skill agent and collect category/domain tags.
  - Call `_build_salary_data()` to combine parsed salary + ML estimator if available.
  - Construct `enrichment_data` dict and update the incoming message in-place.
  - Create an `event_doc` describing the enrichment event for pipeline tracking.
  - Return `(job_id, message, enrichment_data, event_doc)` or `None` on exception (with logging).

- Lines 143-216: `_handle_batch()` — process batch of messages concurrently:
  - Track batch start time and skip empty batches.
  - Use a semaphore limited by `CONCURRENT_JOBS` to bound concurrent enrichment tasks.
  - Wrap `_enrich_one` in `_with_sem` to measure per-job duration and collect results.
  - Launch tasks for all messages, gather results, filter out failed items.
  - If no successes, log a warning and return early.
  - Prepare lists for MongoDB bulk updates (`job_updates`), `pipeline_events` inserts (`event_inserts`), and publish payloads (`publish_list`).

- Lines 218-239: Database writes — jobs bulk update
  - Obtain Mongo client via `get_mongo_client()` and target `jobplatform` DB.
  - Try constructing `pymongo.UpdateOne` ops and call `bulk_write` (ordered=False for speed).
  - On failure, fall back to per-job `update_one` in a best-effort loop (exceptions swallowed to avoid stopping batch).

- Lines 241-249: Database writes — pipeline events inserts
  - Build `InsertOne` ops for `pipeline_events` and bulk write; log warnings on failure but continue.

- Lines 251-258: Publishing
  - Use `self.producer.send_batch()` to publish enriched job payloads to `TOPICS.JOB_ENRICHED`.
  - Exceptions are logged but do not raise so pipeline remains resilient.

- Lines 260-267: Final logging and metrics
  - Compute elapsed time and jobs-per-second (j/s) and log summary for observability.

- Lines 270-327: `_build_salary_data()` helper
  - If a parsed `salary_result` exists and is sufficiently confident (`confidence >= 0.6`) and not estimated, return it.
  - Otherwise, if an ML `salary_estimator` is available, call it and prefer ML output when it has higher confidence or existing data was estimated.
  - If no parsed data but ML estimator available, return ML estimation.
  - On failure or absent estimators, return a default salary object with `None` min/max and low confidence.

- Lines 330-338: `main()` entrypoint
  - Basic logging config, instantiate `EnrichmentService` and `await service.start()`; handle `KeyboardInterrupt` to stop gracefully.

---

Notes / Next steps:
- This doc covers `services/enrichment/main.py`. If you want literal per-line atomic annotations (one explanation per exact source line), I can produce that in a follow-up file that maps each numbered source line to a one-line explanation.
- Next planned file: `services/verifier/main.py` (will continue the same format).
