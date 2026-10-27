"""The signed-in Settings routes, with `access.mode: sessions`.

Served by the refresh helper (refresh_server.py) for every site page,
`/traffic/<site>/[<view>/]...`, behind nginx's session check
(docs/plans/2026-10-11-phase1-accounts-plan.md §2):

  GET  team                      {members, invites}            every member (read-only)
  POST team/invite               email, role -> {link?}        admin
  POST team/role | team/remove | team/resend | team/cancel     admin
  GET  account                   {email, name, totp_on, sessions}
  POST account/name | account/password | account/signout-all
  POST account/totp/start (password) | account/totp/confirm | account/totp/off (password)
  GET  tokens; POST tokens/create (shown once) | tokens/revoke  admin
  GET  audit?action=&limit=      {entries}                     admin

In basic mode they answer 404. The helper reads the session from the
cookie itself (nginx passes it on) and the role from accounts.sqlite on
every call, for the site's own organisation, so a removed member is refused
at once. Every POST needs the same-origin check AND the X-Skald-CSRF header
equal to the session's value (compared in constant time).

"admin" here means owner or admin; only an owner may make or change an
owner. Invite links go out by mail when mail is set up; otherwise (or when
sending fails) the answer carries `link` for the admin to pass on, and the
invite is marked handed: the account made from it must choose a new password
at its first sign-in (accounts/invites.py). Turning two-step sign-in on, or
off, and changing the password all need the current password, counted like
a sign-in try.
"""
from __future__ import annotations

import re

from . import accounts, auth_api
from .accounts import apitokens, auditlog, invites, sessions, totp, users
from .auth_api import answer, csrf_ok, note, read_json, text
from .saas import enabled as saas_on, limits as saas_limits

PAGE = r"^/traffic/(?P<site>[a-z0-9.-]+)/(?:(?P<view>[a-z0-9-]+)/)?"
PATH = re.compile(PAGE + r"(?P<act>team(?:/(?:invite|role|remove|resend|cancel))?"
                         r"|account(?:/(?:name|password|signout-all|totp/start|totp/confirm"
                         r"|totp/off))?"
                         r"|tokens(?:/(?:create|revoke))?|audit)$")
GETS = {"team", "account", "tokens", "audit"}
ADMIN_GETS = {"tokens", "audit"}
RANK = {"viewer": 0, "admin": 1, "owner": 2}


def match(path: str):
    path = path.split("?", 1)[0]
    if ".." in path:
        return None
    return PATH.match(path)


def is_team(path: str) -> bool:
    return match(path) is not None


class Ctx:
    """One request: the open database, who asks, their role on the site's org."""

    def __init__(self, h, db, session, site, role, org, config, allowed):
        self.h, self.db, self.session, self.site = h, db, session, site
        self.role, self.org, self.config, self.allowed = role, org, config, allowed
        self.uid = session["user_id"]

    @property
    def admin(self) -> bool:
        return RANK.get(self.role, -1) >= RANK["admin"]

    def ok(self, **body):
        return answer(self.h, 200, {"ok": True, **body})

    def no(self, code: int, error: str, **extra):
        return answer(self.h, code, {"ok": False, "error": error, **extra})


def handle(h, write: bool, config, live_dir, allowed: set[str], same_origin) -> None:
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
        return _route(h, db, m, act, write, config, allowed)
    except accounts.passwords.Busy as why:
        return answer(h, 503, {"ok": False, "error": str(why)},
                      {"Retry-After": str(auth_api.BUSY_WAIT)})
    finally:
        db.close()


