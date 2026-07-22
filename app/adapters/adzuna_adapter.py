"""
Session 3: Adzuna API Adapter.
Fetches jobs from Adzuna's public API and converts them to RawJob models.
"""

import re
from typing import List, Optional

import httpx

from app.adapters.base import BaseAdapter
from app.config.settings import settings
from app.models.job import RawJob, Company, Location, Salary
from app.utils.logging import get_logger

logger = get_logger(__name__)


class AdzunaAdapter(BaseAdapter):
    """Adapter for the Adzuna job search API."""

    def __init__(self):
        super().__init__("adzuna")
        self.base_url = "https://api.adzuna.com/v1/api/jobs"
        self.app_id = settings.adzuna_app_id
        self.api_key = settings.adzuna_api_key

    async def validate_credentials(self) -> bool:
        """Check if API credentials are configured."""
        return bool(self.app_id and self.api_key)

    async def fetch_jobs(
        self,
        search_term: str = "software engineer",
        location: str = "India",
        limit: int = 50,
    ) -> List[RawJob]:
        """
        Fetch jobs from Adzuna for a given search term and location.
        """
        if not await self.validate_credentials():
            logger.error("Adzuna credentials missing. Add ADZUNA_APP_ID and ADZUNA_API_KEY to .env")
            return []

        logger.info(f"Fetching Adzuna jobs for: {search_term} in {location}")

        # Adzuna uses country codes. 'in' = India
        country = "in" if "india" in location.lower() else "in"

        url = f"{self.base_url}/{country}/search/1"

        params = {
            "app_id": self.app_id,
            "app_key": self.api_key,
            "what": search_term,
            "where": location,
            "results_per_page": min(limit, 50),
            "content-type": "application/json",
        }

        async with httpx.AsyncClient(timeout=settings.request_timeout) as client:
            try:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()

                jobs = self._parse_response(data, location)
                logger.info(f"Adzuna returned {len(jobs)} jobs")
                return jobs

            except httpx.HTTPStatusError as e:
                logger.error(f"Adzuna API HTTP error: {e}")
                return []
            except Exception as e:
                logger.error(f"Adzuna API error: {e}")
                return []

    def _parse_response(self, data: dict, location_fallback: str) -> List[RawJob]:
        """Parse the Adzuna JSON response into RawJob objects."""
        raw_jobs = []
        results = data.get("results", [])

        for item in results:
            try:
                # --- Extract company ---
                company_data = item.get("company", {})
                company = Company(
                    name=company_data.get("display_name", "Unknown"),
                    domain=company_data.get("domain", None),
                )

                # --- Extract location (FIXED: handles both string and list) ---
                location_data = item.get("location", {})
                location = Location(
                    full_address=location_data.get("display_name", location_fallback),
                    country="India",
                )

                # FIX: area could be a string OR a list
                area_value = location_data.get("area")
                if area_value:
                    if isinstance(area_value, str):
                        area_parts = area_value.split(",")
                        if len(area_parts) >= 1:
                            location.city = area_parts[0].strip()
                        if len(area_parts) >= 2:
                            location.state = area_parts[1].strip()
                    elif isinstance(area_value, list):
                        # If it's a list, take the first item
                        if len(area_value) > 0:
                            first_area = area_value[0] if isinstance(area_value[0], str) else str(area_value[0])
                            area_parts = first_area.split(",")
                            if len(area_parts) >= 1:
                                location.city = area_parts[0].strip()
                            if len(area_parts) >= 2:
                                location.state = area_parts[1].strip()

                # --- Extract salary ---
                salary = None
                if item.get("salary_min") is not None or item.get("salary_max") is not None:
                    salary = Salary(
                        min=item.get("salary_min"),
                        max=item.get("salary_max"),
                        currency=item.get("salary_currency", "INR"),
                        period="yearly",
                    )

                # --- Generate a unique job ID ---
                adzuna_id = item.get("id") or item.get("redirect_url", "").split("/")[-1]
                job_id = f"adzuna_{adzuna_id}"

                # --- Build the RawJob ---
                raw_job = RawJob(
                    job_id=job_id,
                    source_platform="adzuna",
                    source_url=item.get("redirect_url", ""),
                    title=item.get("title", "N/A"),
                    company=company,
                    description=item.get("description", ""),
                    salary=salary,
                    location=location,
                    posted_date=item.get("created"),
                    raw_data=item,
                )
                raw_jobs.append(raw_job)

            except Exception as e:
                logger.warning(f"Failed to parse Adzuna job: {e}")
                continue

        return raw_jobs