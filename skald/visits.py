"""Visits: an anonymous journey for every reader's visit, and its metrics.

A visit here is exactly the session aggregate.Tally already counts for real
people - one visitor key, no gap longer than report.session_gap_minutes,
and no page arriving from a new outside source (dimensions.new_source) -
and a visit that read at least one page is a reader. So visits equal
readers, and verify checks that they do.

The visitor key is the address and the user agent, hashed in memory with a
random salt made for this run and never written anywhere. The journey
itself carries neither the address, the user agent nor the hash (since
2.4.0 `Journeys.people`, aligned with the journeys, hands each visit's
address, user agent, referrer and POST times to people/visits.py, which
keeps them apart, and only while the site keeps addresses): a
journey is when it started (to the minute, in the report's time zone), the
country, device, browser and system labels, where it came from, the pages
in order (each with `at`, the seconds since the visit started, bucketed
like durations), how many, how long and where it ended.

What a journey can and cannot see:

  * A page is a page view (parse.Hit.is_page): an HTML document the browser
    loaded. Those are what "pages" counts, and they add up to the pages read
    by people.
  * A site that navigates in the browser (a Next.js or React app) often
    fetches nothing for a click: the page came with the first one. The
    referrer of the next request still names the page the visitor was on,
    so a same-site referrer that is not the page last seen is recorded as
    an "in-app" page - shown in the journey, never counted as a page view.
    It is a floor: a visitor who moves and loads nothing new leaves no line.
  * The duration is from the visit's first request to its last. A visitor
    who reads one page for ten minutes and loads nothing else has a visit
    of a few seconds. Logs cannot see time spent reading.
"""
from __future__ import annotations

import hashlib
import os
from collections import Counter
from dataclasses import dataclass, field
from datetime import timedelta, timezone
from urllib.parse import urlsplit

from . import dimensions as dim
from .classify import Group, Tier
from .countries import UNKNOWN, label as country_label
from .parse import ASSET, BEACON

ARROW = " → "
TRAIL_KEEP = 50          # trail entries kept per journey; counts are of all
FLAGS = ("not_found", "posted", "in_app")
FLAG_WORDS = {"not_found": "met a page not found (404)",
              "posted": "sent a form or other POST",
              "in_app": "moved inside the site without loading a page"}

# An assistant by the name a reader knows it by.
ASSISTANTS = {
    "chatgpt.com": "ChatGPT", "perplexity.ai": "Perplexity", "claude.ai": "Claude",
    "gemini.google.com": "Gemini", "copilot.microsoft.com": "Copilot",
    "you.com": "You.com", "phind.com": "Phind", "poe.com": "Poe", "mistral.ai": "Mistral",
    "meta.ai": "Meta AI",
}


def assistant_label(name: str) -> str:
    return ASSISTANTS.get(name, name)


def seconds_bucket(seconds: int) -> int:
    """A duration, kept to the second under a minute, then to 10 s under
    ten minutes, to the minute under an hour, and to 10 minutes after. The
    median over any period is read from these, so it is that precise."""
    s = max(0, int(seconds))
    if s < 60:
        return s
    if s < 600:
        return s - s % 10
    if s < 3600:
        return s - s % 60
    return s - s % 600


def duration_words(seconds: int | None) -> str:
    """'40s', '1m 40s', '1h 5m'."""
    if seconds is None:
        return "-"
    s = int(seconds)
    if s < 60:
        return f"{s}s"
    if s < 3600:
        return f"{s // 60}m {s % 60:02d}s" if s % 60 else f"{s // 60}m"
    return f"{s // 3600}h {s % 3600 // 60}m"


def _same_site_path(referrer: str, own: set[str]) -> str:
    """The path of a referrer on this site's own hosts, if it names a page
    (not a stylesheet or a script) - else ""."""
    if not referrer:
        return ""
    try:
        parts = urlsplit(referrer)
    except ValueError:
        return ""
    host = (parts.hostname or "").lower()
    if not host or host not in own:
        return ""
    path = parts.path or "/"
    if ASSET.search(path) or BEACON.search(path):
        return ""
    return path[:70]


def _via(hit, source: str, cited: bool, engine: str) -> str:
    """Who sent the visitor: the assistant, the referring site, or the
    campaign's source when a tagged link came without a referrer."""
    if cited:
        return assistant_label(engine)
    if source in ("Direct or unknown", "This site"):
        return ""
    host = dim.referrer_host(hit.referrer)
    if host:
        return host[:60]
    return (dim.query(hit.url).get("utm_source") or "").strip().lower()[:30]


