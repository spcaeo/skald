"""Overview > Insights' "Fix this": the to-do line for the person's own AI agent, and the
full rows for "Me" (2.41; docs/plans/2026-10-26-todos-to-agents.md). Served by
todo_api.py under the settings/ prefix nginx already passes on:

  POST settings/todo-agent {act: "make", items: [id, ...] | "all"}
       -> {ok, line, llms_url, steps_url, expires_at, link_id, cancelled, todos}: one line
          for those to-dos (kit/agent_todos.py), "all": every open to-do an agent can fix.
          Owners and admins. Works once, 24 hours; ends the site's older to-do lines whose
          keys were not taken (never a set-up line). Audit row "kit.todoline", never the code.
  POST settings/todo-agent {act: "status", link_id}
       -> agent.status(): state, opened_at, keys_at, reported_at, todos, fixes (the line's
          own {id: {state, at}}), plus `reports`: the kept fix reports of its to-dos
  POST settings/todo-agent {act: "cancel", link_id}  -> {ok, state: "cancelled"}
  GET  settings/todo-rows?item=<id>
       -> {ok, todo}: the to-do with EVERY row (todo_rows.py), for "Me": the lines to paste
          and the CSV, whatever the browser's files hold. Anyone who may read the site.

The to-dos come from todo_rows.py's file beside the history, the same rows the kit hands
the agent; an id not in it (withheld, fixed, under its threshold) is refused in words.
"""
from __future__ import annotations

from pathlib import Path

from . import todo_marks, todo_rows


class Refused(ValueError):
    def __init__(self, status: int, words: str):
        super().__init__(words)
        self.status = status


def folder_of(config, live_dir, config_path=None) -> Path:
    """Where kit-links.json and the rows file live: the kit's own folder (kit_api)."""
    from .conversions import hooks
    return Path(live_dir) if live_dir is not None else hooks.history_folder(config, config_path)


def pick(folder, db, site: str, items) -> list[dict]:
    """The to-dos asked for, from the rows file: [{id, kind, title}]. Refused in words."""
    from .kit import agent_todos
    got = todo_rows.read(folder, site)
    if got is None:
        raise Refused(409, "The to-do list comes with the next data update: Skald has not written "
                           "it yet.")
    known = {t["id"]: t for t in got.get("todos") or [] if t.get("kind") in agent_todos.KINDS}
    if items == "all":
        marks = todo_marks.current(db, site)
        ids = [i for i in known if (marks.get(i) or {}).get("state") not in ("done", "notnow")]
        if not ids:
            raise Refused(409, "There is no open to-do for an AI agent now.")
    elif isinstance(items, list) and items and all(isinstance(i, str) for i in items):
        ids = list(dict.fromkeys(items))
        gone = [i for i in ids if i not in known]
        if gone:
            raise Refused(404, "That to-do is not on the list now (fixed, under its threshold, "
                               "or its second count disagreed).")
    else:
        raise Refused(400, 'items is a list of to-do ids, or "all".')
    return [{"id": i, "kind": known[i]["kind"], "title": known[i]["title"]} for i in ids]


def make_todo_line(db, config, org, site: str, items, actor, *, live_dir=None, config_path=None,
                   allowed=()) -> dict:
    """One to-do line for `site` (a site of `org`), made as `actor`. Refused in words."""
    from . import kit_api
    from .accounts import orgs, site_setup
    from .kit import agent, agent_todos
    if site not in orgs.sites_of_org(db, org["id"]):
        raise Refused(404, "There is no such site in this organisation.")
    c = kit_api._Core(db, config, org, actor, live_dir, config_path, allowed)
    folder = kit_api._folder(c)
    todos = pick(folder, db, site, items)
    fields = kit_api.fields(c, site)
    found = (site_setup.get(db, site) or {}).get("found")
    code, expires, ended = agent.make(folder, site, None, None, fields, leads=False, found=found,
                                      replace=True, todos=todos, made_by=str(actor))
    lid = agent.link_id(code)
    older, _ = kit_api._ended(c, site, ended, "a new to-do line replaced it")
    kit_api._audit(c, "kit.todoline", site, f"link {lid}; to-dos {','.join(t['id'] for t in todos)}; "
                                           f"works once, for {agent.link.HOURS} hours; {older} "
                                           "older line(s) cancelled")
    llms = f"{fields['base']}{agent.link.PREFIX}llms.txt"
    return {"line": agent_todos.line(site, llms, code, todos), "llms_url": llms,
            "steps_url": f"{fields['base']}{agent.link.PREFIX}{code}/steps",
            "expires_at": agent.link.stamp(expires), "link_id": lid, "cancelled": older,
            "todos": todos}


def status(db, folder, site: str, lid: str) -> dict:
    from .kit import agent
    got = agent.status(folder, site, lid)
    if got["state"] == "unknown" or not got.get("todos"):
        return {"state": "unknown"}
    kept = todo_marks.fixes(db, site)
    got["reports"] = {t["id"]: kept[t["id"]] for t in got["todos"] if t["id"] in kept
                      and kept[t["id"]].get("link_id") == lid}
    return got


def latest(db, folder, site: str) -> dict | None:
    """The site's newest to-do line (never its code), with its reports."""
    from .kit import agent
    got = agent.latest(folder, [site], todo=True).get(site)
    if not got:
        return None
    return {"link_id": got["link_id"], **status(db, folder, site, got["link_id"])}


def server_of(db, site: str) -> dict:
    """What the site check found about the web server, for "Me"'s lines."""
    from .accounts import site_setup
    found = (site_setup.get(db, site) or {}).get("found") or {}
    return {k: found.get(k) for k in ("server", "platform", "framework") if found.get(k)}
