"""Search Console reports on Traffic > Search: new and lost queries, position
tracking and opportunities, worked out from the days the sync already stored
(`search_days`, search/days.py). Nothing is asked of Google here.

Each period of search.json (data.PERIODS: the last N days up to the newest
stored day) gets `coverage`, for both engines, and for Search Console also
`changes`, `positions` and `opportunities`. Bing gives only its weekly top
tables, which cannot say when a query appeared or how a position moved.

coverage       how much of the period the history holds, in plain counts:
  days           N, the period's length
  stored         days with figures
  before_history days before the first stored day (the history starts later)
  missing        [day]: days inside the history with no figures
  provisional    [day]: days the engine may still change
  history_first  the first stored day, or null
  empty          true when every stored day has 0 impressions

changes        new and lost queries, on whole days only: the last N final days
               (ending at the newest final day, so provisional days are left
               out) against the N days before them. Every day of both must be
               stored and final, else `state` says why and nothing is listed.
  state          "ok"; "too_long" (the period and the one before are longer
                 than the 16 months Search Console keeps); "no_final" (no
                 final day yet); "short" (a day of the two is not stored or not
                 final: `need_from` is the first day needed)
  now, before    {"first", "last"}
  new            queries in the query rows of `now` and of no day of `before`:
                 {"count", "clicks", "impressions", "rows": [[query, clicks,
                 impressions, ctr, position]]} (the first LIST rows)
  lost           queries in `before` and in no day of `now`; the same fields,
                 the figures of `before`
  queries_now, queries_before   distinct queries in each
  folded_days    days of the two on which some queries were below the day's
                 top list (days.TOP): such a query may look new or lost when
                 it only moved across that line

positions      each query's and page's average position over the period, in
               buckets of BUCKET[N] days (the oldest may be shorter): Google's
               average position, weighted by impressions, as Google gives it.
  size           days per bucket
  buckets        [{"first", "last", "days" (stored), "provisional": bool}]
  query, page    {"keys": distinct keys in the period, "rows": the TRACK most
                 shown: {"key", "clicks", "impressions", "position", "points":
                 [position or null per bucket], "shown": [impressions per
                 bucket], "first", "last" (the first and the last point with a
                 position), "change": first - last (positive: moved up), null
                 with fewer than two points}}
                 A bucket where the key had no row is null, never 0.

opportunities  queries a page could win more clicks from, by two rules:
  "low_ctr"   shown at least MANY times (the larger of MANY[0] and MANY[1]
              per stored day), a click rate under LOW_CTR, and an average
              position better than HIGH: already high, rarely clicked
  "near"      an average position from NEAR[0] to NEAR[1] and shown at least
              SOME times: the foot of page one or the top of page two
  rows        [{"query", "rule", "clicks", "impressions", "ctr", "position",
              "page" (the page it showed most, by impressions, from
              query_page; null when not known), "pages" (how many pages it
              showed), "page_share" (that page's share of its impressions)}],
              by impressions, then clicks, then query; the first LIST
  count, by_rule {"low_ctr", "near"}, days (stored days with queries),
  rules {"many", "some", "low_ctr", "high", "near"}: the numbers used,
  pages_from (the first day with query_page in the period), pages_days

Figures are summed from each day's stored rows. Rows are each day's top
(days.TOP); a query below it on a day counts in "(all others)" there, so
its sum can be short (the tab says so). Second road:
audit_search_reports.py, by SQL over the stored JSON.
"""
from __future__ import annotations

from datetime import date, timedelta

from . import days as sd

PERIODS = (7, 28, 90, 480)
BUCKET = {7: 1, 28: 1, 90: 7, 480: 30}
TRACK = 100
LIST = 300
MANY = (100, 5)
SOME = (30, 1)
LOW_CTR = 0.01
HIGH = 8.0
NEAR = (8.0, 20.0)
RULES = ("low_ctr", "near")


def _span(first: date, last: date) -> list[str]:
    return [(first + timedelta(days=i)).isoformat() for i in range((last - first).days + 1)]


def _ctr(clicks, shown):
    return round(clicks / shown, 4) if shown else None


def _pos(weight, seen):
    return round(weight / seen, 2) if seen else None


