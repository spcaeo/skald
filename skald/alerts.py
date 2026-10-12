"""Alerts by email: something is wrong now, not tomorrow morning.

Checked on every live run (every 2 minutes), from what that run already has
in memory - the requests of the last hours by minute (requests_feed.Feed's
signals), today's snapshot and history - so a check costs nothing worth
measuring. Each rule can be switched off in the config's `alerts` section:

  site_down         the heartbeat (our own request every 5 minutes) missed or
                    failed `site_down_misses` (2) beats in a row
  logging_stopped   no log line at all for `logging_stopped_minutes` (15)
  server_errors     `server_errors_count` (10) or more 5xx in
                    `server_errors_minutes` (10)
  not_found_surge   people met `not_found_minimum` (10) or more 404s in the last
                    hour, and `not_found_factor` (3) times their usual hour
                    (the median over the last 14 whole days)
  crawler_burst     one crawler or bot made `crawler_burst_share` (50) % or
                    more of the last `crawler_burst_minutes` (30) minutes, and
                    at least `crawler_burst_minimum` (500) requests
  new_crawler       an assistant, search crawler or AI-looking agent never seen
                    before (3 requests at least)
  traffic_drop      yesterday's readers below `traffic_drop_percent` (50) % of
                    the same weekday's median over the 4 weeks before - only
                    whole days, at least 3 of them, and a median of at least
                    `traffic_drop_min_readers` (20)
  ai_*              an AI assistant started or stopped reading a page, or the
                    visits likely sent by AI answers jumped or vanished: whole
                    days, once per day, settings in `alerts.ai` (alerts_ai.py)

Fatigue rules: an alert is mailed once, when it opens. While it stays open,
and if it reopens within `cooldown_hours` (6) of its last mail, nothing more
is sent: the checks that found it again are counted (`repeats`) and listed in
one daily digest after `digest_hour` (8, local). site_down and
logging_stopped send one "resolved" line when they clear.

Never on staging or partial data: mail goes only when `alerts.mail` is on and
the machine's name is `alerts.only_on_host` (when set); otherwise alerts are
evaluated and shown on the page only. The figure-based rules run only when
today's snapshot reconciled; a replay (`--today`) never mails. A failed mail
is noted on the alert and never fails the live run.
"""
from __future__ import annotations

import json
import re
import socket
import statistics
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from . import alerts_ai
from .files import write_atomic

STATE = "alerts-state.json"
KEEP_DAYS = 30

DEFAULTS = {
    "enabled": False, "mail": True, "only_on_host": "", "cooldown_hours": 6, "digest_hour": 8,
    "site_down": True, "site_down_misses": 2,
    "logging_stopped": True, "logging_stopped_minutes": 15,
    "server_errors": True, "server_errors_count": 10, "server_errors_minutes": 10,
    "not_found_surge": True, "not_found_minimum": 10, "not_found_factor": 3,
    "crawler_burst": True, "crawler_burst_share": 50, "crawler_burst_minimum": 500,
    "crawler_burst_minutes": 30,
    "new_crawler": True, "traffic_drop": True, "traffic_drop_percent": 50,
    "traffic_drop_min_readers": 20, "resolved_mail": True,
}
CAUSES = ("site_down", "logging_stopped", "server_errors", "not_found_surge", "crawler_burst",
          "new_crawler", "traffic_drop")
SEVERITY = {"site_down": "high", "logging_stopped": "high", "server_errors": "high",
            "not_found_surge": "medium", "crawler_burst": "medium", "new_crawler": "low",
            "traffic_drop": "medium", **alerts_ai.SEVERITY}
RESOLVED = ("site_down", "logging_stopped")
AI_LOOKING = re.compile(r"\bai\b|ai[-_ ]?bot|gpt|llm|agent|assistant|-user\b|fetcher|claude"
                        r"|perplexity|gemini|mistral|cohere|anthropic|openai", re.I)


