"""
Production ATS Scraper: Discovers companies and syncs jobs from all ATS platforms.
Run: python scripts/run_ats_scraper.py
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path so imports work
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database.mongodb import mongodb
from app.agents.company_discovery import CompanyDiscoveryAgent
from app.agents.job_sync_agent import JobSyncAgent
from app.utils.logging import get_logger

logger = get_logger(__name__)


async def main():
    print("\n" + "="*60)
    print("🏢 ATS-BASED JOB INTELLIGENCE PLATFORM")
    print("="*60 + "\n")

    # Step 1: Connect to MongoDB
    print("📦 Connecting to MongoDB...")
    await mongodb.connect()
    print("✅ Connected to MongoDB\n")

    # Phase 1: Discover companies
    print("🔍 DISCOVERING COMPANIES...")
    print("-"*60)

    discovery = CompanyDiscoveryAgent()
    companies = await discovery.run_discovery()

    print(f"\n✅ Discovered {len(companies)} companies:")
    for c in companies:
        print(f"   • {c.name} ({c.ats_type.upper()})")

    # Phase 2: Sync jobs
    print("\n" + "="*60)
    print("📨 SYNCING JOBS...")
    print("-"*60)

    sync = JobSyncAgent()
    results = await sync.sync_all()

    print("\n" + "="*60)
    print("📊 SYNC RESULTS")
    print("="*60)
    print(f"   Jobs synced: {results['total_jobs']}")
    print(f"   Companies synced: {results['companies_synced']}")
    print(f"   Companies failed: {results['companies_failed']}")
    print("="*60 + "\n")

    print("💡 Open RabbitMQ Dashboard: http://localhost:15672")
    print("   Username: guest, Password: guest")
    print("   Click 'Queues' tab and look for 'raw_jobs'")
    print("="*60 + "\n")


if __name__ == "__main__":
    asyncio.run(main()) 