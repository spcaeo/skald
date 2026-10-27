"""Accounts and tenants: organisations, people, sessions, invites, tokens.

The core library behind `access.mode: sessions` (docs/plans/
2026-10-11-phase1-accounts-plan.md §1). No HTTP here: the helper's sign-in
and team endpoints and the CLI call these functions. Every function takes
an open connection from `connect(path)`; nothing is kept between calls.

    from skald import accounts
    db = accounts.connect(accounts.path_for(config, live_dir))
    try:
        who = accounts.sessions.resolve(db, cookie)
    finally:
        db.close()
"""
from __future__ import annotations

from . import (apitokens, auditlog, counts, db, invites, limits, orgs, passwords, resets,
               sessions, totp, users)
from .db import SCHEMA_VERSION, connect, keyed_hash, now, path_for, tx
from .invites import INVITE_DAYS, accept, cancel, invite, invite_info, pending
from .orgs import (archive_org, assign_site, create_org, get_org, list_orgs, org_of_site,
                   rename_org, restore_org, set_privacy_class, sites_of_org)
from .passwords import MIN_LENGTH, hash_password, password_problem, verify_password
from .resets import RESET_MINUTES, issue_for, request_reset, use_reset
from .sessions import TTL_DAYS
from .users import (ROLES, add_member, authenticate, clean_email, create_user, disable_user,
                    enable_user, find_user, members, remove_member, role_in,
                    set_install_admin, set_name, set_password, set_role, site_role)

__all__ = [
    "apitokens", "auditlog", "counts", "db", "invites", "limits", "orgs", "passwords", "resets",
    "sessions", "totp", "users",
    "SCHEMA_VERSION", "connect", "keyed_hash", "now", "path_for", "tx",
    "INVITE_DAYS", "accept", "cancel", "invite", "invite_info", "pending",
    "assign_site", "create_org", "get_org", "list_orgs", "org_of_site", "rename_org",
    "sites_of_org", "archive_org", "restore_org", "set_privacy_class",
    "MIN_LENGTH", "hash_password", "password_problem", "verify_password",
    "RESET_MINUTES", "issue_for", "request_reset", "use_reset", "TTL_DAYS",
    "ROLES", "add_member", "authenticate", "clean_email", "create_user", "disable_user",
    "enable_user", "find_user", "members", "remove_member", "role_in", "set_install_admin",
    "set_name",
    "set_password", "set_role", "site_role",
]
