import asyncio, time
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from typing import Optional
from main import scrape_all

app = FastAPI(title="ShakesFind API", version="0.1.0")

_last_result = {"companies": [], "generated_at": None}
_last_duration = None
_running = False

async def _do_scrape(registry_path: Optional[str], notion_enabled: bool, force: bool=False):
    global _last_result, _last_duration, _running
    if _running and not force:
        return False  # already running
    _running = True
    t0 = time.time()
    try:
        data = await scrape_all(registry_path=registry_path, notion_enabled=notion_enabled)
        _last_duration = time.time() - t0
        _last_result = {"companies": data, "generated_at": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
    finally:
        _running = False
    return True

@app.get('/health')
async def health():
    return {
        "status": "ok",
        "generated_at": _last_result["generated_at"],
        "companies": len(_last_result["companies"]),
        "running": _running,
        "last_duration_sec": _last_duration
    }

@app.post('/scrape')
@app.get('/scrape')
async def trigger_scrape(registry: Optional[str] = None, notion: bool = False, force: bool = False):
    started = await _do_scrape(registry, notion, force=force)
    return {"started": started, "running": _running, "forced": force}

@app.get('/companies')
async def list_companies():
    return [c['company'] for c in _last_result['companies']]

@app.get('/productions')
async def list_productions(play: Optional[str] = None, company: Optional[str] = None):
    events = []
    for c in _last_result['companies']:
        if company and c['company']['id'] != company:
            continue
        for e in c['events']:
            if play and (e.get('canonical_title') or '').lower().replace(' ', '') != play.replace(' ', '').lower():
                continue
            events.append({**e, 'company': c['company']})
    return events

@app.get('/summary')
async def summary():
    companies = _last_result.get('companies', [])
    total_events = sum(len(c['events']) for c in companies)
    total_shakes = sum(sum(1 for e in c['events'] if e.get('is_shakespeare')) for c in companies)
    return {
        'generated_at': _last_result.get('generated_at'),
        'total_companies': len(companies),
        'total_events': total_events,
        'shakespeare_events': total_shakes,
        'ratio': (total_shakes / total_events) if total_events else 0.0
    }

# Auto initial scrape on startup (registry default: registry.sample.yaml if present)
@app.on_event('startup')
async def startup_scrape():
    try:
        await _do_scrape('registry.sample.yaml', notion_enabled=False)
    except Exception:
        pass

@app.get('/')
async def root():
    return JSONResponse({"message": "ShakesFind API", "endpoints": ["/health", "/companies", "/productions", "/scrape"]})
