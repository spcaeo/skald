"""An independent recount of a stored day, from the raw log lines.

verify.py checks that the figures agree with each other. That cannot catch
a number that is wrong everywhere at once - a session counted twice by the
tally, a breakdown fed the wrong hit, a rule applied in the wrong order. So
this module counts the day again by a different road and compares what it
finds with what history holds (or, with --live, with today's snapshot).

Different road means different code. Nothing here calls the package's
parser, classifier, session counter, page rule or label functions: it has
its own line patterns, its own classification order, its own crawler-visit
rule, its own page rule, and its own browser, system, device, source and
campaign labels. What it shares is only the lists of names - the AI
assistants, search crawlers, bots and scanner paths in classify.py - because
those are data, not logic: a recount with a different list would be counting
something else. The GeoIP file (`logs.country_db`) is data in the same way: a
line with no country of its own is looked up in it, as the main road does.

So when the two disagree, one of two pieces of code that were written apart
is wrong, and the day is withheld until somebody finds out which.

Output never carries an address: anything shaped like one is masked
(`mask`), whatever field it came from.
"""
from __future__ import annotations

import gzip
import ipaddress
import re
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

# The name lists - the only thing shared with the package.
from .classify import (AI_ASKED, AI_REFERRER_HOSTS, AI_TRAINING, AI_UTM, OTHER_BOT,
                       OWN_AGENTS, PROBE, PROBE_QUERY, SEARCH_ENGINE)
from .store import History, READER_KINDS
from . import (audit_drains, audit_extras, audit_more, audit_release2, audit_rendered,
               audit_visits)
# The audit's own labels (moved out whole; still audit.browser_of etc.).
from .audit_labels import (_bare, _host_of, browser_of, campaign_of,  # noqa: F401
                           device_of, referrer_of, source_of, status_of, system_of)

GROUPS = ("people", "answer_engines", "search_engines", "bots", "ours")
DIMS = ("country", "browser", "os", "device", "source", "referrer", "campaign",
        "landing", "hour")
OTHER = "(all others)"          # the label history folds a long tail into

# ------------------------------------------------------------------ lines

_EXTENDED = re.compile(
    r'^(\S+) (\S+) (\S+) "([^"]*)" (\d{3}) (\S+) "([^"]*)" "([^"]*)"'
    r'(?:\s+(\S+))?(?:\s+cc=(\S+))?')
_COMBINED = re.compile(
    r'^(\S+) \S+ \S+ \[([^\]]+)\] "([^"]*)" (\d{3}) (\S+) "([^"]*)" "([^"]*)"(.*)$')
# A combined line's last field, when it is quoted and a host name (a name with
# a letter and a dot; a port dropped). An address list or "-" is not one.
_LAST_QUOTED = re.compile(r'"([^"]*)"\s*$')
_REQUEST = re.compile(r"^([A-Z]+) (\S*)")
# Skald's own endpoints (script-tag events, its file, hooks, shipped logs): a
# POST to one is no form post.
_OWN = re.compile(r"/traffic-(?:beacon(?:$|[/?])|js/|hooks/|ingest/)")
# nginx's $request_id, the last field of the extended layout since it was
# added; older lines have none.
_RID = re.compile(r"\srid=([0-9A-Za-z-]{8,64})\s*$")


@dataclass
class Line:
    when: datetime
    address: str
    host: str
    method: str
    url: str
    status: str
    referrer: str
    agent: str
    country: str
    rid: str = ""
    # Body bytes sent and the response time in seconds, when the line has
    # them (None: not logged). What each crawler costs (audit_crawler_cost).
    size: int | None = None
    seconds: float | None = None

    @property
    def path(self) -> str:
        return self.url.partition("?")[0]


def line_hit(raw: str) -> Line | None:
    """One log line, or None if no layout reads it: nginx's extended or
    combined (Apache's too), a Caddy JSON line, or a Vercel / Netlify drain
    record kept by the ingest endpoint (audit_drains, its own reader)."""
    if raw.lstrip().startswith("{"):
        got = audit_drains.fields(raw)
        return Line(**got) if got else None
    m = _EXTENDED.match(raw)
    if m:
        try:
            when = datetime.fromisoformat(m.group(1))
        except ValueError:
            when = None
        if when is not None:
            got = _line(when, m.group(2), m.group(3), m.group(4), m.group(5),
                        m.group(7), m.group(8), m.group(10))
            rid = _RID.search(raw.rstrip("\n"))
            got.rid = rid.group(1) if rid else ""
            got.size, got.seconds = _byte_count(m.group(6)), _secs(m.group(9))
            return got
    m = _COMBINED.match(raw)
    if m:
        try:
            when = datetime.strptime(m.group(2), "%d/%b/%Y:%H:%M:%S %z")
        except ValueError:
            return None
        got = _line(when, m.group(1), _named_host(m.group(8)), m.group(3), m.group(4),
                    m.group(6), m.group(7), None)
        got.size, got.seconds = _byte_count(m.group(5)), _tail_seconds(m.group(8))
        return got
    return None


