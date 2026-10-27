"""Overview > Insights' "Check again": what each check of a to-do found, kept (2.44).

todo_check.py runs the check (a live fetch of the to-do's exact addresses, or the newest
log lines); this module keeps what it found, per site, in accounts.sqlite beside the
marks (todo_marks.py), in a table made here on first use:

    todo_checks (site, item, at, sweep, start, total, checked, ok, mode, verdict, words,
                 rows, log, by_user, by_who)

One row per check. A to-do with more rows than one check takes (todo_check.CAP) is
checked in pages: the first page starts a "sweep" (`sweep` is that page's `at`), and
"Check the next 50" adds pages to it (`start` is the first row of the page). `rows` is
JSON: what each address answered ({path, status, end, location, ok, why}); never a body,
never a visitor. `log` is JSON: what the newest log lines said since the fix ({since,
lines, failed, newest, read}) or null. `by_who` is "person", "ai-agent" or
"mcp:<token id>" (who asked: the person's own press, or their agent's done report).

Nothing is deleted or rewritten. A to-do whose sweep covered every row and found every
one fixed is marked fixed (todo_marks.mark_checked: state "fixed", kind "checked"); a
later check that finds it broken again puts back the mark it had before. The audit
(audit_todo_checks.py) re-derives each such mark from the rows kept here.

Limits, per site: LIMIT_HOUR checks an hour (every page, every to-do, the agent's too),
and a to-do's sweep starts again at most once a minute (LIMIT_GAP seconds).
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

TABLE = ("CREATE TABLE IF NOT EXISTS todo_checks (site TEXT NOT NULL, item TEXT NOT NULL, "
         "at TEXT NOT NULL, sweep TEXT NOT NULL, start INTEGER NOT NULL, total INTEGER NOT NULL, "
         "checked INTEGER NOT NULL, ok INTEGER NOT NULL, mode TEXT NOT NULL, verdict TEXT NOT NULL, "
         "words TEXT, rows TEXT, log TEXT, by_user INTEGER, by_who TEXT)")
INDEX = "CREATE INDEX IF NOT EXISTS todo_checks_site ON todo_checks (site, item, at)"
LIMIT_HOUR = 30
LIMIT_GAP = 60
VERDICTS = ("fixed", "partly", "not_fixed", "more", "waiting", "error")
BAD_MOST = 200                   # rows still failing handed to the page


def _stamp(now: datetime | None = None) -> str:
    return (now or datetime.now(timezone.utc)).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ready(db) -> None:
    db.execute(TABLE)
    db.execute(INDEX)


def _commit(db) -> None:
    try:
        db.commit()
    except Exception:                    # noqa: BLE001 - an autocommit connection
        pass


def keep(db, site: str, item: str, got: dict, sweep: str | None, by_user=None,
         by_who: str = "person", now: datetime | None = None) -> dict:
    """Keep one check (todo_check.run's answer). `sweep`: the sweep it continues, or None
    to start one. The row as rows() reads it."""
    ready(db)
    at = _stamp(now)
    sweep = sweep or at
    db.execute("INSERT INTO todo_checks (site, item, at, sweep, start, total, checked, ok, mode, "
               "verdict, words, rows, log, by_user, by_who) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, "
               "?, ?, ?, ?, ?)",
               (site, item, at, sweep, int(got.get("start") or 0), int(got.get("total") or 0),
                int(got.get("checked") or 0), int(got.get("ok") or 0), got["mode"], got["verdict"],
                got.get("words") or "", json.dumps(got.get("rows") or [], separators=(",", ":")),
                json.dumps(got["log"], separators=(",", ":")) if got.get("log") is not None else None,
                int(by_user) if by_user is not None else None, by_who))
    _commit(db)
    return {"at": at, "sweep": sweep}


def _row(r) -> dict:
    (item, at, sweep, start, total, checked, ok, mode, verdict, words, rows, log, by_user, by_who) = r
    return {"item": item, "at": at, "sweep": sweep, "start": start, "total": total, "checked": checked,
            "ok": ok, "mode": mode, "verdict": verdict, "words": words or "",
            "rows": json.loads(rows or "[]"), "log": json.loads(log) if log else None,
            "by_user": by_user, "by_who": by_who}


COLS = "item, at, sweep, start, total, checked, ok, mode, verdict, words, rows, log, by_user, by_who"


def rows(db, site: str, item: str | None = None) -> list[dict]:
    """Every check kept for the site (or one to-do), oldest first."""
    try:
        if item is None:
            got = db.execute(f"SELECT {COLS} FROM todo_checks WHERE site = ? ORDER BY at, rowid", (site,))
        else:
            got = db.execute(f"SELECT {COLS} FROM todo_checks WHERE site = ? AND item = ? "
                             "ORDER BY at, rowid", (site, item))
        return [_row(r) for r in got.fetchall()]
    except Exception:                    # noqa: BLE001 - no table yet: nothing checked
        return []


def sweep_of(checks: list[dict]) -> list[dict]:
    """The pages of the newest sweep in `checks` (one to-do's), oldest first."""
    if not checks:
        return []
    last = checks[-1]["sweep"]
    return [c for c in checks if c["sweep"] == last]


def tally(pages: list[dict]) -> dict:
    """A sweep's rows, each address once (its newest answer): {checked, ok, total, next,
    rows}. `next`: the first row not checked yet, or None when every row was."""
    seen: dict[str, dict] = {}
    total, reach = 0, 0
    for p in pages:
        total = p["total"]
        reach = max(reach, p["start"] + p["checked"])
        for r in p["rows"]:
            seen[r["path"]] = r
    got = list(seen.values())
    return {"checked": len(got), "ok": sum(1 for r in got if r.get("ok")), "total": total,
            "next": reach if reach < total else None, "rows": got}


def newest(db, site: str) -> dict[str, dict]:
    """{item: what the page shows of its newest sweep}: the newest page's words and
    verdict, the sweep's counts, and the rows still failing (at most BAD_MOST)."""
    by: dict[str, list[dict]] = {}
    for c in rows(db, site):
        by.setdefault(c["item"], []).append(c)
    out = {}
    for item, checks in by.items():
        pages = sweep_of(checks)
        last = pages[-1]
        t = tally(pages) if last["mode"] == "live" else {"checked": last["checked"], "ok": last["ok"],
                                                         "total": last["total"], "next": None, "rows": []}
        bad = [r for r in t["rows"] if not r.get("ok")]
        out[item] = {"item": item, "at": last["at"], "sweep": last["sweep"], "mode": last["mode"],
                     "verdict": last["verdict"], "words": last["words"], "log": last["log"],
                     "checked": t["checked"], "ok": t["ok"], "total": t["total"], "next": t["next"],
                     "bad": bad[:BAD_MOST], "bad_total": len(bad), "by_user": last["by_user"],
                     "by_who": last["by_who"]}
    return out


def limited(db, site: str, item: str, starting: bool, now: datetime | None = None) -> str | None:
    """Why a check may not run now (plain words), or None."""
    now = now or datetime.now(timezone.utc)
    ready(db)
    hour = _stamp(now - timedelta(hours=1))
    n = db.execute("SELECT COUNT(*) FROM todo_checks WHERE site = ? AND at >= ?", (site, hour)).fetchone()[0]
    if n >= LIMIT_HOUR:
        return f"At most {LIMIT_HOUR} checks an hour for a site. Try again later."
    if starting:
        last = db.execute("SELECT MAX(at) FROM todo_checks WHERE site = ? AND item = ?",
                          (site, item)).fetchone()[0]
        if last:
            gap = (now - datetime.strptime(last, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)).total_seconds()
            if gap < LIMIT_GAP:
                wait = int(LIMIT_GAP - gap) + 1
                return f"This to-do was checked {int(gap)} s ago. Check it again in {wait} s."
    return None


def current_sweep(db, site: str, item: str) -> dict | None:
    """The newest sweep of a to-do, tallied, with its id, or None."""
    pages = sweep_of(rows(db, site, item))
    if not pages:
        return None
    return {"sweep": pages[-1]["sweep"], **tally(pages), "mode": pages[-1]["mode"]}


def names(db, ids) -> dict[int, str]:
    """{user id: email} of who pressed Check again, for the page's "by"."""
    want = sorted({int(i) for i in ids if i is not None})
    if not want:
        return {}
    marks = ",".join("?" * len(want))
    try:
        return {uid: email for uid, email in db.execute(
            f"SELECT id, email FROM users WHERE id IN ({marks})", want)}
    except Exception:                    # noqa: BLE001 - no users table (a test db)
        return {}
