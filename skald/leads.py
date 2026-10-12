"""Leads from the website's CMS, as aggregates beside the traffic (leads.json).

The website keeps every lead in its own SQLite database (a Payload CMS,
collection `submissions`): trial sign-ups, contact messages, early-access
requests, and the "Book a demo" dialog opened or booked. This module reads
that file - **read-only**, never creating or writing it - and turns it into
counts: leads per day by type, statuses, and the leads of the last 30 days
broken down by where the lead's own browser says it first and last came
from. Nothing that names a person leaves this module: no name, email,
phone, company, form field, session id or address hash is ever read into
the output.

Two systems, never joined. The logs know visits; the CMS knows leads. A
lead's "first touch" is what its browser remembered (localStorage, the very
first arrival on that browser), which is not the source of any one visit in
the logs (EDGE-CASES E7). So the funnel puts them side by side for the same
days - readers, pricing and form pages from the logs' journeys, by the
visit's source; demos opened, leads and demos booked from the CMS, by the
lead's first-touch source - and never divides one by the other per visit.

Spam and duplicates are kept by the website (status `spam` / `duplicate`)
and are left out of every lead count here, the same way the website's own
export leaves them out of the team's mail; they are counted on their own.

Config:

    leads:
      db: /path/to/website/payload.db     # absent: leads.json says not available
      admin_note: ...                     # where to see the details
      pricing_paths: [pricing, tarifs]    # optional overrides, see below
      form_paths: [signup, contact, join]

A path entry starting with "/" matches that exact page (with or without
the trailing slash); any other entry matches a page whose last segment is
that word, in any locale (/pricing/, /ca/pricing/, /ca/fr/tarifs/).

Phase 4 adds, over the same 180 days: `attribution_rows` (leads by day,
type, status and touch, with the touch's source, assistant, campaign, utm
source and medium, landing page and whether it was paid), so the app sums
any range; and `time_to_convert` (from the first touch to the lead, in
buckets, and the visits the browser counted before it). Statuses are as
of now: the team's later changes rewrite past days.

`likely_ai` on each attribution row (inferred, ai_likely.py): for a touch
whose source is "Direct or unknown" with no utm_campaign, the assistant
whose user fetcher fetched the touch's landing page in the same minute as
its `at` or up to `attribution.ai_window_minutes` before - from the stored
user fetches (day kind `ai_fetches`, verified whole days) - else "(none)";
"(not recorded)" when those fetches were not kept or the touch has no page
or time; "(none)" for every other touch.

`audit_leads.py` recounts every figure by a different road - SQL GROUP BY
over json_extract within UTC bounds worked out per local day, with its own
source rules - so a mistake here shows up as a disagreement. Each time the
file is built a block the recount disagrees with is withheld
({"state": "withheld", "why"}), a day on its own. `skald leads --audit`
and run-daily run the same comparison and report it.
"""
from __future__ import annotations

import json
import sqlite3
import statistics
from collections import Counter
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode

from . import dimensions as dim
from .classify import FORM_PAGES, PAID_CLICK_IDS, PAID_MEDIUMS, PRICING_PAGES
from .config import setting

TYPES = ["signup", "contact", "waitlist", "demo_opened", "demo_booked"]
STATUSES = ["new", "contacted", "qualified", "won", "lost", "spam", "duplicate"]
EXCLUDED = ("spam", "duplicate")
# The steps of the funnel, in order. The first three are the logs', the
# last three the CMS's.
STEPS = ["readers", "pricing", "form_page", "demo_opened", "leads", "demo_booked"]
LOG_STEPS = STEPS[:3]
FORM_TYPES = ("signup", "contact", "waitlist")
NONE = "(none)"
DAYS = 180
PERIOD_DAYS = 30
TOUCH_DIMS = ("source", "ai", "utm_campaign", "landing")
TOUCHES = (("first", "first_touch"), ("last", "last_touch"))
ATTRIBUTION_COLUMNS = ["day", "type", "status", "touch", "source_type", "ai", "campaign",
                       "utm_source", "utm_medium", "landing", "paid", "likely_ai", "n"]
