"""The second road for the MCP's search_performance (2.48): Search Console's
figures per page and per day, and the index status counts.

Run by audit_search.daily for a site with Search Console connected. It reads
the stored rows by its own SQL (SQLite's json_each over `search_days`, never
search/days.py's reading) and its own SQL over `search_inspect`, and compares
with what mcp/tools_search.figures gives, over the last WINDOW stored days:

  site      each day's clicks and impressions from the `total` row; the sums
  pages     the PAGES most shown paths of the window: each day's clicks and
            impressions summed over every address whose path is the page's
            (its own path parsing: the part after the host, before ? or #);
            a day whose page table has no row for it is 0 when the table is
            complete (no "(all others)", nothing unattributed), else unknown
  countries (2.48) each of those pages' countries over the window, summed by SQL
            from the page_country rows, against the tool's list
  index     each address's newest answer, counted by status

It shares only the table names, the status names and the window's rules.
A problem is a figure the tool gives that this road does not.
"""
from __future__ import annotations

from datetime import date, timedelta

WINDOW = 28
PAGES = 25
TOL = 0.011


def _path(url: str) -> str:
    rest = url.split("://", 1)[1] if "://" in url else url
    cut = rest.find("/")
    p = rest[cut:] if cut >= 0 else "/"
    for mark in ("?", "#"):
        p = p.split(mark, 1)[0]
    return p or "/"


def _window(db, site: str) -> tuple[date, date] | None:
    row = db.execute("SELECT MAX(day) FROM search_days WHERE site = ? AND engine = 'google' "
                     "AND kind = 'total'", (site,)).fetchone()
    if not row or not row[0]:
        return None
    last = date.fromisoformat(row[0])
    return last - timedelta(days=WINDOW - 1), last


def own_pages(db, site: str, first: date, last: date) -> tuple[dict, dict]:
    """({path: {day: [clicks, impressions]}}, {day: complete}) by SQL."""
    got: dict = {}
    complete: dict = {}
    for d, others, un_c, un_i in db.execute(
            "SELECT day, json_extract(data, '$.others.rows'), "
            "json_extract(data, '$.unattributed.clicks'), "
            "json_extract(data, '$.unattributed.impressions') FROM search_days "
            "WHERE site = ? AND engine = 'google' AND kind = 'page' AND day BETWEEN ? AND ?",
            (site, first.isoformat(), last.isoformat())):
        complete[d] = not others and not un_c and not un_i
    for d, url, c, i in db.execute(
            "SELECT s.day, json_extract(r.value, '$[0]'), json_extract(r.value, '$[1]'), "
            "json_extract(r.value, '$[2]') FROM search_days AS s, json_each(s.data, '$.rows') AS r "
            "WHERE s.site = ? AND s.engine = 'google' AND s.kind = 'page' "
            "AND s.day BETWEEN ? AND ?", (site, first.isoformat(), last.isoformat())):
        cell = got.setdefault(_path(url), {}).setdefault(d, [0, 0])
        cell[0] += c
        cell[1] += i
    return got, complete


def check(db, site: str) -> tuple[list[str], int]:
    """(problems, figures compared)."""
    from .mcp.tools_search import figures
    span = _window(db, site)
    if span is None:
        return [], 0
    first, last = span
    problems: list[str] = []
    n = 0
    # The site's days.
    mine = {d: (c, i) for d, c, i in db.execute(
        "SELECT day, json_extract(data, '$.total.clicks'), "
        "json_extract(data, '$.total.impressions') FROM search_days WHERE site = ? "
        "AND engine = 'google' AND kind = 'total' AND day BETWEEN ? AND ?",
        (site, first.isoformat(), last.isoformat()))}
    tool = figures(db, site, "google", None, first, last)
    for row in tool["days"]:
        n += 1
        if mine.get(row["day"]) is None or abs(mine[row["day"]][0] - row["clicks"]) > TOL \
                or abs(mine[row["day"]][1] - row["impressions"]) > TOL:
            problems.append(f"search_performance {site} {row['day']}: tool "
                            f"{row['clicks']}/{row['impressions']}, recount {mine.get(row['day'])}")
    if set(mine) != {r["day"] for r in tool["days"]}:
        problems.append(f"search_performance {site}: days differ")
    # The pages.
    pages, complete = own_pages(db, site, first, last)
    shown = sorted(pages, key=lambda p: (-sum(v[1] for v in pages[p].values()), p))[:PAGES]
    for path in shown:
        tool = figures(db, site, "google", path, first, last)
        for row in tool["days"]:
            n += 1
            have = pages[path].get(row["day"])
            want = have if have else ([0, 0] if complete.get(row["day"]) else None)
            if want is None:
                if row["clicks"] is not None:
                    problems.append(f"search_performance {site} {path} {row['day']}: tool "
                                    f"{row['clicks']}, recount unknown")
            elif row["clicks"] is None or abs(want[0] - row["clicks"]) > TOL \
                    or abs(want[1] - row["impressions"]) > TOL:
                problems.append(f"search_performance {site} {path} {row['day']}: tool "
                                f"{row['clicks']}/{row['impressions']}, recount {want}")
    # The pages' countries.
    pc: dict = {}
    for url_country, c, i in db.execute(
            "SELECT json_extract(r.value, '$[0]'), json_extract(r.value, '$[1]'), "
            "json_extract(r.value, '$[2]') FROM search_days AS s, json_each(s.data, '$.rows') AS r "
            "WHERE s.site = ? AND s.engine = 'google' AND s.kind = 'page_country' "
            "AND s.day BETWEEN ? AND ?", (site, first.isoformat(), last.isoformat())):
        url, _, country = str(url_country).partition("\t")
        cell = pc.setdefault(_path(url), {}).setdefault(country, [0, 0])
        cell[0] += c
        cell[1] += i
    for path in shown:
        told = figures(db, site, "google", path, first, last).get("countries") or []
        for row in told:
            n += 1
            want = (pc.get(path) or {}).get(row["country"])
            if want is None or abs(want[0] - row["clicks"]) > TOL \
                    or abs(want[1] - row["impressions"]) > TOL:
                problems.append(f"search_performance {site} {path} country {row['country']}: "
                                f"tool {row['clicks']}/{row['impressions']}, recount {want}")
    # The index counts.
    try:
        own: dict = {}
        for (status,) in db.execute(
                "SELECT status FROM search_inspect AS a WHERE site = ? AND inspected_at = "
                "(SELECT MAX(b.inspected_at) FROM search_inspect AS b "
                " WHERE b.site = a.site AND b.url = a.url)", (site,)):
            own[status] = own.get(status, 0) + 1
    except Exception:                                   # noqa: BLE001 - an older history
        own = {}
    from .search import inspect
    told = (inspect.counts(db, site) or {}).get("by_status") or {}
    if own or told:
        n += 1
        if own != told:
            problems.append(f"search_performance {site} index: tool {told}, recount {own}")
    return problems, n
