"""
Lever ATS Adapter.
Fetches jobs from Lever's public API.
"""

import re
import hashlib
from typing import List, Optional

import httpx

from app.adapters.ats_base import BaseATSAdapter, ATSCompany
from app.models.job import RawJob, Company, Location, Salary
from app.utils.logging import get_logger

logger = get_logger(__name__)


class LeverAdapter(BaseATSAdapter):
    """Adapter for Lever ATS."""
    
    def __init__(self):
        super().__init__("lever")
        self.base_url = "https://api.lever.co/v0/postings"
    
    async def discover_companies(self, seed_list: List[str]) -> List[ATSCompany]:
        """Discover Lever endpoints for a list of companies."""
        discovered = []
        
        for seed in seed_list:
            company_name = seed.strip().lower()
            company_domain = f"{company_name}.com"
            
            # Lever endpoint
            endpoint = f"{self.base_url}/{company_name}"
            
            # Validate
            if await self._validate_lever_endpoint(endpoint):
                company = ATSCompany(
                    name=company_name.title(),
                    domain=company_domain,
                    ats_type="lever",
                    jobs_endpoint=endpoint,
                    career_page_url=f"https://jobs.lever.co/{company_name}",
                )
                discovered.append(company)
                logger.info(f"Discovered Lever company: {company_name}")
        
        self.supported_companies.extend(discovered)
        return discovered
    
    async def _validate_lever_endpoint(self, url: str) -> bool:
        """Check if Lever endpoint exists."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url)
                return response.status_code == 200
        except Exception:
            return False
    
    async def fetch_jobs(self, company: ATSCompany, limit: int = 100) -> List[RawJob]:
        """Fetch jobs from a Lever company."""
        if company.ats_type != "lever":
            return []
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(company.jobs_endpoint)
                response.raise_for_status()
                data = response.json()
                
                # Lever returns a list of postings directly
                jobs_data = data if isinstance(data, list) else data.get("data", [])
                
                raw_jobs = []
                for job_data in jobs_data[:limit]:
                    raw_job = self._parse_job(job_data, company)
                    if raw_job:
                        raw_jobs.append(raw_job)
                
                logger.info(f"Fetched {len(raw_jobs)} jobs from {company.name} (Lever)")
                return raw_jobs
                
        except Exception as e:
            logger.error(f"Failed to fetch Lever jobs from {company.name}: {e}")
            return []
    
    def _parse_job(self, job_data: dict, company: ATSCompany) -> Optional[RawJob]:
        """Parse Lever job data."""
        try:
            job_id = job_data.get("id")
            if not job_id:
                return None
            
            internal_id = f"lever_{company.name.lower()}_{job_id}"
            
            title = job_data.get("text", "N/A")
            
            location_text = job_data.get("categories", {}).get("location", "India")
            
            location = Location(full_address=location_text)
            
            company_obj = Company(name=company.name, domain=company.domain)
            
            # Lever has description in the "description" field
            description = job_data.get("description", "")
            if description:
                description = re.sub(r"<[^>]+>", " ", description)
                description = " ".join(description.split())
            
            # Lever has "salary" in additionalProperties
            salary = None
            for prop in job_data.get("additionalProperties", []):
                if "salary" in prop.get("name", "").lower():
                    salary_text = prop.get("value", "")
                    salary = self._parse_salary(salary_text)
            
            raw_job = RawJob(
                job_id=internal_id,
                source_platform="lever",
                source_url=job_data.get("applyUrl", ""),
                title=title,
                company=company_obj,
                description=description,
                location=location,
                salary=salary,
                posted_date=job_data.get("createdAt"),
                raw_data=job_data,
            )
            return raw_job
            
        except Exception as e:
            logger.warning(f"Error parsing Lever job: {e}")
            return None
    
    def _parse_salary(self, salary_text: str) -> Optional[Salary]:
        """Parse salary text."""
        if not salary_text:
            return None
        
        numbers = re.findall(r"(\d+[,.]?\d*)", salary_text.replace(",", ""))
        
        if len(numbers) >= 2:
            return Salary(
                min=float(numbers[0]),
                max=float(numbers[1]),
                currency="USD" if "$" in salary_text else "INR",
                period="yearly" if "year" in salary_text.lower() else "yearly",
            )
        return None
    
    def validate_endpoint(self, url: str) -> bool:
        pattern = r"^https://api\.lever\.co/v0/postings/[a-zA-Z0-9-]+$"
        return bool(re.match(pattern, url))