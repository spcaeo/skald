"""Whole-day alerts read from stored history: AI citations and crawlers.

Four rules, beside the AI reading rules (alerts_ai.py) and through the same
machinery (alerts.py): the alert state, one mail per alert, the cooldown,
the daily digest, alerts.json, the dashboard's Alerts tab and the outgoing
webhook event `alert.opened`.

  ai_first_citation    the first visit ever on this site that followed a
                       citation from an assistant fell on the last whole day
  ai_first_cited_page  a page's first visit ever from an AI citation fell
                       on the last whole day
  ai_cited_visits      visits from AI answers (readers whose source is "AI
                       assistant") on the last whole day rose to at least
                       `cited_spike_factor` (2) times the usual and at least
                       `cited_minimum` (10), or fell to at most
                       `cited_drop_percent` (50) % of a usual of at least
                       `cited_minimum`. The usual is the median of the same
                       weekday in the `cited_weeks` (6) weeks before; at
                       least `cited_min_weeks` (4) of them must be counted.
                       Below the minimum it is "too few to judge".
  crawler_silent       an AI or search crawler that made requests on at least
                       `silent_active_days` (7) of the 28 days before has made
                       none in the last `silent_days` (7) whole days

Visits and requests are never mixed: the citation rules count visits (a
person who clicked a link in an answer), the crawler rule counts requests.

No new figure is counted here. The rules read figures each day already
checked twice: each page's first times (`page_firsts`, kept for good as
`page_milestones`; recounted from the raw log by audit_release2), the
visits that followed a citation by assistant and by page (`cited_by`,
`cited_page`), readers by source (`reader_source`, recounted by the audit)
and each crawler's requests (`crawler_paths`, recounted by audit_release2).
Every alert's figures are worked out again from stored history by
audit_alerts.py (run-daily's recounts), with its own code.

Whole days only. A withheld, partial or missing day, or a figure not
recorded, makes a rule wait (state "waiting", with the days): it never fires
on them. The first-citation rules also wait until history is
`first_min_days` (28) days old, so a new install does not call every
citation a first.

Settings: the config's `alerts` section (`cited_weeks: 6`, ...). Evaluated
once per last whole day and kept in the alert state (`history`); evaluated
again when the day or the settings change, or after WAIT_RECHECK while a
rule waits.
"""
from __future__ import annotations

import json
import statistics
from datetime import date, datetime, timedelta, timezone

CAUSES = ("ai_first_citation", "ai_first_cited_page", "ai_cited_visits", "crawler_silent")
SEVERITY = {"ai_first_citation": "low", "ai_first_cited_page": "low",
            "ai_cited_visits": "medium", "crawler_silent": "medium"}
UNIT = {"ai_first_citation": "visits", "ai_first_cited_page": "visits",
        "ai_cited_visits": "visits", "crawler_silent": "requests"}
RULE = {"ai_first_citation": "first_citation", "ai_first_cited_page": "first_cited_page",
        "ai_cited_visits": "cited_visits", "crawler_silent": "crawler_silent"}
DEFAULTS = {
    "first_citation": True, "first_cited_page": True, "first_min_days": 28,
    "first_max_pages": 5,
    "cited_visits": True, "cited_weeks": 6, "cited_min_weeks": 4, "cited_spike_factor": 2,
    "cited_drop_percent": 50, "cited_minimum": 10,
    "crawler_silent": True, "silent_days": 7, "silent_active_days": 7,
}
SILENT_BASE = 28
CITED = "AI assistant"                # the source label of a cited visit
CRAWLERS = ("answer_engines", "search_engines")
WAIT_RECHECK = timedelta(minutes=30)
TOO_FEW = "too few to judge"
LIST = 10
FROM_FIRSTS = ("From figures already checked twice: each page's first times, recounted from "
               "the raw log by the audit. Whole days only.")
FROM_SOURCES = ("From figures already checked twice: readers by source, recounted from the "
                "raw log by the audit. Whole days only.")
FROM_PATHS = ("From figures already checked twice: each crawler's requests, recounted from "
              "the raw log by the audit. Whole days only.")


