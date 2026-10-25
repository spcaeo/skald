"""robots.txt beside what each crawler actually fetched (robots.json).

The site's own robots.txt says what each crawler may fetch; the log says
what it did fetch. This puts them side by side:

  refresh()       the live run fetches <site>/robots.txt at most once an hour
                  (5 s, as our own "site-version-check" agent, so it counts as
                  ours) into robots.txt beside the history, with
                  robots-state.json; a failed fetch keeps the last good copy
  CrawlerPaths    per day, each assistant's and search crawler's requests by
                  path (day_extras kind "crawler_paths": the top PATHS paths
                  per crawler and an "(all others)" row, so the sum holds)
  build()         robots.json: the rules, and per crawler the requests for
                  paths robots.txt disallows it, with Python's own
                  urllib.robotparser and the crawler's token

Only assistants and search crawlers (answer_engines, search_engines) are
collected: their names come from the shared name lists, so the independent
audit (audit_release2.compare_crawler_paths) can recount them. Bots are
named from their own agent strings by the package alone; a bot list here
could not be recounted by a second road, so it is left out. A spoofed
claim ("claims to be GPTBot") is a bot and is not in it either.

Verdicts use the robots.txt fetched last (`robots.fetched_at`): a past day
is judged by today's rules, and the file says so.
"""
from __future__ import annotations

import json
import urllib.request
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.robotparser import RobotFileParser

from .files import write_atomic

PATHS = 200
OTHER = "(all others)"
GROUPS = ("answer_engines", "search_engines")
TEXT = "robots.txt"
STATE = "robots-state.json"
EVERY = timedelta(hours=1)
AGENT = "site-version-check/1"
MAX_BYTES = 500_000
DAYS = 30


# ------------------------------------------------------------ fetching

def url_of(config: dict) -> str | None:
    hosts = [str(h) for h in (((config or {}).get("site") or {}).get("hosts") or [])]
    if not hosts:
        return None
    host = next((h for h in hosts if h.startswith("www.")), hosts[0])
    return f"https://{host}/robots.txt"


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": AGENT})
    with urllib.request.urlopen(req, timeout=5) as resp:
        return resp.read(MAX_BYTES)


def _state(directory: Path) -> dict:
    try:
        got = json.loads((Path(directory) / STATE).read_text())
    except (OSError, ValueError):
        return {}
    return got if isinstance(got, dict) else {}


def refresh(config: dict, directory, now: datetime | None = None, fetch=None) -> dict:
    """Fetch robots.txt when the copy is an hour old or missing. The state;
    never raises."""
    if directory is None:
        return {}
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    url = url_of(config)
    state = _state(directory)
    if url is None:
        return state
    try:
        tried = datetime.fromisoformat(state.get("tried_at") or "")
    except ValueError:
        tried = None
    if tried is not None and now - tried < EVERY and state.get("url") == url:
        return state
    state.update(url=url, tried_at=now.isoformat(timespec="seconds"))
    try:
        body = (fetch or _get)(url)
        text = body.decode("utf-8", "replace")
        write_atomic(Path(directory) / TEXT, text)
        state.update(ok=True, error=None, fetched_at=now.isoformat(timespec="seconds"))
    except Exception as why:            # noqa: BLE001 - keep the last good copy
        state.update(ok=False, error=f"{type(why).__name__}: {why}"[:200])
    try:
        write_atomic(Path(directory) / STATE, json.dumps(state, sort_keys=True) + "\n")
    except OSError:
        pass
    return state


def state(directory) -> dict:
    """The last fetch's state (robots-state.json), {} when there is none."""
    return _state(directory) if directory is not None else {}


def cached(directory) -> str | None:
    try:
        return (Path(directory) / TEXT).read_text(encoding="utf-8", errors="replace")
    except (OSError, TypeError):
        return None


# ------------------------------------------------------------- reading

def parse(text: str) -> dict:
    """{"groups": [{"agents","allow","disallow","crawl_delay"}], "sitemaps": [url]}."""
    groups, sitemaps = [], []
    current = None
    for raw in (text or "").splitlines():
        line = raw.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key, value = key.strip().lower(), value.strip()
        if key == "user-agent":
            if current is None or current["allow"] or current["disallow"] \
                    or current["crawl_delay"] is not None:
                current = {"agents": [], "allow": [], "disallow": [], "crawl_delay": None}
                groups.append(current)
            current["agents"].append(value)
        elif key in ("allow", "disallow") and current is not None:
            if value:
                current[key].append(value)
        elif key == "crawl-delay" and current is not None:
            try:
                current["crawl_delay"] = float(value)
            except ValueError:
                pass
        elif key == "sitemap":
            sitemaps.append(value)
    return {"groups": groups, "sitemaps": sitemaps}


def _parser(text: str) -> RobotFileParser:
    rp = RobotFileParser()
    rp.parse((text or "").splitlines())
    return rp


def verdict(text: str, token: str, path: str) -> bool:
    """May `token` fetch `path` under this robots.txt?"""
    return _parser(text).can_fetch(token, path or "/")


def token_of(name: str) -> str | None:
    """The robots.txt token for a crawler name, or None (no token to check)."""
    name = (name or "").strip()
    if not name or name.startswith(("claims to be", "link preview")) or name == OTHER:
        return None
    return name


def applies(groups: list[dict], token: str) -> str:
    """The group a token falls under: its own name (case-insensitive,
    as robotparser matches it) or "*"."""
    low = token.lower()
    for g in groups:
        for agent in g["agents"]:
            a = agent.lower()
            if a != "*" and a in low:
                return agent
    return "*"


