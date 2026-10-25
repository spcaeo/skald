"""Security alerts to the people on a site (2.21): each team member, by their own choice.

The site's alerts (alerts.py, alerts_security.py) still go where they always went: the
dashboard, the site's confirmed mail recipients when alert mail is on, and the site's
webhooks (Slack too). This adds a mail to each person on the site's team who wants one:

  who        the members of the site's organisation (accounts.sqlite) whose account is
             confirmed (a password set: the invite link was used) and not disabled
  choice     per person and site (Security > Alerts, "Your security alerts"): on or off,
             in the daily summary or right away. Defaults: owners and admins on, in the
             summary; viewers off until they turn it on. The summary (summary_mail.py,
             01:00 in the schedule's zone) is one mail per person a day for every site;
             it is stored as mode "daily"
  what       a possible exposure (security.py's `possible` answers, today so far and the
             last whole day) and an advisory that matches the site's stack (stack.py:
             update needed, no official fix, check your version)
  tracked    every live run and run-daily keep `security_items` up to date (open, still
             open, closed); neither mails by itself any more (2.36: one mail per item and
             per site made 44 mails in a minute for one person)
  right away after every site of a live run or run-daily, right_away(): ONE mail per
             person with every item due on every site they chose "right away" for
  once       each person gets each item once; a reminder only while the item is still
             open after `security.remind_days` (3) days, then every as many days again
             (a summary that carried the item counts as a mail)
  the mail   names the site, what was found, what to do (one line) and the link straight
             to it: <dashboard url>#threats/exposed?item=<id> (or #threats/stack?item=),
             the id an opaque hash of the site and the item, never an address
  logged     every send is a row in the organisation's audit log: who (the address it went
             to), which item and how ("security.alert.sent", never the content)

A person who is also one of the site's alert mail recipients does not get a second mail for
an exposure while the site's alert mail is on. Nothing is sent without accounts (basic
mode) or without a mail server. Kept in accounts.sqlite, tables made here on first use.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone

PREFS = ("CREATE TABLE IF NOT EXISTS security_prefs (user_id INTEGER NOT NULL, site TEXT NOT NULL, "
         "alerts INTEGER NOT NULL, mode TEXT NOT NULL CHECK (mode IN ('now', 'daily')), "
         "updated_at TEXT NOT NULL, PRIMARY KEY (user_id, site))")
ITEMS = ("CREATE TABLE IF NOT EXISTS security_items (site TEXT NOT NULL, item TEXT NOT NULL, "
         "kind TEXT NOT NULL, title TEXT NOT NULL, todo TEXT NOT NULL, first_at TEXT NOT NULL, "
         "last_seen_at TEXT NOT NULL, closed_at TEXT, PRIMARY KEY (site, item))")
SENDS = ("CREATE TABLE IF NOT EXISTS security_sends (site TEXT NOT NULL, item TEXT NOT NULL, "
         "user_id INTEGER NOT NULL, how TEXT NOT NULL, sent_at TEXT NOT NULL)")
ON_ROLES = ("owner", "admin")
REMIND_DAYS = 3
DEFAULT_MODE = "daily"                  # in the daily summary (summary_mail.py), since 2.36
TAB = {"exposure": "exposed", "advisory": "stack"}


def _ready(db) -> None:
    for sql in (PREFS, ITEMS, SENDS):
        db.execute(sql)


def _stamp(now: datetime) -> str:
    return now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def item_id(kind: str, site: str, *parts) -> str:
    raw = "|".join([kind, site, *[str(p) for p in parts]])
    return ("x" if kind == "exposure" else "a") + hashlib.sha256(raw.encode()).hexdigest()[:12]


def link(config: dict, kind: str, item: str) -> str:
    base = str(((config or {}).get("dashboard") or {}).get("url") or "").rstrip("#")
    return f"{base}#threats/{TAB[kind]}?item={item}"


def remind_days(config: dict) -> int:
    try:
        return max(1, int(((config or {}).get("security") or {}).get("remind_days", REMIND_DAYS)))
    except (TypeError, ValueError):
        return REMIND_DAYS


# ------------------------------------------------------------- preferences

def prefs_of(db, user_id: int, role: str | None, site: str) -> dict:
    _ready(db)
    row = db.execute("SELECT alerts, mode FROM security_prefs WHERE user_id = ? AND site = ?",
                     (int(user_id), site)).fetchone()
    if row is None:
        return {"alerts": role in ON_ROLES, "mode": DEFAULT_MODE, "default": True}
    return {"alerts": bool(row[0]), "mode": row[1], "default": False}


def set_prefs(db, user_id: int, site: str, alerts: bool, mode: str, now: datetime | None = None) -> dict:
    if mode not in ("now", "daily"):
        raise ValueError("mode is now or daily")
    _ready(db)
    db.execute("INSERT INTO security_prefs (user_id, site, alerts, mode, updated_at) VALUES "
               "(?, ?, ?, ?, ?) ON CONFLICT(user_id, site) DO UPDATE SET alerts = excluded.alerts, "
               "mode = excluded.mode, updated_at = excluded.updated_at",
               (int(user_id), site, int(bool(alerts)), mode, _stamp(now or datetime.now(timezone.utc))))
    db.commit()
    return {"alerts": bool(alerts), "mode": mode, "default": False}


def recipients(db, site: str) -> list[dict]:
    """The team members who get security alerts for `site`, with their choice."""
    from .accounts.orgs import org_of_site
    _ready(db)
    org = org_of_site(db, site)
    if org is None:
        return []
    out = []
    for r in db.execute("SELECT u.id, u.email, m.role, u.pw_hash IS NOT NULL, u.disabled_at "
                        "FROM members m JOIN users u ON u.id = m.user_id WHERE m.org_id = ? "
                        "ORDER BY u.email", (org["id"],)).fetchall():
        uid, email, role, confirmed, disabled = r
        if not confirmed or disabled:
            continue                    # an unconfirmed or disabled account never gets one
        pref = prefs_of(db, uid, role, site)
        if pref["alerts"]:
            out.append({"user_id": uid, "email": email, "role": role, "mode": pref["mode"],
                        "org_id": org["id"]})
    return out


# ------------------------------------------------------------------- items

def items(config: dict, site: str, blobs: list, stack_read: dict | None) -> list[dict]:
    """[{item, kind, title, todo}] open now: possible exposures of the blobs given (today
    so far, the last whole day) and the stack's advisory matches that need something done."""
    from .alerts_security import advice
    from .security import current
    out, seen = [], set()
    for blob in blobs:
        if not current(blob):           # counted before 2.21.1's rule: never mailed
            continue
        for r in ((blob or {}).get("exposure") or {}).get("rows") or []:
            if r.get("verdict") != "possible":
                continue
            it = item_id("exposure", site, r["host"], r["path"])
            if it in seen:
                continue
            seen.add(it)
            out.append({"item": it, "kind": "exposure",
                        "title": f"Possible exposure on {site}: {r['host']}{r['path']} answered "
                                 f"{r['status']} ({r['size']:,} bytes)",
                        "todo": f"Open it yourself and check what it returns. {advice(r.get('category'))}"})
    for m in (stack_read or {}).get("matches") or []:
        if m["state"] not in ("update_needed", "no_fix", "check_version"):
            continue
        it = item_id("advisory", site, m["advisory"], m["host"], m["product"])
        if it in seen:
            continue
        seen.add(it)
        from .advisories import WORDS
        shown = m["version"] or "version not shown"
        out.append({"item": it, "kind": "advisory",
                    "title": f"Advisory for {site}: {m['product']} {shown} on {m['host']}: "
                             f"{WORDS[m['state']]}",
                    "todo": "Update to the fixed release (Security > Your stack lists it)."
                    if m["state"] == "update_needed" else
                    "Move to a supported branch: this one gets no fix." if m["state"] == "no_fix"
                    else "Check the version on the server against the fixed releases."})
    return out


