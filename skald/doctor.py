"""`skald doctor`: is this install working? One line per part, OK or NEEDS
ATTENTION, and the fix in plain words. OFF is a part that is not in use.

    skald doctor [--json] [--send-test]      (Docker: docker exec skald skald doctor)

The parts, in order:

    daily run      runs.json: run-daily ran in the last 26 hours, and did not fail
                   or stop on a day that does not reconcile
    days stored    the last 14 days (from the first day stored): none missing, none
                   withheld; the backfill command when some are
    access log     logs.dir/logs.base there, readable, written in the last day
    page assets    a request for site.asset_prefixes (default /_next/static/) in the
                   log's last lines: without one no browser counts as a person
    Next.js pages  only when the log's last lines hold Next.js payloads (?_rsc=):
                   whether they record the prefetch header (rsc_prefetch=), without
                   which a page opened inside the site is not counted
    web app        dashboard.app on
    hook receiver  the beacon helper answers on its port (127.0.0.1:8766)
    hook <tool>    each hook set up: its secret, its last delivery (roads.py)
    one lead, two tools   an external ref that arrived from two tools counts twice
    script tag     beacon.origins, the helper serving the file, the last event
    lead database  leads.db readable (only when set)
    mail           the mail settings are complete; nothing is sent unless --send-test
    version        a newer release, from updates.json only: never the network
    crawler checks bots.ranges_dir set (else NEEDS ATTENTION: "crawler checks off",
                   or OFF when SKALD_VERIFY_BOTS says off), and its lists fresh
    disk          free space where the history lives

Every check reads only (--send-test sends one mail to the recipients). A
check that fails to run is reported as NEEDS ATTENTION with its error, never
as OK. Exit status: 0 when nothing needs attention, 1 otherwise. --json
prints the same list as JSON, one object per site (Settings > Leads & integrations
shows the integration lines through integration_checks()).
"""
from __future__ import annotations

import json
import os
import re
import shutil
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from .config import setting

OK, ATTENTION, OFF = "OK", "NEEDS ATTENTION", "OFF"
DAYS = 14
LATE_HOURS = 26
TAIL_BYTES = 512 * 1024
FAR_BYTES = 64 * 1024 * 1024    # page assets: how far back past the tail, at most
QUIET_HOURS = 48                 # the script tag: no event for this long
DISK_MIN_BYTES = 1 << 30
DISK_MIN_SHARE = 0.05


def item(ident: str, part: str, state: str, says: str, fix: str | None = None) -> dict:
    return {"id": ident, "part": part, "state": state, "says": says, "fix": fix}


def in_docker() -> bool:
    return Path("/.dockerenv").exists()


def command(config_path=None) -> str:
    """How this install's owner runs a command, for the fixes."""
    if in_docker():
        return "docker exec skald skald"
    if Path("/usr/local/bin/skald").exists():
        return "sudo skald"
    return f"./bin/skald --config {config_path}" if config_path else "./bin/skald"


def _ago(then, now) -> str:
    from .conversions.roads import ago
    return ago(then, now)


