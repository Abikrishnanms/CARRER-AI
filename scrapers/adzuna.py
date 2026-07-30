"""
scrapers/adzuna.py

Adzuna API client — pulls job listings for a given country/keyword.
"""

import requests
from datetime import datetime, timezone
from typing import List, Dict

from app.config.settings import settings
from app.utils.logger import get_logger

logger = get_logger("scraper.adzuna")

BASE_URL = "https://api.adzuna.com/v1/api/jobs/{country}/search/{page}"


def fetch_jobs(country: str = "in", keyword: str = "data analyst", results_per_page: int = 20, pages: int = 1) -> List[Dict]:
    """
    Fetch job listings from Adzuna's API.
    country: 2-letter country code (e.g. 'in' for India, 'gb', 'us')
    """
    all_jobs = []

    for page in range(1, pages + 1):
        url = BASE_URL.format(country=country, page=page)
        params = {
            "app_id": settings.ADZUNA_APP_ID,
            "app_key": settings.ADZUNA_APP_KEY,
            "results_per_page": results_per_page,
            "what": keyword,
            "content-type": "application/json",
        }

        try:
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as e:
            logger.error(f"Failed to fetch Adzuna jobs (page {page}): {e}")
            break

        results = data.get("results", [])
        if not results:
            logger.info(f"No more results at page {page}")
            break

        for job in results:
            all_jobs.append({
                "title": job.get("title"),
                "company": job.get("company", {}).get("display_name"),
                "location": job.get("location", {}).get("display_name"),
                "description": job.get("description"),
                "url": job.get("redirect_url"),
                "tags": [job.get("category", {}).get("label")] if job.get("category") else [],
                "source": "adzuna",
                "scraped_at": datetime.now(timezone.utc).isoformat(),
                "posted_date": job.get("created"),
                "remote": "remote" in (job.get("title", "") + job.get("description", "") + job.get("location", {}).get("display_name", "")).lower(),
            })

        logger.info(f"Page {page}: fetched {len(results)} jobs")

    logger.info(f"Total Adzuna jobs fetched: {len(all_jobs)}")
    return all_jobs

def print_jobs(jobs: list):
    for i, job in enumerate(jobs, 1):
        print("=" * 80)
        print(f"Job #{i}")
        print("=" * 80)
        print(f"Title      : {job.get('title')}")
        print(f"Company    : {job.get('company') or 'N/A'}")
        print(f"Location   : {job.get('location')}")
        print(f"Posted Date: {job.get('posted_date') or 'N/A'}")
        print(f"Remote     : {job.get('remote')}")
        print(f"Source     : {job.get('source')}")
        print(f"URL        : {job.get('url')}")
        desc = (job.get('description') or '').strip()
        preview = desc[:200] + ("..." if len(desc) > 200 else "")
        print(f"Description: {preview}")
        print()


if __name__ == "__main__":
    jobs = fetch_jobs(country="in", keyword="data analyst", pages=1)
    print(f"Found {len(jobs)} jobs\n")
    print_jobs(jobs)


