"""page_trends.json: each page's visits and AI reads, day by day, and the
pages that changed lately, for Overview > Summary, Traffic > Pages and
AI & bots > Assistants.

Nothing new is counted here: the file puts stored, audited day figures side
by side, per page.

  days[]      one entry per day of the page's window (data_files.DAYS):
              `day`, `state` (as every file), and on a day with figures
                landings  the day kind `landings` as stored (landings.py),
                          or null: not recorded that day
                fetches   the assistants' user fetches (day kind
                          `ai_fetches`, only the user fetchers: ChatGPT-User,
                          Perplexity-User, Claude-User, ...) by path and
                          assistant: {"paths": {path: {assistant: n}},
                          "folded": n}; the FETCH_TOP paths with most fetches
                          (ties by path), the rest summed into "(all others)"
                          per assistant; null when not recorded that day
  today       the live snapshot's same two figures (state, from, until), or null
  changed     the pages whose change date (the website's own, else the
              sitemap's lastmod: lifecycle.py's `updated`) falls in the last
              CHANGED_DAYS days to yesterday, each with what happened since
              (CHANGED_RULES below), and the counts the card says
  same_day    the sitemap's dates look like build times: of its dated pages,
              more than SAME_DAY_SHARE carry the one most common date (and at
              least SAME_DAY_MIN pages do): {"day", "pages", "of"}; else null

A view (page group) gets {"whole_site_only": true}: crawl health and the
change dates are the whole site's. The second count is audit_page_trends.py
(audit_more.DAILY): it reads the same stored blobs with its own SQL and works
every figure here out again.
"""
from __future__ import annotations

from collections import Counter
from datetime import date, timedelta

FETCH_TOP = 200
OTHER = "(all others)"
CHANGED_DAYS = 30
SAME_DAY_SHARE = 0.5      # "most pages changed on the same day": more than half ...
SAME_DAY_MIN = 10         # ... of at least this many dated pages
CHANGED_RULES = {
    "visits": "visits that started on the page, on each whole, verified day from the day it "
              "changed to yesterday (the day kind landings)",
    "search": "of them, visits from a search engine",
    "first_search": "the first of those days with a visit from a search engine",
    "google": "Googlebot (verified) fetched the page on a whole, verified day on or after the "
              "day it changed (crawl health); null when no such day has crawl health",
}


def key(path: str) -> str:
    """One page whether asked for with or without its trailing slash, or a query."""
    path = str(path or "").split("?", 1)[0].split("#", 1)[0]
    return path if path.endswith("/") else path + "/"


def fold_fetches(rows) -> dict:
    """ai_fetches rows [[minute, assistant, path, n]] -> {"paths", "folded"}."""
    per: dict[str, Counter] = {}
    for _minute, who, path, n in rows or []:
        per.setdefault(str(path), Counter())[str(who)] += int(n)
    ordered = sorted(per.items(), key=lambda kv: (-sum(kv[1].values()), kv[0]))
    out = {path: dict(sorted(c.items())) for path, c in ordered[:FETCH_TOP]}
    rest = Counter()
    for _, c in ordered[FETCH_TOP:]:
        rest.update(c)
    if rest:
        out[OTHER] = dict(sorted(rest.items()))
    return {"paths": out, "folded": max(0, len(ordered) - FETCH_TOP)}


def same_day(dates: dict) -> dict | None:
    """{"day", "pages", "of"} when the sitemap's dates look like build times."""
    got = Counter(d["lastmod"] for d in dates.values() if d.get("lastmod"))
    of = sum(got.values())
    if of < SAME_DAY_MIN:
        return None
    day, pages = sorted(got.items(), key=lambda kv: (-kv[1], kv[0]))[0]
    return {"day": day, "pages": pages, "of": of} if pages > of * SAME_DAY_SHARE else None


