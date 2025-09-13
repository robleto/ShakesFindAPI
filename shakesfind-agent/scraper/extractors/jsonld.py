import json
from extruct.jsonld import JsonLdExtractor
from w3lib.html import get_base_url
from bs4 import BeautifulSoup

EVENT_TYPES = {"Event", "TheaterEvent", "PerformingArtsEvent"}

def extract_events_from_jsonld(html: str, base_url: str):
    soup = BeautifulSoup(html, 'html.parser')
    base = get_base_url(html, base_url)
    extractor = JsonLdExtractor()
    try:
        data = extractor.extract(html, base_url=base)
    except Exception:
        data = []
    events = []
    for obj in data:
        t = obj.get('@type')
        types = set([t] if isinstance(t, str) else t or [])
        if types & EVENT_TYPES:
            name = obj.get('name')
            url = obj.get('url') or base_url
            start = obj.get('startDate')
            end = obj.get('endDate')
            loc = obj.get('location') or {}
            venue = (loc.get('name') if isinstance(loc, dict) else None)
            events.append({
                'title': name,
                'url': url,
                'start_date': start,
                'end_date': end,
                'venue': venue,
                'dates_text': f"{start} – {end}" if start or end else None
            })
    return events
