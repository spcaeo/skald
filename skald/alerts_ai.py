"""AI alerts: an assistant starts or stops reading a page, and AI answers
start or stop sending people (issue #5).

Three rules, run with the other alerts (alerts.py) and through the same
machinery: the alert state, one mail per alert, the cooldown, the daily
digest, alerts.json and the dashboard's Alerts tab.

  ai_started_reading  an assistant fetched a page on the last whole day that
                      it had not fetched in the `started_days` (28) days before
  ai_stopped_reading  an assistant that fetched a page in at least
                      `stopped_weeks` (3) of the 4 weeks before the last 7
                      days has not fetched it in those 7 days
  ai_sending_people   the visits likely sent by an assistant on the last whole
                      day jumped (at least `sending_jump_factor` (3) times its
                      daily average over the 28 days before, and at least
                      `sending_jump_minimum` (10)) or vanished (at most
                      `sending_drop_percent` (10) % of an average of at least
                      `sending_min_average` (5) a day). Below both thresholds
                      it is "too few to judge", never an alert.

No new figure is counted here. The rules read figures each day already
checked twice: `crawler_paths` (each assistant's requests by path; summed by
robots.check, recounted from the raw log by audit_release2) and `ai_likely`
(ai_likely.check, recounted by audit_ai_likely.py). Every alert says so.

Whole days only. The last whole day and every day a rule looks back on must
be "ok" with its figures recorded. A withheld, partial or missing day, a day
from before history began, or a figure not recorded makes that rule wait
(state "waiting", with the days): it never fires on them.

An assistant is its owner (OpenAI, Anthropic, Perplexity, Google, Microsoft,
Apple, Meta, ...): GPTBot, OAI-SearchBot and ChatGPT-User are one reader.
Only the answer-engine group counts (search engines have their own pages).
A page is a path that is not a file or the beacon (parse.ASSET, parse.BEACON);
"started" also needs the day's `pages` figures to list it as fetched by an
assistant (answered 2xx, as a page). crawler_paths keeps each crawler's top
200 paths a day and the rest as one "(all others)" row. A page hidden in
that row may have been fetched, so an assistant with such a row on a day
the rule needs to be empty is not judged ("unjudged").

More than `max_pages` (5) pages for one assistant in one rule: one alert
listing them, not one alert each.

Settings: the config's `alerts` section, each key of DEFAULTS with an `ai_`
prefix (`ai_started_days: 28`; two levels, as the standard-library reader
takes them), or a nested `alerts.ai` mapping (PyYAML). Evaluated once per
last whole day and kept in the alert state (`ai`); evaluated again when the
day or the settings change, or after WAIT_RECHECK while a rule waits.
A newly opened AI alert is also queued as the outgoing webhook event
`ai.reading_changed` (conversions/outgoing.py), never from a replay.
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from html import escape as esc

from .bot_verify import vendor_of
from .parse import ASSET, BEACON

CAUSES = ("ai_started_reading", "ai_stopped_reading", "ai_sending_people")
SEVERITY = {"ai_started_reading": "low", "ai_stopped_reading": "medium",
            "ai_sending_people": "medium"}
RULE = {"ai_started_reading": "started_reading", "ai_stopped_reading": "stopped_reading",
        "ai_sending_people": "sending_people"}
DEFAULTS = {
    "started_reading": True, "started_days": 28,
    "stopped_reading": True, "stopped_weeks": 3,
    "sending_people": True, "sending_jump_factor": 3, "sending_jump_minimum": 10,
    "sending_drop_percent": 10, "sending_min_average": 5,
    "max_pages": 5, "weekly_mail": True,
}
EVENT = "ai.reading_changed"
OTHER = "(all others)"            # robots.OTHER
MANY = "(more than one)"          # classify.AI_LIKELY_MANY: not one assistant
GROUP = "answer_engines"
LIKELY_DAYS = 28
WEEKS = 4
WAIT_RECHECK = timedelta(minutes=30)
TOO_FEW = "too few to judge"
LIST = 10                         # pages named in a grouped alert
PAGE_KEY = 70                     # the `pages` figures keep paths to 70 characters
FROM_PATHS = ("From figures already checked twice: each assistant's requests by page "
              "(crawler_paths), summed and recounted from the raw log by the audit. "
              "Whole days only.")
FROM_LIKELY = ("From figures already checked twice: visits likely sent by an AI assistant "
               "(ai_likely), recounted by the audit. Inferred, never certain. Whole days only.")

# Whose crawler each name is (bot_verify's vendors, and the names it has no
# list for). Anything else is its own owner.
VENDORS = {"openai": "OpenAI", "anthropic": "Anthropic", "perplexity": "Perplexity",
           "google": "Google", "bing": "Microsoft", "apple": "Apple", "meta": "Meta",
           "duckduckgo": "DuckDuckGo", "yandex": "Yandex"}
MORE = {"gemini-user": "Google", "mistralai-user": "Mistral", "bytespider": "ByteDance",
        "amazonbot": "Amazon", "ccbot": "Common Crawl", "cohere-ai": "Cohere",
        "claude-web": "Anthropic", "google-agent": "Google", "googleagent-mariner": "Google",
        "google-gemininotebook": "Google", "google-notebooklm": "Google",
        "google-cloudvertexbot": "Google", "amzn-searchbot": "Amazon", "amzn-user": "Amazon",
        "cohere-training-data-crawler": "Cohere"}


def owner(name: str) -> str:
    return VENDORS.get(vendor_of(name) or "") or MORE.get((name or "").lower()) or name


def is_page(path: str) -> bool:
    return (bool(path) and path.startswith("/") and path != OTHER
            and not ASSET.search(path) and not BEACON.search(path))


def settings(config: dict | None) -> dict:
    section = (config or {}).get("alerts") or {}
    nested = section.get("ai") if isinstance(section.get("ai"), dict) else {}
    out = {}
    for key, default in DEFAULTS.items():
        value = section.get(f"ai_{key}", nested.get(key, default))
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
    out["stopped_weeks"] = min(max(out["stopped_weeks"], 1), WEEKS)
    out["started_days"] = max(out["started_days"], 1)
    out["max_pages"] = max(out["max_pages"], 1)
    return out


def rules(cfg: dict) -> list[dict]:
    """The three rules for alerts.json's `rules`, in words."""
    words = {
        "ai_started_reading": f"an AI assistant fetched a page it had not fetched in the "
                              f"{cfg['started_days']} days before (whole days only)",
        "ai_stopped_reading": f"an AI assistant that fetched a page in {cfg['stopped_weeks']}+ "
                              f"of 4 weeks has not fetched it for 7 days (whole days only)",
        "ai_sending_people": f"visits likely sent by an assistant {cfg['sending_jump_factor']}x "
                             f"its 28-day average ({cfg['sending_jump_minimum']}+), or under "
                             f"{cfg['sending_drop_percent']}% of it (average "
                             f"{cfg['sending_min_average']}+ a day); fewer: too few to judge",
    }
    return [{"cause": c, "on": cfg[RULE[c]], "threshold": words[c], "group": "ai"}
            for c in CAUSES]


