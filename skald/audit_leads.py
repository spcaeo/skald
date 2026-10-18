"""The second count of leads.json: every figure the file shows, recounted
from the CMS by SQL GROUP BY over json_extract within UTC bounds worked out
per local day, and compared with what leads.py counted in Python.

What it shares with leads.py: the read-only connection, the column check
and the "(none)" label - no counting code. Its name lists (the funnel's page
words, the paid mediums and click ids) come from classify.py, as leads.py's
do. A touch's source type comes from the audit's own rules
(audit_labels.source_of), never from dimensions.py.
The time to convert is bucketed in SQL from julianday differences; the
visits before a lead by a SQL CASE; the funnel's log steps are recounted
from the same journeys with this module's own page matching.

Each touch's likely_ai (an inferred label, ai_likely.py) is worked out
again here: the touch's minute by SQL strftime('%s'), the stored AI user
fetches read from the history file by its own SQL (json_each over the
day_extras rows of verified whole days), and its own page and window rule;
it shares classify's AI_LIKELY_MANY and ai_likely.FETCH_DAYS, the span the
fetches are looked up over.

leads.py runs it each time it builds leads.json and withholds a block the
recount disagrees with (`findings`, one entry per block, a day on its own);
`skald leads --audit` and run-daily (`daily`, a step from audit_more.py)
report the same comparison (`compare`).
"""
from __future__ import annotations

import re
import sqlite3
from collections import Counter
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlencode

from .ai_likely import FETCH_DAYS
from .audit_labels import source_of
from .classify import AI_LIKELY_MANY, FORM_PAGES, PAID_CLICK_IDS, PAID_MEDIUMS, PRICING_PAGES
from .config import setting, site_name
from .leads import NONE, _columns, connect

FIELDS = ("aiSource", "referrerHost", "utmSource", "utmMedium", "utmCampaign", "landingPath",
          "gclid", "gbraid", "wbraid", "msclkid", "fbclid")
LEFT_OUT = ("spam", "duplicate")
FORM_KINDS = ("signup", "contact", "waitlist")
DAY_MS = 86_400_000
# (upper bound in ms, exclusive, bucket): "1-7d" is 1 to 7 whole days.
CUTS = ((3_600_000, "<1h"), (DAY_MS, "<1d"), (8 * DAY_MS, "1-7d"), (31 * DAY_MS, "8-30d"),
        (91 * DAY_MS, "31-90d"))
STEP_NAMES = ("readers", "pricing", "form_page", "demo_opened", "leads", "demo_booked")


def _bounds(day: date, tz) -> tuple[str, str]:
    """The local day as UTC strings shaped like the CMS's created_at."""
    def iso(d: date) -> str:
        return (datetime.combine(d, time(0), tzinfo=tz).astimezone(timezone.utc)
                .strftime("%Y-%m-%dT%H:%M:%S.000Z"))
    return iso(day), iso(day + timedelta(days=1))


# ------------------------------------------------------------------- SQL

def _object(col: str, have: set) -> str:
    if col not in have:
        return "0"
    return f"CASE WHEN json_valid({col}) THEN json_type({col}) = 'object' ELSE 0 END"


def _field(col: str, key: str, have: set) -> str:
    """A touch's value when it is text or a number (CASE keeps json_type off
    what is not JSON)."""
    if col not in have:
        return "NULL"
    return (f"CASE WHEN json_valid({col}) THEN CASE WHEN json_type({col}) = 'object' THEN "
            f"CASE WHEN json_type({col}, '$.{key}') IN ('text', 'integer', 'real') THEN "
            f"json_extract({col}, '$.{key}') END END END")


