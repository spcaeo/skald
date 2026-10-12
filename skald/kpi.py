"""The headline figures, defined once for the dashboard and the mail.

Each is read from a Totals, so a figure for one day, a week or a month comes
from the same code whether the Totals was built from a log or rebuilt from
history. Two renderers that each worked out "people visits" for themselves is
how the text and HTML of the old report drifted apart.

A change is only stated between two periods that are both complete. A week
with a day missing compared against a full week reads as a 14% fall that
never happened, so it is shown as not comparable instead.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .aggregate import Totals
from .classify import Group, ads_checks


def _group(totals: Totals, which: Group):
    return totals.groups.get(which)


def _people(attr: str) -> Callable[[Totals], int]:
    def get(totals: Totals) -> int:
        stats = _group(totals, Group.PEOPLE)
        return getattr(stats, attr) if stats else 0
    return get


def _tier(tier: str) -> Callable[[Totals], int]:
    def get(totals: Totals) -> int:
        stats = _group(totals, Group.ANSWER_ENGINE)
        return stats.tiers.get(tier, 0) if stats else 0
    return get


def _hits(which: Group) -> Callable[[Totals], int]:
    def get(totals: Totals) -> int:
        stats = _group(totals, which)
        return stats.hits if stats else 0
    return get


def _search_indexing(totals: Totals) -> int:
    """Search-engine fetches, less Google's ads quality checks."""
    stats = _group(totals, Group.SEARCH_ENGINE)
    return stats.hits - ads_checks(stats.engines) if stats else 0


def _probes(totals: Totals) -> int:
    stats = _group(totals, Group.BOTS)
    return stats.probes if stats else 0


def _not_found(totals: Totals) -> int | None:
    """404s people were served. None before the breakdowns were counted."""
    if not totals.breakdowns:
        return None
    stats = _group(totals, Group.PEOPLE)
    return stats.statuses.get("404", 0) if stats else 0


def _server_errors(totals: Totals) -> int | None:
    """5xx responses, to anyone. None before the breakdowns were counted."""
    if not totals.breakdowns:
        return None
    return sum(s.statuses.get("5xx", 0) for s in totals.groups.values())


@dataclass(frozen=True)
class Kpi:
    key: str
    label: str
    note: str
    value: Callable[[Totals], int | None]


KPIS = [
    Kpi("people_readers", "Real people: readers",
        "visits that read at least one page, counted only when the browser loaded the page's scripts and styles, so automated readers are left out",
        _people("readers")),
    Kpi("people_visits", "All browser sessions",
        "including the ones that read no page", _people("visits")),
    Kpi("people_views", "Pages read by people",
        "HTML page views; payloads and assets excluded", _people("views")),
    Kpi("cited_visits", "Visitors from an AI citation",
        "once per visitor; undercounts", _people("cited_visits")),
    Kpi("ai_training", "AI fetches to train or index",
        "nobody is waiting on these", _tier("training")),
    Kpi("ai_asked", "AI fetches for a live question",
        "a reader is waiting on each one", _tier("asked")),
    Kpi("search", "Search-engine fetches",
        "indexing; ads quality checks not included", _search_indexing),
    Kpi("bots", "Bots and scanners",
        "requests, not visitors", _hits(Group.BOTS)),
    Kpi("probes", "of which scanner probes",
        "paths no real site serves", _probes),
    Kpi("people_404", "Page not found, seen by people",
        "404 responses to real people's requests", _not_found),
    Kpi("server_errors", "Server errors (5xx)",
        "responses to anyone; should be zero", _server_errors),
]


def change(current: int | None, previous: int | None) -> tuple[str, str]:
    """(arrow, words) for current against previous. None = not comparable.

    A current value of None was not recorded (history from before the figure
    existed) and is said so.

    Arrows carry direction only, never good or bad: more bots is up, and so
    is more readers. The reader decides which they wanted.
    """
    if current is None:
        return ("", "not recorded")
    if previous is None:
        return ("", "not comparable")
    if previous == 0:
        return ("", "no change") if current == 0 else ("▲", "new")
    pct = (current - previous) / previous * 100
    if round(pct) == 0:
        return ("", "about the same")
    arrow = "▲" if pct > 0 else "▼"
    return (arrow, f"{abs(pct):.0f}%")