def _byte_count(raw: str | None) -> int | None:
    """The size field: a whole number of bytes, or None ("-", absent)."""
    if not raw or not raw.isdigit():
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _secs(raw: str | None) -> float | None:
    """A response time in seconds: a number from 0 up to a day, else None."""
    try:
        value = float(raw) if raw else None
    except ValueError:
        return None
    return value if value is not None and 0 <= value < 86400 else None


def _tail_seconds(tail: str) -> float | None:
    """The combined layout's optional response time: the first field after
    the user agent, when it is digits with at most one decimal point and
    a space or the end after it."""
    if not tail[:1].isspace():
        return None
    first = tail.split(None, 1)[0] if tail.strip() else ""
    whole, dot, frac = first.partition(".")
    if not whole.isdecimal() or (dot and not frac.isdecimal()):
        return None
    return _secs(first)


def _named_host(tail: str) -> str:
    found = _LAST_QUOTED.search(tail or "")
    if not found or found.start() == 0 or not tail[found.start() - 1].isspace():
        return ""
    name = found.group(1).rsplit(":", 1)[0] if found.group(1).count(":") == 1 \
        else found.group(1)
    labels = name.split(".")
    if len(labels) < 2 or not any(c.isalpha() for c in name):
        return ""
    if not all(lab and all(c.isalnum() or c == "-" for c in lab) for lab in labels):
        return ""
    return name.lower()


def _line(when, address, host, request, status, referrer, agent, cc) -> Line:
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    req = _REQUEST.match(request)
    cc = (cc or "").strip()
    return Line(when, address, host or "", req.group(1) if req else "",
                req.group(2) if req else "", status,
                "" if referrer == "-" else referrer, "" if agent == "-" else agent,
                "" if cc in ("", "-", "XX", "ZZ") else cc.upper())


def log_files(config: dict) -> list[Path]:
    """Every rotation of the log, oldest first: base.N.gz ... base.1, base."""
    logs = config.get("logs") or {}
    folder = Path(logs.get("dir") or "/var/log/nginx")
    base = str(logs.get("base") or "access.log")
    found = []
    for path in folder.glob(base + "*"):
        rest = path.name[len(base):]
        m = re.fullmatch(r"(?:\.(\d+))?(?:\.gz)?", rest)
        if m:
            found.append((-(int(m.group(1)) if m.group(1) else 0), path))
    return [p for _, p in sorted(found)]


def raw_lines(path: Path, upto: dict | None = None):
    """A file's text lines. `upto` ({file name: bytes}) is how far the live
    run read each plain file (the snapshot's `read_upto`): only the lines
    wholly inside that many bytes, so lines appended since are not counted.
    No limit (a day's audit, an older snapshot): the whole file."""
    limit = None if path.suffix == ".gz" else (upto or {}).get(path.name)
    if limit is None:
        opener = gzip.open if path.suffix == ".gz" else open
        with opener(path, "rt", errors="replace") as handle:
            yield from handle
        return
    left = int(limit)
    with open(path, "rb") as handle:
        while left > 0:
            raw = handle.readline(left)
            left -= len(raw)
            if not raw.endswith(b"\n"):
                return              # a line cut at the limit (or still being written)
            text = raw[:-1].decode("utf-8", "replace")
            yield (text[:-1] if text.endswith("\r") else text) + "\n"


def _read(paths, upto: dict | None = None):
    """Every readable line, without a second copy of any request id: a line
    repeating an earlier rid= is the same request written twice. `upto`:
    raw_lines."""
    rids = set()
    for path in paths:
        for raw in raw_lines(path, upto):
            got = line_hit(raw)
            if got is None:
                continue
            if got.rid:
                if got.rid in rids:
                    continue
                rids.add(got.rid)
            yield got


# ------------------------------------------------------------ what it is

_PAYLOAD = re.compile(r"[?&](?:_rsc|__flight__|_data)=", re.I)
_ASSET_EXT = (".css", ".js", ".mjs", ".map", ".png", ".jpg", ".jpeg", ".gif",
              ".svg", ".webp", ".avif", ".ico", ".woff", ".woff2", ".ttf", ".eot",
              ".txt", ".xml", ".json", ".webmanifest",
              # release 2: not pages either
              ".xsl", ".xslt", ".rss", ".atom", ".csv", ".tsv", ".pdf", ".zip", ".gz",
              ".tgz", ".rar", ".7z", ".mp4", ".webm", ".mov", ".mp3", ".wav", ".ogg",
              ".m4a", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".wasm")
