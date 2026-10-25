"""ai_ready.json: can AI read each page well? (2.35, AI readiness per page)

From the log and Skald's own stored data only, nothing is asked of any AI.
For one page the dashboard draws six lines (js/ai-ready.js); this file holds
what they stand on, for the whole site:

  robots     the robots.txt robots.py keeps (`url`, `fetched_at`, `ok`: a copy
             is kept, `error` of the last try), and for each of the main AI
             crawlers (CRAWLERS) the rules that apply to it by RFC 9309
             (robots_match.rules_for: {"agents", "rules"}) and `root`: may it
             fetch "/". `missing`: no copy, and the last try was answered with
             a 4xx other than 429 - the site has no robots.txt, so every
             crawler may fetch every page (RFC 9309: an unreachable robots.txt in the 4xx range means no rules). No copy and not
             missing: `crawlers` is null, and the lines say "not known"
  sitemap    `enabled` (crawl_health.sitemap), `day` and `fetched_at` of the
             list kept for today (sitemap.entry_for), `count` its paths, and
             `pages` {page: its lastmod or null} (lifecycle.page_dates: the
             sitemap's latest change date); null when no list is kept
  window     the last WINDOW days to yesterday: `of` days with figures (whole
             or partial, verified), `recorded` of them with the day kind
             ai_status (ai_status.py), `since` the first of those, `folded`
             the days that summed some addresses into "(all others)"
  pages      {page: {"self", "slow", "copies"}} for every page that AI got
             anything but a plain 200 or 304 from on a recorded day, or asked
             for a Markdown copy of. Only addresses shaped like a page count: a
             Markdown copy, or an address ai_formats.format_of calls a "Page",
             also with a closing "/" taken off, with no part that starts with
             "." (/.env, /.git/), that the site's not-a-page list (not_pages.py)
             does not name - no file, feed, API, sitemap or llms.txt. `self`
             {name: {status: n}} for the page's own addresses, `slow` {name: n}
             for them, `copies` {path: {name: {status: n}}} for its Markdown
             copies (copy_of below)
  attention  the pages AI cannot read well, worst first: {"total", "rows"} with
             at most ROWS rows (needs below)

A page is its path cut at "?" and "#", with a "/" added unless it ends with
one (page_trends.key). A Markdown copy belongs to the page it copies
(copy_of): "/a/b.md", "/a/b/index.md" and "/a/b/.md" are "/a/b/"'s,
"/index.md" and "/.md" are "/"'s ( .mdx and .markdown alike).

needs (a row has at least one, worst first): `copy_errors` (a Markdown copy
answered AI with anything but 2xx or 304; `copy_404` of them 404 or 410),
`not_found` (the page answered AI 404 or 410), `server_errors` (5xx),
`blocked` (another 4xx: 401, 403, 429, ...), `robots` (main AI crawlers its
path shuts out while robots.txt lets them fetch "/": a crawler shut out of the
whole site is said once, in robots, not on every page) and `slow`. A sitemap
page with no AI request is listed for `robots` only. `redirects` (3xx but 304)
is said beside them and orders rows that tie, but is no need on its own: the
log does not say where a redirect leads, and a site that sends AI to a page's
Markdown copy on purpose redirects every page. `listed`: the page is in the
sitemap (null: no list kept).

A view (page group) gets {"whole_site_only": true}. The second count is
audit_ai_ready.py (audit_more.DAILY).
"""
from __future__ import annotations

import re
from collections import Counter
from datetime import timedelta
from pathlib import Path

from .ai_status import ASCII_LOWER, COPY_ENDS, OTHER, is_copy

WINDOW = 30
ROWS = 100
# The main AI crawlers whose robots.txt rules each page is checked against:
# [token, what it does]. The names are classify.py's; Google-Extended and
# Applebot-Extended never fetch anything, they are robots.txt switches for
# using what Googlebot and Applebot fetched.
CRAWLERS = (("GPTBot", "training"), ("OAI-SearchBot", "search"), ("ChatGPT-User", "asked"),
            ("ClaudeBot", "training"), ("Claude-User", "asked"), ("PerplexityBot", "search"),
            ("Perplexity-User", "asked"), ("Google-Extended", "training"),
            ("Applebot-Extended", "training"))
NEEDS = ("copy_errors", "not_found", "server_errors", "blocked", "robots", "slow")
_MISSING = re.compile(r"HTTP Error (4\d\d)")


