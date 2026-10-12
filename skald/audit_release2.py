"""The audit's own recount of release 2: crawler checks, link previews, fake
browsers, and data quality.

Part of audit.py's second road. Nothing here calls bot_verify, bot_counts,
quality or the classifier: the stored lists and DNS answers are read again
with their own code, membership is tested with ipaddress networks one by one
(not the merged, bisected ranges bot_verify uses), the fan-out burst is
found with a forward window from each request (bot_verify's FanOut slides a
window back from each), and duplicates are found by comparing the raw text
of each line. What is shared is data only: the vendor tables (which names
belong to whom and which lists or DNS names prove it) and the link-preview
name list, as the audit already shares the crawler name lists.
"""
from __future__ import annotations

import bisect
import gzip
import ipaddress
import json
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .bot_policy import match as policy_match
from .bot_verify import CLAIMS, LOCAL_TOOL, MAX_LIST_AGE, VENDORS
from .classify import LINK_PREVIEWS, OTHER_BOT

FLAGS = ("hosting_network", "fan_out", "bare_mozilla")
_BROWSERISH = re.compile(r"Mozilla/|Opera/|Safari/|Chrome/|Firefox/", re.I)


def _vendor(name: str):
    for pattern, vendor in CLAIMS:
        if pattern.match(name.lower()):
            return vendor
    return None


def _method(vendor) -> str:
    if vendor is None:
        return "none"
    if vendor == "meta":
        return "network"
    lists, names = VENDORS[vendor]
    return "ranges" if lists else ("dns" if names else "none")


class Checks:
    """The documented crawler-check rules, written again."""

    def __init__(self, config: dict, now: datetime) -> None:
        raw = ((config or {}).get("bots") or {}).get("ranges_dir")
        self.on = bool(raw)
        self.folder = Path(str(raw)) if raw else None
        self.nets: dict[str, list] = {}
        self.current: set[str] = set()
        self.dns: dict = {}
        self.hosting: list = []
        self.memo: dict = {}
        if not self.on:
            return
        for path in sorted(self.folder.glob("*.json")):
            if path.name == "dns.json":
                try:
                    self.dns = json.loads(path.read_text()).get("answers") or {}
                except (OSError, ValueError, AttributeError):
                    self.dns = {}
                continue
            try:
                data = json.loads(path.read_text())
                nets = [ipaddress.ip_network(c, strict=False) for c in data["networks"]]
            except (OSError, ValueError, KeyError, TypeError):
                continue
            if not nets:
                continue
            if path.stem == "hosting":
                self.hosting = nets
                continue
            self.nets[path.stem] = nets
            try:
                if now - datetime.fromisoformat(data["fetched"]) <= MAX_LIST_AGE:
                    self.current.add(path.stem)
            except (KeyError, TypeError, ValueError):
                pass

    def _inside(self, address: str, nets: list) -> bool:
        try:
            ip = ipaddress.ip_address(address)
        except ValueError:
            return False
        return any(ip.version == n.version and ip in n for n in nets)

    def verdict(self, name: str, address: str, agent: str):
        """"verified", "unverified", "spoofed", or None (no owner known)."""
        vendor = _vendor(name)
        if vendor is None:
            return None
        if LOCAL_TOOL.search(agent or ""):
            return "unverified"
        if (vendor, address) in self.memo:
            return self.memo[(vendor, address)]
        lists, names = VENDORS[vendor]
        have = [n for n in lists if n in self.nets]
        if any(self._inside(address, self.nets[n]) for n in have):
            out = "verified"
        elif names:
            said = (self.dns.get(f"{vendor}|{address}") or {}).get("result")
            out = said if said in ("verified", "spoofed") else "unverified"
        elif lists and all(n in self.current for n in lists):
            out = "spoofed"
        else:
            out = "unverified"
        self.memo[(vendor, address)] = out
        return out

    def from_hosting(self, address: str) -> bool:
        key = ("hosting", address)
        if key not in self.memo:
            self.memo[key] = bool(self.hosting) and self._inside(address, self.hosting)
        return self.memo[key]


def preview_app(agent: str) -> str:
    for pattern, app in LINK_PREVIEWS:
        if pattern.search(agent):
            return app
    return ""


