"""The day's AI user fetches as minute records: the day kind `ai_fetches`.

What "likely sent by an AI assistant" needs to look back from a lead's or a
conversion's touch (ai_likely.py): per minute (UTC), assistant (by
classify.AI_FETCHER_OWNERS) and path, how many fetches the assistant's
user fetcher made, and how many reads began there (ai_reads.py: an
assistant's page asked for again within its window, or a file the page
loaded, starts none). Nothing else: no address, no user agent, no query
string, nothing about a person - these are an AI company's requests.
Kept FETCH_DAYS (180) days, the leads' window, then deleted (cli.prune_kept).

    {"rows": [["2026-10-12T10:00", "chatgpt.com", "/pricing/", 2, 1], ...]}

The fourth column adds up to the answer-engine group's "asked" requests,
the fifth to the day's reads (ai_reads). A day stored before reads were
counted has four columns: its reads are not recorded, never 0. None (not
recorded) when `attribution.ai_likely` is false. Second count:
audit_ai_likely.py rebuilds the requests, audit_ai_reads.py the reads.
"""
from __future__ import annotations

from collections import Counter

from .ai_likely import minute_iso


def finish(extras, totals, journeys, page_visits, readers_by_hour) -> dict | None:
    conf = getattr(extras, "attribution", None) or {}
    fetched = getattr(extras, "ai_fetches", None)
    if not conf.get("on", True) or fetched is None:
        return None
    rows = Counter(fetched.rows)
    started = getattr(fetched, "started", Counter())
    return {"rows": [[minute_iso(m), who, path, int(n), int(started.get((m, who, path), 0))]
                     for (m, who, path), n in sorted(rows.items())]}


def check(totals, blob, differs, problems) -> None:
    from .classify import Group
    engines = totals.groups.get(Group.ANSWER_ENGINE)
    rows = blob.get("rows") or []
    differs("ai_fetches: user fetches by minute", sum(int(r[3]) for r in rows),
            int(engines.tiers.get("asked", 0)) if engines else 0, "asked fetches")
    if any(len(r) > 4 and int(r[4]) > int(r[3]) for r in rows):
        from .verify import Problem
        problems.append(Problem("ai_fetches", "a minute row with more reads than fetches"))


def reads_of(row) -> int | None:
    """A stored row's reads, or None for a row stored before they were counted."""
    return int(row[4]) if len(row) > 4 else None