def settings(config: dict | None) -> dict:
    section = (config or {}).get("alerts") or {}
    out = {}
    for key, default in DEFAULTS.items():
        value = section.get(key, default)
        if value in (None, "", []):
            value = default
        if isinstance(default, bool):
            out[key] = value if isinstance(value, bool) else (
                str(value).strip().lower() in ("1", "true", "yes", "on"))
        else:
            try:
                out[key] = max(0, int(value))
            except (TypeError, ValueError):
                out[key] = default
    out["cited_weeks"] = min(max(out["cited_weeks"], 4), 8)
    out["cited_min_weeks"] = min(max(out["cited_min_weeks"], 1), out["cited_weeks"])
    out["cited_spike_factor"] = max(out["cited_spike_factor"], 1)
    out["cited_drop_percent"] = min(out["cited_drop_percent"], 99)
    out["cited_minimum"] = max(out["cited_minimum"], 1)
    out["silent_days"] = min(max(out["silent_days"], 1), SILENT_BASE)
    out["silent_active_days"] = min(max(out["silent_active_days"], 1), SILENT_BASE)
    out["first_max_pages"] = max(out["first_max_pages"], 1)
    return out


def rules(cfg: dict) -> list[dict]:
    """The four rules for alerts.json's `rules`, in words."""
    words = {
        "ai_first_citation": "the first visit ever that followed a citation from an AI "
                             "assistant (whole days only)",
        "ai_first_cited_page": "a page's first visit ever from an AI citation (whole days only)",
        "ai_cited_visits": f"visits from AI answers at least {cfg['cited_spike_factor']}x the "
                           f"same weekday's median over {cfg['cited_weeks']} weeks (and "
                           f"{cfg['cited_minimum']}+), or at most {cfg['cited_drop_percent']}% "
                           f"of a median of {cfg['cited_minimum']}+; fewer: too few to judge",
        "crawler_silent": f"an AI or search crawler seen on {cfg['silent_active_days']}+ of 28 "
                          f"days has made no request for {cfg['silent_days']} days",
    }
    return [{"cause": c, "on": cfg[RULE[c]], "threshold": words[c], "unit": UNIT[c],
             **({"group": "ai"} if c.startswith("ai_") else {})} for c in CAUSES]


# ------------------------------------------------------------- helpers

def _rule(on: bool) -> dict:
    return {"on": on, "state": "off" if not on else "ok", "waiting_on": [], "found": 0}


def _wait(rule: dict, gaps: list[str], why: str = "") -> dict:
    rule.update(state="waiting", waiting_on=gaps)
    if why:
        rule["why"] = why
    return rule


def _short(d: date) -> str:
    return f"{d:%a %d %b} ({d.isoformat()})"


def _visits(n) -> str:
    return "not recorded" if n is None else ("1 visit" if n == 1 else f"{n} visits")


def _norm(path: str) -> str:
    """One page whether asked for with or without its trailing slash."""
    return (path or "").rstrip("/") or "/"


def _finding(cause, subject, title, detail, figure, threshold, data) -> dict:
    return {"cause": cause, "subject": subject, "title": title, "detail": detail,
            "figure": figure, "threshold": threshold, "unit": UNIT[cause], "data": data}


def states(history, site: str, first: date, last: date) -> dict:
    return {e["day"]: e["state"] for e in history.daily(site, first, last)}


def _counts(db, site: str, kind: str, day: date) -> dict:
    return {name: int(n) for name, n in db.execute(
        "SELECT name, n FROM counts WHERE site = ? AND kind = ? AND day = ?",
        (site, kind, day.isoformat()))}


def _named_before(db, site: str, kind: str, day: date) -> set:
    return {r[0] for r in db.execute(
        "SELECT DISTINCT name FROM counts WHERE site = ? AND kind = ? AND day < ? AND n > 0",
        (site, kind, day.isoformat()))}


# --------------------------------------------------------------- rules

