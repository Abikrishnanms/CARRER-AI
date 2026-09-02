"""
Search Service — Standalone hybrid search microservice.
Wraps Qdrant vector search with MongoDB full-text fallback.
Can run independently or as a library imported by the gateway.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager
from typing import Any

import uvicorn
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from shared.database.session import get_mongo_client
from shared.utils.logging import setup_logging

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION_JOBS", "job_embeddings")

_model = None
_qdrant = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _model, _qdrant
    # Load embedding model
    try:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(EMBEDDING_MODEL)
        logger.info(f"Embedding model loaded: {EMBEDDING_MODEL}")
    except ImportError:
        logger.warning("sentence-transformers not installed — semantic search disabled")

    # Connect to Qdrant
    try:
        from qdrant_client import QdrantClient
        _qdrant = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
        logger.info("Qdrant connected")
    except Exception as e:
        logger.warning(f"Qdrant unavailable: {e} — falling back to MongoDB FTS")

    logger.info("🔍 Search service started")
    yield
    logger.info("🛑 Search service shutting down")


app = FastAPI(
    title="Search Service",
    description="Hybrid semantic + full-text job search",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict:
    return {
        "status": "healthy",
        "service": "search",
        "embedding_model": EMBEDDING_MODEL if _model else None,
        "qdrant": _qdrant is not None,
    }


@app.get("/search")
async def search(
    q: str = Query(..., min_length=1),
    location: str | None = None,
    remote: str | None = None,
    experience: str | None = None,
    job_type: str | None = None,
    salary_min: float | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    mode: str = Query("hybrid", description="hybrid | semantic | fulltext"),
) -> dict[str, Any]:
    """Hybrid semantic + full-text job search."""
    start = time.perf_counter()
    client = get_mongo_client()
    db = client["jobplatform"]

    results: dict[str, Any] = {}

    if mode in ("hybrid", "semantic") and _model and _qdrant:
        try:
            results = await _vector_search(
                q, location, remote, experience, job_type, salary_min,
                page, page_size, db,
            )
            results["search_engine"] = "qdrant_vector"
        except Exception as e:
            logger.warning(f"Vector search failed, falling back: {e}")

    if not results:
        results = await _mongodb_search(
            q, location, remote, experience, job_type, salary_min,
            page, page_size, db,
        )
        results["search_engine"] = "mongodb_fts"

    latency = (time.perf_counter() - start) * 1000
    return {**results, "query": q, "latency_ms": round(latency, 2)}


async def _vector_search(
    query: str,
    location: str | None,
    remote: str | None,
    experience: str | None,
    job_type: str | None,
    salary_min: float | None,
    page: int,
    page_size: int,
    db: Any,
) -> dict[str, Any]:
    """Qdrant vector similarity search."""
    from qdrant_client.models import FieldCondition, Filter, MatchValue, Range

    vector = _model.encode(query).tolist()
    filters = []
    if remote:
        filters.append(FieldCondition(key="remote_type", match=MatchValue(value=remote)))
    if experience:
        filters.append(FieldCondition(key="experience_level", match=MatchValue(value=experience)))
    if job_type:
        filters.append(FieldCondition(key="job_type", match=MatchValue(value=job_type)))
    if salary_min:
        filters.append(FieldCondition(key="salary_min", range=Range(gte=salary_min)))

    qdrant_filter = Filter(must=filters) if filters else None
    offset = (page - 1) * page_size

    hits = _qdrant.search(
        collection_name=QDRANT_COLLECTION,
        query_vector=vector,
        query_filter=qdrant_filter,
        limit=page_size,
        offset=offset,
        with_payload=True,
        score_threshold=0.3,
    )

    job_ids = [h.payload.get("job_id") for h in hits if h.payload]
    if not job_ids:
        return {"results": [], "total": 0, "page": page, "page_size": page_size}

    cursor = db.jobs.find({"_id": {"$in": job_ids}})
    jobs = await cursor.to_list(length=None)
    jobs_map = {str(j.get("_id")): j for j in jobs}

    results = []
    for h in hits:
        job = jobs_map.get(str(h.payload.get("job_id")))
        if job:
            results.append(_format_job(job, h.score))

    return {"results": results, "total": len(results), "page": page, "page_size": page_size}


async def _mongodb_search(
    query: str,
    location: str | None,
    remote: str | None,
    experience: str | None,
    job_type: str | None,
    salary_min: float | None,
    page: int,
    page_size: int,
    db: Any,
) -> dict[str, Any]:
    """MongoDB regex full-text search fallback."""
    filters: dict[str, Any] = {
        "status": "published",
        "is_duplicate": {"$ne": True},
        "$or": [
            {"title": {"$regex": query, "$options": "i"}},
            {"description": {"$regex": query, "$options": "i"}},
            {"company_name": {"$regex": query, "$options": "i"}},
        ],
    }
    if location:
        filters["$or"] = filters.get("$or", []) + [
            {"location_city": {"$regex": location, "$options": "i"}},
        ]
    if remote:
        filters["remote_type"] = remote
    if experience:
        filters["experience_level"] = experience
    if job_type:
        filters["job_type"] = job_type
    if salary_min:
        filters["salary_max"] = {"$gte": salary_min}

    total = await db.jobs.count_documents(filters)
    skip = (page - 1) * page_size
    cursor = db.jobs.find(filters).sort([("quality_score", -1), ("posted_at", -1)]).skip(skip).limit(page_size)
    jobs = await cursor.to_list(length=page_size)

    return {
        "results": [_format_job(j, j.get("quality_score", 0) / 100) for j in jobs],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def _format_job(job: dict, score: float = 0.0) -> dict[str, Any]:
    """Format a job document for the search API response."""
    from datetime import datetime
    loc_parts = [p for p in [job.get("location_city"), job.get("location_country")] if p]
    loc = ", ".join(loc_parts) or job.get("location_raw") or "Unknown"
    posted = job.get("posted_at")
    return {
        "id": str(job.get("_id")),
        "title": job.get("title"),
        "company_name": job.get("company_name"),
        "location": loc,
        "remote_type": job.get("remote_type"),
        "job_type": job.get("job_type"),
        "experience_level": job.get("experience_level"),
        "required_skills": job.get("required_skills", [])[:8],
        "apply_url": job.get("apply_url"),
        "source_url": job.get("source_url"),
        "is_verified": job.get("is_verified", False),
        "quality_score": job.get("quality_score", 0),
        "match_score": round(score, 3),
        "posted_at": posted.isoformat() if isinstance(posted, datetime) else posted,
    }


async def main() -> None:
    setup_logging()
    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=int(os.getenv("SEARCH_SERVICE_PORT", "8002")),
        log_level="info",
    )
    server = uvicorn.Server(config)
    await server.serve()


if __name__ == "__main__":
    asyncio.run(main())
