"""Settings > Organisation > Organisations, with `access.mode: sessions`.

Served by the refresh helper (refresh_server.py) for every site page,
/traffic/<site>/[<view>/]orgs..., behind nginx's session check. The page's
site only proves the caller may open the dashboard; each route names the
organisation it acts on (`org`, its id: opaque, never a name or an email),
so an organisation with no site yet can be managed too.

  GET  orgs                      {orgs: [cards], install_admin, current}
  GET  orgs/show?org=ID          one organisation: overview, sites, members,
                                 invites, settings, keys, what the reader may do
  GET  orgs/auditlog?org=ID&limit=  its audit rows                    admin
  POST orgs/create               name, privacy_class, owner ("me" or an email),
                                 sites                         install admin
  POST orgs/rename               org, name                            admin
  POST orgs/privacy              org, privacy_class (internal|client)  install admin
  POST orgs/archive | restore    org: its sites paused (resumed); nothing deleted  owner
  POST orgs/move-site            org, site: moved in, keys with it   admin of both
  POST orgs/transfer             org, user: they become an owner, you an admin  owner
  POST orgs/leave                org: you leave (never the last owner)
  POST orgs/prefs                org, require_totp (owner), mail_daily (admin)
  POST orgs/member/invite        org, email, role, sites?             admin
  POST orgs/member/role | remove org, user (an id), role              admin
  POST orgs/member/sites         org, user, sites (a list, or null: every site)  admin
  POST orgs/invite/resend | cancel   org, email                       admin
  POST orgs/token-revoke         org, id                              admin

Who: a member reads their own organisations; an install admin reads and acts
on every one as an owner would. "admin" means owner or admin; only an owner
makes, changes or removes an owner, and an organisation always keeps one
enabled owner (accounts/users.py). Every POST needs the same-origin check and
the session's X-Skald-CSRF value; every change is one audit row. In basic
mode every route answers 404.
"""
from __future__ import annotations

import re

from . import auth_api
from .accounts import (apitokens, auditlog, invites, org_admin, orgs, sessions, site_state,
                       users)
from .auth_api import answer, csrf_ok, note, read_json, text

PAGE = r"^/traffic/(?P<site>[a-z0-9.-]+)/(?:(?P<view>[a-z0-9-]+)/)?"
PATH = re.compile(PAGE + r"(?P<act>orgs(?:/(?:show|create|rename|privacy|archive|restore"
                         r"|move-site|transfer|leave|prefs|token-revoke|auditlog"
                         r"|member/(?:invite|role|remove|sites)|invite/(?:resend|cancel)))?)$")
GETS = {"orgs", "orgs/show", "orgs/auditlog"}
RANK = {"viewer": 0, "admin": 1, "owner": 2}
NOT_YOURS = "There is no such organisation, or you are not a member of it."
LOCKED_ACTS = ("orgs/member/", "orgs/invite/", "orgs/token-revoke")


def match(path: str):
    path = path.split("?", 1)[0]
    if ".." in path:
        return None
    return PATH.match(path)


def is_orgs(path: str) -> bool:
    return match(path) is not None


class Ctx:
    def __init__(self, h, db, session, site, config, live_dir, allowed, history_path=None):
        self.h, self.db, self.session, self.site = h, db, session, site
        self.config, self.live_dir, self.allowed = config, live_dir, allowed
        self.history_path = history_path
        self.uid = session["user_id"]
        self.install_admin = bool(session["install_admin"])

    def ok(self, **body):
        return answer(self.h, 200, {"ok": True, **body})

    def no(self, code: int, error: str, **extra):
        return answer(self.h, code, {"ok": False, "error": error, **extra})


class Org:
    """The organisation a request acts on, with the reader's role in it and the
    role they act with (an install admin acts as an owner)."""

    def __init__(self, row: dict, role: str | None, acts: str):
        self.row, self.id, self.name = row, row["id"], row["name"]
        self.role, self.acts = role, acts

    def at_least(self, need: str) -> bool:
        return RANK.get(self.acts, -1) >= RANK[need]


def handle(h, write: bool, config, live_dir, allowed: set[str], same_origin,
           history_path=None) -> None:
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
        return _route(h, db, m, act, write, config, live_dir, allowed, history_path)
    finally:
        db.close()


