"""The MCP tools about single pages (2.35): page_changes, ai_readiness and
changed_pages (tools_insights.py has what_changed, todos and lost_pages).

They read page_changes.json, ai_ready.json and page_trends.json, the files
Traffic > Pages and AI & bots > Assistants draw from, and count nothing again.
ai_readiness for one page puts together what the page story's "AI readiness"
block stands on: the page's row by ai_ready.needs (the code that makes the
file's list), robots.txt's rules for each main AI crawler decided by
robots_match.decide (the reader the file's rules come from; the page's
robots-match.js is tested against it), the sitemap's entry, and the
assistants' reads from page_trends.json. Whole site only: a view has none of
these files' figures.
"""
from __future__ import annotations

from datetime import date, timedelta

from .data import Refused, anchor_of, num
from .tools import SITE_ARG, schema, tool

PATH_ARG = {"type": "string", "maxLength": 300,
            "description": "A page's path, e.g. /pricing/ (with or without the closing /)."}
VERDICT = {"up": "up", "down": "down", "no_clear_change": "no clear change",
           "too_few": "too few to tell", "not_enough_days": "not enough days",
           "not_recorded": "not recorded", "too_early": "too early to tell",
           "waiting": "waiting for a whole day after the change"}
STATUS = {"waiting": "waiting: no whole day after the change yet",
          "too_early": "too early to tell", "ready": "ready"}
NEED = {"copy": lambda r: r["copy_errors"] > 0, "404": lambda r: r["not_found"] > 0,
        "errors": lambda r: r["server_errors"] + r["blocked"] > 0,
        "robots": lambda r: len(r["robots"]) > 0, "slow": lambda r: r["slow"] > 0}


def _path(given) -> str:
    path = str(given or "").strip()
    if not path.startswith("/"):
        raise Refused("A path starts with /, e.g. /pricing/.")
    return path


def _key(path: str) -> str:
    from ..page_trends import key
    return key(path)


def _whole_site(doc: dict, name: str) -> None:
    if doc.get("whole_site_only"):
        raise Refused(f"{name}.json is kept for the whole site only.")


# ---------------------------------------------------------------- page_changes

def _side(f: dict, side: str) -> str:
    s = f.get(side)
    if not s:
        return "not recorded"
    if f.get("key") == "left":
        return (f"{s['one_page']:,} of {s['visits']:,} visits ({s['share'] * 100:.0f}%)"
                if s.get("share") is not None else "not recorded")
    floor = " (at least)" if s.get("at_least") else ""
    return f"{s['total']:,} over {s['days']} days ({s['per_day']:.1f} a day){floor}"


def _figure_words(f: dict, label: str) -> str:
    verdict = VERDICT.get(f.get("verdict"), f.get("verdict"))
    if f.get("verdict") in ("up", "down"):
        verdict += " (better)" if f["verdict"] == f.get("better") else " (worse)"
    change = f.get("change") or {}
    if "points" in change:
        moved = f", {change['points']:+g} points"
    elif change.get("pct") is not None:
        moved = f", {change['pct']:+g}% per day"
    else:
        moved = ""
    unequal = " (sides have the figure on different numbers of days: compared per day)" \
        if f.get("unequal") else ""
    return (f"{label}: before {_side(f, 'before')}, after {_side(f, 'after')}{moved}: "
            f"{verdict}{unequal}")


@tool("page_changes", "Did my change to a page work?",
      "The page changes marked on Traffic > Pages (\"+ Mark a change\": content, title, a "
      "link to it, a redirect, other) and, for each, the same number of whole days before "
      "and after the day it changed (up to 28 a side; the day itself in neither): visits "
      "that started on the page, leads and conversions that landed there, search engine "
      "visits, AI assistant visits, AI reads and the share who left at once, each with its "
      "verdict (up, down, no clear change, too few to tell; too early to tell under 14 whole "
      "days). Days not whole or not recorded are left out, never counted as zero.",
      schema({"site": SITE_ARG, "path": PATH_ARG,
              "id": {"type": "string", "maxLength": 20,
                     "description": "One change's id, from this tool's list."}}))
