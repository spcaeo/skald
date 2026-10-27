"""Marketing alerts (2.43): a tool stopped answering, leads or bookings dropped, and
Google Analytics far from the log. Through the same machinery as every other alert
(alerts.py): the alert state, one mail per alert, the cooldown, the daily digest,
alerts.json, Settings > This site > Alerts and the webhook event `alert.opened`.

  tool_stopped    one of the site's own tools (yourtools/, "From your tools") has
                  given no good answer for conn.STALE_HOURS (26), or never: its
                  state "stopped" (conn.status). One alert per tool. On by default
  leads_drop      the site's leads (the dashboard's Leads, conversions_leads.
                  period_leads, recounted by audit_client_reports.check_leads: the
                  figure the mails use, mail_html._leads) over the last 7 whole days
                  fell under `leads_drop_percent` (50) % of the 7 before, when those
                  were at least `leads_drop_minimum` (5). On by default
  bookings_drop   Calendly's own "Booked, last 7 days" under `bookings_drop_percent`
                  (50) % of its "Booked, 7 days before", when those were at least
                  `bookings_drop_minimum` (5): Calendly's figures (tool_calendly.py),
                  only while the tool's recheck matches. On by default
  ga4_log_gap     Google Analytics' sessions over its own 28 days against Skald's
                  visits (all browser sessions from the log) over the same dates,
                  as a ratio, at least `ga4_gap_factor` (2) either way. They count in
                  different ways (a script in the browser, with consent, against the
                  server's log), so the alert says "different", never "wrong". Only
                  whole, verified days of the log; off by default

No new figure is counted here: each rule reads a figure already checked twice
(the leads' recount, yourtools/recount.py's recheck of the tool's stored answer, the log's
audit). A figure that is not there (leads not recorded, a tool withheld or not
connected, a day of the log withheld) makes its rule stay silent.

tool_stopped is read on every live run (it reads two small files); the three others
once per last whole day and when the settings change (`state["marketing"]`). Each
rule's subject is fixed (the tool, "leads", "calendly", "ga4"), so an alert stays
open while its condition holds and is mailed once, not once a day. Each
rule's switch: settings_store key alerts.<rule> (Settings > This site > Alerts).
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

CAUSES = ("tool_stopped", "leads_drop", "bookings_drop", "ga4_log_gap")
SEVERITY = {"tool_stopped": "medium", "leads_drop": "medium", "bookings_drop": "medium",
            "ga4_log_gap": "low"}
UNIT = {"tool_stopped": "hours", "leads_drop": "leads", "bookings_drop": "bookings",
        "ga4_log_gap": None}
RULE = {c: c for c in CAUSES}
DEFAULTS = {"tool_stopped": True, "leads_drop": True, "leads_drop_percent": 50,
            "leads_drop_minimum": 5, "bookings_drop": True, "bookings_drop_percent": 50,
            "bookings_drop_minimum": 5, "ga4_log_gap": False, "ga4_gap_factor": 2}
WEEK = 7


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
                out[key] = max(1, int(value))
            except (TypeError, ValueError):
                out[key] = default
    out["leads_drop_percent"] = min(out["leads_drop_percent"], 99)
    out["bookings_drop_percent"] = min(out["bookings_drop_percent"], 99)
    out["ga4_gap_factor"] = max(out["ga4_gap_factor"], 2)
    return out


def rules(cfg: dict) -> list[dict]:
    words = {
        "tool_stopped": "one of your tools (From your tools) gave no good answer for 26 hours",
        "leads_drop": f"leads over the last 7 whole days under {cfg['leads_drop_percent']}% of "
                      f"the 7 before (when those were {cfg['leads_drop_minimum']}+)",
        "bookings_drop": f"Calendly's bookings made in the last 7 days under "
                         f"{cfg['bookings_drop_percent']}% of the 7 before (when those were "
                         f"{cfg['bookings_drop_minimum']}+)",
        "ga4_log_gap": f"Google Analytics' sessions and the log's visits over the same 28 days "
                       f"{cfg['ga4_gap_factor']} to 1 or more apart, either way (different "
                       f"counting, not an error)",
    }
    return [{"cause": c, "on": cfg[RULE[c]], "threshold": words[c], "unit": UNIT[c],
             "group": "marketing"} for c in CAUSES]


def _finding(cause, subject, title, detail, figure=None, threshold=None) -> dict:
    return {"cause": cause, "subject": subject, "title": title, "detail": detail,
            "figure": figure, "threshold": threshold, "unit": UNIT[cause]}


# ------------------------------------------------------------ the rules

def stopped(config: dict, folder, site: str, now: datetime) -> list[dict]:
    """tool_stopped: each tool whose state is "stopped"."""
    from .yourtools import adapters, conn, keys
    out = []
    parts = conn.load(folder, site)
    for tool, adapter in adapters().items():
        part = parts.get(tool) or {}
        if not part.get("on"):
            continue
        key = keys.state(config, folder, site, tool, part.get("options"))
        st = conn.status(part, bool(key.get("set")), now)
        if st["state"] != "stopped":
            continue
        last = conn.parse(part.get("last_ok"))
        hours = int((now - last).total_seconds() // 3600) if last else None
        since = f"since {last:%Y-%m-%d %H:%M} UTC ({hours} hours)" if last else "ever"
        out.append(_finding(
            "tool_stopped", tool, f"{adapter.name} stopped answering",
            f"Skald has had no good answer from {adapter.name} {since}. Its figures on "
            f"Overview are the last good ones, with their age; Skald's own counts are not "
            f"touched. The last try said: {part.get('error') or 'nothing'}. Status and the "
            f"fix: Settings > Leads & tools > {adapter.name}.", hours, conn.STALE_HOURS))
    return out


def _drop(now_n, before_n, percent: int, least: int) -> bool:
    return (now_n is not None and before_n is not None and before_n >= least
            and now_n * 100 < before_n * percent)


def leads(cfg: dict, config: dict, history, site: str, tz, day: date) -> list[dict]:
    """leads_drop over the 7 whole days ending `day` against the 7 before."""
    from .mail_html import _leads
    first = day - timedelta(days=WEEK - 1)
    now_n = _leads(config, history, site, tz, first, day)
    before_n = _leads(config, history, site, tz, first - timedelta(days=WEEK),
                      first - timedelta(days=1))
    if not _drop(now_n, before_n, cfg["leads_drop_percent"], cfg["leads_drop_minimum"]):
        return []
    fall = round(100 * (before_n - now_n) / before_n)
    return [_finding(
        "leads_drop", "leads", f"Leads down {fall}%: {now_n} in 7 days",
        f"{now_n} lead{'' if now_n == 1 else 's'} from {first:%d %b} to {day:%d %b} against "
        f"{before_n} the 7 days "
        f"before (whole days, the site's time zone; the dashboard's Leads, counted twice). "
        f"Leads & sales shows which sources and pages fell.", now_n,
        round(before_n * cfg["leads_drop_percent"] / 100, 1))]


def _tool_figures(config: dict, folder, site: str, tool: str, now) -> dict | None:
    """{report: {figures by (name, dim), start, end, note}} of a tool whose recheck
    matched and that answered within the stale hours; None otherwise."""
    from .yourtools import api
    got = api.view(config, folder, site, admin=False, now=now)
    t = next((x for x in got["tools"] if x["id"] == tool), None)
    if t is None or t["state"] not in ("answering", "failing"):
        return None
    return {r: {"figs": {(f["name"], f["dim"]): f["value"] for f in rep["figures"]},
                "start": rep["start"], "end": rep["end"], "note": rep["note"]}
            for r, rep in t["reports"].items()}


def bookings(cfg: dict, config: dict, folder, site: str, now) -> list[dict]:
    got = _tool_figures(config, folder, site, "calendly", now)
    figs = ((got or {}).get("totals") or {}).get("figs") or {}
    now_n, before_n = figs.get(("booked_7d", None)), figs.get(("booked_prev_7d", None))
    if not _drop(now_n, before_n, cfg["bookings_drop_percent"], cfg["bookings_drop_minimum"]):
        return []
    fall = round(100 * (before_n - now_n) / before_n)
    return [_finding(
        "bookings_drop", "calendly", f"Calendly bookings down {fall}%: {now_n} in 7 days",
        f"Counted from: Calendly. {now_n} bookings made in the last 7 days (UTC) against "
        f"{before_n} the 7 days before, for meetings from 90 days back to 60 ahead. "
        f"Calendly's own figures, apart from Skald's leads.", now_n,
        round(before_n * cfg["bookings_drop_percent"] / 100, 1))]


def ga4_gap(cfg: dict, config: dict, folder, history, site: str, now) -> list[dict]:
    from .classify import Group
    got = _tool_figures(config, folder, site, "ga4", now)
    rep = (got or {}).get("totals") or {}
    sessions = (rep.get("figs") or {}).get(("sessions", None))
    if not sessions or not rep.get("start") or not rep.get("end"):
        return []
    first, last = date.fromisoformat(rep["start"]), date.fromisoformat(rep["end"])
    period = history.period(site, first, last)
    if not period.complete or period.unmeasured_visits:      # whole, verified days only
        return []
    people = period.totals.groups.get(Group.PEOPLE)
    visits = people.visits if people else 0
    if not visits:
        return []
    ratio = sessions / visits
    if 1 / cfg["ga4_gap_factor"] < ratio < cfg["ga4_gap_factor"]:
        return []
    shown = f"{ratio:.1f} to 1" if ratio >= 1 else f"1 to {1 / ratio:.1f}"
    more = "more" if ratio >= 1 else "fewer"
    return [_finding(
        "ga4_log_gap", "ga4", f"Google Analytics and the log differ: {shown}",
        f"Google Analytics counted {sessions:,} sessions from {first:%d %b} to {last:%d %b} "
        f"({rep.get('note') or 'its own days'}); Skald counted {visits:,} "
        f"visits (all browser sessions) in the server log over the same dates (the site's "
        f"time zone): {more} in Google Analytics. They count in different ways, so neither "
        f"is wrong: Google Analytics counts only browsers that ran its script and agreed to "
        f"it, and splits sessions its own way; the log sees every browser that asked for a "
        f"page. A gap this large often means the tag is missing on some pages, a consent "
        f"banner, or a host the log does not cover.", round(ratio, 2),
        f"{cfg['ga4_gap_factor']} to 1 either way")]


def findings(state: dict, config: dict, history, site: str, folder, tz, now: datetime
             ) -> list[dict]:
    """Every marketing alert that holds now. The daily rules are kept in
    `state["marketing"]` and read again only for a new day or new settings."""
    cfg = settings(config)
    now = now.astimezone(timezone.utc)
    found = stopped(config, folder, site, now) if cfg["tool_stopped"] else []
    day = now.astimezone(tz).date() - timedelta(days=1)
    sign = json.dumps(cfg, sort_keys=True)
    mine = state.setdefault("marketing", {})
    if mine.get("day") == day.isoformat() and mine.get("sign") == sign:
        return found + [dict(f) for f in mine.get("found") or []]
    daily: list[dict] = []
    for on, rule in ((cfg["leads_drop"], lambda: leads(cfg, config, history, site, tz, day)),
                     (cfg["bookings_drop"], lambda: bookings(cfg, config, folder, site, now)),
                     (cfg["ga4_log_gap"],
                      lambda: ga4_gap(cfg, config, folder, history, site, now))):
        if on:
            daily += rule()
    mine.update(day=day.isoformat(), sign=sign, found=daily, at=now.isoformat(timespec="seconds"))
    return found + [dict(f) for f in daily]


def run(ctx, state: dict, history, now: datetime) -> list[dict]:
    """findings() for a live run's context; a failure is one line on stderr and
    keeps the last daily findings, so nothing closes and opens again."""
    try:
        return findings(state, ctx.config, history, ctx.site, Path(ctx.db_path).parent,
                        ctx.tz, now)
    except Exception as why:            # noqa: BLE001 - never stops the other alerts
        ctx.err(f"alerts: marketing rules: {type(why).__name__}: {why}")
        return [dict(f) for f in (state.get("marketing") or {}).get("found") or []]
