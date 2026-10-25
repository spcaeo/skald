"""The second count of page_trends.json (page_trends.py): each page's visits
and AI reads by day, and the pages changed lately.

Registered in audit_more.DAILY: run-daily's recounts step reads history with
its own SQL (the `days` table for each day's state, `day_extras` for the
blobs) and the change dates by audit_lastmod.expected (the audit's own
reading of the stored sitemap dates and the website's list), and works every
figure of the file out again. It calls nothing in page_trends.py,
landings.py, crawl_health.py or lifecycle.py to count; it asks
page_trends.figures only for the figures the file shows, to compare them.

  a day         `days` row: verified and no partial_from / partial_until is
                whole ("ok"); verified with either is "partial"; not verified
                "withheld"; no row "missing" (or "before" the site's first row)
  landings      the stored blob, as it is (its own second count is
                audit_landings.py, against the raw lines)
  fetches       the stored ai_fetches rows summed by path and assistant; the
                200 paths with most fetches kept (ties by path), every other
                path summed per assistant into "(all others)"
  a page        its path cut at "?" and "#", a "/" added unless it ends with one
  changed       a page whose change date is within the last 30 days to the
                file's last day; from that date on, over the whole days only:
                its visits and search visits (every spelling of the page in
                the day's landings), the first day with a search visit, and
                whether the Google crawler's paths in that day's crawl health
                hold the page with a request
  build times   of the pages with a sitemap date, more than half on one date
                (at least 10 dated pages)

A problem is a figure the file shows that history does not give. Nothing is
changed: the run's outcome says the recount does not match.
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

WINDOW = 180
RECENT = 30
KEEP = 200
REST = "(all others)"


def set_up(ctx) -> bool:
    """True once a day's visits by landing page were stored for the site."""
    try:
        with ctx.history() as history:
            return history.db.execute("SELECT 1 FROM day_extras WHERE site = ? AND kind = "
                                      "'landings' LIMIT 1", (ctx.site,)).fetchone() is not None
    except Exception:              # noqa: BLE001 - no history yet: nothing to recount
        return False


def _page(path) -> str:
    cut = str(path or "")
    for mark in ("?", "#"):
        cut = cut.split(mark, 1)[0]
    return cut if cut.endswith("/") else cut + "/"


def states(db, site: str, first: date, last: date) -> dict:
    """{day: state} by the audit's own reading of the days table."""
    start = db.execute("SELECT MIN(day) FROM days WHERE site = ?", (site,)).fetchone()[0]
    rows = {r[0]: r for r in db.execute(
        "SELECT day, verified, partial_from, partial_until FROM days WHERE site = ? AND "
        "day BETWEEN ? AND ?", (site, first.isoformat(), last.isoformat()))}
    out, d = {}, first
    while d <= last:
        k = d.isoformat()
        r = rows.get(k)
        out[k] = ("before" if start is None or k < start else "missing") if r is None else (
            "withheld" if not r[1] else "partial" if (r[2] or r[3]) else "ok")
        d += timedelta(days=1)
    return out


def blobs(db, site: str, first: date, last: date) -> dict:
    out: dict = {}
    for day, kind, data in db.execute(
            "SELECT day, kind, data FROM day_extras WHERE site = ? AND day BETWEEN ? AND ? AND "
            "kind IN ('landings', 'ai_fetches', 'crawl_health')",
            (site, first.isoformat(), last.isoformat())):
        out.setdefault(day, {})[kind] = json.loads(data)
    return out


def fetches(rows) -> dict:
    per: dict = {}
    for row in rows or []:
        per.setdefault(str(row[2]), Counter())[str(row[1])] += int(row[3])
    ranked = sorted(per, key=lambda p: (-sum(per[p].values()), p))
    paths = {p: dict(per[p]) for p in ranked[:KEEP]}
    tail = Counter()
    for p in ranked[KEEP:]:
        tail += per[p]
    if tail:
        paths[REST] = dict(tail)
    return {"paths": paths, "folded": len(ranked[KEEP:])}


