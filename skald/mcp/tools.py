"""The MCP tools: read-only answers from the dashboard's data files.

Every tool returns a short plain-English `content` text and the numbers as
`structuredContent`. The text says "visits (an upper bound on people)",
never anything that sounds like a count of humans, and names every day it
left out by date. A site the caller may not read, a bad date or a file
that is not there comes back as a tool error (isError) in plain words.

Registered here: list_sites, overview, breakdown, top_pages, ai_activity,
leads. The rest (funnel, compare, page_story, live_today, data_quality,
site_health) are in tools_more.py.
"""
from __future__ import annotations

import re
import sys
from datetime import timedelta

from ..labels import shown_keys, shown_text, stored
from .data import (HONEST, OTHERS, Refused, anchor_of, counters, coverage,
                   coverage_text, dig, num, pct, period, top, total)

TOOLS: dict[str, dict] = {}
# "Unknown" stored as a label (a country, a device, a touch), inside an answer's sentences.
_UNKNOWN_WORD = re.compile(r"\bUnknown\b")

DIMENSIONS = ("country", "source", "campaign", "landing", "device", "browser", "hour",
              "os", "referrer")

SITE_ARG = {"type": "string",
            "description": "The site's name as list_sites gives it, e.g. example.com. "
                           "May be left out when you may read only one site."}
VIEW_ARG = {"type": "string",
            "description": "A view's slug (a part of the site, e.g. us-english), as "
                           "list_sites gives it. Leave out for the whole site."}
FROM_ARG = {"type": "string", "format": "date", "pattern": r"^\d{4}-\d{2}-\d{2}$",
            "description": "First day, YYYY-MM-DD, in the site's own time zone. "
                           "Default: 6 days before `to`."}
TO_ARG = {"type": "string", "format": "date", "pattern": r"^\d{4}-\d{2}-\d{2}$",
          "description": "Last day, YYYY-MM-DD, inclusive. Default: yesterday, the last "
                         "whole day. With neither date: the last 7 whole days."}


def schema(props: dict, required=()) -> dict:
    return {"type": "object", "properties": props, "required": list(required),
            "additionalProperties": False}


def tool(name: str, title: str, description: str, input_schema: dict):
    """Register a tool: `fn(ctx, args) -> (text, structured)`."""
    def add(fn):
        TOOLS[name] = {"name": name, "title": title, "description": description,
                       "inputSchema": input_schema,
                       "annotations": {"title": title, "readOnlyHint": True,
                                       "destructiveHint": False, "idempotentHint": True,
                                       "openWorldHint": False},
                       "run": fn}
        return fn
    return add


def listing() -> list[dict]:
    return [{k: v for k, v in t.items() if k != "run"} for t in TOOLS.values()]


def validate(spec: dict, args) -> dict:
    """The arguments checked against the tool's inputSchema (the parts the
    tools use: types, enums, bounds, required, no unknown names)."""
    if args is None:
        args = {}
    if not isinstance(args, dict):
        raise Refused("The arguments are an object of names and values.")
    props = spec.get("properties") or {}
    for k in args:
        if k not in props:
            raise Refused(f"Unknown argument {k!r}; this tool takes "
                          f"{', '.join(props) or 'no arguments'}.")
    for k in spec.get("required") or ():
        if args.get(k) in (None, ""):
            raise Refused(f"{k} is needed.")
    for k, v in args.items():
        p = props[k]
        if v is None:
            continue
        kind = p.get("type")
        ok = {"string": isinstance(v, str),
              "integer": isinstance(v, int) and not isinstance(v, bool),
              "object": isinstance(v, dict),
              "array": isinstance(v, list)}.get(kind, True)
        if not ok:
            raise Refused(f"{k} is a{'n' if kind[0] in 'aeio' else ''} {kind}.")
        if "enum" in p and v not in p["enum"]:
            raise Refused(f"{k} is one of: {', '.join(p['enum'])}.")
        if kind == "integer" and not p.get("minimum", v) <= v <= p.get("maximum", v):
            raise Refused(f"{k} is between {p.get('minimum')} and {p.get('maximum')}.")
        if kind == "string" and len(v) > p.get("maxLength", 300):
            raise Refused(f"{k} is too long.")
    return args


