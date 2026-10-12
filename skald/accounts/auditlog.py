"""Who changed what, and when: one row per change, never edited.

`org_id` is the organisation the change belongs to, or None for a change to
a person or to the install (a password, a session, a new user). `actor` is
a user id or "cli". No secret and no address ever goes into a row.
"""
from __future__ import annotations

from . import db as base


def record(db, org_id, actor, action: str, target="", detail="") -> None:
    db.execute("INSERT INTO audit (at, org_id, actor, action, target, detail) "
               "VALUES (?, ?, ?, ?, ?, ?)",
               (base.now(), org_id, str(actor), action, str(target)[:200], str(detail)[:500]))


def recent(db, org_id, limit: int = 200, action: str | None = None) -> list[dict]:
    """Newest first. `org_id` None: every row (install admins and the CLI)."""
    where, args = [], []
    if org_id is not None:
        where.append("a.org_id = ?")
        args.append(org_id)
    if action:
        where.append("a.action = ?")
        args.append(action)
    sql = ("SELECT a.id, a.at, a.org_id, a.actor, a.action, a.target, a.detail, "
           "u.email AS actor_email FROM audit a "
           "LEFT JOIN users u ON a.actor GLOB '[0-9]*' AND u.id = CAST(a.actor AS INTEGER)")
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY a.id DESC LIMIT ?"
    args.append(max(1, min(int(limit), 10000)))
    return base.rows(db, sql, args)
