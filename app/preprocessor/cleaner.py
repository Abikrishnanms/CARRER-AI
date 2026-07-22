"""
Job Cleaner: Handles null values, duplicates, and basic validation.
"""

import hashlib
from typing import List, Optional, Tuple

from app.models.job import RawJob, CleanedJob
from app.utils.logging import get_logger

logger = get_logger(__name__)


class JobCleaner:
    """Cleans raw job data."""

    REQUIRED_FIELDS = ["job_id", "title", "company", "description"]

    def __init__(self):
        self._seen_jobs = {}  # fingerprint -> job_id

    def clean(self, raw_job: RawJob) -> Tuple[Optional[CleanedJob], List[str]]:
        """Clean a raw job."""
        errors = []

        # Check required fields
        for field in self.REQUIRED_FIELDS:
            value = getattr(raw_job, field, None)
            if value is None or (isinstance(value, str) and not value.strip()):
                errors.append(f"Missing required field: {field}")

        if errors:
            return None, errors

        # Check nulls in optional fields
        null_fields = []
        for field in ["salary", "location", "employment_type", "experience_required"]:
            value = getattr(raw_job, field, None)
            if value is None:
                null_fields.append(field)

        # Check duplicates (fingerprint)
        is_duplicate, duplicate_of = self._check_duplicate(raw_job)

        # Build cleaned job
        cleaned = CleanedJob(
            **raw_job.model_dump(),
            cleaned_title=raw_job.title.strip(),
            cleaned_description=raw_job.description.strip(),
            extracted_skills=[],
            is_duplicate=is_duplicate,
            duplicate_of=duplicate_of,
            has_null_values=len(null_fields) > 0,
            null_fields=null_fields,
            validation_errors=errors,
            description_word_count=len(raw_job.description.split()),
            description_has_html="<" in raw_job.description and ">" in raw_job.description,
        )
        return cleaned, errors

    def _check_duplicate(self, job: RawJob) -> Tuple[bool, Optional[str]]:
        """Check for duplicates using fingerprint."""
        fingerprint = hashlib.md5(
            f"{job.title.lower()}|{job.company.name.lower()}|{job.source_platform}".encode()
        ).hexdigest()

        if fingerprint in self._seen_jobs:
            return True, self._seen_jobs[fingerprint]

        self._seen_jobs[fingerprint] = job.job_id
        return False, None