"""Signing in, with `access.mode: sessions`: the /traffic-auth/* routes.

Served by the refresh helper (refresh_server.py), the way bot_policy_api.py
is: `is_auth(path)` and `handle(...)`. The contract is
docs/plans/2026-10-11-phase1-accounts-plan.md §2; nginx's part is §3.

  GET  /traffic-auth/login | forgot | reset | invite    the static pages (webapp/auth/)
  GET  /traffic-auth/auth.js | auth.css                  their script and styles
  GET  /traffic-auth/check          nginx auth_request only (127.0.0.1): reads the
                                    cookie, X-Original-URI (the raw $request_uri) and
                                    X-Original-Path (nginx's normalised $uri); 200
                                    with X-Skald-User (email), X-Skald-Role,
                                    X-Skald-Org (the org's slug); 401 no or expired
                                    session; 403 not a member, or an address the
                                    strict parse refuses (see strict_path)
  POST /traffic-auth/login          email, password, code?, next?
  POST /traffic-auth/logout         303 to the sign-in page, cookie cleared
  POST /traffic-auth/forgot         email: 200 always, the same words
  POST /traffic-auth/reset          token, password
  GET  /traffic-auth/invite-info?t= org, email, role, has_account
  POST /traffic-auth/invite         token, name?, password?

In basic mode every one of these answers 404. Every POST needs the
same-origin check; bodies are JSON objects of at most 4 KiB. The cookie is
`skald_session` (HttpOnly; Secure; SameSite=Lax; Path=/; 14 days).

Sign-in tries are counted per email and per address (accounts.limits): after
5 failures in 15 minutes each further try must wait 30 s (429), and every
failure is written to the audit log. There is never a lock-out. The try is
written BEFORE the password is checked, in one transaction with the check
of the limit (limits.take), so tries sent in parallel cannot slip past it;
a sign-in that works takes its own try back. At most two password checks
run at once (passwords.SLOTS); when they stay busy the answer is 503 with
Retry-After. nginx's limit_req in front (DEPLOY.md) slows a flood further.

An account made from an invite link that was shown to the admin instead of
mailed (`must_reset`) gets `{"must_change": true}` at its first sign-in and
signs in only by sending `new_password` with the right password.

Links in mails start with the install's base URL (`base_url` below): from
the config, never from the request's Host header.
"""
from __future__ import annotations

import hmac
import json
import re
import sys
import threading
from http.cookies import CookieError, SimpleCookie
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

from . import access, accounts
from .accounts import auditlog, limits, sessions, totp, users

PREFIX = "/traffic-auth/"
PAGES_DIR = Path(__file__).resolve().parent / "webapp" / "auth"
# name in the address -> (file in webapp/auth/, content type). Nothing else is served.
STATIC = {
    "login": ("login.html", "text/html; charset=utf-8"),
    "forgot": ("forgot.html", "text/html; charset=utf-8"),
    "reset": ("reset.html", "text/html; charset=utf-8"),
    "invite": ("invite.html", "text/html; charset=utf-8"),
    "auth.js": ("auth.js", "text/javascript; charset=utf-8"),
    "auth.css": ("auth.css", "text/css; charset=utf-8"),
}
CSP = ("default-src 'none'; script-src 'self'; connect-src 'self'; "
       "style-src 'self' 'unsafe-inline'; img-src 'self' data:; base-uri 'none'; "
       "form-action 'self'; frame-ancestors 'none'")
MAX_BODY = 4096
COOKIE = sessions.COOKIE
MAX_AGE = accounts.TTL_DAYS * 86400
LOGIN_LIMIT, LOGIN_MINUTES, LOGIN_WAIT = 5, 15, 30
WAIT_WORDS = "Too many tries. Wait 30 seconds, then try again."
BAD_LOGIN = "That email and password do not match."
BAD_CODE = "That code is not right. Codes change every 30 seconds; try the one the app shows now."
FORGOT_WORDS = ("If that address has an account, a link to choose a new password is on its "
                "way. It works for 60 minutes.")
