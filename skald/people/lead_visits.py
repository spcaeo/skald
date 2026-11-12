"""A lead's own visits, in order (#30, 2.46.5). A listing, never a figure.

For the conversions a person search found (people/lookup.py), the server-log
visits that are that person's, each marked how it is known:

    proven   the only visit that sent a form (a POST) within PROVEN_SECONDS of
             a conversion's time. The site's server reports a lead the moment
             its form is sent, so the visit that sent it is the lead's. Two or
             more visits in that window: none is proven.
    likely   another visit from the same address and the same browser (user
             agent) as a proven one, from AROUND_HOURS before the first proven
             visit to AROUND_HOURS after the last conversion. Likely the same
             person, never certain: an office or a phone network shares an
             address. A visit whose address was dropped (privacy, "(removed)")
             or that has no browser line links no other visit.

`path` returns the visits oldest first, each with its `link` (proven or
likely), `why`, and the conversion steps it sent (`steps`); `first` is the
earliest visit's source (where the person first came from); `unmatched` the
steps no visit is proven for (a payment page, a tool's own webhook, a form
sent from another network). Nothing here is counted into any figure; only
callers who may see a person (admins and owners) get it, through `person`.
"""
from __future__ import annotations

from datetime import timedelta

from ..conversions import store
from .visits import REMOVED, _row, posted_near

PROVEN_SECONDS = 10
AROUND_HOURS = 24
LIMIT = 200


def _step(c: dict) -> dict:
    return {"action": c.get("action"), "stage": c.get("stage"), "at": c.get("at"),
            "tool": c.get("tool"), "ref": c.get("external_ref")}


def path(db, site: str, conversions: list[dict]) -> dict:
    """The person's visits, proven and likely, oldest first (see the module)."""
    rows = sorted((c for c in conversions if c.get("at") and not c.get("test")),
                  key=lambda c: (str(c["at"]), c.get("id") or 0))
    visits: dict = {}
    unmatched = []
    for c in rows:
        near = posted_near(db, site, c["at"], before=PROVEN_SECONDS, after=PROVEN_SECONDS)
        if len(near) != 1:
            unmatched.append({**_step(c), "why": "no visit sent a form at its time" if not near
                              else f"{len(near)} visits sent a form at its time"})
            continue
        v = near[0]
        key = (v["day"], v["seq"])
        got = visits.setdefault(key, {**v, "link": "proven", "steps": [],
                                      "why": "the only visit that sent a form at the lead's time"})
        got["steps"].append(_step(c))
    proven = list(visits.values())
    if proven:
        first = min(store.parse(v["start"]) for v in proven)
        last = max([store.parse(c["at"]) for c in rows] + [store.parse(v["end"]) for v in proven])
        lo = store.stamp(first - timedelta(hours=AROUND_HOURS))
        hi = store.stamp(last + timedelta(hours=AROUND_HOURS))
        # A dropped address ("(removed)", privacy) or a missing browser links nobody.
        pairs = {(v["ip"], v.get("user_agent") or "") for v in proven}
        for ip, agent in sorted((i, a) for i, a in pairs if i and i != REMOVED and a):
            for r in db.execute("SELECT * FROM visits WHERE site = ? AND ip = ? AND "
                                "COALESCE(user_agent, '') = ? AND start >= ? AND start <= ? "
                                "ORDER BY start LIMIT ?", (site, ip, agent, lo, hi, LIMIT)):
                v = _row(r)
                visits.setdefault((v["day"], v["seq"]), {
                    **v, "link": "likely", "steps": [],
                    "why": "the same address and browser as a proven visit"})
    ordered = sorted(visits.values(), key=lambda v: (v["start"], v["seq"]))
    head = ordered[0] if ordered else None
    return {"visits": ordered, "unmatched": unmatched,
            "first": {k: head.get(k) for k in ("start", "source", "via", "referrer", "campaign",
                                                 "landing", "link")} if head else None}

