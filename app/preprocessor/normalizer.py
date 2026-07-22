"""
Job Normalizer: Extracts skills, experience, and normalizes text.
"""

import re
from typing import List, Optional, Set

from app.utils.logging import get_logger

logger = get_logger(__name__)


class JobNormalizer:
    """Normalizes job data."""

    COMMON_SKILLS: Set[str] = {
        "python", "java", "javascript", "react", "angular", "vue",
        "aws", "azure", "gcp", "docker", "kubernetes", "terraform",
        "sql", "postgresql", "mongodb", "redis", "elasticsearch",
        "machine learning", "deep learning", "nlp", "data science",
        "agile", "scrum", "git", "ci/cd", "devops", "sre",
        "leadership", "communication", "problem solving",
    }

    def normalize_title(self, title: str) -> str:
        """Clean title."""
        title = " ".join(title.split())
        title = re.sub(r"^(Urgent|Immediate|Looking for)\s+", "", title, flags=re.IGNORECASE)
        return title.strip()

    def extract_skills(self, text: str) -> List[str]:
        """Extract skills from description."""
        if not text:
            return []

        text = text.lower()
        skills = []
        for skill in self.COMMON_SKILLS:
            if skill in text:
                skills.append(skill)
        return skills

    def extract_experience_years(self, text: str) -> Optional[float]:
        """Extract years of experience."""
        if not text:
            return None

        patterns = [
            r"(\d+)\s*[-–—]\s*(\d+)\s*(?:years?|yrs?)",
            r"(\d+)\s*\+\s*(?:years?|yrs?)",
            r"(\d+)\s*(?:years?|yrs?)\s+experience",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                if len(match.groups()) == 2:
                    return (float(match.group(1)) + float(match.group(2))) / 2
                return float(match.group(1))
        return None