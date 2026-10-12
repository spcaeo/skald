"""The second count of conversions.json's figures (conversions_data.py), by
SQL GROUP BY over conversions.sqlite opened read-only.

conversions_data.py counts in Python from plain SELECTs; this module
counts the same figures again in SQL: local days as UTC bounds in a VALUES
table, buckets by SQL CASE over strftime('%s'), abandonment by NOT EXISTS,
assisted sources and pages by joins. It shares only the name lists in
conversions/__init__.py (the finished stages, the labels for what was not
recorded, the bucket names) and the file's location. Called by
audit_conversions.check_file; a day or block it disagrees with is withheld.

likely_ai (inferred, ai_likely.py): each finished row's first touch is
picked in SQL (the row's own, else the visitor ID's earliest journeys row),
its minute by strftime('%s') of a well-formed UTC stamp, and it is matched
against the history's stored AI user fetches read by audit_leads' own SQL,
by this module's own window rule.
"""
from __future__ import annotations

import sqlite3
from collections import Counter
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

from .audit_leads import _attribution, _bare, _fetches
from .classify import AI_LIKELY_MANY
from .config import site_name
from .conversions import FINISHED, UNKNOWN

COLUMNS = ("source_type", "first_source", "campaign", "landing", "country", "device", "tool")
STAMP = "%Y-%m-%dT%H:%M:%SZ"
DAY = 86400
TOP = 50


def _utc(d: date, tz) -> str:
    return datetime.combine(d, time(0), tzinfo=tz).astimezone(timezone.utc).strftime(STAMP)


def _bounds(tz, first: date, last: date) -> tuple[str, list]:
    rows, args = [], []
    d = first
    while d <= last:
        rows.append("(?, ?, ?)")
        args += [d.isoformat(), _utc(d, tz), _utc(d + timedelta(days=1), tz)]
        d += timedelta(days=1)
    return f"WITH b(day, lo, hi) AS (VALUES {', '.join(rows)}) ", args


