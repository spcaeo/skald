"""Retention cohorts: of the visitors first seen in week W (or on day D), how
many came back in each later week (day). Counted from what is kept, stored as
totals per cohort, recounted by audit_retention.py on its own road.

Who is the same visitor (one identity per site, the first of the first-touch
links, firsttouch.py, that can follow a visitor for weeks):

    address  the kept visits (people/visits.py): the same address with the
             same browser and system, while the site keeps addresses
             (privacy.keep_ips). Horizon H: privacy.keep_days (395).
    hash     else the keyed 30-day code (visitors.py), when the visitor key is
             set. Horizon H: visitors.repeat_days (30). It holds a day and a
             source type per visitor: no country, device, landing page or
             page count, so those splits and "read 2 or more pages" are not
             recorded on this road.
    None     neither: nothing is counted, and the page says why.

The beacon's visitor ID (firsttouch.py's first link) is not used here: it is
seen only on visits that ran the page script, and its page views are kept
journeys.vid_days (30) days, so the same visitor would count as one or two
depending on the script. A forgotten address ("(removed)") is followed by
nothing: its visits are counted in `removed`, never in a cohort.

New, back, and how far a cohort can be followed:

    lookback L   max(H - SPAN, ceil(H / 2)) days: a visitor is NEW on its
                 first visit in the cohort period when no visit of the same
                 identity is kept in the L days before it
    reach        H - L - 1 days: the latest day after a cohort's first day
                 whose cell can be counted while every input is still kept
    back         a member with a visit in the later period (week +k, day +k)
    deep         a member with a visit in that period that read 2 or more pages

A cohort is counted (and counted again each run, the same answer) while the
store still holds every day it reads: from L days before its first day to
yesterday. While nothing has been pruned yet (the store began less than H
days ago) a cohort whose lookback starts before the store began is counted
with `since`: "new" means first seen since that day. Once its inputs are
pruned a cohort is kept as last counted, never counted again: its cells are
"inputs expired", and a later cell it never reached is "not recorded" - never
0. Days are the site's local days; a week starts on Monday.

Stored in history's day_extras on the cohort's first day, kinds
retention_week and retention_day (KINDS), for the whole site only (never a
view). A recount of that day (backfill --force) clears it; the next run
counts it again where its inputs are still kept.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import date, timedelta
from pathlib import Path

VERSION = 1
SPAN = 63                    # the cohort week and the 8 weeks after it
DEEP = 2                     # pages in one visit: "read 2 or more pages"
OFFSETS = {"week": 8, "day": 14}
COHORTS = {"week": 12, "day": 30}
KINDS = {"week": "retention_week", "day": "retention_day"}
SPLITS = ("source", "country", "device", "landing")
TOP = 8                      # values kept per split; the rest are OTHER
OTHER = "(other)"
REMOVED = "(removed)"
DIRECT = "Direct or unknown"


# ------------------------------------------------------------------ the rule

def lookback(horizon: int) -> int:
    return max(int(horizon) - SPAN, (int(horizon) + 1) // 2)


def reach(horizon: int) -> int:
    return int(horizon) - lookback(horizon) - 1


def identity(config: dict, folder, keyed: bool | None = None) -> dict | None:
    """{"by", "horizon", "lookback", "reach"} for this site, or None."""
    from .people import policy
    from .visitors import load_key, repeat_days
    if folder is not None and policy.keep_ips(config, folder):
        by, horizon = "address", policy.keep_days(config)
    elif (load_key(config) is not None) if keyed is None else keyed:
        by, horizon = "hash", repeat_days(config)
    else:
        return None
    return {"by": by, "horizon": horizon, "lookback": lookback(horizon),
            "reach": reach(horizon)}


def week_of(day: date) -> date:
    return day - timedelta(days=day.weekday())


def period(grain: str, start: date, k: int = 0) -> tuple[date, date]:
    """[first, last] of the period k periods after the one starting `start`."""
    n = 7 if grain == "week" else 1
    first = start + timedelta(days=n * k)
    return first, first + timedelta(days=n - 1)


def starts(grain: str, last: date, count: int | None = None) -> list[date]:
    """The cohort periods worth counting: the `count` latest that are over by `last`."""
    count = COHORTS[grain] if count is None else count
    if grain == "week":
        top = week_of(last) if week_of(last) + timedelta(days=6) <= last \
            else week_of(last) - timedelta(days=7)
        return [top - timedelta(days=7 * i) for i in range(count)][::-1]
    return [last - timedelta(days=i) for i in range(count)][::-1]


# ------------------------------------------------------------------ the inputs

class Inputs:
    """What the store holds from `lo` to `hi` (whole days): each identity's
    visits in order, and its latest visit before `lo` (back to `old`)."""

    def __init__(self, by: str) -> None:
        self.by = by
        self.visits: dict[tuple, list[dict]] = {}
        self.before: dict[tuple, date] = {}
        self.removed: dict[date, int] = {}
        self.begun: date | None = None


def _ro(path) -> sqlite3.Connection | None:
    if path is None or not Path(path).is_file():
        return None
    db = sqlite3.connect(f"file:{Path(path).resolve()}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    return db


def _tables(db) -> set:
    return {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}


VISIT = ("day", "seq", "start", "source", "via", "landing", "country", "device", "browser",
         "os", "pages", "seconds", "city", "trail", "campaign", "exit")


def load_kept(cdb, site: str, old: date, lo: date, hi: date) -> Inputs:
    """The kept visits (address road)."""
    got = Inputs("address")
    if cdb is None or not {"visits", "visit_days"} <= _tables(cdb):
        return got
    row = cdb.execute("SELECT MIN(day) FROM visit_days WHERE site = ? AND state = 'whole'",
                      (site,)).fetchone()
    got.begun = date.fromisoformat(row[0]) if row and row[0] else None
    whole = "day IN (SELECT day FROM visit_days WHERE site = ? AND state = 'whole')"
    for r in cdb.execute(f"SELECT ip, browser, os, MAX(day) AS last FROM visits WHERE site = ? "
                         f"AND day >= ? AND day < ? AND ip <> ? AND {whole} "
                         f"GROUP BY ip, browser, os",
                         (site, old.isoformat(), lo.isoformat(), REMOVED, site)):
        got.before[(r["ip"], r["browser"], r["os"])] = date.fromisoformat(r["last"])
    cols = [c for c in VISIT if c in {r[1] for r in cdb.execute("PRAGMA table_info(visits)")}]
    for r in cdb.execute(f"SELECT ip, browser, os, {', '.join(cols)} FROM visits WHERE "
                         f"site = ? AND day >= ? AND day <= ? AND {whole} ORDER BY start, seq",
                         (site, lo.isoformat(), hi.isoformat(), site)):
        d = date.fromisoformat(r["day"])
        if r["ip"] == REMOVED:
            got.removed[d] = got.removed.get(d, 0) + 1
            continue
        v = {c: r[c] for c in cols}
        v["day"] = d
        got.visits.setdefault((r["ip"], r["browser"], r["os"]), []).append(v)
    return got


def load_hashes(hdb, site: str, old: date, lo: date, hi: date) -> Inputs:
    """The 30-day codes (hash road): one row per visitor and day."""
    got = Inputs("hash")
    if hdb is None or "visitor_days" not in _tables(hdb):
        return got
    row = hdb.execute("SELECT MIN(day) FROM visitor_days WHERE site = ?", (site,)).fetchone()
    got.begun = date.fromisoformat(row[0]) if row and row[0] else None
    for visitor, last in hdb.execute(
            "SELECT visitor, MAX(day) FROM visitor_days WHERE site = ? AND kind = 'reader' "
            "AND day >= ? AND day < ? GROUP BY visitor", (site, old.isoformat(), lo.isoformat())):
        got.before[(visitor,)] = date.fromisoformat(last)
    for visitor, d, source in hdb.execute(
            "SELECT visitor, day, source FROM visitor_days WHERE site = ? AND kind = 'reader' "
            "AND day >= ? AND day <= ? ORDER BY day", (site, lo.isoformat(), hi.isoformat())):
        got.visits.setdefault((visitor,), []).append(
            {"day": date.fromisoformat(d), "source": source or DIRECT, "pages": None})
    return got


def load(config: dict, folder, history_db, site: str, ident: dict, old: date, lo: date,
         hi: date) -> Inputs:
    if ident["by"] == "address":
        from .conversions import store
        cdb = _ro(store.path_for(config, folder) if folder is not None else None)
        try:
            return load_kept(cdb, site, old, lo, hi)
        finally:
            if cdb is not None:
                cdb.close()
    return load_hashes(history_db, site, old, lo, hi)


def begun(config: dict, folder, history_db, site: str, by: str) -> date | None:
    """The first whole day the identity's store holds for the site."""
    if by == "address":
        from .conversions import store
        db = _ro(store.path_for(config, folder) if folder is not None else None)
        sql = "SELECT MIN(day) FROM visit_days WHERE site = ? AND state = 'whole'"
        table = "visit_days"
    else:
        db, sql, table = history_db, "SELECT MIN(day) FROM visitor_days WHERE site = ?", \
            "visitor_days"
    if db is None:
        return None
    try:
        if table not in _tables(db):
            return None
        row = db.execute(sql, (site,)).fetchone()
    finally:
        if by == "address":
            db.close()
    return date.fromisoformat(row[0]) if row and row[0] else None


