"""
Company repository for storing ATS-discovered companies.
"""

from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field

from app.database.repositories.base_repository import BaseRepository
from app.database.mongodb import mongodb
from app.adapters.ats_base import ATSCompany
from app.utils.logging import get_logger

logger = get_logger(__name__)


class CompanyDocument(BaseModel):
    """MongoDB document model for companies."""
    name: str
    domain: Optional[str] = None
    ats_type: str
    jobs_endpoint: str
    career_page_url: Optional[str] = None
    is_active: bool = True
    last_synced: Optional[datetime] = None
    metadata: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class CompanyRepository:
    """Repository for company operations."""

    COLLECTION = "companies"

    async def save_company(self, company: ATSCompany) -> bool:
        """Save or update a company."""
        try:
            collection = mongodb.db[self.COLLECTION]

            # Check if exists
            existing = await collection.find_one({"name": company.name})

            if existing:
                # Update
                result = await collection.update_one(
                    {"name": company.name},
                    {
                        "$set": {
                            "domain": company.domain,
                            "ats_type": company.ats_type,
                            "jobs_endpoint": company.jobs_endpoint,
                            "career_page_url": company.career_page_url,
                            "is_active": company.is_active,
                            "metadata": company.metadata or {},
                            "updated_at": datetime.utcnow(),
                        }
                    }
                )
                return result.modified_count > 0
            else:
                # Insert
                doc = CompanyDocument(
                    name=company.name,
                    domain=company.domain,
                    ats_type=company.ats_type,
                    jobs_endpoint=company.jobs_endpoint,
                    career_page_url=company.career_page_url,
                    is_active=company.is_active,
                    metadata=company.metadata or {},
                )
                result = await collection.insert_one(doc.model_dump())
                return bool(result.inserted_id)

        except Exception as e:
            logger.error(f"Failed to save company {company.name}: {e}")
            return False

    async def get_active_companies(self) -> List[ATSCompany]:
        """Get all active companies."""
        try:
            collection = mongodb.db[self.COLLECTION]
            cursor = collection.find({"is_active": True})

            companies = []
            async for doc in cursor:
                company = ATSCompany(
                    name=doc["name"],
                    domain=doc.get("domain"),
                    ats_type=doc["ats_type"],
                    jobs_endpoint=doc["jobs_endpoint"],
                    career_page_url=doc.get("career_page_url"),
                    is_active=doc.get("is_active", True),
                    last_synced=doc.get("last_synced"),
                    metadata=doc.get("metadata"),
                )
                companies.append(company)

            return companies

        except Exception as e:
            logger.error(f"Failed to get active companies: {e}")
            return []

    async def get_company(self, name: str) -> Optional[ATSCompany]:
        """Get a company by name."""
        try:
            collection = mongodb.db[self.COLLECTION]
            doc = await collection.find_one({"name": name})
            if not doc:
                return None

            return ATSCompany(
                name=doc["name"],
                domain=doc.get("domain"),
                ats_type=doc["ats_type"],
                jobs_endpoint=doc["jobs_endpoint"],
                career_page_url=doc.get("career_page_url"),
                is_active=doc.get("is_active", True),
                last_synced=doc.get("last_synced"),
                metadata=doc.get("metadata"),
            )
        except Exception as e:
            logger.error(f"Failed to get company {name}: {e}")
            return None

    async def mark_synced(self, company_name: str) -> bool:
        """Mark a company as synced."""
        try:
            collection = mongodb.db[self.COLLECTION]
            result = await collection.update_one(
                {"name": company_name},
                {"$set": {"last_synced": datetime.utcnow(), "updated_at": datetime.utcnow()}}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Failed to mark synced: {e}")
            return False

    async def deactivate_company(self, company_name: str) -> bool:
        """Deactivate a company."""
        try:
            collection = mongodb.db[self.COLLECTION]
            result = await collection.update_one(
                {"name": company_name},
                {"$set": {"is_active": False, "updated_at": datetime.utcnow()}}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Failed to deactivate company: {e}")
            return False