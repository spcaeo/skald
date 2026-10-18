"""Too fast to be a person: a browser-like visit that read pages faster than anyone can.

Found on the live site (14 Oct 2026): a visit counted as a person read 17
pages, every one of them at second 0 of the visit. It had passed the
rendering test (rendering.py), so it was a visitor. Nobody chooses a link,
waits for the page and chooses the next one 17 times in a second.

How fast is a person? A click is a choice: the eye has to find the link, the
hand has to move, and the page has to arrive before the next choice can be
made. Even a hurried reader clicking through a menu without reading spends
about a second per page: a fast clicker reads 3 pages in 2 seconds, and
stays a person. A browser can be fast without a person -
restoring several tabs of the same site at once - and that is the price of
the rule (CLASSIFICATION.md, "What this cannot know").

So the rule is narrow: a browser-like visit (address and user agent, no gap
longer than the session gap, on the site's own hosts - the visit
rendering.py judges) with at least `site.too_fast_pages` page views (6)
whose page views all fall within `site.too_fast_seconds` (2) of its first
one is not a person. The log stamps whole seconds, so "within 2 seconds"
is 6 pages in under 3 real seconds: two pages a second, sustained, with
nothing slower in the visit. `site.too_fast_pages: 0` turns it off.

A page view is parse.Hit.is_page: a 2xx or 304 GET or HEAD for a document.
Redirects are not pages, so a trailing-slash redirect never makes a fast
reader look faster.

A visit counts whole or not at all, as with rendering: every request of a
too-fast visit moves to bots, as TOO_FAST, so the groups still add up to
the log. A visit that never rendered is NOT_RENDERED first (rule 9); this
is rule 9b.

audit_too_fast.py counts the same thing by a separate road.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .classify import BROWSER, OTHER_BOT, TOO_FAST  # noqa: F401 - TOO_FAST re-exported
from .config import setting

PAGES = 6
SECONDS = 2


def limits(config: dict) -> tuple[int, int]:
    """(pages, seconds): `site.too_fast_pages` (0: off), `site.too_fast_seconds`."""
    try:
        pages = int(setting(config, "site", "too_fast_pages", PAGES))
        seconds = int(setting(config, "site", "too_fast_seconds", SECONDS))
    except (TypeError, ValueError):
        return PAGES, SECONDS
    return max(0, pages), max(0, seconds)


def _aware(when: datetime) -> datetime:
    return when if when.tzinfo else when.replace(tzinfo=timezone.utc)


class TooFast:
    """The first pass: fed every hit of the window, then asked which
    browser-like visits read pages too fast for a person."""

    def __init__(self, hosts: list[str] | None, gap_minutes: int = 30,
                 pages: int = PAGES, seconds: int = SECONDS) -> None:
        self.wanted = {h.lower() for h in (hosts or [])}
        self.gap = timedelta(minutes=gap_minutes)
        self.pages = pages
        self.within = timedelta(seconds=seconds)
        # (address, agent) -> [(when, is a page view)]
        self.seen: dict[tuple[str, str], list] = {}
        self._browser: dict[str, bool] = {}

    def _browser_like(self, agent: str) -> bool:
        got = self._browser.get(agent)
        if got is None:
            got = bool(agent) and bool(BROWSER.search(agent)) and not OTHER_BOT.search(agent)
            if len(self._browser) < 50_000:
                self._browser[agent] = got
        return got

    def __call__(self, hit) -> None:
        if self.pages <= 0:
            return
        host = hit.host.lower()
        if self.wanted and host and host not in self.wanted:
            return
        if not self._browser_like(hit.user_agent):
            return
        self.seen.setdefault((hit.address, hit.user_agent), []).append(
            (_aware(hit.when), hit.is_page))

    def _fast(self, visit: list) -> bool:
        pages = [when for when, page in visit if page]
        return len(pages) >= self.pages and pages[-1] - pages[0] <= self.within

    def spans(self) -> dict[tuple[str, str], list]:
        """{(address, agent): [(first, last), ...]}: the too-fast visits,
        from their first request to their last. Also sets `counts`."""
        out: dict[tuple[str, str], list] = {}
        visits = 0
        for key, events in self.seen.items():
            events.sort(key=lambda e: e[0])
            current: list = []
            for event in events + [None]:
                if current and (event is None or event[0] - current[-1][0] > self.gap):
                    if self._fast(current):
                        visits += 1
                        out.setdefault(key, []).append((current[0][0], current[-1][0]))
                    current = []
                if event is not None:
                    current.append(event)
        self.counts = {"visits": visits}
        return out
