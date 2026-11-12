"""A lead's own visits, in order (#30, 2.46.5). A listing, never a figure.

For the conversions a person search found (people/lookup.py), the server-log
visits that are that person's, each marked how it is known:

    proven   the only visit that sent a form (a POST) within PROVEN_SECONDS of
             a conversion's time. The site's server reports a lead the moment
             its form is sent, so the visit that sent it is the lead's. Two or
             more visits in that window: none is proven.
    likely   another visit from the same address and the same browser (user
             agent) as a proven one, from AROUND_HOURS before the first proven
             visit to AROUND_HOURS after the last conversion. Likely the same
             person, never certain: an office or a phone network shares an
             address. A visit whose address was dropped (privacy, "(removed)")
             or that has no browser line links no other visit.

`path` returns the visits oldest first, each with its `link` (proven or
likely), `why`, and the conversion steps it sent (`steps`); `first` is the
earliest visit's source (where the person first came from); `unmatched` the
steps no visit is proven for (a payment page, a tool's own webhook, a form
sent from another network). Nothing here is counted into any figure; only
callers who may see a person (admins and owners) get it, through `person`.

`visit_marks` (#31) is the other way round, for Traffic > Visitors: which
visits are proven, by the same rule, to have sent a lead ("lead") or a step
of someone who has paid ("customer": a paid row on the same reference), so
the visit list and the visitor drawer show a small pill. Proven only: a likely link is never marked. Labels, never a
figure: app.json's journeys carry them (`won`; no address, no reference, no
name), put there by `mark_journeys` each run (dashboard_webapp.write). The
second road is audit_lead_visits.marks_by_own_road.
"""
from __future__ import annotations

import json
import sqlite3
from bisect import bisect_left, bisect_right
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

from ..conversions import FINISHED, LEAD_ACTIONS, store
from .visits import REMOVED, _row, posted_near

PROVEN_SECONDS = 10
AROUND_HOURS = 24
LIMIT = 200
MARK_LIMIT = 2000               # finished conversions read for the marks, newest first


def _step(c: dict) -> dict:
    return {"action": c.get("action"), "stage": c.get("stage"), "at": c.get("at"),
            "tool": c.get("tool"), "ref": c.get("external_ref")}


def path(db, site: str, conversions: list[dict]) -> dict:
    """The person's visits, proven and likely, oldest first (see the module)."""
    rows = sorted((c for c in conversions if c.get("at") and not c.get("test")),
                  key=lambda c: (str(c["at"]), c.get("id") or 0))
    visits: dict = {}
    unmatched = []
    for c in rows:
        near = posted_near(db, site, c["at"], before=PROVEN_SECONDS, after=PROVEN_SECONDS)
        if len(near) != 1:
            unmatched.append({**_step(c), "why": "no visit sent a form at its time" if not near
                              else f"{len(near)} visits sent a form at its time"})
            continue
        v = near[0]
        key = (v["day"], v["seq"])
        got = visits.setdefault(key, {**v, "link": "proven", "steps": [],
                                      "why": "the only visit that sent a form at the lead's time"})
        got["steps"].append(_step(c))
    proven = list(visits.values())
    if proven:
        first = min(store.parse(v["start"]) for v in proven)
        last = max([store.parse(c["at"]) for c in rows] + [store.parse(v["end"]) for v in proven])
        lo = store.stamp(first - timedelta(hours=AROUND_HOURS))
        hi = store.stamp(last + timedelta(hours=AROUND_HOURS))
        # A dropped address ("(removed)", privacy) or a missing browser links nobody.
        pairs = {(v["ip"], v.get("user_agent") or "") for v in proven}
        for ip, agent in sorted((i, a) for i, a in pairs if i and i != REMOVED and a):
            for r in db.execute("SELECT * FROM visits WHERE site = ? AND ip = ? AND "
                                "COALESCE(user_agent, '') = ? AND start >= ? AND start <= ? "
                                "ORDER BY start LIMIT ?", (site, ip, agent, lo, hi, LIMIT)):
                v = _row(r)
                visits.setdefault((v["day"], v["seq"]), {
                    **v, "link": "likely", "steps": [],
                    "why": "the same address and browser as a proven visit"})
    ordered = sorted(visits.values(), key=lambda v: (v["start"], v["seq"]))
    head = ordered[0] if ordered else None
    return {"visits": ordered, "unmatched": unmatched,
            "first": {k: head.get(k) for k in ("start", "source", "via", "referrer", "campaign",
                                                 "landing", "link")} if head else None}


# ------------------------------------------------------------------ marks (#31)

