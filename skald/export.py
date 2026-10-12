"""Export history (or today so far) as CSV or JSON.

Everything exported comes from the stored aggregates or the live snapshot,
so the same guarantees hold: no address and no user agent of anyone, only
counts, paths, assistant names, citing sites and countries.

Verified days only, unless asked. A withheld day's figures are kept in
history for whoever investigates; `include_withheld` exports them with
state "withheld" on every row, so they cannot be mistaken for good ones.

Six tables:

  daily      day, group: requests, page views, readers (visits with a page
             view), visits, scanner probes (and
             citation visitors on the people row) - one row per group per
             day, so a day's rows add up to its requests
  pages      pages by page views: people's by default, or an engine group's
  ai_pages   pages answer engines fetched
  engines    answer engines by tier and name, and search engines by name
  citations  sites whose citation a person followed, by visitors
  countries  where people's visits came from, by visits

Seven more, from the breakdowns counted since history schema 7:

  readers        readers (visits that read a page) by one dimension at a
                 time - country, browser, os, device, source, referrer,
                 campaign, landing, hour. Each dimension adds up to the
                 day's readers. Dimensions are stored separately, so they
                 cannot be crossed: "Canada and Chrome" is not knowable.
  statuses       requests per group by status class (2xx, 3xx, 404, 4xx,
                 5xx, other)
  not_found      paths people asked for and got a 404, by requests
  server_errors  5xx responses to anyone, by path
  posts          POST requests per group, by path
  speed          people's page views by how long the server took
  slow_pages     pages behind people's slow (1 s or more) page views

A day collected before the breakdowns existed has none: it is listed in the
coverage as "unmeasured", never exported as zeroes.

Three more for visits (export_visits.py): visits (metrics per day),
visit_paths (entry pages, exit pages, steps) and journeys (one anonymous
row per visit, kept report.journey_days days).

Rows are per day; `total` sums each key over the range. Sums of daily top-50
lists undercount the long tail, as on the dashboard.

A filter that does not apply to the table asked for is an error, not
silently ignored: "--country CA" on the pages table would otherwise return
every page and look like an answer.
"""
from __future__ import annotations

import csv
import io
import json
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import date

from .aggregate import READER_DIMS
from .classify import Group, ads_checks, assistant_name
from .dimensions import SPEEDS, STATUSES
from .store import READER_KINDS, History

from . import export_visits as ev

BREAKDOWN_TABLES = ("readers", "statuses", "not_found", "server_errors", "posts",
                    "speed", "slow_pages")
TABLES = ("daily", "pages", "ai_pages", "engines", "citations", "countries",
          *BREAKDOWN_TABLES, *ev.TABLES)
TIERS = ("training", "asked", "cited")

PAGE_KINDS = {
    Group.PEOPLE.value: "people_page",
    Group.ANSWER_ENGINE.value: "engine_page",
    Group.SEARCH_ENGINE.value: "search_page",
}

# Which filters each table understands.
APPLIES = {
    "daily": {"group"},
    "pages": {"group", "path_prefix"},
    "ai_pages": {"path_prefix"},
    "engines": {"group", "tier", "engine"},
    "citations": {"tier", "source"},
    "countries": {"country"},
    "readers": {"dimension", "country", "browser", "os", "device", "source_type",
                "path_prefix"},
    "statuses": {"group", "status"},
    "not_found": {"path_prefix"},
    "server_errors": {"path_prefix"},
    "posts": {"group", "path_prefix"},
    "speed": set(),
    "slow_pages": {"path_prefix"},
    **ev.APPLIES,
}

# On the readers table, a value filter picks its own dimension.
VALUE_DIMENSION = {"country": "country", "browser": "browser", "os": "os",
                   "device": "device", "source_type": "source",
                   "path_prefix": "landing"}


@dataclass
class Filters:
    group: str | None = None
    tier: str | None = None
    engine: str | None = None
    source: str | None = None
    path_prefix: str | None = None
    country: str | None = None
    dimension: str | None = None
    browser: str | None = None
    os: str | None = None
    device: str | None = None
    source_type: str | None = None
    status: str | None = None

    def given(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v}


class ExportError(ValueError):
    """The request cannot be answered honestly as asked."""