# ------------------------------------------------------------- reading

def load(history, site: str, first: date, last: date, kinds) -> dict:
    """{day: {"state", kind: blob or None}} for every day in the range."""
    blobs = history.extras(site, first, last, tuple(kinds))
    out = {}
    for e in history.daily(site, first, last):
        got = blobs.get(e["day"].isoformat()) or {}
        out[e["day"]] = {"state": e["state"], **{k: got.get(k) for k in kinds}}
    return out


def _gaps(days: dict, wanted, kind: str) -> list[str]:
    """The wanted days a rule cannot use: not ok, or the figure not recorded."""
    return sorted(d.isoformat() for d in wanted
                  if (days.get(d) or {}).get("state") != "ok" or days[d].get(kind) is None)


def _owners(blob: dict | None) -> dict:
    """{owner: {"paths": Counter, "hidden": bool, "names": set, "by": {path:
    names}}} of a day's crawler_paths, the answer engines only."""
    out: dict = {}
    for name, got in (blob or {}).items():
        if (got or {}).get("group") != GROUP:
            continue
        slot = out.setdefault(owner(name), {"paths": Counter(), "hidden": False, "names": set(),
                                            "by": {}})
        for path, n in (got.get("paths") or {}).items():
            if not int(n):
                continue
            slot["names"].add(name)
            if path == OTHER:
                slot["hidden"] = True
            else:
                slot["paths"][path] += int(n)
                slot["by"].setdefault(path, set()).add(name)
    return out


