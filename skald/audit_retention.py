"""The second count of the retention cohorts (retention.py).

Registered in audit_more.DAILY: run-daily's recounts step reads every stored
cohort (day_extras kinds retention_week and retention_day) and, for each one
whose inputs are still kept, counts it again from the same kept rows with its
own SQL - conversions.sqlite `visits` (the address road) or history's
`visitor_days` (the 30-day code), opened read-only - by the documented rule
(DATA-CONTRACT-PEOPLE.md, "Retention cohorts"):

  same visitor   address, browser and system all equal (a NULL browser or
                 system equals only NULL); the address "(removed)" is nobody.
                 Or the same 30-day code. Whole days only (visit_days
                 state 'whole'); today's rows are not read.
  new            its earliest visit in the cohort period (by start, then seq)
                 has no visit of the same visitor in the `lookback` days before
                 it; lookback = H - 63, or half of H rounded up when that is
                 more (H: the horizon the blob names)
  back / deep    a visit in the later period / one there with 2 or more pages
  splits         by the first visit's labels; each value the blob names is
                 checked, and "(other)" against the rest
  checkable      the store still holds every day the cohort reads: from
                 `lookback` days before its first day (or, while nothing has
                 been pruned yet, from the store's first day) to yesterday

A cohort whose inputs are past their keeping is "not checkable (inputs
expired)": said, counted, never a problem - it stays as last counted and
checked. The verdict is written into each checked blob (`audit`: {"on", "ok",
"problems"}), so the page withholds a cohort that does not match. Which road,
horizon and lookback were used are settings, read from the blob; the lookback
is checked against the rule. Nothing from retention.py is called.
"""
from __future__ import annotations

import json
import sqlite3
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

from .audit_people import _store

KINDS = ("retention_week", "retention_day")
GONE = "(removed)"
OTHER = "(other)"
NO_SOURCE = "Direct or unknown"


def set_up(ctx) -> bool:
    """True once a cohort is stored (the run before counted one)."""
    db = _open(getattr(ctx, "db_path", None))
    if db is None:
        return False
    try:
        return db.execute("SELECT 1 FROM day_extras WHERE site = ? AND kind IN (?, ?) LIMIT 1",
                          (ctx.site, *KINDS)).fetchone() is not None
    except sqlite3.Error:
        return False
    finally:
        db.close()


def _open(path) -> sqlite3.Connection | None:
    if path is None or not Path(path).is_file():
        return None
    return sqlite3.connect(f"file:{Path(path).resolve()}?mode=ro", uri=True)


