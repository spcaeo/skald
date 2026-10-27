"""The MCP tools for fixing Overview > Insights' to-dos with the assistant itself (2.41):
fix_todo and mark_todo_done. "Fix my Skald to-dos" in Claude Code or Codex then works with
the MCP token alone: no line, no download, no copy and paste.

fix_todo reads: one to-do with EVERY row (todo_rows.py's file beside the history, the
same rows the kit's GET <code>/todo/<id> hands an agent; never the browser's files, which
may be cut short) and its job steps (kit/agent_todos.guide: check first, change only what
is missing, never touch what the to-do does not list, ask before any server change).
Rows are page paths and counts, or where visits came from: never a visitor's address or
email. Any token that may read the site may call it. Without an id: the open to-dos an
agent can fix.

mark_todo_done keeps the assistant's report and, for "done", marks the to-do done, so
Skald's re-check runs on every whole day after (todo_marks.keep_fix, agent_done). It
needs a token with the `setup` scope for that one site, made by an owner or admin who
still is one (apitokens.check), and writes the audit row "mcp.todo_done" (the token's
id, the to-do, the state; never the change). Marking done changes no figure, and is
undone with one click on the dashboard.
"""
from __future__ import annotations

from .data import SITE, Refused
from .tools import SITE_ARG, schema, tool

ID_ARG = {"type": "string", "maxLength": 40,
          "description": "The to-do's id, as todos or fix_todo lists them (lost-pages, "
                         "server-errors, ai-markdown, sitemap, leave-<8 hex>)."}
ROWS_MOST = 5000


def _folder(ctx):
    from ..todo_agent import folder_of
    return folder_of(ctx.config, ctx.live_dir, ctx.config_path)


def _found(ctx, site: str) -> dict | None:
    """The site check's facts (web server, host, framework), when accounts are kept."""
    try:
        from pathlib import Path

        from ..accounts import db as base
        from ..accounts import site_setup
        path = base.path_for(ctx.config, ctx.live_dir)
        if path is None or not Path(path).is_file():
            return None
        db = base.connect(path)
        try:
            return (site_setup.get(db, site) or {}).get("found")
        finally:
            db.close()
    except Exception:                    # noqa: BLE001 - the steps say to find it out
        return None


@tool("fix_todo", "Fix one of Insights' to-dos: every row and the steps",
      "One to-do from Overview > Insights' \"To do now\" with EVERY row behind it (old "
      "addresses and their closest live page, Markdown copies AI asks for, sitemap "
      "addresses, server errors by address, or where visits to a page people leave came "
      "from) and the steps to fix it yourself in the site's own code or server: find where "
      "the site keeps its redirects or rules, check first, change only what is missing, never "
      "touch what the to-do does not list, ask the user before any server change and test it "
      "(`nginx -t`) before a reload. Then call mark_todo_done. Without `id`: the open to-dos "
      "you can fix. Rows hold paths and counts only, never a visitor's address or email.",
      schema({"site": SITE_ARG, "id": ID_ARG,
              "offset": {"type": "integer", "minimum": 0, "default": 0,
                         "description": "The first row to give (for a long list)."},
              "limit": {"type": "integer", "minimum": 1, "maximum": ROWS_MOST, "default": 1000,
                        "description": "Most rows in this answer."}}))
def fix_todo(ctx, args):
    from .. import todo_rows
    from ..kit import agent_todos
    site = ctx.site(args.get("site"))
    want = str(args.get("id") or "").strip()
    folder = _folder(ctx)
    got = todo_rows.read(folder, site)
    if got is None:
        raise Refused(f"{site}'s to-do list is not written yet: it comes with the next data "
                      "update.")
    items = [t for t in got.get("todos") or [] if t.get("kind") in agent_todos.KINDS]
    if not want:
        lines = [f"{site}: {len(items)} to-do{'s' if len(items) != 1 else ''} you can fix."]
        lines += [f"- [{t['id']}] {t['title']}: {t['proof']} ({t.get('rows_total')} rows)"
                  for t in items]
        lines.append("Call fix_todo with an id for its rows and steps.")
        return "\n".join(lines), {"site": site, "todos": [
            {k: t.get(k) for k in ("id", "kind", "title", "proof", "todo", "check", "rows_total",
                                   "first_seen")} for t in items]}
    one = todo_rows.one(folder, site, want)
    if one is None or one.get("kind") not in agent_todos.KINDS:
        raise Refused(f"{site} has no to-do {want!r} now (fixed, under its threshold, or its "
                      "second count disagreed); fix_todo without an id lists them.")
    offset, limit = int(args.get("offset") or 0), int(args.get("limit") or 1000)
    rows = one["rows"][offset:offset + limit]
    steps = agent_todos.guide(one, site, _found(ctx, site))
    cols = [c.get("key") for c in one.get("columns") or []]
    lines = [f"{site}: to-do [{one['id']}] {one['title']}.", f"Proof: {one['proof']}",
             f"To do: {one['todo']}", f"Skald checks it by: {one['check']}.",
             f"Rows {offset + 1 if rows else 0} to {offset + len(rows)} of {one['rows_total']} "
             f"(columns: {', '.join(cols)}):"]
    lines += ["- " + " | ".join("" if r.get(c) is None else str(r.get(c)) for c in cols) for r in rows]
    if offset + len(rows) < one["rows_total"]:
        lines.append(f"More rows: call again with offset {offset + len(rows)}.")
    if one.get("scrubbed"):
        lines.append(f"{one['scrubbed']} value(s) looked like an address or an email and are "
                     "shown as [removed]: leave those rows out.")
    lines += ["", "The steps:", steps]
    return "\n".join(lines), {
        "site": site, "todo": {k: one.get(k) for k in ("id", "kind", "subject", "title", "proof",
                                                       "todo", "check", "window", "columns")},
        "rows": rows, "offset": offset, "rows_total": one["rows_total"], "steps": steps}