class _Visit:
    __slots__ = ("first", "last", "prev", "trail", "times", "pages", "labels",
                 "not_found", "posted", "visitor", "origin", "who")

    def __init__(self, when) -> None:
        self.first = self.last = self.prev = when
        self.trail: list[tuple[str, bool]] = []     # (path, loaded as a page)
        self.times: list = []                       # when each trail entry was seen
        self.visitor = None                         # keyed hash (visitors.py), memory only
        self.pages = 0
        self.labels: dict = {}
        self.not_found = 0
        self.posted = 0
        self.origin = None                          # its first page's (dimensions.page_origin)
        # Its address, user agent, first page's referrer and the times of its
        # POSTs: memory only, handed to people/visits.py (Journeys.people),
        # never put on the anonymous journey.
        self.who = None


@dataclass
class VisitStats:
    """Visit metrics: each histogram adds up to `visits`.

    pages    visits by how many pages they loaded ("1": one-page visits)
    trail    visits by how many pages they were seen on, in-app ones included
    seconds  visits by duration (seconds_bucket)
    exits    visits by the last page they were seen on
    steps    each move from one page to the next ("/a → /b"); they add up
             to the pages seen minus the visits
    flags    visits that met a 404, sent a POST, or moved in-app (FLAGS)

    entries, source, country and device are the same visits by their first
    page; they equal the readers breakdowns, so history does not store
    them twice - a period reads them back from the readers tables.
    """

    visits: int = 0
    pages: Counter = field(default_factory=Counter)
    trail: Counter = field(default_factory=Counter)
    seconds: Counter = field(default_factory=Counter)
    exits: Counter = field(default_factory=Counter)
    steps: Counter = field(default_factory=Counter)
    flags: Counter = field(default_factory=Counter)
    entries: Counter = field(default_factory=Counter)
    source: Counter = field(default_factory=Counter)
    country: Counter = field(default_factory=Counter)
    device: Counter = field(default_factory=Counter)

    STORED = ("pages", "trail", "seconds", "exits", "steps", "flags")
    DERIVED = ("entries", "source", "country", "device")

    def views(self) -> int:
        return sum(int(k) * n for k, n in self.pages.items())

    def seen(self) -> int:
        return sum(int(k) * n for k, n in self.trail.items())

    def one_page(self) -> int:
        return int(self.pages.get("1", 0))

    def per_visit(self) -> float | None:
        return self.views() / self.visits if self.visits else None

    def median_seconds(self) -> int | None:
        if not self.visits:
            return None
        ordered = sorted((int(k), n) for k, n in self.seconds.items() if n)
        middle = (self.visits - 1) // 2
        for value, n in ordered:
            if middle < n:
                return value
            middle -= n
        return None

    def as_dict(self) -> dict:
        out = {"visits": self.visits}
        for name in self.STORED + self.DERIVED:
            out[name] = dict(getattr(self, name))
        return out

    @classmethod
    def from_dict(cls, d: dict | None) -> "VisitStats | None":
        if not isinstance(d, dict):
            return None
        stats = cls(visits=int(d.get("visits", 0)))
        for name in cls.STORED + cls.DERIVED:
            setattr(stats, name, Counter({str(k): int(v) for k, v in
                                          (d.get(name) or {}).items()}))
        return stats


