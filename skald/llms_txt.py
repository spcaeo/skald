"""A suggested /llms.txt: the pages people and AI assistants read most.

llms.txt (https://llmstxt.org) is a Markdown file at a site's root for AI
assistants: an H1 with the site's name, a blockquote with a short summary,
then H2 sections that are lists of links, `- [name](url)` with an optional
`: notes`. A section named "Optional" holds links an assistant may skip.

This builds one from the site's real pages:

  ranking   over the last DAYS (90) whole days, each page's people's page
            views plus AI assistants' fetches made for someone's question
            (`views` + `ai_asked` of the per-page blob, day_extras "pages";
            both are recounted per page by the audit, audit_extras). Only
            recorded ("ok") days are summed; partial, withheld and missing
            days are left out and named. No figure is published: the file is
            a list of links, and the ranking is the figures' only use.
  pages     a page is a 2xx document (parse.Line.is_page), so assets,
            redirects and 404s never enter the per-page blob. Also left out:
            Skald's own and private paths (PRIVATE), paths robots.txt keeps
            every crawler from ("User-agent: *"), pages the website's old-URL
            map redirects or calls gone (report.redirect_map), pages that
            answered 404 or 410 after they were last served, paths that may
            have been cut short in history (MAX_PATH), and pages nobody read.
            With the website's page list (report.pages_meta) only its pages
            are kept, under their titles; otherwise the path is the title.
  sections  by top-level section (/blog/... under "Blog"); pages with no
            section are "Main pages". The first LIMIT pages make the
            sections, the next OPTIONAL go under "Optional". A Markdown copy
            of a page (/blog/post.md beside /blog/post) is not a page of its
            own: the copies go together under "Markdown copies", after the
            pages, and do not take a page's place in LIMIT.

The H1 is the site's name. The summary is the home page's description in the
page list when it has one; otherwise a line asking the owner to write it.

Offered as llms_txt.json beside the dashboard (the AI crawlers settings page
shows it with Copy and Download), `skald llms-txt [--site X] [--out FILE]`
and the MCP resource skald://sites/<site>/llms.txt. Nothing here writes to
the website: the owner decides whether to publish it.
"""
from __future__ import annotations

import re
from collections import Counter
from datetime import timedelta
from pathlib import Path
from urllib.parse import quote
from urllib.robotparser import RobotFileParser

DAYS = 90
LIMIT = 30
OPTIONAL = 20
MAX_PATH = 70           # extras.py keeps a path's first 70 characters
MAIN = "Main pages"
COPIES = "Markdown copies"
COPY = re.compile(r"\.md/?$", re.I)
RANKED_BY = ("people's page views plus AI assistants' fetches for someone's question, "
             "over recorded days")
# First path segments that are never public reading: sign-in, accounts,
# carts, search results, admin, APIs, framework internals.
PRIVATE = frozenset((
    "admin", "administrator", "wp-admin", "wp-login.php", "login", "logout", "signin",
    "sign-in", "signup", "sign-up", "register", "auth", "oauth", "callback", "account",
    "accounts", "my-account", "profile", "user", "users", "dashboard", "settings", "password",
    "reset-password", "unsubscribe", "cart", "basket", "checkout", "search", "preview",
    "draft", "drafts", "private", "internal", "staging", "api", "cdn-cgi", ".well-known",
    "_next", "thank-you", "thanks"))
LOCALE = re.compile(r"^[a-z]{2}(?:[-_][a-z]{2})?$", re.I)


# ------------------------------------------------------------- helpers

def _key(path: str) -> str:
    """One page whether asked for with or without its trailing slash."""
    return path.rstrip("/") or "/"


def private(path: str) -> bool:
    first = path.lstrip("/").split("/", 1)[0].lower()
    return first == "traffic" or first.startswith("traffic-") or first in PRIVATE


def base_url(config: dict) -> str:
    """https://<host> of the site: its www host if it has one (as robots.py)."""
    from .config import site_name
    hosts = [str(h) for h in (((config or {}).get("site") or {}).get("hosts") or [])]
    host = next((h for h in hosts if h.startswith("www.")), hosts[0] if hosts else None)
    return f"https://{host or site_name(config)}"


def url_of(base: str, path: str) -> str:
    return base + quote(path, safe="/-._~!$&'*+,;=:@%")


def _text(value, limit: int = 160) -> str:
    """One line of Markdown-safe text: no line breaks, brackets escaped."""
    text = " ".join(str(value or "").split())[:limit]
    return text.replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]")


