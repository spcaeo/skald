"""The second road for Traffic > Search's reports (search/reports.py): new and
lost queries, position tracking, opportunities, and each period's coverage.

Run by audit_search.daily for a site with Search Console connected (so by
run-daily, after the audit). It works every figure out again by SQL over the
stored JSON (SQLite's json_each over `search_days`), never through
search/days.py's reading or search/reports.py's sums, and compares them with
what reports.for_site gives the tab. It shares only the rules' names and
numbers with reports.py (the periods, the bucket sizes, how many rows are
kept, the opportunity thresholds) and the query_page key's separator.

  coverage   days with a `total` row in the period; days before the first
             stored day; the rest missing; days with a row not final
  changes    the newest final day; both windows whole (every day has a query
             row and every row of the day is final); the queries of each
             window summed by SQL; new = in now and not before, lost = the
             other way; ordered by impressions, clicks, query
  positions  every key's sums by SQL over the period, the TRACK most shown;
             each bucket by SQL with the bucket worked out from the day
             (julianday), counted back from the period's last day
  opportunities  query sums by SQL, the thresholds applied; the page by SQL
             over query_page, the most shown (then most clicked, then first
             by address)

A problem is a figure the tab shows that this road does not give.
"""
from __future__ import annotations

from datetime import date, timedelta

from .search.days import QP_SEP
from .search.reports import (BUCKET, HIGH, LIST, LOW_CTR, MANY, NEAR, PERIODS, SOME,
                             TRACK)

TOL = 0.011

SUMS = """
SELECT json_extract(r.value, '$[0]'),
       SUM(json_extract(r.value, '$[1]')), SUM(json_extract(r.value, '$[2]')),
       SUM(CASE WHEN json_extract(r.value, '$[3]') IS NOT NULL
                 AND json_extract(r.value, '$[2]') > 0
                THEN json_extract(r.value, '$[3]') * json_extract(r.value, '$[2]') ELSE 0 END),
       SUM(CASE WHEN json_extract(r.value, '$[3]') IS NOT NULL
                 AND json_extract(r.value, '$[2]') > 0
                THEN json_extract(r.value, '$[2]') ELSE 0 END){extra}
  FROM search_days AS d, json_each(d.data, '$.rows') AS r
 WHERE d.site = ? AND d.engine = 'google' AND d.kind = ? AND d.day BETWEEN ? AND ?
 GROUP BY 1{group}
"""


def _sums(db, site, kind, first, last) -> dict:
    return {k: (c, i, w, s) for k, c, i, w, s in
            db.execute(SUMS.format(extra="", group=""), (site, kind, first, last))}


def _sums_by_bucket(db, site, kind, first, last, size) -> dict:
    """{(key, bucket counted back from `last`): sums}."""
    extra = f", CAST((julianday('{last}') - julianday(d.day)) / {int(size)} AS INTEGER)"
    out = {}
    for k, c, i, w, s, b in db.execute(SUMS.format(extra=extra, group=", 6"),
                                       (site, kind, first, last)):
        out[(k, b)] = (c, i, w, s)
    return out


def _p(w, s):
    return w / s if s else None


def _r(v):
    return None if v is None else round(v, 2)


def _ctr(c, i):
    return c / i if i else None


def _close(a, b) -> bool:
    if a is None or b is None:
        return a is None and b is None
    return abs(float(a) - float(b)) <= TOL


def _day(d: date) -> str:
    return d.isoformat()


def recount(db, site: str) -> dict:
    """{str(N): {"coverage", "changes", "positions", "opportunities"}} by SQL."""
    last_row = db.execute("SELECT MIN(day), MAX(day) FROM search_days WHERE site = ? AND "
                          "engine = 'google' AND kind = 'total'", (site,)).fetchone()
    if not last_row or not last_row[1]:
        return {}
    history_first, last_s = last_row
    last = date.fromisoformat(last_s)
    window = _day(last - timedelta(days=max(PERIODS) - 1))
    # a day is final when every row stored for it is final
    day_final = {d: bool(f) for d, f in db.execute(
        "SELECT day, MIN(final) FROM search_days WHERE site = ? AND engine = 'google' "
        "AND day BETWEEN ? AND ? GROUP BY day", (site, window, last_s))}
    totals = {d: i for d, i in db.execute(
        "SELECT day, json_extract(data, '$.total.impressions') FROM search_days WHERE "
        "site = ? AND engine = 'google' AND kind = 'total' AND day BETWEEN ? AND ?",
        (site, window, last_s))}
    with_query = {d: o for d, o in db.execute(
        "SELECT day, json_extract(data, '$.others.rows') FROM search_days WHERE site = ? AND "
        "engine = 'google' AND kind = 'query' AND day BETWEEN ? AND ?", (site, window, last_s))}
    with_qp = {d for (d,) in db.execute(
        "SELECT day FROM search_days WHERE site = ? AND engine = 'google' AND "
        "kind = 'query_page' AND day BETWEEN ? AND ?", (site, window, last_s))}
    finals = [d for d in totals if day_final.get(d)]
    last_final = max(finals) if finals else None
    out = {}
    for n in PERIODS:
        first = last - timedelta(days=n - 1)
        days = [_day(first + timedelta(days=i)) for i in range(n)]
        have = [d for d in days if d in totals]
        before = [d for d in days if d < history_first]
        got = {"coverage": {
            "stored": len(have), "before_history": len(before),
            "missing": [d for d in days if d not in totals and d >= history_first],
            "provisional": [d for d in have if not day_final.get(d)],
            "empty": bool(have) and not sum(totals[d] or 0 for d in have)}}
        got["changes"] = _changes(db, site, n, last_final, day_final, with_query)
        got["positions"] = _positions(db, site, n, first, last)
        got["opportunities"] = _opportunities(db, site, days, with_query, with_qp)
        out[str(n)] = got
    return out