SITE_NAME = re.compile(r"^[a-z0-9.-]+$")
# The site switcher, its list, the shared app code and the deploy's build.json
# (name, version, release, commit, time: nothing about any site): any signed-in
# user. sites.json is answered by the helper, filtered to the caller's sites.
ANY_SIGNED_IN = ("", "index.html", "_app", "sites.json", "build.json")
BUSY_WAIT = 2

_threads: list[threading.Thread] = []
_threads_lock = threading.Lock()


# ------------------------------------------------------------ shared helpers

def is_auth(path: str) -> bool:
    return path.split("?", 1)[0].startswith(PREFIX)


def sessions_mode(config) -> bool:
    return access.mode(config) == "sessions"


def open_db(config, live_dir):
    """A fresh connection to accounts.sqlite (the caller closes it), or None."""
    path = accounts.path_for(config or {}, live_dir)
    return accounts.connect(path) if path is not None else None


def cookie_of(headers) -> str | None:
    raw = headers.get("Cookie") or ""
    if not raw or len(raw) > 8192:
        return None
    jar = SimpleCookie()
    try:
        jar.load(raw)
    except CookieError:
        # One malformed cookie of another app must not hide ours.
        for part in raw.split(";"):
            name, _, value = part.strip().partition("=")
            if name == COOKIE:
                return value.strip() or None
        return None
    got = jar.get(COOKIE)
    return got.value if got is not None and got.value else None


def client_ip(h, config=None) -> str:
    """nginx's X-Real-IP on nginx's own connection when the config trusts it
    (access.trust_proxy_ip, default true), else the peer."""
    peer = h.client_address[0]
    return access.proxy_ip(h.headers, peer, config) or peer


def query(path: str) -> dict:
    raw = path.split("?", 1)[1] if "?" in path else ""
    return dict(parse_qsl(raw, keep_blank_values=True)[:20])


def read_json(h, limit: int = MAX_BODY) -> dict | None:
    """The JSON object in the body (at most `limit` bytes, 4 KiB unless a route
    says more), or None after answering 400 or 413."""
    try:
        length = int(h.headers.get("Content-Length") or 0)
    except ValueError:
        length = -1
    if length < 0 or length > limit:
        h._json(400 if length < 0 else 413, {"ok": False, "error": "The request is too large."})
        return None
    raw = h.rfile.read(length) if length else b""
    try:
        got = json.loads(raw.decode("utf-8") or "{}")
    except (UnicodeDecodeError, ValueError):
        got = None
    if not isinstance(got, dict):
        h._json(400, {"ok": False, "error": "Send a JSON object."})
        return None
    return got


def text(form: dict, key: str, limit: int = 1024) -> str:
    value = form.get(key)
    return value[:limit] if isinstance(value, str) else ""


def csrf_ok(session: dict | None, headers) -> bool:
    got = headers.get("X-Skald-CSRF") or ""
    want = (session or {}).get("csrf") or ""
    return bool(got and want) and hmac.compare_digest(got.encode(), want.encode())


def safe_next(raw, fallback: str = "/traffic/") -> str:
    """`next` only when it is a path on this server under /traffic/: no scheme,
    no host, no "//", no backslash or control character, no "..". Else `fallback`."""
    if not isinstance(raw, str) or not raw or len(raw) > 2000:
        return fallback
    if not raw.startswith("/traffic/") or raw.startswith("//"):
        return fallback
    if any(c == "\\" or ord(c) < 0x20 or ord(c) == 0x7f for c in raw):
        return fallback
    parts = urlsplit(raw)
    if parts.scheme or parts.netloc or "//" in parts.path or ".." in parts.path.split("/"):
        return fallback
    return raw


def base_url(config, allowed: set[str] | None = None) -> str | None:
    """Where links in mails point (accounts/links.py, the same rule as the
    CLI's): access.base_url, dashboard.base_url, dashboard.url's scheme and
    host, else the first --origin the helper was given. Never the request's
    Host header, which the asker controls."""
    from .accounts import links
    return links.base_url(config, allowed=allowed)