# ------------------------------------------------------------------ counting

def window(ident: dict, inputs: Inputs, start: date, today: date) -> tuple[bool, str | None]:
    """(countable now, `since`) for the cohort starting `start` (see the module)."""
    need = start - timedelta(days=ident["lookback"])
    kept_from = today - timedelta(days=ident["horizon"])
    begun = inputs.begun
    if begun is None or start < begun:
        return False, None
    if begun <= kept_from:                      # pruned: every input must still be kept
        return need >= kept_from, None
    return True, (begun.isoformat() if need < begun else None)


def members(inputs: Inputs, grain: str, start: date, L: int) -> list[tuple[tuple, dict]]:
    """[(identity, its first visit in the period)] of the visitors new in it."""
    first, last = period(grain, start)
    out = []
    if not hasattr(inputs, "days"):
        inputs.days = {}
        for key, visits in inputs.visits.items():
            for v in visits:
                inputs.days.setdefault(v["day"], set()).add(key)
    keys = set().union(*(inputs.days.get(first + timedelta(days=i), set())
                         for i in range((last - first).days + 1)))
    for key in sorted(keys, key=str):
        visits = inputs.visits[key]
        v0 = next((v for v in visits if first <= v["day"] <= last), None)
        if v0 is None:
            continue
        edge = v0["day"] - timedelta(days=L)
        if any(edge <= v["day"] < v0["day"] for v in visits):
            continue
        before = inputs.before.get(key)
        if before is not None and before >= edge:
            continue
        out.append((key, v0))
    return out


