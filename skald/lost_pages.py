"""lost_pages.json (2.35): old addresses people, search engines or AI still ask for.

Site > Not found's three tabs, and the to-dos that rest on them (todos.py):

  Lost pages      every page-shaped address that answered 404 to people, a
                  search engine or an AI fetcher in the window and is not live
                  now, and has not answered 410 gone since (2.38.0: a 410 is
                  the site's own answer, so handled), most asked first, with the closest live page
                  (closest_page.py: exact, likely or guess) and the server
                  lines for a redirect or "410 gone", as text to copy
  AI asks for     the .md and .mdx addresses AI fetchers asked for and got 404:
  Markdown        those whose page is live (Skald could serve a Markdown copy
                  there), and the rest (copies of old pages)
  After the fix   the addresses someone marked fixed (todo_marks.py), with what
                  came for them on the whole days after that day: 404 answers
                  by who asked, and page views served (2xx or 304). A redirect,
                  to this site or another, or a 410 leaves no 404: fixed

Counted from what each day already holds, nothing new from the log: the day
kind `not_found` (every 404 and 410 by path, status, who asked, scanner probe
or not; recounted from the raw lines by audit_extras.py) and the day kind
`pages` (each page served, by who). The live pages are the sitemap's paths
(sitemap.py, the list kept for the last whole day) and every path served as a
page in the window; an address counts as live once it was served on or after
the last day it failed.

Who asked: people; search engines (the search crawlers: Google, Bing, ...;
the 404 rows do not keep which one); AI (assistants fetching for a question,
and AI crawlers). Bots, scanner probes and our own traffic are left out: a
scanner's /.env is noise, never an old page.

The window: the last WINDOW_DAYS (30) days with figures (verified, whole or
partial), ending yesterday; today is not in it (the live count is not whole).
After the fix also shows today so far, apart.

Second count: audit_todos.py, from history by its own SQL and its own path
rules, sharing only the name lists below. A path it counts differently, or a
total that differs, is withheld: the list says so and shows no figure.
"""
from __future__ import annotations

import re
from collections import Counter
from datetime import date, timedelta

from .closest_page import Live, closest, rules

WINDOW_DAYS = 30
TOP_SOURCES = 4
# ---- name lists (audit_todos.py shares these and nothing else) ---------------------------
# Paths that are no page whatever they answer: feeds, APIs, framework files, well-known
# files, server software's own addresses. Matched at the start of the path, any case.
MACHINE = ("/api/", "/graphql", "/wp-json", "/wp-admin", "/wp-content/", "/wp-includes/",
           "/xmlrpc", "/feed", "/rss", "/atom", "/comments/feed", "/.well-known/", "/_next/",
           "/_nuxt/", "/static/", "/assets/", "/cdn-cgi/", "/v1/", "/v2/", "/node_modules/",
           "/trackback", "/embed", "/oembed", "/amp/")
# A page's last segment: no file ending, or one of these.
PAGE_ENDINGS = ("", ".html", ".htm")
MARKDOWN_ENDINGS = (".md", ".mdx")
# Who asked, from a 404 row's group: the three that matter; the rest are left out.
WHO = {"people": "people", "search_engines": "search", "ai_asked": "ai", "ai_training": "ai"}
# The answer that says an address is gone on purpose: handled, never lost (2.38.0).
GONE = "410"
_ENDING = re.compile(r"\.([A-Za-z0-9]{1,8})$")


def kind_of(path: str) -> str | None:
    """"page", "markdown", "sitemap" (a file named *sitemap*.xml) or None (anything else: an asset, a feed, an API)."""
    if not isinstance(path, str) or not path.startswith("/") or path.startswith("//"):
        return None
    low = path.split("?", 1)[0].lower()
    name = low.rstrip("/").rsplit("/", 1)[-1]
    if "sitemap" in name and (name.endswith(".xml") or name.endswith(".xml.gz")):
        return "sitemap"
    if any(low.startswith(m) for m in MACHINE):
        return None
    if name.endswith(MARKDOWN_ENDINGS):
        return "markdown"
    ending = _ENDING.search(name)
    if ending and "." + ending.group(1) not in PAGE_ENDINGS:
        return None
    return "page"


def markdown_page(path: str, live: Live) -> str | None:
    """The live page a Markdown address is the copy of: /a/b.md -> /a/b/ (or /a/b),
    /a/index.md -> /a/. None when that page is not live."""
    low = path.split("?", 1)[0]
    stem = re.sub(r"\.mdx?$", "", low, flags=re.I)
    if stem.lower().endswith("/index"):
        stem = stem[:-6] or "/"
    return live.find(stem or "/")


def window(p) -> list[str]:
    """The days of the window that have figures, oldest first."""
    first = p.anchor - timedelta(days=WINDOW_DAYS - 1)
    return [e["day"].isoformat() for e in p.daily if e["day"] >= first and p.has_figures(e)]