def _rule(horizon: int) -> int:
    half = -(-int(horizon) // 2)
    return int(horizon) - 63 if int(horizon) - 63 >= half else half


def _span(grain: str, start: date, k: int) -> tuple[str, str]:
    step = 7 if grain == "retention_week" else 1
    a = start + timedelta(days=step * k)
    return a.isoformat(), (a + timedelta(days=step - 1)).isoformat()


class Road:
    """One store, read with the audit's own SQL."""

    def __init__(self, by: str, db, site: str) -> None:
        self.by, self.db, self.site = by, db, site
        if by == "address":
            self.table = "visits"
            self.who = "ip || char(31) || IFNULL(browser, char(30)) || char(31) || " \
                       "IFNULL(os, char(30))"
            self.where = (f"site = '{_q(site)}' AND ip <> '{GONE}' AND day IN (SELECT day "
                          f"FROM visit_days WHERE site = '{_q(site)}' AND state = 'whole')")
        else:
            self.table = "visitor_days"
            self.who = "visitor"
            self.where = f"site = '{_q(site)}' AND kind = 'reader'"

    def first_day(self) -> date | None:
        if self.by == "address":
            sql = "SELECT MIN(day) FROM visit_days WHERE site = ? AND state = 'whole'"
        else:
            sql = "SELECT MIN(day) FROM visitor_days WHERE site = ?"
        got = self.db.execute(sql, (self.site,)).fetchone()
        return date.fromisoformat(got[0]) if got and got[0] else None

    def seen(self, a: str, b: str, deep: bool = False) -> set:
        extra = " AND pages >= 2" if deep else ""
        return {r[0] for r in self.db.execute(
            f"SELECT DISTINCT {self.who} FROM {self.table} WHERE {self.where} "
            f"AND day >= ? AND day <= ?{extra}", (a, b))}

    def firsts(self, a: str, b: str) -> dict[str, dict]:
        """{visitor: its first visit in [a, b]} with day and labels."""
        if self.by == "address":
            rows = self.db.execute(
                f"SELECT {self.who}, day, start, seq, source, country, device, landing "
                f"FROM {self.table} WHERE {self.where} AND day >= ? AND day <= ?", (a, b))
            out: dict[str, tuple] = {}
            for who, day, start, seq, *labels in rows:
                if who not in out or (start, seq) < out[who][0]:
                    out[who] = ((start, seq), day, labels)
            return {w: {"day": d, "source": l[0] or NO_SOURCE,
                        "country": l[1] or "Unknown", "device": l[2] or "Unknown",
                        "landing": l[3] or "Unknown"} for w, (_, d, l) in out.items()}
        got: dict[str, dict] = {}
        for who, day, source in self.db.execute(
                f"SELECT visitor, day, source FROM visitor_days WHERE {self.where} AND "
                f"day >= ? AND day <= ? ORDER BY day DESC", (a, b)):
            got[who] = {"day": day, "source": source or NO_SOURCE}
        return got

    def earlier(self, who: str, day: str, lookback: int) -> bool:
        edge = (date.fromisoformat(day) - timedelta(days=lookback)).isoformat()
        return self.db.execute(
            f"SELECT 1 FROM {self.table} WHERE {self.where} AND {self.who} = ? AND day >= ? "
            f"AND day < ? LIMIT 1", (who, edge, day)).fetchone() is not None


def _q(text: str) -> str:
    return str(text).replace("'", "''")


def checkable(blob: dict, first: date | None, today: date) -> bool:
    start = date.fromisoformat(blob["start"])
    if first is None or start < first:
        return False
    kept_from = today - timedelta(days=int(blob["horizon"]))
    if first > kept_from:                       # nothing pruned yet
        return True
    return start - timedelta(days=int(blob["lookback"])) >= kept_from


def recount(road: Road, kind: str, blob: dict, yesterday: date) -> dict:
    start = date.fromisoformat(blob["start"])
    a, b = _span(kind, start, 0)
    firsts = road.firsts(a, b)
    new = {w: v for w, v in firsts.items() if not road.earlier(w, v["day"], int(blob["lookback"]))}
    got = {"size": len(new), "cells": {}, "split": {}, "end": b}
    dims = ("source", "country", "device", "landing") if road.by == "address" else ("source",)
    split = {d: Counter(v[d] for v in new.values()) for d in dims}
    got["split"] = {d: {"size": c, "cells": {}} for d, c in split.items()}
    k = 1
    while k <= (8 if kind == "retention_week" else 14):
        pa, pb = _span(kind, start, k)
        if date.fromisoformat(pb) > yesterday:
            break
        back = road.seen(pa, pb) & set(new)
        deep = road.seen(pa, pb, True) & set(new) if road.by == "address" else None
        got["cells"][str(k)] = [len(back), None if deep is None else len(deep)]
        for d in dims:
            got["split"][d]["cells"][str(k)] = (
                Counter(new[w][d] for w in back),
                None if deep is None else Counter(new[w][d] for w in deep))
        k += 1
    return got


def compare(kind: str, blob: dict, got: dict, problems: list) -> None:
    name = f"retention {kind[10:]} of {blob['start']}"

    def same(what: str, stored, counted) -> None:
        if stored != counted:
            problems.append(f"{name}: {what}: stored {stored}, the recount finds {counted}")

    same("last day", blob.get("end"), got["end"])
    if kind == "retention_week":
        same("starts on a Monday", date.fromisoformat(blob["start"]).weekday(), 0)
    same("lookback days", int(blob.get("lookback", -1)), _rule(int(blob["horizon"])))
    same("new visitors", int(blob.get("size", -1)), got["size"])
    stored_cells = blob.get("cells") or {}
    same("weeks or days counted", sorted(stored_cells, key=int), sorted(got["cells"], key=int))
    for k, (b, d) in got["cells"].items():
        s = stored_cells.get(k) or [None, None]
        same(f"+{k} came back", s[0], b)
        same(f"+{k} came back and read 2 or more pages", s[1], d)
    for dim, part in got["split"].items():
        rows = (blob.get("split") or {}).get(dim) or {}
        named = [v for v in rows if v != OTHER]
        _split(same, f"by {dim}", rows, named, part["size"], lambda r: r.get("size"))
        for k, (backs, deeps) in part["cells"].items():
            _split(same, f"by {dim} +{k} came back", rows, named, backs,
                   lambda r, k=k: ((r.get("cells") or {}).get(k) or [None])[0])
            if deeps is not None:
                _split(same, f"by {dim} +{k} read 2 or more pages", rows, named, deeps,
                       lambda r, k=k: ((r.get("cells") or {}).get(k) or [None, None])[1])
    if set(got["split"]) != set(blob.get("split") or {}):
        same("splits", sorted(blob.get("split") or {}), sorted(got["split"]))


def _split(same, what: str, rows: dict, named: list, counted: Counter, pick) -> None:
    for v in named:
        same(f"{what} {v}", pick(rows[v]), counted.get(v, 0))
    rest = sum(counted.values()) - sum(counted.get(v, 0) for v in named)
    if OTHER in rows or rest:
        same(f"{what} {OTHER}", pick(rows[OTHER]) if OTHER in rows else 0, rest)


def check(history_db, cdb, site: str, today: date, on: str | None = None) -> dict:
    """{"checked", "expired", "problems"} over every stored cohort; each
    checked blob gets the verdict (written only when `on` is given)."""
    yesterday = today - timedelta(days=1)
    out = {"checked": 0, "expired": 0, "problems": []}
    rows = history_db.execute(
        f"SELECT day, kind, data FROM day_extras WHERE site = ? AND kind IN "
        f"({', '.join('?' * len(KINDS))}) ORDER BY kind, day", (site, *KINDS)).fetchall()
    roads: dict[str, Road] = {}
    verdicts = []
    for day, kind, data in rows:
        blob = json.loads(data)
        by = blob.get("by")
        db = cdb if by == "address" else history_db if by == "hash" else None
        if db is None:
            out["expired"] += 1
            continue
        road = roads.setdefault(by, Road(by, db, site))
        if not checkable(blob, road.first_day(), today):
            out["expired"] += 1
            continue
        found: list[str] = []
        compare(kind, blob, recount(road, kind, blob, yesterday), found)
        out["checked"] += 1
        out["problems"] += found
        blob["audit"] = {"on": on, "ok": not found, "problems": len(found)}
        verdicts.append((json.dumps(blob, sort_keys=True), site, day, kind))
    if on is not None and verdicts:
        with history_db:
            history_db.executemany("UPDATE day_extras SET data = ? WHERE site = ? AND day = ? "
                                   "AND kind = ?", verdicts)
    return out


def daily(ctx, day) -> list[str] | None:
    """run-daily: the problems found (empty: they match); None when no cohort is stored."""
    import sqlite3 as sq
    cdb = _open(_store(ctx.config))
    try:
        with ctx.history() as history:
            if history.db.execute("SELECT 1 FROM day_extras WHERE site = ? AND kind IN (?, ?) "
                                  "LIMIT 1", (ctx.site, *KINDS)).fetchone() is None:
                return None
            got = check(history.db, cdb, ctx.site, ctx.now.date(), day.isoformat())
    except sq.Error as why:
        return [f"retention: the stores could not be read: {type(why).__name__}"]
    finally:
        if cdb is not None:
            cdb.close()
    ctx.out(f"retention: {got['checked']} cohorts recounted"
            + (f", {got['expired']} not checkable (inputs expired)" if got["expired"] else ""))
    return got["problems"]
