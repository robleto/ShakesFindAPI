from selectolax.parser import HTMLParser
from bs4 import BeautifulSoup
import re, datetime, json, asyncio
from ..utils import fetch_text

def _sel(node, selector):
    # support attribute selector like 'a@href'
    if not selector:
        return None
    if '@' in selector:
        css, attr = selector.split('@', 1)
        el = node.css_first(css)
        return (el and el.attributes.get(attr)) or None
    el = node.css_first(selector)
    return (el and el.text(strip=True)) or None

DATE_RANGE_RX = re.compile(r"(?i)\b([A-Z]{3,9}\.?(?:\s+\d{1,2})?)\s*[–-]\s*([A-Z]{3,9}\.?(?:\s+\d{1,2})?),?\s*(\d{4})")
SINGLE_MONTH_RANGE_RX = re.compile(r"(?i)\b([A-Z]{3,9})\s+(\d{1,2})\s*[–-]\s*(\d{1,2}),?\s*(\d{4})")

MONTHS = {m.upper(): i for i, m in enumerate(['January','February','March','April','May','June','July','August','September','October','November','December'], start=1)}

def _parse_date_range(text: str):
    if not text:
        return None, None
    # Pattern: MARCH 19 – APRIL 5, 2026
    m = DATE_RANGE_RX.search(text)
    if m:
        m1, m2, year = m.groups()
        # m1 may include month + day or just month
        def split_md(token):
            parts = token.strip().split()
            if len(parts)==2:
                return parts[0], parts[1]
            return parts[0], None
        mo1, d1 = split_md(m1)
        mo2, d2 = split_md(m2)
        if d1 and d2:
            try:
                s = datetime.date(int(year), MONTHS[mo1.strip('.').upper()], int(d1))
                e = datetime.date(int(year), MONTHS[mo2.strip('.').upper()], int(d2))
                return s.isoformat(), e.isoformat()
            except Exception:
                return None, None
    # Pattern: MARCH 19 – 25, 2026 (single month range)
    m = SINGLE_MONTH_RANGE_RX.search(text)
    if m:
        month, d1, d2, year = m.groups()
        try:
            s = datetime.date(int(year), MONTHS[month.strip('.').upper()], int(d1))
            e = datetime.date(int(year), MONTHS[month.strip('.').upper()], int(d2))
            return s.isoformat(), e.isoformat()
        except Exception:
            return None, None
    return None, None

def _known_stages(company: dict):
    # Allow comma or newline separated stage names in config under 'Stages'
    raw = company.get('Stages') or company.get('Stage List') or ''
    if not raw:
        return []
    parts = [p.strip() for p in re.split(r'[\n,]+', raw) if p.strip()]
    return parts

def _extract_stage(text: str, company: dict):
    if not text:
        return None
    # First: explicit configured stages
    stages = _known_stages(company)
    for st in stages:
        # match whole words ignoring case
        if re.search(rf"\b{re.escape(st)}\b", text, re.I):
            return st
    # Fallback generic pattern like "Something Stage" or "Mainstage"
    m = re.search(r"([A-Z][A-Za-z]*(?:\s+[A-Z][A-Za-z]*)*\s+Stage)\b", text)
    if m:
        return m.group(1)
    # Also capture Mainstage as a single token
    m2 = re.search(r"\b(Mainstage)\b", text, re.I)
    if m2:
        return m2.group(1).title()
    return None

SHORT_RANGE_RX = re.compile(r"^(?P<mon>[A-Z][a-z]{2,8})\s+(?P<d1>\d{1,2})\s*[–-]\s*(?P<d2>\d{1,2})$")

def _infer_year_short_range(text: str, today: datetime.date):
    if not text:
        return None
    m = SHORT_RANGE_RX.search(text.strip())
    if not m:
        return None
    mon = m.group('mon')
    if mon.upper()[:3] not in MONTHS:
        return None
    # assume current year unless month already passed by > 2 months and we are early in year
    year = today.year
    mon_num = MONTHS[[k for k in MONTHS if k.startswith(mon.upper()[:3])][0]]
    if today.month < 3 and mon_num > 10:  # season straddling year (e.g., Dec while current Jan)
        year = today.year - 1
    return f"{text} {year}"

