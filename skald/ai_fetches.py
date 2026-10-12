"""The day's AI user fetches as minute records: the day kind `ai_fetches`.

What "likely sent by an AI assistant" needs to look back from a lead's or a
conversion's touch (ai_likely.py): per minute (UTC), assistant (by
classify.AI_FETCHER_OWNERS) and path, how many fetches the assistant's
user fetcher made. Nothing else: no address, no user agent, no query
string, nothing about a person - these are an AI company's requests.
Kept FETCH_DAYS (180) days, the leads' window, then deleted (cli.prune_kept).

    {"rows": [["2026-10-12T10:00", "chatgpt.com", "/pricing/", 1], ...]}

The rows add up to the answer-engine group's "asked" requests. None (not
recorded) when `attribution.ai_likely` is false. Second count:
audit_ai_likely.py rebuilds the rows from the raw lines.
"""
from __future__ import annotations

from collections import Counter

from .ai_likely import minute_iso


def finish(extras, totals, journeys, page_visits, readers_by_hour) -> dict | None:
    conf = getattr(extras, "attribution", None) or {}
    fetched = getattr(extras, "ai_fetches", None)
    if not conf.get("on", True) or fetched is None:
        return None
    rows = Counter((minute_iso(m), who, path) for m, who, path in fetched.rows)
    return {"rows": [[*key, int(n)] for key, n in sorted(rows.items())]}


def check(totals, blob, differs, problems) -> None:
    from .classify import Group
    engines = totals.groups.get(Group.ANSWER_ENGINE)
    differs("ai_fetches: user fetches by minute", sum(int(r[3]) for r in blob.get("rows") or []),
            int(engines.tiers.get("asked", 0)) if engines else 0, "asked fetches")
