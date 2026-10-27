"""The daily prune (run at the start of each day's collect, cli.collect_day).

Deletes what is kept only for a while: the windows in Settings > Privacy,
else config.yml; totals are kept for good. A site that keeps
everything (keep_everything.py: the install says so, or hosted, an
organisation with no plan or an Enterprise plan) keeps every row: each step
below spares it.
"""
from __future__ import annotations

from datetime import timedelta

from .config import setting


def prune_kept(ctx, history) -> None:
    from . import keep_everything
    from .settings_store import DETAIL_KINDS, prune_plan
    from .store_visits import journey_days
    from .visitors import repeat_days
    spare = keep_everything.of(ctx)
    today = ctx.now.date()
    # Anonymous journeys are kept report.journey_days days; totals for good.
    # A site whose window was changed in Settings keeps its own (settings_store).
    keep, own = prune_plan(ctx.config, "report.journey_days", journey_days(ctx.config))
    history.prune_journeys(today - timedelta(days=keep),
                           {s: today - timedelta(days=n) for s, n in own.items()}, spare)
    keep, own = prune_plan(ctx.config, "visitors.repeat_days", repeat_days(ctx.config))
    history.prune_visitors(today, keep, own, spare)
    # The per-page and per-visit detail behind compare and page history is
    # kept report.retention_days (400); totals and milestones for good.
    keep, own = prune_plan(ctx.config, "report.retention_days",
                           int(setting(ctx.config, "report", "retention_days", 400)))
    history.prune_extras(today, keep, DETAIL_KINDS, own, spare)
    # The AI user fetches behind "likely sent by an AI assistant" (no person
    # in them) are kept as long as the leads look back (ai_likely.py).
    from .ai_likely import FETCH_DAYS
    history.prune_extras(today, FETCH_DAYS, ("ai_fetches",), spare=spare)
    from .people.visits import prune_kept as prune_people   # privacy.keep_days
    prune_people(ctx)
    # The conversions file's own keeping times (conversions.retention_days,
    # journeys.vid_days, deliveries 90 days, the spool): before 2.5.3 only by
    # hand (`conversions prune`), so nothing was ever pruned.
    from .cli_conversions import cmd_prune as prune_conversions
    try:
        prune_conversions(ctx, quiet=True)
    except Exception as why:          # noqa: BLE001 - a prune never stops the run
        ctx.err(f"conversions prune: {type(why).__name__}: {why}")
