"""Crawl health: what each crawler fetched beside the site's sitemap, and the
problems crawlers hit. The day kind `crawl_health` and crawl_health.json.

Like Screaming Frog's Log File Analyser, Botify or Lumar, from the access log:
which sitemap pages each crawler fetched, which it never did (orphans), which
pages it fetched that the sitemap does not list, and the paths that answer
crawlers with a 404 or 410, a 5xx, a redirect, slowly or with a large body.

The crawlers (crawler_of): Google (Googlebot) and Bing (bingbot) of the search
crawlers, and every AI crawler and AI user fetcher by its own name (the
assistants' names classify.py gives; kind "ai_training" or "ai_asked"). Other
search crawlers, bots, people and our own traffic are not in it.

Built in the tally pass (extras.Extras offers every counted hit to
Collector.add), for the whole site only (a view's tally has none). Per crawler,
per path (no query string, first 200 characters), the FIELDS below. A path in
the day's sitemap list (sitemap.for_day: that day's, else the latest kept
before) is "listed". Every listed path is kept; of the others the KEEP most
requested, the rest folded into one "(all others)" entry (`folded` says how
many paths). Per crawler the totals of each field, and:

  listed             distinct sitemap paths it fetched that day
  unlisted           distinct paths it fetched as a page (a 2xx or 304 page
                     view, parse.Hit.is_page) that the sitemap does not list
  unlisted_requests  its page views of those paths
  (listed, unlisted and unlisted_requests are None when no sitemap list was
  kept: not recorded, never 0)

SLOW_MS and LARGE_BYTES set "slow" (the server took at least a second) and
"large" (a body of at least 1 MB). DATA-CONTRACT-CRAWL-HEALTH.md describes the
blob and the file; the second count is audit_crawl_health.py.
"""
from __future__ import annotations

from datetime import timedelta, timezone

from .classify import Group

SLOW_MS = 1000
LARGE_BYTES = 1_000_000
KEEP = 500
OTHER = "(all others)"
SEARCH = {"googlebot": "Google", "bingbot": "Bing"}
FIELDS = ("requests", "pages", "listed", "redirects", "not_found", "server_errors", "slow",
          "large", "timed", "ms", "sized", "bytes", "max_bytes", "last")
SUMMED = ("requests", "pages", "redirects", "not_found", "server_errors", "slow", "large",
          "timed", "ms", "sized", "bytes")
_I = {f: i for i, f in enumerate(FIELDS)}


def crawler_of(verdict) -> tuple[str, str] | None:
    """(name, kind) of a crawler crawl health follows, or None."""
    if verdict.group is Group.SEARCH_ENGINE and verdict.engine:
        name = SEARCH.get(verdict.engine.lower())
        return (name, "search") if name else None
    if verdict.group is Group.ANSWER_ENGINE and verdict.engine and verdict.tier:
        return verdict.engine, "ai_" + verdict.tier.value
    return None


def _blank() -> list:
    return [0] * (len(FIELDS) - 2) + [None, None]


def _iso(when) -> str | None:
    if when is None:
        return None
    when = when if when.tzinfo else when.replace(tzinfo=timezone.utc)
    return when.astimezone(timezone.utc).isoformat(timespec="seconds")


class Collector:
    """Fed every counted hit of the whole site (extras.Extras.add)."""

    def __init__(self) -> None:
        self.sitemap: dict | None = None      # sitemap.for_day (aggregate.Tally sets it)
        self.per: dict[str, dict] = {}

    def add(self, hit, verdict) -> None:
        got = crawler_of(verdict)
        if got is None:
            return
        name, kind = got
        c = self.per.get(name)
        if c is None:
            c = self.per[name] = {"kind": kind, "paths": {}}
        path = hit.path[:200]
        e = c["paths"].get(path)
        if e is None:
            e = c["paths"][path] = _blank()
        e[0] += 1
        if hit.is_page:
            e[1] += 1
        s = hit.status
        if s[:1] == "3" and s != "304":
            e[3] += 1
        if s in ("404", "410"):
            e[4] += 1
        if s[:1] == "5":
            e[5] += 1
        if hit.request_time is not None:
            ms = int(round(hit.request_time * 1000))
            e[8] += 1
            e[9] += ms
            if ms >= SLOW_MS:
                e[6] += 1
        if hit.size is not None:
            size = int(hit.size)
            e[10] += 1
            e[11] += size
            e[12] = size if e[12] is None else max(e[12], size)
            if size >= LARGE_BYTES:
                e[7] += 1
        when = hit.when if hit.when.tzinfo else hit.when.replace(tzinfo=timezone.utc)
        if e[13] is None or when > e[13]:
            e[13] = when

    def finish(self) -> dict:
        listed = self.sitemap["paths"] if self.sitemap else None
        out = {}
        for name in sorted(self.per):
            out[name] = crawler_blob(self.per[name]["kind"], self.per[name]["paths"], listed)
        return {"sitemap": ({"day": self.sitemap["day"], "list": self.sitemap["list"],
                             "paths": len(self.sitemap["paths"])} if self.sitemap else None),
                "slow_ms": SLOW_MS, "large_bytes": LARGE_BYTES, "keep": KEEP,
                "fields": list(FIELDS), "crawlers": out}


