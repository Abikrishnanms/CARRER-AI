"""
Structured logging utilities — JSON formatter for production, pretty for dev.
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any


class _JsonFormatter(logging.Formatter):
    """Emit log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        import json
        from datetime import datetime, timezone

        log_obj: dict[str, Any] = {
            "ts": datetime.now(tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "service": os.getenv("SERVICE_NAME", "unknown"),
        }
        if record.exc_info:
            log_obj["exc"] = self.formatException(record.exc_info)
        if hasattr(record, "extra"):
            log_obj.update(record.extra)  # type: ignore[arg-type]
        return json.dumps(log_obj, default=str)


def setup_logging(
    level: str | None = None,
    json_format: bool | None = None,
) -> None:
    """
    Configure root logger.
    - JSON format in production (APP_ENV=production)
    - Coloured text in development
    """
    log_level = level or os.getenv("LOG_LEVEL", "INFO").upper()
    use_json = json_format if json_format is not None else (
        os.getenv("APP_ENV", "development") == "production"
    )

    root = logging.getLogger()
    root.setLevel(log_level)

    # Remove existing handlers
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    if use_json:
        handler.setFormatter(_JsonFormatter())
    else:
        fmt = "%(asctime)s [%(levelname)-8s] %(name)s — %(message)s"
        handler.setFormatter(logging.Formatter(fmt, datefmt="%H:%M:%S"))

    root.addHandler(handler)

    # Silence noisy third-party loggers
    for noisy in ["aiokafka", "kafka", "httpx", "httpcore", "asyncio", "motor"]:
        logging.getLogger(noisy).setLevel(logging.WARNING)

    logging.getLogger(__name__).debug("Logging configured (level=%s, json=%s)", log_level, use_json)
