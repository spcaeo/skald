"""The second count of first touch (firsttouch.py): where each visit's
visitor first came from, recounted by the audit's own road.

Registered in audit_more.RECOUNTS, so it rides on audit.recount's one pass
over the raw log. `visit` gets each people visit as the audit split it (its
own visit rule, page rule and labels, audit_labels.py); `compare` links each
one again by the documented rule (DATA-CONTRACT-PEOPLE.md, "First touch"),
with its own SQL on the files the links read - conversions.sqlite (the
visitor IDs' page views, the kept visits) and the history's 30-day keyed
hashes - opened read-only, and its own keyed hash of the address
(audit_extras.keyed). It counts the day's figures and sets them against
the stored day_extras `first_touch` (or the live snapshot's); a mismatch
withholds the day like any other.

Which links were on (`roads`: visitor IDs, kept addresses with their days,
the hash window) is a setting, not a figure: it is read from the stored
blob, and the window's end is the audit's own. Nothing from firsttouch.py,
dimensions.py, visits.py or visitors.py is called.

The links read inputs that are kept only for a while: an ID's page views
`journeys.vid_days` (30) unless it converted, the kept visits
`privacy.keep_days`, the 30-day codes `visitors.repeat_days`. A day audited
after inputs it could have read were pruned cannot be linked again the same
way, so, as with the visitor hashes (audit.py), its links are "not checkable
(inputs expired)" - `expired` says so and audit.py names it - never a
mismatch. Only the day's visit count, which needs no kept input, is still
compared. Pruned is shown by the files, like the hashes: a stored day the
count could have read (its own blob says the link was on and it had visits)
whose inputs are gone now - page views of IDs that never converted from
before the earliest one still kept (prunes cut at UTC midnight), no kept
visit of that day, no code of that day. A visitor-ID link counts whether or
not the day used it (a pruned view can make an ambiguous match single); a
kept visit or a code only when the day linked a visit by it.
"""
from __future__ import annotations

import json
import sqlite3
from collections import Counter
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

from .audit_extras import keyed, secret
from .audit_labels import _GOOGLE_SEARCH, _MAIL_HOSTS, _bare, _tags
from .audit_people import _site, _store

BEFORE, AFTER = 2, 30
VID_DAYS = 30                 # journeys.vid_days when not set
DIRECT = "Direct or unknown"
LINKS = ("vid", "address", "hash")
FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def _utc(when: datetime) -> str:
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return when.astimezone(timezone.utc).strftime(FORMAT)


def _history(config: dict) -> Path | None:
    raw = ((config or {}).get("_resolved") or {}).get("history_db") or \
        ((config or {}).get("history") or {}).get("db")
    if not raw or not Path(str(raw)).expanduser().is_absolute():
        return None
    return Path(str(raw)).expanduser()


def _open(path) -> sqlite3.Connection | None:
    if path is None or not Path(path).is_file():
        return None
    return sqlite3.connect(f"file:{Path(path).resolve()}?mode=ro", uri=True)


def ref_label(referrer, own: set) -> str:
    """The audit's referrer label of a first page (the referrer only)."""
    host = _bare(referrer) if referrer else ""
    if not host:
        return "(none)"
    if host in own or "www." + host in own:
        return "(this site)"
    if _GOOGLE_SEARCH.search(host) and host not in _MAIL_HOSTS and \
            _tags(str(referrer).split("#", 1)[0]).get("udm", "").strip() == "50":
        return host[:60] + " (AI Mode)"
    return host[:60]


def host_label(host, own: set) -> str:
    """A beacon page view's referring host as a label: NULL was not kept."""
    if host is None:
        return "(not kept)"
    host = str(host).lower()
    if host.startswith("www."):
        host = host[4:]
    if not host:
        return "(none)"
    return "(this site)" if host in own or "www." + host in own else host[:60]


def _day_span(day: date, tz) -> tuple[datetime, datetime]:
    """A local day as UTC instants [start, end)."""
    zone = tz or timezone.utc
    start = datetime.combine(day, time(0), tzinfo=zone)
    end = datetime.combine(day + timedelta(days=1), time(0), tzinfo=zone)
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)