def key(path: str) -> str:
    path = str(path or "").split("?", 1)[0].split("#", 1)[0]
    return path if path.endswith("/") else path + "/"


def copy_of(path: str) -> str:
    """The page a Markdown copy's path belongs to (module doc)."""
    bare = str(path or "").split("?", 1)[0].split("#", 1)[0].rstrip("/")
    low = bare.translate(ASCII_LOWER)
    for end in sorted(COPY_ENDS, key=len, reverse=True):
        if low.endswith(end):
            bare = bare[:-len(end)]
            break
    if bare.translate(ASCII_LOWER).endswith("/index"):
        bare = bare[:-len("index")]
    return key(bare or "/")


def page_of(path: str) -> tuple[str, bool]:
    """(the page, whether the path is a Markdown copy of it)."""
    return (copy_of(path), True) if is_copy(path) else (key(path), False)


# ---------------------------------------------------------------- parts

def robots_part(config: dict, folder) -> dict:
    from . import robots
    from .robots_match import decide, groups, rules_for
    text = robots.cached(folder) if folder is not None else None
    st = robots.state(folder)
    got = _MISSING.search(str(st.get("error") or ""))
    missing = text is None and got is not None and got.group(1) != "429"
    out = {"url": st.get("url") or robots.url_of(config), "fetched_at": st.get("fetched_at"),
           "ok": text is not None, "error": None if st.get("ok") else st.get("error"),
           "missing": missing, "crawlers": None}
    if text is not None:
        found = groups(text)
        out["crawlers"] = {}
        for token, _ in CRAWLERS:
            mine = rules_for(found, token)
            out["crawlers"][token] = {**mine, "root": decide(mine["rules"], "/")[0]}
    return out


def shut_out(robots: dict, path: str) -> list[str] | None:
    """The main crawlers this path's rules shut out, though they may fetch "/";
    None when robots.txt is not known."""
    from .robots_match import decide
    if robots.get("missing"):
        return []
    if robots.get("crawlers") is None:
        return None
    return [t for t, c in robots["crawlers"].items()
            if c["root"] and not decide(c["rules"], path)[0]]


def sitemap_part(config: dict, folder, today) -> dict:
    from . import lifecycle, sitemap
    on = sitemap.enabled(config)
    found = sitemap.entry_for(folder, today) if (folder is not None and on) else None
    listed = sitemap.load_list(folder, str(found[1].get("list") or "")) if found else None
    out = {"enabled": on, "day": found[0] if found else None,
           "fetched_at": found[1].get("fetched_at") if found else None,
           "count": len(listed) if listed is not None else None, "pages": None}
    if listed is not None:
        dates = lifecycle.page_dates(config, folder)
        out["pages"] = {k: (dates.get(k) or {}).get("lastmod")
                        for k in sorted({key(p) for p in listed})}
    return out


def _add(into: dict, name: str, codes: dict) -> None:
    c = into.setdefault(name, Counter())
    for code, n in codes.items():
        c[str(code)] += int(n)


def shaped(config: dict):
    """path -> (page, copy) for an address shaped like a page, else None (module doc)."""
    from .ai_formats import format_of
    from .not_pages import from_config
    rules = from_config(config)

    def one(path: str):
        page, copy = page_of(path)
        if copy:
            return page, True
        bare = str(path).split("?", 1)[0].split("#", 1)[0]
        if format_of(bare) != "Page" or format_of(bare.rstrip("/") or "/") != "Page" \
                or any(part.startswith(".") for part in bare.split("/")) or rules.match(bare, bare):
            return None
        return page, False
    return one