def page_changes(ctx, args):
    site = ctx.site(args.get("site"))
    doc = ctx.load(site, None, "page_changes")
    _whole_site(doc, "page_changes")
    labels = {m.get("key"): m.get("label") for m in doc.get("measures") or []}
    changes = [c for c in doc.get("changes") or [] if isinstance(c, dict)]
    if args.get("path"):
        want = _key(_path(args["path"]))
        changes = [c for c in changes if _key(c.get("path") or "") == want]
    if args.get("id"):
        changes = [c for c in changes if c.get("id") == args["id"]]
    withheld = doc.get("withheld") or []
    lines = [f"{site}: page changes marked, and whether each worked."]
    if not doc.get("marks"):
        lines.append("Changes can be marked only with accounts (signing in); none are kept "
                     "here.")
    elif not changes:
        lines.append("No change matches." if args.get("path") or args.get("id")
                     else "No page change is marked.")
    for c in changes:
        note = f" \"{c['note']}\"" if c.get("note") else ""
        lines.append(f"- [{c.get('id')}] {c.get('path')} changed {c.get('day')} "
                     f"({c.get('kind')}){note}: {STATUS.get(c.get('status'), c.get('status'))}, "
                     f"{c.get('days_after')} whole days after it"
                     + (f"; the verdict comes on {c.get('verdict_on')}"
                        if c.get("status") != "ready" else "")
                     + f". Before {(c.get('before') or {}).get('first')} to "
                     f"{(c.get('before') or {}).get('last')}, after "
                     f"{(c.get('after') or {}).get('first')} to {(c.get('after') or {}).get('last')}.")
        for f in c.get("figures") or []:
            lines.append("  " + _figure_words(f, labels.get(f.get("key"), f.get("key"))))
        if c.get("leads_why"):
            lines.append(f"  Leads: {c['leads_why']}.")
    if withheld:
        lines.append("Withheld (the second count disagreed, so not shown): " + "; ".join(
            f"{w.get('path')} {w.get('day')} ({'; '.join(map(str, w.get('why') or []))})"
            for w in withheld) + ".")
    lines.append("Rules: " + "; ".join(f"{v}" for v in (doc.get("rules") or {}).values()) + ".")
    return "\n".join(lines), {
        "site": site, "marks": bool(doc.get("marks")), "min_days": doc.get("min_days"),
        "max_days": doc.get("max_days"), "rules": doc.get("rules"),
        "measures": doc.get("measures"), "changes": changes, "withheld": withheld}


# ---------------------------------------------------------------- ai_readiness

def _reads(pt: dict | None, page: str, anchor: date) -> dict | None:
    """The assistants' live fetches of one page: the last 30 days to the anchor, the 30
    before (null unless every one of them is recorded), and the last day with one
    (ai-ready.js readLine)."""
    if not pt or pt.get("whole_site_only"):
        return None
    per = {}
    for d in pt.get("days") or []:
        if d.get("state") not in ("ok", "partial") or not d.get("fetches"):
            continue
        n, who = 0, {}
        for p, w in (d["fetches"].get("paths") or {}).items():
            if p == "(all others)" or _key(p) != page:
                continue
            for name, k in w.items():
                n += int(k)
                who[name] = who.get(name, 0) + int(k)
        per[d["day"]] = (n, who)

    def span(first: date, last: date):
        n = days = count = 0
        day = first
        while day <= last:
            count += 1
            if day.isoformat() in per:
                n += per[day.isoformat()][0]
                days += 1
            day += timedelta(days=1)
        return n, days, count

    now, now_days, now_all = span(anchor - timedelta(days=29), anchor)
    before, b_days, b_all = span(anchor - timedelta(days=59), anchor - timedelta(days=30))
    last = max((d for d, (n, _) in per.items() if n), default=None)
    return {"last_30_days": now, "days_recorded": now_days, "of": now_all,
            "before_30_days": before if b_days == b_all else None,
            "last_day": last, "last_by": per[last][1] if last else None}


def _robots(f: dict, path: str) -> list[dict] | None:
    from ..robots_match import decide
    r = f.get("robots") or {}
    if r.get("missing"):
        return [{"crawler": t, "role": role, "allowed": True, "rule": None, "group": None}
                for t, role in f.get("crawlers") or []]
    if not r.get("crawlers"):
        return None
    out = []
    for token, role in f.get("crawlers") or []:
        c = r["crawlers"].get(token)
        if c is None:
            continue
        allowed, rule = decide(c.get("rules") or [], path)
        out.append({"crawler": token, "role": role, "allowed": allowed, "rule": rule,
                    "group": c.get("agents") or ["*"], "whole_site": not c.get("root")})
    return out


def _times(n: int) -> str:
    return "once" if n == 1 else f"{n:,} times"