def came_back(visits: list[dict], first: date, last: date) -> tuple[dict | None, dict | None]:
    """(the first visit in [first, last], the first there that read DEEP pages)."""
    back = next((v for v in visits if first <= v["day"] <= last), None)
    deep = next((v for v in visits if first <= v["day"] <= last and
                 (v.get("pages") or 0) >= DEEP), None)
    return back, deep


def label(v0: dict, dim: str) -> str:
    raw = v0.get(dim)
    if dim == "source":
        return raw or DIRECT
    return str(raw) if raw not in (None, "") else "Unknown"


def count(inputs: Inputs, ident: dict, grain: str, start: date, last_day: date) -> dict:
    """One cohort's blob (without the store's bookkeeping)."""
    L = ident["lookback"]
    hash_road = inputs.by == "hash"
    group = members(inputs, grain, start, L)
    offsets = [k for k in range(1, OFFSETS[grain] + 1) if period(grain, start, k)[1] <= last_day]
    cells = {str(k): [0, None if hash_road else 0] for k in offsets}
    dims = ("source",) if hash_road else SPLITS
    split: dict[str, dict] = {d: {} for d in dims}
    for key, v0 in group:
        visits = inputs.visits[key]
        for d in dims:
            row = split[d].setdefault(label(v0, d), {"size": 0, "cells": {
                str(k): [0, None if hash_road else 0] for k in offsets}})
            row["size"] += 1
        for k in offsets:
            back, deep = came_back(visits, *period(grain, start, k))
            if back is None:
                continue
            cells[str(k)][0] += 1
            if not hash_road and deep is not None:
                cells[str(k)][1] += 1
            for d in dims:
                c = split[d][label(v0, d)]["cells"][str(k)]
                c[0] += 1
                if not hash_road and deep is not None:
                    c[1] += 1
    first, last = period(grain, start)
    removed = sum(n for d, n in inputs.removed.items() if first <= d <= last)
    return {"version": VERSION, "grain": grain, "start": first.isoformat(),
            "end": last.isoformat(), "by": ident["by"], "horizon": ident["horizon"],
            "lookback": L, "size": len(group), "cells": cells,
            "split": {d: fold(rows) for d, rows in split.items()}, "removed": removed,
            "deep": None if hash_road else DEEP}


