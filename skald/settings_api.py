"""Settings in the dashboard, with `access.mode: sessions` (docs/SETTINGS.md).

Served by the refresh helper (refresh_server.py) the way team_api.py is,
for every site page, `/traffic/<site>/[<view>/]...`, behind nginx's session
check:

  GET  settings                        every setting for this site: its value, where
                                       it comes from, locked or not, and whether the
                                       caller may change it (with the reason when
                                       not); secrets only as {"set": true|false};
                                       for beacon.goals the events it may name, and
                                       which of them the site has counted
  POST settings/save                   {key: value, ...} (null clears a row); a value
                                       that removes stored data also needs
                                       "confirm": "<site name>"
  GET  settings/retention-preview?key=&value=
                                       how many stored days and rows a smaller
                                       window removes at the next run
  POST settings/test-mail              {to}: one short mail through the install's
                                       SMTP settings; admins; 3 per 10 minutes;
                                       only to the caller or a confirmed recipient
                                       (mail_confirm.py)
  GET  settings/audit?action=&limit=&format=csv
                                       the audit log (admins; install admins see
                                       every organisation's rows)

In basic mode every one answers 404. Every POST needs the same-origin check
and the session's X-Skald-CSRF value. Who may change what is in
settings_store.SCHEMA: an admin (or owner) for the site's own settings, an
install admin for the install's (SMTP, backups, log paths, the PageSpeed key),
an owner for the organisation's security. A key config.yml locks is
read-only for everyone.

Security (`refusal`, called by auth_api's nginx check): an organisation
that limits the session length ends older sessions (401, sign in again),
and one that requires two-step sign-in sends members without it back to
the sign-in page, which sets it up (auth_api._login).
"""
from __future__ import annotations

import csv
import io
import re
import smtplib
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from . import accounts, auth_api, settings_store as store
from .accounts import auditlog, limits, sessions, users
from .auth_api import answer, csrf_ok, read_json, text

PAGE = r"^/traffic/(?P<site>[a-z0-9.-]+)/(?:(?P<view>[a-z0-9-]+)/)?"
PATH = re.compile(PAGE + r"(?P<act>settings(?:/(?:save|retention-preview|test-mail|audit))?)$")
GETS = {"settings", "settings/retention-preview", "settings/audit"}
ADMIN = ("owner", "admin")
TEST_LIMIT, TEST_MINUTES = 3, 10
# Values only an install admin sees (a login name, server paths).
INSTALL_ONLY = ("mail.smtp.host", "mail.smtp.port", "mail.smtp.security", "mail.smtp.user",
                "sites.log_dir", "sites.log_base")
CONFIRM_WORDS = ("This removes stored data at the next run. Type the site name, {site}, "
                 "to confirm.")


def match(path: str):
    path = path.split("?", 1)[0]
    if ".." in path:
        return None
    return PATH.match(path)


def is_settings(path: str) -> bool:
    return match(path) is not None


class Ctx:
    def __init__(self, h, db, session, site, role, org, config, live_dir, history_path,
                 config_path):
        self.h, self.db, self.session, self.site = h, db, session, site
        self.role, self.org, self.live_dir = role, org, live_dir
        if history_path is None and live_dir is not None:
            history_path = Path(live_dir) / "history.sqlite"
        self.history_path, self.config_path = history_path, config_path
        self.uid = session["user_id"]
        self.install_admin = bool(session["install_admin"])
        self.config = site_config(config, config_path, site)

    @property
    def admin(self) -> bool:
        return self.role in ADMIN

    def ok(self, **body):
        return answer(self.h, 200, {"ok": True, **body})

    def no(self, code: int, error: str, **extra):
        return answer(self.h, code, {"ok": False, "error": error, **extra})


def site_config(config, config_path, site: str) -> dict:
    """The config.yml layer for `site`: the install's, or another site's
    merged file (multisite.py), with the history's folder known."""
    from .config import site_name
    got = config or {}
    if config_path is not None and site != site_name(got):
        from . import multisite
        try:
            got = next((c for c in multisite.site_configs(got, Path(config_path))
                        if site_name(c) == site), got)
        except SystemExit:
            pass
    return got


def handle(h, write: bool, config, live_dir, allowed: set[str], same_origin,
           history_path=None, config_path=None) -> None:
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
        c = Ctx(h, db, session, m.group("site"), role, org, config, live_dir,
                history_path, config_path)
        c.allowed = allowed
        if act in ("settings/audit", "settings/test-mail", "settings/retention-preview") \
                and not (c.admin or c.install_admin):
            return c.no(403, "Only an admin can do this.", role=role)
        form = {}
        if write:
            form = read_json(h)
            if form is None:
                return None
        return ROUTES[act](c, form)
    finally:
        db.close()


