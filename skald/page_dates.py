"""Each page's own published and modified dates, and every modified date kept
(SKALD-64). Off unless the site's setting `site.page_dates` is on.

A sitemap's <lastmod> says when the site last changed a page, once a day, as
a date (sitemap_dates.py). The page itself often says more: when it was
published and when it was last modified, to the second (page_dates_html.py
reads them). This module fetches each page's HTML to read them, and keeps
every value it ever saw, so a chart can mark each update.

When a page is fetched (refresh(), called by every live run, at most BATCH
pages and BUDGET seconds a run, at most DAY_CAP pages a local day):

  changed   its sitemap date is not the one it had at its last read
  new       never read: its published date is read once
  retry     the last read failed (or was blocked): at most once a day
  monthly   read RECHECK_DAYS ago or more: for a site whose sitemap has no
            dates, or wrong ones

in that order. The pages are the sitemap's list of the day (sitemap.entry_for)
and the LOG_PAGES pages people read most in the last LOG_DAYS days that the
sitemap does not list (the day kind `pages`), never one the site's
not-a-page list names (a feed, an API: not_pages.py). Each request is Skald's own (AGENT; classify.OWN_AGENTS,
so it is never counted as a visitor or a bot), through site_fetch.py's checked
client (public addresses only, size and time limits), following at most
MAX_REDIRECTS redirects and only on the site's own hosts.

The sitemap's dates are read again every SITEMAP_HOURS hours (the day's list,
which Crawl health is judged by, stays the day's first good fetch), a page's
value kept with its time when it is a new one. A read in which more than half
the dated pages get one and the same new value keeps nothing: that sitemap
stamps its build time, which says nothing about a page (the monthly read still
comes). The first time a site is on, the dates its sitemap history
already holds (sitemaps/lastmod/history.json) are copied in, each first seen
on the day Skald saw it.

Storage, in history (schema 16; store.ADDED_TABLES):

  page_dates   (site, path, kind, value, source, first_seen_at): one row per
               value ever seen. kind "published" or "modified"; source
               jsonld, meta or time (the page's own) or sitemap; value as
               page_dates_html.normalise keeps it; first_seen_at the UTC time
               Skald first read it. Never updated, never pruned.
  page_checks  (site, path): the last read of each page: checked_at (UTC),
               outcome (OUTCOMES), the HTTP status, an error in plain words,
               and `sitemap`, the page's sitemap date at that read.

The path is stored as the sitemap or the log spells it; readers join the
spellings of a page (view(): lifecycle._norm). page-dates.json in the live folder
keeps the day's count, the last sitemap read and the last run (not in sitemaps/,
whose clean-up removes any file days.json does not name).

What a page shows (view(), used by lifecycle.py; audit_page_dates.py works
it out again by its own SQL):

  published   the latest published value the page gave (first_seen_at, then
              the value), with its source
  modified    the latest modified value the page itself gave
  changes     every modified value, the page's and the sitemap's, one entry
              per local day: {"day", "at" (the day's latest value), "sources"}
  check       the last read: {"at", "outcome", "status", "error"}
"""
from __future__ import annotations

import json
import sqlite3
from collections import Counter
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote, urljoin, urlsplit

from .files import write_atomic
from .page_dates_html import local_day, normalise, order_key, parse

AGENT_TOKEN = "site-page-dates/"
AGENT = (f"Mozilla/5.0 (compatible; {AGENT_TOKEN}1; reads this page's published and "
         "modified dates once, and again when its sitemap says it changed)")