def _span(day: date, back: int, ahead: int = 0) -> list[date]:
    return [day - timedelta(days=i) for i in range(ahead, back + 1)]


def _rule(on: bool) -> dict:
    return {"on": on, "state": "off" if not on else "ok", "waiting_on": [], "unjudged": [],
            "found": 0}


def _wait(rule: dict, gaps: list[str]) -> dict:
    rule.update(state="waiting", waiting_on=gaps)
    return rule


def _times(n: int) -> str:
    return "once" if n == 1 else f"{n} times"


def _short(d: date) -> str:
    return f"{d:%a %d %b} ({d.isoformat()})"


def _pages_words(pages: list[tuple]) -> str:
    named = ", ".join(f"{p} ({n})" for p, n in pages[:LIST])
    return named + (f", and {len(pages) - LIST} more" if len(pages) > LIST else "")


def _finding(cause, subject, title, detail, figure, threshold, data) -> dict:
    return {"cause": cause, "subject": subject, "title": title, "detail": detail,
            "figure": figure, "threshold": threshold, "data": data}


# --------------------------------------------------------------- rules

def _started(cfg: dict, days: dict, day: date, pages: set | None) -> tuple[list, dict]:
    rule = _rule(cfg["started_reading"])
    if not rule["on"]:
        return [], rule
    n_days = cfg["started_days"]
    base = _span(day, n_days, 1)
    gaps = _gaps(days, [day, *base], "crawler_paths")
    if gaps or pages is None:
        return [], _wait(rule, gaps or [day.isoformat()])
    before: dict = {}
    for d in base:
        for who, got in _owners(days[d]["crawler_paths"]).items():
            slot = before.setdefault(who, {"paths": set(), "hidden": False})
            slot["paths"] |= set(got["paths"])
            slot["hidden"] = slot["hidden"] or got["hidden"]
    found = []
    for who, got in sorted(_owners(days[day]["crawler_paths"]).items()):
        old = before.get(who) or {"paths": set(), "hidden": False}
        new = sorted(((p, n) for p, n in got["paths"].items()
                      if n and is_page(p) and p[:PAGE_KEY] in pages and p not in old["paths"]),
                     key=lambda pn: (-pn[1], pn[0]))
        if not new:
            continue
        if old["hidden"]:
            rule["unjudged"].append(who)
            continue
        names = ", ".join(sorted({x for p, _ in new for x in got["by"][p]}))
        window = f"{base[-1].isoformat()} to {base[0].isoformat()}"
        data = {"kind": "started", "assistant": who,
                "crawlers": sorted({x for p, _ in new for x in got["by"][p]}),
                "day": day.isoformat(), "window": [base[-1].isoformat(), base[0].isoformat()],
                "pages": [{"path": p, "n": n} for p, n in new[:LIST]]}
        since = (f"no fetch of {'it' if len(new) == 1 else 'them'} by {who} in the {n_days} "
                 f"days before ({window})" + ("" if who in before else
                                              f"; {who} fetched nothing at all in those days"))
        if len(new) <= cfg["max_pages"]:
            for p, n in new:
                found.append(_finding(
                    "ai_started_reading", f"{who}: {p}", f"{who} started reading {p}",
                    f"{', '.join(sorted(got['by'][p]))} fetched {p} {_times(n)} on "
                    f"{_short(day)}; {since}. {FROM_PATHS}",
                    n, 0, {**data, "crawlers": sorted(got["by"][p]),
                           "pages": [{"path": p, "n": n}]}))
        else:
            found.append(_finding(
                "ai_started_reading", f"{who}: pages", f"{who} started reading {len(new)} pages",
                f"{names} fetched {len(new)} pages on {_short(day)} with {since}: "
                f"{_pages_words(new)}. {FROM_PATHS}", len(new), 0, data))
    rule["found"] = len(found)
    return found, rule


