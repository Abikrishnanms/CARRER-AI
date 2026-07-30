"""
models/raw_posting.py

Pydantic schema for a raw job posting before it's stored in MongoDB.
"""

from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class RawPosting(BaseModel):
    title: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    url: str
    tags: List[str] = Field(default_factory=list)
    source: str
    scraped_at: str
    posted_date: Optional[str] = None
    remote : Optional[bool] = None