def changed(dates: dict, days: list[dict], anchor: date) -> dict:
    """The pages changed in the last CHANGED_DAYS days, and what happened since.
    `days`: [{"day", "ok", "landings", "crawl"}] oldest first; `crawl` the day's
    crawl_health blob or None."""
    since = (anchor - timedelta(days=CHANGED_DAYS - 1)).isoformat()
    rows = []
    for path, d in sorted(dates.items()):
        when = d.get("updated")
        if not when or when < since:
            continue
        k = key(path)
        visits = search = 0
        counted, missed, short, first_search = [], 0, False, None
        google, google_last, crawled = False, None, False
        for e in days:
            if e["day"] < when:
                continue
            if not e["ok"] or e["landings"] is None:
                missed += 1
            else:
                counted.append(e["day"])
                pages = e["landings"].get("pages") or {}
                row = [0, 0, 0, 0, 0]
                for p, r in pages.items():
                    if p != OTHER and key(p) == k:
                        row = [a + int(b) for a, b in zip(row, r)]
                if int(e["landings"].get("folded") or 0) and not any(
                        p != OTHER and key(p) == k for p in pages):
                    short = True
                visits += row[0]
                search += row[3]
                if row[3] and first_search is None:
                    first_search = e["day"]
            if e["ok"] and e["crawl"] is not None:
                crawled = True
                g = ((e["crawl"].get("crawlers") or {}).get("Google") or {}).get("paths") or {}
                if any(p != OTHER and key(p) == k and int(r[0]) for p, r in g.items()):
                    google, google_last = True, e["day"]
        rows.append({"path": path, "changed": when, "source": d.get("updated_source"),
                     "visits": visits if counted else None,
                     "search": search if counted else None,
                     "first_search": first_search,
                     "counted_from": counted[0] if counted else None,
                     "unmeasured": missed, "at_least": short,
                     "google": google if crawled else None, "google_last": google_last})
    rows.sort(key=lambda r: (r["changed"], r["path"]), reverse=True)
    measured = [r for r in rows if r["visits"] is not None]
    return {"days": CHANGED_DAYS, "since": since, "until": anchor.isoformat(),
            "rules": CHANGED_RULES, "pages": rows,
            "counts": {"pages": len(rows), "measured": len(measured),
                       "visited": sum(1 for r in measured if r["visits"]),
                       "searched": sum(1 for r in measured if r["search"]),
                       "none": sum(1 for r in measured if not r["visits"]),
                       "google": sum(1 for r in rows if r["google"])}}


def figures(history, site: str, daily: list[dict], anchor: date, config: dict, folder) -> dict:
    """The file's body below the envelope, without today. `daily`: History.daily's
    entries for the window, oldest first."""
    from . import lifecycle
    first, last = daily[0]["day"], anchor
    stored = history.extras(site, first, last, ("landings", "ai_fetches", "crawl_health"))
    out_days, flat = [], []
    first_day = None
    for e in daily:
        d = e["day"].isoformat()
        row = {"day": d, "state": e["state"]}
        blobs = stored.get(d) or {}
        ok = e["state"] == "ok"
        if e["state"] in ("ok", "partial"):
            row["landings"] = blobs.get("landings")
            row["fetches"] = (fold_fetches(blobs["ai_fetches"].get("rows"))
                              if blobs.get("ai_fetches") is not None else None)
            if row["landings"] is not None and first_day is None:
                first_day = d
        out_days.append(row)
        flat.append({"day": d, "ok": ok, "landings": blobs.get("landings") if ok else None,
                     "crawl": blobs.get("crawl_health") if ok else None})
    dates = lifecycle.page_dates(config, folder)
    return {"first_day": first_day, "days": out_days,
            "changed": changed(dates, flat, anchor), "same_day": same_day(dates)}


def build(p) -> dict:
    """page_trends.json (data_more.FILES)."""
    if p.view is not None:
        return {"whole_site_only": True}
    from .lifecycle import site_folder
    folder = p.live_dir if p.live_dir is not None else site_folder(p.config, p.site)
    body = figures(p.history, p.key, p.daily, p.anchor, p.config, folder)
    today = p.today_block()
    if today is not None and p.live_ok:
        ex = p.snap.get("extras") or {}
        today["landings"] = ex.get("landings")
        today["fetches"] = (fold_fetches(ex["ai_fetches"].get("rows"))
                            if ex.get("ai_fetches") is not None else None)
    return {"fields": ["visits", "one_page", "views", "search", "ai"], **body, "today": today}
