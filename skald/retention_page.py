"""retention.json (Traffic > Retention) and the visitors behind one cell.

`build(page)` reads the stored cohorts (retention.py, day kinds
retention_week and retention_day) of the latest 12 weeks and 30 days and
says, for every cell, what it is:

    ok        counted: `cells[k]` = [came back, came back and read 2+ pages]
              (the second null on the 30-day code: pages are not kept)
    pending   its period is not over yet
    held      its period, or the cohort's, has a day that is not verified
              (withheld, partial or not collected): not shown
    nr        not recorded: never counted - beyond the days the identity can
              follow (`reach`), or its inputs were pruned before it was
    withheld  the whole cohort, when its recount (audit_retention.py) did not
              match

and, per cohort, `checkable`: false once its inputs are pruned (kept as last
counted, "inputs expired"). Totals and labels only: no address, no code.

`visitors(...)` (people/cohort, admins and owners, written to the audit log)
lists the visits behind one cell, on the address road only: each member's
first visit in the cell's period, with its day and place in the day, so the
visitor drawer opens on it. Recounted from the kept visits now; when that
differs from the stored figure (an address forgotten since), both are said.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from . import retention as rt

LIMIT = 500


def _folder(page) -> Path | None:
    path = getattr(page.history, "path", None)
    return Path(path).parent if path is not None and str(path) != ":memory:" else None


def checkable(blob: dict, begun: date | None, today: date) -> bool:
    start = date.fromisoformat(blob["start"])
    if begun is None or start < begun:
        return False
    kept_from = today - timedelta(days=int(blob["horizon"]))
    return begun > kept_from or start - timedelta(days=int(blob["lookback"])) >= kept_from


def _days_ok(states: dict, first: date, last: date) -> bool:
    d = first
    while d <= last:
        e = states.get(d.isoformat())
        if e is None or e.get("state") != "ok":
            return False
        d += timedelta(days=1)
    return True


def cohort(blob: dict, grain: str, anchor: date, today: date, states: dict,
           begun: date | None) -> dict:
    start = date.fromisoformat(blob["start"])
    first, last = rt.period(grain, start)
    out = {k: blob.get(k) for k in ("start", "end", "size", "removed", "since", "by",
                                    "horizon", "lookback", "computed", "cells", "split",
                                    "audit")}
    out["checkable"] = checkable(blob, begun, today)
    audit = blob.get("audit") or {}
    if audit and not audit.get("ok"):
        out.update(state="withheld", cells={}, split={}, size=None)
        return out
    if not _days_ok(states, first, last):
        out.update(state="held", cells={}, split={}, size=None)
        return out
    out["state"] = "ok"
    reach = rt.reach(int(blob["horizon"]))
    status = {}
    for k in range(1, rt.OFFSETS[grain] + 1):
        a, b = rt.period(grain, start, k)
        if b > anchor:
            status[str(k)] = "pending"
        elif not _days_ok(states, a, b):
            status[str(k)] = "held"
        elif str(k) in (blob.get("cells") or {}):
            status[str(k)] = "ok"
        else:
            status[str(k)] = "nr" if (b - start).days > reach else "nr-pruned"
    out["status"] = status
    return out


def build(page) -> dict:
    """The body of retention.json (DATA-CONTRACT.md)."""
    if page.view is not None:
        return {"identity": None, "why": "view",
                "words": "Retention is counted for the whole site only, not for a view."}
    folder = _folder(page)
    ident = rt.identity(page.config, folder)
    out = {"identity": ident, "deep": rt.DEEP, "anchor": page.anchor.isoformat(),
           "offsets": dict(rt.OFFSETS), "grains": {}}
    if ident is None:
        out["why"] = "none"
        out["words"] = ("Retention needs a way to know a visitor again: kept visits "
                        "(Settings > Privacy & retention > People, keep IP addresses) or the 30-day visitor code "
                        "(the visitor key). This site has neither.")
    begun = {}
    for grain, kind in rt.KINDS.items():
        cohorts = rt.starts(grain, page.anchor)
        stored = page.history.extras(page.key, cohorts[0], cohorts[-1], (kind,))
        rows = []
        for start in cohorts:
            blob = (stored.get(start.isoformat()) or {}).get(kind)
            if not blob:
                rows.append({"start": start.isoformat(),
                             "end": rt.period(grain, start)[1].isoformat(), "state": "nr"})
                continue
            by = blob.get("by")
            if by not in begun:
                begun[by] = rt.begun(page.config, folder, page.history.db, page.key, by)
            rows.append(cohort(blob, grain, page.anchor, page.today, page.states, begun[by]))
        out["grains"][grain] = {"cohorts": rows}
    # The first day the identity's store holds: a cohort before it has no visits to count.
    if ident is not None:
        if ident["by"] not in begun:
            begun[ident["by"]] = rt.begun(page.config, folder, page.history.db, page.key,
                                          ident["by"])
        first = begun[ident["by"]]
        out["begun"] = first.isoformat() if first else None
        out["kept_from"] = (page.today - timedelta(days=ident["horizon"])).isoformat()
    return out


# ------------------------------------------------------------------ the visitors

def visitors(config: dict, folder, history_db, site: str, grain: str, start: str, k: int,
             dim: str | None = None, value: str | None = None, deep: bool = False,
             today: date | None = None) -> dict:
    """The visits behind one cell (see the module). k = 0: the cohort itself."""
    today = today or date.today()
    ident = rt.identity(config, folder)
    out = {"ok": True, "found": False, "rows": [], "stored": None}
    if ident is None or ident["by"] != "address":
        out["why"] = ("Only kept visits (Settings > Privacy & retention > People, keep IP addresses) can list the "
                      "visitors behind a cell; the 30-day code names nobody.")
        return out
    if grain not in rt.KINDS or k < 0 or k > rt.OFFSETS[grain] or \
            (dim is not None and dim not in rt.SPLITS):
        return {"ok": False, "error": "grain is week or day; k 0 to the last offset; "
                                      "split one of " + ", ".join(rt.SPLITS)}
    first = date.fromisoformat(start)
    if grain == "week" and first.weekday() != 0:
        return {"ok": False, "error": "a week starts on a Monday"}
    row = history_db.execute("SELECT data FROM day_extras WHERE site = ? AND day = ? AND "
                             "kind = ?", (site, start, rt.KINDS[grain])).fetchone()
    blob = json.loads(row[0]) if row else None
    if blob:
        out["stored"] = _stored(blob, k, dim, value, deep)
    last_day = today - timedelta(days=1)
    a, b = rt.period(grain, first, k)
    if b > last_day:
        out["why"] = "This period is not over yet."
        return out
    lo = first
    inputs = rt.load(config, folder, history_db, site, ident,
                     lo - timedelta(days=ident["lookback"]), lo, last_day)
    ok, _ = rt.window(ident, inputs, first, today)
    if not ok:
        out["why"] = ("The visits behind this cell are no longer kept (inputs expired): the "
                      "figure stays as last counted.")
        return out
    found = []
    for key, v0 in rt.members(inputs, grain, first, ident["lookback"]):
        if dim is not None and rt.label(v0, dim) != value and value != rt.OTHER:
            continue
        if dim is not None and value == rt.OTHER and blob and \
                rt.label(v0, dim) in ((blob.get("split") or {}).get(dim) or {}):
            continue
        if k == 0:
            hit = v0
        else:
            back, rich = rt.came_back(inputs.visits[key], a, b)
            hit = rich if deep else back
        if hit is not None:
            found.append(_row(hit, v0))
    found.sort(key=lambda r: r["start"], reverse=True)
    out.update(found=bool(found), listed=len(found), rows=found[:LIMIT],
               period={"first": a.isoformat(), "last": b.isoformat()})
    if out["stored"] is not None and out["stored"] != len(found):
        out["differs"] = ("The stored figure was counted before; the kept visits now give "
                          f"{len(found)} (an address forgotten since, or a recount).")
    return out


def _stored(blob: dict, k: int, dim, value, deep: bool):
    part = blob if dim is None else ((blob.get("split") or {}).get(dim) or {}).get(value)
    if not part:
        return None
    if k == 0:
        return part.get("size")
    cell = (part.get("cells") or {}).get(str(k))
    return None if not cell else cell[1 if deep else 0]


def _row(v: dict, v0: dict) -> dict:
    out = {key: (val.isoformat() if isinstance(val, date) else val) for key, val in v.items()}
    try:
        out["trail"] = json.loads(out.get("trail") or "[]")
    except (TypeError, ValueError):
        out["trail"] = []
    out["cohort_first"] = {"day": v0["day"].isoformat(), "source": v0.get("source"),
                           "landing": v0.get("landing")}
    return out