def _stopped(cfg: dict, days: dict, day: date) -> tuple[list, dict]:
    rule = _rule(cfg["stopped_reading"])
    if not rule["on"]:
        return [], rule
    recent = _span(day, 6)
    weeks = [_span(day, 7 * w + 6, 7 * w) for w in range(1, WEEKS + 1)]
    gaps = _gaps(days, recent + [d for w in weeks for d in w], "crawler_paths")
    if gaps:
        return [], _wait(rule, gaps)
    seen: dict = {}                     # owner -> {path: [weeks seen, fetches]}
    names: dict = {}
    for week in weeks:
        got_week: dict = {}
        for d in week:
            for who, got in _owners(days[d]["crawler_paths"]).items():
                for path, by in got["by"].items():
                    names.setdefault((who, path), set()).update(by)
                bucket = got_week.setdefault(who, Counter())
                bucket.update({p: n for p, n in got["paths"].items() if n and is_page(p)})
        for who, paths in got_week.items():
            slot = seen.setdefault(who, {})
            for p, n in paths.items():
                slot.setdefault(p, [0, 0])
                slot[p][0] += 1
                slot[p][1] += n
    now_paths: dict = {}
    for d in recent:
        for who, got in _owners(days[d]["crawler_paths"]).items():
            slot = now_paths.setdefault(who, {"paths": set(), "hidden": False})
            slot["paths"] |= {p for p, n in got["paths"].items() if n}
            slot["hidden"] = slot["hidden"] or got["hidden"]
    first, last = weeks[-1][-1], weeks[0][0]
    found = []
    for who, paths in sorted(seen.items()):
        recent_got = now_paths.get(who) or {"paths": set(), "hidden": False}
        gone = sorted(((p, k, n) for p, (k, n) in paths.items()
                       if k >= cfg["stopped_weeks"] and p not in recent_got["paths"]),
                      key=lambda x: (-x[1], -x[2], x[0]))
        if not gone:
            continue
        if recent_got["hidden"]:
            rule["unjudged"].append(who)
            continue
        crawlers = sorted({x for p, _, _ in gone for x in names.get((who, p), ())})
        quiet = f"none in the 7 days {recent[-1].isoformat()} to {day.isoformat()}"
        data = {"kind": "stopped", "assistant": who, "crawlers": crawlers,
                "day": day.isoformat(), "window": [first.isoformat(), last.isoformat()],
                "pages": [{"path": p, "weeks": k, "n": n} for p, k, n in gone[:LIST]]}
        if len(gone) <= cfg["max_pages"]:
            for p, k, n in gone:
                found.append(_finding(
                    "ai_stopped_reading", f"{who}: {p}", f"{who} stopped reading {p}",
                    f"{', '.join(sorted(names.get((who, p), ())))} fetched {p} in {k} of the "
                    f"4 weeks {first.isoformat()} to {last.isoformat()} ({n} fetches); {quiet}. "
                    f"{FROM_PATHS}", k, cfg["stopped_weeks"],
                    {**data, "crawlers": sorted(names.get((who, p), ())),
                     "pages": [{"path": p, "weeks": k, "n": n}]}))
        else:
            found.append(_finding(
                "ai_stopped_reading", f"{who}: pages", f"{who} stopped reading {len(gone)} pages",
                f"{', '.join(crawlers)} fetched each of these in {cfg['stopped_weeks']}+ of the 4 weeks "
                f"{first.isoformat()} to {last.isoformat()}; {quiet}: "
                f"{_pages_words([(p, n) for p, _, n in gone])}. {FROM_PATHS}",
                len(gone), cfg["stopped_weeks"], data))
    rule["found"] = len(found)
    return found, rule


