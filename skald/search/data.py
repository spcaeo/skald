"""search.json: the Search tab (Traffic > Search), from `search_days` and
the day kind `search_landing` (DATA-CONTRACT.md, "search.json").

Per engine ("google", "bing"):

  connected   the property or site address, or null
  status      the sync state (search/state.py): last sync, next, error in
              plain words, backfill progress, the second road's last result
  summary     days stored, first, last, how many still provisional
  days        every stored day, oldest first: clicks, impressions, ctr,
              position, final
  periods     {"7", "28", "90", "480"}: the last N days up to the newest
              stored day, each with its totals and the query, page, country,
              device and appearance tables summed over those days (search/
              days.fold's top rows per day, then the top TABLE_ROWS of the
              sums; the rest in "others", what the engine does not attribute
              in "unattributed"; `folded_days`: days on which some rows were
              already in "(all others)", so a row's sum may be short)

crosscheck: Search Console clicks beside Skald's people from Google search,
per day and per landing page, over the last CROSS_DAYS days that are final
in Search Console and whole and verified in Skald. Never forced to match:
`notes` say why they differ. `flag` is set when the ratio of the last 7 days
moved by more than half against the 21 before (usually a tracking break).

Figures are the engines', never Skald's own; they are never added to a
Skald figure.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

from .. import store_extras as sx
from . import days as sd, reports, state
from .props import path_of
from .sync import ENGINE_NAMES, connected

PERIODS = (7, 28, 90, 480)
TABLE_ROWS = {"query": 300, "page": 200, "country": 100, "device": 10, "appearance": 50}
CROSS_DAYS = 28
PAGES = 30
OTHER = "(all others)"


def _ctr(clicks, shown):
    return round(clicks / shown, 4) if shown else None


def _sum_kind(blobs: list[dict], cap: int) -> dict:
    """One kind's day blobs summed into one table."""
    rows: dict[str, list] = {}
    others = {"rows": 0, "clicks": 0, "impressions": 0, "weight": 0.0, "seen": 0}
    rest = {"clicks": 0, "impressions": 0}
    total = {"clicks": 0, "impressions": 0, "weight": 0.0, "seen": 0}
    folded = 0
    for b in blobs:
        for key, c, i, p in b.get("rows") or []:
            got = rows.setdefault(key, [key, 0, 0, 0.0, 0])
            got[1] += c
            got[2] += i
            if p is not None and i:
                got[3] += p * i
                got[4] += i
        o = b.get("others") or {}
        if o.get("rows"):
            folded += 1
        others["rows"] = max(others["rows"], int(o.get("rows") or 0))
        others["clicks"] += o.get("clicks") or 0
        others["impressions"] += o.get("impressions") or 0
        if o.get("position") is not None and o.get("impressions"):
            others["weight"] += o["position"] * o["impressions"]
            others["seen"] += o["impressions"]
        for f in rest:
            rest[f] += (b.get("unattributed") or {}).get(f) or 0
        t = b.get("total") or {}
        total["clicks"] += t.get("clicks") or 0
        total["impressions"] += t.get("impressions") or 0
        if t.get("position") is not None and t.get("impressions"):
            total["weight"] += t["position"] * t["impressions"]
            total["seen"] += t["impressions"]
    ordered = sorted(rows.values(), key=lambda r: (-r[1], -r[2], r[0]))
    kept, extra = ordered[:cap], ordered[cap:]
    for r in extra:
        others["clicks"] += r[1]
        others["impressions"] += r[2]
        others["weight"] += r[3]
        others["seen"] += r[4]
    others["rows"] += len(extra)

    def pos(weight, seen):
        return round(weight / seen, 2) if seen else None

    clean = sd._clean
    return {
        "rows": [[r[0], clean(r[1]), clean(r[2]), _ctr(r[1], r[2]), pos(r[3], r[4])]
                 for r in kept],
        "others": {"rows": others["rows"], "clicks": clean(others["clicks"]),
                   "impressions": clean(others["impressions"]),
                   "position": pos(others["weight"], others["seen"])},
        "unattributed": {k: clean(v) for k, v in rest.items()},
        "total": {"clicks": clean(total["clicks"]), "impressions": clean(total["impressions"]),
                  "ctr": _ctr(total["clicks"], total["impressions"]),
                  "position": pos(total["weight"], total["seen"])},
        "folded_days": folded,
    }


def period(stored: dict, finals: dict, last: str, n: int) -> dict:
    end = date.fromisoformat(last)
    first = (end - timedelta(days=n - 1)).isoformat()
    picked = {d: v for d, v in stored.items() if first <= d <= last}
    out = {"first": first, "last": last, "days": len(picked),
           "provisional_days": sorted(d for d in picked if not finals.get(d))}
    for kind in ("total", *TABLE_ROWS):
        blobs = [v[kind] for v in picked.values() if kind in v]
        if kind == "total":
            out["totals"] = _sum_kind(blobs, 1)["total"]
        elif blobs:
            out[kind] = _sum_kind(blobs, TABLE_ROWS[kind])
    return out


def engine_part(p, site: str, engine: str, source: str | None, folder) -> dict:
    status = (state.load(folder, site).get(engine) or {}) if folder else {}
    summary = sd.summary(p.history.db, site, engine)
    part = {"name": ENGINE_NAMES[engine], "connected": source, "status": status,
            "summary": summary, "days": [], "periods": {}}
    if not summary["days"]:
        return part
    first = date.fromisoformat(summary["last"]) - timedelta(days=max(PERIODS) - 1)
    stored, finals = sd.read(p.history.db, site, engine, first,
                             date.fromisoformat(summary["last"]))
    for d in sorted(stored):
        t = (stored[d].get("total") or {}).get("total")
        if t:
            part["days"].append({"day": d, "clicks": t["clicks"], "impressions": t["impressions"],
                                 "ctr": _ctr(t["clicks"], t["impressions"]),
                                 "position": t["position"], "final": bool(finals.get(d))})
    for n in PERIODS:
        part["periods"][str(n)] = period(stored, finals, summary["last"], n)
    for n, got in reports.periods(stored, finals, summary, full=engine == "google").items():
        part["periods"][n].update(got)
    return part


