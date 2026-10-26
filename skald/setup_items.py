"""The "Set up <site>" checklist's lines, worked out on the server (2.39.0).

`items(app, status, tools, settings, waiting)` is js/setup-items.js's
`setupItems` in Python: the same inputs (app.json; GET integrations' doctor
lines `status` and hook states `tools`; GET settings' `settings` and
`mail_waiting`), the same ids, states, titles, plain lines and Set up
dialogs (`act`). tests/test_setup_items.py feeds both the same answers and
expects the same lines, so the MCP tool `setup_left` says what the page shows.

`answers(...)` makes those inputs on the server from the functions behind the
two GET routes (doctor.integration_checks, conversions.roads.hook_states,
settings_store.explain, mail_confirm.keep_confirmed). A part that cannot be
worked out is None, as a failed answer is in the page: its lines say
"unknown", never done.

`JOBS`: the lines an AI agent can do (the set-up line's job ids). countries (a
file on Skald's own server) and mail (a person confirms their own address)
have none. Nothing here counts a figure: it reads what the dashboard reads.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

JOBS = ("logs", "script", "lead", "rsc", "assets", "privacy")
UNKNOWN = "Could not be checked just now. Open this page again in a minute."
_WHEN = re.compile(r"the last event came ([^\n\r  ]+)\Z")   # JS: /(.+)$/


def _doc(status, part: str) -> dict | None:
    return next((x for x in status or () if isinstance(x, dict) and x.get("id") == part), None)


def _num(v) -> float:
    """JS `(v || 0)` for a count."""
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) and v else 0


def _latest(app: dict | None) -> dict | None:
    """Today's live figures when they are today's, else the last whole stored day."""
    app = app or {}
    live = app.get("live") or {}
    if live.get("state") == "ok" and live.get("day") == app.get("today"):
        return live.get("figures") or None
    days = [d for d in app.get("days") or () if isinstance(d, dict) and d.get("state") == "ok"]
    return days[-1] if days else None


def _someone(f) -> bool:
    return _num(((f or {}).get("hits") or {}).get("people")) > 0 or _num((f or {}).get("readers")) > 0


def _tech(d) -> str | None:
    if not d:
        return None
    parts = [f"{d.get('part') or d.get('id')}: {d.get('says')}",
             f"Fix: {d['fix']}" if d.get("fix") and d.get("state") != "OK" else ""]
    return "\n".join(p for p in parts if p)


def _script_words(d) -> str:
    says = str((d or {}).get("says") or "")
    got = _WHEN.search(says)
    when = got.group(1) if got else None
    state = (d or {}).get("state")
    if state == "OK":
        return f"The tag works: the last event came {when or 'lately'}."
    if not d or state == "OFF":
        return "Optional. One line on your pages adds form steps, clicks and bookings."
    if "does not serve" in says:
        return ("The tag is switched on, but Skald's server does not hand it out yet. "
                "Your server admin can fix it.")
    if when:
        return f"No event from the tag since {when}. Check that it is still on your pages."
    return "The tag is not sending yet. Put it on your pages, then test it."


def _line(id_, title, state, says, tech=None, act=None, optional=False) -> dict:
    out = {"id": id_, "title": title, "state": state, "says": says, "tech": tech, "act": act}
    if optional:
        out["optional"] = True
    return out


def items(app=None, status=None, tools=None, settings=None, waiting=()) -> list[dict]:
    """The checklist's lines: {id, title, optional?, state, says, tech, act}."""
    f = _latest(app)
    out = []
    waiting = list(waiting or ())

    # 1. The log is read: the doctor's access-log line, else a live count with requests in it.
    logs = _doc(status, "logs")
    read = bool(f) and _num(f.get("requests")) > 0
    if (logs or {}).get("state") == "OK" or (not logs and read):
        out.append(_line("logs", "Logs arriving", "done",
                         "Visits are arriving: the server's log is read."))
    else:
        out.append(_line("logs", "Logs arriving", "todo",
                         "Visits arrived before, but the server's log cannot be read now." if read
                         else "No visit has reached Skald yet. Connect the site's server so its "
                              "visits arrive.", _tech(logs), "logs"))

    # 2. Page assets: the doctor's line; without it, whether any visit counted as people.
    assets = _doc(status, "assets") or {}
    t2 = "Visits count as people"
    none_yet = ("Visits arrive, but none counts as a person yet: tell Skald where your pages "
                "load their own files.")
    if assets.get("state") == "NEEDS ATTENTION":
        out.append(_line("assets", t2, "todo", none_yet, _tech(assets), "assets"))
    elif assets.get("state") == "OFF" and "not needed" in str(assets.get("says")):
        out.append(_line("assets", t2, "done", "Nothing to set: every visit from a browser counts."))
    elif assets.get("state") == "OK" or _someone(f):
        out.append(_line("assets", t2, "done",
                         "Visits count as people: their browsers load your pages' own files."))
    elif read:
        out.append(_line("assets", t2, "todo", none_yet, None, "assets"))
    else:
        out.append(_line("assets", t2, "wait", "Waits for the first visitor."))

    # 2b. Next.js: only while the log's payloads cannot be told from prefetches.
    rsc = _doc(status, "rsc")
    if (rsc or {}).get("state") == "NEEDS ATTENTION":
        out.append(_line("rsc", "Pages opened inside the site are not counted yet", "todo",
                         "Your site is built with Next.js. A page opened by a link inside the "
                         "site sends no page request, so Skald does not count it yet. One line "
                         "in the web server's log format fixes it.", _tech(rsc), "rsc"))

    # 3. Countries: a visit with a country, or the GeoIP file to set.
    by_country = ((f or {}).get("by") or {}).get("country") or {}
    cc = [k for k in by_country if k and k != "Unknown" and not str(k).startswith("(")]
    if cc:
        out.append(_line("countries", "Countries shown", "done", "Visits show their country."))
    elif _someone(f):
        out.append(_line("countries", "Countries shown", "todo",
                         "Visits come without a country. A country file on Skald's server adds it.",
                         "The log carries no country, and no GeoIP country file is set "
                         "(logs.country_db, or SKALD_COUNTRY_DB in Docker).", "countries"))
    else:
        out.append(_line("countries", "Countries shown", "wait", "Waits for the first visitor."))

    # 4. The script tag (optional): the doctor's line.
    script = _doc(status, "script")
    title = "Script tag events"
    if status is None:
        out.append(_line("script", title, "unknown", UNKNOWN, optional=True))
    elif (script or {}).get("state") == "OK":
        out.append(_line("script", title, "done", _script_words(script), optional=True))
    else:
        out.append(_line("script", title, "todo", _script_words(script),
                         _tech(script) if (script or {}).get("state") == "NEEDS ATTENTION"
                         else None, "script", optional=True))

    # 5. A lead hook (optional): a tool tested or receiving, and none whose last real delivery
    # was refused (that hook is never done, whatever another tool says).
    every = [t for t in tools or () if isinstance(t, dict)]
    hurt = next((t for t in every if t.get("attention") and t.get("state") != "needs_secret"), None)
    ok = [t for t in every if not t.get("attention") and t.get("state") in ("ready", "received")]
    lead = hurt or next((t for t in ok if t.get("state") == "received"), None) or \
        (ok[0] if ok else None) or next((t for t in every if t.get("tool") == "lead"), None)
    title = "Lead hook tested"
    if tools is None:
        out.append(_line("lead", title, "unknown", UNKNOWN, optional=True))
    elif hurt:
        name = hurt.get("name")
        tech = [f"{name}: {hurt.get('words')}.", f"Fix: {hurt['fix']}" if hurt.get("fix") else ""]
        out.append(_line("lead", title, "todo",
                         f"{name}: leads are not arriving. The last one it sent was refused."
                         if hurt.get("state") == "received" else f"{name}: not working yet.",
                         "\n".join(t for t in tech if t), "lead", optional=True))
    elif ok:
        out.append(_line("lead", title, "done", f"{lead.get('name')}: {lead.get('words')}.",
                         optional=True))
    else:
        out.append(_line("lead", title, "todo",
                         "Optional. Your forms or booking tool tell Skald about each lead.",
                         None, "lead", optional=True))

    # 6. Mail: a report on, and a recipient who confirmed.
    title = "Mail recipient confirmed"
    if settings is None:
        out.append(_line("mail", title, "unknown", UNKNOWN))
    else:
        value = lambda k: (settings.get(k) or {}).get("value")       # noqa: E731
        to = value("mail.to") or []
        on = value("mail.daily") or value("mail.weekly")
        done = bool(on and to and not waiting)
        if done:
            n = len(to)
            says = (f"The {'daily' if value('mail.daily') else 'weekly'} mail goes to {n} "
                    f"confirmed recipient{'' if n == 1 else 's'}.")
        elif waiting:
            n = len(waiting)
            says = (f"{n} recipient{' has' if n == 1 else 's have'} not confirmed yet "
                    "(the link in their mail).")
        elif not to:
            says = "Nobody gets the daily mail yet."
        else:
            says = "The daily and the weekly mail are both off."
        out.append(_line("mail", title, "done" if done else "todo", says, None,
                         None if done else "mail"))

    # 7. Privacy: someone chose what is kept about people (not left at the default).
    title = "Privacy settings chosen"
    if settings is None:
        out.append(_line("privacy", title, "unknown", UNKNOWN))
    else:
        ips = settings.get("privacy.keep_ips")
        v = (ips or {}).get("value")
        # full, short or off (2.15.0); true and false from an older answer.
        mode = "full" if v is True else "off" if (v is False or not v) else v
        chosen = bool(ips and ips.get("source") and ips.get("source") != "default")
        if chosen:
            days = (settings.get("privacy.keep_days") or {}).get("value")
            kept = (f"kept{' shortened' if mode == 'short' else ''} with each visit"
                    f"{f' for {days} days' if days else ''}")
            says = f"IP addresses {kept if mode != 'off' else 'not kept'}."
        else:
            says = "Choose what is kept about visitors, then copy the wording for your privacy notice."
        out.append(_line("privacy", title, "done" if chosen else "todo", says, None,
                         None if chosen else "privacy"))
    return out


