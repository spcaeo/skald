"""Accounts from the command line: for servers without a browser.

    skald accounts init --org NAME --owner-email EMAIL [--owner-name NAME]
                        [--map NAME=EMAIL ...] [--base-url URL] [--force]
    skald accounts status
    skald org list | create NAME | rename SLUG NAME
    skald org show | archive | restore SLUG; org privacy SLUG internal|client;
         org transfer SLUG EMAIL [--from EMAIL]                  (cli_orgs.py)
    skald member list | invite EMAIL --role R | role EMAIL R | remove EMAIL   [--org SLUG]
    skald member sites EMAIL [SITE ...] [--all] [--org SLUG]     (cli_orgs.py)
    skald account reset-link | disable | enable | totp-off EMAIL
    skald account install-admin EMAIL on|off
    skald site assign SITE --org SLUG
    skald token create NAME [--scope read|read_private|mcp|ingest|setup ...] [--site S]
                           [--org SLUG]

`account` (one person's sign-in) is singular on purpose: `skald user` is
already the htpasswd command of `access.mode: basic` (access.py) and stays
as it is. `skald token` acts on the accounts file when `access.mode` is
`sessions` (cmd_token_sessions, called from tokens.py).

`accounts init` is the move from basic mode (docs/plans/
2026-10-11-platform-design.md §2): it makes the accounts file, the
organisation and its owner (an install admin), gives the organisation every
site of this install, turns each users.json name into a pending invite (it
asks for the email, or takes --map; a name without one is skipped and
named), moves tokens.json in with the hashes as they are, and prints the
owner's "set your password" link and every invite link. Nothing changes for
visitors until access.mode is `sessions` and nginx is switched. Run twice it
refuses; --force only adds what is missing and never removes or moves.

An invite link that is printed but not mailed is marked handed: the
account made from it must choose a new password at its first sign-in
(accounts/invites.py). `account reset-link` makes a link whenever asked
(resets.issue_for), not limited like the page's "forgot password".

Every change is written by the accounts library, which audits it with the
actor "cli". Exit codes: 0 done, 1 refused or failed, 2 a usage mistake.
"""
from __future__ import annotations

import sys
from pathlib import Path

from . import accounts
from . import tokens as old_tokens
from .access import load_roles, roles_path
from .accounts import apitokens, auditlog, counts, invites, resets, totp
from .accounts import db as base
from .config import site_name

ACTOR = "cli"
NOT_SENT = "invite mail not sent"
NOT_SET_UP = "accounts are not set up here: run `skald accounts init` first"


# ------------------------------------------------------------------ helpers

def _home(ctx) -> Path | None:
    """The history folder (accounts.sqlite, users.json and tokens.json sit
    there), also when ctx is another site's context with its own live_dir."""
    db_path = getattr(ctx, "db_path", None)
    return Path(db_path).parent if db_path is not None else ctx.live_dir


def _path(ctx) -> Path | None:
    return accounts.path_for(ctx.config, _home(ctx))


def _mode(config: dict) -> str:
    return str(((config or {}).get("access") or {}).get("mode") or "basic")


def _sites(ctx) -> list[str]:
    """Every site of this install (multisite.py), first site first."""
    got = []
    for config in getattr(ctx, "all_configs", None) or [ctx.config]:
        name = site_name(config)
        if name not in got:
            got.append(name)
    return got


def _base_url(ctx) -> str | None:
    """--base-url, else the helper's own rule (accounts/links.py)."""
    from .accounts import links
    return links.base_url(ctx.config, override=getattr(ctx.args, "base_url", None))


def _link(base_url: str, kind: str, token: str) -> str:
    from .accounts import links
    return links.link(base_url, kind, token)


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def _interactive() -> bool:
    try:
        return sys.stdin.isatty()
    except (AttributeError, ValueError):
        return False


def _open(ctx):
    path = _path(ctx)
    if path is None or not Path(path).exists():
        ctx.err(NOT_SET_UP)
        return None
    return accounts.connect(path)


def _with_db(fn):
    """Run fn(ctx, db) on an open accounts file; a ValueError is a refusal."""
    def run(ctx) -> int:
        db = _open(ctx)
        if db is None:
            return 1
        try:
            return fn(ctx, db)
        except ValueError as why:
            ctx.err(str(why))
            return 1
        finally:
            db.close()
    return run