def crawler_blob(kind: str, paths: dict, listed) -> dict:
    """One crawler's day: its paths (listed kept, the rest top KEEP and a
    fold) and its totals. `paths`: {path: raw entry, last a datetime}."""
    entries = {}
    others = []
    for path, e in paths.items():
        inside = listed is not None and path in listed
        row = list(e)
        row[2] = 1 if inside else 0
        if inside:
            entries[path] = row
        else:
            others.append((path, row))
    others.sort(key=lambda pr: (-pr[1][0], pr[0]))
    for path, row in others[:KEEP]:
        entries[path] = row
    rest = others[KEEP:]
    if rest:
        fold = _blank()
        fold[2] = 0
        for _, row in rest:
            for f in SUMMED:
                fold[_I[f]] += row[_I[f]]
            if row[12] is not None:
                fold[12] = row[12] if fold[12] is None else max(fold[12], row[12])
            if row[13] is not None and (fold[13] is None or row[13] > fold[13]):
                fold[13] = row[13]
        entries[OTHER] = fold
    for row in entries.values():
        row[13] = _iso(row[13])
    blob = {"kind": kind, **{f: sum(r[_I[f]] for r in entries.values()) for f in SUMMED},
            "paths": dict(sorted(entries.items())), "folded": len(rest)}
    if listed is None:
        blob.update(listed=None, unlisted=None, unlisted_requests=None)
    else:
        outside = [e for p, e in paths.items() if p not in listed and e[1]]
        blob.update(listed=sum(1 for p in paths if p in listed), unlisted=len(outside),
                    unlisted_requests=sum(e[1] for e in outside))
    return blob


# ---------------------------------------------------- day_more registry

def finish(extras, totals, journeys, page_visits, readers_by_hour) -> dict | None:
    got = getattr(extras, "crawl_health", None)
    return None if got is None else got.finish()


def check(totals, blob, differs, problems) -> None:
    """Every AI request is one crawler's; Google and Bing within the search
    crawlers'; each crawler's totals are the sums of its paths; listed paths
    are as many as it says, and none is folded."""
    from .verify import Problem
    crawlers = blob.get("crawlers") or {}
    stats = totals.groups.get(Group.ANSWER_ENGINE)
    differs("crawl_health: AI requests by crawler",
            sum(int(c["requests"]) for c in crawlers.values() if c["kind"] != "search"),
            stats.hits if stats else 0, "requests")
    search = totals.groups.get(Group.SEARCH_ENGINE)
    named = sum(int(c["requests"]) for c in crawlers.values() if c["kind"] == "search")
    if named > (search.hits if search else 0):
        problems.append(Problem("crawl_health", f"Google and Bing made {named:,} requests, "
                                f"more than the {search.hits if search else 0:,} of all "
                                "search crawlers"))
    size = (blob.get("sitemap") or {}).get("paths")
    for name, c in crawlers.items():
        rows = c.get("paths") or {}
        for f in SUMMED:
            differs(f"crawl_health: {name}: {f} by path",
                    sum(int(r[_I[f]]) for r in rows.values()), int(c[f]), f)
        flagged = sum(1 for p, r in rows.items() if r[2] and p != OTHER)
        bad = []
        if (c.get("listed") is None) != (size is None):
            bad.append("listed recorded without a sitemap list, or missing with one")
        elif size is not None:
            if flagged != int(c["listed"]):
                bad.append(f"{flagged} paths marked listed, {c['listed']} counted")
            if int(c["listed"]) > int(size):
                bad.append("more listed paths fetched than the sitemap holds")
            if int(c["unlisted_requests"]) > int(c["pages"]):
                bad.append("more page views of unlisted paths than page views")
        if (OTHER in rows) != (int(c.get("folded") or 0) > 0):
            bad.append("a fold without folded paths, or folded paths without a fold")
        if OTHER in rows and rows[OTHER][2]:
            bad.append("a sitemap path folded")
        for p, r in rows.items():
            if int(r[0]) < max(int(r[1]), int(r[3]) + int(r[4]) + int(r[5])) or \
                    int(r[8]) > int(r[0]) or int(r[10]) > int(r[0]):
                bad.append(f"{p}: parts larger than its requests")
                break
            if (r[12] is None) != (int(r[10]) == 0):
                bad.append(f"{p}: a largest size without a sized line, or none with one")
                break
        for why in bad:
            problems.append(Problem("crawl_health", f"{name}: {why}"))


