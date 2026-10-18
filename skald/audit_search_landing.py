"""The second count of people from search engines by engine and landing page
(day kind `search_landing`, search_landing.py).

Registered in audit_more.RECOUNTS. For every people visit that read a page
and that the audit's own labels (audit_labels.py) call "Search engine", the
audit's first page line is read again here, with rules written apart from
search_landing.py and campaigns.py:

  paid     the landing address's query holds one of classify.CLICK_ID_PARAMS
           with a value (parse_qsl)
  Google   else the referrer's host (urlsplit, no "www.") is a google.<tld>
           search domain - the last label two or three letters, or "com" and
           a country, or "co" and a country - or Google's Android search app
  Bing     else the host is bing.com or under it
  Other    anything else

The landing path is the audit's own label. Only classify.py's names are shared.
"""
from __future__ import annotations

from collections import Counter
from urllib.parse import parse_qsl, urlsplit

from .classify import CLICK_ID_PARAMS

SOURCE = "Search engine"
NAMES = ("Google", "Bing", "Other", "Paid")
OTHER = "(all others)"


def _host(referrer: str) -> str:
    if not referrer:
        return ""
    try:
        host = urlsplit(referrer if "//" in referrer else "//" + referrer).hostname or ""
    except ValueError:
        return ""
    host = host.lower().rstrip(".")
    return host[4:] if host.startswith("www.") else host


def _googles(host: str) -> bool:
    if host == "com.google.android.googlequicksearchbox":
        return True
    labels = host.split(".")
    if "google" not in labels:
        return False
    tail = labels[labels.index("google") + 1:]
    if len(tail) == 1:
        return tail[0].isalpha() and len(tail[0]) in (2, 3)
    if len(tail) == 2:
        return tail[0] in ("com", "co") and tail[1].isalpha() and len(tail[1]) == 2
    return False


def name_of(url: str, referrer: str) -> str:
    query = url.split("?", 1)[1] if "?" in url else ""
    try:
        pairs = parse_qsl(query)[:60]
    except ValueError:
        pairs = []
    if any(k.lower() in CLICK_ID_PARAMS and v for k, v in pairs):
        return "Paid"
    host = _host(referrer)
    if _googles(host):
        return "Google"
    if host == "bing.com" or host.endswith(".bing.com"):
        return "Bing"
    return "Other"


class Recount:
    def __init__(self, config, day, tz, own) -> None:
        self.names: Counter = Counter()
        self.pages = {"Google": Counter(), "Bing": Counter()}

    def visit(self, lines, is_page, labels) -> None:
        if labels is None or labels.get("source") != SOURCE:
            return
        first = next((x for x in lines if is_page(x)), None)
        if first is None:
            return
        name = name_of(first.url, first.referrer)
        self.names[name] += 1
        if name in self.pages:
            self.pages[name][labels["landing"]] += 1

    def compare(self, stored, same, problems) -> None:
        blob = stored.get("search_landing")
        if blob is None:
            return
        same("search_landing: visits", int(blob.get("visits", 0)), sum(self.names.values()))
        kept = blob.get("engines") or {}
        for name in NAMES:
            same(f"search_landing: {name}", int(kept.get(name, 0)), self.names[name])
        for name, counted in self.pages.items():
            pages = {k: int(v) for k, v in ((blob.get("pages") or {}).get(name) or {}).items()}
            for path in sorted(k for k in pages if k != OTHER):
                same(f"search_landing: {name} on {path}", pages[path], counted.get(path, 0))
            rest = sum(counted.values()) - sum(counted.get(k, 0) for k in pages if k != OTHER)
            same(f"search_landing: {name} on {OTHER}", pages.get(OTHER, 0), rest)
