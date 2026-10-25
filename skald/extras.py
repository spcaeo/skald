"""Day figures beyond the cards: hours, our own health, 404s, pages, campaigns.

Built in the same single pass as everything else (aggregate.Tally offers
every counted hit here), finished into plain JSON-ready blobs that history
keeps per day (store_extras, schema 9), the live snapshot carries, and
DATA-CONTRACT.md describes:

  hourly     requests per group per hour, readers (by first page), AI fetches
             to train and for a live question, 5xx - each group's hours add
             up to its day total
  ours       our own traffic by label, the heartbeat (answered or not, the
             gaps between beats), and per hour the server time of every
             request to the site (p50 and p95, ms) and its 5xx
  not_found  every 404 and 410: path, status, who asked (group, AI tier),
             scanner probe or not, where it was linked from, utm_source,
             how many, first and last time
  pages      per page: page views, readers, visits, entries, exits, pages
             after landing, time on page (estimate), 404s and posts made
             from it, AI fetches by tier, search crawls, and the sources,
             assistants and countries of its readers
  campaigns  campaigns.aggregate over the day's journeys
  ...        and the later kinds registered in day_more.py

`check()` holds every sum the contract promises; verify.check runs it.
"""
from __future__ import annotations

from collections import Counter
from datetime import timezone

from . import dimensions as dim
from .classify import AI_REFERRER_HOSTS, Group, assistant_name
from .parse import ASSET

GROUP_KEYS = [g.value for g in Group]
HOUR_KEYS = GROUP_KEYS + ["readers", "ai_asked", "ai_training", "server_errors"]
SEARCH_NAMES = (("google.", "Google"), ("bing.com", "Bing"), ("duckduckgo.com", "DuckDuckGo"),
                ("yahoo.", "Yahoo"), ("yandex.", "Yandex"), ("baidu.com", "Baidu"),
                ("ecosia.org", "Ecosia"), ("search.brave.com", "Brave Search"))


def nf_group(verdict) -> str:
    """Who asked, for the 404 report: a group, AI split by tier."""
    if verdict.group is Group.ANSWER_ENGINE:
        return "ai_asked" if verdict.tier and verdict.tier.value == "asked" else "ai_training"
    return verdict.group.value


def referrer_source(referrer: str, own: set[str]) -> tuple[str, str]:
    """(label, kind) of where a request was linked from: an assistant by its
    domain, a search engine by name, a host, "(this site)" or "(none)"."""
    host = dim.referrer_host(referrer)
    if not host:
        return "(none)", "Direct or unknown"
    if host in own or "www." + host in own:
        return "(this site)", "This site"
    for domain in AI_REFERRER_HOSTS:
        if host == domain or host.endswith("." + domain):
            return assistant_name(domain), "AI assistant"
    kind = dim.source_type(referrer, "", False, own)
    if kind == "Search engine":
        for token, name in SEARCH_NAMES:
            if token in host:
                return name, kind
    return host[:60], kind


def _pct(values: list[int], q: float) -> int | None:
    if not values:
        return None
    values = sorted(values)
    return values[min(len(values) - 1, int(q * len(values)))]


