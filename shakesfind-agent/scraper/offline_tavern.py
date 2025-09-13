import pathlib, re, datetime as _dt, hashlib
from bs4 import BeautifulSoup
from scraper.normalize import normalize_event, parse_dates as _parse_dates
from scraper.resolve import match_shakespeare_local
from scraper.utils import now_utc

__all__ = ["load_offline_tavern_events"]

def load_offline_tavern_events(company: dict):
    """Parse offline snapshot for Shakespeare Tavern (sta) returning normalized event rows.

    Expects keys: id, Name, offline_html, inline_detail.
    """
    offline_html_path = company.get('offline_html') or company.get('Offline HTML')
    if not offline_html_path or not pathlib.Path(offline_html_path).exists():
        return []
    html_data = pathlib.Path(offline_html_path).read_text(encoding='utf-8')
    soup = BeautifulSoup(html_data, 'html.parser')
    tz = company.get('Timezone') or 'UTC'
    shows = []
    range_rx = re.compile(r"^(?P<m1>[A-Za-z]{3,9})\s+(?P<d1>\d{1,2})\s*[–-]\s*(?:(?P<m2>[A-Za-z]{3,9})\s+)?(?P<d2>\d{1,2})\s+(?P<y>\d{4})$")
    months_full = ['January','February','March','April','May','June','July','August','September','October','November','December']
    mon_map = {m.lower(): i for i,m in enumerate(months_full, start=1)}
    mon_abbr = {m[:3].lower(): i for i,m in enumerate(months_full, start=1)}
    def parse_range_dates(dates_text: str):
        if not dates_text:
            return None, None
        m = range_rx.match(dates_text.strip())
        if not m:
            return None, None
        g = m.groupdict()
        def mon_to_num(token):
            if not token: return None
            tl = token.lower()
            return mon_map.get(tl) or mon_abbr.get(tl[:3])
        y = int(g['y'])
        m1 = mon_to_num(g['m1'])
        m2 = mon_to_num(g['m2']) or m1
        try:
            import datetime as _d
            s = _d.date(y, m1, int(g['d1']))
            e = _d.date(y, m2, int(g['d2']))
            return s.isoformat(), e.isoformat()
        except Exception:
            return None, None
    for fc in soup.select('figcaption'):
        title_el = fc.select_one('h1,h2,h3')
        dates_el = fc.select_one('.prod-dates,.dates,.date')
        if not title_el:
            continue
        title = title_el.get_text(strip=True)
        dates_text = dates_el.get_text(strip=True) if dates_el else None
        year = _dt.date.today().year
        if dates_text and not re.search(r'\d{4}', dates_text):
            dates_text = f"{dates_text} {year}"
        start_date, end_date = parse_range_dates(dates_text)
        shows.append({'title': title, 'dates_text': dates_text, 'start_date': start_date, 'end_date': end_date})
    rows = []
    for e in shows:
        clean = normalize_event(e, tz)
        start = e.get('start_date') or clean.get('start_date')
        end = e.get('end_date') or clean.get('end_date')
        date_conf = 'range_inferred'
        if not (start and end):
            ps, pe, date_conf = _parse_dates(clean.get('dates_text'), tz, start, end)
            start, end = ps, pe
        title_display = clean.get('title')
        m = match_shakespeare_local(title_display)
        source_hash = hashlib.sha1(f"{company['id']}|{title_display}|{start}|{end}|".encode('utf-8')).hexdigest()
        rows.append({
            'company_id': company['id'],
            'company_name': company.get('Name'),
            'title_display': title_display,
            'canonical_title': m['canonical_title'],
            'is_shakespeare': bool(m['canonical_title']),
            'start_date': start,
            'end_date': end,
            'venue': None,
            'show_url': None,
            'source_page': company.get('Productions URL') or company.get('Homepage URL'),
            'source_hash': source_hash,
            'match_confidence': m['confidence'],
            'raw_dates_text': clean.get('dates_text'),
            'date_confidence': date_conf,
            'fetched_at_utc': now_utc().isoformat(),
            'play_id': None,
        })
    return rows
