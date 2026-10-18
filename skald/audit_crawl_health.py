"""The second count of crawl health (day kind `crawl_health`).

Registered in audit_more.RECOUNTS. Written apart from crawl_health.py and
sitemap.py; it shares only classify.py's name lists (through the audit's
judge) and the documented thresholds and file layout:

  the crawler   a search crawler the judge named "Googlebot" is Google,
                "bingbot" Bing (any case); an AI crawler or user fetcher by
                the name and tier the audit gave it ("ai_" + tier)
  the path      the URL cut at "?", first 200 characters
  the sitemap   the list the stored day names (`sitemap.list`), read here
                from sitemaps/<list>.json beside the history with its own
                code: its name must be the first 16 hex characters of the
                SHA-256 of its paths joined by newlines (sorted), and
                sitemaps/days.json must name it for the day it says it was
                kept, a day no later than the one recounted. A day stored
                without a sitemap must have none kept before it (unless
                crawl_health.sitemap is off).
  a page        the audit's own page rule (audit.is_page)
  per path      requests; page views; 3xx but 304; 404 and 410; 5xx;
                timed lines, their milliseconds (each rounded) and how many
                took 1,000 ms or more; sized lines, their bytes, the largest
                and how many were 1,000,000 bytes or more; the latest time,
                UTC, to the second

Every path the stored day kept is compared field by field; its folded
"(all others)" entry against what the recount has beyond the kept paths; no
sitemap path may be folded. Each crawler's totals, `listed`, `unlisted` and
`unlisted_requests` are counted again over every path.
"""
from __future__ import annotations

import hashlib
import json
from datetime import timezone
from pathlib import Path

SLOW = 1000
LARGE = 1_000_000
OTHER = "(all others)"
NAMES = {"googlebot": "Google", "bingbot": "Bing"}
ORDER = ("requests", "pages", "listed", "redirects", "not_found", "server_errors", "slow",
         "large", "timed", "ms", "sized", "bytes", "max_bytes", "last")
ADDED = ("requests", "pages", "redirects", "not_found", "server_errors", "slow", "large",
         "timed", "ms", "sized", "bytes")


class _Tally:
    def __init__(self) -> None:
        self.n = dict.fromkeys(ADDED, 0)
        self.biggest = None
        self.latest = None

    def take(self, line, page: bool) -> None:
        n = self.n
        n["requests"] += 1
        n["pages"] += 1 if page else 0
        code = line.status
        if code.startswith("3") and code != "304":
            n["redirects"] += 1
        if code == "404" or code == "410":
            n["not_found"] += 1
        if code.startswith("5"):
            n["server_errors"] += 1
        if line.seconds is not None:
            took = int(round(line.seconds * 1000))
            n["timed"] += 1
            n["ms"] += took
            n["slow"] += 1 if took >= SLOW else 0
        if line.size is not None:
            n["sized"] += 1
            n["bytes"] += int(line.size)
            n["large"] += 1 if int(line.size) >= LARGE else 0
            self.biggest = int(line.size) if self.biggest is None else max(self.biggest,
                                                                          int(line.size))
        stamp = line.when.astimezone(timezone.utc)
        if self.latest is None or stamp > self.latest:
            self.latest = stamp


def _list_file(config: dict, lid: str):
    """(paths or None, why not)."""
    folder = ((config or {}).get("_resolved") or {}).get("live_dir")
    if not folder:
        return None, "no live folder to read the sitemap list from"
    try:
        with open(Path(folder) / "sitemaps" / f"{lid}.json", encoding="utf-8") as handle:
            got = json.load(handle)
    except (OSError, ValueError) as why:
        return None, f"the sitemap list {lid} cannot be read ({type(why).__name__})"
    paths = [str(p) for p in (got.get("paths") or [])] if isinstance(got, dict) else []
    digest = hashlib.sha256("\n".join(sorted(paths)).encode("utf-8")).hexdigest()
    if digest[:16] != lid:
        return None, f"the sitemap list {lid} does not hash to its name"
    return set(paths), ""


def _days_file(config: dict) -> dict:
    folder = ((config or {}).get("_resolved") or {}).get("live_dir")
    try:
        with open(Path(folder) / "sitemaps" / "days.json", encoding="utf-8") as handle:
            got = json.load(handle)
    except (OSError, ValueError, TypeError):
        return {}
    return got if isinstance(got, dict) else {}