def validate(table: str, f: Filters) -> None:
    if table not in TABLES:
        raise ExportError(f"unknown table {table!r}; one of {', '.join(TABLES)}")
    stray = set(f.given()) - APPLIES[table]
    if stray:
        names = ", ".join("--" + s.replace("_", "-") for s in sorted(stray))
        raise ExportError(f"{names} does not apply to the {table} table "
                          f"(it takes: {', '.join(sorted(APPLIES[table])) or 'no filters'})")
    groups = {g.value for g in Group}
    if f.group and f.group not in groups:
        raise ExportError(f"unknown group {f.group!r}; one of {', '.join(sorted(groups))}")
    if table == "pages" and f.group and f.group not in PAGE_KINDS:
        raise ExportError("pages are kept for people, answer_engines and "
                          "search_engines only")
    if table == "engines" and f.group and f.group not in (
            Group.ANSWER_ENGINE.value, Group.SEARCH_ENGINE.value):
        raise ExportError("engines are answer_engines or search_engines")
    if f.tier and f.tier not in TIERS:
        raise ExportError(f"unknown tier {f.tier!r}; one of {', '.join(TIERS)}")
    if table == "engines" and f.tier == "cited":
        raise ExportError("a citation is a person, not an engine fetch: "
                          "use the citations table")
    if table == "citations" and f.tier and f.tier != "cited":
        raise ExportError("citations are the cited tier only")
    if f.status and f.status not in STATUSES:
        raise ExportError(f"unknown status {f.status!r}; one of {', '.join(STATUSES)}")
    if table == "readers":
        reader_dimension(f)


def reader_dimension(f: Filters) -> str | None:
    """The one dimension a readers export is about, from --dimension and the
    value filters. Two different ones cannot be honoured: each breakdown is
    counted on its own, so readers in Canada using Chrome are not known."""
    if f.dimension and f.dimension not in READER_DIMS:
        raise ExportError(f"unknown dimension {f.dimension!r}; one of "
                          f"{', '.join(READER_DIMS)}")
    implied = {VALUE_DIMENSION[k] for k in VALUE_DIMENSION if getattr(f, k)}
    if f.dimension:
        implied.add(f.dimension)
    if len(implied) > 1:
        raise ExportError(
            "readers are broken down one dimension at a time ("
            + ", ".join(sorted(implied)) + " asked together): each breakdown "
            "is stored on its own, so they cannot be crossed - readers in "
            "Canada using Chrome, say, are not knowable from these totals")
    return next(iter(implied), None)


def _reader_wanted(f: Filters, dimension: str, name: str) -> bool:
    """Does this (dimension, name) row pass the readers filters?"""
    wanted = reader_dimension(f)
    if wanted and dimension != wanted:
        return False
    for key, dim in VALUE_DIMENSION.items():
        value = getattr(f, key)
        if not value or dim != dimension:
            continue
        if key == "path_prefix":
            if not name.startswith(value):
                return False
        elif key == "country":
            if name.upper() != value.upper():
                return False
        elif name.lower() != value.lower():
            return False
    return True


def _reader_rows(d: str, state: str, by: dict, f: Filters,
                 credit: str | None) -> list[dict]:
    """readers rows for one day from {dimension: {name: n}}."""
    out = []
    for dimension in READER_DIMS:
        names = by.get(dimension) or {}
        items = (sorted(names.items()) if dimension == "hour"
                 else sorted(names.items(), key=lambda kv: (-kv[1], kv[0])))
        for name, n in items:
            if not n or not _reader_wanted(f, dimension, name):
                continue
            row = {"day": d, "state": state, "dimension": dimension,
                   "name": name, "readers": n}
            if credit and dimension == "country":
                row["source"] = credit
            out.append(row)
    return out


def _breakdown_rows(table: str, d: str, state: str, b: dict, f: Filters,
                    credit: str | None) -> list[dict]:
    """Rows of one breakdown table for one day, from a breakdowns dict
    shaped as live.breakdowns() makes it."""
    def by_size(counter: dict):
        return sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))

    rows: list[dict] = []
    if table == "readers":
        return _reader_rows(d, state, b.get("by", {}), f, credit)
    if table == "statuses":
        for g in Group:
            if f.group and g.value != f.group:
                continue
            got = b.get("statuses", {}).get(g.value, {})
            for status in STATUSES:
                if f.status and status != f.status:
                    continue
                if got.get(status):
                    rows.append({"day": d, "state": state, "group": g.value,
                                 "status": status, "requests": got[status]})
    elif table in ("not_found", "server_errors", "slow_pages"):
        key, num = {"not_found": ("not_found", "requests"),
                    "server_errors": ("server_errors", "requests"),
                    "slow_pages": ("slow_pages", "page_views")}[table]
        for path, n in by_size(b.get(key, {})):
            if n and _matches_path(path, f.path_prefix):
                rows.append({"day": d, "state": state, "path": path, num: n})
    elif table == "posts":
        for g in Group:
            if f.group and g.value != f.group:
                continue
            pages = (b.get("posts", {}).get(g.value) or {}).get("pages", {})
            for path, n in by_size(pages):
                if n and _matches_path(path, f.path_prefix):
                    rows.append({"day": d, "state": state, "group": g.value,
                                 "path": path, "requests": n})
    elif table == "speed":
        got = b.get("speeds", {})
        for bucket in SPEEDS:
            if got.get(bucket):
                rows.append({"day": d, "state": state, "bucket": bucket,
                             "page_views": got[bucket]})
    return rows


