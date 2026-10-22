"""Self-serve sign-up, on the refresh helper (refresh_server.py), before
auth_api's /traffic-auth/ routes. Only with saas.enabled and saas.signup
(and access.mode: sessions); otherwise every route answers 404.

  GET  /traffic-auth/signup            the page: an email address
  GET  /traffic-auth/signup-finish     the page: name, password, organisation, site
  GET  /traffic-auth/signup-info?t=    {email} for a usable link, else 400
  POST /traffic-auth/signup            {email}: 200 and the same words, whether
                                       or not the address has an account; 400 for
                                       a bad address or one outside
                                       saas.allowed_domains; 429 after PER_IP
                                       forms an hour from one client address
  POST /traffic-auth/signup-finish     {token, name, password, org, host}: makes
                                       the account and signs in (Set-Cookie)

Every POST needs the same-origin check; bodies are JSON of at most 4 KiB.
The mail is made and sent on its own thread, so neither the lookup nor the
mail shows in the answer's timing. There is no captcha (standard library
only): the mailed link and the limits are the guard (docs/SAAS.md).
"""
from __future__ import annotations

from . import signup_on, signups
from .. import auth_api
from ..accounts import sessions
from ..auth_api import PREFIX, answer, read_json, text

PAGES = {"signup": "signup.html", "signup-finish": "signup-finish.html"}
NAMES = ("signup", "signup-finish", "signup-info")
SIGNUP_WORDS = ("Check your mail: a link to finish signing up is on its way. It works for "
                f"{signups.SIGNUP_HOURS} hours, once.")
DOMAIN_WORDS = "This address cannot sign up here. Ask the people who run this server."
IP_WORDS = "Too many sign-ups from this address. Try again in an hour."


def name_of(path: str) -> str:
    return path.split("?", 1)[0][len(PREFIX):] if path.startswith(PREFIX) else ""


def is_signup(path: str) -> bool:
    return name_of(path) in NAMES


def handle(h, write: bool, config, live_dir, allowed: set[str], same_origin,
           config_path=None, out=None) -> None:
    if not signup_on(config):
        return answer(h, 404, {"ok": False, "error": "not found"})
    name = name_of(h.path)
    if not write:
        if name in PAGES:
            return _page(h, PAGES[name])
        if name == "signup-info":
            return auth_api._with_db(h, config, live_dir, _info)
        return answer(h, 405, {"ok": False, "error": "wrong method"})
    if name not in ("signup", "signup-finish"):
        return answer(h, 405, {"ok": False, "error": "wrong method"})
    if not same_origin(h.headers, allowed):
        return answer(h, 403, {"ok": False, "error": "same-origin requests only"})
    form = read_json(h)
    if form is None:
        return None
    try:
        if name == "signup":
            return _signup(h, form, config, live_dir, allowed)
        return auth_api._with_db(h, config, live_dir,
                                 lambda h, db: _finish(h, db, form, config, config_path, live_dir,
                                                       out))
    except auth_api.accounts.passwords.Busy as why:
        return answer(h, 503, {"ok": False, "error": str(why)},
                      {"Retry-After": str(auth_api.BUSY_WAIT)})


def _page(h, file: str) -> None:
    try:
        data = (auth_api.PAGES_DIR / file).read_bytes()
    except OSError:
        return answer(h, 404, {"ok": False, "error": "not found"})
    h.send_response(200)
    h.send_header("Content-Type", "text/html; charset=utf-8")
    h.send_header("Content-Security-Policy", auth_api.CSP)
    h.send_header("Cache-Control", "no-store")
    h.send_header("X-Content-Type-Options", "nosniff")
    h.send_header("Referrer-Policy", "no-referrer")
    h.send_header("X-Frame-Options", "DENY")
    h.send_header("Content-Length", str(len(data)))
    h.end_headers()
    h.wfile.write(data)


def _info(h, db) -> None:
    got = signups.info(db, auth_api.query(h.path).get("t", "")[:300])
    if got is None:
        return answer(h, 400, {"ok": False, "error": "This sign-up link has expired, was "
                                                     "used already, or is not complete."})
    return answer(h, 200, {"ok": True, "email": got["email"]})


def _signup(h, form, config, live_dir, allowed) -> None:
    raw = text(form, "email", 300)
    try:
        email = auth_api.users.clean_email(raw)
    except ValueError as why:
        return answer(h, 400, {"ok": False, "error": str(why)})
    if not signups.domain_allowed(config, email):
        return answer(h, 400, {"ok": False, "error": DOMAIN_WORDS})
    ip = auth_api.client_ip(h, config)
    db = auth_api.open_db(config, live_dir)
    if db is None:
        return answer(h, 503, {"ok": False, "error": "accounts are not set up here"})
    try:
        with auth_api.accounts.db.tx(db):
            limited = signups.ip_limited(db, ip)
            if not limited:
                signups.note_ip(db, ip)
    finally:
        db.close()
    if limited:
        return answer(h, 429, {"ok": False, "error": IP_WORDS}, {"Retry-After": "3600"})

    def work():
        from ..accounts import mails as account_mails
        from . import mails
        try:
            db = auth_api.open_db(config, live_dir)
            try:
                kind, token = signups.request(db, email, ip, config)
            finally:
                db.close()
            if kind not in ("new", "exists"):
                return
            base = auth_api.base_url(config, allowed)
            if base is None:
                auth_api.note("sign-up asked but no base URL is set (access.base_url); "
                              "no mail sent")
                return
            if not account_mails.configured(config):
                auth_api.note("sign-up asked but mail is not set up; no mail sent")
                return
            if kind == "new":
                msg = mails.signup_mail(config, email,
                                        f"{base}{PREFIX}signup-finish?t={token}")
            else:
                msg = mails.exists_mail(config, email, f"{base}{PREFIX}login",
                                        f"{base}{PREFIX}forgot")
            account_mails.deliver(msg, config, email)
            auth_api.note("sign-up mail sent")
        except Exception as why:            # a thread must never take the helper down
            auth_api.note(f"sign-up mail not sent: {type(why).__name__}")

    auth_api.spawn(work)
    return answer(h, 200, {"ok": True, "message": SIGNUP_WORDS})


def _finish(h, db, form, config, config_path=None, live_dir=None, out=None) -> None:
    from .. import first_page, ingest, ingest_log
    from ..sites_api import config_sites
    try:
        got = signups.finish(db, text(form, "token", 300), text(form, "name", 100),
                             text(form, "password"), text(form, "org", 100),
                             text(form, "host", 300), config,
                             taken=config_sites(config, config_path),
                             log_root=ingest_log.root(config, ingest.history_folder(config, live_dir)))
    except ValueError as why:
        return answer(h, 400, {"ok": False, "error": str(why)})
    first_page.start(out, got["site"], config_path,     # the page is there at once,
                     before=first_page.logo_fetch(config, config_path, got["site"], live_dir,
                                                  out))   # its logo first (2.25)
    cookie, _csrf = sessions.start(db, got["user"]["id"], auth_api.client_ip(h, config),
                                   h.headers.get("User-Agent", ""))
    return answer(h, 200, {"ok": True, "next": f"/traffic/{got['site']}/", "signed_in": True},
                  {"Set-Cookie": auth_api.set_cookie(cookie)})
