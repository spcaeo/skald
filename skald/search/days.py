"""Search figures in history: the `search_days` table (history schema 14).

One row per site, engine, day and kind, holding one JSON blob:

  engine   "google" (Search Console) or "bing" (Bing Webmaster Tools)
  day      the engine's own day: Search Console's days are Pacific Time
           (America/Los_Angeles), as Google gives them; Bing's are the dates
           Bing gives. Never re-cut into the site's time zone.
  kind     total, query, page, country, device, appearance, and (Search
           Console only) query_page: each query with the page it
           showed, keyed "<query>\t<page>" (QP_SEP), counted by page as Google
           does when the page is a dimension
  final    1 when the engine says the day will not change (Search Console:
           before the answer's first_incomplete_date; Bing: older than
           BING_FINAL_DAYS); 0: provisional, fetched again by the next sync
  source   the property or site address it was read from

A blob (`fold`):

  total         {"clicks", "impressions", "position"}: the engine's own total
                for the day in this kind's terms (Search Console counts a page
                table by page and the rest by property, so the page kind has
                its own total)
  rows          [[key, clicks, impressions, position], ...]: the TOP[kind]
                largest by clicks, then impressions, then key
  others        {"rows", "clicks", "impressions", "position"}: every row past
                the top, summed ("(all others)"); position is their
                impression-weighted mean
  unattributed  {"clicks", "impressions"}: total minus every row the engine
                returned. Positive: what the engine counts but does not give
                by this dimension (Search Console leaves out anonymised
                queries). Negative: rows overlap (one result can count under
                more than one search appearance). Never hidden, never forced.
  complete      no others and nothing unattributed: the rows are the total

So for clicks and impressions alike, always:

    sum(rows) + others + unattributed = total

`write` replaces a day's kinds in one transaction and reads them back:
what is stored must be exactly what was folded from the engine's answer
(`check`), else the write is undone and the sync fails. audit_search.py
re-adds every stored blob by its own SQL (the second road).
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone

ENGINES = ("google", "bing")
KINDS = ("total", "query", "page", "country", "device", "appearance", "query_page")
TOP = {"query": 500, "page": 300, "country": 250, "device": 10, "appearance": 100,
       "query_page": 500}
QP_SEP = "\t"                          # query_page's key: query, a tab, the page address
OTHER = "(all others)"
BING_FINAL_DAYS = 10

TABLE = """
CREATE TABLE IF NOT EXISTS search_days (
    site       TEXT NOT NULL,
    engine     TEXT NOT NULL,           -- google / bing
    day        TEXT NOT NULL,           -- the engine's own day, YYYY-MM-DD
    kind       TEXT NOT NULL,           -- total, query, page, country, device, appearance,
                                        -- query_page
    data       TEXT NOT NULL,           -- JSON (search/days.py)
    final      INTEGER NOT NULL,        -- 1: the engine says it will not change
    source     TEXT NOT NULL,           -- the property / site address
    fetched_at TEXT NOT NULL,           -- UTC, ISO 8601
    PRIMARY KEY (site, engine, day, kind)
)"""


def num(value):
    """A count from an engine: an int when whole (Google sends doubles)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0
    value = float(value)
    return int(value) if value.is_integer() else round(value, 2)


def _clean(n):
    return int(n) if float(n).is_integer() else round(float(n), 2)


def weighted(rows) -> float | None:
    """The impression-weighted mean position of rows [key, c, i, pos]."""
    have = [(r[2], r[3]) for r in rows if r[3] is not None and r[2]]
    weight = sum(i for i, _ in have)
    return round(sum(i * p for i, p in have) / weight, 2) if weight else None


def fold(rows: list, total: dict | None, top: int) -> dict:
    """The blob for one day and kind. `rows` are [key, clicks, impressions,
    position]; `total` the engine's total (None: the rows are all there is,
    as with Bing's top tables)."""
    ordered = sorted(([str(k), num(c), num(i), None if p is None else round(float(p), 2)]
                      for k, c, i, p in rows), key=lambda r: (-r[1], -r[2], r[0]))
    kept, rest = ordered[:top], ordered[top:]
    sum_c = _clean(sum(r[1] for r in ordered))
    sum_i = _clean(sum(r[2] for r in ordered))
    if total is None:
        total = {"clicks": sum_c, "impressions": sum_i, "position": weighted(ordered)}
    total = {"clicks": num(total.get("clicks")), "impressions": num(total.get("impressions")),
             "position": None if total.get("position") is None
             else round(float(total["position"]), 2)}
    others = {"rows": len(rest), "clicks": _clean(sum(r[1] for r in rest)),
              "impressions": _clean(sum(r[2] for r in rest)), "position": weighted(rest)}
    unattributed = {"clicks": _clean(total["clicks"] - sum_c),
                    "impressions": _clean(total["impressions"] - sum_i)}
    return {"total": total, "rows": kept, "others": others, "unattributed": unattributed,
            "complete": not rest and unattributed == {"clicks": 0, "impressions": 0}}


