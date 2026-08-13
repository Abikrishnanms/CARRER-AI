"""
Company Trust Agent — scores companies based on web presence, employee data,
review signals, and scam report history.
"""

from __future__ import annotations

import logging
import os
import re
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


class CompanyTrustResult:
    """Result of a company trust analysis."""

    def __init__(
        self,
        trust_score: float,
        risk_factors: list[str],
        positive_signals: list[str],
        is_blacklisted: bool,
    ) -> None:
        self.trust_score = trust_score  # 0–100
        self.risk_factors = risk_factors
        self.positive_signals = positive_signals
        self.is_blacklisted = is_blacklisted


class CompanyTrustAgent:
    """
    Company Trust Scoring Agent.

    Assigns a trust score (0–100) to a company based on:
    - Known blacklist (obvious scam companies)
    - Domain age and quality signals
    - Company size and founding year plausibility
    - Presence of red-flag phrases in company name/description
    - Historical scam report rate from our platform data
    """

    # Known scam/MLM company patterns
    BLACKLISTED_PATTERNS = [
        r"\bmlm\b", r"multi.?level", r"network marketing",
        r"binary.*plan", r"downline", r"upline",
        r"earn.*lakh.*month", r"work.*home.*earn.*easy",
        r"earn.*daily.*guarantee", r"100%.*profit",
        r"no experience.*high salary", r"data entry.*earn",
    ]

    # Suspicious company name patterns
    SUSPICIOUS_NAME_PATTERNS = [
        r"^\d+", r"company\s*\d+", r"[^\w\s\-&.,]",
        r"pvt.*pvt", r"ltd.*ltd",
    ]

    # Legitimate company signals
    TRUST_SIGNAL_PATTERNS = {
        "has_website": 10,
        "https_website": 5,
        "linkedin_present": 15,
        "glassdoor_present": 10,
        "large_company": 10,  # >200 employees
        "established_company": 10,  # Founded > 5 years ago
        "known_industry": 5,
    }

    # Known trusted companies (seed list)
    VERIFIED_COMPANIES = {
        "google", "microsoft", "amazon", "meta", "apple", "netflix",
        "flipkart", "infosys", "wipro", "tcs", "hcl", "accenture",
        "deloitte", "ibm", "oracle", "salesforce", "adobe", "atlassian",
        "byju", "swiggy", "zomato", "paytm", "ola", "phonepe",
        "stripe", "airbnb", "uber", "linkedin", "twitter", "github",
        "gitlab", "hashicorp", "datadog", "confluent", "databricks",
    }

    def analyze(
        self,
        company_name: str,
        company_data: dict[str, Any] | None = None,
        scam_reports: int = 0,
    ) -> CompanyTrustResult:
        """
        Compute trust score for a company.

        Args:
            company_name: Raw company name from job posting
            company_data: Optional enriched company data from MongoDB
            scam_reports: Number of scam reports against this company

        Returns:
            CompanyTrustResult with trust_score and signals
        """
        score = 50.0  # Neutral baseline
        risk_factors: list[str] = []
        positive_signals: list[str] = []
        is_blacklisted = False

        name_lower = company_name.lower().strip()

        # ── Check 0: Instant blacklist ────────────────────────────────────────
        for pattern in self.BLACKLISTED_PATTERNS:
            if re.search(pattern, name_lower):
                is_blacklisted = True
                risk_factors.append(f"Blacklisted pattern: {pattern}")
                return CompanyTrustResult(
                    trust_score=0.0,
                    risk_factors=risk_factors,
                    positive_signals=[],
                    is_blacklisted=True,
                )

        # ── Check 1: Known verified company ──────────────────────────────────
        slug = re.sub(r"[^a-z0-9]", "", name_lower)
        if any(v in slug or slug in v for v in self.VERIFIED_COMPANIES):
            score += 30
            positive_signals.append(f"Company is on verified company list")

        # ── Check 2: Suspicious name patterns ────────────────────────────────
        for pattern in self.SUSPICIOUS_NAME_PATTERNS:
            if re.search(pattern, company_name):
                score -= 10
                risk_factors.append(f"Suspicious company name format")
                break

        # ── Check 3: Company name length (too short = suspicious) ─────────────
        if len(company_name.strip()) < 3:
            score -= 20
            risk_factors.append("Company name is unusually short")
        elif len(company_name.strip()) > 5:
            score += 5
            positive_signals.append("Company name appears legitimate")

        # ── Check 4: Scam report history ──────────────────────────────────────
        if scam_reports > 10:
            score -= 40
            risk_factors.append(f"High scam report count: {scam_reports}")
            if scam_reports > 25:
                is_blacklisted = True
        elif scam_reports > 3:
            score -= 15
            risk_factors.append(f"Multiple scam reports: {scam_reports}")
        elif scam_reports == 0:
            score += 5
            positive_signals.append("No scam reports on record")

        # ── Check 5: Enriched company data ────────────────────────────────────
        if company_data:
            if company_data.get("website"):
                score += 10
                positive_signals.append("Company has a website")
                if str(company_data.get("website", "")).startswith("https://"):
                    score += 5
                    positive_signals.append("Company website uses HTTPS")

            if company_data.get("linkedin_url"):
                score += 15
                positive_signals.append("Company has a LinkedIn profile")

            if company_data.get("glassdoor_url"):
                score += 10
                positive_signals.append("Company has a Glassdoor listing")

            employee_count = company_data.get("employee_count", 0)
            if employee_count and employee_count > 200:
                score += 10
                positive_signals.append(f"Large company: {employee_count} employees")

            founded_year = company_data.get("founded_year")
            if founded_year:
                age = datetime.utcnow().year - founded_year
                if age >= 5:
                    score += 10
                    positive_signals.append(f"Established company (founded {founded_year})")
                elif age < 0:
                    score -= 10
                    risk_factors.append("Invalid founding year")

            avg_rating = company_data.get("avg_rating")
            if avg_rating:
                if avg_rating >= 3.5:
                    score += 8
                    positive_signals.append(f"Good employee rating: {avg_rating}/5")
                elif avg_rating < 2.0:
                    score -= 10
                    risk_factors.append(f"Poor employee rating: {avg_rating}/5")

        score = max(0.0, min(100.0, score))

        return CompanyTrustResult(
            trust_score=score,
            risk_factors=risk_factors,
            positive_signals=positive_signals,
            is_blacklisted=is_blacklisted,
        )

    def bulk_analyze(
        self,
        companies: list[dict[str, Any]],
    ) -> dict[str, CompanyTrustResult]:
        """Analyze trust for multiple companies at once."""
        results: dict[str, CompanyTrustResult] = {}
        for company in companies:
            name = company.get("name", "")
            if name:
                results[name] = self.analyze(
                    company_name=name,
                    company_data=company,
                    scam_reports=company.get("scam_reports", 0),
                )
        return results