_ASSET_DIRS = ("/_next/", "/static/", "/assets/", "/_nuxt/", "/build/")
_BEACON = re.compile(r"^/(?:api/|api$|__analytics\b|collect\b|beacon\b|ping\b)",
                     re.I)


def _asset(line: Line) -> bool:
    path = line.path.lower()
    return path.endswith(_ASSET_EXT) or path.startswith(_ASSET_DIRS)


def is_page(line: Line) -> bool:
    """A 2xx (or 304: the cached copy, shown) GET or HEAD for a document: no
    payload, asset or beacon."""
    return ((line.status.startswith("2") or line.status == "304")
            and line.method in ("GET", "HEAD")
            and not _PAYLOAD.search(line.url) and not _asset(line)
            and not _BEACON.search(line.path))


_CRAWLER_FILES = {"/robots.txt", "/ads.txt", "/app-ads.txt", "/security.txt",
                  "/.well-known/security.txt"}
_SITEMAP = re.compile(r"sitemap[^/]*\.(?:xml|txt)(?:\.gz)?$", re.I)


def _crawler_file(line: Line) -> bool:
    return line.path.lower() in _CRAWLER_FILES or bool(_SITEMAP.search(line.path))


class Judge:
    """Which group a line is in, decided in the order the package documents
    (CLASSIFICATION.md) - written again here, not called."""

    def __init__(self, config: dict, lines: list[Line], gap: timedelta,
                 now: datetime | None = None, window: tuple | None = None,
                 tz=None) -> None:
        ours = config.get("ours") or {}
        entries = audit_visits.ours_entries
        self.agents = [(v.lower(), l) for v, l in entries(ours.get("user_agents"), "agent", False)]
        self.agents += [(v.lower(), l) for v, l in OWN_AGENTS]
        self.referrers = [(v.lower(), l) for v, l in
                          entries(ours.get("referrers"), "referrer", False)]
        self.networks = [(ipaddress.ip_network(v, strict=False), l, None)
                         for v, l in entries(ours.get("addresses"), "ip", True)]
        self.networks += [(ipaddress.ip_network(v, strict=False), l, since)
                          for v, l, since in audit_visits.page_added(config)]
        self.hosts = {str(h).lower() for h in
                      ((config.get("site") or {}).get("hosts") or [])}
        self.crawlers = self._crawlers(lines, gap)
        # Release 2: crawler checks, old-site paths, fan-out bursts.
        self.checks = audit_release2.Checks(config, now or datetime.now(timezone.utc))
        raw = (config.get("site") or {}).get("legacy_paths") or []
        self.legacy = tuple(str(p) for p in (raw.split() if isinstance(raw, str) else raw)
                            if str(p).startswith("/"))
        self.bursts = audit_release2.bursts(lines, self.hosts)
        # Browser-like visits that drew nothing (audit_rendered): bots.
        first, last = window or ((min(l.when for l in lines), max(l.when for l in lines))
                                 if lines else (None, None))
        self.unrendered = audit_rendered.never_drawn(
            config, lines, gap, self.hosts, first, last, tz or timezone.utc, _asset,
            lambda path: bool(_BEACON.search(path)),
            lambda agent: f"{browser_of(agent)}/{system_of(agent)}",
            audit_extras.keyed, audit_extras.secret(config)) if lines else {}
        # What the last call found beyond the group (audit_release2.BotsRecount).
        self.info: dict = {}

    def _ours(self, line: Line) -> str:
        """The label of the first `ours` rule the line matches, or ""."""
        agent, ref = line.agent.lower(), line.referrer.lower()
        for a, label in self.agents:
            if a in agent:
                return label
        for r, label in self.referrers:
            if ref and r in ref:
                return label
        try:
            ip = ipaddress.ip_address(line.address)
        except ValueError:
            return ""
        for n, label, since in self.networks:
            if ip in n and (since is None or line.when >= since):
                return label
        return ""

    def ours_label(self, line: Line) -> str:
        return self._ours(line)

    def _crawlers(self, lines: list[Line], gap: timedelta) -> dict:
        """Visits that asked for robots.txt or a sitemap on the site and did
        not render its pages (fewer own-site assets than pages read)."""
        per_key: dict[tuple, list[Line]] = {}
        for line in lines:
            if self.hosts and line.host and line.host.lower() not in self.hosts:
                continue
            per_key.setdefault((line.address, line.agent), []).append(line)
        spans: dict[tuple, list] = {}
        for key, seen in per_key.items():
            if not any(_crawler_file(l) for l in seen):
                continue
            seen = sorted(seen, key=lambda l: l.when)
            visits, current = [], [seen[0]]
            for l in seen[1:]:
                if l.when - current[-1].when > gap:
                    visits.append(current)
                    current = []
                current.append(l)
            visits.append(current)
            for visit in visits:
                if not any(_crawler_file(l) for l in visit):
                    continue
                pages = sum(1 for l in visit if is_page(l))
                rendered = 0
                for l in visit:
                    if (_asset(l) or _PAYLOAD.search(l.url)) and l.referrer:
                        ref = _host_of(l.referrer)
                        if (ref in self.hosts) if self.hosts else (
                                ref == l.host.lower() or not l.host):
                            rendered += 1
                if rendered and rendered >= pages:
                    continue
                spans.setdefault(key, []).append((visit[0].when, visit[-1].when))
        return spans

    def _claim(self, name: str, line: Line, group: str) -> str:
        checked = self.checks.verdict(name, line.address, line.agent) if self.checks.on else None
        if checked == "spoofed":
            self.info = {"spoofed": name, "claim_group": group}
            return "bots"
        self.info = {"name": name, "checked": checked}
        return group

    def __call__(self, line: Line) -> tuple[str, bool]:
        """(group, cited) for one line."""
        agent = line.agent
        self.info = {}
        if self._ours(line):
            return "ours", False
        named = AI_ASKED.search(agent) or AI_TRAINING.search(agent)
        if named:
            return self._claim(named.group(0), line, "answer_engines"), False
        app = audit_release2.preview_app(agent)
        if app:
            self.info = {"preview": app}
            return "bots", False
        named = SEARCH_ENGINE.search(agent)
        if named:
            return self._claim(named.group(0), line, "search_engines"), False
        probe = bool(PROBE.search(line.path) or PROBE_QUERY.search(line.url))
        if probe and any(line.path.startswith(p) for p in self.legacy):
            probe = False
        if probe:
            self.info = {"probe": True}
            return "bots", False
        compatible_only = ("(compatible;" in agent.lower() and not re.search(
            r"AppleWebKit|Gecko|Trident|Presto|Chrome/|Safari/|Firefox/", agent, re.I))
        if (not agent or OTHER_BOT.search(agent) or compatible_only
                or line.path.startswith("/.well-known/acme-challenge/")):
            return "bots", False
        browser = re.search(r"Mozilla/|Opera/|Safari/|Chrome/|Firefox/", agent, re.I)
        if not browser:
            return "bots", False
        for first, last in self.crawlers.get((line.address, line.agent), ()):
            if first <= line.when <= last:
                self.info = {"crawler": True}
                return "bots", False
        for first, last in self.unrendered.get((line.address, line.agent), ()):
            if first <= line.when <= last:
                self.info = {"not_rendered": True}
                return "bots", False
        flags = []
        if self.checks.on and self.checks.from_hosting(line.address):
            flags.append("hosting_network")
        if (line.address, line.agent) in self.bursts:
            flags.append("fan_out")
        if agent.strip() == "Mozilla/5.0":
            flags.append("bare_mozilla")
        self.info = {"flags": flags}
        return "people", _cited(line)


