"""In-page events in history: collect, verify, audit, and events.json.

The beacon (beacon_server.py) appends each accepted event to the day's
spool. Once the day is over, run-daily turns the spool into daily counts per
(event, label, path, source) - the label is which button or form, the source
the visit's source type - and keeps them `beacon.keep_days` (400) days:

  event_counts  site, day, event, label, path, source, n   (people only)
  event_days    one row per day: state, totals, our own events, events by
                AI assistant, the helper's counters, anomalies, the audit

Both tables live in the history file. They are created the first time this
module opens it and older code simply ignores them; nothing else in the file
changes. Rows are filed under the site, never a view: a view filters the
rows by its path rule when events.json is written.

Verify, at collect. An event comes from a page someone loaded, so a page's
events cannot run far ahead of its readers:

  * per path, events (except 404_view) <= FACTOR x the page's people views
    or visits from the log, whichever is larger, + SLACK; 404_view against
    the people 404s of that path. A path past its bound is an anomaly,
    recorded and shown, not hidden.
  * for the day, all events <= DAY_FACTOR x people page views + DAY_SLACK.
    Past that, something other than readers is posting: the day's events
    are withheld.

Audit, by a separate road. The spool is recounted from its raw text (a
pattern, not the JSON reader collect used) and compared with what was
stored; and nginx's own record of the beacons it answered 204 (the beacon
log, `beacon.log`) is counted and compared with the spool's lines, allowing
only the events within EDGE_SECONDS of midnight, which the two clocks may
file on different days. A mismatch withholds the day's events. The
recount also reads each line's source with its own pattern and compares
people's events by event and source: a mismatch there withholds only the
by-source block (events.json drops the day's sources; goals leave it out).

Goals (`beacon.goals`, a list of event names): events.json `goals` gives,
per day, each goal's events by source beside the day's visits by source
from the log, so the app shows events per 100 visits by source over any
range of the 400 days, and no rate over fewer than MIN_RATE visits.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from . import beacon
from .config import setting

FACTOR, SLACK = 10, 20
DAY_FACTOR, DAY_SLACK = 10, 50
NF_FACTOR, NF_SLACK = 3, 10
EDGE_SECONDS = 2
ROW_DAYS = 180            # events.json rows: the same 180 days as the other files
PATH_LEN = 200

SCHEMA = """
CREATE TABLE IF NOT EXISTS event_counts (
    site   TEXT NOT NULL,
    day    TEXT NOT NULL,
    event  TEXT NOT NULL,                -- beacon.EVENTS
    label  TEXT NOT NULL,                -- which button or form, "" when none
    path   TEXT NOT NULL,
    source TEXT NOT NULL,                -- dimensions.SOURCE_TYPES
    n      INTEGER NOT NULL,
    PRIMARY KEY (site, day, event, label, path, source)
);
CREATE TABLE IF NOT EXISTS event_days (
    site        TEXT NOT NULL,
    day         TEXT NOT NULL,
    state       TEXT NOT NULL,           -- ok / withheld
    events      INTEGER NOT NULL,        -- people's events, all kinds
    ours_json   TEXT NOT NULL,           -- {event: n} from our own addresses
    ai_json     TEXT NOT NULL,           -- {assistant: {event: n}}
    helper_json TEXT,                    -- the helper's counters for the day
    anomalies   TEXT NOT NULL,           -- JSON list
    problems    TEXT,                    -- why withheld
    audit_json  TEXT,                    -- the audit's result, or NULL
    collected_at TEXT NOT NULL,
    PRIMARY KEY (site, day)
);
"""


def enabled(config: dict) -> bool:
    return setting(config, "beacon", "enabled", False) in (True, "true")


def keep_days(config: dict) -> int:
    return int(setting(config, "beacon", "keep_days", beacon.KEEP_DAYS))


def ensure(db) -> None:
    db.executescript(SCHEMA)


# ------------------------------------------------------------------ counting

def tally(rows: list[dict]) -> dict:
    """The day's counts from spool rows (collect's road)."""
    people, ours, ai = Counter(), Counter(), {}
    for row in rows:
        event = row["e"]
        if row.get("g") == "ours":
            ours[event] += 1
            continue
        people[(event, str(row.get("id") or ""), row["p"][:PATH_LEN],
                str(row.get("s") or "Direct or unknown"))] += 1
        if row.get("ai"):
            ai.setdefault(str(row["ai"]), Counter())[event] += 1
    return {"people": people, "ours": ours, "ai": ai}


def bounds(people: Counter, pages: dict | None, not_found: list | None,
           views: int | None) -> tuple[list[dict], list[str]]:
    """(anomalies, problems) for a day's events against its page views."""
    anomalies, problems = [], []
    total = sum(people.values())
    if views is None:
        anomalies.append({"kind": "unchecked",
                          "note": "the day's page views are not in history; bounds not checked"})
    elif total > DAY_FACTOR * views + DAY_SLACK:
        problems.append(f"{total:,} events against {views:,} page views by people: more than "
                        f"{DAY_FACTOR} per view + {DAY_SLACK}; something other than readers is "
                        f"posting")
    by_path, nf_by_path = Counter(), Counter()
    for (event, _label, path, _source), n in people.items():
        (nf_by_path if event == "404_view" else by_path)[path] += n
    if pages is not None:
        for path, n in sorted(by_path.items()):
            page = pages.get(path[:70]) or {}
            base = max(int(page.get("views", 0)), int(page.get("visits", 0)))
            limit = FACTOR * base + SLACK
            if n > limit:
                anomalies.append({"kind": "path", "path": path, "events": n,
                                  "views": base, "limit": limit})
    if not_found is not None:
        seen = Counter()
        for row in not_found:
            if row.get("group") == "people":
                seen[str(row.get("path", ""))] += int(row.get("n", 0))
        for path, n in sorted(nf_by_path.items()):
            base = seen.get(path[:100], 0)
            limit = NF_FACTOR * base + NF_SLACK
            if n > limit:
                anomalies.append({"kind": "404", "path": path, "events": n,
                                  "views": base, "limit": limit})
    return anomalies, problems


