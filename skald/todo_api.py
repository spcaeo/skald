"""Overview > Insights' to-dos and Site > Not found's fixes, served by the helper under the
`settings/` prefix nginx already passes on (2.35):

  GET  settings/todos       {marks: {item: {state, day, at, first_day}}, role, can_mark,
                            mail: {ready, why}, team: [{id, email, role}] (owners and
                            admins only: who a to-do can be sent to)}
  POST settings/todos       {item, state}: mark a to-do "done", "notnow" or "open" again,
                            or an old address ("path:/old/") "fixed" or "open"
                            (todo_marks.py); owners and admins. A page's change:
                            {item: "page:/x/", state: "changed", day, kind, note}, or
                            {item, state: "open", day} to stop tracking it; GET's
                            `changes` lists the changes tracked now
  POST settings/todo-send   {item, to}: mail one to-do to a team member (`to`: their
                            account id), with its rows as a CSV file attached and the
                            link to it; owners and admins, at most SEND_LIMIT in
                            SEND_MINUTES

Every change and every mail is a row in the organisation's audit log ("todo.marked",
"todo.sent": who, which item, never the rows). The mail goes through the install's own
mail server (mailer.py, Settings > Mail & reports); without one the dialog is not offered and the
answer says why. Who it goes to must be a confirmed member of the site's organisation.
The link in the mail opens the to-do with its list; whoever opens it signs in first, and
someone without rights to the site sees "not available to you". In basic mode (no
accounts) every route answers 404: nothing can be marked or sent.
"""
from __future__ import annotations

import csv
import io
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import auth_api, todo_marks
from .accounts import sessions, users
from .auth_api import answer, csrf_ok

PATH = re.compile(r"^/traffic/(?P<site>[a-z0-9.-]+)/(?:(?P<view>[a-z0-9-]+)/)?"
                  r"(?P<act>settings/(?:todos|todo-send))$")
SEND_LIMIT, SEND_MINUTES = 10, 60
MARKERS = ("owner", "admin")


def match(path: str):
    path = path.split("?", 1)[0]
    return None if ".." in path else PATH.match(path)


def is_todos(path: str) -> bool:
    return match(path) is not None


def _config(config, config_path, site, live_dir) -> dict:
    from . import settings_store as store
    from .settings_api import site_config
    return store.apply(site_config(config, config_path, site), site, live_dir)


def mail_state(cfg: dict) -> dict:
    """{"ready": bool, "why": words}: can the install's mail server send one mail now?"""
    from . import mailer
    try:
        mailer.settings({**cfg, "mail": {**(cfg.get("mail") or {}), "to": ["(a team member)"],
                                         "to_waiting": 0}})
    except Exception as why:            # noqa: BLE001 - Refused, Withheld or a bad value
        return {"ready": False, "why": f"No mail server is set up for this site ({why}). "
                                       "An admin sets one in Settings > Mail & reports."}
    return {"ready": True, "why": ""}


def team(db, site: str) -> list[dict]:
    """The confirmed, active members of the site's organisation."""
    from .accounts.orgs import org_of_site
    org = org_of_site(db, site)
    if org is None:
        return []
    out = []
    for uid, email, role, confirmed, disabled in db.execute(
            "SELECT u.id, u.email, m.role, u.pw_hash IS NOT NULL, u.disabled_at FROM members m "
            "JOIN users u ON u.id = m.user_id WHERE m.org_id = ? ORDER BY u.email", (org["id"],)):
        if confirmed and not disabled:
            out.append({"id": uid, "email": email, "role": role})
    return out


def _today(cfg) -> str:
    from .window import zone
    return datetime.now(zone(cfg)).date().isoformat()


def handle(h, write: bool, config, live_dir, allowed, same_origin, config_path=None, out=None,
           send=None) -> None:
    if not auth_api.sessions_mode(config):
        return answer(h, 404, {"ok": False, "error": "not found"})
    m = match(h.path)
    act = m.group("act")
    if act == "settings/todo-send" and not write:
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
        site = m.group("site")
        role, org = users.site_role(db, session["user_id"], site)
        if org is None or role is None:
            return answer(h, 403, {"ok": False, "error": "Not available to you."})
        cfg = _config(config, config_path, site, live_dir)
        if not write:
            body = {"ok": True, "marks": todo_marks.current(db, site), "changes": todo_marks.changes(db, site),
                    "role": role, "can_mark": role in MARKERS, "mail": mail_state(cfg)}
            if role in MARKERS:
                body["team"] = team(db, site)
            return answer(h, 200, body)
        if role not in MARKERS:
            return answer(h, 403, {"ok": False, "error": "Only an owner or an admin can do this."})
        form = _form(h)
        if form is None:
            return None
        item = form.get("item")
        if not todo_marks.valid_item(item):
            return answer(h, 400, {"ok": False, "error": "Not a to-do or a site path."})
        if act == "settings/todos" and item.startswith("page:"):
            return _page_change(h, db, cfg, site, org, session, item[5:], form)
        if act == "settings/todos":
            state = str(form.get("state") or "")
            try:
                got = todo_marks.mark(db, site, item, state, _today(cfg), session["user_id"])
            except ValueError as why:
                return answer(h, 400, {"ok": False, "error": str(why)})
            from .accounts import auditlog
            auditlog.record(db, org["id"], session["email"], "todo.marked", item[:120], f"{site} {state}")
            return answer(h, 200, {"ok": True, **got, "marks": todo_marks.current(db, site)})
        return _send(h, db, cfg, site, m.group("view"), org, session, item, form.get("to"), out, send)
    finally:
        db.close()


