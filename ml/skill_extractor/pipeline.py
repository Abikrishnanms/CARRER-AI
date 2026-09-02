"""
Skill Extractor — spaCy-based NER pipeline for extracting skills from job descriptions.
Uses a custom entity ruler with a curated skills dictionary.

Usage:
  python ml/skill_extractor/pipeline.py --text "We need Python, FastAPI, and AWS experience."
"""

from __future__ import annotations

import argparse
import json
import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ─── Master Skills Dictionary ─────────────────────────────────────────────────

SKILLS_DB: dict[str, list[str]] = {
    "programming_languages": [
        "Python", "Java", "JavaScript", "TypeScript", "Go", "Golang",
        "Rust", "C++", "C#", "Ruby", "PHP", "Swift", "Kotlin",
        "Scala", "R", "MATLAB", "Perl", "Bash", "Shell",
    ],
    "web_frameworks": [
        "FastAPI", "Django", "Flask", "Spring Boot", "Express.js",
        "React", "Vue.js", "Angular", "Next.js", "Nuxt.js",
        "Svelte", "Ruby on Rails", "Laravel", "NestJS", "Gin",
    ],
    "databases": [
        "PostgreSQL", "MySQL", "MongoDB", "Redis", "Elasticsearch",
        "Cassandra", "DynamoDB", "SQLite", "MariaDB", "Neo4j",
        "Qdrant", "Pinecone", "Weaviate", "CockroachDB",
    ],
    "cloud_devops": [
        "AWS", "GCP", "Azure", "Docker", "Kubernetes", "Terraform",
        "Ansible", "Jenkins", "GitHub Actions", "GitLab CI", "CircleCI",
        "Helm", "Prometheus", "Grafana", "Datadog", "PagerDuty",
        "Nginx", "HAProxy", "Istio", "ArgoCD",
    ],
    "data_ml": [
        "TensorFlow", "PyTorch", "scikit-learn", "Keras", "XGBoost",
        "LightGBM", "Spark", "Hadoop", "Airflow", "dbt", "MLflow",
        "Hugging Face", "LangChain", "LlamaIndex", "spaCy", "NLTK",
        "OpenCV", "Pandas", "NumPy", "SciPy", "Matplotlib",
    ],
    "messaging": [
        "Kafka", "RabbitMQ", "Redis Streams", "AWS SQS", "NATS", "Pulsar",
    ],
    "methodologies": [
        "Agile", "Scrum", "Kanban", "TDD", "BDD", "CI/CD",
        "DevOps", "MLOps", "SRE", "REST API", "GraphQL", "gRPC",
        "Microservices", "Event-Driven Architecture",
    ],
    "soft_skills": [
        "Problem Solving", "Team Player", "Communication", "Leadership",
        "Mentoring", "Project Management", "Stakeholder Management",
    ],
}

# Flatten for lookup
ALL_SKILLS: list[str] = []
SKILL_CATEGORY_MAP: dict[str, str] = {}

for category, skills_list in SKILLS_DB.items():
    for skill in skills_list:
        ALL_SKILLS.append(skill)
        SKILL_CATEGORY_MAP[skill.lower()] = category

# O(1) normalization lookup map
_NORMALIZE_MAP = {s.lower(): s for s in ALL_SKILLS}

# Build regex patterns (sorted by length desc so longer matches win)
ALL_SKILLS_SORTED = sorted(ALL_SKILLS, key=len, reverse=True)
_PATTERN = "|".join(re.escape(s) for s in ALL_SKILLS_SORTED)
_REGEX = re.compile(r"\b(?:" + _PATTERN + r")\b", re.IGNORECASE)


# ─── Extraction Pipeline ──────────────────────────────────────────────────────

class SkillExtractorPipeline:
    """
    Fast regex-based skill extractor with spaCy NER fallback.
    Falls back to pure regex if spaCy is not installed.
    """

    def __init__(self, use_spacy: bool = True) -> None:
        self.nlp = None
        if use_spacy:
            try:
                import spacy
                self.nlp = spacy.blank("en")
                ruler = self.nlp.add_pipe("entity_ruler")
                patterns = [
                    {"label": "SKILL", "pattern": skill}
                    for skill in ALL_SKILLS
                ]
                ruler.add_patterns(patterns)
                logger.info("spaCy entity ruler initialized")
            except ImportError:
                logger.warning("spaCy not available — using regex only")

    def extract(self, text: str) -> dict[str, Any]:
        """
        Extract skills from text.
        Returns: {
          skills: list of unique skill strings,
          categories: dict of category -> list of skills,
          top_skills: top 10 by frequency,
          confidence: float
        }
        """
        if not text:
            return {"skills": [], "categories": {}, "top_skills": [], "confidence": 0.0}

        # Regex extraction (primary)
        matches = _REGEX.findall(text)
        found: dict[str, int] = {}  # skill_normalized -> count
        for m in matches:
            key = m.lower()
            canonical = _normalize(m)
            found[canonical] = found.get(canonical, 0) + 1

        # spaCy NER (secondary enrichment)
        if self.nlp and len(text) < 50_000:
            doc = self.nlp(text)
            for ent in doc.ents:
                if ent.label_ == "SKILL":
                    key = _normalize(ent.text)
                    found[key] = found.get(key, 0) + 1

        unique_skills = list(found.keys())

        # Group by category
        categories: dict[str, list[str]] = {}
        for skill in unique_skills:
            cat = SKILL_CATEGORY_MAP.get(skill.lower(), "other")
            categories.setdefault(cat, []).append(skill)

        top_skills = sorted(found.items(), key=lambda x: x[1], reverse=True)[:10]

        return {
            "skills": unique_skills,
            "categories": categories,
            "top_skills": [s for s, _ in top_skills],
            "skill_frequency": found,
            "confidence": min(1.0, len(unique_skills) / 10),
        }

    def categorize(self, skills: list[str]) -> dict[str, list[str]]:
        """Categorize a list of skill strings."""
        result: dict[str, list[str]] = {}
        for skill in skills:
            cat = SKILL_CATEGORY_MAP.get(skill.lower(), "other")
            result.setdefault(cat, []).append(skill)
        return result


def _normalize(skill_text: str) -> str:
    """Normalize skill text to canonical form (O(1) lookup)."""
    return _NORMALIZE_MAP.get(skill_text.lower(), skill_text.strip())


_shared_pipeline: SkillExtractorPipeline | None = None

@lru_cache(maxsize=2000)
def _cached_extract_skills(text: str) -> tuple[str, ...]:
    global _shared_pipeline
    if _shared_pipeline is None:
        _shared_pipeline = SkillExtractorPipeline(use_spacy=False)
    result = _shared_pipeline.extract(text)
    return tuple(result["skills"])

def extract_skills_from_text(text: str) -> list[str]:
    """Simple function wrapper — returns list of unique extracted skills (cached)."""
    return list(_cached_extract_skills(text))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="TalentLens Skill Extractor")
    parser.add_argument("--text", help="Text to extract skills from")
    parser.add_argument("--file", help="File to read text from")
    args = parser.parse_args()

    text = args.text or (Path(args.file).read_text() if args.file else "")
    if not text:
        parser.error("Provide --text or --file")

    pipeline = SkillExtractorPipeline(use_spacy=True)
    result = pipeline.extract(text)
    print(json.dumps(result, indent=2))