def link(config, allowed, page: str, token: str) -> str | None:
    from .accounts import links
    base = base_url(config, allowed)
    return links.link(base, page, token) if base else None


def spawn(fn) -> threading.Thread:
    """Run `fn` on its own thread (mail, so its timing is not the answer's)."""
    t = threading.Thread(target=fn, daemon=True)
    with _threads_lock:
        _threads[:] = [x for x in _threads if x.is_alive()]
        _threads.append(t)
    t.start()
    return t


def drain(timeout: float = 10) -> None:
    """Wait for the background mail threads (for tests and a clean exit)."""
    with _threads_lock:
        pending = list(_threads)
    for t in pending:
        t.join(timeout)


def note(words: str) -> None:
    """One line to the journal: never an address, an email, a token or a link."""
    sys.stderr.write(f"accounts: {words}\n")


def set_cookie(value: str, remember: bool = True) -> str:
    """The session cookie. Without "Keep me signed in" it has no Max-Age, so the
    browser drops it when it closes (and the server ends it after 12 hours)."""
    keep = f"; Max-Age={MAX_AGE}" if remember else ""
    return f"{COOKIE}={value}; HttpOnly; Secure; SameSite=Lax; Path=/{keep}"


CLEAR_COOKIE = f"{COOKIE}=; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=0"


def answer(h, code: int, body: dict | None = None, headers: dict | None = None) -> None:
    data = json.dumps(body).encode() if body is not None else b""
    h.send_response(code)
    if body is not None:
        h.send_header("Content-Type", "application/json; charset=utf-8")
    for k, v in (headers or {}).items():
        h.send_header(k, v)
    h.send_header("Cache-Control", "no-store")
    h.send_header("X-Content-Type-Options", "nosniff")
    h.send_header("Content-Length", str(len(data)))
    h.end_headers()
    if data:
        h.wfile.write(data)


# ------------------------------------------------------------------ routes

def handle(h, write: bool, config, live_dir, allowed: set[str], same_origin) -> None:
    """Answer one /traffic-auth/ request on handler `h`."""
    if not sessions_mode(config):
        return answer(h, 404, {"ok": False, "error": "not found"})
    try:
        return _route(h, write, config, live_dir, allowed, same_origin)
    except accounts.passwords.Busy as why:
        return answer(h, 503, {"ok": False, "error": str(why)}, {"Retry-After": str(BUSY_WAIT)})


def _route(h, write: bool, config, live_dir, allowed: set[str], same_origin) -> None:
    name = h.path.split("?", 1)[0][len(PREFIX):]
    if not write:
        if name == "check":
            return _check(h, config, live_dir)
        if name == "invite-info":
            return _with_db(h, config, live_dir, _invite_info)
        if name in STATIC:
            return _static(h, name)
        if name == "mail-confirm":                  # a mail recipient's link (mail_confirm.py)
            from . import mail_confirm
            return mail_confirm.http(h, False, config, live_dir)
        return answer(h, 404, {"ok": False, "error": "not found"})
    if name not in ("login", "logout", "forgot", "reset", "invite", "mail-confirm"):
        return answer(h, 404, {"ok": False, "error": "not found"})
    if not same_origin(h.headers, allowed):
        return answer(h, 403, {"ok": False, "error": "same-origin requests only"})
    if name == "mail-confirm":
        from . import mail_confirm
        return mail_confirm.http(h, True, config, live_dir)
    if name == "logout":
        return _with_db(h, config, live_dir, _logout)
    form = read_json(h)
    if form is None:
        return None
    if name == "forgot":
        return _forgot(h, form, config, live_dir, allowed)
    fn = {"login": _login, "reset": _reset, "invite": _invite}[name]
    return _with_db(h, config, live_dir, lambda h, db: fn(h, db, form, config))


