"""The registry of later second counts (phase 4), and run-daily's step for
them. Part of the audit's road: a module here shares only classify.py's
name lists with the code it checks, and labels visits with the audit's own
labels (audit_labels.py), never with dimensions.py.

Two kinds of recount:

RECOUNTS (name -> module): counted in audit.recount's one pass over the raw
lines, and compared in the audit (`skald audit`, run-daily's audit step,
`audit --live`). The module offers a class

    Recount(config, day, tz, own)
        one per recount of a day; `own` is the site's hosts (may be empty).
      .set_window(start, end) -> None   (optional)
        the window recounted, [start, end), before the first line.
      .hit(line, group, tier, name) -> None   (optional)
        every line of the site's hosts in log order, with the audit's
        group, AI tier ("asked", "training" or "") and crawler name.
      .other_host(line) -> None   (optional)
        each line of a host the site does not list, in log order.
      .judged(line, group, info) -> None   (optional)
        the same lines with audit.Judge.info: what the judge found beyond
        the group (a crawler's name, a spoof, a link preview, a probe, a
        crawler session, a visit that never rendered).
      .visit(lines, is_page, labels) -> None
        each people visit: its audit.Line list in time order, assets and
        posts included; `is_page(line)` is the audit's page rule; `labels`
        is the audit's labels of the visit's first page view - country,
        browser, os, device, source, referrer, campaign, landing, hour - or
        None when the visit read no page.
      .compare(stored, same, problems) -> None
        `stored` is the day's day_extras {kind: blob} (or the live
        snapshot's extras); a kind it lacks was not counted that day: skip
        it. `same(what, stored_n, counted_n)` records a mismatch; append a
        string to `problems` for anything else. A mismatch withholds the day.

DAILY (name -> module): second counts of figures that do not come from the
log (a CMS, a spool), run by run-daily after the audit. The module offers

    daily(ctx, day) -> list[str] | None
        the problems found (empty: it matches), None when not set up.
    set_up(ctx) -> bool   (optional)
        False leaves the module out of run-daily's steps altogether.

Neither kind stops the run: a mismatch ends run-daily with exit 1 and
outcome "withheld" (by design, like the audit's), a crash with exit 2,
"failed" (failmail.py). A module not written yet is skipped.
"""
from __future__ import annotations

import importlib

RECOUNTS = {"funnels": "audit_funnels", "engagement": "audit_engagement",
            "utm_hygiene": "audit_utm", "ai_likely": "audit_ai_likely",
            "people": "audit_people", "ai_formats": "audit_ai_formats",
            "crawler_cost": "audit_crawler_cost", "realtime": "audit_realtime",
            "first_touch": "audit_firsttouch", "search_landing": "audit_search_landing",
            "crawl_health": "audit_crawl_health", "security": "audit_security"}
DAILY: dict[str, str] = {"conversions": "audit_conversions", "alerts": "audit_alerts",
                         "search": "audit_search", "retention": "audit_retention",
                         "ai_answers": "audit_ai_answers",
                         "security_alerts": "audit_security", "stack": "audit_stack"}


def _modules(registry: dict) -> dict:
    out = {}
    for name, module in registry.items():
        try:
            out[name] = importlib.import_module(f".{module}", __package__)
        except ModuleNotFoundError as why:
            if why.name != f"{__package__}.{module}":
                raise
    return out


class Recounts:
    """Every registered recount of one day, fed and compared together."""

    def __init__(self, config: dict, day, tz, own: set) -> None:
        self.each = [mod.Recount(config, day, tz, own)
                     for mod in _modules(RECOUNTS).values()]

    def set_window(self, start, end) -> None:
        """The recount's window, [start, end): end is the live snapshot's
        `until` under `audit --live` (a recount that offers set_window)."""
        for r in self.each:
            if hasattr(r, "set_window"):
                r.set_window(start, end)

    def hit(self, line, group: str, tier: str, name: str) -> None:
        """Every line of the site's hosts, as the audit judged it (a recount
        that offers `hit` sees them all: the AI fetches, say)."""
        for r in self.each:
            if hasattr(r, "hit"):
                r.hit(line, group, tier, name)

    def judged(self, line, group: str, info: dict) -> None:
        """The same lines with what the audit's judge found beyond the group
        (audit.Judge.info: the crawler's name, a spoof, a preview, a probe)."""
        for r in self.each:
            if hasattr(r, "judged"):
                r.judged(line, group, info)

    def visit(self, lines: list, is_page, labels: dict | None) -> None:
        for r in self.each:
            r.visit(lines, is_page, labels)

    def other_host(self, line) -> None:
        """A line of a host the site does not list (counted nowhere else): a
        recount that offers `other_host` sees it (Security: bare-IP lines)."""
        for r in self.each:
            if hasattr(r, "other_host"):
                r.other_host(line)

    def compare(self, stored: dict, same, problems: list) -> None:
        for r in self.each:
            r.compare(stored, same, problems)


def start(config: dict, day, tz, own: set) -> Recounts:
    return Recounts(config, day, tz, own)


# ---------------------------------------------------------------- run-daily

def _hold(ctx, code: int, why: str | None) -> None:
    """Keep the worst result for cli.cmd_run_daily: a crash over a mismatch."""
    old = getattr(ctx, "recounts", None)
    if old is None or code > old[0]:
        ctx.recounts = (code, why)


def _run(ctx, name: str, daily, day) -> None:
    from .audit import mask
    try:
        problems = daily(ctx, day)
    except Exception as why:            # noqa: BLE001 - a failure, not a stop
        ctx.err(mask(f"{name}: {type(why).__name__}: {why}"))
        _hold(ctx, 2, None)
        return
    if problems is None:
        return
    if problems:
        ctx.err(f"{name}: THE RECOUNT DOES NOT MATCH ({len(problems)} figures)")
        for p in problems:
            ctx.err(mask(f"  - {p}"))
        _hold(ctx, 1, f"the {name} recount does not match")
    else:
        ctx.out(f"{name}: ok, the recount matches")


def daily_steps(ctx, day) -> list:
    """run-daily's steps for the second counts beside the log's: the leads
    recount (when leads.db is set) and each registered DAILY module. Each
    returns 0; the outcome is kept in ctx.recounts for cmd_run_daily."""
    from .leads import db_path
    found = {name: mod for name, mod in _modules(DAILY).items()
             if getattr(mod, "set_up", lambda _ctx: True)(ctx)}

    def leads() -> int:
        from . import audit_leads
        _run(ctx, "leads audit", audit_leads.daily, day)
        return 0

    def recounts() -> int:
        for name, mod in found.items():
            _run(ctx, name, mod.daily, day)
        return 0

    steps = [("leads audit", leads)] if db_path(ctx.config) is not None else []
    return steps + ([("recounts", recounts)] if found else [])