async def extract_events_from_html_async(html: str, company: dict):
    list_sel = company.get('HTML List Selector')
    fmap_json = company.get('HTML Field Map') or '{}'
    try:
        fmap = json.loads(fmap_json)
    except Exception:
        fmap = {}

    detail_links_sel = None
    detail_map = {}
    html_cfg = company.get('html') or {}
    # new style config inside registry.yaml path: company['html']['detail_links'] etc.
    if isinstance(html_cfg, dict):
        detail_links_sel = html_cfg.get('detail_links')
        detail_map = (html_cfg.get('detail') or {}).get('fields', {}) if html_cfg.get('detail') else {}
    base_results = []
    inline_detail = False
    if isinstance(html_cfg, dict) and html_cfg.get('inline_detail') is True:
        inline_detail = True
    # also honor top-level company flag
    if company.get('inline_detail'):
        inline_detail = True
    if not list_sel or not fmap:
        # fallback: collect rough base results but do NOT return; allow detail_links crawl
        soup = BeautifulSoup(html, 'html.parser')
        candidates = soup.select('article, figure, .event, .show, .production, li')
        fmap_guess = {'title': 'h1, h2, h3, figcaption h1', 'dates': '.date, .dates, figcaption .prod-dates', 'url': 'a@href', 'venue': '.venue'}
        for c in candidates[:40]:
            node = HTMLParser(str(c))
            title = _sel(node, fmap_guess['title'])
            if title:
                base_results.append({'title': title, 'dates_text': _sel(node, fmap_guess['dates']), 'url': _sel(node, fmap_guess['url']), 'venue': _sel(node, fmap_guess['venue'])})
    else:
        tree = HTMLParser(html)
        cards = tree.css(list_sel)
        if len(cards) == 0:
            print(f"[DEBUG] list selector '{list_sel}' matched 0 nodes")
        else:
            print(f"[DEBUG] list selector '{list_sel}' matched {len(cards)} nodes")
            try:
                preview = cards[0].html[:200].replace('\n',' ')
                print(f"[DEBUG] first card preview: {preview}...")
            except Exception:
                pass
        results = []
        for card in cards:
            title = _sel(card, fmap.get('title', ''))
            dates_block = _sel(card, fmap.get('dates', ''))
            dates_text = None
            if dates_block:
                spaced = re.sub(r"(?P<m>[A-Z]{3,9})(\d)", lambda m: m.group('m')+" "+m.group(2), dates_block)
                boundary = re.search(r"(\d{4})(.*)$", spaced)
                if boundary:
                    year_idx = boundary.start(1) + 4
                    by_pos = spaced.find('By ', year_idx)
                    if by_pos != -1 and by_pos - year_idx < 40:
                        spaced = spaced[:by_pos]
                dates_text = spaced.strip()[:140]
            start_date, end_date = _parse_date_range(dates_text or dates_block or '')
            description = None
            try:
                soup = BeautifulSoup(card.html, 'html.parser')
                ps = soup.find_all('p')
                venue_val = None
                if ps:
                    if len(ps) > 1:
                        description = ' '.join(p.get_text(strip=True) for p in ps[1:])[:1000]
                    first_p = ps[0].get_text(" ", strip=True)
                    venue_val = _extract_stage(first_p, company)
                if not venue_val:
                    venue_val = _extract_stage(soup.get_text(" ", strip=True)[:300], company)
            except Exception:
                venue_val = None
            results.append({
                'title': title,
                'dates_text': dates_text,
                'start_date': start_date,
                'end_date': end_date,
                'description': description,
                'url': _sel(card, fmap.get('url', '')),
                'venue': _sel(card, fmap.get('venue', '')) or venue_val,
            })
        base_results.extend([r for r in results if r.get('title')])

    tree = HTMLParser(html)
    cards = tree.css(list_sel)
    if len(cards) == 0:
        print(f"[DEBUG] list selector '{list_sel}' matched 0 nodes")
    else:
        print(f"[DEBUG] list selector '{list_sel}' matched {len(cards)} nodes")
        # show snippet of first card for debugging selectors
        try:
            preview = cards[0].html[:200].replace('\n',' ')
            print(f"[DEBUG] first card preview: {preview}...")
        except Exception:
            pass
    results = []
    for card in cards:
        title = _sel(card, fmap.get('title', ''))
        dates_block = _sel(card, fmap.get('dates', ''))
        # Attempt to isolate first paragraph or line containing a month for cleaner dates_text
        dates_text = None
        if dates_block:
            spaced = re.sub(r"(?P<m>[A-Z]{3,9})(\d)", lambda m: m.group('m')+" "+m.group(2), dates_block)
            # Keep only up to first 'By ' sentence boundary after a year to avoid swallowing description
            boundary = re.search(r"(\d{4})(.*)$", spaced)
            if boundary:
                year_idx = boundary.start(1) + 4
                # Trim after year if a 'By ' appears soon after
                by_pos = spaced.find('By ', year_idx)
                if by_pos != -1 and by_pos - year_idx < 40:
                    spaced = spaced[:by_pos]
            dates_text = spaced.strip()[:140]
        start_date, end_date = _parse_date_range(dates_text or dates_block or '')
        # Attempt to split out description (after first strong or after first period following date line)
        description = None
        try:
            soup = BeautifulSoup(card.html, 'html.parser')
            ps = soup.find_all('p')
            venue_val = None
            if ps:
                if len(ps) > 1:
                    description = ' '.join(p.get_text(strip=True) for p in ps[1:])[:1000]
                first_p = ps[0].get_text(" ", strip=True)
                venue_val = _extract_stage(first_p, company)
            # If not found, attempt within full card text
            if not venue_val:
                venue_val = _extract_stage(soup.get_text(" ", strip=True)[:300], company)
        except Exception:
            venue_val = None
        results.append({
            'title': title,
            'dates_text': dates_text,
            'start_date': start_date,
            'end_date': end_date,
            'description': description,
            'url': _sel(card, fmap.get('url', '')),
            'venue': _sel(card, fmap.get('venue', '')) or venue_val,
        })
    # base_results already built above
    # Inline detail fallback: directly parse figcaption blocks for title & dates if configured
    if inline_detail:
        soup = BeautifulSoup(html, 'html.parser')
        figs = soup.select('figcaption')
        for fc in figs:
            title_el = fc.select_one('h1, h2, h3')
            dates_el = fc.select_one('.prod-dates, .dates, .date')
            href_el = fc.select_one('a.buy-tickets-button')
            title = title_el.get_text(strip=True) if title_el else None
            dates_text = dates_el.get_text(strip=True) if dates_el else None
            if dates_text and re.search(r"\d{4}", dates_text) is None:
                inferred = _infer_year_short_range(dates_text, datetime.date.today())
                if inferred:
                    dates_text = inferred
            start_date, end_date = _parse_date_range(dates_text or '')
            base_results.append({
                'title': title,
                'dates_text': dates_text,
                'start_date': start_date,
                'end_date': end_date,
                'url': href_el['href'] if href_el and href_el.has_attr('href') else None,
                'venue': None
            })

    # If detail crawling specified, visit each unique URL (relative allowed) and merge fields
    if detail_links_sel and detail_map:
        seen = set()
        enriched = []
        tree = HTMLParser(html)
        detail_nodes = tree.css(detail_links_sel) or []
        tasks = []
        url_map = {}
        from urllib.parse import urljoin
        base_url = company.get('Productions URL') or company.get('Homepage URL') or ''
        for dn in detail_nodes:
            href = dn.attributes.get('href') if hasattr(dn, 'attributes') else None
            if not href:
                a = dn.css_first('a')
                if a:
                    href = a.attributes.get('href')
            if not href:
                continue
            full = urljoin(base_url, href)
            if full in seen:
                continue
            seen.add(full)
            url_map[full] = dn
            tasks.append(fetch_text(full))
        pages = await asyncio.gather(*[fetch_text(u) for u in seen], return_exceptions=True) if seen else []
        for page_html, page_url in zip(pages, seen):
            if isinstance(page_html, Exception):
                continue
            ptree = HTMLParser(page_html)
            title = _sel(ptree, detail_map.get('title')) or None
            dates_text = _sel(ptree, detail_map.get('dates')) or None
            if dates_text and re.search(r"\d{4}", dates_text) is None:
                inferred = _infer_year_short_range(dates_text, datetime.date.today())
                if inferred:
                    dates_text = inferred
            start_date, end_date = _parse_date_range(dates_text or '')
            enriched.append({
                'title': title,
                'dates_text': dates_text,
                'start_date': start_date,
                'end_date': end_date,
                'url': page_url,
                'venue': _sel(ptree, detail_map.get('venue',''))
            })
        # prefer enriched detail results if they have start or end date
        detail_titles = {e['title'] for e in enriched if e.get('title')}
        # merge base results lacking dates with enriched
        merged = []
        for b in base_results:
            if b['title'] in detail_titles:
                # find enriched entry
                match = next((e for e in enriched if e['title']==b['title']), None)
                if match:
                    merged.append({**b, **{k:v for k,v in match.items() if v}})
            else:
                merged.append(b)
        # add any enriched not already included
        for e in enriched:
            if e.get('title') and e['title'] not in {m['title'] for m in merged}:
                merged.append(e)
        return merged
    return base_results

# Backwards compatibility wrapper
def extract_events_from_html(html: str, company: dict):
    try:
        loop = asyncio.get_running_loop()
        # If already running (our main scraper loop), schedule and wait
        return loop.create_task(extract_events_from_html_async(html, company))  # caller isn't awaiting -> adjust caller
    except RuntimeError:
        # No running loop; create temporary
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(extract_events_from_html_async(html, company))
        finally:
            loop.close()
