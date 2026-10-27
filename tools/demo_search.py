"""The demo's Search Console and Bing figures (tools/demo.py; Traffic > Search, 2.13).

Made-up answers from stand-ins for the two engines' APIs, read by the real sync
(skald/search/sync.py: fetched, folded, written, read back and checked),
so the demo's Traffic > Search shows what a connected site shows. No network.

Search Console's clicks are drawn from the demo's own visits from Google search
(history's `search_landing`, page by page and day by day, after the backfill),
so its cross-check with Skald's visits looks like a real site's: close, never
equal. Each click and impression is one record (query, page, country, device,
search appearance); a query of None is anonymised (in every total, in no query
row), as Google does. The newest day is two days ago and still provisional.
Bing's figures are a small share of Google's, as on most sites.

For Traffic > Search's reports, a few positions drift day by day (DRIFT), one
query starts in the last weeks (COMING) and one stops (GOING): the new and lost
queries, the position tracking and the opportunities then have something to show.

Drawn from a generator of its own: nothing else in the demo changes with it.
"""
from __future__ import annotations

import random
from collections import defaultdict
from datetime import date, timedelta

SITE_URL = "https://example.com"
# The queries each landing page is found by, with the position it is usually shown at.
QUERIES = {
    "/": [("example", 1.1), ("example analytics", 2.4), ("server log analytics", 6.8)],
    "/pricing/": [("example pricing", 1.3), ("log analytics pricing", 7.9)],
    "/features/": [("server log analytics tool", 5.2), ("ai crawler analytics", 8.6)],
    "/blog/": [("example blog", 1.8)],
    "/blog/ai-crawlers-explained": [("ai crawlers explained", 3.9), ("what is gptbot", 6.1),
                                    ("chatgpt user agent", 9.4)],
    "/blog/fall-launch": [("example fall launch", 2.2)],
    "/guides/getting-started": [("example getting started", 1.6), ("nginx log format", 11.2)],
    "/guides/webhooks": [("example webhooks", 2.0), ("signed webhook example", 8.3)],
    "/customers/": [("example customers", 2.7)],
}
# Pages shown in results but seldom clicked: impressions, few or no clicks.
SHOWN_ONLY = [("/blog/robots-txt-for-ai", "robots.txt for ai crawlers", 14.5),
              ("/guides/log-formats", "nginx combined log format", 18.2),
              ("/about/", "example company", 4.4)]
# Positions that move a little each day (per day; negative: climbing).
DRIFT = {"ai crawler analytics": -0.06, "nginx log format": 0.04, "what is gptbot": -0.03}
# A query found only in the last N days, and one found only before the last N days.
COMING = {"/blog/ai-crawlers-explained": ("gptbot user agent", 7.4, 20)}
GOING = {"/": ("example beta", 2.6, 30)}
COUNTRIES = [("usa", 46), ("gbr", 12), ("can", 10), ("deu", 7), ("ind", 7), ("aus", 5),
             ("fra", 4), ("nld", 4), ("swe", 3), ("bra", 2)]
DEVICES = [("DESKTOP", 58), ("MOBILE", 38), ("TABLET", 4)]


def _pick(x: random.Random, pairs):
    total = sum(w for _, w in pairs)
    r = x.uniform(0, total)
    for v, w in pairs:
        r -= w
        if r <= 0:
            return v
    return pairs[-1][0]


def records(history_db, site: str, first: date, last: date, seed: int) -> dict[str, list[dict]]:
    """{day iso: [record]} for [first, last], each record one query, page, country, device
    and appearance with its clicks, impressions and position."""
    from skald import store_extras as sx
    x = random.Random(seed + 5)
    ours = sx.read(history_db, site, first, last, ("search_landing",))
    out: dict[str, list[dict]] = {}
    d = first
    while d <= last:
        k = d.isoformat()
        age, left = (d - first).days, (last - d).days
        blob = (ours.get(k) or {}).get("search_landing") or {}
        pages = dict(((blob.get("pages") or {}).get("Google") or {}))
        rows: list[dict] = []
        for path, n in sorted(pages.items()):
            path = path.split("?", 1)[0]
            name = path.strip("/").split("/")[-1].replace("-", " ")
            found = list(QUERIES.get(path) or [(f"example {name}".strip(), 3.5)])
            if path in COMING and left < COMING[path][2]:
                found.append(COMING[path][:2])
            if path in GOING and left >= GOING[path][2]:
                found.append(GOING[path][:2])
            clicks = max(0, int(n) + x.choice([-1, 0, 0, 0, 0, 1]))
            shown = clicks * x.randint(14, 38) + x.randint(6, 70)
            for i in range(x.randint(2, 4)):
                q, pos = x.choice(found) if x.random() > 0.12 else (None, 9.0)
                c = clicks if i == 3 else x.randint(0, clicks)
                s = shown if i == 3 else x.randint(c, max(c, shown))
                clicks, shown = clicks - c, shown - s
                rows.append({"query": q, "page": SITE_URL + path, "country": _pick(x, COUNTRIES),
                             "device": _pick(x, DEVICES),
                             "appearance": "FAQ_RICH_RESULT" if path.startswith("/guides/") and x.random() < 0.3 else None,
                             "clicks": c, "impressions": s,
                             "position": max(1.0, round(pos + DRIFT.get(q, 0) * age + x.uniform(-0.6, 0.9), 1))})
            if clicks or shown:
                rows.append({"query": None, "page": SITE_URL + path, "country": "usa", "device": "DESKTOP",
                             "appearance": None, "clicks": clicks, "impressions": shown, "position": 9.0})
        for path, q, pos in SHOWN_ONLY:
            rows.append({"query": q, "page": SITE_URL + path, "country": _pick(x, COUNTRIES),
                         "device": _pick(x, DEVICES), "appearance": None,
                         "clicks": 1 if x.random() < 0.08 else 0, "impressions": x.randint(8, 45),
                         "position": round(pos + x.uniform(-1.5, 1.5), 1)})
        out[k] = [r for r in rows if r["impressions"] > 0]
        d += timedelta(days=1)
    return out