def _blob(p, d: str, kind: str):
    return (p.extras.get(d) or {}).get(kind)


def served_last(p, days: list[str]) -> dict[str, str]:
    """{path: the last day of the window it was served as a page to anyone}."""
    last: dict[str, str] = {}
    for d in days:
        for path, v in (_blob(p, d, "pages") or {}).items():
            if v.get("views") or v.get("search") or v.get("ai_asked") or v.get("ai_training"):
                last[path] = max(last.get(path, ""), d)
    return last


def sitemap_paths(p) -> tuple[list[str] | None, str | None]:
    """(the sitemap's paths kept for the last whole day, that list's day) or (None, None)."""
    from . import sitemap
    if p.live_dir is None:
        return None, None
    found = sitemap.entry_for(p.live_dir, p.anchor)
    if not found:
        return None, None
    return sitemap.load_list(p.live_dir, str(found[1].get("list") or "")), found[0]


def tally(rows_by_day: list[tuple[str, list]]) -> dict[str, dict]:
    """{path: figures} over the days' 404 rows, probes left out: n, people, search, ai,
    ai_asked, ai_training, bots, ours, first_day, last_day, statuses, sources, gone_day.
    A 410 is answered on purpose (2.38.0): it counts no ask, only `statuses` and
    `gone_day`, the last day it was given; first_day and last_day are the 404s'."""
    out: dict[str, dict] = {}
    for d, rows in rows_by_day:
        for r in rows or []:
            if r.get("probe"):
                continue
            path = r["path"]
            got = out.get(path)
            if got is None:
                got = out[path] = {"n": 0, "people": 0, "search": 0, "ai": 0, "ai_asked": 0,
                                   "ai_training": 0, "bots": 0, "ours": 0, "first_day": None,
                                   "last_day": "", "statuses": Counter(), "sources": Counter(),
                                   "gone_day": ""}
            n = int(r["n"])
            if str(r.get("status")) == GONE:
                got["statuses"][GONE] += n
                got["gone_day"] = max(got["gone_day"], d)
                continue
            got["n"] += n
            group = r.get("group")
            who = WHO.get(group)
            if who:
                got[who] += n
            if group in ("ai_asked", "ai_training", "bots", "ours"):
                got[group] += n
            got["statuses"][str(r.get("status"))] += n
            if who:
                got["sources"][str(r.get("source") or "(none)")] += n
            got["first_day"] = d if got["first_day"] is None else min(got["first_day"], d)
            got["last_day"] = max(got["last_day"], d)
    return out


def handled(got: dict) -> bool:
    """Answered 410 gone on or after the last day it answered 404: dealt with on purpose."""
    return got["gone_day"] >= got["last_day"] and bool(got["gone_day"])


class Found:
    """What the lost-page figures stand on, worked out once per page (lost_pages.json and
    todos.json both read it)."""

    def __init__(self, p) -> None:
        self.days = window(p)
        self.first = self.days[0] if self.days else None
        self.last = self.days[-1] if self.days else None
        self.paths = tally([(d, _blob(p, d, "not_found")) for d in self.days])
        self.missing = [d for d in self.days if _blob(p, d, "not_found") is None]
        self.served = served_last(p, self.days)
        listed, self.sitemap_day = sitemap_paths(p)
        self.sitemap = frozenset(listed) if listed is not None else None
        self.live = Live(set(self.served) | set(self.sitemap or ()))
        # For the second count, which reads the same sitemap files its own way.
        self.live_dir, self.anchor = p.live_dir, p.anchor.isoformat()

    def is_live(self, path: str, got: dict) -> bool:
        """In the sitemap, or served as a page on or after the last day it failed."""
        if self.sitemap is not None and path in self.sitemap:
            return True
        return self.served.get(path, "") >= got["last_day"]

    def asked(self, got: dict) -> int:
        return got["people"] + got["search"] + got["ai"]

    def lost(self) -> list[dict]:
        """The lost pages, most asked first (people, then everyone who matters)."""
        out = []
        for path, got in self.paths.items():
            if kind_of(path) != "page" or not self.asked(got) or self.is_live(path, got) \
                    or handled(got):
                continue
            target, how, why = closest(path, self.live)
            out.append({"path": path, "people": got["people"], "search": got["search"],
                        "ai": got["ai"], "bots": got["bots"], "n": got["n"],
                        "first_day": got["first_day"], "last_day": got["last_day"],
                        "statuses": dict(got["statuses"]),
                        "sources": dict(got["sources"].most_common(TOP_SOURCES)),
                        "target": target, "match": how, "why": why, **rules(path, target),
                        # Answering gone instead, when a redirect is suggested: the reader picks.
                        "gone": rules(path, None) if target else None})
        out.sort(key=lambda r: (-(r["people"] + r["search"] + r["ai"]), -r["people"], r["path"]))
        return out

    def markdown(self) -> dict:
        """AI's 404 Markdown asks: {"live": [rows whose page is live], "other": [rows]}."""
        live, other = [], []
        for path, got in self.paths.items():
            if kind_of(path) != "markdown" or not got["ai"]:
                continue
            page = markdown_page(path, self.live)
            row = {"path": path, "ai": got["ai"], "ai_asked": got["ai_asked"],
                   "ai_training": got["ai_training"], "people": got["people"],
                   "search": got["search"], "page": page, **rules(path, page),
                   "first_day": got["first_day"], "last_day": got["last_day"]}
            (live if page else other).append(row)
        for rows in (live, other):
            rows.sort(key=lambda r: (-r["ai"], r["path"]))
        return {"live": live, "other": other}

    def sitemaps(self) -> list[dict]:
        """Sitemap addresses search engines or AI crawlers asked for and got 404 or 410."""
        out = [{"path": path, "search": got["search"], "ai": got["ai"], "n": got["n"],
                "statuses": dict(got["statuses"]), "first_day": got["first_day"],
                "last_day": got["last_day"]}
               for path, got in self.paths.items()
               if kind_of(path) == "sitemap" and got["search"] + got["ai"] and not handled(got)]
        out.sort(key=lambda r: (-(r["search"] + r["ai"]), r["path"]))
        return out


