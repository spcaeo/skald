"""Plans and usage from the command line (docs/SAAS.md).

    skald plan list                          the plans in the config, then each
                                             organisation's plan and status
    skald plan set ORG PLAN [--status S] [--trial-days N]
                                             PLAN "none" takes the plan away (no limits)
    skald usage [--org SLUG] [--month YYYY-MM]
                                             this month's requests against the limit
    skald billing secret key|webhook         the Stripe secret key or the webhook's
                                             signing secret, read from stdin, into
                                             secrets.json (0600); never printed

Registered through cli_more.MODULES ("saas.cli"). ORG is a slug or a name
(`skald org list`). Changes are audited with the actor "cli". Exit codes: 0
done, 1 refused or failed, 2 a usage mistake.
"""
from __future__ import annotations

import sys

from . import STATUSES, enabled
from . import limits, plans

ACTOR = "cli"
SECRETS = {"key": "billing/stripe_key", "webhook": "billing/stripe_webhook"}


def _limit(value) -> str:
    return "no limit" if value is None else f"{value:,}"


def cmd_plan(ctx) -> int:
    from ..cli_accounts import _with_db
    return _with_db(_plan_list if ctx.args.action == "list" else _plan_set)(ctx)


def _plan_list(ctx, db) -> int:
    try:
        table = plans.plans(ctx.config)
    except ValueError as why:
        ctx.err(str(why))
        return 1
    if not enabled(ctx.config):
        ctx.out("saas is off (saas.enabled, access.mode: sessions): no limit applies")
    default = plans.default_plan(ctx.config)
    if not table:
        ctx.out("no plans in the config (saas.plans)")
    for name, p in table.items():
        ctx.out(f"{name}{' (default)' if name == default else ''}: "
                f"sites {_limit(p['sites'])}, requests a month {_limit(p['requests_month'])}, "
                f"retention {_limit(p['retention_days_max'])} days, "
                f"members {_limit(p['members'])}, trial {p['trial_days']} days, "
                f"{'for sale' if p['price_id'] else 'not for sale'}")
    ctx.out("")
    for org in db.execute("SELECT id, slug FROM orgs ORDER BY id").fetchall():
        state = plans.org_state(db, org[0])
        extra = f", trial ends {state['trial_ends_at']}" if state["trial_ends_at"] else ""
        if state["past_due_since"]:
            extra += f", past due since {state['past_due_since']}"
        why = limits.read_only(db, org[0], ctx.config)
        ctx.out(f"{org[1]}: {state['plan'] or '(no plan: no limits)'} {state['plan_status']}"
                f"{extra}{', READ-ONLY' if why else ''} (made by {state['created_via']})")
    return 0


def _plan_set(ctx, db) -> int:
    from ..accounts import db as base
    from ..cli_accounts import _find_org
    org = _find_org(db, ctx.args.org)
    if org is None:
        ctx.err(f"no organisation {ctx.args.org!r}: see `skald org list`")
        return 1
    name = ctx.args.plan
    clear = name.lower() == "none"
    if not clear and name not in plans.plans(ctx.config):
        ctx.err(f"no plan {name!r} in saas.plans: see `skald plan list`")
        return 1
    status = ctx.args.status or ("none" if clear else "active")
    extra = {}
    if ctx.args.trial_days is not None:
        status = ctx.args.status or "trialing"
        extra["trial_ends_at"] = base.shift(int(ctx.args.trial_days) * 86400)
    got = plans.set_plan(db, org["id"], None if clear else name, status, ACTOR, **extra)
    ctx.out(f"{org['slug']}: {got['plan'] or '(no plan)'} {got['plan_status']}")
    if not enabled(ctx.config):
        ctx.out("note: saas is off here, so the plan has no effect until it is on")
    return 0


def cmd_usage(ctx) -> int:
    from ..cli_accounts import _with_db
    return _with_db(_usage)(ctx)


def _usage(ctx, db) -> int:
    from ..cli_accounts import _find_org
    month = ctx.args.month or limits.month_now()
    if len(month) != 7 or month[4] != "-" or not month.replace("-", "").isdigit():
        ctx.err("--month is YYYY-MM")
        return 2
    if ctx.args.org:
        org = _find_org(db, ctx.args.org)
        if org is None:
            ctx.err(f"no organisation {ctx.args.org!r}: see `skald org list`")
            return 1
        found = [org]
    else:
        found = [dict(r) for r in db.execute("SELECT id, slug FROM orgs ORDER BY id")]
    hist = getattr(ctx, "db_path", None)
    for org in found:
        sites = [r[0] for r in db.execute("SELECT name FROM sites WHERE org_id = ? "
                                          "ORDER BY name", (org["id"],))]
        got = limits.usage(hist, sites, month)
        lim = limits.limits_for(db, org["id"], ctx.config)
        cap = None if lim is None else lim["requests_month"]
        if got["withheld"]:
            used = f"withheld: {got['withheld']}"
        elif got["requests"] is None:
            used = "no day recorded"
        else:
            used = f"{got['requests']:,} requests over {got['days']} days"
        ctx.out(f"{org['slug']} {month}: {used}; limit {_limit(cap)}; "
                f"sites {', '.join(sites) or '(none)'}")
        over = limits.over_limit(db, org["id"], ctx.config, hist, month)
        if over:
            ctx.out(f"  over: {', '.join(over)}")
    return 0


def cmd_billing(ctx) -> int:
    from .. import settings_store
    from ..conversions.secrets_store import put
    path = settings_store.secrets_path(ctx.config, getattr(ctx, "live_dir", None))
    if path is None:
        ctx.err("the history's folder is not known, so there is no secrets.json")
        return 1
    value = (sys.stdin.readline() if not sys.stdin.isatty() else
             __import__("getpass").getpass("Paste the secret (not shown): ")).strip()
    if not value or "\n" in value or len(value) > 500:
        ctx.err("give the secret on one line (stdin)")
        return 2
    put(path, SECRETS[ctx.args.which], value)
    ctx.out(f"{SECRETS[ctx.args.which]}: set in {path}")
    return 0


def add_command(sub) -> None:
    p = sub.add_parser("plan", help="saas plans: list them, or set an organisation's")
    acts = p.add_subparsers(dest="action", required=True)
    acts.add_parser("list").set_defaults(run=cmd_plan)
    q = acts.add_parser("set")
    q.add_argument("org", help="the organisation's slug or name")
    q.add_argument("plan", help="a plan in saas.plans, or none")
    q.add_argument("--status", choices=STATUSES)
    q.add_argument("--trial-days", type=int, help="start a trial of N days from now")
    q.set_defaults(run=cmd_plan)

    p = sub.add_parser("usage", help="saas: this month's requests per organisation")
    p.add_argument("--org", metavar="SLUG")
    p.add_argument("--month", metavar="YYYY-MM")
    p.set_defaults(run=cmd_usage)

    p = sub.add_parser("billing", help="saas: the Stripe secrets (read from stdin)")
    acts = p.add_subparsers(dest="action", required=True)
    q = acts.add_parser("secret")
    q.add_argument("which", choices=tuple(SECRETS))
    q.set_defaults(run=cmd_billing)