# From the first touch to the lead, in elapsed time; "1-7d" is 1 to 7 whole days.
CONVERT_BUCKETS = ["<1h", "<1d", "1-7d", "8-30d", "31-90d", ">90d", "unknown", "clock_error"]
VISIT_BUCKETS = ["0", "1", "2", "3-5", "6-10", "11+", "unknown"]
MIN_MEDIAN = 10
BLOCKS = ("period", "by_source_type", "funnel", "attribution_rows", "time_to_convert")

ADMIN_NOTE = ("Aggregates only. Each lead (name, email, form, attribution) is in the "
              "website's admin at /admin, reached through the SSH tunnel to the server.")

# Columns read, and never any other: personal fields are not even selected.
COLUMNS = ("created_at", "type", "status", "locale", "page", "ai_source",
           "first_touch", "last_touch", "visits")


# ------------------------------------------------------------------ reading

def db_path(config: dict) -> Path | None:
    raw = setting(config, "leads", "db")
    return Path(str(raw)).expanduser() if raw else None


def connect(path: Path) -> sqlite3.Connection:
    """The CMS file, read-only. Refuses a file that does not exist rather
    than letting sqlite create an empty one."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"leads database not found: {path}")
    return sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)


def _columns(db: sqlite3.Connection) -> set[str]:
    return {r[1] for r in db.execute("PRAGMA table_info(submissions)")}


def read_rows(db: sqlite3.Connection) -> list[dict]:
    """Every lead as {column: value} for COLUMNS only; a column an older
    schema lacks comes back as None."""
    have = _columns(db)
    if "created_at" not in have or "type" not in have:
        raise ValueError("the submissions table has no created_at or type column")
    picked = [c if c in have else f"NULL AS {c}" for c in COLUMNS]
    cur = db.execute(f"SELECT {', '.join(picked)} FROM submissions")
    return [dict(zip(COLUMNS, row)) for row in cur]


def _utc(text) -> datetime | None:
    if not text:
        return None
    try:
        when = datetime.fromisoformat(str(text).replace("Z", "+00:00"))
    except ValueError:
        return None
    return when if when.tzinfo else when.replace(tzinfo=timezone.utc)


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


def _s(touch: dict, key: str) -> str:
    v = touch.get(key)
    ok = isinstance(v, (str, int, float)) and not isinstance(v, bool)
    return str(v).strip() if ok else ""


def touch_source(touch: dict | None) -> str:
    """A touch's source as one of dimensions.SOURCE_TYPES, by the same rules
    the logs use for a reader's first page; NONE when the lead carried none."""
    if touch is None:
        return NONE
    if _s(touch, "aiSource"):
        return "AI assistant"
    host = _s(touch, "referrerHost")
    tags = [(k, _s(touch, f)) for k, f in (
        ("utm_source", "utmSource"), ("utm_medium", "utmMedium"), ("gclid", "gclid"),
        ("msclkid", "msclkid"), ("fbclid", "fbclid")) if _s(touch, f)]
    url = "/?" + urlencode(tags) if tags else "/"
    return dim.source_type(f"https://{host}/" if host else "", url, False, set())


def touch_labels(touch: dict | None) -> dict[str, str]:
    """{dimension: label} for one touch: source type, assistant, campaign,
    landing page. NONE for what it did not carry."""
    if touch is None:
        return {d: NONE for d in TOUCH_DIMS}
    return {"source": touch_source(touch),
            "ai": _s(touch, "aiSource").lower()[:60] or NONE,
            "utm_campaign": _s(touch, "utmCampaign").lower()[:60] or NONE,
            "landing": _s(touch, "landingPath")[:120] or NONE}


def local_day(row: dict, tz) -> date | None:
    when = _utc(row.get("created_at"))
    return when.astimezone(tz).date() if when else None


# --------------------------------------------------------------- counting

def counted(row: dict) -> bool:
    """A lead, not spam or a duplicate."""
    return (row.get("status") or "new") not in EXCLUDED


