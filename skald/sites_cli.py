"""`skald site add | list | hosts | remove | purge | verify`: dashboard sites (accounts mode).

    skald site list                         every site: config file or dashboard,
                                            active or removed, its organisation
    skald site add HOST --org SLUG [--format F] [--timezone Z]
                                            what Settings > Sites does, for an
                                            install admin at the shell (no token:
                                            make one with `skald token create
                                            --scope ingest --site HOST`); a name
                                            purged in the last 30 days needs
                                            --allow-reuse
    skald site hosts NAME HOST [HOST ...]   replace a dashboard site's host names
                                            (checked like Settings > Sites > Host
                                            names; an audit row). A Host names row
                                            saved in Settings is set to the same list
    skald site remove NAME --yes            stop processing a dashboard site (what an
                                            owner's Remove in Settings does); its data
                                            stays until `site purge`
    skald site purge NAME --yes             delete a REMOVED dashboard site for good:
                                            its history rows, dashboard folder,
                                            state folder, logo folder, ingest logs,
                                            its settings
                                            rows and the tokens that read only it,
                                            its conversions.sqlite rows (every table
                                            with a site column, its outbox cursor),
                                            its hook spool lines and its secrets
                                            (hooks/<site>/*, outgoing/<site>/*); the
                                            name is then held for 30 days
    skald site verify NAME                  mark a site waiting for domain
                                            verification as verified (site_verify.py)

`site assign` stays in cli_accounts.py. Purging cannot be undone; take a
backup first (`skald backup`). Only dashboard sites can be purged: a
config-file site is removed by editing the config.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from .config import site_name

ACTOR = "cli"


def add_site_actions(acts) -> None:
    """Add list, add, hosts, remove, purge and verify under `skald site`
    (cli_accounts.add_command)."""
    q = acts.add_parser("list", help="every site, where it is defined, and its organisation")
    q.set_defaults(run=cmd_list)
    q = acts.add_parser("add", help="add a dashboard site to an organisation")
    q.add_argument("host")
    q.add_argument("--org", required=True, metavar="SLUG")
    q.add_argument("--format", default="auto")
    q.add_argument("--timezone")
    q.add_argument("--allow-reuse", action="store_true",
                   help="re-use a name purged in the last 30 days")
    q.set_defaults(run=cmd_add)
    q = acts.add_parser("hosts", help="replace a dashboard site's host names")
    q.add_argument("name")
    q.add_argument("hosts", nargs="+", metavar="HOST")
    q.set_defaults(run=cmd_hosts)
    q = acts.add_parser("remove", help="stop processing a dashboard site; its data stays "
                        "until purge")
    q.add_argument("name")
    q.add_argument("--yes", action="store_true", help="really remove it")
    q.set_defaults(run=cmd_remove)
    q = acts.add_parser("purge", help="delete a removed dashboard site and all its data, "
                        "its logo folder too")
    q.add_argument("name")
    q.add_argument("--yes", action="store_true", help="really delete; nothing is undone")
    q.set_defaults(run=cmd_purge)
    q = acts.add_parser("verify", help="mark a site's domain as verified")
    q.add_argument("name")
    q.set_defaults(run=cmd_verify)


def _open(ctx):
    from .cli_accounts import _open as open_accounts
    return open_accounts(ctx)


def _ingest_root(ctx) -> Path:
    from .ingest_log import root
    return root(ctx.config, Path(ctx.db_path).parent)


def cmd_list(ctx) -> int:
    from .accounts import orgs, site_configs
    db = _open(ctx)
    if db is None:
        return 1
    try:
        rows = {r["name"]: r for r in site_configs.listing(db)}
        config_names = [site_name(c) for c in (getattr(ctx, "all_configs", None) or [ctx.config])
                        if not c.get("_dashboard_site")]
        for name in sorted(set(config_names) | set(rows)):
            org = orgs.org_of_site(db, name)
            row = rows.get(name)
            where = "dashboard" if row and name not in config_names else "config"
            state = "removed " + row["removed_at"] if row and row["removed_at"] else "active"
            ctx.out(f"{name:<32} {where:<9} {state:<28} "
                    f"{org['slug'] if org else '(no organisation)'}")
    finally:
        db.close()
    return 0


def cmd_add(ctx) -> int:
    from .accounts import site_configs
    from .cli_accounts import _find_org, _sites
    from .ingest_log import site_folder
    db = _open(ctx)
    if db is None:
        return 1
    try:
        org = _find_org(db, ctx.args.org)
        if org is None:
            ctx.err(f"no organisation {ctx.args.org!r}")
            return 1
        name = site_configs.clean_name(ctx.args.host)
        folder = site_folder(_ingest_root(ctx), name)
        site_configs.create(db, org["id"], name, ACTOR, timezone=ctx.args.timezone,
                            fmt=ctx.args.format, log_dir=str(folder), taken=_sites(ctx),
                            allow_reuse=ctx.args.allow_reuse)
    except ValueError as why:
        ctx.err(str(why))
        return 1
    finally:
        db.close()
    folder.mkdir(parents=True, exist_ok=True)
    ctx.out(f"{name} added to {org['name']}; its log folder is {folder}")
    return 0


def cmd_hosts(ctx) -> int:
    from . import settings_store
    from .accounts import site_configs
    name = ctx.args.name
    db = _open(ctx)
    if db is None:
        return 1
    try:
        if site_configs.get(db, name) is None:
            ctx.err(f"{name} is not a dashboard site; set a config-file site's hosts in its "
                    f"config, or `settings set {name} sites.hosts '[\"host\", ...]'`")
            return 1
        try:
            row = site_configs.set_hosts(db, name, ctx.args.hosts, ACTOR)
        except ValueError as why:
            ctx.err(str(why))
            return 1
        # A Host names row saved in Settings wins over the site's own list
        # (settings_store.apply): keep it the same, so this list applies.
        scope = f"site:{name}"
        if settings_store.get(db, scope, "sites.hosts") is not None:
            settings_store.put(db, scope, "sites.hosts", row["hosts"], ACTOR)
            ctx.out("the Host names row saved in Settings is set to the same list")
    finally:
        db.close()
    ctx.out(f"{name} hosts: {' '.join(row['hosts'])} (from the next run; the script tag "
            "reads them within a minute)")
    return 0


def cmd_remove(ctx) -> int:
    from .accounts import site_configs
    name = ctx.args.name
    db = _open(ctx)
    if db is None:
        return 1
    try:
        row = site_configs.get(db, name)
        if row is None:
            ctx.err(f"{name} is not a dashboard site; a config-file site is removed by "
                    "editing the config")
            return 1
        if not ctx.args.yes:
            ctx.err(f"this stops processing {name} (ingest answers 410); its data stays "
                    "until `site purge`. Run again with --yes")
            return 2
        try:
            got = site_configs.remove(db, row["org_id"], name, ACTOR)
        except ValueError as why:
            ctx.err(str(why))
            return 1
    finally:
        db.close()
    ctx.out(f"{name} removed at {got['removed_at']}: processing stopped, data kept until "
            f"`site purge {name} --yes`")
    return 0


def _history_tables(history) -> list[str]:
    names = [r[0] for r in history.db.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'")]
    return [n for n in names
            if any(c[1] == "site" for c in history.db.execute(f"PRAGMA table_info({n})"))]


def cmd_purge(ctx) -> int:
    from .accounts import site_configs
    from .files import slug
    from .multisite import state_dir
    from .store import History
    name = ctx.args.name
    db = _open(ctx)
    if db is None:
        return 1
    try:
        row = site_configs.get(db, name)
        if row is None:
            ctx.err(f"{name} is not a dashboard site; a config-file site is removed by "
                    "editing the config")
            return 1
        if row["active"]:
            ctx.err(f"{name} is still active: remove it in Settings > Sites first")
            return 1
        if not ctx.args.yes:
            ctx.err(f"this deletes every figure and log of {name} for good; "
                    "take a backup, then run again with --yes")
            return 2
        history = History(ctx.db_path)
        try:
            removed = 0
            for table in _history_tables(history):
                removed += history.db.execute(f"DELETE FROM {table} WHERE site = ?",
                                              (name,)).rowcount
            history.db.commit()
        finally:
            history.db.close()
        gone = []
        out = getattr(ctx, "out_dir", None) or _dashboard_out(ctx)
        from .site_logos import folder as logo_folder
        folders = [state_dir(Path(ctx.db_path).parent, name),
                   _ingest_root(ctx) / slug(name),
                   logo_folder(Path(ctx.db_path).parent, name)]
        if out is not None:
            folders.append(Path(out) / slug(name))
        for folder in folders:
            if folder.is_dir():
                shutil.rmtree(folder)
                gone.append(str(folder))
        found = _purge_conversions(ctx, name)
        got = site_configs.purge(db, name, ACTOR)
        from .site_verify import forget, reserve
        forget(db, name)
        until = reserve(db, name, ACTOR)
    except ValueError as why:
        ctx.err(str(why))
        return 1
    finally:
        db.close()
    ctx.out(f"{name} purged: {removed} history rows, {found['rows']} conversions rows, "
            f"{found['spool']} spool lines, {found['secrets']} secrets, {len(gone)} folders, "
            f"{got['tokens_revoked']} tokens revoked; the name is held until {until[:10]}")
    for folder in gone:
        ctx.out(f"  deleted {folder}")
    return 0


def _purge_conversions(ctx, name: str) -> dict:
    """conversions.sqlite rows of every table with a site column, the
    site's meta keys, its hook spool lines and its secrets. Counts."""
    from .conversions import secrets_store, spool, store
    folder = Path(ctx.db_path).parent
    out = {"rows": 0, "spool": 0, "secrets": 0}
    path = store.path_for(ctx.config, folder)
    if path is not None and Path(path).exists():
        db = store.connect(path)
        try:
            with store.tx(db):
                tables = [r[0] for r in db.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'")]
                # outbox before webhooks: its rows point at them
                for table in sorted(tables, key=lambda t: t != "outbox"):
                    cols = [c[1] for c in db.execute(f'PRAGMA table_info("{table}")')]
                    if "site" in cols:
                        out["rows"] += db.execute(f'DELETE FROM "{table}" WHERE site = ?',
                                                  (name,)).rowcount
                for (key,) in db.execute("SELECT key FROM meta").fetchall():
                    if key.endswith(":" + name):          # outbox_cursor:<site>, ...
                        db.execute("DELETE FROM meta WHERE key = ?", (key,))
        finally:
            db.close()
    out["spool"] = spool.scrub(spool.spool_dir(ctx.config, folder),
                               lambda row, texts: row.get("site") == name)
    out["secrets"] = secrets_store.delete(
        secrets_store.path_for(ctx.config, folder),
        lambda key: key.split("/")[:2] in (["hooks", name], ["outgoing", name]))
    return out


def cmd_verify(ctx) -> int:
    from . import site_verify
    db = _open(ctx)
    if db is None:
        return 1
    try:
        if site_verify.mark(db, ctx.args.name, ACTOR, "cli"):
            ctx.out(f"{ctx.args.name} is verified; Skald collects for it from now on")
        else:
            ctx.out(f"{ctx.args.name} was not waiting for verification")
    finally:
        db.close()
    return 0


def _dashboard_out(ctx) -> Path | None:
    from .cli import _path
    return _path(ctx.config, ctx.config_path, "dashboard", "out", None)
