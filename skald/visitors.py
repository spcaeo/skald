"""Returning visitors, over 30 days, without keeping an address.

The owner's rule (2026-10-07): a raw address lives only in the web server's
own log and on the private page; history keeps, for 30 days, a keyed hash
of it - HMAC-SHA256 with a secret key held in the server's environment
(SKALD_VISITOR_KEY), joined with a family label (a reader's browser
family and system, or the assistant's or crawler's name) - and then
deletes it. Without the key the hash cannot be reversed or recomputed from
an address list. Totals are kept for good.

No key configured: nothing is hashed or stored, and every "repeat" and
"returning" field is None (not recorded), never False.

    visitor_days(site, day, visitor, kind, n, source)
      kind    "reader" (n = visits), "asked" or "training" (n = requests)
      source  the source type of the reader's first visit that day

"Repeat" means the same hash on an earlier day within the window:
`visitors.repeat_days` (REPEAT_DAYS, 30, unless changed in Settings, 1-90;
`repeat_days(config)`). The hashes are kept that many days.
Returning readers are counted by the source of their first visit in the
window (first_touch) and by this visit's own source (by_source).
times_seen_30d counts the distinct days it was seen in the 30 days ending
on the day in question, that day included.
"""
from __future__ import annotations

import hashlib
import hmac
import os
from datetime import date, timedelta
from pathlib import Path

from . import dimensions as dim

ENV = "SKALD_VISITOR_KEY"
REPEAT_DAYS = 30


def repeat_days(config: dict) -> int:
    """The returning-visitor window: visitors.repeat_days, else 30."""
    from .config import setting
    try:
        return max(1, int(setting(config or {}, "visitors", "repeat_days", REPEAT_DAYS)))
    except (TypeError, ValueError):
        return REPEAT_DAYS


def load_key(config: dict) -> bytes | None:
    """The secret, from the environment, else from the env file the config
    names (report.env_file) - the refresh helper runs without the cron's
    environment. None when neither has it."""
    value = os.environ.get(ENV, "").strip()
    if not value:
        path = ((config or {}).get("report") or {}).get("env_file")
        if path:
            try:
                for line in Path(str(path)).read_text().splitlines():
                    line = line.strip()
                    if line.startswith("export "):
                        line = line[7:].strip()
                    if line.startswith(ENV + "="):
                        value = line.split("=", 1)[1].strip().strip("'\"")
            except OSError:
                value = ""
    return value.encode() if value else None


def reader_family(agent: str) -> str:
    browser, system, _ = dim.agent_labels(agent)
    return f"{browser}/{system}"


def visitor_hash(key: bytes, address: str, family: str) -> str:
    """Hex HMAC-SHA256 of the address with the key, plus the family."""
    mac = hmac.new(key, address.encode("utf-8", "replace"), hashlib.sha256).hexdigest()
    return hashlib.sha256(f"{mac}|{family}".encode()).hexdigest()[:32]


SCHEMA = """
CREATE TABLE IF NOT EXISTS visitor_days (
    site    TEXT NOT NULL,
    day     TEXT NOT NULL,
    visitor TEXT NOT NULL,               -- keyed hash, see visitors.py
    kind    TEXT NOT NULL,               -- reader / asked / training
    n       INTEGER NOT NULL,
    source  TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (site, day, visitor, kind)
);
"""


def record(db, site: str, day: date, seen: dict) -> None:
    """Replace a day's hashes. `seen` is {(visitor, kind): [n, source]}.
    Called inside History.record's transaction."""
    db.execute("DELETE FROM visitor_days WHERE site = ? AND day = ?", (site, day.isoformat()))
    db.executemany(
        "INSERT INTO visitor_days (site, day, visitor, kind, n, source) VALUES (?, ?, ?, ?, ?, ?)",
        [(site, day.isoformat(), v, k, int(n), src) for (v, k), (n, src) in seen.items()])


def prune(db, today: date, days: int = REPEAT_DAYS, per_site: dict | None = None) -> int:
    """Delete hashes older than `days`; a site in `per_site` ({site: days})
    by its own window."""
    from .store_visits import prune_sites
    return prune_sites(db, "visitor_days", (today - timedelta(days=days)).isoformat(),
                       {s: (today - timedelta(days=n)).isoformat()
                        for s, n in (per_site or {}).items()})


def history_of(db, site: str, day: date, visitors: set[str],
               days: int = REPEAT_DAYS) -> dict[str, dict]:
    """For each visitor, what history says about the `days` before `day`:
    {visitor: {"days": set of days, "first": date str, "first_source": str}}."""
    if not visitors:
        return {}
    first = (day - timedelta(days=days - 1)).isoformat()
    out: dict[str, dict] = {}
    rows = db.execute(
        "SELECT visitor, day, kind, source FROM visitor_days WHERE site = ? AND day >= ? "
        "AND day < ? ORDER BY day", (site, first, day.isoformat())).fetchall()
    for visitor, d, kind, source in rows:
        if visitor not in visitors:
            continue
        got = out.setdefault(visitor, {"days": set(), "first": d, "first_source": ""})
        got["days"].add(d)
        if kind == "reader" and source and not got["first_source"]:
            got["first_source"] = source
    return out


def warming_up(db, site: str, day: date, days: int = REPEAT_DAYS) -> bool:
    """True until history holds hashes from `days` - 1 days before
    `day`: the visitor key was set (or the day backfilled) too recently for
    every earlier visit in the window to be known."""
    row = db.execute("SELECT MIN(day) FROM visitor_days WHERE site = ? AND day < ?",
                     (site, day.isoformat())).fetchone()
    if not row or row[0] is None:
        return True
    return date.fromisoformat(row[0]) > day - timedelta(days=days - 1)


def annotate(totals, db, site: str, day: date, days: int = REPEAT_DAYS) -> None:
    """Fill in returning / days_seen_30d on the journeys, the returning
    readers count and first-touch sources, from the hashes the tally made
    (totals.visitors, never stored on a journey) and history's earlier days.
    With no key (totals.visitors is None) everything stays None."""
    keys = getattr(totals, "visitor_keys", None)
    if keys is None or db is None:
        for j in totals.journeys or []:
            j.setdefault("returning", None)
            j.setdefault("days_seen_30d", None)
        return
    known = history_of(db, site, day, set(keys), days)
    returning = 0
    first_touch: dict[str, int] = {}
    by_source: dict[str, dict] = {}
    for j, v in zip(totals.journeys or [], keys):
        past = known.get(v)
        j["returning"] = bool(past)
        j["days_seen_30d"] = 1 + (len(past["days"]) if past else 0)
        row = by_source.setdefault(j.get("source") or "Direct or unknown",
                                   {"readers": 0, "returning": 0})
        row["readers"] += 1
        if past:
            returning += 1
            row["returning"] += 1
            src = past["first_source"] or "Direct or unknown"
            first_touch[src] = first_touch.get(src, 0) + 1
    # first_touch: by the source of the visitor's first visit within 30 days;
    # by_source: by THIS visit's source (phase 4). warming_up: fewer than 30
    # days of hashes behind the day, so "returning" is a floor.
    totals.returning = {"readers": len(keys), "returning": returning,
                        "first_touch": first_touch, "by_source": by_source,
                        "warming_up": warming_up(db, site, day, days)}
    if totals.extras and "campaigns" in totals.extras:
        totals.extras["campaigns"]["first_touch"] = first_touch
