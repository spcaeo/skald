"""Settings > Leads & tools > Search Console & Bing: connecting Search Console and Bing from
the dashboard, no shell (sessions mode; docs/INTEGRATIONS.md, "Search").

Served by the refresh helper for every site page, beside integrations_api.py
and with its rules (signed in, admin or owner of the site's organisation or
an install admin, same-origin and the CSRF header on every POST, each change
in the audit log, never a secret in an answer):

  GET  integrations/search[?site=]       the keys (install-level: the service
                                         account's email only; the Bing key's
                                         last four characters), each engine's
                                         connection, sync state and stored days
  POST integrations/search/googlekey     {key}: the service-account JSON file's
                                         text; checked (google.check_key), kept
                                         0600 in secrets.json. Install admins.
  POST integrations/search/googleremove  take the uploaded key out. Install admins.
  POST integrations/search/bingkey       {key}: the Bing API key. Install admins.
  POST integrations/search/bingremove    Install admins.
  POST integrations/search/properties    {site, engine}: the properties the key can
                                         see that cover this site's host names
  POST integrations/search/test          {site, engine, source}: the last 3 days,
                                         read and never stored
  POST integrations/search/connect       {site, engine, source, backfill_months}:
                                         save the property (settings, the site's
                                         row), then sync in the background: the
                                         backfill (0, 3 or 16 months) or one sync
  POST integrations/search/disconnect    {site, engine}: stop syncing; what was
                                         synced stays in history
  POST integrations/search/sync          {site}: "Sync now", in the background; at
                                         most once in SYNC_MINUTES per site, 409
                                         while a sync of the site runs

A property is accepted only when it covers one of the site's host names
(props.covers): one key serves every site of the install.
"""
from __future__ import annotations

import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .. import auth_api, integrations_api as base, settings_store
from ..auth_api import answer, csrf_ok, read_json, text
from ..conversions import secrets_store
from . import bing, days, google, http, props, state, sync

PATH = re.compile(base.PAGE + r"(?P<act>integrations/search(?:/(?:googlekey|googleremove|"
                              r"bingkey|bingremove|properties|test|connect|disconnect|sync))?)$")
GETS = {"integrations/search"}
SYNC_MINUTES = 10
USERS_PAGE = "https://search.google.com/search-console/users"
BING_USERS_PAGE = "https://www.bing.com/webmasters/usermanagement"
SETTING = {"google": "search.google_property", "bing": "search.bing_site"}
ROOT = Path(__file__).resolve().parents[2]


def match(path: str):
    path = path.split("?", 1)[0]
    return None if ".." in path else PATH.match(path)


def is_search(path: str) -> bool:
    return match(path) is not None


def spawn(c, site: str, args: list[str]) -> None:
    """Run `skald --site SITE <args>` in the background, detached. Replaced
    in tests."""
    if c.config_path is None:
        raise OSError("the helper does not know its config file")
    log = state.folder(c.folder) / f"{site}.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    with open(log, "a", encoding="utf-8") as out:
        subprocess.Popen([sys.executable, str(ROOT / "bin/skald"), "--config", str(c.config_path),
                          "--site", site, *args], cwd=str(ROOT), stdin=subprocess.DEVNULL,
                         stdout=out, stderr=subprocess.STDOUT, start_new_session=True)


def handle(h, write: bool, config, live_dir, allowed: set[str], same_origin,
           config_path=None) -> None:
    if not auth_api.sessions_mode(config):
        return answer(h, 404, {"ok": False, "error": "not found"})
    m = match(h.path)
    act = m.group("act")
    if write == (act in GETS):
        return answer(h, 405, {"ok": False, "error": "wrong method"})
    if write and not same_origin(h.headers, allowed):
        return answer(h, 403, {"ok": False, "error": "same-origin requests only"})
    db = auth_api.open_db(config, live_dir)
    if db is None:
        return answer(h, 503, {"ok": False, "error": "accounts are not set up here"})
    try:
        from ..accounts import sessions, users
        session = sessions.resolve(db, auth_api.cookie_of(h.headers))
        if session is None:
            return answer(h, 401, {"ok": False, "error": "Sign in first."})
        if write and not csrf_ok(session, h.headers):
            return answer(h, 403, {"ok": False, "error": "The page is out of date. "
                                                         "Reload it and try again."})
        role, org = users.site_role(db, session["user_id"], m.group("site"))
        if role is None and not session["install_admin"]:
            return answer(h, 403, {"ok": False, "error": "You are not a member here."})
        c = base.Ctx(h, db, session, m.group("site"), role, org, config, live_dir, config_path)
        if not (role in base.ADMIN or c.install_admin):
            return c.no(403, "Integrations are for admins.", role=role)
        form = {}
        if write:
            form = read_json(h)
            if form is None:
                return None
        return ROUTES[act](c, form)
    finally:
        db.close()


# ---------------------------------------------------------------- helpers

