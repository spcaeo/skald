"""Look a person up, and list what the figures leave out. Listings, never figures.

`person(q)` takes one address, email, visitor ID or lead reference and finds,
from what is kept:

    visits       every visit kept with that address (people/visits.py), with
                 its day flagged when the day is withheld (its figures did
                 not reconcile). On a site that keeps addresses shortened
                 (privacy.keep_ips: short) a full address finds the visits
                 of its shortened form: `query.short` names it, and the page
                 says one shortened address can be several people
    requests     the address's requests in the private Recent requests feed
                 (the last 6 hours): all there is when addresses are not kept
    leads        the site's lead database rows (read-only), spam, duplicates
                 and test included
    conversions  every conversion row, test and cancelled ones included, and
                 the rows a sync removed
    journeys     the visitor IDs' page views (beacon.visitor_ids)
    candidates   for each lead: the visits that sent a form within two minutes
                 of it; for an address: the leads made just after one of its
                 visits sent a form - matched by time, never certain, said so

and links them: a conversion's visitor ID, email (identity) and reference
lead to more conversions; a lead row's id, session (when it is a visitor ID)
and email lead to its conversions. An address is linked to a lead only
through `candidates`: the lead database keeps no address.

`left_out(...)` lists the leads and conversions the figures leave out: spam,
duplicates and test leads (the lead database's status, or a flag saying
test), and conversions marked test. `conversions_listing(kind)` lists the
cancelled (cancelled, no-show), removed and test conversions with their row
and journey. Names and emails only for a caller who may see private data
and only when the site keeps them.

Everything is read read-only: a lookup never creates or changes a file.
"""
from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from ..conversions import SITE_VID, store
from . import policy

LIMIT = 500
EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,255}$")
REF = re.compile(r"^[\w.:/@+-]{1,300}$")
CANCELLED = ("cancelled", "no_show")
LEAD_COLUMNS = ("id", "created_at", "updated_at", "type", "status", "page", "first_touch",
                "last_touch", "session_id", "ip_country", "flags")


class Invalid(ValueError):
    """A search that is not an address, an email, a visitor ID or a reference."""


def kind_of(q: str) -> tuple[str, str]:
    """(kind, value): ip, email, vid or lead."""
    q = str(q or "").strip()
    if not q or len(q) > 320:
        raise Invalid("Type an IP address, an email, a visitor ID or a lead's id.")
    try:
        return "ip", str(ipaddress.ip_address(q))
    except ValueError:
        pass
    if "@" in q:
        if not EMAIL.match(q):
            raise Invalid("That is not an email address.")
        return "email", q.lower()
    if SITE_VID.match(q):
        return "vid", q
    if not REF.match(q):
        raise Invalid("Type an IP address, an email, a visitor ID or a lead's id.")
    return "lead", q