def _find_org(db, key):
    key = str(key or "").strip().lower()
    for org in accounts.list_orgs(db):
        if key in (org["slug"], org["name"].lower()):
            return org
    return None


def _pick_org(ctx, db) -> tuple[dict | None, int]:
    """(org, 0) for --org, or the only one; (None, exit code) otherwise."""
    slug = getattr(ctx.args, "org", None)
    if slug:
        org = _find_org(db, slug)
        if org is None:
            ctx.err(f"no organisation {slug!r}: see `skald org list`")
            return None, 1
        return org, 0
    orgs = accounts.list_orgs(db)
    if len(orgs) == 1:
        return orgs[0], 0
    if not orgs:
        ctx.err("there is no organisation yet: `skald org create NAME`")
        return None, 1
    ctx.err("there are several organisations: name one with --org SLUG "
            f"({', '.join(o['slug'] for o in orgs)})")
    return None, 2


def _need_user(db, email) -> dict:
    user = accounts.find_user(db, email=email)
    if user is None:
        raise ValueError(f"no account for {email}")
    return user


def _mail_invite(ctx, org: dict, email: str, role: str, link: str) -> str | None:
    """Send the invite mail when accounts/mails.py exists and mail is set
    up; the words to print, or None when no mail goes out."""
    try:
        from .accounts import mails
    except ImportError:
        return None
    if not mails.configured(ctx.config):
        return None
    try:
        msg = mails.invite_mail(ctx.config, email, link, org["name"], role)
        mails.deliver(msg, ctx.config, email)
    except Exception as why:            # the link is printed anyway
        return f"{NOT_SENT} ({type(why).__name__}); give them the link"
    return f"invite mail sent to {email}"


def _mailed(said: str | None) -> bool:
    """Whether _mail_invite's words say the mail went out."""
    return bool(said) and not said.startswith(NOT_SENT)


# ------------------------------------------------------------- accounts init

def _parse_map(pairs) -> dict[str, str]:
    got = {}
    for pair in pairs or ():
        name, sep, email = str(pair).partition("=")
        if not sep or not name.strip() or not email.strip():
            raise ValueError(f"--map takes NAME=EMAIL, not {pair!r}")
        got[name.strip()] = accounts.clean_email(email)
    return got


def _emails_for(ctx, roles: dict, given: dict[str, str]) -> dict[str, str]:
    """users.json name -> email: --map first, then asked on a terminal."""
    got = {n: given[n] for n in roles if n in given}
    for name in sorted(roles):
        if name in got or not _interactive():
            continue
        role = (roles[name] or {}).get("role", "viewer")
        while True:
            answer = input(f"email for {name} ({role}), empty to skip: ").strip()
            if not answer:
                break
            try:
                got[name] = accounts.clean_email(answer)
                break
            except ValueError as why:
                print(why)
    return got


def cmd_accounts_init(ctx) -> int:
    a = ctx.args
    try:
        given = _parse_map(a.map)
        owner_email = accounts.clean_email(a.owner_email)
    except ValueError as why:
        ctx.err(str(why))
        return 2
    base_url = _base_url(ctx)
    if base_url is None:
        ctx.err("the links need the dashboard's address: set access.base_url in the "
                "config or pass --base-url https://your.host")
        return 2
    path = _path(ctx)
    if path is None:
        ctx.err("no history folder: set history.db or access.accounts")
        return 2
    db = accounts.connect(path)
    try:
        if accounts.list_orgs(db) and not a.force:
            ctx.err(f"accounts are already set up in {path}. `skald accounts status` shows "
                    "them; --force adds only what is missing")
            return 1
        roles = load_roles(roles_path(ctx.config, _home(ctx))) or {}
        unknown = sorted(set(given) - set(roles))
        emails = _emails_for(ctx, roles, given)
        try:
            lines = _init(ctx, db, path, base_url, owner_email, roles, emails)
        except ValueError as why:
            ctx.err(f"nothing was changed: {why}")
            return 1
    finally:
        db.close()
    for name in unknown:
        lines.append(f"note: --map {name}=... ignored: {name} is not in users.json")
    for line in lines:
        ctx.out(line)
    return 0