def _track(db, site: str, found: list, now: datetime) -> None:
    """Open the items seen now, keep them open, close the ones gone."""
    stamp = _stamp(now)
    for it in found:
        db.execute("INSERT INTO security_items (site, item, kind, title, todo, first_at, "
                   "last_seen_at) VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(site, item) DO UPDATE "
                   "SET last_seen_at = excluded.last_seen_at, closed_at = NULL, "
                   "title = excluded.title, todo = excluded.todo",
                   (site, it["item"], it["kind"], it["title"], it["todo"], stamp, stamp))
    live = {it["item"] for it in found}
    for (item,) in db.execute("SELECT item FROM security_items WHERE site = ? AND closed_at IS NULL",
                              (site,)).fetchall():
        if item not in live:
            db.execute("UPDATE security_items SET closed_at = ? WHERE site = ? AND item = ?",
                       (stamp, site, item))


def due(db, site: str, user_id: int, item: str, now: datetime, every: int) -> str | None:
    """"first", "reminder" or None: whether this person gets this item now."""
    row = db.execute("SELECT MAX(sent_at) FROM security_sends WHERE site = ? AND item = ? AND "
                     "user_id = ? AND how != 'test'", (site, item, int(user_id))).fetchone()
    if not row or not row[0]:
        return "first"
    last = datetime.strptime(row[0], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    return "reminder" if now - last >= timedelta(days=every) else None


# -------------------------------------------------------------------- mail

def _mail(config: dict, to: str, subject: str, text: str, now: datetime, send) -> str | None:
    """One plain mail to one address; the error in words, or None."""
    from html import escape

    from . import mailer
    try:
        cfg = dict(mailer.settings({**config, "mail": {**((config or {}).get("mail") or {}),
                                                       "to": [to]}}), to=[to])
        msg = mailer._message(cfg, subject, text, "<pre style=\"font:14px/1.5 sans-serif;"
                              "white-space:pre-wrap\">" + escape(text) + "</pre>", now)
        (send or mailer.send)(msg, cfg)
    except Exception as why:            # noqa: BLE001 - never fails the run
        return f"{type(why).__name__}"
    return None


def _log(db, org_id, email: str, item: str, kind: str, how: str) -> None:
    from .accounts import auditlog
    auditlog.record(db, org_id, "skald", "security.alert.sent", email, f"{item} {kind} {how}")


def _skip(config: dict, it: dict, email: str) -> bool:
    """An exposure the site's own alert mail already sends to this address."""
    a = (config or {}).get("alerts") or {}
    flag = lambda v: v is True or str(v).strip().lower() in ("1", "true", "yes", "on")  # noqa: E731
    on = flag(a.get("enabled", False)) and flag(a.get("mail", True)) and \
        flag(a.get("security_exposure", True))
    mailed = {str(x).strip().lower() for x in ((config or {}).get("mail") or {}).get("to") or []}
    return it["kind"] == "exposure" and on and email.strip().lower() in mailed


def track(db, site: str, found: list, now: datetime) -> None:
    """Keep `security_items` up to date for one site; nothing is mailed."""
    _ready(db)
    _track(db, site, found, now)
    db.commit()


def open_items(db, site: str) -> list[dict]:
    """[{item, kind, title, todo, first_at}] open now on `site`, the oldest first."""
    _ready(db)
    rows = db.execute("SELECT item, kind, title, todo, first_at FROM security_items WHERE "
                      "site = ? AND closed_at IS NULL ORDER BY first_at, item", (site,)).fetchall()
    return [dict(zip(("item", "kind", "title", "todo", "first_at"), r)) for r in rows]


def run(db, config: dict, site: str, found: list, now: datetime, mode: str, send=None) -> list:
    """Track the items of one site. "now": then the right-away mail for this site alone (one
    mail per person); "daily": nothing is mailed (the summary does it). [(email, item, how)]."""
    track(db, site, found, now)
    if mode != "now":
        return []
    return [(e, i, h) for e, _, i, h in send_due(db, [(site, config)], now, send)]


def send_due(db, sites: list, now: datetime, send=None) -> list:
    """The people who chose "right away": ONE mail per person with every open item due on
    every site given ([(site, config)]), never one per item. [(email, site, item, how)]."""
    _ready(db)
    configs = dict(sites)
    people: dict[int, dict] = {}
    for site, config in sites:
        found = open_items(db, site)
        if not found:
            continue
        every = remind_days(config)
        for person in recipients(db, site):
            if person["mode"] != "now":
                continue
            for it in found:
                how = due(db, site, person["user_id"], it["item"], now, every)
                if how and not _skip(config, it, person["email"]):
                    got = people.setdefault(person["user_id"], {"email": person["email"],
                                                                "config": config, "due": []})
                    got["due"].append((site, person["org_id"], it, how))
    done = []
    for uid, got in people.items():
        batch = got["due"]
        names = list(dict.fromkeys(site for site, _, _, _ in batch))
        where = names[0] if len(names) == 1 else f"{len(names)} sites"
        subject = (f"Security: {batch[0][2]['title']}" if len(batch) == 1
                   else f"Security: {len(batch)} items on {where}")
        lines = [f"{'Reminder: ' if how == 'reminder' else ''}{it['title']}\n"
                 f"What to do: {it['todo']}\n"
                 f"Open it: {link(configs[site], it['kind'], it['item'])}\n"
                 for site, _, it, how in batch]
        text = (f"Skald found this on {', '.join(names)}:\n\n" + "\n".join(lines) +
                "\nYou chose these right away: one mail per run with everything due. You get "
                "each item once, and a reminder while it stays open. Change this on Security > "
                "Alerts, Your security alerts (the daily summary is the default).\n")
        if _mail(got["config"], got["email"], subject, text, now, send) is not None:
            continue                    # not recorded: the next run tries again
        for site, org_id, it, how in batch:
            db.execute("INSERT INTO security_sends (site, item, user_id, how, sent_at) "
                       "VALUES (?, ?, ?, ?, ?)", (site, it["item"], uid, how, _stamp(now)))
            _log(db, org_id, got["email"], it["item"], it["kind"], how)
            done.append((got["email"], site, it["item"], how))
    db.commit()
    return done


def right_away(contexts: list, send=None) -> list:
    """After every site of a live run or run-daily: the right-away mail. Never raises."""
    if not contexts:
        return []
    first = contexts[0]
    try:
        from .auth_api import open_db, sessions_mode
        if not sessions_mode(first.config):
            return []
        db = open_db(first.config, first.live_dir)
        if db is None:
            return []
        try:
            got = send_due(db, [(c.site, c.config) for c in contexts], first.now, send)
        finally:
            db.close()
        if got:
            first.out(f"security alerts right away: {len({e for e, _, _, _ in got})} people, "
                      f"{len(got)} items, one mail each")
        return got
    except Exception as why:            # noqa: BLE001 - never stops the run
        first.err(f"security alerts: {type(why).__name__}: {why}")
        return []


def test_send(db, config: dict, site: str, user: dict, org_id, now: datetime | None = None,
              send=None) -> str | None:
    """"Send a test security alert": to the person who asked. The error, or None."""
    now = now or datetime.now(timezone.utc)
    _ready(db)
    it = {"item": item_id("exposure", site, "test", _stamp(now)), "kind": "exposure"}
    text = (f"This is a test of Skald's security alerts for {site}. A real one names what was "
            f"found, what to do, and links straight to it, like this:\n"
            f"{link(config, 'exposure', it['item'])}\n")
    error = _mail(config, user["email"], f"Security: a test alert for {site}", text, now, send)
    if error is None:
        db.execute("INSERT INTO security_sends (site, item, user_id, how, sent_at) VALUES "
                   "(?, ?, ?, 'test', ?)", (site, it["item"], int(user["user_id"]), _stamp(now)))
        _log(db, org_id, user["email"], it["item"], "test", "test")
        db.commit()
    return error


# ------------------------------------------------------------- the runs

def _found(config: dict, live_dir, history, site: str, snap: dict | None, day) -> list:
    from . import stack
    from .alerts_security import _whole
    blobs = []
    if snap and snap.get("state") == "ok":
        blobs.append((snap.get("extras") or {}).get("security"))
    if history is not None and day is not None:
        blobs.append(_whole(history, site, day))
    got = stack.latest(live_dir, site) if live_dir is not None else None
    return items(config, site, blobs, (got[1].get("read") if got else None))


def live(ctx, snap: dict | None, send=None) -> None:
    """Every live run: the items tracked; the mail is right_away()'s, after every site.
    Never raises."""
    try:
        from .auth_api import open_db, sessions_mode
        if not sessions_mode(ctx.config):
            return
        db = open_db(ctx.config, ctx.live_dir)
        if db is None:
            return
        try:
            with ctx.history() as history:
                day = ctx.now.astimezone(ctx.tz).date() - timedelta(days=1)
                found = _found(ctx.config, ctx.live_dir, history, ctx.site, snap, day)
            track(db, ctx.site, found, ctx.now)
        finally:
            db.close()
    except Exception as why:            # noqa: BLE001 - never stops the live run
        ctx.err(f"security alerts: {type(why).__name__}: {why}")


def daily(ctx, send=None) -> int:
    """run-daily's step: the items tracked from the last whole day and the stack check. It
    mails nobody (2.36): the 01:00 summary (summary_mail.py) carries them. Always 0."""
    try:
        from .auth_api import open_db, sessions_mode
        if not sessions_mode(ctx.config):
            return 0
        db = open_db(ctx.config, ctx.live_dir)
        if db is None:
            return 0
        try:
            with ctx.history() as history:
                day = ctx.now.astimezone(ctx.tz).date() - timedelta(days=1)
                found = _found(ctx.config, ctx.live_dir, history, ctx.site, None, day)
            track(db, ctx.site, found, ctx.now)
            ctx.out(f"security items: {len(open_items(db, ctx.site))} open; they go in the "
                    "daily summary")
        finally:
            db.close()
    except Exception as why:            # noqa: BLE001 - never stops the run
        ctx.err(f"security mail: {type(why).__name__}: {why}")
    return 0


def public(db, site: str) -> dict:
    """For the page: the open items with their ids (for ?item=)."""
    _ready(db)
    rows = db.execute("SELECT item, kind, title, first_at FROM security_items WHERE site = ? AND "
                      "closed_at IS NULL ORDER BY first_at", (site,)).fetchall()
    return {"open": [dict(zip(("item", "kind", "title", "first_at"), r)) for r in rows]}


def dumps(obj) -> str:
    return json.dumps(obj, separators=(",", ":"))
