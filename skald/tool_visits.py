"""Tools in a browser's clothes: two first-pass rules that need no network data.

Found on a live Next.js site (21 to 24 Oct 2026; COUNTING-TRAPS.md trap 18).
Both passed the rendering test (rendering.py), because both drive a real
browser or fetch the page's assets, and both were counted as people.

**A probe sweep (rule 6c, SWEEP).** One address with a Chrome agent asked
for /index.php, /info.php, /phpinfo.php, /login.php, /admin/, /wp-login.php,
/dashboard.php, /cart.php and more, twice over, on a site that runs none of
them: every one a 404. Each probe was filed under bots (rule 6), but these
are the probe families a real site may serve (scripts, WordPress, admin
panels: classify._SERVED), which move only their own request, so the "/"
it fetched between them were people's pages, a visit and a landing.

A reader may ask for one of those paths, and on a site that serves them
gets an answer. A reader never asks for five different ones that the site
does not have. So an address and agent that asked the site's hosts for at
least SWEEP_PATHS (5) different probe paths (classify.PROBE on the path)
that the site answered with a 4xx or 5xx, in the window, is a scanner on
every request of the window, as rule 6b does for one secret file. Left out
of the count, so that a reader's browser never adds to it:

  * paths under site.legacy_paths (the site's old URLs, trap 8),
  * assets by extension (classify's PROBE matches /wp-content/...png too:
    a page that still embeds an old site's images makes the browser ask),
  * redirects (3xx): a WordPress admin at work gets 302s from wp-admin.

**A link checker (rule 8b, LINK_CHECKER).** The same site's own office ran a
checker with a Chrome agent: in one visit it opened a page with GET, loaded
its assets, then sent HEAD for every link on it, 560 page views in 17
minutes, all counted as one person. A browser opens a page with GET; it
never sends HEAD for a page on its own. So a browser-like visit (address and
agent, no gap over the session gap, on the site's hosts: the visit
rendering.py judges) that sent HEAD for at least HEAD_PAGES (2) different
documents (no asset, payload or beacon) is a tool, and every request of
that visit is bots. Two, not one: a page's own script may check one URL
with HEAD.

Neither rule reads the time a visit lasted, its page count, the hosting
networks or reverse DNS: they work the same with or without bots.ranges_dir.
A visit counts whole, so the groups still add up to the log.

audit_tools.py counts the same things by a separate road.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .classify import (BROWSER, LINK_CHECKER, OTHER_BOT, PROBE,  # noqa: F401 - re-exported
                       SWEEP)
from .parse import ASSET, BEACON, RSC_PAYLOAD

SWEEP_PATHS = 5
HEAD_PAGES = 2


def _aware(when: datetime) -> datetime:
    return when if when.tzinfo else when.replace(tzinfo=timezone.utc)


def _unserved(status: str) -> bool:
    return status[:1] in ("4", "5")


class ProbeSweep:
    """The first pass of rule 6c: fed every hit of the window, it keeps the
    (address, agent) pairs that asked for SWEEP_PATHS different probe paths
    the site did not have."""

    def __init__(self, hosts: list[str] | None, legacy: tuple = (),
                 least: int = SWEEP_PATHS) -> None:
        self.wanted = {h.lower() for h in (hosts or [])}
        self.legacy = tuple(legacy or ())
        self.least = least
        self.paths: dict[tuple[str, str], set] = {}
        self.pairs: set[tuple[str, str]] = set()

    def __call__(self, hit) -> None:
        key = (hit.address, hit.user_agent)
        if key in self.pairs or not _unserved(hit.status):
            return
        host = hit.host.lower()
        if self.wanted and host and host not in self.wanted:
            return
        path = hit.path
        if ASSET.search(path) or not PROBE.search(path):
            return
        if self.legacy and any(path.startswith(p) for p in self.legacy):
            return
        seen = self.paths.setdefault(key, set())
        seen.add(path)
        if len(seen) >= self.least:
            self.pairs.add(key)
            del self.paths[key]


class HeadChecks:
    """The first pass of rule 8b: fed every hit of the window, then asked
    which browser-like visits sent HEAD for HEAD_PAGES different documents."""

    def __init__(self, hosts: list[str] | None, gap_minutes: int = 30,
                 least: int = HEAD_PAGES) -> None:
        self.wanted = {h.lower() for h in (hosts or [])}
        self.gap = timedelta(minutes=gap_minutes)
        self.least = least
        # (address, agent) -> [(when, path of a HEAD document or None)]
        self.seen: dict[tuple[str, str], list] = {}
        self.heads: set[tuple[str, str]] = set()
        self._browser: dict[str, bool] = {}

    def _browser_like(self, agent: str) -> bool:
        got = self._browser.get(agent)
        if got is None:
            got = bool(agent) and bool(BROWSER.search(agent)) and not OTHER_BOT.search(agent)
            if len(self._browser) < 50_000:
                self._browser[agent] = got
        return got

    def __call__(self, hit) -> None:
        host = hit.host.lower()
        if self.wanted and host and host not in self.wanted:
            return
        if not self._browser_like(hit.user_agent):
            return
        key = (hit.address, hit.user_agent)
        head = (hit.method == "HEAD" and not RSC_PAYLOAD.search(hit.url)
                and not ASSET.search(hit.path) and not BEACON.search(hit.path))
        if head:
            self.heads.add(key)
        self.seen.setdefault(key, []).append((_aware(hit.when), hit.path if head else None))

    def spans(self) -> dict[tuple[str, str], list]:
        """{(address, agent): [(first, last), ...]}: the link-checker visits,
        from their first request to their last. Also sets `counts`."""
        out: dict[tuple[str, str], list] = {}
        visits = 0
        for key in self.heads:
            events = sorted(self.seen[key], key=lambda e: e[0])
            current: list = []
            for event in events + [None]:
                if current and (event is None or event[0] - current[-1][0] > self.gap):
                    if len({p for _, p in current if p is not None}) >= self.least:
                        visits += 1
                        out.setdefault(key, []).append((current[0][0], current[-1][0]))
                    current = []
                if event is not None:
                    current.append(event)
        self.counts = {"visits": visits}
        return out