def call(ctx, name: str, args) -> dict:
    """The tools/call result for one tool (the caller checked the name)."""
    spec = TOOLS[name]
    try:
        # A value given in its shown words ("Direct") is looked up by its stored name.
        args = {k: stored(v) for k, v in args.items()}
        text, data = spec["run"](ctx, validate(spec["inputSchema"], args))
    except Refused as why:
        return {"content": [{"type": "text", "text": str(why)}], "isError": True}
    except Exception as why:                       # noqa: BLE001 - never a traceback out
        sys.stderr.write(f"mcp: {name} failed: {type(why).__name__}: {why}\n")
        return {"content": [{"type": "text", "text": "Skald could not answer that just now "
                             "(an error on the server). Nothing was changed."}],
                "isError": True}
    # A person reads the answer: stored labels in it are said as shown (labels.py).
    text = _UNKNOWN_WORD.sub("Not recorded", shown_text(text))
    return {"content": [{"type": "text", "text": text}], "structuredContent": shown_keys(data),
            "isError": False}


def where(site: str, view: str | None) -> str:
    return f"{site}{' (view ' + view + ')' if view else ' (whole site)'}"


def _range(ctx, args, site, view, name="overview"):
    doc = ctx.load(site, view, name)
    anchor = anchor_of(doc)
    first, last = period(args, anchor)
    return doc, anchor, first, last


# ---------------------------------------------------------------- list_sites

@tool("list_sites", "Sites you may read",
      "The sites this token may read, with their views (parts of a site) and the first "
      "and last whole day the data files hold. Start here.", schema({}))
def list_sites(ctx, args):
    rows = []
    for site in ctx.sites():
        ov = ctx.load(site, None, "overview", required=False) or {}
        rows.append({"site": site, "timezone": ov.get("timezone"),
                     "first_day": ov.get("first_day"), "last_whole_day": ov.get("anchor"),
                     "today": ov.get("today"),
                     "views": [{"slug": v.get("slug"), "name": v.get("name"),
                                "rule": v.get("rule")} for v in ov.get("views") or []],
                     "private": ctx.private(site)})
    if not rows:
        return "There is no site here you may read.", {"sites": []}
    lines = [f"{len(rows)} site{'s' if len(rows) != 1 else ''} you may read:"]
    for r in rows:
        views = ", ".join(v["slug"] for v in r["views"]) or "none"
        lines.append(f"- {r['site']}: whole days {r['first_day'] or '?'} to "
                     f"{r['last_whole_day'] or '?'} ({r['timezone'] or 'time zone not set'}); "
                     f"views: {views}")
    return "\n".join(lines), {"sites": rows}


# ---------------------------------------------------------------- overview

def _figures(used: list[dict]) -> dict:
    groups = {}
    for g in ("people", "answer_engines", "search_engines", "bots", "ours"):
        groups[g] = total(used, "groups", g, "hits")
    return {"visits": total(used, "groups", "people", "readers"),
            "pages_read": total(used, "groups", "people", "views"),
            "visits_from_ai_citations": total(used, "cited_visits"),
            "ai_fetches_asked": total(used, "ai_tiers", "asked"),
            "ai_fetches_training": total(used, "ai_tiers", "training"),
            "search_engine_fetches": total(used, "search_indexing"),
            "not_found_people": total(used, "not_found_people"),
            "server_errors": total(used, "server_errors"),
            "one_page_visits": total(used, "visits", "one_page"),
            "returning_visits": total(used, "returning", "returning"),
            "requests_by_group": groups}


@tool("overview", "Headline figures for a date range",
      "Visits (an upper bound on people), pages read, AI assistant fetches, search-engine "
      "fetches, 404s and server errors, summed over the whole, verified days of a range, "
      "with the change against the period before when both are complete. Withheld, "
      "partial and missing days are named and never counted.",
      schema({"site": SITE_ARG, "from": FROM_ARG, "to": TO_ARG, "view": VIEW_ARG}))
