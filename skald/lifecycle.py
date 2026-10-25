"""What happened to a page since it was published (DATA-CONTRACT.md,
"Page lifecycle"): page_index.json, `skald page /path` and the helper's
<page>/api/page?path=.

Publish and update dates come from the website itself, when it gives them:
`report.pages_meta` names a JSON file written at the website's deploy
({"generated", "pages": [{"path","key","locale","title","published",
"updated"}]}). Without it - or for a page it does not list - the page's
"published" is the first day the logs saw it, and `date_source` says so.

Change dates come from the site's sitemap too (sitemap_dates.py: each
<lastmod>, read once a day with the Crawl health fetch, kept across days).
A lastmod is when the site says the page last changed, never a publish
date: it fills "updated" only when the website's own list gives none
(`updated_source` "sitemap"; pages_meta wins, "website"). Each page also
carries `lastmod` (the latest change date its sitemap gave) and
`lastmod_seen` ([[date, the first day Skald saw it], ...], oldest first, at
most sitemap_dates.CAP), so "changed since day X" is lastmod >= X. A page
the sitemap lists but the logs never saw has a row too (published null).

Milestones - Googlebot's and Bingbot's first fetch, each AI crawler's and
assistant's, the first person, the first from a search engine and from each
assistant - are each page's earliest times, kept for good in history
(`page_milestones`, filled at every collect from the day's `page_firsts`,
which the audit recounts from the raw log). The first leads come from the
CMS: the first whose first touch landed on the page, and the first sent
from a form on it.

The daily series is the per-page blob (`day_extras` "pages", all pages,
kept `report.retention_days`), from the publish date - or the first day
seen - to yesterday; a day without figures says so (null), never 0.
"""
from __future__ import annotations

import json
import weakref
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

MAX_DAYS = 400
SINGLE = ("googlebot", "bingbot", "human", "from_search")
MULTI = ("ai_training", "ai_asked", "from_ai")


def _norm(path: str) -> str:
    """One page whether asked for with or without its trailing slash."""
    path = (path or "").split("?", 1)[0]
    return path if path == "/" or path.endswith("/") else path + "/"


def load_meta(config: dict) -> tuple[dict, dict]:
    """({normalised path: entry}, meta) from report.pages_meta."""
    raw = ((config or {}).get("report") or {}).get("pages_meta")
    if not raw:
        return {}, {"source": None, "generated": None}
    try:
        got = json.loads(Path(str(raw)).read_text())
    except (OSError, ValueError):
        return {}, {"source": None, "generated": None}
    pages = {}
    for entry in got.get("pages") or []:
        if isinstance(entry, dict) and str(entry.get("path", "")).startswith("/"):
            pages[_norm(entry["path"])] = entry
    return pages, {"source": "website", "generated": got.get("generated")}


def _local(iso: str | None, tz) -> str | None:
    if not iso:
        return None
    try:
        return datetime.fromisoformat(iso).astimezone(tz).isoformat(timespec="seconds")
    except ValueError:
        return iso


def milestones(history, site: str, path: str | None, tz) -> dict[str, dict]:
    """{path: {"googlebot": {"at"}, ..., "ai_training": [{"who","at"}], ...}},
    both spellings of a path merged (the earliest wins)."""
    out: dict[str, dict] = {}
    for p, kind, who, at, via in history.milestones(site, path):
        got = out.setdefault(_norm(p), {k: None for k in SINGLE} | {k: [] for k in MULTI})
        if kind in SINGLE:
            if got[kind] is None or at < got[kind]["_at"]:
                got[kind] = {"at": _local(at, tz), "_at": at,
                             **({"who": via} if kind == "from_search" else {})}
        elif kind in MULTI:
            same = next((m for m in got[kind] if m["who"] == who), None)
            if same is None:
                got[kind].append({"who": who, "at": _local(at, tz), "_at": at})
            elif at < same["_at"]:
                same.update(at=_local(at, tz), _at=at)
    for got in out.values():
        for kind in SINGLE:
            if got[kind]:
                got[kind].pop("_at", None)
        for kind in MULTI:
            got[kind].sort(key=lambda m: m["_at"])
            for m in got[kind]:
                m.pop("_at", None)
    return out


