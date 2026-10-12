"""The MCP tools that are not plain range sums: funnel, compare, page_story,
live_today, data_quality, site_health and conversions (tools.py has the
rest).

compare and page_story call the same functions the helper's
<page>/api/compare and <page>/api/page call (compare.compare,
lifecycle.story), on the history file opened read-only, so an agent gets
exactly the answer the page gets. A custom funnel is counted by the funnels
page's own code (funnels.clean, funnels.compute) over the journeys the
dashboard wrote to visits.json - no other counting road.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from .data import (HONEST, Refused, anchor_of, coverage, coverage_text, dig, num, parse_day,
                   period, total)
from .tools import FROM_ARG, SITE_ARG, TO_ARG, VIEW_ARG, schema, tool, where

KEEP_ROWS = 50          # compare: dimension rows kept per table in the answer
LABELS = {"visitors": "Visits (an upper bound on people)",
          "visitors_from_ai": "Visits that followed a link from an AI assistant",
          "returning": "Returning visits", "pages_per_visitor": "Pages per visit"}


def _tz(doc: dict):
    try:
        return ZoneInfo(str((doc or {}).get("timezone") or "UTC"))
    except (KeyError, ValueError):
        return timezone.utc


def _history(ctx):
    from ..store import History
    path = ctx.history_path
    if path is None or not path.exists():
        raise Refused("The history file is not on this server, so compare and page "
                      "stories cannot be answered here.")
    return History.reader(path)


# ---------------------------------------------------------------- funnel

STEP = {"type": "object", "description":
        "A step: {\"label\", \"kind\": \"path\" | \"any\" (first step only: every visit), "
        "\"match\": \"equals\" | \"starts_with\" | \"segment\" | \"contains\", \"paths\": "
        "[\"/pricing/\"]}. Lead and event steps are only in saved funnels."}


@tool("funnel", "A funnel over visits",
      "How many visits reached each step in order, and where they dropped off, from the "
      "anonymous journeys of the last 7 days and today. Give the name of a funnel saved on "
      "the dashboard (leave both out to list them), or 2 to 8 steps of your own. Lead "
      "steps come from the website's database and are never divided per visit.",
      schema({"site": SITE_ARG, "view": VIEW_ARG,
              "name": {"type": "string", "maxLength": 60,
                       "description": "A saved funnel's name, e.g. 'Landing to lead'."},
              "steps": {"type": "array", "items": STEP, "description": "Your own steps."},
              "source": {"type": "string", "maxLength": 60,
                         "description": "Only visits from this source type ('AI assistant') "
                                        "or assistant or host ('ChatGPT'). Custom steps "
                                        "only."}}))
def funnel(ctx, args):
    site = ctx.site(args.get("site"))
    view = ctx.view(site, args.get("view"))
    if args.get("steps") is not None:
        return _custom(ctx, site, view, args)
    doc = ctx.load(site, view, "funnels")
    funnels = doc.get("funnels") or []
    name = (args.get("name") or "").strip()
    if name:
        funnels = [f for f in funnels if str(f.get("name", "")).lower() == name.lower()]
        if not funnels:
            names = ", ".join(f.get("name", "") for f in doc.get("funnels") or []) or "none"
            raise Refused(f"{site} has no funnel named {name!r}. Saved: {names}.")
    lines = [f"{where(site, view)}: funnels over visits (an upper bound on people), from the "
             "anonymous journeys of the last 7 days and today."]
    for f in funnels:
        lines.append(_funnel_text(f.get("name"), f.get("result") or {}))
    return "\n".join(lines), {"site": site, "view": view, "funnels": funnels}


def _funnel_text(name, result: dict) -> str:
    parts = []
    for s in result.get("steps") or []:
        if s.get("kind") in ("lead", "event"):
            what = "from the website's database" if s["kind"] == "lead" else "beacon events"
            parts.append(f"{s['label']}: {num(s.get('n'))} ({what}, not per visit)")
        else:
            share = s.get("of_first_pct")
            parts.append(f"{s['label']}: {num(s.get('n'))}"
                         + (f" ({share:g}% of the first step)" if share is not None else ""))
    return (f"- {name} ({result.get('first')} to {result.get('last')}, "
            f"{num(result.get('visits'))} visits): " + " -> ".join(parts))


def _custom(ctx, site, view, args):
    from .. import funnels
    steps = args["steps"]
    if any(isinstance(s, dict) and s.get("kind") in ("lead", "event") for s in steps):
        raise Refused("Lead and event steps are only in funnels saved on the dashboard; "
                      "give path steps here.")
    try:
        f = funnels.clean({"name": "Custom", "steps": steps, "source": args.get("source")})
    except funnels.Invalid as why:
        raise Refused(f"Those steps are not valid: {why}.")
    visits = ctx.load(site, view, "visits")
    ov = ctx.load(site, view, "overview")
    today = date.fromisoformat(ov.get("today") or ov["anchor"])
    states = {d.get("day"): d.get("state") for d in visits.get("days") or []}
    journeys = [j for j in visits.get("journeys") or []
                if states.get(str(j.get("day"))) in ("ok", "partial")]
    if dig(visits, "today", "state") == "ok":
        journeys += list(dig(visits, "today", "journeys") or [])
    first = today - timedelta(days=int(visits.get("journey_days") or 7))
    result, _ = funnels.compute(f, journeys, first, today, None, _tz(ov))
    left = sorted(d for d, s in states.items() if d and d >= first.isoformat()
                  and s in ("withheld", "missing"))
    text = [f"{where(site, view)}: your funnel over visits (an upper bound on people), from "
            "the anonymous journeys of the last 7 days and today.",
            _funnel_text("Custom", result)]
    if left:
        text.append("Days whose journeys are left out (withheld or not collected): "
                    + ", ".join(left) + ".")
    return "\n".join(text), {"site": site, "view": view, "funnel": {**f, "result": result},
                             "days_left_out": left}


# ---------------------------------------------------------------- compare

@tool("compare", "Compare two date ranges",
      "Compare range A (the one looked at) with range B: visits (an upper bound on people), "
      "pages read, AI fetches, search fetches, leads and more, each a sum over the whole, "
      "verified days of its range, with the change and the pages, sources, countries and "
      "devices that moved. Ranges up to 400 days. Default: the last 7 whole days against "
      "the 7 before.",
      schema({"site": SITE_ARG, "view": VIEW_ARG,
              "a_from": {**FROM_ARG, "description": "A's first day, YYYY-MM-DD."},
              "a_to": {**TO_ARG, "description": "A's last day. Default: yesterday."},
              "b_from": {**FROM_ARG, "description": "B's first day. Default: the days "
                                                    "just before A, as many as A has."},
              "b_to": {**TO_ARG, "description": "B's last day."},
              "filters": {"type": "object", "additionalProperties": {"type": "string"},
                          "description": "Optional, e.g. {\"country\": \"CA\"}: page, "
                                         "country, continent, source, assistant, device, "
                                         "browser, os, campaign, landing."}}))
def compare_tool(ctx, args):
    from .. import compare
    site = ctx.site(args.get("site"))
    view = ctx.view(site, args.get("view"))
    ov = ctx.load(site, view, "overview")
    anchor = anchor_of(ov)
    a_first, a_last = period(args, anchor, "a_from", "a_to", max_days=compare.MAX_DAYS)
    length = (a_last - a_first).days + 1
    if args.get("b_from") or args.get("b_to"):
        b_first = parse_day(args.get("b_from") or "", "b_from") if args.get("b_from") else None
        b_last = parse_day(args.get("b_to") or "", "b_to") if args.get("b_to") else None
        b_first = b_first or b_last - timedelta(days=length - 1)
        b_last = b_last or b_first + timedelta(days=length - 1)
    else:
        b_first, b_last = a_first - timedelta(days=length), a_first - timedelta(days=1)
    filters = {str(k): str(v) for k, v in (args.get("filters") or {}).items()}
    history = _history(ctx)
    try:
        got = compare.compare(history, site, view, f"{a_first}..{a_last}",
                              f"{b_first}..{b_last}", filters, ctx.config_for(site), _tz(ov))
    except compare.Invalid as why:
        raise Refused(f"Those ranges or filters are not valid: {why}.")
    finally:
        history.db.close()
    a, b = got["a"], got["b"]
    lines = [f"{where(site, view)}: A {a['from']} to {a['to']} ({a['used']} whole, verified "
             f"days of {a['days']}) against B {b['from']} to {b['to']} ({b['used']} of "
             f"{b['days']})." + (f" Filtered by {filters}." if filters else "")]
    if not got.get("reconciled"):
        lines.append("These figures do not reconcile, so they are withheld: "
                     + "; ".join(got.get("problems") or []) + ".")
        return "\n".join(lines), {k: got.get(k) for k in
                                  ("site", "view", "a", "b", "filters", "reconciled",
                                   "problems")}
    whole = not a["excluded"] and not b["excluded"]
    for m in got["metrics"]:
        label = LABELS.get(m["key"], m["label"])
        change = "" if m["delta_pct"] is None or not whole else f" ({m['delta_pct']:+.1f}%)"
        lines.append(f"- {label}: A {num(m['a'])}, B {num(m['b'])}{change}")
    if not whole:
        lines.append("No change is stated: A or B has days left out, so the two are not "
                     "like for like.")
    for side, meta in (("A", a), ("B", b)):
        if meta["excluded"]:
            lines.append(f"Left out of {side}, never counted as zero: "
                         + _excluded(meta["excluded"]) + ".")
    movers = [r for r in (got["dimensions"].get("pages") or []) if r.get("delta")]
    if movers:
        movers.sort(key=lambda r: -abs(r["delta"]))
        lines.append("Pages that moved most (page views): " + ", ".join(
            f"{r['name']} {r['delta']:+,}" for r in movers[:5]) + ".")
    lines.append("A null figure is one the filters cannot split, or one not recorded. "
                 + HONEST)
    dims = {k: (v[:KEEP_ROWS] if isinstance(v, list) else v)
            for k, v in got["dimensions"].items()}
    return "\n".join(lines), {**got, "dimensions": dims, "dimension_rows_kept": KEEP_ROWS}


def _excluded(rows: list[dict]) -> str:
    """Left-out days by state: each date when few, else a count and the span."""
    by: dict[str, list[str]] = {}
    for e in rows:
        by.setdefault(e["state"], []).append(e["day"])
    return "; ".join(f"{state} " + (", ".join(days) if len(days) <= 8 else
                                    f"{len(days)} days, {days[0]} to {days[-1]}")
                     for state, days in by.items())


# ---------------------------------------------------------------- page_story

@tool("page_story", "One page's story since it was published",
      "What happened to one page since it was published: when Googlebot, Bingbot and each "
      "AI crawler first fetched it, the first person to read it, the first from search and "
      "from an assistant, the first lead, and its days since, with visits (an upper bound "
      "on people) per whole, verified day.",
      schema({"site": SITE_ARG,
              "path": {"type": "string", "maxLength": 300,
                       "description": "The page's path, e.g. /pricing/."}},
             required=("path",)))
def page_story(ctx, args):
    from .. import lifecycle
    site = ctx.site(args.get("site"))
    path = args["path"].strip()
    if not path.startswith("/"):
        raise Refused("A path starts with /, e.g. /pricing/.")
    ov = ctx.load(site, None, "overview")
    tz = _tz(ov)
    history = _history(ctx)
    try:
        got = lifecycle.story(history, site, path, ctx.config_for(site), tz,
                              datetime.now(timezone.utc).astimezone(tz).date())
    finally:
        history.db.close()
    if not got.get("ok"):
        raise Refused(f"{site} has no page {path}: {got.get('error') or 'not found'}.")
    days = got.get("days") or []
    ok = [d for d in days if d.get("state") == "ok"]
    readers, views = total(ok, "readers"), total(ok, "views")
    lines = [f"{site} {got['path']}" + (f" \"{got['title']}\"" if got.get("title") else "")
             + f": published {got.get('published') or 'unknown'} "
             f"({got.get('date_source')}), first seen in the logs {got.get('first_seen')}."]
    marks = got.get("milestones") or {}
    names = {"googlebot": "Googlebot first fetched it", "bingbot": "Bingbot first fetched it",
             "human": "first person read it", "from_search": "first visit from a search engine",
             "lead_landed": "first lead that landed on it", "lead_sent": "first lead sent "
             "from it"}
    for key, label in names.items():
        m = marks.get(key)
        lines.append(f"- {label}: " + (f"{m.get('at')}" + (f" ({m['who']})" if m.get("who")
                                                          else "") if m else "not yet"))
    for key, label in (("ai_training", "AI crawlers (train or index)"),
                       ("ai_asked", "assistants fetching for a question"),
                       ("from_ai", "first visits from an assistant")):
        got_list = marks.get(key) or []
        lines.append(f"- {label}: " + (", ".join(f"{m['who']} {m['at']}" for m in got_list)
                                       or "none yet"))
    if days:
        cov, _ = coverage(days, date.fromisoformat(days[0]["day"]),
                          date.fromisoformat(days[-1]["day"]),
                          date.fromisoformat(days[-1]["day"]))
        lines.append("Since then, over the whole, verified days: visits (an upper bound on "
                     f"people) that read it: {num(readers)}; page views: {num(views)}.")
        lines.append(coverage_text(cov))
    return "\n".join(lines), {k: v for k, v in got.items() if k != "ok"} | {
        "site": site, "visits_total": readers, "page_views_total": views}


# ---------------------------------------------------------------- live_today

@tool("live_today", "Today so far",
      "Today so far, from the live snapshot the server writes every 2 minutes: visits (an "
      "upper bound on people), pages read, AI fetches and the latest AI events (no "
      "addresses). Today is partial and not yet audited: never compare it with whole days.",
      schema({"site": SITE_ARG, "view": VIEW_ARG}))
def live_today(ctx, args):
    site = ctx.site(args.get("site"))
    view = ctx.view(site, args.get("view"))
    doc = ctx.load(site, view, "live")
    state = doc.get("state")
    data = {"site": site, "view": view, "state": state, "stale": bool(doc.get("stale")),
            "day": doc.get("day"), "from": doc.get("from"), "until": doc.get("until"),
            "generated_at": doc.get("generated_at")}
    if doc.get("stale") or state is None:
        return (f"{where(site, view)}: there is no live snapshot for today yet (the last one "
                f"is from {doc.get('day') or 'never'}). No figure is shown for today.", data)
    if state != "ok":
        why = "; ".join(str(p) for p in doc.get("problems") or []) or (
            "nothing logged yet today" if state == "empty" else "the figures did not reconcile")
        return (f"{where(site, view)}, today {doc.get('day')}: {state} ({why}). No figure is "
                "shown, never as zero.", {**data, "problems": doc.get("problems")})
    people = doc.get("people") or {}
    search = doc.get("search") or {}
    data.update({"visits": people.get("readers"), "pages_read": people.get("views"),
                 "visits_from_ai_citations": people.get("cited_visits"),
                 "ai_fetches": doc.get("ai_tiers"), "ai_by_name": doc.get("ai"),
                 "search_engine_fetches": (sum(search.values())
                                           if isinstance(doc.get("search"), dict) else None),
                 "requests": doc.get("requests"), "requests_by_group": doc.get("groups"),
                 "pages": dict(sorted((people.get("pages") or {}).items(),
                                      key=lambda kv: -kv[1])[:20]),
                 "countries": people.get("countries"),
                 "events": [{k: e.get(k) for k in ("at", "kind", "who", "path")}
                            for e in doc.get("events") or []][:20]})
    tiers = doc.get("ai_tiers") or {}
    lines = [f"{where(site, view)}, today {doc.get('day')} from {doc.get('from')} until "
             f"{doc.get('until')} (live, partial, not yet audited; never compare with whole "
             "days).",
             f"Visits (an upper bound on people): {num(data['visits'])}. Pages read: "
             f"{num(data['pages_read'])}. From an AI assistant's link: "
             f"{num(data['visits_from_ai_citations'])}.",
             f"AI fetches: {num(tiers.get('asked'))} when someone asked, "
             f"{num(tiers.get('training'))} to train or index. Search-engine fetches: "
             f"{num(data['search_engine_fetches'])}. All requests: {num(data['requests'])} "
             "(requests are not people)."]
    if data["events"]:
        lines.append("Latest AI events: " + "; ".join(
            f"{e['at']} {e['who']} {e['kind']} {e['path']}" for e in data["events"][:5]) + ".")
    return "\n".join(lines), data


# ---------------------------------------------------------------- data_quality

@tool("data_quality", "Can the figures be trusted",
      "Per day: whether the log was read whole, verify and the independent audit passed, "
      "gaps in the log, unreadable and duplicate lines; plus any data file that failed to "
      "build. Withheld and partial days are listed by date with the reason.",
      schema({"site": SITE_ARG, "from": FROM_ARG, "to": TO_ARG}))
def data_quality(ctx, args):
    site = ctx.site(args.get("site"))
    ov = ctx.load(site, None, "overview")
    anchor = anchor_of(ov)
    first, last = period(args, anchor)
    doc = ctx.load(site, None, "quality")
    cov, _ = coverage(doc.get("days"), first, last, anchor)
    rows = [d for d in doc.get("days") or [] if first.isoformat() <= d.get("day", "")
            <= last.isoformat()]
    mismatch = [d["day"] for d in rows if dig(d, "audit", "state") == "mismatch"]
    not_audited = [d["day"] for d in rows if d.get("state") == "ok"
                   and dig(d, "audit", "state") in (None, "not run")]
    gaps = [(d["day"], g) for d in rows for g in d.get("gaps") or [] if g.get("minutes", 0) >= 60]
    by_day = {d.get("day"): d for d in rows}
    recorded, unrecorded = [], []
    day = first
    while day <= last:
        e = by_day.get(day.isoformat()) or {}
        v = e.get("unparsed")
        if isinstance(v, int) and not isinstance(v, bool):
            recorded.append(v)
        elif day <= anchor:
            unrecorded.append(day.isoformat())
        day += timedelta(days=1)
    unparsed = sum(recorded) if recorded else None
    failing = doc.get("builders_failing") or []
    lines = [f"{site}, {first} to {last}: data quality.", coverage_text(cov)]
    lines.append("Audit mismatches: " + (", ".join(mismatch) if mismatch else "none") + ".")
    if not_audited:
        lines.append("Whole days the audit has not recounted yet: " + ", ".join(not_audited)
                     + ".")
    if gaps:
        lines.append("Log gaps of an hour or more: " + "; ".join(
            f"{day} {g.get('from')}-{g.get('to')} ({g.get('minutes')} min)"
            for day, g in gaps[:10]) + ".")
    lines.append(f"Lines that could not be read: {num(unparsed)}"
                 + (f" (not recorded, so not counted: {', '.join(unrecorded[:10])}"
                    + (f" and {len(unrecorded) - 10} more" if len(unrecorded) > 10 else "")
                    + ")" if unrecorded and recorded else "") + ".")
    lines.append("Data files that failed to build: " + (", ".join(
        f"{f.get('file')} since {f.get('since')} ({f.get('error')})" for f in failing)
        if failing else "none") + ".")
    today = doc.get("today")
    if today:
        lines.append(f"Today: newest log line {today.get('newest_line')}, "
                     f"{num(today.get('lines'))} lines so far.")
    return "\n".join(lines), {"site": site, "from": first.isoformat(), "to": last.isoformat(),
                              "coverage": cov, "days": rows, "audit_mismatch": mismatch,
                              "not_audited": not_audited, "builders_failing": failing,
                              "unparsed": unparsed, "unparsed_not_recorded": unrecorded,
                              "today": today, "runs": doc.get("runs")}


# ---------------------------------------------------------------- site_health

@tool("site_health", "Is the site and Skald healthy",
      "Open alerts, the server's own heartbeat (uptime), server errors and 404s today, "
      "whether Skald's scheduled runs are on time, and the latest page-speed test status.",
      schema({"site": SITE_ARG}))
def site_health(ctx, args):
    site = ctx.site(args.get("site"))
    alerts = ctx.load(site, None, "alerts", required=False) or {}
    health = ctx.load(site, None, "health", required=False) or {}
    ours = ctx.load(site, None, "ours", required=False) or {}
    quality = ctx.load(site, None, "quality", required=False) or {}
    speed = ctx.load(site, None, "speed", required=False) or {}
    open_ = [{k: a.get(k) for k in ("cause", "subject", "severity", "title", "opened_at",
                                     "last_seen_at")} for a in alerts.get("open") or []]
    today = health.get("today") or {}
    statuses = today.get("statuses") or {} if today.get("state") == "ok" else None
    errors = (sum(int(s.get("5xx", 0)) for s in statuses.values()) if statuses is not None
              else None)
    not_found = (int(dig(statuses, "people", "404") or 0) if statuses is not None else None)
    beat = dig(ours, "today", "heartbeat")
    late, never = [], []
    now = _stamp(quality.get("generated_at"))
    for name, r in (quality.get("runs") or {}).items():
        last_ok = _stamp(r.get("last_ok"))
        every = int(r.get("expected_every_min") or 0)
        if last_ok is None:
            never.append(name)
        elif now and every and (now - last_ok).total_seconds() > every * 60 * 2 + 600:
            late.append({"run": name, "last_ok": r.get("last_ok"), "every_min": every})
    data = {"site": site, "alerts_enabled": alerts.get("enabled"), "open_alerts": open_,
            "today": {"state": today.get("state"), "server_errors": errors,
                      "not_found_people": not_found},
            "heartbeat_today": beat, "runs_late": late, "runs_never_ok": never,
            "speed": speed.get("status")}
    lines = [f"{site}: health."]
    lines.append(f"Open alerts: {len(open_)}" + (": " + "; ".join(
        f"{a['title']} ({a['severity']})" for a in open_) if open_ else "") + "."
        + ("" if alerts.get("enabled") else " (Alerts are switched off in the config.)"))
    if today.get("state") == "ok":
        lines.append(f"Today so far: {num(errors)} server errors, {num(not_found)} 404s people "
                     "met.")
    else:
        lines.append("Today: no live figures yet.")
    if isinstance(beat, dict) and beat.get("seen"):
        lines.append(f"Heartbeat today: {num(beat.get('ok'))} of {num(beat.get('expected'))} "
                     f"answered ({num(beat.get('uptime_pct'))}% uptime).")
    else:
        lines.append("Heartbeat: none seen today (not set up, or the site is not answering it).")
    lines.append("Scheduled runs late: " + (", ".join(
        f"{r['run']} (last ok {r['last_ok']})" for r in late) if late else "none") + ".")
    if never:
        lines.append("Never finished here yet: " + ", ".join(never) + ".")
    status = speed.get("status") or {}
    if status:
        lines.append(f"Page speed: {status.get('state')}"
                     + (f" - {status['message']}" if status.get("message") else "") + ".")
    return "\n".join(lines), data


# ---------------------------------------------------------------- conversions

BY_DIMS = ("source_type", "first_source", "landing", "country", "campaign", "device", "tool")
BY_WORDS = {"source_type": "source (last touch)", "first_source": "first touch",
            "landing": "landing page", "country": "country", "campaign": "campaign",
            "device": "device", "tool": "reported by"}

@tool("conversions", "Conversions: demos, forms, sign-ups, payments",
      "Every action that counts (a demo booked, a form sent, a sign-up, a payment), from "
      "the page's script tag, the tools' webhooks and the site's lead database, over a "
      "range of local days: started, completed (completed or paid), abandoned (started "
      "with a visitor ID and not finished in time), the completion rate (only over 10 or "
      "more starts), other stages (cancelled, no-show, won, lost), and completed ones by "
      "source (or by another breakdown: first touch, landing page, country, campaign, "
      "device, tool), with the leads (forms sent and demos booked) and demos booked "
      "among them. Withheld and not-recorded days are named and never counted as zero. "
      "Anonymous: no name, email or visitor ID.",
      schema({"site": SITE_ARG, "from": FROM_ARG, "to": TO_ARG,
              "action": {"type": "string", "maxLength": 40,
                         "description": "Only this action, e.g. 'demo', 'contact', "
                                        "'signup', 'paid'."},
              "by": {"type": "string", "enum": list(BY_DIMS),
                     "description": "Break the completed ones (and the leads) down by: "
                                    "source_type (last touch, the default), first_source "
                                    "(first touch), landing, country, campaign, device, "
                                    "tool."}}))
def conversions(ctx, args):
    site = ctx.site(args.get("site"))
    doc = ctx.load(site, None, "conversions", required=False) or {}
    if not doc.get("available"):
        why = doc.get("reason") or doc.get("error") or "the conversions file is not written"
        return (f"{site}: conversions are not available here ({why}). No figure is shown, "
                "never as zero.", {"site": site, "available": False, "reason": why})
    ov = ctx.load(site, None, "overview", required=False) or {}
    today = str(ov.get("today") or "") or None
    anchor = parse_day(today, "today") if today else anchor_of(ov)
    first, last = period(args, anchor)
    only = str(args.get("action") or "").strip().lower() or None
    dim = str(args.get("by") or "source_type")
    if dim not in BY_DIMS:
        dim = "source_type"
    lead_acts = set(doc.get("lead_actions") or ())
    demo_acts = set(doc.get("demo_actions") or ())
    leads_by: dict = {}
    finished = set(doc.get("finished") or ("completed", "paid"))
    least = int(doc.get("min_rate") or 10)
    by = {d.get("day"): d for d in doc.get("days") or [] if isinstance(d, dict)}
    stages: dict = {}
    abandoned: dict = {}
    sources: dict = {}
    withheld, missing, counted = [], [], 0
    day = first
    while day <= last:
        e = by.get(day.isoformat())
        state = (e or {}).get("state")
        if state == "withheld":
            withheld.append({"day": day.isoformat(), "why": e.get("why") or ""})
        elif state != "ok":
            missing.append(day.isoformat())
        else:
            counted += 1
            for action, per in (e.get("stages") or {}).items():
                if only and action != only:
                    continue
                mine = stages.setdefault(action, {})
                for stage, v in per.items():
                    mine[stage] = mine.get(stage, 0) + int(v)
            for action, v in (e.get("abandoned") or {}).items():
                if not only or action == only:
                    abandoned[action] = abandoned.get(action, 0) + int(v)
            for action, per in (dig(e, "by", dim) or {}).items():
                if not only or action == only:
                    for k, v in per.items():
                        sources[k] = sources.get(k, 0) + int(v)
                if action in lead_acts and (not only or action == only):
                    for k, v in per.items():
                        leads_by[k] = leads_by.get(k, 0) + int(v)
        day += timedelta(days=1)
    actions = {}
    for action, per in sorted(stages.items()):
        started = per.get("started", 0)
        done = sum(v for k, v in per.items() if k in finished)
        actions[action] = {"started": started, "completed": done,
                           "abandoned": abandoned.get(action, 0),
                           "completion_rate": (round(min(done, started) / started, 4)
                                               if started >= least else None),
                           **{k: v for k, v in per.items()
                              if k not in finished and k != "started"}}
    def ranked(got):
        return dict(sorted(got.items(), key=lambda kv: (-kv[1], kv[0])))
    leads = sum(a["completed"] for k, a in actions.items() if k in lead_acts)
    demos = sum(a["completed"] for k, a in actions.items() if k in demo_acts)
    data = {"site": site, "available": True, "from": first.isoformat(),
            "to": last.isoformat(), "action": only, "days_counted": counted,
            "actions": actions, "by": dim, "by_source": ranked(sources),
            "leads": leads if counted else None, "demos_booked": demos if counted else None,
            "lead_actions": sorted(lead_acts), "leads_by": ranked(leads_by),
            "withheld": withheld, "not_recorded": missing,
            "note": doc.get("as_known")}
    lines = [f"{site}, {first} to {last}: conversions ({counted} day"
             f"{'s' if counted != 1 else ''} counted)."]
    if counted:
        for action, a in actions.items():
            rate = (f", {a['completion_rate'] * 100:.1f}% completed" if a["completion_rate"]
                    is not None else (f", too few starts to give a rate (under {least})"
                                      if a["started"] else ""))
            extra = ", ".join(f"{v:,} {k}" for k, v in a.items() if k not in (
                "started", "completed", "abandoned", "completion_rate"))
            lines.append(f"{action}: {a['started']:,} started, {a['completed']:,} completed, "
                         f"{a['abandoned']:,} abandoned{rate}" + (f"; {extra}" if extra else "")
                         + ".")
        if not actions:
            lines.append("No conversion on the counted days.")
        if lead_acts:
            lines.append(f"Leads (forms sent and demos booked, completed): {leads:,}, of them "
                         f"{demos:,} demos booked.")
        if sources:
            lines.append(f"Completed, by {BY_WORDS[dim]}: " + ", ".join(
                f"{k} {v:,}" for k, v in data["by_source"].items()) + ".")
        if leads_by:
            lines.append(f"Leads, by {BY_WORDS[dim]}: " + ", ".join(
                f"{k} {v:,}" for k, v in data["leads_by"].items()) + ".")
    else:
        lines.append("Conversions: not recorded (no day of this range holds checked "
                     "figures), never zero.")
    if withheld:
        lines.append("Days withheld (the second count disagreed, none of their figures are "
                     "counted): " + ", ".join(w["day"] for w in withheld[:10])
                     + (f" and {len(withheld) - 10} more" if len(withheld) > 10 else "") + ".")
    if missing:
        lines.append("Days not recorded: " + ", ".join(missing[:10])
                     + (f" and {len(missing) - 10} more" if len(missing) > 10 else "") + ".")
    if doc.get("as_known"):
        lines.append(doc["as_known"])
    return "\n".join(lines), data


def _stamp(text):
    try:
        got = datetime.fromisoformat(str(text))
    except (TypeError, ValueError):
        return None
    return got if got.tzinfo else got.replace(tzinfo=timezone.utc)
