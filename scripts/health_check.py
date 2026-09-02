"""
Health check script — verifies all platform services are running correctly.
Usage: python scripts/health_check.py [--json] [--exit-on-fail] [--with-throughput]
"""

from __future__ import annotations

import asyncio
import argparse
import json
import os
import sys
import time
from typing import Any


async def check_service(name: str, url: str, timeout: float = 5.0) -> dict[str, Any]:
    """Check if an HTTP service is healthy."""
    try:
        import httpx
        start = time.monotonic()
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            resp = await client.get(url)
        latency_ms = (time.monotonic() - start) * 1000
        is_ok = resp.status_code < 500
        return {
            "name": name, "url": url,
            "status": "healthy" if is_ok else "degraded",
            "http_status": resp.status_code,
            "latency_ms": round(latency_ms, 1),
        }
    except Exception as e:
        return {"name": name, "url": url, "status": "unreachable", "error": str(e)}


async def check_mongodb(uri: str, timeout: float = 5.0) -> dict[str, Any]:
    """Check MongoDB connectivity + rough job count."""
    try:
        from motor.motor_asyncio import AsyncIOMotorClient
        start = time.monotonic()
        client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=int(timeout * 1000))
        await client.admin.command("ping")
        db = client["jobplatform"]
        counts = {
            "jobs_total": await db.jobs.estimated_document_count(),
            "jobs_published": await db.jobs.count_documents({"status": "published"}),
            "events": await db.pipeline_events.estimated_document_count(),
        }
        latency_ms = (time.monotonic() - start) * 1000
        client.close()
        return {
            "name": "MongoDB", "status": "healthy",
            "latency_ms": round(latency_ms, 1),
            "counts": counts,
        }
    except Exception as e:
        return {"name": "MongoDB", "status": "unreachable", "error": str(e)}


async def check_redis(url: str, timeout: float = 5.0) -> dict[str, Any]:
    """Check Redis connectivity."""
    try:
        import redis.asyncio as aioredis
        start = time.monotonic()
        r = aioredis.from_url(url, socket_connect_timeout=timeout)
        await r.ping()
        info = await r.info("memory")
        used_mb = round(info.get("used_memory_human", "0MB"), 2) if isinstance(info.get("used_memory_human"), (int, float)) else info.get("used_memory_human", "?")
        await r.aclose()
        latency_ms = (time.monotonic() - start) * 1000
        return {"name": "Redis", "status": "healthy", "latency_ms": round(latency_ms, 1), "memory": used_mb}
    except Exception as e:
        return {"name": "Redis", "status": "unreachable", "error": str(e)}


async def check_qdrant(host: str, port: int, timeout: float = 5.0) -> dict[str, Any]:
    """Check Qdrant connectivity + collection info."""
    try:
        from qdrant_client import QdrantClient
        start = time.monotonic()
        client = QdrantClient(host=host, port=port)
        collections = client.get_collections().collections
        names = [c.name for c in collections]
        latency_ms = (time.monotonic() - start) * 1000
        return {
            "name": "Qdrant", "status": "healthy",
            "latency_ms": round(latency_ms, 1),
            "collections": names,
        }
    except Exception as e:
        return {"name": "Qdrant", "status": "unreachable", "error": str(e)}


async def check_minio(endpoint: str, access_key: str, secret_key: str, timeout: float = 5.0) -> dict[str, Any]:
    """Check MinIO connectivity."""
    try:
        start = time.monotonic()
        import httpx
        health_url = f"http://{endpoint}/minio/health/live"
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(health_url)
        latency_ms = (time.monotonic() - start) * 1000
        is_ok = resp.status_code < 500
        return {
            "name": "MinIO", "url": health_url,
            "status": "healthy" if is_ok else "degraded",
            "http_status": resp.status_code,
            "latency_ms": round(latency_ms, 1),
        }
    except Exception as e:
        return {"name": "MinIO", "status": "unreachable", "error": str(e)}


