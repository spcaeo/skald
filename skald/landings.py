"""Visits by the page they started on: the day kind `landings`.

What Overview > Summary's "Work on the page, or on traffic?", its "New and
updated pages" and Traffic > Pages' "Left after one page" and "Needs work"
stand on. Per landing page (each people visit counted once, on its first
page, as the readers' landing breakdown counts it), from the day's journeys:

  visits    the visits that started there
  one_page  of them, the visits that loaded that one page and no other: one
            page view in the server's log ("left at once"). A step a
            single-page app shows without asking the server is not in the
            log, so on such a site this is an upper bound
  views     the page views those visits made, on every page
  search    of the visits, those whose source is "Search engine"
  ai        of the visits, those whose source is "AI assistant" (a proven
            citation: a referrer or a tag; "likely" visits are never here)

    {"fields": ["visits", "one_page", "views", "search", "ai"], "top": 200,
     "folded": 0, "pages": {"/pricing/": [12, 9, 17, 4, 1], ...}}

The TOP pages with most visits (ties by path) are kept; the rest are summed
into one "(all others)" row and `folded` says how many paths it holds. Every
field adds up to the day's: visits to the visits, one_page to the one-page
visits, views to people's page views, search and ai to the visits from each
source. One_page <= visits <= views and search + ai <= visits in every row.

Second count: audit_landings.py, from the raw lines with the audit's own
labels and page rule; it shares no code with this module.
"""
from __future__ import annotations

FIELDS = ("visits", "one_page", "views", "search", "ai")
TOP = 200
OTHER = "(all others)"
SEARCH = "Search engine"
AI = "AI assistant"


def _fold(rows: dict) -> tuple[dict, int]:
    ordered = sorted(rows.items(), key=lambda kv: (-kv[1][0], kv[0]))
    out = {path: list(r) for path, r in ordered[:TOP]}
    rest = ordered[TOP:]
    if rest:
        out[OTHER] = [sum(r[i] for _, r in rest) for i in range(len(FIELDS))]
    return out, len(rest)


def finish(extras, totals, journeys, page_visits, readers_by_hour) -> dict | None:
    """The day's blob (day_more.py), or None when visits were not counted."""
    if journeys is None:
        return None
    rows: dict[str, list] = {}
    for j in journeys:
        row = rows.setdefault(str(j.get("landing") or ""), [0] * len(FIELDS))
        pages = int(j.get("pages") or 0)
        source = j.get("source")
        row[0] += 1
        row[1] += 1 if pages == 1 else 0
        row[2] += pages
        row[3] += 1 if source == SEARCH else 0
        row[4] += 1 if source == AI else 0
    pages, folded = _fold(rows)
    return {"fields": list(FIELDS), "top": TOP, "folded": folded, "pages": pages}


def check(totals, blob, differs, problems) -> None:
    """Every sum the blob promises (day_more.py)."""
    from .classify import Group
    from .verify import Problem
    rows = blob.get("pages") or {}
    sums = [sum(int(r[i]) for r in rows.values()) for i in range(len(FIELDS))]
    for path, r in sorted(rows.items()):
        if len(r) != len(FIELDS) or not (0 <= r[1] <= r[0] <= r[2]) or r[3] + r[4] > r[0]:
            problems.append(Problem(f"landings: {path}", f"{r!r} do not fit together "
                                    "(one-page <= visits <= page views, search + AI <= visits)"))
    stats = getattr(totals, "visits", None)
    people = (getattr(totals, "groups", None) or {}).get(Group.PEOPLE)
    if stats is not None:
        differs("landings: visits", sums[0], stats.visits, "visits")
        differs("landings: one-page visits", sums[1], stats.one_page(), "one-page visits")
        by = getattr(stats, "source", None) or {}
        differs("landings: visits from search", sums[3], int(by.get(SEARCH, 0)),
                "visits from search engines")
        differs("landings: visits from AI", sums[4], int(by.get(AI, 0)),
                "visits from AI assistants")
    if people is not None:
        differs("landings: page views", sums[2], int(people.views or 0), "page views by people")
    if int(blob.get("folded") or 0) and OTHER not in rows:
        problems.append(Problem("landings: fold", "paths folded with no (all others) row"))
