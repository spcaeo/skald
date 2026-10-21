"""The audit's own answer to "did a browser draw this visit?" (rendering.py).

Written apart from rendering.py, as the rest of the audit is: its own visit
split, its own asset and page tests, its own reading of the beacon spool
(the raw JSON lines), its own keyed hash and its own query of the stored
readers. It shares only the name lists from classify.py.

The rule it recounts (CLASSIFICATION.md, rule 9): a browser-like visit is
people only when one of its pages drew - an own asset (site.asset_prefixes,
default /_next/static/) or a ?_rsc= payload from 5 s before to
site.render_seconds (30) after a page request - or a beacon page opening
vouches for it, or the same address and agent drew earlier that day, or its
30-day hash was a counted reader on an earlier day. Everything else of a
browser-like visit is a bot. A Next.js navigation (the audit's own test,
audit.navigation) is a page request, and a payload that draws: a visit of
such navigations alone drew.
"""
from __future__ import annotations

import json
import re
import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from .classify import OTHER_BOT

_LOOKS_LIKE_BROWSER = re.compile(r"Mozilla/|Opera/|Safari/|Chrome/|Firefox/", re.I)
_RSC = re.compile(r"[?&](?:_rsc|__flight__|_data)=", re.I)
EARLY = 5            # seconds an asset may be logged before its page


def switched_on(config: dict) -> bool:
    return ((config.get("site") or {}).get("require_rendering", True)) is not False


def prefixes(config: dict) -> tuple[str, ...]:
    raw = (config.get("site") or {}).get("asset_prefixes")
    if raw is None:
        return ("/_next/static/",)
    items = raw.split() if isinstance(raw, str) else list(raw)
    return tuple(str(x) for x in items if str(x).startswith("/"))


def window_seconds(config: dict) -> int:
    got = (config.get("site") or {}).get("render_seconds")
    return 30 if got is None else int(got)


def _utc(when: datetime) -> datetime:
    return when.replace(tzinfo=timezone.utc) if when.tzinfo is None else when


# ---------------------------------------------------------------- beacon

def _spool(config: dict) -> Path | None:
    made = (config.get("_resolved") or {}).get("beacon_spool")
    if made:
        return Path(made)
    raw = (config.get("beacon") or {}).get("spool")
    if raw:
        return Path(str(raw)).expanduser()
    db = (config.get("history") or {}).get("db")
    return Path(str(db)).expanduser().parent / "beacon" if db else None


def openings(config: dict, start: datetime, end: datetime, tz) -> list:
    """[(opened, path)]: one per distinct page opening the spool's people
    events report, opened (at less t) inside [start, end)."""
    if not (config.get("beacon") or {}).get("enabled"):
        return []
    folder = _spool(config)
    if folder is None:
        return []
    found = set()
    day = start.astimezone(tz).date() - timedelta(days=1)
    last = end.astimezone(tz).date()
    while day <= last:
        # The day's events and its openings that are no event (since 2.10.1).
        for path in (folder / f"{day.isoformat()}.jsonl", folder / f"opens-{day.isoformat()}.jsonl"):
            if not path.is_file():
                continue
            for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
                try:
                    row = json.loads(raw)
                except ValueError:
                    continue
                if not isinstance(row, dict) or row.get("g") != "people":
                    continue
                if not isinstance(row.get("e"), str) or not isinstance(row.get("p"), str):
                    continue
                try:
                    opened = _utc(datetime.fromisoformat(str(row["at"]))) - timedelta(
                        seconds=int(row.get("t") or 0))
                except (KeyError, TypeError, ValueError):
                    continue
                if start <= opened < end:
                    found.add((opened, row["p"]))
        day += timedelta(days=1)
    return sorted(found)


# -------------------------------------------------------------- returning

def _window(config: dict) -> int:
    """visitors.repeat_days, read here on the audit's own road (default 30)."""
    try:
        return max(1, int(((config or {}).get("visitors") or {}).get("repeat_days") or 30))
    except (TypeError, ValueError):
        return 30


