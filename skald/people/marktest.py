"""POST <page>/people/mark-test: "Mark as test" and "Not a test" in a lead's or a
conversion's drawer (2.25), for owners and admins.

    body    {"id": <conversion row id>, "test": true | false}
    answer  {"ok", "test", "id", "tool", "ref", "changed": <rows changed>,
             "ids": [the rows changed], "redrawn": true | false}

The same mark as `skald conversions mark-test SITE ID [--unmark]` and the site's
signed `POST /traffic-hooks/<site>/leads/test`: `store.mark_test` marks every stage
of that (tool, external_ref) as TEST_MARKED (a later stage the tool sends for it is
test too), or takes the mark off every stage. The rows stay, listed under "Show left
out", and leave every count.

Guards, as every admin write of the helper: a same-origin request; in sessions mode
an owner or admin of the site's organisation with the session's X-Skald-CSRF value
(helper_sessions.need); in basic mode an owner or admin (access.role_of). A viewer
or an editor gets 403. Each change writes one audit row (sessions: accounts.sqlite;
basic: privacy.log), action `conversions.test` or `conversions.untest`, the user, the
tool and the row ids changed: never the reference, a name or an email. Then the
audit's cached beacon days are counted again (marks.recount) and the page's files
are drawn again (the live run, as after an internal-address change), so the counts
the page shows move with the mark.
"""
from __future__ import annotations

import re

from . import api

PATH = re.compile(api.PAGE + r"people/mark-test$")
ADMIN = ("owner", "admin")


def is_mark(path: str) -> bool:
    return PATH.match(path.split("?", 1)[0]) is not None and ".." not in path


def read_body(form) -> tuple[int, bool]:
    """(row id, True to mark). ValueError with the reason for anything else."""
    if not isinstance(form, dict) or any(k not in ("id", "test") for k in form):
        raise ValueError('the body is {"id": <conversion number>, "test": true or false}')
    rid, on = form.get("id"), form.get("test", True)
    if isinstance(rid, bool) or not isinstance(rid, int) or rid <= 0:
        raise ValueError("id is a conversion's number")
    if not isinstance(on, bool):
        raise ValueError("test is true or false")
    return rid, on


def allowed(h, sessions_mode: bool, same_origin, origins) -> tuple[str, dict | None] | None:
    """(the user, the session or None) for an owner or admin with the page's CSRF
    value; None after answering 403."""
    if not same_origin(h.headers, origins):
        h._json(403, {"ok": False, "error": "same-origin requests only"})
        return None
    if sessions_mode:
        from .. import helper_sessions
        if h.who is None or not helper_sessions.need(h, h.who, install=False):
            return None
        return h.who.get("email") or "", h.who
    user, role = h._user()
    if role not in ADMIN:
        h._json(403, {"ok": False, "role": role,
                      "error": "Only an admin or an owner can mark a lead as test."})
        return None
    return user or "admin", None


def handle(h, config, live_dir, history_path=None, config_path=None, sessions_mode=False,
           origins=frozenset(), same_origin=None, refresh=None) -> None:
    """Answer one POST (the caller is already gated by the helper)."""
    from ..conversions import marks, store
    m = PATH.match(h.path.split("?", 1)[0])
    if m is None or ".." in h.path:
        return h._json(404, {"ok": False, "error": "not found"})
    got = allowed(h, sessions_mode, same_origin or (lambda *_: False), origins)
    if got is None:
        return None
    user, who = got
    form = h._body()
    if form is None:
        return None
    try:
        rid, on = read_body(form)
    except ValueError as why:
        return h._json(400, {"ok": False, "error": str(why)})
    site = m.group("site")
    cfg = api._site_config(config, site, config_path)
    folder = api._folder(cfg, history_path)
    path = store.path_for(cfg, folder) if folder is not None else None
    if path is None or not path.is_file():
        return h._json(404, {"ok": False, "error": "This site has no conversions yet."})
    db = store.connect(path)
    try:
        row = db.execute("SELECT tool, external_ref FROM conversions WHERE id = ? AND site = ?",
                         (rid, site)).fetchone()
        if row is None:
            return h._json(404, {"ok": False, "error": "That conversion is not kept any more. "
                                                       "Reload the page."})
        changed = store.mark_test(db, site, [rid], on)
    finally:
        db.close()
    ids = [r["id"] for r in changed]
    api._audit(config, live_dir, site, who, user, "conversions.test" if on else
               "conversions.untest",
               f"{len(ids)} row(s) {'marked' if on else 'unmarked'} test from the dashboard, "
               f"tool={row[0]} ids={','.join(map(str, ids)) or '-'}")
    if ids and folder is not None:
        marks.recount(folder)
    redrawn = False
    if ids and refresh is not None:
        try:
            redrawn = refresh() == "ran"
        except Exception:                 # noqa: BLE001 - the mark is made; the next run draws
            redrawn = False
    return h._json(200, {"ok": True, "test": on, "id": rid, "tool": row[0], "ref": row[1],
                         "changed": len(ids), "ids": ids, "redrawn": redrawn})
