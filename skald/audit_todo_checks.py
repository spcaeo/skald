"""The second count of "Check again"'s fixed marks (2.44: todo_check.py, todo_checks.py).

A to-do is marked fixed (todo_marks, state "fixed", kind "checked") only when a check's
sweep covered every row and found each one fixed. This module re-derives each such mark
by its own road: its own SQL over accounts.sqlite's `todo_marks` and `todo_checks`, its
own reading of each kept answer (status, where a redirect ended, another host), and its
own rules of what "fixed" means per kind, written again from docs/help/what-to-fix.md:

  lost       410, a 2xx, or a redirect to another host or to an address that answers 2xx
  markdown   a 2xx, or a redirect to another host or to an address that answers 2xx
  sitemap    the same as markdown
  errors     any answer under 500
  leave      never fixed by a check (visits are judged on whole days): a fixed mark on
             one is wrong

It shares nothing with todo_check.py but the table names. A mark it does not find the
same is withheld: the page shows the to-do as not fixed, with the reason
(settings/todos' `checks_withheld`, todos.json's `withheld_fixed`).
"""
from __future__ import annotations

import json

KIND_OF = {"lost-pages": "lost", "ai-markdown": "markdown", "sitemap": "sitemap",
           "server-errors": "errors"}
MOVED = {301, 302, 303, 307, 308}


def _kind(item: str) -> str:
    return KIND_OF.get(item, "leave" if item.startswith("leave-") else "")


def _two(v) -> bool:
    return isinstance(v, int) and 200 <= v <= 299


def fixed_here(kind: str, a: dict) -> bool:
    """This module's own reading of one kept answer."""
    status = a.get("status")
    if not isinstance(status, int):
        return False
    if kind == "errors":
        return status < 500
    if kind not in ("lost", "markdown", "sitemap"):
        return False
    if _two(status) or (kind == "lost" and status == 410):
        return True
    if status in MOVED:
        return bool(a.get("other_host")) or _two(a.get("end"))
    return False


def _marks(db, site: str) -> dict[str, tuple]:
    try:
        got = db.execute("SELECT item, state, at, kind FROM todo_marks WHERE site = ? ORDER BY at, rowid",
                         (site,)).fetchall()
    except Exception:                    # noqa: BLE001 - no table: nothing marked
        return {}
    last = {}
    for item, state, at, kind in got:
        last[item] = (state, at, kind)
    return {i: v for i, v in last.items() if v[0] == "fixed" and v[2] == "checked"
            and not i.startswith(("path:", "page:"))}


def verify(db, site: str) -> dict[str, str]:
    """{to-do id: why} for each fixed mark the kept answers do not bear out."""
    out = {}
    for item, (_state, at, _k) in _marks(db, site).items():
        kind = _kind(item)
        if kind in ("", "leave"):
            out[item] = "a check cannot fix this kind of to-do"
            continue
        try:
            got = db.execute("SELECT at, sweep, total, rows, mode FROM todo_checks WHERE site = ? AND "
                             "item = ? AND at <= ? ORDER BY at, rowid", (site, item, at)).fetchall()
        except Exception:                # noqa: BLE001 - no checks kept
            got = []
        if not got:
            out[item] = "no check is kept for it"
            continue
        sweep = got[-1][1]
        pages = [g for g in got if g[1] == sweep]
        if any(p[4] != "live" for p in pages):
            out[item] = "its check did not ask the addresses"
            continue
        answers: dict[str, dict] = {}
        for _at, _sw, _total, rows, _mode in pages:
            for a in json.loads(rows or "[]"):
                answers[a.get("path")] = a
        total = pages[-1][2]
        good = sum(1 for a in answers.values() if fixed_here(kind, a))
        if total <= 0 or len(answers) != total or good != total:
            out[item] = (f"the second count finds {good} of {total} addresses fixed "
                         f"({len(answers)} answers kept)")
    return out


def read(config, site: str, live_dir=None) -> dict[str, str]:
    """verify() over the install's accounts.sqlite, read-only; {} without one."""
    import sqlite3

    from .settings_store import accounts_file
    path = accounts_file(config) or (accounts_file(config, live_dir) if live_dir else None)
    if path is None:
        return {}
    try:
        db = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5)
    except sqlite3.Error:
        return {}
    try:
        return verify(db, site)
    finally:
        db.close()
