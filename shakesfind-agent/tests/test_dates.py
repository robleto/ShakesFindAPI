import pytest
from scraper.normalize import parse_dates

TZ = 'America/Chicago'

@pytest.mark.parametrize("text,expected", [
    ("March 19 – April 5, 2026", ("2026-03-19","2026-04-05")),
    ("March 19 – 25, 2026", ("2026-03-19","2026-03-25")),
    ("November 26, 2025 – January 4, 2026", ("2025-11-26","2026-01-04")),
    ("October 2 – October 26, 2025", ("2025-10-02","2025-10-26")),
])
def test_parse_ranges(text, expected):
    s,e,_ = parse_dates(text, TZ)
    assert (s,e) == expected

@pytest.mark.parametrize("text", [
    "Festival Stage | Ages 12+",  # no dates
    "By William Shakespeare"      # byline only
])
def test_parse_none(text):
    s,e,_ = parse_dates(text, TZ)
    assert s is None and e is None