def day_counts(rows: list[dict], tz, first: date, last: date) -> list[dict]:
    """One entry per local day in [first, last], oldest first."""
    per: dict[date, dict] = {}
    for row in rows:
        d = local_day(row, tz)
        if d is None or not first <= d <= last:
            continue
        got = per.setdefault(d, {"leads": Counter(), "status": Counter(),
                                 "spam": 0, "duplicates": 0})
        status = row.get("status") or "new"
        got["status"][status] += 1
        if status == "spam":
            got["spam"] += 1
        elif status == "duplicate":
            got["duplicates"] += 1
        else:
            got["leads"][row.get("type") or "unknown"] += 1
    out = []
    for i in range((last - first).days + 1):
        d = first + timedelta(days=i)
        got = per.get(d)
        out.append({"day": d.isoformat(),
                    "leads": dict(got["leads"]) if got else {},
                    "status": dict(got["status"]) if got else {},
                    "spam": got["spam"] if got else 0,
                    "duplicates": got["duplicates"] if got else 0})
    return out


def period(rows: list[dict], tz, first: date, last: date) -> dict:
    """The leads of [first, last] broken down; spam and duplicates are in
    `status` only. Every other breakdown adds up to the leads."""
    leads, status = Counter(), Counter()
    touches = {"first_touch": {d: Counter() for d in TOUCH_DIMS},
               "last_touch": {d: Counter() for d in TOUCH_DIMS}}
    page, locale = Counter(), Counter()
    # Source and assistant crossed with the lead's type: which source and
    # which assistant brought sign-ups, contact requests, demos booked.
    by_type = {k: {} for k in ("first_touch", "last_touch", "ai_first", "ai_last")}
    for row in rows:
        d = local_day(row, tz)
        if d is None or not first <= d <= last:
            continue
        status[row.get("status") or "new"] += 1
        if not counted(row):
            continue
        leads[row.get("type") or "unknown"] += 1
        kind = row.get("type") or "unknown"
        for which, column in (("first_touch", "first_touch"), ("last_touch", "last_touch")):
            labels = touch_labels(_touch(row.get(column)))
            for dname, label in labels.items():
                touches[which][dname][label] += 1
            by_type[which].setdefault(labels["source"], Counter())[kind] += 1
            ai = "ai_first" if which == "first_touch" else "ai_last"
            by_type[ai].setdefault(labels["ai"], Counter())[kind] += 1
        page[(str(row.get("page") or "").split("?")[0][:120]) or NONE] += 1
        locale[(str(row.get("locale") or "").lower()[:10]) or NONE] += 1
    out = {"first": first.isoformat(), "last": last.isoformat(),
           "leads": dict(leads), "status": dict(status),
           "page": dict(page.most_common()), "locale": dict(locale.most_common()),
           "by_type": {k: {name: dict(c) for name, c in v.items()} for k, v in by_type.items()}}
    for which, dims in touches.items():
        out[which] = {d: dict(c.most_common()) for d, c in dims.items()}
    return out


# ------------------------------------------------- attribution (phase 4)

def paid(touch: dict | None) -> bool:
    """An ad click id, or a utm_medium that says paid."""
    if touch is None:
        return False
    return any(_s(touch, k) for k in PAID_CLICK_IDS) or \
        _s(touch, "utmMedium").lower() in PAID_MEDIUMS


def touch_likely(t: dict | None, index: dict | None, window: int, tz) -> str:
    """A touch's likely_ai (see the module's note)."""
    from .ai_likely import likely_for
    if t is None or touch_source(t) != "Direct or unknown" or _s(t, "utmCampaign"):
        return NONE
    raw = t.get("at")
    return likely_for(index, _s(t, "landingPath"), _utc(raw) if isinstance(raw, str) else None,
                      window, tz)


def attribution(rows: list[dict], tz, first: date, last: date,
                likely: tuple | None = None) -> list[list]:
    """Every lead of [first, last] (spam and duplicates too: the status says
    which) twice, once per touch, as ATTRIBUTION_COLUMNS rows. A lead
    without the touch is all "(none)", so each touch adds up to the day's
    statuses. `likely`: (ai_likely.fetch_index, window), or None when the
    fetches are not at hand."""
    index, window = likely or (None, 0)
    got: Counter = Counter()
    for row in rows:
        d = local_day(row, tz)
        if d is None or not first <= d <= last:
            continue
        for which, column in TOUCHES:
            t = _touch(row.get(column))
            lab = touch_labels(t)
            utm = [(_s(t, k).lower()[:60] if t else "") or NONE for k in ("utmSource", "utmMedium")]
            got[(d.isoformat(), row.get("type") or "unknown", row.get("status") or "new", which,
                 lab["source"], lab["ai"], lab["utm_campaign"], *utm, lab["landing"],
                 paid(t), touch_likely(t, index, window, tz))] += 1
    return [[*key, n] for key, n in sorted(got.items())]


