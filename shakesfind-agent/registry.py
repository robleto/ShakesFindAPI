import json, pathlib, yaml

# Load YAML registry describing companies/sites.
# Returns list of company dicts shaped like Notion-derived rows used by scraper.

def load_registry(path: str):
    fp = pathlib.Path(path)
    if not fp.exists():
        raise FileNotFoundError(path)
    data = yaml.safe_load(fp.read_text(encoding="utf-8")) or []
    companies = []
    for entry in data:
        html_cfg = entry.get("html") or {}
        fields = html_cfg.get("fields") or {}
        companies.append({
            "id": entry.get("id"),
            "Name": entry.get("name"),
            "Homepage URL": entry.get("url"),
            "Productions URL": entry.get("url"),
            "Timezone": entry.get("timezone"),
            "HTML List Selector": html_cfg.get("list"),
            "HTML Field Map": json.dumps({
                k: v for k, v in {
                    "title": fields.get("title"),
                    "dates": fields.get("dates"),
                    "url": fields.get("url"),
                    "venue": fields.get("venue")
                }.items() if v
            }),
            "Scrape Strategy": entry.get("strategy") or [],
            "Status": entry.get("status") or "active",
            "inline_detail": html_cfg.get("inline_detail"),
            "offline_html": entry.get("offline_html"),
            "offline_detail_dir": entry.get("offline_detail_dir"),
            "no_network": entry.get("no_network"),
            "_source": "registry",
        })
    return companies
