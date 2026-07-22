"""
Session 3: The Base Adapter.
Every API adapter (Adzuna, etc.) must implement this interface.
"""

from abc import ABC, abstractmethod
from typing import List

from app.models.job import RawJob


class BaseAdapter(ABC):
    """Abstract base class for all job data adapters."""

    def __init__(self, platform_name: str):
        self.platform_name = platform_name

    @abstractmethod
    async def fetch_jobs(
        self,
        search_term: str = "software engineer",
        location: str = "India",
        limit: int = 50
    ) -> List[RawJob]:
        """Fetch jobs from the API and return them as RawJob objects."""
        pass