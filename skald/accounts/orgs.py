"""Organisations and the sites they own.

An install holds organisations; each site belongs to exactly one. Every
request for a site is allowed only for members of its organisation.

Each organisation has (schema 6):

  privacy_class   "internal" (the default): its sites follow the install's
                  keep-everything rule (keep_everything.py), as before.
                  "client": its sites follow their own retention settings,
                  even on an install that keeps everything. Set by an install
                  admin only (set_privacy_class).
  archived_at     "Remove" an organisation archives it: every site of it is
                  paused (stops collecting), nothing is deleted, restore_org
                  undoes it. Deleting data stays a site's own "Delete all data".
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


COLS = "id, name, slug, created_at, privacy_class, archived_at"
PRIVACY_CLASSES = ("internal", "client")
# The marker archive_org writes as the pause's author, so restore_org resumes the
# sites the archive paused and leaves a site paused before it as it was.
ARCHIVE_PAUSE = "org-archive"


def get_org(db, org_id) -> dict | None:
    return base.one(db, f"SELECT {COLS} FROM orgs WHERE id = ?", (org_id,))


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
        return base.rows(db, f"SELECT {COLS} FROM orgs ORDER BY id")
    cols = ", ".join(f"o.{c.strip()}" for c in COLS.split(","))
    return base.rows(db, f"SELECT {cols}, m.role FROM orgs o "
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
    cols = ", ".join(f"o.{c.strip()}" for c in COLS.split(","))
    return base.one(db, f"SELECT {cols} FROM sites s "
                        "JOIN orgs o ON o.id = s.org_id WHERE s.name = ?", (site,))


def sites_of_org(db, org_id) -> list[str]:
    return [r[0] for r in db.execute("SELECT name FROM sites WHERE org_id = ? ORDER BY name",
                                     (org_id,))]


# ------------------------------------------------------------ privacy class

def privacy_class(db, org_id) -> str:
    """"internal" or "client"; "internal" for an organisation not found, so a
    doubt always keeps everything."""
    row = db.execute("SELECT privacy_class FROM orgs WHERE id = ?", (org_id,)).fetchone()
    return row[0] if row is not None and row[0] in PRIVACY_CLASSES else "internal"


def set_privacy_class(db, org_id, cls, actor) -> str:
    """Set the organisation's privacy class (install admins only: the caller
    checks). "internal" follows the install's keep-everything rule; "client"
    makes its sites follow their own retention settings. Audited."""
    cls = str(cls or "").strip().lower()
    if cls not in PRIVACY_CLASSES:
        raise ValueError(f"A privacy class is one of: {', '.join(PRIVACY_CLASSES)}.")
    with base.tx(db):
        old = get_org(db, org_id)
        if old is None:
            raise ValueError("There is no such organisation.")
        if old["privacy_class"] != cls:
            db.execute("UPDATE orgs SET privacy_class = ? WHERE id = ?", (cls, org_id))
            auditlog.record(db, org_id, actor, "org.privacy", old["name"],
                            f"{old['privacy_class']} -> {cls}")
    return cls


# ---------------------------------------------------------- archive, restore

def archive_org(db, org_id, actor) -> list[str]:
    """Archive the organisation: every active site of it is paused (ingest
    answers 503, the runs skip it), nothing is deleted. The sites paused now."""
    from . import site_state
    with base.tx(db):
        org = get_org(db, org_id)
        if org is None:
            raise ValueError("There is no such organisation.")
        if org["archived_at"]:
            raise ValueError(f"{org['name']} is already archived.")
        paused = []
        for site in sites_of_org(db, org_id):
            if site_state.get(db, site)["paused_at"]:
                continue
            site_state.pause(db, org_id, site, actor)
            db.execute("UPDATE site_state SET paused_by = ? WHERE name = ?",
                       (f"{ARCHIVE_PAUSE}:{actor}", site))
            paused.append(site)
        db.execute("UPDATE orgs SET archived_at = ?, archived_by = ? WHERE id = ?",
                   (base.now(), str(actor), org_id))
        auditlog.record(db, org_id, actor, "org.archive", org["name"],
                        f"sites paused: {', '.join(paused) or 'none'}; nothing deleted")
    return paused


def restore_org(db, org_id, actor) -> list[str]:
    """Undo archive_org: the sites the archive paused collect again (a site
    paused before it stays paused). The sites resumed."""
    from . import site_state
    with base.tx(db):
        org = get_org(db, org_id)
        if org is None:
            raise ValueError("There is no such organisation.")
        if not org["archived_at"]:
            raise ValueError(f"{org['name']} is not archived.")
        resumed = []
        for site in sites_of_org(db, org_id):
            row = site_state.get(db, site)
            if row["paused_at"] and str(row["paused_by"] or "").startswith(ARCHIVE_PAUSE + ":"):
                site_state.resume(db, org_id, site, actor)
                resumed.append(site)
        db.execute("UPDATE orgs SET archived_at = NULL, archived_by = NULL WHERE id = ?",
                   (org_id,))
        auditlog.record(db, org_id, actor, "org.restore", org["name"],
                        f"sites resumed: {', '.join(resumed) or 'none'}")
    return resumed