TABLE_DATES = """
CREATE TABLE IF NOT EXISTS page_dates (
    site          TEXT NOT NULL,
    path          TEXT NOT NULL,        -- as the sitemap or the log spells it
    kind          TEXT NOT NULL,        -- published / modified
    value         TEXT NOT NULL,        -- page_dates_html.normalise
    source        TEXT NOT NULL,        -- jsonld / meta / time / sitemap
    first_seen_at TEXT NOT NULL,        -- UTC, ISO 8601: when Skald first read it
    PRIMARY KEY (site, path, kind, value, source)
)"""
TABLE_CHECKS = """
CREATE TABLE IF NOT EXISTS page_checks (
    site       TEXT NOT NULL,
    path       TEXT NOT NULL,
    checked_at TEXT NOT NULL,           -- UTC, ISO 8601
    outcome    TEXT NOT NULL,           -- page_dates.OUTCOMES
    status     INTEGER,                 -- the HTTP status, NULL when none came
    error      TEXT,                    -- plain words, NULL when it was read
    sitemap    TEXT,                    -- the page's sitemap date at this read
    PRIMARY KEY (site, path)
)"""
KINDS = ("published", "modified")
SOURCES = ("jsonld", "meta", "time", "sitemap")
OUTCOMES = ("dated", "not_given", "not_html", "redirected", "failed", "blocked")
FAILED = ("failed", "blocked")
DAY_CAP = 500
BATCH = 6
BUDGET = 12.0
GAP = 0.5
TIMEOUT = 6.0
MAX_BYTES = 1_048_576
MAX_REDIRECTS = 3
RECHECK_DAYS = 30
RETRY_HOURS = 24
SITEMAP_HOURS = 6
BUILD_SHARE = 0.5                  # of the dated pages given one same new value: build times
BUILD_MIN = 20
LOG_DAYS = 7
LOG_PAGES = 200
STATE = "page-dates.json"
REDIRECTS = (301, 302, 303, 307, 308)
SAFE = "/%:@!$&'()*+,;=-._~"       # a path's characters kept as they are; the rest %-encoded
ON = ("true", "on", "yes", "1")


def enabled(config: dict) -> bool:
    """The site's setting `site.page_dates` (Settings, or config.yml's site:)."""
    got = ((config or {}).get("site") or {}).get("page_dates", False)
    return got is True or str(got).lower() in ON


def _utc(now: datetime | None) -> datetime:
    return (now or datetime.now(timezone.utc)).astimezone(timezone.utc)


def _stamp(now: datetime) -> str:
    return now.strftime("%Y-%m-%dT%H:%M:%SZ")


def _when(text) -> datetime | None:
    try:
        return datetime.fromisoformat(str(text).replace("Z", "+00:00"))
    except ValueError:
        return None


# ------------------------------------------------------------- the state file

def _state_path(live_dir) -> Path:
    # Beside the live files, never in sitemaps/: sitemap.keep removes every file
    # there that days.json does not name.
    return Path(live_dir) / STATE


def state(live_dir) -> dict:
    try:
        got = json.loads(_state_path(live_dir).read_text())
    except (OSError, ValueError, TypeError):
        return {}
    return got if isinstance(got, dict) else {}


def _save(live_dir, st: dict) -> None:
    try:
        write_atomic(_state_path(live_dir), json.dumps(st, sort_keys=True) + "\n")
    except OSError:
        pass


# ------------------------------------------------------------- reading rows

def rows(db, site: str) -> tuple[list, list]:
    """(page_dates rows, page_checks rows) of the site; ([], []) in a history
    without the tables (older than schema 16, or opened read-only before)."""
    try:
        dates = db.execute("SELECT path, kind, value, source, first_seen_at FROM page_dates "
                           "WHERE site = ?", (site,)).fetchall()
        checks = db.execute("SELECT path, checked_at, outcome, status, error, sitemap "
                            "FROM page_checks WHERE site = ?", (site,)).fetchall()
    except sqlite3.OperationalError:
        return [], []
    return dates, checks


def _page(path: str) -> str:
    path = (path or "").split("?", 1)[0]
    return path if path == "/" or path.endswith("/") else path + "/"


def view(db, site: str, tz) -> dict:
    """{page (spellings joined): {"published", "modified", "changes", "check"}}
    (module doc). {} when the site has no rows."""
    dates, checks = rows(db, site)
    out: dict[str, dict] = {}

    def entry(path):
        return out.setdefault(_page(path), {"published": None, "modified": None,
                                            "changes": [], "check": None, "_c": {}})

    for path, kind, value, source, seen in dates:
        e = entry(path)
        item = {"at": value, "from": source, "seen": seen}
        rank = (seen, order_key(value))
        if source != "sitemap" and kind in KINDS:
            old = e[kind]
            if old is None or rank > (old["seen"], order_key(old["at"])):
                e[kind] = item
        if kind == "modified":
            day = local_day(value, tz)
            if day:
                got = e["_c"].setdefault(day, {"day": day, "at": value, "sources": set()})
                got["sources"].add(source)
                if order_key(value) > order_key(got["at"]):
                    got["at"] = value
    for path, at, outcome, status, error, _ in checks:
        e = entry(path)
        if e["check"] is None or at > e["check"]["at"]:
            e["check"] = {"at": at, "outcome": outcome, "status": status, "error": error}
    for e in out.values():
        e["changes"] = [{**c, "sources": sorted(c["sources"])}
                        for _, c in sorted(e.pop("_c").items())]
        for kind in KINDS:
            if e[kind]:
                e[kind] = {"at": e[kind]["at"], "from": e[kind]["from"],
                           "day": local_day(e[kind]["at"], tz)}
    return out


