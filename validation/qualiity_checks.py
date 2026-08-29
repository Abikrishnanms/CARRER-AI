"""
validation/quality_checks.py

Additional quality/validation checks for job postings beyond
basic Pydantic schema validation.
"""

import re

SPAM_PATTERNS = [
    r"want all the money",
    r"job hunting indecision",
    r"^no\b.*shapeshifter",
    r"how do i prevent",
]

def is_suspicious_title(title: str) -> bool:
    if not title or len(title.strip()) < 3:
        return True
    for pattern in SPAM_PATTERNS:
        if re.search(pattern, title, re.IGNORECASE):
            return True
    return False

def has_valid_description(description: str, min_length: int = 20) -> bool:
    return bool(description and len(description.strip()) >= min_length)

def has_reasonable_url(url: str) -> bool:
    return bool(url and url.startswith(("http://", "https://")) and len(url) > 15)

def quality_check(job: dict) -> dict:
    """
    Returns a dict with pass/fail + reasons, used to flag jobs as
    'validated' vs 'flagged' beyond basic schema validation.
    """
    reasons = []

    if is_suspicious_title(job.get("title", "")):
        reasons.append("suspicious_title")
    if not has_valid_description(job.get("description", "")):
        reasons.append("thin_description")
    if not has_reasonable_url(job.get("url", "")):
        reasons.append("invalid_url")

    return {
        "is_valid": len(reasons) == 0,
        "reasons": reasons,
    }