"""The MCP tools for "is it working, and what do I fix?" (2.35): what_changed,
todos and lost_pages (tools_pages.py has page_changes, ai_readiness and
changed_pages).

Nothing is counted here. what_changed adds up the same stored, verified days
the dashboard's Overview > Summary card "What changed: is it working?" adds up
(breakdowns.json's visits by source and by landing page, as the breakdown tool
does), and states a change only when both periods are whole. todos and
lost_pages read todos.json and lost_pages.json as the page does: the to-dos and
the lost pages there are the ones the second count (audit_todos.py) agreed
with; the rest are named as withheld, never shown.
"""
from __future__ import annotations

from datetime import timedelta

from .data import (HONEST, OTHERS, Refused, anchor_of, counters, coverage, coverage_text, num,
                   period, total)
from .tools import FROM_ARG, SITE_ARG, TO_ARG, VIEW_ARG, schema, tool, where

SAME = 3                 # a gap of this many visits or fewer reads "about the same" (period-dates.js)
CHANGE_ROWS = 8          # rows per list, as the Summary card shows
STATES = {"open": "to do", "done": "marked done", "notnow": "marked not now"}
VERDICTS = {"waiting": "waiting for a whole day after the mark", "fixed": "fixed",
            "not_yet": "not fixed yet"}
MATCH = {"exact": "the same page", "likely": "the same topic", "guess": "a loose match",
         None: "no good match"}
LIMIT_ARG = {"type": "integer", "minimum": 1, "maximum": 200, "default": 25,
             "description": "Most rows in the answer."}


# ---------------------------------------------------------------- what_changed

def _split(ov, br, first, last, anchor):
    """(visits, {source}, {landing}, coverage, problem) for one period."""
    cov, used = coverage(ov.get("days"), first, last, anchor)
    _, b_used = coverage(br.get("days"), first, last, anchor)
    visits = total(used, "groups", "people", "readers")
    out = {}
    for dim in ("source", "landing"):
        got = counters(b_used, "readers_by", dim)
        if got is not None and visits is not None and sum(got.values()) != visits:
            return visits, None, None, cov, (f"the {dim} rows of {first} to {last} add up to "
                                             f"{sum(got.values()):,}, not the {visits:,} visits")
        out[dim] = got
    return visits, out["source"], out["landing"], cov, None


def change_words(now: int, before: int) -> str:
    gap = now - before
    if abs(gap) <= SAME:
        return "about the same"
    pct = f", {gap / before * 100:+.0f}%" if before else ""
    return f"{gap:+,}{pct}"


def change_rows(a, b, limit: int, skip=()) -> list[dict]:
    """{label: n} of now and before -> rows, the biggest of either first (ov-changed.js)."""
    keys = {k for k in set(a or {}) | set(b or {}) if k not in skip and ((a or {}).get(k) or
                                                                         (b or {}).get(k))}
    rows = [{"label": k, "now": (a or {}).get(k, 0), "before": (b or {}).get(k, 0)} for k in keys]
    rows.sort(key=lambda r: (-max(r["now"], r["before"]), r["label"]))
    for r in rows:
        r["change"] = r["now"] - r["before"]
        r["about_the_same"] = abs(r["change"]) <= SAME
    return rows[:limit]


@tool("what_changed", "What changed against the period before",
      "Overview > Summary's \"What changed: is it working?\": visits (an upper bound on "
      "people) by source and by landing page in a range against the same number of days "
      "just before it, each Now, Before and the change, with the biggest rise and drop. A "
      "gap of 3 visits or fewer is \"about the same\" (the normal day-to-day swing). Stated "
      "only when every day of both periods is whole and verified; otherwise the days left "
      "out are named and nothing is compared.",
      schema({"site": SITE_ARG, "from": FROM_ARG, "to": TO_ARG, "view": VIEW_ARG,
              "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": CHANGE_ROWS,
                        "description": "Rows per list (sources, landing pages)."}}))