def _page_change(h, db, cfg, site, org, session, path, form) -> None:
    """Traffic > Pages > a page: {item: "page:/x/", state: "changed", day, kind, note} marks
    "I changed this page on <day>"; {state: "open", day} stops tracking that change."""
    from .accounts import auditlog
    state, day = str(form.get("state") or ""), form.get("day")
    try:
        if state == "changed":
            got = todo_marks.mark_change(db, site, path, day, str(form.get("kind") or ""),
                                         form.get("note"), _today(cfg), session["user_id"])
        elif state == "open":
            got = todo_marks.stop_change(db, site, path, day, session["user_id"])
        else:
            raise ValueError("a page's change is marked changed, or open to stop tracking it")
    except ValueError as why:
        return answer(h, 400, {"ok": False, "error": str(why)})
    # The note is the team's own words: the audit log keeps the page, the day and the kind only.
    auditlog.record(db, org["id"], session["email"], "todo.marked", ("page:" + path)[:120],
                    f"{site} {state} {got['day']} {got.get('kind') or ''}".strip())
    return answer(h, 200, {"ok": True, **got, "changes": todo_marks.changes(db, site)})


def _send(h, db, cfg, site, view, org, session, item, to, out, send) -> None:
    from .accounts import auditlog
    state = mail_state(cfg)
    if not state["ready"]:
        return answer(h, 409, {"ok": False, "error": state["why"]})
    member = next((t for t in team(db, site) if str(t["id"]) == str(to)), None)
    if member is None:
        return answer(h, 400, {"ok": False, "error": "Pick a member of this site's team."})
    since = (datetime.now(timezone.utc) - timedelta(minutes=SEND_MINUTES)).strftime("%Y-%m-%dT%H:%M:%SZ")
    sent = db.execute("SELECT COUNT(*) FROM audit WHERE org_id = ? AND action = 'todo.sent' AND at >= ?",
                      (org["id"], since)).fetchone()[0]
    if sent >= SEND_LIMIT:
        return answer(h, 429, {"ok": False, "error": f"At most {SEND_LIMIT} to-dos sent in {SEND_MINUTES} minutes."})
    todo = _todo(out, site, view, item)
    if todo is None:
        return answer(h, 404, {"ok": False, "error": "That to-do is not on the list now."})
    error = send_one(cfg, site, todo, member["email"], session["email"], send=send)
    if error:
        return answer(h, 502, {"ok": False, "error": f"The mail server did not take it ({error}). "
                                                     "Check Settings > Mail & reports."})
    auditlog.record(db, org["id"], session["email"], "todo.sent", member["email"], f"{site} {item}")
    return answer(h, 200, {"ok": True, "sent_to": member["email"], "file": todo.get("file")})


def _todo(out, site: str, view: str | None, item: str) -> dict | None:
    from .refresh_server import data_file
    path = data_file(Path(out) if out else None, site, view, "todos")
    if path is None:
        return None
    try:
        body = json.loads(path.read_text())
    except (OSError, ValueError):
        return None
    return next((t for t in body.get("todos") or [] if t.get("id") == item), None)


def rows_csv(todo: dict) -> str:
    """The to-do's rows as CSV, with its columns' labels; a spreadsheet's formula
    characters are prefixed with an apostrophe, as every export does."""
    cols = todo.get("columns") or []
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\r\n")
    w.writerow([c["label"] for c in cols])
    for r in todo.get("rows") or []:
        cells = []
        for c in cols:
            v = r.get(c["key"])
            s = "" if v is None else str(v)
            cells.append("'" + s if s[:1] in ("=", "+", "-", "@", "\t", "\r") else s)
        w.writerow(cells)
    return buf.getvalue()


def link(cfg: dict, item: str) -> str:
    base = str(((cfg or {}).get("dashboard") or {}).get("url") or "").split("#", 1)[0]
    return f"{base}#overview/insights?todo={item}"


def send_one(cfg: dict, site: str, todo: dict, to: str, sender: str, send=None) -> str | None:
    """One mail with the to-do and its CSV. The error in words, or None."""
    from html import escape

    from . import mailer
    text = (f"{sender} sent you a to-do from Skald for {site}.\n\n{todo['title']}\n\n"
            f"Proof: {todo['proof']}\nDo: {todo['todo']}\nSkald will check: {todo['check']}\n\n"
            f"Open it in Skald: {link(cfg, todo['id'])}\n"
            "You sign in first. Without rights to this site the page says \"not available to you\"; "
            "the CSV attached works for anyone.\n")
    if todo.get("rows_total", 0) > len(todo.get("rows") or []):
        text += f"\nThe CSV has the first {len(todo['rows']):,} of {todo['rows_total']:,} rows.\n"
    try:
        now = datetime.now(timezone.utc)
        mcfg = dict(mailer.settings({**cfg, "mail": {**(cfg.get("mail") or {}), "to": [to]}}), to=[to])
        msg = mailer._message(mcfg, f"To do on {site}: {todo['title']}", text,
                              "<pre style=\"font:14px/1.5 sans-serif;white-space:pre-wrap\">"
                              + escape(text) + "</pre>", now)
        msg.add_attachment(rows_csv(todo).encode("utf-8"), maintype="text", subtype="csv",
                           filename=todo.get("file") or "todo.csv")
        (send or mailer.send)(msg, mcfg)
    except Exception as why:            # noqa: BLE001 - said to the person, never raised
        return type(why).__name__
    return None


def _form(h) -> dict | None:
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