def visit_marks(db, site: str, lo: str, hi: str) -> dict[str, str]:
    """{"<day>.<seq>": "lead" | "customer"}: the visits proven (the rule of
    `path`: the only kept visit that sent a form within PROVEN_SECONDS) for a
    finished conversion (completed or paid, not test) whose time is in [lo, hi)
    (UTC stamps). "customer" when its tool and reference have a paid row, at
    any time (the person paid); else "lead" when it is a lead action
    (conversions.LEAD_ACTIONS); else no mark.

    Cheap and bounded, for a run every 2 minutes: one read of the window's
    conversions (index conversions_at), none more when there are none; one of
    the visits that sent a form on the days around them (index visits_day; a
    visit is kept under the local day it started: from 2 days before a
    conversion's UTC day to 1 day after); one of the paid rows of the
    references found. Reads only."""
    found = [r for r in db.execute(
        "SELECT tool, external_ref, action, stage, at FROM conversions WHERE site = ? AND "
        "test = 0 AND stage IN (?, ?) AND at >= ? AND at < ? ORDER BY at DESC LIMIT ?",
        (site, *FINISHED, lo, hi, MARK_LIMIT)) if r[4]]
    days: set[str] = set()
    for *_, at in found:
        try:
            u = store.parse(at).date()
        except ValueError:
            continue
        days |= {(u + timedelta(days=k)).isoformat() for k in (-2, -1, 0, 1)}
    if not days:
        return {}
    posts: list[tuple[str, str]] = []           # (stamp, "day.seq"): every form sent
    for day, seq, raw in db.execute(
            f"SELECT day, seq, posts FROM visits WHERE site = ? AND day IN "
            f"({','.join('?' * len(days))}) AND posts IS NOT NULL AND posts <> '[]'",
            (site, *sorted(days))):
        try:
            stamps = json.loads(raw or "[]")
        except ValueError:
            continue
        posts += [(str(t), f"{day}.{seq}") for t in stamps or [] if t]
    posts.sort()
    times = [t for t, _ in posts]
    proven: list[tuple[str, tuple, str]] = []
    for tool, ref, action, _, at in found:
        try:
            when = store.parse(at)
        except ValueError:
            continue
        a = store.stamp(when - timedelta(seconds=PROVEN_SECONDS))
        b = store.stamp(when + timedelta(seconds=PROVEN_SECONDS))
        near = {key for _, key in posts[bisect_left(times, a):bisect_right(times, b)]}
        if len(near) == 1:
            proven.append((near.pop(), (tool, ref), action))
    if not proven:
        return {}
    paid: set = set()
    refs = sorted({ref for _, (_, ref), _ in proven if ref})
    for i in range(0, len(refs), 500):
        part = refs[i:i + 500]
        paid |= {(t, r) for t, r in db.execute(
            f"SELECT DISTINCT tool, external_ref FROM conversions WHERE site = ? AND test = 0 "
            f"AND stage = 'paid' AND external_ref IN ({','.join('?' * len(part))})",
            (site, *part))}
    out: dict[str, str] = {}
    for key, lead, action in proven:
        mark = "customer" if lead in paid else "lead" if action in LEAD_ACTIONS else None
        if mark and out.get(key) != "customer":
            out[key] = mark
    return out


def mark_journeys(config: dict, folder, site: str, journeys: list[dict]) -> list[dict]:
    """The journeys with `won` ("lead" or "customer") on each visit proven to
    have sent one (visit_marks over the journeys' days). The journeys as they
    were when the site keeps no visits or conversions, or the store cannot be
    read: a label, never in the way of the page."""
    days = sorted({str(j.get("day")) for j in journeys
                   if j.get("day") and j.get("seq") is not None})
    if not days or folder is None:
        return journeys
    try:
        path = store.path_for(config, Path(folder))
        if path is None or not Path(path).is_file():
            return journeys
        first, last = date.fromisoformat(days[0]), date.fromisoformat(days[-1])
        # A visit's day is local; the forms it sent are within a day of it in UTC.
        lo = datetime.combine(first - timedelta(days=1), time(0), tzinfo=timezone.utc)
        hi = datetime.combine(last + timedelta(days=2), time(0), tzinfo=timezone.utc)
        db = sqlite3.connect(f"file:{Path(path).resolve()}?mode=ro", uri=True)
        try:
            have = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
            if not {"conversions", "visits"} <= have:
                return journeys
            marks = visit_marks(db, site, store.stamp(lo), store.stamp(hi))
        finally:
            db.close()
    except (OSError, ValueError, sqlite3.Error):
        return journeys
    if not marks:
        return journeys
    return [{**j, "won": marks[k]} if (k := f"{j.get('day')}.{j.get('seq')}") in marks else j
            for j in journeys]

