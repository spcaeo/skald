"""The system commands: collect history, render the dashboard, send mail.

    skald check      [--day yesterday|YYYY-MM-DD]
    skald collect    [--day yesterday|YYYY-MM-DD] [--log PATH ...]
    skald backfill   --days N [--force]
    skald dashboard  [--out DIR]
    skald mail       --daily|--weekly [--dry-run] [--save-html PATH]
    skald run-daily  [--dry-run]
    skald live       [--out DIR]
    skald export     [--from D --to D] [--table T] [filters] [--format csv|json]
    skald audit      [--day yesterday|YYYY-MM-DD] [--log PATH ...] [--withhold]

run-daily is the cron entry: check, collect yesterday, audit it (an
independent recount from the raw log; then the second counts beside it,
audit_more.py, which never stop the run), render the dashboard,
send the daily mail, and on Mondays the weekly one. Each step runs only if the
one before it succeeded, so a day that does not add up is never stored, drawn
or mailed. Exit status: 0 done, 1 refused (figures or mail), 2 misconfigured.
It notes in runs.json whether a stop was by design (a withheld day) or a
failure; cron then sends one failure mail for a failure only (failmail.py).

live is the near-real-time entry, safe every two minutes: today so far, into
a snapshot file beside the history and the dashboard's "Today so far" panel.
It never writes the history and never mails (see live.py).

Relative paths in the config (history.db, dashboard.out) are taken relative
to the config file, so cron does not need a particular working directory.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Callable

from . import dashboard, export, live, mailer, runs
from .aggregate import Totals
from .config import country_credit, load_config, setting, site_name, views
from .store import History, view_key
from .store_visits import journey_days
from .verify import check
from .window import analyse_window_views, day_window, parse_day, yesterday, zone


def _now(args, tz) -> datetime:
    """Now, or noon on --today in the configured zone (for tests and replays)."""
    if getattr(args, "today", None):
        return datetime.combine(date.fromisoformat(args.today), time(12), tzinfo=tz)
    return datetime.now(timezone.utc).astimezone(tz)


def _path(config: dict, config_path: Path, section: str, key: str,
          default: str | None) -> Path | None:
    raw = setting(config, section, key, default)
    if raw is None:
        return None
    p = Path(str(raw)).expanduser()
    return p if p.is_absolute() else config_path.resolve().parent / p


class Context:
    """Everything a command needs, worked out once from the arguments."""

    def __init__(self, args, config: dict | None = None, live_dir: Path | None = None) -> None:
        self.args = args
        self.config_path = Path(args.config)
        if not self.config_path.exists():
            raise SystemExit(f"config not found: {self.config_path}")
        # Another site of a multi-site install (multisite.py): its merged
        # config and its own folder for live snapshots and state.
        self.raw_config = config if config is not None else load_config(self.config_path)
        self.site = site_name(self.raw_config)
        self.db_path = _path(self.raw_config, self.config_path, "history", "db",
                             "history.sqlite")
        # Settings changed in the dashboard (accounts.sqlite beside the
        # history) laid over config.yml: retention, mail, hosts, time zone.
        # Without an accounts file this is the config as read.
        from . import settings_store
        self.config = settings_store.apply(self.raw_config, self.site, self.db_path.parent)
        self.tz = zone(self.config)
        self.now = _now(args, self.tz)
        # Live snapshots sit beside the history file, never inside it.
        self.live_dir = live_dir if live_dir is not None else self.db_path.parent
        # The history file and the beacon spool, resolved against the config's
        # folder, for code that has only the config: the first pass that asks
        # whether a visit rendered (rendering.py) and the audit's recount.
        from .beacon import spool_dir
        self.config["_resolved"] = {
            "history_db": str(self.db_path),
            "beacon_spool": str(spool_dir(self.config, self.config_path, self.live_dir)),
            # Where funnels.json is saved (funnel_days.py and its recount).
            "live_dir": str(self.live_dir)}
        # Every site's config (multi-site); this one alone otherwise.
        self.all_configs = [self.config]
        try:
            self.views = views(self.config)
        except ValueError as why:
            raise SystemExit(str(why))
        self.out = print
        self.err = lambda *a: print(*a, file=sys.stderr)
        # Why a step stopped run-daily by design (a day that does not
        # reconcile), set by that step; None for any other stop.
        self.by_design: str | None = None
        # A dashboard site with no log line yet (multisite.waiting): set by
        # run-daily's check; the steps that need a day are then skipped.
        self.waiting = False

    def history(self) -> History:
        return History(self.db_path)

    def analyse(self, day: date, logs: list[str] | None = None) -> tuple[Totals, dict]:
        """The day for the whole site, and for each configured view."""
        start, end = day_window(day, self.tz)
        return analyse_window_views(
            self.config, start, end,
            paths=[Path(p) for p in logs] if logs else None,
            now=self.now, views=self.views)

    def problems(self, figures: tuple[Totals, dict]) -> list[tuple[str, list]]:
        """(label, problems) for the site and every view that has any.

        A view with no lines on a day the site had lines is a true zero -
        nobody asked for those paths - not a parse failure, so verify's
        "nothing parsed" does not apply to it. Every other check does.
        """
        totals, by_view = figures
        found = []
        if check(totals):
            found.append(("site", check(totals)))
        for view in self.views:
            got = [p for p in check(by_view[view.slug])
                   if not (p.what == "nothing parsed" and totals.parsed)]
            if got:
                found.append((f"view {view.name}", got))
        return found


def _describe(day: date, totals: Totals) -> str:
    return (f"{day}: {totals.hits:,} requests for this site "
            f"({totals.parsed:,} in the window, {totals.other_hosts:,} other hosts; "
            f"{totals.unparsed:,} of {totals.lines_read:,} lines {totals.lines_scope} "
            f"unreadable)")


def _report_problems(ctx: Context, day: date, problems, label: str = "") -> None:
    ctx.err(f"{day}: FIGURES DO NOT RECONCILE" + (f" ({label})" if label else ""))
    for p in problems:
        ctx.err(f"  - {p}")


def _report_all(ctx: Context, day: date, found: list[tuple[str, list]]) -> None:
    for label, problems in found:
        _report_problems(ctx, day, problems, "" if label == "site" else label)


# ----------------------------------------------------------------- commands

def cmd_check(ctx: Context) -> int:
    day = parse_day(ctx.args.day, ctx.tz, ctx.now)
    figures = ctx.analyse(day, ctx.args.log)
    found = ctx.problems(figures)
    if found:
        _report_all(ctx, day, found)
        return 1
    ctx.out(f"ok: {_describe(day, figures[0])}; every category reconciles"
            + (f", in all {len(ctx.views)} views too" if ctx.views else ""))
    return 0


def prune_kept(ctx: Context, history: History) -> None:
    """Delete what is kept only for a while; a keep-everything site nothing (prune.py)."""
    from .prune import prune_kept as run
    run(ctx, history)


def collect_day(ctx: Context, history: History, day: date,
                logs: list[str] | None = None,
                figures: tuple[Totals, dict] | None = None) -> str:
    """Analyse and store one day. Returns 'ok', 'withheld' or 'empty'.

    A day with lines that fails verify is stored as withheld, figures kept
    for whoever investigates, never shown. A day with no lines at all is not
    stored: it is outside the logs' retention, or the format is wrong, and
    either way a row of zeroes would be a lie.

    Each configured view is stored beside the site, under its own key, with
    its own verify result: a view that does not reconcile is withheld on its
    own page without taking the site down with it. A day before the site's
    last Clear data (site_lifecycle.before_clear) is never stored again.
    """
    from .site_lifecycle import before_clear
    if before_clear(ctx.config, ctx.db_path.parent, ctx.site, day):
        ctx.err(f"{day}: before this site's data was cleared; nothing stored")
        return "empty"
    prune_kept(ctx, history)
    if figures is None:
        figures = ctx.analyse(day, logs)
    totals, by_view = figures
    if totals.parsed == 0:
        ctx.err(f"{day}: no log lines in this day's window; nothing stored")
        return "empty"
    found = dict(ctx.problems(figures))
    # Returning visitors: each visit's keyed hash against the 30 days before.
    from .visitors import annotate, repeat_days
    for t in [totals, *by_view.values()]:
        annotate(t, history.db, ctx.site, day, repeat_days(ctx.config))
    from .people.visits import keep_day            # each visit with its address (2.4.0)
    keep_day(ctx, day, totals)                     # before first touch: the day's own visits
    from .firsttouch import annotate as first_touch, day_end
    first_touch(totals, ctx.config, Path(ctx.db_path).parent, ctx.site, day, ctx.tz,
                day_end(day, ctx.tz), history.db)
    history.record(ctx.site, day, totals, str(ctx.tz), found.get("site", []))
    for view in ctx.views:
        history.record(view_key(ctx.site, view.slug), day, by_view[view.slug],
                       str(ctx.tz), found.get(f"view {view.name}", []),
                       scope=view.describe())
    if found:
        _report_all(ctx, day, list(found.items()))
        ctx.err("  stored as withheld; it will not be shown or mailed")
        return "withheld"
    if totals.partial:
        bits = []
        if totals.partial_from:
            bits.append(f"data from {totals.partial_from.astimezone(ctx.tz):%H:%M}")
        if totals.partial_until:
            bits.append(f"data until {totals.partial_until.astimezone(ctx.tz):%H:%M}")
        ctx.out(f"  stored as a PARTIAL day ({', '.join(bits)}): shown labelled, "
                f"left out of every comparison")
    ctx.out(f"stored {_describe(day, totals)}"
            + (f", and {len(ctx.views)} views" if ctx.views else ""))
    return "ok"


def cmd_collect(ctx: Context) -> int:
    day = parse_day(ctx.args.day, ctx.tz, ctx.now)
    with ctx.history() as history:
        got = collect_day(ctx, history, day, ctx.args.log)
    from .retention import after_collect      # the cohorts, from what is kept
    after_collect(ctx)
    return 0 if got == "ok" else 1


def cmd_backfill(ctx: Context) -> int:
    last = yesterday(ctx.tz, ctx.now)
    days = [last - timedelta(days=i) for i in range(ctx.args.days - 1, -1, -1)]
    tally = {"ok": 0, "withheld": 0, "empty": 0, "skipped": 0}
    with ctx.history() as history:
        for day in days:
            keys = [ctx.site] + [view_key(ctx.site, v.slug) for v in ctx.views]
            # A partial day is collected again: the logs may now hold all of it.
            if not ctx.args.force and all(history.state(k, day) == "ok" for k in keys):
                tally["skipped"] += 1
                continue
            tally[collect_day(ctx, history, day)] += 1
        if ctx.args.force:
            # A recount can take a first visitor away, never only move it
            # earlier: the page milestones are worked out again.
            from .store_extras import rebuild_milestones
            ctx.out(f"page milestones rebuilt from the stored days: "
                    f"{rebuild_milestones(history.db, ctx.site, ctx.tz):,}")
    from .retention import after_collect      # the cohorts, once, from what is kept
    after_collect(ctx)
    ctx.out("backfill: " + ", ".join(f"{k} {v}" for k, v in tally.items()))
    if ctx.args.force:
        from . import markers
        markers.append(ctx.live_dir, "backfill", f"backfill --force {ctx.args.days} days",
                       "history recounted from the logs: " + ", ".join(
                           f"{k} {v}" for k, v in tally.items()))
    if tally["withheld"] or not (tally["ok"] or tally["skipped"]):
        return 1
    return 0


def cmd_dashboard(ctx: Context) -> int:
    given = getattr(ctx.args, "out", None)
    out = (Path(given) if given else
           _path(ctx.config, ctx.config_path, "dashboard", "out", None))
    if out is None:
        ctx.err("no output directory: set dashboard.out or pass --out")
        return 2
    with ctx.history() as history:
        multi = len(ctx.all_configs) > 1
        written = dashboard.write(out, history, ctx.tz, ctx.now,
                                  country_credit(ctx.config), ctx.live_dir,
                                  ctx.views,
                                  refresh=bool((ctx.config.get("dashboard") or {})
                                               .get("refresh_button")),
                                  # The web app unless the config says app: false (2.2.2;
                                  # before, a config without the key got only the plain page).
                                  app=(ctx.config.get("dashboard") or {}).get("app", True)
                                  not in (False, "false", "no", "off", 0),
                                  config=ctx.config,
                                  only=ctx.site if multi else None,
                                  index_sites=[site_name(c) for c in ctx.all_configs]
                                  if multi else None)
        from . import multisite
        sites = multisite.describe(ctx.all_configs, history)
        live_names = {s["name"] for s in sites
                      if live.load(live.path_for(_live_dir_of(ctx, s["name"]), s["name"]))}
        try:
            written += multisite.write_sites(out, sites, live_names)
        except Exception as why:        # noqa: BLE001 - the switcher's list, never the redraw
            ctx.err(f"sites.json: {type(why).__name__}: {why}")
        from . import setup_page        # a waiting or removed site: a page saying so, not a 404
        written += setup_page.write_missing(out, sites, ctx.config, ctx.config_path, ctx.err)
    for path in written:
        if path.suffix == ".html":
            ctx.out(f"wrote {path}")
    csvs = sum(1 for p in written if p.suffix == ".csv")
    if csvs:
        ctx.out(f"wrote {csvs} CSV files beside them")
    data = sum(1 for p in written if p.suffix == ".json")
    if data:
        ctx.out(f"wrote {data} data files (data/*.json)")
    return 0


def _live_dir_of(ctx: Context, name: str) -> Path:
    """Where a site's live snapshot is: beside history for the first site,
    in its own folder for the others (multisite.py)."""
    first = site_name(ctx.all_configs[0])
    from .multisite import state_dir
    return ctx.db_path.parent if name == first else state_dir(ctx.db_path.parent, name)


def _credit_text(config: dict) -> str | None:
    credit = country_credit(config)
    if not credit:
        return None
    return credit[0] + (f" ({credit[1]})" if credit[1] else "")


def cmd_export(ctx: Context) -> int:
    """History, or today so far, as CSV or JSON. Aggregates only."""
    a = ctx.args
    f = export.Filters(group=a.group, tier=a.tier, engine=a.engine,
                       source=a.source, path_prefix=a.path_prefix,
                       country=a.country, dimension=a.dimension,
                       browser=a.browser, os=a.os, device=a.device,
                       source_type=a.source_type, status=a.status)
    credit = _credit_text(ctx.config)
    view = None
    if a.view:
        wanted = a.view.lower()
        view = next((v for v in ctx.views
                     if v.name.lower() == wanted or v.slug == wanted), None)
        if view is None:
            ctx.err(f"no view named {a.view!r}; configured: "
                    + (", ".join(v.name for v in ctx.views) or "none"))
            return 2
    try:
        if a.live:
            if a.first or a.last or a.include_withheld:
                ctx.err("--live exports today so far; it takes no --from, "
                        "--to or --include-withheld")
                return 2
            snap = live.load(live.path_for(ctx.live_dir, ctx.site))
            today = ctx.now.date().isoformat()
            if snap is None or snap.get("day") != today:
                ctx.err("no live snapshot for today; run `skald live` first")
                return 1
            if view is not None:
                snap = live.view_snapshot(snap, view.slug)
                if snap is None:
                    ctx.err(f"today's live snapshot has no figures for the view "
                            f"{view.name!r} yet; run `skald live` again")
                    return 1
            if snap.get("state") != "ok":
                ctx.err(f"today's live figures are {snap.get('state')}: "
                        "nothing to export")
                return 1
            rows = export.rows_from_live(snap, a.table, f, credit)
            first = last = today
            coverage = {"live": snap.get("generated_at")}
        else:
            last_day = (parse_day(a.last, ctx.tz, ctx.now) if a.last
                        else yesterday(ctx.tz, ctx.now))
            first_day = (parse_day(a.first, ctx.tz, ctx.now) if a.first
                         else last_day - timedelta(days=29))
            if last_day < first_day:
                ctx.err("--to is before --from")
                return 2
            key = view_key(ctx.site, view.slug) if view else ctx.site
            with ctx.history() as history:
                rows, coverage = export.rows_from_history(
                    history, key, a.table, first_day, last_day, f,
                    a.include_withheld, credit)
            first, last = first_day.isoformat(), last_day.isoformat()
        if a.total:
            rows = export.total(rows, a.table)
    except export.ExportError as why:
        ctx.err(f"export: {why}")
        return 2
    if a.format == "json":
        meta = {"site": ctx.site, "view": view.name if view else None,
                "table": a.table, "from": first, "to": last,
                "filters": f.given(), "total": a.total,
                "include_withheld": a.include_withheld, "coverage": coverage,
                "generated_at": ctx.now.isoformat(timespec="seconds")}
        if a.table == "countries" and credit:
            meta["attribution"] = credit
        text = export.as_json(rows, meta)
    else:
        text = export.as_csv(rows)
    if a.out:
        from .files import write_atomic
        write_atomic(Path(a.out), text)
        ctx.err(f"wrote {len(rows):,} rows to {a.out}")
    else:
        sys.stdout.write(text)
    return 0


def cmd_live(ctx: Context) -> int:
    """Snapshot today so far, then redraw the dashboard with it.

    Writes only the snapshot file and the dashboard. Never the history,
    never mail. Exits 1 when today's figures do not reconcile (the panel then
    says withheld), 0 otherwise - including "nothing logged yet today".
    """
    from . import requests_feed
    from .privacy import forgotten
    from .window import day_window
    hours, cap = requests_feed.settings(ctx.config)
    utc_now = ctx.now.astimezone(timezone.utc)
    # On a whole second: the feed's "from" is written to the second, and the
    # audit recounts from it, so a cut inside a second disagreed by the lines
    # logged in that second.
    cutoff = (utc_now - timedelta(hours=hours)).replace(microsecond=0)
    feed = requests_feed.Feed(cutoff, cap, ctx.views,
                              str(setting(ctx.config, "report", "heartbeat_label", "heartbeat")),
                              setting(ctx.config, "site", "hosts") or (),
                              int(setting(ctx.config, "report", "session_gap_minutes", 30)))
    midnight = day_window(ctx.now.date(), ctx.tz)[0]
    # Each plain log's size now: every reader of this run, and the audit
    # after it, reads that far and no further (lines keep arriving).
    from .window import plain_sizes
    upto = plain_sizes(ctx.config)
    requests_feed.before_midnight(ctx.config, feed, midnight, utc_now, upto)
    snap = live.build(ctx.config, ctx.site, ctx.tz, ctx.now, ctx.views, ctx.db_path, feed,
                      upto)
    path = live.path_for(ctx.live_dir, ctx.site)
    live.save(path, snap)
    requests_feed.save(requests_feed.path_for(ctx.live_dir, ctx.site), feed.result(
        ctx.tz, forgotten(ctx.live_dir), cutoff,
        utc_now, hours, cap, ctx.now.isoformat(timespec="seconds"), upto))
    if snap["state"] == "ok":
        ctx.out(f"live {snap['day']} to {snap['generated_at']}: "
                f"{snap['requests']:,} requests, every category reconciles")
    elif snap["state"] == "empty":
        from .multisite import WAITING, waiting
        ctx.waiting = waiting(ctx.config, ctx.db_path)
        ctx.out(f"live {snap['day']}: {ctx.site}: {WAITING}" if ctx.waiting else
                f"live {snap['day']}: no requests logged yet today")
    else:
        ctx.err(f"live {snap['day']}: WITHHELD, figures do not reconcile")
        for p in snap["problems"]:
            ctx.err(f"  - {p}")
    _after_live(ctx, snap, feed)
    code = 1 if snap["state"] == "withheld" else 0
    # Recorded before the redraw, so the page it draws shows this run.
    runs.record(ctx.live_dir, "live", code)
    if _path(ctx.config, ctx.config_path, "dashboard", "out", None) or \
            getattr(ctx.args, "out", None):
        drawn = cmd_dashboard(ctx)
        if drawn:
            runs.record(ctx.live_dir, "live", drawn)
            return drawn
    return code


def _after_live(ctx: Context, snap: dict, feed) -> None:
    """The cheap checks that ride on every live run: markers (config and
    website version) and alerts. A failure here never fails the live run."""
    from . import markers
    try:
        markers.note_config(ctx.config_path, ctx.live_dir)
        markers.refresh_version(ctx.config, ctx.live_dir)
    except Exception as why:            # noqa: BLE001 - bookkeeping only
        ctx.err(f"markers: {why}")
    try:
        from . import robots            # the site's robots.txt, at most hourly
        robots.refresh(ctx.config, ctx.live_dir)
    except Exception as why:            # noqa: BLE001
        ctx.err(f"robots: {why}")
    try:
        from . import sitemap           # the site's sitemaps, at most hourly
        sitemap.refresh(ctx.config, ctx.live_dir)
    except Exception as why:            # noqa: BLE001
        ctx.err(f"sitemap: {why}")
    _favicons(ctx, snap, limit=10)
    from .conversions import jobs       # leads into conversions, outgoing webhooks
    jobs.live(ctx)
    if ctx.waiting:                     # no line yet: nothing to alert on
        return
    try:
        from . import alerts
        code = alerts.run(ctx, snap, feed.signals())
        runs.record(ctx.live_dir, "alerts", code)
    except ImportError:
        pass
    except Exception as why:            # noqa: BLE001
        ctx.err(f"alerts: {type(why).__name__}: {why}")
        runs.record(ctx.live_dir, "alerts", 1)


def _favicons(ctx: Context, snap: dict | None, limit: int, days: int = 0) -> None:
    """Referrer favicons, when dashboard.favicons is on: new hosts only, a
    few seconds at most, never failing the run (favicons.py)."""
    on = setting(ctx.config, "dashboard", "favicons", False)
    out = _path(ctx.config, ctx.config_path, "dashboard", "out", None)
    if out is None or not (on is True or str(on).lower() == "true"):
        return
    from . import favicons
    try:
        if days:
            with ctx.history() as history:
                last = ctx.now.date()
                hosts = favicons.hosts_from(snap, history, ctx.site,
                                            last - timedelta(days=days), last)
        else:
            hosts = favicons.hosts_from(snap)
        favicons.refresh(ctx.config, out, ctx.site, hosts, limit=limit, live_dir=ctx.live_dir)
    except Exception as why:            # noqa: BLE001 - icons are a nicety
        ctx.err(f"favicons: {type(why).__name__}: {why}")


def mail(ctx: Context, kind: str, dry_run: bool, save_html: str | None = None) -> int:
    try:
        cfg = mailer.settings(ctx.config)
        with ctx.history() as history:
            msg = mailer.build(kind, ctx.config, history, ctx.tz, ctx.now)
    except mailer.Refused as why:
        ctx.err(f"{kind} mail REFUSED: {why}")
        if isinstance(why, mailer.Withheld):        # the data, not the setup
            ctx.by_design = str(why)
        return 1
    if save_html:
        Path(save_html).write_text(msg.get_body(("html",)).get_content())
    if dry_run:
        ctx.out(mailer.preview(msg))
        return 0
    mailer.send(msg, cfg)
    ctx.out(f"sent {kind} mail to {', '.join(cfg['to'])}: {msg['Subject']}")
    return 0


def cmd_mail(ctx: Context) -> int:
    kind = "weekly" if ctx.args.weekly else "daily"
    return mail(ctx, kind, ctx.args.dry_run, ctx.args.save_html)


def run_steps(steps: list[tuple[str, Callable[[], int]]], err=print,
              stopped: list | None = None) -> int:
    """Run each step while the previous one returned 0. The first failure
    stops; its name goes into `stopped` when one is given."""
    for name, step in steps:
        code = step()
        if code:
            err(f"run-daily stopped at '{name}' (exit {code}); later steps skipped")
            if stopped is not None:
                stopped.append(name)
            return code
    return 0


def audit_day(ctx: Context, day: date, logs: list[str] | None = None,
              withhold: bool = False) -> int:
    """Recount a stored day from the raw log by a separate road (audit.py)
    and compare. A mismatch exits 1; with `withhold` the day - the site and
    every view, which came from the same pass - is marked withheld, so it
    is never drawn or mailed."""
    from . import audit
    try:
        figures = audit.recount(ctx.config, day, ctx.tz,
                                [Path(p) for p in logs] if logs else None, ctx.now)
    except ValueError as why:
        ctx.err(f"audit {day}: {why}")
        return 2
    from .settings_store import prune_plan
    window = int(setting(ctx.config, "visitors", "repeat_days", 30))
    keep, own = prune_plan(ctx.config, "visitors.repeat_days", window)   # as prune_kept keeps hashes
    unchecked: list = []
    with ctx.history() as history:
        problems, compared = audit.compare(
            figures, history, ctx.site, day, window,
            ctx.now.date() - timedelta(days=own.get(ctx.site, keep)), unchecked)
        state = history.state(ctx.site, day)
        if state is not None:
            # The result, for the data-quality panel (quality.json).
            from .store_extras import note
            note(history.db, ctx.site, day, "audit", {
                "state": "mismatch" if problems else "ok",
                "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "compared": compared, "problems": [audit.mask(p) for p in problems[:20]]})
        if problems and withhold and state is not None:
            words = [f"audit: {p}" for p in problems]
            for key in [ctx.site] + [view_key(ctx.site, v.slug) for v in ctx.views]:
                history.withhold(key, day, words)
        breakdowns = history.breakdown_days(ctx.site, day, day)
    if problems:
        ctx.err(f"audit {day}: THE RECOUNT DOES NOT MATCH HISTORY "
                f"({len(problems)} of {compared} figures)")
        for p in problems:
            ctx.err(audit.mask(f"  - {p}"))
        if unchecked:
            ctx.err(f"  {audit.unchecked_words(unchecked).lstrip('; ')}")
        if withhold and state is not None:
            ctx.err("  the day is now withheld; it will not be shown or mailed")
        return 1
    note = ""
    if state == "withheld":
        note = "; the day is stored as withheld, so it is not shown anyway"
    elif day.isoformat() not in breakdowns:
        note = "; breakdowns not recorded for this day (collected before they existed)"
    ctx.out(f"audit ok: {day}: {figures['requests']:,} requests, "
            f"{figures['readers']:,} readers; {compared} figures recounted, "
            f"all match{audit.unchecked_words(unchecked)}{note}")
    return 0


def audit_live(ctx: Context) -> int:
    """Recount today so far over the live snapshot's own window, and compare
    with the snapshot. Never withholds anything: live is never stored."""
    from . import audit
    snap = live.load(live.path_for(ctx.live_dir, ctx.site))
    if snap is None or not snap.get("until"):
        ctx.err("audit --live: no snapshot with its window recorded; run `skald live` first")
        return 2
    day = date.fromisoformat(snap["day"])
    until = datetime.fromisoformat(snap["until"])
    # The bytes the snapshot read (an older one recorded none: whole files).
    upto = snap.get("read_upto")
    try:
        figures = audit.recount(ctx.config, day, ctx.tz,
                                [Path(p) for p in ctx.args.log] if ctx.args.log else None,
                                ctx.now, until=until, upto=upto)
    except ValueError as why:
        ctx.err(f"audit --live: {why}")
        return 2
    if snap.get("state") == "empty" and not figures.get("requests"):   # no log lines yet (2.29)
        ctx.out(f"audit skipped: live {day}: {ctx.site} has no log lines yet")
        return 0
    problems, compared = audit.compare_live(figures, snap)
    if getattr(ctx.args, "show_active", False):     # both roads' active visits, listed
        from .audit_realtime import show_active
        for text in show_active(snap.get("realtime"), figures.get("more"), ctx.tz):
            ctx.out(audit.mask(text))
    # The Recent requests feed: its window's requests by group, recounted.
    import json
    from .requests_feed import path_for
    try:
        feed = json.loads(path_for(ctx.live_dir, ctx.site).read_text())
    except (OSError, ValueError):
        feed = None
    if feed and feed.get("from") and feed.get("generated_at") == snap.get("generated_at"):
        counted = audit.recount_requests(
            ctx.config, ctx.tz, datetime.fromisoformat(feed["from"]), until,
            [Path(p) for p in ctx.args.log] if ctx.args.log else None, feed.get("read_upto"))
        stored = feed.get("by_group") or {}
        for group in sorted(set(stored) | set(counted)):
            compared += 1
            if int(stored.get(group, 0)) != counted.get(group, 0):
                problems.append(f"recent requests, {group}: the feed has "
                                f"{int(stored.get(group, 0)):,}, the recount finds "
                                f"{counted.get(group, 0):,}")
        compared += 1
        if int(feed.get("total", 0)) != sum(counted.values()):
            problems.append(f"recent requests: the feed has {int(feed.get('total', 0)):,}, "
                            f"the recount finds {sum(counted.values()):,}")
    # Real time's 15-second request count, the helper's last one (realtime_tail.py).
    from .audit_realtime import live_tail
    got, n = live_tail(ctx.config, ctx.live_dir, ctx.site, ctx.args.log or None)
    problems += got
    compared += n
    # Yesterday at this hour, and both days by hour (by_now.py).
    from .audit_by_now import check as check_by_now
    got, n = check_by_now(ctx.config, ctx.tz, snap, [Path(p) for p in ctx.args.log] if ctx.args.log else None)
    problems += got
    compared += n
    # The totals the last alert check read.
    from .alerts import load_state
    kept = (load_state(ctx.live_dir).get("figures") or {})
    if kept.get("at") == snap.get("generated_at"):
        counted = audit.recount_alert_figures(
            ctx.config, ctx.tz, kept, [Path(p) for p in ctx.args.log] if ctx.args.log else None,
            upto)
        for key in ("server_errors", "people_404", "requests"):
            compared += 1
            if kept[key]["n"] != counted[key]:
                problems.append(f"alert check, {key} in {kept[key]['minutes']} minutes: "
                                f"{kept[key]['n']:,} against {counted[key]:,} recounted")
        compared += 1
        if kept.get("newest_line") != counted["newest_line"]:
            problems.append(f"alert check, newest line: {kept.get('newest_line')} against "
                            f"{counted['newest_line']}")
    if problems:
        ctx.err(f"audit live {day} to {snap.get('generated_at')}: THE RECOUNT DOES NOT "
                f"MATCH THE SNAPSHOT ({len(problems)} of {compared} figures)")
        for p in problems:
            ctx.err(audit.mask(f"  - {p}"))
        return 1
    ctx.out(f"audit ok: live {day} to {snap.get('generated_at')}: "
            f"{figures['requests']:,} requests, {figures['readers']:,} readers; "
            f"{compared} figures recounted, all match")
    return 0


def cmd_audit(ctx: Context) -> int:
    if ctx.args.live:
        return audit_live(ctx)
    day = parse_day(ctx.args.day, ctx.tz, ctx.now)
    return audit_day(ctx, day, ctx.args.log, ctx.args.withhold)


def daily_steps(ctx: Context) -> list[tuple[str, Callable[[], int]]]:
    day = yesterday(ctx.tz, ctx.now)
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
            _report_all(ctx, day, found)
            # Figures that do not reconcile are held back by design; no log
            # line at all for the day is a failure (logging or format broke).
            if not any(p.what == "nothing parsed" for _, ps in found for p in ps):
                ctx.by_design = "the figures do not reconcile"
            return 1
        ctx.out(f"check ok: {_describe(day, figures[0])}")
        return 0

    def do_collect() -> int:
        with ctx.history() as history:
            got = collect_day(ctx, history, day, figures=held["figures"])
        from .retention import after_collect  # the cohorts (audit_retention recounts)
        after_collect(ctx)
        return 0 if got == "ok" else 1

    def do_verify_bots() -> int:
        # Fetch the crawler owners' lists and look up DNS before counting, so
        # collect and the audit after it read the same answers. Never stops
        # the day: an unreachable list keeps yesterday's copy.
        from . import bot_verify
        try:
            bot_verify.run(ctx)
        except Exception as why:        # noqa: BLE001
            ctx.err(f"verify-bots: {type(why).__name__}: {why}; counting with the stored lists")
        return 0

    def do_audit() -> int:
        code = audit_day(ctx, day, withhold=True)
        if code == 1:                   # the recount disagrees: withheld
            ctx.by_design = "the audit's recount does not match; the day is withheld"
        return code

    from .bot_verify import ranges_dir
    steps = [("verify-bots", do_verify_bots)] if ranges_dir(ctx.config) else []
    steps += [
        ("check", do_check),
        ("collect", do_collect),
        ("audit", do_audit),
    ]
    # Second counts beside the log's (the leads recount, audit_more.DAILY):
    # they never stop the run; cmd_run_daily reads their outcome at the end.
    from . import audit_more
    from .conversions import jobs       # the lead DB and outgoing webhooks, first of all
    steps = jobs.daily_steps(ctx) + steps
    steps += audit_more.daily_steps(ctx, day)
    from . import events                # in-page events (beacon); never stops the run
    if events.enabled(ctx.config):
        steps.append(("events", lambda: events.daily(ctx, day)))
    if setting(ctx.config, "dashboard", "favicons", False) in (True, "true"):
        steps.append(("favicons", lambda: _favicons(ctx, None, limit=40, days=90) or 0))
    from . import kit_api, security_notify, site_logos, stack, updates   # these never fail
    steps += [("logo", lambda: site_logos.daily(ctx)), ("updates", lambda: updates.daily(ctx)),
              ("stack", lambda: stack.daily(ctx)), ("kit tokens", lambda: kit_api.daily(ctx)),
              ("security mail", lambda: security_notify.daily(ctx)),
              ("dashboard", lambda: cmd_dashboard(ctx))]
    # Each mail can be turned off in Settings > Mail & reports (mail.daily, mail.weekly).
    if _mail_on(ctx.config, "daily"):
        steps.append(("daily mail", lambda: mail(ctx, "daily", ctx.args.dry_run)))
    if ctx.now.date().weekday() == 0 and _mail_on(ctx.config, "weekly"):
        steps.append(("weekly mail", lambda: mail(ctx, "weekly", ctx.args.dry_run)))
    if setting(ctx.config, "pagespeed", "enabled", None) in (True, "true") or (
            setting(ctx.config, "pagespeed", "enabled", None) is None and not ctx.args.dry_run
            and setting(ctx.config, "pagespeed", "base_url")):
        # Google's measure of the top landing pages; always returns 0.
        from . import pagespeed
        steps.append(("pagespeed", lambda: pagespeed.run(ctx)))
    # A site still waiting for its first line has no day: only these run.
    return [(name, step) if name in WHILE_WAITING else (name, _unless_waiting(ctx, step))
            for name, step in steps]


WHILE_WAITING = ("verify-bots", "conversions", "check", "favicons", "logo", "updates",
                 "kit tokens", "dashboard")


def _unless_waiting(ctx: Context, step: Callable[[], int]) -> Callable[[], int]:
    return lambda: 0 if ctx.waiting else step()


def _mail_on(config: dict, kind: str) -> bool:
    """mail.daily / mail.weekly: on unless set to false."""
    got = (config.get("mail") or {}).get(kind)
    return not (got is False or str(got).lower() == "false")


def cmd_run_daily(ctx: Context) -> int:
    """The steps, then the outcome in runs.json: ok, withheld (a step stopped
    the run by design) or failed. A crash is noted as failed and raised."""
    ctx.by_design = None
    ctx.waiting = False
    ctx.recounts = None                 # (code, why) from audit_more's steps
    stopped: list[str] = []
    try:
        code = run_steps(daily_steps(ctx), ctx.err, stopped)
        if code == 0 and ctx.recounts:  # a recount disagreed (1) or broke (2)
            code, ctx.by_design = ctx.recounts
            stopped.append("recounts")
    except BaseException as why:
        runs.record(ctx.live_dir, "run-daily", 1, outcome="failed",
                    step=stopped[0] if stopped else None,
                    reason=f"{type(why).__name__}: {why}")
        raise
    outcome = "ok" if code == 0 else "withheld" if code == 1 and ctx.by_design else "failed"
    if code == 0 and ctx.waiting:
        outcome = "waiting"             # a dashboard site with no line yet
    # The step it stopped at and why, for `skald doctor` (runs.json).
    runs.record(ctx.live_dir, "run-daily", code, outcome=outcome,
                step=stopped[0] if code and stopped else None,
                reason=ctx.by_design if code else None)
    return code


# --------------------------------------------------------------------- main

def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="skald", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="config.yml")
    ap.add_argument("--today", metavar="YYYY-MM-DD",
                    help="pretend the local date is this (replays and tests)")
    ap.add_argument("--site", dest="only_site", metavar="NAME",
                    help="with several sites (config `sites:`), work on this one only")
    sub = ap.add_subparsers(dest="command", required=True)

    p = sub.add_parser("check", help="verify one day's figures; store nothing")
    p.add_argument("--day", default="yesterday")
    p.add_argument("--log", action="append", help="read this file, repeatable")
    p.set_defaults(run=cmd_check)

    p = sub.add_parser("collect", help="analyse one day and store it")
    p.add_argument("--day", default="yesterday")
    p.add_argument("--log", action="append", help="read this file, repeatable")
    p.set_defaults(run=cmd_collect)

    p = sub.add_parser("backfill", help="store each of the last N days")
    p.add_argument("--days", type=int, required=True)
    p.add_argument("--force", action="store_true",
                   help="re-collect days already stored and verified")
    p.set_defaults(run=cmd_backfill)

    p = sub.add_parser("dashboard", help="render the static dashboard")
    p.add_argument("--out", help="output directory (default dashboard.out)")
    p.set_defaults(run=cmd_dashboard)

    p = sub.add_parser("mail", help="send the daily or weekly mail")
    which = p.add_mutually_exclusive_group(required=True)
    which.add_argument("--daily", action="store_true")
    which.add_argument("--weekly", action="store_true")
    p.add_argument("--dry-run", action="store_true", help="print, do not send")
    p.add_argument("--save-html", metavar="PATH", help="also write the HTML part")
    p.set_defaults(run=cmd_mail)

    p = sub.add_parser("export", help="history or today so far as CSV or "
                       "JSON; verified days only unless asked")
    p.add_argument("--from", dest="first", metavar="DATE",
                   help="first day (default: 30 days before --to)")
    p.add_argument("--to", dest="last", metavar="DATE",
                   help="last day, inclusive (default: yesterday)")
    p.add_argument("--table", choices=export.TABLES, default="daily")
    p.add_argument("--group", help="people, answer_engines, search_engines, bots, ours")
    p.add_argument("--tier", help="training, asked or cited")
    p.add_argument("--engine", help="an assistant or crawler by name, e.g. GPTBot")
    p.add_argument("--source", help="a citing site, e.g. perplexity.ai; on journeys also a "
                   "referring host or utm_source")
    p.add_argument("--path-prefix", dest="path_prefix", metavar="PREFIX")
    p.add_argument("--country", metavar="CC")
    p.add_argument("--dimension", help="readers table: country, browser, os, "
                   "device, source, referrer, campaign, landing or hour")
    p.add_argument("--browser", help="readers table: a browser family, e.g. Chrome")
    p.add_argument("--os", help="readers table: an operating system, e.g. iOS")
    p.add_argument("--device", help="readers table: Desktop, Mobile or Tablet")
    p.add_argument("--source-type", dest="source_type",
                   help="readers table: a traffic source, e.g. 'Search engine'")
    p.add_argument("--status", help="statuses table: 2xx, 3xx, 404, 4xx, 5xx, other")
    p.add_argument("--view", help="a dashboard.views name: export that view")
    p.add_argument("--total", action="store_true",
                   help="sum over the range instead of one row per day")
    p.add_argument("--include-withheld", action="store_true",
                   help="also export days whose figures did not reconcile, "
                        "marked state=withheld")
    p.add_argument("--live", action="store_true", help="today so far instead")
    p.add_argument("--format", choices=("csv", "json"), default="csv")
    p.add_argument("--out", metavar="FILE", help="write here instead of stdout")
    p.set_defaults(run=cmd_export)

    p = sub.add_parser("audit", help="recount a stored day from the raw log "
                       "by a separate road and compare with history")
    p.add_argument("--day", default="yesterday")
    p.add_argument("--log", action="append", help="read this file, repeatable")
    p.add_argument("--withhold", action="store_true",
                   help="mark the day withheld if anything does not match")
    p.add_argument("--live", action="store_true",
                   help="recount today so far and compare with the live snapshot")
    p.add_argument("--show-active", action="store_true",
                   help="with --live: list both roads' active visits (labels and times, "
                        "no address), to read a real-time mismatch")
    p.set_defaults(run=cmd_audit)

    p = sub.add_parser("live", help="snapshot today so far and redraw the "
                       "dashboard; never stored as a day, never mailed")
    p.add_argument("--out", help="dashboard directory (default dashboard.out)")
    p.set_defaults(run=cmd_live)

    p = sub.add_parser("run-daily", help="check, collect, dashboard, mail")
    p.add_argument("--dry-run", action="store_true",
                   help="print the mail instead of sending it")
    p.set_defaults(run=cmd_run_daily)

    from . import cli_more
    cli_more.register(sub)
    return ap


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if getattr(args, "bare", None) and not Path(args.config).exists():   # try-log needs none
        return args.bare(args)
    if getattr(args, "days", None) is not None and args.days < 1:
        print("--days must be at least 1", file=sys.stderr)
        return 2
    ctx = Context(args)
    from . import multisite
    # The other sites are laid over config.yml as read; each Context adds its own settings.
    # Paused and removed sites are left out of the collecting commands (multisite.contexts).
    stop, contexts, alone = multisite.contexts(ctx, args, Context)
    if stop is not None:
        return stop
    if alone and contexts:
        return _deliver_after(args, contexts, args.run(ctx))
    codes = multisite.run_each(contexts)
    return _deliver_after(args, contexts, max(codes, default=0))


def _deliver_after(args, contexts: list, code: int) -> int:
    """live and run-daily: webhooks, then the right-away security mail, once after all sites."""
    if args.command in ("live", "run-daily"):
        from . import summary_mail
        summary_mail.after_run(contexts, args.command)
    return code
