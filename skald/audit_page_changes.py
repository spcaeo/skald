"""The second count of page_changes.json (page_changes.py): "did my change work?".

page_changes.py puts stored day figures side by side, per tracked change, from the
Page's history reader and conversions.json's audited days. This module works every
figure the file shows out again by its own road:

  the marks     its own SQL over accounts.sqlite's todo_marks: per page and day, the
                newest row (by time, then row id); a change is tracked when that row
                says "changed"
  a day         audit_page_trends.states: the `days` table read by SQL (whole "ok",
                "partial", "withheld", "missing", "before")
  the page      its path cut at "?" and "#", a "/" added unless it ends with one
  landings      the stored blob read by its own SQL; the page's rows summed; a day
                that keeps its top pages only, without this one, is a floor
  reads         the stored ai_fetches rows of the page, summed
  leads         its own SQL GROUP BY over conversions.sqlite: finished rows, not test,
                not a lead's repeat finish (audit_conversions_figures.once), by the
                site's local day and landing page; a day shown without a figure must
                be one conversions.json could not give: before the first row, outside
                its 180 days, withheld by its own second count, or no conversions at all
  each side     the days, totals, per day, share, the change and the verdict, by its own
                arithmetic, with the thresholds page_changes.py names

It shares only the thresholds and the figure names (MIN_DAYS, MAX_DAYS, MIN_SIDE,
MIN_TOTAL, MIN_VISITS, SWING, MEASURES) with page_changes.py. A change whose figures
it does not find the same is left out of the file and named, never shown.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

from .page_changes import MAX_DAYS, MEASURES, MIN_DAYS, MIN_SIDE, MIN_TOTAL, MIN_VISITS, SWING

REST = "(all others)"
CONV_DAYS = 180          # conversions.json's days (DATA-CONTRACT-CONVERSIONS.md)
CLOSE = 1e-3             # figures per day and shares are shown to 4 places


def _page(path) -> str:
    cut = str(path or "")
    for mark in ("?", "#"):
        cut = cut.split(mark, 1)[0]
    return cut if cut.endswith("/") else cut + "/"


def tracked(path: Path | None, site: str) -> dict | None:
    """{(page, day): {"kind", "note"}} by this road's SQL; None without the file."""
    if path is None or not Path(path).is_file():
        return None
    db = sqlite3.connect(f"file:{Path(path).resolve()}?mode=ro", uri=True)
    try:
        rows = db.execute(
            "SELECT t.item, t.day, t.state, t.kind, t.note FROM todo_marks t WHERE t.site = ? AND "
            "substr(t.item, 1, 5) = 'page:' AND t.rowid = (SELECT u.rowid FROM todo_marks u WHERE "
            "u.site = t.site AND u.item = t.item AND u.day = t.day ORDER BY u.at DESC, u.rowid DESC "
            "LIMIT 1)", (site,)).fetchall()
    except sqlite3.Error:
        return {}
    finally:
        db.close()
    return {(item[5:], day): {"kind": kind, "note": note or ""}
            for item, day, state, kind, note in rows if state == "changed"}


def _blobs(db, key: str, first: str, last: str) -> dict:
    out: dict = {}
    for day, kind, data in db.execute(
            "SELECT day, kind, data FROM day_extras WHERE site = ? AND day >= ? AND day <= ? AND "
            "kind IN ('landings', 'ai_fetches')", (key, first, last)):
        try:
            out.setdefault(day, {})[kind] = json.loads(data)
        except ValueError:
            continue
    return out


def _local_bounds(tz, d: date) -> tuple[str, str]:
    f = "%Y-%m-%dT%H:%M:%SZ"
    lo = datetime.combine(d, time(0), tzinfo=tz).astimezone(timezone.utc)
    hi = datetime.combine(d + timedelta(days=1), time(0), tzinfo=tz).astimezone(timezone.utc)
    return lo.strftime(f), hi.strftime(f)


