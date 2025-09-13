from scraper.staleness import analyze_staleness
import datetime

def test_empty_page():
    c = {'id':'x','Name':'Test','Productions URL':'https://example.org/Season-50'}
    res = analyze_staleness(c, [], today=datetime.date(2025,9,13))
    assert res['stale'] and 'empty_page' in res['reasons']

def test_past_only():
    c = {'id':'y','Name':'Past','Productions URL':'https://example.org/fall-2024/'}
    events = [{'start_date':'2024-01-01','end_date':'2024-03-01'}]
    res = analyze_staleness(c, events, today=datetime.date(2025,9,13))
    assert 'past_only' in res['reasons']

def test_url_year_mismatch():
    c = {'id':'z','Name':'Old','Productions URL':'https://example.org/season-2022/'}
    events = [{'start_date':'2022-01-01','end_date':'2022-02-01'}]
    res = analyze_staleness(c, events, today=datetime.date(2025,9,13))
    assert 'url_year_mismatch' in res['reasons']

def test_season_window_expired():
    c = {'id':'h','Name':'Holiday','Productions URL':'https://example.org/holidays-2024/'}
    events = [{'start_date':'2024-12-01','end_date':'2025-01-05'}]
    res = analyze_staleness(c, events, today=datetime.date(2025,9,13))
    assert 'season_window_expired' in res['reasons']
