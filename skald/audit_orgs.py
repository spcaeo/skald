"""The second count of an organisation's figures (org_figures.py `recent`).

The drawer's requests of the 7 days before today are the sum of the
history's daily totals (`days.hits`); this counts the same requests by
another road, the sum of the day's groups (`groups.hits`), which partition
every request of the day (verify.py checks that on every run). The last day
with data is the latest day with any group row here, against the latest day
with hits there. It shares only the list of site names and the two days
with the main count, and opens its own read-only connection.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path


def recount(history_path, sites, first: str, last: str) -> tuple[int | None, str | None]:
    """(requests from `first` to `last`, the latest day with any request) for
    `sites`; (None, None) when the history cannot be read."""
    names = [str(s) for s in sites or ()]
    if not names or history_path is None or not Path(history_path).is_file():
        return None, None
    marks = ",".join("?" * len(names))
    try:
        conn = sqlite3.connect(f"file:{Path(history_path).resolve()}?mode=ro", uri=True)
        try:
            total, latest = 0, None
            for day, hits in conn.execute(
                    f"SELECT day, hits FROM groups WHERE site IN ({marks})", names):
                if first <= day <= last:
                    total += int(hits or 0)
                if hits and (latest is None or day > latest):
                    latest = day
        finally:
            conn.close()
    except sqlite3.Error:
        return None, None
    return total, latest
