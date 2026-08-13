"""
Auth Service — Standalone JWT + OAuth2 authentication microservice.
Handles token issuance, validation, and user session management.
"""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from shared.utils.logging import setup_logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🔐 Auth service started")
    yield
    logger.info("🛑 Auth service shutting down")


app = FastAPI(
    title="Auth Service",
    description="JWT + OAuth2 authentication for Job Intelligence Platform",
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
    return {"status": "healthy", "service": "auth"}


# Re-export the gateway auth router for standalone mode
from services.gateway.routers.auth import router as auth_router  # noqa: E402

app.include_router(auth_router, prefix="/auth", tags=["Authentication"])


async def main() -> None:
    setup_logging()
    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=int(os.getenv("AUTH_SERVICE_PORT", "8001")),
        log_level="info",
    )
    server = uvicorn.Server(config)
    await server.serve()


if __name__ == "__main__":
    asyncio.run(main())