def _elapsed(have: set) -> str:
    """Milliseconds from first_touch.at to created_at, by julianday."""
    if "first_touch" not in have:
        return "NULL"
    at = "json_extract(first_touch, '$.at')"
    return (f"CASE WHEN json_valid(first_touch) THEN CASE WHEN json_type(first_touch) = 'object' "
            f"THEN CASE WHEN json_type(first_touch, '$.at') = 'text' AND "
            f"{at} GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]*' THEN "
            f"CAST(ROUND((julianday(created_at) - julianday({at})) * {DAY_MS}) AS INTEGER) "
            f"END END END")


def _minute(col: str, have: set) -> str:
    """The touch's `at` as whole minutes since the epoch, by strftime."""
    if col not in have:
        return "NULL"
    return (f"CASE WHEN json_valid({col}) THEN CASE WHEN json_type({col}) = 'object' THEN "
            f"CASE WHEN json_type({col}, '$.at') = 'text' THEN "
            f"CAST(strftime('%s', json_extract({col}, '$.at')) AS INTEGER) / 60 END END END")


def _bucket(ms: str) -> str:
    cuts = " ".join(f"WHEN {ms} < {top} THEN '{name}'" for top, name in CUTS)
    return (f"CASE WHEN {ms} IS NULL THEN 'unknown' WHEN {ms} < 0 THEN 'clock_error' "
            f"{cuts} ELSE '>90d' END")


def _visits(have: set) -> str:
    if "visits" not in have:
        return "'unknown'"
    v = "visits"
    return (f"CASE WHEN typeof({v}) IN ('integer', 'real') AND {v} >= 0 AND "
            f"{v} = CAST({v} AS INTEGER) THEN CASE WHEN {v} <= 2 THEN "
            f"CAST(CAST({v} AS INTEGER) AS TEXT) WHEN {v} <= 5 THEN '3-5' "
            f"WHEN {v} <= 10 THEN '6-10' ELSE '11+' END ELSE 'unknown' END")


def _query(have: set) -> str:
    """One local day's leads grouped by everything leads.json splits them by."""
    page = ("SUBSTR(CASE WHEN instr(page, '?') > 0 THEN substr(page, 1, instr(page, '?') - 1) "
            "ELSE page END, 1, 120)") if "page" in have else "NULL"
    inner = ["COALESCE(NULLIF(type, ''), 'unknown')",
             "COALESCE(NULLIF(status, ''), 'new')",
             page, "SUBSTR(LOWER(locale), 1, 10)" if "locale" in have else "NULL",
             _visits(have), _elapsed(have)]
    for col in ("first_touch", "last_touch"):
        inner.append(_object(col, have))
        inner += [_field(col, key, have) for key in FIELDS]
        inner.append(_minute(col, have))
    names = [f"c{i}" for i in range(len(inner))]
    cols = ", ".join(f"{e} AS {c}" for e, c in zip(inner, names))
    return (f"SELECT {', '.join(names)}, {_bucket('c5')}, COUNT(*) FROM "
            f"(SELECT {cols} FROM submissions WHERE created_at >= ? AND created_at < ?) "
            f"GROUP BY {', '.join(names)}")


# ---------------------------------------------------------------- labels

def _clean(v) -> str:
    return "" if v is None else str(v).strip()


def _labels(is_object, values) -> dict:
    """The audit's labels of one touch from its grouped raw fields."""
    if not is_object:
        return {"source": NONE, "ai": NONE, "campaign": NONE, "utm_source": NONE,
                "utm_medium": NONE, "landing": NONE, "paid": False, "page": ""}
    f = {k: _clean(v) for k, v in zip(FIELDS, values)}
    tags = [(k, f[x]) for k, x in (("utm_source", "utmSource"), ("utm_medium", "utmMedium"),
                                   ("gclid", "gclid"), ("gbraid", "gbraid"),
                                   ("wbraid", "wbraid"), ("msclkid", "msclkid"),
                                   ("fbclid", "fbclid")) if f[x]]
    seen = SimpleNamespace(referrer=f"https://{f['referrerHost']}/" if f["referrerHost"] else "",
                           url="/?" + urlencode(tags) if tags else "/")
    cut = {k: f[x].lower()[:60] or NONE for k, x in (
        ("ai", "aiSource"), ("campaign", "utmCampaign"), ("utm_source", "utmSource"),
        ("utm_medium", "utmMedium"))}
    return {"source": source_of(seen, bool(f["aiSource"]), set()), **cut,
            "landing": f["landingPath"][:120] or NONE, "page": f["landingPath"],
            "paid": any(f[k] for k in PAID_CLICK_IDS) or f["utmMedium"].lower() in PAID_MEDIUMS}


