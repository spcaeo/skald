"""Invites: an admin names an email and a role; the link is valid 7 days.

Only the SHA-256 of the link's token is kept. A new invite for the same
email in the same organisation replaces the older one (that is "resend").
Accepting makes the account, or, when the address already has one, just
adds the membership: the password typed then is ignored.

A link that was shown to the admin on screen (no mail set up, or the mail
failed) is marked `handed` (`mark_handed`). Whoever held it may not be the
person the address belongs to, so an account made from it is `must_reset`:
its first sign-in asks for a new password before anything else, and the
password chosen on the invite page works only for that one step. This keeps
an admin who accepts a handed link "to help" from knowing the password the
person goes on to use. It cannot prove the address is theirs: without mail
the install trusts the admin who passes the link on (docs/ACCOUNTS.md).
"""
from __future__ import annotations

import secrets

from . import auditlog, passwords
from . import db as base
from . import users

INVITE_DAYS = 7
NOT_VALID = "This invite link is not valid."


def invite(db, org_id, email, role, actor) -> str:
    """The raw token, for the link. Raises ValueError in plain words."""
    email = users.clean_email(email)
    if role not in users.ROLES:
        raise ValueError(f"A role is one of: {', '.join(users.ROLES)}.")
    token = secrets.token_urlsafe(32)
    with base.tx(db):
        if not db.execute("SELECT 1 FROM orgs WHERE id = ?", (org_id,)).fetchone():
            raise ValueError("There is no such organisation.")
        existing = users.find_user(db, email=email)
        if existing and users.role_in(db, existing["id"], org_id):
            raise ValueError(f"{email} is already a member.")
        db.execute("DELETE FROM invites WHERE org_id = ? AND email = ? AND used_at IS NULL",
                   (org_id, email))
        db.execute("INSERT INTO invites (token_hash, org_id, email, role, invited_by, "
                   "created_at, expires_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                   (base.sha256(token), org_id, email, role, str(actor), base.now(),
                    base.shift(INVITE_DAYS * 86400)))
        auditlog.record(db, org_id, actor, "invite.send", email, role)
    return token


def mark_handed(db, token) -> None:
    """The link of this invite was shown to the admin instead of mailed."""
    if isinstance(token, str) and token:
        db.execute("UPDATE invites SET handed = 1 WHERE token_hash = ?", (base.sha256(token),))


def _find(db, token) -> dict | None:
    if not isinstance(token, str) or not token or len(token) > 200:
        return None
    return base.one(db, "SELECT i.*, o.name AS org FROM invites i JOIN orgs o "
                        "ON o.id = i.org_id WHERE i.token_hash = ?", (base.sha256(token),))


def _usable(found: dict | None) -> dict:
    if found is None:
        raise ValueError(NOT_VALID)
    if found["used_at"]:
        raise ValueError("This invite was already used. Sign in instead.")
    if found["expires_at"] <= base.now():
        raise ValueError("This invite has expired. Ask for a new one.")
    return found


def invite_info(db, token) -> dict | None:
    """What the invite page shows, or None for a bad, used or expired link."""
    try:
        found = _usable(_find(db, token))
    except ValueError:
        return None
    return {"org_id": found["org_id"], "org": found["org"], "email": found["email"],
            "role": found["role"],
            "has_account": users.find_user(db, email=found["email"]) is not None}


def accept(db, token, name, password) -> dict:
    """The user (with "org_id", "role", "new"); ValueError on bad/used/expired."""
    found = _usable(_find(db, token))
    user = users.find_user(db, email=found["email"])
    pw_hash = None
    if user is None:
        problem = passwords.password_problem(password, found["email"])
        if problem:
            raise ValueError(problem)
        pw_hash = passwords.hash_password(password)
    elif user["disabled_at"]:
        raise ValueError("This account is disabled. Ask the person who invited you.")
    with base.tx(db):
        used = db.execute("UPDATE invites SET used_at = ? WHERE token_hash = ? "
                          "AND used_at IS NULL AND expires_at > ?",
                          (base.now(), found["token_hash"], base.now()))
        if not used.rowcount:
            raise ValueError(NOT_VALID)
        new = user is None
        if new:
            name = " ".join(str(name or "").split()) or found["email"].split("@", 1)[0]
            user = users.create_user(db, found["email"], name, actor="invite")
            db.execute("UPDATE users SET pw_hash = ?, must_reset = ? WHERE id = ?",
                       (pw_hash, int(bool(found["handed"])), user["id"]))
        if users.role_in(db, user["id"], found["org_id"]) is None:
            users.add_member(db, found["org_id"], user["id"], found["role"],
                             actor=found["invited_by"])
        auditlog.record(db, found["org_id"], user["id"], "invite.accept", found["email"],
                        found["role"] + ("; link was handed by an admin, new password "
                                         "asked at first sign-in" if new and found["handed"]
                                         else ""))
    got = users.find_user(db, user_id=user["id"])
    got.update(org_id=found["org_id"], role=users.role_in(db, user["id"], found["org_id"]),
               new=new)
    return got


def pending(db, org_id) -> list[dict]:
    """Unused invites of the organisation, with "expired" for the old ones."""
    got = base.rows(db, "SELECT email, role, invited_by, created_at, expires_at FROM invites "
                        "WHERE org_id = ? AND used_at IS NULL ORDER BY created_at, email",
                    (org_id,))
    stamp = base.now()
    for row in got:
        row["expired"] = row["expires_at"] <= stamp
    return got


def cancel(db, org_id, email, actor) -> int:
    email = users.clean_email(email)
    with base.tx(db):
        cur = db.execute("DELETE FROM invites WHERE org_id = ? AND email = ? "
                         "AND used_at IS NULL", (org_id, email))
        if cur.rowcount:
            auditlog.record(db, org_id, actor, "invite.cancel", email)
        return cur.rowcount
