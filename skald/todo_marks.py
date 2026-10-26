"""What people marked on Overview > Insights' to-do list, Site > Not found and
Traffic > Pages (2.35).

A to-do (todos.py) can be marked "done" (Skald re-checks it on the next whole
days) or "not now" (left out of the list until someone puts it back); an old
address on Not found's lost pages can be marked "fixed" (its After the fix tab
then shows what came for it after that day). Kept per site in accounts.sqlite,
beside the settings people change (settings_store.py), in a table made here on
first use:

    todo_marks (site, item, state, day, at, by_user, kind, note)

`item` is a to-do's id (lowercase letters, digits and hyphens: "lost-pages",
"leave-3f9a0c2e") or "path:" and an old address ("path:/blog/old-post/").
`state` is "done", "notnow", "fixed" or "open"; `day` the site's local day it
was marked; `at` the UTC time; `by_user` the account that did it. Nothing is
ever deleted or rewritten (the owner's rule: pause, never delete): a change is a
new row, "open" puts an item back, and an item's state is its newest row. So the
history of every mark stays, for the audit log and for a re-check that wants the
first day something was called done.

Page changes ("did my change work?"): Traffic > Pages > a page's "I changed this
page on <day>" is a row in the same table: `item` "page:" and the page's path,
`state` "changed", `day` the day the page changed (the reader's pick, not the day
it was marked), `kind` what changed (CHANGE_KINDS) and `note` a short note.
Several changes of one page are kept apart by their day; "open" with the same item
and day stops tracking that one (its rows stay). page_changes.py counts the days
before and after.

Without accounts (basic mode) nothing can be marked: the dashboard hides the
buttons and says why.
"""
from __future__ import annotations

import hashlib
import re
from datetime import date, datetime, timedelta, timezone

COLUMNS = ("(site TEXT NOT NULL, item TEXT NOT NULL, "
           "state TEXT NOT NULL CHECK (state IN ('done', 'notnow', 'fixed', 'changed', 'open')), "
           "day TEXT NOT NULL, at TEXT NOT NULL, by_user INTEGER, kind TEXT, note TEXT)")
TABLE = "CREATE TABLE IF NOT EXISTS todo_marks " + COLUMNS
INDEX = "CREATE INDEX IF NOT EXISTS todo_marks_site ON todo_marks (site, item, at)"
STATES = ("done", "notnow", "fixed", "changed", "open")
TODO_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")
PATH_MOST = 300
# What changed on a page (the Mark a change dialog's choices), and how a note is kept.
CHANGE_KINDS = ("content", "title", "backlink", "redirect", "other")
NOTE_MOST = 200
CHANGE_DAYS_BACK = 365          # a change can be dated up to a year back, never ahead
DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def valid_path(path) -> bool:
    """A site path: starts with "/", at most 300 characters, no control character."""
    return (isinstance(path, str) and path.startswith("/") and 0 < len(path) <= PATH_MOST
            and not any(ord(c) < 32 or ord(c) == 127 for c in path))


def valid_item(item) -> bool:
    """A to-do's id, or "path:" (an old address) or "page:" (a page's change) and a path."""
    if not isinstance(item, str):
        return False
    if item.startswith(("path:", "page:")):
        return valid_path(item[5:])
    return bool(TODO_ID.match(item))


def _ready(db) -> None:
    got = db.execute("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'todo_marks'").fetchone()
    if got and "'changed'" not in got[0]:
        # A table from before page changes (2.35's first builds): the same rows, all kept,
        # in the table that also takes "changed", its kind and its note.
        db.execute("ALTER TABLE todo_marks RENAME TO todo_marks_before_changes")
        db.execute("DROP INDEX IF EXISTS todo_marks_site")
        db.execute(TABLE)
        db.execute("INSERT INTO todo_marks (site, item, state, day, at, by_user) SELECT site, item, "
                   "state, day, at, by_user FROM todo_marks_before_changes ORDER BY rowid")
        db.execute("DROP TABLE todo_marks_before_changes")
    db.execute(TABLE)
    db.execute(INDEX)


def _commit(db) -> None:
    try:
        db.commit()
    except Exception:                    # noqa: BLE001 - an autocommit connection has nothing to commit
        pass


def _stamp(now: datetime | None) -> str:
    return (now or datetime.now(timezone.utc)).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def mark(db, site: str, item: str, state: str, day: str, user_id=None,
         now: datetime | None = None) -> dict:
    """Write one change. A path takes "fixed" or "open"; a to-do "done", "notnow" or "open".
    A page's change has its own: mark_change() and stop_change()."""
    if state not in STATES or state == "changed":
        raise ValueError("state is done, notnow, fixed or open")
    if not valid_item(item) or item.startswith("page:"):
        raise ValueError("not a to-do or a site path")
    if item.startswith("path:") != (state in ("fixed",)) and state != "open":
        raise ValueError("a path is marked fixed; a to-do done or not now")
    _ready(db)
    at = _stamp(now)
    db.execute("INSERT INTO todo_marks (site, item, state, day, at, by_user) VALUES (?, ?, ?, ?, ?, ?)",
               (site, item, state, day, at, int(user_id) if user_id is not None else None))
    _commit(db)
    return {"item": item, "state": state, "day": day, "at": at}


