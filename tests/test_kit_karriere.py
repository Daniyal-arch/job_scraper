import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bs4 import BeautifulSoup  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"


def _extract_description(html: str) -> str:
    """Mirrors sources.kit_karriere._fetch_description's parsing logic."""
    soup = BeautifulSoup(html, "lxml")
    detail = soup.select_one(".job-detail")
    for info_box in detail.select(".job-info-box"):
        info_box.decompose()
    return detail.get_text("\n", strip=True)


def test_field_of_study_sidebar_is_excluded_from_description():
    html = (FIXTURES / "kit_detail.html").read_text(encoding="utf-8")
    description = _extract_description(html)

    # This fixture's actual job body is about team assistance / research
    # support, but the page also renders a "Field of study preferred"
    # eligibility widget elsewhere on the page. Regression guard: that
    # widget's own real-world equivalent for other jobs (an Allianz customer
    # service role) was found to list "Geodesy & geoinformatics" /
    # "Remote Sensing and Geoinformatics" among broad eligible fields, which
    # falsely matched our geospatial keywords. This fixture doesn't contain
    # geospatial terms, so we assert the sidebar heading text itself is gone
    # (proof .job-info-box was actually stripped, not just coincidentally
    # keyword-free).
    assert "Field of study preferred" not in description
    assert "Favored career stage" not in description
    assert "This is what the workplace looks like" not in description
    # The real description content must still be present.
    assert "Teamassistenz" in description