def what_changed(ctx, args):
    site = ctx.site(args.get("site"))
    view = ctx.view(site, args.get("view"))
    ov = ctx.load(site, view, "overview")
    br = ctx.load(site, view, "breakdowns")
    anchor = anchor_of(ov)
    first, last = period(args, anchor)
    length = (last - first).days + 1
    b_first, b_last = first - timedelta(days=length), first - timedelta(days=1)
    limit = int(args.get("limit") or CHANGE_ROWS)
    a = _split(ov, br, first, last, anchor)
    b = _split(ov, br, b_first, b_last, anchor)
    data = {"site": site, "view": view,
            "now": {"from": first.isoformat(), "to": last.isoformat(), "visits": a[0],
                    "coverage": a[3]},
            "before": {"from": b_first.isoformat(), "to": b_last.isoformat(), "visits": b[0],
                       "coverage": b[3]},
            "compared": False, "why_not": None, "sources": None, "landing_pages": None,
            "same_within": SAME}
    lines = [f"{where(site, view)}: {first} to {last} against {b_first} to {b_last}."]
    why = None
    if not a[3]["complete"]:
        why = "this period is not whole: " + coverage_text(a[3])
    elif not b[3]["complete"]:
        why = ("the period before was not measured (the site was not counted yet)"
               if b[3]["counted"] == 0 else "the period before is not whole: "
               + coverage_text(b[3]))
    elif a[4] or b[4]:
        why = f"the lists would not add up ({a[4] or b[4]}), so they are withheld"
    elif None in (a[1], a[2], b[1], b[2]):
        why = ("some days of one period were collected before sources and landing pages "
               "were kept, so the lists would not add up")
    if why:
        data["why_not"] = why
        lines.append(f"Not compared: {why}.")
        lines.append(HONEST)
        return "\n".join(lines), data
    src = change_rows(a[1], b[1], limit)
    land = change_rows(a[2], b[2], limit, skip=(OTHERS,))
    data.update({"compared": True, "sources": src, "landing_pages": land})
    lines.append(f"Visits (an upper bound on people): {num(a[0])} now, {num(b[0])} before "
                 f"({change_words(a[0], b[0])}).")
    moves = [r for r in src + land if not r["about_the_same"]]
    up = max((r for r in moves if r["change"] > 0), key=lambda r: r["change"], default=None)
    down = min((r for r in moves if r["change"] < 0), key=lambda r: r["change"], default=None)
    if up:
        lines.append(f"Biggest rise: {up['label']} ({up['before']:,} to {up['now']:,}).")
    if down:
        lines.append(f"Biggest drop: {down['label']} ({down['before']:,} to {down['now']:,}).")
    for title, rows in (("Sources", src), ("Landing pages", land)):
        lines.append(f"{title}: " + ("; ".join(
            f"{r['label']} {r['now']:,} (before {r['before']:,}, {change_words(r['now'], r['before'])})"
            for r in rows) or "none in either period") + ".")
    lines.append(f"\"About the same\" means a gap of {SAME} visits or fewer. " + HONEST)
    return "\n".join(lines), data


# ---------------------------------------------------------------- todos

def _why(why) -> str:
    """A withheld reason: words, or a list of them."""
    if isinstance(why, (list, tuple)):
        return "; ".join(map(str, why)) or "no reason given"
    return str(why or "no reason given")


def _window(w: dict | None) -> str:
    w = w or {}
    if not w.get("first"):
        return "no day with figures in the window"
    return f"{w['first']} to {w['last']} ({w.get('days')} days with figures)"


@tool("todos", "Insights' to-do list: what to fix, and did it work",
      "Overview > Insights' \"To do now\": what to fix on the site, worst leak first (old "
      "page addresses still asked for, server errors, AI asking for Markdown copies that "
      "fail, sitemap addresses that are not there, pages nearly every visit leaves at "
      "once), each with its proof, what to do and how Skald checks it; and each to-do's "
      "state: to do, marked done (with its re-check on the whole days after the mark: "
      "fixed or not yet) or marked not now. Give an id for the rows behind one to-do. "
      "Read-only: marking is done on the dashboard.",
      schema({"site": SITE_ARG,
              "id": {"type": "string", "maxLength": 40,
                     "description": "One to-do's id (from this tool's list), for its rows."},
              "limit": {**LIMIT_ARG, "default": 20,
                        "description": "Most rows of that to-do's list."}}))
