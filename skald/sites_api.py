"""Settings > Sites: adding and removing sites from the dashboard.

Served by the refresh helper for every site page, `/traffic/<site>/[<view>/]`,
with `access.mode: sessions` (404 otherwise), the way team_api.py is:

  GET  sites           the organisation's sites: where each is defined (config
                       file or dashboard), active or removed, its log format
                       and what the ingest endpoint has received; whether the
                       caller may add one (and why not)
  POST sites/add       {host, timezone?, format?, token?, hosts?, asset_prefixes?}
                       -> the site, an ingest token (shown once), the shipper  admin
                          command and the skald.js tag (with token: false, no
                          token: the wizard makes a named one later). hosts:
                          its host names (site_config); asset_prefixes: its
                          Settings > Sites > Page assets (the site's
                          site.asset_prefixes setting), both checked as
                          Settings checks them: the site check's suggestions
  POST sites/token     {name}: a new ingest token for a site          admin
  POST sites/remove    {name, confirm: name}                          owner
                       stops processing; the data stays until an install
                       admin runs `skald site purge <name>`
  POST sites/verify    {name}: look for the site's verification token (DNS
                       TXT or the home page's meta tag, site_verify.py)  admin
  GET  sites/status, POST sites/kit, POST sites/setup, POST sites/detect,
  POST sites/tagcheck: Settings > Connections and the "Add a site" wizard
                       (connections_api.py; detect: the site check;
                       tagcheck: the script tag's page check)          admin
  POST sites/share, GET sites/shares, POST sites/unshare: "Share with your
                       developer" links (share_api.py)                 admin
  POST sites/link, POST sites/pack, POST sites/packmail: the one-command
                       install link and the set-up pack, downloaded or
                       mailed (kit_api.py)                             admin
  POST sites/agentlink, sites/agentstatus, sites/agentcancel: the one line
                       for an AI agent, how far its agent got, and ending
                       it at once (kit_api.py, kit/agent.py)            admin

With saas on, a site added here starts "pending" (site_verify.py): nothing is
collected for it until its domain is verified; the listing shows the token.
A new site gets a "Getting ready" page at once and its first build on a
thread (first_page.py), so its page is never nginx's 404; the same thread asks
the site for its logo first (2.25), so the switcher shows it, not its letter.

"admin" means an owner or admin of the page site's organisation; the new
site joins that organisation. Adding needs `ingest: {enabled: true}` (the
site's log comes in through /traffic-ingest/, ingest.py) and, when
skald.saas.limits exists, the plan's yes (`can_add_site`); a plan
that is read-only (`read_only`: cancelled, long unpaid) refuses every POST
with 402 and the reason. Every
POST needs the same-origin check and the session's X-Skald-CSRF value.
Sites from config files are listed but changed only on the server.
"""
from __future__ import annotations

import re
from pathlib import Path

from . import auth_api, first_page, ingest, ingest_log, site_verify
from .accounts import apitokens, sessions, site_configs, users
from .auth_api import answer, csrf_ok, read_json, text
from .config import site_name

PAGE = r"^/traffic/(?P<site>[a-z0-9.-]+)/(?:(?P<view>[a-z0-9-]+)/)?"
PATH = re.compile(PAGE + r"(?P<act>sites(?:/(?:add|token|remove|verify|status|kit|setup|detect|tagcheck"
                         r"|share|shares|unshare|link|pack|packmail"
                         r"|agentlink|agentstatus|agentcancel))?)$")
GETS = ("sites", "sites/status", "sites/shares")
ADMIN = ("owner", "admin")
SHIP_TOKEN_FILE = "/etc/skald-ship/token"
VERIFY_PER_HOUR = 10       # checks a site may ask for (each a DNS query and a fetch)


def match(path: str):
    path = path.split("?", 1)[0]
    if ".." in path:
        return None
    return PATH.match(path)


