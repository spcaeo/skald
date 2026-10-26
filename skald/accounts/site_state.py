"""A site's lifecycle in accounts.sqlite (`site_state`), for every site of the
install: one made from the dashboard and one from the server's config files alike.

    name                    the site
    paused_at, paused_by    set while the site is paused: the ingest endpoint
                            answers 503 with Retry-After (the shipper keeps its
                            lines and sends them again), live and run-daily skip
                            the site. History, settings, tokens and its pages stay.
    removed_at, removed_by  a config-file site removed from the dashboard (a site
                            made from the dashboard keeps its removal in
                            site_config.removed_at, site_configs.py). Its config
                            entry stays; the runs skip it, ingest answers 410.
    cleared_at, cleared_by  the last "Clear data" (or "Delete all data"): the days
                            before that local day are never collected again, so
                            they read Not recorded (never 0), even while the web
                            server's own log still holds them.

The table is made with CREATE TABLE IF NOT EXISTS on first use, like
site_configs.py's, so an install that never pauses a site is not changed. Each
change writes one audit row (auditlog.py): the site and the actor, nothing else.
"""
from __future__ import annotations

from . import auditlog
from . import db as base

TABLE = """
CREATE TABLE IF NOT EXISTS site_state (
  name TEXT PRIMARY KEY,
  paused_at TEXT, paused_by TEXT, removed_at TEXT, removed_by TEXT,
  cleared_at TEXT, cleared_by TEXT)
"""
FIELDS = ("paused_at", "paused_by", "removed_at", "removed_by", "cleared_at", "cleared_by")


def ensure(db) -> None:
    # execute, not executescript: that would commit a caller's open transaction.
    db.execute(TABLE.strip())


def get(db, name) -> dict:
    """The site's row, or every field None."""
    ensure(db)
    row = db.execute("SELECT * FROM site_state WHERE name = ?", (str(name),)).fetchone()
    return dict(row) if row is not None else {"name": str(name), **dict.fromkeys(FIELDS)}


def every(db) -> dict[str, dict]:
    """{name: row} for every site with a row."""
    ensure(db)
    return {r["name"]: dict(r) for r in db.execute("SELECT * FROM site_state")}


def _set(db, name, **fields) -> None:
    ensure(db)
    db.execute("INSERT OR IGNORE INTO site_state (name) VALUES (?)", (str(name),))
    sets = ", ".join(f"{k} = ?" for k in fields)
    db.execute(f"UPDATE site_state SET {sets} WHERE name = ?", (*fields.values(), str(name)))


def pause(db, org_id, name, actor) -> dict:
    with base.tx(db):
        if get(db, name)["paused_at"]:
            raise ValueError(f"{name} is already paused.")
        _set(db, name, paused_at=base.now(), paused_by=str(actor))
        auditlog.record(db, org_id, actor, "site.pause", name,
                        "collecting stopped; history, settings and tokens kept")
    return get(db, name)


def resume(db, org_id, name, actor) -> dict:
    """Resume a paused site. The row as it was (its paused_at), for the words."""
    with base.tx(db):
        was = get(db, name)
        if not was["paused_at"]:
            raise ValueError(f"{name} is not paused.")
        _set(db, name, paused_at=None, paused_by=None)
        auditlog.record(db, org_id, actor, "site.resume", name,
                        f"paused since {was['paused_at']}")
    return was


def set_removed(db, org_id, name, actor, removed: bool, audit: bool = True) -> dict:
    """A config-file site removed (or restored) from the dashboard."""
    with base.tx(db):
        if removed:
            _set(db, name, removed_at=base.now(), removed_by=str(actor))
        else:
            _set(db, name, removed_at=None, removed_by=None)
        if audit:
            auditlog.record(db, org_id, actor, "site.remove" if removed else "site.restore",
                            name, "processing stopped; data kept" if removed
                            else "processing starts again")
    return get(db, name)


def mark_cleared(db, name, actor) -> dict:
    """The site's data was cleared now: days before today are not collected again."""
    with base.tx(db):
        _set(db, name, cleared_at=base.now(), cleared_by=str(actor))
    return get(db, name)


def forget(db, name) -> None:
    """A dashboard site deleted for good: no row left (its name is held by site_verify)."""
    ensure(db)
    db.execute("DELETE FROM site_state WHERE name = ?", (str(name),))
