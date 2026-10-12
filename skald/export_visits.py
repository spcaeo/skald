"""Export visits: their metrics, their entry and exit pages, and journeys.

Three tables, beside export.py's, from history or today's live snapshot:

  visits       per day: visits, pages loaded, pages per visit, one-page
               visits and their share, median duration, and the visits
               that moved in-app, met a 404 or sent a POST. A total over
               days merges the histograms, so its median is the period's
               median, not an average of medians.
  visit_paths  per day: entry pages, exit pages and steps (page to next
               page), each by visits
  journeys     one anonymous row per visit: start time (to the minute),
               country, device, browser, system, source, landing page, the
               pages in order (in-app ones marked), counts, duration and
               flags. Kept report.journey_days days; never totalled.

Days collected before visits were counted (history schema 8) are listed
as unmeasured in the coverage, never exported as zeroes.
"""
from __future__ import annotations

from collections import Counter
from datetime import date

from .store import READER_KINDS, History
from .store_visits import VISIT_KINDS
from .visits import ARROW, VisitStats, duration_words, sentence

TABLES = ("visits", "visit_paths", "journeys", "campaigns")
APPLIES = {
    "campaigns": {"dimension"},
    "visits": set(),
    "visit_paths": {"path_prefix"},
    "journeys": {"country", "browser", "os", "device", "source_type", "path_prefix",
                 "source"},
}


def metrics_row(d: str, state: str, stats: VisitStats) -> dict:
    per = stats.per_visit()
    median = stats.median_seconds()
    return {
        "day": d, "state": state, "visits": stats.visits, "page_views": stats.views(),
        "pages_per_visit": "" if per is None else f"{per:.2f}",
        "one_page_visits": stats.one_page(),
        "one_page_share": f"{stats.one_page() / stats.visits:.3f}" if stats.visits else "",
        "median_seconds": "" if median is None else median,
        "in_app_visits": stats.flags.get("in_app", 0),
        "visits_with_404": stats.flags.get("not_found", 0),
        "visits_with_post": stats.flags.get("posted", 0),
        "_stats": stats,
    }


def path_rows(d: str, state: str, stats: VisitStats, prefix: str | None) -> list[dict]:
    out = []
    for kind, counter in (("entry", stats.entries), ("exit", stats.exits),
                          ("step", stats.steps)):
        for name, n in sorted(counter.items(), key=lambda kv: (-kv[1], kv[0])):
            if n and (not prefix or name.startswith(prefix)):
                out.append({"day": d, "state": state, "kind": kind, "name": name,
                            "visits": n})
    return out


def journey_text(j: dict) -> str:
    """'/a → /b (in-app) → /c' - the pages in order."""
    return ARROW.join(p + (" (in-app)" if how == "app" else "")
                      for p, how in j.get("trail") or [])


def journey_row(d: str, state: str, j: dict) -> dict:
    return {
        "day": d, "state": state, "start": str(j.get("start", ""))[11:16],
        "country": j.get("country", ""), "device": j.get("device", ""),
        "browser": j.get("browser", ""), "os": j.get("os", ""),
        "source": j.get("source", ""), "via": j.get("via", ""),
        "campaign": j.get("campaign", ""), "landing": j.get("landing", ""),
        "journey": journey_text(j), "pages": j.get("pages", 0),
        "pages_seen": j.get("seen", 0), "in_app": j.get("in_app", 0),
        "seconds": j.get("seconds", 0), "duration": duration_words(j.get("seconds")),
        "exit": j.get("exit", ""), "not_found": j.get("not_found", 0),
        "posted": j.get("posted", 0),
        **{f"utm_{k}": (j.get("utm") or {}).get(k, "") for k in
           ("source", "medium", "campaign", "term", "content")},
        "paid": j.get("paid", ""), "ref_param": j.get("ref_param", ""),
        "ref_host": j.get("ref_host", ""), "ref_page": j.get("ref_page", ""),
        "search_terms": j.get("search_terms", ""),
        "returning": "" if j.get("returning") is None else ("yes" if j["returning"] else "no"),
        "days_seen_30d": "" if j.get("days_seen_30d") is None else j["days_seen_30d"],
        "summary": sentence(j),
    }


def campaign_rows(d: str, state: str, blob: dict | None, f) -> list[dict]:
    from .campaigns import DIMENSIONS
    from .export import ExportError
    if f.dimension and f.dimension not in DIMENSIONS:
        raise ExportError(f"unknown campaign dimension {f.dimension!r}; one of "
                          f"{', '.join(DIMENSIONS)}")
    out = []
    for dimension, rows in ((blob or {}).get("rows") or {}).items():
        if f.dimension and dimension != f.dimension:
            continue
        for r in rows:
            out.append({"day": d, "state": state, "dimension": dimension, "name": r["name"],
                        "visits": r["visits"], "pages": r["pages"],
                        "not_found": r["not_found"], "posts": r["posts"]})
    return out