def elapsed_ms(row: dict) -> int | None:
    """Milliseconds from the first touch's `at` to the lead; None when
    either is missing or not a time."""
    t = _touch(row.get("first_touch"))
    made = _utc(row.get("created_at"))
    raw = t.get("at") if t else None
    when = _utc(raw) if isinstance(raw, str) else None
    if made is None or when is None:
        return None
    return round((made - when).total_seconds() * 1000)


def convert_bucket(ms: int | None) -> str:
    if ms is None:
        return "unknown"
    if ms < 0:
        return "clock_error"
    if ms < 3_600_000:
        return "<1h"
    days = ms // 86_400_000              # whole days elapsed
    if days < 1:
        return "<1d"
    for top, name in ((7, "1-7d"), (30, "8-30d"), (90, "31-90d")):
        if days <= top:
            return name
    return ">90d"


def visits_bucket(v) -> str:
    """The website's `visits` (the browser's count when it sent the form)."""
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return "unknown"
    if isinstance(v, float) and not v.is_integer() or v < 0:
        return "unknown"
    v = int(v)
    if v <= 2:
        return str(v)
    return "3-5" if v <= 5 else "6-10" if v <= 10 else "11+"


def time_to_convert(rows: list[dict], tz, first: date, last: date, has_visits: bool) -> dict:
    """Leads of [first, last] (spam and duplicates left out) by the time from
    their first touch, per day and type; the median over the whole period
    only with MIN_MEDIAN known times."""
    buckets: Counter = Counter()
    visits: Counter = Counter()
    known: list[int] = []
    for row in rows:
        d = local_day(row, tz)
        if d is None or not first <= d <= last or not counted(row):
            continue
        ms = elapsed_ms(row)
        if ms is not None and ms >= 0:
            known.append(ms)
        kind = row.get("type") or "unknown"
        buckets[(d.isoformat(), kind, convert_bucket(ms))] += 1
        visits[(d.isoformat(), kind, visits_bucket(row.get("visits")))] += 1
    median = (round(statistics.median(known) / 3_600_000, 1)
              if len(known) >= MIN_MEDIAN else None)
    return {"first": first.isoformat(), "last": last.isoformat(),
            "buckets": CONVERT_BUCKETS, "rows": [[*k, n] for k, n in sorted(buckets.items())],
            "known": len(known), "median_hours": median,
            "visits_buckets": VISIT_BUCKETS if has_visits else None,
            "visits_rows": [[*k, n] for k, n in sorted(visits.items())] if has_visits else None}


# ---------------------------------------------------------------- funnel

def _segment(path: str) -> str:
    return path.split("?")[0].rstrip("/").rsplit("/", 1)[-1].lower()


def path_test(entries):
    """A test for a path: exact paths (entries starting with "/") or last
    segments (any other entry)."""
    exact = {str(e).rstrip("/") or "/" for e in entries if str(e).startswith("/")}
    words = {str(e).strip("/").lower() for e in entries if not str(e).startswith("/")}

    def test(path: str) -> bool:
        bare = path.split("?")[0]
        return (bare.rstrip("/") or "/") in exact or _segment(bare) in words
    return test


def _paths(config: dict, key: str, default) -> list:
    got = setting(config, "leads", key)
    if isinstance(got, str):
        got = got.split()
    return list(got) if got else list(default)


def _journey_paths(j: dict) -> list[str]:
    trail = j.get("trail") or []
    paths = [t[0] for t in trail if isinstance(t, (list, tuple)) and t]
    if j.get("landing"):
        paths.append(j["landing"])
    return paths


