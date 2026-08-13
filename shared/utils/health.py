"""
Health check utilities — used by services to report their readiness/liveness.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any

logger = logging.getLogger(__name__)


async def check_mongodb(uri: str | None = None) -> dict[str, str]:
    """Check MongoDB connectivity."""
    try:
        from motor.motor_asyncio import AsyncIOMotorClient
        mongo_uri = uri or os.getenv(
            "MONGO_URI",
            "mongodb://admin:admin123@localhost:27017/jobplatform?authSource=admin",
        )
        client: AsyncIOMotorClient = AsyncIOMotorClient(mongo_uri, serverSelectionTimeoutMS=2000)
        await client.admin.command("ping")
        client.close()
        return {"status": "healthy", "component": "mongodb"}
    except Exception as e:
        return {"status": "unhealthy", "component": "mongodb", "error": str(e)}


async def check_redis(url: str | None = None) -> dict[str, str]:
    """Check Redis connectivity."""
    try:
        import redis.asyncio as aioredis
        redis_url = url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        r = aioredis.from_url(redis_url, socket_connect_timeout=2)
        await r.ping()
        await r.aclose()
        return {"status": "healthy", "component": "redis"}
    except Exception as e:
        return {"status": "unhealthy", "component": "redis", "error": str(e)}


async def check_kafka(bootstrap_servers: str | None = None) -> dict[str, str]:
    """Check Kafka/Redpanda connectivity."""
    try:
        from aiokafka.admin import AIOKafkaAdminClient
        servers = bootstrap_servers or os.getenv(
            "KAFKA_BOOTSTRAP_SERVERS", "localhost:19092"
        )
        admin = AIOKafkaAdminClient(bootstrap_servers=servers)
        await asyncio.wait_for(admin.start(), timeout=3.0)
        await admin.close()
        return {"status": "healthy", "component": "kafka"}
    except Exception as e:
        return {"status": "unhealthy", "component": "kafka", "error": str(e)}


async def check_qdrant(host: str | None = None, port: int | None = None) -> dict[str, str]:
    """Check Qdrant vector database connectivity."""
    try:
        from qdrant_client import QdrantClient
        q_host = host or os.getenv("QDRANT_HOST", "localhost")
        q_port = port or int(os.getenv("QDRANT_PORT", "6333"))
        client = QdrantClient(host=q_host, port=q_port, timeout=2.0)
        client.get_collections()
        return {"status": "healthy", "component": "qdrant"}
    except Exception as e:
        return {"status": "unhealthy", "component": "qdrant", "error": str(e)}


async def full_health_check(components: list[str] | None = None) -> dict[str, Any]:
    """
    Run health checks for all or specified components.
    Returns aggregated health status.
    """
    check_fns = {
        "mongodb": check_mongodb,
        "redis": check_redis,
        "kafka": check_kafka,
        "qdrant": check_qdrant,
    }

    targets = components or list(check_fns.keys())
    tasks = {name: check_fns[name]() for name in targets if name in check_fns}

    results = await asyncio.gather(*tasks.values(), return_exceptions=True)
    checks: dict[str, Any] = {}

    for name, result in zip(tasks.keys(), results):
        if isinstance(result, Exception):
            checks[name] = {"status": "unhealthy", "error": str(result)}
        else:
            checks[name] = result

    overall = "healthy" if all(c.get("status") == "healthy" for c in checks.values()) else "degraded"

    return {
        "status": overall,
        "checks": checks,
        "timestamp": time.time(),
    }