def leads(path: Path | None, site: str, tz, first: date, last: date) -> tuple[dict, str | None]:
    """({day: {page: n}}, the first local day with any row) by this road's SQL."""
    if path is None or not Path(path).is_file():
        return {}, None
    from .audit_conversions_figures import _bounds, _fin, once
    head, args = _bounds(tz, first, last)
    db = sqlite3.connect(f"file:{Path(path).resolve()}?mode=ro", uri=True)
    try:
        rows = db.execute(head + "SELECT b.day, c.landing, COUNT(*) FROM conversions c JOIN b ON "
                          "c.at >= b.lo AND c.at < b.hi WHERE c.site = ? AND c.test = 0 AND "
                          f"c.stage IN {_fin()} AND {once()}AND c.landing GLOB '/*' GROUP BY 1, 2",
                          [*args, site]).fetchall()
        lo = db.execute("SELECT MIN(at) FROM conversions WHERE site = ?", (site,)).fetchone()[0]
    except sqlite3.Error:
        return {}, None
    finally:
        db.close()
    out: dict = {}
    for day, landing, n in rows:
        per = out.setdefault(day, {})
        per[_page(landing)] = per.get(_page(landing), 0) + int(n)
    first_day = None
    if lo:
        first_day = datetime.strptime(lo, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).astimezone(tz).date()
    return out, first_day.isoformat() if first_day else None


def _sd2(xs: list[float]) -> float:
    k = len(xs)
    if k < 2:
        return 0.0
    m = sum(xs) / k
    return sum((x - m) * (x - m) for x in xs) / (k - 1)


def _expect(day: date, anchor: date, rows: dict) -> dict:
    """The sides and the verdicts of one change, from {day: figures} this road counted."""
    n = min(MAX_DAYS, (anchor - day).days) if anchor > day else 0
    before = [(day - timedelta(days=i)).isoformat() for i in range(n, 0, -1)]
    after = [(day + timedelta(days=i)).isoformat() for i in range(1, n + 1)]
    out = {"n": n, "figures": {}}
    for m, _w, _b in MEASURES:
        sides, vals = {}, {}
        for name, days in (("before", before), ("after", after)):
            got = [rows[d] for d in days]
            if m == "left":
                have = [g for g in got if g["visits"] is not None]
                v = sum(g["visits"] for g in have)
                o = sum(g["one_page"] for g in have)
                sides[name] = {"days": len(have), "visits": v if have else None,
                               "one_page": o if have else None, "share": o / v if v else None}
                vals[name] = [g["one_page"] / g["visits"] for g in have if g["visits"]]
            else:
                have = [g[m] for g in got if g[m] is not None]
                sides[name] = {"days": len(have), "total": sum(have) if have else None,
                               "per_day": sum(have) / len(have) if have else None}
                vals[name] = [float(x) for x in have]
        b, a = sides["before"], sides["after"]
        if n < MIN_DAYS:
            v = "too_early"
        elif b["days"] == 0 or a["days"] == 0:
            v = "not_recorded"
        elif min(b["days"], a["days"]) < MIN_SIDE:
            v = "not_enough_days"
        else:
            few = (b["visits"] < MIN_VISITS or a["visits"] < MIN_VISITS) if m == "left" \
                else (b["total"] + a["total"] < MIN_TOTAL)
            if few:
                v = "too_few"
            else:
                gap = (a["share"] - b["share"]) if m == "left" else (a["per_day"] - b["per_day"])
                swing = (_sd2(vals["before"]) / len(vals["before"]) if vals["before"] else 0.0) + \
                        (_sd2(vals["after"]) / len(vals["after"]) if vals["after"] else 0.0)
                v = "no_clear_change" if gap == 0 or gap * gap <= SWING * SWING * swing else (
                    "up" if gap > 0 else "down")
        out["figures"][m] = {"before": b, "after": a, "verdict": v}
    return out


def _near(a, b) -> bool:
    if a is None or b is None:
        return a is None and b is None
    return abs(float(a) - float(b)) <= CLOSE


