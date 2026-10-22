"""One visitor's every visit: the visitor drawer's timeline (2.12.0). A listing,
never a figure.

`visitor(config, folder, site, day, seq)` starts from one kept visit (the
day's place of a journey, `seq`, which the anonymous journey carries) and
finds, from what is kept:

    visits       every kept visit of the same address with the same browser
                 and system (the user agent's family: the first-touch rule,
                 firsttouch.py), newest first; only while the site keeps
                 addresses, inside privacy.keep_days. A site that keeps
                 them shortened links by the shortened address: a weaker
                 link (`linked_by` "short_address"), since one shortened
                 address can be several people
    script       when a visitor ID is matched to one of those visits (its
                 page view of the landing page within seconds of the visit's
                 first request, one ID only: matched by time, said so), the
                 ID's other page views, grouped into visits (30 minutes
                 apart), that no kept visit covers: "seen by the script"
    leads        the leads made from 30 seconds before to 2 minutes after a
                 form the visits sent (matched by time, never certain)
    conversions  the matched visitor IDs' conversions (test rows left out)

The oldest is the first touch. Admins and owners only (people/api.py), and
each answer is written to the audit log: the kind, never the value. The
answer holds no address and no visitor ID: labels, times and pages only.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import timedelta
from pathlib import Path

from ..conversions import store
from . import policy

LIMIT = 500
GAP = 30 * 60
FIELDS = ("day", "seq", "start", "end", "source", "via", "referrer", "campaign", "landing",
          "exit", "country", "device", "browser", "os", "pages", "seconds")


def _ro(path):
    if path is None or not Path(path).is_file():
        return None
    db = sqlite3.connect(f"file:{Path(path).resolve()}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    return db


def _visit(r) -> dict:
    out = {k: r[k] for k in FIELDS}
    # city (schema 5): only when a city file named one (logs.city_db); NULL stays None.
    out["city"] = r["city"] if "city" in r.keys() else None
    for key in ("trail", "posts"):
        try:
            out[key] = json.loads(r[key] or "[]")
        except ValueError:
            out[key] = []
    out["kind"] = "kept"
    return out


def visitor(config: dict, folder, site: str, day: str, seq: int) -> dict:
    """The visitor of the kept visit (site, day, seq): see the module."""
    from ..firsttouch import match_vids
    kept = policy.describe(config, folder)
    out = {"ok": True, "found": False, "kept": kept, "visits": [], "leads": [],
           "conversions": [], "withheld": {},
           "linked_by": "short_address" if kept["ip_mode"] == policy.SHORT else "address"}
    if not kept["keep_ips"]:
        out["why"] = "This site keeps no IP addresses with its visits, so its visits cannot be followed across days here. The first touch on each visit is by the visitor ID or the 30-day code."
        return out
    path = store.path_for(config, folder) if folder is not None else None
    db = _ro(path)
    if db is None:
        out["why"] = "No visit is kept yet."
        return out
    with closing(db):
        have = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        if "visits" not in have:
            out["why"] = "No visit is kept yet."
            return out
        row = db.execute("SELECT * FROM visits WHERE site = ? AND day = ? AND seq = ?",
                         (site, day, int(seq))).fetchone()
        if row is None:
            out["why"] = (f"This visit is not kept with its address (visits are kept "
                          f"{kept['keep_days']} days, and today's are written by each live run).")
            return out
        if row["ip"] == "(removed)":
            out["why"] = "This visitor asked to be forgotten: the visit counts, its person does not show."
            return out
        cut = _cut(day, kept["keep_days"])
        rows = db.execute("SELECT * FROM visits WHERE site = ? AND ip = ? AND browser IS ? AND "
                          "os IS ? AND day >= ? ORDER BY start DESC LIMIT ?",
                          (site, row["ip"], row["browser"], row["os"], cut, LIMIT)).fetchall()
        visits = [_visit(r) for r in rows]
        ip = row["ip"]
        vids = {}
        if "journeys" in have:
            from ..beacon import visitor_ids
            if visitor_ids(config):
                vids = match_vids(db, site, [(i, store.parse(v["start"]), v["landing"] or "")
                                             for i, v in enumerate(visits)],
                                  store.parse(max(v["end"] for v in visits)) +
                                  timedelta(seconds=60))
        script = _script(db, site, set(vids.values()), visits) if vids else []
        conv = _conversions(db, site, set(vids.values())) if vids and "conversions" in have \
            else []
    for i, v in enumerate(visits):
        v["linked"] = "this" if (v["day"], v["seq"]) == (day, int(seq)) else "address"
        v["vid_matched"] = i in vids
    allv = sorted(visits + script, key=lambda v: v["start"], reverse=True)
    allv[-1]["first"] = True
    out.update(found=True, visits=allv, conversions=conv,
               leads=_leads(config, folder, visits, ip),
               withheld=_withheld(config, folder, site, {v["day"] for v in visits}),
               vid_matched=bool(vids))
    return out


def _cut(day: str, keep: int) -> str:
    from datetime import date
    return (date.fromisoformat(day) - timedelta(days=int(keep))).isoformat()


def _script(db, site: str, vids: set, visits: list) -> list[dict]:
    """The IDs' page views no kept visit covers, as visits."""
    cols = {r[1] for r in db.execute("PRAGMA table_info(journeys)")}
    via = "via" if "via" in cols else "NULL AS via"
    spans = [(store.parse(v["start"]) - timedelta(seconds=2),
              store.parse(v["end"]) + timedelta(seconds=60)) for v in visits]
    views = []
    for vid in sorted(vids):
        views += [dict(r) for r in db.execute(
            f"SELECT at, path, source_type, {via} FROM journeys WHERE site = ? AND vid = ? "
            f"ORDER BY at LIMIT ?", (site, vid, LIMIT))]
    views.sort(key=lambda r: r["at"])
    groups: list[list] = []
    for r in views:
        when = store.parse(r["at"])
        if any(a <= when <= b for a, b in spans):
            continue
        if groups and (when - store.parse(groups[-1][-1]["at"])).total_seconds() <= GAP:
            groups[-1].append(r)
        else:
            groups.append([r])
    out = []
    for g in groups:
        start, end = store.parse(g[0]["at"]), store.parse(g[-1]["at"])
        out.append({"kind": "script", "day": None, "seq": None, "start": g[0]["at"],
                    "end": g[-1]["at"], "source": g[0]["source_type"] or "Direct or unknown",
                    "via": g[0]["via"] or "", "referrer": None, "campaign": None,
                    "landing": g[0]["path"], "exit": g[-1]["path"], "country": None,
                    "device": None, "browser": None, "os": None, "pages": len(g),
                    "seconds": int((end - start).total_seconds()),
                    "trail": [[r["path"], "page", int((store.parse(r["at"]) - start)
                                                      .total_seconds())] for r in g[:50]],
                    "posts": [], "linked": "vid"})
    return out


