"""The conversions' background work, riding on `skald live` (every two
minutes) and `skald run-daily`:

  * leads: the site's lead DB into conversions.sqlite (from_leads.py);
    live reads only what changed, run-daily reads every lead (and drops the
    rows of leads deleted from the CMS)
  * outgoing: new conversions and abandoned starts into the outbox
    (outgoing.py). Nothing is sent here: a slow receiver of one site must
    not hold up the next. `deliver` sends what is due ONCE, after every
    site's step (cli.main), at most outgoing.RUN_BUDGET seconds in all and
    outgoing.DEADLINE seconds a delivery; what is left waits for the next run

Neither ever stops a run: a failure is one line on stderr. run-daily runs
them first, before the second counts, so the audit sees the store up to date.
"""
from __future__ import annotations

from pathlib import Path


def _folder(ctx) -> Path:
    return Path(ctx.db_path).parent


def _leads(ctx, full: bool) -> None:
    from . import from_leads
    got = from_leads.run(ctx.config, _folder(ctx), ctx.site, full=full)
    if got and got.get("error"):
        ctx.err(f"conversions from leads: {got['error']}")
    elif got and (full or got["added"] or got["removed"]):
        ctx.out(f"conversions from leads: {got['read']} read, {got['added']} added, "
                f"{got['removed']} removed")


def _outgoing(ctx) -> None:
    try:
        from . import outgoing
    except ImportError:
        return
    got = outgoing.run(ctx.config, _folder(ctx), ctx.site, ctx.now, deliver=False)
    if got and got.get("error"):
        ctx.err(f"outgoing webhooks: {got['error']}")


def deliver(contexts) -> None:
    """The outgoing webhooks' one delivery pass, after every site's live or
    daily step: the sites sharing a conversions file together, the whole
    pass within outgoing.RUN_BUDGET seconds. Never raises."""
    try:
        import time
        from . import outgoing, store
        groups: dict[str, tuple] = {}
        for ctx in contexts:
            folder = _folder(ctx)
            path = store.path_for(ctx.config, folder)
            groups.setdefault(str(path), (folder, {}))[1][ctx.site] = ctx.config
        end = time.monotonic() + outgoing.RUN_BUDGET
        for folder, configs in groups.values():
            left = end - time.monotonic()
            if left <= 0:
                break
            got = outgoing.deliver_pass(configs, folder, contexts[0].now, budget=left)
            if got.get("error"):
                contexts[0].err(f"outgoing webhooks: {got['error']}")
            elif got.get("waiting"):
                contexts[0].out(f"outgoing webhooks: {got['waiting']} due, left for the "
                                "next run (time budget spent)")
    except Exception as why:            # noqa: BLE001 - never stops a run
        if contexts:
            contexts[0].err(f"outgoing webhooks: {type(why).__name__}: {why}")


def _each(ctx, full: bool) -> int:
    for name, step in (("leads", lambda: _leads(ctx, full)), ("outgoing", lambda: _outgoing(ctx))):
        try:
            step()
        except Exception as why:            # noqa: BLE001 - never stops a run
            ctx.err(f"conversions {name}: {type(why).__name__}: {why}")
    return 0


def live(ctx) -> None:
    """After the live snapshot: cheap, incremental."""
    _each(ctx, full=False)


def daily_steps(ctx) -> list:
    """run-daily's step, before the second counts; none when the install has
    neither a lead DB to read nor a conversions file."""
    from . import from_leads, store
    if not from_leads.enabled(ctx.config) and \
            not store.path_for(ctx.config, _folder(ctx)).exists():
        return []
    return [("conversions", lambda: _each(ctx, full=True))]
