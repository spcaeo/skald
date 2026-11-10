"""The audit's own answer to "did a person read this fast?" (too_fast.py).

Written apart from too_fast.py, as the rest of the audit is: its own reading
of the two settings, its own browser test, its own visit split. The page
test is the audit's own (audit.is_page, passed in). It shares only the name
list OTHER_BOT from classify.py.

The rule it recounts (CLASSIFICATION.md, rule 9b): a browser-like visit -
address and agent, no gap longer than the session gap, on the site's hosts -
with at least site.too_fast_pages page views (6; 0 turns it off), all of
them within site.too_fast_seconds (2) of its first, is a bot: every line of
it, from its first line to its last. Rule 9c: so is one from a hosting
network (the audit's own reading of the hosting list, passed in) with at
least site.cloud_fast_pages page views (20; 0 turns it off) whose first and
last are no more than site.cloud_fast_seconds (10) apart per later page.
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


def cloud_settings(config: dict) -> tuple[int, int]:
    """(pages, seconds a page) for rule 9c, 20 and 10 when unset."""
    site = (config or {}).get("site") or {}
    try:
        pages = 20 if site.get("cloud_fast_pages") is None else int(site["cloud_fast_pages"])
        pace = 10 if site.get("cloud_fast_seconds") is None else int(site["cloud_fast_seconds"])
    except (TypeError, ValueError):
        return 20, 10
    return max(pages, 0), max(pace, 0)


def too_fast(config: dict, lines: list, gap: timedelta, hosts: set, is_page,
             from_hosting=None) -> dict:
    """{(address, agent): [(first, last)]} of the visits that read too fast."""
    least, seconds = settings(config)
    cloud, pace = cloud_settings(config) if from_hosting is not None else (0, 0)
    if least <= 0 and cloud <= 0:
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
            took = (max(read) - min(read)).total_seconds() if read else 0
            if (least > 0 and len(read) >= least and took <= limit.total_seconds()) or (
                    cloud > 0 and len(read) >= cloud and took <= pace * (len(read) - 1)
                    and from_hosting(pair[0])):
                found.setdefault(pair, []).append((visit[0].when, visit[-1].when))
    return found