NOTES = [
    "Search Console counts clicks on Google's results; Skald counts the visits that arrived "
    "and drew a page. A person who clicks twice is two clicks and may be one visit; a click "
    "closed before the page drew is no visit.",
    "Some browsers and apps send no referrer: Skald files those visits as Direct, not Google.",
    "Search Console's figures here are web results only: Discover, News and image search "
    "are not in them. Ad clicks are not in either side.",
    "Search Console reports a page by its full address; Skald by its path. Two addresses of "
    "one path (http and https, www and none) are added together here.",
]


def crosscheck(p, site: str, google: dict) -> dict:
    """Search Console clicks beside Skald's people from Google search."""
    tz = str(p.tz)
    notes = list(NOTES)
    if tz != "America/Los_Angeles":
        notes.insert(0, f"Search Console's days are Pacific Time; Skald's are {tz}. Each day "
                        "is cut at a different midnight, so single days differ more than weeks.")
    out = {"engine": "google", "days": [], "pages": [], "notes": notes, "flag": None,
           "left_out": []}
    finals = {d["day"]: d for d in google.get("days") or [] if d["final"]}
    if not finals:
        return {**out, "state": "no final Search Console days yet"}
    last = max(finals)
    first = (date.fromisoformat(last) - timedelta(days=CROSS_DAYS - 1)).isoformat()
    ours = sx.read(p.history.db, site, date.fromisoformat(first), date.fromisoformat(last),
                   ("search_landing",))
    states = {d["day"].isoformat(): d["state"] for d in
              p.history.daily(site, date.fromisoformat(first), date.fromisoformat(last))}
    stored, _ = sd.read(p.history.db, site, "google", date.fromisoformat(first),
                        date.fromisoformat(last), ("page",))
    sc_pages, our_pages = defaultdict(float), defaultdict(int)
    for d in sorted(finals):
        if d < first:
            continue
        blob = (ours.get(d) or {}).get("search_landing")
        if states.get(d) != "ok" or blob is None:
            out["left_out"].append({"day": d, "why": "withheld" if states.get(d) == "withheld"
                                    else "not counted by Skald" if blob is None
                                    else states.get(d) or "missing"})
            continue
        sc = finals[d]["clicks"]
        visits = int((blob.get("engines") or {}).get("Google", 0))
        out["days"].append({"day": d, "search_console_clicks": sc, "skald_visits": visits,
                            "difference": sd._clean(visits - sc),
                            "ratio": round(visits / sc, 3) if sc else None})
        for key, c, _i, _p in (stored.get(d, {}).get("page") or {}).get("rows") or []:
            sc_pages[path_of(key)] += c
        for path, n in ((blob.get("pages") or {}).get("Google") or {}).items():
            if path != OTHER:
                our_pages[path.split("?", 1)[0]] += int(n)
    for path in sorted(set(sc_pages) | set(our_pages),
                       key=lambda k: (-sc_pages.get(k, 0), -our_pages.get(k, 0), k))[:PAGES]:
        sc, visits = sd._clean(sc_pages.get(path, 0)), our_pages.get(path, 0)
        out["pages"].append({"path": path, "search_console_clicks": sc, "skald_visits": visits,
                             "difference": sd._clean(visits - sc)})
    sc_all = sum(d["search_console_clicks"] for d in out["days"])
    ours_all = sum(d["skald_visits"] for d in out["days"])
    out["totals"] = {"search_console_clicks": sd._clean(sc_all), "skald_visits": ours_all,
                     "difference": sd._clean(ours_all - sc_all),
                     "ratio": round(ours_all / sc_all, 3) if sc_all else None}
    out["flag"] = _flag(out["days"])
    return out




def _flag(rows: list[dict]) -> str | None:
    if len(rows) < 14:
        return None
    recent, before = rows[-7:], rows[:-7]

    def ratio(part):
        sc = sum(r["search_console_clicks"] for r in part)
        return sum(r["skald_visits"] for r in part) / sc if sc >= 20 else None

    a, b = ratio(recent), ratio(before)
    if a is None or b is None or b == 0:
        return None
    if abs(a - b) / b > 0.5:
        return (f"Skald's visits per Search Console click moved from {b:.2f} to {a:.2f} in the "
                "last 7 days. That is usually a tracking break: a page that stopped drawing, a "
                "redirect that drops the referrer, or a property change.")
    return None


def build(p) -> dict:
    site = p.key.split("::", 1)[0]
    folder = None
    resolved = ((p.config or {}).get("_resolved") or {}).get("history_db")
    if resolved:
        folder = Path(resolved).parent
    sources = connected(p.config)
    engines = {e: engine_part(p, site, e, sources[e], folder) for e in ("google", "bing")}
    from .google import key_state as google_key
    from .bing import key_state as bing_key
    try:
        keys = {"google": bool(google_key(p.config, folder)["client_email"]),
                "bing": bool(bing_key(p.config, folder)["set"])}
    except Exception:                   # noqa: BLE001 - a page, never a stop
        keys = {"google": False, "bing": False}
    return {"engines": engines, "keys": keys, "view_note": (
                "Search figures are for the whole site." if "::" in p.key else None),
            "crosscheck": crosscheck(p, site, engines["google"])}
