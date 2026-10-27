"""Recorded journeys on the dashboard (2.43, recorded/; docs/JOURNEYS.md), with
`access.mode: sessions`. Served by the refresh helper for every site page,
`/traffic/<site>/[<view>/]recorded...`:

  GET  recorded?first=D&last=D     the period's sessions the site sent (newest first,
                                   at most 500) and their figures, each recounted from
                                   the raw events (audit_journeys.check): a period that
                                   does not match says "withheld" and shows no figure.
                                   Every member who reads the site; the address and the
                                   email kept only for owners and admins
  GET  recorded/session?ref=R      one session, every event (R: s and 12 hex); for owners
                                   and admins also the kept log visits linked to it (the
                                   same address inside its time)
  GET  recorded/visit?day=D&seq=S  the sessions linked to one kept log visit (the visitor
                                   drawer): owners and admins only, written to the audit
                                   log ("recorded.visit", never a value)
  GET  recorded/status             Settings › Leads & tools: connected (a secret set, and
                                   where), the receiver's and the helper's addresses, the
                                   last event received, the last 30 days' counts: admins
  POST recorded/connect            make or rotate the site's journey secret, shown once
                                   in the answer and kept 0600 (secrets.json); admins,
                                   same origin and the session's CSRF value; audited

Every answer is the site's own: these figures are never added to the log's.
"""
from __future__ import annotations

import re
import sqlite3
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

from . import auth_api
from .accounts import auditlog, sessions, users
from .auth_api import answer, csrf_ok, read_json
from .recorded import LABEL, TOOL

PAGE = r"^/traffic/(?P<site>[a-z0-9.-]+)/(?:(?P<view>[a-z0-9-]+)/)?"
PATH = re.compile(PAGE + r"recorded(?:/(?P<act>session|visit|status|connect))?$")
REF = re.compile(r"^s[0-9a-f]{12}$")
DAY = re.compile(r"^\d{4}-\d\d-\d\d$")
ADMIN = ("owner", "admin")
MOST_DAYS = 400


def match(path: str):
    path = path.split("?", 1)[0]
    return None if ".." in path else PATH.match(path)


def is_recorded(path: str) -> bool:
    return match(path) is not None


class Ctx:
    def __init__(self, h, db, session, site, role, org, config, live_dir, config_path):
        from .conversions.hooks import history_folder
        self.h, self.db, self.session, self.site = h, db, session, site
        self.role, self.org, self.config = role, org, config or {}
        self.config_path = config_path
        self.uid = session["user_id"]
        self.admin = role in ADMIN or bool(session["install_admin"])
        self.folder = Path(live_dir) if live_dir is not None else \
            history_folder(self.config, config_path)

    def ok(self, **body):
        return answer(self.h, 200, {"ok": True, **body})

    def no(self, code: int, error: str, **extra):
        return answer(self.h, code, {"ok": False, "error": error, **extra})

    def log(self, action: str, detail: str = "", target: str = "") -> None:
        auditlog.record(self.db, self.org["id"] if self.org else None, self.uid, action,
                        target or self.site, detail)

    def conf(self) -> dict:
        """The site's config with its Settings rows applied."""
        from .conversions.hooks import site_configs
        from .settings_store import apply
        conf = site_configs(self.config, self.config_path).get(self.site) or self.config
        try:
            return apply(conf, self.site, self.folder)
        except Exception:                  # noqa: BLE001 - the config's own values
            return conf

    def store(self):
        """conversions.sqlite opened read-only, or None when there is none yet."""
        from .conversions.store import path_for
        path = path_for(self.config, self.folder)
        if path is None or not Path(path).is_file():
            return None
        db = sqlite3.connect(f"file:{Path(path).resolve()}?mode=ro", uri=True, timeout=10)
        return db


def handle(h, write: bool, config, live_dir, allowed: set[str], same_origin,
           config_path=None) -> None:
    if not auth_api.sessions_mode(config):
        return answer(h, 404, {"ok": False, "error": "not found"})
    m = match(h.path)
    act = m.group("act") or ""
    if write != (act == "connect"):
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
        if act in ("visit", "status", "connect") and not c.admin:
            return c.no(403, "Not available to your role.")
        form = read_json(h) if write else auth_api.query(h.path)
        if form is None:
            return None
        return ROUTES[act](c, form)
    finally:
        db.close()


# ------------------------------------------------------------------- reading

def _zone(c: Ctx):
    from .window import zone
    return zone(c.conf())


def _span(c: Ctx, form) -> tuple[str, str] | None:
    """[start, end) in UTC for the days first..last in the site's zone."""
    first, last = form.get("first") or "", form.get("last") or ""
    if not DAY.match(first) or not DAY.match(last):
        return None
    a, b = date.fromisoformat(first), date.fromisoformat(last)
    if b < a or (b - a).days > MOST_DAYS:
        return None
    tz = _zone(c)
    start = datetime.combine(a, time(0), tzinfo=tz).astimezone(timezone.utc)
    end = datetime.combine(b + timedelta(days=1), time(0), tzinfo=tz).astimezone(timezone.utc)
    return start.strftime("%Y-%m-%dT%H:%M:%SZ"), end.strftime("%Y-%m-%dT%H:%M:%SZ")


def _connected(c: Ctx) -> dict:
    from .conversions.secrets_store import Exposed, find
    try:
        value, where = find(c.conf(), c.folder, c.site, TOOL)
    except Exposed:
        return {"connected": False, "where": "", "problem": "the secrets file is not 0600"}
    return {"connected": bool(value), "where": "env" if where.startswith("env") else where}


