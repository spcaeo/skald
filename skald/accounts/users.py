"""People and their memberships.

A user is one email address. Roles are per organisation: owner, admin,
viewer. An organisation always keeps at least one owner who is not
disabled; removing, demoting or disabling the last one is refused in plain
words. The install keeps at least one install admin the same way.
"""
from __future__ import annotations

import re

from . import auditlog, passwords
from . import db as base
from . import sessions

ROLES = ("owner", "admin", "viewer")
EMAIL = re.compile(r"^[^@\s]+@[^@\s.][^@\s]*\.[^@\s.]+$")
PUBLIC = ("id, email, name, install_admin, created_at, last_seen, disabled_at, must_reset, "
          "totp_secret IS NOT NULL AS totp_on, pw_hash IS NOT NULL AS has_password")
SECRET = ", pw_hash, totp_secret, totp_pending, totp_last_step"


def clean_email(email) -> str:
    """Lowercased and stripped; ValueError when it is not an address."""
    email = str(email or "").strip().lower()
    if len(email) > 254 or not EMAIL.match(email):
        raise ValueError("That does not look like an email address.")
    return email


def _shape(row: dict | None) -> dict | None:
    if row is None:
        return None
    for key in ("install_admin", "totp_on", "has_password", "must_reset"):
        row[key] = bool(row[key])
    return row


def find_user(db, email=None, user_id=None, secrets=False) -> dict | None:
    cols = PUBLIC + (SECRET if secrets else "")
    if user_id is not None:
        return _shape(base.one(db, f"SELECT {cols} FROM users WHERE id = ?", (user_id,)))
    try:
        email = clean_email(email)
    except ValueError:
        return None
    return _shape(base.one(db, f"SELECT {cols} FROM users WHERE email = ?", (email,)))


def _need(db, user_id) -> dict:
    user = find_user(db, user_id=user_id)
    if user is None:
        raise ValueError("There is no such user.")
    return user


def create_user(db, email, name, password=None, install_admin=False, actor="cli") -> dict:
    email = clean_email(email)
    pw_hash = None
    if password is not None:
        problem = passwords.password_problem(password, email)
        if problem:
            raise ValueError(problem)
        pw_hash = passwords.hash_password(password)
    with base.tx(db):
        if db.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone():
            raise ValueError(f"{email} already has an account.")
        cur = db.execute("INSERT INTO users (email, name, pw_hash, install_admin, created_at) "
                         "VALUES (?, ?, ?, ?, ?)",
                         (email, " ".join(str(name or "").split())[:100], pw_hash,
                          int(bool(install_admin)), base.now()))
        auditlog.record(db, None, actor, "user.create", email,
                        "install admin" if install_admin else "")
        return find_user(db, user_id=cur.lastrowid)


def authenticate(db, email, password) -> dict | None:
    """The user, when the email and password match an enabled account.
    Does the same scrypt work when they do not, so timing tells nothing."""
    user = find_user(db, email=email, secrets=True)
    if user is None or not user["pw_hash"] or user["disabled_at"]:
        return passwords.burn(password) or None
    if not passwords.verify_password(password, user["pw_hash"]):
        return None
    return find_user(db, user_id=user["id"])


def set_password(db, user_id, pw, actor) -> None:
    user = _need(db, user_id)
    problem = passwords.password_problem(pw, user["email"])
    if problem:
        raise ValueError(problem)
    pw_hash = passwords.hash_password(pw)
    with base.tx(db):
        db.execute("UPDATE users SET pw_hash = ?, must_reset = 0 WHERE id = ?",
                   (pw_hash, user_id))
        sessions.end_all(db, user_id, actor=actor)
        auditlog.record(db, None, actor, "user.password", user["email"])


def set_name(db, user_id, name, actor) -> None:
    user = _need(db, user_id)
    with base.tx(db):
        db.execute("UPDATE users SET name = ? WHERE id = ?",
                   (" ".join(str(name or "").split())[:100], user_id))
        auditlog.record(db, None, actor, "user.name", user["email"])


def disable_user(db, user_id, actor) -> None:
    """Refused (ValueError) for the last active owner of any organisation."""
    user = _need(db, user_id)
    with base.tx(db):
        for (org_id,) in db.execute("SELECT org_id FROM members WHERE user_id = ? AND "
                                    "role = 'owner'", (user_id,)).fetchall():
            _keep_an_owner(db, org_id, user_id)
        db.execute("UPDATE users SET disabled_at = ? WHERE id = ?", (base.now(), user_id))
        sessions.end_all(db, user_id, actor=actor)
        auditlog.record(db, None, actor, "user.disable", user["email"])


