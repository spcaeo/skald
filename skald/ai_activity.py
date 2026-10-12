"""Today's AI activity, one row per event, for the private page.

Every assistant fetch (to train or index, or for a live question) and every
page a reader loaded after arriving from an assistant: time, name, kind,
path, status, country and - the owner's decision, 2026-10-07 - the address,
read from today's raw log. The list lives in the live snapshot (beside
history, not in it) and in ai_activity.json behind the password; the
address is never written to history, an email or a CSV export.

Whether the visitor was seen before comes from the 30 days of keyed hashes
(visitors.py): repeat, times_seen_30d (distinct days, today included) and
first_seen. Without the visitor key those are None.
"""
from __future__ import annotations

import heapq
from collections import Counter
from datetime import date, timezone

from .classify import Group, Tier
from .countries import NAMES

LIMIT = 200


class AIEvents:
    """An observer for the tally pass: keeps the LIMIT newest events and a
    count per name for all of them."""

    def __init__(self, key: bytes | None = None, hidden=None) -> None:
        self.key = key
        # privacy.forgotten: an address someone asked us to forget.
        self.hidden = hidden or (lambda ip: False)
        self.latest: list[tuple] = []
        self.seq = 0
        self.by_name: dict[str, Counter] = {}
        self.kind_of: dict[str, str] = {}
        self.visitors: dict[str, set] = {}
        self.total = 0

    def __call__(self, hit, verdict) -> None:
        if verdict.group is Group.ANSWER_ENGINE and verdict.tier:
            kind, name, family = verdict.tier.value, verdict.engine, verdict.engine
        elif verdict.group is Group.PEOPLE and verdict.tier is Tier.CITED and hit.is_page:
            from .visitors import reader_family
            kind, name, family = "referred", verdict.engine, reader_family(hit.user_agent)
        else:
            return
        visitor = None
        if self.key is not None:
            from .visitors import visitor_hash
            visitor = visitor_hash(self.key, hit.address, family)
            self.visitors.setdefault(name, set()).add(visitor)
        self.total += 1
        self.by_name.setdefault(name, Counter())["events"] += 1
        self.kind_of[name] = kind
        when = hit.when if hit.when.tzinfo else hit.when.replace(tzinfo=timezone.utc)
        self.seq += 1
        item = (when, self.seq, kind, name, hit.path[:100], hit.status,
                (hit.country or "").upper(), hit.address, visitor)
        if len(self.latest) < LIMIT:
            heapq.heappush(self.latest, item)
        elif item > self.latest[0]:
            heapq.heapreplace(self.latest, item)

    def result(self, tz, db=None, site: str = "", day: date | None = None) -> dict:
        """The JSON-ready block, with repeat facts looked up in history's
        earlier days (a read-only connection; None when unavailable)."""
        from .visitors import history_of
        events = sorted(self.latest, reverse=True)
        known = {}
        if self.key is not None and db is not None and day is not None:
            wanted = set()
            for got in self.visitors.values():
                wanted |= got
            known = history_of(db, site, day, wanted)
        out = []
        for when, _, kind, name, path, status, cc, address, visitor in events:
            past = known.get(visitor) if visitor else None
            have = self.key is not None and db is not None
            out.append({
                "at": when.astimezone(tz).isoformat(timespec="seconds"),
                "name": name, "kind": kind, "path": path, "status": int(status),
                "country": cc, "country_name": NAMES.get(cc, ""),
                "ip": "(removed)" if self.hidden(address) else address,
                "repeat": (bool(past) if have else None),
                "times_seen_30d": ((1 + len(past["days"]) if past else 1) if have else None),
                "first_seen": ((past["first"] if past else day.isoformat()) if have and day
                               else None),
            })
        by_name = {}
        for name, c in self.by_name.items():
            seen = self.visitors.get(name)
            repeat = (sum(1 for v in seen if v in known) if seen is not None and db is not None
                      else None)
            by_name[name] = {"kind": self.kind_of[name], "events": int(c["events"]),
                             "visitors": len(seen) if seen is not None else None,
                             "repeat": repeat}
        return {"events": out, "total": self.total, "by_name": by_name}
