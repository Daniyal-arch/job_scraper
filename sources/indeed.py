"""Indeed.de guest search — Tier D source (included per explicit user
decision to accept ToS/ban risk for full coverage).

Search results embed a full JSON blob (window.mosaic.providerData[...]) with
structured fields per card - no HTML scraping needed for the listing. Detail
pages (/viewjob?jk=...) are technically robots.txt-disallowed for generic
crawlers even though not login-gated; per the user's explicit "include
everything" decision we still fetch them (rate-limited, no login) to get the
full description rather than the truncated search snippet.
"""

from __future__ import annotations

import json
import re
import time
from datetime import datetime as dt
from datetime import timezone

import requests
from bs4 import BeautifulSoup

from config import load_locations
from matching import is_relevant, is_within_scope
from sources.base import Job, clean_text
from sources.http_utils import BROWSER_HEADERS as HEADERS

SEARCH_URL = "https://de.indeed.com/jobs"
DETAIL_URL = "https://de.indeed.com/viewjob"
RESULTS_PER_PAGE = 10
MAX_PAGES = 5
REQUEST_DELAY_SECONDS = 1.0

_CARDS_BLOB_RE = re.compile(
    r'window\.mosaic\.providerData\["mosaic-provider-jobcards"\]\s*=\s*(\{.*?\});\s*\n', re.S
)


def _search_page(q: str, location: str, radius_km: int, start: int) -> list[dict]:
    resp = requests.get(
        SEARCH_URL,
        headers=HEADERS,
        params={"q": q, "l": location, "radius": radius_km, "start": start},
        timeout=20,
    )
    resp.raise_for_status()
    match = _CARDS_BLOB_RE.search(resp.text)
    if not match:
        return []
    data = json.loads(match.group(1))
    return data.get("metaData", {}).get("mosaicProviderJobCardsModel", {}).get("results", [])


def _search_all(q: str, location: str, radius_km: int) -> list[dict]:
    all_results: dict[str, dict] = {}
    for page in range(MAX_PAGES):
        time.sleep(REQUEST_DELAY_SECONDS)
        try:
            results = _search_page(q, location, radius_km, start=page * RESULTS_PER_PAGE)
        except requests.RequestException:
            # Anti-bot block (Cloudflare) mid-pagination - keep whatever
            # pages succeeded so far rather than losing the whole run.
            break
        if not results:
            break
        for r in results:
            key = r.get("jobkey")
            if key:
                all_results[key] = r
        if len(results) < RESULTS_PER_PAGE:
            break
    return list(all_results.values())


def _fetch_description(jobkey: str) -> str:
    resp = requests.get(DETAIL_URL, headers=HEADERS, params={"jk": jobkey}, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")
    el = soup.select_one("#jobDescriptionText")
    return el.get_text("\n", strip=True) if el else ""


def run() -> list[Job]:
    locations_cfg = load_locations()
    center_name = locations_cfg["center"]["name"]
    radius_km = locations_cfg["radius_km"]

    candidates = _search_all(q="Werkstudent", location=center_name, radius_km=radius_km)

    jobs: list[Job] = []
    for candidate in candidates:
        jobkey = candidate.get("jobkey")
        if not jobkey:
            continue
        time.sleep(REQUEST_DELAY_SECONDS)
        try:
            description = clean_text(_fetch_description(jobkey))
        except requests.RequestException:
            continue

        title = candidate.get("displayTitle") or candidate.get("title", "")
        combined_text = f"{title}\n{description}"
        relevant, categories = is_relevant(combined_text)
        if not relevant:
            continue

        location_str = candidate.get("formattedLocation", "")
        if not is_within_scope(location_str):
            continue

        jobs.append(
            Job(
                source="indeed",
                title=title,
                company=candidate.get("company", ""),
                location=location_str,
                url=f"{DETAIL_URL}?jk={jobkey}",
                description=description,
                date_scraped=dt.now(timezone.utc).date(),
                matched_categories=categories,
                salary=str(candidate.get("extractedSalary") or ""),
            )
        )

    return jobs


if __name__ == "__main__":
    found = run()
    print(f"Found {len(found)} relevant Werkstudent postings")
    for j in found:
        print(f"- [{', '.join(j.matched_categories)}] {j.title} @ {j.company} ({j.location}) -> {j.url}")