def _init(ctx, db, path, base_url, owner_email, roles, emails) -> list[str]:
    """Everything init writes, in one transaction; the lines to print."""
    a = ctx.args
    out = [f"accounts file: {path}"]
    links, made = [], []
    with base.tx(db):
        org = _find_org(db, a.org) if a.force else None
        if org is None:
            org = accounts.create_org(db, a.org, ACTOR)
            out.append(f"organisation: {org['name']} ({org['slug']}) created")
        else:
            out.append(f"organisation: {org['name']} ({org['slug']}) already there")

        owner = accounts.find_user(db, email=owner_email)
        if owner is None:
            name = a.owner_name or owner_email.split("@", 1)[0]
            owner = accounts.create_user(db, owner_email, name, install_admin=True,
                                         actor=ACTOR)
            out.append(f"owner: {owner_email} (install admin) created")
        elif not owner["install_admin"]:
            out.append(f"note: {owner_email} already has an account that is not an install "
                       "admin; it is left as it is")
        if accounts.role_in(db, owner["id"], org["id"]) is None:
            accounts.add_member(db, org["id"], owner["id"], "owner", ACTOR)
        elif accounts.role_in(db, owner["id"], org["id"]) != "owner":
            out.append(f"note: {owner_email} is a member but not an owner; left as it is")

        assigned = []
        for site in _sites(ctx):
            now_in = accounts.org_of_site(db, site)
            if now_in is None:
                accounts.assign_site(db, site, org["id"], ACTOR)
                assigned.append(site)
            elif now_in["id"] != org["id"]:
                out.append(f"note: {site} belongs to {now_in['slug']}; left there")
        out.append(f"sites given to {org['slug']}: {', '.join(assigned) or 'none new'}")

        waiting = {i["email"] for i in accounts.pending(db, org["id"])}
        skipped = []
        for name in sorted(roles):
            role = (roles[name] or {}).get("role")
            role = role if role in ("admin", "viewer") else "viewer"
            email = emails.get(name)
            if not email:
                skipped.append((name, role))
                continue
            if email == owner_email:
                out.append(f"{name}: {email} is the owner; no invite")
                continue
            user = accounts.find_user(db, email=email)
            if user and accounts.role_in(db, user["id"], org["id"]):
                out.append(f"{name}: {email} is already a member")
                continue
            if email in waiting:
                out.append(f"{name}: {email} is already invited "
                           "(`skald member invite` sends a new link)")
                continue
            token = accounts.invite(db, org["id"], email, role, ACTOR)
            made.append((name, email, role, token, _link(base_url, "invite", token)))

        tokens_file = old_tokens.path_for(ctx.config, _home(ctx))
        in_file = len(old_tokens.load(tokens_file))
        moved = apitokens.import_json(db, tokens_file, org["id"], actor=ACTOR) if in_file else 0
        out.append(f"API tokens: {moved} of {in_file} in tokens.json moved in "
                   "(they keep working; tokens.json is left for basic mode)")

        owner = accounts.find_user(db, user_id=owner["id"])
        if not owner["has_password"]:
            links.append(_link(base_url, "reset", resets.issue_for(db, owner["id"], ACTOR)))
        auditlog.record(db, org["id"], ACTOR, "accounts.init", org["slug"],
                        f"{len(assigned)} sites, {len(made)} invites, {moved} tokens")

    for name, email, role, token, link in made:
        out.append(f"invite {name} -> {email} ({role}), valid {accounts.INVITE_DAYS} days:")
        out.append(f"  {link}")
        said = _mail_invite(ctx, org, email, role, link)
        if said:
            out.append(f"  {said}")
        if not _mailed(said):
            invites.mark_handed(db, token)
    for name, role in skipped:
        out.append(f"skipped {name} ({role}): no email. Later: "
                   f"skald member invite EMAIL --role {role}")
    if links:
        out.append(f"owner {owner_email}: set your password (valid "
                   f"{accounts.RESET_MINUTES} minutes, once):")
        out.append(f"  {links[0]}")
    else:
        out.append(f"owner {owner_email} already has a password")
    if _mode(ctx.config) != "sessions":
        out.append("nothing changes for visitors until access.mode is sessions and nginx "
                   "is switched (DEPLOY.md)")
    return out


# ----------------------------------------------------------- accounts status

