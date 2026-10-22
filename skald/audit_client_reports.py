"""The second count of a client report (client_report_data.py).

A client report shows no figure of its own: it sums days already stored,
verified and audited. What can still go wrong is the summing - which days
count, and adding them - so this module reads the history file again with
its own SQL, opened read-only, and none of store.py: the days' states from
`days`, the people's figures from `groups`, the cited visits from `days`.
It then checks the report against them:

  * which days were whole and verified, withheld, partial, not recorded
  * visitors, pages read and visitors from AI, summed over the whole days
  * each bar of the chart is its day's stored visitors, and a gap is a day
    not in the sum
  * a breakdown never adds up to more than the visitors it breaks down
  * the leads (the dashboard's Leads tile, conversions_leads.period_leads),
    counted again from the conversions file by one SQL GROUP BY
    (recount_leads, check_leads; the mails use it too)
  * Search Console (`search_days`, json_extract by SQL, none of search/):
    which days were final, provisional and not synced; the clicks and
    impressions of the final days; and each table's rows never add up to
    more than that table's own stored total

`recount` returns the differences in words; client_report_data refuses the
report when there is any.
"""
from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from pathlib import Path


def _states(conn, site: str, first: date, last: date) -> dict[str, str]:
    rows = {r[0]: r for r in conn.execute(
        "SELECT day, verified, partial_from, partial_until FROM days WHERE site = ? "
        "AND day >= ? AND day <= ?", (site, first.isoformat(), last.isoformat()))}
    out = {}
    d = first
    while d <= last:
        r = rows.get(d.isoformat())
        out[d.isoformat()] = ("missing" if r is None else "withheld" if not r[1]
                              else "partial" if (r[2] or r[3]) else "ok")
        d += timedelta(days=1)
    return out


def _search_console(conn, site: str, first: date, last: date, sc) -> list[str]:
    """The Search Console section against `search_days` read again."""
    if not sc or not sc.get("connected"):
        return []
    try:
        rows = conn.execute(
            "SELECT day, kind, final, json_extract(data, '$.total.clicks'), "
            "json_extract(data, '$.total.impressions') FROM search_days WHERE site = ? "
            "AND engine = 'google' AND day >= ? AND day <= ? AND kind IN ('total', 'query', "
            "'page')", (site, first.isoformat(), last.isoformat())).fetchall()
    except sqlite3.OperationalError:
        rows = []                       # an older history: no search_days
    kinds: dict[str, dict] = {}
    for day, kind, final, clicks, shown in rows:
        kinds.setdefault(day, {})[kind] = (final, clicks or 0, shown or 0)
    days = []
    d = first
    while d <= last:
        days.append(d.isoformat())
        d += timedelta(days=1)
    final = [x for x in days if x in kinds and "total" in kinds[x]
             and all(v[0] for v in kinds[x].values())]
    want = {"final": final, "provisional": [x for x in days if x in kinds and x not in final],
            "missing": [x for x in days if x not in kinds]}
    found = [f"Search Console {k} days {sc.get(k)} against {v}"
             for k, v in want.items() if sorted(sc.get(k) or []) != v]
    totals = sc.get("totals")
    if final:
        for at, field in ((1, "clicks"), (2, "impressions")):
            theirs = round(sum(kinds[x]["total"][at] for x in final), 2)
            mine = (totals or {}).get(field)
            if mine is None or abs(mine - theirs) > 0.01:
                found.append(f"Search Console {field} {mine} against {theirs}")
        for table, kind in (("queries", "query"), ("pages", "page")):
            cap = sum(kinds[x][kind][1] for x in final if kind in kinds[x])
            if sum(r["clicks"] for r in sc.get(table) or []) > cap + 0.01:
                found.append(f"Search Console {table} add up to more than their {cap} clicks")
    elif totals is not None:
        found.append("Search Console figures given with no final day")
    return found


LEAD_ACTIONS = ("contact", "signup", "waitlist", "trial", "demo")   # conversions.LEAD_ACTIONS
FINISHED = ("completed", "paid")                                     # conversions.FINISHED


