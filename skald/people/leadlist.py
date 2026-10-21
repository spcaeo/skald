"""Leads & sales > Leads: the list of leads of a period, one row per lead. A listing,
never a figure: the page's count beside it is the Leads figure of conversions.json
(js/tabs/leadfigs.js leadsOn), never a count of these rows.

    rows(config, folder, site, first, last, names)

A lead is a finished row (completed or paid) of a lead action (conversions.
LEAD_ACTIONS) in the conversions store, the same rows conversions_data.figures
counts as Leads on the days of [first, last] (local days, `report.timezone`).
Each row says where it came from (`tool`: "site" is the lead database, else the
tool or the page's script tag) and its stage now: the latest later stage of the
same lead (won, lost, cancelled, no-show, rescheduled), else its own.

Left out, listed and never counted (`left_out`): rows marked test, and the lead
database's spam, duplicate and test leads (they make no conversion row).

Names and emails (`names` True) only when the site keeps them
(`conversions.identity: full`); the caller checks the role, the CSRF value and
writes the audit row (people/api.py). Without them the keys are not in a row at
all. A visitor ID is never in a row: the journey (page views, labels only) is.
Read-only, like everything in people/.
"""
from __future__ import annotations

import sqlite3
from datetime import date, datetime, time, timedelta

from ..conversions import FINISHED, LEAD_ACTIONS, store
from . import policy

LIMIT = 2000
JOURNEY = 60
LATER = ("won", "lost", "cancelled", "no_show", "rescheduled")


def _stamp(d: date, tz) -> str:
    return store.stamp(datetime.combine(d, time(0), tzinfo=tz))


def _local(at, tz) -> str | None:
    try:
        return store.parse(str(at)).astimezone(tz).isoformat(timespec="seconds")
    except (TypeError, ValueError):
        return None


def span(first: str, last: str, today: date) -> tuple[date, date]:
    """[first, last] as days; at most 400 days, never after today. ValueError else."""
    a, b = date.fromisoformat(first), date.fromisoformat(last)
    if b < a or (b - a).days > 400:
        raise ValueError("first and last are days, first before last, at most 400 days apart")
    return a, min(b, today)


def rows(config: dict, folder, site: str, first: date, last: date, names: bool) -> dict:
    """{"ok", "rows", "names", "why"}: the period's leads, newest first (see the module)."""
    from ..window import zone
    tz = zone(config)
    full = names and policy.identity_full(config, folder)
    out = {"ok": True, "names": full, "first": first.isoformat(), "last": last.isoformat(),
           "rows": [], "truncated": False,
           "why": None if full else ("This site keeps no names or emails (conversions.identity: "
                                     "anonymous)." if names else None)}
    path = store.path_for(config, folder) if folder is not None else None
    lo, hi = _stamp(first, tz), _stamp(last + timedelta(days=1), tz)
    if path is not None and path.is_file():
        db = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)
        db.row_factory = sqlite3.Row
        try:
            out["rows"], out["truncated"] = _conversions(db, site, lo, hi, tz, full)
        except sqlite3.Error as why:
            return {"ok": False, "error": f"the conversions store could not be read: {why}"}
        finally:
            db.close()
    out["rows"] += _left_out_leads(config, folder, first, last, tz, full)
    out["rows"].sort(key=lambda r: r.get("at") or "", reverse=True)
    return out