def _route(h, db, m, act, write, config, live_dir, allowed, history_path=None):
    session = sessions.resolve(db, auth_api.cookie_of(h.headers))
    if session is None:
        return answer(h, 401, {"ok": False, "error": "Sign in first."})
    if write and not csrf_ok(session, h.headers):
        return answer(h, 403, {"ok": False, "error": "The page is out of date. "
                                                     "Reload it and try again."})
    # The page's own site: the caller must be able to open it (site access too).
    role, _org = users.site_role(db, session["user_id"], m.group("site"))
    if role is None:
        return answer(h, 403, {"ok": False, "error": "You are not a member here."})
    c = Ctx(h, db, session, m.group("site"), config, live_dir, allowed, history_path)
    form = auth_api.query(h.path)
    if write:
        form = read_json(h)
        if form is None:
            return None
    return ROUTES[act](c, form)


def _org(c: Ctx, form, need: str = "viewer") -> Org | None:
    """The organisation `form["org"]` names, when the caller may act on it with
    at least `need`; None after answering 404 or 403."""
    raw = form.get("org")
    oid = int(raw) if isinstance(raw, int) or (isinstance(raw, str) and raw.isdigit()) else None
    row = orgs.get_org(c.db, oid) if oid is not None else None
    role = users.role_in(c.db, c.uid, oid) if row is not None else None
    if row is None or (role is None and not c.install_admin):
        c.no(404, NOT_YOURS)
        return None
    org = Org(row, role, "owner" if c.install_admin else role)
    if not org.at_least(need):
        c.no(403, "Only an owner can do this." if need == "owner"
             else "Only an admin can do this.", role=role)
        return None
    return org


def _locked(c: Ctx, org: Org) -> bool:
    """saas: a payment overdue makes the team read-only (answered 402)."""
    from .saas import limits as saas_limits
    why = saas_limits.read_only(c.db, org.id, c.config)
    if why:
        c.no(402, why, read_only=True)
        return True
    return False


def _member(c: Ctx, org: Org, form) -> dict | None:
    """The member `form["user"]` (an id) names; None after answering 404."""
    raw = form.get("user")
    uid = int(raw) if isinstance(raw, int) or (isinstance(raw, str) and raw.isdigit()) else None
    user = users.find_user(c.db, user_id=uid) if uid is not None else None
    if user is None or users.role_in(c.db, uid, org.id) is None:
        c.no(404, "There is no such member.")
        return None
    return user


def _history(c: Ctx):
    from .saas import limits as saas_limits
    return c.history_path or saas_limits.history_path(c.config, c.live_dir)


# ------------------------------------------------------------------ reading

def _visible(c: Ctx, org_id: int, names: list[str]) -> list[str]:
    """The site names the reader may see: every one for an install admin."""
    if c.install_admin:
        return names
    mine = set(users.visible_sites(c.db, org_id, c.uid))
    return [n for n in names if n in mine]


def listing(c: Ctx, form):
    from .files import slug
    cards = org_admin.cards(c.db, c.uid, c.install_admin)
    for card in cards:
        card["sites"] = _visible(c, card["id"], card["sites"])
        # Where its Settings pages open (Switch): its first site's dashboard.
        card["path"] = f"{slug(card['sites'][0])}/" if card["sites"] else None
    current = orgs.org_of_site(c.db, c.site)
    return c.ok(orgs=cards, install_admin=c.install_admin,
                current=current["id"] if current else None, can_create=c.install_admin)


def _site_rows(c: Ctx, org_id: int, names: list[str]) -> list[dict]:
    from .accounts import site_configs
    from .files import slug
    out = []
    for name in names:
        state = site_state.get(c.db, name)
        try:
            row = site_configs.get(c.db, name)
        except Exception:                 # noqa: BLE001 - an older file: no dashboard sites
            row = None
        removed = state["removed_at"] or (row or {}).get("removed_at")
        out.append({"name": name, "path": f"{slug(name)}/",
                    "state": "removed" if removed else "paused" if state["paused_at"]
                    else "active"})
    return out


def _movable(c: Ctx, org: Org) -> list[dict]:
    """Sites of other organisations the caller may move here: every one for an
    install admin, else those of organisations they are an owner or admin of."""
    out = []
    for o in orgs.list_orgs(c.db) if c.install_admin else orgs.list_orgs(c.db, c.uid):
        if o["id"] == org.id or (not c.install_admin and o.get("role") not in ("owner", "admin")):
            continue
        for name in orgs.sites_of_org(c.db, o["id"]):
            if c.install_admin or users.sees(_limit_raw(c, o["id"]), name):
                out.append({"name": name, "org": o["name"], "org_id": o["id"]})
    return out


