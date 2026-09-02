"""
FastAPI API Gateway — The single entry point for all external requests.
Provides full CRUD APIs, search, auth, resume matching, and orchestration control.
"""

from __future__ import annotations

import logging
import os
import time
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from services.gateway.routers import auth, jobs, search, users, admin, analytics, notifications, resume
from shared.database.session import create_tables
from shared.utils.logging import setup_logging
from shared.utils.metrics import setup_metrics

logger = logging.getLogger(__name__)

# ─── Rate Limiter ─────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)


# ─── Application Lifespan ─────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    logger.info("🚀 Starting Job Intelligence Platform API Gateway")

    # Initialize database tables (dev mode)
    if os.getenv("APP_ENV", "development") == "development":
        await create_tables()
        logger.info("✅ Database tables initialized")

    yield

    from shared.database.session import close_client
    await close_client()
    logger.info("🛑 Shutting down API Gateway")


# ─── FastAPI App ──────────────────────────────────────────────────────────────
app = FastAPI(
    title="Job Intelligence Platform API",
    description="""
## AI-Powered Job Intelligence Platform

Enterprise-grade job aggregation, verification, and intelligent matching.

### Features
- 🔍 **Semantic Search** — Vector + full-text hybrid search across millions of jobs
- 🛡️ **Scam Detection** — ML-powered fraud detection with 95%+ accuracy  
- 🤖 **AI Enrichment** — Automatic skill extraction, salary estimation, and entity recognition
- 🔔 **Smart Notifications** — Email, Telegram, WhatsApp alerts for new matching jobs
- 📊 **Analytics** — Job market trends, salary benchmarks, skill demand

### Authentication
All endpoints require a Bearer JWT token except public search endpoints.
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# ─── Middleware ────────────────────────────────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(GZipMiddleware, minimum_size=1000)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
        "http://localhost:8000",
        "http://localhost:5500",
        "http://127.0.0.1:5500",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ] + [o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()],
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?" if os.getenv("APP_ENV") != "production" else None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Request Timing Middleware ─────────────────────────────────────────────────
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.perf_counter()
    response = await call_next(request)
    process_time = (time.perf_counter() - start_time) * 1000
    response.headers["X-Process-Time-Ms"] = f"{process_time:.2f}"
    response.headers["X-Platform-Version"] = "1.0.0"
    return response


# ─── Include Routers ──────────────────────────────────────────────────────────
API_PREFIX = "/api/v1"

app.include_router(auth.router,          prefix=f"{API_PREFIX}/auth",          tags=["Authentication"])
app.include_router(jobs.router,          prefix=f"{API_PREFIX}/jobs",           tags=["Jobs"])
app.include_router(search.router,        prefix=f"{API_PREFIX}/search",         tags=["Search"])
app.include_router(users.router,         prefix=f"{API_PREFIX}/users",          tags=["Users"])
app.include_router(notifications.router, prefix=f"{API_PREFIX}/notifications",  tags=["Notifications"])
app.include_router(analytics.router,     prefix=f"{API_PREFIX}/analytics",      tags=["Analytics"])
app.include_router(admin.router,         prefix=f"{API_PREFIX}/admin",          tags=["Admin"])
app.include_router(resume.router,        prefix=f"{API_PREFIX}/resume",         tags=["Resume Matching"])


# ─── Root Endpoints ───────────────────────────────────────────────────────────
@app.get("/", tags=["Root"])
async def root() -> dict[str, Any]:
    return {
        "name": "Job Intelligence Platform API",
        "version": "1.0.0",
        "status": "operational",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health", tags=["Health"])
async def health_check() -> dict[str, Any]:
    """
    Health check endpoint for load balancers and Kubernetes liveness probes.
    Returns service status and dependency health.
    """
    import redis.asyncio as aioredis
    from shared.database.session import get_mongo_client

    checks: dict[str, str] = {}

    # Check MongoDB (using Motor)
    try:
        mongo_client = get_mongo_client()
        await mongo_client.admin.command("ping")
        checks["mongodb"] = "healthy"
    except Exception:
        checks["mongodb"] = "unhealthy"

    # Check Redis
    try:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        r = aioredis.from_url(redis_url)
        await r.ping()
        await r.aclose()
        checks["redis"] = "healthy"
    except Exception:
        checks["redis"] = "unhealthy"

    overall_status = "healthy" if all(v == "healthy" for v in checks.values()) else "degraded"

    return {
        "status": overall_status,
        "version": "1.0.0",
        "environment": os.getenv("APP_ENV", "development"),
        "dependencies": checks,
    }


@app.get("/ready", tags=["Health"])
async def readiness_check() -> dict[str, str]:
    """Kubernetes readiness probe."""
    return {"status": "ready"}