def _history_breakdowns(history: History, key: str, days: list[str]) -> dict:
    """{day: breakdowns dict} rebuilt from the counts table, shaped like the
    live snapshot's, so one renderer serves both."""
    kinds = list(READER_KINDS.values()) + [
        "people_404_page", "people_speed", "people_slow_page", "server_error_page",
        "post_total"] + [f"status_{g.value}" for g in Group] + [
        f"post_page_{g.value}" for g in Group]
    by_kind = {kind: name for name, kind in READER_KINDS.items()}
    out: dict[str, dict] = {}
    for d, kind, name, n in history.count_rows(key, kinds, days):
        b = out.setdefault(d, {"by": {}, "not_found": {}, "speeds": {},
                               "slow_pages": {}, "server_errors": {},
                               "statuses": {}, "posts": {}})
        if kind in by_kind:
            b["by"].setdefault(by_kind[kind], {})[name] = n
        elif kind == "people_404_page":
            b["not_found"][name] = n
        elif kind == "people_speed":
            b["speeds"][name] = n
        elif kind == "people_slow_page":
            b["slow_pages"][name] = n
        elif kind == "server_error_page":
            b["server_errors"][name] = n
        elif kind == "post_total":
            b["posts"].setdefault(name, {"total": 0, "pages": {}})["total"] = n
        elif kind.startswith("status_"):
            b["statuses"].setdefault(kind[len("status_"):], {})[name] = n
        elif kind.startswith("post_page_"):
            b["posts"].setdefault(kind[len("post_page_"):],
                                  {"total": 0, "pages": {}})["pages"][name] = n
    return out


def _engine_rows(tier_counts: dict[str, dict], search: dict, f: Filters):
    """(group, tier, name, n) from {tier: {name: n}} and {name: n}."""
    out = []
    if f.group in (None, Group.ANSWER_ENGINE.value):
        for tier in ("training", "asked"):
            if f.tier and f.tier != tier:
                continue
            for name, n in tier_counts.get(tier, {}).items():
                out.append((Group.ANSWER_ENGINE.value, tier, name, n))
    # Search engines have no tier, so any tier filter leaves them out.
    if f.group in (None, Group.SEARCH_ENGINE.value) and not f.tier:
        for name, n in search.items():
            # The tier column says which search fetches are not indexing.
            out.append((Group.SEARCH_ENGINE.value,
                        "ads" if ads_checks({name: 1}) else "", name, n))
    if f.engine:
        out = [r for r in out if r[2].lower() == f.engine.lower()]
    return out


def _matches_path(path: str, prefix: str | None) -> bool:
    return not prefix or path.startswith(prefix)