def _leads(config: dict, tz) -> tuple[dict, dict]:
    """({path: first lead landed ISO}, {path: first lead sent from ISO})."""
    from .leads import _touch, _utc, connect, counted, db_path, read_rows
    path = db_path(config)
    landed, sent = {}, {}
    if path is None:
        return landed, sent
    try:
        db = connect(path)
        try:
            rows = read_rows(db)
        finally:
            db.close()
    except Exception:                   # noqa: BLE001 - the milestone is null
        return landed, sent
    for row in rows:
        if not counted(row) or row.get("type") == "demo_opened":
            continue
        when = _utc(row.get("created_at"))
        if when is None:
            continue
        iso = when.astimezone(tz).isoformat(timespec="seconds")
        touch = _touch(row.get("first_touch")) or {}
        for target, where in ((landed, touch.get("landingPath")), (sent, row.get("page"))):
            if where:
                key = _norm(str(where))
                if key not in target or iso < target[key]:
                    target[key] = iso
    return landed, sent


def _pages_blobs(history, key: str):
    """(day, parsed pages blob) of every stored day, oldest first, one at a
    time; a blob that does not parse is left out."""
    for day, data in history.db.execute(
            "SELECT day, data FROM day_extras WHERE site = ? AND kind = 'pages' ORDER BY day",
            (key,)):
        try:
            yield day, json.loads(data)
        except ValueError:
            continue


def _first_seen(history, key: str) -> dict[str, str]:
    """{normalised path: the first day its page blob shows it}."""
    out: dict[str, str] = {}
    for day, paths in _pages_blobs(history, key):
        for p in paths:
            out.setdefault(_norm(p), day)
    return out


def _published(path: str, meta: dict, seen: dict) -> tuple[str | None, str | None, str]:
    entry = meta.get(path)
    if entry and entry.get("published"):
        return entry["published"], entry.get("updated"), "website"
    return seen.get(path), None, "first seen"


# ------------------------------------------------------------ change dates

def site_folder(config: dict, site: str | None = None) -> Path | None:
    """The site's live folder (its sitemaps/ are there): the config's own,
    or sites/<slug> beside it when the config is another site's (the helper
    and MCP answer every site with the main config)."""
    raw = ((config or {}).get("_resolved") or {}).get("live_dir")
    if not raw:
        return None
    from .config import site_name
    from .files import slug
    if site and site != site_name(config or {}):
        return Path(raw) / "sites" / slug(site)
    return Path(raw)


def sitemap_changes(config: dict, folder) -> tuple[dict, dict | None]:
    """({normalised path: {"lastmod", "lastmod_seen"}}, about) from the
    sitemap's lastmod history. Both spellings of a path are one page: their
    [date, day seen] pairs together, sorted by the day seen (then the date), a
    date kept once (the first day seen), the last CAP; `lastmod` the latest
    date. `about`: {"day", "dated", "missing", "invalid", "future"} of the
    last day merged, or None."""
    from . import sitemap, sitemap_dates
    if folder is None or not sitemap.enabled(config):
        return {}, None
    kept = sitemap_dates.load(folder)
    pairs: dict[str, list] = {}
    for path, entry in kept.items():
        pairs.setdefault(_norm(path), []).extend(
            (str(d), str(day)) for d, day in entry.get("seen") or [])
    out = {}
    for path, got in pairs.items():
        got.sort(key=lambda x: (x[1], x[0]))
        dates, seen = set(), []
        for d, day in got:
            if d not in dates:
                dates.add(d)
                seen.append([d, day])
        out[path] = {"lastmod": max(dates) if dates else None,
                     "lastmod_seen": seen[-sitemap_dates.CAP:]}
    day = sitemap_dates.last_day(folder)
    entry = (sitemap.entry_for(folder, date.fromisoformat(day)) if day else None)
    counts = (entry[1].get("lastmod") or {}) if entry and entry[0] == day else {}
    about = ({"day": day, **{k: counts.get(k) for k in ("dated", "missing", "invalid",
                                                       "future")}} if day else None)
    return out, about


