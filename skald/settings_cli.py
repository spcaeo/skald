"""`skald settings`: the dashboard's settings from the shell (accounts mode).

    skald settings list-keys                every key: kind, where it is saved,
                                            who may change it, its default
    skald settings get SITE [KEY]           each value for SITE, and where it
                                            comes from (site, org, install,
                                            config, default); secrets only
                                            "set" or "not set"
    skald settings set SITE KEY VALUE [--yes]
                                            save a row, checked like the page
                                            (settings_store.validate) and saved
                                            where the page saves it
                                            (settings_store.scope_for), with an
                                            audit row by "cli"

VALUE is JSON (`true`, `180`, `'["/wp-content/", "/wp-includes/"]'`,
`null` to clear the row); a word that is not JSON is taken as text
(`anonymous`). conversions.retention_days also takes 0 or `forever`: leads
and the pages they read kept for good. Run at the server, this is an install admin's tool: it may
change any key except a locked one (config.yml `settings.locked`) and the
secrets, which never go through a command line (shell history): set those
on the Settings page or in the environment. A smaller retention window
removes stored data at the next run, so it needs --yes, as the page asks
for the site's name. Mail recipients saved here get no confirm mail and
receive nothing until they confirm (mail_confirm.py): use the page for them.
"""
from __future__ import annotations

import json

from . import settings_store as store

ACTOR = "cli"


def _site_layer(ctx, site: str) -> dict:
    """The config.yml layer of `site` (the page's own, settings_api.site_config)."""
    from .settings_api import site_config
    return site_config(ctx.raw_config, ctx.config_path, site)


def _known(ctx, site: str) -> bool:
    from .cli_accounts import _sites
    if site in _sites(ctx):
        return True
    ctx.err(f"{site!r} is not a site of this install: see `skald site list`")
    return False


def _shown(value) -> str:
    return "(not set)" if value is None else json.dumps(value, separators=(", ", ": "))


def cmd_list_keys(ctx) -> int:
    for name, key in store.SCHEMA.items():
        if key.kind == "secret":
            default = "secret: set on the page or in $" + key.env
        else:
            default = _shown(key.default)
        span = (f" {key.lo}-{key.hi}" if key.lo is not None else "") + \
            (" or 0 (forever)" if key.forever else "")
        choices = f" ({'|'.join(key.choices)})" if key.choices else ""
        ctx.out(f"{name:<28} {key.kind}{span}{choices}  saved for {key.scopes[0]}, "
                f"{key.who}; default {default}  {key.label}")
    return 0


def cmd_get(ctx, db) -> int:
    site, only = ctx.args.site, ctx.args.key
    if not _known(ctx, site):
        return 2
    if only and only not in store.SCHEMA:
        ctx.err(f"{only!r} is not a setting: see `skald settings list-keys`")
        return 2
    config = _site_layer(ctx, site)
    got = store.explain(config, site, db)
    for name in store.SCHEMA:
        if only and name != only:
            continue
        if name in store.SECRETS:
            state = store.secret_state(config, name, ctx.db_path.parent)
            ctx.out(f"{name:<28} {'set' if state['set'] else 'not set'}"
                    f"{' (environment)' if state['env'] else ''}")
            continue
        entry = got[name]
        lock = ", locked" if entry["locked"] else ""
        ctx.out(f"{name:<28} {_shown(entry['value'])}  ({entry['source']}{lock})")
    return 0


def _value(raw: str):
    try:
        return json.loads(raw)
    except ValueError:
        return raw


def cmd_set(ctx, db) -> int:
    a = ctx.args
    site, name = a.site, a.key
    if not _known(ctx, site):
        return 2
    key = store.SCHEMA.get(name)
    if key is None:
        ctx.err(f"{name!r} is not a setting: see `skald settings list-keys`")
        return 2
    if key.kind == "secret":
        ctx.err(f"{name} is a secret: set it on the Settings page or in the environment "
                f"(${store.secret_name(ctx.config, name)}), never on a command line")
        return 2
    config = _site_layer(ctx, site)
    if name in store.locked(config):
        ctx.err(f"{name}: {store.LOCK_WORDS}")
        return 1
    value = store.validate(name, _value(a.value))
    org = db.execute("SELECT org_id FROM sites WHERE name = ?", (site,)).fetchone()
    if key.scopes[0] in ("site", "org") and org is None:
        ctx.err(f"{site} has no organisation: `skald site assign {site} --org SLUG` first")
        return 1
    scope = store.scope_for(name, site, org[0] if org else None)
    old = store.explain(config, site, db)[name]["value"]
    if key.shrink and store.keeps_less(name, old, value) and not a.yes:
        ctx.err(f"{name} {old} -> {value} removes stored data at the next run; it cannot be "
                "brought back except from a backup. Run again with --yes")
        return 2
    got = store.put(db, scope, name, value, ACTOR)
    ctx.out(f"{name} for {scope}: {_shown(got['old'])} -> {_shown(got['new'])}")
    now = store.explain(config, site, db)[name]
    if value is None:
        ctx.out(f"  now {_shown(now['value'])} ({now['source']})")
    if key.forever and value == 0:
        ctx.out("  0: kept for good; Skald never deletes them (`conversions forget` still "
                "does, for one person)")
    if name == "mail.to":
        ctx.out("  recipients saved here get no confirm mail and receive nothing until they "
                "confirm: add them on the Settings > Mail page instead")
    if name in ("site.asset_prefixes", "site.require_rendering", "sites.hosts"):
        ctx.out("  from the next run; recount stored days with `backfill --days N --force`")
    return 0


def _with_db(fn):
    def run(ctx) -> int:
        from .cli_accounts import _open
        db = _open(ctx)
        if db is None:
            return 1
        try:
            return fn(ctx, db)
        except store.Invalid as why:
            ctx.err(str(why))
            return 1
        finally:
            db.close()
    return run


def add_command(sub) -> None:
    p = sub.add_parser("settings", help="the dashboard's settings from the shell (accounts "
                       "mode): list-keys, get SITE [KEY], set SITE KEY VALUE")
    acts = p.add_subparsers(dest="action", required=True)
    q = acts.add_parser("list-keys", help="every key: kind, scope, who, default")
    q.set_defaults(run=cmd_list_keys)
    q = acts.add_parser("get", help="a site's values and where each comes from")
    q.add_argument("site")
    q.add_argument("key", nargs="?")
    q.set_defaults(run=_with_db(cmd_get))
    q = acts.add_parser("set", help="save one value (JSON; null clears the row), audited "
                        "as cli")
    q.add_argument("site")
    q.add_argument("key")
    q.add_argument("value", help="JSON: true, 180, '[\"/wp-content/\"]', null; or a word")
    q.add_argument("--yes", action="store_true",
                   help="a smaller retention window: really remove the older data")
    q.set_defaults(run=_with_db(cmd_set))