def stored_readers(config: dict, first: date) -> set[str]:
    """Reader hashes history holds for the days before `first` in the
    returning-visitor window (visitors.repeat_days - 1, 29 by default)."""
    made = (config.get("_resolved") or {}).get("history_db")
    db = Path(made) if made else Path(str((config.get("history") or {}).get("db") or ""))
    if not db.name or not db.exists():
        return set()
    site = str((config.get("site") or {}).get("name") or "site")
    try:
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        try:
            got = conn.execute(
                "SELECT visitor FROM visitor_days WHERE kind = 'reader' AND site = ? "
                "AND day < ? AND day >= ?",
                (site, first.isoformat(),
                 (first - timedelta(days=_window(config) - 1)).isoformat()))
            return {row[0] for row in got}
        finally:
            conn.close()
    except sqlite3.Error:
        return set()


# ------------------------------------------------------------------ rule

def never_drawn(config: dict, lines: list, gap: timedelta, hosts: set, start: datetime,
                end: datetime, tz, is_asset, is_beacon, family, keyed, secret,
                is_navigation=None) -> dict:
    """{(address, agent): [(first, last)]} of browser-like visits that drew
    nothing. `lines` is the window's lines; the helpers are the audit's own
    (its asset and beacon path tests, its browser/system label, its hash,
    and its Next.js navigation test: such a payload is a page request too,
    and draws as every payload does)."""
    if not switched_on(config):
        return {}
    own = prefixes(config)
    after = timedelta(seconds=window_seconds(config))
    early = timedelta(seconds=EARLY)

    by_pair: dict[tuple, list] = {}
    for line in lines:
        if hosts and line.host and line.host.lower() not in hosts:
            continue
        agent = line.agent
        if not agent or not _LOOKS_LIKE_BROWSER.search(agent) or OTHER_BOT.search(agent):
            continue
        by_pair.setdefault((line.address, agent), []).append(line)

    # Split each pair into visits, and mark which drew from their own assets.
    visits: list[tuple[tuple, list]] = []
    for pair in sorted(by_pair):
        seen = sorted(by_pair[pair], key=lambda l: l.when)
        group = [seen[0]]
        for line in seen[1:]:
            if line.when - group[-1].when > gap:
                visits.append((pair, group))
                group = []
            group.append(line)
        visits.append((pair, group))

    def page_request(line) -> bool:
        if is_navigation is not None and is_navigation(line):
            return True
        return (line.method in ("GET", "HEAD") and not _RSC.search(line.url)
                and not is_asset(line) and not is_beacon(line.path))

    def draws(line) -> bool:
        return line.path.startswith(own) or bool(_RSC.search(line.url))

    drew = set()
    for n, (_, group) in enumerate(visits):
        fetched = [l.when for l in group if draws(l)]
        if not fetched:
            continue
        asked = [l.when for l in group if page_request(l)]
        if any(p - early <= f <= p + after for f in fetched for p in asked):
            drew.add(n)

    # Beacon openings: each vouches for at most one visit, and for none when
    # a visit that drew already holds that page near that time.
    vouched = set()
    for opened, path in openings(config, start, end, tz):
        near = []
        for n, (pair, group) in enumerate(visits):
            for l in group:
                if (page_request(l) and l.path == path
                        and opened - early <= l.when <= opened + after):
                    near.append((abs((l.when - opened).total_seconds()), l.when, pair, n))
        if not near or any(n in drew or n in vouched for *_, n in near):
            continue
        vouched.add(min(near)[3])

    known = stored_readers(config, start.astimezone(tz).date()) if secret else set()
    out: dict[tuple, list] = {}
    earlier: set = set()
    for n, (pair, group) in enumerate(visits):
        if n in drew or n in vouched:
            earlier.add(pair)
            continue
        if pair in earlier:
            continue
        if known and keyed(secret, pair[0], family(pair[1])) in known:
            continue
        out.setdefault(pair, []).append((group[0].when, group[-1].when))
    return out