def _limit_raw(c: Ctx, org_id: int):
    row = c.db.execute("SELECT sites FROM members WHERE org_id = ? AND user_id = ?",
                       (org_id, c.uid)).fetchone()
    return row[0] if row is not None else None


def _settings(c: Ctx, org_id: int) -> dict:
    from .settings_api import org_setting
    daily = org_setting(c.db, org_id, "mail.daily")
    return {"require_totp": org_setting(c.db, org_id, "security.require_totp") is True,
            "session_days": org_setting(c.db, org_id, "security.session_days"),
            "mail_daily": True if daily is None else bool(daily)}


def show(c: Ctx, form):
    org = _org(c, form)
    if org is None:
        return None
    admin = org.at_least("admin")
    names = _visible(c, org.id, orgs.sites_of_org(c.db, org.id))
    card = org_admin.card(c.db, org.row, org.role)
    card["sites"] = names
    members = [{k: m[k] for k in ("id", "email", "name", "role", "sites", "added_at", "last_seen",
                                  "totp_on", "disabled_at", "has_password")}
               | {"me": m["id"] == c.uid} for m in users.members(c.db, org.id)]
    from .keep_everything import install_on
    may = {"rename": admin, "privacy": c.install_admin, "archive": org.at_least("owner"),
           "members": admin, "owners": org.at_least("owner"), "sites_access": admin,
           "settings_totp": org.at_least("owner"), "settings_mail": admin, "keys": admin,
           "audit": admin, "move": admin, "add_site": admin,
           "leave": org.role is not None, "transfer": org.role == "owner"}
    return c.ok(org=card, role=org.role, acts=org.acts, may=may,
                overview=org_admin.overview(c.db, org.id, _history(c)),
                sites=_site_rows(c, org.id, names), members=members,
                invites=invites.pending(c.db, org.id) if admin else [],
                settings=_settings(c, org.id),
                keys=[{k: v for k, v in t.items() if k != "org_id"}
                      for t in apitokens.listing(c.db, org.id)] if admin else [],
                movable=_movable(c, org) if admin else [],
                install_keeps=install_on(c.config))


def audit(c: Ctx, form):
    org = _org(c, form, "admin")
    if org is None:
        return None
    try:
        limit = max(1, min(int(form.get("limit") or 200), 1000))
    except ValueError:
        limit = 200
    return c.ok(entries=auditlog.recent(c.db, org.id, limit, form.get("action") or None))


# ------------------------------------------------------------- organisation

def create(c: Ctx, form):
    if not c.install_admin:
        return c.no(403, "Only an install admin can make an organisation.")
    cls = text(form, "privacy_class", 20) or "internal"
    if cls not in orgs.PRIVACY_CLASSES:
        return c.no(400, f"A privacy class is one of: {', '.join(orgs.PRIVACY_CLASSES)}.")
    sites = form.get("sites") or []
    if not (isinstance(sites, list) and all(isinstance(s, str) for s in sites)):
        return c.no(400, "sites is a list of site names.")
    owner = text(form, "owner", 300).strip().lower() or "me"
    if owner != "me":
        try:
            owner = users.clean_email(owner)
        except ValueError as why:
            return c.no(400, str(why))
    known = {r[0] for r in c.db.execute("SELECT name FROM sites")}
    unknown = [s for s in sites if s not in known]
    if unknown:
        return c.no(400, f"There is no such site here: {', '.join(unknown)}.")
    person = users.find_user(c.db, email=owner) if owner != "me" else None
    joins = owner == "me" or (person is not None and not person["disabled_at"])
    if sites and not joins:
        # A moved site's tokens keep working only under an owner or admin
        # (apitokens.creator_ok): nobody would be one until the invite is taken.
        return c.no(400, "Move sites in once the first owner has joined, or make yourself "
                         "the first owner.")
    extra = {}
    try:
        made = orgs.create_org(c.db, text(form, "name", 200), c.uid)
        if cls != "internal":
            orgs.set_privacy_class(c.db, made["id"], cls, c.uid)
        if joins:
            users.add_member(c.db, made["id"], c.uid if owner == "me" else person["id"],
                             "owner", c.uid)
        else:
            extra = _invite(c, made, owner, "owner", None)
        for site in sites:
            org_admin.move_site(c.db, site, made["id"], c.uid)
    except ValueError as why:
        return c.no(400, str(why))
    return c.ok(org=org_admin.card(c.db, orgs.get_org(c.db, made["id"]),
                                   users.role_in(c.db, c.uid, made["id"])), **extra)


