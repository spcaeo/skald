"""What happened to a page since it was published (DATA-CONTRACT.md,
"Page lifecycle"): page_index.json, `skald page /path` and the helper's
<page>/api/page?path=.

Publish and update dates come from the website itself, when it gives them:
`report.pages_meta` names a JSON file written at the website's deploy
({"generated", "pages": [{"path","key","locale","title","published",
"updated"}]}). Without it - or for a page it does not list - the page's
"published" is the first day the logs saw it, and `date_source` says so.

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
    for path in sorted(set(meta) | set(seen)):
        published, updated, source = _published(path, meta, seen)
        m = marks.get(path) or {}
        first_ai = [x["at"] for x in m.get("from_ai") or []]
        rows.append({
            "path": path, "title": (meta.get(path) or {}).get("title"),
            "locale": (meta.get(path) or {}).get("locale"),
            "published": published, "updated": updated, "date_source": source,
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
    if path not in meta and path not in seen:
        return {"ok": False, "error": "no such page in the website's list or the logs"}
    published, updated, source = _published(path, meta, seen)
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
            "published": published, "updated": updated, "date_source": source,
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