def _route(h, db, m, act: str, write: bool, config, allowed):
    """One Settings request on an open database: session, CSRF, role, route."""
    session = sessions.resolve(db, auth_api.cookie_of(h.headers))
    if session is None:
        return answer(h, 401, {"ok": False, "error": "Sign in first."})
    if write and not csrf_ok(session, h.headers):
        return answer(h, 403, {"ok": False, "error": "The page is out of date. "
                                                     "Reload it and try again."})
    role, org = users.site_role(db, session["user_id"], m.group("site"))
    if role is None:
        return answer(h, 403, {"ok": False, "error": "You are not a member here."})
    c = Ctx(h, db, session, m.group("site"), role, org, config, allowed)
    if (write and act.startswith(("team/", "tokens/"))) or act in ADMIN_GETS:
        if not c.admin:
            return c.no(403, "Only an admin can do this.", role=role)
    if write and act.startswith(("team/", "tokens/")):
        locked = saas_limits.read_only(db, org["id"], config)   # saas: payment overdue
        if locked:
            return c.no(402, locked, read_only=True)
    form = {}
    if write:
        form = read_json(h)
        if form is None:
            return None
    return ROUTES[act](c, form)


# ---------------------------------------------------------------- /me

def me(h, config, live_dir, site: str, user: str, role: str) -> dict:
    """The contract's /me fields in sessions mode. `user` and `role` are the
    helper's own reading of the session cookie (access.session_caller), never
    a header; the CSRF value, name and flags come from the cookie too."""
    body = {"ok": True, "user": user or None, "name": None, "role": role,
            "org": None, "csrf": None, "mode": "sessions", "install_admin": False,
            "totp_on": False}
    db = auth_api.open_db(config, live_dir)
    if db is None:
        return body
    try:
        who = sessions.resolve(db, auth_api.cookie_of(h.headers))
        org = accounts.org_of_site(db, site)
        body["org"] = org["name"] if org else None
        if saas_on(config) and org is not None:          # saas: the plan and its banner
            body["saas"] = True
            body["plan"] = saas_limits.summary(db, org["id"], config,
                                               saas_limits.history_path(config, live_dir))
        if who is not None:
            user = users.find_user(db, user_id=who["user_id"])
            body.update(user=who["email"], name=who["name"] or None, csrf=who["csrf"],
                        install_admin=who["install_admin"],
                        totp_on=bool(user and user["totp_on"]))
    finally:
        db.close()
    return body


# --------------------------------------------------------------- team

def _target(c: Ctx, form) -> dict | None:
    user = users.find_user(c.db, email=text(form, "email", 300))
    if user is None or users.role_in(c.db, user["id"], c.org["id"]) is None:
        c.no(404, "There is no such member.")
        return None
    return user


def team(c: Ctx, form):
    members = [{k: m[k] for k in ("email", "name", "role", "added_at", "last_seen", "totp_on",
                                  "disabled_at", "has_password")}
               for m in users.members(c.db, c.org["id"])]
    pending = invites.pending(c.db, c.org["id"]) if c.admin else []
    # 2.38.0: the sites this team sees, and the reader's other organisations,
    # each with a site whose Team page shows that organisation's team.
    from .files import slug
    others = []
    for o in accounts.list_orgs(c.db, c.uid):
        names = users.visible_sites(c.db, o["id"], c.uid)
        if o["id"] != c.org["id"] and names:
            others.append({"org": o["name"], "sites": len(names),
                           "path": f"{slug(names[0])}/"})
    return c.ok(org=c.org["name"], role=c.role, members=members, invites=pending,
                sites=accounts.sites_of_org(c.db, c.org["id"]), others=others)


def _send_invite(c: Ctx, email: str, role: str, kind: str, sites=None):
    from .accounts import mails
    try:
        token = invites.invite(c.db, c.org["id"], email, role, c.uid, sites=sites)
    except ValueError as why:
        return c.no(400, str(why))
    url = auth_api.link(c.config, c.allowed, "invite", token)
    if url is None:
        # No base URL: hand back the path; the admin adds their own address.
        url = f"{auth_api.PREFIX}invite?t={token}"
    if not mails.configured(c.config):
        invites.mark_handed(c.db, token)
        return c.ok(link=url, mailed=False)
    try:
        to = users.clean_email(email)
        mails.deliver(mails.invite_mail(c.config, to, url, c.org["name"], role,
                                        c.session["name"] or c.session["email"]), c.config, to)
    except Exception as why:
        note(f"{kind} mail not sent: {type(why).__name__}")
        invites.mark_handed(c.db, token)
        return c.ok(link=url, mailed=False,
                    warning="The mail could not be sent. Pass this link on yourself.")
    return c.ok(mailed=True)


