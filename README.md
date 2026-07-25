# Werkstudent GIS/Geospatial Job Scraper (Karlsruhe area)

Finds **Werkstudent** (working-student) job postings related to GIS,
Geospatial, GeoAI, Remote Sensing, Computer Vision, Surveying, Photogrammetry
etc. (English + German terminology) located in Karlsruhe, Germany and towns
within ~30km. Runs on a GitHub Actions cron schedule and appends new matches
to a Google Sheet.

## How it works

1. Each module in `sources/` scrapes one job platform and returns a list of
   full job records (title, company, location, full description, employment
   type, salary if listed, dates, canonical URL).
2. `matching.py` decides relevance: a posting counts only if it contains a
   Werkstudent-type term **and** at least one geospatial/remote-sensing/
   computer-vision keyword from `config/keywords.yaml`, and its location
   falls within ~30km of Karlsruhe per `config/locations.yaml`.
3. `dedup.py` skips postings whose stable hash is already in the Sheet, so
   re-running never creates duplicate rows.
4. `sheets_writer.py` appends new matches to the configured Google Sheet.
5. `main.py` runs all sources and wires the above together; GitHub Actions
   (`.github/workflows/scrape.yml`) runs it daily and on manual trigger.

## Sources

| Source | Tier | Notes |
|---|---|---|
| Bundesagentur für Arbeit (Jobsuche) | A | Free public JSON endpoint, no auth wall, most reliable source. |
| Fraunhofer careers (jobs.fraunhofer.de, IOSB) | C | Static HTML, schema.org JobPosting microdata. |
| KIT Career Service Jobbörse | C | Static HTML, aggregates all KIT institutes' student jobs. |
| LinkedIn Jobs (guest search) | D | Static HTML, no login. **ToS risk** - see below. |
| Xing Jobs (guest search) | D | Static HTML + JSON-LD JobPosting on detail pages. **ToS risk.** |
| Indeed.de (guest search) | D | Static HTML/JSON. Cloudflare/Turnstile can block after volume. **ToS risk.** |

### Deferred / not implemented

These were reconned but not built, either because they're heavily bot-blocked
or because their location filter turned out to be JS/XHR-driven rather than a
simple URL parameter (would need reverse-engineering an internal API, not
just HTML scraping):

- **Jobmensa, Get in IT** - static HTML but the `location`/`ort` query params
  don't actually filter server-side; the visible HTML is a generic unfiltered
  feed regardless of query string. Confirmed by testing identical results for
  two different cities.
- **Absolventa, Jobware** - Jobware is a full Angular SPA (JS-rendered);
  Absolventa's filtering also appears XHR-driven.
- **StepStone, Stellenanzeigen.de, Monster.de, Kimeta.de, Studitemps.de,
  Yourfirm.de, regional "Jobanzeiger" network** - blocked by Akamai/
  Cloudflare/DataDome bot-management before any content is reachable.
- **Disy Informationssysteme** (Karlsruhe GIS company, genuinely posts
  relevant Werkstudent roles) - the listing page is static, but full job
  descriptions load via a third-party "onlyfy" widget that requires JS
  execution. Worth a manual check periodically: https://www.disy.net/de/karriere/jobs/
- **LUBW, GEO-METRIK-Ingenieurgesellschaft, 3D WELT Vermessung** - small
  Karlsruhe-area geospatial/surveying companies found during recon; no
  current Werkstudent postings at the time of writing, so not worth
  automating yet. Worth a periodic manual check.

### A note on Tier D (LinkedIn/Xing/Indeed)

These platforms' terms of service prohibit automated access, and this was
built with that explicitly accepted by the project owner in exchange for
fuller coverage. Mitigations in place: guest/public pages only (no login,
no stored session), rate-limited requests with delays, and each source
fails gracefully (a block on one source doesn't stop the others or crash the
run). Even so, expect occasional blocks (observed directly during
development - a burst of requests to Indeed triggered a 403/Cloudflare
challenge) and expect selectors to need maintenance when these sites
redesign.

## Setup

### 1. Google Sheet + service account

1. In Google Cloud Console, create (or reuse) a project and enable the
   **Google Sheets API**.
2. Create a **Service Account**, then create a JSON key for it and download it.
3. Create a Google Sheet, and share it with the service account's
   `client_email` (found in the JSON key) as **Editor**.
4. Copy the Sheet ID from its URL:
   `https://docs.google.com/spreadsheets/d/<SHEET_ID>/edit`

### 2. GitHub repo secrets

In the repo's Settings → Secrets and variables → Actions, add:

- `GOOGLE_SERVICE_ACCOUNT_JSON` - the full contents of the downloaded JSON key file.
- `GOOGLE_SHEET_ID` - the Sheet ID from step 1.

### 3. Local run (optional, for testing)

```bash
pip install -r requirements.txt
export GOOGLE_SERVICE_ACCOUNT_JSON="$(cat service-account.json)"
export GOOGLE_SHEET_ID="your-sheet-id"
python main.py
```

Run a single source directly for debugging, e.g.:

```bash
python -m sources.arbeitsagentur
```

### 4. Enable the schedule

The workflow in `.github/workflows/scrape.yml` runs daily at 06:00 UTC and
can also be triggered manually from the Actions tab (`workflow_dispatch`).
No further setup needed once the secrets above are in place.

## Tuning

- **Keywords**: edit `config/keywords.yaml` to add/remove terms per category
  (English and German lists are separate under each category).
- **Location scope**: edit `config/locations.yaml` - `radius_km` and the
  `known_towns` list (used as a fallback when a source doesn't give
  coordinates).
- **Adding a source**: create `sources/<name>.py` exposing a `run() ->
  list[Job]` function (see any existing source for the pattern), then add it
  to `SOURCES` in `main.py`.

## Tests

```bash
pip install -r requirements.txt
pytest tests/ -v
```

Tests cover the keyword/location matching logic (including German compound
words and false-positive guards) and a regression test for a real bug found
during development (KIT's "preferred field of study" eligibility tags were
briefly leaking into the description text and causing false matches).
