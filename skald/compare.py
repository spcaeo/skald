"""Compare any two date ranges: `skald compare` and the helper's
<page>/api/compare (DATA-CONTRACT.md, "Compare").

A is the range being looked at, B the one it is compared with; every figure
is a sum over the **whole, verified days** of each range - a partial,
withheld or missing day is left out and named, never counted as a quiet day.

  metrics      visitors, pages read, visitors from AI, assistant fetches
               (asked, training), search fetches, leads (CMS), returning,
               pages per visitor, 404s people met - from history's totals
  dimensions   pages (page views, every page: day_extras "pages"), and
               sources, AI assistants, countries, continents, devices,
               browsers, systems and campaigns (visitors: day_extras
               "visit_cube", every reader's visit by all its labels at once)

Filters slice the visitors by any cube field (and continent), or by one
page (its readers, views and fetches from the pages blob). A metric a
filter cannot apply to comes back null on both sides, never as a whole-site
figure under a filter. `reconciled` says the dimension rows add up to the
visitors (and the page rows to the page views) over the measured days.
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import date, timedelta

from .classify import Group
from .countries import continent
from .cube import OTHER, VISIT_DIMS

MAX_DAYS = 400
MAX_ROWS = 1000
FILTERS = (*VISIT_DIMS, "continent", "page")
DIMENSIONS = {"sources": "source", "assistants": "assistant", "countries": "country",
              "continents": "continent", "devices": "device", "browsers": "browser",
              "os": "os", "campaigns": "campaign"}
METRICS = (("visitors", "Visitors"), ("pages_read", "Pages read"),
           ("visitors_from_ai", "Visitors from AI"), ("ai_asked", "AI fetches, someone asked"),
           ("ai_training", "AI fetches, to train or index"), ("search", "Search-engine fetches"),
           ("leads", "Leads"), ("returning", "Returning visitors"),
           ("pages_per_visitor", "Pages per visitor"),
           ("not_found_people", "404s people met"))
LEAD_TYPES = ("signup", "contact", "waitlist", "demo_booked")


class Invalid(ValueError):
    pass


def parse_range(text: str) -> tuple[date, date]:
    try:
        a, _, b = (text or "").partition("..")
        first, last = date.fromisoformat(a.strip()), date.fromisoformat((b or a).strip())
    except ValueError:
        raise Invalid(f"a range is YYYY-MM-DD..YYYY-MM-DD, not {text!r}")
    if last < first:
        raise Invalid("a range ends after it starts")
    if (last - first).days + 1 > MAX_DAYS:
        raise Invalid(f"a range is at most {MAX_DAYS} days")
    return first, last


def presets(first: date, last: date) -> dict:
    length = (last - first).days + 1
    try:
        year_first, year_last = first.replace(year=first.year - 1), last.replace(year=last.year - 1)
    except ValueError:                  # 29 February
        year_first = first - timedelta(days=365)
        year_last = last - timedelta(days=365)
    return {"previous": {"from": (first - timedelta(days=length)).isoformat(),
                         "to": (first - timedelta(days=1)).isoformat()},
            "last_year": {"from": year_first.isoformat(), "to": year_last.isoformat()}}


# ---------------------------------------------------------------- one side

# Parsed blobs of past days, kept by the long-lived helper between questions:
# a stored day changes only when it is collected again, which changes its
# collected_at, which is part of the key.
_CACHE: dict = {}
_CACHE_MAX = 3000


def _blobs(history, key: str, days: list[str], kind: str) -> dict[str, object]:
    """{day: parsed blob} for the days that have one."""
    if not days:
        return {}
    marks = ",".join("?" * len(days))
    out = {}
    for day, stamp, data in history.db.execute(
            f"SELECT e.day, d.collected_at, e.data FROM day_extras e JOIN days d "
            f"ON d.site = e.site AND d.day = e.day WHERE e.site = ? AND e.kind = ? "
            f"AND e.day IN ({marks})", (key, kind, *days)):
        tag = (str(history.path), key, day, kind, stamp)
        got = _CACHE.get(tag)
        if got is None:
            try:
                got = json.loads(data)
            except ValueError:
                continue
            if len(_CACHE) >= _CACHE_MAX:
                _CACHE.clear()
            _CACHE[tag] = got
        out[day] = got
    return out


def _page_rows(history, key: str, days: list[str], page: str) -> dict[str, dict]:
    """{day: that page's blob} - read inside SQLite, one page only."""
    if not days:
        return {}
    marks = ",".join("?" * len(days))
    out = {}
    for day, data in history.db.execute(
            f"SELECT day, json_extract(data, ?) FROM day_extras WHERE site = ? AND "
            f"kind = 'pages' AND day IN ({marks})",
            (f'$."{page}"', key, *days)):
        out[day] = json.loads(data) if data else {}
    return out


def _side(history, key: str, site: str, first: date, last: date, filters: dict,
          lead_rows, tz) -> dict:
    states = {e["day"]: e for e in history.daily(key, first, last)}
    used = [d for d, e in states.items() if e["state"] == "ok"]
    excluded = [{"day": d.isoformat(), "state": e["state"]} for d, e in sorted(states.items())
                if e["state"] != "ok"]
    days = [d.isoformat() for d in sorted(used)]
    page = filters.get("page")
    cube_filters = {k: v for k, v in filters.items() if k != "page"}
    dims = {name: Counter() for name in DIMENSIONS}
    pages = Counter()
    visitors_cube = 0
    returning = _blobs(history, key, days, "returning") if not filters else {}
    per_day: dict[str, dict] = {d: {} for d in days}
    if page:
        per_page = _page_rows(history, key, days, page)
        for d, v in per_page.items():
            per_day[d] = {"visitors": int(v.get("readers", 0)), "pages_read": int(v.get("views", 0)),
                          "ai_asked": int(v.get("ai_asked", 0)),
                          "ai_training": int(v.get("ai_training", 0)),
                          "search": int(v.get("search", 0))}
        unmeasured = [d for d in days if d not in per_page]
        got = Counter()
        for d, v in per_page.items():
            pages[page] += int(v.get("views", 0))
            for k in ("readers", "views", "ai_asked", "ai_training", "search"):
                got[k] += int(v.get(k, 0))
            for name in ("sources", "assistants", "countries"):
                dims[name].update({k: int(n) for k, n in (v.get(name) or {}).items()})
            for code, n in (v.get("countries") or {}).items():
                dims["continents"][continent(code)] += int(n)
        metrics = {"visitors": got["readers"], "pages_read": got["views"],
                   "visitors_from_ai": None, "ai_asked": got["ai_asked"],
                   "ai_training": got["ai_training"], "search": got["search"], "leads": None,
                   "returning": None, "pages_per_visitor": None, "not_found_people": None}
    else:
        counts = _blobs(history, key, days, "page_counts")
        cubes = _blobs(history, key, days, "visit_cube")
        unmeasured = [d for d in days if d not in cubes or d not in counts]
        for blob in counts.values():
            for path, v in blob.items():
                pages[path] += v[0]
        combos: Counter = Counter()
        for d, blob in cubes.items():
            day_n = 0
            for row in blob.get("rows") or []:
                combos[tuple(row[:-1])] += row[-1]
                if cube_filters and _passes(row, cube_filters):
                    day_n += row[-1]
            if cube_filters:
                per_day[d] = {"visitors": day_n}
        for labels_t, n in combos.items():
            labels = dict(zip(VISIT_DIMS, labels_t))
            labels["continent"] = (continent(labels["country"]) if labels["country"] != OTHER
                                   else OTHER)
            if any(labels.get(k) != v for k, v in cube_filters.items()):
                continue
            visitors_cube += n
            for name, field in DIMENSIONS.items():
                if field == "assistant" and labels["source"] != "AI assistant":
                    continue
                dims[name][labels[field] or "(none)"] += n
        metrics = _metrics(history, key, days, returning, filters, visitors_cube, lead_rows, tz)
        if not filters:
            per_day = _daily_figures(history, key, days, lead_rows, tz)
    series = []
    for i in range((last - first).days + 1):
        d = (first + timedelta(days=i))
        state = (states.get(d) or {}).get("state", "missing")
        got = per_day.get(d.isoformat()) if state == "ok" else None
        series.append({"day": d.isoformat(), "state": state,
                       **{k: (got.get(k) if got is not None else None) for k in SERIES}})
    return {"from": first.isoformat(), "to": last.isoformat(),
            "days": (last - first).days + 1, "used": len(days), "excluded": excluded,
            "unmeasured": unmeasured, "metrics": metrics, "dims": dims, "pages": pages,
            "visitors_cube": visitors_cube, "series": series}


SERIES = ("visitors", "pages_read", "visitors_from_ai", "ai_asked", "ai_training", "search",
          "leads")


def _passes(row, filters: dict) -> bool:
    labels = dict(zip(VISIT_DIMS, row[:-1]))
    if "continent" in filters:
        labels["continent"] = continent(labels["country"])
    return all(labels.get(k) == v for k, v in filters.items())


def _daily_figures(history, key: str, days: list[str], lead_rows, tz) -> dict[str, dict]:
    """The whole site's figures per used day, for the series."""
    if not days:
        return {}
    marks = ",".join("?" * len(days))
    out = {d: {} for d in days}
    for d, grp, hits, views, readers in history.db.execute(
            f"SELECT day, grp, hits, views, readers FROM groups WHERE site = ? "
            f"AND day IN ({marks})", (key, *days)):
        if grp == Group.PEOPLE.value:
            out[d].update(visitors=readers or 0, pages_read=views or 0)
        elif grp == Group.SEARCH_ENGINE.value:
            out[d]["search"] = hits or 0
    for d, cited in history.db.execute(
            f"SELECT day, cited_visits FROM days WHERE site = ? AND day IN ({marks})",
            (key, *days)):
        out[d]["visitors_from_ai"] = cited or 0
    for d, name, n in history.db.execute(
            f"SELECT day, name, n FROM counts WHERE site = ? AND kind = 'engine_tier' "
            f"AND day IN ({marks})", (key, *days)):
        out[d][f"ai_{name}"] = n
    leads = Counter()
    if lead_rows is not None:
        from .leads import counted, local_day
        for r in lead_rows:
            if counted(r) and r.get("type") in LEAD_TYPES:
                day = local_day(r, tz)
                if day is not None:
                    leads[day.isoformat()] += 1
    for d, got in out.items():
        for k in SERIES:
            got.setdefault(k, 0)
        got["leads"] = leads.get(d, 0) if lead_rows is not None else None
    return out


def _metrics(history, key, days, returning_blobs, filters, visitors_cube, lead_rows,
             tz) -> dict:
    if not days:
        return {k: None for k, _ in METRICS}
    if filters:
        return {"visitors": visitors_cube, **{k: None for k, _ in METRICS if k != "visitors"}}
    marks = ",".join("?" * len(days))
    groups = {g: (h, v, r) for g, h, v, r in history.db.execute(
        f"SELECT grp, SUM(hits), SUM(views), SUM(readers) FROM groups WHERE site = ? "
        f"AND day IN ({marks}) GROUP BY grp", (key, *days))}
    cited = history.db.execute(
        f"SELECT SUM(cited_visits) FROM days WHERE site = ? AND day IN ({marks})",
        (key, *days)).fetchone()[0] or 0
    # `kind IN (...)` lets SQLite seek (site, day, kind) in the key rather
    # than read every count of every day; the second test is the filter.
    counts = {(k, n): v for k, n, v in history.db.execute(
        f"SELECT kind, name, SUM(n) FROM counts WHERE site = ? AND day IN ({marks}) AND "
        f"kind IN ('engine_tier', 'status_people') AND "
        f"(kind = 'engine_tier' OR name = '404') "
        f"GROUP BY kind, name", (key, *days))}
    people = groups.get(Group.PEOPLE.value, (0, 0, 0))
    readers = people[2] or 0
    returning = 0
    for d in days:
        got = returning_blobs.get(d)
        if got is None:
            returning = None
            break
        returning += int(got.get("returning", 0))
    leads = None
    if lead_rows is not None:
        from .leads import counted, local_day
        wanted = {date.fromisoformat(d) for d in days}
        leads = sum(1 for r in lead_rows if counted(r) and (r.get("type") in LEAD_TYPES)
                    and local_day(r, tz) in wanted)
    return {"visitors": readers, "pages_read": people[1] or 0, "visitors_from_ai": cited,
            "ai_asked": int(counts.get(("engine_tier", "asked"), 0)),
            "ai_training": int(counts.get(("engine_tier", "training"), 0)),
            "search": int((groups.get(Group.SEARCH_ENGINE.value) or (0, 0, 0))[0] or 0),
            "leads": leads, "returning": returning,
            "pages_per_visitor": round((people[1] or 0) / readers, 2) if readers else None,
            "not_found_people": int(counts.get(("status_people", "404"), 0))}


# ------------------------------------------------------------------ the two

def _row(name, a: int, b: int) -> dict:
    return {"name": name, "a": a, "b": b, "delta": a - b,
            "delta_pct": round((a - b) / b * 100, 1) if b else None,
            "new": a > 0 and b == 0, "gone": b > 0 and a == 0}


def _table(a: Counter, b: Counter) -> list[dict]:
    names = sorted(set(a) | set(b), key=lambda n: (-max(a.get(n, 0), b.get(n, 0)), str(n)))
    rows = [_row(n, int(a.get(n, 0)), int(b.get(n, 0))) for n in names[:MAX_ROWS]]
    if len(names) > MAX_ROWS:
        rest = names[MAX_ROWS:]
        rows.append(_row(OTHER, sum(int(a.get(n, 0)) for n in rest),
                         sum(int(b.get(n, 0)) for n in rest)))
    return rows


def _lead_rows(config):
    from .leads import connect, db_path, read_rows
    path = db_path(config)
    if path is None:
        return None
    try:
        db = connect(path)
        try:
            return read_rows(db)
        finally:
            db.close()
    except Exception:                   # noqa: BLE001 - leads become null
        return None


def compare(history, site: str, view_slug: str | None, a_text: str, b_text: str,
            filters: dict, config: dict, tz) -> dict:
    """The whole answer for the API and the command."""
    from .store import view_key
    unknown = [k for k in filters if k not in FILTERS]
    if unknown:
        raise Invalid(f"unknown filter {unknown[0]!r}; one of {', '.join(FILTERS)}")
    filters = {k: v for k, v in filters.items() if v not in (None, "")}
    key = view_key(site, view_slug)
    a_first, a_last = parse_range(a_text)
    b_first, b_last = parse_range(b_text)
    leads = _lead_rows(config)
    a = _side(history, key, site, a_first, a_last, filters, leads, tz)
    b = _side(history, key, site, b_first, b_last, filters, leads, tz)
    metrics = []
    for k, label in METRICS:
        x, y = a["metrics"][k], b["metrics"][k]
        row = {"key": k, "label": label, "a": x, "b": y, "delta": None, "delta_pct": None}
        if x is not None and y is not None:
            row["delta"] = round(x - y, 2)
            row["delta_pct"] = round((x - y) / y * 100, 1) if y else None
        metrics.append(row)
    dims = {"pages": _table(a["pages"], b["pages"])}
    page = filters.get("page")
    for name in DIMENSIONS:
        if page and name not in ("sources", "assistants", "countries", "continents"):
            dims[name] = None
        else:
            dims[name] = _table(a["dims"][name], b["dims"][name])
    problems = []
    for side, got in (("A", a), ("B", b)):
        if got["unmeasured"] or page:
            continue
        if not filters and got["metrics"]["visitors"] is not None and \
                got["visitors_cube"] != got["metrics"]["visitors"]:
            problems.append(f"{side}: the visitor rows add up to {got['visitors_cube']}, "
                            f"not the {got['metrics']['visitors']} visitors")
        if not filters and got["metrics"]["pages_read"] is not None and \
                sum(got["pages"].values()) != got["metrics"]["pages_read"]:
            problems.append(f"{side}: the page rows add up to {sum(got['pages'].values())}, "
                            f"not the {got['metrics']['pages_read']} pages read")
    for side, got in (("A", a), ("B", b)):
        for k in ("visitors", "pages_read"):
            total = got["metrics"].get(k)
            parts = [r[k] for r in got["series"] if r[k] is not None]
            if total is not None and parts and sum(parts) != total:
                problems.append(f"{side}: the days' {k} add up to {sum(parts)}, not {total}")
    side_meta = ("from", "to", "days", "used", "excluded", "unmeasured")
    return {"ok": True, "site": site, "view": view_slug,
            "a": {k: a[k] for k in side_meta}, "b": {k: b[k] for k in side_meta},
            "presets": presets(a_first, a_last), "filters": filters, "filtered": bool(filters),
            "metrics": metrics, "series": {"a": a["series"], "b": b["series"]},
            "dimensions": dims,
            "dimension_counts": {"pages": "page views",
                                 **{n: "visitors" for n in DIMENSIONS}},
            "reconciled": not problems, "problems": problems}


# --------------------------------------------------------------- command

def cmd_compare(ctx) -> int:
    from .store import History
    a = ctx.args
    filters = dict(f.split("=", 1) for f in a.filter or [] if "=" in f)
    try:
        with History(ctx.db_path) as history:
            got = compare(history, ctx.site, a.view, a.a, a.b, filters, ctx.config, ctx.tz)
    except Invalid as why:
        ctx.err(f"compare: {why}")
        return 2
    if a.json:
        ctx.out(json.dumps(got, indent=1))
        return 0
    ctx.out(f"A {got['a']['from']}..{got['a']['to']} ({got['a']['used']} whole days)   "
            f"B {got['b']['from']}..{got['b']['to']} ({got['b']['used']} whole days)")
    for m in got["metrics"]:
        pct = "" if m["delta_pct"] is None else f"{m['delta_pct']:+.1f}%"
        ctx.out(f"  {m['label']:<32} {str(m['a']):>9} {str(m['b']):>9}  {pct}")
    if not got["reconciled"]:
        ctx.err("NOT RECONCILED: " + "; ".join(got["problems"]))
        return 1
    return 0


def add_command(sub) -> None:
    p = sub.add_parser("compare", help="compare two date ranges (whole verified days)")
    p.add_argument("--a", required=True, help="YYYY-MM-DD..YYYY-MM-DD: the range looked at")
    p.add_argument("--b", required=True, help="YYYY-MM-DD..YYYY-MM-DD: what it is compared with")
    p.add_argument("--view", help="a view's slug")
    p.add_argument("--filter", action="append", help="name=value, e.g. country=CA (repeatable)")
    p.add_argument("--json", action="store_true")
    p.set_defaults(run=cmd_compare)
