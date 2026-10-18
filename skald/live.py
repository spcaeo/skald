"""Today so far: a live, partial snapshot, kept apart from history.

Run every couple of minutes, it reads today - local midnight in
report.timezone onwards - and writes one small JSON file beside the history
database. The dashboard shows it in its own panel, labelled live and partial.

What keeps it honest is what it is NOT allowed to touch:

  * it never writes the daily history: a day is stored once it is over, by
    collect, from the whole day. A partial day stored as a day would be a
    small number pretending to be a quiet day.
  * it is never mailed and never used in a comparison. The mail and the
    KPI changes read history only.
  * it runs the same verify as everything else. If today's figures so far
    do not reconcile, the snapshot says "withheld" and carries no figures.

The "latest AI activity" list is the one thing here the totals do not keep:
the most recent assistant fetches and citation clicks, each as a time, who
(the assistant's name as the classifier matched it, or the citing site) and
the path. No address and no raw user agent is ever written, for anyone.

Cost: only the files that can hold today are opened (window.files_for), and
lines from before midnight are parsed but not classified. Classification is
cached per user agent (classify.Classifier), which is what makes a run over
a busy day's log take about a second rather than several.
"""
from __future__ import annotations

import heapq
import json
import os
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from .aggregate import READER_DIMS
from .classify import AI_ASKED, Group, Tier
from .config import ours_rules
from .store_visits import journey_days
from .files import slug, write_atomic
from .verify import check
from .window import analyse_window_views, day_window, today

LIVE_VERSION = 1
EVENTS = 20       # latest AI activity rows
TOP = 20          # top pages and names kept
JOURNEYS = 1000   # today's journeys kept in the snapshot, newest first


def path_for(directory: Path, site: str) -> Path:
    """Where a site's snapshot lives: beside the history database."""
    return Path(directory) / f"live-{slug(site)}.json"


class _Activity:
    """Watches the classified hits for assistant fetches and citation clicks.

    Keeps the EVENTS most recent by timestamp - files are read newest first,
    so arrival order is not time order - and counts engines per tier from
    the classifier's own verdict rather than re-deriving the tier from the
    name.
    """

    def __init__(self) -> None:
        self.latest: list[tuple] = []
        self.seq = 0
        self.tiers = {"training": Counter(), "asked": Counter()}

    def __call__(self, hit, verdict) -> None:
        if verdict.group is Group.ANSWER_ENGINE and verdict.tier:
            kind, who = verdict.tier.value, verdict.engine
            self.tiers.setdefault(kind, Counter())[who] += 1
        elif (verdict.group is Group.PEOPLE and verdict.tier is Tier.CITED
              and hit.is_page):
            # One per page landed on, not per request: a citation click
            # drags dozens of asset requests along with the same referrer.
            kind, who = "citation", verdict.engine
        else:
            return
        when = hit.when if hit.when.tzinfo else hit.when.replace(tzinfo=timezone.utc)
        self.seq += 1
        item = (when, self.seq, kind, who, hit.path[:70])
        if len(self.latest) < EVENTS:
            heapq.heappush(self.latest, item)
        elif item > self.latest[0]:
            heapq.heapreplace(self.latest, item)


def _top(counter, limit: int = TOP) -> dict:
    return dict(Counter(counter).most_common(limit))


def breakdowns(totals) -> dict:
    """The breakdowns of a Totals, JSON-ready: readers by each of
    aggregate.READER_DIMS, people's 404s, page speeds and slow pages, and
    per group the requests by status and the form posts. Every list here
    adds up to the figure it breaks down - verify checked it before this
    is called."""
    people = totals.groups.get(Group.PEOPLE)
    return {
        # "city" only when a city file counted it (logs.city_db).
        "by": {name: dict(people.by.get(name, {})) if people else {}
               for name in READER_DIMS + (("city",) if people and "city" in people.by
                                          else ())},
        "not_found": dict(people.not_found) if people else {},
        "speeds": dict(people.speeds) if people else {},
        "slow_pages": dict(people.slow_pages) if people else {},
        "server_errors": dict(totals.server_errors),
        "statuses": {g.value: dict(s.statuses) for g, s in totals.groups.items()},
        "posts": {g.value: {"total": s.posts, "pages": dict(s.post_pages)}
                  for g, s in totals.groups.items() if s.posts},
    }


