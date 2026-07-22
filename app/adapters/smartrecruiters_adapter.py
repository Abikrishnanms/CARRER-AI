"""
SmartRecruiters ATS Adapter.
Fetches jobs from SmartRecruiters public API.
"""

import re
import hashlib
from typing import List, Optional

import httpx

from app.adapters.ats_base import BaseATSAdapter, ATSCompany
from app.models.job import RawJob, Company, Location, Salary
from app.utils.logging import get_logger

logger = get_logger(__name__)


class SmartRecruitersAdapter(BaseATSAdapter):
    """Adapter for SmartRecruiters ATS."""
    
    def __init__(self):
        super().__init__("smartrecruiters")
        self.base_url = "https://api.smartrecruiters.com/v1"
    
    async def discover_companies(self, seed_list: List[str]) -> List[ATSCompany]:
        """Discover SmartRecruiters companies."""
        discovered = []
        
        for seed in seed_list:
            company_name = seed.strip().lower()
            company_domain = f"{company_name}.com"
            
            endpoint = f"{self.base_url}/companies/{company_name}/postings"
            
            if await self._validate_endpoint(endpoint):
                company = ATSCompany(
                    name=company_name.title(),
                    domain=company_domain,
                    ats_type="smartrecruiters",
                    jobs_endpoint=endpoint,
                    career_page_url=f"https://www.smartrecruiters.com/{company_name}",
                )
                discovered.append(company)
                logger.info(f"Discovered SmartRecruiters company: {company_name}")
        
        self.supported_companies.extend(discovered)
        return discovered
    
    async def _validate_endpoint(self, url: str) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url)
                return response.status_code == 200
        except Exception:
            return False
    
    async def fetch_jobs(self, company: ATSCompany, limit: int = 100) -> List[RawJob]:
        """Fetch jobs from SmartRecruiters."""
        if company.ats_type != "smartrecruiters":
            return []
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    company.jobs_endpoint,
                    params={"limit": limit}
                )
                response.raise_for_status()
                data = response.json()
                
                jobs_data = data.get("content", [])
                raw_jobs = []
                
                for job_data in jobs_data:
                    raw_job = self._parse_job(job_data, company)
                    if raw_job:
                        raw_jobs.append(raw_job)
                
                logger.info(f"Fetched {len(raw_jobs)} jobs from {company.name} (SmartRecruiters)")
                return raw_jobs
                
        except Exception as e:
            logger.error(f"Failed to fetch SmartRecruiters jobs from {company.name}: {e}")
            return []
    
    def _parse_job(self, job_data: dict, company: ATSCompany) -> Optional[RawJob]:
        try:
            job_id = job_data.get("id")
            if not job_id:
                return None
            
            internal_id = f"smartrecruiters_{company.name.lower()}_{job_id}"
            
            title = job_data.get("name", "N/A")
            
            # Location
            location_data = job_data.get("location", {})
            location_text = location_data.get("country", "India")
            location = Location(full_address=location_text)
            
            company_obj = Company(name=company.name, domain=company.domain)
            
            description = job_data.get("description", "")
            if description:
                description = re.sub(r"<[^>]+>", " ", description)
                description = " ".join(description.split())
            
            raw_job = RawJob(
                job_id=internal_id,
                source_platform="smartrecruiters",
                source_url=job_data.get("jobAdUrl", ""),
                title=title,
                company=company_obj,
                description=description,
                location=location,
                posted_date=job_data.get("publishedDate"),
                raw_data=job_data,
            )
            return raw_job
            
        except Exception as e:
            logger.warning(f"Error parsing SmartRecruiters job: {e}")
            return None
    
    def validate_endpoint(self, url: str) -> bool:
        return "smartrecruiters.com" in url