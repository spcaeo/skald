"""History for the day extras (schema 9) and the 30-day visitor hashes.

`day_extras(site, day, kind, data)` holds one JSON blob per kind per day -
hourly, ours, not_found, pages, campaigns, returning - exactly as
extras.Extras.finish made them (and visitors.annotate completed them).
They are totals and labels: paths, hosts, names, counts and HH:MM times.
`days.extras` is 1 for a day that has them.

`visitor_days` (visitors.py) is written for the whole site only, never for
a view, and only when the visitor key is configured; rows older than 30
days are deleted on every collect.
"""
from __future__ import annotations

import json
from datetime import date

from . import visitors

KINDS = ("hourly", "ours", "not_found", "pages", "campaigns", "returning",
         # release 2: crawler checks, link previews and fake browsers; data
         # quality; the independent audit's result (written by note()).
         "bots", "quality", "audit",
         # the drill-down cube (cube.py); the hourly figures by UTC hour
         "cube", "hourly_utc",
         # each assistant's and search crawler's requests by path (robots.py)
         "crawler_paths",
         # release 3b: every reader's visit by all its labels (compare), and
         # each page's first times that day (lifecycle)
         "visit_cube", "page_firsts", "page_counts",
         # phase 4 (day_more.py; each written once its module exists): saved
         # funnels counted daily, engagement and new/returning by source and
         # device, campaign tag hygiene
         "funnels", "engagement", "utm_hygiene",
         # likely sent by an AI assistant (inferred, ai_likely.py), and the
         # user fetches it rests on, kept ai_likely.FETCH_DAYS
         "ai_likely", "ai_fetches")

SCHEMA = """
CREATE TABLE IF NOT EXISTS day_extras (
    site TEXT NOT NULL,
    day  TEXT NOT NULL,
    kind TEXT NOT NULL,                  -- see store_extras.KINDS
    data TEXT NOT NULL,                  -- JSON, totals and labels only
    PRIMARY KEY (site, day, kind)
);
""" + visitors.SCHEMA


def write(db, site: str, day: date, totals) -> int | None:
    """Replace a day's extras (inside History.record's transaction).
    Returns the days.extras flag: 1 when written, None when not counted."""
    key = (site, day.isoformat())
    db.execute("DELETE FROM day_extras WHERE site = ? AND day = ?", key)
    extras = getattr(totals, "extras", None)
    if not extras:
        return None
    blobs = dict(extras)
    if getattr(totals, "returning", None) is not None:
        blobs["returning"] = totals.returning
    db.executemany("INSERT INTO day_extras (site, day, kind, data) VALUES (?, ?, ?, ?)",
                   [(*key, kind, json.dumps(blobs[kind], sort_keys=True))
                    for kind in KINDS if kind in blobs])
    if "::" not in site and getattr(totals, "visitor_seen", None) is not None:
        visitors.record(db, site, day, totals.visitor_seen)
    if "::" not in site and blobs.get("page_firsts"):
        record_milestones(db, site, blobs["page_firsts"])
    return 1


def record_milestones(db, site: str, firsts: dict) -> None:
    """Keep each page's earliest time per kind (and crawler or assistant):
    a later day never moves one, an earlier one (a backfill) does."""
    rows = []
    for path, keys in firsts.items():
        for key, (at, who) in keys.items():
            kind = key.split("|", 1)[0]
            name = key.split("|", 1)[1] if "|" in key else ""
            rows.append((site, path, kind, name, at, who if kind == "from_search" else ""))
    db.executemany(
        "INSERT INTO page_milestones (site, path, kind, who, at, via) VALUES (?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(site, path, kind, who) DO UPDATE SET at = excluded.at, via = excluded.via "
        "WHERE excluded.at < page_milestones.at", rows)


def rebuild_milestones(db, site: str, tz) -> int:
    """Work every milestone out again from the stored days' page_firsts.

    record_milestones only ever moves a milestone earlier, which is right
    for a day collected late and wrong for a day recounted under a stricter
    rule: a scraper's "first human visitor" would stay for good. So after a
    recount (backfill --force) the milestones the stored days cover are
    deleted and rebuilt from them; one older than the oldest stored detail
    (report.retention_days) has nothing to be rebuilt from, and is kept.
    Returns the number of milestones afterwards."""
    from datetime import datetime, time, timezone
    rows = db.execute("SELECT day, data FROM day_extras WHERE site = ? AND kind = 'page_firsts' "
                      "ORDER BY day", (site,)).fetchall()
    if not rows:
        return 0
    oldest = date.fromisoformat(rows[0][0])
    since = datetime.combine(oldest, time(0), tzinfo=tz).astimezone(timezone.utc)
    with db:
        db.execute("DELETE FROM page_milestones WHERE site = ? AND at >= ?",
                   (site, since.isoformat(timespec="seconds")))
        for _, data in rows:
            record_milestones(db, site, json.loads(data))
    return db.execute("SELECT COUNT(*) FROM page_milestones WHERE site = ?",
                      (site,)).fetchone()[0]


def note(db, site: str, day: date, kind: str, blob: dict) -> None:
    """Set one blob for a stored day (the audit's result). Re-collecting
    the day deletes it, as it should: a new count needs a new audit."""
    with db:
        db.execute("INSERT OR REPLACE INTO day_extras (site, day, kind, data) "
                   "VALUES (?, ?, ?, ?)", (site, day.isoformat(), kind,
                                           json.dumps(blob, sort_keys=True)))


def read(db, site: str, first: date, last: date,
         kinds: tuple[str, ...] = KINDS) -> dict[str, dict]:
    """{day: {kind: blob}} for the stored days in [first, last]."""
    marks = ",".join("?" * len(kinds))
    out: dict[str, dict] = {}
    for day, kind, data in db.execute(
            f"SELECT day, kind, data FROM day_extras WHERE site = ? AND day BETWEEN ? AND ? "
            f"AND kind IN ({marks})", (site, first.isoformat(), last.isoformat(), *kinds)):
        try:
            out.setdefault(day, {})[kind] = json.loads(data)
        except ValueError:
            continue
    return out