def _when(text) -> datetime | None:
    try:
        got = datetime.fromisoformat(str(text).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return got if got.tzinfo else got.replace(tzinfo=timezone.utc)


# ------------------------------------------------------------------ runs

def daily_run(live_dir, now: datetime, cmd: str) -> dict:
    from . import runs
    part = "Daily run"
    got = runs.load(Path(live_dir)).get("run-daily")
    if not got:
        return item("daily_run", part, ATTENTION, "has never run here",
                    f"Run it once: `{cmd} run-daily`. Docker runs it every day by itself; an "
                    "install-script server runs it from /etc/cron.d/skald.")
    times = [t for t in (_when(got.get("last_ok")), _when(got.get("last_fail"))) if t]
    last = max(times) if times else None
    if last is None:
        return item("daily_run", part, ATTENTION, "runs.json has no time for it",
                    f"Run `{cmd} run-daily`.")
    when = _ago(last.isoformat(), now)
    outcome = got.get("last_outcome") or ("ok" if got.get("last_exit") == 0 else "failed")
    if now - last > timedelta(hours=LATE_HOURS):
        return item("daily_run", part, ATTENTION, f"last ran {when}: it did not run today",
                    f"Check the schedule (Docker: `docker logs skald`; a server: "
                    f"/etc/cron.d/skald), then run `{cmd} run-daily`.")
    if outcome == "failed":
        where = f" at '{got['last_step']}'" if got.get("last_step") else ""
        return item("daily_run", part, ATTENTION, f"failed {when}{where}",
                    f"Run `{cmd} run-daily` to see the error (the failure mail has it too).")
    step, reason = got.get("last_step"), got.get("last_reason")
    if outcome == "withheld" and step == "weekly mail" and "partial day" in str(reason or ""):
        # The mailer's reason ends with why a week needs whole days: said once, below.
        said = re.sub(r"(\s+-\s+the logs do not cover the whole day)?;\s*a week needs seven whole "
                      r"days", "", str(reason)).strip()
        return item("daily_run", part, OK,
                    f"ran {when}; the day itself is stored and checked. Only this week's mail "
                    f"is held back, because a day of the week was partial ({said}). It "
                    f"clears by itself next week, when the week has seven whole days")
    if outcome == "withheld" and step:
        return item("daily_run", part, ATTENTION,
                    f"stopped on purpose {when} at '{step}'"
                    + (f": {reason}" if reason else ""),
                    f"`{cmd} run-daily` prints the same; for a day that does not reconcile, "
                    f"`{cmd} audit --day yesterday` shows what differs.")
    if outcome == "withheld":
        return item("daily_run", part, ATTENTION,
                    f"stopped on purpose {when}: a day's figures did not reconcile",
                    f"`{cmd} audit --day yesterday` shows what differs.")
    if outcome == "waiting":
        return item("daily_run", part, OK, f"ran {when}; the site waits for its first log lines")
    return item("daily_run", part, OK, f"ran {when}")


def days_stored(config: dict, history_path, site: str, tz, now: datetime, live_dir,
                cmd: str) -> dict:
    """The last DAYS days, from the first day stored: missing and withheld."""
    from . import runs
    from .store import History
    part = "Days stored"
    fix_all = f"`{cmd} backfill --days {DAYS}` stores the days the logs still hold."
    path = Path(history_path)
    if not path.is_file():
        if (config or {}).get("_dashboard_site"):
            return item("days", part, OK, "none yet: the site waits for its first log lines")
        return item("days", part, ATTENTION, "no day stored yet", fix_all)
    history = History.reader(path)
    try:
        first = history.first_day(site)
        if first is None:
            if (config or {}).get("_dashboard_site"):
                return item("days", part, OK, "none yet: the site waits for its first log lines")
            return item("days", part, ATTENTION, "no day stored yet", fix_all)
        today = now.astimezone(tz).date()
        last = today - timedelta(days=1)
        span = [last - timedelta(days=i) for i in range(DAYS - 1, -1, -1)]
        span = [d for d in span if d >= first]
        states = {d: history.state(site, d) for d in span}
    finally:
        history.close()
    # Yesterday comes with today's daily run: not missing before it ran.
    ran = runs.load(Path(live_dir)).get("run-daily") or {}
    stamps = [t for t in (_when(ran.get("last_ok")), _when(ran.get("last_fail"))) if t]
    midnight = datetime.combine(today, datetime.min.time(), tzinfo=tz)
    later = states.get(last) is None and not (stamps and max(stamps) >= midnight)
    missing = [d for d, s in states.items() if s is None and not (later and d == last)]
    held = [d for d, s in states.items() if s == "withheld"]
    if not missing and not held:
        note = "; yesterday comes with today's daily run" if later else ""
        return item("days", part, OK, f"the last {len(span)} days are stored{note}")
    words = []
    if missing:
        words.append(f"{len(missing)} missing ({_dates(missing)})")
    if held:
        words.append(f"{len(held)} withheld ({_dates(held)})")
    back = (last - min(missing + held)).days + 1
    fix = (f"`{cmd} backfill --days {back}` collects them again from the logs, while the logs "
           "still hold them.")
    if held:
        fix += f" `{cmd} audit --day {held[-1].isoformat()}` says why a day was withheld."
    return item("days", part, ATTENTION, ", ".join(words), fix)


def _dates(days: list[date]) -> str:
    shown = ", ".join(d.isoformat() for d in days[:5])
    return shown + (f" and {len(days) - 5} more" if len(days) > 5 else "")


# ------------------------------------------------------------------ logs

def _log_path(config: dict) -> tuple[Path, Path]:
    logs = (config or {}).get("logs") or {}
    folder = Path(str(logs.get("dir") or "/var/log/nginx"))
    return folder, folder / str(logs.get("base") or "access.log")


def access_log(config: dict, now: datetime, cmd: str) -> dict:
    part = "Access log"
    folder, path = _log_path(config)
    if not folder.is_dir():
        return item("logs", part, ATTENTION, f"the folder {folder} is not there",
                    "Set logs.dir to the folder the web server writes its access log in "
                    "(Docker: mount that folder at /logs).")
    if not path.exists():
        if (config or {}).get("_dashboard_site"):     # 2.29.1: was a wrong logs.base fix
            return item("logs", part, OK, "none yet: the site waits for its first log lines")
        return item("logs", part, ATTENTION, f"{path} is not there",
                    "Set logs.base to the log's file name (access.log by default).")
    try:
        with open(path, "rb") as handle:
            handle.read(1)
    except OSError as why:
        return item("logs", part, ATTENTION, f"{path} cannot be read ({type(why).__name__})",
                    "Let Skald's user read it: it is in the group adm, which reads "
                    "/var/log/nginx on Ubuntu and Debian. Check with `sudo -u skald "
                    f"head -1 {path}`.")
    written = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
    if now - written > timedelta(hours=24):
        return item("logs", part, ATTENTION,
                    f"{path} is readable but was last written {_ago(written.isoformat(), now)}",
                    "Is this the site's live log? Check logs.dir and logs.base, and that the "
                    "web server writes there.")
    return item("logs", part, OK,
                f"{path} is readable, last written {_ago(written.isoformat(), now)}")


def _tail(config: dict) -> bytes:
    """The log's last TAIL_BYTES (the live file, then its first rotation)."""
    folder, path = _log_path(config)
    tail = b""
    for one in (path, folder / f"{path.name}.1"):
        try:
            with open(one, "rb") as handle:
                size = handle.seek(0, os.SEEK_END)
                handle.seek(max(0, size - TAIL_BYTES))
                tail += handle.read()
        except OSError:
            continue
        if len(tail) >= TAIL_BYTES:
            break
    return tail


def _further(config: dict, needles: list[bytes]) -> bytes | None:
    """The first of `needles` anywhere in the live file and its first rotation,
    read in 1 MiB pieces, FAR_BYTES at most; None when none is there. For a
    quiet site whose last lines are all crawlers (docomatic.ai, 2026-10-26: a
    false "no page assets" while people loaded its pages all day)."""
    folder, path = _log_path(config)
    keep, read = max(len(n) for n in needles) - 1, 0
    for one in (path, folder / f"{path.name}.1"):
        try:
            handle = open(one, "rb")
        except OSError:
            continue
        with handle:
            last = b""
            while read < FAR_BYTES:
                piece = handle.read(min(1 << 20, FAR_BYTES - read))
                if not piece:
                    break
                read += len(piece)
                window = last + piece
                for needle in needles:
                    if needle in window:
                        return needle
                last = window[-keep:] if keep else b""
    return None


# Formats that keep no request header, so cannot record Next.js's prefetch one.
NO_HEADERS = ("vercel_json", "netlify_json", "edge_json", "cloudflare_json", "fastly_json",
              "cloudfront_w3c", "akamai_json")
NEXT_LINE = " rsc_prefetch=$http_next_router_prefetch"
NEXT_APACHE = " rsc_prefetch=%{Next-Router-Prefetch}i"


def next_pages(config: dict) -> dict | None:
    """Next.js payloads (?_rsc=) in the log's last lines, and whether their
    lines record the prefetch header (parse.Hit.rsc_prefetch): without it a
    page opened inside the site is not counted (COUNTING-TRAPS.md, trap 10).
    No payload in the tail: no line at all, so a site that is not Next.js
    is never told about it."""
    from .parse import AUTO_ORDER, PARSERS, detect
    part = "Next.js pages"
    lines = [raw for raw in _tail(config).decode("utf-8", "replace").splitlines()
             if "_rsc=" in raw]
    if not lines:
        return None
    first = PARSERS[detect(lines[-200:])]
    hits = []
    for raw in lines:
        hit = first(raw)
        if hit is None:
            hit = next((h for h in (PARSERS[n](raw) for n in AUTO_ORDER) if h is not None), None)
        if hit is not None:
            hits.append(hit)
    if not hits:
        return None
    if any(hit.rsc_prefetch is not None for hit in hits):
        return item("rsc", part, OK, "the log records Next.js's prefetch header: pages "
                                     "opened inside the site are counted")
    if all(hit.fmt in NO_HEADERS for hit in hits):
        return item("rsc", part, OFF, "this log format carries no request header, so it "
                                      "cannot tell a click from a prefetch: pages opened "
                                      "inside the site are not counted")
    return item("rsc", part, ATTENTION,
                "the log has Next.js page requests (?_rsc=) but not the header that tells a "
                "click from a prefetch: pages opened inside the site are not counted",
                f"Append `{NEXT_LINE}` at the end of the site's nginx log_format (Apache "
                f"LogFormat: `{NEXT_APACHE}`), then `sudo nginx -t` and reload nginx. Lines "
                "from then on count.")


def page_assets(config: dict) -> dict:
    """A request for one of the site's asset prefixes in the log's last
    lines: the evidence that a browser drew a page (rendering.py)."""
    from . import rendering
    part = "Page assets"
    if not rendering.required(config):
        return item("assets", part, OFF, "not needed (site.require_rendering: false)")
    prefixes = rendering.asset_prefixes(config)
    tail = _tail(config)
    if not tail:
        return item("assets", part, OFF, "cannot check: the log is empty or not readable")
    seen = [p for p in prefixes if p.encode() in tail] or (
        ["?_rsc="] if b"_rsc=" in tail else [])
    if seen:
        return item("assets", part, OK, f"requests for {seen[0]} seen in the log")
    far = _further(config, [p.encode() for p in prefixes] + [b"_rsc="]) if prefixes else None
    if far:
        shown = "?_rsc=" if far == b"_rsc=" else far.decode()
        return item("assets", part, OK, f"requests for {shown} seen in the log "
                                        "(not in its last lines: a quiet spell)")
    return item("assets", part, ATTENTION,
                f"no request for {', '.join(prefixes) or 'the asset prefixes'} in the log's "
                "last lines: a visit counts as people only when its browser fetched one",
                "Set site.asset_prefixes to where your pages load their scripts and styles "
                "(WordPress: /wp-content/ and /wp-includes/; many sites: /assets/ or "
                "/static/): Settings > Collect data > What counts, or `settings set <site> "
                "site.asset_prefixes '[\"/wp-content/\"]'`; for the first site also "
                "config.yml (Docker: SKALD_ASSET_PREFIXES). Turn the rule off "
                "(site.require_rendering false) when they come from a CDN this log never sees.")


# ------------------------------------------------------------- the parts

def web_app(config: dict) -> dict:
    on = ((config or {}).get("dashboard") or {}).get("app", True) not in (
        False, "false", "no", "off", 0)
    if on:
        return item("app", "Web app", OK, "on")
    return item("app", "Web app", ATTENTION, "off: the dashboard is a plain page with no menu",
                "Remove `app: false` from the dashboard section of the config.")


def receiver(config: dict, state: dict) -> dict:
    from .conversions.roads import HELPER_URL
    url = str(setting(config, "hooks", "test_url") or HELPER_URL).rstrip("/")
    if state.get("up"):
        return item("receiver", "Hook receiver", OK, f"the beacon helper answers on {url}")
    fix = ("It runs inside the container: `docker logs skald` shows why it stopped."
           if in_docker() else "`sudo systemctl status skald-beacon`; start it with "
                               "`sudo systemctl enable --now skald-beacon`.")
    return item("receiver", "Hook receiver", ATTENTION,
                f"the beacon helper does not answer on {url} ({state.get('error')}): "
                "hooks and the script tag get no answer", fix)


def base_url(config: dict) -> str:
    """Where the tools reach this install: hooks.public_url, else access.base_url."""
    for got in (setting(config, "hooks", "public_url"), setting(config, "access", "base_url")):
        if got:
            return str(got).rstrip("/")
    return ""


def hook_items(site_config: dict, folder, site: str, now: datetime, cmd: str) -> list[dict]:
    from .conversions import event_types, roads, store
    base = base_url(site_config) or "https://<your site>"
    path = store.path_for(site_config, Path(folder))
    db = store.connect(path) if path is not None and Path(path).exists() else None
    try:
        states = roads.hook_states(site_config, folder, site, db, now, cmd, base)
        twice = roads.duplicates(db, site)
    finally:
        if db is not None:
            db.close()
    out = []
    for s in states:
        if s["state"] == "needs_secret":
            continue
        words = s["words"]
        listed = event_types.wanted(site_config, site, s["tool"], folder)
        if listed:
            words += f"; keeps {len(listed)} event type{'s' if len(listed) != 1 else ''} only"
        out.append(item(f"hook:{s['tool']}", f"Hook {s['name']}",
                        ATTENTION if s["attention"] else OK, words, s["fix"]))
    if not out:
        out.append(item("hooks", "Hooks", OFF, "no hook set up",
                        f"To add one: `{cmd} hooks secret {site} <tool>` (or Settings > "
                        "Leads & integrations), then give its address and secret to the tool."))
    if twice:
        shown = "; ".join(f"{d['ref']} ({' and '.join(d['tools'])})" for d in twice[:3])
        out.append(item("duplicates", "One lead, two tools", ATTENTION,
                        f"{len(twice)}{'+' if len(twice) >= 20 else ''} external ref"
                        f"{'s' if len(twice) != 1 else ''} arrived from two tools and count "
                        f"once per tool: {shown}",
                        "Send each lead through one road only (for example the lead "
                        "database or the lead hook, not both)."))
    return out


def script_tag(config: dict, state: dict, live_dir, now: datetime, config_path=None) -> dict:
    from .beacon import spool_dir
    part = "Script tag"
    origins = setting(config, "beacon", "origins") or []
    origins = [origins] if isinstance(origins, str) else list(origins)
    if not origins and state.get("script") is not True:
        return item("script", part, OFF, "not set up (no beacon.origins); hooks work without it",
                    "To add it: set beacon.origins (Docker: SKALD_BEACON_ORIGINS) to the site's "
                    "address, then put the tag from Settings > Collect data > Script tag & goals on every page.")
    shown = ", ".join(origins) or "the helper's --origin"
    if state.get("up") and state.get("script") is False:
        return item("script", part, ATTENTION,
                    f"origins {shown}, but the helper does not serve /traffic-js/skald.js",
                    "Restart the beacon helper after setting beacon.origins.")
    spool = spool_dir(config, config_path, live_dir)
    files = sorted(Path(spool).glob("*.jsonl")) if Path(spool).is_dir() else []
    if not files:
        return item("script", part, ATTENTION, f"origins {shown}; no event has arrived yet",
                    "Put the tag on every page, from one of these origins. nginx must send "
                    "/traffic-beacon and /traffic-js/ to the helper (docs/INTEGRATIONS.md).")
    last = datetime.fromtimestamp(files[-1].stat().st_mtime, timezone.utc)
    when = _ago(last.isoformat(), now)
    if now - last > timedelta(hours=QUIET_HOURS):
        return item("script", part, ATTENTION, f"origins {shown}; the last event came {when}",
                    "Is the tag still on the pages? Open a page and look for a request to "
                    "/traffic-beacon in the browser's network panel.")
    return item("script", part, OK, f"origins {shown}; the last event came {when}")


def lead_database(config: dict) -> dict | None:
    from . import leads
    path = leads.db_path(config)
    if path is None:
        return None
    try:
        db = leads.connect(path)
        try:
            db.execute("SELECT COUNT(*) FROM submissions").fetchone()
        finally:
            db.close()
    except Exception as why:            # noqa: BLE001 - said, never raised
        return item("leads", "Lead database", ATTENTION,
                    f"{path} cannot be read ({type(why).__name__}: {str(why)[:120]})",
                    "Check leads.db and that Skald's user may read the file. Only SQLite "
                    "is read; for Postgres or MySQL use the signed lead hook.")
    return item("leads", "Lead database", OK, f"{path} is readable")


def mail(config: dict, send_test: bool = False) -> dict:
    from . import mailer
    part = "Mail"
    section = (config or {}).get("mail") or {}
    if not section.get("host"):
        return item("mail", part, OFF, "no SMTP server set (mail.host)",
                    "Settings > Mail & reports, or the mail section of the config.")
    try:
        cfg = mailer.settings(config)
    except mailer.Refused as why:
        return item("mail", part, ATTENTION, f"cannot send: {why}",
                    "Settings > Mail & reports, or the mail section of the config.")
    if not send_test:
        return item("mail", part, OK, f"set up: {cfg['host']}:{cfg['port']} to "
                    f"{len(cfg['to'])} recipient{'s' if len(cfg['to']) != 1 else ''} "
                    "(not sent; --send-test sends one)")
    import smtplib
    try:
        now = datetime.now(timezone.utc)
        words = "This is a test mail from the doctor. If you can read it, the mail works."
        msg = mailer._message(cfg, "Test mail from the doctor", words,
                              f"<html><body><p>{words}</p></body></html>", now)
        mailer.send(msg, cfg)
    except (OSError, smtplib.SMTPException) as why:
        return item("mail", part, ATTENTION, f"the test mail did not go: {type(why).__name__}: "
                    f"{str(why)[:160]}", "Check the SMTP server, port, security and login.")
    return item("mail", part, OK, f"a test mail went to {', '.join(cfg['to'])}")


def version(config: dict, folder, now: datetime, cmd: str) -> dict:
    from . import updates
    part = "Version"
    current = updates.current_version() or "unknown"
    if not updates.settings(config)["check"]:
        return item("version", part, OFF, f"{current}; update checks are off (updates.check)")
    state = updates.read(folder)
    found = updates.notice(config, folder, current)
    if found:
        how = "Docker: pull the new image and start it again (docs/UPGRADING.md)" \
            if in_docker() else f"`{cmd} upgrade --dry-run`, then `{cmd} upgrade`"
        return item("version", part, ATTENTION, updates.headline(found), how + ".")
    if not state.get("checked_at"):
        return item("version", part, OK, f"{current}; not asked yet (the daily run asks "
                    "GitHub once a day)")
    return item("version", part, OK, f"{current}, up to date (asked "
                f"{_ago(state['checked_at'], now)})")


def crawler_checks(config: dict, now: datetime, cmd: str) -> dict:
    """Are crawler claims checked against their owners' lists (bot_verify)?"""
    from . import bot_verify
    part = "Crawler checks"
    folder = bot_verify.ranges_dir(config)
    if folder is None:
        what = ("crawler checks off: a fake Googlebot or GPTBot counts as the crawler it "
                "names, and browsers from hosting networks are not flagged")
        if str(os.environ.get("SKALD_VERIFY_BOTS", "")).strip().lower() in \
                ("0", "false", "off", "no"):
            return item("crawlers", part, OFF, what + " (SKALD_VERIFY_BOTS is off)")
        fix = ("Docker: start the container from this release (it sets bots.ranges_dir) "
               "without SKALD_VERIFY_BOTS=off, or add bots.ranges_dir to your mounted "
               "config." if in_docker() else
               "Add `bots: {ranges_dir: <a folder>}` to the config, then run "
               f"`{cmd} verify-bots` (run-daily runs it first from then on).")
        return item("crawlers", part, ATTENTION, what, fix)
    verifier = bot_verify.Verifier(folder, now)
    names = list(bot_verify.LISTS)
    if not verifier.sets:
        return item("crawlers", part, OK, "on; the owners' lists are not fetched yet (the "
                    f"next daily run fetches them, or `{cmd} verify-bots` now)")
    fresh = sum(1 for n in names if n in verifier.fresh)
    if not fresh:
        return item("crawlers", part, ATTENTION,
                    f"on, but every list is older than {bot_verify.MAX_LIST_AGE.days} days: "
                    "no crawler is called fake until they are fetched again",
                    f"Run `{cmd} verify-bots` and read what each list says.")
    says = f"on; {fresh} of {len(names)} owners' lists fresh"
    if verifier.hosting_set is None:
        says += "; hosting networks not fetched"
    return item("crawlers", part, OK, says)


def disk(folder) -> dict:
    try:
        got = shutil.disk_usage(folder)
    except OSError as why:
        return item("disk", "Disk", ATTENTION, f"cannot read: {why}")
    free, share = got.free, got.free / got.total if got.total else 0
    says = f"{free / (1 << 30):.1f} GB free ({share:.0%}) where the history lives"
    if free < DISK_MIN_BYTES or share < DISK_MIN_SHARE:
        return item("disk", "Disk", ATTENTION, says,
                    "Free some space: old backups (backup.daily, backup.weekly) and logs go "
                    "first. Skald stops writing when the disk is full.")
    return item("disk", "Disk", OK, says)


def keep_everything(config: dict, site: str, live_dir) -> dict | None:
    """One line when the site keeps everything (keep_everything.py); none when not."""
    from .keep_everything import Keeper
    why = Keeper(config, live_dir).why(site)
    if why is None:
        return None
    said = {"install": "the install says so (retention.keep_everything)",
            "no plan": "the site's organisation has no plan: the install's own"}.get(why) \
        or f"its plan, {why[5:]}, says so"
    return item("keep", "Keep everything", OK,
                f"on: nothing on this site is deleted or cleared by itself ({said}); "
                f"a person's own deletion request, run by hand, still works")


# ------------------------------------------------------------ all of them

def _safe(ident: str, part: str, fn, *args) -> list[dict]:
    try:
        got = fn(*args)
    except Exception as why:            # noqa: BLE001 - a check that breaks says so
        return [item(ident, part, ATTENTION, f"could not check: {type(why).__name__}: "
                     f"{str(why)[:160]}")]
    if got is None:
        return []
    return got if isinstance(got, list) else [got]


def checks(ctx, send_test: bool = False, helper_state: dict | None = None) -> list[dict]:
    """Every part for one site (a cli.Context)."""
    from .conversions.roads import HELPER_URL, helper
    config, now, cmd = ctx.config, ctx.now.astimezone(timezone.utc), command(ctx.config_path)
    folder = Path(ctx.db_path).parent
    state = helper_state if helper_state is not None else \
        helper(str(setting(config, "hooks", "test_url") or HELPER_URL))
    out = []
    out += _safe("daily_run", "Daily run", daily_run, ctx.live_dir, now, cmd)
    out += _safe("days", "Days stored", days_stored, config, ctx.db_path, ctx.site, ctx.tz,
                 now, ctx.live_dir, cmd)
    out += _safe("logs", "Access log", access_log, config, now, cmd)
    out += _safe("assets", "Page assets", page_assets, config)
    out += _safe("rsc", "Next.js pages", next_pages, config)
    out += _safe("app", "Web app", web_app, config)
    out += _safe("receiver", "Hook receiver", receiver, config, state)
    out += _safe("hooks", "Hooks", hook_items, config, folder, ctx.site, now, cmd)
    out += _safe("script", "Script tag", script_tag, config, state, ctx.live_dir, now,
                 ctx.config_path)
    out += _safe("leads", "Lead database", lead_database, config)
    out += _safe("mail", "Mail", mail, config, send_test)
    out += _safe("version", "Version", version, config, folder, now, cmd)
    out += _safe("crawlers", "Crawler checks", crawler_checks, config, now, cmd)
    out += _safe("disk", "Disk", disk, folder)
    out += _safe("keep", "Keep everything", keep_everything, config, ctx.site, ctx.live_dir)
    return out


def integration_checks(site_config: dict, folder, site: str, live_dir=None,
                       now: datetime | None = None, config_path=None) -> list[dict]:
    """The lines Settings > Leads & integrations shows: the access log and its page
    assets (the first road in, which Overview's first-run checklist also reads),
    the receiver, the script tag, each hook, one lead from two tools, the lead
    database."""
    from .conversions.roads import HELPER_URL, helper
    now = now or datetime.now(timezone.utc)
    cmd = command(config_path)
    state = helper(str(setting(site_config, "hooks", "test_url") or HELPER_URL))
    out = []
    out += _safe("logs", "Access log", access_log, site_config, now, cmd)
    out += _safe("assets", "Page assets", page_assets, site_config)
    out += _safe("rsc", "Next.js pages", next_pages, site_config)
    out += _safe("receiver", "Hook receiver", receiver, site_config, state)
    out += _safe("script", "Script tag", script_tag, site_config, state,
                 live_dir if live_dir is not None else folder, now, config_path)
    out += _safe("hooks", "Hooks", hook_items, site_config, folder, site, now, cmd)
    out += _safe("leads", "Lead database", lead_database, site_config)
    return out


def report(site: str, found: list[dict]) -> dict:
    from . import updates
    return {"site": site, "version": updates.current_version(),
            "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "attention": sum(1 for f in found if f["state"] == ATTENTION), "checks": found}


def lines(site: str, found: list[dict]) -> list[str]:
    from . import updates
    out = [f"doctor for {site} (version {updates.current_version() or 'unknown'})"]
    width = len(ATTENTION)
    for f in found:
        out.append(f"{f['state']:<{width}}  {f['part']}: {f['says']}")
        if f["fix"] and f["state"] != OK:
            out.append(f"{'':<{width}}  fix: {f['fix']}")
    n = sum(1 for f in found if f["state"] == ATTENTION)
    out.append("nothing needs attention" if not n else
               f"{n} part{'s' if n != 1 else ''} need{'' if n != 1 else 's'} attention")
    return out


def cmd_doctor(ctx) -> int:
    found = checks(ctx, send_test=ctx.args.send_test)
    if ctx.args.json:
        ctx.out(json.dumps(report(ctx.site, found), sort_keys=True))
    else:
        for line in lines(ctx.site, found):
            ctx.out(line)
    return 1 if any(f["state"] == ATTENTION for f in found) else 0


def add_command(sub) -> None:
    p = sub.add_parser("doctor", help="is this install working? one line per part, with "
                       "the fix (reads only; --send-test sends one mail)")
    p.add_argument("--json", action="store_true", help="the same list as JSON, one object "
                   "per site")
    p.add_argument("--send-test", dest="send_test", action="store_true",
                   help="also send one test mail to the recipients")
    p.set_defaults(run=cmd_doctor)