def _figures(totals, ai_names: dict | None = None) -> dict:
    """Everything a panel shows, for the site or one view."""
    def group(which):
        return totals.groups.get(which)

    people = group(Group.PEOPLE)
    engines = group(Group.ANSWER_ENGINE)
    search = group(Group.SEARCH_ENGINE)
    bots = group(Group.BOTS)
    ours = group(Group.OURS)
    if ai_names is None:
        names = engines.engines if engines else Counter()
        ai_names = {
            "training": _top({k: v for k, v in names.items() if not AI_ASKED.fullmatch(k)}),
            "asked": _top({k: v for k, v in names.items() if AI_ASKED.fullmatch(k)}),
        }
    return {
        "requests": totals.hits,
        "groups": {g.value: (totals.groups[g].hits if g in totals.groups else 0)
                   for g in Group},
        "people": {
            "visits": people.visits if people else 0,
            "readers": people.readers if people else 0,
            "views": people.views if people else 0,
            "cited_visits": people.cited_visits if people else 0,
            "cited_by": _top(people.cited_by) if people else {},
            "pages": _top(people.pages) if people else {},
            "countries": _top(people.countries) if people else {},
        },
        "ai": ai_names,
        "ai_tiers": dict(engines.tiers) if engines else {},
        "ai_pages": _top(engines.pages) if engines else {},
        "search": _top(search.engines) if search else {},
        "bots": {"requests": bots.hits if bots else 0,
                 "probes": bots.probes if bots else 0},
        "ours": ours.hits if ours else 0,
        "other_hosts": totals.other_hosts,
        "unfiltered": totals.unfiltered,
        "breakdowns": breakdowns(totals),
        # People's visits today: metrics, and the anonymous journeys newest
        # first (visits.py). Our own traffic by the label of its rule.
        "visits": totals.visits.as_dict() if totals.visits is not None else None,
        "journeys": list(reversed(totals.journeys or []))[:JOURNEYS],
        "journeys_total": len(totals.journeys or []),
        "ours_labels": dict(totals.ours_labels or {}),
        "extras": totals.extras,
        "returning": totals.returning,
    }


def _state(totals, problems, site_parsed: int) -> str:
    if site_parsed == 0:
        return "empty"
    return "withheld" if problems else "ok"


def _history(db_path) -> "sqlite3.Connection | None":
    """History, read-only: live never writes it."""
    import sqlite3
    if db_path is None or not Path(db_path).exists():
        return None
    try:
        return sqlite3.connect(f"file:{Path(db_path).resolve()}?mode=ro", uri=True)
    except sqlite3.Error:
        return None


class _Observers:
    """Several observers of the tally pass as one; `excluded` goes to
    those that want another host's lines too (requests_feed.Feed)."""

    def __init__(self, *each) -> None:
        self.each = each

    def __call__(self, hit, verdict) -> None:
        for one in self.each:
            one(hit, verdict)

    def excluded(self, hit) -> None:
        for one in self.each:
            if hasattr(one, "excluded"):
                one.excluded(hit)