def overview(ctx, args):
    site = ctx.site(args.get("site"))
    view = ctx.view(site, args.get("view"))
    doc, anchor, first, last = _range(ctx, args, site, view)
    cov, used = coverage(doc.get("days"), first, last, anchor)
    figures = _figures(used)
    length = (last - first).days + 1
    p_first, p_last = first - timedelta(days=length), first - timedelta(days=1)
    p_cov, p_used = coverage(doc.get("days"), p_first, p_last, anchor)
    previous = change = None
    if cov["complete"] and p_cov["complete"]:
        previous = _figures(p_used)
        change = {k: pct(figures[k], previous[k]) for k in
                  ("visits", "pages_read", "ai_fetches_asked", "ai_fetches_training",
                   "search_engine_fetches")}
    f = figures
    lines = [f"{where(site, view)}, {first} to {last}.",
             f"Visits (an upper bound on people): {num(f['visits'])}. "
             f"Pages read: {num(f['pages_read'])}.",
             f"Visits that followed a link from an AI assistant: "
             f"{num(f['visits_from_ai_citations'])} (a floor: referrers are often stripped).",
             f"AI assistant fetches: {num(f['ai_fetches_asked'])} when someone asked, "
             f"{num(f['ai_fetches_training'])} to train or index. Search-engine fetches: "
             f"{num(f['search_engine_fetches'])}.",
             f"404s people met: {num(f['not_found_people'])}. Server errors: "
             f"{num(f['server_errors'])}.",
             coverage_text(cov)]
    if change is not None:
        lines.append(f"Against {p_first} to {p_last}: visits "
                     f"{_signed(change['visits'])}, pages read {_signed(change['pages_read'])}.")
    else:
        lines.append("No change is stated: this period or the one before is not complete.")
    lines.append(HONEST)
    return "\n".join(lines), {
        "site": site, "view": view, "from": first.isoformat(), "to": last.isoformat(),
        "timezone": doc.get("timezone"), "coverage": cov, "figures": figures,
        "previous": ({"from": p_first.isoformat(), "to": p_last.isoformat(),
                      "figures": previous, "change_pct": change} if previous else None),
        "note": HONEST}


def _signed(v) -> str:
    return "no change stated (none before)" if v is None else f"{v:+.1f}%"


# ---------------------------------------------------------------- breakdown

@tool("breakdown", "Visits by one dimension",
      "Visits (an upper bound on people) that read a page, split by one dimension: country, "
      "source (AI assistant, search engine, social media, ...), campaign, landing page, "
      "device, browser, hour of day (site time), os or referrer. Each split adds up to the "
      "visits over the whole, verified days of the range.",
      schema({"site": SITE_ARG,
              "dimension": {"type": "string", "enum": list(DIMENSIONS),
                            "description": "What to split the visits by."},
              "from": FROM_ARG, "to": TO_ARG, "view": VIEW_ARG,
              "limit": {"type": "integer", "minimum": 1, "maximum": 200, "default": 25,
                        "description": "Most rows; the rest are folded into "
                                       "'(all others)', which keeps the sum."}},
             required=("dimension",)))
def breakdown(ctx, args):
    site = ctx.site(args.get("site"))
    view = ctx.view(site, args.get("view"))
    dim = args["dimension"]
    ov, anchor, first, last = _range(ctx, args, site, view)
    doc = ctx.load(site, view, "breakdowns")
    cov, used = coverage(doc.get("days"), first, last, anchor)
    got = counters(used, "readers_by", dim)
    visits = total(coverage(ov.get("days"), first, last, anchor)[1], "groups", "people",
                   "readers")
    problem = None
    if got is not None and visits is not None and sum(got.values()) != visits:
        problem = (f"the {dim} rows add up to {sum(got.values()):,}, not the {visits:,} "
                   "visits, so they are withheld")
        got = None
    rows = top(got, int(args.get("limit") or 25))
    lines = [f"{where(site, view)}, {first} to {last}: visits (an upper bound on people) "
             f"by {dim}."]
    if problem:
        lines.append(f"Withheld: {problem}.")
    elif rows is None:
        lines.append("Not recorded for every counted day, so no split is shown"
                     if used else "No whole, verified day in this range.")
    else:
        lines.append("; ".join(f"{r['label']} {r['n']:,}" for r in rows) or "none")
        lines.append(f"Total {sum(r['n'] for r in rows):,} visits.")
    if dim == "hour":
        lines.append(f"Hours are in the site's time zone ({doc.get('timezone')}).")
    lines += [coverage_text(cov), HONEST]
    return "\n".join(lines), {"site": site, "view": view, "dimension": dim,
                              "from": first.isoformat(), "to": last.isoformat(),
                              "coverage": cov, "rows": rows,
                              "total": sum(r["n"] for r in rows) if rows is not None else None,
                              "reconciled": problem is None, "problem": problem}


# ---------------------------------------------------------------- top_pages

@tool("top_pages", "Most-read pages",
      "Pages people read most (page views) over a range, with how often AI assistants "
      "fetched each, from the whole, verified days. Each day keeps its top 50 pages, so a "
      "page that never made a day's list is missing from these sums.",
      schema({"site": SITE_ARG, "from": FROM_ARG, "to": TO_ARG, "view": VIEW_ARG,
              "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 10,
                        "description": "How many pages."}}))
