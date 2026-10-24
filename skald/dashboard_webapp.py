"""The web app beside the static pages: its files, and one JSON per page.

When `dashboard.app` is on, each site's folder holds the app's shell as
index.html, the static page as classic.html (a browser without script is
sent there), and data/app.json - the figures the app draws, per day, so it
can sum any range a reader picks. Each view gets its own data/app.json
beside its static page.

The honesty rules are the dashboard's own, carried in the data:

  * a day's figures come from history only, verified; a withheld or missing
    day carries a state and no figures, so the app draws it as an absence
  * a partial day is marked partial with its cut, and the app leaves it out
    of every sum and comparison
  * today comes from the live snapshot, marked live, never as a day
  * aggregates and labels only: no address and no user agent, for anyone;
    journeys are the anonymous ones visits.py writes
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path

from . import live
from .classify import AI_ASKED, Group
from .files import slug, write_atomic
from .firsttouch import for_app
from .kpi import KPIS
from .store import History, view_key
from . import webapp

DATA = "data/app.json"
DAYS = 180          # 90 days shown, and the 90 before them for comparisons
VERSION = 1

# kpi.KPIS keys, as the app names them
KPI_NAMES = {"people_readers": "readers", "people_visits": "visits", "people_views": "views",
             "cited_visits": "cited", "search": "search", "probes": "probes",
             "people_404": "nf", "server_errors": "err"}


def _tiers(engines) -> dict:
    return {"training": {k: v for k, v in engines.items() if not AI_ASKED.fullmatch(k)},
            "asked": {k: v for k, v in engines.items() if AI_ASKED.fullmatch(k)}}


def figures(totals) -> dict:
    """A Totals - one day from history - as the app's Day."""
    groups = totals.groups

    def stats(g):
        return groups.get(g)

    people, engines, search, bots = (stats(Group.PEOPLE), stats(Group.ANSWER_ENGINE),
                                     stats(Group.SEARCH_ENGINE), stats(Group.BOTS))
    out = {"requests": totals.hits,
           "hits": {g.value: (groups[g].hits if g in groups else 0) for g in Group},
           "tiers": {"training": engines.tiers.get("training", 0) if engines else 0,
                     "asked": engines.tiers.get("asked", 0) if engines else 0}}
    out.update({KPI_NAMES[k.key]: k.value(totals) for k in KPIS if k.key in KPI_NAMES})
    out.update({
        "pages": dict(people.pages) if people else {},
        "cited_by": dict(people.cited_by) if people else {},
        "ai_pages": dict(engines.pages) if engines else {},
        "engines": _tiers(engines.engines) if engines else {"training": {}, "asked": {}},
        "search_engines": dict(search.engines) if search else {},
        "bot_agents": ({"Scanner probes": bots.probes, **dict(bots.agents)} if bots.probes
                       else dict(bots.agents)) if bots else {},
    })
    if totals.breakdowns:
        out.update({
            "by": {name: dict(c) for name, c in (people.by if people else {}).items()},
            "statuses": {g.value: dict(s.statuses) for g, s in groups.items()},
            "not_found": dict(people.not_found) if people else {},
            "server_errors": dict(totals.server_errors),
            "speeds": dict(people.speeds) if people else {},
            "slow_pages": dict(people.slow_pages) if people else {},
            "posts": {g.value: {"total": s.posts, "pages": dict(s.post_pages)}
                      for g, s in groups.items() if s.posts},
        })
    if totals.visits is not None:
        v = totals.visits
        out["visit"] = {name: dict(getattr(v, name)) for name in ("pages", "seconds", "exits", "steps", "flags")}
    if totals.ours_labels is not None:
        out["ours_by"] = dict(totals.ours_labels)
    return out