def recent(dates: dict, st: dict, kept: dict, last: date) -> dict:
    """The changed block by the rule above."""
    since = (last - timedelta(days=RECENT - 1)).isoformat()
    rows = {}
    for path, d in dates.items():
        when = d.get("updated")
        if not when or when < since:
            continue
        me = _page(path)
        visits = search = missed = 0
        whole, first_search, found, crawled, last_fetch = [], None, False, False, None
        short = False
        for day in sorted(st):
            if day < when:
                continue
            got = kept.get(day) or {}
            if st[day] != "ok" or got.get("landings") is None:
                missed += 1
            if st[day] != "ok":
                continue
            if got.get("landings") is not None:
                whole.append(day)
                listed = got["landings"].get("pages") or {}
                mine = [r for p, r in listed.items() if p != REST and _page(p) == me]
                if not mine and int(got["landings"].get("folded") or 0):
                    short = True
                visits += sum(int(r[0]) for r in mine)
                s = sum(int(r[3]) for r in mine)
                search += s
                if s and first_search is None:
                    first_search = day
            if got.get("crawl_health") is not None:
                crawled = True
                g = ((got["crawl_health"].get("crawlers") or {}).get("Google") or {})
                if any(p != REST and _page(p) == me and int(r[0])
                       for p, r in (g.get("paths") or {}).items()):
                    found, last_fetch = True, day
        rows[path] = {"changed": when, "visits": visits if whole else None,
                      "search": search if whole else None, "first_search": first_search,
                      "counted_from": whole[0] if whole else None, "unmeasured": missed,
                      "at_least": short, "google": found if crawled else None,
                      "google_last": last_fetch}
    return rows


def build_times(dates: dict):
    got = Counter(d["lastmod"] for d in dates.values() if d.get("lastmod"))
    total = sum(got.values())
    if total < 10:
        return None
    top = max(got.values())
    day = min(d for d, n in got.items() if n == top)
    return {"day": day, "pages": top, "of": total} if top * 2 > total else None


def recheck(db, site: str, last: date, dates: dict, shown: dict) -> list[str]:
    """Every check; `shown` is page_trends.figures' answer for the same days."""
    problems = []
    first = last - timedelta(days=WINDOW - 1)
    st, kept = states(db, site, first, last), blobs(db, site, first, last)
    for row in shown.get("days") or []:
        day = row["day"]
        if row["state"] != st.get(day):
            problems.append(f"page trends {day}: state {row['state']}, history says {st.get(day)}")
            continue
        if st[day] not in ("ok", "partial"):
            continue
        got = kept.get(day) or {}
        if row.get("landings") != got.get("landings"):
            problems.append(f"page trends {day}: landings are not the stored blob")
        want = fetches(got["ai_fetches"].get("rows")) if got.get("ai_fetches") is not None else None
        if row.get("fetches") != want:
            problems.append(f"page trends {day}: fetches by page and assistant do not match "
                            "the stored rows")
    want = recent(dates, st, kept, last)
    got = {r["path"]: r for r in (shown.get("changed") or {}).get("pages") or []}
    for path in sorted(set(want) | set(got)):
        a, b = got.get(path) or {}, want.get(path) or {}
        for field in ("changed", "visits", "search", "first_search", "counted_from",
                      "unmeasured", "at_least", "google", "google_last"):
            if a.get(field) != b.get(field):
                problems.append(f"page trends, changed {path}: {field} shown {a.get(field)!r}, "
                                f"history gives {b.get(field)!r}")
    counts = (shown.get("changed") or {}).get("counts") or {}
    measured = [r for r in want.values() if r["visits"] is not None]
    for name, n in (("pages", len(want)), ("visited", sum(1 for r in measured if r["visits"])),
                    ("searched", sum(1 for r in measured if r["search"])),
                    ("none", sum(1 for r in measured if not r["visits"])),
                    ("google", sum(1 for r in want.values() if r["google"]))):
        if counts.get(name) != n:
            problems.append(f"page trends, changed: {name} shown {counts.get(name)!r}, "
                            f"history gives {n}")
    if shown.get("same_day") != build_times(dates):
        problems.append(f"page trends: same-day dates shown {shown.get('same_day')!r}, the "
                        f"dates give {build_times(dates)!r}")
    return problems


def _dates(ctx) -> dict:
    from .audit_lastmod import _off, expected
    folder = getattr(ctx, "live_dir", None)
    kept = {}
    if folder and not _off(ctx.config):
        try:
            kept = json.loads((Path(folder) / "sitemaps" / "lastmod" / "history.json").read_text())
        except (OSError, ValueError):
            kept = {}
    meta = ((ctx.config or {}).get("report") or {}).get("pages_meta")
    return expected(kept if isinstance(kept, dict) else {}, meta)


def daily(ctx, day) -> list[str] | None:
    """run-daily: the problems found (empty: they match); None when not set up."""
    if not set_up(ctx):
        return None
    from . import page_trends
    with ctx.history() as history:
        first = day - timedelta(days=WINDOW - 1)
        shown = page_trends.figures(history, ctx.site, history.daily(ctx.site, first, day), day,
                                    ctx.config, Path(ctx.live_dir) if ctx.live_dir else None)
        problems = recheck(history.db, ctx.site, day, _dates(ctx), shown)
    ctx.out(f"page trends: {len(shown['days'])} days and "
            f"{len((shown.get('changed') or {}).get('pages') or [])} changed pages recounted")
    return problems
