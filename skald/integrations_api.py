"""Settings > Integrations, with `access.mode: sessions` (docs/INTEGRATIONS.md).

Served by the refresh helper (refresh_server.py) like settings_api.py, for
every site page, `/traffic/<site>/[<view>/]...`, to admins and owners of the
site's organisation and to install admins:

  GET  integrations[?site=]           the script tag and its options; the sites
                                      the caller may manage; for the chosen site
                                      each tool's hook address, whether its secret
                                      is set (and where), its last 50 deliveries;
                                      the outgoing webhooks with their last 50
  POST integrations/secret            {site, tool}: make or rotate a hook's secret;
                                      shown once in the answer, kept 0600. Refused
                                      (409) for Stripe and HubSpot, which sign with
                                      a secret they make (OWN_SECRET)
  POST integrations/hooks/paste       {site, tool, secret}: the signing secret the
                                      tool made (Stripe, HubSpot; Calendly, Cal.com
                                      and Typeform may give their own too), kept
                                      0600 and never sent back
  POST integrations/hooks/remove      {site, tool}: delete the hook's secret, so its
                                      address answers 404 again; its deliveries
                                      stay in the log
  POST integrations/test              {site, tool}: a signed sample posted to the
                                      receiver in this process, marked as a test
                                      (read, logged as "test", never kept)
  POST integrations/webhooks/add      {site, url, events}: an outgoing webhook; its
                                      secret is shown once
  POST integrations/webhooks/remove   {site, id}
  POST integrations/webhooks/rotate   {site, id}: a new secret, shown once
  POST integrations/webhooks/test     {site, id}: a signed sample sent now (at
                                      most 10 s; 3 in 10 minutes per user, then 429)

Which sites: an install admin manages every site of the install (and every
site an organisation holds); an admin or owner only their organisations'
sites. In basic mode every route answers 404. Every POST needs the
same-origin check and the session's X-Skald-CSRF value, and is written to
the audit log (never a secret). An organisation whose plan is locked
(saas: payment overdue) reads but cannot change.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from urllib.parse import urlsplit

from . import auth_api
from .accounts import auditlog, sessions, users
from .auth_api import answer, csrf_ok, read_json, text
from .config import setting
from .conversions import TOOLS, secrets_store, store
from .conversions import hooks as hooks_mod
from .conversions import outgoing
from .conversions.adapters import adapter

PAGE = r"^/traffic/(?P<site>[a-z0-9.-]+)/(?:(?P<view>[a-z0-9-]+)/)?"
PATH = re.compile(PAGE + r"(?P<act>integrations(?:/(?:secret|test|hooks/(?:paste|remove)|"
                         r"webhooks/(?:add|remove|rotate|test)))?)$")
GETS = {"integrations"}
ADMIN = ("owner", "admin")
LOG_ROWS = 50
TEST_LIMIT, TEST_MINUTES = 3, 10        # webhook tests per user (each may wait 10 s)
TOOL_NAMES = {"lead": "Your site's server (lead)", "json": "Zapier, Make, n8n (json)",
              "calendly": "Calendly", "calcom": "Cal.com", "stripe": "Stripe",
              "typeform": "Typeform", "hubspot": "HubSpot"}
# Tools that sign with a secret they make themselves: it is pasted, never made here.
OWN_SECRET = ("stripe", "hubspot")
# Tools that take a secret you choose, or give their own: made here or pasted.
EITHER = ("calendly", "calcom", "typeform")
# lead and json carry Skald's own signature: made here only.
PASTED = re.compile(r"^[\x21-\x7e]{12,500}$")     # one line, no spaces


def match(path: str):
    path = path.split("?", 1)[0]
    if ".." in path:
        return None
    return PATH.match(path)


def is_integrations(path: str) -> bool:
    return match(path) is not None


class Ctx:
    def __init__(self, h, db, session, site, role, org, config, live_dir, config_path):
        self.h, self.db, self.session, self.site = h, db, session, site
        self.role, self.org, self.config = role, org, config or {}
        self.config_path = config_path
        self.uid = session["user_id"]
        self.install_admin = bool(session["install_admin"])
        self.folder = Path(live_dir) if live_dir is not None else \
            hooks_mod.history_folder(self.config, config_path)

    def ok(self, **body):
        return answer(self.h, 200, {"ok": True, **body})

    def no(self, code: int, error: str, **extra):
        return answer(self.h, code, {"ok": False, "error": error, **extra})

    def log(self, action: str, target: str, detail: str = "") -> None:
        auditlog.record(self.db, self.org["id"] if self.org else None, self.uid, action,
                        target, detail)


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
        session = sessions.resolve(db, auth_api.cookie_of(h.headers))
        if session is None:
            return answer(h, 401, {"ok": False, "error": "Sign in first."})
        if write and not csrf_ok(session, h.headers):
            return answer(h, 403, {"ok": False, "error": "The page is out of date. "
                                                         "Reload it and try again."})
        role, org = users.site_role(db, session["user_id"], m.group("site"))
        if role is None and not session["install_admin"]:
            return answer(h, 403, {"ok": False, "error": "You are not a member here."})
        c = Ctx(h, db, session, m.group("site"), role, org, config, live_dir, config_path)
        if not (role in ADMIN or c.install_admin):
            return c.no(403, "Integrations are for admins.", role=role)
        form = {}
        if write:
            form = read_json(h)
            if form is None:
                return None
        return ROUTES[act](c, form)
    finally:
        db.close()


# ------------------------------------------------------------ which sites

def install_sites(c: Ctx) -> dict[str, dict]:
    """{site: its config} for every site this install reports on."""
    return hooks_mod.site_configs(c.config, c.config_path)


def managed(c: Ctx) -> list[str]:
    """The sites the caller may set up integrations for."""
    names: set[str] = set()
    if c.install_admin:
        names |= set(install_sites(c))
        names |= {r[0] for r in c.db.execute("SELECT name FROM sites")}
    for org in users_orgs(c):
        if org.get("role") in ADMIN:
            names |= {r[0] for r in c.db.execute("SELECT name FROM sites WHERE org_id = ?",
                                                 (org["id"],))}
    return sorted(names)


def users_orgs(c: Ctx) -> list[dict]:
    from . import accounts
    return accounts.list_orgs(c.db, c.uid)


def _target(c: Ctx, form: dict) -> str | None:
    """The site a request is about (the form's or the query's `site`, else
    the page's), or None after answering 403."""
    asked = text(form, "site", 100) if form else ""
    asked = asked or auth_api.query(c.h.path).get("site") or c.site
    if asked not in managed(c):
        c.no(403, "You cannot set up integrations for that site.", site=asked)
        return None
    return asked


def _locked(c: Ctx, site: str) -> str | None:
    """Why the site's organisation cannot change things now (saas), or None."""
    from .accounts.orgs import org_of_site
    from .saas import limits
    org = org_of_site(c.db, site)
    return limits.read_only(c.db, org["id"] if org else None, c.config)


def _site_config(c: Ctx, site: str) -> dict:
    return install_sites(c).get(site) or c.config


def _origin(c: Ctx) -> str:
    """Where the tools reach this install: hooks.public_url, access.base_url,
    else this request's own host."""
    for got in (setting(c.config, "hooks", "public_url"), setting(c.config, "access",
                                                                  "base_url")):
        if got:
            return str(got).rstrip("/")
    proto = c.h.headers.get("X-Forwarded-Proto") or "https"
    return f"{proto}://{c.h.headers.get('Host') or 'localhost'}"


def _db(c: Ctx):
    """conversions.sqlite, opened (made when missing); the caller closes it."""
    return store.connect(store.path_for(c.config, c.folder))


# --------------------------------------------------------------- reading

def script(c: Ctx, site: str) -> dict:
    """The tag to copy and what its options do (docs/INTEGRATIONS.md)."""
    conf = _site_config(c, site)
    on = setting(conf, "beacon", "visitor_ids", False) in (True, "true")
    src = f"{_origin(c)}/traffic-js/skald.js"
    return {"tag": f'<script src="{src}" data-site="{site}" defer></script>',
            "src": src, "visitor_ids": on,
            "options": [
                {"attr": "data-consent", "value": "required",
                 "what": "send nothing and keep no ID until the page calls "
                         "skald('consent', true)"},
                {"attr": "data-share-subdomains", "value": "true",
                 "what": "keep the ID in a first-party cookie too, so www. and app. share it"},
                {"attr": "data-link-domains", "value": "",
                 "what": "other domains you own, comma separated: links to them carry the ID"},
                {"attr": "data-accept-id", "value": "true",
                 "what": "take a ?skv= ID a link from your other domains brought, and take it "
                         "out of the address (without it: only from a data-link-domains "
                         "referrer)"},
                {"attr": "data-endpoint", "value": "",
                 "what": "post somewhere else on the same origin (default /traffic-beacon)"}]}


def tools(c: Ctx, site: str, db) -> list[dict]:
    conf = _site_config(c, site)
    base = _origin(c)
    out = []
    for tool in TOOLS:
        try:
            value, where = secrets_store.find(conf, c.folder, site, tool)
            problem = None
        except secrets_store.Exposed:
            value, where, problem = None, "file", "secrets.json is not 0600; fix it on the server"
        out.append({"tool": tool, "name": TOOL_NAMES.get(tool, tool),
                    "url": f"{base}/traffic-hooks/{site}/{tool}",
                    "set": bool(value), "where": "env" if where.startswith("env") else where,
                    "env": where[4:] if where.startswith("env ") else None,
                    "rotatable": not where.startswith("env"), "problem": problem,
                    "make": tool not in OWN_SECRET, "paste": tool in OWN_SECRET + EITHER,
                    "secret_from": TOOL_NAMES.get(tool, tool),
                    "deliveries": store.deliveries(db, site, tool, LOG_ROWS) if db else []})
    return out


def overview(c: Ctx, form):
    site = _target(c, form)
    if site is None:
        return None
    path = store.path_for(c.config, c.folder)
    db = store.connect(path) if path is not None and Path(path).exists() else None
    try:
        hooks_on = site in install_sites(c)
        return c.ok(site=site, sites=managed(c), install_admin=c.install_admin,
                    script=script(c, site), takes_hooks=hooks_on,
                    tools=tools(c, site, db), events=list(outgoing.EVENTS),
                    webhooks=outgoing.listing(db, site) if db else [],
                    locked=_locked(c, site))
    finally:
        if db is not None:
            db.close()


# --------------------------------------------------------------- changes

def _change_target(c: Ctx, form) -> str | None:
    site = _target(c, form)
    if site is None:
        return None
    why = _locked(c, site)
    if why:
        c.no(402, why, read_only=True)
        return None
    return site


def _tool(c: Ctx, form) -> str | None:
    tool = text(form, "tool", 20)
    if tool not in TOOLS:
        c.no(400, f"Name one of the tools: {', '.join(TOOLS)}.")
        return None
    return tool


def secret(c: Ctx, form):
    site = _change_target(c, form)
    if site is None:
        return None
    tool = _tool(c, form)
    if tool is None:
        return None
    env = secrets_store.env_name(_site_config(c, site), site, tool)
    if env:
        return c.no(409, f"This hook's secret is read from the server's environment ({env}); "
                         "change it there.")
    if tool in OWN_SECRET:
        name = TOOL_NAMES[tool]
        return c.no(409, f"{name} signs with a secret it makes itself. Paste the signing "
                         f"secret from {name} instead.")
    path = secrets_store.path_for(c.config, c.folder)
    try:
        had = bool(secrets_store.load(path).get(secrets_store.key(site, tool)))
    except secrets_store.Exposed as why:
        return c.no(500, f"{why}. Fix it on the server first.")
    value = secrets_store.make()
    secrets_store.put(path, secrets_store.key(site, tool), value)
    c.log("hook.secret", f"{site}/{tool}", "rotated" if had else "made")
    return c.ok(site=site, tool=tool, secret=value, rotated=had,
                url=f"{_origin(c)}/traffic-hooks/{site}/{tool}")


def _hook_change(c: Ctx, form):
    """(site, tool, secrets.json path, had a secret) for a change to a hook's
    secret on the page, or None after answering."""
    site = _change_target(c, form)
    tool = None if site is None else _tool(c, form)
    if tool is None:
        return None
    env = secrets_store.env_name(_site_config(c, site), site, tool)
    if env:
        c.no(409, f"This hook's secret is read from the server's environment ({env}); "
                  "change it there.")
        return None
    path = secrets_store.path_for(c.config, c.folder)
    try:
        had = bool(secrets_store.load(path).get(secrets_store.key(site, tool)))
    except secrets_store.Exposed as why:
        c.no(500, f"{why}. Fix it on the server first.")
        return None
    return site, tool, path, had


def paste(c: Ctx, form):
    """The signing secret a tool made (Stripe's whsec_..., HubSpot's client
    secret), typed in once: kept 0600, never sent back, never logged."""
    got = _hook_change(c, form)
    if got is None:
        return None
    site, tool, path, had = got
    if tool not in OWN_SECRET + EITHER:
        return c.no(400, "Skald signs this hook itself: use Make secret.")
    value = form.get("secret")
    value = value.strip() if isinstance(value, str) else ""
    name = TOOL_NAMES[tool]
    if not PASTED.match(value):
        return c.no(400, f"Paste the signing secret from {name}: one line, no spaces, "
                         "12 to 500 characters.")
    if tool == "stripe" and not value.startswith("whsec_"):
        return c.no(400, "A Stripe signing secret starts with whsec_. Copy it from the "
                         "endpoint in Stripe (Developers > Webhooks).")
    secrets_store.put(path, secrets_store.key(site, tool), value)
    c.log("hook.secret", f"{site}/{tool}", "pasted, replaced" if had else "pasted")
    return c.ok(site=site, tool=tool, replaced=had,
                url=f"{_origin(c)}/traffic-hooks/{site}/{tool}")


def remove(c: Ctx, form):
    """Delete a hook's secret: further deliveries are refused (404, as for a
    hook never set up). Its deliveries and its conversions stay."""
    got = _hook_change(c, form)
    if got is None:
        return None
    site, tool, path, had = got
    if not had:
        return c.no(404, "This hook has no secret to remove.")
    secrets_store.delete(path, [secrets_store.key(site, tool)])
    c.log("hook.remove", f"{site}/{tool}", "secret deleted")
    return c.ok(site=site, tool=tool, removed=True)


def test(c: Ctx, form):
    site = _target(c, form)
    if site is None:
        return None
    tool = _tool(c, form)
    if tool is None:
        return None
    if site not in install_sites(c):
        return c.no(409, "This install does not take hooks for that site yet.")
    try:
        value, _ = secrets_store.find(_site_config(c, site), c.folder, site, tool)
    except secrets_store.Exposed as why:
        return c.no(500, f"{why}. Fix it on the server first.")
    if not value:
        return c.no(409, "Make the hook's secret first.")
    mod = adapter(tool)
    now = time.time()
    uri = f"{_origin(c)}/traffic-hooks/{site}/{tool}"
    body = json.dumps(mod.sample(site, now)).encode()
    headers = {k.lower(): v for k, v in mod.sign(body, value, now, "POST", uri).items()}
    headers.update({"content-type": "application/json", "x-skald-test": "1",
                    ":method": "POST", ":uri": uri})
    receiver = hooks_mod.receiver(c.config, c.folder, c.config_path)
    status, got = receiver.process(site, tool, headers, body, value)
    c.log("hook.test", f"{site}/{tool}", f"{status}")
    return c.ok(site=site, tool=tool, status=status, answer=got)


def _wid(c: Ctx, form) -> int | None:
    try:
        return int(form.get("id"))
    except (TypeError, ValueError):
        c.no(400, "Name the webhook by its id.")
        return None


def webhook_add(c: Ctx, form):
    site = _change_target(c, form)
    if site is None:
        return None
    db = _db(c)
    try:
        hook, value = outgoing.add(db, c.config, c.folder, site, form.get("url"),
                                   form.get("events"), c.session["email"])
    except outgoing.Refused as why:
        return c.no(400, str(why))
    except secrets_store.Exposed as why:
        return c.no(500, f"{why}. Fix it on the server first.")
    finally:
        db.close()
    c.log("webhook.add", f"{site} #{hook['id']}", f"{_host(hook['url'])} "
                                                  f"[{','.join(hook['events'])}]")
    return c.ok(site=site, webhook=hook, secret=value)


def webhook_remove(c: Ctx, form):
    site = _change_target(c, form)
    wid = None if site is None else _wid(c, form)
    if wid is None:
        return None
    db = _db(c)
    try:
        hook = outgoing.webhook(db, site, wid)
        gone = outgoing.remove(db, c.config, c.folder, site, wid)
    finally:
        db.close()
    if not gone:
        return c.no(404, "There is no such webhook.")
    c.log("webhook.remove", f"{site} #{wid}", _host(hook["url"]))
    return c.ok(site=site, removed=wid)


def webhook_rotate(c: Ctx, form):
    site = _change_target(c, form)
    wid = None if site is None else _wid(c, form)
    if wid is None:
        return None
    db = _db(c)
    try:
        hook = outgoing.webhook(db, site, wid)
    finally:
        db.close()
    if hook is None:
        return c.no(404, "There is no such webhook.")
    try:
        value = outgoing.rotate(c.config, c.folder, site, wid)
    except secrets_store.Exposed as why:
        return c.no(500, f"{why}. Fix it on the server first.")
    c.log("webhook.rotate", f"{site} #{wid}")
    return c.ok(site=site, id=wid, secret=value)


def _host(url: str) -> str:
    """Only the host of a webhook's address for the audit log: its path or
    query often carries the receiver's token."""
    try:
        return (urlsplit(str(url)).hostname or "?")[:200]
    except ValueError:
        return "?"


def webhook_test(c: Ctx, form):
    site = _target(c, form)
    wid = None if site is None else _wid(c, form)
    if wid is None:
        return None
    from .accounts import db as base, limits
    key = f"webhooktest:{c.uid}"
    with base.tx(c.db):             # a test waits on the receiver: few of them
        if limits.count(c.db, key, TEST_MINUTES) >= TEST_LIMIT:
            return answer(c.h, 429, {"ok": False, "error": f"At most {TEST_LIMIT} webhook "
                                     f"tests in {TEST_MINUTES} minutes. Try again later."},
                          {"Retry-After": str(TEST_MINUTES * 60)})
        limits.note_failure(c.db, key)
    db = _db(c)
    try:
        got = outgoing.test(db, c.config, c.folder, site, wid)
    finally:
        db.close()
    if got is None:
        return c.no(404, "There is no such webhook.")
    c.log("webhook.test", f"{site} #{wid}", got["state"])
    return c.ok(site=site, id=wid, result=got)


ROUTES = {"integrations": overview, "integrations/secret": secret, "integrations/test": test,
          "integrations/hooks/paste": paste, "integrations/hooks/remove": remove,
          "integrations/webhooks/add": webhook_add, "integrations/webhooks/remove": webhook_remove,
          "integrations/webhooks/rotate": webhook_rotate,
          "integrations/webhooks/test": webhook_test}