def _cited(line: Line) -> bool:
    """CLASSIFICATION.md rule 10: the referrer's host is an assistant's, or an
    assistant's utm_source tag is on the URL - whatever the referrer, so a
    tagged link behind a search or own-site referrer is a citation too."""
    host = _host_of(line.referrer) if line.referrer else ""
    if host:
        if any(host == d or host.endswith("." + d) for d in AI_REFERRER_HOSTS):
            return True
        if (host == "bing.com" or host.endswith(".bing.com")) and \
                urlsplit(line.referrer).path.startswith("/chat"):
            return True
    return bool(AI_UTM.search(line.url))


# --------------------------------------------------------------- recount

def _countries(config: dict, lines: list) -> None:
    """Give a line without a country the one the GeoIP file has for its
    address (the file is data, like the name lists; the reader of the
    MaxMind format is conversions/geo.py). Unknown stays "" ."""
    from .conversions.geo import country, database
    path = database(config)
    if not path:
        return
    seen: dict[str, str] = {}
    for line in lines:
        if line.country:
            continue
        got = seen.get(line.address)
        if got is None:
            code = (country(path, line.address) or "").upper()
            got = seen[line.address] = "" if code in ("XX", "ZZ") else code
        line.country = got


def window(day: date, tz) -> tuple[datetime, datetime]:
    start = datetime(day.year, day.month, day.day, tzinfo=tz)
    nxt = day + timedelta(days=1)
    end = datetime(nxt.year, nxt.month, nxt.day, tzinfo=tz)
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)


