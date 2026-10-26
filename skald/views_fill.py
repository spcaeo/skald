"""Filling past days for page groups (views), from the raw log.

A view saved in Settings > Site details > Views is counted from the next run on. Its
past days stay empty ("not recorded for this group") until they are counted
again from the raw log, which holds only the last days the server keeps
(logrotate's 14 on a Debian or Ubuntu default). This module does that:

  reach(config, tz, now)     which whole days the raw log still holds: from the
                             oldest line of the oldest rotation to yesterday
  changed(old, new)          which views a save added or changed (their rule),
                             and which it removed
  run(ctx, days, slugs)      the job: each day the log holds, oldest first,
                             counted once (the same pass and rules as collect),
                             each chosen view's day stored with its own check,
                             then recounted by the audit's own road
                             (audit_views.py); a day that does not match is
                             withheld, never shown. The site's own days are
                             left as they are. Then the dashboard is drawn.

The job runs as `skald --site S views refresh [--days N] [--view SLUG ...]`
(cli_views.py), from the shell or started by the page (views_fill_api.py),
which runs it in the background. One at a time per install: the job holds
`views-fill.lock` (an flock beside the history) and writes its progress to
`views-fill.json` there:

  state        queued | running | done | failed
  site, views  the site, [{slug, name}]
  days, done   how many days, how many counted so far
  first, last  the days (YYYY-MM-DD), oldest and newest
  filled, withheld, empty   per day: stored and audited / withheld / no line
  current      the day being counted
  by, started_at, finished_at, error, kept_days, before
"""
from __future__ import annotations

import fcntl
import json
import os
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from .files import write_atomic

STATE, LOCK = "views-fill.json", "views-fill.lock"
SAMPLE = 2000          # lines read from the oldest rotation to find its oldest line
REACH_FILES = 400      # rotations looked for (base.1 ... base.399.gz)


class Busy(RuntimeError):
    """Another fill holds the lock."""


# ------------------------------------------------------------------ state

