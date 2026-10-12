"""Organisations and the sites they own.

An install holds organisations; each site belongs to exactly one. Every
request for a site is allowed only for members of its organisation.
"""
from __future__ import annotations

import re

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


def org_of_site(db, site) -> dict | None:
    return base.one(db, "SELECT o.id, o.name, o.slug, o.created_at FROM sites s "
                        "JOIN orgs o ON o.id = s.org_id WHERE s.name = ?", (site,))


def sites_of_org(db, org_id) -> list[str]:
    return [r[0] for r in db.execute("SELECT name FROM sites WHERE org_id = ? ORDER BY name",
                                     (org_id,))]
