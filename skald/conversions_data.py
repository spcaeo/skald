"""conversions.json (DATA-CONTRACT.md): what visitors did that counts, per
local day, from conversions.sqlite - the hooks, the beacon's events with
visitor IDs, and the site's lead DB (conversions/).

Per day: every action's rows by stage; abandoned starts (a start with a
visitor ID and no finish within `conversions.abandon_hours`, only once that
window has closed); and, for finished rows (completed or paid), the
breakdowns by source, first source, campaign, landing page, country,
device and tool, the visits before, the time from the first touch, and the
sources that assisted (seen earlier in the browser's journey, not the last
touch; only with visitor IDs). Over the last 30 days: the pages seen
before converting against browsers that did not convert (only with
visitor IDs), and the latest conversions as anonymous timelines.

Counted here in Python from plain SELECTs. audit_conversions.py counts the
same figures again by its own SQL GROUP BY, and the stages from the hook
and beacon spools and the lead DB; a day the two roads disagree on is
withheld, a block too. A figure not recorded is "Unknown", never a guess
(a visit known to carry no campaign tag is "(no campaign tag)", as in the
logs). The same file is written on every page: the
conversions do not know about views.

`likely_ai` per day (inferred, ai_likely.py): finished rows by the
assistant likely behind their first touch - {action: {label: n}}. The
first touch is the row's own (first_source, first_touch_at, landing) when
it has one, else, for a row with a visitor ID, the browser's earliest
journeys row (source_type, at, path). A first touch from "Direct or
unknown" is looked up in the stored AI user fetches (the assistant, or
"(more than one)", or "(none)"); any other source is "(none)"; a first
touch not known, or fetches not kept for its window, is "Unknown".
"""
from __future__ import annotations

import sqlite3
from collections import Counter
from datetime import date, datetime, time, timedelta
from pathlib import Path

from .config import setting
from .conversions import (CONVERT_BUCKETS, DEMO_ACTIONS, FINISHED, LEAD_ACTIONS, MIN_RATE,
                          STAGES, TOOLS, UNKNOWN, VISIT_BUCKETS)

DAYS = 180
PERIOD_DAYS = 30
TIMELINE = 50
TIMELINE_DAYS = 10
TIMELINE_PATHS = 15
TIMELINE_STEPS = 20
PAGES = 50
DIMS = ("source_type", "first_source", "campaign", "landing", "country", "device", "tool")
AS_KNOWN = ("Conversions are as known now. A cancellation, a no-show or a lead the team marks "
            "won, lost or spam later changes the day the action was taken. A visitor ID is "
            "a browser, not a person: one person on two devices is two browsers.")

_MEMO: dict = {}


def _stamp(d: date, tz) -> str:
    from .conversions.store import stamp
    return stamp(datetime.combine(d, time(0), tzinfo=tz))


def _day(at: str, tz) -> str:
    from .conversions.store import parse
    return parse(at).astimezone(tz).date().isoformat()


def _label(dim: str, value) -> str:
    if value is None or value == "":
        return UNKNOWN
    return str(value)


def _ms(at: str, first_touch_at) -> int | None:
    from .conversions.store import parse
    if not first_touch_at:
        return None
    try:
        return round((parse(at) - parse(str(first_touch_at))).total_seconds() * 1000)
    except ValueError:
        return None


def set_up(config: dict, folder: Path, site: str) -> dict:
    """What is turned on, for the tab's empty states."""
    from . import events
    from .conversions import from_leads, secrets_store, store
    hooks = []
    for tool in TOOLS:
        try:
            if secrets_store.find(config, folder, site, tool)[1]:
                hooks.append(tool)
        except secrets_store.Exposed:
            continue
    return {"beacon": events.enabled(config),
            "visitor_ids": setting(config, "beacon", "visitor_ids", False) in (True, "true"),
            "hooks": hooks, "leads_db": from_leads.enabled(config),
            "store": bool(store.path_for(config, folder).exists())}


# ------------------------------------------------------------- per day