def _with_db(h, config, live_dir, fn):
    db = open_db(config, live_dir)
    if db is None:
        return answer(h, 503, {"ok": False, "error": "accounts are not set up here"})
    try:
        return fn(h, db)
    finally:
        db.close()


def _static(h, name: str) -> None:
    file, ctype = STATIC[name]
    path = PAGES_DIR / file
    try:
        data = path.read_bytes()
    except OSError:
        return answer(h, 404, {"ok": False, "error": "not found"})
    h.send_response(200)
    h.send_header("Content-Type", ctype)
    h.send_header("Content-Security-Policy", CSP)
    h.send_header("Cache-Control", "no-store")
    h.send_header("X-Content-Type-Options", "nosniff")
    h.send_header("Referrer-Policy", "no-referrer")
    h.send_header("X-Frame-Options", "DENY")
    h.send_header("Content-Length", str(len(data)))
    h.end_headers()
    h.wfile.write(data)


def strict_path(uri) -> str | None:
    """The path of a /traffic/ address when nothing in it could make nginx
    read it as another path: no "%" (nginx decodes %2e%2e and %2f before it
    maps the path to a file), no empty segment ("//", which nginx merges), no
    "." or ".." segment, no backslash, no "#", nothing outside printable
    ASCII. None otherwise. The query (after "?") is not looked at."""
    if not isinstance(uri, str) or not uri or len(uri) > 4096:
        return None
    path = uri.split("?", 1)[0]
    if path != "/traffic" and not path.startswith("/traffic/"):
        return None
    if any(c in "%\\#" or not 0x21 <= ord(c) <= 0x7e for c in path):
        return None
    segments = path.split("/")[1:]
    for i, seg in enumerate(segments):
        if seg in (".", "..") or (seg == "" and i != len(segments) - 1):
            return None
    return path


def site_of_uri(uri: str) -> str | None:
    """The site a /traffic/<site>/... address is for; "" for the switcher, its
    list and the shared app code (any signed-in user); None when it is not a
    plain /traffic/ address (strict_path)."""
    path = strict_path(uri)
    if path is None:
        return None
    if path in ("/traffic", "/traffic/"):
        return ""
    first = path.split("/")[2]
    return "" if first in ANY_SIGNED_IN else first


def site_of_request(raw, normalised) -> str | None:
    """The site, when nginx's raw address and its own normalised path both pass
    the strict parse and name the same site (or both the shared pages); else
    None. They differ in the file only for nginx's own index and redirects
    (/traffic/x/ and /traffic/x/index.html), never in the site."""
    site, again = site_of_uri(raw or ""), site_of_uri(normalised or "")
    if site is None or again is None or site != again:
        return None
    return site


def _check(h, config, live_dir) -> None:
    if h.client_address[0] != access.PROXY:
        return answer(h, 403)
    db = open_db(config, live_dir)
    if db is None:
        return answer(h, 401)
    try:
        who = sessions.resolve(db, cookie_of(h.headers))
        if who is None:
            return answer(h, 401)
        normalised = h.headers.get("X-Original-Path")
        if not normalised:
            note("check: no X-Original-Path from nginx; every page is refused until the "
                 "nginx config passes it (DEPLOY.md, sessions mode)")
        site = site_of_request(h.headers.get("X-Original-URI"), normalised)
        if site is None:
            return answer(h, 403)
        role, org = "", None
        if site:
            if not SITE_NAME.match(site):
                return answer(h, 403)
            # Membership is read on every request: removing a member ends access at once.
            role, org = users.site_role(db, who["user_id"], site)
            if role is None:
                return answer(h, 403)
            # The organisation's security settings (settings_api.py): a session
            # older than its length, or no two-step sign-in where it is required,
            # goes back to the sign-in page.
            from .settings_api import refusal
            code = refusal(db, who, org)
            if code is not None:
                return answer(h, code)
        return answer(h, 200, None, {"X-Skald-User": who["email"],
                                     "X-Skald-Role": role or "viewer",
                                     "X-Skald-Org": org["slug"] if org else ""})
    finally:
        db.close()