def _sum(rows: list[dict]) -> dict:
    clicks = sum(r["clicks"] for r in rows)
    shown = sum(r["impressions"] for r in rows)
    pos = sum(r["position"] * r["impressions"] for r in rows) / shown if shown else None
    return {"clicks": clicks, "impressions": shown, "ctr": clicks / shown if shown else 0,
            "position": round(pos, 2) if pos is not None else None}


KEY = {"query": "query", "page": "page", "country": "country", "device": "device",
       "searchAppearance": "appearance"}


class FakeGoogle:
    """query(property, body) -> (rows, meta), as google.Client answers."""

    def __init__(self, recs: dict[str, list[dict]]):
        self.recs, self.calls = recs, 0
        self.incomplete = max(recs) if recs else None

    def query(self, prop: str, body: dict):
        self.calls += 1
        first, last = body["startDate"], body["endDate"]
        dims = body.get("dimensions") or []
        groups: dict[tuple, list] = defaultdict(list)
        for day, rows in self.recs.items():
            if not first <= day <= last:
                continue
            for r in rows:
                keys = []
                for dim in dims:
                    v = day if dim == "date" else r[KEY[dim]]
                    if v is None:
                        break
                    keys.append(v)
                else:
                    groups[tuple(keys)].append(r)
        out = [{"keys": list(k), **_sum(v)} for k, v in sorted(groups.items())]
        return out, {"first_incomplete_date": self.incomplete}


class FakeBing:
    """traffic(site_url) and stats(site_url, kind), as bing.Client answers: about an
    eighth of Google's clicks, by day."""

    def __init__(self, recs: dict[str, list[dict]], seed: int):
        x = random.Random(seed + 6)
        self.days, self.rows = [], {"query": [], "page": []}
        for day, rows in sorted(recs.items()):
            d = date.fromisoformat(day)
            t = _sum(rows)
            clicks, shown = round(t["clicks"] * x.uniform(0.08, 0.18)), round(t["impressions"] * x.uniform(0.1, 0.2))
            self.days.append({"day": d, "clicks": clicks, "impressions": shown})
            by = {"query": defaultdict(list), "page": defaultdict(list)}
            for r in rows:
                if r["query"]:
                    by["query"][r["query"]].append(r)
                by["page"][r["page"]].append(r)
            for kind in ("query", "page"):
                for key, got in sorted(by[kind].items())[:12]:
                    s = _sum(got)
                    c = min(clicks, round(s["clicks"] * x.uniform(0.05, 0.2)))
                    i = max(c, round(s["impressions"] * x.uniform(0.08, 0.2)))
                    if i:
                        p = round((s["position"] or 10) + x.uniform(-0.5, 1.5), 2)
                        self.rows[kind].append({"day": d, "key": key, "clicks": c, "impressions": i,
                                                "position": p, "click_position": p})

    def traffic(self, site_url: str) -> list[dict]:
        return list(self.days)

    def stats(self, site_url: str, kind: str) -> list[dict]:
        return list(self.rows[kind])


def sync(root, cfg_path, site: str, today: date, now, seed: int, say=print) -> None:
    """Both engines synced into the demo's history by the real sync, from the stand-ins."""
    from skald.config import load_config
    from skald.search import sync as ss
    from skald.store import History
    newest = today - timedelta(days=2)
    with History(root / "history.sqlite") as history:
        recs = records(history.db, site, today - timedelta(days=62), newest, seed)
    job = ss.Job(config=load_config(cfg_path), site=site, folder=root, db_path=root / "history.sqlite",
                 now=now, out=lambda *_: None, err=say)
    for engine, client, extra in (("google", FakeGoogle(recs), {"backfill_months": 2}),
                                  ("bing", FakeBing(recs, seed), {})):
        code = ss.run(job, engine, client=client, **extra)
        if code:
            raise SystemExit(f"demo: the {engine} search sync failed ({code})")
