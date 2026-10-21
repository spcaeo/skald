"""How far a site's "Add a site" wizard got, so it can be left and resumed.

One row per site in accounts.sqlite (`site_setup`), made with CREATE TABLE
IF NOT EXISTS on first use, like site_configs.py's table:

    name        the site
    org_id      its organisation
    step        the step reached, 1 to 5 (STEPS)
    method      how its visits reach Skald (METHODS), or NULL before step 3
    verified    1 when its domain was verified (site_verify.py) at the last save
    token_id    the id of the sending token made in the wizard, never the token
    found       what the site check saw (site_detect.py), as JSON, so a resumed
                wizard shows it; only the keys site_detect.clean_found keeps
    started_at, updated_at, updated_by, done_at   (done: the Test found lines)

The step and method come from the page; `verified` is read from
site_verify.py, never taken from the page. A change of step, method or
done is one audit row ("site.setup"). `found` was added later: `ensure`
adds the column to an older table.
"""
from __future__ import annotations

import json

from . import auditlog
from . import db as base

TABLE = ("CREATE TABLE IF NOT EXISTS site_setup (name TEXT PRIMARY KEY, org_id INTEGER NOT NULL, "
         "step INTEGER NOT NULL DEFAULT 1, method TEXT, verified INTEGER NOT NULL DEFAULT 0, "
         "token_id TEXT, started_at TEXT NOT NULL, updated_at TEXT NOT NULL, updated_by TEXT, "
         "done_at TEXT, found TEXT)")
STEPS = 5
METHODS = ("docker", "systemd", "cloudflare", "vercel", "netlify", "script")
# The log format a site made from the dashboard is given when its method is
# chosen and nothing has arrived yet: the Worker's records alone need
# edge_json (logs.edge_only_cached is off only then); the rest read as auto.
FORMAT_FOR = {"cloudflare": "edge_json"}


def ensure(db) -> None:
    db.execute(TABLE)
    if "found" not in {r[1] for r in db.execute("PRAGMA table_info(site_setup)")}:
        db.execute("ALTER TABLE site_setup ADD COLUMN found TEXT")


def _entry(row) -> dict:
    d = dict(row)
    d["verified"] = bool(d.get("verified"))
    d["done"] = bool(d.get("done_at"))
    try:
        d["found"] = json.loads(d["found"]) if d.get("found") else None
    except ValueError:
        d["found"] = None
    return d


def get(db, name) -> dict | None:
    ensure(db)
    row = db.execute("SELECT * FROM site_setup WHERE name = ?", (str(name),)).fetchone()
    return _entry(row) if row is not None else None


def for_org(db, org_id) -> dict[str, dict]:
    ensure(db)
    return {r["name"]: _entry(r) for r in
            db.execute("SELECT * FROM site_setup WHERE org_id = ?", (org_id,))}


def save(db, org_id, name, actor, step=None, method=None, token_id=None, done=None,
         found=None) -> dict:
    """Record the wizard's progress for `name`; ValueError in plain words.
    `found`: a site check's facts, cleaned by site_detect.clean_found."""
    from .. import site_detect, site_verify
    if step is not None:
        try:
            step = int(step)
        except (TypeError, ValueError):
            raise ValueError("step is a number from 1 to 5.") from None
        if not 1 <= step <= STEPS:
            raise ValueError("step is a number from 1 to 5.")
    if method is not None and method not in METHODS:
        raise ValueError(f"A method is one of: {', '.join(METHODS)}.")
    if token_id is not None:
        token_id = str(token_id).removeprefix("skald_").split("_", 1)[0][:16]
    found = site_detect.clean_found(found) if found is not None else None
    kept = json.dumps(found, sort_keys=True) if found else None
    ensure(db)
    verified = 0 if site_verify.pending(db, name) else 1
    stamp = base.now()
    with base.tx(db):
        old = get(db, name)
        if old is not None and old["org_id"] != org_id:
            raise ValueError("There is no such site in this organisation.")
        if old is None:
            db.execute("INSERT INTO site_setup (name, org_id, step, method, verified, token_id, "
                       "started_at, updated_at, updated_by, done_at, found) "
                       "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                       (name, org_id, step or 1, method, verified, token_id, stamp, stamp,
                        str(actor), stamp if done else None, kept))
        else:
            db.execute("UPDATE site_setup SET step = ?, method = ?, verified = ?, token_id = ?, "
                       "updated_at = ?, updated_by = ?, done_at = ?, found = ? WHERE name = ?",
                       (step or old["step"], method or old["method"], verified,
                        token_id or old["token_id"], stamp, str(actor),
                        (stamp if done else None) if done is not None else old["done_at"],
                        kept if kept else (json.dumps(old["found"], sort_keys=True)
                                           if old["found"] else None), name))
        new = get(db, name)
        before = (old or {}).get("step"), (old or {}).get("method"), (old or {}).get("done")
        if before != (new["step"], new["method"], new["done"]):
            words = f"step {new['step']} of {STEPS}"
            if new["method"]:
                words += f"; {new['method']}"
            if new["done"]:
                words += "; done"
            auditlog.record(db, org_id, actor, "site.setup", name, words)
    return new


def forget(db, name) -> None:
    ensure(db)
    db.execute("DELETE FROM site_setup WHERE name = ?", (str(name),))
