"""Security > Alerts, "Your security alerts" (security_notify.py), served by the helper under
the `settings/` prefix nginx already passes on:

  GET  settings/security-prefs     your choice for this site: {alerts, mode, default, role,
                                   email, summary_at, open: [the open items]}
  POST settings/security-prefs     {alerts: true|false, mode: "now"|"daily"}: "daily" is the
                                   daily summary (summary_mail.py) at `summary_at` ("off"
                                   when this server does not send it), the default
  POST settings/security-test      a test security alert to you (owners and admins), at most
                                   TEST_LIMIT in TEST_MINUTES; written to the audit log

Any member of the site's organisation sets their own choice (a viewer may opt in); nobody
sets anyone else's. Every POST needs the same-origin check and the session's CSRF value. In
basic mode every route answers 404 (no accounts, no team).
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from . import auth_api, security_notify
from .accounts import sessions, users
from .auth_api import answer, csrf_ok

PATH = re.compile(r"^/traffic/(?P<site>[a-z0-9.-]+)/(?:(?P<view>[a-z0-9-]+)/)?"
                  r"(?P<act>settings/security-(?:prefs|test))$")
TEST_LIMIT, TEST_MINUTES = 3, 10


def match(path: str):
    path = path.split("?", 1)[0]
    return None if ".." in path else PATH.match(path)


def is_security(path: str) -> bool:
    return match(path) is not None


def _config(config, config_path, site, live_dir) -> dict:
    from .settings_api import site_config
    from . import settings_store as store
    return store.apply(site_config(config, config_path, site), site, live_dir)


def handle(h, write: bool, config, live_dir, allowed, same_origin, config_path=None,
           send=None) -> None:
    if not auth_api.sessions_mode(config):
        return answer(h, 404, {"ok": False, "error": "not found"})
    m = match(h.path)
    act = m.group("act")
    if act == "settings/security-test" and not write:
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
            return answer(h, 403, {"ok": False, "error": "The page is out of date. Reload it "
                                                         "and try again."})
        site = m.group("site")
        role, org = users.site_role(db, session["user_id"], site)
        if org is None or role is None:
            return answer(h, 403, {"ok": False, "error": "You are not a member here."})
        uid = session["user_id"]
        if act == "settings/security-prefs":
            if write:
                form = _form(h)
                if form is None:
                    return None
                mode = str(form.get("mode") or security_notify.DEFAULT_MODE)
                if mode not in ("now", "daily"):
                    return answer(h, 400, {"ok": False, "error": "mode is now or daily"})
                pref = security_notify.set_prefs(db, uid, site, bool(form.get("alerts")), mode)
            else:
                pref = security_notify.prefs_of(db, uid, role, site)
            from .summary_mail import at
            return answer(h, 200, {"ok": True, **pref, "role": role, "email": session["email"],
                                   "summary_at": at(), **security_notify.public(db, site)})
        if role not in ("owner", "admin"):
            return answer(h, 403, {"ok": False, "error": "Only an owner or an admin can send a "
                                                         "test security alert."})
        since = (datetime.now(timezone.utc) - timedelta(minutes=TEST_MINUTES)).strftime(
            "%Y-%m-%dT%H:%M:%SZ")
        security_notify._ready(db)
        recent = db.execute("SELECT COUNT(*) FROM security_sends WHERE user_id = ? AND how = "
                            "'test' AND sent_at >= ?", (uid, since)).fetchone()[0]
        if recent >= TEST_LIMIT:
            return answer(h, 429, {"ok": False, "error": f"At most {TEST_LIMIT} test alerts in "
                                                         f"{TEST_MINUTES} minutes."})
        error = security_notify.test_send(db, _config(config, config_path, site, live_dir), site,
                                          {"user_id": uid, "email": session["email"]},
                                          org["id"], send=send)
        if error:
            return answer(h, 502, {"ok": False, "error": "The mail server did not take it "
                                                         f"({error}). Check Settings > Mail & reports."})
        return answer(h, 200, {"ok": True, "sent_to": session["email"]})
    finally:
        db.close()


def _form(h) -> dict | None:
    import json
    try:
        length = int(h.headers.get("Content-Length") or 0)
    except ValueError:
        length = -1
    if length < 0 or length > 4096:
        answer(h, 400, {"ok": False, "error": "body too large"})
        return None
    try:
        got = json.loads((h.rfile.read(length) if length else b"{}").decode("utf-8", "replace") or "{}")
    except ValueError:
        got = None
    if not isinstance(got, dict):
        answer(h, 400, {"ok": False, "error": "a JSON object, please"})
        return None
    return got
