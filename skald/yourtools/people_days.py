"""Names and emails in the tools' stored answers, kept no longer than the site's
People days, even when the tool stopped answering (2.43).

An answer is cut when it comes (Adapter.scrub, sync.people_policy): names and
emails older than the People days, or all of them on a site that keeps no
identity, never reach `yourtools.sqlite`. A tool that keeps answering replaces
its answer at each sync (latest_only). A tool that stopped answering does not,
so its last answer would keep its names past the promise. This sweep closes that:
once a day, in the daily prune (cli_conversions.cmd_prune), each stored answer
goes through its tool's own `scrub` again with the site's People days
(`privacy.keep_days`, each site its own: settings_store.prune_plan; 395 by
default, as at the fetch) counted back from midnight UTC today.

Only the names and emails go (Calendly's invitees, Resend's contacts and
recipients). The figures stay as they are: no figure is read from a name or an
email, so each one is still what the cut answer says. The answer's sha256 is
made again from the cut text in the same write, so recount.py's two checks
hold: the stored answer is the one its hash names, and every figure is
recounted from it (tests/test_yourtools_people_days.py checks both).

A site that keeps everything (keep_everything.Keeper: internal or enterprise,
the organisation rule decides) loses nothing, and the file is not opened when
every site keeps everything. Each site's counts go to the run's output,
privacy.log and the audit log ("privacy.cleared"): never a value.
"""
from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, time, timezone
from pathlib import Path

from . import get, store
from .base import Answer


def _values(node) -> int:
    """How many keys the dicts of `node` hold, at any depth."""
    if isinstance(node, dict):
        return len(node) + sum(_values(v) for v in node.values())
    if isinstance(node, list):
        return sum(_values(v) for v in node)
    return 0


def cut(db, today: date, days_of) -> dict:
    """Cut each answer's names and emails past its site's days (`days_of(site)`;
    None leaves the site as it is). {site: {"answers", "values", "days"}} for the
    sites with any cut. Only `body` and `sha256` change."""
    now = datetime.combine(today, time(0), tzinfo=timezone.utc)
    out: dict = {}
    rows = db.execute("SELECT id, site, tool, report, period, start, end, body FROM answers "
                      "ORDER BY id").fetchall()
    with db:
        for aid, site, tool, report, period, start, end, text in rows:
            adapter = get(tool)
            days = days_of(site)
            if adapter is None or days is None:
                continue
            body = json.loads(text)
            policy = {"identity": True, "keep_days": int(days), "now": now}
            got = adapter.scrub(Answer(report=report, period=period, start=start, end=end,
                                       request={}, body=body), policy)
            removed = _values(body) - _values(got.body)
            if not removed:
                continue
            new = store.body_text(got.body)
            db.execute("UPDATE answers SET body = ?, sha256 = ? WHERE id = ?",
                       (new, hashlib.sha256(new.encode("utf-8")).hexdigest(), aid))
            mine = out.setdefault(site, {"answers": 0, "values": 0, "days": int(days)})
            mine["answers"] += 1
            mine["values"] += removed
    return out


def run(ctx, today: date | None = None) -> dict:
    """The daily prune's step: every site's answers by its own People days."""
    from ..keep_everything import of
    from ..people.policy import keep_days
    from ..settings_store import prune_plan
    spare = of(ctx)                     # a keep-everything site loses nothing
    if spare.all:
        return {}
    folder = Path(ctx.db_path).parent
    if not store.path_for(folder).is_file():
        return {}
    people, own = prune_plan(ctx.config, "privacy.keep_days", keep_days(ctx.config))

    def days_of(site: str) -> int | None:
        return None if spare(site) else own.get(site, people)

    db = store.connect(folder)
    try:
        out = cut(db, today or ctx.now.date(), days_of)
    finally:
        db.close()
    note(ctx, out)
    return out


def words(site: str, got: dict) -> str:
    return (f"{site}: names and emails older than {got['days']} days cut from your tools' "
            f"answers: {got['values']} value(s) in {got['answers']} answer(s); figures kept")


def note(ctx, out: dict) -> None:
    """The run's output, privacy.log and the audit log: counts only."""
    if not out:
        return
    from ..privacy import LOG
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    lines = []
    for site, got in sorted(out.items()):
        ctx.out(f"people days: {words(site, got)}")
        lines.append(f"{stamp} people-days-tools site={site} days={got['days']} "
                     f"answers={got['answers']} values={got['values']}\n")
    live_dir = getattr(ctx, "live_dir", None)
    if live_dir is not None:
        try:
            import os
            log = Path(live_dir) / LOG
            with open(log, "a", encoding="utf-8") as handle:
                handle.write("".join(lines))
            os.chmod(log, 0o640)
        except OSError as why:
            ctx.err(f"people days (tools): privacy.log: {why}")
    try:
        from ..accounts import auditlog, connect
        from ..settings_store import _org_of, accounts_file
        path = accounts_file(ctx.config, live_dir)
        if path is None:
            return
        db = connect(path)
        try:
            for site, got in sorted(out.items()):
                auditlog.record(db, _org_of(db, site), "skald", "privacy.cleared", site,
                                words(site, got).split(": ", 1)[1])
        finally:
            db.close()
    except Exception as why:            # noqa: BLE001 - bookkeeping never stops a run
        ctx.err(f"people days (tools): audit log: {type(why).__name__}: {why}")