class Extras:
    def __init__(self, tz=None, own_hosts: set[str] | None = None,
                 heartbeat: str = "heartbeat", gap_minutes: int = 30) -> None:
        self.tz = tz
        self.own_hosts = own_hosts or set()
        self.heartbeat = heartbeat
        self.hours: dict[str, Counter] = {}
        self.ms: dict[str, list[int]] = {}
        self.beats: list = []                     # (when, ok)
        self.nf: dict[tuple, list] = {}           # key -> [n, first, last]
        self.page_hits: dict[str, Counter] = {}
        from .bot_counts import BotCounts
        self.bots = BotCounts(gap_minutes)
        from .robots import CrawlerPaths
        self.crawler_paths = CrawlerPaths()
        # What each crawler, assistant and bot cost the server (crawler_cost.py).
        from .crawler_cost import Costs
        self.crawler_cost = Costs()
        # Each crawler beside the site's sitemap, and the problems crawlers
        # hit (crawl_health.py). The whole site's tally only: None for a view.
        from .crawl_health import Collector
        self.crawl_health = Collector()
        # What AI crawlers and assistants got back, by address (ai_status.py,
        # AI readiness). The whole site's tally only: None for a view.
        from .ai_status import Collector as AiStatus
        self.ai_status = AiStatus()
        # Scanners, exposures, attack attempts and fake browsers (security.py):
        # a view across the groups. The whole site's tally only: None for a view.
        from .security import Collector as Security
        self.security = Security()
        # The same hourly figures keyed by the UTC hour they started
        # ("YYYY-MM-DDTHH"), so a reader's chosen zone can re-bucket them
        # exactly - the day the clocks go back has two local 01:00 hours.
        self.hours_utc: dict[str, Counter] = {}
        # Each page's first times today, by kind (lifecycle.py): Googlebot,
        # Bingbot, each AI crawler or assistant, the first person, the first
        # from a search engine and from each AI assistant.
        self.firsts: dict[str, dict] = {}
        # AI user fetches by minute (ai_likely.py); its settings and the
        # visits' first times are set by aggregate.Tally.
        from .ai_likely import Fetches
        self.ai_fetches = Fetches()
        # Every AI fetch by what it asked for (ai_formats.py).
        from .ai_formats import Formats
        self.ai_formats = Formats()
        self.attribution: dict | None = None
        self.visit_firsts: list | None = None
        # Link-preview fetches by minute and page (direct_likely.py); its
        # settings and the visits' landing addresses are set by aggregate.Tally.
        from .direct_likely import Previews
        self.link_previews = Previews()
        self.direct_likely: dict | None = None
        self.visit_landings: list | None = None

    def _page(self, path: str) -> Counter:
        got = self.page_hits.get(path)
        if got is None:
            got = self.page_hits[path] = Counter()
        return got

    def _first(self, path: str, key: str, when, who: str = "") -> None:
        got = self.firsts.setdefault(path, {})
        iso = _utc_iso(when)
        old = got.get(key)
        if old is None or iso < old[0]:
            got[key] = [iso, who]

    def firsts_of(self, hit, verdict) -> None:
        """The page first-times this page view sets (lifecycle.py)."""
        if not hit.is_page:
            return
        path, group = hit.path[:70], verdict.group
        if group is Group.SEARCH_ENGINE and verdict.engine:
            low = verdict.engine.lower()
            if low in ("googlebot", "bingbot"):
                self._first(path, low, hit.when)
        elif group is Group.ANSWER_ENGINE and verdict.tier and verdict.engine:
            self._first(path, f"ai_{verdict.tier.value}|{verdict.engine}", hit.when,
                        verdict.engine)
        elif group is Group.PEOPLE:
            self._first(path, "human", hit.when)
            if verdict.tier is not None and verdict.tier.value == "cited":
                self._first(path, f"from_ai|{verdict.engine}", hit.when, verdict.engine)
            own = self.own_hosts or ({hit.host.lower()} if hit.host else set())
            if dim.source_type(hit.referrer, hit.url, False, own) == "Search engine":
                self._first(path, "from_search", hit.when, dim.referrer_host(hit.referrer)[:60])

    def add(self, hit, verdict) -> None:
        self.bots.add(hit, verdict)
        self.ai_fetches.add(hit, verdict)
        self.link_previews.add(hit, verdict)
        self.ai_formats.add(hit, verdict)
        self.firsts_of(hit, verdict)
        self.crawler_paths.add(hit, verdict)
        self.crawler_cost.add(hit, verdict)
        if self.crawl_health is not None:
            self.crawl_health.add(hit, verdict)
        if self.ai_status is not None:
            self.ai_status.add(hit, verdict)
        if self.security is not None:
            self.security.add(hit, verdict)
        hour = dim.hour(hit.when, self.tz)
        row = self.hours.get(hour)
        if row is None:
            row = self.hours[hour] = Counter()
        utc = self.hours_utc.setdefault(utc_hour(hit.when), Counter())
        row[verdict.group.value] += 1
        utc[verdict.group.value] += 1
        status = hit.status
        if verdict.group is Group.ANSWER_ENGINE and verdict.tier:
            row["ai_" + verdict.tier.value] += 1
            utc["ai_" + verdict.tier.value] += 1
        if status[:1] == "5":
            row["server_errors"] += 1
            utc["server_errors"] += 1
        if hit.request_time is not None:
            self.ms.setdefault(hour, []).append(int(round(hit.request_time * 1000)))
        if verdict.group is Group.OURS and verdict.engine == self.heartbeat:
            self.beats.append((hit.when, status[:1] in ("2", "3")))
        own = self.own_hosts or ({hit.host.lower()} if hit.host else set())
        if status in ("404", "410"):
            source, kind = referrer_source(hit.referrer, own)
            utm = (dim.query(hit.url).get("utm_source") or "").strip().lower()[:40]
            key = (hit.path[:100], int(status), nf_group(verdict), bool(verdict.probe),
                   source, kind, utm)
            got = self.nf.get(key)
            if got is None:
                self.nf[key] = [1, hit.when, hit.when]
            else:
                got[0] += 1
                got[1] = min(got[1], hit.when)
                got[2] = max(got[2], hit.when)
        if hit.is_page:
            path = hit.path[:70]
            if verdict.group is Group.PEOPLE:
                self._page(path)["views"] += 1
            elif verdict.group is Group.ANSWER_ENGINE and verdict.tier:
                self._page(path)["ai_" + verdict.tier.value] += 1
            elif verdict.group is Group.SEARCH_ENGINE:
                self._page(path)["search"] += 1
        if verdict.group is Group.PEOPLE and (
                (status == "404" and not ASSET.search(hit.path) and hit.method != "POST")
                or hit.is_form_post):
            # A form post, not the script tag's events to Skald's own
            # endpoints (parse.OWN_ENDPOINT), which every page sends.
            from .visits import _same_site_path
            origin = _same_site_path(hit.referrer, own)
            if origin:
                self._page(origin)["posts_from" if hit.is_form_post else "not_found_from"] += 1

    def reader(self, when) -> None:
        """A reader's first page view (aggregate.Tally), by its UTC hour."""
        self.hours_utc.setdefault(utc_hour(when), Counter())["readers"] += 1

    def _local(self, when) -> str:
        when = when if when.tzinfo else when.replace(tzinfo=timezone.utc)
        return (when.astimezone(self.tz) if self.tz else when).strftime("%H:%M")

    def finish(self, totals, journeys: list[dict], page_visits: dict[str, dict],
               readers_by_hour) -> dict:
        from .campaigns import aggregate
        from .cube import rows as cube_rows
        hourly = {}
        for hour in sorted(set(self.hours) | set(readers_by_hour or {})):
            row = self.hours.get(hour, Counter())
            hourly[hour] = {k: int(row.get(k, 0)) for k in HOUR_KEYS}
            hourly[hour]["readers"] = int((readers_by_hour or {}).get(hour, 0))
        hours_ours = {}
        beats_by_hour: dict[str, Counter] = {}
        for when, ok in self.beats:
            beats_by_hour.setdefault(dim.hour(when, self.tz), Counter())["ok" if ok else "failed"] += 1
        for hour in sorted(set(self.hours) | set(beats_by_hour)):
            ms = self.ms.get(hour, [])
            row = self.hours.get(hour, Counter())
            hours_ours[hour] = {
                "requests": int(sum(row.get(g, 0) for g in GROUP_KEYS)),
                "p50_ms": _pct(ms, 0.5), "p95_ms": _pct(ms, 0.95),
                "server_errors": int(row.get("server_errors", 0)),
                "heartbeat_ok": int(beats_by_hour.get(hour, {}).get("ok", 0)),
                "heartbeat_failed": int(beats_by_hour.get(hour, {}).get("failed", 0)),
            }
        beats = sorted(self.beats, key=lambda b: b[0])
        gaps = []
        for (a, _), (b, _) in zip(beats, beats[1:]):
            minutes = (b - a).total_seconds() / 60
            if minutes > 10:
                gaps.append({"from": self._local(a), "to": self._local(b),
                             "minutes": int(round(minutes))})
        ours = {
            "labels": dict(totals.ours_labels or {}),
            "hours": hours_ours,
            "heartbeat": {"seen": len(beats), "ok": sum(1 for _, ok in beats if ok),
                          "failed": sum(1 for _, ok in beats if not ok),
                          "first": self._local(beats[0][0]) if beats else None,
                          "last": self._local(beats[-1][0]) if beats else None,
                          "last_ok_at": next((_iso(w) for w, ok in reversed(beats) if ok),
                                             None),
                          "gaps": gaps},
        }
        nf_rows = [{"path": k[0], "status": k[1], "group": k[2], "probe": k[3],
                    "source": k[4], "source_kind": k[5], "utm_source": k[6], "n": v[0],
                    "first": self._local(v[1]), "last": self._local(v[2])}
                   for k, v in self.nf.items()]
        nf_rows.sort(key=lambda r: (-r["n"], r["path"]))
        pages = {}
        for path in set(self.page_hits) | set(page_visits):
            hits = self.page_hits.get(path, Counter())
            vis = page_visits.get(path, {})
            pages[path] = {
                "views": int(hits.get("views", 0)),
                **{k: int(vis.get(k, 0)) for k in ("readers", "visits", "entries", "exits",
                                                  "after_pages")},
                **{k: int(hits.get(k, 0)) for k in ("not_found_from", "posts_from",
                                                   "ai_asked", "ai_training", "search")},
                **{k: dict(vis.get(k) or {}) for k in ("time", "sources", "assistants",
                                                      "countries")},
            }
        out = {"hourly": hourly, "ours": ours, "not_found": nf_rows, "pages": pages,
                "campaigns": aggregate(journeys), "bots": self.bots.finish(),
                "cube": cube_rows(journeys), "page_firsts": self.firsts,
                # The same pages, compact, for the compare report over a year:
                # {path: [views, readers, ai_asked, ai_training, search]}.
                "page_counts": {p: [v["views"], v["readers"], v["ai_asked"], v["ai_training"],
                                    v["search"]] for p, v in pages.items()}, "crawler_paths": self.crawler_paths.finish(),
                "hourly_utc": {h: {k: int(c.get(k, 0)) for k in HOUR_KEYS}
                               for h, c in sorted(self.hours_utc.items())}}
        from . import day_more          # the later kinds (funnels, engagement, ...)
        day_more.finish(self, totals, journeys, page_visits, readers_by_hour, out)
        return out