def load(folder) -> dict:
    try:
        got = json.loads((Path(folder) / STATE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return got if isinstance(got, dict) else {}


def save(folder, fresh: bool = False, **fields) -> dict:
    got = {} if fresh else load(folder)
    got.update(fields)
    write_atomic(Path(folder) / STATE, json.dumps(got, indent=1, sort_keys=True) + "\n")
    return got


def now_text(now: datetime | None = None) -> str:
    return (now or datetime.now(timezone.utc)).astimezone(timezone.utc) \
        .isoformat(timespec="seconds")


@contextmanager
def lock(folder):
    """The install's fill lock, or Busy at once."""
    path = Path(folder) / LOCK
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise Busy("a fill is already running") from None
        yield
    finally:
        os.close(fd)


@contextmanager
def guard(folder):
    """A short lock around reading and writing the state (two presses at once)."""
    path = Path(folder) / (LOCK + "-state")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        os.close(fd)


def busy(folder) -> bool:
    try:
        with lock(folder):
            return False
    except Busy:
        return True
    except OSError:
        return False


# ------------------------------------------------------------------ reach

def reach(config: dict, tz, now: datetime | None = None) -> dict:
    """The whole days the raw log still holds, up to yesterday:
    {days, first, last, kept_days, oldest_line}. A day is whole when the
    oldest line is within report.coverage_gap_minutes (60) of its midnight,
    as a stored day is judged (window._mark_partial). No log: days 0."""
    from .parse import log_files, read
    from .config import setting
    now = (now or datetime.now(timezone.utc)).astimezone(tz)
    logs = config.get("logs") or {}
    files = log_files(Path(str(logs.get("dir") or "/var/log/nginx")),
                      str(logs.get("base") or "access.log"), REACH_FILES)
    last = now.date() - timedelta(days=1)
    empty = {"days": 0, "first": None, "last": last.isoformat(), "kept_days": 0,
             "oldest_line": None}
    oldest = None
    for path in reversed(files):            # the oldest rotation first
        try:
            for n, hit in enumerate(read([path], str(logs.get("format") or "auto"))):
                when = hit.when if hit.when.tzinfo else hit.when.replace(tzinfo=timezone.utc)
                oldest = when if oldest is None or when < oldest else oldest
                if n >= SAMPLE:
                    break
        except (OSError, EOFError, ValueError):
            continue
        if oldest is not None:
            break
    if oldest is None:
        return empty
    local = oldest.astimezone(tz)
    gap = timedelta(minutes=int(setting(config, "report", "coverage_gap_minutes", 60)))
    midnight = datetime.combine(local.date(), datetime.min.time(), tzinfo=tz)
    first = local.date() if local - midnight <= gap else local.date() + timedelta(days=1)
    days = max(0, (last - first).days + 1)
    return {"days": days, "first": first.isoformat() if days else None,
            "last": last.isoformat(), "kept_days": (now.date() - local.date()).days + 1,
            "oldest_line": local.date().isoformat()}


# ---------------------------------------------------------------- changes

def _rule(item: dict) -> tuple:
    exclude = item.get("exclude_prefix") or ""
    if isinstance(exclude, list):
        exclude = " ".join(str(x) for x in exclude)
    return (str(item.get("path_prefix") or ""), tuple(sorted(str(exclude).split())))


def changed(old, new) -> tuple[list[dict], list[dict]]:
    """([{slug, name}] added or with a new rule, [{slug, name}] removed),
    by the folder each view is kept in (its slug): a renamed view is a new
    one, its old folder a removed one."""
    from .config import View

    def by_slug(items):
        out = {}
        for item in items or []:
            if isinstance(item, dict) and item.get("name"):
                out[View(str(item["name"])).slug] = item
        return out
    was, now = by_slug(old), by_slug(new)
    added = [{"slug": s, "name": str(v["name"])} for s, v in now.items()
             if s not in was or _rule(was[s]) != _rule(v)]
    gone = [{"slug": s, "name": str(v["name"])} for s, v in was.items() if s not in now]
    return added, gone


# -------------------------------------------------------------------- job

def fill_day(ctx, history, day: date, chosen: list) -> str:
    """Count `day` once and store each chosen view's day, with its own check
    (cli.collect_day's view part). 'ok', 'withheld' or 'empty'."""
    from .store import view_key
    from .visitors import annotate, repeat_days
    figures = ctx.analyse(day)
    totals, by_view = figures
    if totals.parsed == 0:
        return "empty"
    found = dict(ctx.problems(figures))
    held = False
    for view in chosen:
        t = by_view[view.slug]
        annotate(t, history.db, ctx.site, day, repeat_days(ctx.config))
        problems = found.get(f"view {view.name}", [])
        history.record(view_key(ctx.site, view.slug), day, t, str(ctx.tz), problems,
                       scope=view.describe())
        held = held or bool(problems)
    return "withheld" if held else "ok"


def audit_day(ctx, history, day: date, chosen: list) -> list[str]:
    """The audit's road (audit_views.py) over the chosen views' stored day; a
    view that does not match is withheld. The mismatches, in words."""
    from . import audit_views
    from .config import setting
    from .store import view_key
    raw = [v for v in (setting(ctx.config, "dashboard", "views") or [])
           if any(c.name == str(v.get("name")) for c in chosen)]
    figures = audit_views.recount(ctx.config, day, ctx.tz, raw)
    out = []
    for view in chosen:
        problems = audit_views.compare({view.slug: figures[view.slug]}, history, ctx.site,
                                       day)[view.slug]
        if problems and history.status(view_key(ctx.site, view.slug), day) is not None:
            history.withhold(view_key(ctx.site, view.slug), day,
                             [f"audit: {p}" for p in problems])
        out += [f"{view.name}: {p}" for p in problems]
    return out


def run(ctx, days: int, slugs: list[str] | None, by: str = "", folder=None) -> int:
    """The fill. 0 every day filled and audited; 1 a day withheld or nothing
    to fill; 2 a bad view name; 3 another fill is running."""
    from . import markers
    from .window import yesterday
    folder = Path(folder or ctx.db_path.parent)
    chosen = [v for v in ctx.views if not slugs or v.slug in slugs]
    unknown = sorted(set(slugs or []) - {v.slug for v in ctx.views})
    if unknown or not chosen:
        ctx.err(f"views refresh: no view {', '.join(unknown) or 'at all'} for {ctx.site}")
        return 2
    last = yesterday(ctx.tz, ctx.now)
    wanted = [last - timedelta(days=i) for i in range(days - 1, -1, -1)]
    try:
        with lock(folder):
            return _run(ctx, folder, chosen, wanted, by, markers)
    except Busy:
        ctx.err("views refresh: another fill is running on this install; try again "
                "when it ends")
        return 3


def _run(ctx, folder: Path, chosen, wanted, by, markers) -> int:
    got = reach(ctx.config, ctx.tz, ctx.now)
    base = {"site": ctx.site, "views": [{"slug": v.slug, "name": v.name} for v in chosen],
            "days": len(wanted), "done": 0, "filled": 0, "withheld": 0, "empty": 0,
            "first": wanted[0].isoformat() if wanted else None,
            "last": wanted[-1].isoformat() if wanted else None, "current": None,
            "by": by, "started_at": now_text(), "finished_at": None, "error": None,
            "kept_days": got["kept_days"], "before": got["first"], "problems": []}
    save(folder, fresh=True, state="running", **base)
    tally = {"ok": 0, "withheld": 0, "empty": 0}
    problems: list[str] = []
    try:
        with ctx.history() as history:
            for n, day in enumerate(wanted):
                save(folder, current=day.isoformat())
                result = fill_day(ctx, history, day, chosen)
                if result != "empty":
                    found = audit_day(ctx, history, day, chosen)
                    if found:
                        result = "withheld"
                        problems += [f"{day}: {p}" for p in found]
                tally[result] += 1
                ctx.out(f"{day}: {result}")
                save(folder, done=n + 1, filled=tally["ok"], withheld=tally["withheld"],
                     empty=tally["empty"], problems=problems[:20])
        from .cli import cmd_dashboard
        cmd_dashboard(ctx)
    except Exception as why:          # noqa: BLE001 - said in the state, then raised
        save(folder, state="failed", finished_at=now_text(), current=None,
             error=f"{type(why).__name__}: {str(why)[:200]}")
        raise
    words = (f"{tally['ok']} filled and audited, {tally['withheld']} withheld, "
             f"{tally['empty']} with no line in the log")
    save(folder, state="done", finished_at=now_text(), current=None)
    markers.append(ctx.live_dir, "backfill",
                   f"views refresh {len(wanted)} days: " + ", ".join(v.name for v in chosen),
                   "page groups recounted from the logs: " + words)
    ctx.out(f"views refresh: {words}")
    for p in problems:
        ctx.err(f"  withheld: {p}")
    return 0 if wanted and not tally["withheld"] and tally["ok"] else 1