def _firsts(cfg: dict, history, site: str, day: date, tz, state: str) -> tuple:
    """The first citation from each assistant, and of each page."""
    r1, r2 = _rule(cfg["first_citation"]), _rule(cfg["first_cited_page"])
    on = [r for r in (r1, r2) if r["on"]]
    if not on:
        return [], r1, r2
    start = history.first_day(site)
    if state != "ok":
        for r in on:
            _wait(r, [day.isoformat()])
        return [], r1, r2
    if start is None or (day - start).days < cfg["first_min_days"]:
        for r in on:
            _wait(r, [], f"history began {start.isoformat() if start else 'today'}: fewer "
                         f"than {cfg['first_min_days']} days to call a citation a first")
        return [], r1, r2
    db = history.db
    by_who: dict = {}                   # assistant -> (utc at, path)
    by_page: dict = {}                  # page -> (utc at, assistant, path as stored)
    for path, who, at in db.execute(
            "SELECT path, who, at FROM page_milestones WHERE site = ? AND kind = 'from_ai'",
            (site,)):
        if who and (who not in by_who or at < by_who[who][0]):
            by_who[who] = (at, path)
        key = _norm(path)
        if key not in by_page or at < by_page[key][0]:
            by_page[key] = (at, who, path)

    def local_day(at: str) -> date | None:
        try:
            return datetime.fromisoformat(at).astimezone(tz).date()
        except ValueError:
            return None
    since = f"in the stored history since {start.isoformat()}"
    found = []
    if r1["on"]:
        before = _named_before(db, site, "cited_by", day)
        today = _counts(db, site, "cited_by", day)
        for who, (at, path) in sorted(by_who.items()):
            if local_day(at) != day or who in before:
                continue
            n = today.get(who)
            when = datetime.fromisoformat(at).astimezone(tz)
            found.append(_finding(
                "ai_first_citation", who, f"First visit ever from a citation in {who}",
                f"The first visit ever that followed a citation from {who}: {when:%H:%M} on "
                f"{_short(day)}, landing on {path}. {who} sent {_visits(n)} by citation that "
                f"day. No earlier visit followed a citation from it {since}. Visits are "
                f"people who clicked a link in an answer, never the assistant's fetches. "
                f"{FROM_FIRSTS}", n, 0,
                {"kind": "first_citation", "assistant": who, "day": day.isoformat(),
                 "at": at, "path": path, "visits": n, "history_since": start.isoformat()}))
        r1["found"] = len(found)
    if r2["on"]:
        before = {_norm(p) for p in _named_before(db, site, "cited_page", day)}
        today = {}
        for p, n in _counts(db, site, "cited_page", day).items():
            today[_norm(p)] = today.get(_norm(p), 0) + n
        new = sorted(((at, who, path, today.get(key)) for key, (at, who, path) in by_page.items()
                      if local_day(at) == day and key not in before), key=lambda x: (x[0], x[2]))
        pages = [{"path": p, "assistant": w, "at": a, "visits": n} for a, w, p, n in new]
        base = {"kind": "first_cited_page", "day": day.isoformat(),
                "history_since": start.isoformat()}
        if len(new) <= cfg["first_max_pages"]:
            for a, w, p, n in new:
                when = datetime.fromisoformat(a).astimezone(tz)
                found.append(_finding(
                    "ai_first_cited_page", p, f"First visit to {p} from an AI citation",
                    f"The first visit ever that landed on {p} from an AI answer: {when:%H:%M} "
                    f"on {_short(day)}, from {w}. Visits to it from citations that day: "
                    f"{_visits(n)}. No earlier visit landed on it from a citation {since}. "
                    f"{FROM_FIRSTS}", n, 0,
                    {**base, "pages": [{"path": p, "assistant": w, "at": a, "visits": n}]}))
        else:
            named = ", ".join(f"{p} ({w})" for _, w, p, _ in new[:LIST])
            more = f", and {len(new) - LIST} more" if len(new) > LIST else ""
            found.append(_finding(
                "ai_first_cited_page", "pages", f"{len(new)} pages had their first AI citation",
                f"On {_short(day)}, {len(new)} pages had their first visit ever from an AI "
                f"answer: {named}{more}. None of them had one before {since}. {FROM_FIRSTS}",
                len(new), 0, {**base, "pages": pages[:LIST]}))
        r2["found"] = len(found) - r1["found"]
    return found, r1, r2