def done(lines: list[dict]) -> bool:
    """Every line that is not optional is done (js setupDone)."""
    return all(i.get("optional") or i["state"] == "done" for i in lines)


def job_of(line: dict) -> str | None:
    """The set-up line's job for an open line an AI agent can do, else None."""
    act = line.get("act")
    return act if line.get("state") != "done" and act in JOBS else None


# ------------------------------------------------------- the inputs, on the server

def _warn(part: str, why: Exception) -> None:
    sys.stderr.write(f"setup_items: {part} could not be worked out: "
                     f"{type(why).__name__}: {why}\n")


def answers(config: dict, site: str, live_dir=None, config_path=None, base: str = "",
            accounts_db=None) -> dict:
    """{status, tools, settings, waiting}: what GET integrations and GET
    settings answer the page for `site`, worked out by the same functions.
    `accounts_db`: accounts.sqlite open (None: opened here when there is one)."""
    from .config import site_name
    from .conversions import hooks
    from .files import slug
    config = config or {}
    folder = Path(live_dir) if live_dir is not None else hooks.history_folder(config, config_path)
    got = {"status": None, "tools": None, "settings": None, "waiting": []}
    try:
        conf = hooks.site_configs(config, config_path).get(site) or config
    except Exception as why:                       # noqa: BLE001 - the parts say unknown
        _warn("the site's config", why)
        return got
    try:
        from .doctor import integration_checks
        own = folder if site == site_name(config) else folder / "sites" / slug(site)
        got["status"] = integration_checks(conf, folder, site, own, config_path=config_path)
    except Exception as why:                       # noqa: BLE001
        _warn("the doctor's lines", why)
    try:
        got["tools"] = _hooks(config, conf, folder, site, config_path, base)
    except Exception as why:                       # noqa: BLE001
        _warn("the hooks", why)
    db = accounts_db
    try:
        if db is None:
            from .accounts import db as accounts
            path = accounts.path_for(config, folder)
            db = accounts.connect(path) if path is not None and Path(path).is_file() else None
        from .settings_api import site_config
        got["settings"], got["waiting"] = _settings(site_config(config, config_path, site),
                                                    site, db)
    except Exception as why:                       # noqa: BLE001
        _warn("the settings", why)
    finally:
        if db is not None and accounts_db is None:
            db.close()
    return got


def _hooks(config, conf, folder, site, config_path, base) -> list[dict]:
    from .conversions import store
    from .conversions.roads import hook_states
    from .doctor import command
    path = store.path_for(config, folder)
    db = store.connect(path) if path is not None and Path(path).exists() else None
    try:
        return hook_states(conf, folder, site, db, cmd=command(config_path), base=base)
    finally:
        if db is not None:
            db.close()


def _settings(config, site, db) -> tuple[dict, list]:
    """settings_api.settings' `settings` (value and source: what the lines read)
    and `mail_waiting`, for the site's config layer (settings_api.site_config)."""
    from . import settings_store as store
    got = store.explain(config, site, db)
    waiting = []
    mail_to = got.get("mail.to") or {}
    if db is not None and mail_to.get("source") in ("site", "org"):
        from .accounts.orgs import org_of_site
        from .mail_confirm import keep_confirmed
        org = org_of_site(db, site)
        if org is not None:
            own = store._from_config(config, store.SCHEMA["mail.to"]) or []
            waiting = keep_confirmed(db, org["id"], mail_to.get("value"), own)[1]
    return got, waiting