def recount_leads(conv_path, site: str, tz, first: date, last: date) -> dict[str, int] | None:
    """The leads of first..last by action, counted again from the conversions
    file opened read-only by one SQL GROUP BY (none of conversions_data or
    store.py): finished rows of the lead actions, test rows left out, from the
    first local midnight to the one after `last`. None when there is no file."""
    from datetime import datetime, time, timezone
    if conv_path is None or not Path(conv_path).is_file():
        return None
    edge = lambda d: (datetime.combine(d, time(0), tzinfo=tz).astimezone(timezone.utc)  # noqa: E731
                      .strftime("%Y-%m-%dT%H:%M:%SZ"))
    conn = sqlite3.connect(f"file:{Path(conv_path).resolve()}?mode=ro", uri=True)
    acts, fin = ",".join("?" * len(LEAD_ACTIONS)), ",".join("?" * len(FINISHED))
    try:
        # One lead counts once (2.26): a finished row with an earlier finished, unmarked
        # row of the same tool, ref and action (a paid after its completed) is no lead.
        rows = conn.execute(
            f"SELECT c.action, COUNT(*) FROM conversions c WHERE c.site = ? AND c.test = 0 "
            f"AND c.action IN ({acts}) AND c.stage IN ({fin}) AND c.at >= ? AND c.at < ? "
            f"AND NOT EXISTS (SELECT 1 FROM conversions e WHERE e.site = c.site AND "
            f"e.tool = c.tool AND e.external_ref = c.external_ref AND e.action = c.action AND "
            f"e.test = 0 AND e.stage IN ({fin}) AND (e.at < c.at OR (e.at = c.at AND "
            f"e.stage < c.stage))) GROUP BY c.action",
            (site, *LEAD_ACTIONS, *FINISHED, edge(first), edge(last + timedelta(days=1)),
             *FINISHED)).fetchall()
    finally:
        conn.close()
    return {a: int(n) for a, n in rows if n}


def check_leads(conv_path, site: str, tz, first: date, last: date, leads: dict | None) -> list[str]:
    """conversions_leads.period_leads' answer against recount_leads, in words."""
    if not leads or leads.get("state") != "ok":
        return []
    theirs = recount_leads(conv_path, site, tz, first, last)
    if theirs is None:
        return ["leads given with no conversions file to count them from"]
    found = []
    if leads["total"] != sum(theirs.values()):
        found.append(f"leads {leads['total']} against {sum(theirs.values())}")
    if leads.get("by_action") != theirs:
        found.append(f"leads by kind {leads.get('by_action')} against {theirs}")
    return found


def recount(path, site: str, first: date, last: date, data: dict) -> list[str]:
    """What in `data` differs from the history file read again."""
    if path is None or str(path) == ":memory:" or not Path(path).is_file():
        return []                       # an in-memory history (tests): nothing to reopen
    conn = sqlite3.connect(f"file:{Path(path).resolve()}?mode=ro", uri=True)
    try:
        states = _states(conn, site, first, last)
        whole = sorted(d for d, s in states.items() if s == "ok")
        found = []
        cov = data["coverage"]
        mine = {"withheld": cov["withheld"], "partial": cov["partial"],
                "missing": cov["missing"]}
        for kind in ("withheld", "partial", "missing"):
            theirs = sorted(d for d, s in states.items() if s == kind)
            if sorted(mine[kind]) != theirs:
                found.append(f"{kind} days {sorted(mine[kind])} against {theirs}")
        if cov["recorded"] != len(whole):
            found.append(f"{cov['recorded']} days counted against {len(whole)} verified")
        found += _search_console(conn, site, first, last, data.get("search_console"))
        if not whole:
            return found
        marks = ",".join("?" * len(whole))
        per = {r[0]: r[1:] for r in conn.execute(
            f"SELECT day, readers, views FROM groups WHERE site = ? AND grp = 'people' "
            f"AND day IN ({marks})", (site, *whole))}
        cited = conn.execute(f"SELECT COALESCE(SUM(cited_visits), 0) FROM days WHERE site = ? "
                             f"AND day IN ({marks})", (site, *whole)).fetchone()[0]
    finally:
        conn.close()
    readers = [per.get(d, (0, 0))[0] for d in whole]
    visitors = None if any(r is None for r in readers) else sum(readers)
    pages = sum(per.get(d, (0, 0))[1] or 0 for d in whole)
    head = data["headline"]
    for key, theirs in (("visitors", visitors), ("pages", pages), ("ai", cited)):
        if head[key] != theirs:
            found.append(f"{key} {head[key]} against {theirs}")
    for bar in data["daily"]:
        want = per.get(bar["day"], (0, 0))[0] if states.get(bar["day"]) == "ok" else None
        if bar["visitors"] != want:
            found.append(f"the bar for {bar['day']}: {bar['visitors']} against {want}")
    for name in ("sources", "countries", "cities"):
        rows = data.get(name) or []
        if visitors is not None and sum(r["n"] for r in rows) > visitors:
            found.append(f"{name} add up to more than the {visitors} visitors")
    return found