# ------------------------------------------------------------ the values

def _cap(c: Ctx) -> int | None:
    """The organisation's plan's retention_days_max (saas; None: no cap)."""
    from .saas import limits
    return limits.retention_cap(c.db, c.org["id"], c.config)


def described(c: Ctx) -> dict:
    """Every setting for this site, as the page draws it."""
    got = store.explain(c.config, c.site, c.db)
    cap = _cap(c)
    out = {}
    for name, entry in got.items():
        key = store.SCHEMA[name]
        may, why = store.may_edit(name, c.role, c.install_admin, c.config)
        item = {**entry, "editable": may, "reason": why, "label": key.label, "kind": key.kind,
                "scope": key.scopes[0], "who": key.who, "shrink": key.shrink}
        if key.lo is not None:
            most = store.capped(name, cap)
            item.update(lo=key.lo, hi=min(key.hi, most) if most is not None else key.hi)
        if key.choices:
            item["choices"] = list(key.choices)
        if key.kind == "events":
            item["events"] = _goal_choices(c)
        if name in INSTALL_ONLY and not c.install_admin:
            item.update(value=None, hidden=True)
        out[name] = item
    for name in store.SECRETS:
        key = store.SCHEMA[name]
        may, why = store.may_edit(name, c.role, c.install_admin, c.config)
        state = store.secret_state(c.config, name, c.live_dir)
        out[name] = {"set": state["set"], "env": state["env"], "locked": name in
                     store.locked(c.config), "editable": may, "reason": why,
                     "label": key.label, "kind": "secret", "scope": "install", "who": key.who}
    return out


def _goal_choices(c: Ctx) -> list[dict]:
    """The events beacon.goals may name for this site, each with its label
    and whether the site has counted it (event_counts, read-only)."""
    from .beacon import LABELS, allowed_events
    seen: set[str] = set()
    path = c.history_path
    if path is not None and Path(path).is_file():
        import sqlite3
        try:
            conn = sqlite3.connect(f"file:{Path(path).resolve()}?mode=ro", uri=True)
            try:
                seen = {r[0] for r in conn.execute(
                    "SELECT DISTINCT event FROM event_counts WHERE site = ?", (c.site,))}
            finally:
                conn.close()
        except sqlite3.Error:
            seen = set()
    names = [e for e in store.GOAL_EVENTS if e in allowed_events(c.config) or e in seen]
    return [{"name": e, "label": LABELS.get(e, e), "seen": e in seen} for e in names]


def settings(c: Ctx, form):
    return c.ok(site=c.site, org=c.org["name"], role=c.role, install_admin=c.install_admin,
                settings=described(c), totp_on=_totp_on(c.db, c.uid),
                mail_waiting=_waiting(c))


def _waiting(c: Ctx) -> list[str]:
    """Recipients typed on the page that have not confirmed (mail_confirm.py)."""
    from .mail_confirm import keep_confirmed
    got = store.explain(c.config, c.site, c.db)["mail.to"]
    if got["source"] not in ("site", "org"):
        return []
    own = store._from_config(c.config, store.SCHEMA["mail.to"]) or []
    return keep_confirmed(c.db, c.org["id"], got["value"], own)[1]


def _totp_on(db, uid) -> bool:
    user = users.find_user(db, user_id=uid)
    return bool(user and user["totp_on"])


