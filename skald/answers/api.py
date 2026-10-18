"""AI answers in the dashboard, with `access.mode: sessions` (docs/AI-ANSWERS.md).

Served by the refresh helper (refresh_server.py) like integrations_api.py,
for every site page, `/traffic/<site>/[<view>/]...`:

  GET  ai-answers                     the site's lists, its profiles (paused ones
                                      too, never deleted ones), which keys are set
                                      (never a key), each assistant's price and
                                      how it is told the place, each profile's
                                      estimate, and whether the caller may change
                                      them; any member
  GET  ai-answers/answer?id=N         one stored answer in full (the question as
                                      sent, the text, the cited URLs); any member
  POST ai-answers/lists               {questions, brands, competitors, keep_days}
  POST ai-answers/profiles/save       {id?, ...profile}: a new profile, or a new
                                      version of one
  POST ai-answers/profiles/duplicate  {id}
  POST ai-answers/profiles/pause      {id}
  POST ai-answers/profiles/resume     {id}
  POST ai-answers/profiles/delete     {id}: leaves the lists; results stay
  POST ai-answers/profiles/run        {id}: run at the next 15-minute tick

POSTs are for the site's admins and owners and install admins, need the
same-origin check and the session's X-Skald-CSRF value, and are written to
the audit log. An organisation whose plan is locked (saas) reads but cannot
change. In basic mode every route answers 404.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .. import auth_api
from ..accounts import auditlog, sessions, users
from ..auth_api import answer, csrf_ok
from . import KEEP_DAYS, LOCATION, LOCATION_WORDS, NAMES, PROVIDERS, estimate, keys_set, model, price
from . import profiles as P
from . import store

PAGE = r"^/traffic/(?P<site>[a-z0-9.-]+)/(?:(?P<view>[a-z0-9-]+)/)?"
PATH = re.compile(PAGE + r"(?P<act>ai-answers(?:/(?:answer|lists|profiles/(?:save|duplicate|"
                         r"pause|resume|delete|run)))?)$")
GETS = {"ai-answers", "ai-answers/answer"}
ADMIN = ("owner", "admin")
MAX_BODY = 65536


def match(path: str):
    path = path.split("?", 1)[0]
    return None if ".." in path else PATH.match(path)


def is_answers(path: str) -> bool:
    return match(path) is not None


def _body(h) -> dict | None:
    try:
        length = int(h.headers.get("Content-Length") or 0)
    except ValueError:
        length = -1
    if length < 0 or length > MAX_BODY:
        answer(h, 413 if length > 0 else 400, {"ok": False, "error": "The request is too large."})
        return None
    raw = h.rfile.read(length) if length else b""
    try:
        got = json.loads(raw.decode("utf-8") or "{}")
    except (UnicodeDecodeError, ValueError):
        got = None
    if not isinstance(got, dict):
        answer(h, 400, {"ok": False, "error": "Send a JSON object."})
        return None
    return got


class Ctx:
    def __init__(self, h, db, session, site, role, org, config, folder, live_dir):
        self.h, self.db, self.session, self.site, self.role, self.org = h, db, session, site, role, org
        self.config, self.folder, self.live_dir = config or {}, folder, live_dir
        self.uid = session["user_id"]
        self.install_admin = bool(session["install_admin"])

    @property
    def admin(self) -> bool:
        return self.role in ADMIN or self.install_admin

    def who(self) -> str:
        return str(self.session.get("email") or self.uid)

    def ok(self, **body):
        return answer(self.h, 200, {"ok": True, **body})

    def no(self, code: int, error: str):
        return answer(self.h, code, {"ok": False, "error": error})

    def log(self, action: str, detail: str = "") -> None:
        auditlog.record(self.db, self.org["id"] if self.org else None, self.uid, action,
                        f"ai-answers {self.site}", detail[:300])


def handle(h, write: bool, config, live_dir, allowed, same_origin, history_path=None,
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
            return answer(h, 403, {"ok": False, "error": "The page is out of date. Reload it and try again."})
        role, org = users.site_role(db, session["user_id"], m.group("site"))
        if role is None and not session["install_admin"]:
            return answer(h, 403, {"ok": False, "error": "You are not a member here."})
        from ..settings_api import site_config
        site = m.group("site")
        conf = site_config(config, config_path, site)
        folder = Path(history_path).parent if history_path else Path(live_dir)
        c = Ctx(h, db, session, site, role, org, conf, folder, live_dir)
        form = {}
        if write:
            if not c.admin:
                return c.no(403, "Only an admin can change AI answers.")
            locked = _locked(c)
            if locked:
                return c.no(403, locked)
            form = _body(h)
            if form is None:
                return None
        return ROUTES[act](c, form)
    finally:
        db.close()


def _locked(c: Ctx) -> str | None:
    from ..saas import limits
    return limits.read_only(c.db, c.org["id"] if c.org else None, c.config)


# ----------------------------------------------------------------- reads

def described(c: Ctx, adb) -> dict:
    keyed = keys_set(c.config, c.live_dir)
    lists = store.lists(adb, c.site)
    profs = []
    for p in P.listed(adb, c.site):
        asks = P.resolved(p, lists)
        profs.append({**p, "asks_questions": len(asks["questions"]),
                      "estimate": estimate(p, len(asks["questions"]), c.config, keyed)})
    return {"site": c.site, "lists": {**lists, "keep_days": lists["keep_days"] or KEEP_DAYS},
            "profiles": profs, "keys": keyed, "editable": c.admin,
            "providers": [{"id": x, "name": NAMES[x], "model": model(c.config, x),
                           "location": LOCATION[x], "how": LOCATION_WORDS[x],
                           "price": price(c.config, x), "key": keyed[x]} for x in PROVIDERS]}


def get_all(c: Ctx, form: dict):
    with store.opened(c.folder) as adb:
        return c.ok(**described(c, adb))


def get_answer(c: Ctx, form: dict):
    raw = auth_api.query(c.h.path).get("id", "")
    if not raw.isdigit():
        return c.no(400, "Which answer? Give its id.")
    with store.opened(c.folder) as adb:
        r = adb.execute("SELECT * FROM answers WHERE site = ? AND id = ?", (c.site, int(raw))).fetchone()
        if r is None:
            return c.no(404, "No such answer for this site.")
        return c.ok(answer=store.answer_row(r))


# ---------------------------------------------------------------- writes

def save_lists(c: Ctx, form: dict):
    try:
        got = {"questions": P.questions(form.get("questions")), "brands": P.brands(form.get("brands")),
               "competitors": P.competitors(form.get("competitors"))}
        keep = form.get("keep_days")
        got["keep_days"] = None if keep in (None, "") else P._number(keep, "Days kept", 30, 3650, True)
    except P.Invalid as why:
        return c.no(400, str(why))
    with store.opened(c.folder) as adb:
        store.save_lists(adb, c.site, got, c.who())
        c.log("ai_answers.lists", f"{len(got['questions'])} questions, {len(got['brands'])} brand "
              f"terms, {len(got['competitors'])} competitors")
        return c.ok(**described(c, adb))


def save_profile(c: Ctx, form: dict):
    try:
        body = P.check(form)
        with store.opened(c.folder) as adb:
            if form.get("id") not in (None, ""):
                version = P.update(adb, c.site, form["id"], body, c.who())
                c.log("ai_answers.profile.edit", f"profile {form['id']} v{version}: {body['name']}")
            else:
                pid = P.create(adb, c.site, body, c.who())
                c.log("ai_answers.profile.add", f"profile {pid}: {body['name']}")
            return c.ok(**described(c, adb))
    except P.Invalid as why:
        return c.no(400, str(why))


def _act(name: str):
    def act(c: Ctx, form: dict):
        pid = form.get("id")
        try:
            with store.opened(c.folder) as adb:
                if name == "duplicate":
                    P.duplicate(adb, c.site, pid, c.who())
                elif name in ("pause", "resume"):
                    P.pause(adb, c.site, pid, name == "pause", c.who())
                elif name == "delete":
                    P.delete(adb, c.site, pid, c.who())
                else:
                    P.request_run(adb, c.site, pid)
                c.log(f"ai_answers.profile.{name}", f"profile {pid}")
                return c.ok(**described(c, adb))
        except P.Invalid as why:
            return c.no(404 if "No such" in str(why) else 400, str(why))
    return act


ROUTES = {"ai-answers": get_all, "ai-answers/answer": get_answer, "ai-answers/lists": save_lists,
          "ai-answers/profiles/save": save_profile,
          **{f"ai-answers/profiles/{n}": _act(n) for n in ("duplicate", "pause", "resume", "delete", "run")}}
