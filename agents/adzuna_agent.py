"""
agents/adzuna_agent.py

Agent that pulls job listings from Adzuna's API, validates them,
writes to MongoDB, and publishes to the queue for downstream processing.
"""

from typing import Dict, Optional

from agents.base_agent import BaseAgent
from scrapers.adzuna import fetch_jobs
from models.raw_posting import RawPosting


class AdzunaAgent(BaseAgent):

    def __init__(self):
        super().__init__(agent_name="adzuna_agent")

    def run(self, country: str = "in", keyword: str = "data analyst", pages: int = 1):
        self.logger.info(f"Starting Adzuna fetch: country={country}, keyword={keyword}, pages={pages}")
        jobs = fetch_jobs(country=country, keyword=keyword, pages=pages)

        inserted = 0
        skipped = 0

        for job in jobs:
            validated = self._validate(job)
            if not validated:
                skipped += 1
                continue

            try:
                self.mongo.insert_raw_posting(validated)
                self.queue.publish(
                    queue_name="raw_postings_ready",
                    message={"url": validated.get("url"), "source": "adzuna"},
                )
                inserted += 1
            except Exception as e:
                self.logger.error(f"Failed to store/publish job {job.get('url')}: {e}")
                skipped += 1

        self.logger.info(f"Done: {inserted} inserted, {skipped} skipped")
        return {"inserted": inserted, "skipped": skipped}

    def _validate(self, job: Dict) -> Optional[Dict]:
        try:
            posting = RawPosting(**job)
            return posting.model_dump()
        except Exception as e:
            self.logger.warning(f"Validation failed for job {job.get('url')}: {e}")
            return None


if __name__ == "__main__":
    agent = AdzunaAgent()
    result = agent.run(country="in", keyword="data analyst", pages=2)
    print(result)
    agent.close()