def top_pages(ctx, args):
    site = ctx.site(args.get("site"))
    view = ctx.view(site, args.get("view"))
    doc, anchor, first, last = _range(ctx, args, site, view, "breakdowns")
    cov, used = coverage(doc.get("days"), first, last, anchor)
    views = counters(used, "pages")
    ai = counters(used, "ai_pages")
    limit = int(args.get("limit") or 10)
    rows = None
    if views is not None:
        rows = [{"path": r["label"], "page_views": r["n"],
                 "ai_fetches": ai.get(r["label"], 0) if ai is not None else None}
                for r in top(views, limit, fold=False)]
    lines = [f"{where(site, view)}, {first} to {last}: the pages people read most."]
    if rows is None:
        lines.append("Not recorded for every counted day, so no list is shown"
                     if used else "No whole, verified day in this range.")
    else:
        lines += [f"{i}. {r['path']}: {r['page_views']:,} page views"
                  + (f", {r['ai_fetches']:,} AI fetches" if r["ai_fetches"] else "")
                  for i, r in enumerate(rows, 1)] or ["No pages were read."]
        lines.append("Each day keeps its top 50 pages; a page that never made a day's list "
                     "is not in these sums.")
    lines.append(coverage_text(cov))
    return "\n".join(lines), {"site": site, "view": view, "from": first.isoformat(),
                              "to": last.isoformat(), "coverage": cov, "pages": rows,
                              "page_views_all_pages": sum(views.values()) if views else None}


# ---------------------------------------------------------------- ai_activity

@tool("ai_activity", "What AI assistants did",
      "Which AI assistants and crawlers fetched the site (to train or index, or because "
      "someone asked them), which pages they read, and the visits that followed a link "
      "from an assistant - over the whole, verified days of a range. With the read_private "
      "scope, also today's individual fetches with their addresses.",
      schema({"site": SITE_ARG, "from": FROM_ARG, "to": TO_ARG, "view": VIEW_ARG}))
def ai_activity(ctx, args):
    site = ctx.site(args.get("site"))
    view = ctx.view(site, args.get("view"))
    ov, anchor, first, last = _range(ctx, args, site, view)
    doc = ctx.load(site, view, "breakdowns")
    cov, used = coverage(doc.get("days"), first, last, anchor)
    _, ov_used = coverage(ov.get("days"), first, last, anchor)
    training = counters(used, "engines", "training")
    asked = counters(used, "engines", "asked")
    cited = counters(used, "cited_by")
    pages = counters(used, "ai_pages")
    data = {"site": site, "view": view, "from": first.isoformat(), "to": last.isoformat(),
            "coverage": cov,
            "fetches_asked": total(ov_used, "ai_tiers", "asked"),
            "fetches_training": total(ov_used, "ai_tiers", "training"),
            "visits_from_ai_citations": total(ov_used, "cited_visits"),
            "training_by_crawler": top(training, 50),
            "asked_by_assistant": top(asked, 50),
            "citation_visits_by_assistant": top(cited, 50),
            "pages_fetched": top(pages, 25),
            "today_events": None}
    lines = [f"{where(site, view)}, {first} to {last}: AI assistants.",
             f"Fetches because someone asked an assistant: {num(data['fetches_asked'])}"
             + _by(data["asked_by_assistant"]) + ".",
             f"Fetches to train or index: {num(data['fetches_training'])}"
             + _by(data["training_by_crawler"]) + ".",
             f"Visits (an upper bound on people) that followed a link from an assistant: "
             f"{num(data['visits_from_ai_citations'])}" + _by(data["citation_visits_by_assistant"])
             + ". This is a floor: referrers are often stripped. Clicks from Google's AI "
             "Overviews are not measurable (they look like any Google search click).",
             "Pages fetched most: " + (_by(data["pages_fetched"], 10).strip(" ()") or "none")
             + "."]
    if ctx.private(site):
        priv = ctx.load(site, view, "ai_activity", required=False) or {}
        events = dig(priv, "today", "events")
        if isinstance(events, list):
            data["today_events"] = events[:200]
            lines.append(f"Today so far: {len(events)} assistant events (with addresses, "
                         "in the structured answer).")
    lines.append(coverage_text(cov))
    return "\n".join(lines), data


def _by(rows, limit: int = 8) -> str:
    if not rows:
        return ""
    shown = [r for r in rows if r["label"] != OTHERS][:limit]
    return " (" + ", ".join(f"{r['label']} {r['n']:,}" for r in shown) + ")" if shown else ""


# ---------------------------------------------------------------- leads