def sums(stored: dict, days: list[str], kind: str) -> dict:
    """{key: [clicks, impressions, position x impressions, impressions with a position]}."""
    out: dict = {}
    for d in days:
        for key, c, i, p in ((stored.get(d) or {}).get(kind) or {}).get("rows") or []:
            got = out.setdefault(key, [0, 0, 0.0, 0])
            got[0] += c
            got[1] += i
            if p is not None and i:
                got[2] += p * i
                got[3] += i
    return out


def _row(key, v) -> list:
    return [key, sd._clean(v[0]), sd._clean(v[1]), _ctr(v[0], v[1]), _pos(v[2], v[3])]


def _ranked(rows: list[list]) -> list[list]:
    return sorted(rows, key=lambda r: (-r[2], -r[1], r[0]))


# --------------------------------------------------------------------- coverage

def coverage(stored: dict, finals: dict, first: date, last: date,
             history_first: str | None) -> dict:
    span = _span(first, last)
    have = [d for d in span if "total" in (stored.get(d) or {})]
    before = [d for d in span if history_first is None or d < history_first]
    shown = sum((stored[d]["total"].get("total") or {}).get("impressions") or 0 for d in have)
    return {"days": len(span), "stored": len(have), "before_history": len(before),
            "missing": [d for d in span if d not in have and d not in before],
            "provisional": [d for d in have if not finals.get(d)],
            "history_first": history_first, "empty": bool(have) and not shown}


# ---------------------------------------------------------------------- changes

def _part(rows: list[list]) -> dict:
    return {"count": len(rows), "clicks": sd._clean(sum(r[1] for r in rows)),
            "impressions": sd._clean(sum(r[2] for r in rows)), "rows": rows[:LIST]}


def changes(stored: dict, finals: dict, last_final: str | None, n: int,
            history_first: str | None) -> dict:
    if n >= max(PERIODS):
        return {"state": "too_long"}
    if last_final is None:
        return {"state": "no_final"}
    end = date.fromisoformat(last_final)
    now = _span(end - timedelta(days=n - 1), end)
    before = _span(end - timedelta(days=2 * n - 1), end - timedelta(days=n))
    out = {"now": {"first": now[0], "last": now[-1]},
           "before": {"first": before[0], "last": before[-1]}}
    not_whole = [d for d in before + now
                 if "query" not in (stored.get(d) or {}) or not finals.get(d)]
    if not_whole:
        return {**out, "state": "short", "need_from": before[0], "history_first": history_first,
                "not_whole": len(not_whole)}
    cur, old = sums(stored, now, "query"), sums(stored, before, "query")
    folded = sum(1 for d in before + now if (stored[d]["query"].get("others") or {}).get("rows"))
    return {**out, "state": "ok",
            "new": _part(_ranked([_row(k, v) for k, v in cur.items() if k not in old])),
            "lost": _part(_ranked([_row(k, v) for k, v in old.items() if k not in cur])),
            "queries_now": len(cur), "queries_before": len(old), "folded_days": folded}


# -------------------------------------------------------------------- positions

