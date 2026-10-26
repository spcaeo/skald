"""Sites made from the dashboard: a `site_config` row per site in accounts.sqlite.

Config-file sites (config.yml and its `sites:` files, multisite.py) stay
as they are. A site added from Settings > Sites, or with `skald site add`,
is a row here instead: its name (the host), the organisation that owns it,
its host names, views, time zone, log folder and file name, and the log
format. multisite.py reads the active rows and lays each over the
install's config, like a `sites:` file; a config-file site of the same
name wins.

Removing a site (`remove`) only stops processing: the row is marked
removed, multisite.py skips it, the ingest endpoint answers 410; `restore`
undoes it. Its history, dashboard folder and log files stay until an owner's
"Delete all data" or `skald site purge <name>` (site_lifecycle.py), which
archives every store of the site, deletes them, and calls `purge` here.

The table is made with CREATE TABLE IF NOT EXISTS on first use (`ensure`),
outside db.py's numbered schema, so an accounts file without dashboard
sites is not changed at all.
"""
from __future__ import annotations

import json
import re

from . import auditlog
from . import db as base

TABLE = """
CREATE TABLE IF NOT EXISTS site_config (
  name TEXT PRIMARY KEY,
  org_id INTEGER NOT NULL REFERENCES orgs(id),
  hosts TEXT NOT NULL, views TEXT, timezone TEXT, log_dir TEXT, log_base TEXT,
  format TEXT NOT NULL DEFAULT 'auto',
  created_by TEXT, created_at TEXT NOT NULL, removed_at TEXT, removed_by TEXT);
"""
# The log formats a site can name (parse.PARSERS, and auto-detection).
FORMATS = ("auto", "nginx_extended", "nginx_combined", "apache_combined", "caddy_json",
           "cloudflare_json", "cloudfront_w3c", "fastly_json", "akamai_json", "vercel_json",
           "netlify_json", "edge_json")
# A site name is its host: what the dashboard's paths and nginx's routes accept.
NAME = re.compile(r"^(?=.{3,100}$)[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?"
                  r"(?:\.[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?)+$")
RESERVED = {"sites.json", "index.html", "_app", "data", "api", "exports"}


def ensure(db) -> None:
    # execute, not executescript: that would commit a caller's open transaction.
    db.execute(TABLE.strip().rstrip(";"))


def clean_name(name) -> str:
    """The site's name as stored: a lower-case host name with at least one dot."""
    got = str(name or "").strip().lower().rstrip(".")
    if got.startswith(("http://", "https://")):
        got = got.split("://", 1)[1].split("/", 1)[0]
    if not NAME.match(got) or got in RESERVED:
        raise ValueError("A site's name is its host name, like shop.example.com: "
                         "letters, digits, dots and dashes.")
    return got


def _entry(row) -> dict:
    d = dict(row)
    d["hosts"] = json.loads(d["hosts"]) if d.get("hosts") else []
    d["views"] = json.loads(d["views"]) if d.get("views") else []
    d["active"] = not d.get("removed_at")
    return d


def get(db, name) -> dict | None:
    ensure(db)
    row = db.execute("SELECT * FROM site_config WHERE name = ?", (str(name),)).fetchone()
    return _entry(row) if row is not None else None


def listing(db, org_id=None, include_removed: bool = True) -> list[dict]:
    """The dashboard sites, of one organisation or of the install, by name."""
    ensure(db)
    sql, args = "SELECT * FROM site_config", []
    where = []
    if org_id is not None:
        where.append("org_id = ?")
        args.append(org_id)
    if not include_removed:
        where.append("removed_at IS NULL")
    if where:
        sql += " WHERE " + " AND ".join(where)
    return [_entry(r) for r in db.execute(sql + " ORDER BY name", args)]


def active(db) -> list[dict]:
    return listing(db, include_removed=False)