def recount(config: dict, day: date, tz, paths=None, now=None,
            until: datetime | None = None, upto: dict | None = None) -> dict:
    """The day's figures, counted again from the log. `until` cuts the day
    short (today so far, for comparing with the live snapshot); `upto` (the
    snapshot's `read_upto`) reads each plain file only as far as it did."""
    start, end = window(day, tz)
    if until is not None:
        end = min(end, until)
    files = [Path(p) for p in paths] if paths else log_files(config)
    site = config.get("site") or {}
    wanted = {str(h).lower() for h in (site.get("hosts") or [])}
    gap = timedelta(minutes=int((config.get("report") or {}).get(
        "session_gap_minutes") or 30))

    lines = [l for l in _read(files, upto) if start <= l.when < end]
    _countries(config, lines)
    judge = Judge(config, lines, gap, window=(start, end), tz=tz)
    bots = audit_release2.BotsRecount(gap)

    requests = {g: 0 for g in GROUPS}
    posts = {g: 0 for g in GROUPS}
    statuses = {g: Counter() for g in GROUPS}
    excluded = 0
    people: dict[tuple, list] = {}
    ours_labels: Counter = Counter()
    report = config.get("report") or {}
    extras = audit_extras.ExtrasRecount(tz, str(report.get("heartbeat_label") or "heartbeat"),
                                        audit_extras.secret(config))
    firsts = audit_release2.FirstsRecount(wanted, source_of, _bare)
    more = audit_more.start(config, day, tz, wanted)    # phase 4 recounts
    more.set_window(start, end)
    for line in lines:
        if wanted and line.host and line.host.lower() not in wanted:
            excluded += 1
            continue
        group, cited = judge(line)
        bots.hit(line, group, judge.info)
        more.judged(line, group, judge.info)
        requests[group] += 1
        if line.method == "POST" and not _OWN.match(line.path):
            posts[group] += 1
        statuses[group][status_of(line.status)] += 1
        label = tier = name = ""
        if group == "people":
            people.setdefault((line.address, line.agent), []).append((line, cited))
        elif group == "ours":
            label = judge.ours_label(line)
            ours_labels[label] += 1
        elif group == "answer_engines":
            found = AI_ASKED.search(line.agent)
            tier = "asked" if found else "training"
            name = (found or AI_TRAINING.search(line.agent)).group(0)
        firsts.hit(line, group, judge.info, tier, name, cited, is_page(line))
        more.hit(line, group, tier, name)
        extras.hit(line, group, tier, name, label, is_page(line),
                   bool(PROBE.search(line.path) or PROBE_QUERY.search(line.url))
                   and not any(line.path.startswith(p) for p in judge.legacy))

    visits = readers = 0
    by = {name: Counter() for name in DIMS}
    journeys = audit_visits.VisitRecount(wanted)

    def close(visit: list) -> None:
        nonlocal visits, readers
        visits += 1
        labels = _reader(visit, by, wanted, tz)
        readers += labels is not None
        journeys.visit([i[0] for i in visit], is_page)
        more.visit([i[0] for i in visit], is_page, labels)
        _landing(visit, extras)

    for seen in people.values():
        seen.sort(key=lambda item: item[0].when)
        visit: list = []
        came = None             # where the visit's first page came from
        for item in seen:
            here = _came_from(item, wanted) if is_page(item[0]) else None
            if visit and (item[0].when - visit[-1][0].when > gap
                          or _elsewhere(here, came)):
                close(visit)
                visit, came = [], None
            visit.append(item)
            came = came or here
        if visit:
            close(visit)

    return {
        "day": day.isoformat(),
        "requests": sum(requests.values()),
        "excluded": excluded,
        "groups": requests,
        "posts": posts,
        "statuses": statuses,
        "server_errors": sum(c["5xx"] for c in statuses.values()),
        "visits": visits,
        "readers": readers,
        "by": by,
        "journeys": journeys.figures(),
        "journey_pages": journeys.journeys_pages,
        "ours": ours_labels,
        "extras": extras.figures(),
        "bots": bots.figures(),
        "quality": audit_release2.quality(files, start, end, line_hit, upto),
        "page_firsts": firsts.got,
        "more": more,
    }


