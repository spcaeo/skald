"""The site's own sitemap: fetched like robots.txt, kept as a path list per day.

Crawl health (crawl_health.py) sets what each crawler fetched beside what the
site says it has. That needs the site's list of pages, so the live run reads
the sitemap the way robots.py reads robots.txt:

  refresh()   once a day: tried at most once an hour until a fetch of the
              local day works (then that day's list stands), as our own "site-version-check" agent
              (classify.OWN_AGENTS: it counts as ours), 5 s per file. The
              files tried: the Sitemap: lines of the robots.txt robots.py keeps
              (robots.txt) and https://<host>/sitemap.xml, plus any named in
              `crawl_health.sitemaps`. A sitemap index is followed to its
              sitemaps; gzip (.gz) is read. Only URLs on the site's own hosts
              (site.hosts) are fetched or kept: a sitemap on another host is
              skipped and counted. At most FILES files and MAX_BYTES each (a
              sitemap may hold 50,000 URLs, so robots.txt's 500 KB is too small),
              at most MAX_PATHS paths. No DOCTYPE or entity is accepted.
              `crawl_health.sitemap: false` switches the fetch off.
  for_day()   the path list a day is judged by: the list kept for that local
              day, else the latest one kept before it (a failed fetch keeps the
              last good copy). None when no list was ever kept.

Each <url>'s <lastmod> is read in the same pass (sitemap_dates.py): the
path list, and so what Crawl health is judged by, does not depend on it.

Storage, beside the history (the live folder):

  sitemaps/days.json         {day: {"list", "paths", "fetched_at", "sources",
                              "skipped", "truncated", "lastmod"}} - one entry per local day
                              a fetch worked (the day's first good fetch; it is
                              never rewritten, so a day stays judged by one list)
  sitemaps/<list>.json       {"paths": [path, ...]} sorted; <list> is the first
                              16 hex characters of the SHA-256 of the paths, one
                              per line: a list that did not change is kept once
  sitemaps/lastmod/          each path's lastmod dates across days (sitemap_dates.py)
  sitemap-state.json         the last try: urls, tried_at, ok, error, fetched_at

A path is the URL's path (no query string, no fragment), as the log writes it,
so it is compared with a log line's path as it stands. Lists no day names any
more after KEEP_DAYS days are removed.
"""
from __future__ import annotations

import gzip
import hashlib
import io
import json
import re
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

from .files import write_atomic

AGENT = "site-version-check/1"         # robots.AGENT, our own fetcher
EVERY = timedelta(hours=1)
TIMEOUT = 5
FILES = 20
MAX_BYTES = 10_000_000
MAX_PATHS = 100_000
FOLDER = "sitemaps"
DAYS_FILE = "days.json"
STATE = "sitemap-state.json"
KEEP_DAYS = 400
_LOC = re.compile(r"<loc>\s*([^<]+?)\s*</loc>", re.I)
_URL = re.compile(r"<url(?:\s[^>]*)?>(.*?)</url\s*>", re.I | re.S)
_LASTMOD = re.compile(r"<lastmod>\s*([^<]*?)\s*</lastmod>", re.I)
_UNSAFE = re.compile(rb"<!(?:DOCTYPE|ENTITY)", re.I)


# ------------------------------------------------------------ settings

def enabled(config: dict) -> bool:
    got = ((config or {}).get("crawl_health") or {}).get("sitemap", True)
    return got is not False and str(got).lower() not in ("false", "off", "no", "0")


def hosts_of(config: dict) -> list[str]:
    return [str(h).lower() for h in (((config or {}).get("site") or {}).get("hosts") or [])]


def _home(hosts: list[str]) -> str | None:
    if not hosts:
        return None
    return next((h for h in hosts if h.startswith("www.")), hosts[0])


def on_site(url: str, hosts: list[str]) -> bool:
    """An http(s) URL on one of the site's own hosts."""
    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return False
    return parts.scheme in ("http", "https") and (parts.hostname or "").lower() in hosts


def path_of(url: str) -> str | None:
    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return None
    return (parts.path or "/")[:200]


def candidates(config: dict, robots_text: str | None) -> list[str]:
    """The sitemap URLs to start from, robots.txt's first, each once."""
    hosts = hosts_of(config)
    out: list[str] = []
    named = ((config or {}).get("crawl_health") or {}).get("sitemaps") or []
    if robots_text:
        from .robots import parse
        named = list(named) + parse(robots_text)["sitemaps"]
    home = _home(hosts)
    if home:
        named = list(named) + [f"https://{home}/sitemap.xml"]
    for url in named:
        url = str(url).strip()
        if url and url not in out:
            out.append(url)
    return out


# ------------------------------------------------------------ fetching

