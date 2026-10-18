"""First touch: where each visit's visitor first came from (2.12.0).

Most visits say "Direct": no referrer. Many are people who came back, and
first arrived from a search, an assistant or a post days before. For every
reader's visit this finds the visitor's FIRST known visit, by one of three
links, in this order (the first that finds an earlier visit wins):

  vid      the beacon's visitor ID (`beacon.visitor_ids`): the visit is the
           ID's when exactly one ID has a page view of the visit's landing
           page from MATCH_BEFORE seconds before its first request to
           MATCH_AFTER after it (and before the window's end), and that ID
           matches no other visit of the day. Its first touch is the ID's
           earliest page view before that (conversions.sqlite `journeys`):
           its time, page, source type and referring host (`via`, kept
           since conversions schema 5; NULL before: "(not kept)").
  address  the kept visits (people/visits.py), only while the site keeps
           addresses (`privacy.keep_ips`): the earliest kept visit of the
           same address with the same browser and system (the user agent's
           family), started before this one, within `privacy.keep_days`.
           The day's own visits are kept before this runs, so an earlier
           visit the same day counts. A forgotten address is kept as
           "(removed)" and never links.
  hash     the 30-day keyed hash (visitors.py; only with the visitor key):
           the earliest earlier day within `visitors.repeat_days` with the
           same hash and a reader's visit (its day and source type; its
           referrer is not kept), else an earlier visit the same day with
           the same hash (its labels, from memory).

None finds one: "first visit we know of" (`none`) - never a guess. No link
could be tried for the visit (no ID matched, no address kept, no key): `off`.

Each journey gets `first_touch` (labels only: no address, no ID, no hash):
{"by", "day", "start" (local, to the minute; null by hash), "source",
"via", "referrer" (referrer label), "campaign", "landing"}; or {"by":
"none"} / {"by": "off"}. And `seq` (its place in the day, the kept visit's
seq) on the site's own journeys. The day's figures go in day_extras
`first_touch` (FIGURES below). Views get none: their visits are cut by path,
so the site's kept visits would read as earlier visits of the same visit.

The second count is audit_firsttouch.py, by its own road.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import dimensions as dim

VERSION = 1
ROADS = ("vid", "address", "hash")
NONE, OFF = "none", "off"
MATCH_BEFORE, MATCH_AFTER = 2, 30      # seconds around a visit's first request
DIRECT = "Direct or unknown"
NO_REFERRER, NOT_KEPT, THIS_SITE = "(none)", "(not kept)", "(this site)"
STAMP = "%Y-%m-%dT%H:%M:%SZ"
# day_extras "first_touch":
#   roads      {"vid": bool, "address": keep_days or 0, "hash": window or 0}
#   until      the window's end (UTC stamp): no beacon page view after it is read
#   visits     the day's readers' visits
#   by         {vid, address, hash, none, off}: how each was linked (sums to visits)
#   direct     the Direct visits: {visits, known, none, off, first: {source type: n},
#              referrer: {referrer label: n}} (first and referrer sum to known)
#   returning  every visit with an earlier one known: {visits, first, referrer}
FIGURES = ("roads", "until", "visits", "by", "direct", "returning")


def _aware(when: datetime) -> datetime:
    return when if when.tzinfo else when.replace(tzinfo=timezone.utc)


def stamp(when: datetime) -> str:
    return _aware(when).astimezone(timezone.utc).strftime(STAMP)


def referrer_label(referrer: str | None, own: set) -> str:
    """The first page's referrer as the figure names it (dimensions.referrer_label,
    without the landing URL: only the referrer is kept)."""
    if not referrer:
        return NO_REFERRER
    return dim.referrer_label(referrer, own)


def via_label(host: str | None, own: set) -> str:
    """A beacon referring host (journeys.via) as a referrer label."""
    if host is None:
        return NOT_KEPT
    host = str(host).lower()
    host = host[4:] if host.startswith("www.") else host
    if not host:
        return NO_REFERRER
    return THIS_SITE if host in own or "www." + host in own else host[:60]


def roads(config: dict, folder, keyed: bool) -> dict:
    """Which links this site may use (see the module)."""
    from .beacon import visitor_ids
    from .people import policy
    from .visitors import repeat_days
    return {"vid": bool(visitor_ids(config)),
            "address": policy.keep_days(config) if policy.keep_ips(config, folder) else 0,
            "hash": repeat_days(config) if keyed else 0}


def _local(when: datetime, tz) -> datetime:
    when = _aware(when)
    return when.astimezone(tz) if tz is not None else when


def _ro(path) -> sqlite3.Connection | None:
    if path is None or not Path(path).is_file():
        return None
    db = sqlite3.connect(f"file:{Path(path).resolve()}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    return db


def _tables(db) -> set:
    return {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}


# ------------------------------------------------------------------ the links

def match_vids(cdb, site: str, visits: list[tuple], until: datetime) -> dict[int, str]:
    """{index: visitor ID} for the visits (index, first request, landing) one
    ID and only one matches, by the rule in the module."""
    if cdb is None or not visits:
        return {}
    lo = min(_aware(f) for _, f, _ in visits) - timedelta(seconds=MATCH_BEFORE)
    hi = max(_aware(f) for _, f, _ in visits) + timedelta(seconds=MATCH_AFTER)
    views: dict[str, list] = {}
    for vid, at, path in cdb.execute(
            "SELECT vid, at, path FROM journeys WHERE site = ? AND at >= ? AND at <= ? "
            "AND at < ?", (site, stamp(lo), stamp(hi), stamp(until))):
        views.setdefault(path, []).append((at, vid))
    claims: dict[str, list] = {}
    for i, first, landing in visits:
        a = stamp(_aware(first) - timedelta(seconds=MATCH_BEFORE))
        b = stamp(_aware(first) + timedelta(seconds=MATCH_AFTER))
        ids = {vid for at, vid in views.get(landing, ()) if a <= at <= b}
        if len(ids) == 1:
            claims.setdefault(ids.pop(), []).append(i)
    return {got[0]: vid for vid, got in claims.items() if len(got) == 1}


def vid_first(cdb, site: str, vid: str, first: datetime) -> dict | None:
    """The ID's earliest page view before the visit (see the module)."""
    edge = stamp(_aware(first) - timedelta(seconds=MATCH_BEFORE))
    cols = {r[1] for r in cdb.execute("PRAGMA table_info(journeys)")}
    via = "via" if "via" in cols else "NULL"
    row = cdb.execute(f"SELECT at, path, source_type, {via} AS via FROM journeys WHERE "
                      f"site = ? AND vid = ? AND at < ? ORDER BY at LIMIT 1",
                      (site, vid, edge)).fetchone()
    if row is None:
        return None
    return {"at": datetime.strptime(row["at"], STAMP).replace(tzinfo=timezone.utc),
            "source": row["source_type"] or DIRECT, "via_host": row["via"],
            "campaign": "", "landing": row["path"]}


