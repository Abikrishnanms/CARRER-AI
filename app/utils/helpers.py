"""
Helper Functions
"""

import hashlib
import re
from datetime import datetime
from typing import Optional

def generate_job_id(job_url: str, job_title: str) -> str:
    """
    Generate unique job ID using MD5 hash
    
    Args:
        job_url: Job posting URL
        job_title: Job title
    
    Returns:
        MD5 hash as unique ID
    """
    if not job_url or not job_title:
        return None
    
    unique_string = f"{job_url}_{job_title}"
    job_id = hashlib.md5(unique_string.encode()).hexdigest()
    return job_id

def clean_text(text: str) -> Optional[str]:
    """
    Clean text by removing HTML, extra whitespace
    
    Args:
        text: Raw text
    
    Returns:
        Cleaned text or None
    """
    if not text:
        return None
    
    # Remove HTML tags
    text = re.sub('<[^<]+?>', '', text)
    
    # Remove extra whitespace
    text = ' '.join(text.split())
    
    # Remove special characters
    text = text.replace('\n', ' ').replace('\r', '')
    
    return text.strip() or None

def get_current_timestamp() -> str:
    """Get current ISO format timestamp"""
    return datetime.now().isoformat()

def extract_city_from_location(location: str) -> Optional[str]:
    """
    Extract city name from location string
    
    Args:
        location: Location string (e.g., "Bengaluru, Karnataka")
    
    Returns:
        City name or None
    """
    if not location:
        return None
    
    parts = location.split(',')
    return parts[0].strip() if parts else None

def validate_url(url: str) -> bool:
    """
    Validate if URL is properly formatted
    
    Args:
        url: URL to validate
    
    Returns:
        True if valid, False otherwise
    """
    url_pattern = re.compile(
        r'^https?://'
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'
        r'localhost|'
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
        r'(?::\d+)?'
        r'(?:/?|[/?]\S+)$', re.IGNORECASE
    )
    
    return url_pattern.match(url) is not None