def bursts(lines, hosts: set) -> set:
    """(address, agent) pairs where one browser agent came from 10 or more
    addresses within 10 seconds: a forward window from each request."""
    per: dict[str, list] = {}
    for line in lines:
        if hosts and line.host and line.host.lower() not in hosts:
            continue
        agent = line.agent
        if agent and _BROWSERISH.search(agent) and not OTHER_BOT.search(agent):
            per.setdefault(agent, []).append((line.when, line.address))
    found = set()
    for agent, events in per.items():
        if len({a for _, a in events}) < 10:
            continue
        events.sort(key=lambda e: e[0])
        times = [e[0] for e in events]
        for i, (when, _) in enumerate(events):
            j = bisect.bisect_right(times, when + timedelta(seconds=10))
            group = {a for _, a in events[i:j]}
            if len(group) >= 10:
                found.update((a, agent) for a in group)
    return found


class BotsRecount:
    def __init__(self, gap: timedelta = timedelta(minutes=30)) -> None:
        self.gap = gap
        # Browser-like lines that never drew, by address and agent.
        self.undrawn: dict[tuple, list] = {}
        self.checks: dict[str, Counter] = {}
        self.groups: dict[str, str] = {}
        self.previews: Counter = Counter()
        self.flags: dict[str, Counter] = {f: Counter() for f in FLAGS}
        self.addresses: dict[str, set] = {f: set() for f in FLAGS}
        # 403s per AI crawler of the policy catalog (a shared name list).
        self.blocked: Counter = Counter()
        # Requests by path per assistant and search crawler (robots.json).
        self.paths: dict[str, Counter] = {}

    def hit(self, line, group: str, info: dict) -> None:
        if line.status == "403":
            crawler = policy_match(line.agent)
            if crawler is not None:
                self.blocked[crawler.name] += 1
        name = info.get("name") or ""
        if group in ("answer_engines", "search_engines") and name:
            self.paths.setdefault(name, Counter())[line.path[:200]] += 1
            self.groups.setdefault(name, group)
            self.checks.setdefault(name, Counter())[
                "verified" if info.get("checked") == "verified" else "unverified"] += 1
        elif group == "bots" and info.get("spoofed"):
            claim = info["spoofed"]
            self.groups.setdefault(claim, info.get("claim_group", ""))
            self.checks.setdefault(claim, Counter())["spoofed"] += 1
        elif group == "bots" and info.get("preview"):
            self.previews[info["preview"]] += 1
        elif group == "bots" and info.get("not_rendered"):
            self.undrawn.setdefault((line.address, line.agent), []).append(line)
        elif group == "people":
            for flag in info.get("flags") or ():
                self.flags[flag]["requests"] += 1
                self.addresses[flag].add(line.address)

    def figures(self) -> dict:
        return {"verification": {n: {"group": self.groups[n], "method": _method(_vendor(n)),
                                     **{k: c.get(k, 0) for k in
                                        ("verified", "unverified", "spoofed")}}
                                 for n, c in self.checks.items()},
                "link_previews": dict(self.previews),
                "fake_browsers": {f: {"requests": self.flags[f]["requests"],
                                      "addresses": len(self.addresses[f])} for f in FLAGS},
                "blocked": dict(self.blocked),
                "crawler_paths": self.paths,
                "not_rendered": self._undrawn()}

    def _undrawn(self) -> dict:
        """Requests, page views, and visits that read a page, among the lines
        moved to bots for never drawing."""
        from .audit import is_page
        got = {"requests": 0, "pages": 0, "readers": 0}
        for seen in self.undrawn.values():
            seen = sorted(seen, key=lambda l: l.when)
            starts = [0] + [k for k in range(1, len(seen))
                            if seen[k].when - seen[k - 1].when > self.gap]
            for a, b in zip(starts, starts[1:] + [len(seen)]):
                pages = sum(1 for l in seen[a:b] if is_page(l))
                got["requests"] += b - a
                got["pages"] += pages
                got["readers"] += 1 if pages else 0
        return got


# ------------------------------------------------------------- quality

