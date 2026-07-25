import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from matching import is_relevant, is_within_scope, match_categories  # noqa: E402


def test_relevant_gis_werkstudent():
    text = "Wir suchen einen Werkstudenten (m/w/d) im Bereich Geoinformatik / GIS"
    ok, cats = is_relevant(text)
    assert ok
    assert "gis" in cats


def test_irrelevant_without_geospatial_category():
    text = "Werkstudent Marketing (m/w/d) gesucht"
    ok, cats = is_relevant(text)
    assert not ok
    assert cats == []


def test_irrelevant_without_job_type():
    text = "Praktikant Fernerkundung (m/w/d) gesucht"
    ok, cats = is_relevant(text)
    assert not ok


def test_relevant_remote_sensing_colon_in():
    text = "Werkstudent:in Fernerkundung / Remote Sensing"
    ok, cats = is_relevant(text)
    assert ok
    assert "remote_sensing" in cats


def test_german_compound_word_matches():
    text = "Werkstudent (m/w/d) als Vermessungsingenieur gesucht"
    ok, cats = is_relevant(text)
    assert ok
    assert "surveying_geodesy" in cats


def test_short_acronym_does_not_false_match_substring():
    # "Registrierung" contains "gis" as a substring but must not match GIS.
    cats = match_categories("Werkstudent Registrierung und Verwaltung")
    assert "gis" not in cats


def test_gis_acronym_matches_as_whole_word():
    cats = match_categories("Werkstudent GIS Support")
    assert "gis" in cats


def test_within_scope_by_town_name():
    assert is_within_scope("Ettlingen")
    assert not is_within_scope("Berlin")


def test_within_scope_by_coordinates():
    # Karlsruhe city center coordinates -> within scope
    assert is_within_scope("", lat=49.0069, lon=8.4037)
    # Munich coordinates -> out of scope
    assert not is_within_scope("", lat=48.1351, lon=11.5820)