def buckets(first: date, last: date, n: int) -> list[list[str]]:
    """The period's days in buckets of BUCKET[n], oldest first; the oldest may be short."""
    span, size = _span(first, last), BUCKET[n]
    k = -(-len(span) // size)
    return [span[max(0, len(span) - (k - j) * size):len(span) - (k - 1 - j) * size]
            for j in range(k)]


def positions(stored: dict, finals: dict, first: date, last: date, n: int) -> dict:
    parts = buckets(first, last, n)
    out = {"size": BUCKET[n], "buckets": [
        {"first": b[0], "last": b[-1], "days": sum(1 for d in b if d in stored),
         "provisional": any(d in stored and not finals.get(d) for d in b)} for b in parts]}
    span = [d for b in parts for d in b]
    for kind in ("query", "page"):
        total = sums(stored, span, kind)
        keep = sorted(total.items(), key=lambda kv: (-kv[1][1], -kv[1][0], kv[0]))[:TRACK]
        by_bucket = [sums(stored, b, kind) for b in parts] if keep else []
        per = {k: [got.get(k) for got in by_bucket] for k, _ in keep}
        rows = []
        for key, v in keep:
            points = [_pos(c[2], c[3]) if c else None for c in per[key]]
            seen = [p for p in points if p is not None]
            rows.append({"key": key, "clicks": sd._clean(v[0]), "impressions": sd._clean(v[1]),
                         "position": _pos(v[2], v[3]), "points": points,
                         "shown": [sd._clean(c[1]) if c else None for c in per[key]],
                         "first": seen[0] if seen else None, "last": seen[-1] if seen else None,
                         "change": round(seen[0] - seen[-1], 2) if len(seen) > 1 else None})
        out[kind] = {"keys": len(total), "rows": rows}
    return out


# ---------------------------------------------------------------- opportunities

def rule_of(impressions, ctr, position, many: float, some: float) -> str | None:
    if position is None:
        return None
    if NEAR[0] <= position <= NEAR[1] and impressions >= some:
        return "near"
    if position < HIGH and impressions >= many and ctr is not None and ctr < LOW_CTR:
        return "low_ctr"
    return None


def opportunities(stored: dict, first: date, last: date) -> dict:
    span = _span(first, last)
    have = [d for d in span if "query" in (stored.get(d) or {})]
    with_pages = [d for d in span if "query_page" in (stored.get(d) or {})]
    many = max(MANY[0], MANY[1] * len(have))
    some = max(SOME[0], SOME[1] * len(have))
    best: dict = {}
    for key, v in sums(stored, with_pages, "query_page").items():
        query, _, page = str(key).partition(sd.QP_SEP)
        b = best.setdefault(query, {"page": None, "i": -1, "c": -1, "pages": 0, "all": 0})
        b["pages"] += 1
        b["all"] += v[1]
        if (v[1], v[0]) > (b["i"], b["c"]) or ((v[1], v[0]) == (b["i"], b["c"]) and page < b["page"]):
            b.update(page=page, i=v[1], c=v[0])
    found = []
    for key, v in sums(stored, have, "query").items():
        _, clicks, shown, ctr, pos = _row(key, v)
        rule = rule_of(shown, ctr, pos, many, some)
        if rule is None:
            continue
        b = best.get(key)
        found.append({"query": key, "rule": rule, "clicks": clicks, "impressions": shown,
                      "ctr": ctr, "position": pos, "page": b["page"] if b else None,
                      "pages": b["pages"] if b else 0,
                      "page_share": round(b["i"] / b["all"], 4) if b and b["all"] else None})
    found.sort(key=lambda r: (-r["impressions"], -r["clicks"], r["query"]))
    return {"days": len(have), "count": len(found),
            "by_rule": {r: sum(1 for x in found if x["rule"] == r) for r in RULES},
            "rules": {"many": many, "some": some, "low_ctr": LOW_CTR, "high": HIGH,
                      "near": list(NEAR)},
            "pages_from": with_pages[0] if with_pages else None, "pages_days": len(with_pages),
            "rows": found[:LIST]}


# --------------------------------------------------------------------- together

def periods(stored: dict, finals: dict, summary: dict, full: bool = True) -> dict:
    """{str(N): {"coverage", and with full "changes", "positions", "opportunities"}}
    for each period ending at the newest stored day."""
    if not summary.get("last"):
        return {}
    last = date.fromisoformat(summary["last"])
    finals_have = [d for d in stored if finals.get(d) and "total" in stored[d]]
    last_final = max(finals_have) if finals_have else None
    out = {}
    for n in PERIODS:
        first = last - timedelta(days=n - 1)
        got = {"coverage": coverage(stored, finals, first, last, summary.get("first"))}
        if full:
            got["changes"] = changes(stored, finals, last_final, n, summary.get("first"))
            got["positions"] = positions(stored, finals, first, last, n)
            got["opportunities"] = opportunities(stored, first, last)
        out[str(n)] = got
    return out


def for_site(db, site: str, engine: str = "google") -> dict:
    """What search.json's periods carry, read from history (the audit's comparison)."""
    summary = sd.summary(db, site, engine)
    if not summary["days"]:
        return {}
    last = date.fromisoformat(summary["last"])
    stored, finals = sd.read(db, site, engine, last - timedelta(days=max(PERIODS) - 1), last)
    return periods(stored, finals, summary, full=engine == "google")