def _title(segment: str) -> str:
    words = re.sub(r"[-_]+", " ", segment).strip()
    return (words[:1].upper() + words[1:]) if words else MAIN


def _robots(directory) -> RobotFileParser | None:
    from .robots import cached
    text = cached(directory) if directory is not None else None
    if not text:
        return None
    rp = RobotFileParser()
    rp.parse(text.splitlines())
    return rp


def _blob(p, day: str, kind: str):
    return (p.extras.get(day) or {}).get(kind)


# ------------------------------------------------------------ building

def _days(p) -> tuple[list[str], list[dict], str]:
    """(recorded days, days left out, first day) of the last DAYS whole days."""
    first = p.anchor - timedelta(days=DAYS - 1)
    counted, left_out = [], []
    for i in range(DAYS):
        d = (first + timedelta(days=i)).isoformat()
        state = (p.states.get(d) or {}).get("state", "missing")
        if state == "ok":
            counted.append(d)
        elif state != "before":
            left_out.append({"day": d, "state": state})
    return counted, left_out, first.isoformat()


def _read(p, counted: list[str]) -> tuple[Counter, dict, dict, dict]:
    """(reads per page, the spelling read most per page, the last day each
    page was served, the last day each page answered 404 or 410)."""
    reads, spellings, served, missing = Counter(), {}, {}, {}
    for d in counted:
        for path, v in (_blob(p, d, "pages") or {}).items():
            key = _key(path)
            n = int(v.get("views", 0)) + int(v.get("ai_asked", 0))
            reads[key] += n
            spellings.setdefault(key, Counter())[path] += n
            if n or v.get("ai_training") or v.get("search"):
                served[key] = max(served.get(key, ""), d)
        for row in _blob(p, d, "not_found") or []:
            if not row.get("probe") and int(row.get("status", 0)) in (404, 410):
                key = _key(str(row.get("path", "")))
                missing[key] = max(missing.get(key, ""), d)
    best = {k: max(c.items(), key=lambda kv: (kv[1], -len(kv[0])))[0]
            for k, c in spellings.items()}
    return reads, best, served, missing


def suggest(p) -> dict:
    """llms_txt.json's body for one dashboard page (data_files.Page)."""
    from .config import site_name
    from .lifecycle import _norm, load_meta
    from .redirects import RedirectMap
    config = p.config or {}
    counted, left_out, first = _days(p)
    period = {"first": first, "last": p.anchor.isoformat(), "days": DAYS,
              "counted": len(counted), "left_out": left_out}
    meta, _ = load_meta(config)
    out = {"ok": False, "why": None, "period": period, "ranked_by": RANKED_BY,
           "titles": "website" if meta else "paths", "base_url": base_url(config),
           "pages": [], "left_out_paths": {}, "text": None}
    if not counted:
        out["why"] = f"No recorded day in the last {DAYS} days: nothing to rank pages by."
        return out
    reads, best, served, missing = _read(p, counted)
    rp = _robots(p.live_dir)
    redirects = RedirectMap.load((config.get("report") or {}).get("redirect_map"))
    why = Counter()
    kept = []
    for key in sorted(reads, key=lambda k: (-reads[k], k)):
        path = best[key]
        listed = meta.get(_norm(path))
        if private(path):
            why["private"] += 1
        elif len(path) >= MAX_PATH and listed is None:
            why["cut_short"] += 1
        elif rp is not None and not rp.can_fetch("*", path):
            why["robots_txt"] += 1
        elif redirects.state(path)[0] or missing.get(key, "") > served.get(key, ""):
            why["redirected_or_gone"] += 1
        elif meta and listed is None:
            why["not_in_page_list"] += 1
        elif reads[key] < 1:
            why["not_read"] += 1
        else:
            kept.append((path, listed or {}))
    out["left_out_paths"] = {k: why.get(k, 0) for k in (
        "private", "cut_short", "robots_txt", "redirected_or_gone", "not_in_page_list",
        "not_read")}
    if not kept:
        out["why"] = "No page that people or AI assistants read is left to suggest."
        return out
    base = out["base_url"]
    pages = [k for k in kept if not COPY.search(k[0])]
    copies = [k for k in kept if COPY.search(k[0])]
    row = lambda path, entry, optional: {  # noqa: E731
        "path": path, "url": url_of(base, path), "title": entry.get("title") or None,
        "note": entry.get("description") or None, "section": None, "optional": optional}
    rows = [row(path, entry, i >= LIMIT)
            for i, (path, entry) in enumerate(pages[:LIMIT + OPTIONAL])]
    _sections(rows[:LIMIT], meta)
    for path, entry in copies[:LIMIT]:
        rows.append({**row(path, entry, False), "section": COPIES})
    home = meta.get("/") or {}
    name = site_name(config)
    summary = (home.get("description")
               or f"Replace this line with one or two sentences: what {name} offers "
                  "and who it is for.")
    out.update(ok=True, pages=rows, text=render(name, summary, rows))
    return out