def window_part(history, site: str, daily: list[dict], anchor, config: dict) -> tuple[dict, dict]:
    """(window, pages) from the stored ai_status days of the window."""
    first = anchor - timedelta(days=WINDOW - 1)
    which = shaped(config)
    stored = history.extras(site, first, anchor, ("ai_status",))
    of = recorded = folded = 0
    since = None
    pages: dict[str, dict] = {}
    for e in daily:
        if e["day"] < first or e["state"] not in ("ok", "partial"):
            continue
        of += 1
        d = e["day"].isoformat()
        blob = (stored.get(d) or {}).get("ai_status")
        if blob is None:
            continue
        recorded += 1
        since = since or d
        if any(int(v or 0) for v in (blob.get("folded") or {}).values()):
            folded += 1
        for path, per in (blob.get("answers") or {}).items():
            got = which(path) if path != OTHER else None
            if got is None:
                continue
            page, copy = got
            row = pages.setdefault(page, {"self": {}, "slow": Counter(), "copies": {}})
            for name, codes in per.items():
                _add(row["copies"].setdefault(path, {}) if copy else row["self"], name, codes)
        for path, per in (blob.get("slow") or {}).items():
            got = which(path) if path != OTHER else None
            if got is None or got[1]:
                continue
            page = got[0]
            row = pages.setdefault(page, {"self": {}, "slow": Counter(), "copies": {}})
            row["slow"].update({k: int(v) for k, v in per.items()})
    out = {}
    for page in sorted(pages):
        row = pages[page]
        out[page] = {"self": {n: dict(sorted(c.items())) for n, c in sorted(row["self"].items())},
                     "slow": dict(sorted(row["slow"].items())),
                     "copies": {p: {n: dict(sorted(c.items())) for n, c in sorted(per.items())}
                                for p, per in sorted(row["copies"].items())}}
    return ({"days": WINDOW, "first": first.isoformat(), "last": anchor.isoformat(), "of": of,
             "recorded": recorded, "since": since, "folded": folded}, out)


def _sum(per: dict, test) -> int:
    return sum(int(n) for codes in per.values() for code, n in codes.items() if test(code))


def needs(page: str, facts: dict | None, robots: dict, listed) -> dict:
    """One page's needs (module doc) and the names involved."""
    f = facts or {"self": {}, "slow": {}, "copies": {}}
    own = f["self"]
    copies = [per for per in f["copies"].values()]
    bad_copy = sum(_sum(per, lambda c: not (c[:1] == "2" or c == "304")) for per in copies)
    row = {"path": page, "listed": None if listed is None else page in listed,
           "copy_errors": bad_copy,
           "copy_404": sum(_sum(per, lambda c: c in ("404", "410")) for per in copies),
           "not_found": _sum(own, lambda c: c in ("404", "410")),
           "server_errors": _sum(own, lambda c: c[:1] == "5"),
           "blocked": _sum(own, lambda c: c[:1] == "4" and c not in ("404", "410")),
           "robots": shut_out(robots, page) or [],
           "redirects": _sum(own, lambda c: c[:1] == "3" and c != "304"),
           "slow": sum(int(v) for v in f["slow"].values())}
    names = set()
    for per in [own] + copies:
        names.update(n for n, codes in per.items()
                     if any(not (c in ("200", "304") or c[:1] == "2") for c in codes))
    names.update(n for n, v in f["slow"].items() if int(v))
    row["by"] = sorted(names)
    return row


def _weight(r: dict) -> tuple:
    hard = r["copy_errors"] + r["not_found"] + r["server_errors"] + r["blocked"]
    return (-hard, -len(r["robots"]), -r["slow"], -r["redirects"], r["path"])


def attention(pages: dict, robots: dict, sitemap: dict) -> dict:
    listed = sitemap.get("pages")
    rows = []
    for page in sorted(set(pages) | set(listed or {})):
        r = needs(page, pages.get(page), robots, listed)
        if any(r[k] for k in NEEDS):
            rows.append(r)
    rows.sort(key=_weight)
    return {"total": len(rows), "rows": rows[:ROWS]}


def figures(history, site: str, daily: list[dict], anchor, today, config: dict, folder) -> dict:
    """The file's body below the envelope. `daily`: History.daily's entries for
    the window (or longer), oldest first."""
    folder = Path(folder) if folder is not None else None
    robots = robots_part(config, folder)
    sitemap = sitemap_part(config, folder, today)
    window, pages = window_part(history, site, daily, anchor, config)
    return {"crawlers": [[t, what] for t, what in CRAWLERS], "robots": robots,
            "sitemap": sitemap, "window": window, "pages": pages,
            "attention": attention(pages, robots, sitemap)}


def build(p) -> dict:
    """ai_ready.json (data_more.FILES)."""
    if p.view is not None:
        return {"whole_site_only": True}
    from .lifecycle import site_folder
    folder = p.live_dir if p.live_dir is not None else site_folder(p.config, p.site)
    return figures(p.history, p.key, p.daily, p.anchor, p.today, p.config, folder)
