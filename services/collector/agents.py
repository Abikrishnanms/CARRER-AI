"""
Job Collection Agents — Multi-source job aggregation.
Sources: Adzuna API, Greenhouse, Lever, Indeed (scraping), Naukri (scraping), RSS feeds.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import re
import time
from datetime import datetime
from typing import Any
from uuid import uuid4

import httpx
from bs4 import BeautifulSoup

from shared.models.job import CollectionSource, RawJob

logger = logging.getLogger(__name__)

# Common search terms for the Indian job market
DEFAULT_SEARCH_TERMS = [
    "software engineer", "data scientist", "machine learning engineer",
    "python developer", "backend developer", "frontend developer",
    "full stack developer", "devops engineer", "product manager",
    "data analyst", "cloud architect", "cybersecurity", "QA engineer",
    "mobile developer", "AI engineer",
]

# HTTP headers to mimic a real browser
BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}


# ─── Base Collector ────────────────────────────────────────────────────────────

class BaseCollector:
    """Abstract base for all job collectors."""

    source: CollectionSource = CollectionSource.UNKNOWN

    def __init__(self) -> None:
        self.session: httpx.AsyncClient | None = None
        self._request_count = 0
        self._rate_limit = float(os.getenv("SCRAPER_RATE_LIMIT_PER_DOMAIN", "2"))  # req/sec

    async def __aenter__(self) -> BaseCollector:
        self.session = httpx.AsyncClient(
            headers=BROWSER_HEADERS,
            timeout=httpx.Timeout(30.0),
            follow_redirects=True,
        )
        return self

    async def __aexit__(self, *args: Any) -> None:
        if self.session:
            await self.session.aclose()

    async def _rate_limited_get(self, url: str, **kwargs: Any) -> httpx.Response:
        """Rate-limited HTTP GET with jitter."""
        if self._request_count > 0:
            delay = 1.0 / self._rate_limit + (0.5 * (hash(url) % 100) / 100.0)
            await asyncio.sleep(delay)

        self._request_count += 1
        response = await self.session.get(url, **kwargs)
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
        """Generate a stable fingerprint for deduplication."""
        content = "|".join(p.lower().strip() for p in parts if p)
        return hashlib.md5(content.encode()).hexdigest()


# ─── Adzuna API Collector ─────────────────────────────────────────────────────

class AdzunaCollector(BaseCollector):
    """
    Adzuna Jobs API collector.
    Free tier: 250 requests/day with 50 jobs per request.
    API docs: https://developer.adzuna.com/
    """

    source = CollectionSource.ADZUNA
    BASE_URL = "https://api.adzuna.com/v1/api/jobs"

    def __init__(self) -> None:
        super().__init__()
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

        terms = search_terms or DEFAULT_SEARCH_TERMS[:5]
        jobs = []
        run_id = str(uuid4())

        for term in terms:
            if len(jobs) >= limit:
                break

            try:
                term_jobs = await self._collect_term(term, location, run_id, limit - len(jobs))
                jobs.extend(term_jobs)
                logger.info(f"Adzuna: collected {len(term_jobs)} jobs for '{term}'")
            except Exception as e:
                logger.error(f"Adzuna: error collecting '{term}': {e}")

        return jobs

    async def _collect_term(
        self,
        term: str,
        location: str | None,
        run_id: str,
        limit: int,
    ) -> list[RawJob]:
        jobs = []
        results_per_page = min(50, limit)
        max_pages = (limit // results_per_page) + 1

        for page in range(1, max_pages + 1):
            if len(jobs) >= limit:
                break

            params: dict[str, Any] = {
                "app_id": self.app_id,
                "app_key": self.api_key,
                "results_per_page": results_per_page,
                "page": page,
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

                # Stop if we've reached the last page
                if len(data.get("results", [])) < results_per_page:
                    break

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    logger.warning("Adzuna rate limited — waiting 60s")
                    await asyncio.sleep(60)
                elif e.response.status_code == 403:
                    logger.error("Adzuna API credentials invalid")
                    break
                else:
                    logger.error(f"Adzuna HTTP error {e.response.status_code}: {e}")
                    break

        return jobs

    def _parse_adzuna_job(self, item: dict[str, Any], run_id: str) -> RawJob | None:
        """Parse an Adzuna API response item into a RawJob."""
        try:
            company = item.get("company", {})
            location = item.get("location", {})
            location_areas = location.get("area", [])

            # Build location string from areas
            location_raw = ", ".join(reversed(location_areas)) if location_areas else None

            # Parse redirect URL to apply URL
            apply_url = item.get("redirect_url")
            source_url = item.get("redirect_url", "")

            return RawJob(
                source=self.source,
                source_job_id=str(item.get("id", uuid4())),
                source_url=source_url,
                collection_run_id=run_id,
                title=item.get("title", ""),
                description=item.get("description", ""),
                company_name=company.get("display_name", "Unknown"),
                location_raw=location_raw,
                salary_raw=self._format_salary(item),
                job_type_raw=item.get("contract_time"),
                apply_url=apply_url,
                posted_date_raw=item.get("created"),
                raw_data=item,
            )
        except Exception as e:
            logger.warning(f"Failed to parse Adzuna job: {e}")
            return None

    def _format_salary(self, item: dict[str, Any]) -> str | None:
        min_s = item.get("salary_min")
        max_s = item.get("salary_max")
        if min_s and max_s:
            return f"₹{min_s:,.0f} - ₹{max_s:,.0f}"
        elif min_s:
            return f"₹{min_s:,.0f}+"
        return None


# ─── Greenhouse Collector ─────────────────────────────────────────────────────

class GreenhouseCollector(BaseCollector):
    """
    Greenhouse job board API collector.
    No authentication required — uses public job board APIs.
    """

    source = CollectionSource.GREENHOUSE
    # Top companies using Greenhouse with public boards
    DEFAULT_COMPANIES = [
        "google", "dropbox", "airbnb", "stripe", "notion",
        "figma", "discord", "reddit", "twitch", "gitlab",
        "hashicorp", "datadog", "confluent", "databricks",
    ]

    async def collect(
        self,
        search_terms: list[str] | None = None,
        location: str | None = None,
        limit: int = 100,
    ) -> list[RawJob]:
        companies = self.DEFAULT_COMPANIES
        jobs = []
        run_id = str(uuid4())

        for company in companies:
            if len(jobs) >= limit:
                break
            try:
                company_jobs = await self._collect_company(company, run_id)
                jobs.extend(company_jobs)
                logger.info(f"Greenhouse: {len(company_jobs)} jobs from {company}")
            except Exception as e:
                logger.debug(f"Greenhouse: {company} unavailable: {e}")

        return jobs[:limit]

    async def _collect_company(self, company_slug: str, run_id: str) -> list[RawJob]:
        url = f"https://boards-api.greenhouse.io/v1/boards/{company_slug}/jobs"
        response = await self._rate_limited_get(url, params={"content": "true"})
        data = response.json()

        jobs = []
        for item in data.get("jobs", []):
            raw_job = self._parse_greenhouse_job(item, company_slug, run_id)
            if raw_job:
                jobs.append(raw_job)
        return jobs

    def _parse_greenhouse_job(
        self, item: dict[str, Any], company_slug: str, run_id: str
    ) -> RawJob | None:
        try:
            location = item.get("location", {})
            metadata = item.get("metadata", [])
            departments = item.get("departments", [{}])

            # Extract company name from metadata or use slug
            company_name = company_slug.replace("-", " ").title()

            return RawJob(
                source=self.source,
                source_job_id=str(item.get("id")),
                source_url=item.get("absolute_url", ""),
                collection_run_id=run_id,
                title=item.get("title", ""),
                description=item.get("content", ""),
                company_name=company_name,
                location_raw=location.get("name"),
                apply_url=item.get("absolute_url"),
                posted_date_raw=item.get("updated_at"),
                raw_data=item,
            )
        except Exception as e:
            logger.warning(f"Failed to parse Greenhouse job: {e}")
            return None


# ─── Indeed Scraper ───────────────────────────────────────────────────────────

class IndeedScraper(BaseCollector):
    """
    Indeed.com scraper using httpx + BeautifulSoup.
    Rate limited to 2 req/sec to avoid blocking.
    """

    source = CollectionSource.INDEED

    async def collect(
        self,
        search_terms: list[str] | None = None,
        location: str | None = None,
        limit: int = 100,
    ) -> list[RawJob]:
        if not os.getenv("INDEED_SCRAPING_ENABLED", "true").lower() == "true":
            return []

        terms = search_terms or DEFAULT_SEARCH_TERMS[:3]
        jobs = []
        run_id = str(uuid4())
        location = location or "India"

        for term in terms:
            if len(jobs) >= limit:
                break
            try:
                term_jobs = await self._scrape_search(term, location, run_id)
                jobs.extend(term_jobs)
            except Exception as e:
                logger.warning(f"Indeed scraping failed for '{term}': {e}")

        return jobs[:limit]

    async def _scrape_search(
        self, term: str, location: str, run_id: str
    ) -> list[RawJob]:
        jobs = []
        base_url = "https://in.indeed.com/jobs"
        params = {"q": term, "l": location, "sort": "date"}

        response = await self._rate_limited_get(base_url, params=params)
        soup = BeautifulSoup(response.text, "html.parser")

        # Indeed job cards (structure changes frequently)
        job_cards = soup.find_all("div", {"class": re.compile(r"job_seen_beacon|resultContent")})

        for card in job_cards[:20]:  # Limit per page
            raw_job = self._parse_indeed_card(card, run_id)
            if raw_job:
                jobs.append(raw_job)

        return jobs

    def _parse_indeed_card(self, card: Any, run_id: str) -> RawJob | None:
        try:
            # Title
            title_el = card.find("h2", {"class": re.compile(r"jobTitle")})
            if not title_el:
                return None
            title = title_el.get_text(strip=True).replace("new", "").strip()

            # Company
            company_el = card.find("span", {"data-testid": "company-name"})
            company = company_el.get_text(strip=True) if company_el else "Unknown"

            # Location
            location_el = card.find("div", {"data-testid": "text-location"})
            location = location_el.get_text(strip=True) if location_el else None

            # Salary
            salary_el = card.find("div", {"class": re.compile(r"salary|compensation")})
            salary = salary_el.get_text(strip=True) if salary_el else None

            # Job link
            link_el = card.find("a", {"data-jk": True})
            job_key = link_el.get("data-jk") if link_el else str(uuid4())
            source_url = f"https://in.indeed.com/viewjob?jk={job_key}"

            return RawJob(
                source=self.source,
                source_job_id=job_key,
                source_url=source_url,
                collection_run_id=run_id,
                title=title,
                description="",  # Requires a second request per job
                company_name=company,
                location_raw=location,
                salary_raw=salary,
                apply_url=source_url,
                raw_data={"job_key": job_key},
            )
        except Exception as e:
            logger.debug(f"Indeed card parse error: {e}")
            return None


# ─── RSS Feed Collector ───────────────────────────────────────────────────────

class RSSFeedCollector(BaseCollector):
    """Collects jobs from RSS/Atom feeds."""

    source = CollectionSource.RSS

    # Job board RSS feeds
    DEFAULT_FEEDS = [
        "https://weworkremotely.com/remote-jobs.rss",
        "https://remotive.io/api/remote-jobs?format=rss",
        "https://jobicy.com/?feed=job_feed",
    ]

    async def collect(
        self,
        search_terms: list[str] | None = None,
        location: str | None = None,
        limit: int = 100,
    ) -> list[RawJob]:
        import feedparser

        jobs = []
        run_id = str(uuid4())

        for feed_url in self.DEFAULT_FEEDS:
            if len(jobs) >= limit:
                break
            try:
                feed_jobs = await self._parse_feed(feed_url, run_id)
                jobs.extend(feed_jobs)
                logger.info(f"RSS: {len(feed_jobs)} jobs from {feed_url}")
            except Exception as e:
                logger.warning(f"RSS feed error {feed_url}: {e}")

        return jobs[:limit]

    async def _parse_feed(self, url: str, run_id: str) -> list[RawJob]:
        import feedparser

        response = await self._rate_limited_get(url)
        feed = feedparser.parse(response.text)

        jobs = []
        for entry in feed.entries:
            try:
                title = entry.get("title", "")
                company = entry.get("author", entry.get("company", "Unknown"))
                description = entry.get("summary", entry.get("content", [{}])[0].get("value", ""))
                link = entry.get("link", "")
                published = entry.get("published", "")

                jobs.append(RawJob(
                    source=self.source,
                    source_job_id=self._generate_fingerprint(link, title),
                    source_url=link,
                    collection_run_id=run_id,
                    title=title,
                    description=description,
                    company_name=company,
                    apply_url=link,
                    posted_date_raw=published,
                    raw_data=dict(entry),
                ))
            except Exception as e:
                logger.debug(f"RSS entry parse error: {e}")

        return jobs


# ─── Collector Registry ───────────────────────────────────────────────────────

COLLECTOR_REGISTRY: dict[str, type[BaseCollector]] = {
    CollectionSource.ADZUNA: AdzunaCollector,
    CollectionSource.GREENHOUSE: GreenhouseCollector,
    CollectionSource.INDEED: IndeedScraper,
    CollectionSource.RSS: RSSFeedCollector,
}


def get_collector(source: str) -> BaseCollector:
    """Get a collector instance by source name."""
    cls = COLLECTOR_REGISTRY.get(source)
    if not cls:
        raise ValueError(f"Unknown source: {source}. Available: {list(COLLECTOR_REGISTRY.keys())}")
    return cls()