def current(db, site: str) -> dict[str, dict]:
    """{item: {"state", "day", "at", "first_day"}} of every item whose newest row is not
    "open". `first_day`: the first day of the run of that state the newest row ends (a
    to-do marked done twice in a row keeps the first day). Page changes are changes()'."""
    try:
        rows = db.execute("SELECT item, state, day, at FROM todo_marks WHERE site = ? AND "
                          "item NOT LIKE 'page:%' ORDER BY item, at, rowid", (site,)).fetchall()
    except Exception:                    # noqa: BLE001 - no table yet: nothing marked
        return {}
    out: dict[str, dict] = {}
    for item, state, day, at in rows:
        prev = out.get(item)
        first = prev["first_day"] if prev and prev["state"] == state else day
        out[item] = {"state": state, "day": day, "at": at, "first_day": first}
    return {k: v for k, v in out.items() if v["state"] != "open"}


def read(config, site: str, live_dir=None) -> dict[str, dict] | None:
    """current() from the install's accounts.sqlite, opened read-only; None when there is
    no accounts file (basic mode: nothing can be marked). The install's file is the one
    beside the history (`_resolved.history_db`, as the helper finds it), not a second
    site's own folder: that folder keeps the site's live state only (multisite.py)."""
    return _read(config, site, live_dir, current)


def read_changes(config, site: str, live_dir=None) -> list[dict] | None:
    """changes() from the install's accounts.sqlite, read-only; None without one."""
    return _read(config, site, live_dir, changes)


def _read(config, site: str, live_dir, reader):
    import sqlite3

    from .settings_store import accounts_file
    path = accounts_file(config) or (accounts_file(config, live_dir) if live_dir else None)
    if path is None:
        return None
    try:
        db = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5)
    except sqlite3.Error:
        return None
    try:
        return reader(db, site)
    finally:
        db.close()


# ------------------------------------------------------------------ page changes

def change_id(site: str, path: str, day: str) -> str:
    """An opaque id for one change: "c" and 8 hex of a hash of the site, the page and the day."""
    return "c" + hashlib.sha256(f"{site}|{path}|{day}".encode()).hexdigest()[:8]


def clean_note(note) -> str:
    """A note as kept: one line, no control character, at most NOTE_MOST characters."""
    text = " ".join(str(note or "").split())
    return "".join(c for c in text if ord(c) >= 32 and ord(c) != 127)[:NOTE_MOST]


def _check_day(day, today: str) -> None:
    if not isinstance(day, str) or not DAY.match(day):
        raise ValueError("the day is YYYY-MM-DD")
    try:
        d, t = date.fromisoformat(day), date.fromisoformat(today)
    except ValueError:
        raise ValueError("the day is YYYY-MM-DD") from None
    if d > t:
        raise ValueError("a change cannot be dated after today")
    if d < t - timedelta(days=CHANGE_DAYS_BACK):
        raise ValueError(f"a change can be dated at most {CHANGE_DAYS_BACK} days back")


def mark_change(db, site: str, path: str, day: str, kind: str, note: str, today: str,
                user_id=None, now: datetime | None = None) -> dict:
    """"I changed this page on <day>": one row. Marking the same page and day again keeps
    the newest kind and note (the older row stays)."""
    if not valid_path(path):
        raise ValueError("not a site path")
    if kind not in CHANGE_KINDS:
        raise ValueError("what changed is one of " + ", ".join(CHANGE_KINDS))
    _check_day(day, today)
    return _change_row(db, site, path, day, "changed", kind, clean_note(note), user_id, now)


def stop_change(db, site: str, path: str, day: str, user_id=None, now: datetime | None = None) -> dict:
    """Stop tracking one change: an "open" row for its page and day. Nothing is deleted."""
    if not valid_path(path) or not isinstance(day, str) or not DAY.match(day):
        raise ValueError("not a tracked change")
    return _change_row(db, site, path, day, "open", None, None, user_id, now)


def _change_row(db, site, path, day, state, kind, note, user_id, now) -> dict:
    _ready(db)
    at = _stamp(now)
    db.execute("INSERT INTO todo_marks (site, item, state, day, at, by_user, kind, note) "
               "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
               (site, "page:" + path, state, day, at, int(user_id) if user_id is not None else None,
                kind, note))
    _commit(db)
    return {"id": change_id(site, path, day), "path": path, "day": day, "state": state,
            "kind": kind, "note": note, "at": at}