def _updated(path: str, meta: dict, changes: dict) -> tuple[str | None, str | None]:
    """(updated, updated_source): the website's own date wins, then the sitemap's."""
    got = (meta.get(path) or {}).get("updated")
    if got:
        return got, "website"
    got = (changes.get(path) or {}).get("lastmod")
    return (got, "sitemap") if got else (None, None)


def _dated(path: str, meta: dict, changes: dict) -> dict:
    updated, source = _updated(path, meta, changes)
    mine = changes.get(path) or {}
    return {"updated": updated, "updated_source": source, "lastmod": mine.get("lastmod"),
            "lastmod_seen": mine.get("lastmod_seen") or []}


def page_dates(config: dict, folder) -> dict:
    """{path: {"updated", "updated_source", "lastmod", "lastmod_seen"}} for every
    page the website or the sitemap dates: what page_index.json and the story
    show (audit_lastmod.py compares them with its own reading)."""
    meta, _ = load_meta(config)
    changes, _ = sitemap_changes(config, Path(folder) if folder is not None else None)
    return {path: _dated(path, meta, changes) for path in set(meta) | set(changes)}


# ------------------------------------------------------------ page_index.json

# page_index.json is the same on a site's every page (a view gets the
# site's), so one dashboard run works it out once per site: kept per open
# History file, which a run reads and never writes while it draws.
_INDEX: "weakref.WeakKeyDictionary" = weakref.WeakKeyDictionary()


def build(p) -> dict:
    """page_index.json (the whole site's page only; a view gets the same)."""
    site = p.key.split("::", 1)[0]
    done = _INDEX.setdefault(p.history, {})
    tag = (site, p.today, p.anchor)
    if tag not in done:
        done[tag] = _build(p, site)
    return done[tag]


def _build(p, site: str) -> dict:
    meta, about = load_meta(p.config)
    folder = getattr(p, "live_dir", None)
    changes, about["lastmod"] = sitemap_changes(
        p.config, Path(folder) if folder is not None else site_folder(p.config, site))
    seen = _first_seen(p.history, site)
    marks = milestones(p.history, site, None, p.tz)
    landed, sent = _leads(p.config, p.tz)
    views = {"7": Counter(), "30": Counter(), "r30": Counter()}
    for d, blob in p.history.extras(site, p.anchor - timedelta(days=29), p.anchor,
                                    ("pages",)).items():
        recent = d >= (p.anchor - timedelta(days=6)).isoformat()
        for path, v in (blob.get("pages") or {}).items():
            k = _norm(path)
            views["30"][k] += int(v.get("views", 0))
            views["r30"][k] += int(v.get("readers", 0))
            if recent:
                views["7"][k] += int(v.get("views", 0))
    rows = []
    for path in sorted(set(meta) | set(seen) | set(changes)):
        published, _, source = _published(path, meta, seen)
        m = marks.get(path) or {}
        first_ai = [x["at"] for x in m.get("from_ai") or []]
        rows.append({
            "path": path, "title": (meta.get(path) or {}).get("title"),
            "locale": (meta.get(path) or {}).get("locale"),
            "published": published, "date_source": source, **_dated(path, meta, changes),
            "first_seen": seen.get(path),
            "days_since_publish": ((p.today - date.fromisoformat(published)).days
                                   if published else None),
            "milestones": {"googlebot": (m.get("googlebot") or {}).get("at"),
                           "bingbot": (m.get("bingbot") or {}).get("at"),
                           "human": (m.get("human") or {}).get("at"),
                           "from_search": (m.get("from_search") or {}).get("at"),
                           "from_ai": min(first_ai) if first_ai else None,
                           "lead": min([x for x in (landed.get(path), sent.get(path)) if x],
                                       default=None)},
            "views_7d": views["7"].get(path, 0), "views_30d": views["30"].get(path, 0),
            "readers_30d": views["r30"].get(path, 0)})
    return {"meta": about, "pages": rows}


# ------------------------------------------------------------ one page's story