def _hosts(c, site: str) -> list[str]:
    conf = base._site_config(c, site)
    got = settings_store.explain(conf, site, c.db).get("sites.hosts") or {}
    return [str(h) for h in (got.get("value") or [])]


def _sources(c, site: str) -> dict:
    conf = base._site_config(c, site)
    found = settings_store.explain(conf, site, c.db)
    return {e: (found.get(k) or {}).get("value") for e, k in SETTING.items()}


def _job(c, site: str) -> sync.Job:
    conf = settings_store.apply(base._site_config(c, site), site, c.folder)
    db_path = Path(((c.config.get("_resolved") or {}).get("history_db"))
                   or c.folder / "history.sqlite")
    return sync.Job(conf, site, c.folder, db_path, datetime.now(timezone.utc),
                    out=lambda *a: None, err=lambda *a: None)


def _engine(c, form) -> str | None:
    engine = text(form, "engine", 10)
    if engine not in ("google", "bing"):
        c.no(400, "engine is google or bing.")
        return None
    return engine


def _install_admin(c) -> bool:
    if not c.install_admin:
        c.no(403, "Only an install admin can change the keys: they serve every site.")
        return False
    return True


def _secrets(c) -> Path | None:
    path = settings_store.secrets_path(c.config, c.folder)
    if path is None:
        c.no(503, "The server has no secrets file.")
    return path


def instructions(email: str | None, site: str) -> dict:
    """Step A, as numbered steps and as text to send a client."""
    who = email or "(upload the service-account key first)"
    steps = [
        "Open Search Console and pick the property of " + site + ".",
        "Go to Settings > Users and permissions.",
        "Choose Add user and paste this email: " + who + ".",
        "Set Permission to Restricted (read-only) and choose Add.",
    ]
    send = (f"Hello,\n\nTo show {site}'s Google search figures in our Skald analytics, please "
            f"give our read-only robot access to its Search Console property:\n\n"
            + "\n".join(f"{i}. {s}" for i, s in enumerate(steps, 1))
            + f"\n\nThe page is {USERS_PAGE}\nRestricted access can only read figures; it "
              "cannot change anything. You can remove it there at any time.\n\nThank you!")
    return {"email": email, "steps": steps, "link": USERS_PAGE, "send_text": send}


# ---------------------------------------------------------------- reading

def overview(c, form):
    site = base._target(c, form)
    if site is None:
        return None
    gkey = google.key_state(c.config, c.folder)
    bkey = bing.key_state(c.config, c.folder)
    sources = _sources(c, site)
    saved = state.load(c.folder, site)
    engines = {}
    db_path = _job(c, site).db_path
    for engine in ("google", "bing"):
        summary = {}
        if Path(db_path).exists():
            from ..store import History
            try:
                with History.reader(db_path) as history:
                    summary = days.summary(history.db, site, engine)
            except Exception:           # noqa: BLE001 - an older or busy file
                summary = {}
        part = saved.get(engine) or {}
        engines[engine] = {"connected": sources[engine], "status": part, "summary": summary,
                           "busy": state.is_busy(c.folder, site)}
    return c.ok(site=site, sites=base.managed(c), install_admin=c.install_admin,
                hosts=_hosts(c, site), locked=base._locked(c, site),
                keys={"google": {k: gkey.get(k) for k in ("set", "where", "client_email",
                                                          "problem")},
                      "bing": {k: bkey.get(k) for k in ("set", "where", "hint", "problem")}},
                engines=engines, google_steps=instructions(gkey.get("client_email"), site),
                bing_link=BING_USERS_PAGE, sync_every_hours=sync.EVERY_HOURS,
                sync_minutes=SYNC_MINUTES)


# ------------------------------------------------------------------- keys

def google_key(c, form):
    if not _install_admin(c):
        return None
    raw = form.get("key")
    try:
        info = google.check_key(raw if isinstance(raw, str) else "")
    except google.BadKey as why:
        return c.no(400, str(why))
    path = _secrets(c)
    if path is None:
        return None
    secrets_store.put(path, google.SECRET, google.compact(raw))
    c.log("search.key", "google", f"service account {info['client_email']} uploaded")
    return c.ok(client_email=info["client_email"])


def google_remove(c, form):
    if not _install_admin(c):
        return None
    path = _secrets(c)
    if path is None:
        return None
    gone = secrets_store.delete(path, [google.SECRET])
    c.log("search.key", "google", "service-account key removed")
    return c.ok(removed=bool(gone))


def bing_key(c, form):
    if not _install_admin(c):
        return None
    try:
        value = bing.check_key(form.get("key"))
    except bing.BadKey as why:
        return c.no(400, str(why))
    path = _secrets(c)
    if path is None:
        return None
    settings_store.put(c.db, "install", bing.SETTING, value, c.uid, secret=(path, bing.ENV))
    return c.ok(hint="…" + value[-4:])