def _utc_iso(when) -> str:
    when = when if when.tzinfo else when.replace(tzinfo=timezone.utc)
    return when.astimezone(timezone.utc).isoformat(timespec="seconds")


def utc_hour(when) -> str:
    when = when if when.tzinfo else when.replace(tzinfo=timezone.utc)
    return when.astimezone(timezone.utc).strftime("%Y-%m-%dT%H")


def _iso(when) -> str:
    when = when if when.tzinfo else when.replace(tzinfo=timezone.utc)
    return when.isoformat(timespec="seconds")


def check(totals) -> list:
    """Every sum the data contract promises for a day's extras."""
    from .verify import Problem
    ex = getattr(totals, "extras", None)
    problems: list = []
    if not ex:
        return problems

    def differs(what, got, want, of):
        if got != want:
            problems.append(Problem(f"{what} does not sum",
                                    f"{got:,} against {want:,} {of} - off by {got - want:+,}"))

    hourly = ex.get("hourly") or {}
    for g in Group:
        stats = totals.groups.get(g)
        differs(f"{g.value}: requests by hour", sum(h.get(g.value, 0) for h in hourly.values()),
                stats.hits if stats else 0, "requests")
    engines = totals.groups.get(Group.ANSWER_ENGINE)
    for tier in ("asked", "training"):
        differs(f"AI fetches ({tier}) by hour", sum(h.get("ai_" + tier, 0) for h in hourly.values()),
                int(engines.tiers.get(tier, 0)) if engines else 0, "fetches")
    people = totals.groups.get(Group.PEOPLE)
    if people is not None and people.readers is not None:
        differs("readers by hour", sum(h.get("readers", 0) for h in hourly.values()),
                people.readers, "readers")
    utc = ex.get("hourly_utc")
    if utc is not None:
        for key in HOUR_KEYS:
            differs(f"{key} by UTC hour", sum(h.get(key, 0) for h in utc.values()),
                    sum(h.get(key, 0) for h in hourly.values()), "by local hour")
    if totals.breakdowns:
        errors = sum(int(s.statuses.get("5xx", 0)) for s in totals.groups.values())
        differs("server errors by hour", sum(h.get("server_errors", 0) for h in hourly.values()),
                errors, "5xx responses")
        nf = ex.get("not_found") or []
        differs("people's 404s by path", sum(r["n"] for r in nf
                                             if r["group"] == "people" and r["status"] == 404),
                int(people.statuses.get("404", 0)) if people else 0, "404s seen by people")
        differs("404s by path", sum(r["n"] for r in nf if r["status"] == 404),
                sum(int(s.statuses.get("404", 0)) for s in totals.groups.values()), "404s")
    from . import bot_counts, cube, quality
    bot_counts.check(totals, ex.get("bots"), differs, problems)
    cube.check(totals, ex.get("cube"), differs, problems)
    cube.visit_check(totals, ex.get("visit_cube"), differs, problems)
    from . import robots
    robots.check(totals, ex.get("crawler_paths"), problems)
    problems += quality.check(ex.get("quality"), totals.parsed)
    from . import day_more
    day_more.check(totals, ex, differs, problems)
    ours = ex.get("ours") or {}
    differs("requests by hour (server time)",
            sum(h["requests"] for h in (ours.get("hours") or {}).values()),
            sum(s.hits for s in totals.groups.values()), "requests in the groups")
    pages = ex.get("pages") or {}
    if people is not None:
        differs("page views by page", sum(p["views"] for p in pages.values()), people.views,
                "page views by people")
    stats = getattr(totals, "visits", None)
    if stats is not None:
        differs("entries by page", sum(p["entries"] for p in pages.values()), stats.visits, "visits")
        differs("exits by page", sum(p["exits"] for p in pages.values()), stats.visits, "visits")
        camp = ex.get("campaigns") or {}
        for d, rows in (camp.get("rows") or {}).items():
            differs(f"visits by {d}", sum(r["visits"] for r in rows), stats.visits, "visits")
        if camp.get("tagged", 0) > stats.visits:
            problems.append(Problem("tagged visits", "more than the visits"))
    return problems
