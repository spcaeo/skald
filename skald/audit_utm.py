"""The second count of campaign tag hygiene (day kind `utm_hygiene`).

Registered in audit_more.RECOUNTS. For every people visit that read a page,
the audit's own first page line is read again here: its query string with
urllib.parse.parse_qsl, its referrer with urlsplit, and these rules, written
apart from utm_hygiene.py and campaigns.py:

  a tag is one of utm_source, utm_medium, utm_campaign, utm_term,
  utm_content with something other than blanks in it;
  no medium      utm_source set, utm_medium not;
  unknown medium utm_medium, blanks squeezed and lower case, not in
                 classify.UTM_MEDIUMS;
  click id       one of classify.CLICK_ID_PARAMS with a value, and no tag;
  internal       a tag, and a referrer whose host (no "www.") is one of the
                 site's hosts (or the line's own host when none is set).

Only classify.py's name lists are shared. The visit's landing path is the
audit's own label (audit.py), never dimensions.py's.
"""
from __future__ import annotations

from collections import Counter
from urllib.parse import parse_qsl, urlsplit

from .classify import CLICK_ID_PARAMS, UTM_MEDIUMS

NAMES = ("source_no_medium", "unknown_medium", "click_id_no_tags", "internal_tags")
TAGS = ("utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content")
OTHER = "(all others)"


def _params(url: str) -> dict[str, str]:
    query = url.split("?", 1)[1] if "?" in url else ""
    try:
        pairs = parse_qsl(query)[:60]
    except ValueError:
        return {}
    got: dict[str, str] = {}
    for key, value in pairs:
        got[key.lower()] = value
    return got


def _referring_host(referrer: str) -> str:
    if not referrer:
        return ""
    try:
        host = urlsplit(referrer if "//" in referrer else "//" + referrer).hostname or ""
    except ValueError:
        return ""
    host = host.lower().rstrip(".")
    return host[4:] if host.startswith("www.") else host


def judge(url: str, referrer: str, own: set[str]) -> list[str]:
    """Which of NAMES one landing line shows."""
    q = _params(url)
    tags = {k: q[k] for k in TAGS if q.get(k, "").strip()}
    found = []
    if "utm_source" in tags and "utm_medium" not in tags:
        found.append("source_no_medium")
    if "utm_medium" in tags and " ".join(tags["utm_medium"].split()).lower()[:60] \
            not in UTM_MEDIUMS:
        found.append("unknown_medium")
    if not tags and any(q.get(k) for k in CLICK_ID_PARAMS):
        found.append("click_id_no_tags")
    host = _referring_host(referrer)
    if tags and host and (host in own or "www." + host in own):
        found.append("internal_tags")
    return found


class Recount:
    def __init__(self, config, day, tz, own) -> None:
        self.own = set(own or ())
        self.visits = 0
        self.counts: Counter = Counter()
        self.paths = {name: Counter() for name in NAMES}

    def visit(self, lines, is_page, labels) -> None:
        if labels is None:
            return
        first = next((x for x in lines if is_page(x)), None)
        if first is None:
            return
        self.visits += 1
        own = self.own or ({first.host.lower()} if first.host else set())
        for name in judge(first.url, first.referrer, own):
            self.counts[name] += 1
            self.paths[name][labels["landing"]] += 1

    def compare(self, stored, same, problems) -> None:
        blob = stored.get("utm_hygiene")
        if blob is None:
            return
        same("utm_hygiene: visits", int(blob.get("visits", 0)), self.visits)
        counts = blob.get("counts") or {}
        for name in NAMES:
            same(f"utm_hygiene: {name}", int(counts.get(name, 0)), self.counts[name])
            kept = {k: int(v) for k, v in ((blob.get("paths") or {}).get(name) or {}).items()}
            counted = self.paths[name]
            for path in sorted(k for k in kept if k != OTHER):
                same(f"utm_hygiene: {name} on {path}", kept[path], counted.get(path, 0))
            rest = sum(counted.values()) - sum(counted.get(k, 0) for k in kept if k != OTHER)
            same(f"utm_hygiene: {name} on {OTHER}", kept.get(OTHER, 0), rest)
