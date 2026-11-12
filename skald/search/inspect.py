"""Index status per page: Search Console's URL Inspection, kept in history (2.48).

After each good Search Console sync (search/sync.py run), Skald asks Google's URL
Inspection API (https://developers.google.com/webmaster-tools/v1/urlInspection.index/inspect,
the read-only scope the sync already uses) about a few of the site's pages and keeps
Google's answer as given, in the `search_inspect` table (history schema 15):

  verdict           PASS, PARTIAL, FAIL, NEUTRAL (Google's own)
  coverage          Google's coverage words, e.g. "Submitted and indexed",
                    "Crawled - currently not indexed"
  status            one of STATUSES, read from the two above (status_of)
  indexing, robots, page_fetch   Google's indexingState, robotsTxtState, pageFetchState
  last_crawl        Google's lastCrawlTime (UTC), None when Google gives none
  crawled_as        MOBILE / DESKTOP
  google_canonical  the canonical Google chose; user_canonical the page's own

One row per page and Pacific day (Google's quota day): a page asked twice in a
day keeps the later answer. Kept KEEP_DAYS days, so a page's history shows when
it went in or out of the index.

Which pages: the pages Search Console showed in the last PAGE_DAYS days (most
impressions first) and the pages people read that Googlebot fetched
(page_milestones), never asked yet first, then the longest ago; a page asked in
the last FRESH_HOURS is not asked again. At most `search_console.inspect_per_day`
(PER_DAY) a Pacific day, under Google's 2,000 a day per property; 0 turns it off.

A failure (Google's quota, no permission) is kept in the sync state under
"inspect" and never fails the sync or changes a figure. These are Google's
labels, never counts of Skald's: audit_search_pages.py recounts the per-status
counts the MCP shows from the rows by its own road.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

from ..config import setting
from . import http

API = "https://searchconsole.googleapis.com/v1/urlInspection/index:inspect"
PER_DAY = 200
PAGE_DAYS = 28
FRESH_HOURS = 20
KEEP_DAYS = 486
STATUSES = ("indexed", "crawled_not_indexed", "discovered_not_indexed", "unknown_to_google",
            "excluded", "not_known")
WORDS = {"indexed": "indexed", "crawled_not_indexed": "crawled, not indexed",
         "discovered_not_indexed": "discovered, not indexed",
         "unknown_to_google": "not seen by Google yet", "excluded": "excluded",
         "not_known": "not known"}

TABLE = """
CREATE TABLE IF NOT EXISTS search_inspect (
    site             TEXT NOT NULL,
    url              TEXT NOT NULL,      -- the address asked about
    path             TEXT NOT NULL,
    day              TEXT NOT NULL,      -- Google's quota day (Pacific), YYYY-MM-DD
    inspected_at     TEXT NOT NULL,      -- UTC, ISO 8601
    status           TEXT NOT NULL,      -- inspect.STATUSES
    verdict          TEXT,               -- Google's: PASS, PARTIAL, FAIL, NEUTRAL
    coverage         TEXT,               -- Google's coverageState words
    indexing         TEXT,
    robots           TEXT,
    page_fetch       TEXT,
    last_crawl       TEXT,               -- Google's lastCrawlTime, NULL when not given
    crawled_as       TEXT,
    google_canonical TEXT,
    user_canonical   TEXT,
    source           TEXT NOT NULL,      -- the property asked
    PRIMARY KEY (site, url, day)
)"""


def status_of(verdict, coverage) -> str:
    """Google's verdict and coverage words as one of STATUSES."""
    words = str(coverage or "").lower()
    if verdict in ("PASS", "PARTIAL") or words.startswith("submitted and indexed") \
            or words.startswith("indexed"):
        return "indexed"
    if words.startswith("crawled"):
        return "crawled_not_indexed"
    if words.startswith("discovered"):
        return "discovered_not_indexed"
    if "unknown to google" in words:
        return "unknown_to_google"
    if verdict in ("FAIL", "NEUTRAL") and words:
        return "excluded"
    return "not_known"