def build(config: dict, site: str, tz: ZoneInfo, now: datetime,
          views=(), db_path=None, feed=None, upto: dict | None = None) -> dict:
    """Today from local midnight, verified, as a JSON-ready dict.

    With `views` (config.View), each view's figures today are under
    snap["views"][slug], verified on their own, the same way collect
    verifies a view: a view with no lines today is a true zero.

    `upto` is each plain log file's size at the start of the run
    (window.plain_sizes; taken here when not given): every file is read only
    that far, and the snapshot records it as `read_upto`, so `audit --live`
    recounts the very same bytes, not the lines appended since."""
    if upto is None:
        from .window import plain_sizes
        upto = plain_sizes(config)
    now = now.astimezone(tz)
    day = today(tz, now)
    start, end = day_window(day, tz)
    # Up to now, not to midnight: the panel says "00:00 to <now>", and every
    # figure in it must be inside that. Up to the start of this second, not
    # into it: nginx may still be writing lines stamped with it, and a
    # recount a moment later would find one the snapshot never saw.
    end = min(end, now.astimezone(timezone.utc).replace(microsecond=0))
    activity = _Activity()
    from .ai_activity import AIEvents
    from .privacy import forgotten
    from .visitors import annotate, load_key, repeat_days
    hidden = forgotten(Path(db_path).parent if db_path is not None else None)
    ai = AIEvents(load_key(config), hidden)
    from . import realtime
    now_seen = realtime.Observer(end)          # Real time: the last 30 minutes
    from . import by_now
    # Today's page views and AI-sent visits by hour, for "yesterday at this hour".
    hours = by_now.Hours(tz, int(((config.get("report") or {}).get("session_gap_minutes")) or 30))
    observe = _Observers(activity, ai, now_seen, hours, *([feed] if feed is not None else []))

    totals, by_view = analyse_window_views(config, start, end, now=now, top=TOP,
                                           observe=observe, views=views, upto=upto)
    problems = check(totals)
    state = _state(totals, problems, totals.parsed)
    snap = {
        "version": LIVE_VERSION,
        "site": site,
        "timezone": str(tz),
        "day": day.isoformat(),
        "from": start.astimezone(tz).isoformat(),
        "generated_at": now.isoformat(timespec="seconds"),
        # The exact end of the window read, so a recount can use the same one.
        "until": end.isoformat(),
        # How far each plain log file was read, in bytes: the audit reads as far.
        "read_upto": dict(upto),
        "state": state,
        "problems": [str(p) for p in problems] if state == "withheld" else [],
        "parsed": totals.parsed,
        "lines_read": totals.lines_read,
        "unparsed": totals.unparsed,
    }
    if state != "ok":
        return snap
    from .people.visits import keep_live          # today's visits with addresses (2.4.0)
    keep_live(config, db_path, site, day, totals)
    db = _history(db_path)
    try:
        for t in [totals, *by_view.values()]:
            annotate(t, db, site, day, repeat_days(config))
        from .firsttouch import annotate as first_touch   # after keep_live: today's visits
        first_touch(totals, config, Path(db_path).parent if db_path is not None else None,
                    site, day, tz, end, db)
        snap["ai_activity"] = ai.result(tz, db, site, day)
        # Yesterday up to this time of day, by the same tally (by_now.py).
        snap["by_now"] = by_now.part(config, site, tz, end, now, upto, db, totals, hours)
    finally:
        if db is not None:
            db.close()
    snap.update(_figures(totals, {tier: _top(names)
                                  for tier, names in activity.tiers.items()}))
    # What counts as our own traffic, by label only - never an address.
    # Real time (realtime.py): who is on the site now, as of `until`.
    snap["realtime"] = realtime.part(totals, now_seen, tz)
    snap["ours_rules"] = ours_rules(config)
    snap["journey_days"] = journey_days(config)
    snap["events"] = [
        {"at": when.astimezone(tz).isoformat(timespec="seconds"),
         "kind": kind, "who": who, "path": path}
        for when, _, kind, who, path in sorted(activity.latest, reverse=True)
    ]
    snap["views"] = {}
    for view in views:
        figures = by_view[view.slug]
        got = [p for p in check(figures) if p.what != "nothing parsed"]
        entry = {"name": view.name, "state": "withheld" if got else "ok",
                 "problems": [str(p) for p in got]}
        if not got:
            entry.update(_figures(figures))
        snap["views"][view.slug] = entry
    return snap


def view_snapshot(snap: dict | None, slug: str) -> dict | None:
    """A view's part of the site's snapshot, shaped like a snapshot itself,
    so the panel and the export read it the same way. None when the
    snapshot predates views or carries no figures."""
    if not snap or snap.get("state") != "ok":
        return snap
    entry = (snap.get("views") or {}).get(slug)
    if entry is None:
        return None
    out = {k: snap[k] for k in ("version", "site", "timezone", "day", "from",
                                "generated_at", "parsed", "lines_read", "unparsed",
                                "ours_rules", "journey_days")
           if k in snap}
    out.update(entry)
    out.setdefault("events", [])
    return out


def ai_path(path: Path) -> Path:
    """Where today's AI events (with addresses) live: their own file beside
    the snapshot, so the snapshot itself never holds an address."""
    path = Path(path)
    return path.with_name(path.stem + "-ai.json")


def save(path: Path, snap: dict) -> None:
    ai = snap.pop("ai_activity", None)
    if ai is not None:
        write_atomic(ai_path(path), json.dumps(
            {"version": LIVE_VERSION, "day": snap.get("day"),
             "generated_at": snap.get("generated_at"), **ai}, indent=1) + "\n")
        os.chmod(ai_path(path), 0o640)
    elif ai_path(path).exists():
        ai_path(path).unlink()
    write_atomic(Path(path), json.dumps(snap, indent=1, sort_keys=True) + "\n")


def load_ai(path: Path) -> dict | None:
    try:
        got = json.loads(ai_path(path).read_text())
    except (OSError, ValueError):
        return None
    return got if isinstance(got, dict) else None


def load(path: Path) -> dict | None:
    """A snapshot, or None if there is none or it cannot be trusted."""
    try:
        snap = json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return None
    if not isinstance(snap, dict) or snap.get("version") != LIVE_VERSION:
        return None
    return snap


def sites_in(directory: Path) -> list[str]:
    """Sites that have a snapshot in this directory."""
    found = []
    for path in sorted(Path(directory).glob("live-*.json")):
        snap = load(path)
        if snap and snap.get("site"):
            found.append(str(snap["site"]))
    return found
