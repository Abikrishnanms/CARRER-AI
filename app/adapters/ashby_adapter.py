"""
Ashby ATS Adapter.
Fetches jobs from Ashby's public API.
No authentication required for read-only access.
"""

import re
import hashlib
from typing import List, Optional

import httpx

from app.adapters.ats_base import BaseATSAdapter, ATSCompany
from app.models.job import RawJob, Company, Location
from app.utils.logging import get_logger

logger = get_logger(__name__)


class AshbyAdapter(BaseATSAdapter):
    """Adapter for Ashby ATS."""
    
    def __init__(self):
        super().__init__("ashby")
        self.base_url = "https://api.ashbyhq.com/posting-api"
    
    async def discover_companies(self, seed_list: List[str]) -> List[ATSCompany]:
        """Discover Ashby companies from seed list."""
        discovered = []
        
        for seed in seed_list:
            company_name = seed.strip().lower()
            company_domain = f"{company_name}.com"
            
            # Ashby endpoint pattern
            endpoint = f"{self.base_url}/jobPosting/list?organizationId={company_name}"
            
            # Validate by checking if any jobs exist
            if await self._validate_ashby_endpoint(company_name):
                company = ATSCompany(
                    name=company_name.title(),
                    domain=company_domain,
                    ats_type="ashby",
                    jobs_endpoint=f"{self.base_url}/jobPosting/list",
                    career_page_url=f"https://jobs.ashbyhq.com/{company_name}",
                    metadata={"organization_id": company_name},
                )
                discovered.append(company)
                logger.info(f"Discovered Ashby company: {company_name}")
        
        self.supported_companies.extend(discovered)
        return discovered
    
    async def _validate_ashby_endpoint(self, org_id: str) -> bool:
        """Check if Ashby organization exists."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.base_url}/jobPosting/list",
                    json={"organizationId": org_id}
                )
                return response.status_code == 200
        except Exception:
            return False
    
    async def fetch_jobs(self, company: ATSCompany, limit: int = 100) -> List[RawJob]:
        """Fetch jobs from Ashby."""
        if company.ats_type != "ashby":
            return []
        
        try:
            org_id = company.metadata.get("organization_id") if company.metadata else company.name.lower()
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    company.jobs_endpoint,
                    json={
                        "organizationId": org_id,
                        "limit": limit,
                    }
                )
                response.raise_for_status()
                data = response.json()
                
                jobs_data = data.get("results", [])
                raw_jobs = []
                
                for job_data in jobs_data:
                    raw_job = self._parse_job(job_data, company)
                    if raw_job:
                        raw_jobs.append(raw_job)
                
                logger.info(f"Fetched {len(raw_jobs)} jobs from {company.name} (Ashby)")
                return raw_jobs
                
        except Exception as e:
            logger.error(f"Failed to fetch Ashby jobs from {company.name}: {e}")
            return []
    
    def _parse_job(self, job_data: dict, company: ATSCompany) -> Optional[RawJob]:
        """Parse Ashby job data."""
        try:
            job_id = job_data.get("id")
            if not job_id:
                return None
            
            internal_id = f"ashby_{company.name.lower()}_{job_id}"
            
            title = job_data.get("title", "N/A")
            
            # Location
            location_data = job_data.get("location", {})
            location_text = location_data.get("address", {}).get("locality", "India")
            location = Location(full_address=location_text)
            
            company_obj = Company(name=company.name, domain=company.domain)
            
            # Description (Ashby gives it in the job posting)
            description = job_data.get("descriptionPlain", "")
            
            raw_job = RawJob(
                job_id=internal_id,
                source_platform="ashby",
                source_url=job_data.get("jobPostingUrl", ""),
                title=title,
                company=company_obj,
                description=description,
                location=location,
                posted_date=job_data.get("publishedAt"),
                raw_data=job_data,
            )
            return raw_job
            
        except Exception as e:
            logger.warning(f"Error parsing Ashby job: {e}")
            return None
    
    def validate_endpoint(self, url: str) -> bool:
        return "ashbyhq.com" in url