def _sending(cfg: dict, days: dict, day: date) -> tuple[list, dict]:
    rule = _rule(cfg["sending_people"])
    rule["assistants"] = []
    if not rule["on"]:
        return [], rule
    base = _span(day, LIKELY_DAYS, 1)
    gaps = _gaps(days, [day, *base], "ai_likely")
    if gaps:
        return [], _wait(rule, gaps)
    by_day = {d: (days[d]["ai_likely"].get("by_assistant") or {}) for d in [day, *base]}
    who_all = sorted({a for got in by_day.values() for a in got} - {MANY})
    found = []
    window = f"{base[-1].isoformat()} to {base[0].isoformat()}"
    for who in who_all:
        n = int(by_day[day].get(who, 0))
        avg = sum(int(by_day[d].get(who, 0)) for d in base) / len(base)
        need_up = cfg["sending_jump_factor"] * avg
        need_down = avg * cfg["sending_drop_percent"] / 100
        if n >= cfg["sending_jump_minimum"] and n >= need_up:
            verdict = "jumped"
        elif avg >= cfg["sending_min_average"] and n <= need_down:
            verdict = "vanished"
        elif avg < cfg["sending_min_average"] and n < cfg["sending_jump_minimum"]:
            verdict = TOO_FEW
        else:
            verdict = "steady"
        rule["assistants"].append({"assistant": who, "day": n, "average": round(avg, 1),
                                   "verdict": verdict})
        if verdict not in ("jumped", "vanished"):
            continue
        data = {"kind": f"sending_{verdict}", "assistant": who, "day": day.isoformat(),
                "window": [base[-1].isoformat(), base[0].isoformat()], "visits": n,
                "average": round(avg, 1)}
        if verdict == "jumped":
            found.append(_finding(
                "ai_sending_people", f"{who}: jumped",
                f"{who} likely sent {n} visits on {day:%a %d %b}",
                f"Visits likely sent by {who} on {_short(day)}: {n}. Its daily average over the "
                f"{LIKELY_DAYS} days before ({window}): {avg:.1f}. Jumped: "
                f"{cfg['sending_jump_factor']}x the average and {cfg['sending_jump_minimum']}+. "
                f"{FROM_LIKELY}", n, round(need_up, 1), data))
        else:
            found.append(_finding(
                "ai_sending_people", f"{who}: vanished",
                f"{who} likely sent {n} visits on {day:%a %d %b}, against {avg:.1f} a day",
                f"Visits likely sent by {who} on {_short(day)}: {n}. Its daily average over the "
                f"{LIKELY_DAYS} days before ({window}): {avg:.1f}. Vanished: at most "
                f"{cfg['sending_drop_percent']}% of the average. {FROM_LIKELY}",
                n, round(need_down, 1), data))
    rule["found"] = len(found)
    return found, rule


def _page_set(blob: dict | None) -> set | None:
    if blob is None:
        return None
    return {p for p, v in blob.items()
            if int((v or {}).get("ai_asked", 0)) + int((v or {}).get("ai_training", 0)) > 0}


def _first_needed(cfg: dict, day: date) -> date:
    return day - timedelta(days=max(cfg["started_days"], 7 * WEEKS + 6, LIKELY_DAYS))


def judge(cfg: dict, days: dict, day: date, pages: set | None) -> dict:
    """The three rules for one last whole day, from loaded days."""
    started, r1 = _started(cfg, days, day, pages)
    stopped, r2 = _stopped(cfg, days, day)
    sending, r3 = _sending(cfg, days, day)
    return {"day": day.isoformat(), "found": started + stopped + sending,
            "rules": {"started_reading": r1, "stopped_reading": r2, "sending_people": r3}}


def evaluate(cfg: dict, history, site: str, day: date) -> dict:
    """Every AI alert condition that holds for the last whole day `day`."""
    on = [k for k in ("started_reading", "stopped_reading", "sending_people") if cfg[k]]
    kinds = (("crawler_paths",) if {"started_reading", "stopped_reading"} & set(on) else ()) \
        + (("ai_likely",) if "sending_people" in on else ())
    days = load(history, site, _first_needed(cfg, day), day, kinds) if kinds else {}
    pages = None
    if cfg["started_reading"]:
        got = history.extras(site, day, day, ("pages",)).get(day.isoformat()) or {}
        pages = _page_set(got.get("pages"))
    return judge(cfg, days, day, pages)


# ----------------------------------------------------- the live check

def findings(state: dict, config: dict, history, site: str, day: date,
             now: datetime) -> list[dict]:
    """The AI findings for the last whole day `day`, evaluated once and kept
    in state["ai"] (see the module's docstring for when it is redone)."""
    cfg = settings(config)
    key = json.dumps(cfg, sort_keys=True)
    kept = state.get("ai") or {}
    waiting = any(r.get("state") == "waiting" for r in (kept.get("rules") or {}).values())
    try:
        age = now - datetime.fromisoformat(kept.get("evaluated_at") or "")
    except ValueError:
        age = None
    fresh = (kept.get("day") == day.isoformat() and kept.get("key") == key
             and not (waiting and (age is None or age >= WAIT_RECHECK)))
    if not fresh:
        kept = evaluate(cfg, history, site, day)
        kept.update(key=key, evaluated_at=now.astimezone(timezone.utc).isoformat(
            timespec="seconds"))
        state["ai"] = kept
    return [dict(f) for f in kept.get("found") or []]