def _need_words(r: dict, robots: bool = True) -> str:
    bits = []
    if r["copy_errors"]:
        bits.append(f"its Markdown copy failed {_times(r['copy_errors'])}"
                    + (f" ({r['copy_404']:,} of them 404 or 410)" if r["copy_404"] else ""))
    if r["not_found"]:
        bits.append(f"the page answered AI 404 or 410 {_times(r['not_found'])}")
    if r["server_errors"]:
        bits.append(f"server errors {_times(r['server_errors'])}")
    if r["blocked"]:
        bits.append(f"refused (another 4xx) {_times(r['blocked'])}")
    if r["robots"] and robots:
        bits.append("robots.txt shuts out " + ", ".join(r["robots"]))
    if r["slow"]:
        bits.append(f"slow answers (a second or more) {_times(r['slow'])}")
    if r["redirects"]:
        bits.append(f"redirected {_times(r['redirects'])} (said, not a problem: the log does "
                    "not say where a redirect leads)")
    return "; ".join(bits) or "no error, refusal or slow answer"


@tool("ai_readiness", "Can AI read a page well?",
      "From the server's log and Skald's own copies of robots.txt and the sitemap (no AI is "
      "asked anything): without a path, AI & bots > Assistants' \"Pages AI can't read well\", "
      "worst first (a Markdown copy that fails, a 404, server errors, refused, robots.txt "
      "shutting a main AI crawler out, slow answers); with a path, that page's AI readiness: "
      "robots.txt for each of the 9 main AI crawlers with the deciding rule, what AI got back "
      "in the last 30 days, the Markdown copy, the sitemap entry and the last AI read. Not "
      "known when Skald has no copy or no record, never a guess.",
      schema({"site": SITE_ARG, "path": PATH_ARG,
              "need": {"type": "string", "enum": list(NEED),
                       "description": "Only the list's rows with this problem: copy, 404, "
                                      "errors, robots, slow."},
              "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20,
                        "description": "Most rows of the list."}}))
def ai_readiness(ctx, args):
    from ..ai_ready import needs, page_of
    site = ctx.site(args.get("site"))
    f = ctx.load(site, None, "ai_ready")
    _whole_site(f, "ai_ready")
    w = f.get("window") or {}
    sm = f.get("sitemap") or {}
    robots = f.get("robots") or {}
    shut = [t for t, c in (robots.get("crawlers") or {}).items() if not c.get("root")]
    rec = (f"{w.get('recorded', 0)} of {w.get('of', 0)} days with figures recorded "
           f"({w.get('first')} to {w.get('last')})")
    lines = []
    if not args.get("path"):
        att = f.get("attention") or {}
        rows = [r for r in att.get("rows") or [] if NEED.get(args.get("need"), bool)(r)]
        limit = int(args.get("limit") or 20)
        lines.append(f"{site}: pages AI can't read well, worst first, over {rec}: "
                     f"{num(att.get('total'))} pages"
                     + (f" ({len(rows)} with {args['need']} in the {len(att.get('rows') or [])} "
                        "kept)" if args.get("need") else "") + ".")
        if not w.get("recorded"):
            lines.append("What AI got back is not recorded yet (it is kept from 2.35 on).")
        if robots.get("crawlers") is None and not robots.get("missing"):
            lines.append("Skald has no copy of robots.txt, so robots.txt is not known.")
        if shut:
            lines.append("robots.txt keeps these out of the whole site: " + ", ".join(shut) + ".")
        lines += [f"- {r['path']}: {_need_words(r)}" for r in rows[:limit]]
        return "\n".join(lines), {"site": site, "window": w, "whole_site_shut_out": shut,
                                  "total": att.get("total"), "rows": rows[:limit]}
    path = _path(args["path"]).split("?", 1)[0].split("#", 1)[0]
    page = page_of(path)[0]
    ov = ctx.load(site, None, "overview")
    pt = ctx.load(site, None, "page_trends", required=False)
    facts = (f.get("pages") or {}).get(page)
    listed = sm.get("pages")
    row = needs(page, facts, robots, listed)
    rules = _robots(f, path)
    reads = _reads(pt, page, anchor_of(ov))
    lines.append(f"{site} {page}: AI readiness, over {rec}.")
    if rules is None:
        lines.append("robots.txt: not known (Skald has no copy"
                     + (f"; the last try failed: {robots.get('error')}" if robots.get("error")
                        else "") + ").")
    else:
        out = [r for r in rules if not r["allowed"]]
        lines.append("robots.txt: " + ("every main AI crawler may read it." if not out else
                     "keeps out " + ", ".join(
                         f"{r['crawler']} (User-agent: {', '.join(r['group'])}; "
                         f"{(r['rule'] or ['', ''])[0].capitalize()}: {(r['rule'] or ['', ''])[1]})"
                         for r in out) + "."))
    if not w.get("recorded"):
        lines.append("What AI got back: not recorded yet.")
    else:
        lines.append("What AI got back: " + _need_words(row, robots=False) + ".")
        copies = (facts or {}).get("copies") or {}
        if not copies:
            lines.append("Markdown copy: AI asked for none, so Skald cannot tell whether one "
                         "exists.")
    if not sm.get("enabled"):
        lines.append("Sitemap: not read for this site.")
    elif listed is None:
        lines.append("Sitemap: Skald has no copy yet.")
    elif page in listed:
        lines.append(f"Sitemap: listed" + (f", last changed {listed[page]} (its lastmod)"
                                           if listed[page] else ", without a lastmod") + ".")
    else:
        lines.append(f"Sitemap: not listed (read {sm.get('day')}, {num(sm.get('count'))} pages).")
    if reads is None:
        lines.append("Last AI read: not recorded.")
    elif reads["last_30_days"]:
        lines.append(f"Last AI read: {reads['last_day']} ("
                     + ", ".join(f"{k} {v:,}" for k, v in sorted((reads['last_by'] or {}).items()))
                     + f"); {reads['last_30_days']:,} in the last 30 days ({reads['days_recorded']} "
                     f"of {reads['of']} days recorded)"
                     + (f", {reads['before_30_days']:,} in the 30 before"
                        if reads["before_30_days"] is not None else "") + ".")
    else:
        lines.append("Last AI read: no assistant fetched it for someone in the last 30 days"
                     + (f"; the last time was {reads['last_day']}" if reads["last_day"] else "")
                     + ".")
    return "\n".join(lines), {
        "site": site, "path": path, "page": page, "window": w, "robots": rules,
        "robots_known": rules is not None, "answers": facts, "needs": row,
        "sitemap": {"enabled": sm.get("enabled"), "day": sm.get("day"),
                    "listed": None if listed is None else page in listed,
                    "lastmod": (listed or {}).get(page)},
        "reads": reads}


