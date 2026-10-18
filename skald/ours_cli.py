"""`skald ours`: the internal-traffic list (ours_store.py) from the shell.

    skald ours list                       every entry by label: where it is
                                          set, Active or Paused (since when),
                                          and since when it applies
    skald ours pause  LABEL|ADDRESS       stop it applying from now on: its
                                          visits count as visitors
    skald ours resume LABEL|ADDRESS       apply it again from now on
    skald ours edit   LABEL|ADDRESS [--label NEW] [--address NEW]
                                          the old entry ends now, a new one
                                          starts now (days before keep the
                                          old label and address)
    skald ours delete LABEL|ADDRESS --yes stop it applying from now on; it
                                          stays in the file for the days
                                          before, so they recount the same

In Docker: `docker exec skald skald ours ...`. Changes are logged to the
change log as "cli". The page shows them at the next live run (two
minutes). Entries from config.yml always apply and cannot be changed here.
Nothing here prints an address: entries are shown by label, as on the
dashboard (the page's management list is where addresses are shown).
"""
from __future__ import annotations

from . import ours_store

ACTOR = "cli"


def cmd_list(ctx) -> int:
    entries = ours_store.listing(ctx.config)
    if not entries:
        ctx.out("No internal addresses.")
        return 0
    for e in entries:
        if e["source"] == "config":
            state, where, since = "always on", "config.yml", "-"
        else:
            state = "active" if e["active"] else f"paused since {e['paused_since']}"
            where, since = "page", e.get("added_at") or "-"
        ctx.out(f"{e['label']}\t{where}\t{state}\tsince {since}")
    ctx.out(f"{len(entries)} of at most {ours_store.LIMIT} entries.")
    return 0


def _run(ctx, fn, done: str) -> int:
    try:
        entry = fn()
    except (ours_store.Invalid, ours_store.Full, OSError) as why:
        ctx.err(str(why))
        return 1
    ctx.out(done.format(label=entry["label"]))
    return 0


def cmd_pause(ctx) -> int:
    return _run(ctx, lambda: ours_store.pause(ctx.config, ctx.args.entry, by=ACTOR),
                "Paused {label}: from now on its visits count as visitors.")


def cmd_resume(ctx) -> int:
    return _run(ctx, lambda: ours_store.resume(ctx.config, ctx.args.entry, by=ACTOR),
                "{label} is active again: from now on its visits count as our own traffic.")


def cmd_edit(ctx) -> int:
    if not ctx.args.label and not ctx.args.address:
        ctx.err("give --label NEW and/or --address NEW")
        return 2
    return _run(ctx, lambda: ours_store.edit(ctx.config, ctx.args.entry, label=ctx.args.label,
                                             ip=ctx.args.address, by=ACTOR),
                "Saved: from now on it counts as {label}. Days before keep the old values.")


def cmd_delete(ctx) -> int:
    if not ctx.args.yes:
        ctx.err("deleting stops the entry applying to days not yet collected (stored days "
                "keep their figures). To stop it only for a while, use `ours pause`. "
                "Add --yes to delete.")
        return 2
    return _run(ctx, lambda: ours_store.remove(ctx.config, ctx.args.entry, by=ACTOR),
                "Deleted {label}: from now on its visits count as visitors.")


def add_command(sub) -> None:
    p = sub.add_parser("ours", help="internal traffic: list, pause, resume, edit, delete "
                       "the addresses added on the page")
    acts = p.add_subparsers(dest="action", required=True)
    acts.add_parser("list", help="every entry by label, Active or Paused").set_defaults(
        run=cmd_list)
    for name, run, words in (("pause", cmd_pause, "stop it applying from now on"),
                             ("resume", cmd_resume, "apply it again from now on")):
        q = acts.add_parser(name, help=words)
        q.add_argument("entry", metavar="LABEL|ADDRESS")
        q.set_defaults(run=run)
    q = acts.add_parser("edit", help="change the label and/or the address from now on")
    q.add_argument("entry", metavar="LABEL|ADDRESS")
    q.add_argument("--label")
    q.add_argument("--address")
    q.set_defaults(run=cmd_edit)
    q = acts.add_parser("delete", help="stop it applying from now on (needs --yes)")
    q.add_argument("entry", metavar="LABEL|ADDRESS")
    q.add_argument("--yes", action="store_true")
    q.set_defaults(run=cmd_delete)