def _wanted(j: dict, f) -> bool:
    for key, field in (("country", "country"), ("browser", "browser"), ("os", "os"),
                       ("device", "device"), ("source_type", "source")):
        value = getattr(f, key)
        if value and str(j.get(field, "")).lower() != value.lower():
            return False
    if f.source:
        wanted = f.source.lower()
        said = {str(j.get("via", "")).lower(), str(j.get("ref_host", "")).lower(),
                str((j.get("utm") or {}).get("source", "")).lower()}
        if wanted not in said:
            return False
    return not f.path_prefix or str(j.get("landing", "")).startswith(f.path_prefix)


def _day_stats(history: History, key: str, days: list[str]) -> dict[str, VisitStats]:
    kinds = list(VISIT_KINDS.values()) + [READER_KINDS[n] for n in
                                          ("landing", "source", "country", "device")]
    field = {kind: name for name, kind in VISIT_KINDS.items()}
    field.update({READER_KINDS["landing"]: "entries", READER_KINDS["source"]: "source",
                  READER_KINDS["country"]: "country", READER_KINDS["device"]: "device"})
    out: dict[str, VisitStats] = {}
    for d, kind, name, n in history.count_rows(key, kinds, days):
        stats = out.setdefault(d, VisitStats())
        getattr(stats, field[kind])[name] = n
    for stats in out.values():
        stats.visits = sum(stats.pages.values())
    return out


def rows_from_history(history: History, key: str, table: str, first: date, last: date,
                      f, include_withheld: bool, coverage: dict,
                      state: dict[str, str]) -> list[dict]:
    """Rows for the days export.rows_from_history chose (`state`)."""
    if table == "campaigns":
        blobs = history.extras(key, first, last, ("campaigns",))
        coverage["unmeasured"] = [d for d in coverage["recorded"] if d not in blobs]
        rows = []
        for d in sorted(state):
            if d in blobs:
                rows += campaign_rows(d, state[d], blobs[d].get("campaigns"), f)
        return rows
    measured = history.visit_days(key, first, last)
    coverage["unmeasured"] = [d for d in coverage["recorded"] if d not in measured]
    days = sorted(d for d in state if d in measured)
    rows: list[dict] = []
    if table == "journeys":
        for j in reversed(history.journeys(key, first, last)):
            d = j.get("day")
            if d in state and _wanted(j, f):
                rows.append(journey_row(d, state[d], j))
        rows.reverse()                       # newest first
        return rows
    per_day = _day_stats(history, key, days)
    for d in days:
        stats = per_day.get(d, VisitStats())
        if table == "visits":
            rows.append(metrics_row(d, state[d], stats))
        else:
            rows += path_rows(d, state[d], stats, f.path_prefix)
    return rows


def rows_from_live(snap: dict, table: str, f) -> list[dict]:
    from .export import ExportError
    if table == "campaigns":
        return campaign_rows(snap["day"], "live", (snap.get("extras") or {}).get("campaigns"), f)
    stats = VisitStats.from_dict(snap.get("visits"))
    if stats is None:
        raise ExportError("this snapshot predates visits; run `skald live` again")
    d, state = snap["day"], "live"
    if table == "visits":
        return [metrics_row(d, state, stats)]
    if table == "visit_paths":
        return path_rows(d, state, stats, f.path_prefix)
    return [journey_row(d, state, j) for j in snap.get("journeys") or [] if _wanted(j, f)]


def total(rows: list[dict], table: str) -> list[dict]:
    """Sum over the days. Metrics are recomputed from merged histograms."""
    from .export import ExportError
    if table == "journeys":
        raise ExportError("journeys are one row per visit; --total does not apply "
                          "(use --table visits for totals)")
    if table == "campaigns":
        sums: dict[tuple, Counter] = {}
        for row in rows:
            sums.setdefault((row["state"], row["dimension"], row["name"]), Counter()).update(
                {k: row[k] for k in ("visits", "pages", "not_found", "posts")})
        return [{"state": s, "dimension": d, "name": n, **dict(c)}
                for (s, d, n), c in sorted(sums.items(), key=lambda kv: (kv[0][1],
                                                                         -kv[1]["visits"]))]
    by_state: dict[str, list[dict]] = {}
    for row in rows:
        by_state.setdefault(row["state"], []).append(row)
    out = []
    for state, group in by_state.items():
        if table == "visits":
            merged = VisitStats()
            for row in group:
                s = row["_stats"]
                merged.visits += s.visits
                for name in VisitStats.STORED:
                    getattr(merged, name).update(getattr(s, name))
            row = metrics_row("", state, merged)
            del row["day"]
            out.append(row)
            continue
        sums: Counter = Counter()
        for row in group:
            sums[(row["kind"], row["name"])] += row["visits"]
        order = {"entry": 0, "exit": 1, "step": 2}
        for (kind, name), n in sorted(sums.items(),
                                      key=lambda kv: (order[kv[0][0]], -kv[1], kv[0][1])):
            out.append({"state": state, "kind": kind, "name": name, "visits": n})
    return out