def save(c: Ctx, form):
    """Every key checked first (who, lock, value, typed name); then all saved."""
    from .saas import limits
    confirm = form.pop("confirm", None)
    if not form:
        return c.no(400, "Nothing to save.")
    locked = limits.read_only(c.db, c.org["id"], c.config)      # saas: payment overdue
    if locked:
        return c.no(402, locked, read_only=True)
    cap = _cap(c)
    current = store.explain(c.config, c.site, c.db)
    checked, shrinking = {}, []
    for name, value in form.items():
        if name not in store.SCHEMA:
            return c.no(400, f"{name!r} is not a setting that can be changed here.", key=name)
        may, why = store.may_edit(name, c.role, c.install_admin, c.config)
        if not may:
            return c.no(403, why, key=name)
        try:
            checked[name] = store.validate(name, value, cap=cap)
        except store.Invalid as why:
            return c.no(400, str(why), key=name)
        key = store.SCHEMA[name]
        old = (current.get(name) or {}).get("value")
        new = checked[name] if checked[name] is not None else _fallback(c, name, cap)
        if key.shrink and isinstance(old, int) and isinstance(new, int) and new < old:
            shrinking.append(name)
        if name == "security.require_totp" and checked[name] and not _totp_on(c.db, c.uid):
            return c.no(400, "Turn on two-step sign-in for your own account first "
                             "(Settings > Your account), or you would be signed out.", key=name)
    if shrinking and (not isinstance(confirm, str) or confirm.strip().lower() != c.site):
        return c.no(409, CONFIRM_WORDS.format(site=c.site), needs_confirm=True, keys=shrinking)
    saved = []
    for name, value in checked.items():
        scope = store.scope_for(name, c.site, c.org["id"])
        secret = None
        if store.SCHEMA[name].kind == "secret":
            path = store.secrets_path(c.config, c.live_dir)
            if path is None:
                return c.no(503, "The server has no folder for secrets.json.", key=name)
            secret = (path, store.secret_name(c.config, name))
        try:
            store.put(c.db, scope, name, value, c.uid, secret)
        except (store.Invalid, PermissionError) as why:
            return c.no(400, str(why), key=name, saved=saved)
        saved.append(name)
    waiting = _waiting(c)
    if "mail.to" in saved and waiting:
        from .mail_confirm import ask
        ask(c.db, c.config, getattr(c, "allowed", None), c.org, c.site, waiting)
    return c.ok(saved=saved, settings=described(c), mail_waiting=waiting)


def _fallback(c: Ctx, name: str, cap: int | None = None):
    """What a key falls back to when its row here is cleared (cut to the
    plan's cap, as explain cuts it)."""
    got = _uncapped_fallback(c, name)
    most = store.capped(name, cap)
    return min(got, most) if most is not None and isinstance(got, int) else got


def _uncapped_fallback(c: Ctx, name: str):
    scope = store.scope_for(name, c.site, c.org["id"])
    kind = scope.split(":", 1)[0]
    rest = {"site": ("org", "install"), "org": ("install",), "install": ()}[kind]
    for k in rest:
        s = "install" if k == "install" else f"org:{c.org['id']}"
        got = store.get(c.db, s, name)
        if got is not None and k in store.SCHEMA[name].scopes:
            return got
    got = store._from_config(c.config, store.SCHEMA[name])
    return got if got is not None else store.SCHEMA[name].default


# ------------------------------------------------------ retention preview

def _today(c: Ctx) -> date:
    from .window import zone
    try:
        tz = zone(store.apply(c.config, c.site, c.live_dir))
    except Exception:                   # noqa: BLE001 - a bad zone: UTC for a preview
        tz = timezone.utc
    return datetime.now(timezone.utc).astimezone(tz).date()


def _count(path, sql: str, args) -> tuple[int, int, str | None, str | None]:
    """(rows, distinct days, first day, last day) from history, read-only."""
    import sqlite3
    if path is None or not Path(path).is_file():
        return 0, 0, None, None
    try:
        conn = sqlite3.connect(f"file:{Path(path).resolve()}?mode=ro", uri=True)
        try:
            row = conn.execute(sql, args).fetchone()
        finally:
            conn.close()
    except sqlite3.Error:
        return 0, 0, None, None
    return int(row[0] or 0), int(row[1] or 0), row[2], row[3]


def _site_rows(table: str, extra: str = "") -> str:
    return (f"SELECT COUNT(*), COUNT(DISTINCT day), MIN(day), MAX(day) FROM {table} "
            f"WHERE day < ? AND (site = ? OR substr(site, 1, ?) = ?){extra}")


