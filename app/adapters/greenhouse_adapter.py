"""
Greenhouse ATS Adapter.
Fetches jobs from Greenhouse's public API.
No authentication required.
"""

import re
import hashlib
from typing import List, Optional, Dict, Any

import httpx

from app.adapters.ats_base import BaseATSAdapter, ATSCompany
from app.models.job import RawJob, Company, Location, Salary
from app.utils.logging import get_logger

logger = get_logger(__name__)


class GreenhouseAdapter(BaseATSAdapter):
    """Adapter for Greenhouse ATS."""
    
    def __init__(self):
        super().__init__("greenhouse")
        self.base_url = "https://boards-api.greenhouse.io/v1/boards"
    
    async def discover_companies(self, seed_list: List[str]) -> List[ATSCompany]:
        """
        Discover Greenhouse endpoints for a list of companies.
        
        Args:
            seed_list: List of company names or domains
                      (e.g., ["google", "amazon", "flipkart", "swiggy"])
        
        Returns:
            List of ATSCompany objects with validated endpoints.
        """
        discovered = []
        
        for seed in seed_list:
            # Clean the seed
            company_name = seed.strip().lower()
            company_domain = f"{company_name}.com"
            
            # Build the Greenhouse endpoint
            endpoint = f"{self.base_url}/{company_name}/jobs"
            
            # Validate the endpoint exists
            if await self._validate_greenhouse_endpoint(endpoint):
                company = ATSCompany(
                    name=company_name.title(),
                    domain=company_domain,
                    ats_type="greenhouse",
                    jobs_endpoint=endpoint,
                    career_page_url=f"https://boards.greenhouse.io/{company_name}",
                    metadata={"board_name": company_name},
                )
                discovered.append(company)
                logger.info(f"Discovered Greenhouse company: {company_name}")
            else:
                logger.debug(f"Not a Greenhouse board: {company_name}")
        
        self.supported_companies.extend(discovered)
        return discovered
    
    async def _validate_greenhouse_endpoint(self, url: str) -> bool:
        """Check if the Greenhouse endpoint exists and returns valid data."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url)
                if response.status_code == 200:
                    data = response.json()
                    # Greenhouse returns a list of jobs with 'jobs' key
                    return "jobs" in data and isinstance(data["jobs"], list)
                return False
        except Exception:
            return False
    
    async def fetch_jobs(self, company: ATSCompany, limit: int = 100) -> List[RawJob]:
        """
        Fetch jobs from a Greenhouse company.
        
        Args:
            company: ATSCompany object with valid endpoint
            limit: Maximum jobs to fetch
        
        Returns:
            List of RawJob objects
        """
        if company.ats_type != "greenhouse":
            logger.warning(f"Company {company.name} is not using Greenhouse")
            return []
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(company.jobs_endpoint)
                response.raise_for_status()
                data = response.json()
                
                jobs_data = data.get("jobs", [])
                if not jobs_data:
                    logger.info(f"No jobs found for {company.name}")
                    return []
                
                raw_jobs = []
                for job_data in jobs_data[:limit]:
                    raw_job = self._parse_job(job_data, company)
                    if raw_job:
                        raw_jobs.append(raw_job)
                
                logger.info(f"Fetched {len(raw_jobs)} jobs from {company.name}")
                return raw_jobs
                
        except Exception as e:
            logger.error(f"Failed to fetch jobs from {company.name}: {e}")
            return []
    
    def _parse_job(self, job_data: dict, company: ATSCompany) -> Optional[RawJob]:
        """Parse Greenhouse job data into RawJob model."""
        try:
            # Extract job ID
            job_id = job_data.get("id")
            if not job_id:
                return None
            
            # Generate our internal ID
            internal_id = f"greenhouse_{company.name.lower()}_{job_id}"
            
            # Title
            title = job_data.get("title", "N/A")
            
            # Location
            location_data = job_data.get("location", {})
            location_name = location_data.get("name") if location_data else None
            
            location = Location(
                full_address=location_name,
                country="India" if "india" in (location_name or "").lower() else None,
            )
            
            # Company
            company_obj = Company(
                name=company.name,
                domain=company.domain,
                careers_page_url=company.career_page_url,
            )
            
            # Description (clean HTML)
            description = job_data.get("content", "")
            if description:
                # Simple HTML stripping
                description = re.sub(r"<[^>]+>", " ", description)
                description = " ".join(description.split())
            
            # Salary (Greenhouse often doesn't include salary, but we can parse if available)
            salary = None
            # Check for salary in metadata
            for metadata in job_data.get("metadata", []):
                if "salary" in metadata.get("name", "").lower() or "compensation" in metadata.get("name", "").lower():
                    salary_text = metadata.get("value", "")
                    salary = self._parse_salary(salary_text)
            
            # Raw job
            raw_job = RawJob(
                job_id=internal_id,
                source_platform="greenhouse",
                source_url=job_data.get("absolute_url", ""),
                title=title,
                company=company_obj,
                description=description,
                location=location,
                salary=salary,
                posted_date=job_data.get("updated_at"),
                raw_data=job_data,
            )
            return raw_job
            
        except Exception as e:
            logger.warning(f"Error parsing Greenhouse job: {e}")
            return None
    
    def _parse_salary(self, salary_text: str) -> Optional[Salary]:
        """Parse salary text from Greenhouse metadata."""
        if not salary_text:
            return None
        
        # Look for ranges like "₹20L - ₹30L" or "$100k - $150k"
        numbers = re.findall(r"(\d+[,.]?\d*)", salary_text.replace(",", ""))
        
        if len(numbers) >= 2:
            return Salary(
                min=float(numbers[0]),
                max=float(numbers[1]),
                currency="INR" if "₹" in salary_text else "USD",
                period="yearly" if "year" in salary_text.lower() else "yearly",
            )
        elif len(numbers) == 1:
            return Salary(
                min=float(numbers[0]),
                max=float(numbers[0]),
                currency="INR" if "₹" in salary_text else "USD",
                period="yearly" if "year" in salary_text.lower() else "yearly",
            )
        
        return None
    
    def validate_endpoint(self, url: str) -> bool:
        """Validate if URL is a Greenhouse endpoint."""
        pattern = r"^https://boards-api\.greenhouse\.io/v1/boards/[a-zA-Z0-9-]+/jobs$"
        return bool(re.match(pattern, url))