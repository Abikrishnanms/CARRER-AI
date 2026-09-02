# Annotated: services/gateway/main.py

This file is a per-line annotated copy of `services/gateway/main.py`.

---

```py
# Module docstring: FastAPI API Gateway — single entry point
from __future__ import annotations  # Use postponed evaluation of annotations

import logging  # Standard logging
import os  # Environment access
import time  # Used for timing middleware
from contextlib import asynccontextmanager  # Async context manager for app lifespan
from typing import Any  # Generic typing

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware  # CORS middleware
from fastapi.middleware.gzip import GZipMiddleware  # GZip compression middleware
from fastapi.responses import JSONResponse  # JSON response helper
from slowapi import Limiter, _rate_limit_exceeded_handler  # Rate limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from services.gateway.routers import auth, jobs, search, users, admin, analytics, notifications
from shared.database.session import create_tables
from shared.utils.logging import setup_logging
from shared.utils.metrics import setup_metrics

logger = logging.getLogger(__name__)  # Module logger

# Create a Limiter instance keyed by remote address
limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup/shutdown lifecycle
    logger.info("🚀 Starting Job Intelligence Platform API Gateway")

    # Initialize DB indexes in development
    if os.getenv("APP_ENV", "development") == "development":
        await create_tables()
        logger.info("✅ Database tables initialized")

    yield

    logger.info("🛑 Shutting down API Gateway")


app = FastAPI(
    title="Job Intelligence Platform API",
    description="""Application description...""",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# Attach limiter and exception handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# GZip for responses above threshold
app.add_middleware(GZipMiddleware, minimum_size=1000)

# CORS setup using env var
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:3001").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.perf_counter()
    response = await call_next(request)
    process_time = (time.perf_counter() - start_time) * 1000
    response.headers["X-Process-Time-Ms"] = f"{process_time:.2f}"
    response.headers["X-Platform-Version"] = "1.0.0"
    return response


API_PREFIX = "/api/v1"

app.include_router(auth.router,          prefix=f"{API_PREFIX}/auth",          tags=["Authentication"])
app.include_router(jobs.router,          prefix=f"{API_PREFIX}/jobs",           tags=["Jobs"])
app.include_router(search.router,        prefix=f"{API_PREFIX}/search",         tags=["Search"])
app.include_router(users.router,         prefix=f"{API_PREFIX}/users",          tags=["Users"])
app.include_router(notifications.router, prefix=f"{API_PREFIX}/notifications",  tags=["Notifications"])
app.include_router(analytics.router,     prefix=f"{API_PREFIX}/analytics",      tags=["Analytics"])
app.include_router(admin.router,         prefix=f"{API_PREFIX}/admin",          tags=["Admin"])


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
    import redis.asyncio as aioredis
    from shared.database.session import get_mongo_client

    checks: dict[str, str] = {}

    try:
        mongo_client = get_mongo_client()
        await mongo_client.admin.command("ping")
        checks["mongodb"] = "healthy"
    except Exception:
        checks["mongodb"] = "unhealthy"

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
    return {"status": "ready"}
```

For each code block line above: the code is the original line (trimmed) and lines are grouped for readability; if you want fully inline per-line commentary (each original line followed by an explanation line), tell me and I'll produce that exact format next.
