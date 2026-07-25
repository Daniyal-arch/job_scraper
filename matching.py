from __future__ import annotations

import math
import re
from typing import Optional

from config import load_keywords, load_locations


_BOUNDARY_CLASS = r"[\wäöüßÄÖÜ]"


def _bounded_term(term: str) -> str:
    """Build a boundary-safe pattern fragment for one keyword term.

    German is heavily compounding ("Vermessung" -> "Vermessungsingenieur",
    "Fernerkundung" -> "Fernerkundungsdaten"), so for longer terms we only
    require a clean start boundary and allow the match to continue into a
    compound suffix. Short/acronym-like terms (<=4 core chars, e.g. "GIS",
    "GPS") keep a strict trailing boundary too, otherwise they'd false-match
    as a substring inside unrelated words (e.g. "GIS" inside "Registrierung").
    """
    core_len = len(term.replace(" ", "").replace("-", ""))
    escaped = re.escape(term)
    if core_len <= 4:
        return rf"(?<!{_BOUNDARY_CLASS}){escaped}(?!{_BOUNDARY_CLASS})"
    return rf"(?<!{_BOUNDARY_CLASS}){escaped}"


def _terms_pattern(terms: list[str]) -> re.Pattern:
    # Sort longest-first so multi-word terms aren't shadowed by short substrings.
    parts = [_bounded_term(t) for t in sorted(terms, key=len, reverse=True)]
    return re.compile("(?:" + "|".join(parts) + ")", re.IGNORECASE)


def _all_job_type_terms() -> list[str]:
    return load_keywords()["job_type_terms"]


def _category_terms() -> dict[str, list[str]]:
    cats = load_keywords()["categories"]
    out: dict[str, list[str]] = {}
    for name, value in cats.items():
        if name == "tool_boosters":
            out[name] = list(value)
        else:
            out[name] = list(value.get("en", [])) + list(value.get("de", []))
    return out


def is_job_type_match(text: str) -> bool:
    pattern = _terms_pattern(_all_job_type_terms())
    return bool(pattern.search(text))


def match_categories(text: str) -> list[str]:
    """Return the list of category names whose keywords appear in `text`."""
    matched = []
    for category, terms in _category_terms().items():
        if _terms_pattern(terms).search(text):
            matched.append(category)
    return matched


def is_relevant(combined_text: str) -> tuple[bool, list[str]]:
    """A job is relevant iff it's a Werkstudent-type role AND matches at least
    one geospatial/remote-sensing/computer-vision category."""
    categories = match_categories(combined_text)
    if not categories:
        return False, []
    if not is_job_type_match(combined_text):
        return False, []
    return True, categories


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def is_within_scope(location_text: str, lat: Optional[float] = None, lon: Optional[float] = None) -> bool:
    """Prefer coordinate-based radius check; fall back to town-name matching."""
    loc = load_locations()
    center = loc["center"]
    radius_km = loc["radius_km"]

    if lat is not None and lon is not None:
        return haversine_km(lat, lon, center["lat"], center["lon"]) <= radius_km

    if not location_text:
        return False
    text_lower = location_text.lower()
    return any(town.lower() in text_lower for town in loc["known_towns"])