def from_snapshot(snap: dict) -> dict:
    """Today's live snapshot (live.py) as the app's Day."""
    groups, people, b = snap.get("groups", {}), snap.get("people", {}), snap.get("breakdowns") or {}
    statuses = b.get("statuses") or {}
    search = snap.get("search", {})
    ads = sum(v for k, v in search.items() if "ads" in k.lower())
    bots = snap.get("bots", {})
    out = {
        "requests": snap.get("requests", 0),
        "hits": {g.value: groups.get(g.value, 0) for g in Group},
        "readers": people.get("readers", 0), "visits": people.get("visits", 0),
        "views": people.get("views", 0), "cited": people.get("cited_visits", 0),
        "tiers": {"training": snap.get("ai_tiers", {}).get("training", 0),
                  "asked": snap.get("ai_tiers", {}).get("asked", 0)},
        "search": groups.get(Group.SEARCH_ENGINE.value, 0) - ads,
        "probes": bots.get("probes", 0),
        "pages": people.get("pages", {}), "cited_by": people.get("cited_by", {}),
        "ai_pages": snap.get("ai_pages", {}), "engines": snap.get("ai", {}),
        "search_engines": search,
        "bot_agents": {"Scanner probes": bots.get("probes", 0)} if bots.get("probes") else {},
    }
    if b:
        out.update({
            "by": b.get("by", {}), "statuses": statuses, "not_found": b.get("not_found", {}),
            "server_errors": b.get("server_errors", {}), "speeds": b.get("speeds", {}),
            "slow_pages": b.get("slow_pages", {}), "posts": b.get("posts", {}),
            "nf": (statuses.get(Group.PEOPLE.value) or {}).get("404", 0),
            "err": sum((s or {}).get("5xx", 0) for s in statuses.values()),
        })
    if snap.get("visits"):
        out["visit"] = {k: snap["visits"].get(k, {}) for k in ("pages", "seconds", "exits", "steps", "flags")}
    if snap.get("ours_labels") is not None:
        out["ours_by"] = snap.get("ours_labels") or {}
    formats = (snap.get("extras") or {}).get("ai_formats")
    if formats is not None:
        out["ai_formats"] = formats
    touch = for_app((snap.get("extras") or {}).get("first_touch"))
    if touch is not None:
        out["first_touch"] = touch
    # Today's returning readers (visitors.annotate), the shape a stored day has in
    # overview.json; none when no visitor key is set (never 0).
    ret = snap.get("returning")
    if ret and ret.get("readers") is not None:
        out["returning"] = {"readers": int(ret["readers"]), "returning": int(ret.get("returning") or 0)}
    return out


def journey(j: dict, day: str | None = None) -> dict:
    """A stored journey (visits.py) as the app's Journey: labels, pages, times."""
    trail = [{"path": p, "page": kind == "page"} for p, kind in j.get("trail", [])]
    # `at`: each step's seconds since the visit's first request, bucketed
    # (visits.py). Older journeys have none; their steps carry no `at`.
    at = j.get("at")
    if isinstance(at, list) and len(at) == len(trail):
        for step, sec in zip(trail, at):
            step["at"] = sec
    flags = [f for f in ("not_found", "posted", "in_app") if j.get(f)]
    # Fields added later (schema 9: utm, paid, referring page, returning; likely_ai, inferred,
    # ai_likely.py; ai_read, the pages its assistant fetched before, ai_read.py) pass through.
    # city: only when a city file named one (logs.city_db), "Toronto, Ontario, CA".
    extra = {k: j[k] for k in ("utm", "paid", "ref_param", "ref_host", "ref_page", "search_terms",
                               "returning", "days_seen_30d", "likely_ai", "ai_read", "city",
                               # direct_likely.py: a Direct visit's likely reason (inferred)
                               "likely_direct",
                               # firsttouch.py: the visitor's first known visit; seq, the
                               # day's place of the visit (the visitor timeline asks by it)
                               "first_touch", "seq",
                               # visits.py: steps seen in all, and those seen only in
                               # the browser (no page loaded); pages + in_app = seen
                               "seen", "in_app") if k in j}
    return {**extra, "start": j.get("start", ""), "day": day or str(j.get("start", ""))[:10],
            "country": j.get("country", ""), "device": j.get("device", ""),
            "browser": j.get("browser", ""), "os": j.get("os", ""),
            "source": j.get("source", ""), "via": j.get("via", ""), "campaign": j.get("campaign", ""),
            "trail": trail, "pages": j.get("pages", 0), "seconds": j.get("seconds", 0),
            "exit": j.get("exit", ""), "flags": flags}


def _partial(entry: dict) -> str:
    bits = []
    if entry.get("partial_from"):
        bits.append(f"data from {entry['partial_from']:%H:%M}")
    if entry.get("partial_until"):
        bits.append(f"data until {entry['partial_until']:%H:%M}")
    return ", ".join(bits)