STATE_ARG = {"type": "string", "enum": ["done", "partly", "left"], "default": "done",
             "description": "done (every row handled), partly (some: the rest in left), left "
                            "(nothing changed: say why in notes)."}


@tool("mark_todo_done", "Report a to-do you fixed, and mark it done",
      "After fix_todo: keeps what you did for one to-do (the exact change as text, the files, "
      "the rows left and why) so the user sees it beside the to-do, and with state done marks "
      "the to-do done: Skald then checks it with the same measure on every whole day after "
      "(undo is one click on the dashboard; no figure changes). Needs a token with the setup "
      "scope for this one site, made by an owner or admin. Written to the audit log.",
      schema({"site": {**SITE_ARG, "description": "The site's name (left out: the one site the "
                                                 "setup token is for)."},
              "id": ID_ARG, "state": STATE_ARG,
              "change": {"type": "string", "maxLength": 200000,
                         "description": "The exact change, as text: the lines you added, or a diff."},
              "files": {"type": "array", "maxItems": 100, "items": {"type": "string", "maxLength": 300},
                        "description": "The files you changed."},
              "left": {"type": "array", "maxItems": 2000,
                       "items": {"type": "object", "properties": {
                           "row": {"type": "string", "maxLength": 300},
                           "why": {"type": "string", "maxLength": 300}}},
                       "description": "The rows not handled: {row, why}."},
              "notes": {"type": "string", "maxLength": 1000,
                        "description": "Anything else, in one or two plain sentences."}},
             required=("id",)), read_only=False)
def mark_todo_done(ctx, args):
    from .. import todo_marks, todo_rows
    from ..accounts import auditlog
    from ..accounts import db as base
    from ..accounts.orgs import org_of_site
    from ..kit import agent_todos
    from ..sites_api import read_only
    site = args.get("site")
    if site in (None, "") and ctx.setup is not None:
        site = ctx.site(None)
    if not isinstance(site, str) or not SITE.match(site):
        raise Refused(f"{site!r} is not a site name; list_sites gives the names.")
    if ctx.setup is None:
        raise Refused("Marking a to-do done needs a token with the setup scope, over the MCP "
                      "endpoint (POST /traffic-mcp). This connection has no token.")
    ok, why, entry = ctx.setup(site)
    if not ok or not entry:
        raise Refused(f"Marking a to-do done on {site} needs a token with the setup scope for "
                      f"that site, made by an owner or admin: {why or 'not allowed'}.")
    if entry.get("sites") != [site]:
        raise Refused("A token that marks to-dos done is for exactly one site.")
    raw = {"id": args.get("id"), "state": args.get("state") or "done", "change": args.get("change"),
           "files": args.get("files"), "left": args.get("left"), "notes": args.get("notes")}
    if todo_rows.one(_folder(ctx), site, str(raw["id"] or "")) is None:
        raise Refused(f"{site} has no to-do {raw['id']!r} now; fix_todo without an id lists them.")
    try:
        got = agent_todos.clean_fix(raw, [raw["id"]])
    except ValueError as no:
        raise Refused(str(no)) from None
    db = base.connect(base.path_for(ctx.config, ctx.live_dir))
    try:
        org = org_of_site(db, site)
        if org is None or org["id"] != entry["org_id"]:
            raise Refused(f"{site} is not a site of this token's organisation.")
        frozen = read_only(db, ctx.config, org["id"])
        if frozen:
            raise Refused(frozen)
        who = f"mcp:{entry['id']}"
        todo_marks.keep_fix(db, site, got["id"], got["state"], got["change"], got["files"],
                            got["left"], got["notes"], None, who)
        day = agent_todos._today(ctx.config, ctx.config_path, site)
        marked = got["state"] == "done" and todo_marks.agent_done(db, site, got["id"], day, who)
        auditlog.record(db, org["id"], entry.get("created_by") or "mcp", "mcp.todo_done", site,
                        f"token {entry['id']}; to-do {got['id']}; {got['state']}"
                        f"{'; marked done' if marked else ''}; {len(got['left'])} row(s) left")
    finally:
        db.close()
    if got["state"] in ("done", "partly"):
        # 2.44: the same "Check again" the page has, in the background (todo_check.py).
        from .. import todo_check
        todo_check.after_report(ctx.config, ctx.config_path, _folder(ctx), site, got["id"], who)
    if got["state"] == "done":
        text = (f"Kept. [{got['id']}] is marked done{' from ' + day if marked else ' (it was already)'}"
                ": Skald checks it with the same measure on every whole day after. The user can "
                "undo the mark with one click (Overview > Insights).")
    else:
        text = f"Kept. [{got['id']}] stays open ({got['state']}); the user sees what you did and why."
    return text, {"site": site, "id": got["id"], "state": got["state"], "marked_done": bool(marked),
                  "rows_left": len(got["left"])}
