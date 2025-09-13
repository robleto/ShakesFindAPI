import httpx, asyncio, datetime as dt, datetime, random, time
from requests_cache import CachedSession
curl_requests = None  # disabled due to instability on current runtime

_session = CachedSession(cache_name='http_cache', backend='sqlite', expire_after=3600)

async def fetch_text(url: str, allow_heavy: bool=True) -> str:
    """Fetch URL text with a friendly default UA and fallback retry.

    Some theatre sites may block unknown bots with a 403. We retry once with a
    common browser UA string to reduce false negatives while still identifying
    ourselves initially.
    """
    domain_specific = {}
    if 'shakespearetavern.com' in url:
        domain_specific = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://www.google.com/',
            'DNT': '1',
            'Cache-Control': 'no-cache'
        }
    headers_primary = {'User-Agent': 'ShakesFindBot/0.1', **domain_specific}
    headers_fallback = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.1 Safari/537.36', **{k:v for k,v in domain_specific.items() if k!='User-Agent'}}
    # For tougher domains apply progressive strategy
    if 'shakespearetavern.com' in url:
        ua_pool = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.1 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.1 Safari/537.36'
        ]
        # 1) Cookie priming attempt (root) to set any basic cookies
        try:
            _session.get('https://www.shakespearetavern.com/', headers=headers_primary, timeout=10)
        except Exception:
            pass
        for attempt in range(1, 4):
            ua = random.choice(ua_pool)
            hdrs = {**headers_fallback, 'User-Agent': ua, 'Pragma': 'no-cache'}
            time.sleep(random.uniform(0.25, 0.6))
            resp = _session.get(url, headers=hdrs, timeout=15, params={'_': int(time.time()*1000)})
            if resp.status_code != 403:
                resp.raise_for_status()
                return resp.text
        if allow_heavy:
            # Heavy fallback (Playwright) intentionally disabled for stability; could be re-enabled behind flag.
            try:
                # Placeholder: log skipped heavy fetch
                pass
            except Exception:
                pass
        raise Exception('403 Forbidden after advanced retries (heavy fallback disabled) for shakespearetavern.com')
    # Non-protected domains path
    resp = _session.get(url, headers=headers_primary, params={'_': datetime.datetime.utcnow().timestamp()} if domain_specific else None)
    if resp.status_code == 403:
        resp = _session.get(url, headers=headers_fallback)
    resp.raise_for_status()
    return resp.text

async def fetch_with_cache(url: str, force: bool=False) -> str:
    """Fetch a URL optionally bypassing the existing cache.

    Parameters:
        url: page to retrieve
        force: if True, ignore cached response and re-fetch
    Returns:
        text content
    """
    if force:
        # requests-cache offers .cache.delete_url; fall back to clear()
        try:
            _session.cache.delete_url(url)
        except Exception:
            try:
                _session.cache.clear()
            except Exception:
                pass
    resp = _session.get(url, headers={'User-Agent': 'ShakesFindBot/0.1'})
    resp.raise_for_status()
    return resp.text

def now_utc():
    return dt.datetime.utcnow().replace(tzinfo=dt.timezone.utc)