def _flag(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def settings(config: dict) -> dict:
    raw = (config or {}).get("alerts") or {}
    out = {}
    for key, default in DEFAULTS.items():
        value = raw.get(key, default)
        if value in (None, "", []):
            value = default
        if isinstance(default, bool):
            out[key] = _flag(value)
        elif isinstance(default, int):
            try:
                out[key] = int(value)
            except (TypeError, ValueError):
                out[key] = default
        else:
            out[key] = str(value)
    return out


def rules(cfg: dict) -> list[dict]:
    words = {
        "site_down": f"{cfg['site_down_misses']} heartbeats missed or failed in a row",
        "logging_stopped": f"no log line for {cfg['logging_stopped_minutes']} minutes",
        "server_errors": f"{cfg['server_errors_count']}+ server errors (5xx) in "
                         f"{cfg['server_errors_minutes']} minutes",
        "not_found_surge": f"people met {cfg['not_found_minimum']}+ 404s in an hour and "
                           f"{cfg['not_found_factor']}x their usual hour",
        "crawler_burst": f"one crawler {cfg['crawler_burst_share']}%+ of "
                         f"{cfg['crawler_burst_minutes']} minutes and "
                         f"{cfg['crawler_burst_minimum']}+ requests",
        "new_crawler": "an assistant or crawler never seen before (3+ requests)",
        "traffic_drop": f"yesterday's readers under {cfg['traffic_drop_percent']}% of the same "
                        f"weekday's 4-week median (whole days only, median "
                        f"{cfg['traffic_drop_min_readers']}+)",
    }
    return [{"cause": c, "on": cfg[c], "threshold": words[c]} for c in CAUSES]


# ------------------------------------------------------------- findings

def _finding(cause, subject, title, detail, figure=None, threshold=None) -> dict:
    return {"cause": cause, "subject": subject, "title": title, "detail": detail,
            "figure": figure, "threshold": threshold}


def _window(signals: dict, now: datetime, minutes: int):
    first = int(now.timestamp()) // 60 - minutes + 1
    return [c for m, c in signals["minutes"].items() if m >= first]


def check(cfg: dict, signals: dict, snap: dict | None, history, site: str, tz,
          now: datetime, known: set[str], heartbeat_on: bool) -> list[dict]:
    """Every alert condition that holds now."""
    found = []
    now = now.astimezone(timezone.utc)
    beats = signals.get("beats") or []
    if cfg["site_down"] and heartbeat_on:
        misses = cfg["site_down_misses"]
        last_ok = next((w for w, ok in reversed(beats) if ok), None)
        tail = [ok for _, ok in beats[-misses:]]
        quiet = (now - last_ok).total_seconds() / 60 if last_ok else None
        silent = quiet is not None and quiet >= misses * 5 + 1
        failing = len(tail) == misses and not any(tail)
        never = last_ok is None and now - signals["since"] >= timedelta(minutes=misses * 5 + 1)
        if silent or failing or never:
            how = ("its last beats failed" if failing else
                   f"no answered beat for {int(quiet)} minutes" if quiet is not None
                   else "no answered beat in the window")
            found.append(_finding(
                "site_down", "", "The site did not answer its heartbeat",
                f"The 5-minute heartbeat request: {how}. If the log has stopped too, the "
                f"web server itself is down. Check: curl -I the home page; "
                f"systemctl status nginx.", int(quiet) if quiet is not None else None,
                misses * 5))
    newest = signals.get("newest")
    if cfg["logging_stopped"]:
        limit = cfg["logging_stopped_minutes"]
        age = (now - newest).total_seconds() / 60 if newest else None
        if newest is not None and age >= limit:
            found.append(_finding(
                "logging_stopped", "", f"No log line for {int(age)} minutes",
                f"The newest line in the access log is from {newest.astimezone(tz):%H:%M}. "
                f"Either nothing reaches the server or nginx stopped writing its log "
                f"(disk full, log rotation stuck). Check: df -h; ls -l /var/log/nginx.",
                int(age), limit))
    if snap is None or snap.get("state") != "ok":
        return found                    # figures not trusted: absence checks only
    if cfg["server_errors"]:
        got = sum(c.get("5xx", 0) for c in _window(signals, now, cfg["server_errors_minutes"]))
        if got >= cfg["server_errors_count"]:
            found.append(_finding(
                "server_errors", "", f"{got} server errors in {cfg['server_errors_minutes']} minutes",
                "Requests answered 5xx. The Health tab lists the paths; the Recent requests "
                "tab shows each one.", got, cfg["server_errors_count"]))
    if cfg["not_found_surge"]:
        got = sum(c.get("people_404", 0) for c in _window(signals, now, 60))
        usual = _usual_404_hour(history, site, now.astimezone(tz).date())
        need = max(cfg["not_found_minimum"], cfg["not_found_factor"] * usual)
        if got >= need:
            found.append(_finding(
                "not_found_surge", "", f"People met {got} broken pages in the last hour",
                f"Usual: {usual:.1f} an hour (median of the last 14 whole days). A recent "
                f"deploy or a changed link is the likely cause; the Broken links tab "
                f"lists the paths.", got, round(need, 1)))
    if cfg["crawler_burst"]:
        span = _window(signals, now, cfg["crawler_burst_minutes"])
        total = sum(c.get("all", 0) for c in span)
        names: dict[str, int] = {}
        for c in span:
            for k, n in c.items():
                if k.startswith("name:"):
                    names[k[5:]] = names.get(k[5:], 0) + n
        if names and total:
            name, n = max(names.items(), key=lambda kv: kv[1])
            share = n / total * 100
            if n >= cfg["crawler_burst_minimum"] and share >= cfg["crawler_burst_share"]:
                found.append(_finding(
                    "crawler_burst", name, f"{name}: {n:,} requests in "
                    f"{cfg['crawler_burst_minutes']} minutes ({share:.0f}% of all)",
                    "One crawler is most of the traffic right now. Its requests are counted "
                    "in its own group, never as people; check its 404s on the Bots tab.",
                    n, cfg["crawler_burst_minimum"]))
    if cfg["new_crawler"]:
        for name, n in _named(snap, signals).items():
            if name not in known and n >= 3:
                found.append(_finding(
                    "new_crawler", name, f"New crawler or assistant: {name}",
                    f"{n} requests today from an agent never seen before. If it is an AI "
                    f"assistant, add it to the name lists (classify.py) so it is counted "
                    f"in its tier.", n, 3))
    if cfg["traffic_drop"]:
        drop = _traffic_drop(cfg, history, site, now.astimezone(tz).date())
        if drop:
            found.append(drop)
    return found


def _named(snap: dict, signals: dict) -> dict[str, int]:
    """Assistants and search crawlers today, and bots whose name looks like an
    AI agent (from the feed's window), with their requests."""
    out: dict[str, int] = {}
    for tier in (snap.get("ai") or {}).values():
        for name, n in (tier or {}).items():
            out[name] = out.get(name, 0) + int(n)
    for name, n in (snap.get("search") or {}).items():
        out[name] = out.get(name, 0) + int(n)
    others: dict[str, int] = {}
    for c in (signals.get("minutes") or {}).values():
        for k, n in c.items():
            name = k[5:]
            if k.startswith("name:") and AI_LOOKING.search(name) and not name.startswith(
                    ("claims to be", "link preview", "browser-like")):
                others[name] = others.get(name, 0) + n
    for name, n in others.items():
        out.setdefault(name, n)
    return out


def known_names(history, site: str) -> set[str]:
    rows = history.db.execute(
        "SELECT DISTINCT name FROM counts WHERE site = ? AND kind IN "
        "('engine_training', 'engine_asked', 'search_engine', 'bot_agent')", (site,)).fetchall()
    return {r[0] for r in rows}


def _usual_404_hour(history, site: str, today: date) -> float:
    days = [e for e in history.daily(site, today - timedelta(days=14), today - timedelta(days=1))
            if e["state"] == "ok"]
    if not days:
        return 0.0
    got = dict(history.db.execute(
        "SELECT day, n FROM counts WHERE site = ? AND kind = 'status_people' AND name = '404' "
        "AND day BETWEEN ? AND ?", (site, days[0]["day"].isoformat(),
                                    days[-1]["day"].isoformat())).fetchall())
    return statistics.median(int(got.get(e["day"].isoformat(), 0)) for e in days) / 24


def _traffic_drop(cfg: dict, history, site: str, today: date) -> dict | None:
    day = today - timedelta(days=1)
    same = [day - timedelta(weeks=w) for w in range(1, 5)]
    rows = {e["day"]: e for e in history.daily(site, same[-1], day)}
    if (rows.get(day) or {}).get("state") != "ok":
        return None
    base = [rows[d]["groups"][_people()]["readers"] for d in same
            if (rows.get(d) or {}).get("state") == "ok"
            and rows[d]["groups"][_people()]["readers"] is not None]
    readers = rows[day]["groups"][_people()]["readers"]
    if len(base) < 3 or readers is None:
        return None
    median = statistics.median(base)
    if median < cfg["traffic_drop_min_readers"]:
        return None
    if readers * 100 < median * cfg["traffic_drop_percent"]:
        return _finding("traffic_drop", day.isoformat(),
                        f"Readers fell to {readers} on {day:%A %d %b}",
                        f"The same weekday's median over the 4 weeks before: {median:g}. "
                        f"Whole days only. Sources and landing pages on the Overview tab "
                        f"show where the drop came from.", readers,
                        round(median * cfg["traffic_drop_percent"] / 100, 1))
    return None


def _people():
    from .classify import Group
    return Group.PEOPLE


def figures(cfg: dict, signals: dict, now: datetime, local_now: datetime) -> dict:
    """The window totals the rules read, kept so `audit --live` can recount
    them from the raw log: all requests and 5xx (every host) and people's
    404s, each over its rule's minutes up to `at`, and the newest line."""
    def total(key: str, minutes: int) -> int:
        return sum(c.get(key, 0) for c in _window(signals, now, minutes))
    newest = signals.get("newest")
    return {"at": local_now.isoformat(timespec="seconds"),
            "server_errors": {"minutes": cfg["server_errors_minutes"],
                              "n": total("5xx", cfg["server_errors_minutes"])},
            "people_404": {"minutes": 60, "n": total("people_404", 60)},
            "requests": {"minutes": cfg["crawler_burst_minutes"],
                         "n": total("all", cfg["crawler_burst_minutes"])},
            "newest_line": newest.isoformat(timespec="seconds") if newest else None}


# ----------------------------------------------------------------- state

def state_path(directory: Path) -> Path:
    return Path(directory) / STATE


def load_state(directory: Path | None) -> dict:
    if directory is None:
        return {}
    try:
        got = json.loads(state_path(directory).read_text())
    except (OSError, ValueError):
        return {}
    return got if isinstance(got, dict) else {}


def _iso(when: datetime) -> str:
    return when.astimezone(timezone.utc).isoformat(timespec="seconds")


def apply(state: dict, found: list[dict], now: datetime, cfg: dict) -> tuple[list, list]:
    """Open, refresh and close alerts. (to mail now, resolved now)."""
    alerts = state.setdefault("alerts", [])
    by_key = {(a["cause"], a["subject"]): a for a in alerts
              if a["closed_at"] is None}
    recent = {}
    for a in alerts:
        if a["closed_at"] is not None:
            recent.setdefault((a["cause"], a["subject"]), a)
    cooldown = timedelta(hours=cfg["cooldown_hours"])
    to_mail, resolved = [], []
    seen = set()
    for f in found:
        key = (f["cause"], f["subject"])
        seen.add(key)
        alert = by_key.get(key)
        if alert is not None:
            alert.update(last_seen_at=_iso(now), figure=f["figure"], detail=f["detail"],
                         title=f["title"])
            alert["repeats"] += 1
            alert["since_digest"] = alert.get("since_digest", 0) + 1
            continue
        old = recent.get(key)
        mailed_at = old.get("last_mailed_at") if old else None
        if old is not None and mailed_at and now - datetime.fromisoformat(mailed_at) < cooldown:
            old.update(closed_at=None, last_seen_at=_iso(now), figure=f["figure"],
                       detail=f["detail"], title=f["title"])
            old["repeats"] += 1
            old["since_digest"] = old.get("since_digest", 0) + 1
            continue
        alert = {"id": f"{f['cause']}-{now:%Y%m%d%H%M%S}-{len(alerts)}", **f,
                 "severity": SEVERITY[f["cause"]], "opened_at": _iso(now),
                 "last_seen_at": _iso(now), "closed_at": None, "mailed": 0, "repeats": 0,
                 "since_digest": 0, "last_mailed_at": None}
        alerts.append(alert)
        to_mail.append(alert)
    for key, alert in by_key.items():
        if key not in seen:
            alert["closed_at"] = _iso(now)
            if alert["cause"] in RESOLVED and alert["mailed"]:
                resolved.append(alert)
    cutoff = _iso(now - timedelta(days=KEEP_DAYS))
    state["alerts"] = [a for a in alerts if a["closed_at"] is None or a["closed_at"] >= cutoff]
    return to_mail, resolved


def _public(a: dict) -> dict:
    return {k: a.get(k) for k in ("id", "cause", "subject", "severity", "title", "detail",
                                  "figure", "threshold", "opened_at", "last_seen_at",
                                  "closed_at", "mailed", "repeats", "data")}


# ------------------------------------------------------------------ mail

def _send(config: dict, subject: str, text: str, now: datetime) -> str | None:
    """Send one plain mail. The error in words, or None."""
    from html import escape

    from . import mailer
    try:
        cfg = mailer.settings(config)
        msg = mailer._message(cfg, subject, text,
                              "<pre style=\"font:14px/1.5 sans-serif;white-space:pre-wrap\">"
                              + escape(text) + "</pre>", now)
        mailer.send(msg, cfg)
    except Exception as why:            # noqa: BLE001 - never fails the live run
        return f"{type(why).__name__}: {why}"[:200]
    return None


def _body(alert: dict, url: str | None) -> str:
    return (f"{alert['title']}\n\n{alert['detail']}\n\n"
            f"Figure: {alert['figure']}   Threshold: {alert['threshold']}\n"
            f"Opened: {alert['opened_at']} (UTC)\n"
            + (f"\nDashboard: {url}\n" if url else "")
            + "\nYou get one mail per alert. If it stays or comes back within the cooldown, "
              "the repeats go in the daily digest.\n")


def run(ctx, snap: dict | None, signals: dict, send=_send) -> int:
    """The check on a live run: evaluate, update the state, mail. Exit 0."""
    from . import runs  # noqa: F401  (recorded by the caller)
    from .config import ours_rules, setting
    cfg = settings(ctx.config)
    if not cfg["enabled"]:
        return 0
    now = ctx.now.astimezone(timezone.utc)
    state = load_state(ctx.live_dir)
    replay = bool(getattr(ctx.args, "today", None))
    with ctx.history() as history:
        if "known_names" not in state:
            state["known_names"] = sorted(known_names(history, ctx.site)
                                          | set(_named(snap or {}, signals)))
        known = set(state["known_names"])
        label = str(setting(ctx.config, "report", "heartbeat_label", "heartbeat"))
        heartbeat_on = any(r["label"] == label for r in ours_rules(ctx.config))
        found = check(cfg, signals, snap, history, ctx.site, ctx.tz, now, known, heartbeat_on)
        found += _ai(ctx, state, history, now)
    to_mail, resolved = apply(state, found, now, cfg)
    state["figures"] = figures(cfg, signals, now, ctx.now)
    if snap and snap.get("state") == "ok":
        state["known_names"] = sorted(known | set(_named(snap, signals)))
    host_ok = not cfg["only_on_host"] or socket.gethostname() == cfg["only_on_host"]
    mail_on = cfg["mail"] and host_ok and not replay
    url = setting(ctx.config, "dashboard", "url")
    if not replay:                      # webhooks that asked for ai.reading_changed
        alerts_ai.notify(ctx, to_mail)
    if mail_on:
        for alert in to_mail:
            error = send(ctx.config, f"ALERT: {alert['title']}", _body(alert, url), now)
            if error:
                alert["mail_error"] = error
            else:
                alert["mailed"] += 1
                alert["last_mailed_at"] = _iso(now)
        if cfg["resolved_mail"]:
            for alert in resolved:
                send(ctx.config, f"Resolved: {alert['title']}",
                     f"Cleared at {_iso(now)} (UTC), opened {alert['opened_at']}.\n", now)
        _digest(ctx, state, cfg, now, send, url)
    state["checked_at"] = _iso(now)
    state["mail"] = mail_on
    write_atomic(state_path(ctx.live_dir), json.dumps(state, indent=1, sort_keys=True) + "\n")
    for alert in to_mail:
        ctx.out(f"alert: {alert['title']}" + ("" if mail_on else " (not mailed)"))
    return 0


def _ai(ctx, state: dict, history, now: datetime) -> list[dict]:
    """The AI rules for the last whole day (alerts_ai.py). A failure is one
    line on stderr and keeps the last findings, so nothing closes and reopens."""
    day = ctx.now.astimezone(ctx.tz).date() - timedelta(days=1)
    try:
        return alerts_ai.findings(state, ctx.config, history, ctx.site, day, now)
    except Exception as why:            # noqa: BLE001 - never stops the other alerts
        ctx.err(f"alerts: AI rules: {type(why).__name__}: {why}")
        return [dict(f) for f in (state.get("ai") or {}).get("found") or []]


def _digest(ctx, state: dict, cfg: dict, now: datetime, send, url) -> None:
    local = now.astimezone(ctx.tz)
    if local.hour < cfg["digest_hour"] or state.get("digest_sent_on") == local.date().isoformat():
        return
    repeated = [a for a in state.get("alerts", []) if a.get("since_digest")]
    state["digest_sent_on"] = local.date().isoformat()
    if not repeated:
        return
    lines = [f"- {a['title']}: found again {a['since_digest']} times; "
             f"{'still open' if a['closed_at'] is None else 'closed ' + a['closed_at']}"
             for a in repeated]
    error = send(ctx.config, f"Alert digest: {len(repeated)} repeated",
                 "Alerts that came back or stayed open since the last digest (each was "
                 "mailed once when it opened):\n\n" + "\n".join(lines)
                 + (f"\n\nDashboard: {url}\n" if url else "\n"), now)
    if not error:
        for a in repeated:
            a["since_digest"] = 0


# ---------------------------------------------------------- alerts.json

def build(p) -> dict:
    cfg = settings(p.config)
    state = load_state(p.live_dir)
    alerts = state.get("alerts") or []
    open_ = sorted((a for a in alerts if a.get("closed_at") is None),
                   key=lambda a: a["opened_at"], reverse=True)
    closed = sorted((a for a in alerts if a.get("closed_at") is not None),
                    key=lambda a: a["closed_at"], reverse=True)
    return {"enabled": cfg["enabled"], "mail": bool(state.get("mail", False)),
            "checked_at": state.get("checked_at"),
            "rules": rules(cfg) + alerts_ai.rules(alerts_ai.settings(p.config)),
            "open": [_public(a) for a in open_], "closed": [_public(a) for a in closed],
            "ai": alerts_ai.public(state)}


# --------------------------------------------------------------- command

def cmd_alerts(ctx) -> int:
    """Evaluate now from a fresh live pass, print, never mail."""
    from . import requests_feed
    from .config import setting
    from .live import build as live_build
    from .window import day_window
    hours, cap = requests_feed.settings(ctx.config)
    now = ctx.now.astimezone(timezone.utc)
    feed = requests_feed.Feed((now - timedelta(hours=hours)).replace(microsecond=0), cap, ctx.views,
                              str(setting(ctx.config, "report", "heartbeat_label", "heartbeat")))
    requests_feed.before_midnight(ctx.config, feed, day_window(ctx.now.date(), ctx.tz)[0], now)
    snap = live_build(ctx.config, ctx.site, ctx.tz, ctx.now, ctx.views, ctx.db_path, feed)
    cfg = settings(ctx.config)
    with ctx.history() as history:
        state = load_state(ctx.live_dir)
        # Without a stored list, the first live run will take everything
        # seen so far as known; say the same here.
        known = set(state.get("known_names") or
                    (known_names(history, ctx.site) | set(_named(snap, feed.signals()))))
        label = str(setting(ctx.config, "report", "heartbeat_label", "heartbeat"))
        from .config import ours_rules
        found = check(cfg, feed.signals(), snap, history, ctx.site, ctx.tz, now, known,
                      any(r["label"] == label for r in ours_rules(ctx.config)))
        found += _ai(ctx, {}, history, now)
    if getattr(ctx.args, "json", False):
        ctx.out(json.dumps(found, indent=1, default=str))
    else:
        for f in found:
            ctx.out(f"{f['cause']}: {f['title']}")
        if not found:
            ctx.out("no alert conditions hold now")
    return 0


def add_command(sub) -> None:
    p = sub.add_parser("alerts", help="evaluate the alert rules now and print them "
                       "(never mails; the live run mails)")
    p.add_argument("--json", action="store_true")
    p.set_defaults(run=cmd_alerts)
