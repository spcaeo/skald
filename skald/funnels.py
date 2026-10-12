"""Funnels: how many visits went from one step to the next, and where they
dropped off (funnels.json, and the helper's <page>/funnels).

A funnel is a list of steps. A path step is reached when one of the visit's
pages - loaded or moved to inside the app - matches it, after the visit
reached the step before:

  equals       the path, exactly ("/pricing/" also matches "/pricing")
  starts_with  the path starts with it
  segment      the path's last part, in any locale ("pricing" matches
               /pricing/ and /ca/fr/pricing/)
  contains     the path contains it anywhere

A first step of kind "any" is the visit's start: every visit reaches it, and
it uses up no page.

A funnel may start from a source: a source type ("AI assistant") or an
assistant or referring host by name ("ChatGPT", "linkedin.com").

Event steps (kind "event") count in-page events from the beacon (events.py:
history's event_counts on whole days, today's spool) of the named kinds over
the same days - people's events only, by the event's source type when the
funnel has one - shown beside the visit steps like lead steps, never
divided per visit.

Visits come from the anonymous journeys (`report.journey_days`, 7 days, and
today), so every step is exact for that window. Lead steps (kind "lead")
come from the CMS - leads of the given types over the same days, by the
lead's first-touch source when the funnel has a source - and are shown
beside the visit steps, never divided per visit: they are two systems. For
a 90-day view the first step alone is counted from the drill-down cube
when it is a landing-page rule.

Saved funnels live in funnels.json beside the history; only admins may
save or delete one (access.py), and each change is logged with who made it.
From the day it is saved, a funnel is also counted every day when the day
is collected (funnel_days.py): its `history`, kept with the day's detail.
"""
from __future__ import annotations

import json
import os
import re
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from .files import write_atomic

MATCHES = ("equals", "starts_with", "segment", "contains")
MAX_STEPS = 8
MAX_PATHS = 10
NAME = re.compile(r"^[\w .,&()'/-]{1,60}$")
EVENT = re.compile(r"^[a-z0-9_]{1,40}$")
LEAD_TYPES = ("signup", "contact", "waitlist", "demo_opened", "demo_booked")


class Invalid(ValueError):
    pass


def defaults(config: dict | None = None) -> list[dict]:
    from .classify import FORM_PAGES, PRICING_PAGES
    from .leads import _paths
    pricing = _paths(config or {}, "pricing_paths", PRICING_PAGES)
    forms = _paths(config or {}, "form_paths", FORM_PAGES)
    return [{
        "name": "Landing to lead", "saved_by": "default", "saved_at": None, "source": None,
        "steps": [
            {"label": "Landed", "kind": "path", "match": "starts_with", "paths": ["/"]},
            {"label": "Pricing", "kind": "path", "match": "segment",
             "paths": [p.strip("/") for p in pricing]},
            {"label": "Sign-up, contact or early-access page", "kind": "path",
             "match": "segment", "paths": [p.strip("/") for p in forms]},
            {"label": "Opened Book a demo (CMS)", "kind": "lead", "types": ["demo_opened"]},
            {"label": "Lead: sign-up, contact, early access (CMS)", "kind": "lead",
             "types": ["signup", "contact", "waitlist"]},
            {"label": "Demo booked (CMS)", "kind": "lead", "types": ["demo_booked"]},
        ]}]


# -------------------------------------------------------------- matching

def _bare(path: str) -> str:
    return path.split("?", 1)[0]


def matches(step: dict, path: str) -> bool:
    path = _bare(path)
    for want in step.get("paths") or []:
        if step["match"] == "equals":
            if (path.rstrip("/") or "/") == (want.rstrip("/") or "/"):
                return True
        elif step["match"] == "starts_with":
            if path.startswith(want):
                return True
        elif step["match"] == "contains":
            if want in path:
                return True
        elif path.rstrip("/").rsplit("/", 1)[-1].lower() == want.strip("/").lower():
            return True
    return False


def from_source(j: dict, source: str | None) -> bool:
    if not source:
        return True
    want = source.strip().lower()
    return want in ((j.get("source") or "").lower(), (j.get("via") or "").lower(),
                    (j.get("ref_host") or "").lower())


def _pages(j: dict) -> list[str]:
    trail = [t[0] for t in j.get("trail") or [] if isinstance(t, (list, tuple)) and t]
    return trail or ([j["landing"]] if j.get("landing") else [])


def reached(j: dict, steps: list[dict]) -> int:
    """How many of the path steps, in order, this visit reached."""
    pages, at, n = _pages(j), 0, 0
    for step in steps:
        if step.get("kind") == "any":
            n += 1
            continue
        hit = next((i for i in range(at, len(pages)) if matches(step, pages[i])), None)
        if hit is None:
            break
        n, at = n + 1, hit
    return n