def story(history, site: str, path: str, config: dict, tz, today: date) -> dict:
    path = _norm(path)
    meta, _ = load_meta(config)
    # One pass over the page blobs: every path's first day, and this page's
    # entries per day (each blob is parsed once, and only this page is kept).
    seen: dict[str, str] = {}
    mine: dict[str, list] = {}
    for day, pages in _pages_blobs(history, site):
        for p in pages:
            seen.setdefault(_norm(p), day)
        if pages is not None:
            mine[day] = [(p, v) for p, v in pages.items() if _norm(p) == path]
    changes, _ = sitemap_changes(config, site_folder(config, site))
    if path not in meta and path not in seen and path not in changes:
        return {"ok": False, "error": "no such page in the website's list, its sitemap or "
                                      "the logs"}
    published, _, source = _published(path, meta, seen)
    marks = (milestones(history, site, None, tz).get(path)
             or {k: None for k in SINGLE} | {k: [] for k in MULTI})
    landed, sent = _leads(config, tz)
    start = date.fromisoformat(published or seen.get(path) or today.isoformat())
    last = today - timedelta(days=1)
    start = max(start, last - timedelta(days=MAX_DAYS - 1))
    days = []
    if start <= last:
        for e in history.daily(site, start, last):
            d = e["day"].isoformat()
            row = {"day": d, "state": e["state"],
                   "days_since_publish": (e["day"] - date.fromisoformat(published)).days
                   if published else None}
            pages = mine.get(d)
            if e["state"] in ("ok", "partial") and pages is not None:
                got = Counter()
                parts = {"sources": Counter(), "assistants": Counter(), "countries": Counter()}
                for p, v in pages:
                    for k in ("readers", "views", "ai_asked", "ai_training", "search"):
                        got[k] += int(v.get(k, 0))
                    for k in parts:
                        parts[k].update({a: int(b) for a, b in (v.get(k) or {}).items()})
                row.update({k: got[k] for k in ("readers", "views", "ai_asked", "ai_training",
                                                 "search")},
                           **{k: dict(c) for k, c in parts.items()})
            else:
                row.update({k: None for k in ("readers", "views", "ai_asked", "ai_training",
                                              "search", "sources", "assistants", "countries")})
            days.append(row)
    entry = meta.get(path) or {}
    return {"ok": True, "path": path, "title": entry.get("title"), "locale": entry.get("locale"),
            "published": published, "date_source": source, **_dated(path, meta, changes),
            "first_seen": seen.get(path),
            "days_since_publish": (today - date.fromisoformat(published)).days
            if published else None,
            "milestones": {**marks,
                           "lead_landed": {"at": landed[path]} if path in landed else None,
                           "lead_sent": {"at": sent[path]} if path in sent else None},
            "days": days}


def cmd_page(ctx) -> int:
    from .store import History
    with History(ctx.db_path) as history:
        got = story(history, ctx.site, ctx.args.path, ctx.config, ctx.tz, ctx.now.date())
    if ctx.args.json or not got.get("ok"):
        ctx.out(json.dumps(got, indent=1))
        return 0 if got.get("ok") else 1
    ctx.out(f"{got['path']}  {got.get('title') or ''}")
    ctx.out(f"  published {got['published']} ({got['date_source']}), "
            f"{got['days_since_publish']} days ago; first seen {got['first_seen']}")
    if got.get("updated"):
        ctx.out(f"  changed {got['updated']} (from the {got['updated_source']})")
    for d, day in got.get("lastmod_seen") or []:
        ctx.out(f"  sitemap lastmod {d}, first seen {day}")
    for kind, value in got["milestones"].items():
        if isinstance(value, list):
            for m in value:
                ctx.out(f"  {kind:<12} {m['who']:<24} {m['at']}")
        elif value:
            ctx.out(f"  {kind:<12} {value.get('who', ''):<24} {value['at']}")
    for d in got["days"]:
        ctx.out(f"  {d['day']} {d['state']:<8} readers {d['readers']}  views {d['views']}  "
                f"AI {d['ai_asked']}/{d['ai_training']}  search {d['search']}")
    return 0


def add_command(sub) -> None:
    p = sub.add_parser("page", help="one page's story since it was published")
    p.add_argument("path")
    p.add_argument("--json", action="store_true")
    p.set_defaults(run=cmd_page)