def funnel(journeys: list[dict], rows: list[dict], tz, first: date, last: date,
           config: dict | None = None) -> dict:
    """Readers, pricing and form pages per visit source (logs) beside demos
    opened, leads and demos booked per first-touch source (CMS), same days."""
    pricing = path_test(_paths(config or {}, "pricing_paths", PRICING_PAGES))
    form = path_test(_paths(config or {}, "form_paths", FORM_PAGES))
    per: dict[str, Counter] = {}
    for j in journeys:
        src = j.get("source") or "Direct or unknown"
        got = per.setdefault(src, Counter())
        paths = _journey_paths(j)
        got["readers"] += 1
        got["pricing"] += 1 if any(pricing(p) for p in paths) else 0
        got["form_page"] += 1 if any(form(p) for p in paths) else 0
    for row in rows:
        d = local_day(row, tz)
        if d is None or not first <= d <= last or not counted(row):
            continue
        kind = row.get("type") or ""
        step = ("demo_opened" if kind == "demo_opened" else "demo_booked"
                if kind == "demo_booked" else "leads" if kind in FORM_TYPES else None)
        if step is None:
            continue
        per.setdefault(touch_source(_touch(row.get("first_touch"))), Counter())[step] += 1
    order = {name: i for i, name in enumerate(dim.SOURCE_TYPES + [NONE])}
    by_source = [{"source": s, **{k: int(c[k]) for k in STEPS}}
                 for s, c in sorted(per.items(), key=lambda kv: (order.get(kv[0], 99), kv[0]))]
    total = {k: sum(r[k] for r in by_source) for k in STEPS}
    return {"first": first.isoformat(), "last": last.isoformat(),
            "days": (last - first).days + 1, "steps": STEPS,
            "note": ("readers, pricing and form_page are visits from the server logs, by the "
                     "visit's source; a client-side move the app served from its cache leaves "
                     "no line, so they are floors. demo_opened, leads (sign-up, contact, early "
                     "access) and demo_booked come from the CMS, by the source the lead's own "
                     "browser first arrived from. Two systems side by side: never divide one "
                     "by the other per visit."),
            "by_source": by_source, "total": total}


# ----------------------------------------------------------------- checks

def check(blob: dict) -> list[str]:
    """Every sum leads.json promises. An empty list: it reconciles."""
    problems: list[str] = []
    if not blob.get("available"):
        return problems
    total = sum(((blob.get("period") or {}).get("leads") or {}).values())
    for name, table in (blob.get("by_source_type") or {}).items():
        got = sum(n for row in table.values() for n in row.values())
        if got != total:
            problems.append(f"by_source_type.{name} sums to {got}, not the {total} leads")
    for d in blob.get("days") or []:
        leads = sum(d["leads"].values())
        if sum(d["status"].values()) != leads + d["spam"] + d["duplicates"]:
            problems.append(f"{d['day']}: statuses {sum(d['status'].values())} != leads "
                            f"{leads} + spam {d['spam']} + duplicates {d['duplicates']}")
        if d["status"].get("spam", 0) != d["spam"] or \
                d["status"].get("duplicate", 0) != d["duplicates"]:
            problems.append(f"{d['day']}: spam or duplicates differ from their status")
    p = blob.get("period") or {}
    want = sum((p.get("leads") or {}).values())
    for which in ("first_touch", "last_touch"):
        for dname, counter in (p.get(which) or {}).items():
            if sum(counter.values()) != want:
                problems.append(f"period {which}.{dname} adds to {sum(counter.values())}, "
                                f"not the {want} leads")
    for dname in ("page", "locale"):
        if sum((p.get(dname) or {}).values()) != want:
            problems.append(f"period {dname} adds to {sum((p.get(dname) or {}).values())}, "
                            f"not the {want} leads")
    in_days = sum(sum(d["leads"].values()) for d in blob.get("days") or []
                  if p and p["first"] <= d["day"] <= p["last"])
    if p and in_days != want:
        problems.append(f"period leads {want} != the same days' leads {in_days}")
    f = blob.get("funnel") or {}
    for r in f.get("by_source") or []:
        for step in ("pricing", "form_page"):
            if r[step] > r["readers"]:
                problems.append(f"funnel {r['source']}: {step} {r[step]} > readers {r['readers']}")
    for k in STEPS:
        if f and sum(r[k] for r in f.get("by_source") or []) != (f.get("total") or {}).get(k):
            problems.append(f"funnel total {k} is not the sum of its sources")
    return problems + _check_more(blob)


