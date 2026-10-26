"""`skald site add | list | hosts | pause | resume | remove | restore | clear | purge |
verify`: the sites of an accounts install.

    skald site list                         every site: config file or dashboard,
                                            active, paused or removed, its organisation
    skald site add HOST --org SLUG [--format F] [--timezone Z]
                                            what Settings > Sites does, for an
                                            install admin at the shell (no token:
                                            make one with `skald token create
                                            --scope ingest --site HOST`); a name
                                            purged in the last 30 days needs
                                            --allow-reuse
    skald site hosts NAME HOST [HOST ...]   replace a dashboard site's host names
                                            (checked like Settings > Site details > Host
                                            names; an audit row). A Host names row
                                            saved in Settings is set to the same list
    skald site pause NAME                   stop collecting and counting (any site):
                                            ingest answers 503 so the shipper keeps
                                            its lines; live and run-daily skip it
    skald site resume NAME                  start again, and say whether the paused
                                            days can be filled from the log
    skald site remove NAME --yes            stop processing and hide the site; its
                                            data stays (`site restore` undoes it)
    skald site restore NAME                 a removed site is processed again
    skald site clear NAME --yes             archive, then delete the site's collected
                                            data (history, shipped log, leads and
                                            conversions); settings and tokens stay;
                                            the days before read Not recorded
    skald site purge NAME --yes             "Delete all data": archive, then delete
                                            every store of the site (site_data.py),
                                            revoke its tokens. A dashboard site is
                                            gone and its name held for 30 days; a
                                            config-file site keeps its config entry
                                            and becomes removed, with no data
    skald site verify NAME                  mark a site waiting for domain
                                            verification as verified (site_verify.py)

The actions are site_lifecycle.py's, the same as Settings > Sites. The archive
of `clear` and `purge` goes to the backups folder and is kept 30 days. The
install's main site (the config file's own) can only be paused here.
`site assign` stays in cli_accounts.py.
"""
from __future__ import annotations

from pathlib import Path

from .config import site_name

ACTOR = "cli"


def add_site_actions(acts) -> None:
    """Add list, add, hosts, the lifecycle actions and verify under `skald site`
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
    for act, words, yes in (
            ("pause", "stop collecting and counting a site; everything is kept", None),
            ("resume", "start collecting a paused site again", None),
            ("remove", "stop processing a site and hide it; its data stays",
             "really remove it"),
            ("restore", "process a removed site again", None),
            ("clear", "archive, then delete a site's collected data; settings and tokens stay",
             "really delete its data; the archive is kept 30 days"),
            ("purge", "archive, then delete all of a site's data and revoke its tokens",
             "really delete; the archive is kept 30 days")):
        q = acts.add_parser(act, help=words)
        q.add_argument("name")
        if yes:
            q.add_argument("--yes", action="store_true", help=yes)
        q.set_defaults(run=_action(act))
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
    from .accounts import orgs, site_configs, site_state
    db = _open(ctx)
    if db is None:
        return 1
    try:
        rows = {r["name"]: r for r in site_configs.listing(db)}
        states = site_state.every(db)
        config_names = [site_name(c) for c in (getattr(ctx, "all_configs", None) or [ctx.config])
                        if not c.get("_dashboard_site")]
        for name in sorted(set(config_names) | set(rows) | set(states)):
            org = orgs.org_of_site(db, name)
            row, st = rows.get(name), states.get(name) or {}
            where = "dashboard" if row and name not in config_names else "config"
            gone = (row or {}).get("removed_at") or st.get("removed_at")
            state = ("removed " + gone if gone else
                     "paused " + st["paused_at"] if st.get("paused_at") else "active")
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
    _logo(ctx, name)
    return 0


def _logo(ctx, name: str) -> None:
    """The new site's logo, asked now (2.25; at most 20 seconds), so the switcher
    shows it before the morning run. A failure is said, never an error."""
    from . import site_logos
    from .settings_store import apply
    base = Path(ctx.db_path).parent
    try:
        cfg = apply(dict(ctx.raw_config), name, base)
    except Exception:                     # noqa: BLE001 - no accounts file: the config alone
        cfg = ctx.config
    got = site_logos.fetch_now(cfg, name, base, _out(ctx))
    if got.get("ok"):
        ctx.out("  logo: found on the site")
    elif got:
        ctx.out(f"  logo: none yet ({got.get('error')}); the site picker asks again in a day")


def _out(ctx):
    """The dashboard's folder, where sites.json is, or None."""
    try:
        from .cli import _path
        return _path(ctx.raw_config, ctx.config_path, "dashboard", "out", None)
    except Exception:                     # noqa: BLE001 - no dashboard folder: no sites.json
        return None


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


