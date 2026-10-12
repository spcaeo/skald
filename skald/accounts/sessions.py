"""Signed-in sessions: a random cookie, of which only the SHA-256 is kept.

A session lasts TTL_DAYS from its last use ("Keep me signed in"), or
SHORT_SECONDS when the person did not ask to be kept signed in. `resolve` slides it, but writes
at most once an hour per session (SLIDE_SECONDS), so a page load is not a
write. The CSRF value is per session and is not a secret on its own: it
only proves the page that sends it read `/me` with the cookie.
`session_id` (the stored hash) names a session to the page, for "sign out
that one"; it cannot be turned back into the cookie.
"""
from __future__ import annotations

import secrets

from . import auditlog
from . import db as base

TTL_DAYS = 14
SHORT_SECONDS = 12 * 3600
SLIDE_SECONDS = 3600
COOKIE = "skald_session"
MAX_COOKIE = 200


def _hash(cookie) -> str | None:
    if not isinstance(cookie, str) or not cookie or len(cookie) > MAX_COOKIE:
        return None
    return base.sha256(cookie)


def start(db, user_id, ip: str, agent: str, remember: bool = True) -> tuple[str, str]:
    """(cookie value, csrf value) for a new session of an enabled user: TTL_DAYS
    from its last use when `remember`, else SHORT_SECONDS."""
    row = db.execute("SELECT email, disabled_at FROM users WHERE id = ?", (user_id,)).fetchone()
    if row is None or row["disabled_at"]:
        raise ValueError("This account cannot sign in.")
    cookie, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(24)
    stamp = base.now()
    ttl = TTL_DAYS * 86400 if remember else SHORT_SECONDS
    with base.tx(db):
        db.execute("INSERT INTO sessions (id_hash, user_id, csrf, created_at, last_seen, "
                   "expires_at, ip_hash, agent, ttl_seconds) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                   (base.sha256(cookie), user_id, csrf, stamp, stamp, base.shift(ttl),
                    base.keyed_hash(db, ip) if ip else None, str(agent or "")[:200], ttl))
        db.execute("UPDATE users SET last_seen = ? WHERE id = ?", (stamp, user_id))
        auditlog.record(db, None, user_id, "session.start", row["email"])
    return cookie, csrf


def resolve(db, cookie: str | None) -> dict | None:
    """Who holds this cookie, or None (unknown, expired or disabled)."""
    digest = _hash(cookie)
    if digest is None:
        return None
    row = db.execute(
        "SELECT s.id_hash, s.user_id, s.csrf, s.last_seen, s.expires_at, s.ttl_seconds, "
        "u.email, u.name, "
        "u.install_admin, u.disabled_at FROM sessions s JOIN users u ON u.id = s.user_id "
        "WHERE s.id_hash = ?", (digest,)).fetchone()
    if row is None:
        return None
    stamp = base.now()
    if row["expires_at"] <= stamp:
        db.execute("DELETE FROM sessions WHERE id_hash = ?", (digest,))
        return None
    if row["disabled_at"]:
        return None
    ttl = int(row["ttl_seconds"] or TTL_DAYS * 86400)
    if row["last_seen"] <= base.shift(-min(SLIDE_SECONDS, ttl // 12)):
        with base.tx(db):
            db.execute("UPDATE sessions SET last_seen = ?, expires_at = ? WHERE id_hash = ?",
                       (stamp, base.shift(ttl), digest))
            db.execute("UPDATE users SET last_seen = ? WHERE id = ?", (stamp, row["user_id"]))
    return {"user_id": row["user_id"], "email": row["email"], "name": row["name"],
            "install_admin": bool(row["install_admin"]), "session_id": row["id_hash"],
            "csrf": row["csrf"]}


def end(db, cookie) -> None:
    """Sign out the session this cookie holds (nothing if there is none)."""
    digest = _hash(cookie)
    if digest is None:
        return
    with base.tx(db):
        row = db.execute("SELECT user_id FROM sessions WHERE id_hash = ?", (digest,)).fetchone()
        if row is None:
            return
        db.execute("DELETE FROM sessions WHERE id_hash = ?", (digest,))
        auditlog.record(db, None, row["user_id"], "session.end")


def end_id(db, user_id, session_id) -> bool:
    """Sign out one of `user_id`'s own sessions by its id; False if not theirs."""
    with base.tx(db):
        cur = db.execute("DELETE FROM sessions WHERE id_hash = ? AND user_id = ?",
                         (str(session_id or ""), user_id))
        if cur.rowcount:
            auditlog.record(db, None, user_id, "session.end")
        return bool(cur.rowcount)


def end_all(db, user_id, except_session=None, actor=None) -> int:
    """Sign out every session of `user_id` but `except_session`; how many ended.
    `actor` (default: the user) is who asked, for the audit log."""
    with base.tx(db):
        cur = db.execute("DELETE FROM sessions WHERE user_id = ? AND id_hash != ?",
                         (user_id, str(except_session or "")))
        if cur.rowcount:
            auditlog.record(db, None, user_id if actor is None else actor, "session.end_all", "",
                            f"{cur.rowcount} ended")
        return cur.rowcount


def list_for(db, user_id) -> list[dict]:
    """The user's live sessions, newest first. No address, not even hashed."""
    return base.rows(db, "SELECT id_hash AS session_id, created_at, last_seen, expires_at, "
                         "agent FROM sessions WHERE user_id = ? AND expires_at > ? "
                         "ORDER BY last_seen DESC, created_at DESC", (user_id, base.now()))


def prune(db) -> int:
    """Delete expired sessions (the helper may call this now and then)."""
    return db.execute("DELETE FROM sessions WHERE expires_at <= ?", (base.now(),)).rowcount
