import os, asyncio, hashlib, json, pathlib
from dotenv import load_dotenv
from db.notion_client import NotionDB
from scraper.extractors.jsonld import extract_events_from_jsonld
from scraper.extractors.html import extract_events_from_html
from scraper.normalize import normalize_event, parse_dates
from scraper.resolve import resolve_play, match_shakespeare_local
from scraper.utils import fetch_text, now_utc
from registry import load_registry
from scraper.staleness import analyze_staleness
from writers.file_export import export_data

load_dotenv()

def _strategy_enabled(company, name):
    strat = company.get('Scrape Strategy') or company.get('strategy') or company.get('Strategy')
    if not strat:
        return True
    if isinstance(strat, str):
        strat = [s.strip() for s in strat.split(',')]
    return name in strat

DEBUG = os.getenv('SF_DEBUG') == '1'

async def process_company(notion, company, local_only=False, debug: bool=False):
    if company.get('Status') == 'paused':
        return []
    url = company.get('Productions URL') or company.get('Homepage URL')
    if not url:
        return []
    offline_html_path = company.get('offline_html') or company.get('Offline HTML')
    offline_detail_dir = company.get('offline_detail_dir') or company.get('Offline Detail Dir')
    if company.get('id') == 'sta' and company.get('no_network') and company.get('inline_detail'):
        from scraper.offline_tavern import load_offline_tavern_events
        return load_offline_tavern_events(company)
    html = None
    if company.get('no_network') and offline_html_path and os.path.exists(offline_html_path):
        html = pathlib.Path(offline_html_path).read_text(encoding='utf-8')
        print(f"[OFFLINE] Bypassed network; loaded {offline_html_path}")
    else:
        try:
            html = await fetch_text(url, allow_heavy=not company.get('no_network'))
        except Exception as e:
            print(f"[ERR] fetch {company.get('Name')} {url}: {e}")
            if offline_html_path and os.path.exists(offline_html_path):
                try:
                    html = pathlib.Path(offline_html_path).read_text(encoding='utf-8')
                    print(f"[OFFLINE] Loaded snapshot {offline_html_path}")
                except Exception as se:
                    print(f"[ERR] offline snapshot read failed {offline_html_path}: {se}")
            else:
                return []

    events = []
    if _strategy_enabled(company, 'jsonld'):
        events = extract_events_from_jsonld(html, base_url=url)
    if not events and _strategy_enabled(company, 'html'):
        inline_detail = company.get('inline_detail')
        # Fast path for offline + inline_detail: parse figcaptions directly here to avoid heavier extractor
        if company.get('no_network') and inline_detail:
            from bs4 import BeautifulSoup
            import re, datetime
            soup = BeautifulSoup(html, 'html.parser')
            shows = []
            for fc in soup.select('figcaption'):
                title_el = fc.select_one('h1,h2,h3')
                dates_el = fc.select_one('.prod-dates,.dates,.date')
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                dates_text = dates_el.get_text(strip=True) if dates_el else None
                if dates_text and not re.search(r'\d{4}', dates_text):
                    # append current year
                    dates_text = f"{dates_text} {datetime.date.today().year}"
                shows.append({'title': title, 'dates_text': dates_text, 'url': None, 'venue': None})
            events = shows
        else:
            maybe = extract_events_from_html(html, company)
            if asyncio.isfuture(maybe):
                events = await maybe
            else:
                events = maybe
        # If still empty and offline detail dir provided, try parsing each detail file as its own page
        if not events and offline_detail_dir and os.path.isdir(offline_detail_dir):
            detail_events = []
            for f in pathlib.Path(offline_detail_dir).glob('*.html'):
                try:
                    page_html = f.read_text(encoding='utf-8')
                except Exception:
                    continue
                # Minimal reuse: create pseudo company clone with single-page html selectors
                # We rely on existing detail selectors (registry) so push through extractor again
                # by simulating list omission but detail map active
                sub = extract_events_from_html(page_html, company)
                if asyncio.isfuture(sub):
                    sub = await sub
                detail_events.extend(sub)
            # de-duplicate by title
            seen_titles = set()
            merged = []
            for e in detail_events:
                t = e.get('title')
                if t and t not in seen_titles:
                    seen_titles.add(t)
                    merged.append(e)
            if merged:
                print(f"[OFFLINE] Added {len(merged)} events from offline detail snapshots")
                events = merged
    if not events and (debug or DEBUG):
        print(f"[WARN] no events parsed for {company.get('Name')} ({company.get('id')})")

    tz = company.get('Timezone') or os.getenv('TIMEZONE_DEFAULT', 'UTC')
    rows = []
    for e in events:
        clean = normalize_event(e, tz)
        start, end, date_conf = parse_dates(
            clean.get('dates_text'), tz, clean.get('start_date'), clean.get('end_date')
        )
        title_display = clean.get('title')
        venue = clean.get('venue')
        show_url = clean.get('url')
        source_hash = hashlib.sha1(
            f"{company['id']}|{title_display}|{start}|{end}|{venue}".encode('utf-8')
        ).hexdigest()

        if notion and not local_only:
            play_id, confidence = resolve_play(title_display, notion)
            canonical_title = None
        else:
            m = match_shakespeare_local(title_display)
            play_id = None
            confidence = m['confidence']
            canonical_title = m['canonical_title']

        if (not start or not end) and (debug or DEBUG):
            print(
                f"[DATE?] Missing start/end for '{title_display}' raw='{clean.get('dates_text')}'"
            )
        rows.append(
            {
                'company_id': company['id'],
                'company_name': company.get('Name'),
                'title_display': title_display,
                'canonical_title': canonical_title,
                'is_shakespeare': bool(canonical_title),
                'start_date': start,
                'end_date': end,
                'venue': venue,
                'show_url': show_url,
                'source_page': url,
                'source_hash': source_hash,
                'match_confidence': confidence,
                'raw_dates_text': clean.get('dates_text'),
                'date_confidence': date_conf,
                'fetched_at_utc': now_utc().isoformat(),
                'play_id': play_id,
            }
        )
    return rows

