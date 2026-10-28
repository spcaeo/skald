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
  A site's row menu (site_actions_api.py, site_lifecycle.py), for a site made
  here and a config-file site alike; the install's main site can only be paused:
  POST sites/pause     {name}: stop collecting and counting; ingest
                       answers 503 so the shipper keeps its lines; the runs
                       skip it; everything is kept                    admin
  POST sites/resume    {name} -> the days paused, and whether the log can
                       still fill them ("words")                      admin
  POST sites/remove    {name, confirm: name}: stop processing, hide it;
                       the data stays                                 owner
  POST sites/restore   {name}: undo remove                            owner
  POST sites/clear     {name, confirm: name, understood: true}: archive,
                       then delete its collected data; settings and tokens
                       stay -> {archive}                              owner
  POST sites/purge     {name, confirm: name, understood: true}: "Delete all
                       data": archive, then delete every store, revoke its
                       tokens -> {archive, status: deleted|removed}   owner
                       (rate limits: site_actions_api.py)
  POST sites/verify    {name}: look for the site's verification token (DNS
                       TXT or the home page's meta tag, site_verify.py)  admin
  GET  sites/status, POST sites/kit, POST sites/setup, POST sites/detect,
  POST sites/tagcheck, POST sites/trylog: Settings > Data and the
                       "Add a site" wizard (connections_api.py; detect: the
                       site check; tagcheck: the script tag's page check;
                       trylog: Test a sample, the dry run of a pasted log
                       sample, try_log.py; its body may be up to
                       try_log.WEB_BYTES + 4 KiB)                      admin
  POST sites/share, GET sites/shares, POST sites/unshare: "Share with your
                       developer" links (share_api.py)                 admin
  POST sites/link, POST sites/pack, POST sites/packmail: the one-command
                       install link and the set-up pack, downloaded or
                       mailed (kit_api.py)                             admin
  POST sites/agentlink, sites/agentstatus, sites/agentcancel: the one line
                       for an AI agent, how far its agent got, and ending
                       it at once (kit_api.py, kit/agent.py)            admin
  GET  sites/agentleft  every site's open set-up lines, the jobs an agent can
                       do and its newest line: "Lines for your sites", one
                       line per site (kit_left.py)                     admin

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
Sites from config files are listed; their config is changed only on the
server, but they can be paused, removed, cleared and deleted here.

2.44: the adding itself is site_add.py, shared with the MCP's add_site; it
also checks the plan's members for the people a new site names.

2.43 (setup_live.py, setup_people.py): POST sites/live, sites/check,
sites/sendinvites, sites/whofor and GET sites/whoopts (2.44: POST sites/arrived,
connect_check.py, the Test beside every line, command and address Skald gives); sites/add takes the
wizard's first two answers, {org: "same" | <id> | "new", org_name,
privacy_class, people}. A request that names a site of another of the
caller's organisations (`site` or `name` in the body; `?site=` on a GET) is
answered for that site's organisation, with the caller's role there, so the
wizard goes on for a site it just put in another organisation.
"""
from __future__ import annotations

import re
from pathlib import Path

from . import auth_api, ingest, ingest_log, site_verify
from .accounts import apitokens, sessions, site_configs, users
from .auth_api import answer, csrf_ok, read_json, text
from .config import site_name

PAGE = r"^/traffic/(?P<site>[a-z0-9.-]+)/(?:(?P<view>[a-z0-9-]+)/)?"
PATH = re.compile(PAGE + r"(?P<act>sites(?:/(?:add|token|remove|verify|status|kit|setup|detect|tagcheck|trylog"
                         r"|pause|resume|restore|clear|purge"
                         r"|share|shares|unshare|link|pack|packmail"
                         r"|agentlink|agentstatus|agentcancel|agentleft"
                         r"|live|check|sendinvites|whoopts|whofor|arrived))?)$")
GETS = ("sites", "sites/status", "sites/shares", "sites/agentleft", "sites/whoopts")
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
        form = {}
        if write:
            from .try_log import WEB_BYTES
            form = read_json(h, WEB_BYTES + auth_api.MAX_BODY if act == "sites/trylog"
                             else auth_api.MAX_BODY)
            if form is None:
                return None
        role, org = _named(db, session["user_id"], h.path, form, m.group("site"), role, org)
        c = Ctx(h, db, session, m.group("site"), role, org, config or {}, live_dir, allowed,
                config_path, out)
        from .site_actions_api import OWNER_ONLY
        if act in OWNER_ONLY and role != "owner":
            return c.no(403, OWNER_ONLY[act], role=role)
        if write and role not in ADMIN:
            return c.no(403, "Only an admin can do this.", role=role)
        if write:
            frozen = read_only(db, c.config, org["id"])
            if frozen:
                return c.no(402, frozen)
        return ROUTES[act](c, form)
    finally:
        db.close()


def _named(db, uid, path: str, form: dict, page: str, role, org):
    """(role, org) for the site the request names when it is one of another
    organisation the caller is a member of (2.43); else the page site's."""
    from .auth_api import query
    named = form.get("site") or form.get("name") if form else query(path).get("site")
    if not isinstance(named, str) or not named or named == page:
        return role, org
    there, other = users.site_role(db, uid, named)
    if there is None or other is None or other["id"] == org["id"]:
        return role, org
    return there, other


