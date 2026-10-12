"""The second count of a month's usage (saas/limits.py `usage`).

The usage a plan is measured by is the month's requests for an
organisation's sites: the sum of the history's daily totals (`days.hits`).
This counts the same thing by another road: the sum of the day's groups
(`groups.hits`), which partition every request of the day (verify.py checks
that on every run). It shares only the list of site names and the month
with the main count; it opens its own read-only connection.

When the two disagree, the usage is withheld (None), never guessed.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path


def recount(history_path, sites, month: str) -> tuple[int | None, int]:
    """(requests, calendar days with any group) for `sites` in `month`
    ("YYYY-MM"); (None, 0) when the history cannot be read. Only the
    requests are compared: a day with no request has no group rows."""
    names = [str(s) for s in sites or ()]
    if not names or history_path is None or not Path(history_path).is_file():
        return None, 0
    marks = ",".join("?" * len(names))
    try:
        conn = sqlite3.connect(f"file:{Path(history_path).resolve()}?mode=ro", uri=True)
        try:
            total, days = 0, set()
            for day, hits in conn.execute(
                    f"SELECT day, hits FROM groups WHERE site IN ({marks}) "
                    "AND substr(day, 1, 7) = ?", (*names, month)):
                total += int(hits or 0)
                days.add(day)
        finally:
            conn.close()
    except sqlite3.Error:
        return None, 0
    return total, len(days)