def rows_from_history(history: History, key: str, table: str, first: date,
                      last: date, f: Filters, include_withheld: bool = False,
                      credit: str | None = None) -> tuple[list[dict], dict]:
    """Per-day rows and the coverage of the range (recorded/withheld/missing)."""
    validate(table, f)
    found_days = history.day_rows(key, first, last)
    stored = {d: bool(v) for d, v, _, _ in found_days}
    cited = {d: c for d, _, c, _ in found_days}
    partial = {d for d, _, _, p in found_days if p}
    every = [(first.toordinal() + i) for i in range((last - first).days + 1)]
    all_days = [date.fromordinal(o).isoformat() for o in every]
    coverage = {
        "recorded": [d for d in all_days if stored.get(d) is True],
        "withheld": [d for d in all_days if stored.get(d) is False],
        "missing": [d for d in all_days if d not in stored],
    }
    days = coverage["recorded"] + (coverage["withheld"] if include_withheld else [])
    days.sort()
    # A partial day is verified but not whole: it is exported, and every one
    # of its rows says "partial", so a total keeps it apart from whole days.
    state = {d: ("withheld" if not stored[d] else "partial" if d in partial else "ok")
             for d in days}
    rows: list[dict] = []

    if table in ev.TABLES:
        return ev.rows_from_history(history, key, table, first, last, f,
                                    include_withheld, coverage, state), coverage

    if table in BREAKDOWN_TABLES:
        # Days collected before the breakdowns existed are named, not zeroed.
        measured = history.breakdown_days(key, first, last)
        coverage["unmeasured"] = [d for d in coverage["recorded"] if d not in measured]
        per_day = _history_breakdowns(history, key, [d for d in days if d in measured])
        for d in days:
            if d in measured:
                rows += _breakdown_rows(table, d, state[d], per_day.get(d, {}), f, credit)
        return rows, coverage

    if table == "daily":
        found = {(d, g): (h, v, vi, p, r)
                 for d, g, h, v, vi, p, r in history.group_rows(key, days)}
        for d in days:
            for g in Group:
                if f.group and g.value != f.group:
                    continue
                h, v, vi, p, r = found.get((d, g.value), (0, 0, 0, 0, 0))
                rows.append({"day": d, "state": state[d], "group": g.value,
                             "requests": h, "page_views": v,
                             "readers": "" if r is None else r, "visits": vi,
                             "probes": p,
                             "cited_visits": cited[d] if g is Group.PEOPLE else ""})
        return rows, coverage

    if table in ("pages", "ai_pages"):
        group = Group.ANSWER_ENGINE.value if table == "ai_pages" else (
            f.group or Group.PEOPLE.value)
        for d, _, name, n in history.count_rows(key, [PAGE_KINDS[group]], days):
            if _matches_path(name, f.path_prefix):
                row = {"day": d, "state": state[d], "path": name, "page_views": n}
                if table == "pages":
                    row = {"day": d, "state": state[d], "group": group,
                           "path": name, "page_views": n}
                rows.append(row)
        return rows, coverage

    if table == "engines":
        per_day: dict[str, dict] = {}
        for d, kind, name, n in history.count_rows(
                key, ["engine_training", "engine_asked", "search_engine"], days):
            slot = per_day.setdefault(d, {"training": {}, "asked": {}, "search": {}})
            slot[{"engine_training": "training", "engine_asked": "asked",
                  "search_engine": "search"}[kind]][name] = n
        for d in days:
            slot = per_day.get(d, {"training": {}, "asked": {}, "search": {}})
            for group, tier, name, n in _engine_rows(slot, slot["search"], f):
                rows.append({"day": d, "state": state[d], "group": group,
                             "tier": tier, "name": name, "requests": n})
        return rows, coverage

    if table == "citations":
        # One row per assistant per day, whatever name an older row used.
        merged: dict[tuple, int] = {}
        for d, _, name, n in history.count_rows(key, ["cited_by"], days):
            k = (d, assistant_name(name))
            merged[k] = merged.get(k, 0) + n
        wanted = assistant_name(f.source) if f.source else None
        for (d, name), n in sorted(merged.items(), key=lambda kv: (kv[0][0], -kv[1])):
            if not wanted or name == wanted:
                rows.append({"day": d, "state": state[d], "source": name,
                             "visitors": n})
        return rows, coverage

    # countries
    for d, _, name, n in history.count_rows(key, ["people_country_visits"], days):
        if not f.country or name.upper() == f.country.upper():
            row = {"day": d, "state": state[d], "country": name, "visits": n}
            if credit:
                row["source"] = credit
            rows.append(row)
    return rows, coverage


