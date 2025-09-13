import difflib, re
from shakespeare_plays import CANON_TITLES, ALIAS_TO_CANON

# Precompute token sets
_ws_re = re.compile(r"\s+")
_token_re = re.compile(r"[^\w']+")

_STOP_SUFFIX_RE = re.compile(r"(?:[:\-–—]\s*(an\s+adaptation|a\s+new.*|in\s+concert|live).*)$", re.I)
PREFIX_STRIP_RE = re.compile(r"^(?:william\s+)?shakespeare'?s[\s:\-–—]+", re.I)
PARENS_RE = re.compile(r"\([^)]*\)")

CANON_TOKEN_SETS = {title: set(t for t in _token_re.split(title.lower()) if t) for title in CANON_TITLES}

CORE_START_HINTS = [t.split()[0].lower() for t in CANON_TITLES]

def _core_title(raw: str) -> str:
    if not raw:
        return ""
    t = raw.strip()
    t = PARENS_RE.sub(" ", t)
    t = PREFIX_STRIP_RE.sub("", t)
    t = _STOP_SUFFIX_RE.sub("", t)
    # Split on colon/dash and keep left if it looks play-like
    for sep in (":", "—", "–", "-", " | "):
        if sep in t:
            left = t.split(sep, 1)[0].strip()
            if _looks_like_play(left):
                t = left
                break
    t = _ws_re.sub(" ", t).strip(" .:;,-–—").strip()
    return t

def _looks_like_play(fragment: str) -> bool:
    fl = fragment.lower()
    return any(fl.startswith(h) for h in CORE_START_HINTS)

def _tokenize(s: str):
    return [w for w in _token_re.split(s.lower()) if w]

def _subset_score(core_tokens, canon_tokens):
    if not core_tokens or not canon_tokens:
        return 0.0
    inter = core_tokens & canon_tokens
    if not inter:
        return 0.0
    coverage = len(inter) / len(canon_tokens)
    # Require majority of canonical tokens ( > 0.5 ) to even consider
    if coverage < 0.5:
        return 0.0
    noise_ratio = (len(core_tokens) - len(inter)) / max(1, len(canon_tokens))
    # Penalize heavy extra tokens (marketing phrases, names, etc.)
    if noise_ratio > 1.0:
        coverage *= 0.7
    if noise_ratio > 2.0:
        coverage *= 0.5
    return coverage

def match_shakespeare_local(title: str):
    if not title:
        return {"canonical_title": None, "confidence": 0.0}
    core = _core_title(title)
    core_low = core.lower()
    if core_low in ALIAS_TO_CANON:
        return {"canonical_title": ALIAS_TO_CANON[core_low], "confidence": 0.9}
    tokens_list = _tokenize(core)
    core_tokens = set(tokens_list)
    # Fast reject: if we have marketing / concert indicators and fewer than 2 Shakespeare tokens
    BAD_HINTS = {"concert","sings","tribute","unforgettable","legacy"}
    if BAD_HINTS & core_tokens:
        # Only proceed if at least 3 canonical title tokens for some play present
        rich_overlap = any(len(core_tokens & ctoks) >= 3 for ctoks in CANON_TOKEN_SETS.values())
        if not rich_overlap:
            return {"canonical_title": None, "confidence": 0.0}
    best = (None, 0.0)
    for canon, canon_tokens in CANON_TOKEN_SETS.items():
        score = _subset_score(core_tokens, canon_tokens)
        if score >= 0.6 and score > best[1]:
            best = (canon, score)
    if best[0]:
        conf = 0.9 if best[1] >= 0.95 else (0.87 if best[1] >= 0.8 else 0.85)
        return {"canonical_title": best[0], "confidence": conf}
    # Fuzzy: require token length similarity to avoid long marketing titles mapping to short play names
    fuzz = []
    if 1 <= len(tokens_list) <= 8:
        fuzz = difflib.get_close_matches(core, CANON_TITLES, n=1, cutoff=0.72)
    if fuzz:
        return {"canonical_title": fuzz[0], "confidence": 0.8}
    return {"canonical_title": None, "confidence": 0.0}

def resolve_play(title: str, notion):
    if not title:
        return None, 0.0
    # Try exact / alias via Notion first
    play = notion.find_play_by_title(title) if notion else None
    if play:
        return play['id'], 1.0
    play = notion.find_play_by_alias(title) if notion else None
    if play:
        return play['id'], 0.95
    local = match_shakespeare_local(title)
    if local['canonical_title'] and notion:
        p = notion.find_play_by_title(local['canonical_title'])
        if p:
            return p['id'], local['confidence']
    return None, 0.0
