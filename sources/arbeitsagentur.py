"""Bundesagentur für Arbeit "Jobsuche" search — Tier A source.

Community-documented public endpoint (see https://github.com/bundesAPI/jobsuche-api)
that powers arbeitsagentur.de's own job search frontend. No login, no rate-limit
issues observed, returns full structured job details including free-text
description — this is the most reliable source in the whole scraper and is
queried first.

Strategy: search once for "Werkstudent" within the configured radius (server
does the location filtering), paginate through all results, then fetch the
full detail record for each candidate and run it through matching.is_relevant()
to decide whether it's actually geospatial/remote-sensing/computer-vision
related (title alone is rarely enough signal).
"""

from __future__ import annotations

import base64
import time
from datetime import datetime as dt
from datetime import timezone

import requests

from config import load_locations
from matching import is_relevant, is_within_scope
from sources.base import Job, clean_text

BASE_URL = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service"
HEADERS = {"X-API-Key": "jobboerse-jobsuche"}
PAGE_SIZE = 100
REQUEST_DELAY_SECONDS = 0.3


def _search_page(was: str, wo: str, umkreis: int, page: int) -> dict:
    resp = requests.get(
        f"{BASE_URL}/pc/v4/jobs",
        headers=HEADERS,
        params={"was": was, "wo": wo, "umkreis": umkreis, "page": page, "size": PAGE_SIZE},
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()


def _search_all(was: str, wo: str, umkreis: int) -> list[dict]:
    first = _search_page(was, wo, umkreis, page=1)
    results = list(first.get("stellenangebote", []))
    total = first.get("maxErgebnisse", len(results))
    page = 2
    while len(results) < total:
        time.sleep(REQUEST_DELAY_SECONDS)
        batch = _search_page(was, wo, umkreis, page=page)
        offers = batch.get("stellenangebote", [])
        if not offers:
            break
        results.extend(offers)
        page += 1
    return results


def _fetch_detail(refnr: str) -> dict:
    encoded = base64.urlsafe_b64encode(refnr.encode("utf-8")).decode("ascii")
    resp = requests.get(f"{BASE_URL}/pc/v4/jobdetails/{encoded}", headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return resp.json()


def _job_url(refnr: str) -> str:
    return f"https://www.arbeitsagentur.de/jobsuche/jobdetail/{refnr}"


def _format_location(adresse: dict) -> str:
    parts = [adresse.get("ort", ""), adresse.get("plz", "")]
    return ", ".join(p for p in parts if p)


def run() -> list[Job]:
    center_name = load_locations()["center"]["name"]
    radius_km = load_locations()["radius_km"]

    candidates = _search_all(was="Werkstudent", wo=center_name, umkreis=radius_km)

    jobs: list[Job] = []
    for candidate in candidates:
        refnr = candidate.get("refnr")
        if not refnr:
            continue
        time.sleep(REQUEST_DELAY_SECONDS)
        try:
            detail = _fetch_detail(refnr)
        except requests.RequestException:
            continue

        title = detail.get("stellenangebotsTitel", "") or candidate.get("titel", "")
        description = clean_text(detail.get("stellenangebotsBeschreibung", ""))
        combined_text = f"{title}\n{description}"

        relevant, categories = is_relevant(combined_text)
        if not relevant:
            continue

        lokationen = detail.get("stellenlokationen") or []
        adresse = lokationen[0].get("adresse", {}) if lokationen else {}
        lat = lokationen[0].get("breite") if lokationen else None
        lon = lokationen[0].get("laenge") if lokationen else None
        location_str = _format_location(adresse) or candidate.get("arbeitsort", {}).get("ort", "")

        if not is_within_scope(location_str, lat=lat, lon=lon):
            continue

        eintritt = detail.get("eintrittszeitraum") or {}
        jobs.append(
            Job(
                source="arbeitsagentur",
                title=title,
                company=detail.get("firma", "") or candidate.get("arbeitgeber", ""),
                location=location_str,
                url=_job_url(refnr),
                description=description,
                date_scraped=dt.now(timezone.utc).date(),
                matched_categories=categories,
                employment_type=detail.get("stellenangebotsart", ""),
                salary=detail.get("verguetungsangabe", ""),
                date_posted=detail.get("datumErsteVeroeffentlichung", ""),
                application_deadline=eintritt.get("bis", ""),
                lat=lat,
                lon=lon,
                plz=adresse.get("plz", ""),
            )
        )

    return jobs


if __name__ == "__main__":
    found = run()
    print(f"Found {len(found)} relevant Werkstudent postings")
    for j in found:
        print(f"- [{', '.join(j.matched_categories)}] {j.title} @ {j.company} ({j.location}) -> {j.url}")