def rename(c: Ctx, form):
    org = _org(c, form, "admin")
    if org is None:
        return None
    try:
        orgs.rename_org(c.db, org.id, text(form, "name", 200), c.uid)
    except ValueError as why:
        return c.no(400, str(why))
    return c.ok(name=orgs.get_org(c.db, org.id)["name"])


def privacy(c: Ctx, form):
    org = _org(c, form)
    if org is None:
        return None
    if not c.install_admin:
        return c.no(403, "Only an install admin can change the privacy class.")
    try:
        cls = orgs.set_privacy_class(c.db, org.id, text(form, "privacy_class", 20), c.uid)
    except ValueError as why:
        return c.no(400, str(why))
    return c.ok(privacy_class=cls)


def archive(c: Ctx, form):
    org = _org(c, form, "owner")
    if org is None:
        return None
    try:
        paused = orgs.archive_org(c.db, org.id, c.uid)
    except ValueError as why:
        return c.no(400, str(why))
    return c.ok(paused=paused)


def restore(c: Ctx, form):
    org = _org(c, form, "owner")
    if org is None:
        return None
    try:
        resumed = orgs.restore_org(c.db, org.id, c.uid)
    except ValueError as why:
        return c.no(400, str(why))
    return c.ok(resumed=resumed)


def move_site(c: Ctx, form):
    org = _org(c, form, "admin")
    if org is None:
        return None
    site = text(form, "site", 100).strip().lower()
    if site not in {s["name"] for s in _movable(c, org)}:
        return c.no(403, "You can move a site only from an organisation you are an owner or "
                         "admin of.", site=site)
    try:
        got = org_admin.move_site(c.db, site, org.id, c.uid)
    except ValueError as why:
        return c.no(400, str(why))
    return c.ok(**got)


def transfer(c: Ctx, form):
    org = _org(c, form, "owner")
    if org is None:
        return None
    user = _member(c, org, form)
    if user is None:
        return None
    try:
        org_admin.transfer_owner(c.db, org.id, c.uid, user["id"], c.uid)
    except ValueError as why:
        return c.no(400, str(why))
    return c.ok(user=user["id"])


def leave(c: Ctx, form):
    org = _org(c, form)
    if org is None:
        return None
    if org.role is None:
        return c.no(400, "You are not a member of this organisation.")
    try:
        org_admin.leave(c.db, org.id, c.uid)
    except ValueError as why:
        return c.no(400, str(why))
    return c.ok()


def settings(c: Ctx, form):
    from . import settings_store as store
    org = _org(c, form, "admin")
    if org is None:
        return None
    asked = {k: form[k] for k in ("require_totp", "mail_daily") if k in form}
    if not asked:
        return c.no(400, "Nothing to change.")
    if "require_totp" in asked and not org.at_least("owner"):
        return c.no(403, "Only an owner can change the sign-in rule.")
    if any(not isinstance(v, bool) for v in asked.values()):
        return c.no(400, "Each setting here is on (true) or off (false).")
    keys = {"require_totp": "security.require_totp", "mail_daily": "mail.daily"}
    try:
        for k, v in asked.items():
            store.put(c.db, f"org:{org.id}", keys[k], v, c.uid)
    except store.Invalid as why:
        return c.no(400, str(why))
    return c.ok(settings=_settings(c, org.id))


# ------------------------------------------------------------------ members

def _invite(c: Ctx, org_row: dict, email: str, role: str, sites) -> dict:
    """Make the invite and mail it, or hand its link back. Raises ValueError."""
    from .accounts import mails
    token = invites.invite(c.db, org_row["id"], email, role, c.uid, sites=sites)
    url = auth_api.link(c.config, c.allowed, "invite", token) or \
        f"{auth_api.PREFIX}invite?t={token}"
    if not mails.configured(c.config):
        invites.mark_handed(c.db, token)
        return {"link": url, "mailed": False}
    try:
        to = users.clean_email(email)
        mails.deliver(mails.invite_mail(c.config, to, url, org_row["name"], role,
                                        c.session["name"] or c.session["email"]), c.config, to)
    except Exception as why:              # noqa: BLE001 - the link is handed back instead
        note(f"invite mail not sent: {type(why).__name__}")
        invites.mark_handed(c.db, token)
        return {"link": url, "mailed": False,
                "warning": "The mail could not be sent. Pass this link on yourself."}
    return {"mailed": True}


