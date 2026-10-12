"""Counts for `skald accounts status`: how many people, sessions, invites,
tokens. Read-only; numbers only, never an email, a hash or an address.
"""
from __future__ import annotations

from . import db as base


def install(db) -> dict:
    """The whole accounts file."""
    people = db.execute("SELECT COUNT(*), COUNT(disabled_at), "
                        "COALESCE(SUM(install_admin = 1 AND disabled_at IS NULL), 0), "
                        "COALESCE(SUM(must_reset), 0), "
                        "COALESCE(SUM(totp_secret IS NOT NULL), 0), "
                        "COALESCE(SUM(pw_hash IS NULL), 0) FROM users").fetchone()
    stamp = base.now()
    return {
        "people": people[0], "disabled": people[1], "install_admins": people[2],
        "must_reset": people[3], "totp_on": people[4], "no_password": people[5],
        "sessions": db.execute("SELECT COUNT(*) FROM sessions WHERE expires_at > ?",
                               (stamp,)).fetchone()[0],
        "orgs": db.execute("SELECT COUNT(*) FROM orgs").fetchone()[0],
        "sites": db.execute("SELECT COUNT(*) FROM sites").fetchone()[0],
        "audit_rows": db.execute("SELECT COUNT(*) FROM audit").fetchone()[0],
    }


def org(db, org_id) -> dict:
    """One organisation: members by role, open invites, tokens, its sites."""
    roles = dict(db.execute("SELECT role, COUNT(*) FROM members WHERE org_id = ? "
                            "GROUP BY role", (org_id,)).fetchall())
    stamp = base.now()
    toks = db.execute("SELECT COUNT(*), COUNT(revoked_at) FROM tokens WHERE org_id = ?",
                      (org_id,)).fetchone()
    return {
        "members": sum(roles.values()), "owners": roles.get("owner", 0),
        "admins": roles.get("admin", 0), "viewers": roles.get("viewer", 0),
        "invites": db.execute("SELECT COUNT(*) FROM invites WHERE org_id = ? AND used_at IS "
                              "NULL AND expires_at > ?", (org_id, stamp)).fetchone()[0],
        "expired_invites": db.execute("SELECT COUNT(*) FROM invites WHERE org_id = ? AND "
                                      "used_at IS NULL AND expires_at <= ?",
                                      (org_id, stamp)).fetchone()[0],
        "tokens": toks[0] - toks[1], "revoked": toks[1],
        "sites": [r[0] for r in db.execute("SELECT name FROM sites WHERE org_id = ? "
                                           "ORDER BY name", (org_id,))],
    }