def rows_from_live(snap: dict, table: str, f: Filters,
                   credit: str | None = None) -> list[dict]:
    """The same tables for today so far. Only a reconciled snapshot exports."""
    validate(table, f)
    if snap.get("state") != "ok":
        raise ExportError(f"today's live figures are {snap.get('state', 'missing')}; "
                          "nothing to export")
    d, state = snap["day"], "live"
    people = snap.get("people", {})
    rows: list[dict] = []
    if table in ev.TABLES:
        return ev.rows_from_live(snap, table, f)
    if table in BREAKDOWN_TABLES:
        if "breakdowns" not in snap:
            raise ExportError("this snapshot predates the breakdowns; run "
                              "`skald live` again to refresh it")
        return _breakdown_rows(table, d, state, snap["breakdowns"], f, credit)
    if table == "daily":
        groups = snap.get("groups", {})
        for g in Group:
            if f.group and g.value != f.group:
                continue
            row = {"day": d, "state": state, "group": g.value,
                   "requests": groups.get(g.value, 0), "page_views": "",
                   "readers": "", "visits": "", "probes": "", "cited_visits": ""}
            if g is Group.PEOPLE:
                row.update(page_views=people.get("views", 0),
                           visits=people.get("visits", 0),
                           readers=people.get("readers", 0),
                           cited_visits=people.get("cited_visits", 0))
            if g is Group.BOTS:
                row["probes"] = snap.get("bots", {}).get("probes", 0)
            rows.append(row)
    elif table in ("pages", "ai_pages"):
        group = Group.ANSWER_ENGINE.value if table == "ai_pages" else (
            f.group or Group.PEOPLE.value)
        source = {Group.PEOPLE.value: people.get("pages", {}),
                  Group.ANSWER_ENGINE.value: snap.get("ai_pages", {})}.get(group)
        if source is None:
            raise ExportError(f"the live snapshot does not keep pages for {group}")
        for name, n in source.items():
            if _matches_path(name, f.path_prefix):
                row = {"day": d, "state": state, "path": name, "page_views": n}
                if table == "pages":
                    row = {"day": d, "state": state, "group": group,
                           "path": name, "page_views": n}
                rows.append(row)
    elif table == "engines":
        for group, tier, name, n in _engine_rows(snap.get("ai", {}),
                                                 snap.get("search", {}), f):
            rows.append({"day": d, "state": state, "group": group, "tier": tier,
                         "name": name, "requests": n})
    elif table == "citations":
        wanted = assistant_name(f.source) if f.source else None
        for name, n in people.get("cited_by", {}).items():
            if not wanted or assistant_name(name) == wanted:
                rows.append({"day": d, "state": state, "source": name, "visitors": n})
    else:
        for name, n in people.get("countries", {}).items():
            if not f.country or name.upper() == f.country.upper():
                row = {"day": d, "state": state, "country": name, "visits": n}
                if credit:
                    row["source"] = credit
                rows.append(row)
    return rows


NUMERIC = ("requests", "page_views", "readers", "visits", "probes", "cited_visits",
           "visitors")


def total(rows: list[dict], table: str) -> list[dict]:
    """Sum each key over the days: drop the day, add the numbers.

    Rows with a different state (withheld included) are summed separately,
    so a total never mixes verified and withheld figures unlabelled. Lists
    come out largest first; the daily table keeps its group order.
    """
    if table in ev.TABLES:
        return ev.total(rows, table)
    sums: dict[tuple, Counter] = {}
    order: list[tuple] = []
    for row in rows:
        ident = tuple((k, v) for k, v in row.items()
                      if k not in NUMERIC and k != "day")
        if ident not in sums:
            sums[ident] = Counter()
            order.append(ident)
        for k in NUMERIC:
            if k in row and row[k] != "":
                sums[ident][k] += int(row[k])
    out = []
    for ident in order:
        row = dict(ident)
        row.update(sums[ident])
        out.append(row)
    lead = next((k for k in NUMERIC if out and k in out[0]), None)
    if table == "readers":
        out.sort(key=lambda r: (READER_DIMS.index(r["dimension"]) if r.get("dimension")
                                in READER_DIMS else len(READER_DIMS),
                                r["name"] if r.get("dimension") == "hour"
                                else -int(r.get("readers") or 0)))
    elif lead and table not in ("daily", "speed", "statuses"):
        out.sort(key=lambda r: -int(r.get(lead) or 0))
    return out


# Spreadsheet programs run a cell that starts with one of these as a formula.
# Paths come from request lines anyone can send, so every text cell that
# would start with one is prefixed with an apostrophe.
_FORMULA = ("=", "+", "-", "@", "\t", "\r")


def _cell(value) -> str:
    text = "" if value is None else str(value)
    return "'" + text if text.startswith(_FORMULA) else text


def _public(rows: list[dict]) -> list[dict]:
    """Rows without their working keys ("_stats" and the like)."""
    return [{k: v for k, v in row.items() if not k.startswith("_")} for row in rows]


def as_csv(rows: list[dict]) -> str:
    rows = _public(rows)
    if not rows:
        return ""
    fields: list[str] = []
    for row in rows:
        fields += [k for k in row if k not in fields]
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(fields)
    for row in rows:
        writer.writerow([_cell(row.get(k, "")) for k in fields])
    return buffer.getvalue()


def as_json(rows: list[dict], meta: dict) -> str:
    return json.dumps({**meta, "rows": _public(rows)}, indent=1, sort_keys=False) + "\n"