class _SameSite(urllib.request.HTTPRedirectHandler):
    """Follows a redirect only to the site's own hosts."""

    def __init__(self, hosts: list[str]) -> None:
        self.hosts = hosts

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not on_site(newurl, self.hosts):
            raise ValueError(f"redirected off the site's hosts to {newurl[:120]}")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _getter(hosts: list[str]):
    opener = urllib.request.build_opener(_SameSite(hosts))

    def get(url: str) -> bytes:
        req = urllib.request.Request(url, headers={"User-Agent": AGENT})
        with opener.open(req, timeout=TIMEOUT) as resp:
            return resp.read(MAX_BYTES + 1)
    return get


def _unzip(body: bytes, url: str) -> bytes:
    if body[:2] != b"\x1f\x8b":
        return body
    with gzip.GzipFile(fileobj=io.BytesIO(body)) as handle:
        got = handle.read(MAX_BYTES + 1)
    if len(got) > MAX_BYTES:
        raise ValueError(f"{url}: over {MAX_BYTES:,} bytes unzipped")
    return got


def read_body(body: bytes, url: str) -> tuple[str, list[str]]:
    """("index" | "urlset" | "text", [URL]) from one sitemap file's bytes."""
    kind, locs, _ = read_entries(body, url)
    return kind, locs


def read_entries(body: bytes, url: str) -> tuple[str, list[str], list[tuple[str, str]]]:
    """read_body's (kind, [URL]) and, for a urlset, [(URL, <lastmod> text)]
    for each <url> that has a <lastmod> (its first <loc>, its first <lastmod>).
    The URL list is every <loc> in the file, as before: lastmod never changes it."""
    if len(body) > MAX_BYTES:
        raise ValueError(f"{url}: over {MAX_BYTES:,} bytes")
    body = _unzip(body, url)
    if _UNSAFE.search(body):
        raise ValueError(f"{url}: a DOCTYPE or ENTITY, refused")
    text = body.decode("utf-8", "replace").lstrip("﻿")
    head = text.lstrip()[:2000].lower()
    if head.startswith("<"):
        kind = "index" if "<sitemapindex" in head else "urlset"
        if "<urlset" not in head and "<sitemapindex" not in head:
            raise ValueError(f"{url}: neither a urlset nor a sitemap index")
        from html import unescape
        stamps = []
        if kind == "urlset":
            for block in _URL.finditer(text):
                loc, mod = _LOC.search(block.group(1)), _LASTMOD.search(block.group(1))
                if loc and mod:
                    stamps.append((unescape(loc.group(1)), unescape(mod.group(1))))
        return kind, [unescape(m.group(1)) for m in _LOC.finditer(text)], stamps
    return "text", [ln.strip() for ln in text.splitlines()
                    if ln.strip().lower().startswith(("http://", "https://"))], []


def collect(config: dict, robots_text: str | None, fetch=None) -> dict:
    """Every page path the site's sitemaps list, and each kept path's
    <lastmod> texts ("lastmod": {path: [text]}). Raises when no sitemap could
    be read at all."""
    hosts = hosts_of(config)
    fetch = fetch or _getter(hosts)
    queue = candidates(config, robots_text)
    seen: set[str] = set()
    paths: set[str] = set()
    raws: dict[str, list[str]] = {}
    sources, errors = [], []
    skipped = 0
    truncated = False
    while queue:
        url = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)
        if not on_site(url, hosts):
            skipped += 1
            continue
        if len(sources) + len(errors) >= FILES:
            truncated = True
            break
        try:
            kind, locs, stamps = read_entries(fetch(url), url)
        except Exception as why:            # noqa: BLE001 - try the others
            errors.append(f"{url}: {type(why).__name__}: {why}"[:200])
            continue
        sources.append(url)
        if kind == "index":
            queue.extend(u for u in locs if u not in seen)
            continue
        for loc in locs:
            if not on_site(loc, hosts):
                skipped += 1
                continue
            p = path_of(loc)
            if p is None:
                continue
            if len(paths) >= MAX_PATHS and p not in paths:
                truncated = True
                continue
            paths.add(p)
        for loc, text in stamps:
            p = path_of(loc) if on_site(loc, hosts) else None
            if p is not None and p in paths:
                raws.setdefault(p, []).append(text[:64])
    if not sources:
        raise ValueError("; ".join(errors) or "no sitemap on the site's hosts")
    return {"paths": sorted(paths), "sources": sources, "skipped": skipped,
            "truncated": truncated, "errors": errors, "lastmod": raws}


# ------------------------------------------------------------- storage

def list_id(paths: list[str]) -> str:
    return hashlib.sha256("\n".join(sorted(paths)).encode("utf-8")).hexdigest()[:16]


def _days(directory: Path) -> dict:
    try:
        got = json.loads((Path(directory) / FOLDER / DAYS_FILE).read_text())
    except (OSError, ValueError):
        return {}
    return got if isinstance(got, dict) else {}