def quality(files, start: datetime, end: datetime, parse) -> dict:
    """Lines in [start, end) counted from the raw text: parsed, byte-identical
    repeats within one second, old-layout lines, and gaps of over 10
    minutes. `parse(raw)` is audit.line_hit; `old(raw)` tells the layout.
    A line repeating an earlier request id (rid=) is not parsed: it is
    counted as removed, in the window its own timestamp falls in."""
    from .audit import _EXTENDED
    seen: dict[int, set] = {}
    rids: set = set()
    parsed = dupes = old = removed = 0
    minutes = set()
    for path in files:
        opener = gzip.open if str(path).endswith(".gz") else open
        with opener(path, "rt", errors="replace") as handle:
            for raw in handle:
                line = parse(raw)
                if line is None:
                    continue
                if line.rid:
                    if line.rid in rids:
                        removed += start <= line.when < end
                        continue
                    rids.add(line.rid)
                if not (start <= line.when < end):
                    continue
                parsed += 1
                second = int(line.when.timestamp())
                text = raw.rstrip("\n")
                bucket = seen.setdefault(second, set())
                if text in bucket:
                    dupes += 1
                else:
                    bucket.add(text)
                # The old layout is nginx's or Apache's combined: no host.
                # A drain record (JSON, audit_drains) is not an old layout.
                if not _EXTENDED.match(raw) and not raw.lstrip().startswith("{"):
                    old += 1
                minutes.add(second // 60)
    ordered = sorted(minutes)
    gaps = sum(1 for a, b in zip(ordered, ordered[1:]) if b - a - 1 > 10)
    return {"parsed": parsed, "duplicates": dupes, "old_format": old, "gaps": gaps,
            "duplicates_removed": removed}


def compare_crawler_paths(stored: dict, got: dict, same, problems) -> None:
    """Each assistant's and search crawler's requests by path against the
    recount: every kept path exactly, the folded tail against the rest."""
    blob = stored.get("crawler_paths")
    if blob is None:
        return
    for name in sorted(set(blob) | set(got)):
        kept = (blob.get(name) or {}).get("paths") or {}
        mine = got.get(name) or Counter()
        same(f"{name}: requests (crawler paths)", int((blob.get(name) or {}).get("requests", 0)),
             sum(mine.values()))
        named = [p for p in kept if p != "(all others)"]
        for path in sorted(named):
            same(f"{name}: {path}", int(kept[path]), mine.get(path, 0))
        same(f"{name}: (all others)", int(kept.get("(all others)", 0)),
             sum(mine.values()) - sum(mine.get(p, 0) for p in named))


def compare_cube(stored: dict, by: dict, readers: int, same, problems) -> None:
    """The cube's rows against the recount's own readers by country, device,
    source and landing page (exact while the day is not folded)."""
    blob = stored.get("cube")
    if blob is None:
        return
    rows = blob.get("rows") or []
    same("cube: visits", sum(r[-1] for r in rows), readers)
    if blob.get("folded"):
        return
    for i, field in ((0, "country"), (1, "landing"), (2, "source"), (4, "device")):
        kept = Counter()
        for r in rows:
            kept[r[i]] += r[-1]
        mine = by.get(field) or Counter()
        for label in sorted(set(kept) | set(mine)):
            same(f"cube {field}: {label}", kept.get(label, 0), mine.get(label, 0))


def compare(stored: dict, got_bots: dict, got_quality: dict | None, same, problems) -> None:
    blob = stored.get("bots")
    if blob is None:
        problems.append("no crawler-check figures stored (collected before release 2)")
    else:
        ver = blob.get("verification") or {}
        for name in sorted(set(ver) | set(got_bots["verification"])):
            mine = got_bots["verification"].get(name) or {}
            kept = ver.get(name) or {}
            for k in ("verified", "unverified", "spoofed"):
                same(f"{name}: {k}", int(kept.get(k, 0)), int(mine.get(k, 0)))
        prev = blob.get("link_previews") or {}
        for app in sorted(set(prev) | set(got_bots["link_previews"])):
            same(f"link previews: {app}", int(prev.get(app, 0)),
                 int(got_bots["link_previews"].get(app, 0)))
        fake = blob.get("fake_browsers") or {}
        for flag in FLAGS:
            for k in ("requests", "addresses"):
                same(f"fake browsers ({flag}): {k}", int((fake.get(flag) or {}).get(k, 0)),
                     int(got_bots["fake_browsers"][flag][k]))
        if "not_rendered" in blob:                 # stored since visitors had to render
            kept, mine = blob.get("not_rendered") or {}, got_bots["not_rendered"]
            for k in ("requests", "pages", "readers"):
                same(f"browser-like, never rendered: {k}", int(kept.get(k, 0)),
                     int(mine.get(k, 0)))
        if "blocked" in blob:                      # stored since the AI crawler settings
            kept, mine = blob.get("blocked") or {}, got_bots["blocked"]
            for name in sorted(set(kept) | set(mine)):
                same(f"403s to {name}", int(kept.get(name, 0)), int(mine.get(name, 0)))
    q = stored.get("quality")
    if got_quality is None:
        return
    if q is None:
        problems.append("no data-quality figures stored (collected before release 2)")
        return
    for k in ("parsed", "duplicates", "old_format"):
        same(f"quality: {k}", int(q.get(k) or 0), int(got_quality[k]))
    if "duplicates_removed" in q:                  # stored once rid= was logged
        same("quality: duplicates removed", int(q.get("duplicates_removed") or 0),
             int(got_quality.get("duplicates_removed", 0)))
    same("quality: gaps", len(q.get("gaps") or []), int(got_quality["gaps"]))


# ------------------------------------------- release 3b: compare and lifecycle

def assistant_of(line) -> str:
    """The assistant a reader came from, by the documented rule (the referrer
    host, most specific first, or Bing's /chat, else a utm_source tag, also
    behind any other referrer), named by the shared alias list - written
    again, not called."""
    from urllib.parse import urlsplit
    from .classify import AI_REFERRER_HOSTS, AI_UTM, ASSISTANT_ALIASES
    ref = line.referrer
    if ref:
        try:
            parts = urlsplit(ref if "//" in ref else "//" + ref)
        except ValueError:
            return ""
        host = (parts.hostname or "").lower().rstrip(".")
        for domain in AI_REFERRER_HOSTS:
            if host == domain or host.endswith("." + domain):
                return ASSISTANT_ALIASES.get(domain, domain)
        if (host == "bing.com" or host.endswith(".bing.com")) and parts.path.startswith("/chat"):
            return ASSISTANT_ALIASES.get("bing.com/chat", "bing.com/chat")
    found = AI_UTM.search(line.url)
    if not found:
        return ""
    name = found.group(1).lower()
    return ASSISTANT_ALIASES.get(name, name)


class FirstsRecount:
    """Each page's first times in the day, from the raw lines."""

    def __init__(self, hosts: set, source_of, bare) -> None:
        self.hosts, self.source_of, self.bare = hosts, source_of, bare
        self.got: dict[str, dict] = {}

    def _take(self, path: str, key: str, when, who: str = "") -> None:
        iso = when.astimezone(timezone.utc).isoformat(timespec="seconds")
        slot = self.got.setdefault(path, {})
        if key not in slot or iso < slot[key][0]:
            slot[key] = [iso, who]

    def hit(self, line, group: str, info: dict, tier: str, name: str, cited: bool,
            page: bool) -> None:
        if not page:
            return
        path = line.path[:70]
        if group == "search_engines" and (info.get("name") or "").lower() in ("googlebot",
                                                                             "bingbot"):
            self._take(path, info["name"].lower(), line.when)
        elif group == "answer_engines" and name:
            self._take(path, f"ai_{tier}|{name}", line.when, name)
        elif group == "people":
            self._take(path, "human", line.when)
            if cited:
                who = assistant_of(line)
                self._take(path, f"from_ai|{who}", line.when, who)
            own = self.hosts or ({line.host.lower()} if line.host else set())
            if self.source_of(line, False, own) == "Search engine":
                self._take(path, "from_search", line.when,
                           self.bare(line.referrer)[:60] if line.referrer else "")


def compare_firsts(stored: dict, got: dict, same, problems) -> None:
    blob = stored.get("page_firsts")
    if blob is None:
        return
    for path in sorted(set(blob) | set(got)):
        mine, kept = got.get(path) or {}, blob.get(path) or {}
        for key in sorted(set(mine) | set(kept)):
            a, b = kept.get(key), mine.get(key)
            if a is not None:
                a = list(a)
            if a != b:
                problems.append(f"page {path} first {key}: history has {a}, the recount "
                                f"finds {b}")
        same(f"page {path}: first times", len(kept), len(mine))


def compare_visit_cube(stored: dict, by: dict, readers: int, same, problems) -> None:
    """Every field of every reader's visit, summed, against the recount's own
    readers by that label (exact unless folded)."""
    blob = stored.get("visit_cube")
    if blob is None:
        return
    rows = blob.get("rows") or []
    same("visit cube: visits", sum(r[-1] for r in rows), readers)
    if blob.get("folded"):
        return
    for i, field in ((0, "country"), (1, "landing"), (2, "source"), (4, "device"),
                     (5, "browser"), (6, "os"), (7, "campaign")):
        kept = Counter()
        for r in rows:
            kept[r[i]] += r[-1]
        mine = by.get(field) or Counter()
        for label in sorted(set(kept) | set(mine)):
            same(f"visit cube {field}: {label}", kept.get(label, 0), mine.get(label, 0))
