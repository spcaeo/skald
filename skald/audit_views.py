"""The audit's road for page groups (views): a stored view day recounted
from the raw log and compared with history.

A view (Settings > Sites > Views, `dashboard.views`) is the site's counting
rules over the lines whose path it takes. audit.py recounts the whole site
only; this module recounts each view the same independent way: the audit's
own line reader, its own same-click rule, its own group order (audit.Judge,
judged over the whole day, as the main road classifies over the whole day),
its own visit rule and its own page rule, and here its own path test. Nothing
calls config.View.matches, the parser, the classifier or the tally. What it
shares is the view list itself (names and prefixes are data: a recount with a
different list would be counting something else) and the key a view is
stored under (store.view_key).

Compared, per view: requests for the site's hosts, requests by group, the
people's visits and readers, and, on a day stored with breakdowns, responses
by status class for each group. A view day that does not match is withheld
by the caller (views_fill.py), never shown.
"""
from __future__ import annotations

from collections import Counter
from datetime import date, timedelta

from .files import slug as slug_of
from .store import History, view_key

GROUPS = ("people", "answer_engines", "search_engines", "bots", "ours")


def _under(path: str, prefix: str) -> bool:
    """Written apart from config.View: an empty prefix takes every path;
    "/ca/" takes /ca/..., and the bare /ca too."""
    if prefix == "":
        return True
    if path[:len(prefix)] == prefix:
        return True
    return prefix[-1:] == "/" and path == prefix[:-1]


def rules(raw: list) -> list[tuple[str, str, str, tuple]]:
    """(slug, name, prefix, exclusions) from the `dashboard.views` items."""
    out = []
    for item in raw or []:
        name = str(item.get("name") or "")
        exclude = item.get("exclude_prefix") or ""
        if isinstance(exclude, str):
            exclude = exclude.split()
        out.append((slug_of(name.lower()), name, str(item.get("path_prefix") or ""),
                    tuple(str(x) for x in exclude)))
    return out


def takes(rule: tuple, path: str) -> bool:
    _, _, prefix, exclude = rule
    if not _under(path, prefix):
        return False
    for x in exclude:
        if _under(path, x):
            return False
    return True


def recount(config: dict, day: date, tz, raw_views: list, paths=None) -> dict:
    """{slug: figures} for each view: the day counted again from the log."""
    from . import audit
    from pathlib import Path
    start, end = audit.window(day, tz)
    files = [Path(p) for p in paths] if paths else audit.log_files(config)
    wanted = {str(h).lower() for h in ((config.get("site") or {}).get("hosts") or [])}
    gap = timedelta(minutes=int((config.get("report") or {}).get(
        "session_gap_minutes") or 30))
    lines = audit.same_click(audit.in_time_order(
        [l for l in audit._read(files) if start <= l.when < end]))
    audit._countries(config, lines)
    judge = audit.Judge(config, lines, gap, window=(start, end), tz=tz)
    chosen = rules(raw_views)
    got = {r[0]: {"requests": 0, "groups": Counter(), "statuses": {g: Counter() for g in GROUPS},
                  "people": {}} for r in chosen}
    for line in lines:
        if wanted and line.host and line.host.lower() not in wanted:
            continue
        mine = [r[0] for r in chosen if takes(r, line.path)]
        if not mine:
            # Judged all the same: the judge's view of the day is the whole day's.
            judge(line)
            continue
        group, cited = judge(line)
        for s in mine:
            f = got[s]
            f["requests"] += 1
            f["groups"][group] += 1
            f["statuses"][group][audit.status_of(line.status)] += 1
            if group == "people":
                f["people"].setdefault((line.address, line.agent), []).append((line, cited))
    out = {}
    for s, f in got.items():
        visits = readers = 0
        for seen in f.pop("people").values():
            seen.sort(key=lambda item: item[0].when)
            for visit in _visits(seen, gap, wanted):
                visits += 1
                readers += any(audit.is_page(item[0]) for item in visit)
        out[s] = {**f, "visits": visits, "readers": readers}
    return out


def _visits(seen: list, gap: timedelta, wanted: set) -> list[list]:
    """SOP.md "What a visit is", by the audit's own rule (audit._elsewhere)."""
    from . import audit
    found, visit, came = [], [], None
    for item in seen:
        here = audit._came_from(item, wanted) if audit.is_page(item[0]) else None
        if visit and (item[0].when - visit[-1][0].when > gap or audit._elsewhere(here, came)):
            found.append(visit)
            visit, came = [], None
        visit.append(item)
        came = came or here
    if visit:
        found.append(visit)
    return found


def compare(figures: dict, history: History, site: str, day: date) -> dict[str, list[str]]:
    """{slug: mismatches} against each view's stored day; a view not stored
    that day is one mismatch ("not stored")."""
    db = history.db
    out: dict[str, list[str]] = {}
    for s, f in figures.items():
        key = (view_key(site, s), day.isoformat())
        problems: list[str] = []
        out[s] = problems
        row = db.execute("SELECT hits, breakdowns FROM days WHERE site = ? AND day = ?",
                         key).fetchone()
        if row is None:
            problems.append(f"{day}: not stored for this group")
            continue

        def same(what, stored, counted):
            if stored != counted:
                problems.append(f"{what}: history has {stored:,}, the recount finds {counted:,}")

        same("requests", row[0], f["requests"])
        stored = {g: (h, v, r) for g, h, v, r in db.execute(
            "SELECT grp, hits, visits, readers FROM groups WHERE site = ? AND day = ?", key)}
        for g in GROUPS:
            same(f"{g}: requests", stored.get(g, (0, 0, 0))[0], f["groups"].get(g, 0))
        p = stored.get("people", (0, 0, 0))
        same("people: visits", p[1] or 0, f["visits"])
        if p[2] is not None:
            same("people: readers", p[2], f["readers"])
        if not row[1]:
            continue
        counts: dict[str, Counter] = {}
        for kind, name, n in db.execute(
                "SELECT kind, name, n FROM counts WHERE site = ? AND day = ? AND kind LIKE "
                "'status\\_%' ESCAPE '\\'", key):
            counts.setdefault(kind, Counter())[name] = n
        for g in GROUPS:
            mine, theirs = counts.get(f"status_{g}", Counter()), f["statuses"][g]
            for status in sorted(set(mine) | set(theirs)):
                same(f"{g}: {status} responses", mine.get(status, 0), theirs.get(status, 0))
    return out


def figures_compared(figures: dict) -> int:
    """How many figures compare() looks at for one view (for the job's line)."""
    return 1 + len(GROUPS) + 2 + sum(len(c) for c in figures["statuses"].values())
