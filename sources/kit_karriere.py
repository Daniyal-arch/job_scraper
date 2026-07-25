"""KIT (Karlsruher Institut für Technologie) Career Service Jobbörse — Tier C.

Legacy PHP-driven job board, plain server-rendered HTML, no anti-bot measures.
It aggregates student jobs (Werkstudent/HiWi/internship) across all KIT
institutes in one place, so we search it directly rather than per-institute
pages (most institute pages only list PhD/postdoc openings).

The listing only exposes a state-level region ("Baden-Württemberg"), not a
city, so the actual workplace city/address is embedded as free text inside
the job description (companies write their own address block). We match
location scope against the full description text rather than a structured
field.
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

BASE_URL = "https://www.careerservice.kit.edu/en/kit-interne/studierenden_stellen_praktika/"
REQUEST_DELAY_SECONDS = 0.5


def _search_listing() -> list[dict]:
    resp = requests.get(BASE_URL, headers=HEADERS, params={"search_text": "Werkstudent"}, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    listings = []
    for box in soup.select(".job-box"):
        title_link = box.select_one(".job-box-data a")
        company_el = box.select_one(".job-box-hl")
        if not title_link or not title_link.get("href"):
            continue
        listings.append(
            {
                "title": title_link.get_text(" ", strip=True),
                "company": company_el.get_text(" ", strip=True) if company_el else "",
                "url": urljoin(BASE_URL, title_link["href"]),
            }
        )
    return listings


def _fetch_description(url: str) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")
    detail = soup.select_one(".job-detail")
    if not detail:
        return ""
    # .job-info-box sidebars list eligibility metadata ("Field of study
    # preferred", career stage, workplace setup) as broad tag lists, not
    # facts about what the role itself involves - e.g. a generic insurance
    # Werkstudent role open to "any technical field" will list Geodesy,
    # Remote Sensing, etc. among dozens of unrelated fields. Strip them so
    # only the free-text job description feeds keyword matching.
    for info_box in detail.select(".job-info-box"):
        info_box.decompose()
    return detail.get_text("\n", strip=True)


def _guess_town(text: str) -> str:
    for town in load_locations()["known_towns"]:
        if town.lower() in text.lower():
            return town
    return ""


def run() -> list[Job]:
    listings = _search_listing()

    jobs: list[Job] = []
    for listing in listings:
        time.sleep(REQUEST_DELAY_SECONDS)
        try:
            description = clean_text(_fetch_description(listing["url"]))
        except requests.RequestException:
            continue

        combined_text = f"{listing['title']}\n{description}"
        relevant, categories = is_relevant(combined_text)
        if not relevant:
            continue

        if not is_within_scope(combined_text):
            continue

        jobs.append(
            Job(
                source="kit",
                title=listing["title"],
                company=listing["company"],
                location=_guess_town(combined_text) or "Baden-Württemberg",
                url=listing["url"],
                description=description,
                date_scraped=dt.now(timezone.utc).date(),
                matched_categories=categories,
            )
        )

    return jobs


if __name__ == "__main__":
    found = run()
    print(f"Found {len(found)} relevant Werkstudent postings")
    for j in found:
        print(f"- [{', '.join(j.matched_categories)}] {j.title} @ {j.company} ({j.location}) -> {j.url}")
