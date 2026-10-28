"""People and their memberships.

A user is one email address. Roles are per organisation: owner, admin,
viewer. An organisation always keeps at least one owner who is not
disabled; removing, demoting or disabling the last one is refused in plain
words. The install keeps at least one install admin the same way.

Site access (schema 6): an admin or a viewer may be limited to some of the
organisation's sites (`members.sites`, a JSON list; NULL: every site, the
default). `site_role` answers None for a site outside the list, so every place
that decides a member's sites (nginx's session check, /me, the switcher, the
helper's routes, tokens they make, the mails) refuses it alike. An owner always
sees every site: making someone an owner clears their list.
"""
from __future__ import annotations

import json
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
        # The welcome line (2.44.0): one row made with the account, taken by its first /me.
        db.execute("INSERT INTO settings (scope, key, value, updated_by, updated_at) "
                   "VALUES (?, 'welcome', 'true', ?, ?)", (f"user:{cur.lastrowid}", actor, base.now()))
        auditlog.record(db, None, actor, "user.create", email,
                        "install admin" if install_admin else "")
        return find_user(db, user_id=cur.lastrowid)


def take_welcome(db, user_id) -> bool:
    """True once: on a new person's first dashboard load. Accounts made before
    2.44.0 have no row, so nobody already signed in sees it."""
    with base.tx(db):
        cur = db.execute("DELETE FROM settings WHERE scope = ? AND key = 'welcome'",
                         (f"user:{int(user_id)}",))
    return cur.rowcount == 1


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
    """(role, org) for `user_id` on `site`: (None, org) when not a member, or a
    member limited to other sites of it; (None, None) when the site belongs to
    no organisation."""
    from .orgs import org_of_site
    org = org_of_site(db, site)
    if org is None:
        return None, None
    row = db.execute("SELECT role, sites FROM members WHERE org_id = ? AND user_id = ?",
                     (org["id"], user_id)).fetchone()
    if row is None or not sees(row[1], site):
        return None, org
    return row[0], org


# ------------------------------------------------------------ site access

def _limit(raw) -> list[str] | None:
    """A stored `members.sites` / `invites.sites` value as a list, or None (every site)."""
    if raw in (None, ""):
        return None
    try:
        got = json.loads(raw)
    except (TypeError, ValueError):
        return []                       # unreadable: no site (never more than was given)
    return [str(s) for s in got] if isinstance(got, list) else []


site_limit = _limit


def sees(raw, site) -> bool:
    """Whether a member whose stored limit is `raw` may see `site`."""
    limit = _limit(raw)
    return limit is None or str(site) in limit


def site_access(db, org_id, user_id) -> list[str] | None:
    """The sites a member is limited to (only those still in the organisation),
    or None for every site."""
    row = db.execute("SELECT sites FROM members WHERE org_id = ? AND user_id = ?",
                     (org_id, user_id)).fetchone()
    limit = _limit(row[0]) if row is not None else None
    if limit is None:
        return None
    own = {r[0] for r in db.execute("SELECT name FROM sites WHERE org_id = ?", (org_id,))}
    return sorted(s for s in limit if s in own)


def visible_sites(db, org_id, user_id) -> list[str]:
    """The organisation's sites this member may see, by name."""
    names = [r[0] for r in db.execute("SELECT name FROM sites WHERE org_id = ? ORDER BY name",
                                      (org_id,))]
    limit = site_access(db, org_id, user_id)
    return names if limit is None else [n for n in names if n in limit]


def clean_sites(db, org_id, sites) -> list[str] | None:
    """A limit given by a person (a list of site names, or None for every site),
    checked against the organisation's sites. ValueError in plain words."""
    if sites is None:
        return None
    if not isinstance(sites, (list, tuple)) or not all(isinstance(s, str) for s in sites):
        raise ValueError("Sites is a list of site names, or none for every site.")
    got = sorted({s.strip().lower() for s in sites if s.strip()})
    if not got:
        raise ValueError("Choose at least one site, or every site.")
    own = {r[0] for r in db.execute("SELECT name FROM sites WHERE org_id = ?", (org_id,))}
    foreign = [s for s in got if s not in own]
    if foreign:
        raise ValueError(f"Not a site of this organisation: {', '.join(foreign)}.")
    return got


def set_site_access(db, org_id, user_id, sites, actor) -> list[str] | None:
    """Limit a member to `sites` (None: every site). An owner always sees every
    site. Their sessions on a site taken away end at its next request."""
    user = _need(db, user_id)
    with base.tx(db):
        role = role_in(db, user_id, org_id)
        if role is None:
            raise ValueError(f"{user['email']} is not a member.")
        got = clean_sites(db, org_id, sites)
        if got is not None and role == "owner":
            raise ValueError("An owner sees every site. Make them an admin or a viewer first.")
        old = site_access(db, org_id, user_id)
        db.execute("UPDATE members SET sites = ? WHERE org_id = ? AND user_id = ?",
                   (json.dumps(got) if got is not None else None, org_id, user_id))
        if old != got:
            auditlog.record(db, org_id, actor, "member.sites", user["email"],
                            f"{', '.join(old) if old is not None else 'every site'} -> "
                            f"{', '.join(got) if got is not None else 'every site'}")
    return got


def add_member(db, org_id, user_id, role, actor, sites=None) -> None:
    """`sites`: limit the new member to these sites of the organisation (not an owner)."""
    role = _role(role)
    user = _need(db, user_id)
    with base.tx(db):
        if not db.execute("SELECT 1 FROM orgs WHERE id = ?", (org_id,)).fetchone():
            raise ValueError("There is no such organisation.")
        if role_in(db, user_id, org_id):
            raise ValueError(f"{user['email']} is already a member.")
        limit = clean_sites(db, org_id, sites) if role != "owner" else None
        db.execute("INSERT INTO members (org_id, user_id, role, added_by, added_at, sites) "
                   "VALUES (?, ?, ?, ?, ?, ?)", (org_id, user_id, role, str(actor), base.now(),
                                                 json.dumps(limit) if limit else None))
        auditlog.record(db, org_id, actor, "member.add", user["email"],
                        role + (f"; only {', '.join(limit)}" if limit else ""))


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
        if role == "owner" and site_access(db, org_id, user_id) is not None:
            db.execute("UPDATE members SET sites = NULL WHERE org_id = ? AND user_id = ?",
                       (org_id, user_id))
            auditlog.record(db, org_id, actor, "member.sites", user["email"],
                            "every site: an owner sees every site")


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
    """Each member, with "sites": the sites they are limited to, or None (every site)."""
    got = base.rows(db, "SELECT u.id, u.email, u.name, m.role, m.added_at, u.last_seen, "
                        "u.totp_secret IS NOT NULL AS totp_on, u.disabled_at, "
                        "u.pw_hash IS NOT NULL AS has_password, m.sites FROM members m "
                        "JOIN users u ON u.id = m.user_id WHERE m.org_id = ? "
                        "ORDER BY u.email", (org_id,))
    own = {r[0] for r in db.execute("SELECT name FROM sites WHERE org_id = ?", (org_id,))}
    for m in got:
        m["totp_on"], m["has_password"] = bool(m["totp_on"]), bool(m["has_password"])
        limit = _limit(m["sites"])
        m["sites"] = None if limit is None else sorted(s for s in limit if s in own)
    return got


def owners(db, org_id) -> list[dict]:
    """The organisation's enabled owners, by email."""
    return [m for m in members(db, org_id) if m["role"] == "owner" and not m["disabled_at"]]
