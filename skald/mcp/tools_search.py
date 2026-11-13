"""The MCP tool for Search Console and Bing figures: search_performance (2.48).

It reads what the search sync stored in history (`search_days`, search/days.py):
the engine's own clicks, impressions, CTR and position, per day, for the whole
site or one page (a path), with the page's top queries, and (Search Console)
each page's index status from URL Inspection (`search_inspect`,
search/inspect.py). Nothing is asked of Google here and nothing is counted
anew: every figure is the engine's own, labelled so, never added to Skald's.

Unknown stays unknown. A day the sync has not stored is listed as missing. A
page's day is 0 only when that day's page table is complete (every page
Google gave is in it): Google gives no row for a page with no impressions.
When the table is not complete (more pages than the TOP_PAGES kept, or
clicks Google does not give by page) a page with no row is null, never 0.

audit_search_pages.py recounts the per-page figures by its own road.
"""
from __future__ import annotations

from datetime import date, timedelta

from .data import Refused
from .tools import SITE_ARG, schema, tool

ENGINES = ("google", "bing")
NAMES = {"google": "Search Console", "bing": "Bing Webmaster Tools"}
MAX_DAYS = 93
TOP_QUERIES = 10
TOP_PAGES = 20
TOP_COUNTRIES = 10
DAY = {"type": "string", "format": "date", "pattern": r"^\d{4}-\d{2}-\d{2}$"}


def _ctr(clicks, shown):
    return round(clicks / shown, 4) if shown else None


def _num(n):
    return int(n) if float(n).is_integer() else round(float(n), 2)


def _add(acc: list, c, i, p) -> None:
    """acc = [clicks, impressions, position x impressions, impressions with a position]."""
    acc[0] += c
    acc[1] += i
    if p is not None and i:
        acc[2] += p * i
        acc[3] += i


def _figs(acc: list) -> dict:
    return {"clicks": _num(acc[0]), "impressions": _num(acc[1]), "ctr": _ctr(acc[0], acc[1]),
            "position": round(acc[2] / acc[3], 2) if acc[3] else None}


def page_path(key: str) -> str:
    from ..search.props import path_of
    return path_of(key)


def norm_path(given) -> str | None:
    if given in (None, ""):
        return None
    if not isinstance(given, str) or not given.startswith("/") or len(given) > 2000:
        raise Refused("`path` is a page's path, starting with /, e.g. /pricing/.")
    return given.split("?", 1)[0].split("#", 1)[0] or "/"


def page_day(blob: dict | None, path: str) -> dict | None:
    """One page's figures on one day from that day's page blob: every address
    of the path added (http and https, www and none). None when the day is not
    stored, or the page has no row and the table is not complete."""
    if not blob:
        return None
    acc, seen = [0, 0, 0.0, 0], False
    for key, c, i, p in blob.get("rows") or []:
        if page_path(key) == path:
            _add(acc, c, i, p)
            seen = True
    if not seen and not blob.get("complete"):
        return None
    return _figs(acc)


def page_queries(stored: dict, days: list[str], path: str, n: int = TOP_QUERIES) -> list[dict]:
    """The page's top queries over the days, from the stored query_page rows
    (each day's largest query-page pairs only)."""
    from ..search.days import QP_SEP
    got: dict = {}
    for d in days:
        for key, c, i, p in ((stored.get(d) or {}).get("query_page") or {}).get("rows") or []:
            query, _, page = key.partition(QP_SEP)
            if page and page_path(page) == path:
                _add(got.setdefault(query, [0, 0, 0.0, 0]), c, i, p)
    rows = [{"query": q, **_figs(v)} for q, v in got.items()]
    rows.sort(key=lambda r: (-r["clicks"], -r["impressions"], r["query"]))
    return rows[:n]


def page_countries(stored: dict, days: list[str], path: str,
                   n: int = TOP_COUNTRIES) -> tuple[list[dict], list[str]]:
    """The page's countries over the days, from the stored page_country rows
    (2.48; each day's 1,000 largest page-country pairs), and the days that have
    none stored (fetched before 2.48: not known, never 0)."""
    from ..search.days import QP_SEP
    got: dict = {}
    without = []
    for d in days:
        blob = (stored.get(d) or {}).get("page_country")
        if blob is None:
            without.append(d)
            continue
        for key, c, i, p in blob.get("rows") or []:
            page, _, country = key.partition(QP_SEP)
            if page_path(page) == path:
                _add(got.setdefault(country, [0, 0, 0.0, 0]), c, i, p)
    rows = [{"country": k, **_figs(v)} for k, v in got.items()]
    rows.sort(key=lambda r: (-r["clicks"], -r["impressions"], r["country"]))
    return rows[:n], without


def top_of(stored: dict, days: list[str], kind: str, n: int, by_path: bool = False) -> list[dict]:
    got: dict = {}
    for d in days:
        for key, c, i, p in ((stored.get(d) or {}).get(kind) or {}).get("rows") or []:
            k = page_path(key) if by_path else key
            _add(got.setdefault(k, [0, 0, 0.0, 0]), c, i, p)
    name = "path" if by_path else kind
    rows = [{name: k, **_figs(v)} for k, v in got.items()]
    rows.sort(key=lambda r: (-r["clicks"], -r["impressions"], r[name]))
    return rows[:n]