def _validated(hosts, timezone, views, fmt, name: str) -> tuple[list, str | None, list, str]:
    from ..settings_store import Invalid, validate
    try:
        hosts = validate("sites.hosts", hosts or [name])
        timezone = validate("sites.timezone", timezone) if timezone else None
        views = validate("sites.views", views) if views else []
    except Invalid as why:
        raise ValueError(str(why)) from None
    fmt = str(fmt or "auto").strip()
    if fmt not in FORMATS:
        raise ValueError(f"A log format is one of: {', '.join(FORMATS)}.")
    return hosts, timezone, views, fmt


def create(db, org_id, name, actor, hosts=None, timezone=None, views=None, log_dir=None,
           log_base="access.log", fmt="auto", taken=(), allow_reuse=False) -> dict:
    """Add a dashboard site owned by `org_id`. `taken`: the install's
    config-file site names, which a new site may not reuse. A name purged
    in the last 30 days is refused unless `allow_reuse` (the install
    admin's `--allow-reuse`; site_verify.py). Raises ValueError with the
    reason in plain words."""
    from ..site_verify import refuse_reserved
    name = clean_name(name)
    hosts, timezone, views, fmt = _validated(hosts, timezone, views, fmt, name)
    ensure(db)
    with base.tx(db):
        if not db.execute("SELECT 1 FROM orgs WHERE id = ?", (org_id,)).fetchone():
            raise ValueError("There is no such organisation.")
        if name in set(taken) or db.execute("SELECT 1 FROM sites WHERE name = ?",
                                            (name,)).fetchone() \
                or db.execute("SELECT 1 FROM site_config WHERE name = ?", (name,)).fetchone():
            raise ValueError(f"{name} is already a site of this install.")
        refuse_reserved(db, name, allow_reuse)
        db.execute("INSERT INTO site_config (name, org_id, hosts, views, timezone, log_dir, "
                   "log_base, format, created_by, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                   (name, org_id, json.dumps(hosts), json.dumps(views) if views else None,
                    timezone, str(log_dir) if log_dir else None, log_base or "access.log",
                    fmt, str(actor), base.now()))
        db.execute("INSERT INTO sites (name, org_id) VALUES (?, ?)", (name, org_id))
        auditlog.record(db, org_id, actor, "site.add", name, f"format {fmt}")
    return get(db, name)


def remove(db, org_id, name, actor) -> dict:
    """Stop processing a dashboard site of `org_id`; its data stays."""
    ensure(db)
    with base.tx(db):
        got = get(db, name)
        if got is None or got["org_id"] != org_id:
            raise ValueError("There is no such site made from the dashboard here.")
        if got["removed_at"]:
            raise ValueError(f"{name} is already removed.")
        db.execute("UPDATE site_config SET removed_at = ?, removed_by = ? WHERE name = ?",
                   (base.now(), str(actor), got["name"]))
        auditlog.record(db, org_id, actor, "site.remove", got["name"],
                        "processing stopped; data kept until purged")
    return get(db, name)


def set_hosts(db, name, hosts, actor) -> dict:
    """Replace an active dashboard site's host names (checked like Settings'
    Host names, settings_store "sites.hosts"); one audit row, old -> new."""
    from ..settings_store import validate
    ensure(db)
    hosts = validate("sites.hosts", hosts)
    with base.tx(db):
        got = get(db, name)
        if got is None:
            raise ValueError(f"{name} is not a site made from the dashboard.")
        if got["removed_at"]:
            raise ValueError(f"{name} is removed.")
        db.execute("UPDATE site_config SET hosts = ? WHERE name = ?",
                   (json.dumps(hosts), got["name"]))
        if got["hosts"] != hosts:
            auditlog.record(db, got["org_id"], actor, "site.hosts", got["name"],
                            f"{' '.join(got['hosts'])} -> {' '.join(hosts)}")
    return get(db, name)