def cmd_accounts_status(ctx) -> int:
    path = _path(ctx)
    ctx.out(f"mode: {_mode(ctx.config)}")
    if path is None or not Path(path).exists():
        ctx.out(f"accounts: not set up ({path or 'no history folder'}); "
                "`skald accounts init` sets them up")
        return 0
    db = accounts.connect(path)
    try:
        ctx.out(f"accounts file: {path}")
        ctx.out(f"schema version: {base.schema_version(db)}")
        n = counts.install(db)
        ctx.out(f"people: {n['people']} ({n['disabled']} disabled, {n['no_password']} without "
                f"a password yet, {n['must_reset']} must choose a new one, "
                f"{n['totp_on']} with two-step sign-in)")
        ctx.out(f"install admins: {n['install_admins']}")
        ctx.out(f"sessions: {n['sessions']}")
        ctx.out(f"organisations: {n['orgs']}")
        for org in accounts.list_orgs(db):
            o = counts.org(db, org["id"])
            expired = f" (+{o['expired_invites']} expired)" if o["expired_invites"] else ""
            ctx.out(f"  {org['name']} ({org['slug']}): {_plural(o['members'], 'member')} "
                    f"(owners {o['owners']}, admins {o['admins']}, viewers {o['viewers']}), "
                    f"{_plural(o['invites'], 'pending invite')}"
                    f"{expired}, "
                    f"{_plural(o['tokens'], 'token')} ({o['revoked']} revoked), "
                    f"sites: {', '.join(o['sites']) or 'none'}")
        loose = [s for s in _sites(ctx) if accounts.org_of_site(db, s) is None]
        if loose:
            ctx.out(f"sites with no organisation (nobody can see them in sessions mode): "
                    f"{', '.join(loose)}")
    finally:
        db.close()
    return 0


# ----------------------------------------------------------------------- org

@_with_db
def cmd_org(ctx, db) -> int:
    a = ctx.args
    if a.action == "list":
        orgs = accounts.list_orgs(db)
        for org in orgs:
            sites = accounts.sites_of_org(db, org["id"])
            ctx.out(f"{org['slug']:<24} {org['name']:<24} "
                    f"{_plural(len(accounts.members(db, org['id'])), 'member')}  "
                    f"sites: {', '.join(sites) or 'none'}")
        if not orgs:
            ctx.out("no organisations")
        return 0
    if a.action == "create":
        org = accounts.create_org(db, a.name, ACTOR)
        ctx.out(f"created {org['name']} ({org['slug']})")
        return 0
    org = _find_org(db, a.slug)
    if org is None:
        ctx.err(f"no organisation {a.slug!r}")
        return 1
    accounts.rename_org(db, org["id"], a.name, ACTOR)
    ctx.out(f"{org['slug']} is now called {' '.join(a.name.split())}")
    return 0


# -------------------------------------------------------------------- member

def _role_ok(ctx, role) -> bool:
    if role in accounts.ROLES:
        return True
    ctx.err(f"a role is one of: {', '.join(accounts.ROLES)}")
    return False


@_with_db
def cmd_member(ctx, db) -> int:
    a = ctx.args
    if a.action in ("invite", "role") and not _role_ok(ctx, a.role):
        return 2
    org, code = _pick_org(ctx, db)
    if org is None:
        return code
    if a.action == "list":
        ctx.out(f"{org['name']} ({org['slug']})")
        for m in accounts.members(db, org["id"]):
            notes = [n for n, on in (("disabled", m["disabled_at"]),
                                     ("no password yet", not m["has_password"]),
                                     ("two-step on", m["totp_on"])) if on]
            ctx.out(f"  {m['email']:<32} {m['role']:<7} {m['name'] or '-':<20} "
                    f"last seen {m['last_seen'] or 'never'}"
                    f"{'  (' + ', '.join(notes) + ')' if notes else ''}")
        for i in accounts.pending(db, org["id"]):
            state = "expired" if i["expired"] else f"until {i['expires_at']}"
            ctx.out(f"  {i['email']:<32} {i['role']:<7} invited, {state}")
        return 0
    if a.action == "invite":
        base_url = _base_url(ctx)
        if base_url is None:
            ctx.err("the link needs the dashboard's address: set access.base_url or "
                    "pass --base-url https://your.host")
            return 2
        token = accounts.invite(db, org["id"], a.email, a.role, ACTOR)
        email = accounts.clean_email(a.email)
        link = _link(base_url, "invite", token)
        ctx.out(f"invited {email} to {org['slug']} as {a.role}, valid "
                f"{accounts.INVITE_DAYS} days:\n  {link}")
        said = _mail_invite(ctx, org, email, a.role, link)
        if said:
            ctx.out(said)
        if not _mailed(said):
            invites.mark_handed(db, token)
            ctx.out("not mailed: the account made from this link must choose a new password "
                    "at its first sign-in")
        return 0
    if a.action == "role":
        user = _need_user(db, a.email)
        accounts.set_role(db, org["id"], user["id"], a.role, ACTOR)
        ctx.out(f"{user['email']} is now {a.role} in {org['slug']}")
        return 0
    user = accounts.find_user(db, email=a.email)
    if user and accounts.role_in(db, user["id"], org["id"]):
        accounts.remove_member(db, org["id"], user["id"], ACTOR)
        ctx.out(f"removed {user['email']} from {org['slug']} (the account stays)")
        return 0
    if accounts.cancel(db, org["id"], a.email, ACTOR):
        ctx.out(f"cancelled the invite for {accounts.clean_email(a.email)}")
        return 0
    ctx.err(f"{a.email} is neither a member of {org['slug']} nor invited")
    return 1