def _audit_fail(db, email: str, user: dict | None, why: str) -> None:
    """The failure in the audit log (the try itself was counted before the check)."""
    if limits.too_many(db, f"login:email:{email}", LOGIN_LIMIT, LOGIN_MINUTES):
        why += f"; {LOGIN_LIMIT} or more in {LOGIN_MINUTES} minutes, each try now waits 30 s"
    orgs = [o["id"] for o in accounts.list_orgs(db, user["id"])] if user else []
    actor = user["id"] if user else "-"
    for org_id in orgs or [None]:
        auditlog.record(db, org_id, actor, "login.fail", email, why)


def take_try(db, keys) -> list[int] | None:
    """Count one sign-in try for each key before the password is checked, or
    None when a key must wait (the caller answers 429)."""
    return limits.take(db, keys, LOGIN_LIMIT, LOGIN_MINUTES, LOGIN_WAIT)


WAIT = {"ok": False, "error": WAIT_WORDS}
MUST_CHANGE = ("Choose a new password before you go on: the one you have was set "
               "from an invite link that someone else may have seen.")


def _login(h, db, form, config=None) -> None:
    try:
        email = users.clean_email(text(form, "email", 300))
    except ValueError:
        email = text(form, "email", 300).strip().lower()
    password, code = text(form, "password"), text(form, "code", 64)
    ip = client_ip(h, config)
    email_key, ip_key = f"login:email:{email}", f"login:ip:{accounts.keyed_hash(db, ip)}"
    tries = take_try(db, (email_key, ip_key))
    if tries is None:
        return answer(h, 429, WAIT, {"Retry-After": str(LOGIN_WAIT)})
    user = accounts.authenticate(db, email, password)
    if user is None:
        _audit_fail(db, email, users.find_user(db, email=email),
                    "wrong password or unknown email")
        return answer(h, 401, {"ok": False, "error": BAD_LOGIN})
    if user["totp_on"]:
        if not code.strip():
            limits.forget(db, tries)
            return answer(h, 200, {"ok": True, "needs_code": True})
        if not totp.check_user(db, user["id"], code):
            _audit_fail(db, email, user, "wrong two-step code")
            return answer(h, 401, {"ok": False, "error": BAD_CODE})
    limits.forget(db, tries)
    limits.clear(db, email_key)
    # A new password first (checked, not yet set), then two-step set-up: the
    # set-up's answer makes the recovery codes, and nothing after it may
    # answer without them (they are shown once).
    if user["must_reset"]:
        new = text(form, "new_password")
        if not new:
            return answer(h, 200, {"ok": True, "must_change": True, "message": MUST_CHANGE})
        if new == password:
            return answer(h, 400, {"ok": False, "must_change": True,
                                   "error": "Choose a password different from the one you "
                                            "have now."})
        problem = accounts.passwords.password_problem(new, user["email"])
        if problem:
            return answer(h, 400, {"ok": False, "must_change": True, "error": problem})
    codes = None
    if not user["totp_on"]:
        codes, refused = _setup_totp(h, db, user, form)
        if refused:
            return None
    if user["must_reset"]:
        try:
            users.set_password(db, user["id"], new, user["id"])
        except ValueError as why:
            return answer(h, 400, {"ok": False, "must_change": True, "error": str(why)})
    remember = form.get("remember", True) is not False
    cookie, _csrf = sessions.start(db, user["id"], ip, h.headers.get("User-Agent", ""),
                                   remember=remember)
    body = {"ok": True, "next": safe_next(form.get("next"))}
    if codes:
        body["recovery_codes"] = codes
    return answer(h, 200, body, {"Set-Cookie": set_cookie(cookie, remember)})


SETUP_WORDS = ("Your organisation requires two-step sign-in. Add this account to an "
               "authenticator app, then type the code it shows.")