def member_invite(c: Ctx, form):
    from .saas import limits as saas_limits
    org = _org(c, form, "admin")
    if org is None or _locked(c, org):
        return None
    role, email = text(form, "role", 20), text(form, "email", 300).strip().lower()
    if role not in users.ROLES:
        return c.no(400, f"A role is one of: {', '.join(users.ROLES)}.")
    if role == "owner" and not org.at_least("owner"):
        return c.no(403, "Only an owner can invite an owner.")
    sites = form.get("sites")
    ok, why = saas_limits.can_add_member(c.db, org.id, c.config, email)
    if not ok:
        return c.no(402, why, limit="members")
    try:
        return c.ok(**_invite(c, org.row, email, role, sites))
    except ValueError as why:
        return c.no(400, str(why))


def member_role(c: Ctx, form):
    org = _org(c, form, "admin")
    if org is None or _locked(c, org):
        return None
    user = _member(c, org, form)
    if user is None:
        return None
    role, old = text(form, "role", 20), users.role_in(c.db, user["id"], org.id)
    if role not in users.ROLES:
        return c.no(400, f"A role is one of: {', '.join(users.ROLES)}.")
    if "owner" in (role, old) and not org.at_least("owner"):
        return c.no(403, "Only an owner can make or change an owner.")
    try:
        users.set_role(c.db, org.id, user["id"], role, c.uid)
    except ValueError as why:
        return c.no(400, str(why))
    return c.ok(user=user["id"], role=role)


def member_remove(c: Ctx, form):
    org = _org(c, form, "admin")
    if org is None or _locked(c, org):
        return None
    user = _member(c, org, form)
    if user is None:
        return None
    if users.role_in(c.db, user["id"], org.id) == "owner" and not org.at_least("owner"):
        return c.no(403, "Only an owner can remove an owner.")
    try:
        users.remove_member(c.db, org.id, user["id"], c.uid)
    except ValueError as why:
        return c.no(400, str(why))
    return c.ok(user=user["id"])


def member_sites(c: Ctx, form):
    org = _org(c, form, "admin")
    if org is None or _locked(c, org):
        return None
    user = _member(c, org, form)
    if user is None:
        return None
    if user["id"] == c.uid and not c.install_admin:
        return c.no(400, "Ask another admin to change the sites you see.")
    try:
        got = users.set_site_access(c.db, org.id, user["id"], form.get("sites"), c.uid)
    except ValueError as why:
        return c.no(400, str(why))
    return c.ok(user=user["id"], sites=got)


def invite_resend(c: Ctx, form):
    org = _org(c, form, "admin")
    if org is None or _locked(c, org):
        return None
    try:
        email = users.clean_email(text(form, "email", 300))
    except ValueError as why:
        return c.no(400, str(why))
    found = [i for i in invites.pending(c.db, org.id) if i["email"] == email]
    if not found:
        return c.no(404, "There is no open invite for that address.")
    if found[0]["role"] == "owner" and not org.at_least("owner"):
        return c.no(403, "Only an owner can invite an owner.")
    try:
        return c.ok(**_invite(c, org.row, email, found[0]["role"], found[0]["sites"]))
    except ValueError as why:
        return c.no(400, str(why))


def invite_cancel(c: Ctx, form):
    org = _org(c, form, "admin")
    if org is None or _locked(c, org):
        return None
    try:
        gone = invites.cancel(c.db, org.id, text(form, "email", 300), c.uid)
    except ValueError as why:
        return c.no(400, str(why))
    return c.ok() if gone else c.no(404, "There is no open invite for that address.")


def token_revoke(c: Ctx, form):
    org = _org(c, form, "admin")
    if org is None or _locked(c, org):
        return None
    try:
        apitokens.revoke(c.db, org.id, text(form, "id", 200), c.uid)
    except ValueError as why:
        return c.no(404, str(why))
    return c.ok()


ROUTES = {
    "orgs": listing, "orgs/show": show, "orgs/auditlog": audit, "orgs/create": create,
    "orgs/rename": rename, "orgs/privacy": privacy, "orgs/archive": archive,
    "orgs/restore": restore, "orgs/move-site": move_site, "orgs/transfer": transfer,
    "orgs/leave": leave, "orgs/prefs": settings, "orgs/member/invite": member_invite,
    "orgs/member/role": member_role, "orgs/member/remove": member_remove,
    "orgs/member/sites": member_sites, "orgs/invite/resend": invite_resend,
    "orgs/invite/cancel": invite_cancel, "orgs/token-revoke": token_revoke,
}