# ------------------------------------------------------------------- account

@_with_db
def cmd_account(ctx, db) -> int:
    a = ctx.args
    user = _need_user(db, a.email)
    if a.action == "reset-link":
        base_url = _base_url(ctx)
        if base_url is None:
            ctx.err("the link needs the dashboard's address: set access.base_url or "
                    "pass --base-url https://your.host")
            return 2
        if user["disabled_at"]:
            ctx.err(f"{user['email']} is disabled: `skald account enable` first")
            return 1
        token = resets.issue_for(db, user["id"], ACTOR)
        ctx.out(f"set-your-password link for {user['email']} (valid "
                f"{accounts.RESET_MINUTES} minutes, once):\n  "
                f"{_link(base_url, 'reset', token)}")
        return 0
    if a.action == "disable":
        accounts.disable_user(db, user["id"], ACTOR)
        ctx.out(f"disabled {user['email']}; their sessions are ended")
        return 0
    if a.action == "enable":
        accounts.enable_user(db, user["id"], ACTOR)
        ctx.out(f"enabled {user['email']}")
        return 0
    if a.action == "install-admin":
        accounts.set_install_admin(db, user["id"], a.flag == "on", ACTOR)
        ctx.out(f"{user['email']} is {'now' if a.flag == 'on' else 'no longer'} an install "
                "admin (server-wide settings: bot policy, funnels, internal addresses)")
        return 0
    totp.disable(db, user["id"], ACTOR)
    ctx.out(f"two-step sign-in is off for {user['email']}; they can turn it on again")
    return 0


# ---------------------------------------------------------------------- site

@_with_db
def cmd_site(ctx, db) -> int:
    a = ctx.args
    sites = _sites(ctx)
    if a.site not in sites:
        ctx.err(f"{a.site!r} is not a site of this install ({', '.join(sites)})")
        return 2
    org = _find_org(db, a.org)
    if org is None:
        ctx.err(f"no organisation {a.org!r}")
        return 1
    accounts.assign_site(db, a.site, org["id"], ACTOR)
    ctx.out(f"{a.site} now belongs to {org['name']} ({org['slug']})")
    return 0


# ------------------------------------------------------ token, sessions mode

@_with_db
def cmd_token_sessions(ctx, db) -> int:
    """`skald token create|list|revoke` on the accounts file (sessions mode)."""
    a = ctx.args
    if a.action == "create":
        if not a.name:
            ctx.err("give the token a name: what uses it")
            return 2
        org, code = _pick_org(ctx, db)
        if org is None:
            return code
        scopes = getattr(a, "scope", None) or ["read"]
        bad = [x for x in scopes if x not in apitokens.SCOPES]
        if bad:
            ctx.err(f"a scope is one of: {', '.join(apitokens.SCOPES)}")
            return 2
        token = apitokens.create(db, org["id"], a.name, sites=a.site or None,
                                 private=a.private, scopes=scopes, actor=ACTOR)
        ctx.out(f"{token}\n(shown once; only its hash is kept. Use it as "
                f"'Authorization: Bearer <token>'.)")
        return 0
    slug = getattr(a, "org", None)
    orgs = [o for o in accounts.list_orgs(db) if not slug or slug in (o["slug"], o["name"])]
    if a.action == "list":
        shown = 0
        for org in orgs:
            for t in apitokens.listing(db, org["id"]):
                state = f"revoked {t['revoked_at']}" if t["revoked_at"] else "active"
                ctx.out(f"{t['id']}  {org['slug']:<16} {t['name']:<24} "
                        f"{', '.join(t['sites'] or ['all sites'])}  {','.join(t['scopes'])}"
                        f"{'  +addresses' if t['private'] else ''}  {state}")
                shown += 1
        if not shown:
            ctx.out("no tokens")
        return 0
    tid = (a.name or "").removeprefix("skald_").split("_", 1)[0]
    for org in orgs:
        for t in apitokens.listing(db, org["id"]):
            if t["id"] == tid:
                apitokens.revoke(db, org["id"], tid, ACTOR)
                ctx.out(f"revoked {tid} ({t['name']})")
                return 0
    ctx.err(f"no token {tid}")
    return 1


