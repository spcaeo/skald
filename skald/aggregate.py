"""Turn a stream of hits into the numbers a card shows.

The distinction this module exists to enforce: **requests are not visitors.**

One person clicking through a modern JavaScript site produces one HTML request
and then dozens more - payload fetches for each navigation, analytics beacons,
fonts, images - every one carrying the same referrer and the same user agent.
Count requests and you report a crowd. The system this was extracted from told
its owner "56 people followed a citation to us" on a day when the truth was
one person, one IP, fifty seconds, and not a single HTML page view.

So three different quantities are kept apart, and named so a report cannot
accidentally print one while meaning another:

  hits      every request. Only useful for "how much work did the server do".
  views     requests for something a person could read (see Hit.is_page).
  visits    distinct sessions: same address and user agent, within a gap;
            for people, a page arriving from a new outside source (an
            assistant, a website, a search engine, a tagged link) starts
            a new one (_Sessions).

A visit is the closest honest answer to "how many people", and it is still an
upper bound - a household behind one address is one visit, and a scanner
presenting a Chrome user agent is counted as a visit until it asks for
something that gives it away.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Callable, Iterable

from . import dimensions as dim
from .extras import Extras
from .visits import Journeys
from .classify import Classifier, Group, Tier
from .countries import UNKNOWN
from .parse import Hit

# Breakdowns of people's readers, each counted once per reader at the
# visit's first page view, so each one adds up to `readers` exactly.
READER_DIMS = ("country", "browser", "os", "device", "source", "referrer",
               "campaign", "landing", "hour")


@dataclass
class GroupStats:
    """What one card is built from."""

    hits: int = 0
    views: int = 0
    probes: int = 0
    visits: int = 0
    # Visits that read at least one page. For people this is the headline:
    # a session that only fetched assets, payloads or redirects is a browser,
    # not a reader. None when read back from history written before it was
    # counted.
    readers: int | None = 0
    # Visits by country - where each visit started - not requests: one reader
    # loading forty assets is one visit from one country.
    countries: Counter = field(default_factory=Counter)
    pages: Counter = field(default_factory=Counter)
    agents: Counter = field(default_factory=Counter)
    # answer engines only
    tiers: Counter = field(default_factory=Counter)
    engines: Counter = field(default_factory=Counter)
    # people only: who cited us, counted in VISITS not hits
    cited_by: Counter = field(default_factory=Counter)
    cited_pages: Counter = field(default_factory=Counter)
    cited_visits: int = 0
    # Every group: requests by status class (dimensions.STATUSES), adding up
    # to `hits`; POST requests (form posts and API calls), and the paths
    # they went to.
    statuses: Counter = field(default_factory=Counter)
    posts: int = 0
    post_pages: Counter = field(default_factory=Counter)
    # People only. Readers broken down by READER_DIMS: {dimension: Counter}.
    by: dict = field(default_factory=dict)
    # Pages people asked for and got a 404, by path (adds up to the 404s).
    not_found: Counter = field(default_factory=Counter)
    # People's page views by how long the server took (dimensions.SPEEDS),
    # and the pages behind the slow ones.
    speeds: Counter = field(default_factory=Counter)
    slow_pages: Counter = field(default_factory=Counter)


@dataclass
class Totals:
    hits: int = 0
    parsed: int = 0
    # Requests for a host this report is not about: a sibling service on the
    # same server (api., app.), or the bare IP. Kept as a count so the
    # subtraction is visible - `parsed` is every line read, `hits` is what the
    # cards are about, and this is the difference.
    other_hosts: int = 0
    other_host_names: Counter = field(default_factory=Counter)
    # Lines with no host at all - the combined format does not log one - read
    # while a host filter was set. They cannot be tested against it, so they
    # are counted in `hits` like any other, and this says how many, so a
    # report can state that the filter did not apply to them.
    unfiltered: int = 0
    # Lines, and those no format could parse. For an exact window, the
    # window's own lines; an unreadable line is placed by its neighbours in
    # the file (parse.ReadStats). For a whole-file glance, the files. verify
    # fails when the share is above
    # max_unparsed_share (report.max_unparsed_percent, default 1%).
    lines_read: int = 0
    unparsed: int = 0
    # Where those lines were counted: "in the window" (an exact window:
    # its own readable lines plus the unreadable ones placed in it) or "in the
    # files read" (a whole-file glance).
    lines_scope: str = "in the files read"
    # None: already judged - a period re-read from history, each of whose days
    # was checked against the configured limit when it was collected.
    max_unparsed_share: float | None = 0.01
    # A window the logs do not wholly cover. partial_from: nothing shows the
    # logs reaching back before the window's start (the log began mid-day -
    # a launch, a new server - or retention cut the start off), so the data
    # begins at the first line. partial_until: the window is not over yet.
    # Either way the figures are true but are not a whole day, and must not
    # be compared or mailed as one.
    partial_from: object = None
    partial_until: object = None
    # Server errors (5xx) for every group, by path.
    server_errors: Counter = field(default_factory=Counter)
    # The breakdowns above (statuses, readers by country and the rest) were
    # counted: true for figures built from a log. False for a Totals put
    # together by hand, and for a period that includes days collected before
    # they existed: then they are absent, never partial sums shown as whole.
    breakdowns: bool = False
    # People's visits (visits.VisitStats) and their anonymous journeys, and
    # our own traffic by the label of the rule it matched. None when not
    # counted: a Totals put together by hand, a period with a day collected
    # before they existed, or (journeys) any period read back from history.
    visits: object = None
    journeys: list | None = None
    ours_labels: Counter | None = None
    # Schema 9 (extras.py): hours, our own health, 404s, pages, campaigns -
    # one JSON-ready dict per day. visitor_keys (aligned with journeys) and
    # visitor_seen ({(hash, kind): [n, source]}) are keyed hashes for
    # returning visitors (visitors.py): None when no key is configured, and
    # never put on a journey. returning: set by visitors.annotate.
    extras: dict | None = None
    visitor_keys: list | None = None
    # Who each journey's visit was (address, user agent, referrer, POST
    # times), aligned with journeys; memory only, kept by people/visits.py
    # when the site keeps addresses (privacy.keep_ips).
    people: list | None = None
    visitor_seen: dict | None = None
    returning: dict | None = None

    @property
    def partial(self) -> bool:
        return self.partial_from is not None or self.partial_until is not None
    groups: dict[Group, GroupStats] = field(default_factory=dict)
    first: object = None
    last: object = None

    def group(self, which: Group) -> GroupStats:
        return self.groups.setdefault(which, GroupStats())


class _Sessions:
    """Counts distinct visitors without holding every hit in memory.

    A session key is (address, user agent). A new visit is counted when that
    key has not been seen, or was last seen longer ago than the gap. Logs are
    read newest-file-first in places, so the comparison uses absolute distance
    rather than assuming time moves forward.

    With `origin` (people's page views only, dimensions.page_origin), a page
    that arrives from an outside source other than the open visit's own also
    starts a new visit (dimensions.new_source): the classic session rule, so
    a reader who comes back from an assistant inside the gap is a visit from
    that assistant. Other groups split on the gap alone.
    """

    def __init__(self, gap_minutes: int) -> None:
        self.gap = timedelta(minutes=gap_minutes)
        self.last: dict[tuple[str, str], object] = {}
        self.read: dict[tuple[str, str], bool] = {}
        self.origin: dict[tuple[str, str], tuple | None] = {}
        self.count = 0

    def saw(self, hit: Hit, origin: tuple | None = None) -> bool:
        key = (hit.address, hit.user_agent)
        previous = self.last.get(key)
        self.last[key] = hit.when
        if (previous is None or abs(hit.when - previous) > self.gap
                or dim.new_source(origin, self.origin.get(key))):
            self.count += 1
            self.read[key] = False
            self.origin[key] = origin
            return True
        if self.origin.get(key) is None:
            self.origin[key] = origin
        return False

    def first_page(self, hit: Hit) -> bool:
        """True for the first page view of the visit this hit belongs to.
        Call after saw()."""
        key = (hit.address, hit.user_agent)
        if self.read.get(key):
            return False
        self.read[key] = True
        return True


class Tally:
    """One set of totals being built, a hit at a time.

    Classification and the host filter are decided once per hit by the
    caller, then the hit is offered to every tally that wants it: the whole
    site, and each path view. So views cost one pass, not one per view, and
    every tally applies exactly the same rules.
    """

    def __init__(self, session_gap_minutes: int = 30, tz=None,
                 own_hosts: set[str] | None = None, options: dict | None = None) -> None:
        options = options or {}
        self.key = options.get("visitor_key")
        self.totals = Totals(breakdowns=True)
        self.tz = tz
        self.own_hosts = own_hosts or set()
        self.sessions: dict[Group, _Sessions] = {
            g: _Sessions(session_gap_minutes) for g in Group
        }
        self.cited_sessions = _Sessions(session_gap_minutes)
        self.cited_keys: set[tuple[str, str]] = set()
        self.journeys = Journeys(session_gap_minutes, tz, self.own_hosts, self.key)
        self.extras = Extras(tz, self.own_hosts, options.get("heartbeat") or "heartbeat",
                             session_gap_minutes)
        # The saved funnels to count today (funnel_days.wanted), or None.
        self.extras.funnels = options.get("funnels")
        # attribution.ai_likely / ai_window_minutes (ai_likely.settings).
        self.extras.attribution = options.get("attribution")
        self.ai_seen: dict[tuple[str, str], list] = {}
        self.totals.ours_labels = Counter()
        # quality.Quality for the whole site's tally only: it is fed every
        # line of the window, whatever its host (summarise_views).
        self.quality = None
        # Every reader's visit by all its labels at once, for the compare
        # report (cube.visit_rows): no top-N, so any slice of any page holds.
        self.visit_cube: Counter = Counter()

    def excluded(self, hit: Hit) -> None:
        """A line for a host this report is not about: counted, not used."""
        self.totals.parsed += 1
        self.totals.other_hosts += 1
        self.totals.other_host_names[hit.host[:40]] += 1

    def add(self, hit: Hit, verdict, unfiltered: bool = False) -> None:
        totals = self.totals
        totals.parsed += 1
        if unfiltered:
            totals.unfiltered += 1
        if totals.first is None or hit.when < totals.first:
            totals.first = hit.when
        if totals.last is None or hit.when > totals.last:
            totals.last = hit.when

        stats = totals.group(verdict.group)
        stats.hits += 1
        if verdict.probe:
            stats.probes += 1
        if hit.is_page:
            stats.views += 1
            stats.pages[hit.path[:70]] += 1
        sessions = self.sessions[verdict.group]
        origin = None
        if hit.is_page and verdict.group is Group.PEOPLE:
            origin = dim.page_origin(hit.referrer, hit.url, verdict.tier is Tier.CITED,
                                     self.own_hosts or ({hit.host.lower()} if hit.host else set()))
        if sessions.saw(hit, origin):
            stats.visits += 1
            if hit.country:
                stats.countries[hit.country] += 1
        if hit.is_page and sessions.first_page(hit):
            stats.readers += 1
            if verdict.group is Group.PEOPLE:
                self._reader(stats, hit, verdict)
                self.extras.reader(hit.when)
        status = dim.status_class(hit.status)
        stats.statuses[status] += 1
        if hit.is_form_post:
            stats.posts += 1
            stats.post_pages[hit.path[:70]] += 1
        if status == "5xx":
            totals.server_errors[hit.path[:70]] += 1
        if verdict.group is Group.PEOPLE:
            if status == "404":
                stats.not_found[hit.path[:70]] += 1
            if hit.is_page:
                bucket = dim.speed(hit.request_time)
                stats.speeds[bucket] += 1
                if bucket in dim.SLOW:
                    stats.slow_pages[hit.path[:70]] += 1

        self.extras.add(hit, verdict)
        if verdict.group is Group.PEOPLE:
            self.journeys.add(hit, verdict)
        elif verdict.group is Group.OURS:
            totals.ours_labels[verdict.engine or "(unlabelled)"] += 1
        elif (verdict.group is Group.ANSWER_ENGINE and verdict.tier
              and self.key is not None):
            from .visitors import visitor_hash
            got = self.ai_seen.setdefault(
                (visitor_hash(self.key, hit.address, verdict.engine), verdict.tier.value), [0, ""])
            got[0] += 1

        if verdict.group is Group.ANSWER_ENGINE:
            if verdict.tier:
                stats.tiers[verdict.tier.value] += 1
            if verdict.engine:
                stats.engines[verdict.engine] += 1
        elif verdict.group is Group.SEARCH_ENGINE:
            if verdict.engine:
                stats.engines[verdict.engine] += 1
        elif verdict.group is Group.PEOPLE and verdict.tier is Tier.CITED:
            # Counted per visitor, not per request. A key already seen inside
            # the gap adds nothing, which is the whole fix.
            key = (hit.address, hit.user_agent)
            fresh = self.cited_sessions.saw(hit)
            if fresh or key not in self.cited_keys:
                self.cited_keys.add(key)
                stats.cited_visits += 1
                stats.cited_by[verdict.engine] += 1
            if hit.is_page:
                stats.cited_pages[hit.path[:70]] += 1
        elif verdict.group is Group.BOTS and not verdict.probe:
            stats.agents[verdict.engine or _short_agent(hit.user_agent)] += 1

    def _reader(self, stats: GroupStats, hit: Hit, verdict) -> None:
        """One reader, at the first page they read: where they came from,
        on what, and when. Every dimension gets exactly one label."""
        browser, system, device = dim.agent_labels(hit.user_agent)
        cited = verdict.tier is Tier.CITED
        own = self.own_hosts or ({hit.host.lower()} if hit.host else set())
        labels = {
            "country": hit.country.upper() if hit.country else UNKNOWN,
            "browser": browser,
            "os": system,
            "device": device,
            "source": dim.source_type(hit.referrer, hit.url, cited, own),
            "referrer": dim.referrer_label(hit.referrer, own, hit.url),
            "campaign": dim.campaign(hit.url),
            "landing": hit.path[:70],
            "hour": dim.hour(hit.when, self.tz),
        }
        for name, value in labels.items():
            stats.by.setdefault(name, Counter())[value] += 1
        self.visit_cube[(labels["country"], labels["landing"], labels["source"],
                         verdict.engine if cited else "", labels["device"], labels["browser"],
                         labels["os"], labels["campaign"])] += 1

    def finish(self, top: int) -> Totals:
        totals = self.totals
        totals.hits = totals.parsed - totals.other_hosts
        totals.other_host_names = Counter(dict(totals.other_host_names.most_common(top)))
        for stats in totals.groups.values():
            stats.countries = Counter(dict(stats.countries.most_common(top)))
            stats.pages = Counter(dict(stats.pages.most_common(top)))
            stats.agents = Counter(dict(stats.agents.most_common(top)))
            stats.engines = Counter(dict(stats.engines.most_common(top)))
            stats.cited_pages = Counter(dict(stats.cited_pages.most_common(top)))
            # Folded, not cut: the tail is one "(all others)" row, so each
            # still adds up to the figure it breaks down.
            stats.post_pages = dim.fold(stats.post_pages, top)
            stats.not_found = dim.fold(stats.not_found, top)
            stats.slow_pages = dim.fold(stats.slow_pages, top)
            stats.by = {name: dim.fold(c, max(top, 25)) for name, c in stats.by.items()}
        totals.server_errors = dim.fold(totals.server_errors, top)
        totals.journeys, totals.visits = self.journeys.finish(top)
        totals.visitor_keys = self.journeys.visitor_keys
        totals.people = self.journeys.people
        if self.key is not None:
            seen = dict(self.ai_seen)
            for j, visitor in zip(totals.journeys, totals.visitor_keys or []):
                got = seen.setdefault((visitor, "reader"), [0, j.get("source", "")])
                got[0] += 1
            totals.visitor_seen = seen
        people = totals.groups.get(Group.PEOPLE)
        self.extras.visit_firsts = self.journeys.firsts
        totals.extras = self.extras.finish(totals, totals.journeys, self.journeys.pages,
                                           people.by.get("hour") if people else {})
        if self.quality is not None:
            totals.extras["quality"] = self.quality.finish()
        from .cube import visit_rows
        totals.extras["visit_cube"] = visit_rows(self.visit_cube)
        return totals


def summarise_views(
    hits: Iterable[Hit],
    classifier: Classifier,
    session_gap_minutes: int = 30,
    top: int = 8,
    hosts: list[str] | None = None,
    observe: Callable[[Hit, object], None] | None = None,
    views: dict[str, Callable[[Hit], bool]] | None = None,
    tz=None,
    options: dict | None = None,
) -> tuple[Totals, dict[str, Totals]]:
    """The whole site, and each view, in one pass.

    A view is a test on the hit - in practice a path prefix (config.views).
    It sees only the lines it matches, and builds its totals from them with
    the same rules, so its five groups add up to its own line count exactly
    as the site's do. A line for another host is excluded everywhere it is
    counted, the same way.
    """
    from .quality import Quality
    wanted = {h.lower() for h in (hosts or [])}
    whole = Tally(session_gap_minutes, tz, wanted, options)
    whole.quality = Quality(tz)
    tallies = {name: (test, Tally(session_gap_minutes, tz, wanted, options))
               for name, test in (views or {}).items()}
    for hit in hits:
        whole.quality.add(hit)
        chosen = [t for test, t in tallies.values() if test(hit)]
        if wanted and hit.host and hit.host.lower() not in wanted:
            whole.excluded(hit)
            for t in chosen:
                t.excluded(hit)
            if observe is not None and hasattr(observe, "excluded"):
                observe.excluded(hit)
            continue
        unfiltered = bool(wanted) and not hit.host
        verdict = classifier(hit)
        if observe is not None:
            observe(hit, verdict)
        whole.add(hit, verdict, unfiltered)
        for t in chosen:
            t.add(hit, verdict, unfiltered)
    return (whole.finish(top),
            {name: t.finish(top) for name, (_, t) in tallies.items()})


def summarise(
    hits: Iterable[Hit],
    classifier: Classifier,
    session_gap_minutes: int = 30,
    top: int = 8,
    hosts: list[str] | None = None,
    observe: Callable[[Hit, object], None] | None = None,
    tz=None,
) -> Totals:
    """Everything the cards need, in one pass over the log.

    `observe(hit, verdict)` is called for every counted hit, after it is
    classified - for a caller that wants something the totals do not keep,
    such as the most recent assistant fetches, without a second pass.

    `hosts` is the list of hostnames this report is about. One server usually
    answers for several: a marketing site, an API, a customer app, and its own
    bare IP address. Pooling them makes every figure meaningless - on the
    reference server 4,265 API calls and 3,003 app requests were being counted
    as website visitors, and 2,695 requests to the bare IP were counted as
    whatever user agent they claimed, when a request to an IP address is never
    a person: nobody types one.

    Leave it empty to count everything, which is right for a server with one
    site on it.
    """
    return summarise_views(hits, classifier, session_gap_minutes, top, hosts,
                           observe, tz=tz)[0]


def _short_agent(agent: str) -> str:
    """A name a person can read, out of a user-agent string.

    Bots usually put their name first or in a +http://... note. This is a
    presentation nicety and nothing depends on it being right.
    """
    if not agent:
        return "(no user agent)"
    if "Nexus 5X Build/MMB29P" in agent:
        return "Googlebot template, no Googlebot"
    # "Mozilla/5.0 (compatible; ctwatch/0.1)": the name is after "compatible;".
    named = _COMPATIBLE.search(agent)
    if named:
        return named.group(1)[:28]
    head = agent.split("/")[0].split(" ")[0]
    if head == "Mozilla":
        return "browser-like agent"
    return (head or agent)[:28]


_COMPATIBLE = re.compile(r"compatible;\s*([^/;)]+?)\s*(?:/|;|\))")