def _record(row: tuple) -> dict:
    kind, status, page, locale, visits, ms = row[:6]
    k = len(FIELDS) + 2
    first, last = row[6:6 + k], row[6 + k:6 + 2 * k]
    out = {"type": kind, "status": status, "page": page or NONE, "locale": locale or NONE,
           "visits": visits, "ms": ms, "bucket": row[-2], "n": row[-1],
           "first": _labels(first[0], first[1:-1]), "last": _labels(last[0], last[1:-1])}
    out["first"]["minute"], out["last"]["minute"] = first[-1], last[-1]
    return out


# ------------------------------------------------------------- likely AI

_CUT = re.compile(r"[?#]")


def _bare(path: str) -> str:
    got = _CUT.split(path or "", 1)[0][:70]
    while len(got) > 1 and got.endswith("/"):
        got = got[:-1]
    return got or "/"


def _fetches(history, site: str, first: date, last: date) -> tuple[set, dict] | None:
    """(the verified whole days with fetch records, {page: [(minute, assistant)]})
    from the history file, read-only, by SQL."""
    if history is None or not Path(history).is_file():
        return None
    db = sqlite3.connect(f"file:{Path(history).resolve()}?mode=ro", uri=True)
    try:
        span = (site, first.isoformat(), last.isoformat())
        days = {d for (d,) in db.execute(
            "SELECT x.day FROM day_extras x JOIN days d ON d.site = x.site AND d.day = x.day "
            "WHERE x.site = ? AND x.kind = 'ai_fetches' AND x.day BETWEEN ? AND ? "
            "AND d.verified = 1 AND COALESCE(d.partial_from, '') = '' "
            "AND COALESCE(d.partial_until, '') = '' AND json_valid(x.data) "
            "AND json_type(x.data, '$.rows') = 'array'", span)}
        pages: dict = {}
        for day, stamp, who, path in db.execute(
                "SELECT x.day, CAST(strftime('%s', json_extract(r.value, '$[0]')) AS INTEGER) "
                "/ 60, json_extract(r.value, '$[1]'), json_extract(r.value, '$[2]') "
                "FROM day_extras x, json_each(x.data, '$.rows') r WHERE x.site = ? AND "
                "x.kind = 'ai_fetches' AND x.day BETWEEN ? AND ? AND json_valid(x.data)", span):
            if day in days and stamp is not None:
                pages.setdefault(_bare(str(path)), []).append((stamp, str(who)))
    finally:
        db.close()
    return days, pages


def _likely(lab: dict, fetched, window: int, tz) -> str:
    if lab["source"] != "Direct or unknown" or lab["campaign"] != NONE:
        return NONE
    stamp = lab.get("minute")
    if fetched is None or stamp is None or not lab["page"]:
        return "(not recorded)"
    days, pages = fetched
    for edge in (stamp - window, stamp):
        if datetime.fromtimestamp(edge * 60, tz).date().isoformat() not in days:
            return "(not recorded)"
    who = {w for m, w in pages.get(_bare(lab["page"]), ()) if m <= stamp <= m + window}
    if not who:
        return NONE
    return who.pop() if len(who) == 1 else AI_LIKELY_MANY


def _attribution(config: dict | None) -> tuple[bool, int]:
    got = (config or {}).get("attribution") or {}
    on = got.get("ai_likely", True) not in (False, "false", "no", "off", 0)
    try:
        return on, max(0, int(got.get("ai_window_minutes", 15)))
    except (TypeError, ValueError):
        return on, 15