def _conversions(db, site: str, lo: str, hi: str, tz, full: bool) -> tuple[list, bool]:
    cols = {r[1] for r in db.execute("PRAGMA table_info(conversions)")}
    if not cols:
        return [], False
    test = "c.test" if "test" in cols else "0"
    label = "c.label" if "label" in cols else "NULL"
    who = ", i.email AS email, i.name AS name" if full else ""
    join = " LEFT JOIN identities i ON i.id = c.identity_id" if full else ""
    marks, acts = ",".join("?" * len(FINISHED)), ",".join("?" * len(LEAD_ACTIONS))
    found = db.execute(
        f"SELECT c.id, c.action, c.stage, c.at, c.vid, c.external_ref, c.tool, c.source_type, "
        f"c.first_source, c.campaign, c.landing, c.country, c.device, {test} AS test, "
        f"{label} AS label{who} FROM conversions c{join} WHERE c.site = ? AND c.at >= ? "
        f"AND c.at < ? AND c.stage IN ({marks}) AND c.action IN ({acts}) "
        f"ORDER BY c.at DESC, c.id DESC LIMIT ?",
        (site, lo, hi, *FINISHED, *LEAD_ACTIONS, LIMIT + 1)).fetchall()
    truncated = len(found) > LIMIT
    found = found[:LIMIT]
    steps: dict = {}
    refs = sorted({r["external_ref"] for r in found})
    for i in range(0, len(refs), 500):
        part = refs[i:i + 500]
        for s in db.execute(f"SELECT tool, external_ref, action, stage, at, {label.replace('c.', '')} "
                            f"AS label FROM conversions WHERE site = ? AND {test.replace('c.', '')} = 0 "
                            f"AND external_ref IN ({','.join('?' * len(part))}) ORDER BY at, id",
                            (site, *part)):
            steps.setdefault((s["tool"], s["external_ref"]), []).append(s)
    journeys = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type = 'table' "
                                         "AND name = 'journeys'")}
    out = []
    for r in found:
        mine = steps.get((r["tool"], r["external_ref"]), [])
        later = [s for s in mine if s["stage"] in LATER and s["at"] >= r["at"]]
        now = later[-1]["stage"] if later else r["stage"]
        row = {"id": r["id"], "at": _local(r["at"], tz), "action": r["action"], "label": r["label"],
               "stage": r["stage"], "now": now, "tool": r["tool"], "source": r["source_type"],
               "first_source": r["first_source"], "campaign": r["campaign"],
               "landing": r["landing"], "country": r["country"], "device": r["device"],
               "left_out": "test" if r["test"] else None, "browser": bool(r["vid"]),
               "steps": [{"at": _local(s["at"], tz), "action": s["action"], "stage": s["stage"],
                          "tool": s["tool"], "label": s["label"]} for s in mine]}
        if full:
            row["email"], row["name"] = r["email"], r["name"]
        if r["vid"] and journeys:
            row["journey"] = [{"at": _local(j[0], tz), "path": j[1], "source_type": j[2]}
                              for j in db.execute("SELECT at, path, source_type FROM journeys "
                                                  "WHERE site = ? AND vid = ? AND at <= ? "
                                                  "ORDER BY at DESC LIMIT ?",
                                                  (site, r["vid"], r["at"], JOURNEY))][::-1]
        out.append(row)
    return out, truncated


def _left_out_leads(config: dict, folder, first: date, last: date, tz, full: bool) -> list:
    """The lead database's spam, duplicate and test leads of the period (lookup.left_out)."""
    from .lookup import _has_flags, _lead_rows
    where = "WHERE lower(COALESCE(status, '')) IN ('spam', 'duplicate', 'test')"
    try:
        if _has_flags(config):
            where += " OR lower(COALESCE(flags, '')) LIKE '%test%'"
        leads = _lead_rows(config, where, (), full, full)
    except sqlite3.Error:
        return []
    out = []
    for lead in leads:
        at = _lead_local(lead.get("created_at"), tz)
        if not at or not (first.isoformat() <= at[:10] <= last.isoformat()):
            continue
        row = {"id": f"lead-{lead.get('id')}", "at": at, "action": _lead_action(lead.get("type")),
               "label": None, "stage": "completed", "now": lead.get("status") or "new",
               "tool": "site", "source": lead.get("last_source"), "first_source": lead.get("first_source"),
               "campaign": None, "landing": lead.get("landing"), "country": lead.get("ip_country"),
               "device": None, "left_out": "test" if lead.get("test") else lead.get("status"), "browser": False, "steps": []}
        if full:
            row["email"], row["name"] = lead.get("email"), lead.get("name")
        out.append(row)
    return out


def _lead_local(text, tz) -> str | None:
    from ..leads import _utc
    when = _utc(text)
    return when.astimezone(tz).isoformat(timespec="seconds") if when else None


def _lead_action(kind) -> str:
    k = str(kind or "").lower()
    return "demo" if k == "demo_booked" else k
