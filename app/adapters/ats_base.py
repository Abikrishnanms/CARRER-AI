"""
ATS Adapter Base: Common interface for all Applicant Tracking Systems.
Greenhouse, Lever, Workday, Ashby, etc.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

from app.models.job import RawJob, Company, Location, Salary


@dataclass
class ATSCompany:
    """Discovered company with ATS information."""
    name: str
    domain: str
    ats_type: str  # greenhouse, lever, workday, ashby, smartrecruiters
    jobs_endpoint: str
    career_page_url: str
    is_active: bool = True
    last_synced: Optional[str] = None
    metadata: Dict[str, Any] = None


class BaseATSAdapter(ABC):
    """Base class for all ATS platform adapters."""
    
    def __init__(self, ats_type: str):
        self.ats_type = ats_type
        self.supported_companies: List[ATSCompany] = []
    
    @abstractmethod
    async def discover_companies(self, seed_list: List[str]) -> List[ATSCompany]:
        """
        Given a seed list of company names/domains, discover their ATS endpoints.
        Returns: List of ATSCompany objects with validated endpoints.
        """
        pass
    
    @abstractmethod
    async def fetch_jobs(self, company: ATSCompany, limit: int = 100) -> List[RawJob]:
        """
        Fetch jobs from a specific company's ATS endpoint.
        Returns: List of RawJob objects.
        """
        pass
    
    @abstractmethod
    def validate_endpoint(self, url: str) -> bool:
        """
        Validate if the URL is a valid ATS endpoint.
        Returns: True if valid, False otherwise.
        """
        pass