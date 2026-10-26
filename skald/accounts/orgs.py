"""Organisations and the sites they own.

An install holds organisations; each site belongs to exactly one. Every
request for a site is allowed only for members of its organisation.
"""
from __future__ import annotations

import json
import re
import sqlite3

from . import auditlog
from . import db as base


def _slug(db, name: str) -> str:
    stem = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40] or "org"
    slug, n = stem, 1
    while db.execute("SELECT 1 FROM orgs WHERE slug = ?", (slug,)).fetchone():
        n += 1
        slug = f"{stem}-{n}"
    return slug


def _name(name) -> str:
    name = " ".join(str(name or "").split())[:100]
    if not name:
        raise ValueError("Give the organisation a name.")
    return name


def create_org(db, name, actor) -> dict:
    name = _name(name)
    with base.tx(db):
        cur = db.execute("INSERT INTO orgs (name, slug, created_at) VALUES (?, ?, ?)",
                         (name, _slug(db, name), base.now()))
        auditlog.record(db, cur.lastrowid, actor, "org.create", name)
        return get_org(db, cur.lastrowid)


def get_org(db, org_id) -> dict | None:
    return base.one(db, "SELECT id, name, slug, created_at FROM orgs WHERE id = ?", (org_id,))


def rename_org(db, org_id, name, actor) -> None:
    name = _name(name)
    with base.tx(db):
        old = get_org(db, org_id)
        if old is None:
            raise ValueError("There is no such organisation.")
        db.execute("UPDATE orgs SET name = ? WHERE id = ?", (name, org_id))
        auditlog.record(db, org_id, actor, "org.rename", name, f"was {old['name']}")


def list_orgs(db, user_id=None) -> list[dict]:
    """Every organisation, or those `user_id` is a member of (with "role")."""
    if user_id is None:
        return base.rows(db, "SELECT id, name, slug, created_at FROM orgs ORDER BY id")
    return base.rows(db, "SELECT o.id, o.name, o.slug, o.created_at, m.role FROM orgs o "
                         "JOIN members m ON m.org_id = o.id WHERE m.user_id = ? ORDER BY o.id",
                     (user_id,))


def assign_site(db, site, org_id, actor) -> None:
    """Give `site` to the organisation. A token reads only its own
    organisation's sites, so the tokens that name this site alone (a site's
    log shipper, a one-site MCP token) move with it (2.38.0; before, they
    stopped working). A token naming other sites too, or all of the old
    organisation's, stays there. Its settings (site_config) and its set-up
    progress (site_setup) move too, also when the site is already there, so
    running it again mends a move made before 2.38.0 (left behind, the old
    organisation's Settings > Sites still listed the site and its wizard
    could save nothing: "There is no such site in this organisation")."""
    site = str(site or "").strip()
    if not site:
        raise ValueError("Name the site.")
    with base.tx(db):
        if get_org(db, org_id) is None:
            raise ValueError("There is no such organisation.")
        before = org_of_site(db, site)
        db.execute("INSERT INTO sites (name, org_id) VALUES (?, ?) "
                   "ON CONFLICT(name) DO UPDATE SET org_id = excluded.org_id", (site, org_id))
        auditlog.record(db, org_id, actor, "site.assign", site,
                        f"was {before['name']}" if before else "")
        for table, what in (("site_config", "its settings"), ("site_setup", "its set-up progress")):
            try:
                moved = db.execute(f"UPDATE {table} SET org_id = ? WHERE name = ? AND org_id != ?",
                                   (org_id, site, org_id)).rowcount
            except sqlite3.OperationalError:    # a table not made yet: nothing to move
                moved = 0
            if moved:
                auditlog.record(db, org_id, actor, "site.move", site, f"{what} moved with it")
        if before is None or before["id"] == org_id:
            return
        for tid, name in db.execute("SELECT id, name FROM tokens WHERE org_id = ? AND sites = ?",
                                    (before["id"], json.dumps([site]))).fetchall():
            db.execute("UPDATE tokens SET org_id = ? WHERE id = ?", (org_id, tid))
            auditlog.record(db, org_id, actor, "token.move", tid,
                            f"{name}: moved with {site} from {before['name']}")


def org_of_site(db, site) -> dict | None:
    return base.one(db, "SELECT o.id, o.name, o.slug, o.created_at FROM sites s "
                        "JOIN orgs o ON o.id = s.org_id WHERE s.name = ?", (site,))


def sites_of_org(db, org_id) -> list[str]:
    return [r[0] for r in db.execute("SELECT name FROM sites WHERE org_id = ? ORDER BY name",
                                     (org_id,))]
