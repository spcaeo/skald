"""Did a browser render the page? The test a visit must pass to count as a person.

A user agent is a claim, and every scraper copies a browser's. What a scraper
does not do is render: a real browser that opens a page goes on to fetch the
page's own scripts and styles, a fraction of a second later. On the audited
day (2026-10-10, on the first live install) 717 browser-like visitors fetched
a page and 13 of them loaded a single script or stylesheet; the other 704 took
the HTML and left - 99% desktop, 95% one page, median visit 0 seconds. Counting them made
"visitors" about forty times too high (COUNTING-TRAPS.md, trap 13).

So a browser-like visit (one address and user agent, no gap longer than the
session gap, on the site's own hosts) counts as people only with evidence
that a browser drew the page. Any one of these is enough:

  * assets   it fetched one of the site's page assets (`site.asset_prefixes`,
             default /_next/static/) or a framework payload (?_rsc=, which only
             the page's running script asks for) within `site.render_seconds`
             (default 30) after one of its pages - or up to EARLY_SECONDS
             before it, because a streamed page is logged when it ends, after
             the browser already asked for its styles. Images, /og/ cards and
             favicons do not count: a link unfurler fetches those too.
  * beacon   an event from the page's own script (the beacon spool) was sent
             from one of its pages: same path, opened within the same window. A
             page opening that is no event (page_view without beacon-only mode or
             visitor IDs) counts too, from the day's opens file (since 2.10.1).
  * earlier  the same address and agent rendered a page earlier the same day:
             a returning browser has the assets in its cache and asks for none.
  * returning  its 30-day keyed hash (visitors.py) was a counted reader on an
             earlier day, for the same reason a day later.

A Next.js navigation (parse.Hit.soft_navigation: ?_rsc= on a line that
records the prefetch header, sent without it) is a page of the visit and,
being a payload, its own evidence: only the page's running script asks for
one. A visit whose only pages are such navigations (a tab left open, a page
restored from the cache) counts as people on that alone.

A visit counts whole or not at all: once any of its pages rendered, every
request of the visit is people's. Every request of a visit that did not
render moves to bots, as NOT_RENDERED, so the groups still add up to the log.

The visit judged here is split on the gap alone, never on the source: the
question is whether this browser drew, and a person who comes back from an
assistant two minutes later has the assets cached and asks for none. The
people's visits (aggregate._Sessions) then split by source inside it, on
both roads alike; audit_rendered.py judges the same gap-only spans.

A page Chrome's prefetch proxy fetched (SKALD-41): Google Search on Android
Chrome fetches a result's HTML through Chrome's private prefetch proxy, from
Google's network, and the browser then fetches the page's files from its own
address. Joined on one address, neither half would render. So a page line
from a proxy address (Google's published list, bot_verify.PREFETCH_PROXY) is
the browser's when the same agent fetched an own asset or payload from
another, non-proxy address within the same window (EARLY_SECONDS before to
render_seconds after) whose referrer is that page (same host, same path),
and that browser did not fetch that page itself in the same window around
the fetch (then the files are its own page's); the nearest such fetch wins. `rejoined` then gives the page line that
browser's address and country, in every pass that counts: one visit, the
person's own. A proxy page nobody opened joins nothing and stays a bot.

What it cannot know: a person whose browser blocks scripts and styles, or
who reads through a text-only browser, is left out with the scrapers. The
beacon shows how rare that is (README, "What this cannot know").

audit_rendered.py counts the same thing by a separate road.
"""
from __future__ import annotations

import bisect
import dataclasses
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

from .classify import BROWSER, NOT_RENDERED, OTHER_BOT  # noqa: F401 - NOT_RENDERED re-exported
from .config import setting
from .parse import ASSET, BEACON, RSC_PAYLOAD

ASSET_PREFIXES = ("/_next/static/",)
RENDER_SECONDS = 30
# A page is logged when its response ends. A streamed page's styles are asked
# for before that, so an asset may be logged a few seconds before its page.
EARLY_SECONDS = 5


def required(config: dict) -> bool:
    """`site.require_rendering`, on unless set to false. Off is for a site
    whose assets are served from somewhere this log never sees (a CDN on
    another host): then nothing could ever render, and nobody would count."""
    return setting(config, "site", "require_rendering", True) is not False