def row_of(site: str, url: str, prop: str, answer: dict, now: datetime) -> dict:
    """One answer of Google's as a row (nothing invented: missing stays None)."""
    from .sync import pacific_today
    got = ((answer or {}).get("inspectionResult") or {}).get("indexStatusResult") or {}
    text = lambda k: (str(got[k]) if got.get(k) not in (None, "") else None)  # noqa: E731
    return {"site": site, "url": url, "path": urlsplit(url).path or "/",
            "day": pacific_today(now).isoformat(),
            "inspected_at": now.astimezone(timezone.utc).isoformat(timespec="seconds"),
            "status": status_of(got.get("verdict"), got.get("coverageState")),
            "verdict": text("verdict"), "coverage": text("coverageState"),
            "indexing": text("indexingState"), "robots": text("robotsTxtState"),
            "page_fetch": text("pageFetchState"), "last_crawl": text("lastCrawlTime"),
            "crawled_as": text("crawledAs"), "google_canonical": text("googleCanonical"),
            "user_canonical": text("userCanonical"), "source": prop}


COLUMNS = ("site", "url", "path", "day", "inspected_at", "status", "verdict", "coverage",
           "indexing", "robots", "page_fetch", "last_crawl", "crawled_as", "google_canonical",
           "user_canonical", "source")


def write(db, rows: list[dict], now: datetime) -> int:
    if not rows:
        return 0
    marks = ",".join("?" * len(COLUMNS))
    with db:
        db.executemany(f"INSERT OR REPLACE INTO search_inspect ({','.join(COLUMNS)}) "
                       f"VALUES ({marks})", [tuple(r[c] for c in COLUMNS) for r in rows])
        cut = (now.date() - timedelta(days=KEEP_DAYS)).isoformat()
        db.execute("DELETE FROM search_inspect WHERE day < ?", (cut,))
    return len(rows)


# ------------------------------------------------------------------ which pages

def _host(config) -> str | None:
    hosts = setting(config or {}, "site", "hosts") or []
    return str(hosts[0]).lower().split(":", 1)[0] if hosts else None


def candidates(db, site: str, config, now: datetime) -> list[str]:
    """Addresses to ask about, in order: never asked first (Search Console's pages by
    impressions, then pages people read that Googlebot fetched), then the longest ago."""
    first = (now.date() - timedelta(days=PAGE_DAYS)).isoformat()
    shown: dict = {}
    for (data,) in db.execute("SELECT data FROM search_days WHERE site = ? AND engine = 'google' "
                              "AND kind = 'page' AND day >= ?", (site, first)):
        for key, _c, i, _p in json.loads(data).get("rows") or []:
            shown[key] = shown.get(key, 0) + i
    urls = sorted(shown, key=lambda k: (-shown[k], k))
    hosts = [urlsplit(u) for u in urls]
    base = (f"{hosts[0].scheme}://{hosts[0].netloc}" if hosts
            else (f"https://{_host(config)}" if _host(config) else None))
    if base:
        have = {urlsplit(u).path for u in urls}
        try:
            read = db.execute(
                "SELECT h.path FROM page_milestones h JOIN page_milestones g "
                "ON g.site = h.site AND g.path = h.path AND g.kind = 'googlebot' "
                "WHERE h.site = ? AND h.kind = 'human' ORDER BY h.path", (site,)).fetchall()
        except Exception:                               # noqa: BLE001 - an older history
            read = []
        urls += [base + p for (p,) in read if p.startswith("/") and p not in have]
    last: dict = {}
    try:
        for url, at in db.execute("SELECT url, MAX(inspected_at) FROM search_inspect "
                                  "WHERE site = ? GROUP BY url", (site,)):
            last[url] = at
    except Exception:                                   # noqa: BLE001 - no table yet
        pass
    fresh = (now - timedelta(hours=FRESH_HOURS)).astimezone(timezone.utc) \
        .isoformat(timespec="seconds")
    never = [u for u in urls if u not in last]
    old = sorted((u for u in urls if u in last and last[u] < fresh), key=lambda u: last[u])
    return never + old