def _check_more(blob: dict) -> list[str]:
    """attribution_rows: each touch adds up to the day's statuses;
    time_to_convert: its buckets and its visits each add up to the day's
    leads, and `known` is the sum of the known buckets."""
    problems: list[str] = []
    rows, ttc = blob.get("attribution_rows"), blob.get("time_to_convert")
    per_touch: Counter = Counter()
    for r in rows or []:
        per_touch[(r[0], r[3])] += r[-1]
    convert: Counter = Counter()
    seen: Counter = Counter()
    for r in (ttc or {}).get("rows") or []:
        convert[r[0]] += r[-1]
    for r in (ttc or {}).get("visits_rows") or []:
        seen[r[0]] += r[-1]
    for d in blob.get("days") or []:
        day, leads = d["day"], sum(d["leads"].values())
        everyone = sum(d["status"].values())
        if rows is not None and any(per_touch[(day, t)] != everyone for t, _ in TOUCHES):
            problems.append(f"{day}: attribution_rows do not add up to the {everyone} statuses")
        if ttc and convert[day] != leads:
            problems.append(f"{day}: time_to_convert adds to {convert[day]}, not {leads} leads")
        if ttc and ttc.get("visits_rows") is not None and seen[day] != leads:
            problems.append(f"{day}: time_to_convert visits add to {seen[day]}, not {leads}")
    if ttc:
        known = sum(r[-1] for r in ttc["rows"] if r[2] not in ("unknown", "clock_error"))
        if known != ttc["known"]:
            problems.append(f"time_to_convert known {ttc['known']} != its buckets' {known}")
        if ttc["median_hours"] is not None and ttc["known"] < MIN_MEDIAN:
            problems.append("time_to_convert gives a median over too few known times")
    return problems


# ---------------------------------------------------------------- the file

def _unavailable(error: str, note: str) -> dict:
    return {"available": False, "error": error, "admin_note": note, "types": TYPES,
            "since": None, "days": [], "period": None, "funnel": None,
            "attribution_rows": None, "time_to_convert": None}


def withhold(out: dict, found: dict[str, list[str]]) -> dict:
    """`out` with every block in `found` ({block or "days/<day>": problems})
    replaced by {"state": "withheld", "why"}; "*" withholds them all. Adds
    `withheld`: {block: why}."""
    def why(problems: list[str]) -> str:
        more = f" (and {len(problems) - 3} more)" if len(problems) > 3 else ""
        return ("the second count (audit_leads.py) disagrees: " + "; ".join(problems[:3])
                + more)
    if "*" in found:
        found = {**{b: found["*"] for b in BLOCKS},
                 **{f"days/{d['day']}": found["*"] for d in out["days"]}}
    said = {k: why(v) for k, v in found.items() if v}
    for block in BLOCKS:
        if block in said:
            out[block] = {"state": "withheld", "why": said[block]}
    out["days"] = [{"day": d["day"], "state": "withheld", "why": said[f"days/{d['day']}"]}
                   if f"days/{d['day']}" in said else d for d in out["days"]]
    out["withheld"] = said
    return out


def _audited(out: dict, path: Path, tz, today: date, journeys: list[dict],
             config: dict, history_path=None) -> dict:
    """The second count of every block; a block that disagrees is withheld.
    A recount that cannot run withholds them all."""
    from . import audit_leads
    try:
        recount = audit_leads.audit_leads(path, tz, today - timedelta(days=DAYS - 1), today,
                                          journeys=journeys, config=config,
                                          history=history_path)
        found = audit_leads.findings(out, recount)
    except Exception as why:            # noqa: BLE001 - unchecked figures are withheld
        found = {"*": [f"the recount could not run: {type(why).__name__}: {why}"]}
    return withhold(out, found)