def _setup_totp(h, db, user, form) -> tuple[list[str] | None, bool]:
    """When an organisation of the user requires two-step sign-in and it is
    off (settings_api): the first answer starts it (`needs_setup`, the secret
    and its otpauth link); the next, with `setup_code`, turns it on. (recovery
    codes or None, True when an answer was already sent)."""
    from .settings_api import totp_required
    if not totp_required(db, user["id"]):
        return None, False
    code = text(form, "setup_code", 32).strip()
    if not code:
        secret, uri = totp.begin(db, user["id"])
        answer(h, 200, {"ok": True, "needs_setup": True, "secret": secret, "uri": uri,
                        "message": SETUP_WORDS})
        return None, True
    try:
        return totp.confirm(db, user["id"], code, user["id"]), False
    except ValueError as why:
        answer(h, 400, {"ok": False, "needs_setup": True, "error": str(why)})
        return None, True


def _logout(h, db) -> None:
    sessions.end(db, cookie_of(h.headers))
    h.send_response(303)
    h.send_header("Location", PREFIX + "login")
    h.send_header("Set-Cookie", CLEAR_COOKIE)
    h.send_header("Cache-Control", "no-store")
    h.send_header("Content-Length", "0")
    h.end_headers()


def _forgot(h, form, config, live_dir, allowed) -> None:
    email = text(form, "email", 300)

    def work():
        # Everything, even the lookup, off the answer's clock: the reply is the
        # same, at the same speed, whether or not the address has an account.
        from .accounts import mails
        try:
            db = open_db(config, live_dir)
            if db is None:
                return
            try:
                token = accounts.request_reset(db, email)
            finally:
                db.close()
            if token is None:
                return
            url = link(config, allowed, "reset", token)
            if url is None:
                note("reset link made but no base URL is set (access.base_url); no mail sent")
                return
            if not mails.configured(config):
                note("reset link made but mail is not set up; no mail sent "
                     "(skald account reset-link makes one by hand)")
                return
            to = users.clean_email(email)
            mails.deliver(mails.reset_mail(config, to, url), config, to)
            note("reset mail sent")
        except Exception as why:            # a thread must never take the helper down
            note(f"reset mail not sent: {type(why).__name__}")

    spawn(work)
    return answer(h, 200, {"ok": True, "message": FORGOT_WORDS})


def _reset(h, db, form, config=None) -> None:
    try:
        accounts.use_reset(db, text(form, "token", 300), text(form, "password"))
    except ValueError as why:
        return answer(h, 400, {"ok": False, "error": str(why)})
    return answer(h, 200, {"ok": True, "next": PREFIX + "login"})


def _invite_info(h, db) -> None:
    got = accounts.invite_info(db, query(h.path).get("t", "")[:300])
    if got is None:
        return answer(h, 400, {"ok": False, "error": "This invite has expired, was used "
                                                     "already, or was cancelled."})
    return answer(h, 200, {"ok": True, "org": got["org"], "email": got["email"],
                           "role": got["role"], "has_account": got["has_account"]})


def _invite(h, db, form, config=None) -> None:
    try:
        user = accounts.accept(db, text(form, "token", 300), text(form, "name", 100),
                               text(form, "password"))
    except ValueError as why:
        return answer(h, 400, {"ok": False, "error": str(why)})
    sites = accounts.sites_of_org(db, user["org_id"])
    nxt = f"/traffic/{sites[0]}/" if sites else "/traffic/"
    if not user["new"] or user["must_reset"]:
        # The link alone never signs in an existing account: whoever holds the
        # link may not be that person (the admin who made it, when mail is not
        # set up). They sign in with their own password. A new account from a
        # link that was shown to the admin is not signed in either: its first
        # sign-in asks for a new password (must_reset).
        return answer(h, 200, {"ok": True, "next": nxt, "signed_in": False,
                               "must_change": bool(user["must_reset"])})
    cookie, _csrf = sessions.start(db, user["id"], client_ip(h, config),
                                   h.headers.get("User-Agent", ""))
    return answer(h, 200, {"ok": True, "next": nxt, "signed_in": True},
                  {"Set-Cookie": set_cookie(cookie)})
