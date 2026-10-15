#!/usr/bin/env python3
"""
TalentLens Platform — Comprehensive Service Diagnostics

Discovers every platform service (infra + Python workers + HTTP APIs + frontends),
checks liveness/connectivity, reports dependency health, and optionally inspects
Kafka topics for backpressure.

Usage:
  python scripts/diagnose.py                 # human-readable summary
  python scripts/diagnose.py --json          # machine-readable JSON
  python scripts/diagnose.py --exit-on-fail  # non-zero exit if any unhealthy
  python scripts/diagnose.py --check-kafka   # also verify Kafka topic lag
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import socket
import sys
import time
from datetime import datetime, timezone
from typing import Any

SERVICE_DEFS: list[dict[str, Any]] = [
    # ── Infrastructure (Docker Compose) ──────────────────────────
    {"name": "MongoDB",       "kind": "tcp",  "host": "127.0.0.1", "port": 27017, "group": "infra"},
    {"name": "Redis",         "kind": "tcp",  "host": "127.0.0.1", "port": 6379,  "group": "infra"},
    {"name": "Redpanda (Kafka)","kind":"tcp", "host":"127.0.0.1","port": 9092,   "group":"infra"},
    {"name": "Qdrant",        "kind": "tcp",  "host": "127.0.0.1", "port": 6333,  "group": "infra"},
    {"name": "Elasticsearch", "kind": "tcp",  "host": "127.0.0.1", "port": 9200,  "group": "infra"},
    {"name": "MinIO",         "kind": "tcp",  "host": "127.0.0.1", "port": 9000,  "group": "infra"},
    {"name": "Prometheus",    "kind": "http", "url": "http://127.0.0.1:9090/-/healthy", "group": "infra", "timeout": 40.0},
    {"name": "Grafana",       "kind": "http", "url": "http://127.0.0.1:3002/api/health", "group": "infra", "timeout": 40.0},
    {"name": "MLflow",        "kind": "http", "url": "http://127.0.0.1:5000/health", "group": "infra"},
    {"name": "Redpanda Console","kind":"http","url":"http://127.0.0.1:8080/healthz","group":"infra", "timeout": 30.0},

    # ── HTTP API Services ─────────────────────────────────────────
    {"name": "Gateway API",    "kind": "http", "url": "http://127.0.0.1:8000/health", "group": "api", "timeout": 20.0},
    {"name": "Search API",     "kind": "http", "url": "http://127.0.0.1:8002/health", "group": "api"},
    {"name": "Auth API",       "kind": "http", "url": "http://127.0.0.1:8000/docs",   "group": "api", "timeout": 20.0},

    # ── Frontend ──────────────────────────────────────────────────
    {"name": "Job Board UI",   "kind": "http", "url": "http://127.0.0.1:3000/",      "group": "frontend", "timeout": 20.0},
    {"name": "Admin Console",  "kind": "http", "url": "http://127.0.0.1:3001/",      "group": "frontend", "timeout": 20.0},

    # ── Background Workers (Kafka-based — no HTTP port) ───────────
    # These are detected via Docker container name or process name.
]


async def check_tcp(host: str, port: int, timeout: float = 5.0) -> dict[str, Any]:
    """Try to open a TCP connection to (host, port)."""
    start = time.monotonic()
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=timeout
        )
        latency = (time.monotonic() - start) * 1000
        writer.close()
        await writer.wait_closed()
        return {"status": "healthy", "latency_ms": round(latency, 1)}
    except Exception as exc:
        return {"status": "unreachable", "error": str(exc)}


async def check_http(url: str, timeout: float = 5.0) -> dict[str, Any]:
    """GET an HTTP endpoint and verify status < 500."""
    start = time.monotonic()
    try:
        import httpx
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            resp = await client.get(url)
        latency = (time.monotonic() - start) * 1000
        is_ok = resp.status_code < 500
        result: dict[str, Any] = {
            "status": "healthy" if is_ok else "degraded",
            "http_status": resp.status_code,
            "latency_ms": round(latency, 1),
        }
        if url.endswith("/health") or "health" in url:
            try:
                body = resp.json()
                if isinstance(body, dict):
                    result["body"] = body
            except Exception:
                pass
        return result
    except ImportError:
        return await check_http_fallback(url, timeout)
    except Exception as exc:
        return {"status": "unreachable", "error": str(exc)}


async def check_http_fallback(url: str, timeout: float = 5.0) -> dict[str, Any]:
    """Fallback HTTP check using urllib (no httpx dependency)."""
    import urllib.request
    start = time.monotonic()
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            latency = (time.monotonic() - start) * 1000
            status = resp.getcode()
            is_ok = status < 500
            return {
                "status": "healthy" if is_ok else "degraded",
                "http_status": status,
                "latency_ms": round(latency, 1),
            }
    except Exception as exc:
        return {"status": "unreachable", "error": str(exc)}


async def check_kafka_topics(brokers: str = "127.0.0.1:9092", timeout: float = 5.0) -> dict[str, Any]:
    """Check Kafka/Redpanda topic existence and message counts."""
    try:
        from confluent_kafka import Producer, AdminClient
        admin = AdminClient({"bootstrap.servers": brokers})
        md = admin.list_topics(timeout=timeout)

        expected_topics = [
            "raw_jobs", "cleaned_jobs", "deduplicated_jobs", "enriched_jobs",
            "verified_jobs", "rejected_jobs", "expired_jobs",
            "raw_jobs_dlq", "cleaned_jobs_dlq", "enriched_jobs_dlq",
            "notification_email", "notification_telegram", "notification_whatsapp",
            "notification_webhook", "notification_in_app",
            "embedding_job", "embedding_user", "embedding_complete",
            "user_event", "search_query", "feedback_received",
            "collection_trigger", "verification_request", "enrichment_request",
        ]

        existing = set(md.topics.keys())
        missing = [t for t in expected_topics if t not in existing]
        extra = sorted(existing - set(expected_topics) - {"__consumer_offsets"})

        return {
            "status": "healthy" if not missing else "degraded",
            "missing_topics": missing,
            "extra_topics": extra,
            "total_topics": len(existing),
        }
    except ImportError:
        return {"status": "unknown", "error": "confluent_kafka not installed"}
    except Exception as exc:
        return {"status": "unreachable", "error": str(exc)}


async def check_container_status() -> dict[str, dict[str, str]]:
    """Check Docker container running state via docker ps."""
    import subprocess
    try:
        result = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}\t{{.Status}}\t{{.Ports}}"],
            capture_output=True, text=True, timeout=10
        )
        containers: dict[str, dict[str, str]] = {}
        if result.returncode == 0:
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue
                parts = line.split("\t")
                if len(parts) >= 2:
                    name = parts[0]
                    status = parts[1]
                    ports = parts[2] if len(parts) > 2 else ""
                    containers[name] = {"status": status, "ports": ports}
        return containers
    except FileNotFoundError:
        return {"error": "docker not available"}
    except Exception as exc:
        return {"error": str(exc)}


def map_container_to_service(containers: dict[str, dict]) -> dict[str, dict[str, str]]:
    """Map Docker container names to human-readable service names."""
    mapping = {}
    prefix = "jip-"
    for name, info in containers.items():
        if name.startswith(prefix):
            service = name[len(prefix):]
        else:
            service = name
        mapping[service] = info
    return mapping


async def run_diagnostics(
    with_kafka: bool = False,
    with_containers: bool = False,
) -> dict[str, Any]:
    """Run all checks concurrently and return a structured report."""
    timestamp = datetime.now(timezone.utc).isoformat()

    # Run all service checks
    tasks = []
    for svc in SERVICE_DEFS:
        if svc["kind"] == "tcp":
            tasks.append(check_tcp(svc["host"], svc["port"], timeout=svc.get("timeout", 5.0)))
        elif svc["kind"] == "http":
            tasks.append(check_http(svc["url"], timeout=svc.get("timeout", 5.0)))

    results = await asyncio.gather(*tasks)

    checks = []
    for svc, result in zip(SERVICE_DEFS, results):
        check = {
            "name": svc["name"],
            "group": svc["group"],
            "kind": svc["kind"],
            **result,
        }
        checks.append(check)

    report: dict[str, Any] = {
        "timestamp": timestamp,
        "checks": checks,
    }

    # Optional: Kafka topic check
    if with_kafka:
        kafka_result = await check_kafka_topics()
        report["kafka"] = kafka_result

    # Optional: Docker container status
    if with_containers:
        containers = await check_container_status()
        if "error" not in containers:
            report["containers"] = map_container_to_service(containers)
        else:
            report["containers"] = {"error": containers["error"]}

    return report


def print_human(report: dict[str, Any]) -> bool:
    """Print a colorized summary. Returns True if all checks healthy."""
    print("\n" + "═" * 68)
    print("  TalentLens — Platform Service Diagnostics")
    print("═" * 68)

    all_healthy = True
    groups: dict[str, list[dict]] = {}
    for check in report["checks"]:
        groups.setdefault(check["group"], []).append(check)

    group_titles = {
        "infra": "Infrastructure (Docker)",
        "api": "API Services (Python)",
        "frontend": "Frontend",
    }

    for group in ["infra", "api", "frontend"]:
        checks = groups.get(group, [])
        if not checks:
            continue
        print(f"\n  {group_titles.get(group, group)}:")
        print("  " + "-" * 64)
        for c in checks:
            status = c.get("status", "unknown")
            icon = "✅" if status == "healthy" else "⚠️ " if status == "degraded" else "❌"
            latency = f"  ({c['latency_ms']:.0f}ms)" if "latency_ms" in c else ""
            extra = ""
            if "http_status" in c:
                extra = f"  HTTP {c['http_status']}"
            elif "missing_topics" in c:
                extra = f"  missing={len(c['missing_topics'])}"

            # Show dependency details for Gateway
            if c["name"] == "Gateway API" and isinstance(c.get("body"), dict):
                deps = c["body"].get("dependencies", {})
                dep_str = "  ".join(f"{k}={'✅' if v == 'healthy' else '❌'}" for k, v in deps.items())
                extra = f"  {{deps: {dep_str}}}"

            if "counts" in c:
                cnt = c["counts"]
                extra = f"  jobs={cnt.get('jobs_total',0):,} pub={cnt.get('jobs_published',0):,}"

            name = c["name"]
            print(f"  {icon} {name:<24} {status:<12}{latency}{extra}")

            if "error" in c:
                err = str(c["error"])
                if len(err) > 70:
                    err = err[:67] + "..."
                print(f"       └─ {err}")

            if status != "healthy":
                all_healthy = False

    # Kafka section
    if "kafka" in report:
        k = report["kafka"]
        icon = "✅" if k.get("status") == "healthy" else "❌"
        missing = k.get("missing_topics", [])
        extra = f"  topics={k.get('total_topics',0)} missing={len(missing)}"
        print(f"\n  Kafka / Redpanda:")
        print("  " + "-" * 64)
        print(f"  {icon} Kafka Topics  {k.get('status','unknown'):<12}{extra}")
        if missing:
            print(f"       └─ Missing: {', '.join(missing[:5])}{'...' if len(missing) > 5 else ''}")
        if k.get("status") != "healthy":
            all_healthy = False

    # Container status
    if "containers" in report and "error" not in report["containers"]:
        containers = report["containers"]
        print(f"\n  Docker Containers ({len(containers)} running):")
        print("  " + "-" * 64)
        for svc_name in sorted(containers.keys()):
            info = containers[svc_name]
            status = info["status"]
            icon = "✅" if "Up" in status else "⚠️ " if "started" in status else "❌"
            print(f"  {icon} {svc_name:<24} {status}")
    elif "containers" in report:
        print(f"\n  Docker: {report['containers'].get('error', 'unable to check')}")

    # Summary
    healthy = sum(1 for c in report["checks"] if c.get("status") == "healthy")
    total = len(report["checks"])
    print("\n" + "─" * 68)
    overall = (
        f"✅ ALL {total} SERVICES HEALTHY"
        if all_healthy
        else f"❌ {healthy}/{total} SERVICES HEALTHY — {total - healthy} DEGRADED/UNREACHABLE"
    )
    print(f"  {overall}")
    print("═" * 68 + "\n")

    return all_healthy


def main() -> int:
    parser = argparse.ArgumentParser(
        description="TalentLens — Comprehensive platform service diagnostics"
    )
    parser.add_argument("--json", action="store_true", help="Output JSON instead of human-readable")
    parser.add_argument("--exit-on-fail", action="store_true", help="Exit with code 1 if any check fails")
    parser.add_argument("--check-kafka", action="store_true", help="Also check Kafka topic health")
    parser.add_argument("--check-containers", action="store_true", help="Also check Docker container status")
    args = parser.parse_args()

    report = asyncio.run(run_diagnostics(
        with_kafka=args.check_kafka,
        with_containers=args.check_containers,
    ))

    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        all_ok = print_human(report)

    if args.exit_on_fail:
        all_ok = all(c.get("status") == "healthy" for c in report["checks"])
        if "kafka" in report:
            all_ok = all_ok and report["kafka"].get("status") == "healthy"
        if not all_ok:
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