def likely_fetches(config: dict, history, today: date) -> tuple | None:
    """(fetch index, window) for touch_likely, from the whole site's stored
    AI user fetches; None when off or without a history."""
    from .ai_likely import FETCH_DAYS, fetch_index, settings
    from .config import site_name
    got = settings(config)
    if history is None or not got["on"]:
        return None
    first = today - timedelta(days=FETCH_DAYS + 1)
    return fetch_index(history, site_name(config), first, today), got["window"]


def blob(config: dict, tz, today: date, journeys: list[dict],
         journey_first: date, audited: bool = True, history=None) -> dict:
    """leads.json's body. `journeys`: the visits of [journey_first, today].
    audited (the file's way): every block recounted, a disagreeing one
    withheld; False gives the figures as counted, for the recount to check.
    `history` (store.History) holds the AI user fetches for likely_ai."""
    note = str(setting(config, "leads", "admin_note", ADMIN_NOTE))
    path = db_path(config)
    if path is None:
        return _unavailable("leads.db not set", note)
    try:
        db = connect(path)
        try:
            rows = read_rows(db)
            has_visits = "visits" in _columns(db)
        finally:
            db.close()
    except (OSError, sqlite3.Error, ValueError) as why:
        return _unavailable(f"could not read the leads database: {why}", note)
    days = [local_day(r, tz) for r in rows]
    since = min((d for d in days if d is not None), default=None)
    out = {"available": True, "error": None, "admin_note": note, "types": TYPES,
           "since": since.isoformat() if since else None,
           "days": day_counts(rows, tz, today - timedelta(days=DAYS - 1), today),
           "period": period(rows, tz, today - timedelta(days=PERIOD_DAYS), today),
           "by_source_type": None,
           "funnel": funnel(journeys, rows, tz, journey_first, today, config),
           "attribution_columns": ATTRIBUTION_COLUMNS,
           "attribution_rows": attribution(rows, tz, today - timedelta(days=DAYS - 1), today,
                                           likely_fetches(config, history, today)),
           "likely_ai": likely_note(config),
           "time_to_convert": time_to_convert(rows, tz, today - timedelta(days=DAYS - 1), today,
                                              has_visits)}
    out["by_source_type"] = out["period"].pop("by_type")
    problems = check(out)
    if problems:
        return {**_unavailable("leads figures do not reconcile: " + "; ".join(problems[:3]),
                               note), "problems": problems}
    return _audited(out, path, tz, today, journeys, config,
                    getattr(history, "path", None)) if audited else out


def likely_note(config: dict) -> dict:
    from .data_reports import likely_note as note
    return note(config)


def _page_journeys(page) -> tuple[list[dict], date]:
    from .store_visits import journey_days
    keep = journey_days(page.config)
    first = page.today - timedelta(days=keep)
    stored = [j for j in page.history.journeys(page.key, first, page.anchor)
              if (page.states.get(str(j.get("day"))) or {}).get("state") in ("ok", "partial")]
    if page.live_ok:
        stored += list((page.snap or {}).get("journeys") or [])
    return stored, first


def build(page) -> dict:
    """leads.json for a page (data_files.Page). The same on every page: the
    CMS does not know about views, and the funnel uses the whole site's
    journeys."""
    site = page.key.split("::", 1)[0]
    if site != page.key:
        from .data_files import Page
        whole = Page.__new__(Page)
        whole.__dict__.update(page.__dict__)
        whole.key = site
        whole.daily = page.history.daily(site, page.first, page.anchor)
        whole.states = {e["day"].isoformat(): e for e in whole.daily}
        page = whole
    journeys, first = _page_journeys(page)
    return blob(page.config, page.tz, page.today, journeys, first, history=page.history)


# ---------------------------------------------------------------- command

