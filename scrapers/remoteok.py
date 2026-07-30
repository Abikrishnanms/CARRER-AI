"""
scrapers/remoteok.py

RemoteOK API client — pulls remote job listings via their public JSON API.
No scraping involved; this is a sanctioned API endpoint.
"""

import re
import json
import requests
from datetime import datetime, timezone
from typing import List, Dict

from app.utils.logger import get_logger

logger = get_logger("scraper.remoteok")

API_URL = "https://remoteok.com/api"


def clean_description(text: str) -> str:
    if not text:
        return text
    # Remove RemoteOK's anti-spam tag line
    text = re.sub(r"Please mention the word.*?\(#\w+\)\.", "", text, flags=re.DOTALL)
    # Strip HTML tags
    text = re.sub(r"<[^>]+>", " ", text)
    return text.strip()
def fix_encoding(text: str) -> str:
    if not text:
        return text
    try:
        return text.encode('latin-1').decode('utf-8')
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text  

def fetch_jobs(limit: int = 50) -> List[Dict]:
    try:
        response = requests.get(API_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        response.raise_for_status()
        data = json.loads(response.content.decode('utf-8'))
    except (requests.RequestException, UnicodeDecodeError, json.JSONDecodeError) as e:
        logger.error(f"Failed to fetch RemoteOK jobs: {e}")
        return []

    jobs_raw = data[1:] if data and "legal" in data[0] else data

    jobs = []
    for job in jobs_raw[:limit]:
        try:
            jobs.append({
                "title": fix_encoding(job.get("position")),
                "company": fix_encoding(job.get("company")),
                "location": fix_encoding(job.get("location")) or "Remote",
                "description": clean_description(fix_encoding(job.get("description"))),
                "url": job.get("url"),
                "tags": job.get("tags", []),
                "source": "remoteok",
                "scraped_at": datetime.now(timezone.utc).isoformat(),
            })
        except Exception as e:
            logger.warning(f"Skipping malformed job entry: {e}")

    logger.info(f"Fetched {len(jobs)} jobs from RemoteOK")
    return jobs

from tabulate import tabulate

if __name__ == "__main__":
    jobs = fetch_jobs(limit=10)

    print(f"\nFound {len(jobs)} jobs\n")

    for i, job in enumerate(jobs, 1):
        print("=" * 80)
        print(f"JOB #{i}")
        print("=" * 80)

        print(f"Title    : {job['title']}")
        print(f"Company  : {job['company']}")
        print(f"Location : {job['location']}")
        print(f"Tags     : {', '.join(job['tags'][:5])}")

        print(f"\nDescription:")
        print(job['description'][:250] + "...")

        print(f"\nURL:")
        print(job['url'])

        input("\nPress Enter for next job...")