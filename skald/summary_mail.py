"""The daily summary (2.36): one mail per person a day, at 01:00, with what to look at on
every site they look after.

On 2026-10-25 one person got 44 security mails in a minute: the first run after a fix sent
one mail per item and per site. This is the one mail that replaces them:

  who        on each site, the people security_notify.recipients() picks: confirmed, not
             disabled members of the site's organisation with security alerts on (in the
             summary or right away). accounts.sqlite is one file for the install, so a
             person on several sites gets ONE mail covering all of them
  what       a section per site, only the sites that have something, each part in order:
               Security       the open items (security_items: possible exposures and stack
                              advisories); "New" for one this person was never mailed (in a
                              summary or right away), then the ones still open (a reminder)
               To-dos to fix  the open Insights to-dos (todos.json, todos.py), less the ones
                              marked done or "not now" since it was written (todo_marks.py);
                              "New" for one this person was never mailed, first, with "N new
                              to-dos your AI agent can fix" and each one's link that opens
                              Fix this > My AI agent (fix=1&by=agent, 2.41; the page still reads the older fixby=). Never a line or
                              a code: a code in a mail would be a key in an inbox
               Set-up         doctor's NEEDS ATTENTION lines that read local files only
                              (SETUP): the daily run, days stored, the access log, page
                              assets, Next.js pages, the script tag, hooks, the lead database,
                              crawler checks, the disk. The hook receiver's check asks the
                              helper over HTTP and is left out; an install-wide line (the
                              disk, crawler checks) is said once per mail
             each line: what it is, what to do (one line), the link straight to it; at most
             MOST per part and site, then "and N more: <link>". Plain text, with the same
             HTML the security mail uses (security_notify._mail)
  nothing    a person with nothing open gets no mail
  when       `skald summary-mail` sends it (`--dry-run` prints it; `--after HH:MM` does
             nothing before that time, for an hourly cron line). Docker's scheduler runs it
             at SKALD_SUMMARY_AT (01:00, "off" stops it) in the schedule's zone
  once       summary_sends (user_id, day): claimed before the send and removed when the
             send fails, so the next run retries, while a restart or a second run the same
             day sends nothing. summary_items keeps the items each mail carried; each
             security item it carried is also a security_sends row ("summary")
  logged     "summary.sent" in the audit log of each organisation it covered: to whom, the
             day, how many items and sites, never the content

The pass after every site of a live run or run-daily is here too (after_run): the
conversions' webhook delivery, then the right-away security mail (security_notify.right_away),
then the plans' usage alerts (saas/usage_alerts.py).
Kept in accounts.sqlite, tables made here on first use. Nothing is sent without accounts.
"""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

SENDS = ("CREATE TABLE IF NOT EXISTS summary_sends (user_id INTEGER NOT NULL, day TEXT NOT NULL, "
         "sent_at TEXT NOT NULL, items INTEGER NOT NULL, sites INTEGER NOT NULL, "
         "PRIMARY KEY (user_id, day))")
ITEMS = ("CREATE TABLE IF NOT EXISTS summary_items (user_id INTEGER NOT NULL, day TEXT NOT NULL, "
         "site TEXT NOT NULL, part TEXT NOT NULL, item TEXT NOT NULL)")
MOST = 10                               # lines per part and site, then "and N more"
# The to-do kinds an AI agent can fix (todos.AGENT_KINDS; kept here so the mail does not load todos.py).
AGENT_KINDS = ("lost", "errors", "markdown", "sitemap", "leave")
AT = "01:00"
PARTS = (("security", "Security"), ("todos", "To-dos to fix"), ("setup", "Set-up problems"))
# doctor's checks that read local files only, and the ones the Integrations page shows.
SETUP = ("daily_run", "days", "logs", "assets", "rsc", "script", "hooks", "leads", "crawlers",
         "disk")
ON_PAGE = ("logs", "assets", "rsc", "script", "hooks", "duplicates", "leads")
ONCE = ("disk", "crawlers")             # install-wide: once per mail


