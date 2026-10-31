"""Recent requests: every request of the last few hours, one row each.

The "Recent requests" tab. Each live run (every 2 minutes) keeps the
requests of the last `requests.window_hours` hours (6), newest first, at most
`requests.cap` rows (5,000): when, from where, what was asked and answered,
the group it was counted in and - in words - the rule that put it there,
whether it counted as a page view, the assistant, the campaign tags, the
crawler check and any warning flags (DATA-CONTRACT.md, requests.json).

The group and rule are the live tally's own verdict for the hit, taken as it
is counted (an observer on the same pass), so the feed cannot disagree with
the figures. Before 06:00 the window reaches into yesterday: that part is
classified the way the day's collect will see it - over yesterday's whole
window, so a browser that fetched robots.txt at 23:50 is a crawler from its
first request that day.

Privacy: the address is shown (the owner's decision, 2026-10-07) and lives
only here - the private file beside the history (`live-<site>-requests.json`,
0640) and the page's data/requests.json behind the password. It is never
stored in history, mailed or exported. The file holds its window and nothing
older. An address on the forget list (`skald forget`) is "(removed)". Query
values that could be personal are replaced by "…" (clean_query), and a path
segment holding an "@" is replaced too.
"""
from __future__ import annotations

import json
import os
import re
from collections import Counter, deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qsl, quote, urlsplit

from . import dimensions as dim
from .classify import (BROWSER, CRAWLER_PATH, CRAWLER_SESSION, LINK_PREVIEW, OTHER_BOT,
                       Group, Tier)
from .countries import NAMES
from .files import write_atomic
from .parse import ASSET, BEACON, OWN_ENDPOINT, RSC_PAYLOAD
from .visits import assistant_label   # "ChatGPT", not chatgpt.com

VERSION = 1
WINDOW_HOURS = 6
CAP = 5000
STALE_MINUTES = 10
EXCLUDED = "excluded"
REMOVED = "(removed)"

KIND_WORDS = {"page": "page view", "rsc": "Next.js payload (_rsc)", "asset": "asset",
              "beacon": "beacon", "crawler_file": "crawler file", "redirect": "redirect",
              "not_modified": "not modified (304)", "not_found": "not found",
              "client_error": "client error", "server_error": "server error",
              "post": "form post", "script_event": "script tag event",
              "skald_endpoint": "Skald endpoint", "other": "other",
              "page_script": "page's own script (not a form)",
              "refused_post": "POST the site refused (not a form)",
              "not_page": "not a page (a machine address)"}


def settings(config: dict) -> tuple[int, int]:
    raw = (config or {}).get("requests") or {}
    try:
        hours = max(1, min(24, int(raw.get("window_hours") or WINDOW_HOURS)))
        cap = max(100, min(50_000, int(raw.get("cap") or CAP)))
    except (TypeError, ValueError):
        hours, cap = WINDOW_HOURS, CAP
    return hours, cap


def path_for(directory: Path, site: str) -> Path:
    from .live import path_for as snapshot
    snap = Path(snapshot(directory, site))
    return snap.with_name(snap.stem + "-requests.json")


# ------------------------------------------------------------ one row

def kind_of(hit) -> str:
    status = hit.status
    if OWN_ENDPOINT.match(hit.path) and hit.method != "GET":
        # Skald's own endpoints (parse.OWN_ENDPOINT): the script tag posts
        # its events to /traffic-beacon or /traffic-js/; hooks and shipped
        # logs post to /traffic-hooks/ and /traffic-ingest/. None of them
        # is a form the site's visitor sent.
        return ("script_event" if hit.path.startswith(("/traffic-beacon", "/traffic-js/"))
                else "skald_endpoint")
    if hit.method == "POST":
        # A POST a page's own script sends by itself (form_names.py: a 204
        # with no body, a beacon on the list, the site's own list) is no form.
        if hit.script_post:
            return "page_script"
        # Refused (form_names.REFUSED): nothing at that address took it.
        return "post" if hit.is_form_post else "refused_post"
    if status[:1] == "5":
        return "server_error"
    if status in ("404", "410"):
        return "not_found"
    if status == "304":
        return "not_modified"
    if status[:1] == "3":
        return "redirect"
    if status[:1] == "4":
        return "client_error"
    if CRAWLER_PATH.search(hit.path):
        return "crawler_file"
    if hit.not_page_rule:
        # Shaped like a page, on the site's not-a-page list (not_pages.py).
        return "not_page"
    if RSC_PAYLOAD.search(hit.url):
        # A Next.js navigation on a log that records the prefetch header
        # is a page view (parse.Hit.soft_navigation); any other payload is not.
        return "page" if hit.is_page else "rsc"
    if ASSET.search(hit.path):
        return "asset"
    if BEACON.search(hit.path):
        return "beacon"
    return "page" if hit.is_page else "other"