def asset_prefixes(config: dict) -> tuple[str, ...]:
    raw = setting(config, "site", "asset_prefixes", None)
    if raw is None:
        return ASSET_PREFIXES
    if isinstance(raw, str):
        raw = raw.split()
    return tuple(str(p) for p in raw if str(p).startswith("/"))


def render_seconds(config: dict) -> int:
    return int(setting(config, "site", "render_seconds", RENDER_SECONDS))


def _aware(when: datetime) -> datetime:
    return when if when.tzinfo else when.replace(tzinfo=timezone.utc)


class Rendering:
    """The first pass: fed every hit of the window, then asked which
    browser-like visits never rendered.

    `opens` is the beacon's page openings, [(path, when opened)], and
    `returning(address, agent)` says whether that visitor was a counted
    reader on an earlier day; both may be empty. `proxy(address)` says
    whether an address is Chrome's prefetch proxy (None: no list).
    """

    def __init__(self, hosts: list[str] | None, gap_minutes: int = 30,
                 prefixes: tuple[str, ...] = ASSET_PREFIXES,
                 seconds: int = RENDER_SECONDS, opens=(), returning=None,
                 proxy=None) -> None:
        self.wanted = {h.lower() for h in (hosts or [])}
        self.gap = timedelta(minutes=gap_minutes)
        self.prefixes = tuple(prefixes)
        self.after = timedelta(seconds=seconds)
        self.before = timedelta(seconds=EARLY_SECONDS)
        self.opens = sorted((_aware(at), path) for path, at in opens)
        self.returning = returning
        self.proxy = proxy
        # (address, agent) -> [(when, path or None, renders, referrer,
        # country)]: a document carries its path, an asset or payload carries
        # renders=True. The last two are the hit's own strings, for the
        # prefetch-proxy join.
        self.seen: dict[tuple[str, str], list] = {}
        # (proxy address, agent) -> {(when, path): (address, country)}: the
        # proxy's pages each browser drew (unrendered() fills it).
        self.joined: dict[tuple[str, str], dict] = {}
        self._browser: dict[str, bool] = {}

    def _browser_like(self, agent: str) -> bool:
        got = self._browser.get(agent)
        if got is None:
            got = bool(agent) and bool(BROWSER.search(agent)) and not OTHER_BOT.search(agent)
            if len(self._browser) < 50_000:
                self._browser[agent] = got
        return got

    def renders(self, hit) -> bool:
        """A request only a browser drawing the page makes."""
        return hit.path.startswith(self.prefixes) or bool(RSC_PAYLOAD.search(hit.url))

    @staticmethod
    def document(hit) -> bool:
        """A request for the page itself, whatever its answer (a 404 page
        renders too): a GET or HEAD that is no asset, payload or beacon."""
        return (hit.method in ("GET", "HEAD") and not RSC_PAYLOAD.search(hit.url)
                and not ASSET.search(hit.path) and not BEACON.search(hit.path))

    def __call__(self, hit) -> None:
        host = hit.host.lower()
        if self.wanted and host and host not in self.wanted:
            return
        if not self._browser_like(hit.user_agent):
            return
        when = _aware(hit.when)
        if self.renders(hit):
            # A Next.js navigation (parse.Hit.soft_navigation) is a page of
            # its own, and the payload it is shows the page's script drew it.
            item = (when, hit.path if hit.soft_navigation else None, True,
                    hit.referrer, hit.country)
        elif self.document(hit):
            item = (when, hit.path, False, None, None)
        else:
            item = (when, None, False, None, None)
        self.seen.setdefault((hit.address, hit.user_agent), []).append(item)

    # ------------------------------------------------------------ verdicts

    def _visits(self, events: list) -> list[list]:
        events.sort(key=lambda e: e[0])
        visits, current = [], []
        for event in events:
            if current and event[0] - current[-1][0] > self.gap:
                visits.append(current)
                current = []
            current.append(event)
        if current:
            visits.append(current)
        return visits

    def _drawn(self, visit: list) -> bool:
        renders = [e[0] for e in visit if e[2]]
        if not renders:
            return False
        for when, path, *_ in visit:
            if path is None:
                continue
            k = bisect.bisect_left(renders, when - self.before)
            if k < len(renders) and renders[k] <= when + self.after:
                return True
        return False

    def unrendered(self) -> dict[tuple[str, str], list]:
        """{(address, agent): [(first, last), ...]}: the visits that count
        as bots. Also sets `counts`: visits by the evidence that let them in."""
        visits = {key: self._visits(events) for key, events in self.seen.items()}
        drawn = {(key, i) for key, vs in visits.items() for i, v in enumerate(vs)
                 if self._drawn(v)}
        self.joined = self._join_proxy(visits, drawn)
        signed = self._beacon(visits, drawn)
        out: dict[tuple[str, str], list] = {}
        counts = {"assets": 0, "beacon": 0, "earlier": 0, "returning": 0, "not_rendered": 0,
                  "proxy_pages": sum(len(v) for v in self.joined.values())}
        for key, vs in visits.items():
            before = False
            back = None
            for i, visit in enumerate(vs):
                if (key, i) in drawn:
                    why = "assets"
                elif (key, i) in signed:
                    why = "beacon"
                elif before:
                    why = "earlier"
                else:
                    if back is None:
                        back = bool(self.returning and self.returning(*key))
                    why = "returning" if back else ""
                if why:
                    counts[why] += 1
                    before = before or why in ("assets", "beacon")
                    continue
                counts["not_rendered"] += 1
                out.setdefault(key, []).append((visit[0][0], visit[-1][0]))
        self.counts = counts
        return out

    def _beacon(self, visits: dict, drawn: set) -> set:
        """The visits a beacon page-opening vouches for. Each opening vouches
        for one visit at most: none when a visit that rendered already has
        that page at that time, else the nearest one in time (then the
        earliest, then the lowest address and agent)."""
        if not self.opens:
            return set()
        pages: dict[str, list] = {}
        for key, vs in visits.items():
            for i, visit in enumerate(vs):
                for when, path, *_ in visit:
                    if path is not None:
                        pages.setdefault(path, []).append((when, key, i))
        signed: set = set()
        for opened, path in self.opens:
            near = [(abs((when - opened).total_seconds()), when, key, i)
                    for when, key, i in pages.get(path, ())
                    if opened - self.before <= when <= opened + self.after]
            if not near or any((key, i) in drawn or (key, i) in signed
                               for _, _, key, i in near):
                continue
            near.sort()
            signed.add((near[0][2], near[0][3]))
        return signed

    def _from_page(self, referrer: str, path: str) -> bool:
        """The referrer is this page of the site: same path, a wanted host."""
        try:
            got = urlsplit(referrer)
        except ValueError:
            return False
        host = (got.hostname or "").lower()
        if not host or (self.wanted and host not in self.wanted):
            return False
        return (got.path or "/") == path

    def _join_proxy(self, visits: dict, drawn: set) -> dict:
        """The prefetch proxy's pages each browser drew (module docstring):
        {(proxy address, agent): {(when, path): (address, country)}}. The
        browser's visit that drew one is added to `drawn`: the page is its."""
        if self.proxy is None:
            return {}
        proxied = {key for key in visits if self.proxy(key[0])}
        if not proxied:
            return {}
        agents = {agent for _, agent in proxied}
        # agent -> [(when, address, visit index, referrer, country)] of the
        # draws from other addresses, in time order.
        draws: dict[str, list] = {}
        for key, vs in visits.items():
            if key[1] not in agents or key in proxied:
                continue
            for i, visit in enumerate(vs):
                for when, _, renders, referrer, country in visit:
                    if renders and referrer:
                        draws.setdefault(key[1], []).append((when, key[0], i, referrer, country))
        for got in draws.values():
            got.sort(key=lambda d: (d[0], d[1]))
        own: dict = {}          # (address, agent, visit) -> {path: [its page times]}

        def fetched_itself(address: str, agent: str, i: int, path: str, at) -> bool:
            pages = own.get((address, agent, i))
            if pages is None:
                pages = own[(address, agent, i)] = {}
                for when, p, renders, *_ in visits[(address, agent)][i]:
                    if p is not None and not renders:
                        pages.setdefault(p, []).append(when)
            return any(t - self.before <= at <= t + self.after for t in pages.get(path, ()))

        joined: dict = {}
        for key in sorted(proxied):
            got = draws.get(key[1])
            if not got:
                continue
            times = [d[0] for d in got]
            for visit in visits[key]:
                for when, path, renders, *_ in visit:
                    if path is None or renders:
                        continue
                    k = bisect.bisect_left(times, when - self.before)
                    near = [(abs((d[0] - when).total_seconds()), d[1], d[0], d)
                            for d in got[k:bisect.bisect_right(times, when + self.after)]
                            if self._from_page(d[3], path)
                            and not fetched_itself(d[1], key[1], d[2], path, d[0])]
                    if not near:
                        continue
                    _, address, _, (_, _, i, _, country) = min(near)
                    joined.setdefault(key, {})[(when, path)] = (address, country)
                    drawn.add(((address, key[1]), i))
        return joined


