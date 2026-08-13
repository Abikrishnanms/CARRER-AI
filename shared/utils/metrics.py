"""
Prometheus metrics — optional, silently no-ops when prometheus_client not installed.
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

_metrics: dict[str, Any] = {}
_enabled = False


def setup_metrics(app: Any = None, port: int = 9090) -> None:
    """
    Set up Prometheus metrics collection.
    If prometheus_client is not installed, logs a warning and continues.
    """
    global _enabled

    if os.getenv("METRICS_ENABLED", "true").lower() != "true":
        logger.info("Prometheus metrics disabled via METRICS_ENABLED=false")
        return

    try:
        from prometheus_client import Counter, Gauge, Histogram, start_http_server

        _metrics["jobs_collected_total"] = Counter(
            "jobs_collected_total",
            "Total jobs collected from all sources",
            ["source"],
        )
        _metrics["jobs_processed_total"] = Counter(
            "jobs_processed_total",
            "Total jobs processed by pipeline stage",
            ["stage", "status"],
        )
        _metrics["jobs_rejected_total"] = Counter(
            "jobs_rejected_total",
            "Total jobs rejected (scam/duplicate)",
            ["reason"],
        )
        _metrics["api_requests_total"] = Counter(
            "api_requests_total",
            "Total API requests",
            ["method", "endpoint", "status_code"],
        )
        _metrics["api_request_duration_seconds"] = Histogram(
            "api_request_duration_seconds",
            "API request latency",
            ["method", "endpoint"],
        )
        _metrics["pipeline_queue_size"] = Gauge(
            "pipeline_queue_size",
            "Number of jobs queued at each stage",
            ["stage"],
        )
        _metrics["active_workers"] = Gauge(
            "active_workers",
            "Active workers per service",
            ["service"],
        )

        if app is None:
            # Start standalone metrics server
            metrics_port = int(os.getenv("METRICS_PORT", str(port)))
            start_http_server(metrics_port)
            logger.info(f"Prometheus metrics server started on :{metrics_port}")
        else:
            # Mount to FastAPI
            try:
                from prometheus_fastapi_instrumentator import Instrumentator
                Instrumentator().instrument(app).expose(app)
                logger.info("Prometheus metrics mounted on /metrics")
            except ImportError:
                logger.warning(
                    "prometheus-fastapi-instrumentator not installed — "
                    "metrics will not be exposed via FastAPI"
                )

        _enabled = True

    except ImportError:
        logger.warning(
            "prometheus_client not installed — metrics collection disabled. "
            "Install with: pip install prometheus-client"
        )


def increment(metric: str, labels: dict[str, str] | None = None, value: float = 1.0) -> None:
    """Increment a counter metric (no-op if metrics disabled)."""
    if not _enabled:
        return
    m = _metrics.get(metric)
    if m and labels:
        m.labels(**labels).inc(value)
    elif m:
        m.inc(value)


def observe(metric: str, value: float, labels: dict[str, str] | None = None) -> None:
    """Observe a histogram/gauge value (no-op if metrics disabled)."""
    if not _enabled:
        return
    m = _metrics.get(metric)
    if m and labels:
        m.labels(**labels).observe(value)
    elif m:
        m.observe(value)


def set_gauge(metric: str, value: float, labels: dict[str, str] | None = None) -> None:
    """Set a gauge metric value (no-op if metrics disabled)."""
    if not _enabled:
        return
    m = _metrics.get(metric)
    if m and labels:
        m.labels(**labels).set(value)
    elif m:
        m.set(value)