async def scrape_all(registry_path=None, notion_enabled=True, debug: bool=False, only_ids=None):
    notion = None
    companies = []
    if registry_path:
        companies.extend(load_registry(registry_path))
    if notion_enabled:
        try:
            notion = NotionDB()
            companies.extend(notion.list_companies())
        except KeyError:
            if not companies:
                print("No Notion credentials; registry only mode.")
    uniq_map = {c['id']: c for c in companies}
    if only_ids:
        subset = {}
        for oid in only_ids:
            if oid in uniq_map:
                subset[oid] = uniq_map[oid]
        uniq = subset.values()
    else:
        uniq = uniq_map.values()
    results = []
    tavern_company = None
    for c in uniq:
        if c.get('id') == 'sta':
            tavern_company = c
            continue  # skip for now; we'll append offline
        rows = await process_company(
            notion if notion_enabled else None,
            c,
            local_only=not notion_enabled,
            debug=debug
        )
        stale_data = analyze_staleness(c, rows)
        if stale_data['stale']:
            print(f"[STALE] {c.get('Name')} reasons={','.join(stale_data['reasons'])}")
        results.append({
            'company': {
                'id': c['id'],
                'name': c.get('Name'),
                'url': c.get('Productions URL') or c.get('Homepage URL')
            },
            'events': rows,
            'meta': stale_data
        })
    # Append offline tavern events at end
    if tavern_company and tavern_company.get('no_network'):
        try:
            from scraper.offline_tavern import load_offline_tavern_events
            tavern_rows = load_offline_tavern_events(tavern_company)
            stale_data = analyze_staleness(tavern_company, tavern_rows)
            results.append({
                'company': {
                    'id': tavern_company['id'],
                    'name': tavern_company.get('Name'),
                    'url': tavern_company.get('Productions URL') or tavern_company.get('Homepage URL')
                },
                'events': tavern_rows,
                'meta': stale_data
            })
        except Exception as e:
            print(f"[STA-OFFLINE-MERGE-ERR] {e}")
    return results

async def main(registry_path=None, notion_enabled=True, export_path=None, export_fmt='json', pretty=False, debug=False, stale_report_path=None, only_ids=None):
    all_results = await scrape_all(registry_path=registry_path, notion_enabled=notion_enabled, debug=debug, only_ids=only_ids)
    if export_path:
        # compute summary
        total_events = sum(len(c['events']) for c in all_results)
        total_shakes = sum(sum(1 for e in c['events'] if e.get('is_shakespeare')) for c in all_results)
        stale_companies = [c for c in all_results if c.get('meta', {}).get('stale')]
        stale_count = len(stale_companies)
        # severity weighting
        sev_weights = {'high':3,'medium':2,'low':1,None:0}
        sev_counts = {'high':0,'medium':0,'low':0}
        weighted_total = 0
        for c in stale_companies:
            sev = c.get('meta', {}).get('severity')
            if sev in sev_counts:
                sev_counts[sev] += 1
            weighted_total += sev_weights.get(sev, 0)
        summary = {
            'total_events': total_events,
            'shakespeare_events': total_shakes,
            'stale_companies': stale_count,
            'stale_severity_counts': sev_counts,
            'stale_severity_weighted': weighted_total
        }
        export_data({'companies': all_results, '_summary': summary}, export_path, fmt=export_fmt, pretty=pretty)
        print(f"[OUT] Wrote {export_path} (events={total_events}, shakespeare={total_shakes}, stale_companies={stale_count}, severity_weight={weighted_total})")
        if stale_report_path:
            stale_only = [
                {
                    'company': c['company'],
                    'reasons': c['meta'].get('reasons'),
                    'severity': c['meta'].get('severity'),
                    'info': c['meta'].get('info')
                } for c in all_results if c.get('meta', {}).get('stale')
            ]
            payload = {
                'generated_at': now_utc().isoformat(),
                'count': len(stale_only),
                'severity_counts': sev_counts,
                'severity_weighted': weighted_total,
                'stale': stale_only
            }
            p = pathlib.Path(stale_report_path)
            if p.suffix.lower() != '.json':
                p = p.with_suffix('.json')
            if pretty:
                p.write_text(json.dumps(payload, indent=2), encoding='utf-8')
            else:
                p.write_text(json.dumps(payload), encoding='utf-8')
            print(f"[OUT] Wrote stale report {p} (count={len(stale_only)})")

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--registry', help='Path to registry YAML')
    parser.add_argument('--no-notion', action='store_true')
    parser.add_argument('--export', help='Output file path (json or yaml)')
    parser.add_argument('--format', default='json', choices=['json','yaml'])
    parser.add_argument('--pretty', action='store_true')
    parser.add_argument('--debug', action='store_true')
    parser.add_argument('--stale-report', help='Optional path to write stale companies report JSON')
    parser.add_argument('--only', help='Comma-separated company IDs to process')
    args = parser.parse_args()
    only_ids = [s.strip() for s in args.only.split(',')] if args.only else None
    asyncio.run(main(
        registry_path=args.registry,
        notion_enabled=not args.no_notion,
        export_path=args.export,
        export_fmt=args.format,
        pretty=args.pretty,
        debug=args.debug,
        stale_report_path=args.stale_report,
        only_ids=only_ids
    ))
