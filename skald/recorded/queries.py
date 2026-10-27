"""Recorded journeys for the dashboard (journeys_api.py): sessions and their figures.

A session is what the site sent under one session ID, from its first event to its
last. It belongs to the day (in the site's time zone) of its first event. Its figures
are its own: sessions, visitors, pages read and actions, never added to the log's
visits (docs/JOURNEYS.md). audit_journeys.py recounts `figures` from the raw JSON.

    sessions(db, site, start, end, private)   the period's sessions, newest first
    figures(db, site, start, end)             {"sessions", "visitors", "page_views",
                                               "actions", "by_event"}
    session(db, site, ref, private)           one session, every event
    for_visit(db, site, visit)                the sessions linked to one kept log visit
    log_visits(db, site, ref)                 the kept log visits linked to a session

Linking a session to the log's own visit, never by guess:
    "visitor_id"   the session carries the script tag's visitor ID (skald_vid) and
                   that ID was matched to the visit (firsttouch.match_vids)
    "address"      the same kept address (the same privacy setting made both), with
                   the session inside the visit's time, a minute either side
`private`: owners and admins see the address and the email kept; others never do.
"""
from __future__ import annotations

from datetime import timedelta

from ..conversions import store as cstore
from . import ENDINGS, EVENTS
from .store import present

SLACK = timedelta(seconds=60)
LIMIT = 500
COLS = ("event_id", "event_name", "occurred_at", "visitor_id", "session_id", "ref", "path",
        "skald_vid", "ip", "email", "raw")


def _rows(db, sql: str, args=()) -> list[dict]:
    return [dict(zip(COLS, r)) for r in db.execute(
        f"SELECT {', '.join(COLS)} FROM recorded_events WHERE {sql} "
        "ORDER BY occurred_at, received_at, event_id", args)]


def _session(rows: list[dict], private: bool, earlier: bool) -> dict:
    import json
    first, last = rows[0], rows[-1]
    t0 = cstore.parse(first["occurred_at"])
    pages = [r for r in rows if r["event_name"] == "page_view"]
    actions = [r for r in rows if r["event_name"] not in ("session_started", "page_view")]
    touch = {}
    for r in rows:
        if r["event_name"] == "session_started":
            got = json.loads(r["raw"]).get("touch") or {}
            touch = {"landing": got.get("landing_path"),
                     "referrer": (got.get("referrer") or {}).get("host"),
                     **{k[4:]: got[k] for k in ("utm_source", "utm_medium", "utm_campaign")
                        if got.get(k)}}
            break
    ended = next((name for name in ENDINGS if any(a["event_name"] == name for a in actions)), "")
    out = {"ref": first["ref"], "start": first["occurred_at"], "end": last["occurred_at"],
           "seconds": int((cstore.parse(last["occurred_at"]) - t0).total_seconds()),
           "landing": (touch.get("landing") or (pages[0]["path"] if pages else first["path"])),
           "pages": len(pages), "events": len(rows), "returning": earlier,
           "trail": [[p["path"], int((cstore.parse(p["occurred_at"]) - t0).total_seconds())]
                     for p in pages[:100]],
           "actions": [{"event": a["event_name"], "path": a["path"],
                        "label": json.loads(a["raw"]).get("label"),
                        "at": int((cstore.parse(a["occurred_at"]) - t0).total_seconds())}
                       for a in actions[:50]],
           "ended": ended, "touch": {k: v for k, v in touch.items() if k != "landing" and v},
           "script_id": any(r["skald_vid"] for r in rows)}
    if private:
        out["ip"] = next((r["ip"] for r in rows if r["ip"]), None)
        out["email"] = next((r["email"] for r in rows if r["email"]), None)
    return out


