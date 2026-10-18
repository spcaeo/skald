"""Exact time windows: one local calendar day, or a run of them.

`--days N` reads N log files and reports whatever is in them, which is the
right tool for a glance and the wrong one for history. Rotation does not
happen at midnight (Debian's cron.daily runs around 06:25), so "the file for
yesterday" holds parts of two days, and a series built from files would
double-count or drop the hours either side of each rotation.

A day here is [00:00, 24:00) in the configured IANA timezone, converted to
an absolute instant at each end. On the day clocks change it is 23 or 25
hours long, and it is meant to be: that is how long the day was where the
reader lives.

Which files to open is decided from their modification times, so a day in a
fourteen-day backfill opens two or three files rather than all fourteen. The
filter on each hit's own timestamp is what makes the answer exact; the file
choice only decides how much has to be read to find it.
"""
from __future__ import annotations

import os
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Iterable, Iterator
from zoneinfo import ZoneInfo

from .aggregate import Totals, summarise_views
from .classify import Classifier, crawler_visits
from .config import setting
from .parse import (HOLD, Hit, Lateness, ReadStats, geo_database, in_time_order, log_files,
                    oldest_first, read, sizes)

# A line can land in the file after the one its timestamp belongs to: the
# server buffers writes, and reopens its log some time after the rename. Six
# hours is far more than either, and costs at most one extra file read.
ROTATION_SLACK = timedelta(hours=6)

# History keeps longer lists than a mail card shows, so a 30-day table can
# sum them. The cards still show their own top few.
HISTORY_TOP = 50


def zone(config: dict) -> ZoneInfo:
    """The reader's timezone, from `report.timezone`. UTC when unset."""
    return ZoneInfo(str(setting(config, "report", "timezone", "UTC")))


def today(tz: ZoneInfo, now: datetime | None = None) -> date:
    return (now or datetime.now(timezone.utc)).astimezone(tz).date()


def yesterday(tz: ZoneInfo, now: datetime | None = None) -> date:
    return today(tz, now) - timedelta(days=1)


def day_window(day: date, tz: ZoneInfo) -> tuple[datetime, datetime]:
    """[local midnight, next local midnight), as aware UTC datetimes."""
    return range_window(day, day, tz)


def range_window(first: date, last: date, tz: ZoneInfo) -> tuple[datetime, datetime]:
    """From the start of `first` to the end of `last`, both local days."""
    start = datetime.combine(first, time(0), tzinfo=tz)
    end = datetime.combine(last + timedelta(days=1), time(0), tzinfo=tz)
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)


def parse_day(text: str, tz: ZoneInfo, now: datetime | None = None) -> date:
    """"yesterday", "today" or YYYY-MM-DD."""
    if text == "yesterday":
        return yesterday(tz, now)
    if text == "today":
        return today(tz, now)
    return date.fromisoformat(text)


def files_for(paths: list[Path], start: datetime, end: datetime) -> list[Path]:
    """The rotations that can hold a line between `start` and `end`.

    `paths` is newest first, as parse.log_files returns them. A file's
    modification time is when its last line was written, and the file one
    rotation older stopped being written when this one started. So file k
    covers roughly (mtime of k+1, mtime of k], and is needed when that span
    meets the window. Anything unreadable by stat is kept: reading too much
    is slow, reading too little is wrong.
    """
    def mtime(p: Path) -> datetime | None:
        try:
            return datetime.fromtimestamp(os.stat(p).st_mtime, tz=timezone.utc)
        except OSError:
            return None

    times = [mtime(p) for p in paths]
    chosen = []
    for k, path in enumerate(paths):
        newest = times[k]
        older = times[k + 1] if k + 1 < len(times) else None
        if newest is not None and newest < start:
            continue
        if older is not None and older - ROTATION_SLACK >= end:
            continue
        chosen.append(path)
    return chosen


def within(hits: Iterable[Hit], start: datetime, end: datetime) -> Iterator[Hit]:
    """Only the hits in [start, end). A timestamp with no offset is UTC."""
    for hit in hits:
        when = hit.when if hit.when.tzinfo else hit.when.replace(tzinfo=timezone.utc)
        if start <= when < end:
            yield hit


def window_paths(config: dict, start: datetime, end: datetime,
                 now: datetime | None = None) -> list[Path]:
    """Every rotation the window could need, from `logs.dir` and `logs.base`.

    How far back to look is worked out from the window rather than from
    `logs.days`, so asking for a day ten days ago reads the rotations that
    hold it whatever `days` is set to for the glance report.
    """
    logs = config.get("logs") or {}
    age = (now or datetime.now(timezone.utc)) - start
    reach = max(2, age.days + 3)
    paths = log_files(Path(logs.get("dir") or "/var/log/nginx"),
                      logs.get("base") or "access.log", reach)
    return files_for(paths, start, end)