def _empty(journeys: bool) -> dict:
    return {"stages": {}, "abandoned": {}, "by": {d: {} for d in DIMS}, "visits_before": {},
            "time_to_convert": {}, "assisted": {} if journeys else None, "likely_ai": {}}


def _add(table: dict, a: str, b: str) -> None:
    per = table.setdefault(a, {})
    per[b] = per.get(b, 0) + 1


def likely_label(db, row, likely: tuple | None, tz) -> str:
    """The likely assistant behind a finished row's first touch (see above)."""
    from .ai_likely import DIRECT, NOT_RECORDED, likely_for
    from .conversions import store
    if row["first_source"] is not None:
        source, at, path = row["first_source"], row["first_touch_at"], row["landing"]
    elif row["vid"]:
        got = db.execute("SELECT source_type, at, path FROM journeys WHERE site = ? AND vid = ? "
                         "AND at <= ? ORDER BY at, rowid LIMIT 1",
                         (row["site"], row["vid"], row["at"])).fetchone()
        if got is None:
            return UNKNOWN
        source, at, path = got
    else:
        return UNKNOWN
    if source is None:
        return UNKNOWN
    if source != DIRECT:
        return "(none)"
    try:
        when = store.parse(str(at)) if at else None
    except ValueError:
        when = None
    index, window = likely or (None, 0)
    got = likely_for(index, path or "", when, window, tz)
    return UNKNOWN if got == NOT_RECORDED else got


def figures(db, site: str, tz, first: date, last: date, now: str, hours: float,
            likely: tuple | None = None) -> dict:
    """{local day: figures} for first..last. Days with no row are left out.
    `likely`: (ai_likely.fetch_index, window), or None (every likely_ai
    "Unknown")."""
    from .conversions import store
    from .leads import convert_bucket, visits_bucket
    lo, hi = _stamp(first, tz), _stamp(last + timedelta(days=1), tz)
    journeys = db.execute("SELECT 1 FROM journeys WHERE site = ? LIMIT 1",
                          (site,)).fetchone() is not None
    out: dict = {}
    for r in db.execute("SELECT * FROM conversions WHERE site = ? AND at >= ? AND at < ? "
                        "AND test = 0 ORDER BY at, id", (site, lo, hi)).fetchall():
        f = out.setdefault(_day(r["at"], tz), _empty(journeys))
        _add(f["stages"], r["action"], r["stage"])
        if r["stage"] not in FINISHED:
            continue
        for dim in DIMS:
            _add(f["by"][dim], r["action"], _label(dim, r[dim]))
        _add(f["visits_before"], r["action"], visits_bucket(r["visits_before"]))
        _add(f["time_to_convert"], r["action"],
             convert_bucket(_ms(r["at"], r["first_touch_at"])))
        _add(f["likely_ai"], r["action"], likely_label(db, r, likely, tz))
        if journeys and r["vid"]:
            seen = {s for (s,) in db.execute(
                "SELECT DISTINCT source_type FROM journeys WHERE site = ? AND vid = ? AND "
                "at < ?", (site, r["vid"], r["at"])) if s}
            for src in seen - {r["source_type"]}:
                _add(f["assisted"], r["action"], src)
    for r in store.abandoned(db, site, lo, hi, hours, now):
        f = out.setdefault(_day(r["at"], tz), _empty(journeys))
        f["abandoned"][r["action"]] = f["abandoned"].get(r["action"], 0) + 1
    return out


# ----------------------------------------------------- over the period

def _converting(db, site: str, lo: str, hi: str) -> dict[str, str]:
    """{vid: the first finished at in [lo, hi)}."""
    out: dict[str, str] = {}
    marks = ",".join("?" * len(FINISHED))
    for vid, at in db.execute(f"SELECT vid, at FROM conversions WHERE site = ? AND vid IS NOT "
                              f"NULL AND stage IN ({marks}) AND at >= ? AND at < ? "
                              f"AND test = 0",
                              (site, *FINISHED, lo, hi)):
        if vid not in out or at < out[vid]:
            out[vid] = at
    return out