async def run_all_checks(base_url: str = "http://localhost", with_throughput: bool = False) -> list[dict[str, Any]]:
    """Run all health checks concurrently."""
    services = [
        check_service("Gateway API", f"{base_url}:8000/health"),
        check_service("Search Service", f"{base_url}:8002/health"),
        check_service("Redpanda Admin", f"{base_url}:8080/v1/status/health"),
        check_service("Prometheus", f"{base_url}:9090/-/healthy"),
        check_service("Grafana", f"{base_url}:3002/api/health"),
        check_service("Elasticsearch", f"{base_url}:9200/_cluster/health", timeout=7.0),
        check_mongodb(os.getenv("MONGO_URI", "mongodb://admin:admin123@localhost:27017/jobplatform?authSource=admin")),
        check_redis(os.getenv("REDIS_URL", "redis://localhost:6379/0")),
        check_qdrant(os.getenv("QDRANT_HOST", "localhost"), int(os.getenv("QDRANT_PORT", "6333"))),
        check_minio(
            os.getenv("MINIO_ENDPOINT", "localhost:9000"),
            os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
            os.getenv("MINIO_SECRET_KEY", "minioadmin123"),
        ),
    ]

    if with_throughput:
        services.append(check_service("Job Board UI", f"{base_url}:3000/"))
        services.append(check_service("Admin UI", f"{base_url}:3001/"))

    results = await asyncio.gather(*services, return_exceptions=True)
    processed = []
    for r in results:
        if isinstance(r, Exception):
            processed.append({"status": "error", "error": str(r)})
        else:
            processed.append(r)

    return processed


def print_results(results: list[dict], use_json: bool = False) -> bool:
    """Print health check results. Returns True if all healthy."""
    if use_json:
        print(json.dumps({"checks": results, "timestamp": time.time()}, indent=2, default=str))
        return all(r.get("status") == "healthy" for r in results)

    print("\n" + "═" * 58)
    print("  TalentLens Platform Health Check  (Capacity Edition)")
    print("═" * 58)
    all_healthy = True
    for r in results:
        status = r.get("status", "unknown")
        icon = "✅" if status == "healthy" else "⚠️ " if status == "degraded" else "❌"
        latency = f" ({r['latency_ms']:.0f}ms)" if "latency_ms" in r else ""
        name = r.get("name", "?")
        extra = ""
        if "counts" in r:
            c = r["counts"]
            extra = f"  [jobs={c['jobs_total']:,} pub={c['jobs_published']:,} ev={c['events']:,}]"
        if "collections" in r:
            extra = f"  [{', '.join(r['collections']) or 'no collections'}]"
        if "memory" in r:
            extra = f"  [mem={r['memory']}]"
        print(f"  {icon} {name:<22} {status:<12}{latency}{extra}")
        if "error" in r:
            err = str(r["error"])
            if len(err) > 80:
                err = err[:77] + "..."
            print(f"       └─ {err}")
        if status != "healthy":
            all_healthy = False

    print("─" * 58)
    overall = "✅ ALL SYSTEMS HEALTHY" if all_healthy else "❌ SOME SERVICES DEGRADED / UNREACHABLE"
    print(f"  {overall}")
    print("═" * 58 + "\n")
    return all_healthy


async def main(args: argparse.Namespace) -> int:
    base = args.base_url.rstrip("/")
    results = await run_all_checks(base, with_throughput=args.with_throughput)
    all_ok = print_results(results, use_json=args.json)
    if args.exit_on_fail and not all_ok:
        return 1
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TalentLens Platform Health Check (Capacity Edition)")
    parser.add_argument("--base-url", default="http://localhost", help="Base URL for HTTP services")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--exit-on-fail", action="store_true", help="Exit with code 1 if unhealthy")
    parser.add_argument("--with-throughput", action="store_true", help="Also check UI ports (3000/3001)")
    args = parser.parse_args()
    exit_code = asyncio.run(main(args))
    sys.exit(exit_code)
