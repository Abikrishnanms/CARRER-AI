"""
Job Sync Agent: Fetches jobs from all discovered ATS companies.
"""

import asyncio
from typing import List, Dict, Optional

from app.adapters.greenhouse_adapter import GreenhouseAdapter
from app.adapters.lever_adapter import LeverAdapter
from app.adapters.ashby_adapter import AshbyAdapter
from app.adapters.smartrecruiters_adapter import SmartRecruitersAdapter
from app.adapters.jobspy_adapter import JobSpyAdapter  # optional
from app.adapters.ats_base import ATSCompany
from app.broker.producer import RabbitMQProducer
from app.database.repositories.company_repository import CompanyRepository
from app.utils.logging import get_logger

logger = get_logger(__name__)


class JobSyncAgent:
    """
    Synchronizes jobs from all discovered ATS companies.
    """

    def __init__(self):
        self.company_repo = CompanyRepository()
        # Instantiate all adapters
        self.greenhouse = GreenhouseAdapter()
        self.lever = LeverAdapter()
        self.ashby = AshbyAdapter()
        self.smartrecruiters = SmartRecruitersAdapter()
        self.jobspy = JobSpyAdapter()
        self.producer = None

    async def sync_all(self) -> dict:
        """
        Sync jobs from all active companies across all ATS systems.
        """
        logger.info("Starting job sync cycle...")

        # Get all active companies
        companies = await self.company_repo.get_active_companies()
        logger.info(f"Syncing {len(companies)} companies...")

        # Group by ATS type
        ats_groups = {}
        for company in companies:
            if company.ats_type not in ats_groups:
                ats_groups[company.ats_type] = []
            ats_groups[company.ats_type].append(company)

        # Connect to RabbitMQ
        self.producer = RabbitMQProducer()
        await self.producer.connect()

        results = {
            "total_jobs": 0,
            "companies_synced": 0,
            "companies_failed": 0,
        }

        # Process each ATS type
        for ats_type, company_list in ats_groups.items():
            adapter = self._get_adapter(ats_type)
            if not adapter:
                logger.warning(f"No adapter for ATS type: {ats_type}")
                continue

            for company in company_list:
                try:
                    jobs = await adapter.fetch_jobs(company, limit=100)

                    if jobs:
                        for job in jobs:
                            await self.producer.publish_raw_job(job, f"{ats_type}_sync")
                        results["total_jobs"] += len(jobs)
                        results["companies_synced"] += 1
                        logger.info(f"Synced {len(jobs)} jobs from {company.name}")
                    else:
                        logger.debug(f"No new jobs from {company.name}")

                    # Mark as synced
                    await self.company_repo.mark_synced(company.name)

                except Exception as e:
                    logger.error(f"Failed to sync {company.name}: {e}")
                    results["companies_failed"] += 1

        # Close RabbitMQ
        await self.producer.close()

        logger.info(f"Sync complete: {results['total_jobs']} jobs from {results['companies_synced']} companies")
        return results

    def _get_adapter(self, ats_type: str):
        """Return the appropriate adapter for the given ATS type."""
        adapters = {
            "greenhouse": self.greenhouse,
            "lever": self.lever,
            "ashby": self.ashby,                      
            "smartrecruiters": self.smartrecruiters,  
            "jobspy": self.jobspy,
        }
        return adapters.get(ats_type)