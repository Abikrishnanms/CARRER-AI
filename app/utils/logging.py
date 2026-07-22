"""
Session 2.5: Structured Logging Setup.
Configures logging with structlog for JSON-formatted logs.
"""

import logging
import sys
from typing import Optional

import structlog

# Configure structlog for structured logging
structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)


def get_logger(name: Optional[str] = None) -> structlog.BoundLogger:
    """
    Get a structured logger instance.

    Args:
        name: Logger name (usually __name__)

    Returns:
        Structlog bound logger
    """
    # Configure standard logging for structlog
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.INFO,
    )

    if name:
        return structlog.get_logger(name)
    return structlog.get_logger()