def _cited(cfg: dict, history, site: str, day: date, st: dict) -> tuple:
    """Visits from AI answers against the same weekday's median."""
    rule = _rule(cfg["cited_visits"])
    if not rule["on"]:
        return [], rule
    same = [day - timedelta(weeks=w) for w in range(1, cfg["cited_weeks"] + 1)]
    marks = ",".join("?" * (len(same) + 1))
    recorded = {r[0] for r in history.db.execute(
        f"SELECT day FROM days WHERE site = ? AND breakdowns = 1 AND day IN ({marks})",
        (site, day.isoformat(), *(d.isoformat() for d in same)))}

    def usable(d: date) -> bool:
        return st.get(d) == "ok" and d.isoformat() in recorded
    if not usable(day):
        return [], _wait(rule, [day.isoformat()])
    kept = [d for d in same if usable(d)]
    skipped = [d.isoformat() for d in same if not usable(d)]
    if len(kept) < cfg["cited_min_weeks"]:
        return [], _wait(rule, skipped)
    got = {r[0]: int(r[1]) for r in history.db.execute(
        f"SELECT day, n FROM counts WHERE site = ? AND kind = 'reader_source' AND name = ? "
        f"AND day IN ({marks})", (site, CITED, day.isoformat(), *(d.isoformat() for d in same)))}
    # A recorded day keeps only the sources it had: no row is no visit.
    n = got.get(day.isoformat(), 0)
    weeks = [(d, got.get(d.isoformat(), 0)) for d in kept]
    median = statistics.median(v for _, v in weeks)
    up = cfg["cited_spike_factor"] * median
    down = median * cfg["cited_drop_percent"] / 100
    if n >= cfg["cited_minimum"] and n >= up:
        verdict = "rose"
    elif median >= cfg["cited_minimum"] and n <= down:
        verdict = "fell"
    elif median < cfg["cited_minimum"] and n < cfg["cited_minimum"]:
        verdict = TOO_FEW
    else:
        verdict = "steady"
    rule.update(day_visits=n, median=median, weeks=len(kept), skipped=skipped, verdict=verdict)
    if verdict not in ("rose", "fell"):
        return [], rule
    wd = f"{day:%A}"
    listed = ", ".join(f"{d:%d %b} {v}" for d, v in weeks)
    rule_words = (f"The rule: at least {cfg['cited_spike_factor']} times the usual and at least "
                  f"{cfg['cited_minimum']} visits; or at most {cfg['cited_drop_percent']}% of a "
                  f"usual of at least {cfg['cited_minimum']}.")
    detail = (f"Visits that followed a citation in an AI answer (source \"{CITED}\") on "
              f"{_short(day)}: {n}. Usual for a {wd}: {median:g}, the median of the "
              f"{len(kept)} {wd}s before ({listed})"
              + (f"; not counted, so left out: {', '.join(skipped)}" if skipped else "")
              + f". {rule_words} Visits are people; bot and AI fetcher requests are never in "
                f"this figure. {FROM_SOURCES}")
    data = {"kind": f"cited_{verdict}", "day": day.isoformat(), "visits": n, "median": median,
            "weeks": [{"day": d.isoformat(), "visits": v} for d, v in weeks],
            "skipped": skipped, "spike_factor": cfg["cited_spike_factor"],
            "drop_percent": cfg["cited_drop_percent"], "minimum": cfg["cited_minimum"]}
    title = (f"Visits from AI answers {verdict} to {n} on {day:%a %d %b} "
             f"(usual {median:g})")
    rule["found"] = 1
    return [_finding("ai_cited_visits", verdict, title, detail, n,
                     round(up if verdict == "rose" else down, 1), data)], rule