def at() -> str:
    """The summary's time of day (SKALD_SUMMARY_AT), or "off"."""
    got = str(os.environ.get("SKALD_SUMMARY_AT") or AT).strip()
    return "off" if got.lower() in ("off", "0", "no", "false") else got


def _ready(db) -> None:
    db.execute(SENDS)
    db.execute(ITEMS)


def _stamp(now: datetime) -> str:
    return now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _base(config: dict) -> str:
    return str(((config or {}).get("dashboard") or {}).get("url") or "").split("#", 1)[0]


# ----------------------------------------------------------------- the parts

def security_part(db, site: str, config: dict) -> list[dict]:
    from . import security_notify as sn
    return [{"item": it["item"], "title": it["title"], "todo": it["todo"],
             "link": sn.link(config, it["kind"], it["item"])} for it in sn.open_items(db, site)]


def todo_part(db, site: str, config: dict, out) -> list[dict]:
    """The open to-dos of todos.json, less the ones marked since it was written."""
    from . import todo_api, todo_marks
    from .refresh_server import data_file
    path = data_file(Path(out) if out else None, site, None, "todos")
    if path is None:
        return []
    try:
        body = json.loads(path.read_text())
    except (OSError, ValueError):
        return []
    marks = todo_marks.current(db, site)
    got = []
    for t in body.get("todos") or []:
        if not isinstance(t, dict) or not t.get("id") or t.get("state", "open") != "open":
            continue
        if (marks.get(t["id"]) or {}).get("state") in ("done", "notnow"):
            continue
        what = f"{t.get('title') or t['id']}. {t.get('proof') or ''}".strip()
        link = todo_api.link(config, t["id"])
        got.append({"item": t["id"], "title": what, "todo": t.get("todo") or "", "link": link,
                    # 2.41: the dialog that makes the line, on the person's press: a code in
                    # a mail would be a key in an inbox, so the mail never holds one.
                    "fix": f"{link}&fix=1&by=agent" if t.get("agent", t.get("kind") in AGENT_KINDS) and link.split("#")[0]
                    else None})
    return got


def _was_listed(db, user_id: int, site: str, part: str, item: str) -> bool:
    """A summary mail carried this item to this person before (summary_items)."""
    row = db.execute("SELECT 1 FROM summary_items WHERE user_id = ? AND site = ? AND part = ? "
                     "AND item = ? LIMIT 1", (int(user_id), site, part, item)).fetchone()
    return row is not None


def setup_part(s: dict, now: datetime) -> list[dict]:
    """doctor's NEEDS ATTENTION lines for one site, from local reads only (no network)."""
    from . import doctor as d
    from .window import zone
    cfg, cmd, now = s["config"], d.command(s.get("config_path")), now.astimezone(timezone.utc)
    folder, live = Path(s["history"]).parent, Path(s["live_dir"])
    runs = {"daily_run": (d.daily_run, live, now, cmd),
            "days": (d.days_stored, cfg, s["history"], s["site"], zone(cfg), now, live, cmd),
            "logs": (d.access_log, cfg, now, cmd), "assets": (d.page_assets, cfg),
            "rsc": (d.next_pages, cfg),
            "script": (d.script_tag, cfg, {}, live, now, s.get("config_path")),
            "hooks": (d.hook_items, cfg, folder, s["site"], now, cmd),
            "leads": (d.lead_database, cfg), "crawlers": (d.crawler_checks, cfg, now, cmd),
            "disk": (d.disk, folder)}
    base = _base(cfg)
    got = []
    for ident in SETUP:
        fn, *args = runs[ident]
        for f in d._safe(ident, ident.replace("_", " ").capitalize(), fn, *args):
            if f["state"] != d.ATTENTION:
                continue
            page = f["id"] in ON_PAGE or f["id"].startswith("hook:")
            got.append({"item": "setup:" + f["id"], "title": f"{f['part']}: {f['says']}",
                        "todo": f["fix"] or f"`{cmd} doctor` says more.",
                        "link": f"{base}#settings/site/leads" if page and base else None,
                        "where": None if page and base else f"on the server: `{cmd} doctor`",
                        "says": f["says"]})
    return got


