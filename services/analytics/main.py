"""
Analytics Service — Aggregates job market data and generates platform insights.
Runs periodic aggregation jobs and exposes results via MongoDB for the gateway to serve.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timedelta
from typing import Any

from shared.database.session import get_mongo_client
from shared.utils.logging import setup_logging

logger = logging.getLogger(__name__)


class AnalyticsService:
    """
    Analytics Agent.
    - Runs scheduled aggregation queries
    - Caches results in a `analytics_cache` MongoDB collection
    - Updates every ANALYTICS_REFRESH_INTERVAL_MINUTES minutes
    """

    def __init__(self) -> None:
        self.running = False
        self.refresh_interval = int(
            os.getenv("ANALYTICS_REFRESH_INTERVAL_MINUTES", "30")
        ) * 60

    async def start(self) -> None:
        self.running = True
        logger.info("📊 Analytics service started")
        await self._run_loop()

    async def stop(self) -> None:
        self.running = False

    async def _run_loop(self) -> None:
        while self.running:
            try:
                logger.info("🔄 Running analytics aggregation...")
                await self._aggregate_all()
                logger.info(f"✅ Analytics aggregation complete. Next run in {self.refresh_interval}s")
            except Exception as e:
                logger.exception(f"Analytics aggregation failed: {e}")
            await asyncio.sleep(self.refresh_interval)

    async def _aggregate_all(self) -> None:
        """Run all aggregation pipelines and cache results."""
        client = get_mongo_client()
        db = client["jobplatform"]

        now = datetime.utcnow()
        cutoff_30d = now - timedelta(days=30)

        tasks = [
            self._agg_overview(db, now),
            self._agg_skill_demand(db, cutoff_30d),
            self._agg_salary_benchmarks(db),
            self._agg_top_companies(db),
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.warning(f"Aggregation task {i} failed: {result}")

    async def _agg_overview(self, db: Any, now: datetime) -> None:
        total_jobs = await db.jobs.count_documents({"status": "published"})
        new_today = await db.jobs.count_documents(
            {"created_at": {"$gte": now - timedelta(hours=24)}}
        )
        verified_jobs = await db.jobs.count_documents({"is_verified": True, "status": "published"})
        remote_jobs = await db.jobs.count_documents({"status": "published", "remote_type": "remote"})

        await db.analytics_cache.update_one(
            {"_id": "overview"},
            {"$set": {
                "total_jobs": total_jobs,
                "new_today": new_today,
                "verified_jobs": verified_jobs,
                "remote_jobs": remote_jobs,
                "updated_at": now,
            }},
            upsert=True,
        )

    async def _agg_skill_demand(self, db: Any, cutoff: datetime) -> None:
        pipeline = [
            {"$match": {"created_at": {"$gte": cutoff}, "status": "published"}},
            {"$unwind": "$required_skills"},
            {"$group": {"_id": "$required_skills", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 50},
        ]
        cursor = db.jobs.aggregate(pipeline)
        top_skills = await cursor.to_list(length=50)

        await db.analytics_cache.update_one(
            {"_id": "skill_demand"},
            {"$set": {
                "top_skills": [{"skill": r["_id"], "count": r["count"]} for r in top_skills if r.get("_id")],
                "updated_at": datetime.utcnow(),
            }},
            upsert=True,
        )

    async def _agg_salary_benchmarks(self, db: Any) -> None:
        pipeline = [
            {"$match": {"status": "published", "salary_min": {"$ne": None}}},
            {
                "$group": {
                    "_id": "$experience_level",
                    "avg_min": {"$avg": "$salary_min"},
                    "avg_max": {"$avg": "$salary_max"},
                    "count": {"$sum": 1},
                }
            },
        ]
        cursor = db.jobs.aggregate(pipeline)
        benchmarks = await cursor.to_list(length=10)

        await db.analytics_cache.update_one(
            {"_id": "salary_benchmarks"},
            {"$set": {
                "data": [
                    {
                        "experience_level": r["_id"],
                        "avg_min": round(r.get("avg_min") or 0),
                        "avg_max": round(r.get("avg_max") or 0),
                        "count": r["count"],
                    }
                    for r in benchmarks if r.get("_id")
                ],
                "updated_at": datetime.utcnow(),
            }},
            upsert=True,
        )

    async def _agg_top_companies(self, db: Any) -> None:
        pipeline = [
            {"$match": {"status": "published"}},
            {
                "$group": {
                    "_id": "$company_name",
                    "job_count": {"$sum": 1},
                    "avg_quality": {"$avg": "$quality_score"},
                }
            },
            {"$sort": {"job_count": -1}},
            {"$limit": 20},
        ]
        cursor = db.jobs.aggregate(pipeline)
        companies = await cursor.to_list(length=20)

        await db.analytics_cache.update_one(
            {"_id": "top_companies"},
            {"$set": {
                "companies": [
                    {"name": r["_id"], "job_count": r["job_count"]}
                    for r in companies if r.get("_id")
                ],
                "updated_at": datetime.utcnow(),
            }},
            upsert=True,
        )


async def main() -> None:
    setup_logging()
    service = AnalyticsService()
    try:
        await service.start()
    except KeyboardInterrupt:
        await service.stop()


if __name__ == "__main__":
    asyncio.run(main())
