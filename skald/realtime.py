"""Real time: who is on the site now, as of the live run (every 2 minutes).

Overview > Real time and the top of Overview > Summary in Live mode. Two
roads, never mixed on screen:

  * people, from this module: built inside the live run from the same
    tally as every other figure of today (live.build), so the people rule
    - rendering, crawler sessions, our own traffic, the visit gap - is the
    main road's, to the letter. Fresh to the live run's `until`.
  * requests, from realtime_tail.py: the newest log lines counted every
    15 seconds by the helper, all requests of the site's hosts, unsorted
    (a request is not a person). Fresh to the second it was read.

What the live run adds to its snapshot, `realtime` (docs/DATA-CONTRACT-REALTIME.md):

  active        readers' visits (visits that read a page, = the readers)
                with a request in the last 5 and the last 30 minutes before
                `until`: {"5": n, "30": n}
  per_minute    the last MINUTES clock minutes, oldest first, the last one
                running to `until`: per minute the visits under way (first
                request before the minute ended, last request in it or
                after), the visits that started in it, and the requests of
                each group in it
  countries     every country with a visit today: its visits and how many
                of them are active (last 30 minutes)
  cities        only with a city file (logs.city_db): each city with a
                visit today, "Toronto, Ontario, CA": {visits, active, lat,
                lon}; every active city, then the most visits up to
                TOP_CITIES, the rest one "(all others)" row (no point). A
                visit whose city is not recorded is in no row: their visits
                are visits_today minus the rows' sum
  sources, devices
                the active visits by their source and device (the labels of
                their first page, as the readers breakdowns label it)
  pages         people's page views in the last 30 minutes, by page (folded:
                the top TOP_PAGES and "(all others)")
  machines      requests in the last 30 minutes: AI assistants and search
                crawlers by name (folded), other bots and scanners as one count
  newest        the NEWEST newest visits by their first request: start (to
                the minute), country, device, source, who sent it, landing
                page, pages read so far, still active, where its visitor first
                came from (first_touch, firsttouch.py) and its place in the day
                (seq). No address, no user agent, ever.

audit_realtime.py counts every one of these again from the raw lines
(`skald audit --live`).

realtime.json (the data file, data_more.FILES) is this part of the snapshot
for the site's own page; a view's page says the figures are the whole site's.
"""
from __future__ import annotations

import math
from collections import Counter
from datetime import datetime, timedelta, timezone

from . import dimensions as dim
from .classify import Group

VERSION = 1
MINUTES = 30             # the window: active "now", per-minute bars, lists
SHORT = 5                # "active in the last 5 minutes"
TOP_PAGES = 25
TOP_NAMES = 15
TOP_CITIES = 60
OTHER = "(all others)"
NEWEST = 10
STALE_MINUTES = 10


def _aware(when: datetime) -> datetime:
    return when if when.tzinfo else when.replace(tzinfo=timezone.utc)


def minute_of(when: datetime) -> int:
    """Minutes since the epoch: the clock minute a moment falls in."""
    return int(_aware(when).timestamp()) // 60


def last_minute(until: datetime) -> int:
    """The last clock minute before `until` (an end, not included): the
    minute of the moment just before it."""
    return (math.ceil(_aware(until).timestamp()) - 1) // 60


def slots(until: datetime, minutes: int = MINUTES) -> list[tuple[datetime, datetime]]:
    """The clock minutes shown, oldest first: (start, end), the last one
    ending at `until` (it is still running)."""
    last = last_minute(until)
    out = []
    for m in range(last - minutes + 1, last + 1):
        start = datetime.fromtimestamp(m * 60, timezone.utc)
        out.append((start, min(start + timedelta(minutes=1), until)))
    return out


class Observer:
    """The live tally's observer (live._Observers): requests per minute by
    group, people's page views and the machines of the last 30 minutes."""

    def __init__(self, until: datetime, minutes: int = MINUTES) -> None:
        self.until = _aware(until)
        self.since = self.until - timedelta(minutes=minutes)
        self.first = last_minute(self.until) - minutes + 1
        self.requests: dict[int, Counter] = {}
        self.pages: Counter = Counter()
        self.ai: Counter = Counter()
        self.search: Counter = Counter()
        self.bots = 0

    def __call__(self, hit, verdict) -> None:
        when = _aware(hit.when)
        if when >= self.until:
            return
        m = minute_of(when)
        if m >= self.first:
            self.requests.setdefault(m, Counter())[verdict.group.value] += 1
        if when < self.since:
            return
        group = verdict.group
        if group is Group.ANSWER_ENGINE:
            self.ai[verdict.engine or "(unnamed)"] += 1
        elif group is Group.SEARCH_ENGINE:
            self.search[verdict.engine or "(unnamed)"] += 1
        elif group is Group.BOTS:
            self.bots += 1
        elif group is Group.PEOPLE and hit.is_page:
            self.pages[hit.path[:70]] += 1