def pages_before(db, site: str, lo: str, hi: str) -> dict | None:
    """Pages seen before converting (by converting browsers) against pages
    seen by browsers that did not convert in [lo, hi). None without journeys."""
    if db.execute("SELECT 1 FROM journeys WHERE site = ? LIMIT 1", (site,)).fetchone() is None:
        return None
    conv = _converting(db, site, lo, hi)
    seen_conv: Counter = Counter()
    converting = 0
    for vid, at in conv.items():
        paths = {p for (p,) in db.execute("SELECT DISTINCT path FROM journeys WHERE site = ? "
                                          "AND vid = ? AND at <= ?", (site, vid, at))}
        if paths:
            converting += 1
            seen_conv.update(paths)
    by_vid: dict[str, set] = {}
    for vid, path in db.execute("SELECT vid, path FROM journeys WHERE site = ? AND at >= ? "
                                "AND at < ?", (site, lo, hi)):
        if vid not in conv:
            by_vid.setdefault(vid, set()).add(path)
    seen_other: Counter = Counter()
    for paths in by_vid.values():
        seen_other.update(paths)
    ranked = sorted(set(seen_conv) | set(seen_other),
                    key=lambda p: (-seen_conv[p], -seen_other[p], p))[:PAGES]
    return {"converting": converting, "other": len(by_vid),
            "pages": [[p, seen_conv[p], seen_other[p]] for p in ranked]}


def timeline(db, site: str, tz, lo: str, hi: str, held: set) -> list[dict]:
    """The latest finished conversions of [lo, hi) as anonymous timelines,
    newest first: never a visitor ID, an email or a name. Withheld days
    left out."""
    out, done = [], set()
    marks = ",".join("?" * len(FINISHED))
    for r in db.execute(f"SELECT * FROM conversions WHERE site = ? AND stage IN ({marks}) "
                        f"AND at >= ? AND at < ? AND test = 0 ORDER BY at DESC, id DESC",
                        (site, *FINISHED, lo, hi)).fetchall():
        key = ("vid", r["vid"]) if r["vid"] else ("ref", r["tool"], r["external_ref"])
        if key in done or _day(r["at"], tz) in held:
            continue
        done.add(key)
        if r["vid"]:
            steps = db.execute("SELECT at, action, stage, tool FROM conversions WHERE site = ? "
                               "AND vid = ? AND test = 0 ORDER BY at, id",
                               (site, r["vid"])).fetchall()
            visits: dict[str, dict] = {}
            for at, path, source in db.execute(
                    "SELECT at, path, source_type FROM journeys WHERE site = ? AND vid = ? "
                    "AND at <= ? ORDER BY at", (site, r["vid"], r["at"])):
                v = visits.setdefault(_day(at, tz), {"day": _day(at, tz), "source": source,
                                                     "paths": []})
                if len(v["paths"]) < TIMELINE_PATHS and (not v["paths"] or
                                                         v["paths"][-1] != path):
                    v["paths"].append(path)
            days = list(visits.values())[-TIMELINE_DAYS:]
        else:
            steps = db.execute("SELECT at, action, stage, tool FROM conversions WHERE site = ? "
                               "AND tool = ? AND external_ref = ? AND test = 0 ORDER BY at, id",
                               (site, r["tool"], r["external_ref"])).fetchall()
            days = []
        out.append({"at": _local(r["at"], tz), "action": r["action"], "stage": r["stage"],
                    "tool": r["tool"], "source": r["source_type"],
                    "first_source": r["first_source"], "campaign": r["campaign"],
                    "landing": r["landing"], "country": r["country"], "device": r["device"],
                    "visits_before": r["visits_before"],
                    "first_touch": _local(r["first_touch_at"], tz),
                    "browser": bool(r["vid"]), "visits": days,
                    "steps": [{"at": _local(s[0], tz), "action": s[1], "stage": s[2],
                               "tool": s[3]} for s in steps[-TIMELINE_STEPS:]]})
        if len(out) >= TIMELINE:
            break
    return out