# -------------------------------------------------------------------- parser

def add_command(sub) -> None:
    p = sub.add_parser("accounts", help="accounts mode: set up (init) and status")
    acts = p.add_subparsers(dest="action", required=True)
    q = acts.add_parser("init", help="make the accounts file from users.json and tokens.json")
    q.add_argument("--org", required=True, help="the organisation's name")
    q.add_argument("--owner-email", required=True, help="the owner (an install admin)")
    q.add_argument("--owner-name", help="the owner's name (default: from the email)")
    q.add_argument("--map", action="append", metavar="NAME=EMAIL",
                   help="the email of a users.json name (repeatable); others are asked")
    q.add_argument("--base-url", help="https://host of the dashboard, for the links "
                   "(default access.base_url, then dashboard.base_url, then "
                   "dashboard.url)")
    q.add_argument("--force", action="store_true",
                   help="already set up: add only what is missing, never remove")
    q.set_defaults(run=cmd_accounts_init)
    q = acts.add_parser("status", help="mode, organisations, people, invites, tokens")
    q.set_defaults(run=cmd_accounts_status)

    p = sub.add_parser("org", help="organisations (accounts mode)")
    acts = p.add_subparsers(dest="action", required=True)
    acts.add_parser("list").set_defaults(run=cmd_org)
    q = acts.add_parser("create")
    q.add_argument("name")
    q.set_defaults(run=cmd_org)
    q = acts.add_parser("rename")
    q.add_argument("slug")
    q.add_argument("name")
    q.set_defaults(run=cmd_org)
    from .cli_orgs import add_member_actions, add_org_actions   # show, archive, ... (cli_orgs.py)
    add_org_actions(acts)

    p = sub.add_parser("member", help="members and invites of an organisation (accounts mode)")
    acts = p.add_subparsers(dest="action", required=True)
    for action, extra in (("list", ()), ("invite", ("email",)), ("role", ("email", "role")),
                          ("remove", ("email",))):
        q = acts.add_parser(action)
        for name in extra:
            q.add_argument(name)
        if action == "invite":
            q.add_argument("--role", required=True, help="owner, admin or viewer")
            q.add_argument("--base-url", help="https://host of the dashboard, for the link")
        q.add_argument("--org", metavar="SLUG", help="needed when there are several")
        q.set_defaults(run=cmd_member)
    add_member_actions(acts)

    p = sub.add_parser("account", help="one person's sign-in (accounts mode); "
                       "`skald user` is the basic-mode password file")
    acts = p.add_subparsers(dest="action", required=True)
    for action in ("reset-link", "disable", "enable", "totp-off", "install-admin"):
        q = acts.add_parser(action)
        q.add_argument("email")
        if action == "reset-link":
            q.add_argument("--base-url", help="https://host of the dashboard, for the link")
        if action == "install-admin":
            q.add_argument("flag", choices=("on", "off"))
        q.set_defaults(run=cmd_account)

    p = sub.add_parser("site", help="the install's sites (accounts mode): assign, list, add, "
                       "hosts, remove, purge, verify")
    acts = p.add_subparsers(dest="action", required=True)
    q = acts.add_parser("assign")
    q.add_argument("site")
    q.add_argument("--org", required=True, metavar="SLUG")
    q.set_defaults(run=cmd_site)
    from .sites_cli import add_site_actions      # list, add, hosts, remove, purge, verify
    add_site_actions(acts)
