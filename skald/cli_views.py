"""`skald --site S views ...`: page groups (views) from the shell.

    skald --site S views list
    skald --site S views refresh [--days N] [--view SLUG ...]

`refresh` fills a view's past days from the raw log (views_fill.py): every
whole day the log still holds (or the last N days), each chosen view counted
with the site's rules, checked, and recounted by the audit's own road
(audit_views.py); a day that does not match is withheld. The site's own days
are left as they are. It is what Settings > Site > Views starts with "Fill
past days for the new groups"; one fill at a time per install.

Exit: 0 every day filled and audited, 1 a day withheld or nothing to fill,
2 no such view, 3 another fill is running.
"""
from __future__ import annotations


def cmd_list(ctx) -> int:
    from .store import view_key
    from .views_fill import reach
    got = reach(ctx.config, ctx.tz, ctx.now)
    with ctx.history() as history:
        for v in ctx.views:
            first = history.first_day(view_key(ctx.site, v.slug))
            ctx.out(f"{v.slug}\t{v.name}\t{v.describe()}\t"
                    f"from {first.isoformat() if first else 'no day stored yet'}")
    if not ctx.views:
        ctx.out(f"{ctx.site}: no views (Settings > Site > Views, or dashboard.views)")
    ctx.out(f"the raw log holds {got['days']} whole day(s)"
            + (f", {got['first']} to {got['last']}" if got["days"] else ""))
    return 0


def cmd_refresh(ctx) -> int:
    from .views_fill import reach, run
    days = ctx.args.days
    if days is None:
        got = reach(ctx.config, ctx.tz, ctx.now)
        days = got["days"]
        if not days:
            ctx.err("views refresh: the raw log holds no whole day before today; "
                    "nothing to fill")
            return 1
        ctx.out(f"the raw log holds {days} whole day(s), {got['first']} to {got['last']}")
    return run(ctx, days, ctx.args.view or None, by=ctx.args.by or "cli")


def add_command(sub) -> None:
    p = sub.add_parser("views", help="page groups: list them, or fill their past days "
                       "from the raw log (refresh)")
    acts = p.add_subparsers(dest="action", required=True)
    q = acts.add_parser("list", help="each view, its rule and its first stored day")
    q.set_defaults(run=cmd_list)
    q = acts.add_parser("refresh", help="recount the views' past days from the raw log, "
                        "audited (default: every whole day the log holds)")
    q.add_argument("--days", type=int, help="the last N days instead")
    q.add_argument("--view", action="append", metavar="SLUG",
                   help="only this view (its folder name), repeatable; default every view")
    q.add_argument("--by", help="who asked (the page passes the admin's email)")
    q.set_defaults(run=cmd_refresh)