def sums_hold(blob: dict) -> list[str]:
    """What does not add up in one blob (empty: it holds)."""
    out = []
    for field, at in (("clicks", 1), ("impressions", 2)):
        got = sum(r[at] for r in blob.get("rows") or []) + blob["others"][field] + \
            blob["unattributed"][field]
        if abs(got - blob["total"][field]) > 0.01:
            out.append(f"{field}: rows + others + unattributed = {got}, "
                       f"total {blob['total'][field]}")
    return out


def _now(now: datetime | None) -> str:
    return (now or datetime.now(timezone.utc)).astimezone(timezone.utc) \
        .isoformat(timespec="seconds")


def write(db, site: str, engine: str, days: dict, finals: dict, source: str,
          now: datetime | None = None) -> int:
    """Replace each day's kinds: days = {day: {kind: blob}}. Read back and
    checked in the same transaction; raises ValueError (nothing kept) when
    what was stored is not what was given or a blob does not add up."""
    stamp = _now(now)
    count = 0
    with db:
        for day, kinds in sorted(days.items()):
            d = day.isoformat() if isinstance(day, date) else str(day)
            for kind, blob in kinds.items():
                problems = sums_hold(blob)
                if problems:
                    raise ValueError(f"{engine} {d} {kind} does not add up: "
                                     + "; ".join(problems))
                db.execute(
                    "INSERT OR REPLACE INTO search_days (site, engine, day, kind, data, final, "
                    "source, fetched_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (site, engine, d, kind, json.dumps(blob, sort_keys=True),
                     1 if finals.get(day, finals.get(d)) else 0, source, stamp))
                count += 1
        problems = check(db, site, engine, days)
        if problems:
            raise ValueError("stored differs from the engine's answer: " + "; ".join(problems[:5]))
    return count


def check(db, site: str, engine: str, days: dict) -> list[str]:
    """What is stored for these days is exactly what was folded."""
    out = []
    for day, kinds in days.items():
        d = day.isoformat() if isinstance(day, date) else str(day)
        stored = {k: json.loads(v) for k, v in db.execute(
            "SELECT kind, data FROM search_days WHERE site = ? AND engine = ? AND day = ?",
            (site, engine, d))}
        for kind, blob in kinds.items():
            if stored.get(kind) != json.loads(json.dumps(blob)):
                out.append(f"{engine} {d} {kind}")
    return out


def read(db, site: str, engine: str, first: date, last: date,
         kinds=KINDS) -> tuple[dict, dict]:
    """({day: {kind: blob}}, {day: final}) for the days stored in [first, last]."""
    marks = ",".join("?" * len(kinds))
    out: dict = {}
    finals: dict = {}
    for d, kind, data, final in db.execute(
            f"SELECT day, kind, data, final FROM search_days WHERE site = ? AND engine = ? "
            f"AND day BETWEEN ? AND ? AND kind IN ({marks}) ORDER BY day",
            (site, engine, first.isoformat(), last.isoformat(), *kinds)):
        out.setdefault(d, {})[kind] = json.loads(data)
        finals[d] = bool(final) and finals.get(d, True)
    return out, finals


def summary(db, site: str, engine: str) -> dict:
    """{"days", "first", "last", "provisional", "fetched_at"} of the stored days."""
    try:
        row = db.execute(
            "SELECT COUNT(*), MIN(day), MAX(day), SUM(1 - final), MAX(fetched_at) "
            "FROM search_days WHERE site = ? AND engine = ? AND kind = 'total'",
            (site, engine)).fetchone()
    except Exception:                   # noqa: BLE001 - an older history: no table
        row = (0, None, None, 0, None)
    return {"days": int(row[0] or 0), "first": row[1], "last": row[2],
            "provisional": int(row[3] or 0), "fetched_at": row[4]}


def provisional(db, site: str, engine: str) -> list[str]:
    return [r[0] for r in db.execute(
        "SELECT DISTINCT day FROM search_days WHERE site = ? AND engine = ? AND final = 0 "
        "ORDER BY day", (site, engine))]