def rejoined(hit, joined: dict | None):
    """The hit as counted: a prefetch-proxy page a browser drew (SKALD-41)
    becomes that browser's, with its address and country. Any other hit
    is itself."""
    if not joined:
        return hit
    got = joined.get((hit.address, hit.user_agent))
    if not got:
        return hit
    to = got.get((_aware(hit.when), hit.path))
    if to is None:
        return hit
    return dataclasses.replace(hit, address=to[0], country=to[1] or hit.country)


# ----------------------------------------------------------------- inputs

def resolved(config: dict, name: str):
    """A path the command line resolved against the config's folder
    (cli.Context), or None when the config was not loaded that way."""
    got = ((config or {}).get("_resolved") or {}).get(name)
    return got or None


def beacon_opens(config: dict, start: datetime, end: datetime) -> list[tuple[str, datetime]]:
    """[(path, when the page was opened)] from the beacon spool's people
    events in [start, end): `at` less `t` seconds. One per page opening,
    however many events it sent."""
    if not setting(config, "beacon", "enabled", False):
        return []
    from . import beacon
    from .window import zone
    tz = zone(config)
    spool = resolved(config, "beacon_spool") or beacon.spool_dir(config)
    out: set = set()
    day = start.astimezone(tz).date() - timedelta(days=1)
    while day <= end.astimezone(tz).date():
        # The day's events, then its openings that are no event (2.10.1).
        rows = list(beacon.read_day(spool, day)) + list(_opens(beacon.opens_file(spool, day)))
        for row in rows:
            if row.get("g") != "people":
                continue
            try:
                at = datetime.fromisoformat(str(row.get("at")))
                opened = _aware(at) - timedelta(seconds=int(row.get("t") or 0))
            except (TypeError, ValueError):
                continue
            if start <= opened < end:
                out.add((row["p"], opened))
        day += timedelta(days=1)
    return sorted(out, key=lambda o: (o[1], o[0]))


