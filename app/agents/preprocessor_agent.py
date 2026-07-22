"""
Preprocessor Agent: Consumes raw jobs, cleans them, and publishes cleaned jobs.
"""

import asyncio
from typing import Optional

from app.broker.consumer import RabbitMQConsumer
from app.broker.producer import RabbitMQProducer
from app.broker.queues import CLEANED_JOBS_QUEUE, RAW_JOBS_QUEUE
from app.models.job import RawJob, CleanedJob
from app.models.messages import JobMessage
from app.preprocessor.cleaner import JobCleaner
from app.preprocessor.normalizer import JobNormalizer
from app.utils.logging import get_logger

logger = get_logger(__name__)


class PreprocessorAgent:
    """Cleans and enriches raw jobs."""

    def __init__(self):
        self._consumer: Optional[RabbitMQConsumer] = None
        self._producer: Optional[RabbitMQProducer] = None
        self._cleaner = JobCleaner()
        self._normalizer = JobNormalizer()

    async def start(self) -> None:
        """Start the preprocessor."""
        logger.info("Starting Preprocessor Agent...")

        self._consumer = RabbitMQConsumer(queue_name=RAW_JOBS_QUEUE, prefetch_count=10)
        self._producer = RabbitMQProducer()

        await self._consumer.connect()
        await self._producer.connect()

        await self._consumer.consume(self._process_message)

    async def _process_message(self, message: JobMessage) -> None:
        """Process a raw job message."""
        try:
            raw_job = RawJob(**message.payload)

            # Clean
            cleaned_job, errors = self._cleaner.clean(raw_job)
            if not cleaned_job:
                logger.warning(f"Job failed cleaning: {message.job_id}, errors: {errors}")
                return

            # Normalize
            cleaned_job.cleaned_title = self._normalizer.normalize_title(raw_job.title)
            cleaned_job.cleaned_description = self._normalizer.normalize_description(raw_job.description)
            cleaned_job.extracted_skills = self._normalizer.extract_skills(
                f"{cleaned_job.title} {cleaned_job.description}"
            )
            cleaned_job.extracted_experience_years = self._normalizer.extract_experience_years(
                cleaned_job.description
            )

            # Publish cleaned job
            await self._publish_cleaned_job(cleaned_job, "preprocessor")

            logger.info(
                "Job preprocessed",
                job_id=cleaned_job.job_id,
                skills=len(cleaned_job.extracted_skills),
                duplicate=cleaned_job.is_duplicate,
            )

        except Exception as e:
            logger.error(f"Failed to process job {message.job_id}: {e}", exc_info=True)

    async def _publish_cleaned_job(self, job: CleanedJob, source_agent: str) -> None:
        """Publish cleaned job."""
        message = JobMessage(
            source_agent=source_agent,
            source_platform=job.source_platform,
            job_id=job.job_id,
            payload=job.model_dump(mode="json"),
        )
        await self._producer.publish(queue_name=CLEANED_JOBS_QUEUE, message=message)

    async def stop(self) -> None:
        """Stop the agent."""
        if self._consumer:
            await self._consumer.close()
        if self._producer:
            await self._producer.close()