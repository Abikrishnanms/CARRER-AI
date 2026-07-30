"""
scrapers/naukri.py

Scraper for Naukri.com job listings — built on BaseScraper.
Uses Playwright (fetch_rendered) since Naukri's search results are
rendered client-side via Next.js/React and don't appear in raw HTML.
"""

from bs4 import BeautifulSoup
from datetime import datetime, timezone
from typing import List, Dict, Optional

from scrapers.base_scraper import BaseScraper


class NaukriScraper(BaseScraper):

    SEARCH_URL = "https://www.naukri.com/{keyword}-jobs-in-{location}"

    def __init__(self):
        super().__init__(source_name="naukri")

    def search_jobs(self, keyword: str, location: str, pages: int = 1) -> List[Dict]:
        """
        Search Naukri listings for a keyword/location.
        Returns a list of dicts with basic info + job detail URL.
        """
        results = []
        keyword_slug = keyword.strip().lower().replace(" ", "-")
        location_slug = location.strip().lower().replace(" ", "-")

        for page in range(1, pages + 1):
            url = self.SEARCH_URL.format(keyword=keyword_slug, location=location_slug)
            if page > 1:
                url += f"-{page}"

            html = self.fetch_rendered(url)
            if not html:
                self.logger.warning(f"No HTML returned for page {page}, stopping.")
                break

            soup = BeautifulSoup(html, "html.parser")
            cards = soup.select("div.srp-jobtuple-wrapper")

            if not cards:
                self.logger.warning(f"No job cards found on page {page} — selector may be outdated.")
                break

            for card in cards:
                job = self._parse_card(card)
                if job:
                    results.append(job)

            self.logger.info(f"Page {page}: found {len(cards)} cards, {len(results)} total so far.")

        return results

    def _parse_card(self, card) -> Optional[Dict]:
        try:
            title_tag = card.select_one("a.title")
            company_tag = card.select_one("a.comp-name")
            location_tag = card.select_one("span.locWdth")
            exp_tag = card.select_one("span.expwdth")

            if not title_tag:
                return None

            return {
                "title": title_tag.get_text(strip=True),
                "url": title_tag.get("href"),
                "company": company_tag.get_text(strip=True) if company_tag else None,
                "location": location_tag.get_text(strip=True) if location_tag else None,
                "experience": exp_tag.get_text(strip=True) if exp_tag else None,
                "source": "naukri",
                "scraped_at": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as e:
            self.logger.error(f"Failed to parse card: {e}")
            return None

    def parse_job_detail(self, url: str) -> Optional[Dict]:
        """
        Fetch and parse the full job description from a detail page.
        Naukri detail pages are also JS-rendered, so we use fetch_rendered here too.
        """
        html = self.fetch_rendered(url)
        if not html:
            return None

        soup = BeautifulSoup(html, "html.parser")
        desc_tag = soup.select_one("div.styles_JDC__dang-inner-html__h0K4t")

        description = desc_tag.get_text(separator="\n", strip=True) if desc_tag else None

        return {
            "url": url,
            "description": description,
            "source": "naukri",
            "scraped_at": datetime.now(timezone.utc).isoformat(),
        }


if __name__ == "__main__":
    scraper = NaukriScraper()
    jobs = scraper.search_jobs(keyword="data analyst", location="bangalore", pages=1)
    print(f"Found {len(jobs)} jobs")
    for j in jobs[:3]:
        print(j)
    scraper.close()