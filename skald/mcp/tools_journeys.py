"""The MCP tool for how people reach pages and where they go next: page_journeys (2.49, #51).

It reads the stored journeys (history `journeys`, store_visits.py): one anonymous
row per visit, with its pages in order, its source and referrer, country,
device and new or returning; no address, no user agent, no visitor key. They
are kept `report.journey_days` (longer while the site keeps everything), so a
day before the oldest kept one is named in `not_kept`, never counted as 0.

For each page asked (a path; several at once):
  visits     the visits that read the page (a page view in the visit's trail)
  arrived    how they came to it: landed on it (by the visit's source and
             referring site) or the page read just before it in the visit
  next       the page read just after it, or "left the site"
  who        new / returning, lead / customer (only visits proven to have sent a
             form: people/lead_visits.mark_journeys), countries, devices
  latest     the newest visits, newest first: day, start, source, pages in order

A page read twice in one visit counts that visit once; its arrival is the
first time, its next page the last time. audit_page_journeys.py recounts the
visits, arrivals and next pages by its own road (SQL and json_each).
"""
from __future__ import annotations

from collections import Counter
from datetime import date, timedelta
from pathlib import Path

from .data import Refused
from .tools import SITE_ARG, schema, tool

MAX_PATHS = 20
MAX_DAYS = 93
TOP = 10
LATEST = 20
LEFT = "(left the site)"
LANDED = "(landed here)"


def page_views(j: dict) -> list[str]:
    """The visit's page views in order (its trail's "page" steps)."""
    out = []
    for step in j.get("trail") or []:
        if isinstance(step, (list, tuple)) and len(step) >= 2 and step[1] == "page":
            out.append(str(step[0]))
    return out


def norm(path) -> str:
    if not isinstance(path, str) or not path.startswith("/") or len(path) > 2000:
        raise Refused("Each page is a path starting with /, e.g. /pricing/.")
    return path.split("?", 1)[0].split("#", 1)[0] or "/"


def _ranked(c: Counter, n: int = TOP) -> list[dict]:
    return [{"value": k, "visits": v} for k, v in sorted(c.items(), key=lambda x: (-x[1], x[0]))[:n]]


def one_page(path: str, journeys: list[dict], latest: int = LATEST) -> dict:
    """One page's visits, arrivals, next pages and who, from journeys newest first."""
    visits, sources, before, after = 0, Counter(), Counter(), Counter()
    who = {"new": 0, "returning": 0, "lead": 0, "customer": 0}
    countries, devices, rows = Counter(), Counter(), []
    for j in journeys:
        pages = page_views(j)
        if path not in pages:
            continue
        visits += 1
        first, last = pages.index(path), len(pages) - 1 - pages[::-1].index(path)
        if first == 0:
            before[LANDED] += 1
            src = j.get("source") or "Direct or unknown"
            via = j.get("via") or j.get("ref_host") or ""
            sources[f"{src}: {via}" if via and via != src else src] += 1
        else:
            before[pages[first - 1]] += 1
        after[pages[last + 1] if last + 1 < len(pages) else LEFT] += 1
        who["returning" if j.get("returning") else "new"] += 1
        if j.get("won") in ("lead", "customer"):
            who[j["won"]] += 1
        countries[j.get("country") or "not recorded"] += 1
        devices[j.get("device") or "not recorded"] += 1
        if len(rows) < latest:
            rows.append({"day": j.get("day"), "start": j.get("start"), "source": j.get("source"),
                         "via": j.get("via") or None, "country": j.get("country") or None,
                         "device": j.get("device") or None, "returning": bool(j.get("returning")),
                         "won": j.get("won"), "pages": pages, "seconds": j.get("seconds")})
    return {"path": path, "visits": visits,
            "arrived": {"landed_here": before[LANDED], "landed_from": _ranked(sources),
                        "from_page": _ranked(Counter({k: v for k, v in before.items() if k != LANDED}))},
            "next": _ranked(after), "left": after[LEFT], "who": {**who, "countries": _ranked(countries),
                                             "devices": _ranked(devices)},
            "latest": rows}


def kept_from(db, site: str) -> str | None:
    got = db.execute("SELECT MIN(day) FROM journeys WHERE site = ?", (site,)).fetchone()
    return got[0] if got else None


def counted_days(db, site: str, first: date, last: date) -> set[str]:
    """Days in the range whose visits were counted (history `days.journeys` = 1)."""
    return {r[0] for r in db.execute(
        "SELECT day FROM days WHERE site = ? AND day BETWEEN ? AND ? AND journeys = 1",
        (site, first.isoformat(), last.isoformat()))}


