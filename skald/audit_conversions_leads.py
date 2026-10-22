"""The second count of the lead figures added in 2.5.0 (conversions_leads.py):
conversions.json's `today` listing and the lead findings in insights.json,
counted again by SQL GROUP BY over conversions.sqlite opened read-only.

conversions_leads.py counts in Python from plain SELECTs and from
conversions.json's checked days; this module counts straight from the rows,
by its own SQL: local days as UTC bounds, the lead actions and finished
stages as SQL IN lists, test rows left out by `test = 0` (the listing
counts them apart). It shares only the name lists in conversions/__init__.py
(LEAD_ACTIONS, FINISHED, UNKNOWN) and the file's location.

    check_today      problems with the `today` block: its total, its test
                     count, and (when every row is listed) its rows by
                     action, stage and test mark, each against the SQL;
                     and its `by_now` (check_by_now): yesterday's leads to
                     the same time of day and both days by hour, one SQL
                     COUNT per local hour; and its `same_time`
                     (check_same_time, 2.27): the day before each of
                     Leads' periods (7, 30, 90 days), to the same hour
    check_insights   {index: problems} for the lead findings whose numbers
                     the SQL does not give: `after` and `before` over their
                     periods, by the subject's column; for a "most leads"
                     finding, the SQL's own leader, its count and the total

A listing the recount disagrees with is withheld; a finding is left out and
named in insights.json's `leads_withheld`.
"""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from .audit_conversions_figures import STAMP, _open, _utc, once
from .conversions import FINISHED, LEAD_ACTIONS, UNKNOWN

# The subject's column, by this module's own reading of the finding.
COLUMN = {"site": None, "source": "source_type", "page": "landing", "country": "country"}
SKIP = {UNKNOWN, "(none)", "(this site)", "(all others)", "(no campaign tag)"}


def _in(names) -> str:
    return "(" + ", ".join(f"'{n}'" for n in names) + ")"


LEADS = (f"FROM conversions c WHERE c.site = ? AND c.test = 0 AND c.action IN "
         f"{_in(LEAD_ACTIONS)} AND c.stage IN {_in(FINISHED)} AND c.at >= ? AND c.at < ? "
         f"AND {once('c')}")


def _bounds(tz, first: str, last: str) -> tuple[str, str]:
    a, b = date.fromisoformat(first), date.fromisoformat(last)
    return _utc(a, tz), _utc(b + timedelta(days=1), tz)


def range_counts(db, site: str, tz, first: str, last: str, column: str | None) -> Counter:
    """Leads over first..last (local days), by `column` ("leads" alone when None)."""
    lo, hi = _bounds(tz, first, last)
    if column is None:
        n = db.execute(f"SELECT COUNT(*) {LEADS}", (site, lo, hi)).fetchone()[0]
        return Counter({"leads": n})
    return Counter(dict(db.execute(
        f"SELECT COALESCE(NULLIF({column}, ''), ?), COUNT(*) {LEADS} GROUP BY 1",
        (UNKNOWN, site, lo, hi)).fetchall()))


def check_insights(path: Path, site: str, tz, items: list[dict]) -> dict[int, list[str]]:
    """{index: problems} for the findings the SQL count disagrees with."""
    out: dict[int, list[str]] = {}
    db = _open(path)
    try:
        for i, item in enumerate(items):
            kind = (item.get("subject") or {}).get("kind")
            name = (item.get("subject") or {}).get("name")
            if kind not in COLUMN:
                out[i] = [f"a lead finding about {kind!r} cannot be recounted"]
                continue
            column = COLUMN[kind]
            after = item["period"]["after"]
            now = range_counts(db, site, tz, after[0], after[1], column)
            problems = []
            if item.get("top"):
                ranked = sorted(((k, v) for k, v in now.items() if k not in SKIP and v),
                                key=lambda kv: (-kv[1], kv[0]))
                leader = ranked[0][0] if ranked and (len(ranked) == 1 or
                                                     ranked[1][1] < ranked[0][1]) else None
                whole = sum(range_counts(db, site, tz, after[0], after[1], None).values())
                if leader != name:
                    problems.append(f"the SQL count's leader is {leader!r}, not {name!r}")
                if now.get(name, 0) != item.get("after"):
                    problems.append(f"{name}: file {item.get('after')}, SQL recount "
                                    f"{now.get(name, 0)}")
                if whole != item.get("of"):
                    problems.append(f"all leads: file {item.get('of')}, SQL recount {whole}")
            else:
                if now.get(name, 0) != item.get("after"):
                    problems.append(f"after: file {item.get('after')}, SQL recount "
                                    f"{now.get(name, 0)}")
                before = item["period"].get("before")
                if before is not None:
                    then = range_counts(db, site, tz, before[0], before[1], column)
                    if then.get(name, 0) != item.get("before"):
                        problems.append(f"before: file {item.get('before')}, SQL recount "
                                        f"{then.get(name, 0)}")
            if problems:
                out[i] = problems
    finally:
        db.close()
    return out


