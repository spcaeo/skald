"""The second road for a lead's touches Skald filled from its page views (2.45).

The main road is conversions/fill.py: at intake and on each run it fills a
lead with a visitor ID and no touches (and a script-tag conversion's first
source, campaign and first touch time) from the ID's page views, and names
the columns in `filled`. conversions.json then counts those columns like any
other (audit_conversions_figures counts them again from the same columns).
This module checks the columns themselves: for every row of the shown days
that may have been filled, it works the values out again from the journeys,
read whole in time order with its own time parser, the visits split going
forward (a gap of more than VISIT_GAP starts a new one) where fill.py walks
back, and compares them with what the row holds - the value and whether
`filled` names it. It shares only the name lists in conversions/__init__.py
(FILLABLE, FILLED_BEACON, BEACON_TOOL, VISIT_GAP) and the file's location.

The click (click_kind, click_id) is not a figure and is not checked here.
A day with a row it disagrees with is withheld (audit_conversions.check_file).
"""
from __future__ import annotations

import sqlite3
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

from .conversions import BEACON_TOOL, FILLABLE, FILLED_BEACON, VISIT_GAP

FIGURES = tuple(c for c in FILLABLE if c != "click")


def _when(text) -> datetime | None:
    try:
        got = datetime.fromisoformat(str(text).replace("Z", "+00:00"))
    except ValueError:
        return None
    return got if got.tzinfo else got.replace(tzinfo=timezone.utc)


def _edge(d: date, tz) -> str:
    return datetime.combine(d, time(0), tzinfo=tz).astimezone(timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")


def expected(views: list, at: str) -> dict:
    """The FIGURES a row converted at `at` gets from its ID's page views
    (at, path, source_type, campaign, in time order, rowid breaking ties);
    every one None without a page view at or before `at`."""
    seen = [v for v in views if v[0] <= at]
    if not seen:
        return dict.fromkeys(FIGURES)
    start, prev = seen[0], _when(seen[0][0])
    for view in seen[1:]:
        moment = _when(view[0])
        if prev is not None and moment is not None and (moment - prev).total_seconds() > VISIT_GAP:
            start = view
        prev = moment
    first = seen[0]
    return {"source_type": start[2], "first_source": first[2], "campaign": start[3],
            "landing": first[1], "first_touch_at": first[0]}


def _skalds(row: dict) -> tuple[str, ...]:
    """The FIGURES Skald may hold on this row, by the rule fill.py follows."""
    named = set((row["filled"] or "").split(",")) - {""}
    if row["tool"] == BEACON_TOOL:
        base = tuple(c for c in FILLED_BEACON if c in FIGURES)
    elif all(row[c] is None or c in named for c in ("source_type", "first_source")):
        base = FIGURES
    else:
        return ()
    return tuple(c for c in base if c in named or row[c] is None)


def check(path: Path, site: str, tz, first: date, last: date) -> dict[str, list[str]]:
    """{local day: problems} for the rows of first..last whose filled touches
    the page views do not bear out."""
    if path is None or not Path(path).is_file():
        return {}
    db = sqlite3.connect(f"file:{Path(path).resolve()}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    try:
        have = {r[1] for r in db.execute("PRAGMA table_info(conversions)")}
        if "filled" not in have:
            return {}
        rows = [dict(r) for r in db.execute(
            "SELECT id, tool, vid, at, filled, " + ", ".join(FIGURES) + " FROM conversions "
            "WHERE site = ? AND vid IS NOT NULL AND at >= ? AND at < ?",
            (site, _edge(first, tz), _edge(last + timedelta(days=1), tz)))]
        out: dict[str, list[str]] = {}
        cache: dict = {}
        for row in rows:
            cols = _skalds(row)
            if not cols:
                continue
            if row["vid"] not in cache:
                cache[row["vid"]] = [tuple(v) for v in db.execute(
                    "SELECT at, path, source_type, campaign FROM journeys WHERE site = ? AND "
                    "vid = ? ORDER BY at, rowid", (site, row["vid"]))]
            want = expected(cache[row["vid"]], row["at"])
            named = set((row["filled"] or "").split(",")) - {"", "click"}
            should = {c for c in cols if want[c] is not None}
            moment = _when(row["at"])
            day = moment.astimezone(tz).date().isoformat() if moment else "?"
            for c in cols:
                if row[c] != want[c]:
                    out.setdefault(day, []).append(
                        f"{day} lead row {row['id']} {c}: stored {row[c]!r}, its page views "
                        f"say {want[c]!r}")
            if named != should:
                out.setdefault(day, []).append(
                    f"{day} lead row {row['id']}: filled names {sorted(named)}, its page views "
                    f"fill {sorted(should)}")
        return out
    finally:
        db.close()
