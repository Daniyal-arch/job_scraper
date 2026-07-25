from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Optional


def clean_text(text: Optional[str]) -> str:
    if not text:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


@dataclass
class Job:
    source: str
    title: str
    company: str
    location: str
    url: str
    description: str
    date_scraped: date

    matched_categories: list[str] = field(default_factory=list)
    employment_type: str = ""
    hours_per_week: str = ""
    salary: str = ""
    requirements: str = ""
    date_posted: str = ""
    application_deadline: str = ""
    lat: Optional[float] = None
    lon: Optional[float] = None
    plz: str = ""

    def dedup_hash(self) -> str:
        """Stable identity for a posting, used to skip rows already written.

        Prefers the canonical URL (most sources give a unique job URL/refnr).
        Falls back to company+title+location for sources where the URL is
        unstable (e.g. rewritten per session).
        """
        key = self.url.strip().lower() or f"{self.company}|{self.title}|{self.location}".strip().lower()
        return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]

    def to_row(self) -> list[str]:
        """Column order must match the header row written by sheets_writer."""
        return [
            self.dedup_hash(),
            self.source,
            ", ".join(self.matched_categories),
            self.title,
            self.company,
            self.location,
            self.employment_type,
            self.hours_per_week,
            self.salary,
            self.date_posted,
            self.application_deadline,
            self.url,
            clean_text(self.description),
            clean_text(self.requirements),
            self.date_scraped.isoformat(),
        ]


SHEET_HEADER = [
    "dedup_hash",
    "source",
    "matched_categories",
    "title",
    "company",
    "location",
    "employment_type",
    "hours_per_week",
    "salary",
    "date_posted",
    "application_deadline",
    "url",
    "description",
    "requirements",
    "date_scraped",
]