def todos(ctx, args):
    site = ctx.site(args.get("site"))
    doc = ctx.load(site, None, "todos")
    items = [t for t in doc.get("todos") or [] if isinstance(t, dict)]
    withheld = doc.get("withheld") or []
    want = str(args.get("id") or "").strip()
    limit = int(args.get("limit") or 20)
    if want:
        got = next((t for t in items if t.get("id") == want), None)
        if got is None:
            held = next((w for w in withheld if w.get("id") == want), None)
            if held:
                raise Refused(f"The to-do {want} is withheld: the second count disagreed "
                              f"({_why(held.get('why'))}), "
                              "so its figures are not shown.")
            raise Refused(f"{site} has no to-do {want!r} now; this tool without an id lists "
                          "them.")
        return _one(site, got, limit)
    lines = [f"{site}: Insights' to-do list, over {_window(doc.get('window'))}."]
    if not doc.get("marks"):
        lines.append("Marks are not kept here (no accounts), so every to-do shows as to do.")
    groups = {"open": [], "done": [], "notnow": []}
    for t in items:
        groups.setdefault(t.get("state") or "open", []).append(t)
    if groups["open"]:
        lines.append("To do now, worst leak first:")
        lines += [f"- [{t['id']}] {t.get('title')}: {t.get('proof')} To do: {t.get('todo')} "
                  f"(open in {t.get('open', {}).get('name')})" for t in groups["open"]]
    else:
        lines.append("Nothing to do now: no problem passed its threshold.")
    if groups["done"]:
        lines.append("Done, and did it work?")
        lines += [f"- [{t['id']}] {t.get('title')}: marked done "
                  f"{(t.get('marked') or {}).get('first_day') or '?'}. "
                  f"{(t.get('recheck') or {}).get('words') or ''}".rstrip() for t in groups["done"]]
    if groups["notnow"]:
        lines.append("Marked not now: " + "; ".join(f"[{t['id']}] {t.get('title')}"
                                                    for t in groups["notnow"]) + ".")
    if withheld:
        lines.append("Withheld (the second count disagreed, so they are not shown): "
                     + "; ".join(f"{w.get('title')} ({_why(w.get('why'))})"
                                 for w in withheld) + ".")
    keep = ("id", "kind", "subject", "title", "proof", "todo", "check", "figures", "window",
            "state", "marked", "recheck", "rows_total", "open")
    return "\n".join(lines), {
        "site": site, "window": doc.get("window"), "limits": doc.get("limits"),
        "marks": bool(doc.get("marks")),
        "todos": [{k: t.get(k) for k in keep} | {"state_words": STATES.get(t.get("state"), "")}
                  for t in items],
        "withheld": withheld}


def _one(site: str, t: dict, limit: int):
    rows = list(t.get("rows") or [])[:limit]
    cols = t.get("columns") or []
    lines = [f"{site}: to-do [{t['id']}] {t.get('title')} ({STATES.get(t.get('state'), '')}).",
             f"Proof: {t.get('proof')}", f"To do: {t.get('todo')}",
             f"How Skald checks it: {t.get('check')}."]
    if t.get("recheck"):
        lines.append(f"Re-check: {t['recheck'].get('words')}")
    head = [c.get("label") or c.get("key") for c in cols]
    lines.append(f"The list ({len(rows)} of {t.get('rows_total', len(rows))} rows): "
                 + " | ".join(head))
    for r in rows:
        lines.append("- " + " | ".join("" if r.get(c.get("key")) is None else str(r.get(c.get("key")))
                                       for c in cols))
    return "\n".join(lines), {"site": site, "todo": {k: v for k, v in t.items() if k != "rows"},
                              "rows": rows, "rows_shown": len(rows),
                              "rows_total": t.get("rows_total", len(rows))}


# ---------------------------------------------------------------- lost_pages

@tool("lost_pages", "Old addresses still asked for, with the closest live page",
      "Site > Not found: page addresses people, search engines and AI asked for in the last "
      "30 whole days that now answer 404 or 410 (scanner probes and bots left out), most "
      "asked first, each with the closest live page Skald found (the same page, the same "
      "topic, a loose match, or no good match) and the nginx or Apache line to copy (a 301 "
      "redirect, or 410 gone). part=markdown gives the Markdown copies (.md) AI asked for; "
      "part=fixed the addresses marked fixed and what came for them since. Skald never "
      "changes the web server.",
      schema({"site": SITE_ARG,
              "part": {"type": "string", "enum": ["lost", "markdown", "fixed"],
                       "default": "lost",
                       "description": "lost (the default), markdown or fixed."},
              "server": {"type": "string", "enum": ["nginx", "apache"], "default": "nginx",
                         "description": "Which server's line to give in the text."},
              "limit": LIMIT_ARG}))