@contextmanager
def _ro(path):
    """A file opened read-only, or None when it is not there."""
    if path is None or not Path(path).is_file():
        yield None
        return
    db = sqlite3.connect(f"file:{Path(path).resolve()}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    try:
        yield db
    finally:
        db.close()


def _tables(db) -> set:
    return {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}


def _email_ids(db, site: str, email: str) -> set[int]:
    row = db.execute("SELECT value FROM meta WHERE key = 'hash_key'").fetchone()
    if row is None:
        return set()
    digest = hmac.new(bytes.fromhex(row[0]), email.strip().lower().encode(),
                      hashlib.sha256).hexdigest()
    return {r[0] for r in db.execute("SELECT id FROM identities WHERE site = ? AND "
                                     "email_hash = ?", (site, digest))}


# ----------------------------------------------------------- lead database

def _lead_rows(config: dict, where: str = "", args=(), private: bool = False,
               full: bool = False) -> list[dict]:
    """Lead database rows (newest first), read-only; [] when not set up."""
    from ..leads import db_path, touch_source, _touch
    path = db_path(config or {})
    if path is None or not Path(path).is_file():
        return []
    with _ro(path) as db:
        have = {r[1] for r in db.execute("PRAGMA table_info(submissions)")}
        if "id" not in have or "created_at" not in have:
            return []
        wanted = LEAD_COLUMNS + (("email", "name") if private and full else ())
        picked = [c if c in have else f"NULL AS {c}" for c in wanted]
        rows = db.execute(f"SELECT {', '.join(picked)} FROM submissions {where} "
                          f"ORDER BY created_at DESC LIMIT {LIMIT}", args).fetchall()
    from ..beacon import visitor_ids
    keeps_vid = visitor_ids(config)
    out = []
    for r in rows:
        row = {k: r[k] for k in wanted}
        first, last = _touch(row.pop("first_touch")), _touch(row.pop("last_touch"))
        row["first_source"] = touch_source(first) if first else None
        row["last_source"] = touch_source(last or first) if (last or first) else None
        row["landing"] = (first or {}).get("landingPath") if isinstance(first, dict) else None
        row["status"] = str(row.get("status") or "new").lower()
        row["test"] = row["status"] == "test" or "test" in str(row.get("flags") or "").lower()
        row["left_out"] = row["status"] in ("spam", "duplicate") or row["test"]
        session = str(row.pop("session_id") or "")
        # A visitor ID only for admins, and only where the site has visitor IDs
        # on (beacon.visitor_ids): a site's session column is no visitor else.
        row["vid"] = session if private and keeps_vid and SITE_VID.match(session) else None
        row.pop("flags", None)
        out.append(row)
    return out


def _lead_where(column: str, values) -> tuple[str, list]:
    values = sorted({str(v) for v in values if v})
    if not values:
        return "", []
    return f"{column} IN ({','.join('?' * len(values))})", values


# ------------------------------------------------------------------ person

def person(config: dict, folder, site: str, q: str, live_dir=None) -> dict:
    """Everything kept about one person, linked (see the module)."""
    from .visits import _row, posted_near
    kind, value = kind_of(q)
    full = policy.identity_full(config, folder)
    short = policy.ip_mode(config, folder) == policy.SHORT
    ips, emails, vids, refs = set(), set(), set(), set()
    {"ip": ips, "email": emails, "vid": vids, "lead": refs}[kind].add(value)
    query = {"kind": kind, "value": value}
    if kind == "ip" and short:
        query["short"] = policy.shorten(value)
    out = {"ok": True, "query": query,
           "kept": policy.describe(config, folder), "visits": [], "requests": [],
           "leads": [], "conversions": [], "removed": [], "journeys": [],
           "candidates": [], "withheld": {}}
    path = store.path_for(config, folder) if folder is not None else None
    leads: dict = {}

    def more_leads() -> None:
        for column, values in (("id", refs), ("session_id", vids),
                               *((("lower(email)", emails),) if full else ())):
            where, args = _lead_where(column, values)
            if not where:
                continue
            try:
                found = _lead_rows(config, f"WHERE {where}", args, True, full)
            except sqlite3.Error:
                found = []
            for row in found:
                leads[str(row["id"])] = row
                refs.add(str(row["id"]))
                if row.get("vid"):
                    vids.add(row["vid"])
                if row.get("email"):
                    emails.add(str(row["email"]).lower())

    with _ro(path) as db:
        have = _tables(db) if db is not None else set()
        ids: set[int] = set()
        conv: dict = {}
        for _ in range(3):                    # leads <-> conversions <-> IDs
            before = (len(conv), len(vids), len(refs), len(emails), len(leads))
            more_leads()
            if db is not None and "conversions" in have:
                for e in list(emails):
                    ids |= _email_ids(db, site, e)
                for column, values in (("identity_id", ids), ("vid", vids),
                                       ("external_ref", refs)):
                    for v in list(values):
                        for r in db.execute(
                                f"SELECT c.*, i.email AS email, i.name AS name FROM "
                                f"conversions c LEFT JOIN identities i ON i.id = c.identity_id "
                                f"WHERE c.site = ? AND c.{column} = ? LIMIT {LIMIT}",
                                (site, v)).fetchall():
                            conv[r["id"]] = dict(r)
                            if r["vid"]:
                                vids.add(r["vid"])
                            refs.add(r["external_ref"])
                            if r["identity_id"]:
                                ids.add(r["identity_id"])
                            if r["email"]:
                                emails.add(str(r["email"]).lower())
            if (len(conv), len(vids), len(refs), len(emails), len(leads)) == before:
                break
        out["conversions"] = sorted(conv.values(), key=lambda r: (r["at"], r["id"]),
                                    reverse=True)
        if db is not None and "removed" in have:
            for r in db.execute("SELECT * FROM removed WHERE site = ? ORDER BY removed_at "
                                "DESC LIMIT ?", (site, LIMIT)).fetchall():
                row = dict(r)
                try:
                    row["row"] = json.loads(row["row"])
                except ValueError:
                    row["row"] = {}
                ident = row["row"].get("identity_id")
                if row["vid"] in vids or row["external_ref"] in refs or ident in ids:
                    out["removed"].append(row)
        if db is not None and "journeys" in have:
            for v in sorted(vids):
                out["journeys"] += [dict(r, vid=v) for r in db.execute(
                    "SELECT at, path, source_type FROM journeys WHERE site = ? AND vid = ? "
                    "ORDER BY at LIMIT ?", (site, v, LIMIT))]
        if db is not None and "visits" in have:
            for ip in sorted(ips):
                forms = sorted({ip, policy.shorten(ip)}) if short else [ip]
                out["visits"] += [_row(r) for r in db.execute(
                    f"SELECT * FROM visits WHERE site = ? AND ip IN "
                    f"({','.join('?' * len(forms))}) ORDER BY start DESC LIMIT ?",
                    (site, *forms, LIMIT))]
            for lead in leads.values():
                at = _stamp_of(lead.get("created_at"))
                if at:
                    for v in posted_near(db, site, at):
                        out["candidates"].append({"lead": str(lead["id"]), **v})
    if kind == "ip":
        out["candidates"] += _leads_at_posts(config, out["visits"], full)
    out["leads"] = sorted(leads.values(), key=lambda r: str(r.get("created_at") or ""),
                          reverse=True)
    out["requests"] = _requests(live_dir, site, ips)
    out["withheld"] = _withheld(config, folder, site,
                                {v["day"] for v in out["visits"] + out["candidates"]})
    out["keys"] = {"ips": sorted(ips | {v["ip"] for v in out["visits"] + out["candidates"]}
                                 - {"(removed)"}),
                   "emails": sorted(emails), "vids": sorted(vids), "leads": sorted(refs)}
    if not full:
        for r in out["conversions"]:
            r.pop("email", None)
            r.pop("name", None)
    return out


def _leads_at_posts(config: dict, visits: list, full: bool) -> list[dict]:
    """The other way round, for an address: leads made from 30 seconds before
    to 2 minutes after one of its visits sent a form. Matched by time."""
    from datetime import timedelta
    out, seen = [], set()
    for v in visits:
        for at in v.get("posts") or []:
            try:
                when = store.parse(at)
            except (TypeError, ValueError):
                continue
            lo = (when - timedelta(seconds=30)).strftime("%Y-%m-%d %H:%M:%S")
            hi = (when + timedelta(seconds=120)).strftime("%Y-%m-%d %H:%M:%S")
            try:
                rows = _lead_rows(config, "WHERE julianday(created_at) BETWEEN julianday(?) "
                                  "AND julianday(?)", (lo, hi), True, full)
            except sqlite3.Error:
                rows = []
            for lead in rows:
                if (lead["id"], v["id"]) not in seen:
                    seen.add((lead["id"], v["id"]))
                    out.append({"lead": str(lead["id"]), **v})
    return out


def _stamp_of(text) -> str | None:
    from ..leads import _utc
    when = _utc(text)
    return store.stamp(when) if when else None


def _requests(live_dir, site: str, ips: set) -> list[dict]:
    """The address's rows in the private Recent requests feed (6 hours)."""
    if live_dir is None or not ips:
        return []
    from ..requests_feed import path_for
    try:
        feed = json.loads(Path(path_for(Path(live_dir), site)).read_text())
    except (OSError, ValueError):
        return []
    return [r for r in feed.get("rows") or [] if isinstance(r, dict) and r.get("ip") in ips]


def _withheld(config: dict, folder, site: str, days: set) -> dict:
    """{day: "withheld"} for the days the history withholds."""
    path = policy.history_path(config, folder)
    if not days:
        return {}
    with _ro(path) as db:
        if db is None:
            return {}
        marks = ",".join("?" * len(days))
        try:
            return {r[0]: "withheld" for r in db.execute(
                f"SELECT day FROM days WHERE site = ? AND day IN ({marks}) AND NOT verified",
                (site, *sorted(days)))}
        except sqlite3.Error:
            return {}


# --------------------------------------------------------------- listings

def left_out(config: dict, folder, site: str, private: bool) -> dict:
    """The leads and conversions the figures leave out, newest first."""
    full = private and policy.identity_full(config, folder)
    try:
        leads = _lead_rows(config, "WHERE lower(COALESCE(status, '')) IN "
                           "('spam', 'duplicate', 'test') OR lower(COALESCE(flags, '')) "
                           "LIKE '%test%'" if _has_flags(config) else
                           "WHERE lower(COALESCE(status, '')) IN ('spam', 'duplicate', 'test')",
                           (), private, full)
    except sqlite3.Error as why:
        return {"ok": False, "error": f"the lead database could not be read: {why}"}
    out = {"ok": True, "leads": [], "conversions": conversions_listing(
        config, folder, site, "test", private)["rows"]}
    for row in leads:
        row["why"] = "test" if row["test"] else row["status"]
        out["leads"].append(row)
    return out


def _has_flags(config: dict) -> bool:
    from ..leads import db_path
    path = db_path(config or {})
    with _ro(path) as db:
        if db is None:
            return False
        return "flags" in {r[1] for r in db.execute("PRAGMA table_info(submissions)")}


def conversions_listing(config: dict, folder, site: str, kind: str, private: bool) -> dict:
    """kind "cancelled", "removed" or "test": the rows with their journey."""
    full = private and policy.identity_full(config, folder)
    path = store.path_for(config, folder) if folder is not None else None
    rows: list[dict] = []
    with _ro(path) as db:
        have = _tables(db) if db is not None else set()
        if kind == "removed" and "removed" in have:
            for r in db.execute("SELECT * FROM removed WHERE site = ? ORDER BY removed_at DESC "
                                "LIMIT ?", (site, LIMIT)).fetchall():
                row = dict(r)
                try:
                    row["row"] = json.loads(row["row"])
                except ValueError:
                    row["row"] = {}
                rows.append(row)
        elif kind in ("cancelled", "test") and "conversions" in have:
            cols = {r[1] for r in db.execute("PRAGMA table_info(conversions)")}
            if kind == "test" and "test" not in cols:
                return {"ok": True, "kind": kind, "rows": []}
            where = "c.test <> 0" if kind == "test" else \
                f"c.stage IN ({','.join('?' * len(CANCELLED))})"
            args = () if kind == "test" else CANCELLED
            rows = [dict(r) for r in db.execute(
                f"SELECT c.*, i.email AS email, i.name AS name FROM conversions c LEFT JOIN "
                f"identities i ON i.id = c.identity_id WHERE c.site = ? AND {where} "
                f"ORDER BY c.at DESC LIMIT ?", (site, *args, LIMIT)).fetchall()]
        if db is not None and "journeys" in have:
            for row in rows:
                vid = row.get("vid") or (row.get("row") or {}).get("vid")
                row["journey"] = [dict(r) for r in db.execute(
                    "SELECT at, path, source_type FROM journeys WHERE site = ? AND vid = ? "
                    "ORDER BY at LIMIT 200", (site, vid))] if vid else []
    for row in rows:
        for target in (row, row.get("row") or {}):
            if not full:
                target.pop("email", None)
                target.pop("name", None)
            if not private:
                target.pop("vid", None)
                # The page script's reference is made from the visitor ID (2.25).
                if "external_ref" in target:
                    target["external_ref"] = policy.shown_ref(target.get("tool"),
                                                              target["external_ref"], False)
    return {"ok": True, "kind": kind, "rows": rows}
