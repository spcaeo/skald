"""The second road for the synced search figures (search/, history table
`search_days`). Registered in audit_more.DAILY: run-daily runs it after the
audit, for each site with Search Console or Bing connected.

Search Console's and Bing's figures are not Skald's count: they come from
the engine, like a booking from a hook or a lead from the CMS, so the audit
cannot recount them from the log. What it checks instead, apart from the
sync's code (search/days.py, search/sync.py):

  1. Every stored blob of the last CHECK_DAYS stored days adds up, re-added by
     SQL (SQLite's json_each over the stored JSON, never days.sums_hold): for
     clicks and impressions, the rows plus "(all others)" plus what the
     engine does not attribute equal the blob's total.
  2. Search Console's query, country, device and search-appearance blobs
     carry the same day total as the day's `total` row (all four are counted
     by property); the page blob carries Google's by-page total, which may be
     larger and is never compared with it; the query_page blob (each query
     with its page, counted by page) carries the page blob's total.
  3. One figure is fetched again from the engine: the newest final day's
     clicks and impressions (Search Console: dataState "final", by property;
     Bing: GetRankAndTrafficStats), by its own request, and compared with
     what is stored. An engine that cannot be reached is said in the log and
     is not a mismatch; a figure that differs is.

  4. The Search tab's reports (search/reports.py: new and lost queries,
     position tracking, opportunities) are worked out again by SQL from the
     stored rows (audit_search_reports.py) and compared with what the tab shows.

A mismatch ends run-daily as "withheld" (audit_more): the search tables say
the day is in question rather than draw it. The cross-check against Skald's
own visits (search/data.py) is a comparison, never a check: the two count
different things and are never expected to match.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

CHECK_DAYS = 40


def set_up(ctx) -> bool:
    from .search.sync import connected
    return any(connected(getattr(ctx, "config", None) or {}).values())


def daily(ctx, day) -> list[str] | None:
    from .search.sync import connected
    engines = [e for e, source in connected(ctx.config).items() if source]
    if not engines:
        return None
    from .search import state
    problems: list[str] = []
    with ctx.history() as history:
        db = history.db
        for engine in engines:
            found = sums(db, ctx.site, engine)
            if engine == "google":
                found += same_totals(db, ctx.site)
                found += same_page_totals(db, ctx.site)
                from . import audit_search_reports
                found += audit_search_reports.check(db, ctx.site)
            found += refetch(ctx, db, engine)
            # The Search tab says what the second road found, in plain words.
            state.update(Path(ctx.db_path).parent, ctx.site, engine, audit={
                "at": state.now_text(), "ok": not found, "problems": found[:10]})
            problems += found
    return problems


def _recent(db, site: str, engine: str) -> str | None:
    row = db.execute("SELECT day FROM search_days WHERE site = ? AND engine = ? "
                     "GROUP BY day ORDER BY day DESC LIMIT 1 OFFSET ?",
                     (site, engine, CHECK_DAYS - 1)).fetchone()
    return row[0] if row else None


def sums(db, site: str, engine: str) -> list[str]:
    """Rows + others + unattributed = total, by SQL."""
    since = _recent(db, site, engine) or "0000-00-00"
    out = []
    for d, kind, field, total, rows, others, rest in db.execute(
            """
            SELECT s.day, s.kind, f.name,
                   json_extract(s.data, '$.total.' || f.name),
                   (SELECT COALESCE(SUM(json_extract(r.value, '$[' || f.pos || ']')), 0)
                      FROM json_each(s.data, '$.rows') AS r),
                   json_extract(s.data, '$.others.' || f.name),
                   json_extract(s.data, '$.unattributed.' || f.name)
              FROM search_days AS s,
                   (SELECT 'clicks' AS name, 1 AS pos UNION ALL
                    SELECT 'impressions', 2) AS f
             WHERE s.site = ? AND s.engine = ? AND s.day >= ?
            """, (site, engine, since)):
        if None in (total, others, rest) or abs((rows + others + rest) - total) > 0.01:
            out.append(f"{engine} {d} {kind}: {field} rows {rows} + others {others} + "
                       f"unattributed {rest} != total {total}")
    return out


def same_totals(db, site: str) -> list[str]:
    since = _recent(db, site, "google") or "0000-00-00"
    out = []
    for d, kind, clicks, shown, day_clicks, day_shown in db.execute(
            """
            SELECT k.day, k.kind, json_extract(k.data, '$.total.clicks'),
                   json_extract(k.data, '$.total.impressions'),
                   json_extract(t.data, '$.total.clicks'),
                   json_extract(t.data, '$.total.impressions')
              FROM search_days AS k JOIN search_days AS t
                ON t.site = k.site AND t.engine = k.engine AND t.day = k.day
               AND t.kind = 'total'
             WHERE k.site = ? AND k.engine = 'google' AND k.day >= ?
               AND k.kind IN ('query', 'country', 'device', 'appearance')
            """, (site, since)):
        if (clicks, shown) != (day_clicks, day_shown):
            out.append(f"google {d} {kind}: total {clicks}/{shown} is not the day's "
                       f"{day_clicks}/{day_shown}")
    return out


def same_page_totals(db, site: str) -> list[str]:
    """query_page is counted by page, as the page blob is: the same day total."""
    since = _recent(db, site, "google") or "0000-00-00"
    out = []
    for d, clicks, shown, page_clicks, page_shown in db.execute(
            """
            SELECT k.day, json_extract(k.data, '$.total.clicks'),
                   json_extract(k.data, '$.total.impressions'),
                   json_extract(p.data, '$.total.clicks'),
                   json_extract(p.data, '$.total.impressions')
              FROM search_days AS k JOIN search_days AS p
                ON p.site = k.site AND p.engine = k.engine AND p.day = k.day
               AND p.kind = 'page'
             WHERE k.site = ? AND k.engine = 'google' AND k.day >= ? AND k.kind = 'query_page'
            """, (site, since)):
        if (clicks, shown) != (page_clicks, page_shown):
            out.append(f"google {d} query_page: total {clicks}/{shown} is not the page "
                       f"table's {page_clicks}/{page_shown}")
    return out


def _newest_final(db, site: str, engine: str):
    return db.execute(
        "SELECT day, json_extract(data, '$.total.clicks'), "
        "json_extract(data, '$.total.impressions'), source FROM search_days "
        "WHERE site = ? AND engine = ? AND kind = 'total' AND final = 1 "
        "ORDER BY day DESC LIMIT 1", (site, engine)).fetchone()


def refetch(ctx, db, engine: str) -> list[str]:
    """The newest final day's totals, asked of the engine again."""
    from .search import http, sync
    got = _newest_final(db, ctx.site, engine)
    if got is None:
        return []
    day, clicks, shown, source = got
    job = sync.job_of(ctx)
    try:
        if engine == "google":
            client = sync.google_client(job)
            rows, _ = client.query(source, {
                "startDate": day, "endDate": day, "dimensions": ["date"], "type": "web",
                "dataState": "final", "aggregationType": "byProperty"})
            answer = [(r.get("clicks", 0), r.get("impressions", 0)) for r in rows]
        else:
            client = sync.bing_client(job)
            answer = [(r["clicks"], r["impressions"]) for r in client.traffic(source)
                      if r["day"] == date.fromisoformat(day)]
    except http.Failed as why:
        ctx.err(f"search audit: could not ask {engine} again ({why}); not checked today")
        return []
    fresh = answer[0] if answer else (0, 0)
    if (float(fresh[0]), float(fresh[1])) != (float(clicks), float(shown)):
        return [f"{engine} {day}: stored {clicks} clicks / {shown} impressions, the engine "
                f"now says {fresh[0]} / {fresh[1]}"]
    return []

