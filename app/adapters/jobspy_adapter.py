"""
JobSpy Adapter: Aggregates jobs from Indeed, LinkedIn, ZipRecruiter, Glassdoor.
Uses the python-jobspy library (maintained scraper).
"""

from typing import List, Optional

from jobspy import scrape_jobs

from app.adapters.ats_base import BaseATSAdapter, ATSCompany
from app.models.job import RawJob, Company, Location, Salary
from app.utils.logging import get_logger

logger = get_logger(__name__)


class JobSpyAdapter(BaseATSAdapter):
    """
    Adapter for JobSpy library.
    Scrapes Indeed, LinkedIn, ZipRecruiter, Glassdoor.
    """
    
    def __init__(self):
        super().__init__("jobspy")
        # JobSpy doesn't need company discovery; it's site-based
        self.supported_sites = ["indeed", "linkedin", "zip_recruiter", "glassdoor"]
    
    async def discover_companies(self, seed_list: List[str]) -> List[ATSCompany]:
        """JobSpy doesn't discover companies; it scrapes job boards."""
        # Return empty list, or return a placeholder company representing the board
        placeholder = ATSCompany(
            name="JobSpy Aggregator",
            domain="jobspy.com",
            ats_type="jobspy",
            jobs_endpoint="https://jobspy.com",
            career_page_url="https://jobspy.com",
            metadata={"sites": self.supported_sites},
        )
        self.supported_companies.append(placeholder)
        return [placeholder]
    
    async def fetch_jobs(self, company: ATSCompany, limit: int = 100) -> List[RawJob]:
        """
        Fetch jobs using JobSpy from multiple job boards.
        """
        logger.info("JobSpy: Fetching jobs from Indeed, LinkedIn, ZipRecruiter...")
        
        try:
            # JobSpy scrapes synchronously, but we can run it in a thread pool
            import asyncio
            loop = asyncio.get_event_loop()
            
            # Run the synchronous scraper in a thread
            jobs_df = await loop.run_in_executor(
                None,
                lambda: scrape_jobs(
                    site_name=["indeed", "linkedin", "zip_recruiter", "glassdoor"],
                    search_term="software engineer",
                    location="India",
                    results_wanted=limit,
                    hours_old=72,  # Only recent jobs
                    country_indeed='in',  # Indeed India
                )
            )
            
            if jobs_df.empty:
                logger.info("JobSpy: No jobs found")
                return []
            
            raw_jobs = []
            for _, row in jobs_df.iterrows():
                raw_job = self._parse_row(row)
                if raw_job:
                    raw_jobs.append(raw_job)
            
            logger.info(f"JobSpy: Fetched {len(raw_jobs)} jobs")
            return raw_jobs
            
        except Exception as e:
            logger.error(f"JobSpy failed: {e}")
            return []
    
    def _parse_row(self, row) -> Optional[RawJob]:
        """Parse a pandas row from JobSpy into RawJob."""
        try:
            job_id = row.get('id', '')
            if not job_id:
                import hashlib
                job_id = hashlib.md5(f"{row.get('title')}{row.get('company')}".encode()).hexdigest()[:12]
            
            internal_id = f"jobspy_{job_id}"
            
            title = row.get('title', 'N/A')
            company_name = row.get('company', 'Unknown')
            
            location_text = row.get('location', 'India')
            location = Location(full_address=location_text)
            
            company_obj = Company(name=company_name)
            
            description = row.get('description', '')
            
            # Salary parsing
            salary = None
            salary_min = row.get('min_amount')
            salary_max = row.get('max_amount')
            if salary_min or salary_max:
                salary = Salary(
                    min=float(salary_min) if salary_min else None,
                    max=float(salary_max) if salary_max else None,
                    currency=row.get('currency', 'INR'),
                    period=row.get('interval', 'yearly'),
                )
            
            raw_job = RawJob(
                job_id=internal_id,
                source_platform="jobspy",
                source_url=row.get('job_url', ''),
                title=title,
                company=company_obj,
                description=description,
                location=location,
                salary=salary,
                posted_date=row.get('date_posted'),
                raw_data=row.to_dict(),
            )
            return raw_job
            
        except Exception as e:
            logger.debug(f"Error parsing JobSpy row: {e}")
            return None
    
    def validate_endpoint(self, url: str) -> bool:
        return True  # Always valid