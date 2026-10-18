"""The second count of the citation and crawler alerts (alerts_history.py).

Registered in audit_more.DAILY: run-daily's recounts step reads the alert
check's last evaluation (`history` in alerts-state.json beside the live
files) and works every alert's figures out again from stored history, with
its own code and its own reading of the tables. It shares no code with
alerts_history.py, not even a name list:

  a day it may use   a `days` row that is verified and has no partial_from
                     or partial_until (and breakdowns = 1 where the figure is
                     a breakdown)
  a first citation   read from each stored day's `page_firsts` blob (keys
                     "from_ai|<assistant>": [utc time, assistant]), not from
                     the page_milestones table the rule reads; and from the
                     `counts` rows cited_by / cited_page of earlier days
  a page             its path cut at "?" or "#", any trailing "/" taken off
  visits from AI     the `counts` row reader_source "AI assistant" (no row on
                     a counted day is 0 visits)
  a median           the middle value of the sorted list (the mean of the
                     two middle ones for an even count)
  crawler requests   each stored day's `crawler_paths` blob, the crawler's
                     `requests`

A problem is a figure the alert states that history does not give. It never
changes the alert: the run's outcome says the recount does not match.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

STATE_FILE = "alerts-state.json"
SOURCE = "AI assistant"


def set_up(ctx) -> bool:
    on = ((getattr(ctx, "config", None) or {}).get("alerts") or {}).get("enabled", False)
    return on is True or str(on).strip().lower() in ("1", "true", "yes", "on")


def daily(ctx, day) -> list[str] | None:
    """The problems with the kept alerts (empty: they match), None when the
    alert check has kept nothing yet."""
    try:
        state = json.loads((Path(ctx.live_dir) / STATE_FILE).read_text())
    except (OSError, ValueError):
        return None
    kept = (state or {}).get("history") if isinstance(state, dict) else None
    if not kept:
        return None
    with ctx.history() as history:
        return recheck(history.db, ctx.site, kept)


# --------------------------------------------------------------- reading

def _ok(db, site: str, d: str, breakdowns: bool = False) -> bool:
    row = db.execute("SELECT verified, partial_from, partial_until, breakdowns FROM days "
                     "WHERE site = ? AND day = ?", (site, d)).fetchone()
    if row is None or not row[0] or row[1] or row[2]:
        return False
    return not breakdowns or row[3] == 1


def _bare(path: str) -> str:
    cut = str(path or "")
    for mark in ("?", "#"):
        cut = cut.split(mark, 1)[0]
    return cut.rstrip("/") or "/"


def _blob(db, site: str, d: str, kind: str):
    row = db.execute("SELECT data FROM day_extras WHERE site = ? AND day = ? AND kind = ?",
                     (site, d, kind)).fetchone()
    return None if row is None else json.loads(row[0])


def _firsts_before(db, site: str, d: str):
    for day, data in db.execute("SELECT day, data FROM day_extras WHERE site = ? AND "
                                "kind = 'page_firsts' AND day < ?", (site, d)):
        yield day, json.loads(data)


def _count(db, site: str, kind: str, d: str, names) -> int | None:
    rows = [int(r[0]) for r in db.execute(
        f"SELECT n FROM counts WHERE site = ? AND kind = ? AND day = ? AND name IN "
        f"({','.join('?' * len(names))})", (site, kind, d, *names))]
    return sum(rows) if rows else None


def _earlier(db, site: str, kind: str, d: str) -> set:
    return {name for (name,) in db.execute(
        "SELECT DISTINCT name FROM counts WHERE site = ? AND kind = ? AND day < ? AND n > 0",
        (site, kind, d))}


def _cited_firsts(blob: dict | None) -> list[tuple]:
    """[(utc time, bare page, path, assistant)] of a page_firsts blob."""
    out = []
    for path, keys in (blob or {}).items():
        for key, got in (keys or {}).items():
            if key.startswith("from_ai|"):
                out.append((got[0], _bare(path), path, key[len("from_ai|"):]))
    return out


# --------------------------------------------------------------- checks

def _first_citation(db, site: str, data: dict, problems: list) -> None:
    d, who = data["day"], data["assistant"]
    if not _ok(db, site, d):
        problems.append(f"first citation from {who}: {d} is not a whole counted day")
        return
    mine = sorted(x for x in _cited_firsts(_blob(db, site, d, "page_firsts")) if x[3] == who)
    if not mine or mine[0][0] != data["at"] or not any(
            x[0] == data["at"] and x[1] == _bare(data["path"]) for x in mine):
        problems.append(f"first citation from {who}: the alert says {data['at']} on "
                        f"{data['path']}, the day's page first-times say "
                        f"{(mine[0][0] + ' on ' + mine[0][2]) if mine else 'none'}")
    for day, blob in _firsts_before(db, site, d):
        if any(x[3] == who for x in _cited_firsts(blob)):
            problems.append(f"first citation from {who}: {day} already had one")
            break
    if who in _earlier(db, site, "cited_by", d):
        problems.append(f"first citation from {who}: an earlier day counted visits from it")
    n = _count(db, site, "cited_by", d, [who])
    if n != data.get("visits"):
        problems.append(f"first citation from {who}: {data.get('visits')} visits in the "
                        f"alert, {n} stored")


def _first_pages(db, site: str, alert: dict, problems: list) -> None:
    data = alert["data"]
    d = data["day"]
    if not _ok(db, site, d):
        problems.append(f"first cited pages: {d} is not a whole counted day")
        return
    today = _cited_firsts(_blob(db, site, d, "page_firsts"))
    before = set()
    for _, blob in _firsts_before(db, site, d):
        before |= {x[1] for x in _cited_firsts(blob)}
    before |= {_bare(p) for p in _earlier(db, site, "cited_page", d)}
    for page in data.get("pages") or []:
        bare = _bare(page["path"])
        times = sorted(x[0] for x in today if x[1] == bare)
        if not times or times[0] != page["at"]:
            problems.append(f"first cited page {page['path']}: the alert says {page['at']}, "
                            f"the day's page first-times say {times[0] if times else 'none'}")
        if bare in before:
            problems.append(f"first cited page {page['path']}: an earlier day had one")
        names = [p for (p,) in db.execute(
            "SELECT DISTINCT name FROM counts WHERE site = ? AND kind = 'cited_page' AND day = ?",
            (site, d)) if _bare(p) == bare]
        n = _count(db, site, "cited_page", d, names) if names else None
        if n != page.get("visits"):
            problems.append(f"first cited page {page['path']}: {page.get('visits')} visits in "
                            f"the alert, {n} stored")
    if alert.get("subject") == "pages":
        oldest = db.execute("SELECT MIN(day) FROM day_extras WHERE site = ? AND "
                            "kind = 'page_firsts'", (site,)).fetchone()[0]
        start = db.execute("SELECT MIN(day) FROM days WHERE site = ?", (site,)).fetchone()[0]
        if oldest and start and oldest <= start:   # the blobs cover all history: count them
            n = len({x[1] for x in today} - before)
            if n != alert.get("figure"):
                problems.append(f"first cited pages: {alert.get('figure')} in the alert, "
                                f"{n} recounted")


def _median(values: list) -> float:
    got = sorted(values)
    mid = len(got) // 2
    return got[mid] if len(got) % 2 else (got[mid - 1] + got[mid]) / 2


def _cited(db, site: str, alert: dict, problems: list) -> None:
    data = alert["data"]

    def visits(d: str) -> int:
        return _count(db, site, "reader_source", d, [SOURCE]) or 0
    days = [data["day"]] + [w["day"] for w in data.get("weeks") or []]
    for d in days:
        if not _ok(db, site, d, breakdowns=True):
            problems.append(f"visits from AI answers: {d} is not a whole counted day")
            return
    for d in data.get("skipped") or []:
        if _ok(db, site, d, breakdowns=True):
            problems.append(f"visits from AI answers: {d} was left out but is counted")
    n = visits(data["day"])
    if n != data["visits"] or n != alert.get("figure"):
        problems.append(f"visits from AI answers on {data['day']}: {data['visits']} in the "
                        f"alert, {n} stored")
    weeks = []
    for w in data.get("weeks") or []:
        got = visits(w["day"])
        weeks.append(got)
        if got != w["visits"]:
            problems.append(f"visits from AI answers on {w['day']}: {w['visits']} in the "
                            f"alert, {got} stored")
    if not weeks:
        problems.append("visits from AI answers: no weeks to compare with")
        return
    median = _median(weeks)
    if median != data["median"]:
        problems.append(f"visits from AI answers: median {data['median']} in the alert, "
                        f"{median} recounted")
    rose = n >= data["minimum"] and n >= data["spike_factor"] * median
    fell = median >= data["minimum"] and n * 100 <= median * data["drop_percent"]
    if (data["kind"] == "cited_rose" and not rose) or (data["kind"] == "cited_fell" and not fell):
        problems.append(f"visits from AI answers: {n} against {median} does not meet the "
                        f"alert's own rule ({data['kind']})")


def _silent(db, site: str, data: dict, problems: list) -> None:
    name = data["crawler"]

    def span(first: str, last: str) -> list[str]:
        a, b = date.fromisoformat(first), date.fromisoformat(last)
        return [(a + timedelta(days=i)).isoformat() for i in range((b - a).days + 1)]
    active = requests = 0
    last = None
    for d in span(*data["window"]) + span(*data["quiet"]):
        blob = _blob(db, site, d, "crawler_paths")
        if not _ok(db, site, d) or blob is None:
            problems.append(f"{name} silent: {d} is not a whole counted day")
            return
        n = int((blob.get(name) or {}).get("requests") or 0)
        if d >= data["quiet"][0]:
            if n:
                problems.append(f"{name} silent: {n} requests stored on {d}")
        elif n:
            active, requests, last = active + 1, requests + n, d
    if (active, requests, last) != (data["active_days"], data["requests"], data["last_seen"]):
        problems.append(f"{name} silent: the alert says {data['requests']} requests on "
                        f"{data['active_days']} days, the last {data['last_seen']}; stored: "
                        f"{requests} on {active}, the last {last}")


CHECKS = {"first_citation": lambda db, s, a, p: _first_citation(db, s, a["data"], p),
          "first_cited_page": _first_pages,
          "cited_rose": _cited, "cited_fell": _cited,
          "silent": lambda db, s, a, p: _silent(db, s, a["data"], p)}


def recheck(db, site: str, kept: dict) -> list[str]:
    """Each kept alert's figures against stored history. The problems."""
    problems: list[str] = []
    for alert in kept.get("found") or []:
        kind = (alert.get("data") or {}).get("kind")
        check = CHECKS.get(kind)
        if check is None:
            problems.append(f"{alert.get('cause')}: no recount for an alert of kind {kind}")
            continue
        try:
            check(db, site, alert, problems)
        except (KeyError, TypeError, ValueError) as why:
            problems.append(f"{alert.get('cause')}: the alert's figures cannot be read "
                            f"({type(why).__name__})")
    return problems