class Journeys:
    """Builds the visits of one group's hits, a hit at a time.

    The session rule is aggregate._Sessions' to the letter - a new visit
    when the key has not been seen or was last seen more than the gap away,
    or when a page arrives from an outside source other than the visit's
    own (dimensions.new_source), in the order the hits arrive - so its
    visits with a page are exactly the readers.
    """

    def __init__(self, gap_minutes: int = 30, tz=None,
                 own_hosts: set[str] | None = None, key: bytes | None = None) -> None:
        self.gap = timedelta(minutes=gap_minutes)
        # The visitor key (visitors.load_key): with it, each visit carries a
        # keyed hash for returning-visitor counts, kept apart from the journey.
        self.key = key
        self.visitor_keys: list[str] | None = None
        self.firsts: list | None = None
        self.people: list | None = None
        self.pages: dict[str, dict] = {}
        self.tz = tz
        self.own_hosts = own_hosts or set()
        # Made here, held only in memory, gone when the run ends.
        self._salt = os.urandom(16)
        self.open: dict[bytes, _Visit] = {}
        self.done: list[_Visit] = []
        # The city fill (conversions/geo.Cities), set by the tally when a
        # city file is set: a journey then carries its first page's city.
        self.cities = None

    def _key(self, hit) -> bytes:
        raw = f"{hit.address}\0{hit.user_agent}".encode("utf-8", "replace")
        return hashlib.blake2b(raw, key=self._salt, digest_size=16).digest()

    def add(self, hit, verdict) -> None:
        key = self._key(hit)
        visit = self.open.get(key)
        own = self.own_hosts or ({hit.host.lower()} if hit.host else set())
        origin = (dim.page_origin(hit.referrer, hit.url, verdict.tier is Tier.CITED, own)
                  if hit.is_page else None)
        if (visit is None or abs(hit.when - visit.prev) > self.gap
                or dim.new_source(origin, visit.origin)):
            if visit is not None:
                self._close(visit)
            visit = self.open[key] = _Visit(hit.when)
        if visit.origin is None:
            visit.origin = origin
        visit.prev = hit.when
        visit.first = min(visit.first, hit.when)
        visit.last = max(visit.last, hit.when)
        if hit.status == "404" and not ASSET.search(hit.path):
            visit.not_found += 1
        if visit.who is None:
            visit.who = {"ip": hit.address, "user_agent": hit.user_agent, "referrer": "",
                         "posts": []}
        if hit.is_form_post:
            visit.posted += 1
            if len(visit.who["posts"]) < 20:
                visit.who["posts"].append(hit.when)
        path = hit.path[:70]
        if visit.trail and hit.status[:1] in ("2", "3"):
            # Where the visitor was when this was asked for. A cancelled
            # request (499) may be the page they just left, so it says nothing.
            moved = _same_site_path(hit.referrer, own)
            if moved and moved != visit.trail[-1][0] and not (hit.is_page and moved == path):
                visit.trail.append((moved, False))
                visit.times.append(hit.when)
        if hit.is_page:
            if not visit.pages:
                visit.labels = self._labels(hit, verdict, own)
                if self.key is not None:
                    from .visitors import reader_family, visitor_hash
                    visit.visitor = visitor_hash(self.key, hit.address,
                                                 reader_family(hit.user_agent))
            if not visit.pages:
                visit.who["referrer"] = (hit.referrer or "")[:300]
            visit.pages += 1
            visit.trail.append((path, True))
            visit.times.append(hit.when)

    def _labels(self, hit, verdict, own: set[str]) -> dict:
        """The visit by its first page - the same labels as the readers."""
        browser, system, device = dim.agent_labels(hit.user_agent)
        cited = verdict.tier is Tier.CITED
        source = dim.source_type(hit.referrer, hit.url, cited, own)
        campaign = dim.campaign(hit.url)
        from .campaigns import fields
        city = self.cities(hit.address, hit.country) if self.cities is not None else ""
        return {
            "country": hit.country.upper() if hit.country else UNKNOWN,
            # Only when known: a visit without one has no "city" at all.
            **({"city": city} if city else {}),
            "browser": browser, "os": system, "device": device,
            "source": source, "via": _via(hit, source, cited, verdict.engine),
            "campaign": "" if campaign == dim.NO_CAMPAIGN else campaign,
            **fields(hit.url, hit.referrer, source),
        }

    def _close(self, visit: _Visit) -> None:
        if visit.pages:
            self.done.append(visit)

    def finish(self, top: int) -> tuple[list[dict], VisitStats]:
        """(journeys oldest first, their metrics)."""
        for visit in self.open.values():
            self._close(visit)
        self.open = {}
        visits = sorted(self.done, key=lambda v: v.first)
        self.done = []
        stats = VisitStats(visits=len(visits))
        journeys = []
        self.visitor_keys = [v.visitor for v in visits] if self.key is not None else None
        # Who each visit was (address, user agent, referrer, POST times),
        # aligned with the journeys, in memory only (people/visits.py keeps
        # them when the site keeps addresses).
        self.people = [dict(v.who or {}, first=v.first, last=v.last) for v in visits]
        # Each visit's first request, aligned with the journeys, in memory
        # only (ai_likely.py compares it with the AI fetches before it).
        self.firsts = [v.first for v in visits]
        self.pages = _page_figures(visits)
        for v in visits:
            trail = [p for p, _ in v.trail]
            seconds = int((v.last - v.first).total_seconds())
            in_app = sum(1 for _, loaded in v.trail if not loaded)
            stats.pages[str(v.pages)] += 1
            stats.trail[str(len(trail))] += 1
            stats.seconds[str(seconds_bucket(seconds))] += 1
            stats.exits[trail[-1]] += 1
            for a, b in zip(trail, trail[1:]):
                stats.steps[a + ARROW + b] += 1
            for flag, n in (("not_found", v.not_found), ("posted", v.posted),
                            ("in_app", in_app)):
                if n:
                    stats.flags[flag] += 1
            landing = next(p for p, loaded in v.trail if loaded)
            stats.entries[landing] += 1
            for name in ("source", "country", "device"):
                getattr(stats, name)[v.labels[name]] += 1
            start = v.first if v.first.tzinfo else v.first.replace(tzinfo=timezone.utc)
            if self.tz is not None:
                start = start.astimezone(self.tz)
            journeys.append({
                "start": start.strftime("%Y-%m-%dT%H:%M"),
                **v.labels,
                "landing": landing, "exit": trail[-1],
                "pages": v.pages, "seen": len(trail), "in_app": in_app,
                "trail": [[p, "page" if loaded else "app"]
                          for p, loaded in v.trail[:TRAIL_KEEP]],
                # When each trail entry was seen: seconds since the visit's
                # first request, bucketed like durations (funnel_days.py).
                "at": [seconds_bucket(int((t - v.first).total_seconds()))
                       for t in v.times[:TRAIL_KEEP]],
                "seconds": seconds,"not_found": v.not_found, "posted": v.posted,
            })
        stats.exits = dim.fold(stats.exits, top)
        stats.steps = dim.fold(stats.steps, top)
        wide = max(top, 25)          # as the readers breakdowns are folded
        stats.entries = dim.fold(stats.entries, wide)
        stats.country = dim.fold(stats.country, wide)
        return journeys, stats