def _span(first: date, last: date) -> list[str]:
    return [(first + timedelta(days=i)).isoformat() for i in range((last - first).days + 1)]


def _dates(args, newest: str | None) -> tuple[date, date]:
    try:
        last = date.fromisoformat(args["to"]) if args.get("to") else (
            date.fromisoformat(newest) if newest else date.today())
        first = date.fromisoformat(args["from"]) if args.get("from") else last - timedelta(days=27)
    except ValueError:
        raise Refused("Dates are YYYY-MM-DD.") from None
    if first > last:
        raise Refused("`from` is after `to`.")
    if (last - first).days + 1 > MAX_DAYS:
        raise Refused(f"At most {MAX_DAYS} days at a time.")
    return first, last


WORDS = {"off": "not connected", "waiting": "connected, not synced yet",
         "answering": "answering", "failing": "last try failed",
         "not_answering": "never answered", "stopped": "stopped answering"}


def state_words(status: dict, source) -> str:
    """The sync's state in the words your_tools uses (search/health.py's rule: "stopped
    answering" only after a day, or health.STOPPED_TRIES tries, of failures since it worked)."""
    from ..search import health
    return WORDS[health.status(status, source)["state"]]


def engine_state(ctx, site: str, engine: str, db) -> dict:
    """{"source", "state", "last_answer", "error", "stopped", "reason", "what_to_do",
    "stored"} for one engine."""
    from ..search import days as sd, state, sync
    folder = ctx.history_path.parent if ctx.history_path is not None else None
    status = (state.load(folder, site).get(engine) or {}) if folder else {}
    source = status.get("source") or sync.connected(ctx.config_for(site))[engine]
    stored = sd.summary(db, site, engine)
    if source is None and stored["days"]:
        source = "(stored earlier)"
    from ..search import health
    st = health.status({**status, "engine": engine}, source)
    return {"engine": engine, "name": sync.ENGINE_NAMES[engine], "source": source,
            "state": WORDS[st["state"]], "last_answer": status.get("last_ok"),
            "last_try": status.get("last_sync"), "error": status.get("error"),
            "stopped": st["stopped"], "reason": st["reason"], "what_to_do": st["advice"],
            "stored": stored}


@tool("search_performance", "Search Console and Bing: clicks, impressions, position",
      "Google Search Console's (or Bing Webmaster Tools') own figures, as the search sync "
      "stored them: clicks, impressions, CTR and average position per day, for the whole "
      "site or one page (`path`), with the page's top queries and, for Search Console, the "
      "page's index status from URL Inspection (indexed or not, Google's reason, its last "
      "crawl, the canonical Google chose and whether it matches the page's own). Without "
      "`path`: the site's totals per day, top pages, top queries and countries, and how many "
      "inspected pages are indexed. Days are the engine's own (Search Console: Pacific time); "
      "the newest 2-3 days are provisional and may change. A day the sync has not stored is "
      "listed as missing; a page Google gave no row for is 0 only when that day's page table "
      "is complete, else null. These are the engine's counts (clicks on its results), never "
      "Skald's visits: never add them to Skald's figures.",
      schema({"site": SITE_ARG,
              "path": {"type": "string", "maxLength": 2000,
                       "description": "A page's path, e.g. /pricing/. Leave out for the whole "
                                      "site."},
              "from": {**DAY, "description": "First day, YYYY-MM-DD (the engine's day). "
                                             "Default: 27 days before `to`."},
              "to": {**DAY, "description": "Last day, inclusive. Default: the newest day "
                                           "stored."},
              "engine": {"type": "string", "enum": list(ENGINES),
                         "description": "google (Search Console, the default) or bing."}}))
def search_performance(ctx, args):
    from .tools_more import _history
    site = ctx.site(args.get("site"))
    engine = args.get("engine") or "google"
    path = norm_path(args.get("path"))
    with _history(ctx) as h:
        st = engine_state(ctx, site, engine, h.db)
        first, last = _dates(args, st["stored"]["last"])
        got = figures(h.db, site, engine, path, first, last)
    out = {"site": site, "engine": engine, "name": st["name"], "path": path,
           "from": first.isoformat(), "to": last.isoformat(), "source": st["source"],
           "state": st["state"], "last_answer": st["last_answer"], "error": st["error"],
           "counted_from": f"{st['name']}'s own figures (clicks on its results), not Skald's "
                           "visits", **got}
    return _text(out), out


