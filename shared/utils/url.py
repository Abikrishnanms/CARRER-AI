"""
URL normalization utilities for Job Intelligence Platform.
Ensures all scraped and returned URLs are clean, valid, and clickable direct apply links.
"""

from __future__ import annotations

import html
import re
from urllib.parse import quote_plus

SOURCE_BASE_DOMAINS: dict[str, str] = {
    "adzuna": "https://www.adzuna.com",
    "indeed": "https://in.indeed.com",
    "naukri": "https://www.naukri.com",
    "linkedin": "https://www.linkedin.com",
    "greenhouse": "https://boards.greenhouse.io",
    "lever": "https://jobs.lever.co",
    "workday": "https://www.workday.com",
    "rss": "https://weworkremotely.com",
    "government": "https://www.india.gov.in",
    "company_careers": "https://www.google.com",
}

COMPANY_DIRECT_CAREER_URLS: dict[str, str] = {
    "google": "https://careers.google.com/jobs/results/?q={title}",
    "microsoft": "https://careers.microsoft.com/us/en/search-results?q={title}",
    "amazon": "https://www.amazon.jobs/en/search?base_query={title}",
    "flipkart": "https://www.flipkartcareers.com/",
    "infosys": "https://career.infosys.com/",
    "tcs": "https://www.tcs.com/careers",
    "wipro": "https://careers.wipro.com/",
    "razorpay": "https://razorpay.com/jobs/",
    "zepto": "https://www.zepto.com/careers",
    "meesho": "https://meesho.io/careers",
    "cred": "https://cred.club/careers",
    "groww": "https://groww.in/careers",
    "phonepe": "https://www.phonepe.com/careers/",
    "swiggy": "https://careers.swiggy.com/",
    "zomato": "https://www.zomato.com/careers",
    "ola": "https://ola.criteriacorp.com/",
    "postman": "https://www.postman.com/careers/",
    "freshworks": "https://www.freshworks.com/company/careers/",
    "accenture india": "https://www.accenture.com/in-en/careers/jobsearch?keyword={title}",
    "uber india": "https://www.uber.com/us/en/careers/list/?query={title}",
    "meta india": "https://www.metacareers.com/jobs/?q={title}",
    "apple india": "https://jobs.apple.com/en-in/search?search={title}",
    "stripe india": "https://stripe.com/jobs/search?query={title}",
    "paytm": "https://paytm.com/careers",
    "byju's": "https://byjus.com/careers/",
    "unacademy": "https://unacademy.com/careers",
    "upgrad": "https://www.upgrad.com/careers/",
    "hcl technologies": "https://www.hcltech.com/careers",
    "tech mahindra": "https://careers.techmahindra.com/",
    "deloitte usi": "https://www2.deloitte.com/ui/en/careers/life-at-deloitte.html",
    "pwc india": "https://www.pwc.in/careers.html",
    "ey gds": "https://www.ey.com/en_in/careers",
    "kpmg india": "https://kpmg.com/in/en/home/careers.html",
    "goldman sachs bengaluru": "https://www.goldmansachs.com/careers/",
    "jp morgan chase": "https://careers.jpmorgan.com/us/en/home",
    "morgan stanley": "https://www.morganstanley.com/people-opportunities/careers",
    "atlassian bengaluru": "https://www.atlassian.com/company/careers",
    "dream11": "https://careers.dream11.com/",
    "urban company": "https://careers.urbancompany.com/",
}


def normalize_url(
    url: str | None,
    title: str | None = None,
    company_name: str | None = None,
    source: str | None = None,
) -> str:
    """
    Clean, validate, and normalize a URL.
    - Decodes HTML entities (&amp; -> &)
    - Fixes protocol-relative URLs (//...)
    - Prepends https:// if scheme is missing
    - Replaces invalid dummy domains (.example.com) with direct company career / search links
    - Fallback to direct company career or LinkedIn / Google Search URL if empty
    """
    if not url:
        return _make_direct_apply_fallback(title, company_name)

    # 1. Decode HTML entities and strip surrounding whitespace/quotes
    cleaned = html.unescape(str(url)).strip().strip("\"'<>")

    if not cleaned or cleaned.startswith(("#", "javascript:", "mailto:")):
        return _make_direct_apply_fallback(title, company_name)

    # 2. Handle dummy / synthetic example domains (e.g., workday.example.com)
    if "example.com" in cleaned or "example.org" in cleaned or "simulated" in cleaned or "google.com/search" in cleaned:
        return _make_direct_apply_fallback(title, company_name)

    # 3. Fix protocol-relative URLs (e.g. //domain.com/path)
    if cleaned.startswith("//"):
        cleaned = f"https:{cleaned}"
    # 4. Add https:// if no protocol is present
    elif not cleaned.startswith(("http://", "https://")):
        if "/" in cleaned and not cleaned.startswith("/"):
            cleaned = f"https://{cleaned}"
        elif cleaned.startswith("/"):
            base = SOURCE_BASE_DOMAINS.get((source or "").lower(), "https://www.google.com")
            cleaned = f"{base}{cleaned}"
        else:
            cleaned = f"https://{cleaned}"

    # 5. Clean up any accidental double-slashes in path (except after http(s):)
    scheme_part, _, rest = cleaned.partition("://")
    if rest:
        rest = re.sub(r"/+", "/", rest)
        cleaned = f"{scheme_part}://{rest}"

    return cleaned


def _make_direct_apply_fallback(title: str | None, company_name: str | None) -> str:
    """Generate a direct company career portal or direct job search URL."""
    comp_lower = (company_name or "").lower().strip()
    title_clean = quote_plus((title or "").strip())

    if comp_lower in COMPANY_DIRECT_CAREER_URLS:
        pattern = COMPANY_DIRECT_CAREER_URLS[comp_lower]
        return pattern.format(title=title_clean)

    # Try partial match for known companies
    for known_comp, pattern in COMPANY_DIRECT_CAREER_URLS.items():
        if known_comp in comp_lower or comp_lower in known_comp:
            return pattern.format(title=title_clean)

    # Direct LinkedIn job search fallback if company name is provided
    if company_name and comp_lower not in ("unknown", "various"):
        comp_clean = quote_plus(company_name.strip())
        return f"https://www.linkedin.com/jobs/search/?keywords={comp_clean}+{title_clean}"

    if title:
        return f"https://www.linkedin.com/jobs/search/?keywords={title_clean}"

    return "https://www.linkedin.com/jobs/search/"


async def verify_live_url(url: str | None, timeout: float = 3.5) -> dict[str, Any]:
    """
    Check if a URL is active and reachable via HTTP HEAD/GET request.
    Returns dict with is_reachable flag, status_code, and final URL.
    """
    import httpx

    if not url or not url.startswith(("http://", "https://")):
        return {"is_reachable": False, "status_code": None, "error": "invalid_scheme"}

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
    }
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            try:
                resp = await client.head(url, headers=headers)
                if resp.status_code < 400:
                    return {"is_reachable": True, "status_code": resp.status_code, "final_url": str(resp.url)}
            except Exception:
                pass

            resp = await client.get(url, headers=headers)
            is_ok = resp.status_code < 400
            return {
                "is_reachable": is_ok,
                "status_code": resp.status_code,
                "final_url": str(resp.url),
            }
    except Exception as e:
        return {"is_reachable": False, "status_code": None, "error": str(e)}