# Query keys whose values are kept as they are: attribution and framework
# keys. Click ids are kept as present, never their value.
KEEP_KEYS = re.compile(r"^(?:utm_[a-z]+|ref|source|via|_rsc|lang|locale|hl|page|p|amp;[a-z_]+)$",
                       re.I)
CLICK_IDS = {"gclid", "gbraid", "wbraid", "msclkid", "fbclid", "li_fat_id", "ttclid", "twclid",
             "dclid", "yclid"}
PERSONAL = re.compile(r"@|\d{6,}|[A-Za-z0-9_-]{24,}|%40")


def clean_query(url: str) -> str:
    """The query with every value that could identify someone replaced.

    Attribution and framework keys keep their value (unless it holds an
    "@"); click ids show as "(id)"; any other value is kept only when it is
    short and plain - no "@", no run of 6 digits, no long token."""
    if "?" not in url:
        return ""
    try:
        pairs = parse_qsl(url.split("?", 1)[1], keep_blank_values=True)[:30]
    except ValueError:
        return "…"
    out = []
    for key, value in pairs:
        low = key.lower()
        if low in CLICK_IDS:
            value = "(id)"
        elif KEEP_KEYS.match(low):
            value = "…" if ("@" in value or "%40" in value) else value[:60]
        elif len(value) > 32 or PERSONAL.search(value):
            value = "…"
        key = "…" if PERSONAL.search(key) else key[:40]
        out.append(f"{key}={value if value in ('…', '(id)') else quote(value, safe='/:,()_-.')}")
    return "&".join(out)[:300]


def clean_path(path: str) -> str:
    if "@" in path or "%40" in path:
        path = "/".join("…" if ("@" in seg or "%40" in seg) else seg for seg in path.split("/"))
    return path[:300]


def _referrer(referrer: str) -> tuple[str, str]:
    if not referrer:
        return "", ""
    first = referrer.split(",", 1)[0].strip()
    try:
        parts = urlsplit(first if "//" in first else "//" + first)
        return (parts.hostname or "")[:100], clean_path(parts.path or "")[:200]
    except ValueError:
        return "", ""


def _agent(hit, verdict) -> str:
    from .aggregate import _short_agent
    agent = hit.user_agent
    if verdict is not None and verdict.group in (Group.ANSWER_ENGINE, Group.SEARCH_ENGINE):
        return verdict.engine
    if verdict is not None and verdict.claim:
        return verdict.claim
    if agent and BROWSER.search(agent) and not OTHER_BOT.search(agent):
        return dim.browser(agent)
    return _short_agent(agent)


