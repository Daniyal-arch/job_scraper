"""Xing Jobs guest search — Tier D source (included per explicit user
decision to accept ToS/ban risk for full coverage).

Search results are server-rendered (styled-components SSR) but rely on
auto-generated CSS class names that change between deploys, so card fields
are read via stable attributes instead (article[data-testid], aria-label,
visible text order) rather than brittle class selectors. Detail pages embed
a full schema.org JobPosting as JSON-LD - by far the most reliable field
source of any Tier D site, no HTML scraping needed for the description.
"""

from __future__ import annotations

import json
import time
from datetime import datetime as dt
from datetime import timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from config import load_locations
from matching import is_relevant, is_within_scope
from sources.base import Job, clean_text
from sources.http_utils import BROWSER_HEADERS as HEADERS

BASE_URL = "https://www.xing.com"
REQUEST_DELAY_SECONDS = 1.0


def _search_links(keywords: str, location: str) -> list[str]:
    resp = requests.get(
        f"{BASE_URL}/jobs/search",
        headers=HEADERS,
        params={"keywords": keywords, "location": location},
        timeout=20,
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    hrefs = {
        urljoin(BASE_URL, a["href"])
        for a in soup.select('article[data-testid="job-search-result"] a[href^="/jobs/"]')
        if a.get("href")
    }
    return sorted(hrefs)


def _fetch_job_posting(url: str) -> dict | None:
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(script.string)
        except (TypeError, ValueError):
            continue
        if isinstance(data, dict) and data.get("@type") == "JobPosting":
            return data
    return None


def run() -> list[Job]:
    center_name = load_locations()["center"]["name"]
    links = _search_links(keywords="Werkstudent", location=center_name)

    jobs: list[Job] = []
    for url in links:
        time.sleep(REQUEST_DELAY_SECONDS)
        try:
            posting = _fetch_job_posting(url)
        except requests.RequestException:
            continue
        if not posting:
            continue

        title = posting.get("title", "")
        description = clean_text(BeautifulSoup(posting.get("description", ""), "lxml").get_text("\n"))
        combined_text = f"{title}\n{description}"

        relevant, categories = is_relevant(combined_text)
        if not relevant:
            continue

        locations = posting.get("jobLocation") or []
        address = locations[0].get("address", {}) if locations else {}
        location_str = ", ".join(
            p for p in [address.get("addressLocality", ""), address.get("postalCode", "")] if p
        )

        if not is_within_scope(location_str):
            continue

        org = posting.get("hiringOrganization") or {}
        jobs.append(
            Job(
                source="xing",
                title=title,
                company=org.get("name", ""),
                location=location_str,
                url=posting.get("url", url),
                description=description,
                date_scraped=dt.now(timezone.utc).date(),
                matched_categories=categories,
                date_posted=posting.get("datePosted", ""),
                employment_type=posting.get("employmentType", ""),
                application_deadline=posting.get("validThrough", ""),
            )
        )

    return jobs


if __name__ == "__main__":
    found = run()
    print(f"Found {len(found)} relevant Werkstudent postings")
    for j in found:
        print(f"- [{', '.join(j.matched_categories)}] {j.title} @ {j.company} ({j.location}) -> {j.url}")
