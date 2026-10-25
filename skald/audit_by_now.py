"""The second count of "yesterday at this hour" (by_now.py), for `skald audit --live`.

The live snapshot's `by_now` holds yesterday from midnight to the same time
of day as today's `until`, and both days by local hour. This module counts
the same again from the raw lines, by the audit's road (audit.py): its own
line reader, its own judge (the groups, the rendering rule, the cited rule),
its own page rule and its own visits. Only classify.py's name lists are
shared, through the audit.

  visitors      the audit's visits (one address and user agent, split on the
                gap or on a page from somewhere else) that hold a page, by the
                local hour of that first page
  pages         people's page lines, by local hour
  ai_visitors   people's lines the judge calls cited, per address and user
                agent, a new one after the gap: by the local hour of each
                one's first cited line

Compared: yesterday's three figures, its three series hour by hour, and
today's three series hour by hour (today's figures themselves are the main
audit's). A `by_now` that is not "ok" carries no figures: nothing to compare.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

from . import audit

KEYS = ("visitors", "pages", "ai_visitors")
HOURS = [f"{h:02d}" for h in range(24)]


def recount(config: dict, tz, start: datetime, end: datetime, paths=None,
            upto: dict | None = None) -> dict:
    """{"visitors", "pages", "ai_visitors", "hours": {key: [24]}} for [start, end)."""
    files = [Path(p) for p in paths] if paths else audit.log_files(config)
    wanted = {str(h).lower() for h in ((config.get("site") or {}).get("hosts") or [])}
    gap = timedelta(minutes=int((config.get("report") or {}).get("session_gap_minutes") or 30))
    lines = audit.same_click(audit.in_time_order(
        [l for l in audit._read(files, upto, config) if start <= l.when < end]))
    audit._countries(config, lines)
    judge = audit.Judge(config, lines, gap, window=(start, end), tz=tz)
    hour = lambda line: f"{line.when.astimezone(tz).hour:02d}"   # noqa: E731
    pages, ai, readers = Counter(), Counter(), Counter()
    people: dict[tuple, list] = {}
    cited_last: dict[tuple, datetime] = {}
    for line in lines:
        if wanted and line.host and line.host.lower() not in wanted:
            continue
        group, cited = judge(line)
        if group != "people":
            continue
        key = (line.address, line.agent)
        people.setdefault(key, []).append((line, cited))
        if audit.is_page(line):
            pages[hour(line)] += 1
        if cited:
            last = cited_last.get(key)
            if last is None or line.when - last > gap:
                ai[hour(line)] += 1
            cited_last[key] = line.when

    def close(visit: list) -> None:
        first = next((item[0] for item in visit if audit.is_page(item[0])), None)
        if first is not None:
            readers[hour(first)] += 1

    for seen in people.values():
        seen.sort(key=lambda item: item[0].when)
        visit, came = [], None
        for item in seen:
            here = audit._came_from(item, wanted) if audit.is_page(item[0]) else None
            if visit and (item[0].when - visit[-1][0].when > gap or audit._elsewhere(here, came)):
                close(visit)
                visit, came = [], None
            visit.append(item)
            came = came or here
        if visit:
            close(visit)
    hours = {"visitors": [readers.get(h, 0) for h in HOURS], "pages": [pages.get(h, 0) for h in HOURS],
             "ai_visitors": [ai.get(h, 0) for h in HOURS]}
    return {**{k: sum(hours[k]) for k in KEYS}, "hours": hours}


def compare(stored: dict, counted: dict, same, what: str, figures: bool = True) -> None:
    """`same(what, stored, counted)` for the figures (when `figures`) and each hour."""
    if figures:
        for k in KEYS:
            same(f"{what}: {k}", stored.get(k), counted[k])
    hours = stored.get("hours") if figures else stored
    if hours is None:
        return
    for k in KEYS:
        mine = hours.get(k) or []
        for i, h in enumerate(HOURS):
            got = mine[i] if i < len(mine) else None
            if got or counted["hours"][k][i]:
                same(f"{what}: {k} at {h}:00", got, counted["hours"][k][i])


def check(config: dict, tz, snap: dict, paths=None) -> tuple[list[str], int]:
    """(problems, figures compared) for the snapshot's `by_now`."""
    part = snap.get("by_now")
    if not part or snap.get("state") != "ok":
        return [], 0
    problems: list[str] = []
    compared = 0
    upto = snap.get("read_upto")

    def same(what: str, stored, counted) -> None:
        nonlocal compared
        compared += 1
        if stored != counted:
            problems.append(f"yesterday at this hour, {what}: the snapshot has {stored}, "
                            f"the recount finds {counted}")

    if part.get("state") == "ok":
        got = recount(config, tz, datetime.fromisoformat(part["from"]),
                      datetime.fromisoformat(part["until"]), paths, upto)
        compare(part, got, same, f"{part['day']} to {part['until'][11:16]}")
    if part.get("today_hours") is not None:
        got = recount(config, tz, datetime.fromisoformat(snap["from"]),
                      datetime.fromisoformat(snap["until"]), paths, upto)
        compare(part["today_hours"], got, same, "today by hour", figures=False)
    return problems, compared