# ------------------------------------------------------------- fetching a page

def _fetch(url: str, deadline: float):
    from . import site_fetch
    return site_fetch.fetch(url, deadline=deadline, max_bytes=MAX_BYTES, agent=AGENT)


def _header(got, name: str) -> str:
    try:
        return str(got.header(name) or "")
    except AttributeError:
        return str(((getattr(got, "headers", None) or {}).get(name) or [""])[0])


def _charset(ctype: str) -> str:
    for part in ctype.split(";")[1:]:
        k, _, v = part.strip().partition("=")
        if k.lower() == "charset" and v.strip():
            return v.strip().strip('"').lower()
    return "utf-8"


def read_page(url: str, hosts: list[str], now: datetime, fetch=None,
              deadline: float | None = None) -> dict:
    """{"outcome", "status", "error", "dates"} for one page (OUTCOMES)."""
    from . import site_fetch
    from .sitemap import on_site
    get = fetch or _fetch
    deadline = deadline if deadline is not None else time.monotonic() + TIMEOUT
    for hop in range(MAX_REDIRECTS + 1):
        try:
            got = get(url, deadline)
        except site_fetch.Refused as why:
            return {"outcome": "failed", "status": None, "error": str(why)[:200], "dates": None}
        except OSError as why:
            return {"outcome": "failed", "status": None,
                    "error": (str(why) or "the connection failed")[:200], "dates": None}
        status = int(getattr(got, "status", 0) or 0)
        if status in REDIRECTS:
            where = _header(got, "location").strip()
            if not where:
                return {"outcome": "failed", "status": status,
                        "error": "a redirect without an address", "dates": None}
            nxt = urljoin(url, where)
            if not on_site(nxt, hosts):
                return {"outcome": "redirected", "status": status,
                        "error": "it redirects to another site", "dates": None}
            if hop == MAX_REDIRECTS:
                return {"outcome": "failed", "status": status,
                        "error": f"more than {MAX_REDIRECTS} redirects", "dates": None}
            url = nxt
            continue
        body = bytes(getattr(got, "body", b"") or b"")
        if status != 200:
            sniff = body[:20000].lower()
            blocked = status in (403, 429, 503) and (
                _header(got, "cf-mitigated") or b"challenge" in sniff or b"captcha" in sniff)
            return {"outcome": "blocked" if blocked else "failed", "status": status,
                    "error": ("a bot check stopped the request" if blocked
                              else f"the page answered {status}"), "dates": None}
        ctype = _header(got, "content-type").lower()
        if ctype and "html" not in ctype:
            return {"outcome": "not_html", "status": status, "error": None, "dates": None}
        try:
            text = body.decode(_charset(ctype), errors="replace")
        except LookupError:
            text = body.decode("utf-8", errors="replace")
        dates = parse(text, urlsplit(url).path or "/", now)
        dated = any(dates.values())
        return {"outcome": "dated" if dated else "not_given", "status": status,
                "error": None, "dates": dates}
    return {"outcome": "failed", "status": None, "error": "too many redirects", "dates": None}


# ------------------------------------------------------------- which pages, when

def _log_pages(history, site: str, today: date, config: dict) -> list[str]:
    from .not_pages import from_config
    rules = from_config(config)
    readers: dict[str, int] = {}
    for _, kinds in history.extras(site, today - timedelta(days=LOG_DAYS),
                                   today - timedelta(days=1), ("pages",)).items():
        for path, v in ((kinds or {}).get("pages") or {}).items():
            if not isinstance(path, str) or not path.startswith("/") or "?" in path:
                continue
            if rules.match(path, path):
                continue
            readers[path] = readers.get(path, 0) + int((v or {}).get("readers") or 0)
    ranked = sorted((p for p, n in readers.items() if n > 0), key=lambda p: (-readers[p], p))
    return ranked[:LOG_PAGES]


def candidates(config: dict, live_dir, history, site: str, today: date) -> list[str]:
    """The sitemap's pages of the day, then the most read pages it does not list;
    never an address the site's not-a-page list names (a feed, an API)."""
    from . import sitemap
    from .not_pages import from_config
    rules = from_config(config)
    found = sitemap.entry_for(live_dir, today)
    listed = (sitemap.load_list(live_dir, str(found[1].get("list") or "")) or []) if found else []
    listed = [p for p in listed if not rules.match(p.split("?", 1)[0], p)]
    have = {_page(p) for p in listed}
    extra = [p for p in _log_pages(history, site, today, config) if _page(p) not in have]
    return list(dict.fromkeys(listed + extra))


