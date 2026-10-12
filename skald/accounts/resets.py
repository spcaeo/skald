"""Forgotten passwords: a link valid 60 minutes, used once.

`request_reset` does the same work whether or not the address has an
account (the same hashing, the same rate-limit write) and answers None for
an unknown, disabled or rate-limited address; the caller says the same
words either way. At most RESETS_PER_HOUR links per address per hour.
Using a link sets the password, voids the user's other links and ends every
session of the user (and clears `must_reset`).

`issue_for` is the link an install admin or the CLI makes for someone
(`skald account reset-link`): not counted against the 3 an hour, and
audited with who made it.
"""
from __future__ import annotations

import secrets

from . import auditlog, limits, passwords
from . import db as base
from . import sessions, users

RESET_MINUTES = 60
RESETS_PER_HOUR = 3
NOT_VALID = "This reset link is not valid."


def request_reset(db, email) -> str | None:
    try:
        email = users.clean_email(email)
    except ValueError:
        email = ""
    key = f"reset:{email}"
    limited = limits.too_many(db, key, limit=RESETS_PER_HOUR, minutes=60)
    limits.note_failure(db, key)
    user = users.find_user(db, email=email) if email else None
    token = secrets.token_urlsafe(32)
    digest = base.sha256(token)
    if limited or user is None or user["disabled_at"]:
        return None
    with base.tx(db):
        db.execute("INSERT INTO resets (token_hash, user_id, created_at, expires_at) "
                   "VALUES (?, ?, ?, ?)",
                   (digest, user["id"], base.now(), base.shift(RESET_MINUTES * 60)))
        auditlog.record(db, None, user["id"], "reset.request", email)
    return token


def issue_for(db, user_id, actor) -> str:
    """A reset link's raw token for `user_id`, made by `actor` (an admin or
    "cli"). ValueError for an unknown or disabled account."""
    user = users.find_user(db, user_id=user_id)
    if user is None:
        raise ValueError("There is no such user.")
    if user["disabled_at"]:
        raise ValueError(f"{user['email']} is disabled. Enable the account first.")
    token = secrets.token_urlsafe(32)
    with base.tx(db):
        db.execute("INSERT INTO resets (token_hash, user_id, created_at, expires_at) "
                   "VALUES (?, ?, ?, ?)",
                   (base.sha256(token), user["id"], base.now(), base.shift(RESET_MINUTES * 60)))
        auditlog.record(db, None, actor, "reset.issue", user["email"])
    return token


def use_reset(db, token, new_password) -> dict:
    """Set the password; returns the user. ValueError on a bad link or password."""
    if not isinstance(token, str) or not token or len(token) > 200:
        raise ValueError(NOT_VALID)
    found = base.one(db, "SELECT * FROM resets WHERE token_hash = ?", (base.sha256(token),))
    if found is None:
        raise ValueError(NOT_VALID)
    if found["used_at"]:
        raise ValueError("This reset link was already used. Ask for a new one.")
    if found["expires_at"] <= base.now():
        raise ValueError("This reset link has expired. Ask for a new one.")
    user = users.find_user(db, user_id=found["user_id"])
    if user is None or user["disabled_at"]:
        raise ValueError(NOT_VALID)
    problem = passwords.password_problem(new_password, user["email"])
    if problem:
        raise ValueError(problem)
    pw_hash = passwords.hash_password(new_password)
    with base.tx(db):
        used = db.execute("UPDATE resets SET used_at = ? WHERE token_hash = ? "
                          "AND used_at IS NULL", (base.now(), found["token_hash"]))
        if not used.rowcount:
            raise ValueError(NOT_VALID)
        db.execute("UPDATE resets SET used_at = ? WHERE user_id = ? AND used_at IS NULL",
                   (base.now(), user["id"]))
        db.execute("UPDATE users SET pw_hash = ?, must_reset = 0 WHERE id = ?",
                   (pw_hash, user["id"]))
        sessions.end_all(db, user["id"])
        auditlog.record(db, None, user["id"], "reset.use", user["email"])
    return users.find_user(db, user_id=user["id"])