def judged(config: dict, tz, start: datetime, end: datetime, paths=None,
           upto: dict | None = None):
    """(line, group) for every line in [start, end), group "excluded" for
    another host; each local day's part judged over that day from its
    midnight, as the live run and its feed are. `upto`: raw_lines."""
    files = [Path(p) for p in paths] if paths else log_files(config)
    wanted = {str(h).lower() for h in ((config.get("site") or {}).get("hosts") or [])}
    gap = timedelta(minutes=int((config.get("report") or {}).get(
        "session_gap_minutes") or 30))
    lines = [l for l in _read(files, upto) if l.when < end]
    day = start.astimezone(tz).date()
    while True:
        first, last = window(day, tz)
        if first >= end:
            break
        part = [l for l in lines if first <= l.when < min(last, end)]
        judge = Judge(config, part, gap, window=(first, min(last, end)), tz=tz)
        for line in part:
            if line.when < start:
                continue
            if wanted and line.host and line.host.lower() not in wanted:
                yield line, "excluded"
            else:
                yield line, judge(line)[0]
        day += timedelta(days=1)


def recount_requests(config: dict, tz, start: datetime, end: datetime,
                     paths=None, upto: dict | None = None) -> Counter:
    """Requests in [start, end) by group (and "excluded")."""
    return Counter(group for _, group in judged(config, tz, start, end, paths, upto))