def is_sites(path: str) -> bool:
    return match(path) is not None


def config_sites(config, config_path) -> list[str]:
    """The names of the sites config files define (never dashboard rows)."""
    from . import multisite
    names = [site_name(config or {})]
    if config_path is not None and (config or {}).get("sites"):
        try:
            for got in multisite.site_configs({**config}, Path(config_path)):
                if not got.get("_dashboard_site"):
                    names.append(site_name(got))
        except SystemExit:
            pass
    return names


def _plan(name: str, db, config, org_id):
    """(True, the answer) of skald.saas.limits.<name>(db, org_id,
    config), or (False, None) when that module or function is absent."""
    try:
        from .saas import limits as plan
    except ImportError:
        return False, None
    fn = getattr(plan, name, None)
    if fn is None:
        return False, None
    import inspect
    given = {"db": db, "config": config, "org_id": org_id}
    names = inspect.signature(fn).parameters
    takes_all = any(p.kind is p.VAR_KEYWORD for p in names.values())
    return True, fn(**(given if takes_all else {k: v for k, v in given.items() if k in names}))


def read_only(db, config, org_id) -> str | None:
    """Why the organisation cannot change anything now (saas.limits.read_only:
    a cancelled or long unpaid plan), or None."""
    try:
        found, got = _plan("read_only", db, config, org_id)
    except Exception as why:              # noqa: BLE001 - a broken check refuses
        return f"The plan could not be checked ({type(why).__name__})."
    return str(got) if found and got else None


def plan_allows(db, config, org_id) -> str | None:
    """None, or the plan's reason not to add a site: saas.limits.can_add_site
    (db, org_id, config) when that module exists, answering (ok, reason),
    True/None (yes), False or a reason."""
    try:
        found, got = _plan("can_add_site", db, config, org_id)
    except Exception as why:              # noqa: BLE001 - a broken check refuses
        return f"The plan's limits could not be checked ({type(why).__name__})."
    if not found:
        return None
    if isinstance(got, (tuple, list)) and got:
        return None if got[0] else (str(got[1]) if len(got) > 1 and got[1]
                                    else "Your plan does not allow another site.")
    if got is False:
        return "Your plan does not allow another site."
    if isinstance(got, str) and got:
        return got
    return None


def _base(config, allowed) -> str:
    raw = ((config or {}).get("ingest") or {}).get("url") or auth_api.base_url(config, allowed)
    return str(raw or "https://<this server>").rstrip("/")


def _tag_base(c) -> str:
    from .integrations_api import _origin
    return _origin(c)


def ship_command(config, allowed, site: str) -> str:
    return (f"skald-ship --url {_base(config, allowed)}{ingest.PREFIX}{site} "
            f"--token-file {SHIP_TOKEN_FILE} --log /var/log/nginx/access.log")


def tag(site: str, base: str = "") -> str:
    # The path the beacon helper serves the tag on (beacon_server.SNIPPET_PATH),
    # on this install's address (integrations_api._origin): the page loads it
    # from here and posts its events here too. No change on the site's server.
    return f'<script src="{base}/traffic-js/skald.js" data-site="{site}" defer></script>'


class Ctx:
    def __init__(self, h, db, session, site, role, org, config, live_dir, allowed, config_path,
                 out=None):
        self.h, self.db, self.session, self.site = h, db, session, site
        self.role, self.org, self.config, self.live_dir = role, org, config, live_dir
        self.allowed, self.config_path, self.out = allowed, config_path, out
        self.uid = session["user_id"]

    def ok(self, **body):
        return answer(self.h, 200, {"ok": True, **body})

    def no(self, code: int, error: str, **extra):
        return answer(self.h, code, {"ok": False, "error": error, **extra})

    def ingest_root(self) -> Path:
        return ingest_log.root(self.config, ingest.history_folder(self.config, self.live_dir))