def changes(db, site: str) -> list[dict]:
    """The changes tracked now, newest day first: [{"id", "path", "day", "kind", "note",
    "at", "first_at"}]. Per page and day the newest row says; "open" stops it. `first_at`:
    when it was first marked (the run of "changed" rows the newest one ends)."""
    try:
        rows = db.execute("SELECT item, state, day, at, kind, note FROM todo_marks WHERE site = ? "
                          "AND item LIKE 'page:%' ORDER BY at, rowid", (site,)).fetchall()
    except Exception:                    # noqa: BLE001 - no table yet (or one without kind): nothing tracked
        return []
    last: dict[tuple, dict] = {}
    for item, state, day, at, kind, note in rows:
        k = (item[5:], day)
        prev = last.get(k)
        first = prev["first_at"] if prev and prev["state"] == "changed" and state == "changed" else at
        last[k] = {"state": state, "kind": kind, "note": note or "", "at": at, "first_at": first}
    out = [{"id": change_id(site, path, day), "path": path, "day": day, "kind": v["kind"],
            "note": v["note"], "at": v["at"], "first_at": v["first_at"]}
           for (path, day), v in last.items() if v["state"] == "changed"]
    out.sort(key=lambda c: (c["day"], c["path"]), reverse=True)
    return out


# ------------------------------------------------------------------ an AI agent's fixes (2.41)
#
# What the person's own AI agent did for a to-do (kit/agent_todos.py's POST <code>/fix, and
# the MCP tool mark_todo_done): one row per report, never rewritten, the newest one says.
#
#     todo_fixes (site, item, at, state, change, files, left_rows, notes, link_id, by_who)
#
# `state` is "done", "partly" or "left"; `change` the exact change as text (the redirect
# lines it added, a diff), at most FIX_CHANGE_MOST characters; `files` and `left_rows` JSON
# lists; `by_who` "ai-agent" (a line) or "mcp:<token id>". "done" also marks the to-do
# done (mark()), so the re-check runs on the whole days after; "Undo" puts it back.

FIX_TABLE = ("CREATE TABLE IF NOT EXISTS todo_fixes (site TEXT NOT NULL, item TEXT NOT NULL, "
             "at TEXT NOT NULL, state TEXT NOT NULL CHECK (state IN ('done', 'partly', 'left')), "
             "change TEXT, files TEXT, left_rows TEXT, notes TEXT, link_id TEXT, by_who TEXT)")
FIX_STATES = ("done", "partly", "left")
FIX_CHANGE_MOST = 200_000


def keep_fix(db, site: str, item: str, state: str, change: str = "", files=(), left=(),
             notes: str = "", link_id: str | None = None, by_who: str = "ai-agent",
             now: datetime | None = None) -> dict:
    """Keep one fix report (cleaned by the caller); the row as fixes() reads it."""
    import json
    if state not in FIX_STATES:
        raise ValueError("state is done, partly or left")
    if not TODO_ID.match(item or ""):
        raise ValueError("not a to-do's id")
    db.execute(FIX_TABLE)
    at = _stamp(now)
    change = (change or "")[:FIX_CHANGE_MOST]
    db.execute("INSERT INTO todo_fixes (site, item, at, state, change, files, left_rows, notes, "
               "link_id, by_who) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
               (site, item, at, state, change, json.dumps(list(files)), json.dumps(list(left)),
                notes or "", link_id, by_who))
    _commit(db)
    return {"item": item, "at": at, "state": state, "change": change, "files": list(files),
            "left": list(left), "notes": notes or "", "link_id": link_id, "by": by_who}


def fixes(db, site: str) -> dict[str, dict]:
    """{item: the newest fix report} of the site's to-dos."""
    import json
    try:
        rows = db.execute("SELECT item, at, state, change, files, left_rows, notes, link_id, by_who "
                          "FROM todo_fixes WHERE site = ? ORDER BY at, rowid", (site,)).fetchall()
    except Exception:                    # noqa: BLE001 - no table yet: no fix reported
        return {}
    out = {}
    for item, at, state, change, files, left, notes, lid, by in rows:
        out[item] = {"item": item, "at": at, "state": state, "change": change or "",
                     "files": json.loads(files or "[]"), "left": json.loads(left or "[]"),
                     "notes": notes or "", "link_id": lid, "by": by}
    return out


def agent_done(db, site: str, item: str, day: str, by_who: str) -> bool:
    """Mark a to-do done for an agent's "done" report, unless it is done already
    (the re-check keeps counting from the first day). True when a row was written."""
    if (current(db, site).get(item) or {}).get("state") == "done":
        return False
    mark(db, site, item, "done", day, None)
    return True