def _refusal(c: Ctx) -> str | None:
    from .site_add import refusal
    return refusal(c.db, c.config, c.org["id"], c.role)


def listing(c: Ctx, form):
    from .accounts import orgs
    names = orgs.sites_of_org(c.db, c.org["id"])
    rows = {r["name"]: r for r in site_configs.listing(c.db, c.org["id"])}
    root = c.ingest_root()
    from .accounts import site_state
    states = site_state.every(c.db)
    main = site_name(c.config)
    out = []
    for name in sorted(set(names) | set(rows)):
        row = rows.get(name)
        st = states.get(name) or {}
        gone = (row["removed_at"] if row else None) or st.get("removed_at")
        folder = ingest_log.site_folder(root, name)
        entry = {"name": name, "source": "dashboard" if row else "config",
                 "status": "removed" if gone else "paused" if st.get("paused_at") else "active",
                 "main": name == main and row is None,
                 "paused_at": st.get("paused_at"), "cleared_at": st.get("cleared_at"),
                 "format": row["format"] if row else None,
                 "hosts": row["hosts"] if row else None,
                 "created_at": row["created_at"] if row else None,
                 "removed_at": gone,
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


def _new_token(c: Ctx, name: str, org_id=None) -> str:
    return apitokens.create(c.db, org_id or c.org["id"], f"Log shipper for {name}"[:60], sites=[name],
                            scopes=("ingest",), actor=c.uid)


def add(c: Ctx, form):
    """POST sites/add: site_add.add, the one code path (the MCP's add_site too)."""
    from . import site_add
    try:
        got = site_add.add(c.db, c.config, c.org, c.uid, form, live_dir=c.live_dir,
                           config_path=c.config_path, allowed=c.allowed, out=c.out,
                           origin=_tag_base(c), role=c.role,
                           install_admin=bool((c.session or {}).get("install_admin")))
    except site_add.Refused as why:
        return c.no(why.status, str(why))
    return c.ok(**got)


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


def _left(c, form):
    from .kit_left import agent_left
    return agent_left(c, form)


def _lifecycle():
    from .site_actions_api import ROUTES as acts
    return acts


ROUTES = {"sites": listing, "sites/add": add, "sites/token": new_token, **_lifecycle(),
          "sites/verify": verify, "sites/status": _more("status"), "sites/kit": _more("kit_zip"),
          "sites/setup": _more("setup"), "sites/detect": _more("detect"),
          "sites/tagcheck": _more("tag_check"), "sites/trylog": _more("try_sample"),
          "sites/link": _kit("link"), "sites/pack": _kit("pack_zip"),
          "sites/packmail": _kit("pack_mail"),
          "sites/agentlink": _kit("agent_link"), "sites/agentstatus": _kit("agent_status"),
          "sites/agentcancel": _kit("agent_cancel"), "sites/agentleft": _left,
          "sites/share": _share("share"),
          "sites/shares": _share("shares"), "sites/unshare": _share("unshare")}


def _live():
    from .setup_live import ROUTES as live
    return live


ROUTES.update(_live())          # 2.43: sites/live, check, sendinvites, whoopts, whofor


def _arrived():
    from .connect_check import ROUTES as arrived
    return arrived


ROUTES.update(_arrived())       # 2.44: sites/arrived, every connect journey's Test
