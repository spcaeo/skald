""""Not a problem": an owner or admin closes one possible exposure (SKALD-59).

A possible exposure is a 2xx with a size unlike the host's harmless page. Some are a site's own
public file (a feed, an export, an admin call of the team's own tools) and need no fix; before
SKALD-59 nothing could close one, and the daily summary listed it every day.

  a mark      per site, item (security_notify.item_id: host and path) and answer: the status
              and size it was judged on, who marked it and when. One path can get several
              answers (the same page compressed and not: 184 and 626 bytes), so an item can
              hold several marks, one per answer someone checked
  covers      an answer with the same status and a size within the day's `tolerance` of a
              marked one: no item, mail or site alert for it (security_notify.items,
              alerts_security.exposures); the page shows the row as "Not a problem" and
              leaves it out of the verdict
  not covered another status or size (the file changed): judged again, opened and mailed. The
              mark stays for the answer it was made for: if that answer comes back, it is
              covered again
  undo        "Check it again" takes back every mark of the item
  who         owners and admins of the site's organisation (security_api.py), each mark and
              each undo a row in the organisation's audit log

The counts never change: the figures say what the server answered; a mark is a person's
judgement of one answer. Kept in accounts.sqlite (made here on first use), cleared and purged
with the site's data (site_data.ACCOUNTS_DATA); basic mode (no accounts) has no marks.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

MARKS = ("CREATE TABLE IF NOT EXISTS security_marks (site TEXT NOT NULL, item TEXT NOT NULL, "
         "status TEXT NOT NULL, size INTEGER NOT NULL, user_id INTEGER NOT NULL, "
         "marked_at TEXT NOT NULL, PRIMARY KEY (site, item, status, size))")
NO_SIZE = -1                            # stored for an answer the log has no size for
ITEM = re.compile(r"x[0-9a-f]{12}")
STATUS = re.compile(r"[2-5][0-9][0-9]")
MAX_SIZE = 10 ** 12
MAX_MARKS = 5000                        # per site: an owner or admin cannot fill the file
TOLERANCE = 16                          # security_names.DEFAULTS, for a blob without rules


def _ready(db) -> None:
    db.execute(MARKS)


def _stamp(now: datetime) -> str:
    return now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def of_site(db, site: str) -> dict:
    """{item: [{status, size, user_id, marked_at, by}]} for `site` (`by`: the marker's
    address; size None: not recorded), each item's newest mark first."""
    _ready(db)
    rows = db.execute("SELECT m.item, m.status, m.size, m.user_id, m.marked_at, u.email FROM "
                      "security_marks m LEFT JOIN users u ON u.id = m.user_id WHERE m.site = ? "
                      "ORDER BY m.item, m.marked_at DESC, m.status, m.size", (site,)).fetchall()
    out: dict = {}
    for item, status, size, uid, at, email in rows:
        out.setdefault(item, []).append({"status": status, "size": None if size == NO_SIZE
                                         else size, "user_id": uid, "marked_at": at,
                                         "by": email or ""})
    return out


def for_site(config: dict, live_dir, site: str) -> dict:
    """The site's marks for a run, {} without accounts or on any error (never stops a run)."""
    try:
        from .auth_api import open_db, sessions_mode
        if not sessions_mode(config):
            return {}
        db = open_db(config, live_dir)
        if db is None:
            return {}
        try:
            return of_site(db, site)
        finally:
            db.close()
    except Exception:                   # noqa: BLE001 - no marks is the safe side
        return {}


def covering(marks, status, size, tolerance) -> dict | None:
    """The mark among `marks` (one item's) that covers this answer, or None: the same status,
    and a size within `tolerance` (both sizes not recorded counts as the same)."""
    tol = TOLERANCE if tolerance is None else int(tolerance)
    for m in marks or ():
        if str(m.get("status")) != str(status):
            continue
        if m.get("size") is None or size is None:
            if m.get("size") is None and size is None:
                return m
        elif abs(int(m["size"]) - int(size)) <= tol:
            return m
    return None


def check(item, status, size) -> str | None:
    """What is wrong with a mark asked for, in words, or None."""
    if not isinstance(item, str) or not ITEM.fullmatch(item):
        return "That is not a possible exposure's id."
    if not isinstance(status, str) or not STATUS.fullmatch(status):
        return "The answer's status is missing."
    if size is not None and (isinstance(size, bool) or not isinstance(size, int)
                             or not 0 <= size < MAX_SIZE):
        return "The answer's size is not a number of bytes."
    return None


def mark(db, site: str, item: str, status: str, size, user_id: int, org_id, email: str,
         now: datetime | None = None) -> dict:
    """Mark this answer of `item` not a problem; its open security item closes now. Raises
    ValueError past MAX_MARKS marks on the site (a mark already there is only renewed)."""
    _ready(db)
    known = db.execute("SELECT 1 FROM security_marks WHERE site = ? AND item = ? AND status = ? "
                       "AND size = ?", (site, item, status, NO_SIZE if size is None
                                        else int(size))).fetchone()
    if known is None and db.execute("SELECT COUNT(*) FROM security_marks WHERE site = ?",
                                    (site,)).fetchone()[0] >= MAX_MARKS:
        raise ValueError(f"This site already has {MAX_MARKS:,} marks. Take some back with "
                         "Check it again first.")
    stamp = _stamp(now or datetime.now(timezone.utc))
    db.execute("INSERT INTO security_marks (site, item, status, size, user_id, marked_at) "
               "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(site, item, status, size) DO UPDATE SET "
               "user_id = excluded.user_id, marked_at = excluded.marked_at",
               (site, item, status, NO_SIZE if size is None else int(size), int(user_id), stamp))
    from .security_notify import _ready as items_ready
    items_ready(db)
    db.execute("UPDATE security_items SET closed_at = ? WHERE site = ? AND item = ? AND "
               "closed_at IS NULL", (stamp, site, item))
    from .accounts import auditlog
    auditlog.record(db, org_id, email, "security.item.not_a_problem", item,
                    f"{site} answered {status} ({'no size' if size is None else f'{size} bytes'})")
    db.commit()
    return of_site(db, site)


def unmark(db, site: str, item: str, org_id, email: str) -> dict:
    """Take back every mark of `item`: the next run judges it again (and opens it if seen)."""
    _ready(db)
    gone = db.execute("DELETE FROM security_marks WHERE site = ? AND item = ?",
                      (site, item)).rowcount
    if gone:
        from .accounts import auditlog
        auditlog.record(db, org_id, email, "security.item.check_again", item, site)
    db.commit()
    return of_site(db, site)
