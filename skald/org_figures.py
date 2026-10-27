"""An organisation's figures for Settings > Organisations' drawer (Overview):
the requests of the 7 days before today and the last day with any request,
for the organisation's sites, from the history's daily totals (`days`).

Each figure has a second count (audit_orgs.py, from the day's groups); when
the two disagree, or the history holds no day of the window, the figure is
None (withheld, "Not recorded"), never 0. Requests are requests: never
reported as people.
"""
from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from pathlib import Path

DAYS = 7


def window(today: date | None = None) -> tuple[str, str]:
    """(first, last) ISO days: the 7 calendar days before today."""
    today = today or date.today()
    return (today - timedelta(days=DAYS)).isoformat(), (today - timedelta(days=1)).isoformat()


def recent(history_path, sites, today: date | None = None) -> dict:
    """{"requests_7d", "last_day", "withheld"}: None for what is not known."""
    from . import audit_orgs
    out = {"requests_7d": None, "last_day": None, "withheld": None}
    names = [str(s) for s in sites or ()]
    if not names or history_path is None or not Path(history_path).is_file():
        return out
    first, last = window(today)
    marks = ",".join("?" * len(names))
    try:
        conn = sqlite3.connect(f"file:{Path(history_path).resolve()}?mode=ro", uri=True)
        try:
            days, total = conn.execute(
                f"SELECT COUNT(*), SUM(hits) FROM days WHERE site IN ({marks}) "
                "AND day >= ? AND day <= ?", (*names, first, last)).fetchone()
            latest = conn.execute(
                f"SELECT MAX(day) FROM days WHERE site IN ({marks}) AND hits > 0",
                names).fetchone()[0]
        finally:
            conn.close()
    except sqlite3.Error as why:
        out["withheld"] = f"the history could not be read ({type(why).__name__})"
        return out
    again, again_last = audit_orgs.recount(history_path, names, first, last)
    if days:
        if again == int(total or 0):
            out["requests_7d"] = int(total or 0)
        else:
            out["withheld"] = (f"the daily totals and their groups do not add up for {first} "
                               f"to {last}; run the audit (skald audit)")
    if latest is not None:
        if latest == again_last:
            out["last_day"] = latest
        else:
            out["withheld"] = out["withheld"] or ("the last day with data does not agree; "
                                                  "run the audit (skald audit)")
    return out