def rule_of(hit, verdict, kind: str, role: tuple | None = None) -> str:
    """The rule in words. `role`: an assistant's user fetch's (role, page)
    from ai_reads.Roles - a file its page loaded is never "AI asked"."""
    if verdict is None:
        return "excluded: other host"
    group = verdict.group
    if group is Group.OURS:
        return f"ours: {verdict.engine or 'listed'}"
    if group is Group.ANSWER_ENGINE:
        tier = verdict.tier.value if verdict.tier else "fetch"
        if role and role[0] == "file":
            return (f"AI page file: {verdict.engine}, loaded by {role[1]}" if role[1]
                    else f"AI page file: {verdict.engine}")
        if role and role[0] == "repeat":
            return f"AI {tier}: {verdict.engine}, the same read again"
        return f"AI {tier}: {verdict.engine}"
    if group is Group.SEARCH_ENGINE:
        return f"search: {verdict.engine}"
    if group is Group.BOTS:
        if verdict.probe and not verdict.engine:
            return "bot: scanner probe"
        if verdict.engine == CRAWLER_SESSION:
            return "bot: browser-like crawler (robots.txt or sitemap, no rendering)"
        if verdict.engine:
            return f"bot: {verdict.engine}"
        from .aggregate import _short_agent
        return f"bot: {_short_agent(hit.user_agent)}"
    words = KIND_WORDS["page"] if hit.is_page else KIND_WORDS.get(kind, kind)
    if verdict.tier is Tier.CITED:
        return f"people: {words} from {assistant_label(verdict.engine)}"
    return f"people: {words}"


def row(hit, verdict, tz, hidden, duplicate: bool, source: str = "",
        role: tuple | None = None) -> dict:
    when = hit.when if hit.when.tzinfo else hit.when.replace(tzinfo=timezone.utc)
    kind = kind_of(hit)
    ref_host, ref_path = _referrer(hit.referrer)
    browser, system, device = dim.agent_labels(hit.user_agent)
    cc = (hit.country or "").upper()
    tags = dim.query(hit.url)
    utm = {k: " ".join(tags[f"utm_{k}"].split())[:60] for k in
           ("source", "medium", "campaign", "term", "content") if tags.get(f"utm_{k}", "").strip()}
    flags = list(verdict.flags) if verdict is not None else []
    if verdict is not None and verdict.probe:
        flags.append("probe")
    if verdict is not None and verdict.legacy:
        flags.append("legacy_path")
    if hit.fmt in ("nginx_combined", "apache_combined"):
        flags.append("old_format")
    if duplicate:
        flags.append("duplicate")
    group = verdict.group.value if verdict is not None else EXCLUDED
    assistant = ""
    if verdict is not None and (verdict.group is Group.ANSWER_ENGINE
                                or verdict.tier is Tier.CITED):
        assistant = verdict.engine
    out = {
        "at": when.astimezone(tz).isoformat(timespec="seconds"),
        "ip": REMOVED if hidden(hit.address) else hit.address,
        "country": cc, "country_name": NAMES.get(cc, ""),
        "host": hit.host[:100], "method": hit.method[:10],
        "path": clean_path(hit.path), "query": clean_query(hit.url),
        "status": int(hit.status) if hit.status.isdigit() else 0,
        "bytes": hit.size,
        "ms": int(round(hit.request_time * 1000)) if hit.request_time is not None else None,
        "ref_host": ref_host, "ref_path": ref_path,
        "agent": _agent(hit, verdict), "os": system, "device": device,
        "group": group, "rule": rule_of(hit, verdict, kind, role), "kind": kind,
        "page_view": bool(verdict is not None and hit.is_page),
        "assistant": assistant, "source": source, "utm": utm,
        "verified": verdict.verified if verdict is not None else None,
        "flags": flags,
    }
    if kind == "not_page":
        out["not_page"] = hit.not_page_rule         # the entry (not_pages.py)
    if role:
        # An assistant's user fetch: "read", "repeat" (the same read asked
        # again) or "file" (a file its page loaded), and the read's page.
        out["ai_role"], out["ai_of"] = role[0], role[1]
    return out


# ------------------------------------------------------------- the feed

