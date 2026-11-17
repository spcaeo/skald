"""The daily summary (2.36): one mail per person a day, at 01:00, with what to look at on
every site they look after.

On 2026-10-25 one person got 44 security mails in a minute: the first run after a fix sent
one mail per item and per site. This is the one mail that replaces them:

  who        on each site, the people security_notify.recipients() picks: confirmed, not
             disabled members of the site's organisation with security alerts on (in the
             summary or right away). accounts.sqlite is one file for the install, so a
             person on several sites gets ONE mail covering all of them
  what       (#68, kept short: Gmail clips a long mail and filters take it for bulk mail)
             four counts, then Act now and an overview, from one digest for both parts:
               Act now        the open security items (security_items: possible exposures
                              and stack advisories that need an update) and doctor's NEEDS
                              ATTENTION lines that read local files only (SETUP: the daily
                              run, days stored, the access log, page assets, Next.js pages,
                              the script tag, hooks, the lead database, crawler checks, the
                              disk; an install-wide one said once per mail). One line each:
                              the site, a short name, "New" (never mailed to this person) or
                              "Still open", one link. Items of one site with the same name
                              are one line, "(N)". No descriptions and no addresses: the
                              link opens them. At most MOST lines per site, then "N more"
               Overview       one row per site: act now, the open Insights to-dos
                              (todos.json, less the ones marked done or "not now" since:
                              todo_marks.py) and notes (advisories that only ask to check a
                              version nobody can see); every figure links to its list
             every figure is counted from the open items; the counts are the sums of the
             overview's columns. Plain text and HTML (summary_html.py)
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
MOST = 10                               # act-now lines per site, then "and N more"
FOLD = 2                                # items of one site with one name: one line, "(N)"
AT = "01:00"
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
    return [{"item": it["item"], "kind": it["kind"], "title": it["title"], "todo": it["todo"],
             "link": sn.link(config, it["kind"], it["item"])} for it in sn.open_items(db, site)]


def todo_part(db, site: str, config: dict, out) -> list[dict]:
    """The open to-dos of todos.json, less the ones marked since it was written. The mail
    counts them (#68); the list itself is one press away, on the dashboard."""
    from . import todo_marks
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
        if (marks.get(t["id"]) or {}).get("state") in ("done", "notnow", "fixed"):
            continue
        got.append({"item": t["id"]})
    return got


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


def more_link(config: dict, part: str, kind: str | None = None) -> str:
    base = _base(config)
    if part == "security" and kind == "advisory":
        return base + "#threats/stack"
    return base + {"security": "#threats/exposed", "todos": "#overview/insights",
                   "setup": "#settings/todo"}[part]


def upto(site: str, out) -> str | None:
    """The last whole day the site's to-dos count (todos.json window.last), or None. The
    mail goes out at 01:00, before that morning's run counts yesterday, so this is usually
    two days before the mail's own day: the mail says so."""
    from .refresh_server import data_file
    path = data_file(Path(out) if out else None, site, None, "todos")
    if path is None:
        return None
    try:
        last = (json.loads(path.read_text()).get("window") or {}).get("last")
    except (OSError, ValueError, AttributeError):
        return None
    return last if isinstance(last, str) and len(last) == 10 else None


# ------------------------------------------------------------------ the mail

def _was_mailed(db, site: str, item: str, user_id: int) -> bool:
    row = db.execute("SELECT 1 FROM security_sends WHERE site = ? AND item = ? AND user_id = ? "
                     "AND how != 'test' LIMIT 1", (site, item, int(user_id))).fetchone()
    return row is not None


def _plural(n: int, word: str, many: str | None = None) -> str:
    return f"{n:,} {word if n == 1 else (many or word + 's')}"


def _check_version(it: dict) -> bool:
    """A stack advisory that only asks to check a version nobody can see (a note, not an act)."""
    from .advisories import WORDS
    return it.get("kind") == "advisory" and str(it.get("title", "")).endswith(
        ": " + WORDS["check_version"])


def _head(part: str, it: dict) -> str:
    """The item's short name, the same for look-alikes: what the mail shows of it."""
    title = str(it.get("title") or it.get("item") or "")
    if part == "setup":
        return f"Set-up: {title.partition(': ')[0]}"
    if it.get("kind") == "exposure":
        return "Possible exposure"
    return f"Stack advisory: {title.rpartition(': ')[2]}"


def fold(entries: list[dict]) -> list[dict]:
    """FOLD or more entries of one site with the same name become one line, "(N)", with one
    link to their list. Every item stays carried and recorded; the order is kept."""
    groups: dict[tuple, list[dict]] = {}
    for e in entries:
        groups.setdefault((e["part"], e.get("kind"), e["head"]), []).append(e)
    out = []
    for same in groups.values():
        e = same[0]
        if len(same) < FOLD:
            out += same
            continue
        marks = {x["mark"] for x in same}
        out.append({**e, "items": [i for x in same for i in x["items"]],
                    "mark": "New" if "New" in marks else e["mark"],
                    "folded": len(same), "link": e["more"] or e["link"]})
    return out


def _entry(db, person: dict, site: str, part: str, it: dict, config: dict) -> dict:
    if part == "security":
        mark = "Still open" if _was_mailed(db, site, it["item"], person["user_id"]) else "New"
    else:
        mark = ""
    base = _base(config)
    return {"site": site, "part": part, "kind": it.get("kind"), "items": [it["item"]],
            "head": _head(part, it), "mark": mark, "link": it.get("link"),
            "where": it.get("where"), "more": more_link(config, part, it.get("kind"))
            if base else None, "folded": 0}


def digest(db, person: dict, sites: dict) -> dict | None:
    """The mail's content, once, for both parts, or None (nothing open):
    {sites: [{site, url, act, act_more, n_act, n_todos, n_notes, links, upto}],
     act, todos, notes, items, carried, upto}. Every figure is counted here from the open
    items, nothing is written in by hand: act = the act-now lines (possible exposures,
    advisories that need an update, set-up problems; one name on one site is one line),
    todos = the open to-dos, notes = advisories that only ask to check a version. The
    totals are the sums of the overview's columns."""
    said, rows, carried = set(), [], []
    for site in person["sites"]:
        got = sites.get(site)
        if not got:
            continue
        cfg = got["config"]
        setup = [it for it in got.get("setup") or []
                 if not (it["item"][6:] in ONCE and it["item"] in said)]
        said |= {it["item"] for it in setup if it["item"][6:] in ONCE}
        security = list(got.get("security") or [])
        todos = list(got.get("todos") or [])
        notes = [it for it in security if _check_version(it)]
        act = [_entry(db, person, site, "security", it, cfg) for it in security
               if not _check_version(it)] + [_entry(db, person, site, "setup", it, cfg)
                                             for it in setup]
        act = fold([e for e in act if e["mark"] == "New"] + [e for e in act if e["mark"] != "New"])
        if not (act or todos or notes):
            continue
        carried += [(site, "security", it["item"]) for it in security]
        carried += [(site, "todos", it["item"]) for it in todos]
        carried += [(site, "setup", it["item"]) for it in setup]
        base = _base(cfg)
        rows.append({"site": site, "url": base or None, "act": act[:MOST],
                     "act_more": (len(act) - MOST, more_link(cfg, "security"))
                     if len(act) > MOST and base else None,
                     "n_act": len(act), "n_todos": len(todos), "n_notes": len(notes),
                     "links": {"act": (act[0]["more"] if act else None),
                               "todos": more_link(cfg, "todos") if base else None,
                               "notes": more_link(cfg, "security", "advisory") if base else None},
                     "upto": got.get("upto")})
    if not rows:
        return None
    ups = [r["upto"] for r in rows if r.get("upto")]
    return {"sites": rows, "act": sum(r["n_act"] for r in rows),
            "todos": sum(r["n_todos"] for r in rows),
            "notes": sum(r["n_notes"] for r in rows), "items": len(carried),
            "carried": carried, "upto": max(ups) if ups else None}


def act_now(d: dict) -> list[dict]:
    """Act now over every site: the new ones first (never mailed to this person), then the
    set-up problems, then the ones still open; the sites' order inside each."""
    rank = {"New": 0, "": 1}
    return sorted((e for r in d["sites"] for e in r["act"]), key=lambda e: rank.get(e["mark"], 2))


def subject_of(d: dict) -> str:
    parts = []
    if d["act"]:
        parts.append(f"{d['act']:,} to act on")
    if d["todos"]:
        parts.append(_plural(d["todos"], "to-do"))
    if not parts:
        parts.append(_plural(d["notes"], "note"))
    k = len(d["sites"])
    return f"{', '.join(parts)} on {_plural(k, 'site')}"


def _day(text: str | None, weekday: bool = True) -> str:
    if not text:
        return ""
    d = datetime.strptime(text, "%Y-%m-%d")
    return (f"{d:%a} " if weekday else "") + f"{d.day} {d:%b %Y}"


def counts_line(d: dict) -> str:
    bits = [f"{d['act']:,} to act on now", _plural(d["todos"], "to-do"),
            _plural(d["notes"], "note"), _plural(len(d["sites"]), "site")]
    return " · ".join(bits)


def footer_words() -> str:
    return (f"Sent each day at {at()} while something is open. "
            "To stop it: Security > Alerts in Skald.")


def _text_entry(e: dict) -> str:
    mark = f"[{e['mark']}] " if e["mark"] else ""
    many = f" ({e['folded']:,})" if e["folded"] else ""
    end = e.get("link") or (f"({e['where']})" if e.get("where") else "")
    return f"- {mark}{e['site']} · {e['head']}{many}" + (f"\n  {end}" if end else "")


def as_text(d: dict, day: str) -> str:
    """The plain-text part, from the same digest as the HTML part."""
    out = [f"Skald daily summary · {_day(day)}"]
    if d["upto"]:
        out.append(f"Figures up to {_day(d['upto'])}, the last whole day counted.")
    out += ["", counts_line(d), ""]
    act = act_now(d)
    if act:
        out += [f"ACT NOW ({d['act']:,})"] + [_text_entry(e) for e in act]
        out += [f"- and {r['act_more'][0]:,} more on {r['site']}: {r['act_more'][1]}"
                for r in d["sites"] if r["act_more"]]
        out.append("")
    out.append("OVERVIEW")
    width = max(len(r["site"]) for r in d["sites"])
    out.append(f"  {'Site':<{width}}  Act now  To-dos  Notes")
    for r in d["sites"]:
        cells = [r["n_act"], r["n_todos"], r["n_notes"]]
        out.append((f"  {r['site']:<{width}}  " + "  ".join(
            f"{(f'{c:,}' if c else '-'):>{w}}" for c, w in zip(cells, (7, 6, 5)))
            + (f"  {r['url']}" if r["url"] else "")).rstrip())
    out += ["", footer_words()]
    return "\n".join(out) + "\n"


def compose(db, person: dict, sites: dict, day: str, logo: bool = False) -> dict | None:
    """{subject, text, html, carried: [(site, part, item)], count, sites} or None (nothing
    open). `sites`: {site: {"config", "security", "todos", "setup", "upto"}} for every site
    of the person. The plain-text and HTML parts come from one digest, so they cannot
    disagree; `count` is every item carried, folded or not."""
    d = digest(db, person, sites)
    if d is None:
        return None
    from . import summary_html
    return {"subject": subject_of(d), "text": as_text(d, day),
            "html": summary_html.render(d, day, logo=logo), "carried": d["carried"],
            "count": d["items"], "sites": len(d["sites"])}


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
        out=print, setup=None, html_dir=None) -> dict:
    """Build and send the day's summaries. `sites`: [{site, config, live_dir, history, out,
    config_path}]; `setup` replaces setup_part (tests); `html_dir` (dry run only): each
    mail's HTML part written there as summary-<user id>.html. {"sent", "failed", "nothing",
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
                            "setup": setup(s, now), "upto": upto(s["site"], s.get("out"))}
    from .mailer import _logo
    logo = _logo()
    tally = {"sent": 0, "failed": 0, "nothing": 0, "already": 0, "items": 0}
    for person in sorted(who.values(), key=lambda p: p["email"]):
        if db.execute("SELECT 1 FROM summary_sends WHERE user_id = ? AND day = ?",
                      (person["user_id"], day)).fetchone():
            tally["already"] += 1
            continue
        mail = compose(db, person, found, day, logo=logo is not None)
        if mail is None:
            tally["nothing"] += 1
            continue
        if dry_run:
            out(f"To: {person['email']}\nSubject: {brand.prefix()} {mail['subject']}\n\n"
                f"{mail['text']}\n")
            if html_dir:
                page = Path(html_dir) / f"summary-{int(person['user_id'])}.html"
                page.write_text(mail["html"])
                out(f"HTML part: {page}")
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
        error = sn._mail(cfg, person["email"], mail["subject"], mail["text"], now, send,
                         html=mail["html"], logo=logo)
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
                  dry_run=bool(getattr(ctx.args, "dry_run", False)), out=ctx.out,
                  html_dir=getattr(ctx.args, "html", None))
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
    p.add_argument("--html", metavar="DIR", help="with --dry-run: write each mail's HTML part "
                   "into DIR (summary-<user id>.html), to look at it in a browser")
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
