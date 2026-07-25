"""Google Sheets output — the only destination for scraped jobs (per plan).

Auth: a Google Cloud service account JSON key, provided via the
GOOGLE_SERVICE_ACCOUNT_JSON env var (its raw JSON content — this is what the
GitHub Actions workflow injects from a repo secret). The target spreadsheet
must be shared with that service account's client_email as an Editor.

Required env vars:
  GOOGLE_SERVICE_ACCOUNT_JSON  - raw JSON key content
  GOOGLE_SHEET_ID              - the spreadsheet ID (from its URL)
  GOOGLE_SHEET_WORKSHEET_NAME  - optional, defaults to "Jobs"
"""

from __future__ import annotations

import json
import os

import gspread
from google.oauth2.service_account import Credentials

from sources.base import SHEET_HEADER, Job

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
DEFAULT_WORKSHEET_NAME = "Jobs"


def _service_account_info() -> dict:
    # .strip() guards against a stray trailing newline/space that CI secret
    # UIs (and copy-paste in general) commonly introduce - a raw JSON string
    # with a trailing "\n" still parses fine, but a padded sheet ID below
    # would silently 404 since it no longer matches the real ID.
    raw_json = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"].strip()
    return json.loads(raw_json)


def _get_client(info: dict) -> gspread.Client:
    creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    return gspread.authorize(creds)


def get_worksheet() -> gspread.Worksheet:
    info = _service_account_info()
    client = _get_client(info)
    sheet_id = os.environ["GOOGLE_SHEET_ID"].strip()
    worksheet_name = os.environ.get("GOOGLE_SHEET_WORKSHEET_NAME", DEFAULT_WORKSHEET_NAME)

    try:
        spreadsheet = client.open_by_key(sheet_id)
    except gspread.SpreadsheetNotFound:
        raise RuntimeError(
            f"Spreadsheet '{sheet_id}' not found or not accessible. Check that "
            f"GOOGLE_SHEET_ID is exactly the ID from the sheet's URL (no extra "
            f"quotes/whitespace), and that the sheet is shared with "
            f"'{info.get('client_email')}' as Editor."
        ) from None
    try:
        worksheet = spreadsheet.worksheet(worksheet_name)
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title=worksheet_name, rows=1000, cols=len(SHEET_HEADER))

    first_row = worksheet.row_values(1)
    if first_row != SHEET_HEADER:
        worksheet.update("A1", [SHEET_HEADER])

    return worksheet


def get_existing_hashes(worksheet: gspread.Worksheet) -> set[str]:
    hash_column = worksheet.col_values(1)  # dedup_hash is column A
    return set(hash_column[1:])  # skip header


def append_jobs(worksheet: gspread.Worksheet, jobs: list[Job]) -> None:
    if not jobs:
        return
    rows = [job.to_row() for job in jobs]
    worksheet.append_rows(rows, value_input_option="RAW")
