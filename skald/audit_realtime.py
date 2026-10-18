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

The tail (recount_tail): every line of the site's hosts in the tail file's
own window [from, until), per clock minute, against what the helper counted.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone

OTHER = "(all others)"
MINUTES = 30
SHORT = 5
NEWEST = 10


def _minute(when: datetime) -> int:
    return int(when.timestamp()) // 60


def _last(end: datetime) -> int:
    """The minute of the last moment before `end`: the newest minute shown."""
    whole = int(end.timestamp())
    return (whole - (0 if end.timestamp() > whole else 1)) // 60


class Recount:
    def __init__(self, config: dict, day, tz, own: set) -> None:
        self.tz = tz
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
        sources, devices, pages = Counter(), Counter(), Counter()
        ai, search = Counter(), Counter()
        bots = 0
        active = {str(SHORT): 0, str(MINUTES): 0}
        for first, final, labels, _, seen in self.visits:
            row = countries.setdefault(labels["country"], [0, 0])
            row[0] += 1
            for i in range(MINUTES):
                if first < ends[i] and final >= starts[i]:
                    under[i] += 1
                if starts[i] <= first < ends[i]:
                    started[i] += 1
            if final >= since:
                active[str(MINUTES)] += 1
                row[1] += 1
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
        return {"active": active, "under": under, "started": started, "requests": requests,
                "starts": starts, "countries": countries, "sources": sources,
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
    for line in _read(files):
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


def live_tail(config: dict, live_dir, site: str, paths=None) -> tuple[list[str], int]:
    """(mismatches, figures compared) for the helper's last tail file, if any."""
    from .realtime_tail import load, tail_path
    answer = load(tail_path(live_dir, site))
    if not answer or not answer.get("from") or not answer.get("until"):
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