def listing(c: Ctx, form):
    from . import audit_journeys
    from .recorded import queries
    span = _span(c, form)
    if span is None:
        return c.no(400, "Give first and last as days (YYYY-MM-DD), at most 400 days apart.")
    db = c.store()
    out = {"label": LABEL, **_connected(c), "first": form["first"], "last": form["last"],
           "private": c.admin}
    if db is None:
        return c.ok(**out, state="ok", figures=queries.figures(_empty(), c.site, *span),
                    sessions=[])
    try:
        figs = queries.figures(db, c.site, *span)
        problems = audit_journeys.check(db, c.site, *span, figs)
        got = queries.sessions(db, c.site, *span, private=c.admin)
    finally:
        db.close()
    if problems:
        # Every figure reconciles, or it is withheld: the list stays, the counts go.
        return c.ok(**out, state="withheld", figures=None, sessions=got,
                    why="The figures did not match their recount from the raw events.",
                    **({"problems": problems[:10]} if c.admin else {}))
    return c.ok(**out, state="ok", figures=figs, sessions=got)


def _empty():
    db = sqlite3.connect(":memory:")
    return db


def one_session(c: Ctx, form):
    from .recorded import queries
    ref = form.get("ref") or ""
    if not REF.match(ref):
        return c.no(400, "That session is not one Skald keeps.")
    db = c.store()
    if db is None:
        return c.no(404, "That session is no longer kept.")
    try:
        got = queries.session(db, c.site, ref, private=c.admin)
        visits = queries.log_visits(db, c.site, ref) if got and c.admin else []
    finally:
        db.close()
    if got is None:
        return c.no(404, "That session is no longer kept.")
    if c.admin:
        c.log("recorded.session", "one recorded session viewed")
    return c.ok(label=LABEL, session=got, visits=visits, private=c.admin)


def visit(c: Ctx, form):
    from .firsttouch import match_vids
    from .recorded import queries
    day, seq = form.get("day") or "", form.get("seq") or ""
    if not DAY.match(day) or not seq.isdigit():
        return c.no(400, "Give the visit's day and number.")
    db = c.store()
    if db is None:
        return c.ok(label=LABEL, sessions=[], **_connected(c))
    try:
        have = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        if "visits" not in have:
            return c.ok(label=LABEL, sessions=[], **_connected(c))
        row = db.execute("SELECT start, end, ip, landing FROM visits WHERE site = ? AND day = ? "
                         "AND seq = ?", (c.site, day, int(seq))).fetchone()
        if row is None:
            return c.ok(label=LABEL, sessions=[], **_connected(c))
        vid = None
        if "journeys" in have:
            from .conversions.store import parse
            got = match_vids(db, c.site, [(0, parse(row[0]), row[3] or "")],
                             parse(row[1] or row[0]) + timedelta(seconds=60))
            vid = got.get(0)
        found = queries.for_visit(db, c.site, {"start": row[0], "end": row[1], "ip": row[2]},
                                  vid, private=True)
    finally:
        db.close()
    c.log("recorded.visit", f"{len(found)} recorded session(s) linked to one visit")
    return c.ok(label=LABEL, sessions=found, **_connected(c))


def status(c: Ctx, form):
    from .conversions.store import path_for
    from .integrations_api import _origin
    from .recorded import store
    base = _origin(c)
    out = {"label": LABEL, "site": c.site, **_connected(c),
           "url": f"{base}/traffic-hooks/{c.site}/journey",
           "withdraw_url": f"{base}/traffic-hooks/{c.site}/journey/withdraw",
           "helper": f"{base}/traffic-js/journeys.js", "last_received": None, "counts": {},
           "events_30d": 0}
    path = path_for(c.config, c.folder)
    if path is not None and Path(path).is_file():
        db = c.store()
        try:
            if store.present(db):
                since = (datetime.now(timezone.utc) - timedelta(days=30))
                out["last_received"] = store.last_received(db, c.site)
                out["counts"] = store.counts(db, c.site, since.date().isoformat())
                out["events_30d"] = int(db.execute(
                    "SELECT COUNT(*) FROM recorded_events WHERE site = ? AND received_at >= ?",
                    (c.site, since.strftime("%Y-%m-%dT%H:%M:%SZ"))).fetchone()[0])
        finally:
            db.close()
    return c.ok(**out)


def connect(c: Ctx, form):
    from .conversions import secrets_store
    from .integrations_api import _locked, _origin
    why = _locked(c, c.site)
    if why:
        return c.no(402, why, read_only=True)
    env = secrets_store.env_name(c.conf(), c.site, TOOL)
    if env:
        return c.no(409, f"This site's journey secret is read from the server's environment "
                         f"({env}); change it there.")
    path = secrets_store.path_for(c.config, c.folder)
    try:
        had = bool(secrets_store.load(path).get(secrets_store.key(c.site, TOOL)))
    except secrets_store.Exposed as err:
        return c.no(500, f"{err}. Fix it on the server first.")
    value = secrets_store.make()
    secrets_store.put(path, secrets_store.key(c.site, TOOL), value)
    c.log("hook.secret", "rotated" if had else "made", f"{c.site}/{TOOL}")
    base = _origin(c)
    return c.ok(site=c.site, secret=value, rotated=had,
                url=f"{base}/traffic-hooks/{c.site}/journey",
                withdraw_url=f"{base}/traffic-hooks/{c.site}/journey/withdraw",
                helper=f"{base}/traffic-js/journeys.js")


ROUTES = {"": listing, "session": one_session, "visit": visit, "status": status,
          "connect": connect}
