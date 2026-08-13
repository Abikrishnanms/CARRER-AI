"""
Health check script — verifies all platform services are running correctly.
Usage: python scripts/health_check.py [--json] [--exit-on-fail]
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
        async with httpx.AsyncClient(timeout=timeout) as client:
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
    """Check MongoDB connectivity."""
    try:
        from motor.motor_asyncio import AsyncIOMotorClient
        start = time.monotonic()
        client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=int(timeout * 1000))
        await client.admin.command("ping")
        latency_ms = (time.monotonic() - start) * 1000
        client.close()
        return {"name": "MongoDB", "status": "healthy", "latency_ms": round(latency_ms, 1)}
    except Exception as e:
        return {"name": "MongoDB", "status": "unreachable", "error": str(e)}


async def check_redis(url: str, timeout: float = 5.0) -> dict[str, Any]:
    """Check Redis connectivity."""
    try:
        import redis.asyncio as aioredis
        start = time.monotonic()
        r = aioredis.from_url(url, socket_connect_timeout=timeout)
        await r.ping()
        await r.aclose()
        latency_ms = (time.monotonic() - start) * 1000
        return {"name": "Redis", "status": "healthy", "latency_ms": round(latency_ms, 1)}
    except Exception as e:
        return {"name": "Redis", "status": "unreachable", "error": str(e)}


async def run_all_checks(base_url: str = "http://localhost") -> list[dict[str, Any]]:
    """Run all health checks concurrently."""
    services = [
        check_service("Gateway API", f"{base_url}:8000/health"),
        check_service("Search Service", f"{base_url}:8002/health"),
        check_service("Prometheus", f"{base_url}:9090/-/healthy"),
        check_mongodb(os.getenv("MONGO_URI", "mongodb://admin:admin123@localhost:27017/jobplatform?authSource=admin")),
        check_redis(os.getenv("REDIS_URL", "redis://localhost:6379/0")),
    ]

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
        print(json.dumps({"checks": results, "timestamp": time.time()}, indent=2))
        return all(r.get("status") == "healthy" for r in results)

    # Terminal output
    print("\n" + "═" * 50)
    print("  TalentLens Platform Health Check")
    print("═" * 50)
    all_healthy = True
    for r in results:
        status = r.get("status", "unknown")
        icon = "✅" if status == "healthy" else "⚠️ " if status == "degraded" else "❌"
        latency = f" ({r['latency_ms']:.0f}ms)" if "latency_ms" in r else ""
        name = r.get("name", "?")
        print(f"  {icon} {name:<20} {status:<12}{latency}")
        if "error" in r:
            print(f"       └─ {r['error']}")
        if status != "healthy":
            all_healthy = False

    print("─" * 50)
    overall = "✅ ALL SYSTEMS HEALTHY" if all_healthy else "❌ SOME SERVICES DEGRADED"
    print(f"  {overall}")
    print("═" * 50 + "\n")
    return all_healthy


async def main(args: argparse.Namespace) -> int:
    base = args.base_url.rstrip("/")
    results = await run_all_checks(base)
    all_ok = print_results(results, use_json=args.json)
    if args.exit_on_fail and not all_ok:
        return 1
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TalentLens Platform Health Check")
    parser.add_argument("--base-url", default="http://localhost", help="Base URL for services")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--exit-on-fail", action="store_true", help="Exit with code 1 if unhealthy")
    args = parser.parse_args()
    exit_code = asyncio.run(main(args))
    sys.exit(exit_code)
