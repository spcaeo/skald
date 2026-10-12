"""The site's own lead database as a conversion source (tool "site").

The website already keeps every lead in its CMS database (`leads.db`, the
`submissions` table leads.py reads). Each lead becomes conversion rows,
so leads reach the Conversions tab without any change to the website:

    external_ref   the lead's id
    action, stage  by type (conversions.LEAD_TYPES): demo_booked -> demo,
                   contact, signup, waitlist completed; demo_opened -> demo
                   started. A status in LEAD_OUTCOMES (won, lost) adds a
                   second row of that stage; spam and duplicates make none.
    at             created_at (every row of the lead; "as known": a status
                   the team changes later changes that day)
    vid            session_id, when it looks like a visitor ID
    touches        first_touch / last_touch: source (by leads.touch_source),
                   campaign, landing; first_touch.at
    visits_before  the `visits` column, when present and a whole number
    country        ip_country, only when the row has two letters
    device         never: the lead DB does not say (NULL, not recorded)

The file is opened read-only and only the columns above are read; name
and email only when the site's `conversions.identity` is full.

Idempotent: a sync makes the store's rows for each lead it reads match the
lead, keeping the rows that are already right (same ids, so an outgoing
webhook is not sent twice). Incremental: only leads whose updated_at (or
created_at) is at or after the last one seen are read (meta
"leads_sync:<site>"); `full=True` (run-daily) reads them all and also drops
the rows of leads deleted from the CMS.

On when `leads.db` is set, unless `conversions.from_leads: false`.
The second count is audit_conversions.recount_leads (its own SQL).
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from ..config import setting
from . import (ACTION, LEAD_EXCLUDED, LEAD_OUTCOMES, LEAD_TYPES, LEADS_TOOL, SITE_VID,
               action_name, store)
from .adapters import when

COLUMNS = ("id", "created_at", "updated_at", "type", "status", "first_touch", "last_touch",
           "visits", "ip_country", "session_id")
PERSONAL = ("email", "name")
# The lead DB's touch fields -> the hooks' touch fields (adapters.TOUCH_KEYS).
TOUCH_FIELDS = {"landingPath": "landing", "utmSource": "utm_source", "utmMedium": "utm_medium",
                "utmCampaign": "utm_campaign", "utmContent": "utm_content",
                "utmTerm": "utm_term", "gclid": "gclid", "msclkid": "msclkid",
                "fbclid": "fbclid"}
# What decides whether a stored row is still right.
SAME = ("action", "at", "vid")


def enabled(config: dict) -> bool:
    from ..leads import db_path
    on = setting(config or {}, "conversions", "from_leads", True)
    return db_path(config or {}) is not None and on not in (False, "false")


def _mark_key(site: str) -> str:
    return f"leads_sync:{site}"


def _touch(raw) -> dict | None:
    if raw is None or raw == "":
        return None
    if isinstance(raw, dict):
        return raw
    try:
        got = json.loads(raw)
    except (TypeError, ValueError):
        return None
    return got if isinstance(got, dict) else None


def _record_touch(t: dict | None) -> dict | None:
    """The lead DB's touch as a hook touch (normalise.py reads it)."""
    if not t:
        return None
    out = {}
    host = t.get("referrerHost")
    if isinstance(host, str) and host.strip():
        out["referrer"] = f"https://{host.strip()}/"
    for theirs, ours in TOUCH_FIELDS.items():
        v = t.get(theirs)
        if isinstance(v, (str, int, float)) and not isinstance(v, bool) and str(v).strip():
            out[ours] = str(v).strip()[:300]
    at = when(t.get("at")) if isinstance(t.get("at"), str) else None
    if at:
        out["at"] = at
    return out or None


def _visits(v) -> int | None:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    if isinstance(v, float) and not v.is_integer():
        return None
    return int(v) if 0 <= v <= 100000 else None


def _pairs(lead: dict) -> list[tuple[str, str]]:
    """(action, stage) rows one lead makes; [] for spam, duplicates and a
    type that is no token."""
    status = str(lead.get("status") or "new").strip().lower()
    if status in LEAD_EXCLUDED:
        return []
    kind = str(lead.get("type") or "").strip().lower()
    action, stage = LEAD_TYPES.get(kind, (action_name(kind), "completed"))
    if not ACTION.match(action):
        return []
    out = [(action, stage)]
    if stage == "completed" and status in LEAD_OUTCOMES:
        out.append((action, status))
    return out


