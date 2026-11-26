"""One page's Google Search figures for Traffic > Pages, the page drawer
(SKALD-64): GET <page>/api/page-search?path=&days= (refresh_server.py).

Nothing new is counted: the figures are mcp/tools_search.figures' over the
stored `search_days` rows, the same the MCP's search_performance gives and
audit_search_pages.py recounts by its own SQL (each day's clicks and
impressions, the countries, the queries). Per answer:

  period   the last `days` days (7 to MAX_DAYS, default DEFAULT_DAYS) up to the
           newest day Search Console has stored, in Google's own days (Pacific
           Time); Google gives no figures for today and is two or three days
           late, so the drawer never shows "today" here
  days     each stored day: clicks, impressions, ctr, position, final; null
           figures on a day the page was not in that day's top list while the
           list was not complete (never 0: not known)
  totals   the sums over the days with figures, `totals_partial` when some
           days had none (`not_in_page_table`)
  before   the same number of days just before: totals only
  queries  the page's TOP_QUERIES largest queries (each day's top query-page
           pairs, summed); countries the page's largest countries
  address  the path the figures are for: the drawer's own, or, when Search
           Console has no row at all for it in the period, the same path with
           its closing "/" added or taken off, when that one has rows

{"connected": false} when Search Console has never stored a day for the site.
"""
from __future__ import annotations

from datetime import date, timedelta

DEFAULT_DAYS = 28
MAX_DAYS = 93
TOP_QUERIES = 25


def _newest(db, site: str) -> date | None:
    row = db.execute("SELECT MAX(day) FROM search_days WHERE site = ? AND engine = 'google' "
                     "AND kind = 'page'", (site,)).fetchone()
    return date.fromisoformat(row[0]) if row and row[0] else None


def _seen(got: dict) -> bool:
    return any(d.get("impressions") for d in got.get("days") or [])


def answer(db, site: str, path: str, days=DEFAULT_DAYS) -> dict:
    from ..mcp.tools_search import figures
    path = str(path or "").split("?", 1)[0].split("#", 1)[0]
    if not path.startswith("/") or len(path) > 2000:
        return {"ok": False, "error": "path is a page's path, starting with /"}
    try:
        days = max(7, min(MAX_DAYS, int(days)))
    except (TypeError, ValueError):
        days = DEFAULT_DAYS
    try:
        last = _newest(db, site)
    except Exception:                    # noqa: BLE001 - an older history: no table
        last = None
    if last is None:
        return {"ok": True, "connected": False, "path": path}
    first = last - timedelta(days=days - 1)
    got = figures(db, site, "google", path, first, last, TOP_QUERIES)
    address = path
    if not _seen(got) and path != "/":
        other = path[:-1] if path.endswith("/") else path + "/"
        twin = figures(db, site, "google", other, first, last, TOP_QUERIES)
        if _seen(twin):
            got, address = twin, other
    b_last = first - timedelta(days=1)
    before = figures(db, site, "google", address, b_last - timedelta(days=days - 1), b_last, 0)
    return {"ok": True, "connected": True, "engine": "google", "path": path,
            "address": address, "first": first.isoformat(), "last": last.isoformat(),
            "length": days, "days": got["days"], "totals": got.get("totals"),
            "totals_partial": got.get("totals_partial"),
            "not_in_page_table": got.get("not_in_page_table") or [],
            "missing_days": got.get("missing_days") or [],
            "provisional_days": got.get("provisional_days") or [],
            "queries": got.get("top_queries") or [], "countries": got.get("countries") or [],
            "countries_not_stored": got.get("countries_not_stored") or [],
            "index": got.get("index"),
            "before": {"first": (b_last - timedelta(days=days - 1)).isoformat(),
                       "last": b_last.isoformat(), "totals": before.get("totals"),
                       "totals_partial": before.get("totals_partial"),
                       "missing_days": before.get("missing_days") or []}}
