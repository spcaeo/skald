"""The second road for "the search sync stopped" (#40, search/health.py).

The main road reads the state file's summary fields (`last_ok`, `last_sync`, `ok`,
`fails`). This one reads only the kept tries (`tries`: each sync's time and outcome,
oldest first) and works the answer out again by itself:

  worked   some try in the list ended well
  since    the newest good try's time
  fails    the tries after it, all failed
  stopped  worked, at least one failed try after the good one, and either
           health.STOPPED_TRIES of them or the newest failed STOPPED_HOURS or more after
           the good one

It shares only those two numbers with the main road. It then compares its answer with
what Settings and the Search tab show (health.of) and with the Overview > Insights to-do
(health.todos): stopped or not, since when, and the failed tries (when the list is not cut
short at health.KEEP_TRIES). An engine whose state file has no tries yet (written before
2.49) is not checked.

Registered in audit_more.DAILY ("search_sync"); todos.build runs `check` too, and leaves
out a search to-do it does not bear out (todos.json `withheld`).
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from .search.health import KEEP_TRIES, STOPPED_HOURS, STOPPED_TRIES


def _at(text) -> datetime | None:
    try:
        got = datetime.fromisoformat(str(text))
    except (TypeError, ValueError):
        return None
    return got if got.tzinfo else got.replace(tzinfo=timezone.utc)


def own(tries) -> dict | None:
    """{"worked", "since", "fails", "stopped"} from the kept tries; None when none are kept."""
    tries = [t for t in (tries or []) if isinstance(t, dict) and _at(t.get("at"))]
    if not tries:
        return None
    good, fails, newest_fail = None, 0, None
    for t in sorted(tries, key=lambda t: _at(t["at"])):
        if t.get("ok") is True:
            good, fails, newest_fail = t["at"], 0, None
        else:
            fails += 1
            newest_fail = t["at"]
    stopped = False
    if good is not None and fails:
        hours = (_at(newest_fail) - _at(good)).total_seconds() / 3600
        stopped = fails >= STOPPED_TRIES or hours >= STOPPED_HOURS
    return {"worked": good is not None, "since": good, "fails": fails, "stopped": stopped,
            "cut": len(tries) >= KEEP_TRIES}


def check(saved: dict, engine: str, source, shown: dict, todo: dict | None) -> list[str]:
    """The problems found for one engine: `shown` is health.of (Settings, the Search tab),
    `todo` the to-do Insights gets (None: no to-do)."""
    mine = own(((saved or {}).get(engine) or {}).get("tries"))
    if mine is None:
        return []
    if not source:
        mine["stopped"] = False         # not connected is never stopped
    out = []
    if mine["stopped"] != bool(shown.get("stopped")):
        out.append(f"{engine}: the tries say {'stopped' if mine['stopped'] else 'not stopped'}, "
                   f"Settings says {shown.get('state')}")
    if mine["stopped"] != (todo is not None):
        out.append(f"{engine}: the tries say {'stopped' if mine['stopped'] else 'not stopped'}, "
                   f"Insights {'has' if todo else 'has no'} to-do")
    if not mine["stopped"] or out:
        return out
    fig = (todo or {}).get("figures") or {}
    for name, theirs in (("Settings", shown), ("Insights", fig)):
        if _at(theirs.get("since")) != _at(mine["since"]):
            out.append(f"{engine}: the last good sync by the tries is {mine['since']}, "
                       f"{name} says {theirs.get('since')}")
        if not mine["cut"] and theirs.get("fails") != mine["fails"]:
            out.append(f"{engine}: the tries count {mine['fails']} failed in a row, "
                       f"{name} says {theirs.get('fails')}")
    return out


def check_site(config: dict, folder, site: str) -> dict[str, list[str]]:
    """{engine: problems} for every engine of the site, against what health gives."""
    from .search import health, state
    from .search.sync import connected
    saved = state.load(folder, site)
    todos = {t["subject"]: t for t in health.todos(config, folder, site)}
    out = {}
    for engine, source in connected(config or {}).items():
        out[engine] = check(saved, engine, source, health.of(saved, engine, source),
                            todos.get(engine))
    return out


def set_up(ctx) -> bool:
    from .search.sync import connected
    return any(connected(getattr(ctx, "config", None) or {}).values())


def daily(ctx, day) -> list[str] | None:
    """run-daily's step (audit_more.DAILY)."""
    if not set_up(ctx):
        return None
    got = check_site(ctx.config, Path(ctx.db_path).parent, ctx.site)
    return [p for problems in got.values() for p in problems]