def _page_figures(visits: list[_Visit]) -> dict[str, dict]:
    """Per page, from the visits: readers (visits that loaded it), visits
    (that were seen on it, in-app included), entries, exits, pages after
    landing, time on page (to the next page seen - an estimate; a visit's
    last page has none), and the sources, assistants and countries of the
    visits that read it."""
    out: dict[str, dict] = {}

    def page(path: str) -> dict:
        got = out.get(path)
        if got is None:
            got = out[path] = {"readers": 0, "visits": 0, "entries": 0, "exits": 0,
                               "after_pages": 0, "time": Counter(), "sources": Counter(),
                               "assistants": Counter(), "countries": Counter()}
        return got

    for v in visits:
        loaded = {p for p, ok in v.trail if ok}
        for p in loaded:
            row = page(p)
            row["readers"] += 1
            row["countries"][v.labels.get("country", UNKNOWN)] += 1
        for p in {p for p, _ in v.trail}:
            page(p)["visits"] += 1
        landing = next(p for p, ok in v.trail if ok)
        row = page(landing)
        row["entries"] += 1
        row["after_pages"] += v.pages - 1
        row["sources"][v.labels.get("source", "")] += 1
        if v.labels.get("source") == "AI assistant" and v.labels.get("via"):
            row["assistants"][v.labels["via"]] += 1
        page(v.trail[-1][0])["exits"] += 1
        for (p, _), a, b in zip(v.trail, v.times, v.times[1:]):
            page(p)["time"][str(seconds_bucket(int((b - a).total_seconds())))] += 1
    return out


# -------------------------------------------------------------- in words

SOURCE_WORDS = {
    "Search engine": "search", "Social media": "social", "Email": "email",
}


def came_from(j: dict) -> str:
    """'from ChatGPT', 'from google.com (search)', 'direct (no referrer, no tag)'."""
    source, via = j.get("source", ""), j.get("via", "")
    if source == "AI assistant":
        words = f"from {via or 'an AI assistant'}"
    elif source in SOURCE_WORDS:
        words = f"from {via} ({SOURCE_WORDS[source]})" if via else f"from {SOURCE_WORDS[source]}"
    elif source == "Other website":
        words = f"from {via}" if via else "from another website"
    elif source == "This site":
        words = "from this site, after a pause"
    elif source == "Tagged link":
        words = f"tagged link ({via})" if via else "tagged link"
    else:
        words = "direct (no referrer, no tag)"
    if j.get("campaign"):
        words += f", campaign {j['campaign']}"
    return words


