"""The second count of the sitemap's change dates (sitemap_dates.py, and the
`updated`, `updated_source`, `lastmod` and `lastmod_seen` lifecycle.py shows).

Registered in audit_more.DAILY: run-daily's recounts step re-reads the stored
files beside the history with its own code - sitemaps/lastmod/history.json,
sitemaps/days.json, the day's sitemaps/<list>.json and the website's own page
list (report.pages_meta) - and works every page's figures out again by the
documented rule (DATA-CONTRACT-CRAWL-HEALTH.md, "Change dates"). It calls
nothing in sitemap.py, sitemap_dates.py or lifecycle.py to count; it asks
lifecycle.page_dates only for the figures it shows, to compare them.

  the file      version 1; each path's `seen` pairs [date, day]: real dates,
                a date no later than the day it was seen, the days in rising
                order, no two pairs in a row with one date, at most `cap`;
                `now` is the last pair's date or null, and when not null the
                path's `last` is the file's day
  the day       days.json's entry for the file's day says, under "lastmod":
                version 1, `dated` = the paths with a `now`, dated + missing +
                invalid + future = the day's paths, and `digest` = the first
                16 hex characters of the SHA-256 of the sorted "path<TAB>now"
                lines joined by newlines; every path with a `now` is in the
                day's list; every day a pair names has a days.json entry
  a page        its path cut at "?", a "/" added unless it ends with one; the
                pairs of every spelling together, sorted by day then date, a
                date kept once (its first pair), the last `cap`; `lastmod` the
                latest date
  updated       the website's list's `updated` for the page when it gives one
                ("website"), else the page's lastmod ("sitemap"), else null

A problem is a figure shown that the stored files do not give. Nothing is
changed: the run's outcome says the recount does not match.
"""
from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path

VERSION = 1
OFF = ("false", "off", "no", "0")


def _file(ctx) -> Path | None:
    folder = getattr(ctx, "live_dir", None)
    return Path(folder) / "sitemaps" / "lastmod" / "history.json" if folder else None


def set_up(ctx) -> bool:
    """True once a day's lastmod dates were kept for the site."""
    path = _file(ctx)
    return path is not None and path.is_file()


def _json(path: Path):
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return None


def _real(text) -> bool:
    try:
        date.fromisoformat(str(text))
    except ValueError:
        return False
    return len(str(text)) == 10


def _page(path: str) -> str:
    path = str(path).partition("?")[0]
    return path if path.endswith("/") else path + "/"


def _off(config: dict) -> bool:
    got = ((config or {}).get("crawl_health") or {}).get("sitemap", True)
    return got is False or str(got).lower() in OFF


def check_file(kept: dict, days: dict, folder: Path) -> list[str]:
    """The history file against itself, days.json and the day's list."""
    problems = []
    if kept.get("version") != VERSION:
        return [f"lastmod: history.json is version {kept.get('version')}, not {VERSION}"]
    day, cap = str(kept.get("day") or ""), int(kept.get("cap") or 0)
    paths = kept.get("paths") if isinstance(kept.get("paths"), dict) else {}
    if not _real(day):
        return [f"lastmod: history.json names no day ({day!r})"]
    now = {}
    first_kept = min(days) if days else day       # days.json keeps 400 days
    for path, entry in sorted(paths.items()):
        seen = entry.get("seen") or []
        if not seen or len(seen) > cap:
            problems.append(f"lastmod {path}: {len(seen)} dates kept, the cap is {cap}")
        for i, pair in enumerate(seen):
            if not (isinstance(pair, list) and len(pair) == 2 and _real(pair[0])
                    and _real(pair[1])):
                problems.append(f"lastmod {path}: {pair!r} is not [date, day]")
                break
            if pair[0] > pair[1]:
                problems.append(f"lastmod {path}: {pair[0]} is after the day it was seen, "
                                f"{pair[1]}")
            if i and (pair[1] <= seen[i - 1][1] or pair[0] == seen[i - 1][0]):
                problems.append(f"lastmod {path}: {pair!r} does not follow {seen[i - 1]!r}")
            if pair[1] >= first_kept and "lastmod" not in (days.get(pair[1]) or {}):
                problems.append(f"lastmod {path}: seen on {pair[1]}, a day days.json "
                                "kept no dates for")
        if entry.get("now") is not None:
            now[path] = entry["now"]
            if not seen or entry["now"] != seen[-1][0] or entry.get("last") != day:
                problems.append(f"lastmod {path}: now {entry['now']} is not its last date "
                                f"seen on {day}")
    said = (days.get(day) or {}).get("lastmod")
    if not isinstance(said, dict):
        return problems + [f"lastmod: days.json keeps no lastmod counts for {day}"]
    if said.get("version") != VERSION:
        problems.append(f"lastmod: days.json {day} is version {said.get('version')}")
    n = {k: int(said.get(k) or 0) for k in ("dated", "missing", "invalid", "future")}
    if n["dated"] != len(now):
        problems.append(f"lastmod: {day} says {n['dated']} pages dated, the file has "
                        f"{len(now)}")
    if sum(n.values()) != int((days.get(day) or {}).get("paths") or 0):
        problems.append(f"lastmod: {day}'s counts add up to {sum(n.values())}, the list "
                        f"holds {(days.get(day) or {}).get('paths')}")
    lines = "\n".join(sorted(f"{p}\t{d}" for p, d in now.items()))
    if hashlib.sha256(lines.encode("utf-8")).hexdigest()[:16] != said.get("digest"):
        problems.append(f"lastmod: the file's dates do not hash to {day}'s digest")
    listed = _json(folder / "sitemaps" / f"{(days.get(day) or {}).get('list')}.json")
    listed = set((listed or {}).get("paths") or []) if isinstance(listed, dict) else set()
    outside = sorted(p for p in now if p not in listed)
    if outside:
        problems.append(f"lastmod: dated paths not in {day}'s list: {', '.join(outside[:5])}")
    return problems


