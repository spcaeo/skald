"""History for visits: their metrics kept for good, their journeys for a week.

The metrics are histograms and top lists in the `counts` table, like every
other breakdown, under the kinds in VISIT_KINDS; `days.journeys` is 1 for a
day they were counted on (schema 8). A period sums them back into one
visits.VisitStats only when every day in it has them - a month's median
from ten of its thirty days is not the month's median.

The journeys themselves - one anonymous row per visit, as visits.Journeys
writes them - go in the `journeys` table and are deleted once they are
older than `report.journey_days` (default 7). They carry no address, no
user agent and no visitor key; only labels, pages and times to the minute.
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import date

from .config import setting
from .visits import VisitStats

JOURNEY_DAYS = 7

# VisitStats field -> counts kind. Entries, sources, countries and devices
# of visits are the readers breakdowns (visits.check holds them equal), so
# they are not stored twice.
VISIT_KINDS = {
    "pages": "visit_pages",
    "trail": "visit_trail",
    "seconds": "visit_seconds",
    "exits": "visit_exit",
    "steps": "visit_step",
    "flags": "visit_flag",
}
OURS_KIND = "ours_label"


def journey_days(config: dict) -> int:
    """How many days of journeys to keep: report.journey_days, at least 1."""
    return max(1, int(setting(config, "report", "journey_days", JOURNEY_DAYS)))


def count_rows(totals) -> list[tuple[str, str, int]]:
    """(kind, name, n) rows for a day's visit metrics and our own labels."""
    rows: list[tuple[str, str, int]] = []
    stats = totals.visits
    if stats is not None:
        for name, kind in VISIT_KINDS.items():
            rows += [(kind, str(k), int(n)) for k, n in getattr(stats, name).items() if n]
    if totals.ours_labels:
        rows += [(OURS_KIND, str(k), int(n)) for k, n in totals.ours_labels.items() if n]
    return rows


def write_journeys(db, key: tuple[str, str], totals) -> None:
    """Replace a day's journeys. Called inside History.record's transaction."""
    db.execute("DELETE FROM journeys WHERE site = ? AND day = ?", key)
    if totals.journeys:
        db.executemany(
            "INSERT INTO journeys (site, day, seq, data) VALUES (?, ?, ?, ?)",
            [(*key, i, json.dumps(j, sort_keys=True))
             for i, j in enumerate(totals.journeys)])


def period_stats(summed: dict[str, Counter], visits: int, people) -> VisitStats:
    """A period's VisitStats from its summed counts; the first-page labels
    come back from the readers breakdowns they equal."""
    stats = VisitStats(visits=visits)
    for name, kind in VISIT_KINDS.items():
        setattr(stats, name, Counter(dict(summed.get(kind, Counter()).most_common())))
    if people is not None and people.by:
        for mine, theirs in (("entries", "landing"), ("source", "source"),
                             ("country", "country"), ("device", "device")):
            setattr(stats, mine, Counter(people.by.get(theirs) or {}))
    return stats


def journeys(db, site: str, first: date, last: date) -> list[dict]:
    """Stored journeys in [first, last], newest first, each with its day."""
    out = []
    for day, data in db.execute(
            "SELECT day, data FROM journeys WHERE site = ? AND day BETWEEN ? AND ? "
            "ORDER BY day DESC, seq DESC", (site, first.isoformat(), last.isoformat())):
        try:
            item = json.loads(data)
        except ValueError:
            continue
        item["day"] = day
        out.append(item)
    return out


def prune(db, keep_from: date, per_site: dict | None = None, spare=None) -> int:
    """Delete every journey from before `keep_from`; a site in `per_site`
    ({site: date}, from its own report.journey_days) by its own date. Rows
    deleted. `spare`: see prune_sites."""
    return prune_sites(db, "journeys", keep_from.isoformat(),
                       {s: d.isoformat() for s, d in (per_site or {}).items()}, spare=spare)


def prune_sites(db, table: str, cutoff: str, per_site: dict | None = None,
                where: str = "", args: tuple = (), spare=None) -> int:
    """Delete `table` rows with day < `cutoff` (ISO), except that a site
    named in `per_site` ({site: its own cutoff}) - with its views - is cut at
    its own day. With no `per_site` this is one DELETE over every site, as
    before settings existed. `where` adds " AND ..." with `args`. `spare`
    (site -> bool, keep_everything.Keeper): a site it names keeps every row,
    with its views."""
    from .store import VIEW_MARK
    per_site = dict(per_site or {})
    if spare is not None:
        if getattr(spare, "all", False):
            return 0
        for (name,) in db.execute(f"SELECT DISTINCT site FROM {table}").fetchall():
            base = str(name).split(VIEW_MARK, 1)[0]
            if spare(base):
                per_site[base] = ""     # day < "" is never true: nothing goes

    def own(site: str) -> tuple[str, tuple]:
        mark = site + VIEW_MARK
        return "(site = ? OR substr(site, 1, ?) = ?)", (site, len(mark), mark)

    sql, params = f"DELETE FROM {table} WHERE day < ?{where}", [cutoff, *args]
    for site in sorted(per_site):
        clause, more = own(site)
        sql += f" AND NOT {clause}"
        params += more
    with db:
        gone = db.execute(sql, params).rowcount
        for site in sorted(per_site):
            clause, more = own(site)
            gone += db.execute(f"DELETE FROM {table} WHERE day < ?{where} AND {clause}",
                               [per_site[site], *args, *more]).rowcount
    return gone