def compute(funnel: dict, journeys: list[dict], first: date, last: date,
            lead_rows: list[dict] | None, tz, cube_days: list[dict] | None = None,
            event_rows: list[tuple] | None = None) -> dict:
    """The step counts for one funnel."""
    steps = funnel["steps"]
    source = funnel.get("source")
    path_steps = [s for s in steps if s["kind"] in ("path", "any")]
    mine = [j for j in journeys if from_source(j, source)]
    depth = Counter(reached(j, path_steps) for j in mine)
    out, prev, first_n = [], None, None
    k = 0
    for step in steps:
        if step["kind"] in ("path", "any"):
            k += 1
            n = sum(c for d, c in depth.items() if d >= k)
            first_n = n if first_n is None else first_n
            row = {"label": step["label"], "kind": step["kind"], "n": n,
                   "of_previous_pct": round(n / prev * 100, 1) if prev else None,
                   "of_first_pct": round(n / first_n * 100, 1) if first_n else None,
                   "drop": (prev - n) if prev is not None else None}
            prev = n
        elif step["kind"] == "event":
            row = {"label": step["label"], "kind": "event",
                   "n": _events(event_rows, step.get("events") or [], source),
                   "of_previous_pct": None, "of_first_pct": None, "drop": None}
        else:
            row = {"label": step["label"], "kind": "lead",
                   "n": _leads(lead_rows, tz, first, last, step.get("types") or [], source),
                   "of_previous_pct": None, "of_first_pct": None, "drop": None}
        out.append(row)
    long = None
    if cube_days is not None and path_steps and steps[0]["kind"] == "any":
        long = {"days": len(cube_days), "first_step": sum(
            r[-1] for d in cube_days for r in (d.get("rows") or [])
            if not source or source.lower() in (r[2].lower(), r[3].lower()))}
    elif cube_days is not None and path_steps and steps[0]["kind"] == "path":
        long = {"days": len(cube_days), "first_step": sum(
            r[-1] for d in cube_days for r in (d.get("rows") or [])
            if r[0] != "(all others)" and matches(path_steps[0], r[1])
            and (not source or source.lower() in (r[2].lower(), r[3].lower())))}
    return {"first": first.isoformat(), "last": last.isoformat(), "visits": len(mine),
            "steps": out}, long


def _events(rows, names: list[str], source) -> int | None:
    """People's events of these kinds: rows are (day, event, source, n)."""
    if rows is None:
        return None
    want = (source or "").strip().lower()
    return sum(n for _, event, src, n in rows
               if event in names and (not want or (src or "").lower() == want))


def event_rows(history, site: str, config: dict, live_dir, first: date, anchor: date,
               today: date) -> list[tuple] | None:
    """(day, event, source, n) for people's events: whole stored days in
    [first, anchor] and today's spool. None when the beacon is off."""
    from . import beacon, events
    if not events.enabled(config):
        return None
    events.ensure(history.db)
    ok = {d for d, st in history.db.execute(
        "SELECT day, state FROM event_days WHERE site = ? AND day BETWEEN ? AND ?",
        (site, first.isoformat(), anchor.isoformat())) if st == "ok"}
    rows = [(d, e, src, n) for d, e, src, n in history.db.execute(
        "SELECT day, event, source, n FROM event_counts WHERE site = ? AND day BETWEEN ? AND ?",
        (site, first.isoformat(), anchor.isoformat())) if d in ok]
    try:
        spool = beacon.spool_dir(config, None, live_dir)
        for r in beacon.read_day(spool, today):
            if r.get("g") == "people":
                rows.append((today.isoformat(), r.get("e", ""), r.get("s", ""), 1))
    except Exception:                   # noqa: BLE001 - today's events missing, not the funnel
        pass
    return rows


def _leads(rows, tz, first: date, last: date, types: list[str], source) -> int | None:
    if rows is None:
        return None
    from .leads import _touch, counted, local_day, touch_labels, touch_source
    n = 0
    for row in rows:
        d = local_day(row, tz)
        if d is None or not first <= d <= last or not counted(row):
            continue
        if (row.get("type") or "") not in types:
            continue
        if source:
            touch = _touch(row.get("first_touch"))
            names = {touch_source(touch).lower(),
                     *(v.lower() for v in touch_labels(touch).values() if v)}
            if source.strip().lower() not in names:
                continue
        n += 1
    return n


# --------------------------------------------------------------- storage

def store_path(directory) -> Path | None:
    return Path(directory) / "funnels.json" if directory is not None else None


def saved(directory) -> list[dict]:
    path = store_path(directory)
    try:
        got = json.loads(path.read_text()) if path else {}
    except (OSError, ValueError):
        return []
    items = got.get("funnels") if isinstance(got, dict) else None
    return [f for f in (items or {}).values() if isinstance(f, dict)]


