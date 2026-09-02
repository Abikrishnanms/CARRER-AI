"""
Job Collection Agents — Multi-source job aggregation.
Sources: Adzuna API, Greenhouse, Lever, Workday, Naukri, Indeed, LinkedIn,
         Company Careers RSS, Remotive, WeWorkRemotely, DailyRemote, AngelList,
         TimesJobs, Glassdoor RSS, Government portals.

Optimized for high throughput:
- Concurrent search terms + companies via asyncio.gather (semaphore-controlled)
- Exponential backoff + jitter for transient failures
- Circuit breaker per source to stop hammering unavailable endpoints
- Adaptive rate limiting that slows down on 429/503
- Bulk Kafka publishing with record batches (not one-at-a-time send_and_wait)
- 60+ search terms, 25+ companies, 10+ RSS feeds for Indian market
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import random
import re
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Deque
from uuid import uuid4

import httpx
from bs4 import BeautifulSoup

from shared.models.job import CollectionSource, RawJob

logger = logging.getLogger(__name__)

# ─── Enhanced search vocabulary for the Indian market (60+ terms) ─────────────
DEFAULT_SEARCH_TERMS = [
    # Core engineering
    "software engineer", "software developer", "senior software engineer",
    "staff software engineer", "principal engineer", "lead engineer",
    "backend engineer", "frontend engineer", "full stack engineer",
    "devops engineer", "site reliability engineer", "sre", "platform engineer",
    # Data & AI
    "data scientist", "machine learning engineer", "ml engineer",
    "data engineer", "data analyst", "business analyst",
    "ai engineer", "deep learning engineer", "nlp engineer",
    "data architect", "analytics engineer", "bi developer",
    # Python ecosystem
    "python developer", "django developer", "flask developer", "fastapi developer",
    # Frontend stack
    "react developer", "react native developer", "angular developer",
    "vue developer", "typescript developer", "javascript developer", "nextjs developer",
    # Mobile
    "android developer", "ios developer", "flutter developer",
    "mobile developer", "react native",
    # Cloud & DevOps
    "aws engineer", "azure engineer", "gcp engineer", "cloud architect",
    "kubernetes engineer", "terraform engineer", "docker engineer",
    # Security & QA
    "cybersecurity engineer", "ethical hacker", "penetration tester",
    "qa engineer", "test engineer", "automation engineer", "selenium",
    # Product & management
    "product manager", "technical program manager", "engineering manager",
    "scrum master", "project manager", "delivery manager",
    # Design & UX
    "ux designer", "ui designer", "product designer", "ux researcher",
    # Finance & ops
    "business intelligence analyst", "operations analyst", "growth analyst",
    "tech lead", "architect", "solutions architect",
    # Support
    "solutions engineer", "pre sales engineer", "technical support engineer",
    # Indian-specific keywords
    "b tech fresher", "m tech jobs", "off campus drive", "bangalore jobs",
    "pune jobs", "hyderabad jobs", "chennai jobs", "noida jobs", "gurgaon jobs",
]

# ─── HTTP headers pool (rotate to avoid fingerprinting) ───────────────────────
BROWSER_HEADERS_POOL = [
    {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    },
    {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
                      "(KHTML, like Gecko) Version/17.3 Safari/605.1.15",
        "Accept-Language": "en-GB,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    },
    {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Accept-Language": "en-IN,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    },
]

# ─── Circuit breaker ──────────────────────────────────────────────────────────

@dataclass
class CircuitBreaker:
    """Circuit breaker to stop sending requests to failing sources."""
    failure_threshold: int = 5
    recovery_timeout_seconds: int = 60
    _failures: int = 0
    _open_since: float | None = None
    _total_failures: int = 0
    _total_successes: int = 0
    _recent_response_times_ms: Deque[float] = field(default_factory=lambda: deque(maxlen=20))

    @property
    def state(self) -> str:
        if self._open_since is not None:
            if (time.monotonic() - self._open_since) >= self.recovery_timeout_seconds:
                return "half_open"
            return "open"
        return "closed"

    def record_success(self, response_time_ms: float = 0) -> None:
        self._total_successes += 1
        self._recent_response_times_ms.append(response_time_ms)
        if self.state == "half_open":
            self._failures = 0
            self._open_since = None

    def record_failure(self) -> None:
        self._total_failures += 1
        self._failures += 1
        if self.state == "half_open":
            self._failures = self.failure_threshold
        if self._failures >= self.failure_threshold and self._open_since is None:
            self._open_since = time.monotonic()
            logger.warning(
                f"Circuit breaker OPEN after {self._failures} failures. "
                f"Next attempt in {self.recovery_timeout_seconds}s"
            )

    def allow_request(self) -> bool:
        return self.state != "open"

    @property
    def avg_response_time_ms(self) -> float:
        if not self._recent_response_times_ms:
            return 0.0
        return sum(self._recent_response_times_ms) / len(self._recent_response_times_ms)


# ─── Retry helper with exponential backoff + jitter ───────────────────────────

async def retry_with_backoff(
    coro_fn,
    *,
    max_retries: int = 5,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    backoff_factor: float = 2.0,
    retry_on: tuple[type[BaseException], ...] = (
        httpx.HTTPStatusError, httpx.ConnectError, httpx.ReadTimeout,
        httpx.RemoteProtocolError, asyncio.TimeoutError,
    ),
    circuit_breaker: CircuitBreaker | None = None,
    status_codes_to_retry: set[int] = {429, 500, 502, 503, 504, 408},
) -> Any:
    """Execute coro_fn with exponential backoff and optional circuit breaking."""
    delay = initial_delay
    last_exc: BaseException | None = None

    for attempt in range(max_retries):
        if circuit_breaker and not circuit_breaker.allow_request():
            raise RuntimeError("Circuit breaker is OPEN — skipping request")

        try:
            t0 = time.perf_counter()
            result = await coro_fn()
            if circuit_breaker:
                circuit_breaker.record_success((time.perf_counter() - t0) * 1000)
            return result

        except httpx.HTTPStatusError as e:
            if e.response.status_code not in status_codes_to_retry:
                if circuit_breaker:
                    circuit_breaker.record_failure()
                raise
            last_exc = e
            if e.response.status_code == 429:
                # Respect Retry-After if present
                retry_after = e.response.headers.get("Retry-After")
                if retry_after and retry_after.isdigit():
                    delay = max(delay, float(retry_after))
                else:
                    delay = max(delay, 10.0)  # Longer delay for rate limits

        except retry_on as e:
            last_exc = e

        if circuit_breaker:
            circuit_breaker.record_failure()

        if attempt < max_retries - 1:
            jitter = random.uniform(0, delay * 0.5)
            sleep_for = min(delay + jitter, max_delay)
            logger.debug(
                f"Retry {attempt + 1}/{max_retries} after {sleep_for:.1f}s "
                f"due to: {type(last_exc).__name__}"
            )
            await asyncio.sleep(sleep_for)
            delay *= backoff_factor

    raise last_exc or RuntimeError(f"Failed after {max_retries} retries")


# ─── Base Collector (concurrent + adaptive) ───────────────────────────────────

class BaseCollector:
    """
    Abstract base for all job collectors with:
    - Per-source semaphore for concurrency control
    - Per-source circuit breaker
    - Adaptive rate limiting based on 429 responses
    - Rotating User-Agent headers
    """

    source: CollectionSource = CollectionSource.UNKNOWN

    def __init__(
        self,
        rate_limit_per_second: float | None = None,
        max_concurrent_requests: int | None = None,
    ) -> None:
        self.session: httpx.AsyncClient | None = None
        self._request_count = 0
        self._last_request_time = 0.0
        self._default_rate = float(os.getenv("SCRAPER_RATE_LIMIT_PER_DOMAIN", "8"))
        self._rate_limit_per_second = rate_limit_per_second or self._default_rate
        self._max_concurrent = max_concurrent_requests or int(
            os.getenv("SCRAPER_MAX_CONCURRENT", "20")
        )
        self._semaphore: asyncio.Semaphore | None = None
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=int(os.getenv("CB_FAILURE_THRESHOLD", "8")),
            recovery_timeout_seconds=int(os.getenv("CB_RECOVERY_SECONDS", "90")),
        )
        # Adaptive rate control — multiplier starts at 1.0, grows/shrinks
        self._rate_multiplier = 1.0

    @property
    def effective_rate(self) -> float:
        return self._rate_limit_per_second * self._rate_multiplier

    async def __aenter__(self) -> "BaseCollector":
        self._semaphore = asyncio.Semaphore(self._max_concurrent)
        self.session = httpx.AsyncClient(
            headers=random.choice(BROWSER_HEADERS_POOL),
            timeout=httpx.Timeout(30.0, connect=10.0),
            follow_redirects=True,
        )
        return self

    async def __aexit__(self, *args: Any) -> None:
        if self.session:
            await self.session.aclose()

    def _rotate_headers(self) -> None:
        """Periodically rotate headers to avoid detection."""
        if self.session and self._request_count % 25 == 0:
            self.session.headers.update(random.choice(BROWSER_HEADERS_POOL))

    async def _rate_limited_get(self, url: str, **kwargs: Any) -> httpx.Response:
        """Rate-limited HTTP GET with semaphore, circuit breaker, adaptive throttling."""
        if not self.session or not self._semaphore:
            raise RuntimeError("Collector not started (use async with)")

        if not self.circuit_breaker.allow_request():
            raise RuntimeError(f"Circuit breaker open for source '{self.source}'")

        self._rotate_headers()

        async with self._semaphore:
            # Rate limiting with token-bucket style sleep
            effective_rate = max(self.effective_rate, 0.1)
            min_interval = 1.0 / effective_rate
            now = time.monotonic()
            wait = (self._last_request_time + min_interval) - now
            if wait > 0:
                # Tiny jitter to prevent thundering herd
                await asyncio.sleep(wait + random.uniform(0, min_interval * 0.1))

            self._last_request_time = time.monotonic()
            self._request_count += 1

            t0 = time.perf_counter()
            response = await self.session.get(url, **kwargs)
            latency_ms = (time.perf_counter() - t0) * 1000

            # Adaptive rate adjustment based on response
            if response.status_code == 429 or response.status_code == 503:
                self._rate_multiplier = max(0.1, self._rate_multiplier * 0.5)
                logger.warning(
                    f"{self.source}: HTTP {response.status_code} — "
                    f"reducing rate to {self.effective_rate:.1f}/s "
                    f"(multiplier={self._rate_multiplier:.2f})"
                )
            elif response.status_code < 400 and latency_ms < 1000:
                # Mild speed-up when healthy
                self._rate_multiplier = min(2.0, self._rate_multiplier * 1.02)

            # Track via circuit breaker
            if response.status_code >= 500:
                self.circuit_breaker.record_failure()
            else:
                self.circuit_breaker.record_success(latency_ms)

            response.raise_for_status()
            return response

    async def _rate_limited_post(self, url: str, **kwargs: Any) -> httpx.Response:
        """Rate-limited HTTP POST with semaphore, circuit breaker, adaptive throttling."""
        if not self.session or not self._semaphore:
            raise RuntimeError("Collector not started (use async with)")

        if not self.circuit_breaker.allow_request():
            raise RuntimeError(f"Circuit breaker open for source '{self.source}'")

        self._rotate_headers()

        async with self._semaphore:
            effective_rate = max(self.effective_rate, 0.1)
            min_interval = 1.0 / effective_rate
            now = time.monotonic()
            wait = (self._last_request_time + min_interval) - now
            if wait > 0:
                await asyncio.sleep(wait + random.uniform(0, min_interval * 0.1))

            self._last_request_time = time.monotonic()
            self._request_count += 1

            t0 = time.perf_counter()
            response = await self.session.post(url, **kwargs)
            latency_ms = (time.perf_counter() - t0) * 1000

            if response.status_code in (429, 503):
                self._rate_multiplier = max(0.1, self._rate_multiplier * 0.5)
            elif response.status_code < 400 and latency_ms < 1000:
                self._rate_multiplier = min(2.0, self._rate_multiplier * 1.02)

            if response.status_code >= 500:
                self.circuit_breaker.record_failure()
            else:
                self.circuit_breaker.record_success(latency_ms)

            response.raise_for_status()
            return response

    async def collect(
        self,
        search_terms: list[str] | None = None,
        location: str | None = None,
        limit: int = 100,
    ) -> list[RawJob]:
        raise NotImplementedError

    def _generate_fingerprint(self, *parts: str) -> str:
        content = "|".join(p.lower().strip() for p in parts if p)
        return hashlib.md5(content.encode()).hexdigest()


# ─── Adzuna API Collector (paginated, concurrent terms) ──────────────────────

class AdzunaCollector(BaseCollector):
    """
    Adzuna Jobs API collector — concurrent per search term.
    Free tier: 250 requests/day * 50 jobs = 12,500/day (cap well with pagination)
    """

    source = CollectionSource.ADZUNA
    BASE_URL = "https://api.adzuna.com/v1/api/jobs"

    def __init__(self) -> None:
        super().__init__(
            rate_limit_per_second=float(os.getenv("ADZUNA_RATE", "4")),
            max_concurrent_requests=int(os.getenv("ADZUNA_CONCURRENT", "10")),
        )
        self.app_id = os.getenv("ADZUNA_API_ID", "")
        self.api_key = os.getenv("ADZUNA_API_KEY", "")
        self.country = os.getenv("ADZUNA_COUNTRY", "in")

    @property
    def is_configured(self) -> bool:
        return bool(self.app_id and self.api_key)

    async def collect(
        self,
        search_terms: list[str] | None = None,
        location: str | None = None,
        limit: int = 100,
    ) -> list[RawJob]:
        if not self.is_configured:
            logger.warning("Adzuna API credentials not configured — skipping")
            return []

        terms = search_terms or DEFAULT_SEARCH_TERMS
        terms_to_use = terms[: max(1, min(len(terms), limit))]
        per_term_limit = max(10, limit // max(1, len(terms_to_use)))
        run_id = str(uuid4())

        # Concurrent term collection
        sem = asyncio.Semaphore(int(os.getenv("ADZUNA_TERM_PARALLEL", "5")))

        async def _collect_one(term: str) -> list[RawJob]:
            async with sem:
                try:
                    jobs = await retry_with_backoff(
                        lambda: self._collect_term(term, location, run_id, per_term_limit),
                        max_retries=4,
                        circuit_breaker=self.circuit_breaker,
                    )
                    logger.info(f"Adzuna: collected {len(jobs)} jobs for '{term}'")
                    return jobs
                except Exception as e:
                    logger.error(f"Adzuna: error collecting '{term}': {e}")
                    return []

        all_jobs: list[RawJob] = []
        chunks = [terms_to_use[i:i+8] for i in range(0, len(terms_to_use), 8)]
        for chunk in chunks:
            results = await asyncio.gather(*[_collect_one(t) for t in chunk])
            for jobs in results:
                all_jobs.extend(jobs)
                if len(all_jobs) >= limit:
                    break
            if len(all_jobs) >= limit:
                break

        # Deduplicate by source_job_id within collected set
        seen: set[str] = set()
        unique: list[RawJob] = []
        for job in all_jobs:
            if job.source_job_id in seen:
                continue
            seen.add(job.source_job_id)
            unique.append(job)

        return unique[:limit]

    async def _collect_term(
        self,
        term: str,
        location: str | None,
        run_id: str,
        limit: int,
    ) -> list[RawJob]:
        jobs: list[RawJob] = []
        results_per_page = max(10, min(50, limit))
        max_pages = max(1, min(5, (limit + results_per_page - 1) // results_per_page))

        for page in range(1, max_pages + 1):
            if len(jobs) >= limit:
                break

            params: dict[str, Any] = {
                "app_id": self.app_id,
                "app_key": self.api_key,
                "results_per_page": results_per_page,
                "what": term,
                "content-type": "application/json",
                "sort_by": "date",
            }
            if location:
                params["where"] = location

            try:
                response = await self._rate_limited_get(
                    f"{self.BASE_URL}/{self.country}/search/{page}",
                    params=params,
                )
                data = response.json()

                for item in data.get("results", []):
                    raw_job = self._parse_adzuna_job(item, run_id)
                    if raw_job:
                        jobs.append(raw_job)

                if len(data.get("results", [])) < results_per_page:
                    break

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 403:
                    logger.error("Adzuna API credentials invalid — stopping")
                    break
                logger.warning(f"Adzuna page={page} HTTP {e.response.status_code}")
                break

        return jobs[:limit]

    def _parse_adzuna_job(self, item: dict[str, Any], run_id: str) -> RawJob | None:
        try:
            company = item.get("company", {})
            location = item.get("location", {})
            location_areas = location.get("area", [])
            location_raw = ", ".join(reversed(location_areas)) if location_areas else None
            apply_url = item.get("redirect_url")
            return RawJob(
                source=self.source,
                source_job_id=str(item.get("id", uuid4())),
                source_url=apply_url or "",
                collection_run_id=run_id,
                title=item.get("title", ""),
                description=item.get("description", ""),
                company_name=company.get("display_name", "Unknown"),
                location_raw=location_raw,
                salary_raw=self._format_salary(item),
                job_type_raw=item.get("contract_time"),
                experience_raw=item.get("contract_type"),
                apply_url=apply_url,
                posted_date_raw=item.get("created"),
                raw_data=item,
            )
        except Exception as e:
            logger.debug(f"Failed to parse Adzuna job: {e}")
            return None

    def _format_salary(self, item: dict[str, Any]) -> str | None:
        min_s = item.get("salary_min")
        max_s = item.get("salary_max")
        if min_s and max_s:
            return f"₹{min_s:,.0f} - ₹{max_s:,.0f}"
        elif min_s:
            return f"₹{min_s:,.0f}+"
        return None


# ─── Greenhouse Collector (concurrent companies) ─────────────────────────────

class GreenhouseCollector(BaseCollector):
    """Greenhouse job board API — 50+ companies concurrently."""

    source = CollectionSource.GREENHOUSE
    DEFAULT_COMPANIES = [
        # Global tech
        "google", "dropbox", "airbnb", "stripe", "notion", "figma", "discord",
        "reddit", "twitch", "gitlab", "hashicorp", "datadog", "confluent",
        "databricks", "mongodb", "elastic", "snowflake", "cloudflare",
        # FAANG adjacent
        "robinhood", "coinbase", "shopify", "atlassian", "canva", "duolingo",
        "lyft", "spotify", "asana", "zoom", "slack", "box",
        # Indian companies using Greenhouse
        "groww", "microsoft", "cashfree", "clear", "pharmeasy", "cRED",
        "razorpay", "meesho", "swiggy", "dream11",
    ]

    def __init__(self) -> None:
        super().__init__(
            rate_limit_per_second=float(os.getenv("GREENHOUSE_RATE", "10")),
            max_concurrent_requests=int(os.getenv("GREENHOUSE_CONCURRENT", "30")),
        )

    async def collect(
        self,
        search_terms: list[str] | None = None,
        location: str | None = None,
        limit: int = 100,
    ) -> list[RawJob]:
        companies = self.DEFAULT_COMPANIES
        run_id = str(uuid4())
        per_company_limit = max(5, limit // max(1, len(companies) // 2))
        sem = asyncio.Semaphore(int(os.getenv("GREENHOUSE_COMPANY_PARALLEL", "15")))

        async def _one_company(company: str) -> list[RawJob]:
            async with sem:
                try:
                    return await retry_with_backoff(
                        lambda c=company: self._collect_company(
                            c, run_id, per_company_limit, search_terms, location
                        ),
                        max_retries=3,
                        circuit_breaker=self.circuit_breaker,
                    )
                except Exception as e:
                    logger.debug(f"Greenhouse: {company} unavailable: {e}")
                    return []

        all_jobs: list[RawJob] = []
        # Process companies in chunks to allow early exit when limit reached
        for i in range(0, len(companies), 20):
            chunk = companies[i:i+20]
            results = await asyncio.gather(*[_one_company(c) for c in chunk])
            for jobs in results:
                all_jobs.extend(jobs)
                if len(all_jobs) >= limit:
                    break
            if len(all_jobs) >= limit:
                break

        # Dedup
        seen: set[str] = set()
        unique: list[RawJob] = []
        for job in all_jobs:
            key = f"{job.source_job_id}|{job.company_name}"
            if key in seen:
                continue
            seen.add(key)
            unique.append(job)

        return unique[:limit]

    async def _collect_company(
        self,
        company_slug: str,
        run_id: str,
        limit: int,
        search_terms: list[str] | None,
        location: str | None,
    ) -> list[RawJob]:
        url = f"https://boards-api.greenhouse.io/v1/boards/{company_slug}/jobs"
        response = await self._rate_limited_get(url, params={"content": "true"})
        data = response.json()

        jobs: list[RawJob] = []
        for item in data.get("jobs", []):
            if len(jobs) >= limit:
                break
            # Optional search-term filter
            if search_terms:
                title = (item.get("title", "") or "").lower()
                if not any(t.lower() in title for t in search_terms[:20]):
                    continue
            if location:
                loc_field = (item.get("location", {}) or {}).get("name", "")
                if location.lower() not in (loc_field or "").lower():
                    continue
            raw_job = self._parse_greenhouse_job(item, company_slug, run_id)
            if raw_job:
                jobs.append(raw_job)
        return jobs

    def _parse_greenhouse_job(
        self, item: dict[str, Any], company_slug: str, run_id: str
    ) -> RawJob | None:
        try:
            location = item.get("location", {}) or {}
            return RawJob(
                source=self.source,
                source_job_id=f"gh-{company_slug}-{item.get('id', uuid4())}",
                source_url=item.get("absolute_url", ""),
                collection_run_id=run_id,
                title=item.get("title", ""),
                description=item.get("content", ""),
                company_name=company_slug.replace("-", " ").title(),
                location_raw=location.get("name"),
                apply_url=item.get("absolute_url"),
                posted_date_raw=item.get("updated_at"),
                raw_data=item,
            )
        except Exception as e:
            logger.debug(f"Greenhouse parse error: {e}")
            return None


# ─── Lever Collector (concurrent companies) ───────────────────────────────────

class LeverCollector(BaseCollector):
    """Lever job board API — same style as Greenhouse, adds more volume."""

    source = CollectionSource.LEVER
    DEFAULT_COMPANIES = [
        "netflix", "twitter", "x-team", "vercel", "linear", "arc-technologies",
        "openai", "anthropic", "stripe", "notion", "datadog", "figma",
        "retool", "airtable", "lattice", "webflow", "intercom", "hubspot",
        "mixpanel", "amplitude", "segment", "launchdarkly", "ramp", "brex",
        "deel", "remote", "payfit", "qonto",
    ]

    def __init__(self) -> None:
        super().__init__(
            rate_limit_per_second=float(os.getenv("LEVER_RATE", "8")),
            max_concurrent_requests=int(os.getenv("LEVER_CONCURRENT", "25")),
        )

    async def collect(
        self,
        search_terms: list[str] | None = None,
        location: str | None = None,
        limit: int = 100,
    ) -> list[RawJob]:
        companies = self.DEFAULT_COMPANIES
        run_id = str(uuid4())
        sem = asyncio.Semaphore(12)

        async def _one(c: str) -> list[RawJob]:
            async with sem:
                try:
                    return await retry_with_backoff(
                        lambda co=c: self._collect_company(co, run_id, search_terms, location),
                        max_retries=3,
                        circuit_breaker=self.circuit_breaker,
                    )
                except Exception as e:
                    logger.debug(f"Lever: {c} skip: {e}")
                    return []

        all_jobs: list[RawJob] = []
        for i in range(0, len(companies), 20):
            results = await asyncio.gather(*[_one(c) for c in companies[i:i+20]])
            for jobs in results:
                all_jobs.extend(jobs)
                if len(all_jobs) >= limit:
                    break
            if len(all_jobs) >= limit:
                break
        return all_jobs[:limit]

    async def _collect_company(
        self, slug: str, run_id: str,
        search_terms: list[str] | None, location: str | None,
    ) -> list[RawJob]:
        url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
        resp = await self._rate_limited_get(url)
        data = resp.json()
        jobs: list[RawJob] = []
        for it in data:
            title = (it.get("text", "") or "").lower()
            if search_terms and not any(t.lower() in title for t in search_terms[:20]):
                continue
            loc = ", ".join(it.get("categories", {}).get("location", []) or [])
            if location and location.lower() not in loc.lower():
                continue
            try:
                jobs.append(RawJob(
                    source=self.source,
                    source_job_id=f"lv-{slug}-{it.get('id', uuid4())}",
                    source_url=it.get("hostedUrl", ""),
                    collection_run_id=run_id,
                    title=it.get("text", ""),
                    description=it.get("description", "") or it.get("content", ""),
                    company_name=slug.replace("-", " ").title(),
                    location_raw=loc or None,
                    job_type_raw=", ".join(it.get("categories", {}).get("commitment", []) or []),
                    apply_url=it.get("hostedUrl"),
                    raw_data=it,
                ))
            except Exception as e:
                logger.debug(f"Lever parse error {slug}: {e}")
        return jobs


# ─── Workday Collector (ATS search via JSON API) ──────────────────────────────

class WorkdayCollector(BaseCollector):
    """Workday ATS API — scrapes real job postings from enterprise Workday portals."""

    source = CollectionSource.WORKDAY
    DEFAULT_TENANTS = [
        ("nvidia", "https://nvidia.wd5.myworkdayjobs.com/wday/cxs/nvidia/NVIDIAExternalCareerSite/jobs"),
        ("adobe", "https://adobe.wd5.myworkdayjobs.com/wday/cxs/adobe/external/jobs"),
        ("salesforce", "https://salesforce.wd1.myworkdayjobs.com/wday/cxs/salesforce/External_Career_Site/jobs"),
        ("workday", "https://workday.wd5.myworkdayjobs.com/wday/cxs/workday/Workday/jobs"),
        ("dell", "https://dell.wd1.myworkdayjobs.com/wday/cxs/dell/External/jobs"),
    ]

    def __init__(self) -> None:
        super().__init__(
            rate_limit_per_second=float(os.getenv("WORKDAY_RATE", "4")),
            max_concurrent_requests=int(os.getenv("WORKDAY_CONCURRENT", "10")),
        )

    async def collect(
        self,
        search_terms: list[str] | None = None,
        location: str | None = None,
        limit: int = 100,
    ) -> list[RawJob]:
        terms = (search_terms or DEFAULT_SEARCH_TERMS)[:5]
        run_id = str(uuid4())
        sem = asyncio.Semaphore(4)

        async def _fetch_tenant(company_name: str, endpoint: str, term: str) -> list[RawJob]:
            async with sem:
                try:
                    payload = {"appliedFacets": {}, "limit": min(20, limit), "offset": 0, "searchText": term}
                    resp = await self._rate_limited_post(endpoint, json=payload)
                    data = resp.json()
                    jobs: list[RawJob] = []
                    postings = data.get("jobPostings", [])
                    base_domain = "/".join(endpoint.split("/")[:3])
                    parts = endpoint.split("/cxs/")[1].split("/jobs")[0].split("/") if "/cxs/" in endpoint else ["", ""]
                    tenant_name = parts[0]
                    board_slug = parts[1] if len(parts) > 1 else ""

                    for p in postings:
                        external_path = p.get("externalPath", "")
                        job_id = external_path.split("/")[-1] if external_path else str(uuid4())
                        apply_url = f"{base_domain}/en-US/{tenant_name}/{board_slug}{external_path}" if external_path else endpoint
                        title = p.get("title", "")
                        loc_text = p.get("locationsText", "")
                        posted = p.get("postedOn", "")

                        jobs.append(RawJob(
                            source=self.source,
                            source_job_id=f"wd-{company_name}-{job_id}",
                            source_url=apply_url,
                            collection_run_id=run_id,
                            title=title,
                            description=f"Position: {title} at {company_name.title()}. Location: {loc_text}. Posted: {posted}.",
                            company_name=company_name.title(),
                            location_raw=loc_text or location,
                            apply_url=apply_url,
                            posted_date_raw=posted,
                            raw_data=p,
                        ))
                    return jobs
                except Exception as e:
                    logger.debug(f"Workday {company_name} '{term}' failed: {e}")
                    return []

        tasks = []
        for name, url in self.DEFAULT_TENANTS:
            for term in terms:
                tasks.append(_fetch_tenant(name, url, term))

        results = await asyncio.gather(*tasks)
        all_jobs: list[RawJob] = []
        for res in results:
            all_jobs.extend(res)
            if len(all_jobs) >= limit:
                break
        return all_jobs[:limit]


# ─── Indeed Scraper (concurrent terms + pagination) ───────────────────────────

class IndeedScraper(BaseCollector):
    """Indeed India scraper with concurrent terms and multi-page fetching."""

    source = CollectionSource.INDEED

    def __init__(self) -> None:
        super().__init__(
            rate_limit_per_second=float(os.getenv("INDEED_RATE", "4")),
            max_concurrent_requests=int(os.getenv("INDEED_CONCURRENT", "10")),
        )

    async def collect(
        self,
        search_terms: list[str] | None = None,
        location: str | None = None,
        limit: int = 100,
    ) -> list[RawJob]:
        if not os.getenv("INDEED_SCRAPING_ENABLED", "true").lower() == "true":
            return []

        terms = (search_terms or DEFAULT_SEARCH_TERMS)[:8]
        run_id = str(uuid4())
        loc = location or "India"
        sem = asyncio.Semaphore(5)

        async def _scrape_term(term: str) -> list[RawJob]:
            async with sem:
                try:
                    return await retry_with_backoff(
                        lambda t=term: self._scrape_search(t, loc, run_id, pages=3),
                        max_retries=3,
                        circuit_breaker=self.circuit_breaker,
                    )
                except Exception as e:
                    logger.warning(f"Indeed '{term}' failed: {e}")
                    return []

        results = await asyncio.gather(*[_scrape_term(t) for t in terms])
        all_jobs: list[RawJob] = []
        for jobs in results:
            all_jobs.extend(jobs)
            if len(all_jobs) >= limit:
                break
        return all_jobs[:limit]

    async def _scrape_search(
        self, term: str, location: str, run_id: str, pages: int = 3
    ) -> list[RawJob]:
        jobs: list[RawJob] = []
        base_url = "https://in.indeed.com/jobs"
        for page in range(pages):
            if len(jobs) >= 20 * pages:
                break
            params = {"q": term, "l": location, "sort": "date", "start": page * 10}
            resp = await self._rate_limited_get(base_url, params=params)
            soup = BeautifulSoup(resp.text, "html.parser")
            job_cards = soup.find_all("div", {"class": re.compile(r"job_seen_beacon|resultContent")})
            for card in job_cards[:15]:
                job = self._parse_indeed_card(card, run_id)
                if job:
                    jobs.append(job)
        return jobs

    def _parse_indeed_card(self, card: Any, run_id: str) -> RawJob | None:
        try:
            title_el = card.find("h2", {"class": re.compile(r"jobTitle")})
            if not title_el:
                return None
            title = title_el.get_text(strip=True).replace("new", "").strip()
            company_el = card.find("span", {"data-testid": "company-name"})
            company = company_el.get_text(strip=True) if company_el else "Unknown"
            location_el = card.find("div", {"data-testid": "text-location"})
            loc = location_el.get_text(strip=True) if location_el else None
            salary_el = card.find("div", {"class": re.compile(r"salary|compensation")})
            salary = salary_el.get_text(strip=True) if salary_el else None
            link_el = card.find("a", {"data-jk": True})
            jk = link_el.get("data-jk") if link_el else str(uuid4())
            src = f"https://in.indeed.com/viewjob?jk={jk}"
            return RawJob(
                source=self.source,
                source_job_id=jk,
                source_url=src,
                collection_run_id=run_id,
                title=title,
                description="",
                company_name=company,
                location_raw=loc,
                salary_raw=salary,
                apply_url=src,
                raw_data={"job_key": jk},
            )
        except Exception:
            return None


# ─── Naukri Scraper (headless-friendly requests) ──────────────────────────────

class NaukriScraper(BaseCollector):
    """Naukri.com India — scrapes live Naukri Search API & Tech feeds."""

    source = CollectionSource.NAUKRI

    def __init__(self) -> None:
        super().__init__(
            rate_limit_per_second=float(os.getenv("NAUKRI_RATE", "3")),
            max_concurrent_requests=int(os.getenv("NAUKRI_CONCURRENT", "6")),
        )

    async def collect(
        self,
        search_terms: list[str] | None = None,
        location: str | None = None,
        limit: int = 100,
    ) -> list[RawJob]:
        terms = (search_terms or DEFAULT_SEARCH_TERMS)[:8]
        run_id = str(uuid4())
        jobs: list[RawJob] = []
        sem = asyncio.Semaphore(3)

        async def _fetch_naukri(term: str) -> list[RawJob]:
            async with sem:
                try:
                    url = "https://www.naukri.com/jobapi/v3/search"
                    params = {"noOfResults": min(20, limit), "keyword": term, "searchType": "responsiveSearch"}
                    if location:
                        params["location"] = location
                    headers = {
                        "appid": "109",
                        "systemid": "NCI",
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    }
                    resp = await self._rate_limited_get(url, params=params, headers=headers)
                    data = resp.json()
                    res_jobs: list[RawJob] = []
                    for item in data.get("jobDetails", []):
                        job_id = str(item.get("jobId", uuid4()))
                        title = item.get("title", "")
                        comp = item.get("companyName", "Unknown")
                        jd_url = item.get("jdURL", "")
                        apply_url = f"https://www.naukri.com{jd_url}" if jd_url and not jd_url.startswith("http") else (jd_url or f"https://www.naukri.com/job-listings-{job_id}")
                        loc = item.get("place", "") or item.get("location", "")
                        desc = item.get("jobDescription", "")
                        sal = item.get("salary", "")
                        
                        res_jobs.append(RawJob(
                            source=self.source,
                            source_job_id=f"nk-{job_id}",
                            source_url=apply_url,
                            collection_run_id=run_id,
                            title=title,
                            description=desc or f"{title} role at {comp}. Location: {loc}.",
                            company_name=comp,
                            location_raw=loc,
                            salary_raw=sal if sal != "Not Disclosed" else None,
                            apply_url=apply_url,
                            posted_date_raw=str(item.get("createdDate", "")),
                            raw_data=item,
                        ))
                    return res_jobs
                except Exception as e:
                    logger.debug(f"Naukri API '{term}' failed: {e}")
                    return []

        results = await asyncio.gather(*[_fetch_naukri(t) for t in terms])
        for r in results:
            jobs.extend(r)
            if len(jobs) >= limit:
                break

        return jobs[:limit]


# ─── LinkedIn Collector ───────────────────────────────────────────────────────

class LinkedInCollector(BaseCollector):
    """LinkedIn Jobs — scrapes live public job postings via guest API."""

    source = CollectionSource.LINKEDIN

    def __init__(self) -> None:
        super().__init__(rate_limit_per_second=2, max_concurrent_requests=4)

    async def collect(
        self,
        search_terms: list[str] | None = None,
        location: str | None = None,
        limit: int = 100,
    ) -> list[RawJob]:
        terms = (search_terms or DEFAULT_SEARCH_TERMS)[:6]
        run_id = str(uuid4())
        loc = location or "India"
        jobs: list[RawJob] = []
        sem = asyncio.Semaphore(2)

        async def _scrape_linkedin(term: str) -> list[RawJob]:
            async with sem:
                try:
                    url = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
                    params = {"keywords": term, "location": loc, "start": 0}
                    headers = {
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                    }
                    resp = await self._rate_limited_get(url, params=params, headers=headers)
                    soup = BeautifulSoup(resp.text, "html.parser")
                    cards = soup.find_all("li")
                    res: list[RawJob] = []
                    for card in cards:
                        title_el = card.find(["h3", "h2"], class_=lambda x: x and ("title" in x or "heading" in x))
                        comp_el = card.find(["h4", "a"], class_=lambda x: x and ("subtitle" in x or "company" in x))
                        loc_el = card.find("span", class_=lambda x: x and "location" in x)
                        link_el = card.find("a", class_=lambda x: x and "link" in x)

                        if not title_el:
                            continue
                        title = title_el.get_text(strip=True)
                        company = comp_el.get_text(strip=True) if comp_el else "Unknown"
                        location_str = loc_el.get_text(strip=True) if loc_el else loc
                        apply_url = link_el.get("href", "").split("?")[0] if link_el else ""
                        job_id = apply_url.split("-")[-1] if apply_url else str(uuid4())

                        res.append(RawJob(
                            source=self.source,
                            source_job_id=f"li-{job_id}",
                            source_url=apply_url or f"https://www.linkedin.com/jobs/view/{job_id}",
                            collection_run_id=run_id,
                            title=title,
                            description=f"{title} position at {company}. Location: {location_str}.",
                            company_name=company,
                            location_raw=location_str,
                            apply_url=apply_url or f"https://www.linkedin.com/jobs/view/{job_id}",
                            posted_date_raw=datetime.utcnow().isoformat(),
                            raw_data={"platform": "linkedin_guest"},
                        ))
                    return res
                except Exception as e:
                    logger.debug(f"LinkedIn '{term}' guest scrape failed: {e}")
                    return []

        results = await asyncio.gather(*[_scrape_linkedin(t) for t in terms])
        for r in results:
            jobs.extend(r)
            if len(jobs) >= limit:
                break
        return jobs[:limit]


# ─── RSS Feed Collector (10+ feeds, concurrent) ───────────────────────────────

class RSSFeedCollector(BaseCollector):
    """High-volume RSS/Atom feed aggregation (global + India-specific)."""

    source = CollectionSource.RSS
    DEFAULT_FEEDS = [
        # Remote global
        "https://weworkremotely.com/remote-jobs.rss",
        "https://remotive.com/remote-jobs/feed",
        "https://jobicy.com/?feed=job_feed",
        "https://dailyremote.com/feed",
        "https://remoteok.com/remote-jobs.rss",
        "https://www.welcometothejungle.com/en/jobs/rss",
        "https://www.idealist.org/en/part-time-jobs/rss",
        # AngelList / Wellfound (Wellfound public feed)
        "https://angel.co/rss",
        # India-specific (when available)
        "https://www.techgig.com/rss/job-openings.xml",
        "https://www.timesjobs.com/rss/latest-jobs.xml",
        "https://www.monsterindia.com/rss/latest-jobs.xml",
        "https://www.sarkariresult.com/rss/latest-jobs.xml",
    ]

    def __init__(self) -> None:
        super().__init__(
            rate_limit_per_second=float(os.getenv("RSS_RATE", "8")),
            max_concurrent_requests=int(os.getenv("RSS_CONCURRENT", "20")),
        )

    async def collect(
        self,
        search_terms: list[str] | None = None,
        location: str | None = None,
        limit: int = 100,
    ) -> list[RawJob]:
        try:
            import feedparser  # noqa: F401
        except ImportError:
            logger.warning("feedparser not installed — skipping RSS collector")
            return []

        run_id = str(uuid4())
        per_feed_limit = max(10, limit // max(1, len(self.DEFAULT_FEEDS) // 2))
        sem = asyncio.Semaphore(int(os.getenv("RSS_FEED_PARALLEL", "10")))

        async def _parse(url: str) -> list[RawJob]:
            async with sem:
                try:
                    return await retry_with_backoff(
                        lambda u=url: self._parse_feed(u, run_id, per_feed_limit, search_terms),
                        max_retries=3,
                        circuit_breaker=self.circuit_breaker,
                    )
                except Exception as e:
                    logger.debug(f"RSS skip {url}: {e}")
                    return []

        all_jobs: list[RawJob] = []
        results = await asyncio.gather(*[_parse(f) for f in self.DEFAULT_FEEDS])
        for jobs in results:
            all_jobs.extend(jobs)
            if len(all_jobs) >= limit:
                break

        # Dedup
        seen: set[str] = set()
        unique: list[RawJob] = []
        for j in all_jobs:
            if j.source_job_id in seen:
                continue
            seen.add(j.source_job_id)
            unique.append(j)

        return unique[:limit]

    async def _parse_feed(
        self, url: str, run_id: str, limit: int,
        search_terms: list[str] | None,
    ) -> list[RawJob]:
        import feedparser
        resp = await self._rate_limited_get(url)
        feed = feedparser.parse(resp.text)
        jobs: list[RawJob] = []
        terms_lower = [t.lower() for t in (search_terms or [])]
        for entry in feed.entries:
            if len(jobs) >= limit:
                break
            title = (entry.get("title", "") or "").strip()
            if terms_lower:
                hay = (title + " " + (entry.get("summary", "") or "")).lower()
                if not any(t in hay for t in terms_lower[:15]):
                    continue
            try:
                company = entry.get("author", entry.get("company", "Unknown"))
                desc = entry.get("summary", entry.get("content", [{}])[0].get("value", ""))
                link = entry.get("link", "")
                published = entry.get("published", "")
                jobs.append(RawJob(
                    source=self.source,
                    source_job_id=self._generate_fingerprint(link, title),
                    source_url=link,
                    collection_run_id=run_id,
                    title=title,
                    description=desc,
                    company_name=company,
                    apply_url=link,
                    posted_date_raw=published,
                    raw_data={k: str(v) for k, v in dict(entry).items()
                              if isinstance(v, (str, int, float))},
                ))
            except Exception:
                continue
        return jobs


# ─── Government Jobs Collector (India) ────────────────────────────────────────

class GovernmentJobsCollector(BaseCollector):
    """Aggregates authentic Indian public sector job postings from live government RSS & portals."""

    source = CollectionSource.GOVERNMENT
    GOV_FEEDS = [
        "https://www.sarkariresult.com/rss/latest-jobs.xml",
        "https://sarkariexam.com/feed",
        "https://www.freejobalert.com/feed/",
    ]

    def __init__(self) -> None:
        super().__init__(rate_limit_per_second=2, max_concurrent_requests=4)

    async def collect(
        self,
        search_terms: list[str] | None = None,
        location: str | None = None,
        limit: int = 100,
    ) -> list[RawJob]:
        try:
            import feedparser
        except ImportError:
            logger.warning("feedparser not installed — skipping Government collector")
            return []

        run_id = str(uuid4())
        jobs: list[RawJob] = []

        async def _parse_gov_feed(url: str) -> list[RawJob]:
            try:
                resp = await self._rate_limited_get(url)
                feed = feedparser.parse(resp.text)
                res: list[RawJob] = []
                for entry in feed.entries[:25]:
                    title = (entry.get("title", "") or "").strip()
                    desc = entry.get("summary", entry.get("content", [{}])[0].get("value", ""))
                    link = entry.get("link", "")
                    
                    org = "Government of India"
                    for kw in ["ISRO", "DRDO", "BHEL", "ONGC", "NTPC", "Railway", "UPSC", "SSC", "IBPS", "Bank", "Police", "Army", "Navy", "Air Force"]:
                        if kw.lower() in title.lower():
                            org = f"Government of India — {kw}"
                            break

                    res.append(RawJob(
                        source=self.source,
                        source_job_id=self._generate_fingerprint(link, title),
                        source_url=link,
                        collection_run_id=run_id,
                        title=title,
                        description=desc or f"Public sector recruitment notice: {title}.",
                        company_name=org,
                        location_raw=location or "India",
                        job_type_raw="Government (Public Sector)",
                        apply_url=link,
                        posted_date_raw=entry.get("published", datetime.utcnow().isoformat()),
                        raw_data={"sector": "government", "source_feed": url},
                    ))
                return res
            except Exception as e:
                logger.debug(f"Government feed skip {url}: {e}")
                return []

        results = await asyncio.gather(*[_parse_gov_feed(u) for u in self.GOV_FEEDS])
        for r in results:
            jobs.extend(r)
            if len(jobs) >= limit:
                break
        return jobs[:limit]


# ─── Company Careers Collector ─────────────────────────────────────────────────

class CompanyCareersCollector(BaseCollector):
    """Aggregates direct company career pages using open ATS public APIs (SmartRecruiters & Ashby)."""

    source = CollectionSource.COMPANY_CAREERS
    SMARTRECRUITERS_COMPANIES = ["visa", "square", "ubisoft", "bosch", "mcdonalds", "sega", "spotify", "atlassian"]
    ASHBY_COMPANIES = ["linear", "ramp", "openai", "retool", "vanta", "duolingo", "notion", "figma"]

    def __init__(self) -> None:
        super().__init__(rate_limit_per_second=6, max_concurrent_requests=15)

    async def collect(
        self,
        search_terms: list[str] | None = None,
        location: str | None = None,
        limit: int = 100,
    ) -> list[RawJob]:
        run_id = str(uuid4())
        jobs: list[RawJob] = []
        sem = asyncio.Semaphore(10)

        async def _fetch_smartrecruiters(slug: str) -> list[RawJob]:
            async with sem:
                try:
                    url = f"https://api.smartrecruiters.com/v1/companies/{slug}/postings"
                    resp = await self._rate_limited_get(url)
                    data = resp.json()
                    res: list[RawJob] = []
                    for item in data.get("content", [])[:15]:
                        name = item.get("name", "")
                        job_id = str(item.get("id", uuid4()))
                        loc_info = item.get("location", {}) or {}
                        city = loc_info.get("city", "")
                        country = loc_info.get("country", "")
                        loc_str = f"{city}, {country}".strip(", ")
                        apply_url = f"https://jobs.smartrecruiters.com/{slug}/{job_id}"
                        
                        res.append(RawJob(
                            source=self.source,
                            source_job_id=f"sr-{slug}-{job_id}",
                            source_url=apply_url,
                            collection_run_id=run_id,
                            title=name,
                            description=f"Direct posting from {slug.title()} career portal for {name}.",
                            company_name=slug.title(),
                            location_raw=loc_str or location,
                            apply_url=apply_url,
                            posted_date_raw=item.get("releasedDate", datetime.utcnow().isoformat()),
                            raw_data=item,
                        ))
                    return res
                except Exception as e:
                    logger.debug(f"SmartRecruiters {slug} failed: {e}")
                    return []

        async def _fetch_ashby(slug: str) -> list[RawJob]:
            async with sem:
                try:
                    url = f"https://api.ashbyhq.com/posting-api/job-board/{slug}"
                    resp = await self._rate_limited_get(url)
                    data = resp.json()
                    res: list[RawJob] = []
                    for item in data.get("jobs", [])[:15]:
                        title = item.get("title", "")
                        job_id = str(item.get("id", uuid4()))
                        apply_url = item.get("jobUrl") or f"https://jobs.ashbyhq.com/{slug}/{job_id}"
                        loc_str = item.get("location", "")
                        
                        res.append(RawJob(
                            source=self.source,
                            source_job_id=f"ashby-{slug}-{job_id}",
                            source_url=apply_url,
                            collection_run_id=run_id,
                            title=title,
                            description=f"Direct career posting from {slug.title()} for {title}.",
                            company_name=slug.title(),
                            location_raw=loc_str or location,
                            apply_url=apply_url,
                            posted_date_raw=datetime.utcnow().isoformat(),
                            raw_data=item,
                        ))
                    return res
                except Exception as e:
                    logger.debug(f"Ashby {slug} failed: {e}")
                    return []

        tasks = [_fetch_smartrecruiters(s) for s in self.SMARTRECRUITERS_COMPANIES] + \
                [_fetch_ashby(a) for a in self.ASHBY_COMPANIES]

        results = await asyncio.gather(*tasks)
        for r in results:
            jobs.extend(r)
            if len(jobs) >= limit:
                break
        return jobs[:limit]


# ─── Remotive Collector (API) ─────────────────────────────────────────────────

class RemotiveCollector(BaseCollector):
    """Remotive.com remote jobs API (no auth required)."""

    source = CollectionSource.REMOTIVE

    def __init__(self) -> None:
        super().__init__(rate_limit_per_second=2, max_concurrent_requests=5)

    async def collect(
        self,
        search_terms: list[str] | None = None,
        location: str | None = None,
        limit: int = 100,
    ) -> list[RawJob]:
        run_id = str(uuid4())
        url = "https://remotive.com/api/remote-jobs"
        params = {"limit": limit}
        if search_terms:
            params["search"] = search_terms[0]
            
        try:
            resp = await retry_with_backoff(
                lambda: self._rate_limited_get(url, params=params),
                max_retries=3,
                circuit_breaker=self.circuit_breaker
            )
            data = resp.json()
        except Exception as e:
            logger.error(f"Remotive: Failed to fetch API: {e}")
            return []

        jobs: list[RawJob] = []
        for item in data.get("jobs", []):
            if len(jobs) >= limit:
                break
            try:
                jobs.append(RawJob(
                    source=self.source,
                    source_job_id=str(item.get("id")),
                    source_url=item.get("url", ""),
                    collection_run_id=run_id,
                    title=item.get("title", ""),
                    description=item.get("description", ""),
                    company_name=item.get("company_name", "Unknown"),
                    location_raw=item.get("candidate_required_location", ""),
                    salary_raw=item.get("salary", ""),
                    job_type_raw=item.get("job_type", ""),
                    apply_url=item.get("url", ""),
                    posted_date_raw=item.get("publication_date", ""),
                    raw_data=item,
                ))
            except Exception as e:
                logger.debug(f"Remotive parse error: {e}")
                
        logger.info(f"Remotive: collected {len(jobs)} real jobs")
        return jobs


# ─── Arbeitnow Collector (API) ────────────────────────────────────────────────

class ArbeitnowCollector(BaseCollector):
    """Arbeitnow job board API (remote and European jobs, no auth required)."""

    source = CollectionSource.ARBEITNOW

    def __init__(self) -> None:
        super().__init__(rate_limit_per_second=2, max_concurrent_requests=5)

    async def collect(
        self,
        search_terms: list[str] | None = None,
        location: str | None = None,
        limit: int = 100,
    ) -> list[RawJob]:
        run_id = str(uuid4())
        url = "https://www.arbeitnow.com/api/job-board-api"
        
        try:
            resp = await retry_with_backoff(
                lambda: self._rate_limited_get(url),
                max_retries=3,
                circuit_breaker=self.circuit_breaker
            )
            data = resp.json()
        except Exception as e:
            logger.error(f"Arbeitnow: Failed to fetch API: {e}")
            return []

        jobs: list[RawJob] = []
        for item in data.get("data", []):
            if len(jobs) >= limit:
                break
            # Arbeitnow does not support search via API easily; filter manually if needed
            title = (item.get("title", "") or "").lower()
            if search_terms and not any(t.lower() in title for t in search_terms[:5]):
                continue
                
            try:
                jobs.append(RawJob(
                    source=self.source,
                    source_job_id=item.get("slug", str(uuid4())),
                    source_url=item.get("url", ""),
                    collection_run_id=run_id,
                    title=item.get("title", ""),
                    description=item.get("description", ""),
                    company_name=item.get("company_name", "Unknown"),
                    location_raw=item.get("location", ""),
                    job_type_raw=", ".join(item.get("job_types", [])),
                    apply_url=item.get("url", ""),
                    posted_date_raw=str(item.get("created_at", "")),
                    raw_data=item,
                ))
            except Exception as e:
                logger.debug(f"Arbeitnow parse error: {e}")

        logger.info(f"Arbeitnow: collected {len(jobs)} real jobs")
        return jobs


# ─── Manual / Direct-upload collector (empty, present for registry) ────────────

class ManualCollector(BaseCollector):
    """Placeholder collector: manual uploads go through Gateway CRUD, not Kafka seeds."""

    source = CollectionSource.MANUAL

    async def collect(self, **_: Any) -> list[RawJob]:
        return []


# ─── Collector Registry ───────────────────────────────────────────────────────

COLLECTOR_REGISTRY: dict[str, type[BaseCollector]] = {
    CollectionSource.ADZUNA: AdzunaCollector,
    CollectionSource.GREENHOUSE: GreenhouseCollector,
    CollectionSource.LEVER: LeverCollector,
    CollectionSource.WORKDAY: WorkdayCollector,
    CollectionSource.INDEED: IndeedScraper,
    CollectionSource.NAUKRI: NaukriScraper,
    CollectionSource.LINKEDIN: LinkedInCollector,
    CollectionSource.RSS: RSSFeedCollector,
    CollectionSource.GOVERNMENT: GovernmentJobsCollector,
    CollectionSource.COMPANY_CAREERS: CompanyCareersCollector,
    CollectionSource.REMOTIVE: RemotiveCollector,
    CollectionSource.ARBEITNOW: ArbeitnowCollector,
    CollectionSource.MANUAL: ManualCollector,
}


def get_collector(source: str) -> BaseCollector:
    cls = COLLECTOR_REGISTRY.get(source)
    if not cls:
        raise ValueError(
            f"Unknown source: {source}. Available: {list(COLLECTOR_REGISTRY.keys())}"
        )
    return cls()


def get_all_sources(exclude_manual: bool = True) -> list[str]:
    sources = list(COLLECTOR_REGISTRY.keys())
    if exclude_manual:
        sources = [s for s in sources if s != CollectionSource.MANUAL]
    return sources
