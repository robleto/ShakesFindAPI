import json, sys, datetime, re, pathlib
from bs4 import BeautifulSoup

SNAPSHOT = pathlib.Path('snapshots/sta/on-stage.html')
COMPANY_ID = 'sta'
COMPANY_NAME = 'Shakespeare Tavern Atlanta'

def infer_year(dates_text: str) -> str:
    if not dates_text:
        return dates_text
    if re.search(r'\d{4}', dates_text):
        return dates_text
    return f"{dates_text} {datetime.date.today().year}"

MONTHS = {m.lower(): i for i,m in enumerate(['January','February','March','April','May','June','July','August','September','October','November','December'], start=1)}
MON_ABBR = {m[:3].lower(): i for i,m in enumerate(['January','February','March','April','May','June','July','August','September','October','November','December'], start=1)}

RANGE_RX = re.compile(r"^(?P<m1>[A-Za-z]{3,9})\s+(?P<d1>\d{1,2})\s*[–-]\s*(?:(?P<m2>[A-Za-z]{3,9})\s+)?(?P<d2>\d{1,2})\s+(?P<y>\d{4})$")

def parse_range(dates_text: str):
    if not dates_text:
        return None, None
    m = RANGE_RX.match(dates_text.strip())
    if not m:
        return None, None
    g = m.groupdict()
    y = int(g['y'])
    def mon_to_num(token):
        if not token:
            return None
        tl = token.lower()
        return MONTHS.get(tl) or MON_ABBR.get(tl[:3])
    m1 = mon_to_num(g['m1'])
    m2 = mon_to_num(g['m2']) or m1
    try:
        s = datetime.date(y, m1, int(g['d1']))
        e = datetime.date(y, m2, int(g['d2']))
        return s.isoformat(), e.isoformat()
    except Exception:
        return None, None

def parse_figcaptions(html: str):
    soup = BeautifulSoup(html, 'html.parser')
    shows = []
    for fc in soup.select('figcaption'):
        title_el = fc.select_one('h1,h2,h3')
        if not title_el:
            continue
        title = title_el.get_text(strip=True)
        dates_el = fc.select_one('.prod-dates,.dates,.date')
        dates_text = infer_year(dates_el.get_text(strip=True) if dates_el else None)
        start_date = end_date = None
        if dates_text:
            start_date, end_date = parse_range(dates_text)
        shows.append({
            'company_id': COMPANY_ID,
            'company_name': COMPANY_NAME,
            'title': title,
            'dates_text': dates_text,
            'start_date': start_date,
            'end_date': end_date
        })
    return shows

def main():
    if not SNAPSHOT.exists():
        print(json.dumps({'error': 'snapshot_missing', 'path': str(SNAPSHOT)}))
        return
    html = SNAPSHOT.read_text(encoding='utf-8')
    shows = parse_figcaptions(html)
    print(json.dumps({
        'company_id': COMPANY_ID,
        'company_name': COMPANY_NAME,
        'count': len(shows),
        'productions': shows
    }, indent=2))

if __name__ == '__main__':
    main()