def handle(h, write: bool, config, live_dir, allowed: set[str], same_origin,
           config_path=None, out=None) -> None:
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
        if role is None:
            return answer(h, 403, {"ok": False, "error": "You are not a member here."})
        c = Ctx(h, db, session, m.group("site"), role, org, config or {}, live_dir, allowed,
                config_path, out)
        if act == "sites/remove" and role != "owner":
            return c.no(403, "Only an owner can remove a site.", role=role)
        if write and role not in ADMIN:
            return c.no(403, "Only an admin can do this.", role=role)
        if write:
            frozen = read_only(db, c.config, org["id"])
            if frozen:
                return c.no(402, frozen)
        form = {}
        if write:
            form = read_json(h)
            if form is None:
                return None
        return ROUTES[act](c, form)
    finally:
        db.close()


def _refusal(c: Ctx) -> str | None:
    if c.role not in ADMIN:
        return "Only an admin can add a site."
    if not ingest.enabled(c.config):
        return ("Adding sites here needs the log endpoint switched on "
                "(ingest.enabled in the server's config).")
    return plan_allows(c.db, c.config, c.org["id"])


def listing(c: Ctx, form):
    from .accounts import orgs
    names = orgs.sites_of_org(c.db, c.org["id"])
    rows = {r["name"]: r for r in site_configs.listing(c.db, c.org["id"])}
    root = c.ingest_root()
    out = []
    for name in sorted(set(names) | set(rows)):
        row = rows.get(name)
        folder = ingest_log.site_folder(root, name)
        entry = {"name": name, "source": "dashboard" if row else "config",
                 "status": "active" if (row is None or row["active"]) else "removed",
                 "format": row["format"] if row else None,
                 "hosts": row["hosts"] if row else None,
                 "created_at": row["created_at"] if row else None,
                 "removed_at": row["removed_at"] if row else None,
                 "ingest": ingest_log.summary(folder) if folder.is_dir() else None,
                 "verify": site_verify.shown(c.db, name)}
        out.append(entry)
    refusal = _refusal(c)
    from . import connections_api
    more = connections_api.extras(c, [s["name"] for s in out]) if c.role in ADMIN else {}
    for entry in out:
        entry.update((more.get("progress") or {}).get(entry["name"]) or {})
    more.pop("progress", None)
    return c.ok(org=c.org["name"], role=c.role, sites=out, can_add=refusal is None,
                add_refused=refusal, formats=list(site_configs.FORMATS),
                ingest_enabled=ingest.enabled(c.config),
                ingest_url=f"{_base(c.config, c.allowed)}{ingest.PREFIX}", **more)


def _new_token(c: Ctx, name: str) -> str:
    return apitokens.create(c.db, c.org["id"], f"Log shipper for {name}"[:60], sites=[name],
                            scopes=("ingest",), actor=c.uid)


def add(c: Ctx, form):
    refusal = _refusal(c)
    if refusal:
        return c.no(403, refusal)
    from . import settings_store
    from .accounts import db as base
    try:
        name = site_configs.clean_name(text(form, "host", 200))
        folder = ingest_log.site_folder(c.ingest_root(), name)
        assets = form.get("asset_prefixes") or None
        if assets is not None:
            try:
                assets = settings_store.validate("site.asset_prefixes", assets)
            except settings_store.Invalid as why:
                raise ValueError(str(why)) from None
        with base.tx(c.db):
            site_configs.create(
                c.db, c.org["id"], name, c.uid, hosts=form.get("hosts") or None,
                timezone=text(form, "timezone", 64) or None,
                fmt=text(form, "format", 40) or "auto", log_dir=str(folder),
                taken=config_sites(c.config, c.config_path))
            token = _new_token(c, name) if form.get("token") is not False else None
            if assets:
                settings_store.put(c.db, f"site:{name}", "site.asset_prefixes", assets, c.uid)
            if saas_on(c.config):
                site_verify.start(c.db, name)
    except ValueError as why:
        return c.no(400, str(why))
    folder.mkdir(parents=True, exist_ok=True)
    # Its page is there at once, not a 404; its logo is asked for first (2.25).
    first_page.start(c.out, name, c.config_path,
                     before=first_page.logo_fetch(c.config, c.config_path, name, c.live_dir, c.out))
    return c.ok(site=name, token=token, log_dir=str(folder),
                ingest_url=f"{_base(c.config, c.allowed)}{ingest.PREFIX}{name}",
                ship_command=ship_command(c.config, c.allowed, name), tag=tag(name, _tag_base(c)),
                token_file=SHIP_TOKEN_FILE, verify=site_verify.shown(c.db, name))