def rows_for(lead: dict, site: str, identity_full: bool = False) -> list[dict]:
    """The store's rows for one lead (normalise.row's shape)."""
    from ..leads import NONE, touch_source
    from .normalise import row as make_row
    at = when(lead.get("created_at"))
    if at is None:
        return []
    first_raw, last_raw = _touch(lead.get("first_touch")), _touch(lead.get("last_touch"))
    first, last = _record_touch(first_raw), _record_touch(last_raw)
    source = touch_source(last_raw or first_raw) if (last_raw or first_raw) else None
    first_source = touch_source(first_raw) if first_raw else None
    vid = str(lead.get("session_id") or "").strip()
    country = str(lead.get("ip_country") or "").strip()
    out = []
    for action, stage in _pairs(lead):
        rec = {"action": action, "stage": stage, "external_ref": str(lead["id"]), "at": at,
               "vid": vid if SITE_VID.match(vid) else None, "first_touch": first,
               "last_touch": last, "source_type": None if source == NONE else source,
               "country": country if len(country) == 2 else None,
               "visits_before": _visits(lead.get("visits")),
               "first_touch_at": (first or {}).get("at")}
        if identity_full and lead.get("email"):
            rec.update(email=str(lead["email"])[:320], name=lead.get("name"))
        row = make_row(rec, site, LEADS_TOOL, at, set(), identity_full)
        row["first_source"] = None if first_source in (None, NONE) else first_source
        out.append(row)
    return out


def _read(path: Path, since: str | None, identity_full: bool) -> list[dict]:
    from ..leads import connect
    db = connect(path)
    try:
        have = {r[1] for r in db.execute("PRAGMA table_info(submissions)")}
        if "id" not in have or "created_at" not in have or "type" not in have:
            raise ValueError("the submissions table has no id, created_at or type column")
        wanted = COLUMNS + (PERSONAL if identity_full else ())
        picked = [c if c in have else f"NULL AS {c}" for c in wanted]
        changed = "COALESCE(updated_at, created_at)" if "updated_at" in have else "created_at"
        sql = f"SELECT {', '.join(picked)}, {changed} AS mark FROM submissions"
        args: tuple = ()
        if since:
            sql += f" WHERE {changed} >= ?"
            args = (since,)
        return [dict(zip(wanted + ("mark",), r)) for r in db.execute(sql, args)]
    finally:
        db.close()


def sync(db: sqlite3.Connection, path: Path, site: str, identity_full: bool = False,
         full: bool = False) -> dict:
    """Make the store's tool-"site" rows match the lead DB. Counts:
    {"read", "added", "removed", "kept"}. Raises OSError / sqlite3.Error /
    ValueError when the lead DB cannot be read."""
    row = db.execute("SELECT value FROM meta WHERE key = ?", (_mark_key(site),)).fetchone()
    since = None if full or row is None else row[0]
    leads = _read(Path(path), since, identity_full)
    got = {"read": len(leads), "added": 0, "removed": 0, "kept": 0}
    mark = max((str(r["mark"]) for r in leads if r.get("mark")), default=since)
    with store.tx(db):
        seen = set()
        for lead in leads:
            ref = str(lead["id"])
            seen.add(ref)
            want = {r["stage"]: r for r in rows_for(lead, site, identity_full)}
            have = {r["stage"]: dict(r) for r in db.execute(
                "SELECT id, stage, action, at, vid FROM conversions WHERE site = ? AND "
                "tool = ? AND external_ref = ?", (site, LEADS_TOOL, ref))}
            for stage, old in have.items():
                new = want.get(stage)
                if new is not None and all(old[k] == new[k] for k in SAME):
                    got["kept"] += 1
                    want.pop(stage)
                    continue
                db.execute("DELETE FROM conversions WHERE id = ?", (old["id"],))
                got["removed"] += 1
            for new in want.values():
                got["added"] += int(store.record_conversion(db, new))
        if full:
            for (ref,) in db.execute("SELECT DISTINCT external_ref FROM conversions WHERE "
                                     "site = ? AND tool = ?", (site, LEADS_TOOL)).fetchall():
                if ref not in seen:
                    got["removed"] += db.execute(
                        "DELETE FROM conversions WHERE site = ? AND tool = ? AND "
                        "external_ref = ?", (site, LEADS_TOOL, ref)).rowcount
        if mark:
            db.execute("INSERT INTO meta (key, value) VALUES (?, ?) ON CONFLICT(key) DO "
                       "UPDATE SET value = excluded.value", (_mark_key(site), mark))
    return got


def run(config: dict, folder: Path, site: str, full: bool = False) -> dict | None:
    """Sync this site's leads into conversions.sqlite. None when it is not
    on; {"error"} when the lead DB cannot be read (never raises)."""
    from ..leads import db_path
    from .hooks import identity_full
    if not enabled(config):
        return None
    path = db_path(config)
    if not Path(path).is_file():
        return {"error": f"not found: {path}"}
    try:
        db = store.connect(store.path_for(config, folder))
    except (OSError, sqlite3.Error, RuntimeError) as why:
        return {"error": f"conversions file: {type(why).__name__}: {why}"}
    try:
        return sync(db, path, site, identity_full(config), full)
    except (OSError, sqlite3.Error, ValueError) as why:
        return {"error": f"{type(why).__name__}: {why}"}
    finally:
        db.close()