def clean(raw: dict) -> dict:
    """A funnel from the page, checked; raises Invalid."""
    name = str(raw.get("name") or "").strip()
    if not NAME.match(name):
        raise Invalid("a name of 1 to 60 letters, digits and simple punctuation")
    steps = raw.get("steps")
    if not isinstance(steps, list) or not 2 <= len(steps) <= MAX_STEPS:
        raise Invalid(f"2 to {MAX_STEPS} steps")
    out = []
    for s in steps:
        if not isinstance(s, dict):
            raise Invalid("each step is an object")
        label = " ".join(str(s.get("label") or "").split())[:60] or "Step"
        if s.get("kind") == "any":
            if out:
                raise Invalid("only the first step may be any visit")
            out.append({"label": label, "kind": "any"})
            continue
        if s.get("kind") == "event":
            names = [str(e) for e in s.get("events") or [] if EVENT.match(str(e))][:10]
            if not names:
                raise Invalid("an event step needs event names, e.g. cta_click")
            out.append({"label": label, "kind": "event", "events": names})
            continue
        if s.get("kind", "path") == "lead":
            types = [t for t in s.get("types") or [] if t in LEAD_TYPES]
            if not types:
                raise Invalid(f"a lead step needs types from {', '.join(LEAD_TYPES)}")
            out.append({"label": label, "kind": "lead", "types": types})
            continue
        match = s.get("match") or "equals"
        if match not in MATCHES:
            raise Invalid(f"match is one of {', '.join(MATCHES)}")
        paths = [str(p).strip()[:100] for p in (s.get("paths") or [])][:MAX_PATHS]
        if not paths or any(not p or (match in ("equals", "starts_with") and not p.startswith("/"))
                            or any(c in p for c in "<>\"' ") for p in paths):
            raise Invalid("each path step needs paths starting with /")
        out.append({"label": label, "kind": "path", "match": match, "paths": paths})
    if out[0]["kind"] not in ("path", "any"):
        raise Invalid("the first step is a page or any visit")
    source = str(raw.get("source") or "").strip()[:60] or None
    return {"name": name, "source": source, "steps": out}


def save(directory, raw: dict, by: str) -> dict:
    funnel = clean(raw)
    if funnel["name"] in {f["name"] for f in defaults()}:
        raise Invalid("that name is a default funnel's")
    path = store_path(directory)
    try:
        items = json.loads(path.read_text()).get("funnels") or {}
    except (OSError, ValueError, AttributeError):
        items = {}
    if funnel["name"] not in items and len(items) >= 30:
        raise Invalid("at most 30 saved funnels; delete one first")
    funnel.update(saved_by=by or "?", saved_at=datetime.now(timezone.utc)
                  .isoformat(timespec="seconds"))
    items[funnel["name"]] = funnel
    write_atomic(path, json.dumps({"funnels": items}, indent=1) + "\n")
    os.chmod(path, 0o640)
    _log(directory, "save", funnel["name"], by)
    return funnel


def delete(directory, name: str, by: str) -> None:
    path = store_path(directory)
    try:
        items = json.loads(path.read_text()).get("funnels") or {}
    except (OSError, ValueError, AttributeError):
        items = {}
    if name not in items:
        raise Invalid(f"no saved funnel {name!r}")
    items.pop(name)
    write_atomic(path, json.dumps({"funnels": items}, indent=1) + "\n")
    _log(directory, "delete", name, by)


def _log(directory, action: str, name: str, by: str) -> None:
    with open(Path(directory) / "funnels-changes.log", "a", encoding="utf-8") as handle:
        handle.write(f"{datetime.now(timezone.utc).isoformat(timespec='seconds')}\t{action}\t"
                     f"{name}\t{by or '?'}\n")


# ---------------------------------------------------------------- the file

def build(p) -> dict:
    from .leads import _page_journeys, connect, db_path, read_rows
    journeys, first = _page_journeys(p) if p.view is None else _view_journeys(p)
    rows = None
    path = db_path(p.config)
    if path is not None:
        try:
            db = connect(path)
            try:
                rows = read_rows(db)
            finally:
                db.close()
        except Exception:               # noqa: BLE001 - lead steps say "not recorded"
            rows = None
    cube = p.history.extras(p.key, p.anchor - timedelta(days=89), p.anchor, ("cube",))
    cube_days = [{"rows": (b.get("cube") or {}).get("rows")} for b in cube.values()]
    out = []
    site = p.key.split("::", 1)[0]
    try:
        events_rows = event_rows(p.history, site, p.config, p.live_dir, first, p.anchor, p.today)
    except Exception:                   # noqa: BLE001 - event steps say "not recorded"
        events_rows = None
    from .funnel_days import history
    for f in defaults(p.config) + saved(p.live_dir):
        result, long = compute(f, journeys, first, p.today, rows, p.tz, cube_days, events_rows)
        out.append({**f, "result": result, "long": long, "history": history(p, f)})
    return {"funnels": out, "api": {"list": "funnels", "save": "funnels/save",
                                    "delete": "funnels/delete"}}


def _view_journeys(p) -> tuple[list[dict], date]:
    """The view's journeys, from verified days only (ok or partial), as
    leads._page_journeys keeps the whole site's: a withheld day's journeys
    are never counted."""
    from .store_visits import journey_days
    first = p.today - timedelta(days=journey_days(p.config))
    got = [j for j in p.history.journeys(p.key, first, p.anchor)
           if (p.states.get(str(j.get("day"))) or {}).get("state") in ("ok", "partial")]
    if p.live_ok:
        got += list((p.snap or {}).get("journeys") or [])
    return got, first
