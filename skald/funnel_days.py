"""Funnel history: each saved funnel counted over each day's journeys when
the day is collected (day_extras kind `funnels`, registered in day_more.py).

Journeys are kept 7 days (privacy), so a funnel's history starts on the day
it is saved: a day is counted for a funnel only when the funnel was saved
on or before it (its `saved_at`, in the report's time zone). Earlier days
are "not recorded", never zero.

Only the visit steps are counted here - the first step ("any" or a page)
and every later page step. Lead and event steps come from other systems
and have their own history. A series is keyed by a hash of those counted
steps and the funnel's source (`series_key`): changing a page or the source
starts a new series; renaming, relabelling or changing a lead step does not.

Per series, per day:

  visits     the day's visits from the funnel's source (all visits if none)
  reached    visits that reached each counted step, in order (funnels.py's
             rule: a step is met by the first trail entry at or after the
             one that met the step before; "any" uses no entry)
  by_source  {source type: [reached per step]}
  by_device  {device: [reached per step]}
  next       per step, where the visits that got no further went next: the
             first later trail entry with another path, or LEFT; the top 10
             and "(all others)". For the last step: every visit that reached
             it. Each sums to reached[k] - reached[k + 1] (the last: reached).
  complete   visits that reached the last step, by the time from the first
             step (its trail entry's `at`, or the visit's start for "any") to
             the entry that met the last step, in TIMES; null with one step

Every sum is held by `check`; the second count is audit_funnels.py.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path

from .funnels import from_source, matches

LEFT = "(left the site)"
OTHER = "(all others)"
TOP_NEXT = 10
# Time to complete: (label, upper bound in seconds, exclusive); None = no bound.
TIMES = (("under 10s", 10), ("10-30s", 30), ("30s-1m", 60), ("1-3m", 180),
         ("3-10m", 600), ("10-30m", 1800), ("30m or more", None))


def time_bucket(seconds: int) -> str:
    for label, below in TIMES:
        if below is None or seconds < below:
            return label
    return TIMES[-1][0]


# ------------------------------------------------------------ the series

def counted_steps(steps: list[dict]) -> list[dict]:
    """The visit steps of a funnel, with their labels."""
    out = []
    for s in steps or []:
        if s.get("kind") == "any":
            out.append({"label": s.get("label") or "Any visit", "kind": "any"})
        elif s.get("kind", "path") == "path":
            out.append({"label": s.get("label") or "Step", "kind": "path",
                        "match": s.get("match") or "equals", "paths": list(s.get("paths") or [])})
    return out


def series_key(funnel: dict) -> str:
    """sha256 of the counted steps without labels, and the source, as
    compact sorted JSON; the first 16 hex digits."""
    steps = [{k: v for k, v in s.items() if k != "label"}
             for s in counted_steps(funnel.get("steps"))]
    text = json.dumps({"source": funnel.get("source") or None, "steps": steps},
                      sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def series(funnel: dict) -> dict:
    """What collect counts for one saved funnel."""
    return {"key": series_key(funnel), "name": str(funnel.get("name") or ""),
            "source": funnel.get("source") or None,
            "steps": counted_steps(funnel.get("steps"))}


def saved_day(funnel: dict, tz) -> date | None:
    """The local day a funnel was saved, or None when unknown."""
    try:
        when = datetime.fromisoformat(str(funnel.get("saved_at") or ""))
    except ValueError:
        return None
    when = when if when.tzinfo else when.replace(tzinfo=timezone.utc)
    return when.astimezone(tz).date() if tz is not None else when.date()


def wanted(config: dict, day: date | None, tz) -> list[dict] | None:
    """The series to count on `day`: the funnels in funnels.json (beside the
    live snapshot) saved on or before it. None when there is no folder."""
    folder = ((config or {}).get("_resolved") or {}).get("live_dir")
    if not folder or day is None:
        return None
    from .funnels import saved
    out = []
    for f in saved(Path(folder)):
        since = saved_day(f, tz)
        if since is not None and since <= day and counted_steps(f.get("steps")):
            out.append(series(f))
    return out


# -------------------------------------------------------------- counting

def positions(j: dict, steps: list[dict]) -> list[int]:
    """The trail index that met each step reached, in order (-1 for "any")."""
    pages = [t[0] for t in j.get("trail") or [] if isinstance(t, (list, tuple)) and t]
    out, start = [], 0
    for step in steps:
        if step["kind"] == "any":
            out.append(-1)
            continue
        hit = next((i for i in range(start, len(pages)) if matches(step, pages[i])), None)
        if hit is None:
            break
        out.append(hit)
        start = hit
    return out


def _next_page(j: dict, at: int) -> str:
    pages = [t[0] for t in j.get("trail") or [] if isinstance(t, (list, tuple)) and t]
    if at < 0:
        return pages[0] if pages else LEFT
    here = pages[at]
    return next((p for p in pages[at + 1:] if p != here), LEFT)


def _fold(c: Counter) -> dict:
    kept = c.most_common(TOP_NEXT)
    out = dict(kept)
    rest = sum(c.values()) - sum(n for _, n in kept)
    if rest:
        out[OTHER] = rest
    return out


def count(s: dict, journeys: list[dict]) -> dict:
    """One series over a day's journeys."""
    steps = s["steps"]
    k = len(steps)
    mine = [j for j in journeys if from_source(j, s.get("source"))]
    reached = [0] * k
    by_source: dict[str, list[int]] = {}
    by_device: dict[str, list[int]] = {}
    nxt = [Counter() for _ in range(k)]
    complete: Counter = Counter()
    for j in mine:
        got = positions(j, steps)
        depth = len(got)
        if not depth:
            continue
        src = by_source.setdefault(str(j.get("source") or ""), [0] * k)
        dev = by_device.setdefault(str(j.get("device") or ""), [0] * k)
        for i in range(depth):
            reached[i] += 1
            src[i] += 1
            dev[i] += 1
        nxt[depth - 1][_next_page(j, got[-1])] += 1
        if depth == k and k > 1:
            at = j.get("at") or []
            begin = 0 if got[0] < 0 else at[got[0]]
            complete[time_bucket(max(0, at[got[-1]] - begin))] += 1
    return {"name": s["name"], "source": s.get("source"), "steps": steps,
            "visits": len(mine), "reached": reached, "by_source": by_source,
            "by_device": by_device, "next": [_fold(c) for c in nxt],
            "complete": dict(complete) if k > 1 else None}


