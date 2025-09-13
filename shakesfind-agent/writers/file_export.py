import json, pathlib, datetime as dt

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None


def _ensure_dir(path: str):
    p = pathlib.Path(path).expanduser().resolve()
    if p.parent and not p.parent.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
    return p

def export_data(data: dict, path: str, fmt: str = "json", pretty: bool = False):
    p = _ensure_dir(path)
    stamp = dt.datetime.utcnow().isoformat()
    data.setdefault("_meta", {})
    data["_meta"].update({
        "generated_at_utc": stamp,
        "record_count": sum(len(c.get("events", [])) for c in data.get("companies", [])),
        "shakespeare_events": sum(sum(1 for e in c.get('events', []) if e.get('is_shakespeare')) for c in data.get('companies', []))
    })
    fmt = fmt.lower()
    if fmt == "yaml":
        if yaml is None:
            raise RuntimeError("PyYAML not installed; cannot export yaml")
        with p.open("w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)
    else:
        with p.open("w", encoding="utf-8") as f:
            if pretty:
                json.dump(data, f, indent=2, ensure_ascii=False)
            else:
                json.dump(data, f, separators=(",", ":"), ensure_ascii=False)
    return str(p)