def recount_alert_figures(config: dict, tz, kept: dict, paths=None,
                          upto: dict | None = None) -> dict:
    """The totals an alert check read (alerts.figures), counted again: each
    over the whole minutes from `minutes - 1` before `at`'s minute to `at`."""
    at = datetime.fromisoformat(kept["at"]).astimezone(timezone.utc)
    end = at                            # the live window ends at the second's start
    longest = max(kept[k]["minutes"] for k in ("server_errors", "people_404", "requests"))
    start = datetime.fromtimestamp((int(at.timestamp()) // 60 - longest + 1) * 60, timezone.utc)
    got = {"server_errors": 0, "people_404": 0, "requests": 0}
    newest = None
    for line, group in judged(config, tz, start, end, paths, upto):
        age = int(at.timestamp()) // 60 - int(line.when.timestamp()) // 60
        if age < kept["server_errors"]["minutes"] and line.status.startswith("5"):
            got["server_errors"] += 1
        if age < kept["people_404"]["minutes"] and group == "people" and line.status == "404":
            got["people_404"] += 1
        if age < kept["requests"]["minutes"]:
            got["requests"] += 1
    for line in _read([Path(p) for p in paths] if paths else log_files(config), upto):
        if line.when < end and (newest is None or line.when > newest):
            newest = line.when
    got["newest_line"] = newest.isoformat(timespec="seconds") if newest else None
    return got


def _came_from(item: tuple, wanted: set) -> tuple | None:
    """A page view's source, referrer and campaign, by the audit's labels;
    None when the site's hosts are not known, so its own links cannot be
    told from outside ones."""
    line, cited = item
    own = wanted or ({line.host.lower()} if line.host else set())
    if not own:
        return None
    return source_of(line, cited, own), referrer_of(line, own), campaign_of(line.url)


def _elsewhere(here: tuple | None, came: tuple | None) -> bool:
    """SOP.md "What a visit is": inside the gap, a page from outside the
    site (not from the site itself, not without referrer and tag) that came
    from somewhere other than the visit's first page opens a new visit."""
    if here is None or came is None:
        return False
    return here[0] not in ("This site", "Direct or unknown") and here != came


def _landing(visit: list, extras) -> None:
    first = next((item[0] for item in visit if is_page(item[0])), None)
    if first is not None:
        extras.visit(first, f"{browser_of(first.agent)}/{system_of(first.agent)}")


def _reader(visit: list, by: dict, wanted: set, tz) -> dict | None:
    """Label the visit's first page view in every dimension: its labels,
    or None if it read no page."""
    first = next((item for item in visit if is_page(item[0])), None)
    if first is None:
        return None
    line, cited = first
    own = wanted or ({line.host.lower()} if line.host else set())
    labels = {
        "country": line.country or "Unknown",
        "browser": browser_of(line.agent),
        "os": system_of(line.agent),
        "device": device_of(line.agent),
        "source": source_of(line, cited, own),
        "referrer": referrer_of(line, own),
        "campaign": campaign_of(line.url),
        "landing": line.path[:70],
        "hour": f"{line.when.astimezone(tz).hour:02d}",
    }
    for name, value in labels.items():
        by[name][value] += 1
    return labels


_IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_IPV6 = re.compile(r"[0-9A-Fa-f:]*:[0-9A-Fa-f:]*:[0-9A-Fa-f:.]*")


def _v6(m: re.Match) -> str:
    try:
        ipaddress.IPv6Address(m.group(0))
    except ValueError:
        return m.group(0)          # a time of day, say: 07:32:01
    return "[address]"


def mask(text: str) -> str:
    """Anything shaped like an address, hidden - in every line printed."""
    return _IPV6.sub(_v6, _IPV4.sub("[address]", text))


def compare(figures: dict, history: History, site: str, day: date,
            window: int = 30) -> tuple[list[str], int]:
    """(mismatches, how many figures were compared) against the stored day.
    `window`: the returning-visitor days (visitors.repeat_days, default 30)."""
    key = (site, day.isoformat())
    db = history.db
    row = db.execute("SELECT hits, breakdowns, journeys, extras FROM days "
                     "WHERE site = ? AND day = ?", key).fetchone()
    if row is None:
        return [f"{day}: not stored in history; collect it before auditing it"], 0
    problems: list[str] = []
    compared = 0

    def same(what: str, stored, counted) -> None:
        nonlocal compared
        compared += 1
        if stored != counted:
            problems.append(f"{what}: history has {stored:,}, the recount "
                            f"finds {counted:,}")

    same("requests for this site", row[0], figures["requests"])
    stored_groups = {g: (h, vi, r) for g, h, vi, r in db.execute(
        "SELECT grp, hits, visits, readers FROM groups WHERE site = ? AND day = ?", key)}
    for g in GROUPS:
        same(f"{g}: requests", stored_groups.get(g, (0, 0, 0))[0],
             figures["groups"][g])
    p = stored_groups.get("people", (0, 0, 0))
    same("people: visits", p[1], figures["visits"])
    if p[2] is not None:
        same("people: readers", p[2], figures["readers"])

    if not row[1]:
        return problems, compared        # collected before breakdowns existed

    counts: dict[str, Counter] = {}
    for kind, name, n in db.execute(
            "SELECT kind, name, n FROM counts WHERE site = ? AND day = ?", key):
        counts.setdefault(kind, Counter())[name] = n

    for g in GROUPS:
        stored = counts.get(f"status_{g}", Counter())
        counted = figures["statuses"][g]
        for status in sorted(set(stored) | set(counted)):
            same(f"{g}: {status} responses", stored.get(status, 0),
                 counted.get(status, 0))
        same(f"{g}: POST requests",
             counts.get("post_total", Counter()).get(g, 0),
             figures["posts"][g])
    same("server errors (5xx) by path, summed",
         sum(counts.get("server_error_page", Counter()).values()),
         figures["server_errors"])

    stored_readers = p[2] or 0
    for name in DIMS:
        _compare_dim(name, counts.get(READER_KINDS[name], Counter()),
                     figures["by"][name], stored_readers, same, problems)
    if row[2]:                           # visits counted (schema 8)
        audit_visits.compare(audit_visits.from_counts(counts),
                             counts.get("ours_label", Counter()), figures, same)
    if row[3]:                           # day extras counted (schema 9)
        _compare_extras(db, key, day, figures, same, problems, window)
    return problems, compared


def _compare_extras(db, key, day: date, figures: dict, same, problems: list,
                    window: int = 30) -> None:
    import json
    stored = {kind: json.loads(data) for kind, data in db.execute(
        "SELECT kind, data FROM day_extras WHERE site = ? AND day = ?", key)}
    visitors = None
    if figures["extras"]["visitors"] is not None and "::" not in key[0]:
        visitors = {(v, k): n for v, k, n in db.execute(
            "SELECT visitor, kind, n FROM visitor_days WHERE site = ? AND day = ?", key)}
        # Returning readers: visits whose hash history holds on an earlier day
        # within the window (30 days unless visitors.repeat_days says).
        first = (day - timedelta(days=window - 1)).isoformat()
        earlier = {v for (v,) in db.execute(
            "SELECT DISTINCT visitor FROM visitor_days WHERE site = ? AND day >= ? AND "
            "day < ?", (key[0], first, key[1]))}
        counted = sum(n for (v, k), n in figures["extras"]["visitors"].items()
                      if k == "reader" and v in earlier)
        same("returning readers", int((stored.get("returning") or {}).get("returning", 0)),
             counted)
        for r in figures["more"].each:   # by this visit's source (audit_engagement.py)
            getattr(r, "returning", lambda *a: None)(stored.get("returning"), earlier, same, problems)
    audit_extras.compare(stored, visitors, figures["extras"], same, problems)
    audit_visits.compare_pages(stored.get("pages"), figures["journeys"], same)
    if "bots" in stored or "quality" in stored:          # collected by release 2
        audit_release2.compare(stored, figures["bots"], figures["quality"], same, problems)
        audit_release2.compare_cube(stored, figures["by"], figures["readers"], same, problems)
        audit_release2.compare_visit_cube(stored, figures["by"], figures["readers"], same,
                                          problems)
        audit_release2.compare_firsts(stored, figures["page_firsts"], same, problems)
        audit_release2.compare_crawler_paths(stored, figures["bots"]["crawler_paths"], same,
                                             problems)
    figures["more"].compare(stored, same, problems)      # phase 4 (audit_more.py)


def _compare_dim(name: str, stored: Counter, counted: Counter, readers: int,
                 same, problems: list[str]) -> None:
    """Every label the stored list kept, exactly; its folded tail against
    the recount's remainder; and the list against its own readers."""
    if sum(stored.values()) != readers:
        problems.append(f"readers by {name}: the stored rows sum to "
                        f"{sum(stored.values()):,}, not their own {readers:,} readers")
    kept = [label for label in stored if label != OTHER]
    for label in sorted(kept):
        same(f"readers by {name}: {label}", stored[label], counted.get(label, 0))
    rest = sum(counted.values()) - sum(counted.get(label, 0) for label in kept)
    same(f"readers by {name}: {OTHER}", stored.get(OTHER, 0), rest)


def compare_live(figures: dict, snap: dict) -> tuple[list[str], int]:
    """(mismatches, figures compared) against today's live snapshot, counted
    over the same window (midnight to the snapshot's own time)."""
    if snap.get("state") != "ok":
        return [f"the live snapshot is {snap.get('state')}; nothing to compare"], 0
    problems: list[str] = []
    compared = 0

    def same(what: str, stored, counted) -> None:
        nonlocal compared
        compared += 1
        if stored != counted:
            problems.append(f"{what}: the snapshot has {stored:,}, the recount "
                            f"finds {counted:,}")

    same("requests for this site", snap.get("requests", 0), figures["requests"])
    for g in GROUPS:
        same(f"{g}: requests", (snap.get("groups") or {}).get(g, 0), figures["groups"][g])
    people = snap.get("people") or {}
    same("people: visits", people.get("visits", 0), figures["visits"])
    same("people: readers", people.get("readers", 0), figures["readers"])
    b = snap.get("breakdowns")
    if not b:
        return problems + ["the snapshot predates the breakdowns"], compared
    for g in GROUPS:
        stored = Counter((b.get("statuses") or {}).get(g) or {})
        for status in sorted(set(stored) | set(figures["statuses"][g])):
            same(f"{g}: {status} responses", stored.get(status, 0),
                 figures["statuses"][g].get(status, 0))
        same(f"{g}: POST requests", ((b.get("posts") or {}).get(g) or {}).get("total", 0),
             figures["posts"][g])
    same("server errors (5xx)", sum((b.get("server_errors") or {}).values()),
         figures["server_errors"])
    for name in DIMS:
        _compare_dim(name, Counter((b.get("by") or {}).get(name) or {}),
                     figures["by"][name], people.get("readers", 0), same, problems)
    if snap.get("visits") is None:
        return problems + ["the snapshot predates visits"], compared
    audit_visits.compare(snap["visits"], Counter(snap.get("ours_labels") or {}),
                         figures, same)
    if snap.get("extras"):
        audit_extras.compare(snap["extras"], None, figures["extras"], same, problems)
        audit_visits.compare_pages(snap["extras"].get("pages"), figures["journeys"], same)
        if "bots" in snap["extras"]:
            audit_release2.compare(snap["extras"], figures["bots"], figures["quality"],
                                   same, problems)
            audit_release2.compare_visit_cube(snap["extras"], figures["by"],
                                              figures["readers"], same, problems)
            audit_release2.compare_firsts(snap["extras"], figures["page_firsts"], same,
                                          problems)
            audit_release2.compare_cube(snap["extras"], figures["by"], figures["readers"],
                                        same, problems)
            audit_release2.compare_crawler_paths(snap["extras"],
                                                 figures["bots"]["crawler_paths"], same, problems)
        # Real time (audit_realtime.py) is the snapshot's own part, not an extra.
        figures["more"].compare({**snap["extras"], "realtime": snap.get("realtime")},
                                same, problems)
    same("journeys in the snapshot", int(snap.get("journeys_total", 0)),
         figures["journeys"]["visits"])
    listed = snap.get("journeys") or []
    if len(listed) == int(snap.get("journeys_total", 0)):   # none cut off
        same("pages loaded in the journeys", sum(int(j.get("pages", 0)) for j in listed),
             figures["journey_pages"])
    return problems, compared