def preview(c: Ctx, form):
    from .store import VIEW_MARK
    q = auth_api.query(c.h.path)
    name = q.get("key") or ""
    if name not in store.SCHEMA or not store.SCHEMA[name].shrink:
        return c.no(400, "Ask about one of the retention settings.")
    try:
        value = store.validate(name, q.get("value"))
    except store.Invalid as why:
        return c.no(400, str(why))
    if value is None:
        value = _fallback(c, name, _cap(c))
    old = store.explain(c.config, c.site, c.db)[name]["value"]
    body = {"key": name, "value": value, "current": old, "shrinks": bool(value < old),
            "rows": 0, "days": 0, "first": None, "last": None, "files": 0}
    if not body["shrinks"]:
        return c.ok(**body)
    if name.startswith("backup."):
        body["files"] = _backups_gone(c, name, value)
        return c.ok(**body)
    cutoff = (_today(c) - timedelta(days=value)).isoformat()
    mark = c.site + VIEW_MARK
    site_args = (cutoff, c.site, len(mark), mark)
    history = c.history_path
    if name == "report.retention_days":
        marks = ",".join("?" * len(store.DETAIL_KINDS))
        got = _count(history, _site_rows("day_extras", f" AND kind IN ({marks})"),
                     (*site_args, *store.DETAIL_KINDS))
    elif name == "report.journey_days":
        got = _count(history, _site_rows("journeys"), site_args)
    elif name == "privacy.keep_days":    # visits with addresses (conversions.sqlite)
        from .people.visits import preview as people_preview
        got = people_preview(c.config, Path(history).parent if history else None, c.site, cutoff)
    elif name == "visitors.repeat_days":
        got = _count(history, _site_rows("visitor_days"), site_args)
    else:                               # beacon.keep_days: the day's counts
        a = _count(history, _site_rows("event_counts"), site_args)
        b = _count(history, _site_rows("event_days"), site_args)
        got = (a[0] + b[0], max(a[1], b[1]), min(filter(None, (a[2], b[2])), default=None),
               max(filter(None, (a[3], b[3])), default=None))
        body["files"] = _spool_gone(c, cutoff)
    body.update(rows=got[0], days=got[1], first=got[2], last=got[3])
    return c.ok(**body)


def _spool_gone(c: Ctx, cutoff: str) -> int:
    from .beacon import spool_dir
    try:
        spool = spool_dir(c.config, c.config_path, c.live_dir)
        found = 0
        for path in Path(spool).glob("*.json*"):
            stem = path.name.split(".", 1)[0].replace("stats-", "")
            if re.match(r"^\d{4}-\d\d-\d\d$", stem) and stem < cutoff:
                found += 1
        return found
    except OSError:
        return 0


def _backups_gone(c: Ctx, name: str, value: int) -> int:
    from . import backup
    raw = ((c.config or {}).get("backup") or {}).get("dir")
    folder = Path(str(raw)) if raw and Path(str(raw)).is_absolute() else (
        Path(c.live_dir) / "backups" if c.live_dir is not None else None)
    if folder is None or not folder.is_dir():
        return 0
    files = backup._dailies(folder) if name == "backup.daily" else backup._weeklies(folder)
    return max(0, len(files) - value)


# -------------------------------------------------------------- test mail

def test_mail(c: Ctx, form):
    from . import mailer
    from .accounts import db as base
    try:
        to = users.clean_email(text(form, "to", 300))
    except ValueError as why:
        return c.no(400, str(why))
    from .mail_confirm import keep_confirmed
    own = [c.session["email"], *(store._from_config(c.config, store.SCHEMA["mail.to"]) or [])]
    if not keep_confirmed(c.db, c.org["id"], [to], own)[0]:
        return c.no(403, "A test mail goes to your own address or to a recipient who has "
                         "confirmed (the link in their confirm mail).")
    merged = store.apply(c.config, c.site, c.live_dir)
    missing = _not_set_up(merged.get("mail") or {}, c.install_admin)
    if missing:
        return c.no(400, missing)
    key = f"testmail:{c.uid}"
    with base.tx(c.db):
        if limits.count(c.db, key, TEST_MINUTES) >= TEST_LIMIT:
            return answer(c.h, 429, {"ok": False, "error": f"At most {TEST_LIMIT} test mails "
                                     f"in {TEST_MINUTES} minutes. Try again later."},
                          {"Retry-After": str(TEST_MINUTES * 60)})
        limits.note_failure(c.db, key)
    section = {**(merged.get("mail") or {}), "to": [to]}
    keep = {k: merged[k] for k in ("_resolved", "history", "hooks", "access") if k in merged}
    if c.live_dir is not None:
        keep["_resolved"] = {**keep.get("_resolved", {}),
                             "history_db": str(Path(c.live_dir) / "history.sqlite")}
    try:
        cfg = mailer.settings({**keep, "mail": section})
        now = datetime.now(timezone.utc)
        words = (f"This is a test mail from Skald for {c.site}, sent by "
                 f"{c.session['email']} from Settings > Mail.\n\nIf you can read it, the "
                 "mail settings work.")
        msg = mailer._message(cfg, f"Test mail for {c.site}", words,
                              f"<html><body><p>{_esc(words)}</p></body></html>", now)
        mailer.send(msg, cfg)
    except mailer.Refused as why:
        auditlog.record(c.db, c.org["id"], c.uid, "mail.test", to, f"refused: {why}")
        return c.no(400, f"Not sent: {why}.")
    except (OSError, smtplib.SMTPException) as why:
        auditlog.record(c.db, c.org["id"], c.uid, "mail.test", to,
                        f"failed: {type(why).__name__}")
        return c.no(502, f"The mail server did not take it: {type(why).__name__}: "
                         f"{str(why)[:200]}")
    auditlog.record(c.db, c.org["id"], c.uid, "mail.test", to, "sent")
    return c.ok(sent=True, to=to)