def _text(b: dict) -> str:
    if not b["available"]:
        return f"leads: not available ({b['error']})"
    p, f, t = b["period"], b["funnel"], b.get("time_to_convert")
    lines = []
    if p.get("state") == "withheld":
        lines.append(f"LEADS withheld: {p['why']}")
    else:
        lines.append(f"LEADS {p['first']} to {p['last']} (spam and duplicates excluded)")
        lines += [f"  {k:<12} {p['leads'].get(k, 0):>5}" for k in TYPES]
        lines.append("  status       " + ", ".join(f"{k} {v}" for k, v in p["status"].items()))
        lines.append("  first touch  " + ", ".join(
            f"{k} {v}" for k, v in p["first_touch"]["source"].items()))
    if t and t.get("state") != "withheld":
        got: Counter = Counter()
        for r in t["rows"]:
            got[r[2]] += r[-1]
        median = "not given (under 10 known)" if t["median_hours"] is None \
            else f"{t['median_hours']} hours"
        lines.append(f"TIME TO CONVERT {t['first']} to {t['last']}: "
                     + ", ".join(f"{k} {got[k]}" for k in t["buckets"] if got[k])
                     + f"; median {median}")
    if f.get("state") == "withheld":
        lines.append(f"FUNNEL withheld: {f['why']}")
    else:
        lines.append(f"FUNNEL {f['first']} to {f['last']} ({f['days']} days)")
        lines.append("  " + f"{'source':<20}" + "".join(f"{s:>12}" for s in STEPS))
        for r in f["by_source"] + [{"source": "total", **f["total"]}]:
            lines.append("  " + f"{r['source'][:20]:<20}"
                         + "".join(f"{r[s]:>12}" for s in STEPS))
    lines += [f"  withheld {k}: {v}" for k, v in (b.get("withheld") or {}).items()
              if k.startswith("days/")]
    lines.append("  " + b["admin_note"])
    return "\n".join(lines)


def site_journeys(ctx) -> tuple[list[dict], date]:
    """The whole site's stored journeys of verified days, and their first day."""
    from .config import site_name
    from .store_visits import journey_days
    today = ctx.now.date()
    first = today - timedelta(days=journey_days(ctx.config))
    site = site_name(ctx.config)
    with ctx.history() as history:
        anchor = today - timedelta(days=1)
        states = {e["day"].isoformat(): e["state"] for e in history.daily(site, first, anchor)}
        journeys = [j for j in history.journeys(site, first, anchor)
                    if states.get(str(j.get("day"))) in ("ok", "partial")]
    return journeys, first


def current(ctx, audited: bool = True) -> dict:
    """leads.json's body for the whole site today, from the stored journeys
    of verified days (the command's and run-daily's)."""
    journeys, first = site_journeys(ctx)
    with fetch_history(ctx) as history:
        return blob(ctx.config, ctx.tz, ctx.now.date(), journeys, first, audited, history)


@contextmanager
def fetch_history(ctx):
    """The history file opened read-only, for the AI user fetches behind
    likely_ai; None when there is none."""
    from .store import History
    path = getattr(ctx, "db_path", None)
    if not isinstance(path, (str, Path)) or not Path(path).is_file():
        yield None
        return
    history = History.reader(path)
    try:
        yield history
    finally:
        history.close()


def cmd_leads(ctx) -> int:
    from .audit_leads import audit_leads, compare
    today = ctx.now.date()
    b = current(ctx, audited=not ctx.args.audit)
    if ctx.args.json:
        ctx.out(json.dumps(b, indent=1, ensure_ascii=False))
    else:
        ctx.out(_text(b))
    if not b["available"]:
        return 1
    if ctx.args.audit:
        journeys, _ = site_journeys(ctx)
        got = compare(b, audit_leads(db_path(ctx.config), ctx.tz,
                                     today - timedelta(days=DAYS - 1), today,
                                     journeys=journeys, config=ctx.config,
                                     history=ctx.db_path))
        for p in got:
            ctx.err(f"  - {p}")
        ctx.out("leads audit: " + ("ok, the SQL recount matches" if not got
                                   else f"{len(got)} figures differ"))
        return 1 if got else 0
    return 0


def add_command(sub) -> None:
    p = sub.add_parser("leads", help="leads from the website's CMS, aggregates only "
                       "(read-only); --audit recounts them by SQL")
    p.add_argument("--json", action="store_true", help="print leads.json's body")
    p.add_argument("--audit", action="store_true",
                   help="recount every figure by SQL GROUP BY and compare")
    p.set_defaults(run=cmd_leads)