@tool("leads", "Leads from the website's forms",
      "Leads from the website's own database (sign-ups, contact, early access, demos), as "
      "counts by type over a range, plus the last 30 days by the source the lead's browser "
      "remembered. Aggregates only: no name, email or address, and a lead is never joined "
      "to a visit.",
      schema({"site": SITE_ARG, "from": FROM_ARG, "to": TO_ARG}))
def leads(ctx, args):
    site = ctx.site(args.get("site"))
    ov = ctx.load(site, None, "overview")
    anchor = anchor_of(ov)
    first, last = period(args, anchor)
    doc = ctx.load(site, None, "leads")
    if not doc.get("available"):
        why = doc.get("error") or "the website's lead database could not be read"
        return (f"{site}: leads are not available here ({why}). No lead figure is shown, "
                "never as zero.",
                {"site": site, "available": False, "error": why})
    by = {d.get("day"): d for d in doc.get("days") or [] if isinstance(d, dict)}
    got, spam, dupes, missing, withheld, counted = {}, 0, 0, [], [], 0
    day = first
    while day <= last:
        e = by.get(day.isoformat())
        if isinstance(e, dict) and e.get("state") == "withheld":
            withheld.append({"day": day.isoformat(), "why": e.get("why") or ""})
        elif not _lead_figures(e):
            missing.append(day.isoformat())
        else:
            counted += 1
            for k, v in e["leads"].items():
                got[k] = got.get(k, 0) + int(v)
            spam += int(e["spam"])
            dupes += int(e["duplicates"])
        day += timedelta(days=1)
    types = doc.get("types") or sorted(got)
    blocks = {k: (b.get("why") or "") for k in ("period", "by_source_type", "funnel")
              if isinstance(b := doc.get(k), dict) and b.get("state") == "withheld"}
    lines = [f"{site}, {first} to {last}: leads from the website's database "
             "(spam and duplicates left out)."]
    if counted:
        lines += [", ".join(f"{t} {got.get(t, 0):,}" for t in types) + ".",
                  f"Left out: {spam:,} spam, {dupes:,} duplicates."]
    else:
        lines.append("Leads: not recorded (no day of this range holds checked figures), "
                     "never zero.")
    if withheld:
        lines.append("Days withheld (the second count disagreed, so none of their leads are "
                     "counted): " + ", ".join(w["day"] for w in withheld[:10])
                     + (f" and {len(withheld) - 10} more" if len(withheld) > 10 else "") + ".")
    if missing:
        lines.append("Days the leads file does not hold: " + ", ".join(missing[:10])
                     + (f" and {len(missing) - 10} more" if len(missing) > 10 else "") + ".")
    p = None if "period" in blocks else (doc.get("period") or {})
    source = dig(p, "first_touch", "source")
    if source:
        lines.append(f"Last 30 days and today ({p.get('first')} to {p.get('last')}), by the "
                     "source the lead's own browser remembered first: "
                     + ", ".join(f"{k} {v:,}" for k, v in sorted(source.items(),
                                                                 key=lambda kv: -kv[1])) + ".")
    names = {"period": "the last 30 days by source", "by_source_type": "leads by source "
             "type", "funnel": "the funnel"}
    for k, why in blocks.items():
        lines.append(f"Withheld, never shown: {names[k]} ({why or 'no reason given'}).")
    lines.append("Aggregates only; a lead is never joined to a visit.")
    return "\n".join(lines), {
        "site": site, "available": True, "from": first.isoformat(), "to": last.isoformat(),
        "days_counted": counted, "days_not_held": missing, "days_withheld": withheld,
        "leads": {t: got.get(t, 0) for t in types} if counted else None,
        "spam": spam if counted else None, "duplicates": dupes if counted else None,
        "last_30_days": p or None,
        "by_source_type": None if "by_source_type" in blocks else doc.get("by_source_type"),
        "funnel": None if "funnel" in blocks else doc.get("funnel"),
        "blocks_withheld": blocks}


def _lead_figures(e) -> bool:
    """A leads.json day that holds its figures (leads by type, spam, duplicates)."""
    if not isinstance(e, dict) or not isinstance(e.get("leads"), dict):
        return False
    vals = list(e["leads"].values()) + [e.get("spam"), e.get("duplicates")]
    return all(isinstance(v, int) and not isinstance(v, bool) for v in vals)


from . import tools_more  # noqa: E402,F401 - registers the other tools

from . import tools_people  # noqa: E402,F401 - registers find_person (2.4.0)