def lost_pages(ctx, args):
    site = ctx.site(args.get("site"))
    doc = ctx.load(site, None, "lost_pages")
    part = args.get("part") or "lost"
    server = args.get("server") or "nginx"
    limit = int(args.get("limit") or 25)
    w = doc.get("window") or {}
    lines = [f"{site}: Site > Not found, {_window(w)}."]
    if w.get("not_recorded"):
        lines.append("Days not recorded, left out (never zero): "
                     + ", ".join(w["not_recorded"][:10])
                     + (f" and {len(w['not_recorded']) - 10} more" if len(w["not_recorded"]) > 10
                        else "") + ".")
    data = {"site": site, "part": part, "window": w, "live": doc.get("live"),
            "marks": bool(doc.get("marks")), "totals": doc.get("totals"),
            "withheld": doc.get("withheld") or [], "rows": None, "rows_total": None}
    if part == "fixed":
        rows = doc.get("fixed") or []
        data.update({"rows": rows[:limit], "rows_total": len(rows)})
        if not doc.get("marks"):
            lines.append("Marks are not kept here (no accounts), so no address is marked fixed.")
        elif not rows:
            lines.append("No address is marked fixed.")
        for r in rows[:limit]:
            lines.append(f"- {r['path']}: marked fixed {r.get('marked_day')}; "
                         f"{VERDICTS.get(r.get('verdict'), r.get('verdict'))} over {r.get('days')} "
                         f"whole days since (asked by people {r.get('people')}, search engines "
                         f"{r.get('search')}, AI {r.get('ai')}; served as a page "
                         f"{r.get('served')} times).")
        return "\n".join(lines), data
    if data["withheld"]:
        lines.append("Withheld, never shown: the second count disagreed ("
                     + _why(data["withheld"]) + ").")
        return "\n".join(lines), data
    t = doc.get("totals") or {}
    if part == "markdown":
        md = doc.get("markdown") or {}
        rows = [{**r, "of_live_page": True} for r in md.get("live") or []] + \
               [{**r, "of_live_page": False} for r in md.get("other") or []]
        data.update({"rows": rows[:limit], "rows_total": len(rows)})
        lines.append(f"AI asked {num(t.get('md_asks'))} times for {num(t.get('md_paths'))} "
                     f"Markdown addresses that failed; {num(t.get('md_live'))} of them copy a "
                     f"live page ({num(t.get('md_live_asks'))} asks).")
        for r in rows[:limit]:
            what = f"copies {r['page']}" if r.get("page") else "no live page"
            lines.append(f"- {r['path']} ({what}): AI {r.get('ai')} (for a question "
                         f"{r.get('ai_asked')}, to train or index {r.get('ai_training')}); "
                         f"line: {r.get(server) or 'none (the address cannot go in a line as it is)'}")
        return "\n".join(lines), data
    rows = doc.get("lost") or []
    data.update({"rows": rows[:limit], "rows_total": len(rows)})
    lines.append(f"{num(t.get('paths'))} old page addresses answered not found: people asked "
                 f"{num(t.get('people'))} times, search engines {num(t.get('search'))}, AI "
                 f"{num(t.get('ai'))}.")
    for r in rows[:limit]:
        target = (f"closest live page {r['target']} ({MATCH.get(r.get('match'), r.get('match'))})"
                  if r.get("target") else "no good match: answer 410 gone")
        fixed = f"; marked fixed {r['marked']}" if r.get("marked") else ""
        lines.append(f"- {r['path']}: people {r.get('people')}, search engines {r.get('search')}, "
                     f"AI {r.get('ai')}; {target}{fixed}; line: "
                     f"{r.get(server) or 'none (the address cannot go in a line as it is)'}")
    if len(rows) > limit:
        lines.append(f"{len(rows) - limit} more; raise limit to see them.")
    return "\n".join(lines), data
