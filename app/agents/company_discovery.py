"""
Company Discovery Agent.
Autonomously discovers companies and their ATS endpoints.
"""

import asyncio
from typing import List, Dict, Optional
from datetime import datetime

from app.adapters.ats_base import ATSCompany
from app.adapters.greenhouse_adapter import GreenhouseAdapter
from app.adapters.lever_adapter import LeverAdapter
from app.database.repositories.company_repository import CompanyRepository
from app.utils.logging import get_logger

logger = get_logger(__name__)


class CompanyDiscoveryAgent:
    """
    Autonomous agent that discovers companies and their ATS systems.
    """

    def __init__(self):
        self.greenhouse = GreenhouseAdapter()
        self.lever = LeverAdapter()
        self.company_repo = CompanyRepository()

        # Seed list of companies to discover
        self.seed_companies = [
            # Indian Tech Companies
            "flipkart", "swiggy", "zomato", "paytm", "razorpay",
            "ola", "uber", "amazon", "google", "microsoft",
            "oracle", "salesforce", "adobe", "cisco", "intel",
            "ibm", "dell", "hp", "accenture", "tcs", "infosys",
            "wipro", "hcl", "techmahindra", "lti", "mindtree",
            "persistent", "mphasis", "hexaware", "cognizant", "capgemini",

            # Indian Banks & Financial
            "icici", "hdfc", "sbi", "axis", "kotak",
            "yesbank", "indusind", "idfc", "bajajfinserv", "adityabirla",
            "bajajallianz", "icicilombard", "sbiinsurance", "hdfclife",

            # Indian Startups
            "zerodha", "groww", "cred", "phonepe", "bharatpe",
            "byjus", "oyo", "dream11", "incred", "caratlane",
            "lenskart", "boAt", "cos", "unacademy", "upstox",
            "sharechat", "moj", "dailyhunt", "coinbase", "coinDCX",
            "zepz", "soroco", "fractal", "muSigma", "tigeranalytics",

            # E-commerce
            "myntra", "nykaa", "meesho", "snapdeal", "shopclues",
            "limeroad", "pepperfry", "urbanladder", "boat", "bose",

            # Indian Unicorns
            "byjus", "oyo", "dream11", "incred", "caratlane",

            # ====== GLOBAL TECH GIANTS ======
            "netflix", "apple", "facebook", "meta", "twitter",
            "spotify", "airbnb", "uberglobal", "lyft", "doordash",
            "instacart", "stripe", "square", "shopify", "twilio",
            "slack", "zoom", "datadog", "cloudflare", "palantir",
            "snowflake", "elastic", "confluent", "mongodb", "redis",
            
            # ====== GLOBAL CONSULTING ======
            "mckinsey", "bain", "bcg", "deloitte", "pwc",
            "ey", "kpmg", "accentureglobal", "capco", "oliverwyman",
    
            # ====== GLOBAL BANKS ======
            "goldmansachs", "morganstanley", "jpmorgan", "citibank", "bnpparibas",
            "ubs", "credit suisse", "barclays", "hsbc", "deutschebank",
    
            # ====== AUTOMOTIVE & MANUFACTURING ======
            "tesla", "toyota", "honda", "bmw", "mercedes",
            "ford", "gm", "volkswagen", "hyundai", "kia",
    
            # ====== HEALTHCARE & PHARMA ======
            "pfizer", "johnsonandjohnson", "moderna", "biogen", "gsk",
            "novartis", "roche", "merck", "bayer", "astrazeneca",
            
        ]

        self.discovered_companies: Dict[str, ATSCompany] = {}

    async def run_discovery(self) -> List[ATSCompany]:
        """
        Run the discovery process across all ATS systems.

        Returns:
            List of newly discovered companies.
        """
        logger.info("Starting company discovery cycle...")
        logger.info(f"Checking {len(self.seed_companies)} companies...")

        all_discovered = []

        # Try Greenhouse first
        greenhouse_results = await self.greenhouse.discover_companies(self.seed_companies)
        all_discovered.extend(greenhouse_results)

        # Try Lever next
        discovered_names = [g.name.lower() for g in greenhouse_results]
        remaining = [c for c in self.seed_companies if c.lower() not in discovered_names]

        if remaining:
            lever_results = await self.lever.discover_companies(remaining)
            all_discovered.extend(lever_results)

        # Store discovered companies in MongoDB
        for company in all_discovered:
            self.discovered_companies[company.name.lower()] = company
            await self.company_repo.save_company(company)

        logger.info(f"Discovery complete: {len(all_discovered)} new companies discovered")
        return all_discovered

    async def get_active_companies(self) -> List[ATSCompany]:
        """
        Get all active companies that should be synced.
        """
        return await self.company_repo.get_active_companies()


# Usage
async def discover_companies():
    from app.database.mongodb import mongodb
    await mongodb.connect()
    agent = CompanyDiscoveryAgent()
    companies = await agent.run_discovery()

    print(f"\n✅ Discovered {len(companies)} companies:")
    for c in companies:
        print(f"   • {c.name} ({c.ats_type.upper()})")
    return companies