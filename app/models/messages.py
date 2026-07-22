"""
SESSION 2: The RabbitMQ Message Envelope.
This wraps the RawJob for safe travel through the queue.
"""

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class JobMessage(BaseModel):
    """
    The message envelope that travels through RabbitMQ.
    """
    # --- Message Routing Metadata ---
    version: str = "1.0"
    message_id: str = Field(default_factory=lambda: str(uuid4()))
    correlation_id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # --- Sender Info ---
    source_agent: str       # e.g., "adzuna_adapter"
    source_platform: str    # e.g., "adzuna"

    # --- The Data ---
    job_id: str
    payload: Dict[str, Any]  # This will hold the serialized RawJob dictionary

    # --- Retry & Error Handling ---
    retry_count: int = 0
    max_retries: int = 3
    error_message: Optional[str] = None
    error_traceback: Optional[str] = None