def expected(kept: dict, meta_file) -> dict:
    """{page: {"updated", "updated_source", "lastmod", "lastmod_seen"}} by the rule."""
    cap = int(kept.get("cap") or 0)
    pairs: dict[str, list] = {}
    for path, entry in (kept.get("paths") or {}).items():
        for d, day in entry.get("seen") or []:
            pairs.setdefault(_page(path), []).append((str(day), str(d)))
    meta = {}
    got = _json(Path(str(meta_file))) if meta_file else None
    listed = (got.get("pages") or []) if isinstance(got, dict) else []
    for entry in listed:
        if isinstance(entry, dict) and str(entry.get("path", "")).startswith("/"):
            meta[_page(entry["path"])] = entry
    out = {}
    for page in set(pairs) | set(meta):
        kept_dates, seen = set(), []
        for day, d in sorted(pairs.get(page) or []):
            if d not in kept_dates:
                kept_dates.add(d)
                seen.append([d, day])
        latest = max(kept_dates) if kept_dates else None
        own = (meta.get(page) or {}).get("updated")
        out[page] = {"updated": own or latest,
                     "updated_source": "website" if own else "sitemap" if latest else None,
                     "lastmod": latest, "lastmod_seen": seen[-cap:] if cap else []}
    return out


def recheck(config: dict, folder: Path, shown: dict) -> list[str]:
    """Every check; `shown` is lifecycle.page_dates' answer for the site."""
    kept = _json(folder / "sitemaps" / "lastmod" / "history.json")
    if not isinstance(kept, dict):
        return ["lastmod: sitemaps/lastmod/history.json cannot be read"]
    days = _json(folder / "sitemaps" / "days.json")
    problems = check_file(kept, days if isinstance(days, dict) else {}, folder)
    want = {} if _off(config) else expected(
        kept, ((config or {}).get("report") or {}).get("pages_meta"))
    for page in sorted(set(want) | set(shown)):
        a, b = shown.get(page) or {}, want.get(page) or {}
        for field in ("updated", "updated_source", "lastmod", "lastmod_seen"):
            if (a.get(field) or None) != (b.get(field) or None):
                problems.append(f"lastmod {page}: {field} shown {a.get(field)!r}, the files "
                                f"give {b.get(field)!r}")
    return problems


def daily(ctx, day) -> list[str] | None:
    """run-daily: the problems found (empty: they match); None when no dates are kept."""
    if not set_up(ctx):
        return None
    from . import lifecycle
    folder = Path(ctx.live_dir)
    shown = lifecycle.page_dates(ctx.config, folder)
    problems = recheck(ctx.config, folder, shown)
    ctx.out(f"sitemap lastmod: {sum(1 for v in shown.values() if v.get('lastmod'))} pages "
            "with a change date rechecked from the stored files")
    return problems