# ---------------------------------------------------- crawl_health.json

WINDOWS = (7, 30)
PAGE_ROWS = 3000
LIST_ROWS = 300
PROBLEM_ROWS = 100
PROBLEMS = ("not_found", "server_errors", "redirects", "slow", "large")


class _Path:
    __slots__ = ("vals", "max_bytes", "last", "days", "by")

    def __init__(self) -> None:
        self.vals = [0] * len(SUMMED)
        self.max_bytes = None
        self.last = None
        self.days: set = set()
        self.by: dict[str, list] = {}         # crawler -> [requests, pages, problems...]

    def add(self, day: str, name: str, r: list) -> None:
        for k, f in enumerate(SUMMED):
            self.vals[k] += int(r[_I[f]])
        if r[12] is not None:
            self.max_bytes = r[12] if self.max_bytes is None else max(self.max_bytes, r[12])
        if r[13] and (self.last is None or r[13] > self.last):
            self.last = r[13]
        self.days.add(day)
        mine = self.by.setdefault(name, [0] * len(SUMMED))
        for k, f in enumerate(SUMMED):
            mine[k] += int(r[_I[f]])

    def get(self, f: str) -> int:
        return self.vals[SUMMED.index(f)]


def _window(blobs: list[tuple[str, dict]], current: frozenset | None) -> dict:
    """One window's figures from its days' blobs ([(day, blob)])."""
    crawlers: dict[str, dict] = {}
    paths: dict[str, _Path] = {}
    for day, blob in blobs:
        for name, c in (blob.get("crawlers") or {}).items():
            agg = crawlers.setdefault(name, {"kind": c["kind"], "requests": 0, "days": 0,
                                             "folded": False, "last": None, "seen": {},
                                             **{p: 0 for p in PROBLEMS}})
            agg["requests"] += int(c["requests"])
            agg["days"] += 1
            agg["folded"] = agg["folded"] or bool(c.get("folded"))
            for p in PROBLEMS:
                agg[p] += int(c.get(p) or 0)
            for path, r in (c.get("paths") or {}).items():
                if path == OTHER:
                    continue
                paths.setdefault(path, _Path()).add(day, name, r)
                seen = agg["seen"].setdefault(path, [0, 0, None])
                seen[0] += int(r[0])
                seen[1] += int(r[1])
                if r[13] and (seen[2] is None or r[13] > seen[2]):
                    seen[2] = r[13]
                if r[13] and (agg["last"] is None or r[13] > agg["last"]):
                    agg["last"] = r[13]
    size = len(current) if current is not None else None
    rows = []
    for name, agg in crawlers.items():
        seen = agg.pop("seen")
        row = {"name": name, **agg, "paths": len(seen)}
        if current is None:
            row.update(listed=None, coverage=None, orphans=None, unlisted=None,
                       per_page=None)
        else:
            inside = [path for path in seen if path in current]
            row.update(listed=len(inside),
                       coverage=round(len(inside) / size, 4) if size else None,
                       orphans=size - len(inside),
                       unlisted=sum(1 for p, s in seen.items() if p not in current and s[1]),
                       per_page=(round(sum(seen[p][0] for p in inside) / len(inside), 2)
                                 if inside else None))
        rows.append(row)
    rows.sort(key=lambda r: (r["kind"] != "search", -r["requests"], r["name"]))

    def by(item: _Path, f: str) -> dict:
        k = SUMMED.index(f)
        return {n: v[k] for n, v in sorted(item.by.items()) if v[k]}

    unlisted = []
    if current is not None:
        for path, item in paths.items():
            if path not in current and item.get("pages"):
                unlisted.append({"path": path, "pages": item.get("pages"),
                                 "requests": item.get("requests"), "by": by(item, "pages"),
                                 "days": len(item.days), "last": item.last})
        unlisted.sort(key=lambda r: (-r["pages"], r["path"]))
    problems = {}
    for f in PROBLEMS:
        got = []
        for path, item in paths.items():
            n = item.get(f)
            if not n:
                continue
            row = {"path": path, "n": n, "requests": item.get("requests"), "by": by(item, f),
                   "last": item.last,
                   "listed": None if current is None else path in current}
            if f == "slow":
                row["mean_ms"] = round(item.get("ms") / item.get("timed")) \
                    if item.get("timed") else None
            if f == "large":
                row["max_bytes"] = item.max_bytes
                row["mean_bytes"] = round(item.get("bytes") / item.get("sized")) \
                    if item.get("sized") else None
            got.append(row)
        got.sort(key=lambda r: (-r["n"], r["path"]))
        problems[f] = {"total": len(got), "rows": got[:PROBLEM_ROWS]}
    return {"crawlers": rows, "unlisted": {"total": len(unlisted), "rows": unlisted[:LIST_ROWS]},
            "problems": problems, "days": len(blobs), "_paths": paths}