def _not_set_up(mail: dict, install_admin: bool) -> str | None:
    """A plain sentence when the sender or the SMTP server is missing, or None."""
    if not str(mail.get("from") or "").strip():
        what = "Set the sender address first (Mail server (SMTP) > Sender address)."
    elif not str(mail.get("host") or "").strip():
        what = "Set the mail server first (Mail server (SMTP) > SMTP server)."
    else:
        return None
    return what if install_admin else what + " An install admin sets it."


def _esc(words: str) -> str:
    from html import escape
    return escape(words).replace("\n\n", "</p><p>")


# --------------------------------------------------------------- audit log

def audit(c: Ctx, form):
    q = auth_api.query(c.h.path)
    try:
        limit = max(1, min(int(q.get("limit") or (5000 if q.get("format") == "csv" else 500)),
                           5000))
    except ValueError:
        limit = 500
    org_id = None if c.install_admin else c.org["id"]
    entries = auditlog.recent(c.db, org_id, limit, q.get("action") or None)
    where, args = ("", ()) if org_id is None else (" WHERE org_id = ?", (org_id,))
    actions = [r[0] for r in c.db.execute(
        f"SELECT DISTINCT action FROM audit{where} ORDER BY action", args)]
    if q.get("format") == "csv":
        return _csv(c, entries)
    return c.ok(entries=entries, actions=actions, all_orgs=org_id is None)


def _cell(value) -> str:
    """A CSV cell a spreadsheet never runs as a formula."""
    text_ = "" if value is None else str(value)
    return "'" + text_ if text_[:1] in ("=", "+", "-", "@", "\t", "\r") else text_


def _csv(c: Ctx, entries: list[dict]):
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["at", "actor", "action", "target", "detail"])
    for e in entries:
        w.writerow([_cell(e["at"]), _cell(e.get("actor_email") or e["actor"]),
                    _cell(e["action"]), _cell(e["target"]), _cell(e["detail"])])
    data = out.getvalue().encode("utf-8")
    h = c.h
    h.send_response(200)
    h.send_header("Content-Type", "text/csv; charset=utf-8")
    h.send_header("Content-Disposition", f'attachment; filename="skald-audit-{c.site}.csv"')
    h.send_header("Cache-Control", "no-store")
    h.send_header("X-Content-Type-Options", "nosniff")
    h.send_header("Content-Length", str(len(data)))
    h.end_headers()
    h.wfile.write(data)
    return None


ROUTES = {"settings": settings, "settings/save": save, "settings/retention-preview": preview,
          "settings/test-mail": test_mail, "settings/audit": audit}


# --------------------------------------------------------------- security

def org_setting(db, org_id, name: str):
    return store.get(db, f"org:{org_id}", name) if org_id is not None else None


def totp_required(db, user_id) -> bool:
    """True when any organisation the user belongs to requires two-step sign-in."""
    for org in accounts.list_orgs(db, user_id):
        if org_setting(db, org["id"], "security.require_totp") is True:
            return True
    return False


def refusal(db, who: dict, org: dict | None) -> int | None:
    """401 when this organisation's security settings end the session (too
    old, or two-step sign-in required and not on: the sign-in page sets it
    up); None when the session may go on."""
    if org is None:
        return None
    days = org_setting(db, org["id"], "security.session_days")
    if isinstance(days, int) and not isinstance(days, bool):
        row = db.execute("SELECT created_at FROM sessions WHERE id_hash = ?",
                         (who["session_id"],)).fetchone()
        if row is not None and row[0] <= accounts.db.shift(-days * 86400):
            db.execute("DELETE FROM sessions WHERE id_hash = ?", (who["session_id"],))
            return 401
    if org_setting(db, org["id"], "security.require_totp") is True and \
            not _totp_on(db, who["user_id"]):
        return 401
    return None