def visitor(j: dict) -> str:
    """'🇨🇦 CAN · Mobile, Safari on iOS'."""
    return (f"{country_label(j.get('country', ''))} · {j.get('device', '')}, "
            f"{j.get('browser', '')} on {j.get('os', '')}")


def browser_steps(j: dict) -> int:
    """Steps of a journey seen only in the browser (no page loaded): its
    `in_app`, or the "app" entries of its trail for an older journey."""
    got = j.get("in_app")
    if isinstance(got, int):
        return max(0, got)
    return sum(1 for _, how in j.get("trail") or [] if how == "app")


def pages_words(j: dict) -> str:
    """'3 pages (2 seen in the browser)': the pages loaded from the server and
    the steps seen only in the browser, both stated; '2 pages' when none.
    `pages` keeps its meaning (page views, on both roads); this is words."""
    loaded = int(j.get("pages", 0) or 0)
    browser = browser_steps(j)
    seen = loaded + browser
    words = f"{seen:,} page{'s' if seen != 1 else ''}"
    return f"{words} ({browser:,} seen in the browser)" if browser else words


def sentence(j: dict) -> str:
    """One journey as plain words, as the CSV and the page say it."""
    trail = ARROW.join(p + (" (in-app)" if how == "app" else "")
                       for p, how in j.get("trail") or [])
    return (f"{str(j.get('start', ''))[11:16]} · {visitor(j)} · {came_from(j)} → "
            f"{trail} · {pages_words(j)} · "
            f"{duration_words(j.get('seconds'))}")


# ------------------------------------------------------------------ verify

def check(totals) -> list:
    """Visits add up: to the readers, to the pages read, and to themselves.

    Run by verify.check whenever the visits were counted. A day or a live
    snapshot where any of these fails is withheld like any other.
    """
    from .verify import Problem
    stats = getattr(totals, "visits", None)
    problems: list = []

    def differs(what: str, got: int, want: int, of: str) -> None:
        if got != want:
            problems.append(Problem(f"{what} does not sum",
                                    f"{got:,} against {want:,} {of} - off by {got - want:+,}"))

    labels = getattr(totals, "ours_labels", None)
    if labels is not None:
        ours = totals.groups.get(Group.OURS)
        differs("our own traffic by label", sum(labels.values()),
                ours.hits if ours else 0, "requests of our own")
    if stats is None:
        return problems
    people = totals.groups.get(Group.PEOPLE)
    views = people.views if people else 0
    if people is None or people.readers is not None:
        differs("visits", stats.visits, people.readers if people else 0, "readers")
    differs("pages loaded in visits", stats.views(), views, "page views by people")
    for name in ("pages", "trail", "seconds", "exits"):
        differs(f"visits by {name}", sum(getattr(stats, name).values()),
                stats.visits, "visits")
    differs("steps from page to page", sum(stats.steps.values()),
            stats.seen() - stats.visits, "pages seen beyond each visit's first")
    if stats.seen() < stats.views():
        problems.append(Problem("pages seen in visits",
                                f"{stats.seen():,} seen is fewer than the "
                                f"{stats.views():,} loaded"))
    for flag, n in stats.flags.items():
        if n > stats.visits:
            problems.append(Problem(f"visits that {FLAG_WORDS.get(flag, flag)}",
                                    f"{n:,} of only {stats.visits:,} visits"))
    journeys = getattr(totals, "journeys", None)
    if journeys is not None:
        differs("journeys", len(journeys), stats.visits, "visits")
        differs("pages in the journeys", sum(j["pages"] for j in journeys),
                views, "page views by people")
        differs("pages seen in the journeys", sum(j["seen"] for j in journeys),
                stats.seen(), "pages seen in visits")
    if people is not None and totals.breakdowns and stats.entries:
        for mine, theirs in (("entries", "landing"), ("source", "source"),
                             ("country", "country"), ("device", "device")):
            got, want = getattr(stats, mine), people.by.get(theirs) or Counter()
            if Counter(got) != Counter(want):
                problems.append(Problem(f"visits by {mine} do not match readers by {theirs}",
                                        f"{sum(got.values()):,} visits against "
                                        f"{sum(want.values()):,} readers, or a label differs"))
    return problems