def fold(rows: dict) -> dict:
    """The TOP biggest values; the rest summed into OTHER (cells too)."""
    order = sorted(rows, key=lambda v: (-rows[v]["size"], v))
    out = {v: rows[v] for v in order[:TOP]}
    rest = order[TOP:]
    if rest:
        other = {"size": 0, "cells": {}}
        for v in rest:
            other["size"] += rows[v]["size"]
            for k, (b, d) in rows[v]["cells"].items():
                c = other["cells"].setdefault(k, [0, None if d is None else 0])
                c[0] += b
                if d is not None:
                    c[1] += d
        out[OTHER] = other
    return out


# ------------------------------------------------------------------ the run

def record(config: dict, folder, history_db, site: str, today: date,
           keyed: bool | None = None) -> dict | None:
    """Count every cohort worth counting whose inputs are still kept, and keep
    it on its first day. None when the site has no identity (see the module).
    {"counted", "left"}: cohorts counted now, and those left as they were."""
    ident = identity(config, folder, keyed)
    if ident is None or history_db is None or "::" in site:
        return None
    last_day = today - timedelta(days=1)
    # The latest cohorts, and every stored one that may still be countable
    # (a forgotten address changes it: counted again, never left stale).
    todo = {g: set(starts(g, last_day)) for g in KINDS}
    edge = (today - timedelta(days=ident["horizon"])).isoformat()
    for day, kind in history_db.execute(
            "SELECT day, kind FROM day_extras WHERE site = ? AND kind IN (?, ?) AND day >= ?",
            (site, *KINDS.values(), edge)):
        todo["week" if kind == KINDS["week"] else "day"].add(date.fromisoformat(day))
    # Every cohort and cell in full from `lo`; before it, each identity's
    # latest visit, back to the lookback of the oldest cohort.
    lo = min(min(todo["week"]), min(todo["day"]))
    inputs = load(config, folder, history_db, site, ident,
                  lo - timedelta(days=ident["lookback"]), lo, last_day)
    out = {"counted": 0, "left": 0, "identity": ident}
    rows = []
    for grain in ("week", "day"):
        for start in sorted(todo[grain]):
            ok, since = window(ident, inputs, start, today)
            if not ok:
                out["left"] += 1
                continue
            blob = count(inputs, ident, grain, start, last_day)
            blob.update(computed=last_day.isoformat(), since=since,
                        kept_from=(today - timedelta(days=ident["horizon"])).isoformat())
            rows.append((site, start.isoformat(), KINDS[grain],
                         json.dumps(blob, sort_keys=True)))
            out["counted"] += 1
    with history_db:
        history_db.executemany("INSERT OR REPLACE INTO day_extras (site, day, kind, data) "
                               "VALUES (?, ?, ?, ?)", rows)
    return out


def after_collect(ctx) -> None:
    """collect, backfill and run-daily: count the cohorts after the days are
    stored (the whole site only). A failure is said, never stops the run."""
    try:
        with ctx.history() as history:
            got = record(ctx.config, Path(ctx.db_path).parent, history.db, ctx.site,
                         ctx.now.date())
    except (OSError, sqlite3.Error, ValueError) as why:
        ctx.err(f"retention: not counted: {type(why).__name__}: {why}")
        return
    if got is not None:
        ctx.out(f"retention: {got['counted']} cohorts counted by {got['identity']['by']}"
                + (f", {got['left']} left as last counted" if got["left"] else ""))
