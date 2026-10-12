"""The second count of the visits kept with their address (people/visits.py).

Registered in audit_more.RECOUNTS, so it rides on audit.recount's one pass
over the raw log: `visit` gets each people visit as the audit split it (its
own visit rule, its own page rule, the address and user agent as the key),
and counts, per address, the visits that read a page (readers) and their
page views. `compare` opens conversions.sqlite read-only and, by its own
SQL, sets the day's kept rows against that:

  * the visits kept equal the day's readers, and their pages its page views;
  * every address kept has exactly the visits and pages the recount finds;
  * the rows kept as "(removed)" (an address on the forgotten list) equal
    the recount's visits of the addresses not kept by name.

Only whole days (state "whole", written by the daily run) are compared:
today's rows are rewritten every live run and a day the site kept no
address for has no `visit_days` row. A mismatch withholds the day like any
other audit finding. No address is ever written into a problem.

It shares nothing with the main road but the file's location and the
table's name.
"""
from __future__ import annotations

import sqlite3
from collections import Counter
from pathlib import Path

REMOVED = "(removed)"


def _store(config: dict) -> Path | None:
    """conversions.sqlite: `conversions.db`, else beside the history."""
    raw = ((config or {}).get("conversions") or {}).get("db")
    if raw:
        return Path(str(raw)).expanduser()
    history = ((config or {}).get("_resolved") or {}).get("history_db") or \
        ((config or {}).get("history") or {}).get("db")
    if not history or not Path(str(history)).expanduser().is_absolute():
        return None
    return Path(str(history)).expanduser().parent / "conversions.sqlite"


def _site(config: dict) -> str:
    site = (config or {}).get("site") or {}
    hosts = site.get("hosts") or []
    return str(site.get("name") or (hosts[0] if hosts else "") or "site")


class Recount:
    def __init__(self, config: dict, day, tz, own: set) -> None:
        self.config, self.day = config, day
        self.visits: Counter = Counter()
        self.pages: Counter = Counter()

    def visit(self, lines: list, is_page, labels: dict | None) -> None:
        if labels is None or not lines:
            return
        address = lines[0].address
        self.visits[address] += 1
        self.pages[address] += sum(1 for line in lines if is_page(line))

    def kept(self) -> tuple | None:
        """(day row, {address: (visits, pages)}) or None when not kept."""
        path = _store(self.config)
        if path is None or not path.is_file():
            return None
        db = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)
        try:
            have = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE "
                                             "type = 'table'")}
            if not {"visits", "visit_days"} <= have:
                return None
            key = (_site(self.config), self.day.isoformat())
            row = db.execute("SELECT state, visits, pages FROM visit_days WHERE site = ? AND "
                             "day = ?", key).fetchone()
            if row is None or row[0] != "whole":
                return None
            per = {ip: (n, p) for ip, n, p in db.execute(
                "SELECT ip, COUNT(*), COALESCE(SUM(pages), 0) FROM visits WHERE site = ? AND "
                "day = ? GROUP BY ip", key)}
        finally:
            db.close()
        return row, per

    def compare(self, stored: dict, same, problems: list) -> None:
        got = self.kept()
        if got is None:
            return
        (_, day_visits, day_pages), per = got
        rows = sum(n for n, _ in per.values())
        same("visits kept with an address", rows, sum(self.visits.values()))
        same("page views of the visits kept with an address",
             sum(p for _, p in per.values()), sum(self.pages.values()))
        same("visits kept: the day's own count", day_visits, rows)
        same("visits kept: the day's own page count", day_pages,
             sum(p for _, p in per.values()))
        differ = 0
        for address, (n, p) in per.items():
            if address != REMOVED and (n, p) != (self.visits.get(address, 0),
                                                 self.pages.get(address, 0)):
                differ += 1
        same("addresses whose kept visits differ from the recount", differ, 0)
        rest = sum(n for a, n in self.visits.items() if a not in per)
        same("visits kept without their address (forgotten)", per.get(REMOVED, (0, 0))[0],
             rest)