def public(state: dict) -> dict | None:
    """The kept evaluation for alerts.json: the day and each rule's state."""
    kept = state.get("ai")
    if not kept:
        return None
    return {"day": kept.get("day"), "evaluated_at": kept.get("evaluated_at"),
            "rules": kept.get("rules") or {}}


def body(alert: dict, site: str) -> dict:
    """The outgoing webhook's body: assistant, pages, days and numbers only."""
    data = alert.get("data") or {}
    return {"event": EVENT, "site": site, "alert_id": alert.get("id"),
            "cause": alert.get("cause"), "kind": data.get("kind"),
            "assistant": data.get("assistant"), "crawlers": data.get("crawlers") or [],
            "day": data.get("day"), "window": data.get("window"), "pages": data.get("pages") or [],
            "visits": data.get("visits"), "average": data.get("average"),
            "title": alert.get("title"), "detail": alert.get("detail"),
            "figure": alert.get("figure"), "threshold": alert.get("threshold"),
            "opened_at": alert.get("opened_at")}


def notify(ctx, opened: list[dict]) -> int:
    """Queue `ai.reading_changed` for each newly opened AI alert. Count;
    never raises (a webhook is a job beside the run)."""
    mine = [a for a in opened if a.get("cause") in CAUSES]
    if not mine:
        return 0
    try:
        from pathlib import Path

        from .conversions import outgoing
        folder = Path(ctx.db_path).parent
        return sum(outgoing.notify(ctx.config, folder, ctx.site, EVENT, a["id"],
                                   body(a, ctx.site), ctx.now) for a in mine)
    except Exception as why:            # noqa: BLE001
        ctx.err(f"alerts: ai.reading_changed webhook: {type(why).__name__}: {why}")
        return 0


# ------------------------------------------------------- weekly mail

def weekly(config: dict, history, site: str, first: date, last: date) -> tuple[str, str]:
    """The weekly mail's "AI reading changes": (text, html), or ("", "")
    when alerts or alert mail are off, or `alerts.ai.weekly_mail` is."""
    from .alerts import settings as alert_settings
    base, cfg = alert_settings(config), settings(config)
    on = [k for k in ("started_reading", "stopped_reading", "sending_people") if cfg[k]]
    if not (base["enabled"] and base["mail"] and cfg["weekly_mail"] and on):
        return "", ""
    days = load(history, site, _first_needed(cfg, first), last, ("crawler_paths", "ai_likely"))
    pages = history.extras(site, first, last, ("pages",))
    lines, waits = [], set()
    d = first
    while d <= last:
        got = judge(cfg, days, d, _page_set((pages.get(d.isoformat()) or {}).get("pages")))
        for f in got["found"]:
            if f["cause"] == "ai_stopped_reading" and d != last:
                continue                # stopped: as of the week's last day only
            lines.append(f"{f['title']} ({d:%a %d %b})")
        for name, rule in got["rules"].items():
            if rule["state"] == "waiting" and (name != "stopped_reading" or d == last):
                waits.add(name.replace("_", " "))
        d += timedelta(days=1)
    if not lines and not waits:
        lines = ["No assistant started or stopped reading a page; no jump or fall in visits "
                 "likely sent by AI answers (or too few to judge)."]
    note = (("Not judged, waiting for whole days: " + ", ".join(sorted(waits)) + ". "
             if waits else "")
            + "From figures already checked twice: each assistant's requests by page, and "
              "visits likely sent by an AI assistant (inferred, never certain). Whole days only.")
    text = "AI READING CHANGES\n" + "".join(f"  - {x}\n" for x in lines) + f"  {note}\n\n"
    from .mail_html import FONT, INK, _card
    rows = "".join(f'<div class="s-ink" style="font:400 14px/1.5 {FONT};color:{INK};'
                   f'padding:3px 0">{esc(x)}</div>' for x in lines)
    return text, _card("AI reading changes", rows, esc(note))