def address_first(cdb, site: str, ip: str, browser, system, first: datetime,
                  since: str) -> dict | None:
    """The earliest kept visit of the address with the same browser and
    system, started before `first`, on or after the day `since`."""
    row = cdb.execute(
        "SELECT start, source, via, referrer, campaign, landing FROM visits WHERE site = ? "
        "AND ip = ? AND browser IS ? AND os IS ? AND start < ? AND day >= ? "
        "ORDER BY start LIMIT 1",
        (site, ip, browser or None, system or None, stamp(first), since)).fetchone()
    if row is None:
        return None
    return {"at": datetime.strptime(row["start"], STAMP).replace(tzinfo=timezone.utc),
            "source": row["source"] or DIRECT, "via": row["via"] or "",
            "referrer_raw": row["referrer"], "campaign": row["campaign"] or "",
            "landing": row["landing"] or ""}


def hash_days(hdb, site: str, day, window: int, wanted: set) -> dict[str, tuple]:
    """{hash: (earliest earlier day, its source type)} over the window."""
    if hdb is None or not wanted:
        return {}
    first = (day - timedelta(days=window - 1)).isoformat()
    out: dict[str, tuple] = {}
    for visitor, d, source in hdb.execute(
            "SELECT visitor, day, source FROM visitor_days WHERE site = ? AND kind = 'reader' "
            "AND day >= ? AND day < ? ORDER BY day", (site, first, day.isoformat())):
        if visitor in wanted and visitor not in out:
            out[visitor] = (d, source or DIRECT)
    return out


# ------------------------------------------------------------------ annotate

