import re, dateparser
from dateutil.parser import parse as dtparse
from dateutil.tz import gettz

CLEAN_PATTERNS = [
    (re.compile(r"^The (Folger|RSC|Globe) Presents[:\s]+", re.I), ""),
    # Marketing prefixes like WILLIAM SHAKESPEARE'S MUCH ADO ABOUT NOTHING
    (re.compile(r"(?i)^(William\s+Shakespeare'?s\s+)+"), ""),
    # Redundant BY lines accidentally captured as title
    (re.compile(r"(?i)^By William Shakespeare$"), ""),
]

def normalize_event(evt: dict, tz: str):
    title = (evt.get('title') or '').strip()
    for rx, rep in CLEAN_PATTERNS:
        title = rx.sub(rep, title)
    return {
        'title': title,
        'url': evt.get('url'),
        'venue': evt.get('venue'),
        'dates_text': evt.get('dates_text') or '',
    'start_date': evt.get('start_date'),  # keep if extractor already parsed
    'end_date': evt.get('end_date'),
    }

def parse_dates(dates_text: str, tz: str, start_hint=None, end_hint=None):
    tzinfo = gettz(tz)
    if start_hint:
        try:
            s = dtparse(start_hint)
            e = dtparse(end_hint) if end_hint else None
            return s.date().isoformat(), (e and e.date().isoformat()), 1.0
        except Exception:
            pass
    if not dates_text:
        return None, None, 0.0
    text = dates_text.strip()
    text = re.sub(r"([A-Za-z]{3,9})(\d)", r"\1 \2", text)
    month = r"(January|February|March|April|May|June|July|August|September|October|November|December)"
    day = r"(\d{1,2})"
    year = r"(\d{4})"
    rx_cross = re.compile(fr"{month}\s+{day}\s*,?\s+{year}\s*[–-]\s*{month}\s+{day}\s*,?\s+{year}", re.I)
    rx_two_month_one_year = re.compile(fr"{month}\s+{day}\s*[–-]\s*{month}\s+{day},?\s+{year}", re.I)
    rx_same_month_range = re.compile(fr"{month}\s+{day}\s*[–-]\s*{day},?\s+{year}", re.I)
    from calendar import month_name
    def mnum(mo):
        return list(month_name).index(mo.capitalize())
    import datetime
    m = rx_cross.search(text)
    if m:
        mo1, d1, y1, mo2, d2, y2 = m.groups()
        try:
            s = datetime.date(int(y1), mnum(mo1), int(d1))
            e = datetime.date(int(y2), mnum(mo2), int(d2))
            conf = 1.0 if y1 == y2 else 0.95
            return s.isoformat(), e.isoformat(), conf
        except Exception:
            pass
    m = rx_two_month_one_year.search(text)
    if m:
        mo1, d1, mo2, d2, yr = m.groups()
        try:
            s = datetime.date(int(yr), mnum(mo1), int(d1))
            e = datetime.date(int(yr), mnum(mo2), int(d2))
            return s.isoformat(), e.isoformat(), 0.95
        except Exception:
            pass
    m = rx_same_month_range.search(text)
    if m:
        mo, d1, d2, yr = m.groups()
        try:
            s = datetime.date(int(yr), mnum(mo), int(d1))
            e = datetime.date(int(yr), mnum(mo), int(d2))
            return s.isoformat(), e.isoformat(), 0.9
        except Exception:
            pass
    parts = re.split(r"\s*[–-]\s*", text)
    s = dateparser.parse(parts[0], settings={'TIMEZONE': tz, 'RETURN_AS_TIMEZONE_AWARE': False}) if parts else None
    e = dateparser.parse(parts[1], settings={'TIMEZONE': tz, 'RETURN_AS_TIMEZONE_AWARE': False}) if len(parts)>1 else None
    conf = 0.7 if (s and e) else 0.4 if (s or e) else 0.0
    return (s and s.date().isoformat()), (e and e.date().isoformat()), conf