# ----------------------------------------------------------------- lifecycle

ASK = {"remove": "this stops processing {name} and hides it (ingest answers 410); its data "
                 "stays. Run again with --yes",
       "clear": "this archives, then deletes every figure, shipped log line and lead of "
                "{name}; its settings and tokens stay. Run again with --yes",
       "purge": "this archives, then deletes every figure, log, lead, setting and token of "
                "{name}. Run again with --yes"}


def _action(act: str):
    def run(ctx) -> int:
        return cmd_action(ctx, act)
    return run


def cmd_action(ctx, act: str) -> int:
    from . import site_lifecycle as life
    db = _open(ctx)
    if db is None:
        return 1
    try:
        try:
            site = life.find(db, ctx.args.name, ctx.raw_config, ctx.config_path)
            if act in ASK and not ctx.args.yes:
                ctx.err(ASK[act].format(name=site["name"]))
                return 2
            got = _run(ctx, db, life, act, site)
        except life.Refused as why:
            ctx.err(str(why))
            return 1
        except ValueError as why:
            ctx.err(str(why))
            return 1
    finally:
        db.close()
    _say(ctx, act, site["name"], got)
    return 0


def _run(ctx, db, life, act: str, site: dict) -> dict:
    if act == "pause":
        return life.pause(db, site, ACTOR)
    if act == "resume":
        from .ingest import site_configs
        own = site_configs(ctx.raw_config, ctx.config_path).get(site["name"]) or ctx.config
        return life.resume(db, site, ACTOR, own)
    if act == "remove":
        return life.remove(db, site, ACTOR)
    if act == "restore":
        return life.restore(db, site, ACTOR)
    from .cli_accounts import _path as accounts_path
    inst = life.install(ctx.config, ctx.config_path, Path(ctx.db_path).parent, _out(ctx))
    got = (life.clear if act == "clear" else life.purge)(db, accounts_path(ctx), inst, site,
                                                         ACTOR)
    out = _out(ctx)
    if act == "clear" and out is not None:
        # Its pages again now, from no data: a paused site's live run would not draw them.
        from . import first_page
        first_page.placeholder(out, site["name"])
        got["drawn"] = first_page.build(ctx.config_path, site["name"], out)
    return got


def _say(ctx, act: str, name: str, got: dict) -> None:
    if act == "pause":
        ctx.out(f"{name} paused at {got['paused_at']}: nothing is collected or counted until "
                f"`site resume {name}`; history, settings and tokens are kept")
    elif act == "resume":
        ctx.out(f"{name} resumed. {got['words']}")
    elif act == "remove":
        ctx.out(f"{name} removed at {got['removed_at']}: processing stopped, data kept; "
                f"`site restore {name}` undoes it")
    elif act == "restore":
        ctx.out(f"{name} restored: it is {got['status']} again")
    else:
        gone = got["deleted"]
        ctx.out(f"{name}: archive written to {got['archive']} (kept 30 days)")
        ctx.out(f"  deleted: {gone['rows']} database rows, {gone['files']} files or folders, "
                f"{gone['spool']} hook spool lines"
                + (f", {gone['secrets']} secrets, {gone['links']} set-up links, "
                   f"{got['tokens_revoked']} tokens revoked" if act == "purge" else ""))
        for line in gone.get("items", []):
            ctx.out(f"    {line}")
        if act == "clear":
            ctx.out("  settings and tokens kept; the days before today read Not recorded; "
                    + ("its pages are drawn again" if got.get("drawn") else
                       "the next dashboard run draws its pages again"))
        elif got.get("status") == "deleted":
            ctx.out(f"  the site is gone; its name is held until {got['name_held_until'][:10]}")
        else:
            ctx.out("  its config entry stays; the site is removed, with no data "
                    f"(`site restore {name}` collects it again from today)")


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