def team_invite(c: Ctx, form):
    role = text(form, "role", 20)
    if role not in users.ROLES:
        return c.no(400, f"A role is one of: {', '.join(users.ROLES)}.")
    if role == "owner" and c.role != "owner":
        return c.no(403, "Only an owner can invite an owner.")
    ok, why = saas_limits.can_add_member(c.db, c.org["id"], c.config,
                                         text(form, "email", 300).strip().lower())
    if not ok:
        return c.no(402, why, limit="members")
    return _send_invite(c, text(form, "email", 300), role, "invite")


def team_resend(c: Ctx, form):
    try:
        email = users.clean_email(text(form, "email", 300))
    except ValueError as why:
        return c.no(400, str(why))
    found = [i for i in invites.pending(c.db, c.org["id"]) if i["email"] == email]
    if not found:
        return c.no(404, "There is no open invite for that address.")
    if found[0]["role"] == "owner" and c.role != "owner":
        return c.no(403, "Only an owner can invite an owner.")
    return _send_invite(c, email, found[0]["role"], "invite resend", found[0].get("sites"))


def team_cancel(c: Ctx, form):
    try:
        gone = invites.cancel(c.db, c.org["id"], text(form, "email", 300), c.uid)
    except ValueError as why:
        return c.no(400, str(why))
    return c.ok() if gone else c.no(404, "There is no open invite for that address.")


def team_role(c: Ctx, form):
    user = _target(c, form)
    if user is None:
        return None
    role, old = text(form, "role", 20), users.role_in(c.db, user["id"], c.org["id"])
    if role not in users.ROLES:
        return c.no(400, f"A role is one of: {', '.join(users.ROLES)}.")
    if "owner" in (role, old) and c.role != "owner":
        return c.no(403, "Only an owner can make or change an owner.")
    try:
        users.set_role(c.db, c.org["id"], user["id"], role, c.uid)
    except ValueError as why:
        return c.no(400, str(why))
    return c.ok(email=user["email"], role=role)


def team_remove(c: Ctx, form):
    user = _target(c, form)
    if user is None:
        return None
    if users.role_in(c.db, user["id"], c.org["id"]) == "owner" and c.role != "owner":
        return c.no(403, "Only an owner can remove an owner.")
    try:
        users.remove_member(c.db, c.org["id"], user["id"], c.uid)
    except ValueError as why:
        return c.no(400, str(why))
    return c.ok(email=user["email"])


# ------------------------------------------------------------ account

def account(c: Ctx, form):
    user = users.find_user(c.db, user_id=c.uid)
    live = [{**s, "current": s["session_id"] == c.session["session_id"]}
            for s in sessions.list_for(c.db, c.uid)]
    return c.ok(email=user["email"], name=user["name"], totp_on=user["totp_on"],
                role=c.role, org=c.org["name"], sessions=live)


def _password_right(c: Ctx, password: str) -> bool:
    """The account's own password, counted like a sign-in so a stolen session
    cannot guess it fast."""
    tries = auth_api.take_try(c.db, (f"login:email:{c.session['email']}",))
    if tries is None:
        return False
    if accounts.authenticate(c.db, c.session["email"], password) is None:
        auditlog.record(c.db, c.org["id"], c.uid, "login.fail", c.session["email"],
                        "wrong current password in Settings")
        return False
    accounts.limits.forget(c.db, tries)
    return True


def account_name(c: Ctx, form):
    name = " ".join(text(form, "name", 200).split())
    if not name:
        return c.no(400, "Type a name.")
    users.set_name(c.db, c.uid, name, c.uid)
    return c.ok(name=name[:100])