def _pages(current: list[str], windows: dict) -> dict:
    """The sitemap's pages, each with every crawler's fetches in 7 and 30
    days and its last fetch (30 days and today)."""
    w7, w30 = windows[7]["_paths"], windows[30]["_paths"]
    rows = []
    for path in current:
        crawls = {}
        long, short = w30.get(path), w7.get(path)
        for name, v in (long.by.items() if long else ()):
            crawls[name] = [short.by.get(name, [0])[0] if short else 0, v[0]]
        rows.append({"path": path, "crawls": crawls})
    rows.sort(key=lambda r: (sum(c[1] for c in r["crawls"].values()), r["path"]))
    return {"total": len(rows), "rows": rows[:PAGE_ROWS]}


def _last_by(blobs: list[tuple[str, dict]]) -> dict:
    """{path: {crawler: last ISO}} over the days given."""
    out: dict[str, dict] = {}
    for _, blob in blobs:
        for name, c in (blob.get("crawlers") or {}).items():
            for path, r in (c.get("paths") or {}).items():
                if path == OTHER or not r[13]:
                    continue
                slot = out.setdefault(path, {})
                if slot.get(name) is None or r[13] > slot[name]:
                    slot[name] = r[13]
    return out


def _trend(blob: dict | None) -> dict | None:
    if blob is None:
        return None
    size = (blob.get("sitemap") or {}).get("paths")
    return {name: {"kind": c["kind"], "requests": c["requests"], "listed": c.get("listed"),
                   "sitemap": size, "unlisted": c.get("unlisted"),
                   **{p: c.get(p) for p in PROBLEMS}}
            for name, c in (blob.get("crawlers") or {}).items()}


def build(p) -> dict:
    """crawl_health.json: the sitemap now, per crawler its coverage, orphans,
    unlisted pages and problems over the last 7 and 30 days and today, the
    sitemap's pages with each crawler's fetches, and 30 days of trend."""
    from . import sitemap
    if p.view is not None:
        return {"whole_site_only": True}
    st = sitemap.state(p.live_dir)
    found = sitemap.entry_for(p.live_dir, p.today) if p.live_dir is not None else None
    current_list = sitemap.load_list(p.live_dir, found[1].get("list")) if found else None
    current = frozenset(current_list) if current_list is not None else None
    info = {"enabled": sitemap.enabled(p.config), "url": (st.get("urls") or [None])[0],
            "sources": st.get("urls") or (found[1].get("sources") if found else []) or [],
            "tried_at": st.get("tried_at"), "ok": st.get("ok"), "error": st.get("error"),
            "fetched_at": found[1].get("fetched_at") if found else None,
            "day": found[0] if found else None,
            "paths": len(current) if current is not None else None,
            "skipped": found[1].get("skipped") if found else None,
            "truncated": found[1].get("truncated") if found else None,
            "lastmod": found[1].get("lastmod") if found else None}
    first = p.anchor - timedelta(days=max(WINDOWS) - 1)
    stored = p.history.extras(p.key, first, p.anchor, ("crawl_health",))
    days, kept = [], []
    for e in p.daily:
        if e["day"] < first:
            continue
        row = p.day_entry(e)
        d = e["day"].isoformat()
        blob = (stored.get(d) or {}).get("crawl_health") if p.has_figures(e) else None
        if p.has_figures(e):
            row["crawlers"] = _trend(blob)
            if blob is not None:
                kept.append((d, blob))
        days.append(row)
    today = p.today_block()
    if today is not None and p.live_ok:
        blob = (p.snap.get("extras") or {}).get("crawl_health")
        today["crawlers"] = _trend(blob)
        if blob is not None:
            kept.append((p.today.isoformat(), blob))
    windows = {}
    for w in WINDOWS:
        since = (p.anchor - timedelta(days=w - 1)).isoformat()
        windows[w] = _window([(d, b) for d, b in kept if d >= since], current)
    pages = _pages(current_list or [], windows) if current is not None else None
    if pages is not None:
        last = _last_by(kept)
        for row in pages["rows"]:
            for name, c in row["crawls"].items():
                c.append((last.get(row["path"]) or {}).get(name))
    for w in windows.values():
        w.pop("_paths")
    return {"sitemap": info, "slow_ms": SLOW_MS, "large_bytes": LARGE_BYTES,
            "windows": {str(w): v for w, v in windows.items()}, "pages": pages,
            "days": days, "today": today}