def figures(db, site: str, engine: str, path: str | None, first: date, last: date) -> dict:
    """The figures search_performance gives (audit_search_pages recounts them)."""
    from ..search import days as sd
    stored, finals = sd.read(db, site, engine, first, last)
    span = _span(first, last)
    have = [d for d in span if d in stored]
    out = {"missing_days": [d for d in span if d not in stored],
           "provisional_days": [d for d in have if not finals.get(d)], "days": []}
    inspected = None
    if engine == "google":
        from ..search import inspect
        inspected = inspect.latest(db, site, path) if path else inspect.counts(db, site)
    if path:
        acc, unknown = [0, 0, 0.0, 0], []
        for d in have:
            got = page_day((stored[d] or {}).get("page"), path)
            out["days"].append({"day": d, "final": bool(finals.get(d)),
                                **(got or {"clicks": None, "impressions": None, "ctr": None,
                                           "position": None})})
            if got is None:
                unknown.append(d)
            else:
                _add(acc, got["clicks"], got["impressions"], got["position"])
        out["not_in_page_table"] = unknown
        out["totals"] = None if len(unknown) == len(have) else _figs(acc)
        out["totals_partial"] = bool(unknown)
        out["top_queries"] = page_queries(stored, have, path) if engine == "google" else []
        if engine == "google":
            out["countries"], out["countries_not_stored"] = page_countries(stored, have, path)
    else:
        acc = [0, 0, 0.0, 0]
        for d in have:
            t = ((stored[d] or {}).get("total") or {}).get("total") or {}
            if not t:
                continue
            out["days"].append({"day": d, "final": bool(finals.get(d)), "clicks": t["clicks"],
                                "impressions": t["impressions"],
                                "ctr": _ctr(t["clicks"], t["impressions"]),
                                "position": t.get("position")})
            _add(acc, t["clicks"], t["impressions"], t.get("position"))
        out["totals"] = _figs(acc) if have else None
        out["top_pages"] = top_of(stored, have, "page", TOP_PAGES, by_path=True)
        out["top_queries"] = top_of(stored, have, "query", TOP_QUERIES)
        out["countries"] = top_of(stored, have, "country", TOP_COUNTRIES)
    out["index"] = inspected
    return out


def _f(v, pct=False) -> str:
    if v is None:
        return "not known"
    return f"{v * 100:.1f}%" if pct else f"{v:,}"


def _text(o: dict) -> str:
    what = f"{o['site']}{o['path'] or ''}"
    head = (f"{o['name']} for {what}, {o['from']} to {o['to']} (its own days): "
            f"{o['state']}" + (f", last answer {o['last_answer']}" if o["last_answer"] else "")
            + ". " + o["counted_from"] + ".")
    lines = [head]
    if o["state"] == "not connected" and not o["days"]:
        lines.append("Nothing stored: connect it in Settings > Leads & tools > Search Console "
                     "& Bing.")
        return "\n".join(lines)
    t = o.get("totals")
    if t:
        lines.append(f"Total: {_f(t['clicks'])} clicks, {_f(t['impressions'])} impressions, "
                     f"CTR {_f(t['ctr'], True)}, position {_f(t['position'])}"
                     + (" (some days not known: not in that day's page table)"
                        if o.get("totals_partial") else "") + ".")
    if o["missing_days"]:
        lines.append(f"Not stored: {', '.join(o['missing_days'])}.")
    if o["provisional_days"]:
        lines.append(f"Provisional (may change): {', '.join(o['provisional_days'])}.")
    if o.get("not_in_page_table"):
        lines.append("Not known (the page had no row and that day's page table is not "
                     f"complete): {', '.join(o['not_in_page_table'])}.")
    for d in o["days"][-14:]:
        lines.append(f"  {d['day']}: {_f(d['clicks'])} clicks, {_f(d['impressions'])} "
                     f"impressions, position {_f(d['position'])}"
                     + ("" if d["final"] else " (provisional)"))
    for q in o.get("top_queries") or []:
        lines.append(f"  query \"{q['query']}\": {q['clicks']} clicks, {q['impressions']} "
                     f"impressions, position {_f(q['position'])}")
    for c in (o.get("countries") or [])[:10]:
        lines.append(f"  country {c['country']}: {c['clicks']} clicks, {c['impressions']} "
                     "impressions")
    if o.get("countries_not_stored"):
        lines.append("Countries not stored for: " + ", ".join(o["countries_not_stored"])
                     + " (fetched before 2.48).")
    for p in o.get("top_pages") or []:
        lines.append(f"  page {p['path']}: {p['clicks']} clicks, {p['impressions']} impressions")
    ix = o.get("index")
    if isinstance(ix, dict) and ix.get("inspected_at"):
        lines.append(f"Index (URL Inspection, {ix['inspected_at']}): {ix['verdict_words']}; "
                     f"{ix.get('coverage') or 'no coverage state'}; last crawl "
                     f"{ix.get('last_crawl') or 'not given'}; Google's canonical "
                     f"{ix.get('google_canonical') or 'not given'}"
                     + ("" if ix.get("canonical_match") is None else
                        (" (matches the page's own)" if ix["canonical_match"]
                         else " (not the page's own)")) + ".")
    elif isinstance(ix, dict) and "pages" in ix:
        lines.append(f"Index (URL Inspection): {ix['pages']} pages inspected"
                     + "".join(f", {n} {k}" for k, n in ix["by_verdict"].items()) + ".")
    elif o["path"] and o["engine"] == "google":
        lines.append("Index: this page has not been inspected yet (URL Inspection runs with "
                     "the daily sync, a few hundred pages a day).")
    return "\n".join(lines)
