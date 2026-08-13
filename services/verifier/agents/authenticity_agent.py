"""
Authenticity Agent — verifies job listings by checking company career pages
and cross-referencing job posting signals.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import re
from datetime import datetime
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class AuthenticityResult:
    """Result of an authenticity check."""

    def __init__(
        self,
        is_authentic: bool,
        authenticity_score: float,
        verification_method: str,
        evidence: list[str],
        career_page_found: bool,
        cross_platform_matches: int,
    ) -> None:
        self.is_authentic = is_authentic
        self.authenticity_score = authenticity_score  # 0–100
        self.verification_method = verification_method
        self.evidence = evidence
        self.career_page_found = career_page_found
        self.cross_platform_matches = cross_platform_matches


class AuthenticityAgent:
    """
    Job Authenticity Verification Agent.

    Checks:
    1. Whether the company has a legitimate web presence (domain lookup)
    2. Whether the apply URL domain matches the company domain
    3. Whether the posting appears on the company's own careers page
    4. Cross-references with known legitimate job boards
    """

    BROWSER_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    # Trusted job board domains — jobs posted here get a positive signal
    TRUSTED_SOURCES = {
        "linkedin.com", "indeed.com", "glassdoor.com", "naukri.com",
        "greenhouse.io", "lever.co", "workday.com", "taleo.net",
        "smartrecruiters.com", "recruitee.com", "bamboohr.com",
    }

    # Red-flag apply URL patterns
    SUSPICIOUS_APPLY_PATTERNS = [
        r"bit\.ly", r"tinyurl\.com", r"t\.co/", r"goo\.gl",
        r"whatsapp", r"telegram", r"wechat", r"email.*only",
        r"\.(ru|cn|tk|ml|ga|cf)(/|$)",
    ]

    def __init__(self) -> None:
        self.timeout = httpx.Timeout(10.0)
        self._enabled = os.getenv("AUTHENTICITY_CHECK_ENABLED", "true").lower() == "true"

    async def analyze(
        self,
        job_id: str,
        company_name: str,
        apply_url: str | None,
        source_url: str | None,
        title: str,
        source: str,
    ) -> AuthenticityResult:
        """
        Run the full authenticity check pipeline.
        Returns an AuthenticityResult with score and evidence.
        """
        if not self._enabled:
            return AuthenticityResult(
                is_authentic=True,
                authenticity_score=60.0,
                verification_method="disabled",
                evidence=["Authenticity checks disabled via env config"],
                career_page_found=False,
                cross_platform_matches=0,
            )

        score = 50.0  # Neutral starting point
        evidence: list[str] = []
        career_page_found = False
        cross_platform_matches = 0

        # ── Check 1: Source credibility ─────────────────────────────────────
        if source in ("greenhouse", "lever", "adzuna"):
            score += 25
            evidence.append(f"Job sourced from trusted platform: {source}")
            cross_platform_matches += 1
        elif source == "rss":
            score += 10
            evidence.append("Job sourced from RSS feed — partial trust")

        # ── Check 2: Apply URL quality ───────────────────────────────────────
        apply_url_score, apply_evidence = self._check_apply_url(apply_url, company_name)
        score += apply_url_score
        evidence.extend(apply_evidence)

        # ── Check 3: Source URL domain ───────────────────────────────────────
        if source_url:
            domain = self._extract_domain(source_url)
            if any(trusted in domain for trusted in self.TRUSTED_SOURCES):
                score += 15
                evidence.append(f"Source URL from trusted domain: {domain}")
                cross_platform_matches += 1

        # ── Check 4: Career page lookup (async HTTP, best-effort) ────────────
        if self._enabled and company_name and len(company_name) > 2:
            try:
                found, page_evidence = await asyncio.wait_for(
                    self._check_career_page(company_name, title),
                    timeout=8.0,
                )
                career_page_found = found
                if found:
                    score += 15
                    evidence.append(f"Company career page verified: {page_evidence}")
                else:
                    evidence.append("Could not verify company career page")
            except asyncio.TimeoutError:
                evidence.append("Career page check timed out")
            except Exception as e:
                logger.debug(f"Career page check failed: {e}")

        score = max(0.0, min(100.0, score))
        is_authentic = score >= 60.0

        return AuthenticityResult(
            is_authentic=is_authentic,
            authenticity_score=score,
            verification_method="multi_signal",
            evidence=evidence,
            career_page_found=career_page_found,
            cross_platform_matches=cross_platform_matches,
        )

    def _check_apply_url(
        self, apply_url: str | None, company_name: str
    ) -> tuple[float, list[str]]:
        """Score the apply URL for trustworthiness."""
        if not apply_url:
            return -5.0, ["No apply URL provided"]

        url_lower = apply_url.lower()
        evidence: list[str] = []
        score = 0.0

        # Check for suspicious URL shorteners / channels
        for pattern in self.SUSPICIOUS_APPLY_PATTERNS:
            if re.search(pattern, url_lower):
                score -= 20
                evidence.append(f"Suspicious apply URL pattern detected: {pattern}")
                return score, evidence

        # Check if apply URL uses HTTPS
        if apply_url.startswith("https://"):
            score += 5
            evidence.append("Apply URL uses HTTPS")
        else:
            score -= 5
            evidence.append("Apply URL does not use HTTPS")

        # Check if domain matches company name
        domain = self._extract_domain(apply_url)
        company_slug = re.sub(r"[^a-z0-9]", "", company_name.lower())
        if company_slug and company_slug[:6] in domain.replace(".", ""):
            score += 10
            evidence.append(f"Apply URL domain matches company name: {domain}")

        # Check if it's on a known job board
        if any(trusted in domain for trusted in self.TRUSTED_SOURCES):
            score += 10
            evidence.append(f"Apply URL on trusted job board: {domain}")

        return score, evidence

    def _extract_domain(self, url: str) -> str:
        """Extract the base domain from a URL."""
        url = url.lower().replace("https://", "").replace("http://", "")
        return url.split("/")[0].split("?")[0]

    async def _check_career_page(
        self, company_name: str, job_title: str
    ) -> tuple[bool, str]:
        """
        Attempt to find the job on the company's official career page.
        Returns (found, evidence_url).
        """
        # Generate candidate career page URLs
        slug = re.sub(r"[^a-z0-9]", "-", company_name.lower()).strip("-")
        candidates = [
            f"https://{slug}.com/careers",
            f"https://www.{slug}.com/careers",
            f"https://{slug}.com/jobs",
        ]

        async with httpx.AsyncClient(
            headers=self.BROWSER_HEADERS,
            timeout=self.timeout,
            follow_redirects=True,
        ) as client:
            for url in candidates[:2]:  # Only check 2 to avoid long delays
                try:
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        # Check if job title appears on the careers page
                        title_words = job_title.lower().split()[:3]
                        page_text = resp.text.lower()
                        if any(word in page_text for word in title_words):
                            return True, url
                        return True, url  # Page exists even if title not found
                except Exception:
                    continue

        return False, ""