class Feed:
    """Collects the window's requests as they are counted. Call it as the
    tally's observer (hit, verdict); `excluded(hit)` for another host."""

    def __init__(self, cutoff: datetime, cap: int, views=(), heartbeat: str = "heartbeat",
                 own_hosts=(), gap_minutes: int = 30, prefixes=None) -> None:
        self.cutoff = cutoff
        # Each user fetch's role (ai_reads.py): seen from before the cutoff
        # too, so a read that began just before it is still one read.
        from .ai_reads import Roles
        self.roles = Roles(prefixes) if prefixes is not None else Roles()
        # People's visits as the feed sees them, for each row's `source`:
        # the source of the visit's first page view (as journeys label it),
        # or of its first request until a page is read. A page from a new
        # outside source starts a new visit, as in the journeys.
        self.own = {h.lower() for h in own_hosts}
        self.gap = timedelta(minutes=gap_minutes)
        self.visits: dict[tuple[str, str], dict] = {}
        # What the alert check reads (alerts.py): per minute, all requests,
        # 5xx, people's 404s and each crawler or bot by name; the heartbeat's
        # beats; the newest line seen.
        self.minutes: dict[int, Counter] = {}
        self.beats: list = []
        self.newest: datetime | None = None
        self.heartbeat = heartbeat
        self.rows: deque = deque(maxlen=cap)
        self.total = 0
        self.by_group: Counter = Counter()
        self.views = list(views)
        self.by_view: dict[str, Counter] = {v.slug: Counter() for v in self.views}
        from .quality import Duplicates
        self.dups = Duplicates()

    def _take(self, hit, verdict) -> None:
        when = hit.when if hit.when.tzinfo else hit.when.replace(tzinfo=timezone.utc)
        duplicate = self.dups.seen(hit)
        visit = self._visit(hit, verdict, when)
        role = None
        if verdict is not None and verdict.group is Group.ANSWER_ENGINE \
                and verdict.tier is Tier.ASKED:
            role = self.roles(verdict.engine or "", hit.path, hit.url, hit.referrer,
                              hit.host, hit.when)
        if self.newest is None or when > self.newest:
            self.newest = when
        if when < self.cutoff:
            return
        group = verdict.group.value if verdict is not None else EXCLUDED
        self._signal(hit, verdict, when)
        self.total += 1
        self.by_group[group] += 1
        for v in self.views:
            if v.matches(hit.path):
                self.by_view[v.slug][group] += 1
        self.rows.append((hit, verdict, duplicate, visit, role))

    def _visit(self, hit, verdict, when: datetime) -> dict | None:
        if verdict is None or verdict.group is not Group.PEOPLE:
            return None
        key = (hit.address, hit.user_agent)
        visit = self.visits.get(key)
        own = self.own or ({hit.host.lower()} if hit.host else set())
        cited = verdict.tier is Tier.CITED
        source = dim.source_type(hit.referrer, hit.url, cited, own)
        page = dim.page_origin(hit.referrer, hit.url, cited, own) if hit.is_page else None
        # The visits' own rule (aggregate._Sessions): the gap, or a page from
        # a new outside source.
        if (visit is None or when - visit["last"] > self.gap
                or dim.new_source(page, visit["origin"])):
            visit = self.visits[key] = {"last": when, "source": source, "page": hit.is_page,
                                        "origin": page}
        elif not visit["page"] and hit.is_page:
            visit.update(source=source, page=True, origin=page)
        visit["last"] = max(visit["last"], when)
        return visit

    def _signal(self, hit, verdict, when: datetime) -> None:
        minute = self.minutes.setdefault(int(when.timestamp()) // 60, Counter())
        minute["all"] += 1
        if hit.status[:1] == "5":
            minute["5xx"] += 1
        if verdict is None:
            return
        if verdict.group is Group.PEOPLE and hit.status == "404":
            minute["people_404"] += 1
        elif verdict.group is Group.OURS:
            if verdict.engine == self.heartbeat:
                self.beats.append((when, hit.status[:1] in ("2", "3")))
        elif verdict.group is not Group.PEOPLE:
            name = verdict.claim or verdict.engine or _agent(hit, verdict)
            minute["name:" + name[:60]] += 1

    def signals(self) -> dict:
        return {"minutes": self.minutes, "beats": sorted(self.beats, key=lambda b: b[0]),
                "newest": self.newest, "since": self.cutoff}

    def __call__(self, hit, verdict) -> None:
        self._take(hit, verdict)

    def excluded(self, hit) -> None:
        self._take(hit, None)

    def result(self, tz, hidden, start: datetime, until: datetime, hours: int,
               cap: int, generated_at: str, read_upto: dict | None = None) -> dict:
        ordered = sorted(self.rows, key=lambda r: r[0].when if r[0].when.tzinfo
                         else r[0].when.replace(tzinfo=timezone.utc), reverse=True)
        return {"version": VERSION, "generated_at": generated_at,
                "from": start.astimezone(tz).isoformat(timespec="seconds"),
                "until": until.astimezone(tz).isoformat(timespec="seconds"),
                "window_hours": hours, "cap": cap, "total": self.total,
                # How far each plain log file was read (parse.sizes), for the audit.
                **({"read_upto": dict(read_upto)} if read_upto is not None else {}),
                "by_group": dict(self.by_group),
                "by_view": {slug: {"total": sum(c.values()), "by_group": dict(c)}
                            for slug, c in self.by_view.items()},
                "rows": [row(h, v, tz, hidden, d, visit["source"] if visit else "", role)
                         for h, v, d, visit, role in ordered]}


def before_midnight(config: dict, feed: Feed, midnight: datetime, now: datetime,
                    upto: dict | None = None) -> None:
    """Feed the part of the window before today's midnight, classified over
    yesterday's whole window (as collect will). `upto`: the live run's byte
    limits (parse.read)."""
    from .config import setting
    from .parse import geo_database, one_click, read
    from .window import ordered_classifier, within, window_paths
    if feed.cutoff >= midnight:
        return
    start = midnight - timedelta(hours=26)       # yesterday's start, DST or not
    paths = window_paths(config, start, midnight, now)
    if not paths:
        return
    from .parse import oldest_first
    paths = oldest_first(paths)
    fmt = (config.get("logs") or {}).get("format") or "auto"
    tz_day_start = _day_start(config, midnight)
    from .not_pages import from_config
    rules = from_config(config)
    classifier, _ = ordered_classifier(
        config, lambda: within(read(paths, fmt, upto=upto, page_rules=rules), tz_day_start,
                               midnight),
        tz_day_start, midnight)
    wanted = {str(h).lower() for h in (setting(config, "site", "hosts") or [])}
    for hit in one_click(within(read(paths, fmt, geo=geo_database(config), upto=upto,
                                     page_rules=rules), feed.cutoff, midnight)):
        if wanted and hit.host and hit.host.lower() not in wanted:
            feed.excluded(hit)
        else:
            feed(hit, classifier(hit))


def _day_start(config: dict, midnight: datetime) -> datetime:
    from .window import day_window, zone
    tz = zone(config)
    day = (midnight.astimezone(tz) - timedelta(hours=1)).date()
    return day_window(day, tz)[0]


def save(path: Path, data: dict) -> None:
    write_atomic(Path(path), json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n")
    os.chmod(path, 0o640)


def load(path: Path) -> dict | None:
    try:
        got = json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return None
    return got if isinstance(got, dict) and got.get("version") == VERSION else None


# ------------------------------------------------------------ requests.json

def build(p) -> dict:
    hours, cap = settings(p.config)
    empty = {"state": "empty", "window_hours": hours, "cap": cap, "from": None, "until": None,
             "total": 0, "shown": 0, "truncated": False, "by_group": {}, "rows": []}
    if p.live_dir is None:
        return empty
    got = load(path_for(p.live_dir, p.site))
    if not got:
        return empty
    rows = got.get("rows") or []
    total, by_group = got.get("total", 0), got.get("by_group") or {}
    if p.view is not None:
        rows = [r for r in rows if p.view.matches(r.get("path", ""))]
        part = (got.get("by_view") or {}).get(p.view.slug) or {"total": len(rows),
                                                                "by_group": {}}
        total, by_group = part["total"], part["by_group"]
    state = "ok" if rows or total else "empty"
    try:
        made = datetime.fromisoformat(got["generated_at"])
        if p.now - made > timedelta(minutes=STALE_MINUTES):
            state = "stale"
    except (KeyError, TypeError, ValueError):
        state = "stale"
    return {"state": state, "window_hours": got.get("window_hours", hours),
            "cap": got.get("cap", cap), "from": got.get("from"), "until": got.get("until"),
            "total": int(total), "shown": len(rows), "truncated": int(total) > len(rows),
            "by_group": by_group, "rows": rows}