def more_link(config: dict, part: str) -> str:
    base = _base(config)
    return base + {"security": "#threats/exposed", "todos": "#overview/insights",
                   "setup": "#settings/todo"}[part]


# ------------------------------------------------------------------ the mail

def _was_mailed(db, site: str, item: str, user_id: int) -> bool:
    row = db.execute("SELECT 1 FROM security_sends WHERE site = ? AND item = ? AND user_id = ? "
                     "AND how != 'test' LIMIT 1", (site, item, int(user_id))).fetchone()
    return row is not None


def _line(it: dict, mark: str = "") -> str:
    where = f"Open it: {it['link']}" if it.get("link") else f"Where: {it.get('where')}"
    fix = f"\n  Fix it with your AI agent: {it['fix']}" if it.get("fix") else ""
    return f"- {mark}{it['title']}\n  What to do: {it['todo']}\n  {where}{fix}\n"


def compose(db, person: dict, sites: dict, day: str) -> dict | None:
    """{subject, text, carried: [(site, part, item)], count, sites} or None (nothing open).
    `sites`: {site: {"config", "security", "todos", "setup"}} for every site of the person."""
    blocks, carried, count, said = [], [], 0, set()
    for site in person["sites"]:
        got = sites.get(site)
        if not got:
            continue
        parts = []
        for part, name in PARTS:
            found = list(got.get(part) or [])
            if part == "setup":
                found = [it for it in found if not (it["item"][6:] in ONCE and it["item"] in said)]
                said |= {it["item"] for it in found if it["item"][6:] in ONCE}
            if not found:
                continue
            marks = {}
            if part == "security":
                new = [it for it in found if not _was_mailed(db, site, it["item"], person["user_id"])]
                old = [it for it in found if it not in new]
                found = new + old
                marks = {it["item"]: ("New: " if it in new else "Still open: ") for it in found}
                head = f"{name} ({len(found)}, {len(new)} new)" if new else f"{name} ({len(found)})"
            elif part == "todos":
                # 2.41: the to-dos this person was never mailed first, said as work their AI
                # agent can do; the line itself is made only when they press (never mailed).
                new = [it for it in found if not _was_listed(db, person["user_id"], site, part, it["item"])]
                found = new + [it for it in found if it not in new]
                marks = {it["item"]: ("New: " if it in new else "") for it in found}
                head = f"{name} ({len(found)})"
                agent = [it for it in new if it.get("fix")]
                if agent:
                    head += (f"\n{len(agent)} new to-do{'s' if len(agent) != 1 else ''} your AI agent "
                             "can fix: open one with the link below, choose My AI agent, and paste the "
                             "line into your agent.")
            else:
                head = f"{name} ({len(found)})"
            shown = found[:MOST]
            lines = [_line(it, marks.get(it["item"], "")) for it in shown]
            if len(found) > MOST:
                lines.append(f"- and {len(found) - MOST} more: {more_link(got['config'], part)}\n")
            parts.append(f"{head}\n" + "".join(lines))
            carried += [(site, part, it["item"]) for it in found]
            count += len(found)
        if parts:
            blocks.append(f"== {site} ==\n\n" + "\n".join(parts))
    if not blocks:
        return None
    n, k = count, len(blocks)
    subject = f"{n} thing{'s' if n != 1 else ''} to look at on {k} site{'s' if k != 1 else ''}"
    d = datetime.strptime(day, "%Y-%m-%d")
    text = (f"Your Skald summary for {d.day} {d:%b %Y}: {subject}.\n\n" + "\n".join(blocks) +
            f"\nYou get this once a day ({at()} in the schedule's time zone), only when something "
            "is open, for every site you get security alerts for. Change it on Security > "
            "Alerts, Your security alerts: off, or the security items right away.\n")
    return {"subject": subject, "text": text, "carried": carried, "count": n, "sites": k}


