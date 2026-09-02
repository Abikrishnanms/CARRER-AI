"""
Semantic + hybrid search router using Qdrant vector search + MongoDB full-text.
Handles job search, autocomplete, and related jobs.
"""

from __future__ import annotations

import logging
import time
from typing import Any
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, Query, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

from shared.database.session import get_db

logger = logging.getLogger(__name__)
router = APIRouter()


async def trigger_search_collection(q: str, location: str | None = None) -> None:
    """Trigger background collection for search term."""
    try:
        from shared.kafka.producer import get_producer
        from shared.kafka.topics import TOPICS
        import uuid

        producer = await get_producer()
        task = {
            "task_id": str(uuid.uuid4()),
            "sources": ["adzuna", "greenhouse", "indeed", "rss"],
            "search_terms": [q],
            "location": location,
            "limit": 100,
            "triggered_by": "search_auto_trigger",
            "triggered_at": datetime.now(timezone.utc).isoformat(),
        }
        await producer.send(TOPICS.COLLECTION_TRIGGER, task)
        logger.info(f"Triggered background collection for search: q='{q}', location='{location}'")
    except Exception as e:
        logger.error(f"Failed to trigger background search collection: {e}")


@router.get("", summary="Semantic job search")
async def search_jobs(
    background_tasks: BackgroundTasks,
    q: str = Query(..., min_length=1, description="Search query — natural language supported"),
    location: str | None = Query(None),
    remote: str | None = Query(None),
    skills: list[str] = Query(default=[]),
    experience: str | None = Query(None),
    salary_min: float | None = Query(None),
    salary_max: float | None = Query(None),
    job_type: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    search_mode: str = Query("hybrid", description="hybrid, semantic, fulltext"),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict[str, Any]:
    """
    Hybrid semantic search combining:
    1. Vector similarity (Qdrant) for semantic meaning
    2. Full-text search (MongoDB FTS) for exact matches
    3. Business rules (trust score, freshness) for ranking
    """
    start = time.perf_counter()

    # Trigger background scraping for this search term
    background_tasks.add_task(trigger_search_collection, q, location)

    # Try vector search first
    results = await _hybrid_search(
        query=q,
        location=location,
        remote=remote,
        skills=skills,
        experience=experience,
        salary_min=salary_min,
        salary_max=salary_max,
        job_type=job_type,
        page=page,
        page_size=page_size,
        search_mode=search_mode,
        db=db,
    )

    latency_ms = (time.perf_counter() - start) * 1000

    return {
        **results,
        "query": q,
        "search_mode": search_mode,
        "search_latency_ms": round(latency_ms, 2),
    }


async def _hybrid_search(
    query: str,
    db: AsyncIOMotorDatabase,
    location: str | None = None,
    remote: str | None = None,
    skills: list[str] | None = None,
    experience: str | None = None,
    salary_min: float | None = None,
    salary_max: float | None = None,
    job_type: str | None = None,
    page: int = 1,
    page_size: int = 20,
    search_mode: str = "hybrid",
) -> dict[str, Any]:
    """Execute hybrid search with Qdrant + MongoDB fallback."""

    if search_mode in ("hybrid", "semantic"):
        # Try Qdrant vector search
        try:
            return await _qdrant_search(
                query=query,
                location=location,
                remote=remote,
                skills=skills,
                experience=experience,
                salary_min=salary_min,
                salary_max=salary_max,
                job_type=job_type,
                page=page,
                page_size=page_size,
                db=db,
            )
        except Exception as e:
            logger.warning(f"Qdrant search failed, falling back to MongoDB FTS: {e}")

    # Fallback: MongoDB text search
    return await _mongodb_fts_search(
        query=query,
        location=location,
        remote=remote,
        experience=experience,
        job_type=job_type,
        salary_min=salary_min,
        salary_max=salary_max,
        page=page,
        page_size=page_size,
        db=db,
    )


async def _qdrant_search(
    query: str,
    db: AsyncIOMotorDatabase,
    location: str | None = None,
    remote: str | None = None,
    skills: list[str] | None = None,
    experience: str | None = None,
    salary_min: float | None = None,
    salary_max: float | None = None,
    job_type: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    """Search using Qdrant vector similarity."""
    import os
    from qdrant_client import QdrantClient
    from qdrant_client.models import Filter, FieldCondition, MatchValue, Range
    from sentence_transformers import SentenceTransformer

    qdrant_host = os.getenv("QDRANT_HOST", "localhost")
    qdrant_port = int(os.getenv("QDRANT_PORT", "6333"))
    collection = os.getenv("QDRANT_COLLECTION_JOBS", "job_embeddings")

    client = QdrantClient(host=qdrant_host, port=qdrant_port)
    model = SentenceTransformer(os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2"))

    # Generate query embedding
    query_embedding = model.encode(query).tolist()

    # Build Qdrant filters
    qdrant_filters = []
    if location:
        qdrant_filters.append(FieldCondition(key="location", match=MatchValue(value=location)))
    if remote:
        qdrant_filters.append(FieldCondition(key="remote_type", match=MatchValue(value=remote)))
    if experience:
        qdrant_filters.append(FieldCondition(key="experience_level", match=MatchValue(value=experience)))
    if job_type:
        qdrant_filters.append(FieldCondition(key="job_type", match=MatchValue(value=job_type)))
    if salary_min:
        qdrant_filters.append(FieldCondition(key="salary_min", range=Range(gte=salary_min)))

    qdrant_filter = Filter(must=qdrant_filters) if qdrant_filters else None

    # Search
    offset = (page - 1) * page_size
    results = client.search(
        collection_name=collection,
        query_vector=query_embedding,
        query_filter=qdrant_filter,
        limit=page_size,
        offset=offset,
        with_payload=True,
        score_threshold=0.3,
    )

    # Fetch full job details from DB
    job_ids = [r.payload.get("job_id") for r in results if r.payload]
    if not job_ids:
        return {"results": [], "total": 0, "page": page, "page_size": page_size}

    cursor = db.jobs.find({"_id": {"$in": job_ids}})
    jobs = await cursor.to_list(length=None)
    jobs_map = {str(j.get("_id")): j for j in jobs}

    formatted = []
    for r in results:
        job_id = r.payload.get("job_id")
        job = jobs_map.get(str(job_id))
        if job:
            formatted.append(_format_job_result(job, match_score=r.score))

    return {
        "results": formatted,
        "total": len(formatted),
        "page": page,
        "page_size": page_size,
        "search_engine": "qdrant_vector",
    }


async def _mongodb_fts_search(
    query: str,
    db: AsyncIOMotorDatabase,
    location: str | None = None,
    remote: str | None = None,
    experience: str | None = None,
    job_type: str | None = None,
    salary_min: float | None = None,
    salary_max: float | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    """Fallback full-text search using MongoDB regex/text."""
    filters = {
        "status": "published",
        "is_duplicate": False,
        "$or": [
            {"title": {"$regex": query, "$options": "i"}},
            {"description": {"$regex": query, "$options": "i"}},
            {"company_name": {"$regex": query, "$options": "i"}},
        ]
    }

    if location:
        filters["$or"] = filters.get("$or", []) + [
            {"location_city": {"$regex": location, "$options": "i"}},
            {"location_state": {"$regex": location, "$options": "i"}},
            {"location_country": {"$regex": location, "$options": "i"}},
            {"location_raw": {"$regex": location, "$options": "i"}},
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
        "results": [_format_job_result(j, match_score=j.get("quality_score", 0) / 100.0) for j in jobs],
        "total": total,
        "page": page,
        "page_size": page_size,
        "search_engine": "mongodb_fts",
    }


@router.get("/autocomplete", summary="Search autocomplete suggestions")
async def autocomplete(
    q: str = Query(..., min_length=2),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict[str, Any]:
    """Return autocomplete suggestions for job titles, companies, and skills."""
    # Job title suggestions
    title_pipeline = [
        {"$match": {"title": {"$regex": q, "$options": "i"}}},
        {"$group": {"_id": "$title", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 5}
    ]
    title_cursor = db.jobs.aggregate(title_pipeline)
    title_result = await title_cursor.to_list(length=5)
    titles = [{"type": "title", "value": r["_id"], "count": r["count"]} for r in title_result if r.get("_id")]

    # Company suggestions
    company_pipeline = [
        {"$match": {"company_name": {"$regex": q, "$options": "i"}}},
        {"$group": {"_id": "$company_name", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 5}
    ]
    company_cursor = db.jobs.aggregate(company_pipeline)
    company_result = await company_cursor.to_list(length=5)
    companies = [{"type": "company", "value": r["_id"], "count": r["count"]} for r in company_result if r.get("_id")]

    return {
        "query": q,
        "suggestions": titles + companies,
    }


@router.get("/similar/{job_id}", summary="Find similar jobs")
async def similar_jobs(
    job_id: str,
    limit: int = Query(10, ge=1, le=20),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict[str, Any]:
    """Find semantically similar jobs using vector search."""
    job = await db.jobs.find_one({"_id": job_id})
    if not job:
        job = await db.jobs.find_one({"id": job_id})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Use the job's embedding to find similar ones
    if job.get("embedding_id"):
        try:
            import os
            from qdrant_client import QdrantClient

            client = QdrantClient(
                host=os.getenv("QDRANT_HOST", "localhost"),
                port=int(os.getenv("QDRANT_PORT", "6333")),
            )
            collection = os.getenv("QDRANT_COLLECTION_JOBS", "job_embeddings")

            # Get the job's vector
            points = client.retrieve(collection, ids=[job["embedding_id"]], with_vectors=True)
            if points:
                vector = points[0].vector
                similar = client.search(
                    collection_name=collection,
                    query_vector=vector,
                    limit=limit + 1,  # +1 because the job itself will be returned
                    with_payload=True,
                )
                # Filter out the job itself
                similar = [s for s in similar if s.payload.get("job_id") != job_id][:limit]

                job_ids = [s.payload.get("job_id") for s in similar]
                cursor = db.jobs.find({"_id": {"$in": job_ids}})
                similar_jobs = await cursor.to_list(length=None)

                return {
                    "job_id": job_id,
                    "similar": [_format_job_result(j) for j in similar_jobs],
                }
        except Exception as e:
            logger.warning(f"Vector similarity search failed: {e}")

    # Fallback: keyword-based similarity
    first_word = job.get("title", "").split()[0] if job.get("title") else ""
    filters = {
        "_id": {"$ne": job_id},
        "status": "published",
        "title": {"$regex": first_word, "$options": "i"}
    }
    cursor = db.jobs.find(filters).limit(limit)
    similar_jobs = await cursor.to_list(length=limit)

    return {
        "job_id": job_id,
        "similar": [_format_job_result(j) for j in similar_jobs],
        "method": "keyword_fallback",
    }


def _format_job_result(job: dict, match_score: float = 0.0) -> dict[str, Any]:
    """Format a Job dict for API response."""
    salary_min_val = job.get("salary_min")
    salary_max_val = job.get("salary_max")
    salary_display = None
    if salary_min_val and salary_max_val:
        salary_display = f"₹{salary_min_val/100000:.1f}L - ₹{salary_max_val/100000:.1f}L/year"
    elif salary_min_val:
        salary_display = f"₹{salary_min_val/100000:.1f}L+/year"

    sp = job.get("scam_probability", 0)
    if sp < 0.2: risk = "very_low"
    elif sp < 0.4: risk = "low"
    elif sp < 0.6: risk = "medium"
    elif sp < 0.8: risk = "high"
    else: risk = "very_high"

    location_parts = [p for p in [job.get("location_city"), job.get("location_state"), job.get("location_country")] if p]
    location_str = ", ".join(location_parts) if location_parts else job.get("location_raw") or "Unknown"

    posted_at = job.get("posted_at")
    
    return {
        "id": str(job.get("_id", job.get("id"))),
        "title": job.get("title"),
        "company_name": job.get("company_name"),
        "location": location_str,
        "remote_type": job.get("remote_type"),
        "job_type": job.get("job_type"),
        "experience_level": job.get("experience_level"),
        "salary_display": salary_display,
        "required_skills": job.get("required_skills", []),
        "tech_stack": job.get("tech_stack", []),
        "posted_at": posted_at.isoformat() if isinstance(posted_at, datetime) else posted_at,
        "apply_url": job.get("apply_url"),
        "source_url": job.get("source_url"),
        "scam_risk": risk,
        "is_verified": job.get("is_verified", False),
        "quality_score": job.get("quality_score", 0),
        "match_score": round(match_score, 3),
    }
