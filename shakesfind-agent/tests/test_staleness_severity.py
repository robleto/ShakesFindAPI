from scraper.staleness import analyze_staleness
import datetime

TODAY = datetime.date(2025,9,13)

def make_event(s,e=None):
    return {'start_date':s,'end_date':e or s}

def test_past_only_threshold():
    # 10 days past should NOT trigger past_only
    c = {'Productions URL':'https://example.org/season-2025'}
    events = [make_event('2025-08-30','2025-09-01')]  # only 12 days before today
    res = analyze_staleness(c, events, today=TODAY)
    assert 'past_only' not in res['reasons']

def test_past_only_after_30_days():
    c = {'Productions URL':'https://example.org/season-2025'}
    events = [make_event('2025-07-01','2025-07-10')]
    res = analyze_staleness(c, events, today=TODAY)
    assert 'past_only' in res['reasons']
    assert res['severity'] in ('low','medium','high')

def test_empty_page_severity_high():
    c = {'Productions URL':'https://example.org/fall-2024'}
    res = analyze_staleness(c, [], today=TODAY)
    assert 'empty_page' in res['reasons'] and res['severity'] == 'high'