def _listed(sums: dict) -> list:
    rows = [(k, v[0], v[1], _p(v[2], v[3])) for k, v in sums.items()]
    rows.sort(key=lambda r: (-r[2], -r[1], r[0]))
    return rows


def _changes(db, site, n, last_final, day_final, with_query) -> dict:
    if n >= max(PERIODS):
        return {"state": "too_long"}
    if last_final is None:
        return {"state": "no_final"}
    end = date.fromisoformat(last_final)
    now = (_day(end - timedelta(days=n - 1)), _day(end))
    before = (_day(end - timedelta(days=2 * n - 1)), _day(end - timedelta(days=n)))
    whole = sum(1 for d, f in day_final.items()
                if before[0] <= d <= now[1] and f and d in with_query)
    if whole != 2 * n:
        return {"state": "short", "need_from": before[0]}
    cur, old = _sums(db, site, "query", *now), _sums(db, site, "query", *before)
    folded = sum(1 for d, o in with_query.items() if before[0] <= d <= now[1] and o)
    new = _listed({k: v for k, v in cur.items() if k not in old})
    lost = _listed({k: v for k, v in old.items() if k not in cur})
    return {"state": "ok", "now": now, "before": before, "new": new, "lost": lost,
            "queries_now": len(cur), "queries_before": len(old), "folded_days": folded}