def _sections(rows: list[dict], meta: dict) -> None:
    """Each main row's section: its first segment when that segment holds
    more than one page here; a locale prefix the page list names is skipped."""
    def parts(row):
        segs = [s for s in row["path"].split("/") if s]
        locale = str((meta.get(row["path"].rstrip("/") + "/") or {}).get("locale") or "")
        if len(segs) > 1 and locale and segs[0].lower() == locale.lower() and \
                LOCALE.match(segs[0]):
            return segs[1:], segs[0]
        return segs, None

    split = [parts(r) for r in rows]
    parents = Counter((s[0], loc) for s, loc in split if s)
    deeper = {(s[0], loc) for s, loc in split if len(s) > 1}
    for row, (segs, loc) in zip(rows, split):
        if segs and ((segs[0], loc) in deeper or parents[(segs[0], loc)] > 1):
            row["section"] = _title(segs[0]) + (f" ({loc})" if loc else "")
        else:
            row["section"] = MAIN + (f" ({loc})" if loc else "")


def render(name: str, summary: str, rows: list[dict]) -> str:
    """The llms.txt text: H1, blockquote, H2 sections in the order of their
    best page, then "Optional"."""
    def item(r):
        note = f": {_text(r['note'], 300)}" if r.get("note") else ""
        return f"- [{_text(r['title'] or r['path'])}]({r['url']}){note}"

    order: list[str] = []
    by: dict[str, list[str]] = {}
    for r in rows:
        if r["optional"]:
            continue
        if r["section"] not in by and r["section"] != COPIES:
            order.append(r["section"])
        by.setdefault(r["section"], []).append(item(r))
    if COPIES in by:                      # the copies after the pages they copy
        order.append(COPIES)
    parts = [f"# {_text(name, 120)}", f"> {_text(summary, 500)}"]
    for section in order:
        parts.append(f"## {section}\n\n" + "\n".join(by[section]))
    extra = [item(r) for r in rows if r["optional"]]
    if extra:
        parts.append("## Optional\n\n" + "\n".join(extra))
    return "\n\n".join(parts) + "\n"


def build(p) -> dict:
    """data_more's builder: llms_txt.json."""
    return suggest(p)


# --------------------------------------------------------------- command

def cmd_llms_txt(ctx) -> int:
    from .data_files import Page
    from .store import History
    with History(ctx.db_path) as history:
        page = Page(history, ctx.site, ctx.site, None, ctx.tz, ctx.now, None, ctx.config,
                    live_dir=ctx.live_dir)
        got = suggest(page)
    period = got["period"]
    ctx.err(f"{ctx.site}: suggested from {period['counted']} recorded days, "
            f"{period['first']} to {period['last']}; ranked by {RANKED_BY}.")
    if period["left_out"]:
        ctx.err("left out (not recorded): " + ", ".join(
            f"{d['day']} ({d['state']})" for d in period["left_out"]))
    if not got["ok"]:
        ctx.err(got["why"])
        return 1
    if ctx.args.out:
        target = Path(ctx.args.out)
        target.write_text(got["text"], encoding="utf-8")
        ctx.err(f"wrote {target}. Check it, then publish it yourself as /llms.txt; "
                "Skald never writes to your website.")
    else:
        ctx.out(got["text"], end="")
    return 0


def add_command(sub) -> None:
    import argparse
    p = sub.add_parser("llms-txt", help="suggest an /llms.txt from the pages read most "
                                        "(prints it; never writes to the website)")
    p.add_argument("--site", dest="only_site", metavar="NAME", default=argparse.SUPPRESS,
                   help="with several sites, this one")
    p.add_argument("--out", metavar="FILE", help="write it to FILE instead of printing it")
    p.set_defaults(run=cmd_llms_txt)