def finish(extras, totals, journeys, page_visits, readers_by_hour) -> dict | None:
    """day_more's hook: {key: series figures}, or None when no funnel is
    saved for the day (or collect did not say which)."""
    wanted_now = getattr(extras, "funnels", None)
    if not wanted_now or journeys is None:
        return None
    return {s["key"]: count(s, journeys) for s in wanted_now}


def check(totals, blob: dict, differs, problems: list) -> None:
    """Every sum the contract promises for the day's funnel figures."""
    from .verify import Problem
    journeys = getattr(totals, "journeys", None)
    stats = getattr(totals, "visits", None)
    total = len(journeys) if journeys is not None else (stats.visits if stats else None)
    for key, f in blob.items():
        name = f"funnel {f.get('name', key)}"
        reached, steps = f.get("reached") or [], f.get("steps") or []
        k = len(steps)
        if len(reached) != k or len(f.get("next") or []) != k:
            problems.append(Problem(f"{name}: steps", "the counts are not one per step"))
            continue
        if series_key(f) != key:
            problems.append(Problem(f"{name}: key", "its steps do not match its key"))
        if total is not None:
            if f.get("source"):
                if f["visits"] > total:
                    problems.append(Problem(f"{name}: visits", "more than the day's visits"))
            else:
                differs(f"{name}: visits", f["visits"], total, "visits")
        if k and steps[0]["kind"] == "any":
            differs(f"{name}: step 1", reached[0], f["visits"], "visits from its source")
        if any(a < b for a, b in zip([f["visits"]] + reached, reached)):
            problems.append(Problem(f"{name}: steps", "a step has more visits than the one before"))
        for i in range(k):
            for split in ("by_source", "by_device"):
                differs(f"{name}: step {i + 1} {split.replace('_', ' ')}",
                        sum(v[i] for v in (f.get(split) or {}).values()), reached[i], "visits")
            left = reached[i] - (reached[i + 1] if i + 1 < k else 0)
            differs(f"{name}: next pages after step {i + 1}", sum(f["next"][i].values()),
                    left, "visits that went no further")
        if f.get("complete") is not None:
            differs(f"{name}: time to complete", sum(f["complete"].values()),
                    reached[-1] if reached else 0, "visits that reached the last step")


# -------------------------------------------------------- funnels.json

FIGURES = ("visits", "reached", "by_source", "by_device", "next", "complete")


def _figures(blob: dict | None) -> dict:
    return {k: (blob.get(k) if blob is not None else None) for k in FIGURES}


def history(p, funnel: dict) -> dict | None:
    """funnels.json's `history` of a saved funnel on a page (data_files.Page):
    its series' days from the day it was saved (or the first day stored
    under its key, if earlier) to yesterday, and today from the snapshot.
    Only an `ok` day carries figures; a figure not recorded is null."""
    if funnel.get("saved_by") == "default":
        return None
    key = series_key(funnel)
    since = saved_day(funnel, p.tz)
    held = sorted(d for d, ex in (p.extras or {}).items()
                  if key in ((ex or {}).get("funnels") or {}))
    starts = [d for d in ([since.isoformat()] if since else []) + held[:1]]
    start = min(starts) if starts else None
    days = []
    for e in p.daily if start else []:
        d = e["day"].isoformat()
        if d < start:
            continue
        row = p.day_entry(e)
        if e["state"] == "ok":
            row.update(_figures(((p.extras.get(d) or {}).get("funnels") or {}).get(key)))
        days.append(row)
    today = None
    if p.live_ok and start and p.today.isoformat() >= start:
        blob = (((p.snap or {}).get("extras") or {}).get("funnels") or {}).get(key)
        today = {"day": p.today.isoformat(), **_figures(blob)}
    return {"key": key, "since": start,
            "steps": [s["label"] for s in counted_steps(funnel.get("steps"))],
            "days": days, "today": today}