def annotate(totals, config: dict, folder, site: str, day, tz, until: datetime,
             history_db=None, view: bool = False) -> dict | None:
    """Give each journey its first touch and its seq, and the day its
    figures (totals.extras["first_touch"]). None when no link is on, or a
    view (see the module)."""
    journeys = list(getattr(totals, "journeys", None) or [])
    people = list(getattr(totals, "people", None) or [])
    keys = getattr(totals, "visitor_keys", None)
    if view or len(people) != len(journeys):
        return None
    for seq, j in enumerate(journeys):
        j["seq"] = seq
    on = roads(config, folder, keys is not None)
    if not any(on.values()):
        return None
    from .beacon import own_hosts
    from .conversions import store
    own = own_hosts(config)
    cpath = store.path_for(config, folder) if folder is not None else None
    cdb = _ro(cpath)
    try:
        have = _tables(cdb) if cdb is not None else set()
        vdb = cdb if on["vid"] and "journeys" in have else None
        adb = cdb if on["address"] and "visits" in have else None
        vids = match_vids(vdb, site, [(i, w["first"], j.get("landing") or "")
                                      for i, (j, w) in enumerate(zip(journeys, people))],
                          until) if vdb is not None else {}
        hashed = hash_days(history_db, site, day, on["hash"], set(keys or [])) \
            if on["hash"] and keys is not None else {}
        since = (day - timedelta(days=on["address"])).isoformat() if on["address"] else ""
        blob = _empty(on, until)
        for i, (j, who) in enumerate(zip(journeys, people)):
            got = _first(i, j, who, journeys, people, keys, vids, vdb, adb, hashed,
                         site, since, own, tz)
            j["first_touch"] = got
            _count(blob, j, got)
    finally:
        if cdb is not None:
            cdb.close()
    totals.extras = totals.extras if totals.extras is not None else {}
    totals.extras["first_touch"] = blob
    return blob


def _first(i, j, who, journeys, people, keys, vids, vdb, adb, hashed, site, since,
           own, tz) -> dict:
    first = _aware(who["first"])
    tried = False
    if i in vids:
        tried = True
        got = vid_first(vdb, site, vids[i], first)
        if got is not None:
            return _touch("vid", got, tz, via_label(got["via_host"], own),
                          got["via_host"] or "")
    if adb is not None and who.get("ip"):
        tried = True
        got = address_first(adb, site, str(who["ip"]), j.get("browser"), j.get("os"),
                            first, since)
        if got is not None:
            return _touch("address", got, tz, referrer_label(got["referrer_raw"], own),
                          got["via"])
    if keys is not None and hashed is not None and keys[i]:
        tried = True
        if keys[i] in hashed:
            d, source = hashed[keys[i]]
            return {"by": "hash", "day": d, "start": None, "source": source, "via": "",
                    "referrer": NOT_KEPT, "campaign": "", "landing": ""}
        for k in range(i):
            if keys[k] == keys[i] and _aware(people[k]["first"]) < first:
                e = journeys[k]
                got = {"at": people[k]["first"], "source": e.get("source") or DIRECT,
                       "campaign": e.get("campaign") or "", "landing": e.get("landing") or ""}
                return _touch("hash", got, tz,
                              referrer_label(people[k].get("referrer"), own), e.get("via") or "")
    return {"by": NONE if tried else OFF}


def _touch(by: str, got: dict, tz, referrer: str, via: str) -> dict:
    local = _local(got["at"], tz)
    return {"by": by, "day": local.date().isoformat(), "start": local.strftime("%Y-%m-%dT%H:%M"),
            "source": got["source"], "via": via or "", "referrer": referrer,
            "campaign": got.get("campaign") or "", "landing": got.get("landing") or ""}


def _empty(on: dict, until: datetime) -> dict:
    return {"version": VERSION, "roads": dict(on), "until": stamp(until), "visits": 0,
            "by": {k: 0 for k in (*ROADS, NONE, OFF)},
            "direct": {"visits": 0, "known": 0, NONE: 0, OFF: 0, "first": {}, "referrer": {}},
            "returning": {"visits": 0, "first": {}, "referrer": {}}}


def _count(blob: dict, j: dict, got: dict) -> None:
    by = got["by"]
    blob["visits"] += 1
    blob["by"][by] += 1
    known = by in ROADS
    parts = [blob["returning"]] if known else []
    if (j.get("source") or DIRECT) == DIRECT:
        d = blob["direct"]
        d["visits"] += 1
        d["known" if known else by] += 1
        if known:
            parts.append(d)
    for part in parts:
        if part is blob["returning"]:
            part["visits"] += 1
        part["first"][got["source"]] = part["first"].get(got["source"], 0) + 1
        part["referrer"][got["referrer"]] = part["referrer"].get(got["referrer"], 0) + 1


def day_end(day, tz) -> datetime:
    """The end of the local day `day` (the daily run's window end)."""
    from datetime import time
    nxt = datetime.combine(day + timedelta(days=1), time(0))
    return nxt.replace(tzinfo=tz) if tz is not None else nxt.replace(tzinfo=timezone.utc)


def for_app(blob) -> dict | None:
    """A day's blob as app.json carries it: the counts, and the links on as
    true/false (never summed into a range)."""
    if not isinstance(blob, dict):
        return None
    out = {k: blob[k] for k in ("visits", "by", "direct", "returning") if k in blob}
    out["roads"] = {k: bool((blob.get("roads") or {}).get(k)) for k in ROADS}
    return out