def _open(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{Path(path).resolve()}?mode=ro", uri=True)


def _fin() -> str:
    return "(" + ", ".join(f"'{s}'" for s in FINISHED) + ")"


VISITS = ("CASE WHEN c.visits_before IS NULL OR typeof(c.visits_before) <> 'integer' "
          "OR c.visits_before < 0 THEN 'unknown' WHEN c.visits_before <= 2 "
          "THEN CAST(c.visits_before AS TEXT) WHEN c.visits_before <= 5 THEN '3-5' "
          "WHEN c.visits_before <= 10 THEN '6-10' ELSE '11+' END")
GAP = ("(CAST(strftime('%s', c.at) AS INTEGER) - "
       "CAST(strftime('%s', c.first_touch_at) AS INTEGER))")
CONVERT = (f"CASE WHEN c.first_touch_at IS NULL OR strftime('%s', c.first_touch_at) IS NULL "
           f"THEN 'unknown' WHEN {GAP} < 0 THEN 'clock_error' WHEN {GAP} < 3600 THEN '<1h' "
           f"WHEN {GAP} < {DAY} THEN '<1d' WHEN {GAP} < {8 * DAY} THEN '1-7d' "
           f"WHEN {GAP} < {31 * DAY} THEN '8-30d' WHEN {GAP} < {91 * DAY} THEN '31-90d' "
           f"ELSE '>90d' END")


FIRST = ("CASE WHEN c.first_source IS NOT NULL THEN {own} WHEN c.vid IS NOT NULL THEN "
         "(SELECT j.{col} FROM journeys j WHERE j.site = c.site AND j.vid = c.vid AND "
         "j.at <= c.at ORDER BY j.at, j.rowid LIMIT 1) END")
WELL_FORMED = "'[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z'"


def _likely_rows(db, head: str, args: list, site: str):
    """(day, action, source, minute, page, n) per finished row's first touch."""
    pick = {name: FIRST.format(own=own, col=col) for name, own, col in (
        ("src", "c.first_source", "source_type"), ("tat", "c.first_touch_at", "at"),
        ("page", "c.landing", "path"))}
    sql = (head.rstrip() + f", t AS (SELECT b.day AS day, c.action AS action, {pick['src']} AS "
           f"src, {pick['tat']} AS tat, {pick['page']} AS page FROM conversions c JOIN b ON "
           f"c.at >= b.lo AND c.at < b.hi WHERE c.site = ? AND c.test = 0 "
           f"AND c.stage IN {_fin()}) "
           f"SELECT day, action, src, CASE WHEN tat GLOB {WELL_FORMED} THEN "
           f"CAST(strftime('%s', tat) AS INTEGER) / 60 END, page, COUNT(*) FROM t "
           f"GROUP BY 1, 2, 3, 4, 5")
    return db.execute(sql, [*args, site]).fetchall()


def _likely(src, stamp, page, fetched, window: int, tz) -> str:
    if src is None:
        return UNKNOWN
    if src != "Direct or unknown":
        return "(none)"
    if fetched is None or stamp is None or not page:
        return UNKNOWN
    days, pages = fetched
    if any(datetime.fromtimestamp(m * 60, tz).date().isoformat() not in days
           for m in (stamp - window, stamp)):
        return UNKNOWN
    who = {w for m, w in pages.get(_bare(page), ()) if m <= stamp <= m + window}
    return (who.pop() if len(who) == 1 else AI_LIKELY_MANY) if who else "(none)"


def recount(path: Path, site: str, tz, first: date, last: date, now: str,
            hours: float, history=None, config: dict | None = None) -> dict[str, Counter]:
    """{day: Counter} keyed ("stages", action, stage), ("abandoned", action),
    ("by", column, action, label), ("visits", action, bucket), ("ttc",
    action, bucket), ("likely", action, label) and, when the site has
    journeys, ("assisted", action, source)."""
    head, args = _bounds(tz, first, last)
    # A row marked test is never a figure: left out here by this road's own SQL.
    join = ("FROM conversions c JOIN b ON c.at >= b.lo AND c.at < b.hi WHERE c.site = ? "
            "AND c.test = 0 ")
    out: dict[str, Counter] = {}

    def put(rows, *kind):
        for day, *key, n in rows:
            out.setdefault(day, Counter())[(*kind, *key)] += n

    db = _open(path)
    try:
        def q(sql, extra=()):
            return db.execute(head + sql, [*args, site, *extra]).fetchall()

        put(q(f"SELECT b.day, c.action, c.stage, COUNT(*) {join}GROUP BY 1, 2, 3"), "stages")
        for col in COLUMNS:
            rows = db.execute(head + f"SELECT b.day, c.action, COALESCE(NULLIF(c.{col}, ''), "
                              f"?), COUNT(*) {join}AND c.stage IN {_fin()} GROUP BY 1, 2, 3",
                              [*args, UNKNOWN, site]).fetchall()
            put(rows, "by", col)
        put(q(f"SELECT b.day, c.action, {VISITS}, COUNT(*) {join}AND c.stage IN {_fin()} "
              f"GROUP BY 1, 2, 3"), "visits")
        put(q(f"SELECT b.day, c.action, {CONVERT}, COUNT(*) {join}AND c.stage IN {_fin()} "
              f"GROUP BY 1, 2, 3"), "ttc")
        cutoff = (datetime.strptime(now, STAMP) - timedelta(hours=hours)).strftime(STAMP)
        put(q(f"SELECT b.day, c.action, COUNT(*) {join}AND c.stage = 'started' AND c.vid IS "
              f"NOT NULL AND c.at <= ? AND NOT EXISTS (SELECT 1 FROM conversions f WHERE "
              f"f.site = c.site AND f.test = 0 AND (f.vid = c.vid OR (c.identity_id IS NOT NULL AND "
              f"f.identity_id = c.identity_id)) AND f.action = c.action AND f.stage IN "
              f"{_fin()} AND f.at >= c.at AND f.at <= strftime('%Y-%m-%dT%H:%M:%SZ', c.at, "
              f"'+{float(hours)} hours')) GROUP BY 1, 2", (cutoff,)), "abandoned")
        on, window = _attribution(config)
        fetched = _fetches(history, site_name(config or {}),
                           last - timedelta(days=_keep() + 1), last) if on else None
        for day, action, src, stamp, page, n in _likely_rows(db, head, args, site):
            out.setdefault(day, Counter())[("likely", action,
                                            _likely(src, stamp, page, fetched, window, tz))] += n
        if db.execute("SELECT COUNT(*) FROM journeys WHERE site = ?", (site,)).fetchone()[0]:
            via = join.replace("WHERE", "JOIN journeys j ON j.site = c.site AND j.vid = c.vid "
                                        "AND j.at < c.at WHERE")
            put(q(f"SELECT b.day, c.action, j.source_type, COUNT(DISTINCT c.id) {via}AND "
                  f"c.stage IN {_fin()} AND j.source_type IS NOT NULL AND j.source_type <> '' "
                  f"AND (c.source_type IS NULL OR j.source_type <> c.source_type) "
                  f"GROUP BY 1, 2, 3"), "assisted")
    finally:
        db.close()
    return out


def _keep() -> int:
    from .ai_likely import FETCH_DAYS
    return FETCH_DAYS


def _flat(day: dict) -> Counter:
    """A conversions.json day as the recount's keys."""
    out: Counter = Counter()
    for action, per in (day.get("stages") or {}).items():
        for stage, n in per.items():
            out[("stages", action, stage)] += n
    for action, n in (day.get("abandoned") or {}).items():
        out[("abandoned", action)] += n
    for col, table in (day.get("by") or {}).items():
        for action, per in table.items():
            for label, n in per.items():
                out[("by", col, action, label)] += n
    for name, kind in (("visits_before", "visits"), ("time_to_convert", "ttc"),
                       ("assisted", "assisted"), ("likely_ai", "likely")):
        for action, per in (day.get(name) or {}).items():
            for key, n in per.items():
                out[(kind, action, key)] += n
    return +out


def check_days(path: Path, site: str, tz, first: date, last: date, now: str, hours: float,
               days: list[dict], history=None, config: dict | None = None
               ) -> dict[str, list[str]]:
    """{day: problems} for every shown day the SQL count disagrees with."""
    shown = [d for d in days if d.get("state") == "ok"]
    if not shown:
        return {}
    counted = recount(path, site, tz, first, last, now, hours, history, config)
    out: dict[str, list[str]] = {}
    for d in shown:
        mine, theirs = _flat(d), +counted.get(d["day"], Counter())
        if d.get("assisted") is None:
            theirs = Counter({k: n for k, n in theirs.items() if k[0] != "assisted"})
        for key in sorted(set(mine) | set(theirs), key=str):
            if mine[key] != theirs[key]:
                out.setdefault(d["day"], []).append(
                    f"{d['day']} {' '.join(map(str, key))}: file {mine[key]}, "
                    f"SQL recount {theirs[key]}")
    return out


def recount_pages(path: Path, site: str, tz, first: date, last: date) -> dict | None:
    """{"converting", "other", "pages": {path: (converting, other)}}; None
    without journeys."""
    lo, hi = _utc(first, tz), _utc(last + timedelta(days=1), tz)
    db = _open(path)
    try:
        if not db.execute("SELECT COUNT(*) FROM journeys WHERE site = ?",
                          (site,)).fetchone()[0]:
            return None
        conv = (f"WITH conv AS (SELECT vid, MIN(at) AS at FROM conversions WHERE site = ? AND "
                f"test = 0 AND vid IS NOT NULL AND stage IN {_fin()} AND at >= ? AND at < ? "
                f"GROUP BY vid) ")
        a = (site, lo, hi, site)
        converting = db.execute(conv + "SELECT COUNT(DISTINCT c.vid) FROM conv c JOIN journeys "
                                "j ON j.site = ? AND j.vid = c.vid AND j.at <= c.at",
                                a).fetchone()[0]
        mine = dict(db.execute(conv + "SELECT j.path, COUNT(DISTINCT c.vid) FROM conv c JOIN "
                               "journeys j ON j.site = ? AND j.vid = c.vid AND j.at <= c.at "
                               "GROUP BY j.path", a).fetchall())
        rest = ("FROM journeys WHERE site = ? AND at >= ? AND at < ? AND vid NOT IN "
                "(SELECT vid FROM conv)")
        b = (site, lo, hi, site, lo, hi)
        other = db.execute(conv + f"SELECT COUNT(DISTINCT vid) {rest}", b).fetchone()[0]
        theirs = dict(db.execute(conv + f"SELECT path, COUNT(DISTINCT vid) {rest} "
                                 f"GROUP BY path", b).fetchall())
    finally:
        db.close()
    return {"converting": converting, "other": other,
            "pages": {p: (mine.get(p, 0), theirs.get(p, 0)) for p in set(mine) | set(theirs)}}


def check_pages(path: Path, site: str, tz, first: date, last: date, block) -> list[str]:
    """Problems with conversions.json's pages_before."""
    got = recount_pages(path, site, tz, first, last)
    if got is None or block is None:
        return [] if got is None and block is None else \
            [f"pages_before is {'missing' if block is None else 'shown'} but the SQL count "
             f"{'has' if got is not None else 'has no'} journeys"]
    out = []
    for key in ("converting", "other"):
        if block.get(key) != got[key]:
            out.append(f"pages_before {key}: file {block.get(key)}, SQL recount {got[key]}")
    ranked = sorted(got["pages"], key=lambda p: (-got["pages"][p][0], -got["pages"][p][1], p))
    if [r[0] for r in block.get("pages") or []] != ranked[:TOP]:
        out.append("pages_before: the pages listed are not the SQL recount's top pages")
    for path_, c, o in block.get("pages") or []:
        if got["pages"].get(path_) != (c, o):
            out.append(f"pages_before {path_}: file {c}/{o}, SQL recount "
                       f"{got['pages'].get(path_)}")
    return out