def build(history: History, key: str, site: str, tz, now: datetime, snap: dict | None,
          views=(), refresh: bool = False, credit=None) -> dict:
    """Everything one page's app reads, JSON-ready."""
    anchor = now.date() - timedelta(days=1)
    start = history.first_day(key)
    first = max(anchor - timedelta(days=DAYS - 1), start) if start else anchor
    days = []
    # Each day's figures, as history.period(key, d, d, include_partial=True)
    # makes them, read for all the days at once (store.History.periods).
    periods = history.periods(key, first, anchor, include_partial=True) if start else {}
    # AI fetches by what they asked for (ai_formats.py): absent on a day
    # collected before it was counted, never 0.
    formats = history.extras(key, first, anchor, ("ai_formats", "first_touch")) if start else {}
    for entry in history.daily(key, first, anchor) if start else []:
        d: date = entry["day"]
        item = {"day": d.isoformat(), "state": entry["state"]}
        if entry["state"] in ("ok", "partial"):
            period = periods[d]
            item.update(figures(period.totals))
            blob = (formats.get(d.isoformat()) or {}).get("ai_formats")
            if blob is not None:
                item["ai_formats"] = blob
            touch = for_app((formats.get(d.isoformat()) or {}).get("first_touch"))
            if touch is not None:
                item["first_touch"] = touch
            if entry["state"] == "partial":
                item["partial"] = _partial(entry)
        days.append(item)
    out = {
        "version": VERSION, "site": site, "tz": str(tz),
        "generated_at": now.isoformat(timespec="seconds"),
        "today": now.date().isoformat(), "anchor": anchor.isoformat(),
        "firstDay": start.isoformat() if start else None,
        "views": [{"slug": v.slug, "name": v.name} for v in views],
        "canRefresh": bool(refresh), "refreshUrl": "refresh",
        "credit": {"text": credit[0], "url": credit[1]} if credit else None,
        "days": days, "live": None,
        "journeys": [journey(j, j.get("day")) for j in history.journeys(key, first, anchor)],
    }
    if snap:
        state = snap.get("state")
        out["live"] = {"state": state, "day": snap.get("day"), "generated_at": snap.get("generated_at"),
                       "from": snap.get("from"), "problems": snap.get("problems", [])}
        if state == "ok":
            out["live"]["figures"] = from_snapshot(snap)
            out["live"]["events"] = snap.get("events") or []
            # Yesterday at this hour (by_now.py): the site's page only.
            if snap.get("by_now") is not None:
                out["live"]["by_now"] = snap["by_now"]
            out["journeys"] = [journey(j) for j in snap.get("journeys") or []] + out["journeys"]
    return out


def release_zones(config: dict | None, tz) -> list[str]:
    """The zones the footer gives the release time in: `dashboard.release_zones`
    (IANA names, a list), else the site's own zone."""
    raw = ((config or {}).get("dashboard") or {}).get("release_zones")
    zones = [str(z) for z in raw] if isinstance(raw, list) else []
    return zones or [str(tz)]


def write(out: Path, history: History, site: str, tz, now: datetime, snap: dict | None,
          views=(), refresh: bool = False, credit=None, config: dict | None = None) -> list[Path]:
    """The app for one site: its data beside the site page and each view's,
    then the app's own files (the shell as index.html, shared code in _app/)."""
    folder = Path(out) / slug(site)
    written = []
    for view in (None, *views):
        key = view_key(site, view.slug) if view else site
        part = live.view_snapshot(snap, view.slug) if view else snap
        data = build(history, key, site, tz, now, part, views, refresh, credit)
        data["releaseZones"] = release_zones(config, tz)
        # A city file is set (logs.city_db): the app says "not recorded"
        # for a visit without a city, and how to set one when it is not.
        from .conversions.geo import city_database
        data["cities"] = bool(city_database(config or {}))
        path = (folder / view.slug if view else folder) / DATA
        # The data layer's own files beside this one, so the app asks only for those that exist.
        data["files"] = sorted(p.stem for p in path.parent.glob("*.json") if p.name != path.name)
        write_atomic(path, json.dumps(data, separators=(",", ":"), default=str) + "\n")
        written.append(path)
    return written + webapp.install(out, [site])
