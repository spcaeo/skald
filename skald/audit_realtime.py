"""The second count of Real time (the live snapshot's `realtime` part, and
the helper's last 15-second request count).

Registered in audit_more.RECOUNTS as "realtime", so audit.recount feeds it in
its one pass over the raw lines; it is compared by `skald audit --live`
(the part is never stored in history, so a day's audit has none to compare
and skips it). Written apart from realtime.py and realtime_tail.py: it reads
the audit's lines (audit.Line), the audit's groups and names (audit.Judge),
the audit's visits and the audit's labels of a visit's first page. Only
classify.py's name lists are shared, through the audit.

  the window      the recount's own end (the snapshot's `until`, which
                  `audit --live` recounts to): the last MINUTES clock
                  minutes, the last one cut at that end; "now" is the 30
                  minutes before it, "the last 5" the 5 before it
  active          a reader's visit (a visit with a page) whose last line is
                  in the last 5 / 30 minutes
  per minute      under way: the visit's first line before the minute's end
                  and its last line at or after its start; started: its
                  first line in it; requests: the lines of each group in it
  countries       every reader's visit today by the country of its first
                  page, and of those the ones active
  sources, devices
                  the active visits by the labels of their first page
  pages           people's page lines in the last 30 minutes, by path (the
                  first 70 characters, the query cut)
  machines        lines in the last 30 minutes: AI assistants and search
                  crawlers by the judge's name, other bots as one count
  newest          the newest visits by their first line: start to the
                  minute, country and pages read
  doing           the active visits by their newest line (2.20): start to
                  the minute, country, pages read and the newest line
  cities          with a city file only: every reader's visit today by the
                  audit's own city of its first page (audit_cities.py), and
                  of those the ones active; a visit with no city is in no
                  row. Each city the part kept, exactly; its "(all others)"
                  against the rest

The tail (recount_tail): every line of the site's hosts in the tail file's
own window [from, until), per clock minute, against what the helper counted.
Only a fresh tail is compared: its `until` no more than FRESH_MINUTES before
the audit's own end (the live snapshot's `until`). The helper writes the tail
only while someone has Real time open, so the file can be hours old, and a
line whose time is inside that old window may reach the log long after it
(a log shipper's lag: docomatic.ai, 2026-10-22, a tail from 20:52 UTC was
"14, the recount finds 18" four hours later, every run). The raw log does not
say when a line arrived, only when its request was made, so the recount
cannot leave out the late ones; age is the one rule it can apply. A stale
tail is reported as skipped, with its time, never as a mismatch and never
silently. A fresh tail is compared exactly: lines that reach the log within
those minutes, but after the helper read it, still show as a mismatch.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone

OTHER = "(all others)"
MINUTES = 30
SHORT = 5
NEWEST = 10
DOING = 50
# How old the helper's tail may be, against the audit's own end, and still be compared.
FRESH_MINUTES = 5


def _minute(when: datetime) -> int:
    return int(when.timestamp()) // 60


def _last(end: datetime) -> int:
    """The minute of the last moment before `end`: the newest minute shown."""
    whole = int(end.timestamp())
    return (whole - (0 if end.timestamp() > whole else 1)) // 60


class Recount:
    def __init__(self, config: dict, day, tz, own: set) -> None:
        self.tz = tz
        # A city file set (logs.city_db): cities are recounted.
        self.cities = bool(((config or {}).get("logs") or {}).get("city_db"))
        self.end = None
        self.lines: list[tuple] = []          # (when, group, name) of the last minutes
        self.visits: list[tuple] = []         # (first, last, labels, pages, page lines)

    def set_window(self, start: datetime, end: datetime) -> None:
        self.end = end

    def judged(self, line, group: str, info: dict) -> None:
        if self.end is None or line.when >= self.end:
            return
        if _minute(line.when) > _last(self.end) - MINUTES - 1:
            self.lines.append((line.when, group, info.get("name") or "(unnamed)"))

    def visit(self, lines: list, is_page, labels: dict | None) -> None:
        if labels is None or not lines:
            return
        pages = [(l.when, l.path[:70]) for l in lines if is_page(l)]
        self.visits.append((lines[0].when, lines[-1].when, labels, len(pages), pages))

    # ------------------------------------------------------------ the figures
    def figures(self, end: datetime) -> dict:
        since, recent = end - timedelta(minutes=MINUTES), end - timedelta(minutes=SHORT)
        last = _last(end)
        starts = [datetime.fromtimestamp(m * 60, timezone.utc)
                  for m in range(last - MINUTES + 1, last + 1)]
        ends = [min(s + timedelta(minutes=1), end) for s in starts]
        under, started = [0] * MINUTES, [0] * MINUTES
        requests = [Counter() for _ in range(MINUTES)]
        countries: dict[str, list] = {}
        cities: dict[str, list] | None = {} if self.cities else None
        sources, devices, pages = Counter(), Counter(), Counter()
        ai, search = Counter(), Counter()
        bots = 0
        active = {str(SHORT): 0, str(MINUTES): 0}
        for first, final, labels, _, seen in self.visits:
            row = countries.setdefault(labels["country"], [0, 0])
            row[0] += 1
            place = None
            if cities is not None and labels.get("city") not in (None, "Unknown"):
                place = cities.setdefault(labels["city"], [0, 0])
                place[0] += 1
            for i in range(MINUTES):
                if first < ends[i] and final >= starts[i]:
                    under[i] += 1
                if starts[i] <= first < ends[i]:
                    started[i] += 1
            if final >= since:
                active[str(MINUTES)] += 1
                row[1] += 1
                if place is not None:
                    place[1] += 1
                sources[labels["source"]] += 1
                devices[labels["device"]] += 1
            if final >= recent:
                active[str(SHORT)] += 1
            for when, path in seen:
                if since <= when < end:
                    pages[path] += 1
        for when, group, name in self.lines:
            if when >= end:
                continue
            i = _minute(when) - (last - MINUTES + 1)
            if 0 <= i < MINUTES:
                requests[i][group] += 1
            if when < since:
                continue
            if group == "answer_engines":
                ai[name] += 1
            elif group == "search_engines":
                search[name] += 1
            elif group == "bots":
                bots += 1
        newest = sorted(self.visits, key=lambda v: v[0], reverse=True)
        doing = sorted((v for v in self.visits if v[1] >= since), key=lambda v: v[1], reverse=True)
        return {"doing": doing,"active": active, "under": under, "started": started, "requests": requests,
                "starts": starts, "countries": countries, "cities": cities,
                "sources": sources,
                "devices": devices, "pages": pages, "ai": ai, "search": search, "bots": bots,
                "visits": len(self.visits), "newest": newest}

    def compare(self, stored: dict, same, problems: list) -> None:
        part = (stored or {}).get("realtime")
        if not part:
            return
        try:
            end = datetime.fromisoformat(part["until"]).astimezone(timezone.utc)
        except (KeyError, TypeError, ValueError):
            problems.append("real time: the snapshot's part has no time to recount to")
            return
        got = self.figures(end)
        same("real time: readers' visits today", int(part.get("visits_today", 0)), got["visits"])
        for k in (str(SHORT), str(MINUTES)):
            same(f"real time: visits active in the last {k} minutes",
                 int((part.get("active") or {}).get(k, 0)), got["active"][k])
        rows = part.get("per_minute") or []
        same("real time: minutes shown", len(rows), MINUTES)
        for i, row in enumerate(rows[:MINUTES]):
            at = got["starts"][i].astimezone(self.tz).isoformat(timespec="minutes")
            if row.get("at") != at:
                problems.append(f"real time: minute {i + 1} is {row.get('at')}, "
                                f"the recount's is {at}")
                continue
            same(f"real time {at}: visits under way", int(row.get("under_way", 0)), got["under"][i])
            same(f"real time {at}: visits started", int(row.get("started", 0)), got["started"][i])
            kept = Counter(row.get("requests") or {})
            for g in sorted(set(kept) | set(got["requests"][i])):
                same(f"real time {at}: {g} requests", int(kept.get(g, 0)), got["requests"][i][g])
        stored_cc = part.get("countries") or {}
        for cc in sorted(set(stored_cc) | set(got["countries"])):
            s = stored_cc.get(cc) or {}
            c = got["countries"].get(cc, [0, 0])
            same(f"real time: visits today from {cc}", int(s.get("visits", 0)), c[0])
            same(f"real time: visits active from {cc}", int(s.get("active", 0)), c[1])
        _cities(part.get("cities"), got["cities"], same, problems)
        for name, key in (("sources", "sources"), ("devices", "devices")):
            kept = Counter(part.get(key) or {})
            for label in sorted(set(kept) | set(got[key])):
                same(f"real time: active visits, {name} {label}", int(kept.get(label, 0)),
                     got[key][label])
        same("real time: page views in the last 30 minutes", int(part.get("page_views", 0)),
             sum(got["pages"].values()))
        _folded("real time: page views of", Counter(part.get("pages") or {}), got["pages"], same)
        machines = part.get("machines") or {}
        _folded("real time: AI assistant requests,",
                Counter(machines.get("answer_engines") or {}), got["ai"], same)
        _folded("real time: search crawler requests,",
                Counter(machines.get("search_engines") or {}), got["search"], same)
        same("real time: bot and scanner requests", int(machines.get("bots", 0)), got["bots"])
        _newest(part.get("newest") or [], got["newest"], self.tz, same, problems)
        if "doing" in part:
            _doing(part.get("doing") or [], got["doing"], self.tz, same, problems)


def _cities(stored: dict | None, counted: dict | None, same, problems: list) -> None:
    """Each city the part kept, its visits and active visits exactly; the
    folded "(all others)" against the rest. A city file on one road only
    is a mismatch."""
    if stored is None and counted is None:
        return
    if stored is None or counted is None:
        problems.append("real time: cities are counted on one road only "
                        f"(the snapshot {'has' if stored is not None else 'has none'})")
        return
    for i, what in ((0, "visits today"), (1, "visits active")):
        kept = Counter({k: int((v or {}).get("visits" if i == 0 else "active", 0))
                        for k, v in stored.items()})
        _folded(f"real time: {what} from", kept, Counter({k: v[i] for k, v in counted.items()}),
                same)


def _folded(what: str, stored: Counter, counted: Counter, same) -> None:
    """Each label kept exactly; the folded "(all others)" against the rest."""
    for label in sorted(k for k in stored if k != OTHER):
        same(f"{what} {label}", stored[label], counted.get(label, 0))
    rest = sum(v for k, v in counted.items() if k not in stored or k == OTHER)
    same(f"{what} {OTHER}", stored.get(OTHER, 0), rest)


def _newest(listed: list, visits: list, tz, same, problems: list) -> None:
    """The newest visits: start (to the minute), country and pages, as a set
    (two visits that started in the same second may be listed either way)."""
    if len(visits) > NEWEST and visits[NEWEST - 1][0] == visits[NEWEST][0]:
        return          # a tie at the edge of the list: either visit may be in it
    def key(start, country, pages):
        return f"{start} {country} {pages}"
    stored = Counter(key(v.get("start"), v.get("country"), int(v.get("pages", 0))) for v in listed)
    counted = Counter(key(first.astimezone(tz).strftime("%Y-%m-%dT%H:%M"), labels["country"], n)
                      for first, _, labels, n, _ in visits[:NEWEST])
    same("real time: newest visits listed", sum(stored.values()), sum(counted.values()))
    for k in sorted(set(stored) | set(counted)):
        if stored[k] != counted[k]:
            problems.append(f"real time: newest visits, {k}: listed {stored[k]}, "
                            f"recounted {counted[k]}")


def _doing(listed: list, active: list, tz, same, problems: list) -> None:
    """What visitors are doing now (2.20): the DOING active visits by their newest line,
    each by start (to the minute), country and pages read, as a set (two visits whose
    newest lines came in the same second may be listed either way), and its newest line
    to the second; never more rows than visits active."""
    same("real time: active visits listed with their pages", len(listed), min(len(active), DOING))
    if len(active) > DOING and active[DOING - 1][1] == active[DOING][1]:
        return
    def key(start, country, pages, last):
        return f"{start} {country} {pages} {last}"
    stored = Counter(key(v.get("start"), v.get("country"), int(v.get("pages", 0)), v.get("last")) for v in listed)
    counted = Counter(key(first.astimezone(tz).strftime("%Y-%m-%dT%H:%M"), labels["country"], n,
                          final.astimezone(tz).isoformat(timespec="seconds"))
                      for first, final, labels, n, _ in active[:DOING])
    for k in sorted(set(stored) | set(counted)):
        if stored[k] != counted[k]:
            problems.append(f"real time: active visit, {k}: listed {stored[k]}, recounted {counted[k]}")


# ------------------------------------------------------------------ the tail

def recount_tail(config: dict, answer: dict, paths=None) -> Counter:
    """Lines of the site's hosts in the tail file's window, per epoch minute."""
    from pathlib import Path
    from .audit import _read, log_files
    start = datetime.fromisoformat(answer["from"])
    end = datetime.fromisoformat(answer["until"])
    files = [Path(p) for p in paths] if paths else log_files(config)
    wanted = {str(h).lower() for h in ((config.get("site") or {}).get("hosts") or [])}
    got: Counter = Counter()
    # As far as the helper read each file (its `read_upto`); a tail file
    # written before it recorded one is counted from the whole files.
    for line in _read(files, answer.get("read_upto")):
        if not start <= line.when < end:
            continue
        if wanted and line.host and line.host.lower() not in wanted:
            continue
        got[_minute(line.when)] += 1
    return got


def compare_tail(answer: dict, counted: Counter, same) -> None:
    stored = {int(k): int(v) for k, v in (answer.get("per_minute") or {}).items()}
    for m in sorted(set(stored) | set(counted)):
        at = datetime.fromtimestamp(m * 60, timezone.utc).isoformat(timespec="minutes")
        same(f"real time requests (15-second count) at {at} UTC", stored.get(m, 0), counted[m])
    same("real time requests (15-second count), total", int(answer.get("total", 0)),
         sum(counted.values()))


def _audit_end(live_dir, site: str) -> datetime:
    """The live audit's own end: the snapshot's `until` (what `audit --live`
    recounts to), else now."""
    from .live import load, path_for
    snap = load(path_for(live_dir, site)) or {}
    try:
        return datetime.fromisoformat(snap["until"]).astimezone(timezone.utc)
    except (KeyError, TypeError, ValueError):
        return datetime.now(timezone.utc)


def stale(answer: dict, end: datetime) -> str | None:
    """Why the tail is too old to compare (FRESH_MINUTES before `end`), or None."""
    until = datetime.fromisoformat(answer["until"]).astimezone(timezone.utc)
    if end.astimezone(timezone.utc) - until <= timedelta(minutes=FRESH_MINUTES):
        return None
    when = until.strftime("%H:%M" if until.date() == end.astimezone(timezone.utc).date()
                          else "%Y-%m-%d %H:%M")
    return (f"real time requests (15-second count): skipped (snapshot from {when} UTC, "
            f"older than {FRESH_MINUTES} minutes)")


def live_tail(config: dict, live_dir, site: str, paths=None, end: datetime | None = None,
              say=print) -> tuple[list[str], int]:
    """(mismatches, figures compared) for the helper's last tail file, if any.
    A stale one (stale()) is not compared: `say` reports it skipped."""
    from .realtime_tail import load, tail_path
    answer = load(tail_path(live_dir, site))
    if not answer or not answer.get("from") or not answer.get("until"):
        return [], 0
    why = stale(answer, end if end is not None else _audit_end(live_dir, site))
    if why:
        say(why)
        return [], 0
    problems: list[str] = []
    compared = 0

    def same(what: str, stored: int, counted: int) -> None:
        nonlocal compared
        compared += 1
        if stored != counted:
            problems.append(f"{what}: the helper counted {stored:,}, the recount finds "
                            f"{counted:,}")
    compare_tail(answer, recount_tail(config, answer, paths), same)
    return problems, compared