def _state(directory: Path) -> dict:
    try:
        got = json.loads((Path(directory) / STATE).read_text())
    except (OSError, ValueError):
        return {}
    return got if isinstance(got, dict) else {}


def state(directory) -> dict:
    return _state(directory) if directory is not None else {}


def keep(directory: Path, day: date, got: dict, fetched_at: str, tz=None) -> dict:
    """Write the day's list (once per content) and its entry in days.json;
    with `tz` and the fetch's lastmod texts, the day's lastmod dates too
    (sitemap_dates.py: their counts in the entry, the dates in its history)."""
    folder = Path(directory) / FOLDER
    folder.mkdir(parents=True, exist_ok=True)
    lid = list_id(got["paths"])
    target = folder / f"{lid}.json"
    if not target.exists():
        write_atomic(target, json.dumps({"paths": got["paths"]}) + "\n")
    days = _days(directory)
    days[day.isoformat()] = {"list": lid, "paths": len(got["paths"]),
                             "fetched_at": fetched_at, "sources": got["sources"][:FILES],
                             "skipped": got["skipped"], "truncated": got["truncated"]}
    if tz is not None and "lastmod" in got:
        from . import sitemap_dates
        found, counts = sitemap_dates.dates(got["paths"], got["lastmod"], tz, day)
        sitemap_dates.merge(directory, day, found)
        days[day.isoformat()]["lastmod"] = {"version": sitemap_dates.VERSION, **counts,
                                            "digest": sitemap_dates.digest(found)}
    oldest = (day - timedelta(days=KEEP_DAYS)).isoformat()
    days = {d: e for d, e in sorted(days.items()) if d >= oldest}
    write_atomic(folder / DAYS_FILE, json.dumps(days, indent=1, sort_keys=True) + "\n")
    named = {e.get("list") for e in days.values()}
    for old in folder.glob("*.json"):
        if old.name != DAYS_FILE and old.stem not in named:
            try:
                old.unlink()
            except OSError:
                pass
    return days[day.isoformat()]


def refresh(config: dict, directory, now: datetime | None = None, fetch=None) -> dict:
    """Fetch the sitemaps when the last try is an hour old. The state;
    never raises."""
    if directory is None or not enabled(config) or not hosts_of(config):
        return state(directory)
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    st = _state(directory)
    try:
        tried = datetime.fromisoformat(st.get("tried_at") or "")
    except ValueError:
        tried = None
    from .robots import cached
    from .window import zone
    day = now.astimezone(zone(config)).date()
    if day.isoformat() in _days(directory):
        return st                       # the day's list is kept: it never changes
    if tried is not None and now - tried < EVERY:
        return st
    st.update(tried_at=now.isoformat(timespec="seconds"))
    try:
        got = collect(config, cached(directory), fetch)
        stamp = now.isoformat(timespec="seconds")
        entry = keep(Path(directory), day, got, stamp, zone(config))
        st.update(ok=True, error=None, fetched_at=stamp, urls=got["sources"][:FILES],
                  paths=entry["paths"], lastmod=entry.get("lastmod"), skipped=got["skipped"],
                  truncated=got["truncated"], file_errors=got["errors"][:5])
    except Exception as why:            # noqa: BLE001 - keep the last good copy
        st.update(ok=False, error=f"{type(why).__name__}: {why}"[:300])
    try:
        write_atomic(Path(directory) / STATE, json.dumps(st, sort_keys=True) + "\n")
    except OSError:
        pass
    return st


def load_list(directory, lid: str) -> list[str] | None:
    try:
        got = json.loads((Path(directory) / FOLDER / f"{lid}.json").read_text())
    except (OSError, ValueError, TypeError):
        return None
    paths = got.get("paths") if isinstance(got, dict) else None
    return [str(p) for p in paths] if isinstance(paths, list) else None


def entry_for(directory, day: date) -> tuple[str, dict] | None:
    """(the day the list was kept, its entry): that day's, else the latest before."""
    if directory is None:
        return None
    days = _days(directory)
    wanted = day.isoformat()
    kept = [d for d in days if d <= wanted]
    if not kept:
        return None
    d = max(kept)
    return d, days[d]


def for_day(config: dict, day: date | None) -> dict | None:
    """What a tally judges `day` by: {"day", "list", "paths": frozenset} or
    None (no list kept yet, the fetch is off, or no live folder)."""
    folder = ((config or {}).get("_resolved") or {}).get("live_dir")
    if not folder or day is None or not enabled(config):
        return None
    found = entry_for(folder, day)
    if found is None:
        return None
    d, entry = found
    paths = load_list(folder, str(entry.get("list") or ""))
    if paths is None:
        return None
    return {"day": d, "list": entry["list"], "paths": frozenset(paths)}