def _mail_config(person: dict, sites: dict, fallback: dict) -> dict:
    """The first of the person's sites whose mail server is set up, else the install's."""
    from .todo_api import mail_state
    for site in person["sites"]:
        cfg = (sites.get(site) or {}).get("config")
        if cfg and mail_state(cfg)["ready"]:
            return cfg
    return fallback


def people(db, names: list[str]) -> dict[int, dict]:
    """{user_id: {user_id, email, sites: [site], orgs: {site: org_id}}} over every site."""
    from . import security_notify as sn
    got: dict[int, dict] = {}
    for site in names:
        for p in sn.recipients(db, site):
            one = got.setdefault(p["user_id"], {"user_id": p["user_id"], "email": p["email"],
                                                "sites": [], "orgs": {}})
            one["sites"].append(site)
            one["orgs"][site] = p["org_id"]
    return got


def run(db, sites: list[dict], now: datetime, day: str, send=None, dry_run: bool = False,
        out=print, setup=None) -> dict:
    """Build and send the day's summaries. `sites`: [{site, config, live_dir, history, out,
    config_path}]; `setup` replaces setup_part (tests). {"sent", "failed", "nothing",
    "already", "items"}."""
    setup = setup or setup_part
    from . import brand
    from . import security_notify as sn
    _ready(db)
    sn._ready(db)
    who = people(db, [s["site"] for s in sites])
    wanted = {site for p in who.values() for site in p["sites"]}
    found = {}
    for s in sites:
        if s["site"] not in wanted:
            continue                    # nobody to tell: nothing read
        found[s["site"]] = {"config": s["config"],
                            "security": security_part(db, s["site"], s["config"]),
                            "todos": todo_part(db, s["site"], s["config"], s.get("out")),
                            "setup": setup(s, now)}
    tally = {"sent": 0, "failed": 0, "nothing": 0, "already": 0, "items": 0}
    for person in sorted(who.values(), key=lambda p: p["email"]):
        if db.execute("SELECT 1 FROM summary_sends WHERE user_id = ? AND day = ?",
                      (person["user_id"], day)).fetchone():
            tally["already"] += 1
            continue
        mail = compose(db, person, found, day)
        if mail is None:
            tally["nothing"] += 1
            continue
        if dry_run:
            out(f"To: {person['email']}\nSubject: {brand.prefix()} {mail['subject']}\n\n"
                f"{mail['text']}\n")
            tally["items"] += mail["count"]
            continue
        try:                            # the claim: a second run the same day stops here
            db.execute("INSERT INTO summary_sends (user_id, day, sent_at, items, sites) VALUES "
                       "(?, ?, ?, ?, ?)", (person["user_id"], day, _stamp(now), mail["count"],
                                           mail["sites"]))
        except sqlite3.IntegrityError:
            tally["already"] += 1
            continue
        cfg = _mail_config(person, found, sites[0]["config"])
        error = sn._mail(cfg, person["email"], mail["subject"], mail["text"], now, send)
        if error is not None:
            db.execute("DELETE FROM summary_sends WHERE user_id = ? AND day = ?",
                       (person["user_id"], day))
            tally["failed"] += 1
            out(f"summary mail: one not sent ({error}); the next run tries again")
            continue
        _record(db, person, mail, day, now)
        tally["sent"] += 1
        tally["items"] += mail["count"]
    _commit(db)
    return tally


def _record(db, person: dict, mail: dict, day: str, now: datetime) -> None:
    from .accounts import auditlog
    uid = person["user_id"]
    per_org: dict = {}
    for site, part, item in mail["carried"]:
        db.execute("INSERT INTO summary_items (user_id, day, site, part, item) VALUES "
                   "(?, ?, ?, ?, ?)", (uid, day, site, part, item))
        if part == "security":
            db.execute("INSERT INTO security_sends (site, item, user_id, how, sent_at) VALUES "
                       "(?, ?, ?, 'summary', ?)", (site, item, uid, _stamp(now)))
        org = person["orgs"].get(site)
        per_org.setdefault(org, [0, set()])
        per_org[org][0] += 1
        per_org[org][1].add(site)
    for org, (n, names) in per_org.items():
        auditlog.record(db, org, "skald", "summary.sent", person["email"],
                        f"{day} {n} items on {len(names)} sites")