def _local(at, tz) -> str | None:
    from .conversions.store import parse
    if not at:
        return None
    try:
        return parse(str(at)).astimezone(tz).isoformat(timespec="seconds")
    except ValueError:
        return None


# ------------------------------------------------------------- the file

def recorded_since(config: dict, db, site: str, tz) -> str | None:
    """conversions.json `since`: the first local day conversions are recorded
    for, or None. The earliest of the first row kept, the first row taken
    away (store.remove: it was recorded), and - once the lead DB has been
    read into the store (its sync mark) - the lead DB's first lead of any
    status: spam and duplicates make no row, yet their day was read, so a
    day after it with no lead counted is 0, not "not recorded" (2.5.1).
    audit_conversions_figures.check_since finds the same day by its own SQL."""
    from .conversions import from_leads
    from .conversions.adapters import when
    stamps = [db.execute("SELECT MIN(at) FROM conversions WHERE site = ?", (site,)).fetchone()[0],
              db.execute("SELECT MIN(at) FROM removed WHERE site = ? AND at IS NOT NULL",
                         (site,)).fetchone()[0]]
    if from_leads.enabled(config) and db.execute(
            "SELECT 1 FROM meta WHERE key = ?", (from_leads._mark_key(site),)).fetchone():
        from .leads import connect, db_path
        try:
            lead_db = connect(db_path(config))
            try:
                made = [when(r[0]) for r in lead_db.execute("SELECT created_at FROM submissions")]
            finally:
                lead_db.close()
            stamps.append(min((m for m in made if m), default=None))
        except (OSError, sqlite3.Error):
            pass                        # not read now: the rows alone say
    days = [_day(s, tz) for s in stamps if s]
    return min(days) if days else None


def _unavailable(reason: str, found: dict) -> dict:
    return {"available": False, "reason": reason, "set_up": found, "min_rate": MIN_RATE,
            "as_known": AS_KNOWN, "stages": list(STAGES), "finished": list(FINISHED),
            "dims": list(DIMS), "visit_buckets": list(VISIT_BUCKETS),
            "convert_buckets": list(CONVERT_BUCKETS), "since": None, "days": [],
            "lead_actions": list(LEAD_ACTIONS), "demo_actions": list(DEMO_ACTIONS),
            "period": None, "pages_before": None, "timeline": [], "today": None,
            "withheld": {}}


def blob(config: dict, folder: Path, site: str, tz, today: date, now: datetime,
         audited: bool = True, history=None) -> dict:
    """conversions.json's body. audited (the file's way): the second count
    runs and what it disagrees with is withheld. `history` (store.History)
    holds the AI user fetches behind likely_ai."""
    from .data_reports import likely_note
    from .leads import likely_fetches
    from .conversions import from_beacon, store
    found = set_up(config, folder, site)
    path = store.path_for(config, folder)
    if not path.exists():
        return _unavailable("no conversions yet: nothing has been recorded", found)
    first = today - timedelta(days=DAYS - 1)
    start = today - timedelta(days=PERIOD_DAYS - 1)
    now_s = store.stamp(now)
    hours = from_beacon.abandon_hours(config)
    db = store.connect(path)
    try:
        since = recorded_since(config, db, site, tz)
        per = figures(db, site, tz, first, today, now_s, hours,
                      likely_fetches(config, history, today))
        lo, hi = _stamp(start, tz), _stamp(today + timedelta(days=1), tz)
        pages = pages_before(db, site, lo, hi)
        out = {"available": True, "reason": None, "set_up": found, "min_rate": MIN_RATE,
               "as_known": AS_KNOWN, "abandon_hours": hours, "stages": list(STAGES),
               "finished": list(FINISHED), "dims": list(DIMS),
               "visit_buckets": list(VISIT_BUCKETS), "convert_buckets": list(CONVERT_BUCKETS),
               "since": since, "days": [], "likely_ai": likely_note(config),
               "lead_actions": list(LEAD_ACTIONS), "demo_actions": list(DEMO_ACTIONS),
               "period": {"first": start.isoformat(), "last": today.isoformat()},
               "pages_before": pages, "timeline": [], "withheld": {}}
        for i in range(DAYS):
            d = (first + timedelta(days=i)).isoformat()
            if since is None or d < since:
                out["days"].append({"day": d, "state": "before"})
            else:
                out["days"].append({"day": d, "state": "ok", **(per.get(d) or _empty(
                    pages is not None))})
        held = {}
        if audited:
            from . import audit_conversions
            try:
                held = audit_conversions.check_file(config, folder, site, tz, first, today,
                                                    now_s, hours, out,
                                                    getattr(history, "path", None))
            except Exception as why:        # noqa: BLE001 - unchecked figures are withheld
                held = {"*": [f"the recount could not run: {type(why).__name__}: {why}"]}
        out = withhold(out, held)
        days_held = {k.split("/", 1)[1] for k in out["withheld"] if k.startswith("days/")}
        out["timeline"] = timeline(db, site, tz, lo, hi, days_held)
        out["today"] = _today(db, path, site, tz, today, days_held, audited, out["withheld"])
    finally:
        db.close()
    return out


