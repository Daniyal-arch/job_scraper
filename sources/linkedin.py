"""LinkedIn Jobs guest search — Tier D source (highest ToS risk, included per
explicit user decision to accept the ban/breakage risk for full coverage).

Both the guest search results page and guest job-view detail pages are fully
server-rendered HTML, reachable via plain HTTP GET with no login and no
JS execution required (confirmed by direct fetch, not just via a browser).
robots.txt disallows LinkedIn's *internal* AJAX "seeMoreJobPostings"
pagination endpoint for named bots - we avoid that specific endpoint and use
the normal search URL's own `start` pagination instead, which is the same
one a signed-out visitor's browser loads. LinkedIn's User Agreement still
broadly prohibits automated access, so this stays rate-limited and
guest-page-only (no login, no cookies retained).
"""

from __future__ import annotations

import time
from datetime import datetime as dt
from datetime import timezone
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from config import load_locations
from matching import is_relevant, is_within_scope
from sources.base import Job, clean_text
from sources.http_utils import BROWSER_HEADERS as HEADERS

SEARCH_URL = "https://www.linkedin.com/jobs/search"
PAGE_SIZE = 25
MAX_PAGES = 4
REQUEST_DELAY_SECONDS = 1.5


def _canonical_url(href: str) -> str:
    parsed = urlparse(href)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"


def _search_page(keywords: str, location: str, start: int) -> list[dict]:
    resp = requests.get(
        SEARCH_URL,
        headers=HEADERS,
        params={"keywords": keywords, "location": location, "start": start},
        timeout=20,
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    cards = []
    for card in soup.select(".base-search-card"):
        link = card.select_one("a.base-card__full-link")
        title_el = card.select_one(".base-search-card__title")
        company_el = card.select_one(".base-search-card__subtitle")
        location_el = card.select_one(".job-search-card__location")
        date_el = card.select_one("time")
        if not link or not link.get("href"):
            continue
        cards.append(
            {
                "url": _canonical_url(link["href"]),
                "title": title_el.get_text(strip=True) if title_el else "",
                "company": company_el.get_text(strip=True) if company_el else "",
                "location": location_el.get_text(strip=True) if location_el else "",
                "date_posted": date_el.get("datetime", "") if date_el else "",
            }
        )
    return cards


def _search_all(keywords: str, location: str) -> list[dict]:
    all_cards: dict[str, dict] = {}
    for page in range(MAX_PAGES):
        time.sleep(REQUEST_DELAY_SECONDS)
        try:
            cards = _search_page(keywords, location, start=page * PAGE_SIZE)
        except requests.RequestException:
            # Anti-bot block mid-pagination - keep whatever pages succeeded.
            break
        if not cards:
            break
        for c in cards:
            all_cards[c["url"]] = c
        if len(cards) < PAGE_SIZE:
            break
    return list(all_cards.values())


def _fetch_description(url: str) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")
    el = soup.select_one(".show-more-less-html__markup") or soup.select_one(".description__text")
    return el.get_text("\n", strip=True) if el else ""


def run() -> list[Job]:
    center_name = load_locations()["center"]["name"]
    candidates = _search_all(keywords="Werkstudent", location=center_name)

    jobs: list[Job] = []
    for candidate in candidates:
        time.sleep(REQUEST_DELAY_SECONDS)
        try:
            description = clean_text(_fetch_description(candidate["url"]))
        except requests.RequestException:
            continue

        combined_text = f"{candidate['title']}\n{description}"
        relevant, categories = is_relevant(combined_text)
        if not relevant:
            continue

        if not is_within_scope(candidate["location"]):
            continue

        jobs.append(
            Job(
                source="linkedin",
                title=candidate["title"],
                company=candidate["company"],
                location=candidate["location"],
                url=candidate["url"],
                description=description,
                date_scraped=dt.now(timezone.utc).date(),
                matched_categories=categories,
                date_posted=candidate["date_posted"],
            )
        )

    return jobs


if __name__ == "__main__":
    found = run()
    print(f"Found {len(found)} relevant Werkstudent postings")
    for j in found:
        print(f"- [{', '.join(j.matched_categories)}] {j.title} @ {j.company} ({j.location}) -> {j.url}")