def _opens(path) -> list[dict]:
    import json
    from pathlib import Path
    if not Path(path).is_file():
        return []
    out = []
    for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict) and isinstance(row.get("e"), str) \
                and isinstance(row.get("p"), str):
            out.append(row)
    return out


def earlier_readers(config: dict, first_day, key: bytes | None):
    """returning(address, agent): was this visitor's keyed hash a counted
    reader on one of the days before `first_day` in the returning-visitor
    window (visitors.repeat_days - 1: 29 by default)? None without a key or
    a history file to read."""
    if key is None:
        return None
    from pathlib import Path
    import sqlite3
    from .config import site_name
    from .visitors import reader_family, repeat_days, visitor_hash
    db = Path(resolved(config, "history_db") or str(setting(config, "history", "db", "") or "")
              ).expanduser()
    if not db.name or not db.is_file():
        return None
    try:
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        try:
            rows = conn.execute(
                "SELECT DISTINCT visitor FROM visitor_days WHERE site = ? AND kind = 'reader' "
                "AND day >= ? AND day < ?",
                (site_name(config), (first_day - timedelta(days=repeat_days(config) - 1)).isoformat(),
                 first_day.isoformat())).fetchall()
        finally:
            conn.close()
    except sqlite3.Error:
        return None
    known = {v for (v,) in rows}
    if not known:
        return None
    return lambda address, agent: visitor_hash(key, address, reader_family(agent)) in known