def set_format(db, name, fmt, actor) -> dict:
    """Change an active dashboard site's log format; one audit row."""
    ensure(db)
    fmt = str(fmt or "").strip()
    if fmt not in FORMATS:
        raise ValueError(f"A log format is one of: {', '.join(FORMATS)}.")
    with base.tx(db):
        got = get(db, name)
        if got is None or got["removed_at"]:
            raise ValueError(f"{name} is not an active site made from the dashboard.")
        if got["format"] != fmt:
            db.execute("UPDATE site_config SET format = ? WHERE name = ?", (fmt, got["name"]))
            auditlog.record(db, got["org_id"], actor, "site.format", got["name"],
                            f"{got['format']} -> {fmt}")
    return get(db, name)


def restore(db, org_id, name, actor) -> dict:
    """Undo `remove`: the site is processed again (its data was kept)."""
    ensure(db)
    with base.tx(db):
        got = get(db, name)
        if got is None or got["org_id"] != org_id:
            raise ValueError("There is no such site made from the dashboard here.")
        if not got["removed_at"]:
            raise ValueError(f"{name} is not removed.")
        db.execute("UPDATE site_config SET removed_at = NULL, removed_by = NULL WHERE name = ?",
                   (got["name"],))
        auditlog.record(db, org_id, actor, "site.restore", got["name"],
                        "processing starts again")
    return get(db, name)


def revoke_tokens(db, org_id, name) -> int:
    """Tokens that read only this site are revoked; a token for several sites
    loses this one. How many were revoked."""
    revoked = 0
    for tid, sites in db.execute("SELECT id, sites FROM tokens WHERE org_id = ? AND "
                                 "revoked_at IS NULL", (org_id,)).fetchall():
        listed = json.loads(sites) if sites else None
        if not listed or name not in listed:
            continue
        if listed == [name]:
            db.execute("UPDATE tokens SET revoked_at = ? WHERE id = ?", (base.now(), tid))
            revoked += 1
        else:
            db.execute("UPDATE tokens SET sites = ? WHERE id = ?",
                       (json.dumps([s for s in listed if s != name]), tid))
    return revoked


def purge(db, name, actor, detail: str = "", allow_active: bool = False) -> dict:
    """Forget a dashboard site in accounts.sqlite: its row, its organisation
    link, its settings rows; tokens that read only it are revoked (a token for
    several sites loses it). The history and files are the caller's
    (site_data.py, through site_lifecycle.py). `allow_active`: an owner's
    "Delete all data" and `skald site purge` take an active site too, with
    one audit row."""
    ensure(db)
    with base.tx(db):
        got = get(db, name)
        if got is None:
            raise ValueError(f"{name} is not a site made from the dashboard.")
        if got["active"] and not allow_active:
            raise ValueError(f"{name} is still active: remove it in Settings > Sites first.")
        revoked = revoke_tokens(db, got["org_id"], got["name"])
        db.execute("DELETE FROM settings WHERE scope = ?", (f"site:{got['name']}",))
        from . import site_setup
        site_setup.forget(db, got["name"])
        db.execute("DELETE FROM sites WHERE name = ?", (got["name"],))
        db.execute("DELETE FROM site_config WHERE name = ?", (got["name"],))
        auditlog.record(db, got["org_id"], actor, "site.purge", got["name"],
                        f"{detail + '; ' if detail else ''}{revoked} tokens revoked")
    return {**got, "tokens_revoked": revoked}


def as_config(entry: dict, log_dir_default=None) -> dict:
    """The config sections a dashboard site lays over the install's
    (multisite.merged), as a `sites:` file would."""
    over = {"site": {"name": entry["name"], "hosts": list(entry["hosts"] or [entry["name"]])},
            "logs": {"dir": entry.get("log_dir") or (str(log_dir_default)
                                                     if log_dir_default else None),
                     "base": entry.get("log_base") or "access.log",
                     "format": entry.get("format") or "auto"}}
    if not over["logs"]["dir"]:
        over["logs"].pop("dir")
    if entry.get("timezone"):
        over["report"] = {"timezone": entry["timezone"]}
    if entry.get("views"):
        over["dashboard"] = {"views": list(entry["views"])}
    over["_dashboard_site"] = True
    return over
