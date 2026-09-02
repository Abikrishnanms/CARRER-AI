"""
Salary Extractor Agent — estimates salary ranges from job descriptions using
rule-based extraction + LLM fallback.
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


class SalaryEstimate:
    """Salary estimation result."""

    def __init__(
        self,
        min_value: float | None,
        max_value: float | None,
        currency: str,
        period: str,
        is_estimated: bool,
        confidence: float,
        source: str,
    ) -> None:
        self.min_value = min_value
        self.max_value = max_value
        self.currency = currency
        self.period = period
        self.is_estimated = is_estimated
        self.confidence = confidence  # 0.0 – 1.0
        self.source = source  # "explicit", "llm_extracted", "estimated"

    @property
    def midpoint(self) -> float | None:
        if self.min_value is not None and self.max_value is not None:
            return (self.min_value + self.max_value) / 2
        return self.min_value or self.max_value

    def to_dict(self) -> dict[str, Any]:
        return {
            "min_value": self.min_value,
            "max_value": self.max_value,
            "currency": self.currency,
            "period": self.period,
            "is_estimated": self.is_estimated,
            "confidence": self.confidence,
            "source": self.source,
        }


# ─── Rule-based patterns ──────────────────────────────────────────────────────

# Matches: ₹5L, ₹5 LPA, ₹5-10 LPA, INR 500000-1000000, $50k-$80k, ₹5L-10L
_SALARY_PATTERNS = [
    # Compact lakh shorthand: "₹5L-10L", "₹5L to 10L", "5L-10L" (L attached to each number)
    (
        r"(?:₹|inr|rs\.?)\s*(\d+(?:\.\d+)?)\s*l(?:akh)?\s*(?:[-–to]+)\s*(\d+(?:\.\d+)?)\s*l(?:akh)?",
        "INR", "yearly", 100_000,
    ),
    (
        r"(\d+(?:\.\d+)?)\s*l(?:akh)?\s*(?:[-–to]+)\s*(\d+(?:\.\d+)?)\s*l(?:akh)?",
        "INR", "yearly", 100_000,
    ),
    # INR Lakh patterns: "5-10 LPA", "5 to 10 lakh" (unit at end only)
    (
        r"(?:₹|inr|rs\.?)\s*(\d+(?:\.\d+)?)\s*(?:[-–to]+)\s*(\d+(?:\.\d+)?)\s*(?:l(?:akh)?|lpa|lac)",
        "INR", "yearly", 100_000,
    ),
    (
        r"(\d+(?:\.\d+)?)\s*(?:[-–to]+)\s*(\d+(?:\.\d+)?)\s*(?:l(?:akh)?|lpa|lac)",
        "INR", "yearly", 100_000,
    ),
    # USD patterns: "$50k-$80k", "$50,000-$80,000"
    (
        r"\$\s*(\d+(?:\.\d+)?)\s*k?\s*(?:[-–to]+)\s*\$?\s*(\d+(?:\.\d+)?)\s*k?",
        "USD", "yearly", None,
    ),
    # Per month: "₹50,000 per month", "Rs 50000/month"
    (
        r"(?:₹|inr|rs\.?)\s*(\d[\d,]*)\s*(?:[-–to]+)?\s*(?:(\d[\d,]*)\s*)?(?:per\s*month|/month|p\.?m\.?)",
        "INR", "monthly", 1,
    ),
    # Generic: "5 to 10 LPA"
    (
        r"(\d+(?:\.\d+)?)\s*to\s*(\d+(?:\.\d+)?)\s*(?:l(?:akh)?|lpa|lac)\s*(?:per\s*annum|p\.?a\.?)?",
        "INR", "yearly", 100_000,
    ),
]


# Experience-level salary benchmarks (INR yearly, Indian market)
_EXPERIENCE_SALARY_MAP = {
    "entry": (300_000, 700_000),
    "mid": (700_000, 1_500_000),
    "senior": (1_500_000, 3_000_000),
    "lead": (2_500_000, 5_000_000),
    "executive": (4_000_000, 10_000_000),
}


class SalaryExtractionAgent:
    """
    Salary Extraction and Estimation Agent.

    Pipeline:
    1. Rule-based regex extraction from raw salary string and description
    2. If no salary found, LLM extraction from description (optional)
    3. If still no salary, estimate from experience level
    """

    def __init__(self, use_llm: bool = False) -> None:
        self.use_llm = use_llm

    def extract_from_raw(self, salary_raw: str | None) -> SalaryEstimate | None:
        """Extract salary from a raw salary string (e.g., '₹5L-10L PA')."""
        if not salary_raw:
            return None

        text = salary_raw.lower().replace(",", "")
        return self._apply_patterns(text, source="explicit")

    def extract_from_description(self, description: str | None) -> SalaryEstimate | None:
        """
        Extract salary from the job description using regex patterns.
        Less reliable than raw salary field but useful as fallback.
        """
        if not description:
            return None

        text = description.lower().replace(",", "")

        # Look for salary-adjacent keywords to reduce false positives
        salary_sections = re.findall(
            r".{0,100}(?:salary|compensation|ctc|pay|package|stipend|remuneration).{0,200}",
            text,
            re.IGNORECASE,
        )
        search_text = " ".join(salary_sections) if salary_sections else text[:500]

        result = self._apply_patterns(search_text, source="description_extracted")
        if result:
            result.confidence *= 0.7  # Lower confidence from description
            result.is_estimated = False
        return result

    def estimate_from_experience(
        self,
        experience_level: str,
        job_type: str = "full_time",
    ) -> SalaryEstimate:
        """
        Estimate salary based on experience level when no explicit data is found.
        Returns an estimated salary range.
        """
        level_key = experience_level.lower() if experience_level else "mid"
        min_sal, max_sal = _EXPERIENCE_SALARY_MAP.get(level_key, (500_000, 1_200_000))

        # Adjust for part-time/contract
        if job_type in ("part_time", "freelance"):
            min_sal = int(min_sal * 0.5)
            max_sal = int(max_sal * 0.5)

        return SalaryEstimate(
            min_value=float(min_sal),
            max_value=float(max_sal),
            currency="INR",
            period="yearly",
            is_estimated=True,
            confidence=0.3,  # Low confidence for estimated values
            source="experience_estimation",
        )

    async def extract(
        self,
        salary_raw: str | None,
        description: str | None,
        experience_level: str | None = None,
        job_type: str = "full_time",
    ) -> SalaryEstimate:
        """
        Full extraction pipeline with fallback chain.
        """
        # 1. Try raw salary field
        result = self.extract_from_raw(salary_raw)
        if result:
            return result

        # 2. Try description extraction
        result = self.extract_from_description(description)
        if result:
            return result

        # 3. LLM extraction (if enabled and description is available)
        if self.use_llm and description and len(description) > 50:
            result = await self._extract_with_llm(description)
            if result:
                return result

        # 4. Estimate from experience level
        if experience_level:
            return self.estimate_from_experience(experience_level, job_type)

        # 5. No salary info at all
        return SalaryEstimate(
            min_value=None,
            max_value=None,
            currency="INR",
            period="yearly",
            is_estimated=True,
            confidence=0.0,
            source="unknown",
        )

    def _apply_patterns(
        self, text: str, source: str
    ) -> SalaryEstimate | None:
        """Apply regex patterns to extract salary range from text."""
        for pattern, currency, period, multiplier in _SALARY_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    groups = [g for g in match.groups() if g is not None]
                    val1 = float(groups[0]) * (multiplier or 1)
                    val2 = float(groups[1]) * (multiplier or 1) if len(groups) > 1 else val1

                    # Handle USD 'k' shorthand
                    if currency == "USD":
                        if val1 < 500:
                            val1 *= 1000
                        if val2 < 500:
                            val2 *= 1000

                    min_val = min(val1, val2)
                    max_val = max(val1, val2)

                    # Sanity check
                    if min_val <= 0 or max_val > 1_000_000_000:
                        continue

                    return SalaryEstimate(
                        min_value=min_val,
                        max_value=max_val,
                        currency=currency,
                        period=period,
                        is_estimated=False,
                        confidence=0.85,
                        source=source,
                    )
                except (ValueError, IndexError):
                    continue
        return None

    async def _extract_with_llm(self, description: str) -> SalaryEstimate | None:
        """Use LLM to extract salary information from job description."""
        try:
            from shared.llm.router import get_llm_router

            router = get_llm_router()
            prompt = f"""Extract salary information from this job description. 
Return ONLY a JSON object with keys: min_value (number), max_value (number), currency (INR/USD), period (yearly/monthly).
If no salary is mentioned, return null.

Job description:
{description[:800]}

JSON response:"""

            response = await router.invoke(
                prompt=prompt,
                task_type="salary_estimation",
                max_tokens=200,
            )

            import json
            content = response.get("content", "")
            # Extract JSON from response
            json_match = re.search(r"\{[^}]+\}", content)
            if json_match:
                data = json.loads(json_match.group())
                if data and data.get("min_value"):
                    return SalaryEstimate(
                        min_value=float(data.get("min_value", 0)),
                        max_value=float(data.get("max_value") or data.get("min_value", 0)),
                        currency=data.get("currency", "INR"),
                        period=data.get("period", "yearly"),
                        is_estimated=False,
                        confidence=0.6,
                        source="llm_extracted",
                    )
        except Exception as e:
            logger.debug(f"LLM salary extraction failed: {e}")

        return None