# ----------------------------------------------------------- collection

class CrawlerPaths:
    """Fed every counted hit (extras.Extras): requests by path per crawler."""

    def __init__(self) -> None:
        self.per: dict[str, Counter] = {}
        self.group: dict[str, str] = {}

    def add(self, hit, verdict) -> None:
        group = verdict.group.value
        if group not in GROUPS or not verdict.engine:
            return
        self.group.setdefault(verdict.engine, group)
        self.per.setdefault(verdict.engine, Counter())[hit.path[:200]] += 1

    def finish(self) -> dict:
        out = {}
        for name, paths in sorted(self.per.items()):
            kept = dict(paths.most_common(PATHS))
            rest = sum(paths.values()) - sum(kept.values())
            if rest:
                kept[OTHER] = kept.get(OTHER, 0) + rest
            out[name] = {"group": self.group[name], "requests": int(sum(paths.values())),
                         "paths": kept}
        return out


def check(totals, blob: dict | None, problems: list) -> None:
    """Each crawler's paths add up to its requests; each group's crawlers
    add up to that group's requests (every assistant and search crawler
    request is named)."""
    from .verify import Problem
    if blob is None:
        return
    by_group: Counter = Counter()
    for name, got in blob.items():
        if sum(got["paths"].values()) != got["requests"]:
            problems.append(Problem("crawler paths", f"{name}: paths do not add up to "
                                    f"its {got['requests']:,} requests"))
        by_group[got["group"]] += got["requests"]
    from .classify import Group
    for g in (Group.ANSWER_ENGINE, Group.SEARCH_ENGINE):
        stats = totals.groups.get(g)
        hits = stats.hits if stats else 0
        if by_group.get(g.value, 0) != hits:
            problems.append(Problem("crawler paths", f"{g.value}: {by_group.get(g.value, 0):,} "
                                    f"by crawler against {hits:,} requests"))


# ----------------------------------------------------------- robots.json

def _disallowed(rp: RobotFileParser | None, token: str | None, paths: dict) -> tuple[int, list]:
    if rp is None or token is None:
        return 0, []
    hits = Counter()
    for path, n in paths.items():
        if path == OTHER:
            continue
        if not rp.can_fetch(token, path or "/"):
            hits[path] += n
    return sum(hits.values()), [{"path": p, "n": n} for p, n in hits.most_common(10)]


def build(p) -> dict:
    directory = p.live_dir
    text = cached(directory) if directory is not None else None
    state = _state(directory) if directory is not None else {}
    parsed = parse(text) if text is not None else {"groups": [], "sitemaps": []}
    rp = _parser(text) if text is not None else None
    robots = {"url": state.get("url") or url_of(p.config), "fetched_at": state.get("fetched_at"),
              "ok": bool(state.get("ok")) and text is not None,
              "error": state.get("error") if not state.get("ok") else None,
              "groups": parsed["groups"], "sitemaps": parsed["sitemaps"]}
    first = p.anchor - timedelta(days=DAYS - 1)
    blobs = p.history.extras(p.key, first, p.anchor, ("crawler_paths",))
    days, totals = [], {}
    for e in p.daily:
        if e["day"] < first:
            continue
        row = p.day_entry(e)
        blob = (blobs.get(e["day"].isoformat()) or {}).get("crawler_paths") \
            if p.has_figures(e) else None
        if p.has_figures(e):
            row["crawlers"] = None if blob is None else {}
        for name, got in (blob or {}).items():
            n, _ = _disallowed(rp, token_of(name), got["paths"])
            row["crawlers"][name] = {"requests": got["requests"], "disallowed": n}
            agg = totals.setdefault(name, {"group": got["group"], "paths": Counter(),
                                           "days": 0, "last": ""})
            agg["paths"].update(got["paths"])
            agg["days"] += 1
            agg["last"] = e["day"].isoformat()
        days.append(row)
    today = {}
    # Today counted (a live snapshot that adds up, with its crawler_paths, which keeps every
    # name): a crawler not in it made no request today, a real 0. Not counted: None ("-").
    today_counted = p.live_ok and ((p.snap.get("extras") or {}).get("crawler_paths")) is not None
    if p.live_ok:
        for name, got in (((p.snap.get("extras") or {}).get("crawler_paths")) or {}).items():
            n, _ = _disallowed(rp, token_of(name), got["paths"])
            today[name] = {"requests": got["requests"], "disallowed": n}
            agg = totals.setdefault(name, {"group": got["group"], "paths": Counter(),
                                           "days": 0, "last": ""})
            agg["paths"].update(got["paths"])
            agg["days"] += 1
            agg["last"] = p.today.isoformat()
    crawlers = []
    for name, agg in totals.items():
        token = token_of(name)
        n, top = _disallowed(rp, token, agg["paths"])
        crawlers.append({
            "name": name, "group": agg["group"], "token": token,
            "applies": applies(parsed["groups"], token) if token else None,
            "root_allowed": (rp.can_fetch(token, "/") if rp is not None and token else None),
            "days_seen": agg["days"], "requests": int(sum(agg["paths"].values())),
            "paths": len([k for k in agg["paths"] if k != OTHER]),
            "disallowed": n, "disallowed_paths": top,
            "today": today.get(name) or ({"requests": 0, "disallowed": 0} if today_counted else None),
            "_last": agg["last"]})
    crawlers.sort(key=lambda c: (c["_last"], c["requests"]), reverse=True)
    for c in crawlers:
        c.pop("_last")
    return {"robots": robots, "crawlers": crawlers, "days": days}
