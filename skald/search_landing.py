"""People from search engines by engine and landing page: the day kind
`search_landing`, Skald's own side of the Search tab's cross-check.

Search Console counts clicks on Google's results; the log counts the visits
that arrived. To put them side by side, per day, from the day's journeys
(one per people visit), the visits whose source is "Search engine":

  visits   every such visit
  engines  {"Google", "Bing", "Other", "Paid"}: by the referring host (any
           google.<tld> search domain or Google's Android search app; bing.com),
           "Paid" when the landing address carries an ad click id (Search
           Console and Bing count unpaid results only), "Other" for every
           other engine and for a tagged link with no referrer
  pages    {"Google": {landing path: visits}, "Bing": {...}}: the TOP largest
           and "(all others)", each adding up to its engine's visits

The sums: engines add up to visits; each engine's pages add up to it.
Second count: audit_search_landing.py, from the raw lines with its own
host rules; it shares only classify.py's click-id names.
"""
from __future__ import annotations

import re
from collections import Counter

ENGINES = ("Google", "Bing", "Other", "Paid")
PAGED = ("Google", "Bing")
SOURCE = "Search engine"
TOP = 200
OTHER = "(all others)"
_GOOGLE = re.compile(r"(?:^|\.)google\.(?:com(?:\.[a-z]{2})?|co\.[a-z]{2}|[a-z]{2,3})$")
_GOOGLE_APP = "com.google.android.googlequicksearchbox"


def engine_of(j: dict) -> str:
    if j.get("paid"):
        return "Paid"
    host = str(j.get("ref_host") or "").lower()
    if host == _GOOGLE_APP or _GOOGLE.search(host):
        return "Google"
    if host == "bing.com" or host.endswith(".bing.com"):
        return "Bing"
    return "Other"


def _fold(paths: Counter) -> dict:
    ordered = sorted(paths.items(), key=lambda kv: (-kv[1], kv[0]))
    out = dict(ordered[:TOP])
    rest = sum(n for _, n in ordered[TOP:])
    if rest:
        out[OTHER] = rest
    return out


def finish(extras, totals, journeys, page_visits, readers_by_hour) -> dict | None:
    if journeys is None:
        return None
    engines = Counter({e: 0 for e in ENGINES})
    pages = {e: Counter() for e in PAGED}
    for j in journeys:
        if j.get("source") != SOURCE:
            continue
        engine = engine_of(j)
        engines[engine] += 1
        if engine in pages:
            pages[engine][str(j.get("landing") or "")] += 1
    return {"visits": sum(engines.values()), "engines": {e: int(engines[e]) for e in ENGINES},
            "pages": {e: _fold(pages[e]) for e in PAGED}}


def check(totals, blob, differs, problems) -> None:
    engines = blob.get("engines") or {}
    differs("search_landing: engines", sum(int(v) for v in engines.values()),
            int(blob.get("visits", 0)), "visits")
    for e in PAGED:
        differs(f"search_landing: {e} by landing page",
                sum(int(v) for v in ((blob.get("pages") or {}).get(e) or {}).values()),
                int(engines.get(e, 0)), "visits")
    by = getattr(getattr(totals, "visits", None), "source", None)
    if by is not None:
        differs("search_landing: visits", int(blob.get("visits", 0)), int(by.get(SOURCE, 0)),
                "visits")