def plain_sizes(config: dict) -> dict[str, int]:
    """The live log and its first rotation (the files still written to),
    each one's size in bytes now: what a live run reads up to (parse.sizes)."""
    logs = config.get("logs") or {}
    return sizes(log_files(Path(logs.get("dir") or "/var/log/nginx"),
                           logs.get("base") or "access.log", 2))


def analyse_window(config: dict, start: datetime, end: datetime,
                   paths: list[Path] | None = None,
                   now: datetime | None = None, top: int = HISTORY_TOP,
                   observe=None) -> Totals:
    """Totals for exactly [start, end). `parsed` counts hits in the window.

    So a window with no lines in it fails verify's "nothing parsed" check,
    which is the point: a day missing from the logs must not be stored or
    mailed as a calm row of zeroes.
    """
    return analyse_window_views(config, start, end, paths, now, top, observe)[0]


def analyse_window_views(config: dict, start: datetime, end: datetime,
                         paths: list[Path] | None = None,
                         now: datetime | None = None, top: int = HISTORY_TOP,
                         observe=None, views=None,
                         upto: dict | None = None) -> tuple[Totals, dict]:
    """The whole site and each config.View, in one pass over the window.
    `upto` reads each plain file only that far (parse.read): a live run."""
    logs = config.get("logs") or {}
    # Files named by the caller are read whole: they were chosen on purpose,
    # and their modification times say nothing about rotation order.
    if paths is None:
        paths = window_paths(config, start, end, now)
    paths = oldest_first(paths)
    tests = {v.slug: (lambda hit, v=v: v.matches(hit.path)) for v in (views or [])}
    fmt = logs.get("format") or "auto"
    classifier, hold = ordered_classifier(
        config, lambda: within(read(paths, fmt, upto=upto), start, end), start, end)
    stats = ReadStats()
    edges = _Edges()
    whole, by_view = summarise_views(
        edges.watch(in_time_order(
            within(read(paths, fmt, stats, geo_database(config), upto), start, end), hold)),
        classifier,
        int(setting(config, "report", "session_gap_minutes", 30)),
        top=top,
        hosts=setting(config, "site", "hosts"),
        observe=observe,
        views=tests,
        tz=zone(config),
        options=options(config, start.astimezone(zone(config)).date()),
    )
    gap = timedelta(minutes=int(setting(config, "report", "coverage_gap_minutes", 60)))
    _mark_partial(whole, start, end, now, edges, gap)
    # The unreadable share belongs to this window, not to the files: a quiet
    # day's junk must not be diluted by a busy neighbour sharing its file.
    placed = stats.in_window(start, end)
    # A line dropped as a repeated request id is still a line in the window.
    removed = stats.removed_in(start, end)
    stats.lines, stats.unparsed = whole.parsed + placed + removed, placed
    whole.lines_scope = "in the window"
    if whole.extras and "quality" in whole.extras:
        whole.extras["quality"].update(lines=stats.lines, unparsed=stats.unparsed,
                                       duplicates_removed=removed,
                                       files=[p.name for p in paths])
    for totals in by_view.values():
        totals.partial_from, totals.partial_until = whole.partial_from, whole.partial_until
    return _with_read_stats(config, whole, stats), by_view


class _Edges:
    """The first and last line in the window, whatever host they were for:
    they show when the logs were being written, which is what coverage is."""

    def __init__(self) -> None:
        self.first = None
        self.last = None

    def watch(self, hits):
        for hit in hits:
            when = hit.when if hit.when.tzinfo else hit.when.replace(tzinfo=timezone.utc)
            if self.first is None or when < self.first:
                self.first = when
            if self.last is None or when > self.last:
                self.last = when
            yield hit


def _mark_partial(totals: Totals, start: datetime, end: datetime,
                  now: datetime | None, edges: _Edges, gap: timedelta) -> None:
    """Say so when the window's own lines do not cover it.

    Whole means the first line is within `gap` of the window's start and the
    last within `gap` of its end - judged on the lines themselves. An older
    file written before midnight proves nothing about a hole after it, and
    took a three-day hole for a whole day. A log that starts exactly at
    midnight is whole. A quiet site that is genuinely silent for longer than
    the gap at either end of the day should raise report.coverage_gap_minutes.
    """
    if edges.first is None:
        return
    if edges.first - start > gap:
        totals.partial_from = edges.first
    now = now or datetime.now(timezone.utc)
    if now < end:
        totals.partial_until = now
    elif end - edges.last > gap:
        totals.partial_until = edges.last