def visit_figures(visits, until: datetime, minutes: int = MINUTES) -> dict:
    """The people part from the readers' visits: an iterable of (first,
    last, labels) with labels holding country, source and device. Shared by
    the live run (the journeys) and nothing else: the audit has its own."""
    until = _aware(until)
    since, recent = until - timedelta(minutes=minutes), until - timedelta(minutes=SHORT)
    edges = slots(until, minutes)
    under = [0] * len(edges)
    started = [0] * len(edges)
    countries: dict[str, dict] = {}
    cities: dict[str, dict] = {}
    sources, devices = Counter(), Counter()
    active = {str(SHORT): 0, str(minutes): 0}
    for first, last, labels in visits:
        first, last = _aware(first), _aware(last)
        cc = labels.get("country") or "Unknown"
        row = countries.setdefault(cc, {"visits": 0, "active": 0})
        row["visits"] += 1
        city = labels.get("city") or ""
        if city:
            place = cities.setdefault(city, {"visits": 0, "active": 0})
            place["visits"] += 1
        if last < edges[0][0]:
            continue
        for i, (start, end) in enumerate(edges):
            if first < end and last >= start:
                under[i] += 1
            if start <= first < end:
                started[i] += 1
        if last >= since:
            active[str(minutes)] += 1
            row["active"] += 1
            if city:
                place["active"] += 1
            sources[labels.get("source") or "Direct or unknown"] += 1
            devices[labels.get("device") or "Unknown"] += 1
        if last >= recent:
            active[str(SHORT)] += 1
    return {"active": active, "under_way": under, "started": started,
            "countries": dict(sorted(countries.items())), "cities": cities,
            "sources": dict(sources.most_common()), "devices": dict(devices.most_common())}


def city_rows(cities: dict, points: dict) -> dict:
    """The cities kept: every active one, then the most visits up to
    TOP_CITIES; the rest folded into one OTHER row. Each kept city with
    its point (lat, lon) when the file had one."""
    order = sorted(cities.items(), key=lambda kv: (-kv[1]["active"], -kv[1]["visits"], kv[0]))
    out, rest = {}, {"visits": 0, "active": 0}
    for name, row in order:
        if row["active"] or len(out) < TOP_CITIES:
            out[name] = dict(row)
            if name in points:
                out[name]["lat"], out[name]["lon"] = points[name]
        else:
            rest["visits"] += row["visits"]
            rest["active"] += row["active"]
    if rest["visits"]:
        out[OTHER] = rest
    return out


def part(totals, observer: Observer, tz, minutes: int = MINUTES) -> dict:
    """The snapshot's `realtime` part, from the day's tally and the observer."""
    until = observer.until
    journeys = list(totals.journeys or [])
    people = list(totals.people or [])
    if len(people) != len(journeys):
        people = []
    rows = [(who["first"], who["last"], j) for j, who in zip(journeys, people)]
    got = visit_figures(rows, until, minutes)
    per_minute = []
    for i, (start, _) in enumerate(slots(until, minutes)):
        per_minute.append({"at": start.astimezone(tz).isoformat(timespec="minutes"),
                           "under_way": got["under_way"][i], "started": got["started"][i],
                           "requests": dict(observer.requests.get(minute_of(start), {}))})
    recent = until - timedelta(minutes=SHORT)
    since = until - timedelta(minutes=minutes)
    newest = []
    for first, last, j in sorted(rows, key=lambda r: _aware(r[0]), reverse=True)[:NEWEST]:
        newest.append({"start": j.get("start"), "country": j.get("country"),
                       "city": j.get("city") or "",
                       "device": j.get("device"), "browser": j.get("browser"),
                       "source": j.get("source"), "via": j.get("via") or "",
                       "landing": j.get("landing"), "pages": j.get("pages", 0),
                       # steps seen only in the browser (visits.py): shown beside pages
                       "in_app": j.get("in_app", 0),
                       # firsttouch.py: where its visitor first came from (labels only)
                       "first_touch": j.get("first_touch"),
                       # the visit's place in the day: the visitor drawer opens it
                       "seq": j.get("seq"),
                       "active": "5" if _aware(last) >= recent else
                       "30" if _aware(last) >= since else ""})
    points = getattr(totals, "city_points", None)
    more = {} if points is None else {"cities": city_rows(got["cities"], points)}
    return {
        **more,
        "version": VERSION, "minutes": minutes, "short": SHORT,
        "until": until.astimezone(tz).isoformat(timespec="seconds"),
        "visits_today": len(rows),
        "active": got["active"],
        "per_minute": per_minute,
        "countries": got["countries"],
        "sources": got["sources"], "devices": got["devices"],
        "pages": dict(dim.fold(observer.pages, TOP_PAGES)),
        "page_views": sum(observer.pages.values()),
        "machines": {"answer_engines": dict(dim.fold(observer.ai, TOP_NAMES)),
                     "search_engines": dict(dim.fold(observer.search, TOP_NAMES)),
                     "bots": observer.bots},
        "newest": newest,
    }


# ------------------------------------------------------------- realtime.json

def build(p) -> dict:
    """realtime.json: the snapshot's `realtime` part, for the site's own
    page. A view's page carries none: the figures are the whole site's."""
    if p.view is not None:
        return {"state": "site", "realtime": None}
    snap = p.snap
    if not snap:
        return {"state": "empty", "realtime": None}
    if snap.get("state") != "ok":
        return {"state": snap.get("state") or "empty", "realtime": None}
    part = snap.get("realtime")
    if not part:
        return {"state": "empty", "realtime": None}
    state = "ok"
    try:
        if p.now - datetime.fromisoformat(part["until"]) > timedelta(minutes=STALE_MINUTES):
            state = "stale"
    except (KeyError, TypeError, ValueError):
        state = "stale"
    return {"state": state, "realtime": part}