def sitemap_now(dates: list) -> dict[str, str]:
    """{path: the latest sitemap value} from page_dates rows."""
    best: dict[str, tuple] = {}
    for path, kind, value, source, seen in dates:
        if kind == "modified" and source == "sitemap":
            rank = (seen, order_key(value), value)
            if path not in best or rank > best[path]:
                best[path] = rank
    return {p: r[2] for p, r in best.items()}


def due(paths: list[str], checks: dict, latest: dict, now: datetime) -> list[tuple[str, str]]:
    """[(path, why)] in the order they are read (module doc)."""
    groups: dict[str, list] = {"changed": [], "new": [], "retry": [], "monthly": []}
    for p in paths:
        c = checks.get(p)
        if c is None:
            groups["new"].append(p)
            continue
        at = _when(c["checked_at"])
        age = (now - at) if at else timedelta(days=RECHECK_DAYS)
        if c["outcome"] in FAILED:
            if age >= timedelta(hours=RETRY_HOURS):
                groups["retry"].append(p)
            continue
        if latest.get(p) and latest[p] != c["sitemap"]:
            groups["changed"].append(p)
        elif age >= timedelta(days=RECHECK_DAYS):
            groups["monthly"].append(p)
    return [(p, why) for why in ("changed", "new", "retry", "monthly") for p in groups[why]]


# ------------------------------------------------------------- writing rows

def record(db, site: str, path: str, got: dict, sitemap_value, now: datetime) -> None:
    stamp = _stamp(now)
    with db:
        db.execute("INSERT OR REPLACE INTO page_checks (site, path, checked_at, outcome, "
                   "status, error, sitemap) VALUES (?, ?, ?, ?, ?, ?, ?)",
                   (site, path, stamp, got["outcome"], got["status"], got["error"],
                    sitemap_value))
        for kind, found in (got.get("dates") or {}).items():
            if found:
                db.execute("INSERT OR IGNORE INTO page_dates (site, path, kind, value, source, "
                           "first_seen_at) VALUES (?, ?, ?, ?, ?, ?)",
                           (site, path, kind, found[0], found[1], stamp))


def import_history(db, site: str, live_dir, tz) -> int:
    """Copy the sitemap's kept dates (sitemaps/lastmod/history.json) in once:
    each [date, day seen] a sitemap row first seen at that local day's start."""
    from . import sitemap_dates
    added = 0
    with db:
        for path, entry in sitemap_dates.load(live_dir).items():
            for d, day in entry.get("seen") or []:
                try:
                    start = datetime.combine(date.fromisoformat(str(day)), datetime.min.time(),
                                             tz).astimezone(timezone.utc)
                except ValueError:
                    continue
                cur = db.execute("INSERT OR IGNORE INTO page_dates (site, path, kind, value, "
                                 "source, first_seen_at) VALUES (?, ?, 'modified', ?, "
                                 "'sitemap', ?)", (site, path, str(d), _stamp(start)))
                added += cur.rowcount
    return added


def read_sitemap(db, site: str, config: dict, live_dir, now: datetime, fetch=None) -> int | str:
    """The sitemap's dates now: a page's latest valid one is kept, with its time,
    when it is not the page's latest sitemap value already. A value seen before
    (the date went back) is first seen again now. "build_times" (nothing kept)
    when one and the same new value is on more than BUILD_SHARE of the dated
    pages (and BUILD_MIN at least): the sitemap stamps its build time, not each
    page's change. A first value, or a date followed by a time, counts as new
    too: only the one shared stamp tells a build apart from real edits."""
    from . import sitemap
    from .robots import cached
    got = sitemap.collect(config, cached(live_dir), fetch)
    stamp = _stamp(now)
    latest = sitemap_now(rows(db, site)[0])
    new = {}
    dated = 0
    for path, texts in (got.get("lastmod") or {}).items():
        values = [v for v in (normalise(t, now) for t in texts) if v]
        if not values:
            continue
        dated += 1
        value = max(values, key=order_key)
        if latest.get(path) != value:
            new[path] = value
    shared = max(Counter(new.values()).values(), default=0)
    if shared >= BUILD_MIN and shared > dated * BUILD_SHARE:
        return "build_times"
    added = 0
    with db:
        for path, value in new.items():
            cur = db.execute("INSERT OR IGNORE INTO page_dates (site, path, kind, value, source, "
                             "first_seen_at) VALUES (?, ?, 'modified', ?, 'sitemap', ?)",
                             (site, path, value, stamp))
            if not cur.rowcount:
                db.execute("UPDATE page_dates SET first_seen_at = ? WHERE site = ? AND path = ? "
                           "AND kind = 'modified' AND value = ? AND source = 'sitemap'",
                           (stamp, site, path, value))
            added += 1
    return added