def _commit(db) -> None:
    try:
        db.commit()
    except Exception:                    # noqa: BLE001 - an autocommit connection has nothing to commit
        pass


# ---------------------------------------------------------------- the command

def site_list(ctx) -> list[dict]:
    """Every site of the install (ctx.all_configs), or the one --site names."""
    from .cli import _path
    from .config import site_name
    only = getattr(ctx.args, "only_site", None)
    got = []
    for cfg in ctx.all_configs:
        site = site_name(cfg)
        if only and site != only:
            continue
        res = cfg.get("_resolved") or {}
        got.append({"site": site, "config": cfg,
                    "live_dir": Path(res.get("live_dir") or ctx.live_dir),
                    "history": Path(res.get("history_db") or ctx.db_path),
                    "out": _path(cfg, ctx.config_path, "dashboard", "out", None),
                    "config_path": ctx.config_path})
    return got


def cmd_summary_mail(ctx, send=None) -> int:
    from .auth_api import open_db, sessions_mode
    if not sessions_mode(ctx.config):
        ctx.out("summary mail: off on this install (it needs accounts: access.mode sessions)")
        return 0
    local = ctx.now.astimezone(ctx.tz)
    after = getattr(ctx.args, "after", None)
    if after:
        h, m = (int(x) for x in str(after).split(":", 1))
        if (local.hour, local.minute) < (h, m):
            ctx.out(f"summary mail: not before {after} ({local:%H:%M} now in {ctx.tz})")
            return 0
    sites = site_list(ctx)
    if not sites:
        ctx.out("summary mail: no site")
        return 0
    db = open_db(ctx.config, ctx.live_dir)
    if db is None:
        ctx.out("summary mail: no accounts file")
        return 0
    try:
        got = run(db, sites, ctx.now, local.date().isoformat(), send=send,
                  dry_run=bool(getattr(ctx.args, "dry_run", False)), out=ctx.out)
    finally:
        db.close()
    ctx.out(f"summary mail for {local.date().isoformat()}: {got['sent']} sent ({got['items']} "
            f"items), {got['already']} sent before today, {got['nothing']} with nothing open, "
            f"{got['failed']} failed" + (" (dry run: nothing sent)" if ctx.args.dry_run else ""))
    return 1 if got["failed"] else 0


def _time(text: str) -> str:
    import argparse
    import re
    if not re.fullmatch(r"([01]?\d|2[0-3]):[0-5]\d", str(text).strip()):
        raise argparse.ArgumentTypeError(f"{text!r} is not a time of day (HH:MM, 24-hour)")
    return str(text).strip()


def add_command(sub) -> None:
    p = sub.add_parser("summary-mail", help="the daily summary: one mail per person with what "
                       "to look at on every site (security, to-dos, set-up)")
    p.add_argument("--dry-run", action="store_true", help="print the mails instead of sending them")
    p.add_argument("--after", type=_time, metavar="HH:MM",
                   help="do nothing before this time of day (the site's zone): for an hourly "
                        "cron line")
    p.set_defaults(run=cmd_summary_mail)


# ------------------------------------------------- after every site of a run

def after_run(contexts: list, command: str = "live") -> None:
    """live and run-daily: the webhooks each site queued (conversions/jobs.py), then the
    right-away security mail, one per person for every site (security_notify.right_away),
    then the plans' usage alerts (saas/usage_alerts.py; nothing while saas is off)."""
    from . import security_notify
    from .conversions import jobs
    from .saas import usage_alerts
    jobs.deliver(contexts)
    security_notify.right_away(contexts)
    usage_alerts.after_run(contexts, command)
