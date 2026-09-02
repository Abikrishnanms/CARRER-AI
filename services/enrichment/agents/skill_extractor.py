"""
Skill Extraction Agent — NLP-powered skill extraction from job descriptions.
Uses spaCy NER + skill taxonomy matching + LLM fallback.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any

from shared.models.job import Skill, SkillCategory, ExperienceLevel

logger = logging.getLogger(__name__)

# ─── Built-in Skill Taxonomy ──────────────────────────────────────────────────
# A curated subset of the O*NET skill taxonomy + tech skills
# In production, this is loaded from PostgreSQL (skill_taxonomy table)

SKILL_TAXONOMY: dict[str, dict[str, Any]] = {
    # Programming Languages
    "python": {"category": "technical", "aliases": ["python3", "python 3", "py"]},
    "javascript": {"category": "technical", "aliases": ["js", "es6", "es2015", "node.js", "nodejs"]},
    "typescript": {"category": "technical", "aliases": ["ts"]},
    "java": {"category": "technical", "aliases": ["java 8", "java 11", "java 17"]},
    "c++": {"category": "technical", "aliases": ["cpp", "c plus plus"]},
    "rust": {"category": "technical", "aliases": ["rust-lang"]},
    "go": {"category": "technical", "aliases": ["golang", "go lang"]},
    "kotlin": {"category": "technical", "aliases": []},
    "swift": {"category": "technical", "aliases": []},
    "r": {"category": "technical", "aliases": ["r programming", "r language"]},
    "scala": {"category": "technical", "aliases": []},
    "php": {"category": "technical", "aliases": ["php7", "php8"]},
    "ruby": {"category": "technical", "aliases": ["ruby on rails", "ror"]},

    # Web Frameworks
    "react": {"category": "technical", "aliases": ["reactjs", "react.js"]},
    "vue": {"category": "technical", "aliases": ["vuejs", "vue.js"]},
    "angular": {"category": "technical", "aliases": ["angularjs"]},
    "django": {"category": "technical", "aliases": ["django rest framework", "drf"]},
    "fastapi": {"category": "technical", "aliases": ["fast api"]},
    "flask": {"category": "technical", "aliases": []},
    "spring boot": {"category": "technical", "aliases": ["spring", "spring framework"]},
    "express": {"category": "technical", "aliases": ["express.js", "expressjs"]},
    "next.js": {"category": "technical", "aliases": ["nextjs", "next js"]},

    # Databases
    "postgresql": {"category": "technical", "aliases": ["postgres", "pg"]},
    "mysql": {"category": "technical", "aliases": []},
    "mongodb": {"category": "technical", "aliases": ["mongo"]},
    "redis": {"category": "technical", "aliases": []},
    "elasticsearch": {"category": "technical", "aliases": ["elastic search", "es"]},
    "cassandra": {"category": "technical", "aliases": ["apache cassandra"]},
    "dynamodb": {"category": "technical", "aliases": ["dynamo db"]},
    "sqlite": {"category": "technical", "aliases": []},
    "oracle": {"category": "technical", "aliases": ["oracle db"]},
    "mssql": {"category": "technical", "aliases": ["sql server", "microsoft sql"]},

    # Cloud & DevOps
    "aws": {"category": "technical", "aliases": ["amazon web services"]},
    "gcp": {"category": "technical", "aliases": ["google cloud", "google cloud platform"]},
    "azure": {"category": "technical", "aliases": ["microsoft azure"]},
    "docker": {"category": "technical", "aliases": ["containerization"]},
    "kubernetes": {"category": "technical", "aliases": ["k8s"]},
    "terraform": {"category": "technical", "aliases": ["tf"]},
    "ansible": {"category": "technical", "aliases": []},
    "jenkins": {"category": "technical", "aliases": ["jenkins ci"]},
    "github actions": {"category": "technical", "aliases": ["gh actions"]},
    "gitlab ci": {"category": "technical", "aliases": ["gitlab"]},

    # AI/ML
    "machine learning": {"category": "technical", "aliases": ["ml"]},
    "deep learning": {"category": "technical", "aliases": ["dl"]},
    "tensorflow": {"category": "technical", "aliases": ["tf", "tensorflow 2"]},
    "pytorch": {"category": "technical", "aliases": ["torch"]},
    "scikit-learn": {"category": "technical", "aliases": ["sklearn", "scikit learn"]},
    "nlp": {"category": "technical", "aliases": ["natural language processing"]},
    "computer vision": {"category": "technical", "aliases": ["cv", "image processing"]},
    "llm": {"category": "technical", "aliases": ["large language models"]},
    "langchain": {"category": "technical", "aliases": []},
    "hugging face": {"category": "technical", "aliases": ["huggingface", "transformers"]},

    # Data & Analytics
    "sql": {"category": "technical", "aliases": ["structured query language"]},
    "pandas": {"category": "technical", "aliases": []},
    "numpy": {"category": "technical", "aliases": []},
    "spark": {"category": "technical", "aliases": ["apache spark", "pyspark"]},
    "kafka": {"category": "technical", "aliases": ["apache kafka"]},
    "airflow": {"category": "technical", "aliases": ["apache airflow"]},
    "tableau": {"category": "tool", "aliases": []},
    "power bi": {"category": "tool", "aliases": ["powerbi"]},
    "dbt": {"category": "technical", "aliases": ["data build tool"]},

    # Soft Skills
    "communication": {"category": "soft", "aliases": []},
    "leadership": {"category": "soft", "aliases": ["team leadership"]},
    "problem solving": {"category": "soft", "aliases": ["analytical thinking"]},
    "teamwork": {"category": "soft", "aliases": ["collaboration", "team player"]},
    "agile": {"category": "soft", "aliases": ["scrum", "kanban"]},
    "project management": {"category": "soft", "aliases": ["pmp"]},

    # Testing
    "pytest": {"category": "technical", "aliases": []},
    "jest": {"category": "technical", "aliases": []},
    "selenium": {"category": "technical", "aliases": []},
    "cypress": {"category": "technical", "aliases": []},
    "unit testing": {"category": "technical", "aliases": ["tdd", "test driven development"]},

    # Architecture & Patterns
    "microservices": {"category": "technical", "aliases": ["micro services"]},
    "api design": {"category": "technical", "aliases": ["rest api", "restful", "graphql"]},
    "system design": {"category": "technical", "aliases": []},
    "event-driven": {"category": "technical", "aliases": ["event driven architecture"]},

    # Certifications
    "aws certified": {"category": "certification", "aliases": ["aws solutions architect", "aws ccp"]},
    "google certified": {"category": "certification", "aliases": ["gcp certified"]},
    "cpa": {"category": "certification", "aliases": []},
    "pmp": {"category": "certification", "aliases": ["pmi-pmp"]},
}

# Build reverse alias lookup
ALIAS_TO_SKILL: dict[str, str] = {}
for skill_name, info in SKILL_TAXONOMY.items():
    ALIAS_TO_SKILL[skill_name] = skill_name
    for alias in info.get("aliases", []):
        ALIAS_TO_SKILL[alias.lower()] = skill_name


# ─── Experience Level Indicators ──────────────────────────────────────────────

EXPERIENCE_INDICATORS = {
    ExperienceLevel.ENTRY: [
        r"\b0[–-]1\s*year", r"\bfresher", r"\bgraduate", r"\bjunior\b",
        r"\bentry.?level\b", r"\bno experience\b", r"\b0-2 years\b",
    ],
    ExperienceLevel.MID: [
        r"\b[2-4][–-]\d\s*year", r"\bmid.?level\b", r"\bintermediate\b",
    ],
    ExperienceLevel.SENIOR: [
        r"\b[5-9]\+?\s*year", r"\bsenior\b", r"\bsr\.\b", r"\blead\b",
    ],
    ExperienceLevel.LEAD: [
        r"\bteam lead\b", r"\btech lead\b", r"\barchitect\b", r"\bprincipal\b",
    ],
    ExperienceLevel.EXECUTIVE: [
        r"\bvp\b", r"\bdirector\b", r"\bcto\b", r"\bceo\b", r"\bhead of\b",
        r"\bvice president\b",
    ],
}


class SkillExtractionAgent:
    """
    Skill Extraction Agent using multi-layer approach:
    1. Taxonomy matching (fast, rule-based) — primary
    2. spaCy NER (if available) — secondary
    3. LLM extraction (if configured) — for complex/ambiguous cases

    Architecture doc: Section 3.3.5
    """

    def __init__(self) -> None:
        self._nlp = None
        self._llm_router = None
        self._load_spacy()

    def _load_spacy(self) -> None:
        """Load spaCy model if available."""
        try:
            import spacy
            model_name = os.getenv("SKILL_EXTRACTOR_MODEL", "en_core_web_sm")
            self._nlp = spacy.load(model_name)
            logger.info(f"spaCy model '{model_name}' loaded for skill extraction")
        except Exception as e:
            logger.info(f"spaCy not available ({e}) — using taxonomy matching only")

    async def extract(
        self,
        title: str,
        description: str,
        use_llm: bool = True,
    ) -> list[Skill]:
        """
        Extract skills from job title and description.
        Returns deduplicated, normalized skill list with confidence scores.
        """
        full_text = f"{title}\n{description}"

        # Layer 1: Taxonomy matching
        taxonomy_skills = self._extract_by_taxonomy(full_text)

        # Layer 2: spaCy NER (if available)
        if self._nlp:
            spacy_skills = self._extract_by_spacy(full_text)
            # Merge without duplicates
            existing_names = {s.normalized_name for s in taxonomy_skills}
            for skill in spacy_skills:
                if skill.normalized_name not in existing_names:
                    taxonomy_skills.append(skill)
                    existing_names.add(skill.normalized_name)

        # Layer 3: LLM extraction for short/ambiguous descriptions
        if use_llm and len(taxonomy_skills) < 3 and len(description) > 100:
            llm_skills = await self._extract_by_llm(title, description, taxonomy_skills)
            existing_names = {s.normalized_name for s in taxonomy_skills}
            for skill in llm_skills:
                if skill.normalized_name not in existing_names:
                    taxonomy_skills.append(skill)

        # Detect required vs nice-to-have
        taxonomy_skills = self._classify_required(full_text, taxonomy_skills)

        return taxonomy_skills

    def _extract_by_taxonomy(self, text: str) -> list[Skill]:
        """Fast taxonomy-based skill extraction using regex."""
        skills = []
        text_lower = text.lower()
        found = set()

        for term, canonical_name in ALIAS_TO_SKILL.items():
            if canonical_name in found:
                continue

            # Word boundary match to avoid partial matches
            pattern = r'\b' + re.escape(term) + r'\b'
            if re.search(pattern, text_lower):
                skill_info = SKILL_TAXONOMY.get(canonical_name, {})
                category = SkillCategory(skill_info.get("category", "technical"))

                skills.append(Skill(
                    name=canonical_name.title(),
                    normalized_name=canonical_name,
                    category=category,
                    confidence=0.9,
                    source="taxonomy",
                ))
                found.add(canonical_name)

        return skills

    def _extract_by_spacy(self, text: str) -> list[Skill]:
        """Extract entities using spaCy NER."""
        if not self._nlp:
            return []

        doc = self._nlp(text[:10000])  # Limit to 10k chars
        skills = []

        for ent in doc.ents:
            if ent.label_ in ("PRODUCT", "ORG", "GPE"):
                name_lower = ent.text.lower().strip()
                # Check if it's in our taxonomy
                if name_lower in ALIAS_TO_SKILL:
                    canonical = ALIAS_TO_SKILL[name_lower]
                    skill_info = SKILL_TAXONOMY.get(canonical, {})
                    skills.append(Skill(
                        name=ent.text,
                        normalized_name=canonical,
                        category=SkillCategory(skill_info.get("category", "technical")),
                        confidence=0.7,
                        source="spacy",
                    ))

        return skills

    async def _extract_by_llm(
        self,
        title: str,
        description: str,
        existing_skills: list[Skill],
    ) -> list[Skill]:
        """Use LLM to extract skills not found by taxonomy."""
        try:
            from shared.llm.router import get_llm_router
            router = get_llm_router()

            existing_names = [s.name for s in existing_skills]
            prompt = f"""Extract technical and soft skills from this job posting.