def asked_today(db, site: str, now: datetime) -> int:
    from .sync import pacific_today
    try:
        return int(db.execute("SELECT COUNT(*) FROM search_inspect WHERE site = ? AND day = ?",
                              (site, pacific_today(now).isoformat())).fetchone()[0])
    except Exception:                                   # noqa: BLE001
        return 0


def per_day(config) -> int:
    got = setting(config or {}, "search_console", "inspect_per_day")
    try:
        return max(0, min(2000, int(PER_DAY if got is None else got)))
    except (TypeError, ValueError):
        return PER_DAY


def inspect_one(client, prop: str, url: str, api: str = API) -> dict:
    """Google's answer about one address (client: a search/google.Client)."""
    return client.call_url("POST", api, {"inspectionUrl": url, "siteUrl": prop,
                                         "languageCode": "en-US"})


def run(job, client, prop: str, limit: int | None = None) -> dict:
    """Ask about the next pages within today's budget; keep every answer.
    Returns {"asked", "kept", "error"}; never raises for Google's refusals."""
    now = job.now
    with job.history() as h:
        budget = per_day(job.config) - asked_today(h.db, job.site, now)
        todo = candidates(h.db, job.site, job.config, now) if budget > 0 else []
    todo = todo[:max(0, min(budget, limit if limit is not None else budget))]
    rows, error = [], None
    given = getattr(job, "api", None) or {}
    # A job pointed at another Search Console (a test's fake server) never asks Google's.
    api = given.get("google_inspect") or (None if given.get("google_api") else API)
    if api is None:
        return {"asked": 0, "kept": 0, "error": None}
    for url in todo:
        try:
            rows.append(row_of(job.site, url, prop, inspect_one(client, prop, url, api), now))
        except http.Failed as why:
            error = str(why)
            break
    with job.history() as h:
        kept = write(h.db, rows, now)
    return {"asked": len(todo), "kept": kept, "error": error}


# ------------------------------------------------------------------ reading

def _row(r: dict) -> dict:
    out = dict(r)
    out["verdict_words"] = WORDS.get(r["status"], r["status"])
    if r.get("google_canonical") and r.get("user_canonical"):
        out["canonical_match"] = r["google_canonical"] == r["user_canonical"]
    else:
        out["canonical_match"] = None
    return out


def latest(db, site: str, path: str) -> dict | None:
    """The newest answer about any address of the path, with the one before it
    when the status changed (None: never asked)."""
    try:
        cur = db.execute(f"SELECT {','.join(COLUMNS)} FROM search_inspect WHERE site = ? "
                         "AND path = ? ORDER BY inspected_at DESC LIMIT 30", (site, path))
        rows = [dict(zip(COLUMNS, r)) for r in cur]
    except Exception:                                   # noqa: BLE001 - no table yet
        return None
    if not rows:
        return None
    out = _row(rows[0])
    changed = next((r for r in rows[1:] if r["status"] != rows[0]["status"]), None)
    out["before"] = ({"status": changed["status"], "inspected_at": changed["inspected_at"]}
                     if changed else None)
    return out


def counts(db, site: str) -> dict | None:
    """Each page's newest answer, counted by status, with the pages not indexed."""
    try:
        rows = db.execute(
            "SELECT s.path, s.status, s.coverage, s.inspected_at FROM search_inspect s "
            "JOIN (SELECT url, MAX(inspected_at) AS at FROM search_inspect WHERE site = ? "
            "GROUP BY url) n ON n.url = s.url AND n.at = s.inspected_at WHERE s.site = ?",
            (site, site)).fetchall()
    except Exception:                                   # noqa: BLE001 - no table yet
        return None
    if not rows:
        return None
    by: dict = {}
    for _p, status, _c, _a in rows:
        by[status] = by.get(status, 0) + 1
    words = {WORDS.get(k, k): n for k, n in sorted(by.items(), key=lambda kv: -kv[1])}
    return {"pages": len(rows), "by_status": by, "by_verdict": words,
            "not_indexed": sorted(({"path": p, "status": s, "coverage": c, "inspected_at": a}
                                   for p, s, c, a in rows if s != "indexed"),
                                  key=lambda r: r["path"])[:50]}
