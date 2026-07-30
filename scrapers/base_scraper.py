"""
scrapers/base_scraper.py

Shared base class for all job-board scrapers (Naukri, Indeed, LinkedIn, Shine, etc.)
Handles session management, headers, retries, rate-limiting, and common fetch logic.
Also supports JS-rendered pages (React/Next.js sites like Naukri) via Playwright.
"""

import time
import random
from typing import Optional

import requests
from requests.adapters import HTTPAdapter, Retry
from playwright.sync_api import sync_playwright

from app.utils.logger import get_logger
from app.config import settings


USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
]


class BaseScraper:
    """
    Common functionality every source-specific scraper builds on:
    - persistent session with retry/backoff (for static pages)
    - Playwright-based rendering (for JS-heavy pages)
    - randomized headers
    - polite delay between requests
    - centralized logging
    """

    def __init__(self, source_name: str, min_delay: float = 2.0, max_delay: float = 5.0):
        self.source_name = source_name
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.logger = get_logger(f"scraper.{source_name}")
        self.session = self._build_session()

    def _build_session(self) -> requests.Session:
        session = requests.Session()
        retries = Retry(
            total=3,
            backoff_factor=1.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
        )
        adapter = HTTPAdapter(max_retries=retries)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    def _headers(self) -> dict:
        return {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Connection": "keep-alive",
        }

    def _delay(self):
        wait = random.uniform(self.min_delay, self.max_delay)
        time.sleep(wait)

    def fetch(self, url: str, params: Optional[dict] = None) -> Optional[str]:
        """
        Fetch a URL politely via plain requests: random headers + delay + retry.
        Use this for static/server-rendered pages.
        Returns raw HTML text, or None on failure.
        """
        try:
            self._delay()
            response = self.session.get(
                url, headers=self._headers(), params=params, timeout=15
            )
            response.raise_for_status()
            self.logger.info(f"Fetched {url} [{response.status_code}]")
            return response.text
        except requests.RequestException as e:
            self.logger.error(f"Failed to fetch {url}: {e}")
            return None

    def fetch_rendered(self, url: str, wait_ms: int = 6000, timeout: int = 30000) -> Optional[str]:
        """
        Fetch a JS-rendered page using a real headless browser (Playwright).
        Use this for React/Next.js/Vue-heavy sites like Naukri, where content
        is injected client-side and won't appear in a plain requests.get() response.

        wait_ms: fixed wait after page load to allow client-side rendering to finish.
                 (More reliable here than wait_for_selector, which can time out
                 even when the page is rendering correctly.)
        """
        try:
            self._delay()
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(user_agent=self._headers()["User-Agent"])
                page.goto(url, timeout=timeout)
                page.wait_for_timeout(wait_ms)
                html = page.content()
                browser.close()
                self.logger.info(f"Rendered {url} via Playwright")
                return html
        except Exception as e:
            self.logger.error(f"Playwright fetch failed for {url}: {e}")
            return None

    def close(self):
        self.session.close()