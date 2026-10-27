"""The second count of recorded journeys (recorded/, 2.43): shares only the name lists
in recorded/__init__.py with the main code.

From each stored event's raw JSON, read here with this file's own code:

  projection   every column (event_id, event_name, occurred_at, visitor_id,
               session_id, path, skald_vid, ip, email) is the raw JSON's value, and
               the session's opaque ref is its own hash of the session ID
  consent      every event kept says analytics "granted", a known event name and
               schema version 1
  sessions     one visitor per session ID
  withdrawn    no event is kept for a visitor whose withdrawal still stands
  figures      for a period: sessions that started in it, their visitors, pages read,
               actions and each event's count, compared with the main code's
               (recorded/queries.figures). A difference withholds the period's figures

    check(db, site, start, end, figures) -> list of problems ([] when it matches)
    daily(ctx, day)                      run-daily (audit_more.DAILY "recorded_journeys")
"""
from __future__ import annotations

import hashlib
import hmac
import json
import sqlite3
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

from .recorded import EVENTS, GRANTED, VERSION

PROJECTED = ("event_id", "event_name", "occurred_at", "visitor_id", "session_id", "path",
             "skald_vid", "ip", "email")
NOT_ACTIONS = ("session_started", "page_view")


def _when(text: str) -> datetime:
    return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def _have(db) -> bool:
    return db.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND "
                      "name = 'recorded_events'").fetchone() is not None


def _events(db, site: str, problems: list) -> list[dict]:
    """Every event of the site, from its raw JSON, after checking its columns."""
    out = []
    cols = ", ".join(("ref", "raw") + PROJECTED)
    for row in db.execute(f"SELECT {cols} FROM recorded_events WHERE site = ?", (site,)):
        ref, raw, columns = row[0], row[1], dict(zip(PROJECTED, row[2:]))
        try:
            e = json.loads(raw)
        except ValueError:
            problems.append("an event's raw JSON cannot be read")
            continue
        if not isinstance(e, dict):
            problems.append("an event's raw JSON is not an object")
            continue
        for key in PROJECTED:
            if e.get(key) != columns[key]:
                problems.append(f"an event's {key} column is not its raw value")
        mine = "s" + hashlib.sha256(f"{site}\0{e.get('session_id')}".encode()).hexdigest()[:12]
        if ref != mine:
            problems.append("an event's session ref is not its session's")
        if (e.get("consent") or {}).get("analytics") != GRANTED:
            problems.append("an event is kept without analytics consent")
        if e.get("event_name") not in EVENTS or e.get("schema_version") != VERSION:
            problems.append("an event is kept with an unknown name or version")
        out.append(e)
    return out


def _withdrawn(db, site: str, events: list[dict], now: datetime) -> list[str]:
    key = db.execute("SELECT value FROM meta WHERE key = 'recorded_hash_key'").fetchone()
    if key is None:
        return []
    stones = {r[0] for r in db.execute(
        "SELECT digest FROM recorded_tombstones WHERE site = ? AND expires_at > ?",
        (site, now.strftime("%Y-%m-%dT%H:%M:%SZ")))}
    if not stones:
        return []
    for vid in {e.get("visitor_id") for e in events}:
        mark = hmac.new(key[0].encode(), f"{site}\0{vid}".encode(), hashlib.sha256).hexdigest()
        if mark in stones:
            return ["events are kept for a visitor who withdrew"]
    return []


def recount(events: list[dict], start: datetime, end: datetime, problems: list) -> dict:
    """The period's figures from the raw events."""
    by_session: dict[str, list[dict]] = {}
    for e in events:
        by_session.setdefault(e["session_id"], []).append(e)
    got = {"sessions": 0, "visitors": 0, "page_views": 0, "actions": 0,
           "by_event": {name: 0 for name in EVENTS}}
    visitors = set()
    for sid, evs in by_session.items():
        owners = {e["visitor_id"] for e in evs}
        if len(owners) > 1:
            problems.append("a session holds two visitors")
        first = min(_when(e["occurred_at"]) for e in evs)
        if not start <= first < end:
            continue
        got["sessions"] += 1
        visitors |= owners
        for e in evs:
            got["by_event"][e["event_name"]] += 1
    got["visitors"] = len(visitors)
    got["page_views"] = got["by_event"]["page_view"]
    got["actions"] = sum(n for name, n in got["by_event"].items() if name not in NOT_ACTIONS)
    return got


def check(db, site: str, start: str, end: str, figures: dict,
          now: datetime | None = None) -> list[str]:
    """[] when the main code's `figures` for [start, end) are the raw events' own."""
    if not _have(db):
        return [] if not any((figures or {}).get(k) for k in ("sessions", "page_views")) \
            else ["figures are shown but no recorded event is kept"]
    problems: list[str] = []
    events = _events(db, site, problems)
    problems += _withdrawn(db, site, events, now or datetime.now(timezone.utc))
    got = recount(events, _when(start), _when(end), problems)
    for key in ("sessions", "visitors", "page_views", "actions"):
        if (figures or {}).get(key) != got[key]:
            problems.append(f"{key}: shown {figures.get(key)}, recounted {got[key]}")
    shown = (figures or {}).get("by_event") or {}
    for name in EVENTS:
        if shown.get(name, 0) != got["by_event"][name]:
            problems.append(f"{name}: shown {shown.get(name, 0)}, recounted {got['by_event'][name]}")
    return sorted(set(problems))


# ---------------------------------------------------------------- run-daily

def _path(ctx) -> Path | None:
    from .conversions.store import path_for
    folder = Path(ctx.db_path).parent if getattr(ctx, "db_path", None) else None
    got = path_for(ctx.config, folder)
    return got if got is not None and Path(got).is_file() else None


def set_up(ctx) -> bool:
    """True once the site has a recorded event."""
    path = _path(ctx)
    if path is None:
        return False
    try:
        db = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)
        try:
            return _have(db) and db.execute("SELECT 1 FROM recorded_events WHERE site = ? "
                                            "LIMIT 1", (ctx.site,)).fetchone() is not None
        finally:
            db.close()
    except sqlite3.Error:
        return False


def daily(ctx, day) -> list[str] | None:
    """The day (in the site's zone) recounted against the main code's figures."""
    from .recorded import queries
    from .window import zone
    path = _path(ctx)
    if path is None:
        return None
    tz = zone(ctx.config)
    start = datetime.combine(day, time(0), tzinfo=tz).astimezone(timezone.utc)
    end = datetime.combine(day + timedelta(days=1), time(0), tzinfo=tz).astimezone(timezone.utc)
    a, b = (x.strftime("%Y-%m-%dT%H:%M:%SZ") for x in (start, end))
    db = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)
    try:
        if not _have(db):
            return None
        shown = queries.figures(db, ctx.site, a, b)
        problems = check(db, ctx.site, a, b, shown, getattr(ctx, "now", None))
    finally:
        db.close()
    ctx.out(f"recorded journeys: {shown['sessions']} session(s), {shown['page_views']} "
            "page(s) read, recounted from the raw events")
    return problems
