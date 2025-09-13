import re, datetime

SEASON_TOKENS = re.compile(r"(?i)\b(spring|summer|fall|autumn|winter|holiday|holidays)\b")
YEAR_RX = re.compile(r"(20\d{2})")
SEASON_NUMBER_RX = re.compile(r"Season[-_ ]?(\d{2,})", re.I)


SEVERITY_RULES = {
    'empty_page': 'high',
    'url_year_mismatch': 'high',
    'missing_new_season': 'high',
    'season_empty_old': 'high',
    'season_window_expired': 'medium',
    'season_number_empty': 'medium',
    'past_only': 'low',
}

def analyze_staleness(company: dict, events: list, today: datetime.date=None):
    """Return dict with stale flag, reasons, and info.
    Heuristics:
      - empty_page: zero events
      - past_only: all events ended before today
      - url_year_mismatch: URL contains year far in past (>1 year behind current)
      - season_window_expired: season/holiday token year expired
    """
    today = today or datetime.date.today()
    reasons = []
    info = {}
    url = company.get('Productions URL') or company.get('Homepage URL') or ''
    if not events:
        reasons.append('empty_page')
    # collect date stats
    dates = []
    for e in events:
        sd = e.get('start_date')
        ed = e.get('end_date') or sd
        try:
            if ed:
                dates.append(datetime.date.fromisoformat(ed))
        except Exception:
            pass
    if dates:
        max_end = max(dates)
        info['latest_end'] = max_end.isoformat()
        # past_only only if more than 30 days in the past
        if max_end < (today - datetime.timedelta(days=30)):
            reasons.append('past_only')
    # URL year mismatch
    years = [int(y) for y in YEAR_RX.findall(url)]
    this_year = today.year
    if years:
        uy = years[-1]
        info['url_year'] = uy
        # too far in past
        if uy < this_year - 1:
            reasons.append('url_year_mismatch')
        # upcoming-year expectation: if url year < current and no events OR past_only already flagged
        if not events and uy < this_year:
            reasons.append('missing_new_season')
    # season / holiday token
    if SEASON_TOKENS.search(url):
        info['season_token'] = True
        if years:
            uy = years[-1]
            if uy < this_year and today.month >= 3:
                reasons.append('season_window_expired')
            if not events and uy < this_year:
                reasons.append('season_empty_old')
        else:
            # No year; if past_only already flagged keep; else cannot assert
            pass
    # season numeric
    m = SEASON_NUMBER_RX.search(url)
    if m:
        info['season_number'] = int(m.group(1))
        if not events:
            reasons.append('season_number_empty')
    stale = bool(reasons)
    # pick highest severity among reasons
    severity_rank = {'low':1,'medium':2,'high':3}
    severity = None
    for r in reasons:
        sev = SEVERITY_RULES.get(r, 'low')
        if not severity or severity_rank[sev] > severity_rank[severity]:
            severity = sev
    return {'stale': stale, 'reasons': reasons, 'severity': severity, 'info': info}
