"""Organisation management from the command line (accounts mode), the same
actions as Settings > Organisations (orgs_api.py):

    skald org show SLUG                       its sites, members, plan, privacy, state
    skald org archive SLUG | restore SLUG     pause (resume) its sites; nothing deleted
    skald org privacy SLUG internal|client    the organisation rule (keep_everything.py)
    skald org transfer SLUG EMAIL [--from EMAIL]
                                              EMAIL becomes an owner, the former owner
                                              (--from, or the only owner) an admin
    skald member sites EMAIL [SITE ...] [--all] [--org SLUG]
                                              which sites a member sees (none named:
                                              show them; --all: every site)

Every change is audited with the actor "cli". Exit codes as cli_accounts.py:
0 done, 1 refused or failed, 2 a usage mistake.
"""
from __future__ import annotations

from . import accounts
from .accounts import org_admin, orgs, users
from .cli_accounts import ACTOR, _find_org, _need_user, _pick_org, _plural, _with_db


def _org(ctx, db, slug):
    org = _find_org(db, slug)
    if org is None:
        ctx.err(f"no organisation {slug!r}: see `skald org list`")
    return org


@_with_db
def cmd_org_show(ctx, db) -> int:
    org = _org(ctx, db, ctx.args.slug)
    if org is None:
        return 1
    card = org_admin.card(db, org)
    from .keep_everything import install_on
    keeps = install_on(ctx.config)
    rule = ("client: its sites follow their own retention settings"
            if card["privacy_class"] == "client" else
            "internal: " + ("the install keeps everything" if keeps
                            else "the install's retention settings apply"))
    ctx.out(f"{org['name']} ({org['slug']}), id {org['id']}")
    ctx.out(f"  state: {card['state']}"
            f"{' since ' + card['archived_at'] if card['archived_at'] else ''}")
    ctx.out(f"  created: {card['created_at']}")
    ctx.out(f"  plan: {card['plan'] or 'internal'}")
    ctx.out(f"  privacy class: {rule}")
    ctx.out(f"  sites: {', '.join(card['sites']) or 'none'}")
    ctx.out(f"  {_plural(card['members'], 'member')}:")
    for m in accounts.members(db, org["id"]):
        seen = ", ".join(m["sites"]) if m["sites"] is not None else "every site"
        ctx.out(f"    {m['email']:<32} {m['role']:<7} sees {seen}")
    return 0


@_with_db
def cmd_org_archive(ctx, db) -> int:
    org = _org(ctx, db, ctx.args.slug)
    if org is None:
        return 1
    if ctx.args.action == "archive":
        paused = orgs.archive_org(db, org["id"], ACTOR)
        ctx.out(f"archived {org['name']}: {_plural(len(paused), 'site')} paused "
                f"({', '.join(paused) or 'none'}); nothing is deleted. "
                f"`skald org restore {org['slug']}` undoes it")
        return 0
    resumed = orgs.restore_org(db, org["id"], ACTOR)
    ctx.out(f"restored {org['name']}: {_plural(len(resumed), 'site')} collect again "
            f"({', '.join(resumed) or 'none'})")
    return 0


@_with_db
def cmd_org_privacy(ctx, db) -> int:
    org = _org(ctx, db, ctx.args.slug)
    if org is None:
        return 1
    cls = orgs.set_privacy_class(db, org["id"], ctx.args.privacy_class, ACTOR)
    ctx.out(f"{org['name']} is now {cls}: " + (
        "its sites follow their own retention settings, even if the install keeps everything"
        if cls == "client" else "its sites follow the install's keep-everything rule"))
    return 0


@_with_db
def cmd_org_transfer(ctx, db) -> int:
    org = _org(ctx, db, ctx.args.slug)
    if org is None:
        return 1
    to = _need_user(db, ctx.args.email)
    if ctx.args.from_email:
        old = _need_user(db, ctx.args.from_email)
    else:
        owners = [m for m in users.owners(db, org["id"]) if m["id"] != to["id"]]
        if len(owners) != 1:
            ctx.err("name the owner who hands it on with --from EMAIL "
                    f"({len(owners)} other owners)")
            return 2
        old = owners[0]
    org_admin.transfer_owner(db, org["id"], old["id"], to["id"], ACTOR)
    ctx.out(f"{to['email']} is now an owner of {org['slug']}; {old['email']} is an admin")
    return 0


@_with_db
def cmd_member_sites(ctx, db) -> int:
    a = ctx.args
    org, code = _pick_org(ctx, db)
    if org is None:
        return code
    user = _need_user(db, a.email)
    if a.all and a.sites:
        ctx.err("name sites or --all, not both")
        return 2
    if a.all or a.sites:
        got = users.set_site_access(db, org["id"], user["id"], None if a.all else a.sites,
                                    ACTOR)
        ctx.out(f"{user['email']} now sees {', '.join(got) if got else 'every site'} "
                f"of {org['slug']}")
        return 0
    if users.role_in(db, user["id"], org["id"]) is None:
        ctx.err(f"{user['email']} is not a member of {org['slug']}")
        return 1
    limit = users.site_access(db, org["id"], user["id"])
    ctx.out(f"{user['email']} sees {', '.join(limit) if limit is not None else 'every site'} "
            f"of {org['slug']}")
    return 0


def add_org_actions(acts) -> None:
    """`org show|archive|restore|privacy|transfer` (cli_accounts.add_command)."""
    q = acts.add_parser("show", help="sites, members, plan, privacy class and state")
    q.add_argument("slug", help="the organisation (its slug or name: `skald org list`)")
    q.set_defaults(run=cmd_org_show)
    for action, words in (("archive", "pause every site of it; nothing is deleted"),
                          ("restore", "the sites the archive paused collect again")):
        q = acts.add_parser(action, help=words)
        q.add_argument("slug", help="the organisation (its slug or name: `skald org list`)")
        q.set_defaults(run=cmd_org_archive)
    q = acts.add_parser("privacy", help="internal (the install's keep-everything rule) or "
                        "client (its sites follow their own retention)")
    q.add_argument("slug", help="the organisation (its slug or name: `skald org list`)")
    q.add_argument("privacy_class", choices=orgs.PRIVACY_CLASSES,
                   help="internal or client")
    q.set_defaults(run=cmd_org_privacy)
    q = acts.add_parser("transfer", help="hand the ownership on: EMAIL becomes an owner, "
                        "the former owner an admin")
    q.add_argument("slug", help="the organisation (its slug or name: `skald org list`)")
    q.add_argument("email", help="the member who becomes an owner")
    q.add_argument("--from", dest="from_email", metavar="EMAIL",
                   help="the owner who hands it on (needed when there are several)")
    q.set_defaults(run=cmd_org_transfer)


def add_member_actions(acts) -> None:
    """`member sites` (cli_accounts.add_command)."""
    q = acts.add_parser("sites", help="which sites a member sees: name them, --all, or none "
                        "to show")
    q.add_argument("email", help="the member")
    q.add_argument("sites", nargs="*", metavar="SITE",
                   help="the sites they may see (none: show what they see now)")
    q.add_argument("--all", action="store_true", help="every site of the organisation")
    q.add_argument("--org", metavar="SLUG", help="needed when there are several")
    q.set_defaults(run=cmd_member_sites)
