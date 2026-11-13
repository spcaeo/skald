"""Second count for the MCP's page_journeys (2.49, #51), by its own road.

page_journeys (mcp/tools_journeys.py) reads the stored journeys in Python: a
visit read a page when a "page" step of its trail names it; it landed on the
page when its first page step does; it left from the page when its last page
step does. This recounts the same three figures straight from the `journeys`
table in SQL (json_each over each visit's trail), sharing nothing with the
tool but the word "page", for the site's most read pages over its newest
CHECK_DAYS kept days, and says where they differ.

Run by the day audit (audit.py) for every site that keeps journeys.
"""
from __future__ import annotations

from datetime import date, timedelta

CHECK_DAYS = 7
TOP_PATHS = 25

STEPS = ("SELECT j.day, j.seq, CAST(t.key AS INTEGER) AS k, json_extract(t.value, '$[0]') AS path "
         "FROM journeys j, json_each(j.data, '$.trail') t "
         "WHERE j.site = ? AND j.day BETWEEN ? AND ? AND json_extract(t.value, '$[1]') = 'page'")


def recount(db, site: str, first: str, last: str, paths: list[str]) -> dict:
    """{path: (visits, landed, left)} by SQL."""
    got = {}
    for p in paths:
        visits = db.execute(f"SELECT COUNT(*) FROM (SELECT DISTINCT day, seq FROM ({STEPS}) "
                            "WHERE path = ?)", (site, first, last, p)).fetchone()[0]
        landed = db.execute(
            f"SELECT COUNT(*) FROM ({STEPS}) s WHERE s.path = ? AND s.k = "
            f"(SELECT MIN(k) FROM ({STEPS}) o WHERE o.day = s.day AND o.seq = s.seq)",
            (site, first, last, p, site, first, last)).fetchone()[0]
        left = db.execute(
            f"SELECT COUNT(*) FROM ({STEPS}) s WHERE s.path = ? AND s.k = "
            f"(SELECT MAX(k) FROM ({STEPS}) o WHERE o.day = s.day AND o.seq = s.seq)",
            (site, first, last, p, site, first, last)).fetchone()[0]
        got[p] = (visits, landed, left)
    return got


def check(db, site: str) -> tuple[list[str], int]:
    """(problems, figures compared) for the newest CHECK_DAYS kept days."""
    newest = db.execute("SELECT MAX(day) FROM journeys WHERE site = ?", (site,)).fetchone()[0]
    if not newest:
        return [], 0
    last = date.fromisoformat(newest)
    first = last - timedelta(days=CHECK_DAYS - 1)
    a, b = first.isoformat(), last.isoformat()
    paths = [r[0] for r in db.execute(
        f"SELECT path, COUNT(*) AS n FROM ({STEPS}) GROUP BY path ORDER BY n DESC, path LIMIT ?",
        (site, a, b, TOP_PATHS))]
    if not paths:
        return [], 0
    from .mcp.tools_journeys import figures
    tool = {p["path"]: p for p in figures(db, site, paths, first, last)["pages"]}
    second = recount(db, site, a, b, paths)
    problems, n = [], 0
    for p in paths:
        t = tool[p]
        mine = (t["visits"], t["arrived"]["landed_here"], t["left"])
        for name, x, y in zip(("visits", "landed on it", "left from it"), mine, second[p]):
            n += 1
            if x != y:
                problems.append(f"page_journeys {site} {p} {a}..{b}: {name} {x}, recounted {y}")
    return problems, n


def daily(ctx, day) -> list[str] | None:
    """The newest kept days' page_journeys figures recounted (day: unused, the
    tool reads the newest kept days). None when the site keeps no journeys."""
    with ctx.history() as history:
        problems, n = check(history.db, ctx.site)
    if not n:
        return None
    ctx.out(f"page journeys: {n} figures recounted for the {TOP_PATHS} most read pages of "
            f"the newest {CHECK_DAYS} kept days" + ("" if problems else ", all match"))
    return problems