def bing_remove(c, form):
    if not _install_admin(c):
        return None
    path = _secrets(c)
    if path is None:
        return None
    settings_store.put(c.db, "install", bing.SETTING, None, c.uid, secret=(path, bing.ENV))
    secrets_store.delete(path, [bing.ENV])          # put leaves an empty value
    return c.ok(removed=True)


# ------------------------------------------------------------ the wizard

def properties(c, form):
    site = base._target(c, form)
    engine = _engine(c, form) if site else None
    if engine is None:
        return None
    hosts = _hosts(c, site)
    if not hosts:
        return c.no(409, "Set this site's host names first (Settings > Site).")
    job = _job(c, site)
    try:
        client = sync.google_client(job) if engine == "google" else sync.bing_client(job)
        found = client.sites()
    except http.Failed as why:
        return c.no(502, str(why))
    fit = props.matching(found, hosts)
    return c.ok(engine=engine, hosts=hosts, properties=fit, seen=len(found),
                hint=None if fit else (
                    f"The key can see {len(found)} propert{'y' if len(found) == 1 else 'ies'}, "
                    f"none for {', '.join(hosts)}. Do step 1 first, then wait a minute."))


def _source(c, form, engine: str, site: str) -> str | None:
    try:
        source = (props.google_property if engine == "google" else props.bing_site)(
            form.get("source"))
    except props.Invalid as why:
        c.no(400, str(why))
        return None
    hosts = _hosts(c, site)
    if not hosts or not props.covers(source, hosts):
        c.no(403, f"{source} does not cover this site's host names "
                  f"({', '.join(hosts) or 'none set'}).")
        return None
    return source


def test(c, form):
    site = base._target(c, form)
    engine = _engine(c, form) if site else None
    source = _source(c, form, engine, site) if engine else None
    if source is None:
        return None
    try:
        got = sync.test(_job(c, site), engine, source)
    except http.Failed as why:
        return c.no(502, str(why))
    except ValueError as why:
        return c.no(502, f"The answer did not add up: {why}")
    return c.ok(**got)


def connect(c, form):
    site = base._change_target(c, form)
    engine = _engine(c, form) if site else None
    source = _source(c, form, engine, site) if engine else None
    if source is None:
        return None
    months = form.get("backfill_months") or 0
    if months not in (0, 3, 16) or engine == "bing" and months:
        return c.no(400, "backfill_months is 0, 3 or 16 (Search Console only).")
    settings_store.put(c.db, f"site:{site}", SETTING[engine], source, c.uid)
    state.update(c.folder, site, engine, source=source, error=None, error_since=None,
                 error_mailed=None, connected_at=state.now_text(),
                 backfill={"state": "queued", "months": months, "done": 0, "of": None}
                 if months else None)
    command = "search-console" if engine == "google" else "bing"
    args = [command, "sync"] + (["--backfill-months", str(months)] if months else [])
    try:
        spawn(c, site, args)
        started = True
    except OSError:
        started = False
    return c.ok(engine=engine, source=source, started=started, backfill_months=months)


def disconnect(c, form):
    site = base._change_target(c, form)
    engine = _engine(c, form) if site else None
    if engine is None:
        return None
    settings_store.put(c.db, f"site:{site}", SETTING[engine], None, c.uid)
    state.update(c.folder, site, engine, source=None, disconnected_at=state.now_text(),
                 next_sync=None)
    return c.ok(engine=engine, kept=True)


def sync_now(c, form):
    site = base._change_target(c, form)
    if site is None:
        return None
    if not any(_sources(c, site).values()):
        return c.no(409, "Nothing is connected for this site yet.")
    if state.is_busy(c.folder, site):
        return c.no(409, "A sync of this site is running now.")
    asked = (state.load(c.folder, site).get("asked") or {}).get("at")
    now = datetime.now(timezone.utc)
    if asked:
        try:
            wait = datetime.fromisoformat(asked) + timedelta(minutes=SYNC_MINUTES) - now
        except ValueError:
            wait = timedelta(0)
        if wait > timedelta(0):
            return c.no(429, f"Synced a moment ago: try again in {int(wait.total_seconds() // 60) + 1} "
                             "minutes.", retry_after=int(wait.total_seconds()))
    state.update(c.folder, site, "asked", at=state.now_text(now))
    try:
        spawn(c, site, ["search", "sync"])
    except OSError as why:
        return c.no(503, f"The sync could not start ({why.strerror or why}).")
    c.log("search.sync", site, "sync now")
    return c.ok(started=True)


ROUTES = {"integrations/search": overview, "integrations/search/googlekey": google_key,
          "integrations/search/googleremove": google_remove,
          "integrations/search/bingkey": bing_key, "integrations/search/bingremove": bing_remove,
          "integrations/search/properties": properties, "integrations/search/test": test,
          "integrations/search/connect": connect, "integrations/search/disconnect": disconnect,
          "integrations/search/sync": sync_now}
