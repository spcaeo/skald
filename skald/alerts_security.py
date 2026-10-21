"""Security's alerts, through the same machinery as the others (alerts.py): the
alert state, one mail per alert, the cooldown, the digest, alerts.json, Site >
Alerts and the outgoing webhook event `alert.opened` (Slack's shape for a
hooks.slack.com address).

  security_exposure  a scanner probe answered 2xx with a size unlike the
                     host's shell (security.py, "possible"), today so far (the
                     live snapshot) or on the last whole day: one alert per
                     host and path. On by default: it follows the site's alert
                     settings (alerts.enabled, alerts.mail); its own switch
                     `alerts.security_exposure`
  stack_advisory     an advisory shipped with Skald matches the site's stack (stack.py's
                     last check: update needed, no official fix, check your version); one
                     alert per advisory, host and product. On by default
  scan_wave          scanner probes on the last whole day at least
                     `scan_wave_factor` (3) times the median of the
                     `scan_wave_days` (14) days before that have the figure,
                     and at least `scan_wave_minimum` (200). At least
                     `scan_wave_min_days` (7) such days, else it waits. Off by
                     default (`alerts.scan_wave`)

No new figure is counted here: both read the day kind `security`, recounted by
audit_security.py. A withheld or partial day is never used. The wave's
median and figure are kept in the alert state (`security`) and worked out
again from history by audit_security.recheck (run-daily's recounts).
"""
from __future__ import annotations

import json
import statistics
from datetime import date, timedelta

CAUSES = ("security_exposure", "scan_wave", "stack_advisory")
SEVERITY = {"security_exposure": "high", "scan_wave": "medium", "stack_advisory": "high"}
UNIT = {"security_exposure": "bytes", "scan_wave": "requests", "stack_advisory": None}
RULE = {"security_exposure": "security_exposure", "scan_wave": "scan_wave",
        "stack_advisory": "stack_advisory"}
DEFAULTS = {"security_exposure": True, "scan_wave": False, "stack_advisory": True,
            "scan_wave_factor": 3,
            "scan_wave_days": 14, "scan_wave_min_days": 7, "scan_wave_minimum": 200}
ADVICE = {
    "secrets": "Deny dotfiles and key files at the web server, for example in nginx: "
               "location ~ /\\. { deny all; }  Then rotate any secret the file held.",
    "cloud": "Keep deploy and cloud files out of the web root, or deny them: "
             "location ~* \\.(tf|tfvars|tfstate|ya?ml)$ { deny all; }",
    "dumps": "Move backups and dumps out of the web root; deny "
             "location ~* \\.(sql|bak|zip|tar|gz)$ { deny all; }",
    "wordpress": "If the site is not WordPress, answer these paths with a 404.",
    "php": "If the site runs no PHP, answer *.php with a 404 rather than a page.",
    "admin": "Put admin panels behind a login or an address allow-list.",
}
DEFAULT_ADVICE = "Open the path yourself and check what it returns; deny it at the web server if it is not meant to be public."


def settings(config: dict | None) -> dict:
    section = (config or {}).get("alerts") or {}
    out = {}
    for key, default in DEFAULTS.items():
        value = section.get(key, default)
        if value in (None, "", []):
            value = default
        if isinstance(default, bool):
            out[key] = value if isinstance(value, bool) else \
                str(value).strip().lower() in ("1", "true", "yes", "on")
        else:
            try:
                out[key] = max(1, int(value))
            except (TypeError, ValueError):
                out[key] = default
    out["scan_wave_min_days"] = min(out["scan_wave_min_days"], out["scan_wave_days"])
    return out


def rules(cfg: dict) -> list[dict]:
    words = {
        "security_exposure": "a scanner probe answered 2xx with a size unlike the host's "
                             "fallback page (today, or the last whole day)",
        "stack_advisory": "an advisory shipped with Skald applies to the site's stack (update "
                          "needed, no official fix for the branch, or check your version)",
        "scan_wave": f"scanner probes on the last whole day {cfg['scan_wave_factor']}x the "
                     f"median of the {cfg['scan_wave_days']} days before (at least "
                     f"{cfg['scan_wave_min_days']} of them counted) and "
                     f"{cfg['scan_wave_minimum']}+",
    }
    return [{"cause": c, "on": cfg[RULE[c]], "threshold": words[c], "unit": UNIT[c],
             "group": "security"} for c in CAUSES]


def advice(category: str) -> str:
    return ADVICE.get(category, DEFAULT_ADVICE)