class Recount:
    def __init__(self, config: dict, day, tz, own: set) -> None:
        self.config, self.day, self.tz, self.own = config, day, tz, set(own or ())
        self.key = secret(config)
        self.end: datetime | None = None
        self.visits: list[dict] = []
        self.expired: list[str] = []         # what audit.py says is not checkable

    def set_window(self, start, end) -> None:
        self.end = end

    def visit(self, lines: list, is_page, labels: dict | None) -> None:
        if labels is None or not lines:
            return
        pages = [l for l in lines if is_page(l)]
        family = f"{labels['browser']}/{labels['os']}"
        self.visits.append({
            "first": lines[0].when, "address": lines[0].address,
            "browser": labels["browser"], "os": labels["os"], "source": labels["source"],
            "landing": labels["landing"], "referrer": pages[0].referrer if pages else "",
            "hash": keyed(self.key, pages[0].address, family) if self.key and pages else None})

    # ------------------------------------------------------------ the links
    def _ids(self, db, site: str) -> dict[int, str]:
        if db is None or not self.visits or self.end is None:
            return {}
        firsts = [v["first"] for v in self.visits]
        rows = db.execute("SELECT vid, at, path FROM journeys WHERE site = ? AND at >= ? AND "
                          "at <= ? AND at < ?",
                          (site, _utc(min(firsts) - timedelta(seconds=BEFORE)),
                           _utc(max(firsts) + timedelta(seconds=AFTER)), _utc(self.end))
                          ).fetchall()
        claimed: dict[str, list] = {}
        for i, v in enumerate(self.visits):
            lo = _utc(v["first"] - timedelta(seconds=BEFORE))
            hi = _utc(v["first"] + timedelta(seconds=AFTER))
            ids = {vid for vid, at, path in rows if path == v["landing"] and lo <= at <= hi}
            if len(ids) == 1:
                claimed.setdefault(next(iter(ids)), []).append(i)
        return {idx[0]: vid for vid, idx in claimed.items() if len(idx) == 1}

    def _link(self, i: int, v: dict, ids: dict, cdb, hdb_days: dict, roads: dict,
              site: str, have: set) -> tuple[str, str | None, str | None]:
        """(how, first source, first referrer label) for one visit."""
        tried = False
        if i in ids:
            tried = True
            cols = [r[1] for r in cdb.execute("PRAGMA table_info(journeys)")]
            pick = "via" if "via" in cols else "NULL"
            row = cdb.execute(f"SELECT source_type, {pick} FROM journeys WHERE site = ? AND "
                              f"vid = ? AND at < ? ORDER BY at LIMIT 1",
                              (site, ids[i], _utc(v["first"] - timedelta(seconds=BEFORE)))
                              ).fetchone()
            if row is not None:
                return "vid", row[0] or DIRECT, host_label(row[1], self.own)
        if roads.get("address") and cdb is not None and "visits" in have and v["address"]:
            tried = True
            since = (self.day - timedelta(days=int(roads["address"]))).isoformat()
            row = cdb.execute("SELECT source, referrer FROM visits WHERE site = ? AND ip = ? AND "
                              "browser IS ? AND os IS ? AND start < ? AND day >= ? "
                              "ORDER BY start LIMIT 1",
                              (site, v["address"], v["browser"] or None, v["os"] or None,
                               _utc(v["first"]), since)).fetchone()
            if row is not None:
                return "address", row[0] or DIRECT, ref_label(row[1], self.own)
        if roads.get("hash") and v["hash"]:
            tried = True
            if v["hash"] in hdb_days:
                return "hash", hdb_days[v["hash"]], "(not kept)"
            same = [w for w in self.visits if w["hash"] == v["hash"] and w["first"] < v["first"]]
            if same:
                w = min(same, key=lambda x: x["first"])
                return "hash", w["source"], ref_label(w["referrer"], self.own)
        return ("none" if tried else "off"), None, None

    def _hashes(self, window: int, site: str) -> dict[str, str]:
        db = _open(_history(self.config))
        if db is None or not window:
            return {}
        wanted = {v["hash"] for v in self.visits if v["hash"]}
        out: dict[str, str] = {}
        try:
            for visitor, source in db.execute(
                    "SELECT visitor, source FROM visitor_days WHERE site = ? AND "
                    "kind = 'reader' AND day >= ? AND day < ? ORDER BY day",
                    (site, (self.day - timedelta(days=int(window) - 1)).isoformat(),
                     self.day.isoformat())):
                if visitor in wanted and visitor not in out:
                    out[visitor] = source or DIRECT
        except sqlite3.Error:
            return {}
        finally:
            db.close()
        return out

    def counted(self, roads: dict) -> dict:
        site = _site(self.config)
        self.visits.sort(key=lambda v: v["first"])
        cdb = _open(_store(self.config))
        got = {"visits": 0, "by": Counter(), "direct": Counter(), "direct_first": Counter(),
               "direct_referrer": Counter(), "returning": 0, "first": Counter(),
               "referrer": Counter()}
        try:
            have = {r[0] for r in cdb.execute("SELECT name FROM sqlite_master WHERE "
                                              "type = 'table'")} if cdb is not None else set()
            ids = self._ids(cdb, site) if roads.get("vid") and "journeys" in have else {}
            days = self._hashes(roads.get("hash") or 0, site) if self.key else {}
            for i, v in enumerate(self.visits):
                how, source, ref = self._link(i, v, ids, cdb, days, roads, site, have)
                got["visits"] += 1
                got["by"][how] += 1
                known = how in LINKS
                if known:
                    got["returning"] += 1
                    got["first"][source] += 1
                    got["referrer"][ref] += 1
                if v["source"] == DIRECT:
                    got["direct"]["visits"] += 1
                    got["direct"]["known" if known else how] += 1
                    if known:
                        got["direct_first"][source] += 1
                        got["direct_referrer"][ref] += 1
        finally:
            if cdb is not None:
                cdb.close()
        return got

    # ------------------------------------------------------------ expired inputs
    def gone(self, blob: dict) -> list[str]:
        """The links whose inputs the day could have read are pruned now
        (see the module): [] when every one is still kept."""
        roads, by = blob.get("roads") or {}, blob.get("by") or {}
        hdb = _open(_history(self.config))
        if hdb is None:
            return []
        cdb = _open(_store(self.config))
        site, x = _site(self.config), self.day
        start_x, end_x = _day_span(x, self.tz)
        out: list[str] = []
        try:
            back = max(int(roads.get("address") or 0), int(roads.get("hash") or 0),
                       self._vid_days() + 1) + 1
            blobs = {}
            for d, data in hdb.execute(
                    "SELECT day, data FROM day_extras WHERE site = ? AND kind = 'first_touch' "
                    "AND day >= ? AND day <= ?",
                    (site, (x - timedelta(days=back)).isoformat(), x.isoformat())):
                try:
                    blobs[d] = json.loads(data)
                except (TypeError, ValueError):
                    continue

            def had(d: date, road: str) -> bool:
                b = blobs.get(d.isoformat())
                return isinstance(b, dict) and bool((b.get("roads") or {}).get(road)) \
                    and int(b.get("visits") or 0) > 0

            have = {r[0] for r in cdb.execute("SELECT name FROM sqlite_master WHERE "
                                              "type = 'table'")} if cdb is not None else set()
            # The count ran once the day was over: its prune had cut at UTC midnight
            # vid_days before that date at the earliest (cli.prune_kept, store.prune).
            # Page views were kept at all: one still is, or the day linked a visit by ID.
            if roads.get("vid") and "journeys" in have and (int(by.get("vid") or 0) or cdb.execute(
                    "SELECT 1 FROM journeys WHERE site = ? LIMIT 1", (site,)).fetchone()):
                lo = datetime.combine(end_x.date() - timedelta(days=self._vid_days()), time(0),
                                      tzinfo=timezone.utc)
                kept = cdb.execute(
                    "SELECT MIN(at) FROM journeys j WHERE site = ? AND NOT EXISTS (SELECT 1 "
                    "FROM conversions c WHERE c.site = j.site AND c.vid = j.vid)",
                    (site,)).fetchone()[0] if "conversions" in have else cdb.execute(
                    "SELECT MIN(at) FROM journeys WHERE site = ?", (site,)).fetchone()[0]
                cut = end_x if kept is None else datetime.combine(
                    datetime.strptime(kept, FORMAT).date(), time(0), tzinfo=timezone.utc)
                hi = min(cut, end_x)
                d = lo.astimezone(self.tz or timezone.utc).date()
                while lo < hi and d <= x:
                    a, b = _day_span(d, self.tz)
                    if b > lo and a < hi and had(d, "vid"):
                        out.append("vid")
                        break
                    d += timedelta(days=1)
            keep = int(roads.get("address") or 0)
            if keep and int(by.get("address") or 0) and "visits" in have:
                first = max(x - timedelta(days=keep), end_x.date() - timedelta(days=keep))
                kept_days = {r[0] for r in cdb.execute(
                    "SELECT DISTINCT day FROM visits WHERE site = ? AND day >= ? AND day <= ?",
                    (site, first.isoformat(), x.isoformat()))}
                d = first
                while d <= x:
                    if d.isoformat() not in kept_days and had(d, "address"):
                        out.append("address")
                        break
                    d += timedelta(days=1)
            window = int(roads.get("hash") or 0)
            if window and int(by.get("hash") or 0):
                first = x - timedelta(days=window - 1)
                coded = {r[0] for r in hdb.execute(
                    "SELECT DISTINCT day FROM visitor_days WHERE site = ? AND day >= ? AND day < ?",
                    (site, first.isoformat(), x.isoformat()))}
                d = first
                while d < x:
                    if d.isoformat() not in coded and had(d, "hash"):
                        out.append("hash")
                        break
                    d += timedelta(days=1)
        except sqlite3.Error:
            return out
        finally:
            hdb.close()
            if cdb is not None:
                cdb.close()
        return out

    def _vid_days(self) -> int:
        try:
            return max(1, int(((self.config or {}).get("journeys") or {}).get("vid_days")
                              or VID_DAYS))
        except (TypeError, ValueError):
            return VID_DAYS

    def compare(self, stored: dict, same, problems: list) -> None:
        blob = stored.get("first_touch")
        if not isinstance(blob, dict):
            return                           # not counted that day (no link on, or a view)
        if self.gone(blob):
            # Its links cannot be made again: not checkable, never a mismatch.
            self.expired = ["first touch"]
            same("first touch: visits", int(blob.get("visits", 0)), len(self.visits))
            return
        if self.end is not None and blob.get("until") != _utc(self.end):
            problems.append("first touch: the stored window's end is not the recount's")
        got = self.counted(blob.get("roads") or {})
        same("first touch: visits", int(blob.get("visits", 0)), got["visits"])
        for how in (*LINKS, "none", "off"):
            same(f"first touch: visits linked by {how}", int((blob.get("by") or {}).get(how, 0)),
                 got["by"][how])
        d = blob.get("direct") or {}
        for field in ("visits", "known", "none", "off"):
            same(f"first touch: direct visits, {field}", int(d.get(field, 0)),
                 got["direct"][field])
        _each(same, "first touch: direct visits first from", d.get("first"), got["direct_first"])
        _each(same, "first touch: direct visits first referrer", d.get("referrer"),
              got["direct_referrer"])
        r = blob.get("returning") or {}
        same("first touch: returning visits", int(r.get("visits", 0)), got["returning"])
        _each(same, "first touch: returning visits first from", r.get("first"), got["first"])
        _each(same, "first touch: returning visits first referrer", r.get("referrer"),
              got["referrer"])


def _each(same, what: str, stored, counted: Counter) -> None:
    stored = stored or {}
    for k in sorted(set(stored) | set(counted)):
        same(f"{what} {k}", int(stored.get(k, 0)), int(counted.get(k, 0)))