def _silent(cfg: dict, history, site: str, day: date, st: dict) -> tuple:
    """An AI or search crawler that came often and has stopped."""
    rule = _rule(cfg["crawler_silent"])
    if not rule["on"]:
        return [], rule
    quiet = [day - timedelta(days=i) for i in range(cfg["silent_days"])]
    base = [quiet[-1] - timedelta(days=i) for i in range(1, SILENT_BASE + 1)]
    blobs = history.extras(site, base[-1], day, ("crawler_paths",))
    wanted = quiet + base
    gaps = sorted(d.isoformat() for d in wanted if st.get(d) != "ok" or (
        blobs.get(d.isoformat()) or {}).get("crawler_paths") is None)
    if gaps:
        return [], _wait(rule, gaps)

    def requests(d: date) -> dict:
        out = {}
        for name, got in (blobs[d.isoformat()]["crawler_paths"] or {}).items():
            if (got or {}).get("group") in CRAWLERS and int(got.get("requests") or 0):
                out[name] = (got["group"], int(got["requests"]))
        return out
    seen: dict = {}                     # name -> [group, days, requests, last day]
    for d in sorted(base):
        for name, (group, n) in requests(d).items():
            slot = seen.setdefault(name, [group, 0, 0, d])
            slot[1] += 1
            slot[2] += n
            slot[3] = d
    lately = set()
    for d in quiet:
        lately |= set(requests(d))
    found = []
    for name, (group, k, n, last) in sorted(seen.items()):
        if k < cfg["silent_active_days"] or name in lately:
            continue
        kind = "AI crawler" if group == "answer_engines" else "search crawler"
        found.append(_finding(
            "crawler_silent", name, f"{name} has made no request for {cfg['silent_days']} days",
            f"{name} ({kind}) made {n} requests on {k} of the {SILENT_BASE} days "
            f"{base[-1].isoformat()} to {base[0].isoformat()}, the last on {last.isoformat()}; "
            f"none in the {cfg['silent_days']} whole days {quiet[-1].isoformat()} to "
            f"{day.isoformat()}. Requests, not visits: a crawler is never a person. If it "
            f"should still come, check robots.txt and any firewall or CDN rule. {FROM_PATHS}",
            0, 0, {"kind": "silent", "crawler": name, "group": group, "day": day.isoformat(),
                   "quiet": [quiet[-1].isoformat(), day.isoformat()],
                   "window": [base[-1].isoformat(), base[0].isoformat()], "active_days": k,
                   "requests": n, "last_seen": last.isoformat()}))
    rule["found"] = len(found)
    return found, rule


def evaluate(cfg: dict, history, site: str, day: date, tz) -> dict:
    """Every rule here for the last whole day `day`."""
    first = day - timedelta(days=max(7 * cfg["cited_weeks"], SILENT_BASE + cfg["silent_days"]))
    st = states(history, site, first, day)
    firsts, r1, r2 = _firsts(cfg, history, site, day, tz, st.get(day))
    cited, r3 = _cited(cfg, history, site, day, st)
    silent, r4 = _silent(cfg, history, site, day, st)
    return {"day": day.isoformat(), "found": firsts + cited + silent,
            "rules": {"first_citation": r1, "first_cited_page": r2, "cited_visits": r3,
                      "crawler_silent": r4}}


# ----------------------------------------------------- the live check

def findings(state: dict, config: dict, history, site: str, day: date, now: datetime,
             tz) -> list[dict]:
    """The findings for the last whole day `day`, evaluated once and kept in
    state["history"] (see the module's docstring for when it is redone)."""
    cfg = settings(config)
    key = json.dumps(cfg, sort_keys=True)
    kept = state.get("history") or {}
    waiting = any(r.get("state") == "waiting" for r in (kept.get("rules") or {}).values())
    try:
        age = now - datetime.fromisoformat(kept.get("evaluated_at") or "")
    except ValueError:
        age = None
    fresh = (kept.get("day") == day.isoformat() and kept.get("key") == key
             and not (waiting and (age is None or age >= WAIT_RECHECK)))
    if not fresh:
        kept = evaluate(cfg, history, site, day, tz)
        kept.update(key=key, evaluated_at=now.astimezone(timezone.utc).isoformat(
            timespec="seconds"))
        state["history"] = kept
    return [dict(f) for f in kept.get("found") or []]


def public(state: dict) -> dict | None:
    """The kept evaluation for alerts.json: the day and each rule's state."""
    kept = state.get("history")
    if not kept:
        return None
    return {"day": kept.get("day"), "evaluated_at": kept.get("evaluated_at"),
            "rules": kept.get("rules") or {}}