def _finding(cause, subject, title, detail, figure, threshold, data=None) -> dict:
    return {"cause": cause, "subject": subject, "title": title, "detail": detail,
            "figure": figure, "threshold": threshold, "unit": UNIT[cause], "data": data}


def _whole(history, site: str, day: date) -> dict | None:
    """The day's `security` blob when the day is verified and whole, else None."""
    row = history.db.execute("SELECT verified, partial_from, partial_until FROM days "
                             "WHERE site = ? AND day = ?", (site, day.isoformat())).fetchone()
    if row is None or not row[0] or row[1] or row[2]:
        return None
    got = history.db.execute("SELECT data FROM day_extras WHERE site = ? AND day = ? AND "
                             "kind = 'security'", (site, day.isoformat())).fetchone()
    return json.loads(got[0]) if got else None


def exposures(blobs: list[tuple[str, dict | None]]) -> list[dict]:
    out, seen = [], set()
    for when, blob in blobs:
        for r in ((blob or {}).get("exposure") or {}).get("rows") or []:
            if r.get("verdict") != "possible":
                continue
            subject = f"{r['host']}{r['path']}"
            if subject in seen:
                continue
            seen.add(subject)
            shell = r.get("shell_size")
            why = (f"the host's fallback page is {shell:,} bytes" if shell is not None
                   else "the host gave no other probe path the same size, so there is no "
                        "harmless page to set it against")
            out.append(_finding(
                "security_exposure", subject,
                f"Possible exposure: {subject} answered {r['status']} ({r['size']:,} bytes)",
                f"A scanner asked for {r['path']} on {r['host']} at {r['at']} (UTC) ({when}) "
                f"and got a {r['status']} with {r['size']:,} bytes; {why}. The log shows the "
                f"size, never the content: check the path now. {advice(r.get('category'))}",
                r["size"], shell, {"host": r["host"], "path": r["path"], "at": r["at"],
                                   "category": r.get("category")}))
    return out


def wave(cfg: dict, history, site: str, day: date) -> dict:
    """The scan-wave rule for `day`: {state, figure, median, days, found}."""
    blob = _whole(history, site, day)
    if blob is None:
        return {"state": "waiting", "why": f"{day} is not a whole, verified day with the figure",
                "day": day.isoformat()}
    before = []
    for k in range(1, cfg["scan_wave_days"] + 1):
        d = day - timedelta(days=k)
        got = _whole(history, site, d)
        if got is not None:
            before.append((d.isoformat(), int(got["probes"])))
    figure = int(blob["probes"])
    if len(before) < cfg["scan_wave_min_days"]:
        return {"state": "waiting", "day": day.isoformat(), "figure": figure,
                "days": [d for d, _ in before],
                "why": f"{len(before)} of the {cfg['scan_wave_min_days']} days needed"}
    median = statistics.median(n for _, n in before)
    need = max(cfg["scan_wave_factor"] * median, cfg["scan_wave_minimum"])
    return {"state": "ok", "day": day.isoformat(), "figure": figure, "median": median,
            "need": need, "days": [d for d, _ in before], "found": figure >= need}


def advisory_findings(site: str, folder) -> list[dict]:
    """One alert per advisory match that needs something done (stack.py's last check)."""
    from . import security_notify, stack
    got = stack.latest(folder, site) if folder is not None else None
    out = []
    for it in security_notify.items({}, site, [], got[1].get("read") if got else None):
        out.append(_finding("stack_advisory", it["item"], it["title"], it["todo"], None, None,
                            {"item": it["item"]}))
    return out


def findings(state: dict, config: dict, snap: dict | None, history, site: str,
             day: date, folder=None) -> list[dict]:
    """Every security alert that holds now; `day` is the last whole day."""
    cfg = settings(config)
    found = []
    if cfg["stack_advisory"]:
        found += advisory_findings(site, folder)
    if cfg["security_exposure"]:
        blobs = []
        if snap and snap.get("state") == "ok":
            blobs.append(("today", (snap.get("extras") or {}).get("security")))
        blobs.append((day.isoformat(), _whole(history, site, day)))
        found += exposures(blobs)
    if cfg["scan_wave"]:
        got = wave(cfg, history, site, day)
        state["security"] = {"wave": got, "settings": {k: cfg[k] for k in DEFAULTS}}
        if got.get("found"):
            found.append(_finding(
                "scan_wave", got["day"],
                f"Scan wave: {got['figure']:,} scanner probes on {got['day']}",
                f"Usual: {got['median']:g} a day (median of {len(got['days'])} days before). "
                "Security > Who is scanning us lists the addresses; Block list exports them.",
                got["figure"], got["need"]))
    else:
        state.pop("security", None)
    return found