# ---------------------------------------------------------------- funnel

def _words(config: dict, key: str, default) -> list[str]:
    got = setting(config or {}, "leads", key)
    return (got.split() if isinstance(got, str) else list(got)) if got else list(default)


def _matches(entries: list[str]):
    pages = {e.rstrip("/") or "/" for e in map(str, entries) if e[:1] == "/"}
    last = {e.strip("/").lower() for e in map(str, entries) if e[:1] != "/"}

    def hit(path: str) -> bool:
        bare = str(path).partition("?")[0]
        whole = bare.rstrip("/") or "/"
        tail = whole.split("/")[-1].lower() if whole != "/" else ""
        return whole in pages or tail in last
    return hit


def _log_steps(journeys: list[dict], config: dict) -> dict:
    """readers, pricing, form_page per visit source, recounted."""
    pricing = _matches(_words(config, "pricing_paths", PRICING_PAGES))
    form = _matches(_words(config, "form_paths", FORM_PAGES))
    out: dict = {}
    for j in journeys:
        seen = [e[0] for e in (j.get("trail") or []) if isinstance(e, (list, tuple)) and len(e)]
        seen += [j["landing"]] if j.get("landing") else []
        got = out.setdefault(j.get("source") or "Direct or unknown", Counter())
        got["readers"] += 1
        got["pricing"] += any(map(pricing, seen))
        got["form_page"] += any(map(form, seen))
    return out


# --------------------------------------------------------------- recount

def audit_leads(path, tz, first: date, last: date, journeys: list[dict] | None = None,
                config: dict | None = None, history=None) -> dict:
    """The recount of [first, last]: per local day, the leads grouped by SQL
    (`records`), and leads by type and rows by status (`days`); the
    funnel's log steps when `journeys` are given. `history`: the history
    file, for each touch's likely_ai."""
    on, window = _attribution(config)
    fetched = _fetches(history, site_name(config or {}),
                       last - timedelta(days=FETCH_DAYS + 1), last) if on else None
    db = connect(Path(path))
    try:
        have = _columns(db)
        sql = _query(have)
        records, days = {}, {}
        d = first
        while d <= last:
            got = [_record(r) for r in db.execute(sql, _bounds(d, tz))]
            for r in got:
                for which in ("first", "last"):
                    r[which]["likely"] = _likely(r[which], fetched, window, tz)
            leads, status = Counter(), Counter()
            for r in got:
                status[r["status"]] += r["n"]
                if r["status"] not in LEFT_OUT:
                    leads[r["type"]] += r["n"]
            records[d.isoformat()] = got
            days[d.isoformat()] = {"leads": dict(leads), "status": dict(status)}
            d += timedelta(days=1)
    finally:
        db.close()
    return {"first": first.isoformat(), "last": last.isoformat(), "days": days,
            "records": records, "has_visits": "visits" in have,
            "log": None if journeys is None else _log_steps(journeys, config or {})}


def _within(audit: dict, first: str, last: str) -> list[dict]:
    return [r for day, recs in audit["records"].items() if first <= day <= last for r in recs]


def _period(recs: list[dict]) -> dict:
    out = {"leads": Counter(), "status": Counter(), "page": Counter(), "locale": Counter()}
    for which in ("first", "last"):
        for dim in ("source", "ai", "utm_campaign", "landing"):
            out[f"{which}_touch.{dim}"] = Counter()
    crossed = {k: {} for k in ("first_touch", "last_touch", "ai_first", "ai_last")}
    for r in recs:
        n = r["n"]
        out["status"][r["status"]] += n
        if r["status"] in LEFT_OUT:
            continue
        out["leads"][r["type"]] += n
        out["page"][r["page"]] += n
        out["locale"][r["locale"]] += n
        for which in ("first", "last"):
            lab = r[which]
            for dim, key in (("source", "source"), ("ai", "ai"), ("utm_campaign", "campaign"),
                             ("landing", "landing")):
                out[f"{which}_touch.{dim}"][lab[key]] += n
            for name, key in ((f"{which}_touch", "source"), (f"ai_{which}", "ai")):
                got = crossed[name].setdefault(lab[key], Counter())
                got[r["type"]] += n
    return {"flat": {k: dict(v) for k, v in out.items()},
            "crossed": {k: {s: dict(c) for s, c in v.items()} for k, v in crossed.items()}}


