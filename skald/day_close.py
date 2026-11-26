"""Yesterday stored soon after midnight: `skald close-day` (SKALD-61, 2026-11-26).

Until 2.58 a day was stored only by run-daily, at 07:15 in the site's zone, so
from midnight to about 08:15 yesterday was "not collected" on every site:
Yesterday showed nothing, and 7, 30 and 90 days each lost their last day and
their comparison. From India that is most of the working day.

close-day runs the same check, collect and audit as run-daily, for yesterday
only, then redraws the dashboard: nothing else (no mail, no recounts beside
the log's, no network). The scheduler runs it at SKALD_CLOSE_AT (00:20). The
morning run is unchanged: it counts yesterday again from the log, which by
then also holds any line a remote sender delivered late, and that count is
the one kept. A day that does not reconcile at 00:20 is withheld, as it would
be at 07:15, and counted again at 07:15.

A day already stored whole and verified is left alone (a restart, or a
collect someone ran by hand): close-day never counts a day a second time.

Just after midnight is when a remote sender's late lines for yesterday still
arrive (a retry after a refusal, a batch). One landing between the collect and
its audit makes the audit's recount higher, and the day would be withheld until
the morning. So an audit that does not match is followed by one more count of
the whole day (check, collect, audit), which then reads the late lines on both
roads; only a second mismatch leaves the day withheld. Until the morning run
has run, a withheld or missing yesterday is not a set-up problem (doctor) and a
client report waits for the morning's count (client_reports_send).
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Callable

from . import runs

# run-daily's steps that close-day runs too, in run-daily's order (cli.daily_steps).
CLOSE_STEPS = ("check", "collect", "audit", "events", "dashboard")


def close_steps(ctx) -> list[tuple[str, Callable[[], int]]]:
    """close-day's steps for yesterday: run-daily's check, collect and audit, the
    in-page events and the dashboard; nothing that mails, fetches or recounts
    beside the log. A site waiting for its first line runs check and dashboard only."""
    from . import cli, events
    from .window import yesterday
    day = yesterday(ctx.tz, ctx.now)
    steps = core_steps(ctx, day)
    if events.enabled(ctx.config):
        steps.append(("events", lambda: events.daily(ctx, day)))
    steps.append(("dashboard", lambda: cli.cmd_dashboard(ctx)))
    return [(name, step) if name in cli.WHILE_WAITING else (name, cli._unless_waiting(ctx, step))
            for name, step in steps]


def morning_ran(live_dir, now: datetime, tz) -> bool:
    """True once run-daily has ended (ok or failed) since local midnight: until
    then yesterday's stored count may be close-day's, which the morning recounts."""
    if live_dir is None:
        return True
    got = runs.load(Path(live_dir)).get("run-daily") or {}
    midnight = datetime.combine(now.astimezone(tz).date(), datetime.min.time(), tzinfo=tz)
    for key in ("last_ok", "last_fail"):
        try:
            when = datetime.fromisoformat(str(got.get(key)))
        except ValueError:
            continue
        if when.tzinfo is not None and when >= midnight:
            return True
    return False


def core_steps(ctx, day) -> list[tuple[str, Callable[[], int]]]:
    """check, collect and audit one day: run-daily's own three steps, shared
    with close-day so the two can never count a day differently."""
    from . import cli
    held: dict[str, tuple] = {}

    def do_check() -> int:
        from .multisite import WAITING, waiting
        held["figures"] = figures = ctx.analyse(day)
        if waiting(ctx.config, ctx.db_path, figures[0].lines_read):
            ctx.waiting = True
            ctx.out(f"{ctx.site}: {WAITING}; nothing to collect for {day}, "
                    "nothing stored or mailed")
            return 0
        found = ctx.problems(figures)
        if found:
            cli._report_all(ctx, day, found)
            # Figures that do not reconcile are held back by design; no log
            # line at all for the day is a failure (logging or format broke).
            if not any(p.what == "nothing parsed" for _, ps in found for p in ps):
                ctx.by_design = "the figures do not reconcile"
            return 1
        ctx.out(f"check ok: {cli._describe(day, figures[0])}")
        return 0

    def do_collect() -> int:
        with ctx.history() as history:
            got = cli.collect_day(ctx, history, day, figures=held["figures"])
        from .retention import after_collect  # the cohorts (audit_retention recounts)
        after_collect(ctx)
        return 0 if got == "ok" else 1

    def do_audit() -> int:
        code = cli.audit_day(ctx, day, withhold=True)
        if code == 1:                   # the recount disagrees: withheld
            ctx.by_design = "the audit's recount does not match; the day is withheld"
        return code

    return [("check", do_check), ("collect", do_collect), ("audit", do_audit)]


def stored_whole(ctx, day) -> bool:
    """True when the day is stored, verified and whole (not partial)."""
    with ctx.history() as history:
        row = history.db.execute(
            "SELECT verified, partial_from, partial_until FROM days WHERE site = ? AND day = ?",
            (ctx.site, day.isoformat())).fetchone()
    return bool(row and row[0] and not (row[1] or row[2]))


def cmd_close_day(ctx) -> int:
    """Store yesterday now, as run-daily would; runs.json `close-day` says how it went."""
    from .run_steps import run_steps
    from .window import yesterday
    day = yesterday(ctx.tz, ctx.now)
    if stored_whole(ctx, day):
        ctx.out(f"{ctx.site}: {day} is stored, whole and verified already; nothing to close")
        runs.record(ctx.live_dir, "close-day", 0, outcome="ok")
        return 0
    ctx.by_design, ctx.waiting, ctx.recounts = None, False, None
    stopped: list[str] = []
    try:
        code = run_steps(close_steps(ctx), ctx.err, stopped)
        if code == 1 and stopped == ["audit"]:
            # Late lines may have landed between the collect and its audit: count the
            # whole day once more, so both roads read them.
            ctx.out(f"{ctx.site}: {day}: the audit did not match; lines may still be "
                    "arriving, so the day is counted once more")
            ctx.by_design, stopped = None, []
            code = run_steps(close_steps(ctx), ctx.err, stopped)
    except BaseException as why:
        runs.record(ctx.live_dir, "close-day", 1, outcome="failed",
                    step=stopped[0] if stopped else None, reason=f"{type(why).__name__}: {why}")
        raise
    outcome = "ok" if code == 0 else "withheld" if code == 1 and ctx.by_design else "failed"
    if code == 0 and ctx.waiting:
        outcome = "waiting"
    runs.record(ctx.live_dir, "close-day", code, outcome=outcome,
                step=stopped[0] if code and stopped else None,
                reason=ctx.by_design if code else None)
    if code == 0 and not ctx.waiting:
        ctx.out(f"{ctx.site}: {day} closed; run-daily counts it again in the morning")
    return code


def add_command(sub) -> None:
    p = sub.add_parser("close-day", help="store yesterday now (check, collect, audit, "
                       "dashboard); the scheduler runs it soon after midnight")
    p.set_defaults(run=cmd_close_day)
