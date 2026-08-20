**Skill Extractor — `ml/skill_extractor/pipeline.py` (Annotated copy)**

Summary: Regex-first skill extraction pipeline with optional spaCy entity-ruler enhancement. Uses a curated skills dictionary and returns categorized skills, top skills, frequency and confidence.

---

```python
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
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Master skills dictionary grouped by category
SKILLS_DB: dict[str, list[str]] = {
    ...
}

# Flatten to `ALL_SKILLS` and `SKILL_CATEGORY_MAP`, build `_REGEX` sorted by length

class SkillExtractorPipeline:
    """
    Fast regex-based skill extractor with spaCy NER fallback.
    Falls back to pure regex if spaCy is not installed.
    """

    def __init__(self, use_spacy: bool = True) -> None:
        # Try to bootstrap a blank spaCy pipeline with an entity_ruler and add patterns
        # If spaCy is unavailable, warn and rely on regex-only extraction.
        ...

    def extract(self, text: str) -> dict[str, Any]:
        # 1) Run `_REGEX.findall(text)` to count occurrences
        # 2) Optionally run `spaCy` entity ruler for additional matches
        # 3) Aggregate unique skills, group by category via `SKILL_CATEGORY_MAP`
        # 4) Return `skills`, `categories`, `top_skills`, `skill_frequency`, `confidence`
        ...

    def categorize(self, skills: list[str]) -> dict[str, list[str]]:
        # Map skill strings to categories
        ...

def _normalize(skill_text: str) -> str:
    # Normalize token to canonical entry from the dictionary
    ...

def extract_skills_from_text(text: str) -> list[str]:
    pipeline = SkillExtractorPipeline(use_spacy=False)
    result = pipeline.extract(text)
    return result["skills"]

if __name__ == "__main__":
    # CLI wrapper to extract skills from `--text` or `--file`
    ...
```

Grouped explanations:

- The extractor is intentionally regex-first for speed and robustness across large volumes; spaCy is used only when available for higher-quality NER.
- The curated `SKILLS_DB` covers programming languages, frameworks, databases, cloud/devops, data/ML, messaging, methodologies and soft skills; `ALL_SKILLS_SORTED` ensures longer tokens match before shorter ones.
- `SkillExtractorPipeline.extract()` computes normalized skill frequencies and categories, returning a `confidence` proportional to the number of unique skills found.

Notes:
- This module is used by the `enrichment` service to produce `required_skills`, `tech_stack`, and `skills_data` for each job document.
- To extend extraction, update `SKILLS_DB` and re-run services; adding spaCy model patterns would improve recall for variant spellings.