def _nonzero(d) -> dict:
    return {k: v for k, v in (d or {}).items() if v}


# ---------------------------------------------------------------- compare

def findings(built: dict, audit: dict) -> dict[str, list[str]]:
    """Where leads.json and the recount disagree, by block ("period",
    "by_source_type", "funnel", "attribution_rows", "time_to_convert") or
    day ("days/<day>"). A block the recount does not cover is skipped."""
    out: dict[str, list[str]] = {}

    def say(block: str, text: str) -> None:
        out.setdefault(block, []).append(text)

    def covered(block) -> bool:
        return isinstance(block, dict) and "state" not in block and "first" in block and \
            audit["first"] <= block["first"] and block["last"] <= audit["last"]

    for d in built.get("days") or []:
        want = audit["days"].get(d["day"])
        if want is None or d.get("state") == "withheld":
            continue
        if _nonzero(d["leads"]) != want["leads"]:
            say(f"days/{d['day']}", f"leads {d['leads']} != recount {want['leads']}")
        if _nonzero(d["status"]) != want["status"]:
            say(f"days/{d['day']}", f"statuses {d['status']} != recount {want['status']}")
        if (d["spam"], d["duplicates"]) != (want["status"].get("spam", 0),
                                            want["status"].get("duplicate", 0)):
            say(f"days/{d['day']}", f"spam {d['spam']} or duplicates {d['duplicates']} "
                                    f"!= recount {want['status']}")
    p = built.get("period")
    if covered(p):
        want = _period(_within(audit, p["first"], p["last"]))
        for name, got in (("leads", p["leads"]), ("status", p["status"]), ("page", p["page"]),
                          ("locale", p["locale"]),
                          *((f"{w}.{dim}", p[w][dim]) for w in ("first_touch", "last_touch")
                            for dim in ("source", "ai", "utm_campaign", "landing"))):
            if _nonzero(got) != want["flat"][name]:
                say("period", f"{name} {got} != recount {want['flat'][name]}")
        crossed = built.get("by_source_type")
        if isinstance(crossed, dict) and "state" not in crossed:
            for name, mine in want["crossed"].items():
                if crossed.get(name) != mine:
                    say("by_source_type", f"{name} {crossed.get(name)} != recount {mine}")
    _funnel(built.get("funnel"), audit, covered, say)
    _rows(built, audit, covered, say)
    return out


def _funnel(f, audit: dict, covered, say) -> None:
    if not covered(f):
        return
    want: dict = {}
    for r in _within(audit, f["first"], f["last"]):
        kind = r["type"]
        step = ("demo_opened" if kind == "demo_opened" else "demo_booked"
                if kind == "demo_booked" else "leads" if kind in FORM_KINDS else None)
        if step and r["status"] not in LEFT_OUT:
            want.setdefault(r["first"]["source"], Counter())[step] += r["n"]
    steps = STEP_NAMES[3:] if audit["log"] is None else STEP_NAMES
    for src, c in (audit["log"] or {}).items():
        want.setdefault(src, Counter()).update(c)
    want = {s: _nonzero(c) for s, c in want.items() if _nonzero(c)}
    got = {r["source"]: _nonzero({k: r[k] for k in steps}) for r in f.get("by_source") or []}
    got = {s: c for s, c in got.items() if c}
    if got != want:
        say("funnel", f"by source {got} != recount {want}")
    total = {k: sum(c.get(k, 0) for c in want.values()) for k in steps}
    if {k: (f.get("total") or {}).get(k) for k in steps} != total:
        say("funnel", f"total {f.get('total')} != recount {total}")