Return ONLY a JSON array of skill names. Be concise.

Job Title: {title}
Description (first 500 chars): {description[:500]}
Already found: {existing_names}

Return format: ["skill1", "skill2", ...]
Only return skills NOT already in the 'Already found' list."""

            result = await router.invoke(prompt, task_type="skill_extraction")
            content = result.get("content", "[]")

            # Parse JSON response
            import json
            raw = re.search(r'\[.*?\]', content, re.DOTALL)
            if raw:
                skill_names = json.loads(raw.group())
                skills = []
                for name in skill_names[:10]:  # Limit to 10 LLM-extracted skills
                    if isinstance(name, str) and len(name) < 50:
                        normalized = name.lower().strip()
                        # Check taxonomy
                        canonical = ALIAS_TO_SKILL.get(normalized, normalized)
                        skill_info = SKILL_TAXONOMY.get(canonical, {})
                        skills.append(Skill(
                            name=name.strip(),
                            normalized_name=canonical,
                            category=SkillCategory(skill_info.get("category", "technical")),
                            confidence=0.6,
                            source="llm",
                        ))
                return skills

        except Exception as e:
            logger.debug(f"LLM skill extraction failed: {e}")

        return []

    def _classify_required(
        self,
        full_text: str,
        skills: list[Skill],
    ) -> list[Skill]:
        """
        Classify each skill as required vs nice-to-have
        based on surrounding context.
        """
        nice_to_have_context = re.compile(
            r"(preferred|nice to have|good to have|plus|bonus|desirable|optional|advantageous)"
            r".{0,200}$",
            re.IGNORECASE | re.MULTILINE,
        )

        for skill in skills:
            # Check if skill appears after nice-to-have phrases
            skill_pos = full_text.lower().find(skill.normalized_name)
            if skill_pos > 0:
                preceding = full_text[max(0, skill_pos - 200):skill_pos]
                if re.search(
                    r"(nice to have|good to have|preferred|plus|bonus|optional)",
                    preceding,
                    re.IGNORECASE,
                ):
                    skill.is_required = False

        return skills

    def detect_experience_level(self, text: str) -> ExperienceLevel:
        """Detect required experience level from job text."""
        text_lower = text.lower()

        for level, patterns in EXPERIENCE_INDICATORS.items():
            for pattern in patterns:
                if re.search(pattern, text_lower, re.IGNORECASE):
                    return level

        return ExperienceLevel.UNKNOWN