def check_today(path: Path, site: str, tz, today: date, block: dict | None) -> list[str]:
    """Problems with conversions.json's `today` listing."""
    if not block or block.get("state") != "ok":
        return []
    lo, hi = _utc(today, tz), _utc(today + timedelta(days=1), tz)
    db = _open(path)
    try:
        got = {(a, s, bool(t)): n for a, s, t, n in db.execute(
            f"SELECT action, stage, test <> 0, COUNT(*) FROM conversions WHERE site = ? AND "
            f"action IN {_in(LEAD_ACTIONS)} AND at >= ? AND at < ? GROUP BY 1, 2, 3",
            (site, lo, hi))}
        # 2.26: the rows that finish a lead again, marked `repeat` and not listed as leads.
        again = db.execute(f"SELECT COUNT(*) FROM conversions c WHERE c.site = ? AND c.action "
                           f"IN {_in(LEAD_ACTIONS)} AND c.at >= ? AND c.at < ? AND c.test = 0 "
                           f"AND NOT ({once('c')})", (site, lo, hi)).fetchone()[0]
    finally:
        db.close()
    out = []
    total, tests = sum(got.values()), sum(n for (_, _, t), n in got.items() if t)
    if len(block.get("rows") or []) == total and \
            sum(1 for r in block["rows"] if r.get("repeat")) != again:
        out.append(f"today: file marks {sum(1 for r in block['rows'] if r.get('repeat'))} "
                   f"repeat finishes, SQL recount {again}")
    if block.get("total") != total:
        out.append(f"today: file lists {block.get('total')} rows, SQL recount {total}")
    if block.get("tests") != tests:
        out.append(f"today: file marks {block.get('tests')} test rows, SQL recount {tests}")
    rows = block.get("rows") or []
    if len(rows) == total:
        mine = Counter((r.get("action"), r.get("stage"), bool(r.get("test"))) for r in rows)
        for key in sorted(set(mine) | set(got), key=str):
            if mine.get(key, 0) != got.get(key, 0):
                out.append(f"today {' '.join(map(str, key))}: file {mine.get(key, 0)}, "
                           f"SQL recount {got.get(key, 0)}")
    elif len(rows) > total:
        out.append(f"today: {len(rows)} rows listed, more than the {total} the SQL finds")
    day = today.isoformat()
    if any(str(r.get("at") or "")[:10] != day for r in rows):
        out.append("today: a listed row is not of today")
    if block.get("by_now") is not None:
        out += check_by_now(path, site, tz, today, block["by_now"])
    if block.get("same_time") is not None:
        out += check_same_time(path, site, tz, today, block["same_time"])
    return out


def check_same_time(path: Path, site: str, tz, today: date, part: dict) -> list[str]:
    """Problems with `today.same_time` (2.27): each period's day before, from its
    midnight to the file's time of day, recounted by one SQL GROUP BY action
    between UTC bounds this module works out itself (the day's local midnight,
    and that day at `time`)."""
    out = []
    try:
        hh, mm, ss = (int(x) for x in str(part.get("time") or "").split(":"))
    except ValueError:
        return [f"same time: {part.get('time')!r} is not a time of day"]
    db = _open(path)
    try:
        for e in part.get("days") or []:
            if e.get("state") != "ok":
                continue
            day = date.fromisoformat(e["day"])
            if (today - day).days != e.get("back"):
                out.append(f"same time {e['day']}: not {e.get('back')} days before today")
            cut = datetime(day.year, day.month, day.day, hh, mm, ss, tzinfo=tz)
            if e.get("until") != cut.isoformat(timespec="seconds"):
                out.append(f"same time {e['day']}: until {e.get('until')}, expected "
                           f"{cut.isoformat(timespec='seconds')}")
            hi = cut.astimezone(timezone.utc).strftime(STAMP)
            got = dict(db.execute(f"SELECT c.action, COUNT(*) {LEADS} GROUP BY 1",
                                  (site, _utc(day, tz), hi)).fetchall())
            if e.get("leads") != sum(got.values()):
                out.append(f"same time {e['day']} to {str(e.get('until'))[11:16]}: file "
                           f"{e.get('leads')} leads, SQL recount {sum(got.values())}")
            if {k: v for k, v in (e.get("actions") or {}).items() if v} != got:
                out.append(f"same time {e['day']} by action: file {e.get('actions')}, "
                           f"SQL recount {got}")
    finally:
        db.close()
    return out


def _hour_counts(db, site: str, tz, day: date, cut: datetime | None) -> list[int]:
    """Leads in each local hour of `day` (cut short at `cut`), one SQL COUNT
    per hour between that hour's UTC bounds."""
    got = []
    nxt = day + timedelta(days=1)
    for hour in range(24):
        lo = datetime(day.year, day.month, day.day, hour, tzinfo=tz)
        hi = (datetime(day.year, day.month, day.day, hour + 1, tzinfo=tz) if hour < 23
              else datetime(nxt.year, nxt.month, nxt.day, tzinfo=tz))
        if cut is not None:
            hi = min(hi, cut)
        if hi <= lo:
            got.append(0)
            continue
        utc = [x.astimezone(timezone.utc).strftime(STAMP) for x in (lo, hi)]
        got.append(db.execute(f"SELECT COUNT(*) {LEADS}", (site, *utc)).fetchone()[0])
    return got


def check_by_now(path: Path, site: str, tz, today: date, part: dict) -> list[str]:
    """Problems with `today.by_now`: yesterday's leads to the same time of day,
    and both days by local hour, against the SQL's own hour bounds."""
    out = []
    db = _open(path)
    try:
        if part.get("today_hours") is not None:
            mine = _hour_counts(db, site, tz, today, None)
            if list(part["today_hours"]) != mine:
                out.append(f"today's leads by hour: file {part['today_hours']}, SQL recount {mine}")
        if part.get("state") == "ok":
            cut = datetime.fromisoformat(part["until"])
            mine = _hour_counts(db, site, tz, today - timedelta(days=1), cut)
            if part.get("hours") is None or list(part["hours"]) != mine:
                out.append(f"yesterday's leads by hour to {part['until'][11:16]}: file "
                           f"{part.get('hours')}, SQL recount {mine}")
            if part.get("leads") != sum(mine):
                out.append(f"yesterday's leads to {part['until'][11:16]}: file {part.get('leads')}, "
                           f"SQL recount {sum(mine)}")
    finally:
        db.close()
    return out