def after_fix(p, marks: dict | None) -> list[dict]:
    """The addresses marked fixed, with what came for them on the whole days after the day
    they were marked (and today so far, apart)."""
    fixed = {k[5:]: v for k, v in (marks or {}).items()
             if k.startswith("path:") and v["state"] == "fixed"}
    if not fixed:
        return []
    have = {e["day"].isoformat(): e for e in p.daily}
    live_rows = ((p.snap or {}).get("extras") or {}).get("not_found") if p.live_ok else None
    live_pages = ((p.snap or {}).get("extras") or {}).get("pages") if p.live_ok else None
    out = []
    for path, mark in sorted(fixed.items()):
        since = mark["day"]
        days = [d for d, e in sorted(have.items()) if d > since and p.has_figures(e)]
        got = tally([(d, [r for r in (_blob(p, d, "not_found") or []) if r["path"] == path])
                     for d in days]).get(path)
        served = sum(_served(_blob(p, d, "pages"), path) for d in days)
        today = None
        if live_rows is not None:
            t = tally([(p.today.isoformat(), [r for r in live_rows if r["path"] == path])]).get(path)
            today = {"people": t["people"] if t else 0, "search": t["search"] if t else 0,
                     "ai": t["ai"] if t else 0, "served": _served(live_pages, path)}
        row = {"path": path, "marked_day": since, "days": len(days),
               "people": got["people"] if got else 0, "search": got["search"] if got else 0,
               "ai": got["ai"] if got else 0, "bots": got["bots"] if got else 0,
               "served": served, "today": today}
        failed = row["people"] + row["search"] + row["ai"]
        row["verdict"] = "waiting" if not days else ("not_yet" if failed else "fixed")
        out.append(row)
    return out


def _served(pages: dict | None, path: str) -> int:
    v = (pages or {}).get(path) or {}
    return int(v.get("views", 0)) + int(v.get("search", 0)) + int(v.get("ai_asked", 0)) + \
        int(v.get("ai_training", 0))


def totals(lost: list[dict], md: dict) -> dict:
    return {"paths": len(lost), "people": sum(r["people"] for r in lost),
            "search": sum(r["search"] for r in lost), "ai": sum(r["ai"] for r in lost),
            "md_paths": len(md["live"]) + len(md["other"]), "md_live": len(md["live"]),
            "md_asks": sum(r["ai"] for r in md["live"] + md["other"]),
            "md_live_asks": sum(r["ai"] for r in md["live"])}


def build(p) -> dict:
    """lost_pages.json's body (DATA-CONTRACT.md)."""
    from . import audit_todos, todo_marks
    found = Found(p)
    site = p.key.split("::", 1)[0]
    marks = todo_marks.read(p.config, site, p.live_dir)
    lost, md = found.lost(), found.markdown()
    fixed_paths = {k[5:]: v for k, v in (marks or {}).items() if k.startswith("path:") and v["state"] == "fixed"}
    for r in lost:
        r["marked"] = fixed_paths.get(r["path"], {}).get("day")
    body = {"window": {"first": found.first, "last": found.last, "days": len(found.days),
                       "of": WINDOW_DAYS, "not_recorded": found.missing},
            "live": {"sitemap": len(found.sitemap) if found.sitemap is not None else None,
                     "sitemap_day": found.sitemap_day, "served": len(found.served),
                     "pages": len(found.live)},
            "marks": marks is not None, "totals": totals(lost, md), "lost": lost,
            "markdown": md, "fixed": after_fix(p, marks), "withheld": []}
    # The second count: anything it does not find the same is withheld, and said so.
    why = audit_todos.check_lost(p.history.db, p.key, found.first, found.last, body, found)
    if why:
        body.update({"withheld": why, "totals": None, "lost": None, "markdown": None})
    return body