def new_token(c: Ctx, form):
    from .accounts import orgs
    name = text(form, "name", 200)
    if name not in orgs.sites_of_org(c.db, c.org["id"]):
        return c.no(404, "There is no such site in this organisation.")
    row = site_configs.get(c.db, name)
    if row is not None and not row["active"]:
        return c.no(400, f"{name} is removed.")
    try:
        token = _new_token(c, name)
    except ValueError as why:
        return c.no(400, str(why))
    return c.ok(site=name, token=token, ship_command=ship_command(c.config, c.allowed, name),
                token_file=SHIP_TOKEN_FILE)


def remove(c: Ctx, form):
    name = text(form, "name", 200)
    row = site_configs.get(c.db, name)
    if row is None or row["org_id"] != c.org["id"]:
        from .accounts import orgs
        if name in orgs.sites_of_org(c.db, c.org["id"]):
            return c.no(400, "This site is defined in the server's config files; "
                             "it is removed there.")
        return c.no(404, "There is no such site in this organisation.")
    if text(form, "confirm", 200) != name:
        return c.no(400, f"Type the site name, {name}, to confirm.")
    try:
        site_configs.remove(c.db, c.org["id"], name, c.uid)
    except ValueError as why:
        return c.no(400, str(why))
    return c.ok(site=name, status="removed")


def verify(c: Ctx, form):
    from .accounts import limits, orgs
    name = text(form, "name", 200)
    if name not in orgs.sites_of_org(c.db, c.org["id"]):
        return c.no(404, "There is no such site in this organisation.")
    key = f"site-verify:{name}"
    if limits.too_many(c.db, key, limit=VERIFY_PER_HOUR, minutes=60):
        return c.no(429, "Too many checks for this site. Try again in an hour.")
    limits.note_failure(c.db, key)
    got = site_verify.check(c.db, name, c.config, c.uid)
    if not got["verified"]:
        return c.no(400, got["error"], verified=False)
    return c.ok(site=name, verified=True, method=got["method"])


def saas_on(config) -> bool:
    from .saas import enabled
    return enabled(config)


def _share(name):
    def call(c, form):
        from . import share_api
        return getattr(share_api, name)(c, form)
    return call


def _kit(name):
    def call(c, form):
        from . import kit_api
        return getattr(kit_api, name)(c, form)
    return call


def _more(name):
    def call(c, form):
        from . import connections_api
        return getattr(connections_api, name)(c, form)
    return call


ROUTES = {"sites": listing, "sites/add": add, "sites/token": new_token, "sites/remove": remove,
          "sites/verify": verify, "sites/status": _more("status"), "sites/kit": _more("kit_zip"),
          "sites/setup": _more("setup"), "sites/detect": _more("detect"),
          "sites/tagcheck": _more("tag_check"),
          "sites/link": _kit("link"), "sites/pack": _kit("pack_zip"),
          "sites/packmail": _kit("pack_mail"),
          "sites/agentlink": _kit("agent_link"), "sites/agentstatus": _kit("agent_status"),
          "sites/agentcancel": _kit("agent_cancel"),
          "sites/share": _share("share"),
          "sites/shares": _share("shares"), "sites/unshare": _share("unshare")}
