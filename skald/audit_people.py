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

Shortened addresses (2.15.0, `privacy.keep_ips: short`). This file shortens
each address by its own code (`short_address`), sharing only the documented
rule with people/policy.py: an IPv4 address's last octet zeroed, an IPv6
address cut to its first 48 bits, an IPv4-mapped IPv6 address read as
IPv4, anything else kept as it is. On a site that shortens:

  * no kept address may be in full (one that its own rule would change);
  * the recount's visits are grouped by shortened address, and each kept
    shortened address must hold exactly that group's visits and pages -
    or, on a day with "(removed)" rows (a forgotten address inside the
    group), no more than the group, the totals above taking up the rest.

A site that keeps full addresses again (switched back from short) still
holds its older days shortened: a day whose full-address check fails, whose
every kept address is already in shortened form and which passes the
shortened check, is a day kept shortened, and passes.

Only whole days (state "whole", written by the daily run) are compared:
today's rows are rewritten every live run and a day the site kept no
address for has no `visit_days` row. A mismatch withholds the day like any
other audit finding. No address is ever written into a problem.

It shares nothing with the main road but the file's location and the
table's name.
"""
from __future__ import annotations

import ipaddress
import sqlite3
from collections import Counter
from pathlib import Path

REMOVED = "(removed)"
V4_KEEP = 0xFFFFFF00                         # the first 24 bits of an IPv4 address
V6_KEEP = ((1 << 48) - 1) << 80              # the first 48 bits of an IPv6 address


def short_address(address: str) -> str:
    """The shortened form, by the documented rule (see the module)."""
    text = "" if address is None else str(address)
    try:
        ip = ipaddress.ip_address(text.strip())
    except ValueError:
        return text
    mapped = getattr(ip, "ipv4_mapped", None)
    if mapped is not None:
        ip = mapped
    if ip.version == 4:
        return str(ipaddress.IPv4Address(int(ip) & V4_KEEP))
    return str(ipaddress.IPv6Address(int(ip) & V6_KEEP))


def shortens(config: dict) -> bool:
    """Whether the site keeps addresses shortened: `privacy.keep_ips` is
    the word short (never a default)."""
    raw = ((config or {}).get("privacy") or {}).get("keep_ips")
    return isinstance(raw, str) and raw.strip().lower() == "short"


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
        named = [a for a in per if a != REMOVED]
        if shortens(self.config):
            same("addresses kept in full on a site that keeps them shortened",
                 sum(1 for a in named if short_address(a) != a), 0)
            for check in self._shortened(per):
                same(*check)
            return
        full = self._full(per)
        if any(a != b for _, a, b in full) and named and \
                all(short_address(a) == a for a in named):
            short = self._shortened(per)
            if all(a == b for _, a, b in short):
                full = short                 # a day kept while the site shortened
        for check in full:
            same(*check)

    def _full(self, per: dict) -> list[tuple]:
        """Each kept address against its own visits in the recount."""
        differ = 0
        for address, (n, p) in per.items():
            if address != REMOVED and (n, p) != (self.visits.get(address, 0),
                                                 self.pages.get(address, 0)):
                differ += 1
        rest = sum(n for a, n in self.visits.items() if a not in per)
        return [("addresses whose kept visits differ from the recount", differ, 0),
                ("visits kept without their address (forgotten)",
                 per.get(REMOVED, (0, 0))[0], rest)]

    def _shortened(self, per: dict) -> list[tuple]:
        """Each kept shortened address against the recount's visits of every
        address that shortens to it (see the module)."""
        visits, pages = Counter(), Counter()
        for address, n in self.visits.items():
            visits[short_address(address)] += n
            pages[short_address(address)] += self.pages.get(address, 0)
        gone = per.get(REMOVED, (0, 0))[0] > 0
        differ = 0
        for address, (n, p) in per.items():
            if address == REMOVED:
                continue
            want = (visits.get(address, 0), pages.get(address, 0))
            if (n > want[0] or p > want[1]) if gone else (n, p) != want:
                differ += 1
        return [("shortened addresses whose kept visits differ from the recount", differ, 0),
                ("visits kept without their address (forgotten), shortened",
                 per.get(REMOVED, (0, 0))[0], sum(visits.values()) - rows_named(per))]


def rows_named(per: dict) -> int:
    """The visits kept under an address (not "(removed)")."""
    return sum(n for a, (n, _) in per.items() if a != REMOVED)
