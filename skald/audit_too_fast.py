"""The audit's own answer to "did a person read this fast?" (too_fast.py).

Written apart from too_fast.py, as the rest of the audit is: its own reading
of the two settings, its own browser test, its own visit split. The page
test is the audit's own (audit.is_page, passed in). It shares only the name
list OTHER_BOT from classify.py.

The rule it recounts (CLASSIFICATION.md, rule 9b): a browser-like visit -
address and agent, no gap longer than the session gap, on the site's hosts -
with at least site.too_fast_pages page views (6; 0 turns it off), all of
them within site.too_fast_seconds (2) of its first, is a bot: every line of
it, from its first line to its last.
"""
from __future__ import annotations

import re
from datetime import timedelta

from .classify import OTHER_BOT

_BROWSERISH = re.compile(r"Mozilla/|Opera/|Safari/|Chrome/|Firefox/", re.I)


def settings(config: dict) -> tuple[int, int]:
    """(pages, seconds) as config.yml's site section says, 6 and 2 when unset."""
    site = (config or {}).get("site") or {}
    try:
        pages = 6 if site.get("too_fast_pages") is None else int(site["too_fast_pages"])
        seconds = 2 if site.get("too_fast_seconds") is None else int(site["too_fast_seconds"])
    except (TypeError, ValueError):
        return 6, 2
    return max(pages, 0), max(seconds, 0)


def too_fast(config: dict, lines: list, gap: timedelta, hosts: set, is_page) -> dict:
    """{(address, agent): [(first, last)]} of the visits that read too fast."""
    least, seconds = settings(config)
    if least <= 0:
        return {}
    limit = timedelta(seconds=seconds)
    pairs: dict[tuple, list] = {}
    for line in lines:
        if hosts and line.host and line.host.lower() not in hosts:
            continue
        agent = line.agent
        if not agent or not _BROWSERISH.search(agent) or OTHER_BOT.search(agent):
            continue
        pairs.setdefault((line.address, agent), []).append(line)
    found: dict[tuple, list] = {}
    for pair, seen in pairs.items():
        seen.sort(key=lambda l: l.when)
        cut = [0] + [k for k in range(1, len(seen)) if seen[k].when - seen[k - 1].when > gap]
        for a, b in zip(cut, cut[1:] + [len(seen)]):
            visit = seen[a:b]
            read = [l.when for l in visit if is_page(l)]
            if len(read) >= least and max(read) - min(read) <= limit:
                found.setdefault(pair, []).append((visit[0].when, visit[-1].when))
    return found