def figures(db, site: str, paths: list[str], first: date, last: date,
            marks=None) -> dict:
    """Every asked page's figures (the audit compares these). `marks`: a function
    adding `won` to journeys (lead_visits.mark_journeys), or None."""
    from ..store_visits import journeys as stored
    oldest = kept_from(db, site)
    js = stored(db, site, max(first, date.fromisoformat(oldest)) if oldest else first, last) \
        if oldest else []
    if marks is not None and js:
        js = marks(js)
    counted = counted_days(db, site, first, last)
    days = [(first + timedelta(days=i)).isoformat() for i in range((last - first).days + 1)]
    not_kept = [d for d in days if oldest is None or d < oldest]
    missing = [d for d in days if d not in not_kept and d not in counted]
    return {"kept_from": oldest, "not_kept": not_kept, "missing_days": missing,
            "visits_read": len(js), "pages": [one_page(p, js) for p in paths]}


DAY = {"type": "string", "pattern": r"^\d{4}-\d{2}-\d{2}$"}


@tool("page_journeys", "How people reach pages and where they go next",
      "For one or more pages (paths): the visits that read each page over whole days, how "
      "they arrived (landed on it, by source and referring site, or the page read just "
      "before), the page read next (or left the site), who they were (new or returning, "
      "lead or customer when the visit is proven to have sent a form, countries, devices) "
      "and the newest visits, newest first, each with its pages in order. Visits are "
      "anonymous (no address); they are kept for a limited number of days: days before the "
      "oldest kept one are listed in `not_kept` and never counted as 0. A page read twice "
      "in one visit counts that visit once.",
      schema({"site": SITE_ARG,
              "paths": {"type": "array", "minItems": 1, "maxItems": MAX_PATHS,
                        "items": {"type": "string", "maxLength": 2000},
                        "description": "Pages' paths, e.g. [\"/pricing/\", \"/demo/\"]."},
              "from": {**DAY, "description": "First day, YYYY-MM-DD (site time). Default: "
                                             "6 days before `to`."},
              "to": {**DAY, "description": "Last day, inclusive. Default: the newest whole "
                                           "day stored."}}, required=("paths",)))
def page_journeys(ctx, args):
    from .tools_more import _history
    site = ctx.site(args.get("site"))
    paths = list(dict.fromkeys(norm(p) for p in (args.get("paths") or [])))
    if not paths:
        raise Refused("Give at least one page in `paths`.")
    with _history(ctx) as h:
        newest = h.db.execute("SELECT MAX(day) FROM days WHERE site = ? AND journeys = 1",
                              (site,)).fetchone()[0]
        try:
            last = date.fromisoformat(args["to"]) if args.get("to") else (
                date.fromisoformat(newest) if newest else date.today())
            first = date.fromisoformat(args["from"]) if args.get("from") else last - timedelta(days=6)
        except ValueError:
            raise Refused("Dates are YYYY-MM-DD.") from None
        if first > last:
            raise Refused("`from` is after `to`.")
        if (last - first).days + 1 > MAX_DAYS:
            raise Refused(f"At most {MAX_DAYS} days at a time.")
        marks = _marker(ctx, site)
        got = figures(h.db, site, paths, first, last, marks)
    out = {"site": site, "from": first.isoformat(), "to": last.isoformat(),
           "counted_from": "Skald's stored visits (anonymous, from the server log)", **got}
    return _text(out), out


def _marker(ctx, site: str):
    """Lead / customer marks from the site's lead store, or None when it has none."""
    try:
        from ..people.lead_visits import mark_journeys
        config = ctx.config_for(site)
        folder = Path(ctx.history_path).parent if ctx.history_path else None
    except Exception:                                   # noqa: BLE001 - a label, never in the way
        return None
    return lambda js: mark_journeys(config, folder, site, js)


def _text(o: dict) -> str:
    lines = [f"How people reach pages on {o['site']}, {o['from']} to {o['to']} "
             f"({o['counted_from']})."]
    if o["not_kept"]:
        lines.append(f"Visits are kept from {o['kept_from'] or 'no day yet'}: "
                     f"{len(o['not_kept'])} day(s) of the range are not kept (not counted, not 0).")
    if o["missing_days"]:
        lines.append(f"Days not counted yet: {', '.join(o['missing_days'])}.")
    for p in o["pages"]:
        a = p["arrived"]
        lines.append(f"\n{p['path']}: {p['visits']} visit(s).")
        if not p["visits"]:
            continue
        lines.append(f"  Landed on it: {a['landed_here']}"
                     + (" (" + ", ".join(f"{x['value']} {x['visits']}" for x in a["landed_from"][:5]) + ")"
                        if a["landed_from"] else "") + ".")
        if a["from_page"]:
            lines.append("  Came from: " + ", ".join(f"{x['value']} {x['visits']}"
                                                     for x in a["from_page"][:5]) + ".")
        lines.append("  Next: " + ", ".join(f"{x['value']} {x['visits']}" for x in p["next"][:5]) + ".")
        w = p["who"]
        lines.append(f"  Who: {w['new']} new, {w['returning']} returning, {w['lead']} lead(s), "
                     f"{w['customer']} customer(s).")
        for v in p["latest"][:5]:
            lines.append(f"  - {v['day']} {str(v['start'] or '')[11:16]} {v['source'] or ''}"
                         f"{' (' + v['via'] + ')' if v['via'] else ''}: " + " > ".join(v["pages"]))
    return "\n".join(lines)