def _people_views(history, site: str, day: date) -> int | None:
    from .classify import Group
    for entry in history.daily(site, day, day):
        if entry["state"] in ("ok", "partial"):
            people = (entry.get("groups") or {}).get(Group.PEOPLE) or {}
            got = people.get("views")
            return int(got) if got is not None else None
    return None


def collect(history, config: dict, site: str, spool: Path, day: date,
            now: datetime | None = None) -> dict:
    """Count a day's spool into history. Returns the event_days row as a dict."""
    ensure(history.db)
    rows = beacon.read_day(spool, day)
    got = tally(rows)
    extras = history.extras(site, day, day, ("pages", "not_found")).get(day.isoformat(), {})
    anomalies, problems = bounds(got["people"], extras.get("pages"), extras.get("not_found"),
                                 _people_views(history, site, day))
    if rows.bad:
        anomalies.append({"kind": "spool", "note": f"{rows.bad} unreadable spool lines skipped"})
    helper = beacon.read_stats(spool, day)
    state = "withheld" if problems else "ok"
    stamp = (now or datetime.now(timezone.utc)).isoformat(timespec="seconds")
    key = (site, day.isoformat())
    db = history.db
    with db:
        db.execute("DELETE FROM event_counts WHERE site = ? AND day = ?", key)
        db.executemany(
            "INSERT INTO event_counts (site, day, event, label, path, source, n) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            [(*key, *k, n) for k, n in sorted(got["people"].items())])
        db.execute(
            "INSERT OR REPLACE INTO event_days (site, day, state, events, ours_json, ai_json, "
            "helper_json, anomalies, problems, audit_json, collected_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?)",
            (*key, state, sum(got["people"].values()), json.dumps(dict(got["ours"])),
             json.dumps({a: dict(c) for a, c in got["ai"].items()}),
             json.dumps(helper) if helper else None, json.dumps(anomalies),
             "; ".join(problems) or None, stamp))
        cutoff = (day - timedelta(days=keep_days(config))).isoformat()
        db.execute("DELETE FROM event_counts WHERE site = ? AND day < ?", (site, cutoff))
        db.execute("DELETE FROM event_days WHERE site = ? AND day < ?", (site, cutoff))
    return {"day": day.isoformat(), "state": state, "events": sum(got["people"].values()),
            "ours": sum(got["ours"].values()), "anomalies": anomalies, "problems": problems}


# --------------------------------------------------------------------- audit

_E = re.compile(r'"e":"([^"\\]{1,40})"')
_G = re.compile(r'"g":"([a-z]{1,10})"')
_AT = re.compile(r'"at":"([^"]{19,40})"')
# The visit's source type: a key of its own (after "{" or ","), letters and
# spaces only. Absent or empty is "Direct or unknown", as the helper writes it.
_S = re.compile(r'[{,]"s":"([A-Za-z ]{0,40})"')
_NGINX = re.compile(r"^(\S+) (\d{3})\b(?: (\S+))?")
NO_SOURCE = "Direct or unknown"


def recount_spool(path: Path) -> tuple[Counter, Counter, list[datetime], Counter]:
    """(people by event, ours by event, times, people by (event, source))
    from the raw spool text."""
    people, ours, times, by_source = Counter(), Counter(), [], Counter()
    if not path.exists():
        return people, ours, times, by_source
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        e, g, at = _E.search(line), _G.search(line), _AT.search(line)
        if not (e and g and at):
            continue
        if g.group(1) == "ours":
            ours[e.group(1)] += 1
        else:
            people[e.group(1)] += 1
            s = _S.search(line)
            by_source[(e.group(1), (s.group(1) if s else "") or NO_SOURCE)] += 1
        try:
            times.append(datetime.fromisoformat(at.group(1)))
        except ValueError:
            pass
    return people, ours, times, by_source


def beacon_log_files(config: dict) -> list[Path]:
    raw = setting(config, "beacon", "log")
    if not raw:
        return []
    from .parse import log_files
    path = Path(str(raw))
    return log_files(path.parent, path.name, 3)


def count_answered(files: list[Path], start: datetime, end: datetime,
                   site: str | None = None, first: bool = True) -> int:
    """204s (counted beacons) in nginx's beacon log inside [start, end).

    Since 2.9.0 the helper names the site each answer was for and nginx logs
    it as a third field: with `site`, only that site's are counted. A line
    without one (written before) was the first site's, the only one then."""
    import gzip
    n = 0
    for path in files:
        opener = gzip.open if path.suffix == ".gz" else open
        with opener(path, "rt", errors="replace") as handle:
            for line in handle:
                m = _NGINX.match(line)
                if not m or m.group(2) != "204":
                    continue
                if site is not None:
                    named = (m.group(3) or "").strip()
                    if named in ("", "-") and not first:
                        continue
                    if named not in ("", "-") and named != site:
                        continue
                try:
                    when = datetime.fromisoformat(m.group(1))
                except ValueError:
                    continue
                if start <= when < end:
                    n += 1
    return n


def audit(history, config: dict, site: str, spool: Path, day: date, tz,
          withhold: bool = True, first: bool = True) -> dict:
    """Recount a stored day by the second road. Returns the result, which
    is also stored on the day's row."""
    from .window import day_window
    ensure(history.db)
    row = history.db.execute("SELECT state, ours_json FROM event_days WHERE site = ? AND day = ?",
                             (site, day.isoformat())).fetchone()
    if row is None:
        return {"state": "not collected"}
    people, ours, times, by_source = recount_spool(beacon.day_file(spool, day))
    stored = Counter({e: n for e, n in history.db.execute(
        "SELECT event, SUM(n) FROM event_counts WHERE site = ? AND day = ? GROUP BY event",
        (site, day.isoformat()))})
    stored_source = Counter({(e, src): n for e, src, n in history.db.execute(
        "SELECT event, source, SUM(n) FROM event_counts WHERE site = ? AND day = ? "
        "GROUP BY event, source", (site, day.isoformat()))})
    # By source: a mismatch withholds the by-source block only (events.json
    # drops the day's sources and goals leave it out); the totals stand.
    source_problems = [f"people {e} from {src}: spool {by_source.get((e, src), 0)}, "
                       f"history {stored_source.get((e, src), 0)}"
                       for e, src in sorted(set(by_source) | set(stored_source))
                       if by_source.get((e, src), 0) != stored_source.get((e, src), 0)]
    stored_ours = Counter(json.loads(row[1] or "{}"))
    problems = []
    for name, a, b in (("people", people, stored), ("ours", ours, stored_ours)):
        for event in sorted(set(a) | set(b)):
            if a.get(event, 0) != b.get(event, 0):
                problems.append(f"{name} {event}: spool {a.get(event, 0)}, "
                                f"history {b.get(event, 0)}")
    start, end = day_window(day, tz)
    files = beacon_log_files(config)
    nginx = None
    if files:
        nginx = count_answered(files, start, end, site, first)
        lines = sum(people.values()) + sum(ours.values())
        edge = sum(1 for t in times
                   if abs((t - start).total_seconds()) <= EDGE_SECONDS
                   or abs((end - t).total_seconds()) <= EDGE_SECONDS)
        if abs(nginx - lines) > edge:
            problems.append(f"nginx answered {nginx} beacons with 204, the spool holds {lines}")
    result = {"state": "mismatch" if problems else "ok",
              "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "spool": sum(people.values()) + sum(ours.values()), "nginx": nginx,
              "problems": problems[:20],
              "by_source": "mismatch" if source_problems else "ok",
              "by_source_problems": source_problems[:20]}
    with history.db as db:
        if problems and withhold:
            db.execute("UPDATE event_days SET state = 'withheld', problems = ? "
                       "WHERE site = ? AND day = ?",
                       ("audit: " + "; ".join(problems[:5]), site, day.isoformat()))
        db.execute("UPDATE event_days SET audit_json = ? WHERE site = ? AND day = ?",
                   (json.dumps(result), site, day.isoformat()))
    return result


# ----------------------------------------------------------------- events.json

def _day_rows(db, site: str, first: date, last: date) -> dict[str, dict]:
    out = {}
    for r in db.execute(
            "SELECT day, state, events, ours_json, ai_json, helper_json, anomalies, problems, "
            "audit_json FROM event_days WHERE site = ? AND day BETWEEN ? AND ?",
            (site, first.isoformat(), last.isoformat())):
        out[r[0]] = {"state": r[1], "events": r[2], "ours": json.loads(r[3] or "{}"),
                     "ai": json.loads(r[4] or "{}"), "helper": json.loads(r[5]) if r[5] else None,
                     "anomalies": json.loads(r[6] or "[]"), "problems": r[7],
                     "audit": json.loads(r[8]) if r[8] else None}
    return out


def _site_of(key: str) -> str:
    return key.split("::", 1)[0]


def build(p) -> dict:
    """events.json (DATA-CONTRACT.md) for one page: data_more registers it."""
    site, view = _site_of(p.key), p.view
    keep = keep_days(p.config)
    first, last = p.anchor - timedelta(days=keep - 1), p.anchor
    ensure(p.history.db)
    days_db = _day_rows(p.history.db, site, first, last)
    row_first = p.anchor - timedelta(days=ROW_DAYS - 1)
    rows, totals, by_source = [], {}, {}
    for day, event, label, path, source, n in p.history.db.execute(
            "SELECT day, event, label, path, source, n FROM event_counts "
            "WHERE site = ? AND day BETWEEN ? AND ? ORDER BY day, event, path",
            (site, first.isoformat(), last.isoformat())):
        if view is not None and not view.matches(path):
            continue
        if days_db.get(day, {}).get("state") == "ok":
            totals.setdefault(day, Counter())[event] += n
            checked = _by_source(days_db[day])
            if checked == "ok":
                by_source.setdefault(day, {}).setdefault(event, Counter())[source] += n
            if day >= row_first.isoformat():
                # A day whose sources did not recount keeps its totals, not its sources.
                rows.append([day, event, label, path,
                             None if checked == "withheld" else source, n])
    started = min(days_db) if days_db else None
    days = []
    for i in range(keep):
        day = (first + timedelta(days=i)).isoformat()
        got = days_db.get(day)
        if got is None:
            days.append({"day": day, "state": "before" if started is None or day < started
                         else "missing"})
            continue
        entry = {"day": day, "state": got["state"], "anomalies": got["anomalies"],
                 "audit": (got["audit"] or {}).get("state"), "by_source": _by_source(got)}
        if got["state"] == "ok":
            entry["events"] = dict(totals.get(day, {}))
            entry["ours"] = got["ours"] if view is None else None
            entry["ai"] = got["ai"] if view is None else None
        else:
            entry["problems"] = got["problems"] or ""
        days.append(entry)
    spool = beacon.spool_dir(p.config, None, p.live_dir)
    return {"events": [{"name": e, "label": beacon.LABELS[e]}
                       for e in beacon.allowed_events(p.config)],
            "keep_days": keep, "first_day": started,
            "limits": {"factor": FACTOR, "slack": SLACK, "day_factor": DAY_FACTOR,
                       "day_slack": DAY_SLACK},
            "row_fields": ["day", "event", "label", "path", "source", "n"],
            "rows_from": row_first.isoformat(), "rows": rows, "days": days,
            "goals": goals_block(p, started, days_db, by_source, first, last),
            "today": _today(p, spool, view),
            "helper": {"today": beacon.read_stats(spool, p.today),
                       "yesterday": (days_db.get(p.anchor.isoformat()) or {}).get("helper")
                       or beacon.read_stats(spool, p.anchor)}}


def _by_source(got: dict) -> str | None:
    """A day's events by source: "ok" (recounted and matching), "withheld"
    (the recount by source disagreed), None (not recounted by source yet)."""
    said = (got.get("audit") or {}).get("by_source")
    return {"ok": "ok", "mismatch": "withheld"}.get(said) if got["state"] == "ok" else None


# ---------------------------------------------------------------------- goals

MIN_RATE = 10             # no rate over fewer visits than this (DATA-CONTRACT.md)


def goal_names(config: dict) -> list[str]:
    """`beacon.goals`: the events that are goals, each once, only those this
    site counts (beacon.allowed_events), in the order given."""
    raw = setting(config, "beacon", "goals") or []
    if isinstance(raw, str):
        raw = [raw]
    allowed = beacon.allowed_events(config)
    out: list[str] = []
    for name in raw:
        name = str(name).strip()
        if name in allowed and name not in out:
            out.append(name)
    return out


def _visits_by_source(p, first: date, last: date) -> tuple[dict, dict]:
    """({day: log state}, {day: {source type: visits}}) for the page's key:
    readers by source (the audit holds them) on whole, verified days."""
    states, visits = {}, {}
    for entry in p.history.daily(p.key, first, last):
        states[entry["day"].isoformat()] = entry["state"]
    measured = p.history.breakdown_days(p.key, first, last)
    days = sorted(d for d, st in states.items() if st == "ok" and d in measured)
    from .store import READER_KINDS
    for day, _kind, name, n in p.history.count_rows(p.key, [READER_KINDS["source"]], days):
        visits.setdefault(day, {})[name] = int(n)
    return states, {d: visits.get(d, {}) for d in days}


def goals_block(p, started: str | None, days_db: dict, by_source: dict, first: date,
                last: date) -> dict | None:
    """events.json `goals`: per day from the first event day, each goal's
    events by source beside the day's visits by source. A day counts only
    when its events are ok and recounted by source, and its log day is
    whole and verified; any other day is "left_out" with why."""
    names = goal_names(p.config)
    if not names:
        return None
    out = {"names": names, "labels": {g: beacon.LABELS.get(g, g) for g in names},
           "min_rate": MIN_RATE, "days": []}
    if started is None:
        return out
    begin = max(first, date.fromisoformat(started))
    states, visits = _visits_by_source(p, begin, last)
    day = begin
    while day <= last:
        d = day.isoformat()
        day += timedelta(days=1)
        got = days_db.get(d)
        why = None
        if got is None:
            why = "events not collected"
        elif got["state"] != "ok":
            why = "events withheld"
        elif _by_source(got) is None:
            why = "events not yet recounted by source"
        elif _by_source(got) == "withheld":
            why = "events by source did not recount"
        elif states.get(d) != "ok" or d not in visits:
            why = {"partial": "the log covers part of the day",
                   "withheld": "the day's log figures are withheld"}.get(
                states.get(d), "the day's visits by source are not recorded")
        if why:
            out["days"].append({"day": d, "state": "left_out", "why": why})
            continue
        got_events = by_source.get(d, {})
        out["days"].append({"day": d, "state": "ok", "visits": visits[d],
                            "events": {g: dict(got_events[g]) for g in names
                                       if g in got_events}})
    return out


def _today(p, spool: Path, view) -> dict | None:
    rows = beacon.read_day(spool, p.today)
    if view is not None:
        rows = [r for r in rows if view.matches(r["p"])]
    got = tally(rows)
    people = got["people"]
    if not rows:
        return {"state": "empty", "events": {}, "ours": {}, "rows": [], "ai": {}}
    views = None
    if p.snap and p.snap.get("state") == "ok" and view is None:
        # The live snapshot keeps people's page views under "people"; its
        # "groups" holds each group's request count (a number).
        views = (p.snap.get("people") or {}).get("views")
    _anomalies, problems = bounds(people, None, None, int(views) if views is not None else 0)
    if problems and views is not None:
        return {"state": "withheld", "problems": "; ".join(problems)}
    by_event = Counter()
    for (event, *_), n in people.items():
        by_event[event] += n
    times = sorted(r.get("at", "") for r in rows)
    return {"state": "ok", "from": times[0], "until": times[-1], "events": dict(by_event),
            "ours": dict(got["ours"]) if view is None else None,
            "ai": {a: dict(c) for a, c in got["ai"].items()} if view is None else None,
            "rows": [[*k, n] for k, n in sorted(people.items())]}


# ---------------------------------------------------------------- the command

def daily(ctx, day: date) -> int:
    """run-daily's step: collect yesterday's events, audit them, prune the
    spool. Never stops the run: events are an add-on to the log's figures."""
    if not enabled(ctx.config):
        return 0
    spool = beacon.spool_dir(ctx.config, ctx.config_path, ctx.live_dir)
    try:
        with ctx.history() as history:
            got = collect(history, ctx.config, ctx.site, spool, day)
            checked = audit(history, ctx.config, ctx.site, spool, day, ctx.tz,
                            first=_first(ctx))
        beacon.prune(spool, ctx.now.date(), keep_days(ctx.config))
    except Exception as why:            # noqa: BLE001 - never fails the day
        ctx.err(f"events {day}: {type(why).__name__}: {why}")
        return 0
    _say(ctx, got, checked)
    return 0


def _first(ctx) -> bool:
    """The install's first site: its state lives beside the history; the
    others' in sites/<name> (multisite.state_dir)."""
    return Path(ctx.live_dir) == Path(ctx.db_path).parent


def _say(ctx, got: dict, checked: dict) -> None:
    word = "WITHHELD" if got["state"] == "withheld" or checked.get("state") == "mismatch" \
        else "ok"
    ctx.out(f"events {got['day']}: {word}: {got['events']:,} events by people, "
            f"{got['ours']:,} our own; audit {checked.get('state')}"
            + (f" (nginx {checked['nginx']}, spool {checked['spool']})"
               if checked.get("nginx") is not None else "")
            + ("; by source WITHHELD" if checked.get("by_source") == "mismatch" else ""))
    for a in got["anomalies"]:
        ctx.out("  anomaly: " + (a.get("note") or
                                  f"{a['path']}: {a['events']} events, bound {a['limit']}"))
    for p in got["problems"] + checked.get("problems", []) + \
            checked.get("by_source_problems", []):
        ctx.err(f"  - {p}")


def cmd_events(ctx) -> int:
    from .window import parse_day
    day = parse_day(ctx.args.day, ctx.tz, ctx.now)
    spool = beacon.spool_dir(ctx.config, ctx.config_path, ctx.live_dir)
    if ctx.args.collect or ctx.args.audit:
        with ctx.history() as history:
            got = collect(history, ctx.config, ctx.site, spool, day) if ctx.args.collect else None
            checked = audit(history, ctx.config, ctx.site, spool, day, ctx.tz,
                            withhold=ctx.args.collect, first=_first(ctx))
        if got:
            _say(ctx, got, checked)
        else:
            ctx.out(f"events audit {day}: {checked.get('state')}; by source "
                    f"{checked.get('by_source')}")
            for p in checked.get("problems", []) + checked.get("by_source_problems", []):
                ctx.err(f"  - {p}")
        return 1 if "mismatch" in (checked.get("state"), checked.get("by_source")) else 0
    got = tally(beacon.read_day(spool, day))
    by_event = Counter()
    for (event, *_), n in got["people"].items():
        by_event[event] += n
    ctx.out(f"events {day} in the spool ({beacon.day_file(spool, day)}):")
    for event in beacon.allowed_events(ctx.config):
        if by_event.get(event) or got["ours"].get(event):
            ctx.out(f"  {event:16} {by_event.get(event, 0):6,} people "
                    f"{got['ours'].get(event, 0):6,} ours")
    stats = beacon.read_stats(spool, day)
    if stats:
        ctx.out("  helper: " + ", ".join(f"{k} {v}" for k, v in sorted(stats.items())
                                          if isinstance(v, int)))
    return 0


def add_command(sub) -> None:
    p = sub.add_parser("events", help="in-page events from the beacon: show a day's spool, "
                       "or --collect / --audit it into history")
    p.add_argument("--day", default="today")
    which = p.add_mutually_exclusive_group()
    which.add_argument("--collect", action="store_true",
                       help="count the day's spool into history, verify and audit it")
    which.add_argument("--audit", action="store_true",
                       help="recount a stored day from the spool and nginx's beacon log")
    p.set_defaults(run=cmd_events)