def check_one(c: dict, st: dict, kept: dict, conv: tuple, anchor: date, mark) -> list[str]:
    problems = []
    if mark is None:
        return [f"{c['path']} {c['day']}: no tracked change in the marks"]
    if (c.get("kind"), c.get("note") or "") != (mark["kind"], mark["note"]):
        problems.append(f"{c['path']} {c['day']}: what changed is not the mark's")
    me, day = _page(c["path"]), date.fromisoformat(c["day"])
    per_conv, conv_first, conv_file = conv
    rows = {}
    for r in c.get("days") or []:
        d = r["day"]
        state = st.get(d, "missing")
        if r["state"] != state:
            problems.append(f"{c['path']} {d}: state {r['state']}, history says {state}")
        got = kept.get(d) or {}
        want = {"visits": None, "one_page": None, "search": None, "ai": None, "reads": None}
        if state == "ok" and got.get("landings") is not None:
            listed = got["landings"].get("pages") or {}
            mine = [v for p, v in listed.items() if p != REST and _page(p) == me]
            want.update(visits=sum(int(v[0]) for v in mine), one_page=sum(int(v[1]) for v in mine),
                        search=sum(int(v[3]) for v in mine), ai=sum(int(v[4]) for v in mine))
            if bool(not mine and int(got["landings"].get("folded") or 0)) != bool(r.get("at_least")):
                problems.append(f"{c['path']} {d}: the floor mark does not match the stored landings")
        if state == "ok" and got.get("ai_fetches") is not None:
            want["reads"] = sum(int(x[3]) for x in got["ai_fetches"].get("rows") or [] if _page(x[2]) == me)
        for f, v in want.items():
            if r.get(f) != v:
                problems.append(f"{c['path']} {d}: {f} shown {r.get(f)!r}, history gives {v!r}")
        # Leads: a figure must be this road's count; no figure must be one conversions could not give.
        if r.get("leads") is not None:
            n = (per_conv.get(d) or {}).get(me, 0)
            if r["leads"] != n:
                problems.append(f"{c['path']} {d}: leads shown {r['leads']}, conversions give {n}")
            want["leads"] = r["leads"]
        else:
            why = r.get("leads_state")
            ok = (why == "withheld"
                  or (why == "before" and (conv_first is None or d < conv_first))
                  or (why == "not_kept" and d <= (anchor - timedelta(days=CONV_DAYS)).isoformat())
                  or (why == "off" and not conv_file))
            if not ok:
                problems.append(f"{c['path']} {d}: leads not shown ({why}), yet conversions record the day")
            want["leads"] = None
        rows[d] = want
    n = min(MAX_DAYS, (anchor - day).days) if anchor > day else 0
    need = [(day + timedelta(days=i)).isoformat() for i in range(-n, n + 1)]
    if sorted(rows) != need:
        return problems + [f"{c['path']} {c['day']}: the days shown are not the {n} before and after"]
    exp = _expect(day, anchor, rows)
    if c.get("days_after") != exp["n"]:
        problems.append(f"{c['path']} {c['day']}: {c.get('days_after')} days after shown, {exp['n']} counted")
    shown = {f["key"]: f for f in c.get("figures") or []}
    for m, want in exp["figures"].items():
        got = shown.get(m)
        if got is None:
            problems.append(f"{c['path']} {c['day']}: {m} missing")
            continue
        for name in ("before", "after"):
            for k, v in want[name].items():
                if not _near(got[name].get(k), v):
                    problems.append(f"{c['path']} {c['day']}: {m} {name} {k} shown "
                                    f"{got[name].get(k)!r}, recount {v!r}")
        if got.get("verdict") != want["verdict"]:
            problems.append(f"{c['path']} {c['day']}: {m} verdict {got.get('verdict')}, "
                            f"recount {want['verdict']}")
    return problems


def check(p, found: list[dict], conv_body) -> dict[str, list[str]]:
    """{change id: problems} for the changes page_changes.figures gave; {} when all match."""
    if not found:
        return {}
    from .conversions import store
    from .conversions_data import store_folder
    from .settings_store import accounts_file
    from .audit_page_trends import states
    site = p.key.split("::", 1)[0]
    marks = tracked(accounts_file(p.config) or (accounts_file(p.config, p.live_dir) if p.live_dir else None),
                    site) or {}
    days = sorted(r["day"] for c in found for r in c.get("days") or [])
    first, last = (date.fromisoformat(days[0]), date.fromisoformat(days[-1])) if days else (p.anchor, p.anchor)
    db = p.history.db
    st = states(db, p.key, first, last)
    kept = _blobs(db, p.key, first.isoformat(), last.isoformat())
    cpath = store.path_for(p.config, Path(store_folder(p)))
    per_conv, conv_first = leads(cpath, site, p.tz, first, last)
    conv_file = bool(cpath and Path(cpath).is_file() and conv_first)
    out = {}
    for c in found:
        got = check_one(c, st, kept, (per_conv, conv_first, conv_file), p.anchor,
                        marks.get((c["path"], c["day"])))
        if got:
            out[c["id"]] = got
    missing = set(marks) - {(c["path"], c["day"]) for c in found}
    if missing:
        for c in found:
            out.setdefault(c["id"], []).append(f"the marks hold {len(missing)} change(s) the file leaves out")
    return out
