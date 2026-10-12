"""`skald site add | list | purge | verify`: dashboard sites on the server (accounts mode).

    skald site list                         every site: config file or dashboard,
                                            active or removed, its organisation
    skald site add HOST --org SLUG [--format F] [--timezone Z]
                                            what Settings > Sites does, for an
                                            install admin at the shell (no token:
                                            make one with `skald token create
                                            --scope ingest --site HOST`); a name
                                            purged in the last 30 days needs
                                            --allow-reuse
    skald site purge NAME --yes             delete a REMOVED dashboard site for good:
                                            its history rows, dashboard folder,
                                            state folder, ingest logs, its settings
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
    """Add list, add and purge under `skald site` (cli_accounts.add_command)."""
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
    q = acts.add_parser("purge", help="delete a removed dashboard site and all its data")
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
        folders = [state_dir(Path(ctx.db_path).parent, name),
                   _ingest_root(ctx) / slug(name)]
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