def enable_user(db, user_id, actor) -> None:
    user = _need(db, user_id)
    with base.tx(db):
        db.execute("UPDATE users SET disabled_at = NULL WHERE id = ?", (user_id,))
        auditlog.record(db, None, actor, "user.enable", user["email"])


def set_install_admin(db, user_id, flag, actor) -> None:
    """Turn the install-admin flag on or off; the last enabled install admin
    keeps it (ValueError)."""
    user = _need(db, user_id)
    flag = bool(flag)
    with base.tx(db):
        if not flag and user["install_admin"]:
            others = db.execute("SELECT COUNT(*) FROM users WHERE install_admin = 1 AND "
                                "id != ? AND disabled_at IS NULL", (user_id,)).fetchone()[0]
            if not others:
                raise ValueError("This is the last install admin. Make someone else one "
                                 "first.")
        db.execute("UPDATE users SET install_admin = ? WHERE id = ?", (int(flag), user_id))
        auditlog.record(db, None, actor, "user.install_admin", user["email"],
                        "on" if flag else "off")


def _role(role) -> str:
    if role not in ROLES:
        raise ValueError(f"A role is one of: {', '.join(ROLES)}.")
    return role


def role_in(db, user_id, org_id) -> str | None:
    row = db.execute("SELECT role FROM members WHERE org_id = ? AND user_id = ?",
                     (org_id, user_id)).fetchone()
    return row[0] if row else None


def site_role(db, user_id, site) -> tuple[str | None, dict | None]:
    """(role, org) for `user_id` on `site`: (None, org) when not a member,
    (None, None) when the site belongs to no organisation."""
    from .orgs import org_of_site
    org = org_of_site(db, site)
    if org is None:
        return None, None
    return role_in(db, user_id, org["id"]), org


def add_member(db, org_id, user_id, role, actor) -> None:
    role = _role(role)
    user = _need(db, user_id)
    with base.tx(db):
        if not db.execute("SELECT 1 FROM orgs WHERE id = ?", (org_id,)).fetchone():
            raise ValueError("There is no such organisation.")
        if role_in(db, user_id, org_id):
            raise ValueError(f"{user['email']} is already a member.")
        db.execute("INSERT INTO members (org_id, user_id, role, added_by, added_at) "
                   "VALUES (?, ?, ?, ?, ?)", (org_id, user_id, role, str(actor), base.now()))
        auditlog.record(db, org_id, actor, "member.add", user["email"], role)


def _keep_an_owner(db, org_id, user_id) -> None:
    others = db.execute(
        "SELECT COUNT(*) FROM members m JOIN users u ON u.id = m.user_id "
        "WHERE m.org_id = ? AND m.role = 'owner' AND m.user_id != ? "
        "AND u.disabled_at IS NULL", (org_id, user_id)).fetchone()[0]
    if not others:
        raise ValueError("This is the only owner of the organisation. "
                         "Make someone else an owner first.")


def set_role(db, org_id, user_id, role, actor) -> None:
    role = _role(role)
    user = _need(db, user_id)
    with base.tx(db):
        old = role_in(db, user_id, org_id)
        if old is None:
            raise ValueError(f"{user['email']} is not a member.")
        if old == "owner" and role != "owner":
            _keep_an_owner(db, org_id, user_id)
        db.execute("UPDATE members SET role = ? WHERE org_id = ? AND user_id = ?",
                   (role, org_id, user_id))
        auditlog.record(db, org_id, actor, "member.role", user["email"], f"{old} -> {role}")


def remove_member(db, org_id, user_id, actor) -> None:
    user = _need(db, user_id)
    with base.tx(db):
        old = role_in(db, user_id, org_id)
        if old is None:
            raise ValueError(f"{user['email']} is not a member.")
        if old == "owner":
            _keep_an_owner(db, org_id, user_id)
        db.execute("DELETE FROM members WHERE org_id = ? AND user_id = ?", (org_id, user_id))
        auditlog.record(db, org_id, actor, "member.remove", user["email"], old)


def members(db, org_id) -> list[dict]:
    got = base.rows(db, "SELECT u.id, u.email, u.name, m.role, m.added_at, u.last_seen, "
                        "u.totp_secret IS NOT NULL AS totp_on, u.disabled_at, "
                        "u.pw_hash IS NOT NULL AS has_password FROM members m "
                        "JOIN users u ON u.id = m.user_id WHERE m.org_id = ? "
                        "ORDER BY u.email", (org_id,))
    for m in got:
        m["totp_on"], m["has_password"] = bool(m["totp_on"]), bool(m["has_password"])
    return got
