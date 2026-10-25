"""The demo's tracked page changes (Traffic > Pages > a page, "Did my change work?"; T8).

Three changes a team marked, written through the real road (todo_marks.mark_change) into the
accounts file beside the history, so the live run's page_changes.json counts them and its
second count (audit_page_changes.py) checks them like any install's:

  /pricing/            30 days ago, a new title: 28 whole days on each side, compared
  /features/           20 days ago, new content: 19 days on each side, compared
  /blog/fall-launch    6 days ago, new content: too early to tell (6 of 14 days)

The demo has no sign-in, so nobody can mark or stop one there: the page says why.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

CHANGES = (
    ("/pricing/", 30, "title", "New title and a shorter plan table"),
    ("/features/", 20, "content", "Rewrote the top section around server logs"),
    ("/blog/fall-launch", 6, "content", ""),
)


def seed(root: Path, config: dict, site: str, today: date, say=print) -> int:
    """Writes the changes; returns how many."""
    from skald import todo_marks
    from skald.accounts.db import connect, path_for
    db = connect(path_for(config, root))
    try:
        for path, back, kind, note in CHANGES:
            day = today - timedelta(days=back)
            at = datetime.combine(day, time(10, 0), tzinfo=timezone.utc)
            todo_marks.mark_change(db, site, path, day.isoformat(), kind, note, today.isoformat(), None, at)
    finally:
        db.close()
    say(f"demo: {len(CHANGES)} tracked page changes")
    return len(CHANGES)