def _today(db, path, site: str, tz, today: date, held: set, audited: bool,
           withheld: dict) -> dict:
    """conversions.json `today` (conversions_leads.today_block), checked by
    audit_conversions_leads.check_today when audited; withheld (and named
    in `withheld["today"]`) when the recount disagrees or cannot run."""
    from .conversions_leads import today_block
    block = today_block(db, site, tz, today, held)
    if not audited or block["state"] != "ok":
        return block
    from . import audit_conversions_leads
    try:
        problems = audit_conversions_leads.check_today(path, site, tz, today, block)
    except Exception as why:            # noqa: BLE001 - an unchecked listing is withheld
        problems = [f"the recount could not run: {type(why).__name__}: {why}"]
    if not problems:
        return block
    why = ("the second count (audit_conversions_leads.py) disagrees: " + "; ".join(problems[:3])
           + (f" (and {len(problems) - 3} more)" if len(problems) > 3 else ""))
    withheld["today"] = why
    return {"day": block["day"], "state": "withheld", "why": why}


def withhold(out: dict, found: dict[str, list[str]]) -> dict:
    """Days ("days/<day>") and blocks ("pages_before") the second count
    disagrees with, replaced by {"state": "withheld", "why"}; "*" all."""
    def why(problems: list[str]) -> str:
        more = f" (and {len(problems) - 3} more)" if len(problems) > 3 else ""
        return ("the second count (audit_conversions.py) disagrees: "
                + "; ".join(problems[:3]) + more)
    if "*" in found:
        found = {"pages_before": found["*"],
                 **{f"days/{d['day']}": found["*"] for d in out["days"]
                    if d["state"] == "ok"}}
    said = {k: why(v) for k, v in found.items() if v}
    if "pages_before" in said and out.get("pages_before") is not None:
        out["pages_before"] = {"state": "withheld", "why": said["pages_before"]}
    out["days"] = [{"day": d["day"], "state": "withheld", "why": said[f"days/{d['day']}"]}
                   if f"days/{d['day']}" in said else d for d in out["days"]]
    out["withheld"] = said
    return out


def build(page) -> dict:
    """conversions.json for a page (data_files.Page): the whole site's, the
    same on every page of it, worked out once per run."""
    from .conversions.hooks import history_folder
    site = page.key.split("::", 1)[0]
    folder = page.live_dir if page.live_dir is not None else history_folder(page.config)
    key = (site, str(folder), page.now.isoformat())
    if key not in _MEMO:
        _MEMO.clear()
        _MEMO[key] = blob(page.config, Path(folder), site, page.tz, page.today, page.now,
                          history=getattr(page, "history", None))
    return _MEMO[key]