def account_password(c: Ctx, form):
    if not _password_right(c, text(form, "current")):
        return c.no(403, "The current password is not right.")
    try:
        users.set_password(c.db, c.uid, text(form, "new"), c.uid)
    except ValueError as why:
        return c.no(400, str(why))
    # Every session ended, this one too: start a fresh one for this browser.
    cookie, csrf = sessions.start(c.db, c.uid, auth_api.client_ip(c.h, c.config),
                                  c.h.headers.get("User-Agent", ""))
    return answer(c.h, 200, {"ok": True, "csrf": csrf},
                  {"Set-Cookie": auth_api.set_cookie(cookie)})


def account_signout_all(c: Ctx, form):
    ended = sessions.end_all(c.db, c.uid, except_session=c.session["session_id"])
    return c.ok(ended=ended)


def account_totp_start(c: Ctx, form):
    if users.find_user(c.db, user_id=c.uid)["totp_on"]:
        return c.no(400, "Two-step sign-in is already on. Turn it off first to change the app.")
    if not _password_right(c, text(form, "password")):
        return c.no(403, "Type your current password to turn on two-step sign-in.")
    secret, uri = totp.begin(c.db, c.uid)
    return c.ok(secret=secret, uri=uri)


def account_totp_confirm(c: Ctx, form):
    try:
        codes = totp.confirm(c.db, c.uid, text(form, "code", 32), c.uid)
    except ValueError as why:
        return c.no(400, str(why))
    return c.ok(recovery_codes=codes)


def account_totp_off(c: Ctx, form):
    if not _password_right(c, text(form, "password")):
        return c.no(403, "The password is not right.")
    totp.disable(c.db, c.uid, c.uid)
    return c.ok()


# ------------------------------------------------------- tokens, audit

def tokens(c: Ctx, form):
    return c.ok(tokens=apitokens.listing(c.db, c.org["id"]))


def tokens_create(c: Ctx, form):
    sites, scopes = form.get("sites"), form.get("scopes")
    if sites is not None and not (isinstance(sites, list) and
                                  all(isinstance(s, str) for s in sites)):
        return c.no(400, "sites is a list of site names.")
    if scopes is None:
        scopes = ["read"]
    if not (isinstance(scopes, list) and all(isinstance(s, str) for s in scopes)):
        return c.no(400, "scopes is a list.")
    try:
        token = apitokens.create(c.db, c.org["id"], text(form, "name", 200), sites or None,
                                 form.get("private") is True, scopes, c.uid)
    except ValueError as why:
        return c.no(400, str(why))
    tid = token.split("_", 2)[1]
    entry = next((t for t in apitokens.listing(c.db, c.org["id"]) if t["id"] == tid), {})
    return c.ok(token=token, **{k: v for k, v in entry.items() if k != "org_id"})


def tokens_revoke(c: Ctx, form):
    try:
        apitokens.revoke(c.db, c.org["id"], text(form, "id", 200), c.uid)
    except ValueError as why:
        return c.no(404, str(why))
    return c.ok()


def audit(c: Ctx, form):
    q = auth_api.query(c.h.path)
    try:
        limit = max(1, min(int(q.get("limit") or 200), 1000))
    except ValueError:
        limit = 200
    entries = auditlog.recent(c.db, c.org["id"], limit, q.get("action") or None)
    return c.ok(entries=entries)


ROUTES = {
    "team": team, "team/invite": team_invite, "team/role": team_role,
    "team/remove": team_remove, "team/resend": team_resend, "team/cancel": team_cancel,
    "account": account, "account/name": account_name, "account/password": account_password,
    "account/signout-all": account_signout_all, "account/totp/start": account_totp_start,
    "account/totp/confirm": account_totp_confirm, "account/totp/off": account_totp_off,
    "tokens": tokens, "tokens/create": tokens_create, "tokens/revoke": tokens_revoke,
    "audit": audit,
}
