"""Fraunhofer careers portal (jobs.fraunhofer.de) — Tier C source.

Runs on SAP SuccessFactors; both the search results page and job detail pages
are plain server-rendered HTML with schema.org JobPosting microdata on detail
pages (itemprop="title"/"description"/"streetAddress"/"datePosted"), so no
headless browser is needed. Search query params (q, locationsearch) are
applied server-side — confirmed by comparing result sets for different
locations.

We search once for "Werkstudent" scoped to Karlsruhe; this naturally surfaces
postings from Fraunhofer IOSB (the Karlsruhe institute with a geospatial/
computer-vision focus) alongside any other Fraunhofer Karlsruhe institute.
"""

from __future__ import annotations

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

BASE_URL = "https://jobs.fraunhofer.de"
REQUEST_DELAY_SECONDS = 0.5


def _search_links(q: str, location: str) -> list[str]:
    resp = requests.get(
        f"{BASE_URL}/search/",
        headers=HEADERS,
        params={"q": q, "locationsearch": location},
        timeout=20,
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")
    hrefs = {
        urljoin(BASE_URL, a["href"])
        for a in soup.select("a.jobTitle-link")
        if a.get("href")
    }
    return sorted(hrefs)


def _fetch_detail(url: str) -> dict:
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    # The page also embeds JobPosting microdata for "similar jobs" sidebar
    # widgets, so a page-wide find() can pick up the wrong job's fields.
    # Scope every lookup to the main posting's own itemtype=JobPosting block.
    scope = soup.find(attrs={"itemtype": "http://schema.org/JobPosting", "class": "jobDisplayShell"}) or soup

    def _meta(prop: str) -> str:
        el = scope.find(attrs={"itemprop": prop})
        return el.get("content", "") if el and el.name == "meta" else ""

    title_el = scope.find(attrs={"itemprop": "title"})
    desc_el = scope.find(attrs={"itemprop": "description"})

    return {
        "title": title_el.get_text(" ", strip=True) if title_el else "",
        "description": desc_el.get_text("\n", strip=True) if desc_el else "",
        # Format observed: "City, DE, PLZ". Note: this field is occasionally
        # stale/mismatched vs. the job's own URL slug on Fraunhofer's site
        # (a rendering quirk on their end) - harmless here since IOSB's
        # Karlsruhe and Ettlingen sites are both well within our radius.
        "location": _meta("streetAddress"),
        "date_posted": _meta("datePosted"),
        "organization": _meta("hiringOrganization") or "Fraunhofer-Gesellschaft",
    }


def run() -> list[Job]:
    center_name = load_locations()["center"]["name"]
    links = _search_links(q="Werkstudent", location=center_name)

    jobs: list[Job] = []
    for url in links:
        time.sleep(REQUEST_DELAY_SECONDS)
        try:
            detail = _fetch_detail(url)
        except requests.RequestException:
            continue

        title = detail["title"]
        description = clean_text(detail["description"])
        combined_text = f"{title}\n{description}"

        relevant, categories = is_relevant(combined_text)
        if not relevant:
            continue

        location_str = detail["location"]
        if not is_within_scope(location_str):
            continue

        jobs.append(
            Job(
                source="fraunhofer",
                title=title,
                company=detail["organization"],
                location=location_str,
                url=url,
                description=description,
                date_scraped=dt.now(timezone.utc).date(),
                matched_categories=categories,
                date_posted=detail["date_posted"],
            )
        )

    return jobs


if __name__ == "__main__":
    found = run()
    print(f"Found {len(found)} relevant Werkstudent postings")
    for j in found:
        print(f"- [{', '.join(j.matched_categories)}] {j.title} @ {j.company} ({j.location}) -> {j.url}")