def _grouped(rows: list[dict]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for r in rows:
        out.setdefault(r["ref"], []).append(r)
    return out


def _earlier(db, site: str, sessions: dict[str, list[dict]]) -> set[str]:
    """The refs whose visitor had a session before this one."""
    out = set()
    for ref, rows in sessions.items():
        if db.execute("SELECT 1 FROM recorded_events WHERE site = ? AND visitor_id = ? AND "
                      "ref != ? AND occurred_at < ? LIMIT 1",
                      (site, rows[0]["visitor_id"], ref, rows[0]["occurred_at"])).fetchone():
            out.add(ref)
    return out


def _in_period(db, site: str, start: str, end: str) -> dict[str, list[dict]]:
    """Every event of each session that started in [start, end)."""
    refs = [r[0] for r in db.execute(
        "SELECT ref FROM recorded_events WHERE site = ? GROUP BY ref "
        "HAVING MIN(occurred_at) >= ? AND MIN(occurred_at) < ?", (site, start, end))]
    out: dict[str, list[dict]] = {}
    for i in range(0, len(refs), 400):
        part = refs[i:i + 400]
        rows = _rows(db, f"site = ? AND ref IN ({','.join('?' * len(part))})", (site, *part))
        out.update(_grouped(rows))
    return out


def sessions(db, site: str, start: str, end: str, private: bool = False,
             limit: int = LIMIT) -> list[dict]:
    if not present(db):
        return []
    found = _in_period(db, site, start, end)
    earlier = _earlier(db, site, found)
    got = [_session(rows, private, ref in earlier) for ref, rows in found.items()]
    got.sort(key=lambda s: (s["start"], s["ref"]), reverse=True)
    return got[:limit]


def figures(db, site: str, start: str, end: str) -> dict:
    """The period's figures: sessions (started in it), their visitors, pages read
    and actions (every event but session_started and page_view), by event."""
    out = {"sessions": 0, "visitors": 0, "page_views": 0, "actions": 0,
           "by_event": dict.fromkeys(EVENTS, 0)}
    if not present(db):
        return out
    found = _in_period(db, site, start, end)
    visitors = set()
    for rows in found.values():
        visitors.add(rows[0]["visitor_id"])
        for r in rows:
            out["by_event"][r["event_name"]] = out["by_event"].get(r["event_name"], 0) + 1
    out["sessions"], out["visitors"] = len(found), len(visitors)
    out["page_views"] = out["by_event"]["page_view"]
    out["actions"] = sum(n for k, n in out["by_event"].items()
                         if k not in ("session_started", "page_view"))
    return out


def session(db, site: str, ref: str, private: bool = False) -> dict | None:
    if not present(db):
        return None
    rows = _rows(db, "site = ? AND ref = ?", (site, ref))
    if not rows:
        return None
    earlier = _earlier(db, site, {ref: rows})
    out = _session(rows, private, ref in earlier)
    others = db.execute("SELECT COUNT(DISTINCT ref) FROM recorded_events WHERE site = ? AND "
                        "visitor_id = ?", (site, rows[0]["visitor_id"])).fetchone()[0]
    out["visitor_sessions"] = int(others)
    return out


def for_visit(db, site: str, visit: dict, vid: str | None = None,
              private: bool = False) -> list[dict]:
    """The sessions linked to one kept log visit {start, end, ip}: by the visitor
    ID matched to it (`vid`), and by the same address inside its time."""
    if not present(db):
        return []
    lo = cstore.stamp(cstore.parse(visit["start"]) - SLACK)
    hi = cstore.stamp(cstore.parse(visit.get("end") or visit["start"]) + SLACK)
    how: dict[str, str] = {}
    if vid:
        for (ref,) in db.execute("SELECT DISTINCT ref FROM recorded_events WHERE site = ? AND "
                                 "skald_vid = ? AND occurred_at >= ? AND occurred_at <= ?",
                                 (site, vid, lo, hi)):
            how[ref] = "visitor_id"
    if visit.get("ip") and visit["ip"] != "(removed)":
        for (ref,) in db.execute("SELECT DISTINCT ref FROM recorded_events WHERE site = ? AND "
                                 "ip = ? AND occurred_at >= ? AND occurred_at <= ?",
                                 (site, visit["ip"], lo, hi)):
            how.setdefault(ref, "address")
    out = []
    for ref, by in how.items():
        got = session(db, site, ref, private)
        if got:
            out.append({**got, "linked_by": by})
    return sorted(out, key=lambda s: s["start"])


def log_visits(db, site: str, ref: str) -> list[dict]:
    """The kept log visits linked to the session by the same address inside their
    time (a visit kept with its address: people/visits.py). Labels and times only."""
    if not present(db):
        return []
    have = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    if "visits" not in have:
        return []
    rows = _rows(db, "site = ? AND ref = ?", (site, ref))
    ip = next((r["ip"] for r in rows if r["ip"]), None)
    if not rows or not ip:
        return []
    a, b = rows[0]["occurred_at"], rows[-1]["occurred_at"]
    out = []
    for r in db.execute("SELECT day, seq, start, end, source, landing, pages FROM visits "
                        "WHERE site = ? AND ip = ? AND start <= ? AND end >= ? ORDER BY start",
                        (site, ip, cstore.stamp(cstore.parse(b) + SLACK),
                         cstore.stamp(cstore.parse(a) - SLACK))):
        out.append({"day": r[0], "seq": r[1], "start": r[2], "end": r[3], "source": r[4],
                    "landing": r[5], "pages": r[6], "linked_by": "address"})
    return out