# ------------------------------------------------------------- the live run's step

def refresh(config: dict, live_dir, history, site: str, now: datetime | None = None,
            fetch=None, sitemap_fetch=None, sleep=time.sleep, clock=time.monotonic) -> dict:
    """One live run's share (module doc). A page that fails is recorded as
    failed and the run goes on; a history that cannot be written ends the run's
    share (said in "error"); the state is saved either way. Returns what it did:
    {"on", "read", "dated", "failed", "left_today", ...}."""
    if live_dir is None or not enabled(config):
        return {"on": False}
    from . import sitemap
    from .config import site_name
    from .window import zone
    now = _utc(now)
    tz = zone(config)
    today = now.astimezone(tz).date()
    st = state(live_dir)
    if st.get("day") != today.isoformat():
        st.update(day=today.isoformat(), fetched=0)
    db = history.db
    out = {"on": True, "read": 0, "dated": 0, "failed": 0, "sitemap": None}
    left = max(0, DAY_CAP - int(st.get("fetched") or 0))
    todo: list = []
    latest: dict = {}
    try:
        if not st.get("imported"):
            out["imported"] = import_history(db, site, live_dir, tz)
            st["imported"] = _stamp(now)
        last = _when(st.get("sitemap_at"))
        if sitemap.enabled(config) and (last is None
                                        or now - last >= timedelta(hours=SITEMAP_HOURS)):
            st["sitemap_at"] = _stamp(now)
            try:
                out["sitemap"] = read_sitemap(db, site, config, live_dir, now, sitemap_fetch)
                st["sitemap_error"] = None
            except Exception as why:      # noqa: BLE001 - the last good dates stand
                st["sitemap_error"] = f"{type(why).__name__}: {why}"[:300]
        if left:
            dates, checks = rows(db, site)
            latest = sitemap_now(dates)
            by_path = {c[0]: {"checked_at": c[1], "outcome": c[2], "sitemap": c[5]}
                       for c in checks}
            todo = due(candidates(config, live_dir, history, site, today), by_path, latest, now)
        hosts = sitemap.hosts_of(config) or [site_name(config).lower()]
        home = sitemap._home(hosts)
        stop = clock() + BUDGET
        for i, (path, _) in enumerate(todo[:min(BATCH, left)]):
            if clock() > stop - 2:
                break
            if i:
                sleep(GAP)
            try:
                got = read_page(f"https://{home}{quote(path, safe=SAFE)}", hosts, now, fetch,
                                min(stop, clock() + TIMEOUT))
            except Exception as why:      # noqa: BLE001 - one page never stops the rest
                got = {"outcome": "failed", "status": None, "dates": None,
                       "error": f"{type(why).__name__}: {why}"[:200]}
            record(db, site, path, got, latest.get(path), now)
            st["fetched"] = int(st.get("fetched") or 0) + 1
            out["read"] += 1
            key = "dated" if got["outcome"] == "dated" else \
                "failed" if got["outcome"] in FAILED else "other"
            out[key] = out.get(key, 0) + 1
    except Exception as why:              # noqa: BLE001 - a locked history: the next run
        out["error"] = f"{type(why).__name__}: {why}"[:300]
    finally:
        out["waiting"] = max(0, len(todo) - out["read"])
        out["left_today"] = max(0, DAY_CAP - int(st.get("fetched") or 0))
        st["last_run"] = {"at": _stamp(now), **{k: v for k, v in out.items() if k != "on"}}
        _save(live_dir, st)
    return out


def live_step(ctx) -> None:
    """cli._after_live: refresh() when the site has it on; a failure is said, never raised."""
    if not enabled(ctx.config):
        return
    try:
        with ctx.history() as history:
            refresh(ctx.config, ctx.live_dir, history, ctx.site)
    except Exception as why:            # noqa: BLE001 - never fails the live run
        ctx.err(f"page dates: {type(why).__name__}: {why}")