class Recount:
    def __init__(self, config, day, tz, own) -> None:
        self.config, self.day = config, day
        self.crawlers: dict[str, dict] = {}       # name -> {"kind", "paths": {path: _Tally}}

    def _take(self, name: str, kind: str, line) -> None:
        from .audit import is_page
        mine = self.crawlers.setdefault(name, {"kind": kind, "paths": {}})
        mine["paths"].setdefault(line.url.partition("?")[0][:200], _Tally()).take(
            line, is_page(line))

    def judged(self, line, group, info) -> None:
        if group == "search_engines":
            name = NAMES.get(str((info or {}).get("name") or "").lower())
            if name:
                self._take(name, "search", line)

    def hit(self, line, group, tier, name) -> None:
        if group == "answer_engines" and name and tier:
            self._take(name, "ai_" + tier, line)

    def visit(self, lines, is_page, labels) -> None:
        return

    def _sitemap(self, blob: dict, problems: list):
        """The recount's own reading of the sitemap list the day names."""
        said = blob.get("sitemap")
        days = _days_file(self.config)
        wanted = self.day.isoformat()
        if said is None:
            off = str(((self.config or {}).get("crawl_health") or {}).get("sitemap", True)
                      ).lower() in ("false", "off", "no", "0")
            if not off and any(d < wanted for d in days):
                problems.append("crawl_health: stored without a sitemap, but a sitemap list "
                                f"was kept before {wanted}")
            return None
        lid, kept_day = str(said.get("list") or ""), str(said.get("day") or "")
        if kept_day > wanted:
            problems.append(f"crawl_health: judged by a sitemap kept {kept_day}, after the day")
        if (days.get(kept_day) or {}).get("list") != lid:
            problems.append(f"crawl_health: sitemaps/days.json does not name list {lid} "
                            f"for {kept_day}")
        paths, why = _list_file(self.config, lid)
        if paths is None:
            problems.append(f"crawl_health: {why}")
            return None
        if len(paths) != int(said.get("paths") or 0):
            problems.append(f"crawl_health: the sitemap list holds {len(paths):,} paths, "
                            f"the day says {said.get('paths')}")
        return paths

    def compare(self, stored, same, problems) -> None:
        blob = stored.get("crawl_health")
        if blob is None:
            return
        if (int(blob.get("slow_ms") or 0), int(blob.get("large_bytes") or 0)) != (SLOW, LARGE):
            problems.append("crawl_health: stored with other slow or large thresholds")
        listed = self._sitemap(blob, problems)
        kept_all = blob.get("crawlers") or {}
        for name in sorted(set(kept_all) | set(self.crawlers)):
            self._one(name, kept_all.get(name), self.crawlers.get(name), listed,
                      blob.get("sitemap") is not None, same, problems)

    def _one(self, name, kept, mine, listed, has_list, same, problems) -> None:
        what = f"crawl_health: {name}"
        kept = kept or {"paths": {}}
        paths = (mine or {}).get("paths") or {}
        if mine and kept.get("kind") not in (None, mine["kind"]):
            problems.append(f"{what}: stored as {kept.get('kind')}, the recount finds "
                            f"{mine['kind']}")
        for f in ADDED:
            same(f"{what}: {f}", int(kept.get(f) or 0), sum(t.n[f] for t in paths.values()))
        rows = kept.get("paths") or {}
        at = {f: i for i, f in enumerate(ORDER)}
        for path in sorted(p for p in rows if p != OTHER):
            row, t = rows[path], paths.get(path) or _Tally()
            for f in ADDED:
                same(f"{what} {path}: {f}", int(row[at[f]]), t.n[f])
            if row[at["max_bytes"]] != t.biggest:
                problems.append(f"{what} {path}: largest body {row[at['max_bytes']]}, the "
                                f"recount finds {t.biggest}")
            last = t.latest.isoformat(timespec="seconds") if t.latest else None
            if row[at["last"]] != last:
                problems.append(f"{what} {path}: last {row[at['last']]}, the recount "
                                f"finds {last}")
            inside = listed is not None and path in listed
            if bool(row[at["listed"]]) != inside:
                problems.append(f"{what} {path}: marked {'' if row[at['listed']] else 'not '}"
                                "in the sitemap, and it is "
                                f"{'' if inside else 'not'}".rstrip())
        rest = [t for p, t in paths.items() if p not in rows or p == OTHER]
        fold = rows.get(OTHER)
        for f in ADDED:
            same(f"{what} {OTHER}: {f}", int(fold[at[f]]) if fold else 0,
                 sum(t.n[f] for t in rest))
        if listed is not None:
            hidden = [p for p in paths if p in listed and p not in rows]
            if hidden:
                problems.append(f"{what}: sitemap paths folded or left out: "
                                f"{', '.join(sorted(hidden)[:5])}")
            outside = [t for p, t in paths.items() if p not in listed and t.n["pages"]]
            same(f"{what}: sitemap paths fetched", int(kept.get("listed") or 0),
                 sum(1 for p in paths if p in listed))
            same(f"{what}: unlisted pages", int(kept.get("unlisted") or 0), len(outside))
            same(f"{what}: page views of unlisted pages", int(kept.get("unlisted_requests") or 0),
                 sum(t.n["pages"] for t in outside))
        elif has_list is False and kept.get("listed") is not None:
            problems.append(f"{what}: sitemap figures stored with no sitemap list")