def analyse_paths(config: dict, paths: list[Path], top: int = 8,
                  fmt: str | None = None) -> Totals:
    """Totals for whole files - the glance report's --days and --log modes.

    Same classifier, same host filter, same session gap as the exact-window
    path; only the time filter is absent.
    """
    logs = config.get("logs") or {}
    paths = oldest_first(paths)
    fmt = fmt or logs.get("format") or "auto"
    classifier, hold = ordered_classifier(config, lambda: read(paths, fmt))
    stats = ReadStats()
    totals = summarise_views(
        in_time_order(read(paths, fmt, stats, geo_database(config)), hold),
        classifier,
        int(setting(config, "report", "session_gap_minutes", 30)),
        top=top,
        hosts=setting(config, "site", "hosts"),
        tz=zone(config),
    )[0]
    return _with_read_stats(config, totals, stats)


def options(config: dict, day: date | None = None) -> dict:
    """What a tally needs beyond the session gap: the visitor key (for
    returning visitors), the label of our own heartbeat, and the saved
    funnels to count on `day` (funnel_days.wanted)."""
    from .ai_likely import settings as attribution
    from .conversions.geo import cities
    from .funnel_days import wanted
    from .sitemap import for_day
    from .visitors import load_key
    return {"visitor_key": load_key(config), "attribution": attribution(config),
            "heartbeat": str(setting(config, "report", "heartbeat_label", "heartbeat")),
            "funnels": wanted(config, day, zone(config)),
            # the site's sitemap paths kept for `day` (crawl_health.py)
            "sitemap": for_day(config, day),
            # logs.city_db: one fill (one lookup per address) for every tally.
            "cities": cities(config)}


def ordered_classifier(config: dict, lines, start: datetime | None = None,
                       end: datetime | None = None) -> tuple[Classifier, object]:
    """(the classifier, the hold that reads these lines in time order).

    Both passes read the lines in timestamp order, ties in file order
    (parse.in_time_order; CLASSIFICATION.md, "Line order"). `lines()` is a
    fresh read of them. The first pass learns how far out of order they
    are; only when a line was further behind than parse.HOLD, so that pass
    was not wholly in order, is it read again holding back that far. The
    count's own pass is then given that hold, and is exact.
    """
    seen = Lateness()
    classifier = _classifier(config, in_time_order(lines(), HOLD, seen), start, end)
    if seen.inverted:
        classifier = _classifier(config, in_time_order(lines(), seen.hold()), start, end)
    return classifier, seen.hold()


def _classifier(config: dict, first_pass, start: datetime | None = None,
                end: datetime | None = None) -> Classifier:
    """The config's classifier, told which sessions are crawlers and which
    browser-like visits never rendered a page (rendering.py).

    That takes a pass of its own: a crawler may fetch robots.txt after the
    pages, and a page's assets come after it, so every one of its requests
    is judged on the whole visit. Parsing is cheap next to classifying, so
    the window is simply read twice. `start` and `end` name the window, for
    the beacon's page openings and the readers of the days before it.
    """
    from . import rendering, too_fast
    from .classify import FanOut
    classifier = Classifier.from_config(config)
    gap = int(setting(config, "report", "session_gap_minutes", 30))
    hosts = setting(config, "site", "hosts")
    fan = FanOut()
    drawn = None
    if rendering.required(config):
        opens, returning = [], None
        if start is not None and end is not None:
            from .visitors import load_key
            opens = rendering.beacon_opens(config, start, end)
            returning = rendering.earlier_readers(
                config, start.astimezone(zone(config)).date(), load_key(config))
        drawn = rendering.Rendering(hosts, gap, rendering.asset_prefixes(config),
                                    rendering.render_seconds(config), opens, returning)

    pages, seconds = too_fast.limits(config)
    fast = too_fast.TooFast(hosts, gap, pages, seconds) if pages else None

    def also(hit) -> None:
        fan(hit)
        if drawn is not None:
            drawn(hit)
        if fast is not None:
            fast(hit)

    classifier.crawler_visits = crawler_visits(first_pass, gap, hosts, also=also)
    classifier.fan_out = fan.pairs()
    if drawn is not None:
        classifier.unrendered = drawn.unrendered()
        classifier.rendering = drawn.counts
    if fast is not None:
        classifier.too_fast = fast.spans()
    return classifier


def _with_read_stats(config: dict, totals: Totals, stats: ReadStats) -> Totals:
    """Attach what the reader saw, and the configured tolerance for it.

    Views do not get it: an unreadable line has no path either, and the
    site's own check already fails the day.
    """
    totals.lines_read, totals.unparsed = stats.lines, stats.unparsed
    totals.max_unparsed_share = float(
        setting(config, "report", "max_unparsed_percent", 1)) / 100
    return totals