def _positions(db, site, n, first, last) -> dict:
    size = BUCKET[n]
    k = -(-n // size)
    out = {"buckets": k}
    for kind in ("query", "page"):
        total = _sums(db, site, kind, _day(first), _day(last))
        keep = sorted(total.items(), key=lambda kv: (-kv[1][1], -kv[1][0], kv[0]))[:TRACK]
        cells = _sums_by_bucket(db, site, kind, _day(first), _day(last), size) if keep else {}
        rows = []
        for key, v in keep:
            # oldest first: bucket k-1 counted back is the oldest
            points = [_r(_p(*cells[(key, b)][2:])) if (key, b) in cells else None
                      for b in range(k - 1, -1, -1)]
            rows.append((key, v[0], v[1], _r(_p(v[2], v[3])), points))
        out[kind] = {"keys": len(total), "rows": rows}
    return out


def _opportunities(db, site, days, with_query, with_qp) -> dict:
    have = [d for d in days if d in with_query]
    pages = [d for d in days if d in with_qp]
    many, some = max(MANY[0], MANY[1] * len(have)), max(SOME[0], SOME[1] * len(have))
    best: dict = {}
    if pages:
        pairs = _sums(db, site, "query_page", pages[0], pages[-1])
        for key, (c, i, _w, _s) in sorted(pairs.items(), key=lambda kv: (-kv[1][1], -kv[1][0],
                                                                          kv[0])):
            query, _, page = str(key).partition(QP_SEP)
            best.setdefault(query, page)
    found = []
    if have:
        for key, (c, i, w, s) in _sums(db, site, "query", have[0], have[-1]).items():
            ctr, pos = _ctr(c, i), _r(_p(w, s))
            ctr = None if ctr is None else round(ctr, 4)
            if pos is None:
                continue
            if NEAR[0] <= pos <= NEAR[1] and i >= some:
                rule = "near"
            elif pos < HIGH and i >= many and ctr is not None and ctr < LOW_CTR:
                rule = "low_ctr"
            else:
                continue
            found.append((key, rule, c, i, pos, best.get(key)))
    found.sort(key=lambda r: (-r[3], -r[2], r[0]))
    return {"rows": found, "many": many, "some": some}


# ------------------------------------------------------------------- compare

def compare(shown: dict, counted: dict) -> list[str]:
    """What the tab shows (reports.for_site) against the recount."""
    out = []
    if set(shown) != set(counted):
        return [f"search reports: periods {sorted(shown)} shown, {sorted(counted)} recounted"]
    for n in sorted(counted, key=int):
        a, b = shown[n], counted[n]
        where = f"search reports {n} days"
        cov = a["coverage"]
        for f in ("stored", "before_history", "missing", "provisional", "empty"):
            if cov.get(f) != b["coverage"][f]:
                out.append(f"{where}: coverage {f} {cov.get(f)!r}, recount {b['coverage'][f]!r}")
        out += _compare_changes(where, a["changes"], b["changes"])
        out += _compare_positions(where, a["positions"], b["positions"])
        out += _compare_opps(where, a["opportunities"], b["opportunities"])
    return out


def _rows_differ(shown_rows, counted_rows) -> str | None:
    for x, y in zip(shown_rows, counted_rows):
        if x[0] != y[0] or not (_close(x[1], y[1]) and _close(x[2], y[2])
                                and _close(x[4], _r(y[3]))):
            return f"{x[0]!r}: shown {x[1:3] + [x[4]]}, recount {[y[1], y[2], _r(y[3])]}"
    return None


def _compare_changes(where, a, b) -> list[str]:
    if a.get("state") != b["state"]:
        return [f"{where}: new and lost {a.get('state')!r}, recount {b['state']!r}"]
    if b["state"] == "short" and a.get("need_from") != b["need_from"]:
        return [f"{where}: new and lost need days from {a.get('need_from')}, recount "
                f"{b['need_from']}"]
    if b["state"] != "ok":
        return []
    out = []
    if (a["now"]["first"], a["now"]["last"]) != b["now"] or \
            (a["before"]["first"], a["before"]["last"]) != b["before"]:
        out.append(f"{where}: new and lost compare {a['now']} with {a['before']}, recount "
                   f"{b['now']} with {b['before']}")
    for f in ("queries_now", "queries_before", "folded_days"):
        if a.get(f) != b[f]:
            out.append(f"{where}: {f} {a.get(f)}, recount {b[f]}")
    for side in ("new", "lost"):
        got, want = a[side], b[side]
        if got["count"] != len(want) or not _close(got["clicks"], sum(r[1] for r in want)) \
                or not _close(got["impressions"], sum(r[2] for r in want)):
            out.append(f"{where}: {side} queries {got['count']} ({got['clicks']} clicks, "
                       f"{got['impressions']} impressions), recount {len(want)} "
                       f"({sum(r[1] for r in want)}, {sum(r[2] for r in want)})")
        if len(got["rows"]) != min(LIST, len(want)):
            out.append(f"{where}: {side} lists {len(got['rows'])} rows, recount "
                       f"{min(LIST, len(want))}")
        bad = _rows_differ(got["rows"], want)
        if bad:
            out.append(f"{where}: {side} {bad}")
    return out


def _compare_positions(where, a, b) -> list[str]:
    out = []
    if len(a["buckets"]) != b["buckets"]:
        out.append(f"{where}: {len(a['buckets'])} position buckets, recount {b['buckets']}")
    for kind in ("query", "page"):
        got, want = a[kind], b[kind]
        if got["keys"] != want["keys"] or len(got["rows"]) != len(want["rows"]):
            out.append(f"{where}: positions {kind} {got['keys']} keys / {len(got['rows'])} "
                       f"tracked, recount {want['keys']} / {len(want['rows'])}")
            continue
        for x, y in zip(got["rows"], want["rows"]):
            key, clicks, shown, pos, points = y
            if x["key"] != key or not (_close(x["clicks"], clicks) and _close(x["impressions"], shown)
                                       and _close(x["position"], pos)):
                out.append(f"{where}: positions {kind} {x['key']!r}: shown {x['clicks']}/"
                           f"{x['impressions']}/{x['position']}, recount {key!r} {clicks}/"
                           f"{shown}/{pos}")
                break
            if len(x["points"]) != len(points) or \
                    not all(_close(p, q) for p, q in zip(x["points"], points)):
                out.append(f"{where}: positions {kind} {key!r}: points {x['points']}, "
                           f"recount {points}")
                break
    return out


def _compare_opps(where, a, b) -> list[str]:
    out = []
    if (a["rules"]["many"], a["rules"]["some"]) != (b["many"], b["some"]):
        out.append(f"{where}: opportunity floors {a['rules']['many']}/{a['rules']['some']}, "
                   f"recount {b['many']}/{b['some']}")
    want = b["rows"]
    if a["count"] != len(want) or len(a["rows"]) != min(LIST, len(want)):
        return out + [f"{where}: {a['count']} opportunities, recount {len(want)}"]
    for x, y in zip(a["rows"], want):
        key, rule, clicks, shown, pos, page = y
        if (x["query"], x["rule"], x["page"]) != (key, rule, page) or not (
                _close(x["clicks"], clicks) and _close(x["impressions"], shown)
                and _close(x["position"], pos)):
            out.append(f"{where}: opportunity {x['query']!r} {x['rule']} {x['page']!r} "
                       f"{x['clicks']}/{x['impressions']}/{x['position']}, recount {key!r} "
                       f"{rule} {page!r} {clicks}/{shown}/{pos}")
            break
    return out


def check(db, site: str) -> list[str]:
    """The tab's reports against the recount; empty when they match."""
    from .search import reports
    try:
        shown = reports.for_site(db, site)
    except Exception as why:            # noqa: BLE001 - a crash is a finding, said plainly
        return [f"search reports: could not be worked out ({type(why).__name__}: {why})"]
    return compare(shown, recount(db, site))