def _rows(built: dict, audit: dict, covered, say) -> None:
    days = set(audit["records"])
    rows = built.get("attribution_rows")
    if isinstance(rows, list):
        want = Counter()
        for day, recs in audit["records"].items():
            for r in recs:
                for which in ("first", "last"):
                    lab = r[which]
                    want[(day, r["type"], r["status"], which, lab["source"], lab["ai"],
                          lab["campaign"], lab["utm_source"], lab["utm_medium"],
                          lab["landing"], lab["paid"], lab["likely"])] += r["n"]
        got = Counter({tuple(r[:-1]): r[-1] for r in rows if r[0] in days})
        if got != want:
            diff = sorted(set(got.items()) ^ set(want.items()))[:3]
            say("attribution_rows", f"rows differ from the recount, e.g. {diff}")
    t = built.get("time_to_convert")
    if not isinstance(t, dict) or "state" in t:
        return
    buckets, visits, known = Counter(), Counter(), Counter()
    for day, recs in audit["records"].items():
        for r in recs:
            if r["status"] in LEFT_OUT:
                continue
            buckets[(day, r["type"], r["bucket"])] += r["n"]
            visits[(day, r["type"], r["visits"])] += r["n"]
            if r["ms"] is not None and r["ms"] >= 0 and t["first"] <= day <= t["last"]:
                known[r["ms"]] += r["n"]
    if Counter({tuple(r[:-1]): r[-1] for r in t["rows"] if r[0] in days}) != buckets:
        say("time_to_convert", "the buckets differ from the julianday recount")
    if t.get("visits_rows") is None:
        if audit["has_visits"]:
            say("time_to_convert", "visits are not given, yet the column exists")
    elif Counter({tuple(r[:-1]): r[-1] for r in t["visits_rows"] if r[0] in days}) != visits:
        say("time_to_convert", "the visits before the lead differ from the recount")
    if covered(t):
        n = sum(known.values())
        median = _median(known) if n >= 10 else None
        if (t["known"], t["median_hours"]) != (n, median):
            say("time_to_convert", f"known {t['known']}, median {t['median_hours']} != "
                                   f"recount {n}, {median}")


def _median(known: Counter) -> float:
    """The middle known time in hours (the mean of the two middle ones for
    an even count), from {ms: n}."""
    n = sum(known.values())
    want = [(n - 1) // 2, n // 2]
    got, seen = [], 0
    for ms in sorted(known):
        while want and want[0] < seen + known[ms]:
            got.append(ms)
            want.pop(0)
        seen += known[ms]
    return round((got[0] + got[1]) / 2 / 3_600_000, 1)


def compare(built: dict, audit: dict) -> list[str]:
    """Where leads.json and the SQL recount disagree, as one list."""
    return [f"{block}: {p}" for block, problems in findings(built, audit).items()
            for p in problems]


def daily(ctx, day: date) -> list[str] | None:
    """run-daily's step (audit_more.DAILY's contract): leads.json's figures
    as counted today, against the recount of the same 180 days. None when
    leads are not set up. A body that fails its own sums is a mismatch; a
    database that cannot be read is an error."""
    from .leads import DAYS, blob, db_path, fetch_history, site_journeys
    path = db_path(ctx.config)
    if path is None:
        return None
    journeys, first = site_journeys(ctx)
    today = ctx.now.date()
    with fetch_history(ctx) as history:
        built = blob(ctx.config, ctx.tz, today, journeys, first, audited=False,
                     history=history)
    if not built["available"]:
        if built.get("problems"):
            return list(built["problems"])
        raise OSError(built["error"])
    return compare(built, audit_leads(path, ctx.tz, today - timedelta(days=DAYS - 1), today,
                                      journeys=journeys, config=ctx.config,
                                      history=getattr(history, "path", None)))