def _conversions(db, site: str, vids: set) -> list[dict]:
    cols = {r[1] for r in db.execute("PRAGMA table_info(conversions)")}
    test = " AND test = 0" if "test" in cols else ""
    out = []
    for vid in sorted(vids):
        out += [dict(r) for r in db.execute(
            f"SELECT id, action, stage, at, tool, external_ref, source_type, landing FROM "
            f"conversions WHERE site = ? AND vid = ?{test} ORDER BY at", (site, vid))]
    return sorted(out, key=lambda r: r["at"], reverse=True)


def _leads(config: dict, folder, visits: list, ip: str) -> list[dict]:
    """Leads made just after one of the visits sent a form, with the visit."""
    from .lookup import _leads_at_posts
    full = policy.identity_full(config, folder)
    try:
        found = _leads_at_posts(config, [dict(v, ip=ip, id=(v["day"], v["seq"]))
                                         for v in visits], full)
    except sqlite3.Error:
        return []
    from .lookup import _lead_rows, _lead_where
    where, args = _lead_where("id", {r["lead"] for r in found})
    try:
        rows = {str(r["id"]): r for r in _lead_rows(config, f"WHERE {where}", args, True,
                                                     False)} if where else {}
    except sqlite3.Error:
        rows = {}
    out = []
    for r in found:
        lead = rows.get(str(r["lead"])) or {}
        out.append({"lead": str(r["lead"]), "visit_start": r["start"],
                    "created_at": lead.get("created_at"), "type": lead.get("type"),
                    "status": lead.get("status"), "left_out": lead.get("left_out")})
    return out


def _withheld(config: dict, folder, site: str, days: set) -> dict:
    from .lookup import _withheld as held
    return held(config, folder, site, days)