# ---------------------------------------------------------------- changed_pages

@tool("changed_pages", "New and updated pages: are they getting found?",
      "Overview > Summary's \"New and updated pages\": the pages changed in the last 30 days "
      "(the website's own date, else the sitemap's lastmod), with the visits and search "
      "engine visits that started on each since, the first search visit, and whether "
      "Google's verified crawler fetched it since. Over whole, verified days only; days not "
      "counted are said, never zero. Says so when most sitemap dates fall on one day (they "
      "look like build times).",
      schema({"site": SITE_ARG,
              "limit": {"type": "integer", "minimum": 1, "maximum": 200, "default": 25,
                        "description": "Most pages."}}))
def changed_pages(ctx, args):
    site = ctx.site(args.get("site"))
    pt = ctx.load(site, None, "page_trends")
    _whole_site(pt, "page_trends")
    ch = pt.get("changed") or {}
    pages = ch.get("pages") or []
    limit = int(args.get("limit") or 25)
    c = ch.get("counts") or {}
    lines = [f"{site}: pages changed {ch.get('since')} to {ch.get('until')}: "
             f"{num(c.get('pages'))} pages, {num(c.get('visited'))} visited since, "
             f"{num(c.get('searched'))} found by search, {num(c.get('none'))} with no visit, "
             f"{num(c.get('google'))} fetched by Google since."]
    same = pt.get("same_day")
    if same:
        lines.append(f"Note: {same.get('pages')} of {same.get('of')} dated pages in the sitemap "
                     f"carry {same.get('day')}: these dates look like build times, not changes.")
    for p in pages[:limit]:
        visits = ("not recorded" if p.get("visits") is None else
                  f"{p['visits']:,} visits{' (at least)' if p.get('at_least') else ''}, "
                  f"{p.get('search') or 0:,} from search")
        first = f", first search visit {p['first_search']}" if p.get("first_search") else ""
        google = {True: f"Google fetched it (last {p.get('google_last')})", False:
                  "Google has not fetched it since", None: "Google's fetches not recorded"}[
                      p.get("google")]
        gap = (f"; {p['unmeasured']} days since not counted" if p.get("unmeasured") else "")
        lines.append(f"- {p['path']}: changed {p.get('changed')} (from the {p.get('source')}); "
                     f"{visits}{first}; {google}{gap}.")
    if len(pages) > limit:
        lines.append(f"{len(pages) - limit} more; raise limit to see them.")
    return "\n".join(lines), {"site": site, "since": ch.get("since"), "until": ch.get("until"),
                              "rules": ch.get("rules"), "counts": c, "same_day": same,
                              "pages": pages[:limit], "pages_total": len(pages)}
