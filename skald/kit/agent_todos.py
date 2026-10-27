"""Overview > Insights' to-dos as AI agent jobs (2.41,
docs/plans/2026-10-26-todos-to-agents.md).

A to-do line is an agent line (agent.py) whose entry has `todos`: [{id, kind, title}],
and whose jobs are `todo-<kind>` (agent_jobs.TODO_JOBS), one per kind it carries. Its
words:

    fix the Skald to-do "<title>" for <site> — read <llms> and use code <code> (works once, 24 hours)
    fix the Skald to-dos for <site> (<n>: "<title>", ...) — read <llms> and use code <code> (...)

It makes no token and no lead secret: its keys file holds SKALD_SITE and SKALD_REPORT_KEY.
A new to-do line ends the site's older to-do lines whose keys were not taken, never a
set-up line (and a set-up line never ends a to-do line).

Its routes, on the beacon helper beside agent.py's (curl or Wget, the header
X-Skald-Report-Key from the keys file; an ended code: 410):

  GET  /traffic-kit/<code>/todo/<id>   one to-do of the line with EVERY row, as JSON, from
                                       todo_rows.py's file beside the history (never the
                                       browser's data files, which may be cut short); only
                                       a to-do the line carries, of the line's own site
  POST /traffic-kit/<code>/fix         one to-do's report, JSON, at most FIX_MOST bytes:
                                       {id, state: done | partly | left, change, files,
                                       left: [{row, why}], notes}; kept in accounts.sqlite
                                       (todo_marks.keep_fix); "done" marks the to-do done
                                       (todo_marks.agent_done), so Skald's re-check runs on
                                       the whole days after. Audited ("todo.fixed", actor
                                       "ai-agent", the link id), never the change itself.

A leaked code can at most read the to-dos' paths and counts and mark one done, which
changes no figure, only starts a re-check, and is undone with one click.

The steps: todo-head.md, keys.md (step 1), todo-rows.md (step 2), todo-where.md (step 3,
when a kind needs a redirect or a server rule), jobs/todo-<kind>.md for each kind, and
todo-finish.md. The MCP's fix_todo hands the same job text with the rows inline
(`guide`).
"""
from __future__ import annotations

import hmac
import json
import re
import sqlite3
import sys
import time
from pathlib import Path

from . import agent_jobs, link

KINDS = ("lost", "errors", "markdown", "sitemap", "leave")
JOB = {k: f"todo-{k}" for k in KINDS}
WHERE = ("lost", "markdown", "sitemap")          # the kinds that need step 3
MOST = 25                                        # to-dos in one line
TITLE_MOST = 120
FIX_MOST = 256 * 1024
TEXT_MOST = 1000
LEFT_MOST = 2000
FILES_MOST = 100
ACTOR = "ai-agent"
TODO_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")
HERE = Path(__file__).resolve().parent / "agent"


def kind_of(todo_id: str) -> str | None:
    """The kind of a to-do id (todos.py's ids)."""
    fixed = {"lost-pages": "lost", "server-errors": "errors", "ai-markdown": "markdown",
             "sitemap": "sitemap"}
    if todo_id in fixed:
        return fixed[todo_id]
    return "leave" if re.match(r"^leave-[0-9a-f]{8}$", todo_id or "") else None


def clean(todos) -> list[dict]:
    """[{id, kind, title}] in the list's order, each once; ValueError in plain words."""
    if not isinstance(todos, list) or not todos:
        raise ValueError("Name at least one to-do.")
    if len(todos) > MOST:
        raise ValueError(f"At most {MOST} to-dos in one line.")
    out, seen = [], set()
    for t in todos:
        tid = t.get("id") if isinstance(t, dict) else None
        kind = kind_of(tid) if isinstance(tid, str) else None
        if kind is None or t.get("kind") != kind:
            raise ValueError("That is not a to-do an AI agent can fix.")
        if tid in seen:
            continue
        seen.add(tid)
        title = " ".join(str(t.get("title") or tid).split())[:TITLE_MOST].replace('"', "'")
        out.append({"id": tid, "kind": kind, "title": title})
    return out


def jobs_of(todos: list[dict]) -> list[str]:
    return [JOB[k] for k in KINDS if any(t["kind"] == k for t in todos)]


def is_todo(entry: dict | None) -> bool:
    return bool((entry or {}).get("todos"))


def line(site: str, llms: str, code: str, todos: list[dict], hours: int = link.HOURS) -> str:
    tail = f"read {llms} and use code {code} (works once, {hours} hours)"
    if len(todos) == 1:
        return f'fix the Skald to-do "{todos[0]["title"]}" for {site} — {tail}'
    names = ", ".join(f'"{t["title"]}"' for t in todos)
    return f"fix the Skald to-dos for {site} ({len(todos)}: {names}) — {tail}"


# --------------------------------------------------------------- steps

def _read(name: str) -> str:
    return (HERE / name).read_text(encoding="utf-8")


def _rows_file(env_dir: str, site: str, tid: str) -> str:
    return f"{env_dir}/{site}.todo-{tid}.json"


def _fetch(here: str, env_dir: str, env_file: str, site: str, tid: str) -> str:
    out = _rows_file(env_dir, site, tid)
    return (f"    grep '^SKALD_REPORT_KEY=' {env_file} | sed 's/^SKALD_REPORT_KEY=/X-Skald-Report-Key: /' "
            f"| (umask 077 && curl -sS -H @- -o {out} -w 'HTTP %{{http_code}}\\n' "
            f"'{here}/todo/{tid}')")


def _rows_where(todos: list[dict], kind: str, env_dir: str, site: str) -> str:
    files = [f"`{_rows_file(env_dir, site, t['id'])}`" for t in todos if t["kind"] == kind]
    return "the file " + files[0] if len(files) == 1 else "the files " + ", ".join(files)


def _leave_list(todos: list[dict]) -> str:
    return "\n".join(f"- `{t['id']}`: {t['title']}" for t in todos if t["kind"] == "leave")


def _parts(kinds: list[str]) -> tuple[list[str], dict]:
    """The step files after the keys, and their numbers."""
    names = ["todo-rows.md"] + (["todo-where.md"] if any(k in WHERE for k in kinds) else [])
    names += [f"jobs/todo-{k}.md" for k in kinds] + ["todo-finish.md"]
    return names, {name: str(n) for n, name in enumerate(names, 2)}


def steps(entry: dict, code: str, base: str) -> str:
    """The to-do line's steps in Markdown: addresses, ids and words, never a key."""
    fields = entry.get("fields") or {}
    todos = entry["todos"]
    site = entry["site"]
    kinds = [k for k in KINDS if any(t["kind"] == k for t in todos)]
    root = (fields.get("base") or base or "").rstrip("/")
    here = f"{root}{link.PREFIX}{code}"
    env_dir, env_file = "$HOME/.config/skald", f"$HOME/.config/skald/{site}.env"
    names, numbers = _parts(kinds)
    parts = [_read("todo-head.md"), _read("keys.md").replace("__N__", "1")]
    for name in names:
        text = _read(name).replace("__N__", numbers[name])
        if name.startswith("jobs/todo-"):
            kind = name[len("jobs/todo-"):-3]
            text = text.replace("__ROWS__", _rows_where(todos, kind, env_dir, site))
        parts.append(text)
    dashboard = fields.get("dashboard") or ""
    values = {
        "SITE": site, "COUNT": f"{len(todos)} to-do{'s' if len(todos) != 1 else ''}",
        "TODO_LIST": "\n".join(f"- `{t['id']}`: {t['title']}" for t in todos),
        "EXPIRES": link.stamp(entry["expires_at"]).replace("T", " ")[:16],
        "DASHBOARD": dashboard, "INSIGHTS": f"{dashboard}#overview/insights" if dashboard else
        "Overview > Insights", "HELP": fields.get("help") or "",
        "FOUND": agent_jobs.found_lines(entry.get("found") or None),
        "ENV_FILE": env_file, "ENV_DIR": env_dir, "KEYS_URL": f"{here}/keys",
        "KEY_NAMES": "`SKALD_SITE` and `SKALD_REPORT_KEY` (to get the rows and to report)",
        "FETCH": "\n".join(_fetch(here, env_dir, env_file, site, t["id"]) for t in todos),
        "STEP_ROWS": numbers["todo-rows.md"], "STEP_WHERE": numbers.get("todo-where.md", ""),
        "LEAVE_LIST": _leave_list(todos), "IDS": ", ".join(f"`{t['id']}`" for t in todos),
        "FIX_URL": f"{here}/fix"}
    return agent_jobs.fill("\n".join(parts), values)


def guide(todo: dict, site: str, found: dict | None = None) -> str:
    """One to-do's job for the MCP's fix_todo: the same text, the rows in the answer."""
    kind = todo["kind"]
    names = (["todo-where.md"] if kind in WHERE else []) + [f"jobs/todo-{kind}.md"]
    parts = []
    for n, name in enumerate(names, 1):
        parts.append(_read(name).replace("__N__", str(n)))
    text = "\n".join(parts).replace("__ROWS__", "`rows` in this answer (every row)")
    text = agent_jobs.fill(text, {
        "SITE": site, "STEP_WHERE": "1", "LEAVE_LIST": f"- `{todo['id']}`: {todo.get('title')}"})
    head = ("Rules: look before you change, and change only what is missing; never touch what "
            "this to-do does not list; ask the user before any server or web-server change, "
            "and test it (`nginx -t` or the equivalent) before a reload; never change a setting "
            "in Skald itself.\n\nWhat Skald's site check found:\n" + agent_jobs.found_lines(found))
    tail = (f"\n## Then\n\nTell the user what you did. Then call `mark_todo_done` with `id` "
            f"`{todo['id']}`, `state` (done, partly or left), the exact `change` as text and the "
            "rows `left` with why. `done` marks the to-do done in Skald, which then re-checks it "
            "on every whole day after (undo is one click in Skald).")
    return f"{head}\n\n{text}{tail}"


# --------------------------------------------------------------- routes

def _no(h, code: int, error: str) -> None:
    from . import agent
    agent._json(h, code, {"ok": False, "error": error})


def _checked(h, folder, code: str, now: float):
    """The entry when the request may go on, else None after answering."""
    from . import agent
    if not (h.headers.get("User-Agent") or "").lower().startswith(link.AGENTS):
        _no(h, 403, "Use curl in a shell, as the steps show; never a web reader or fetch tool.")
        return None
    entry = agent.find(folder, code)
    if entry is None:
        _no(h, 404, agent.UNKNOWN.strip())
        return None
    if not is_todo(entry):
        _no(h, 404, "This line carries no to-do.")
        return None
    key = (h.headers.get(agent.REPORT_HEADER) or "").strip()
    want = entry.get("report_key") or ""
    if not key or not want or not hmac.compare_digest(agent._key_hash(key), want):
        _no(h, 403, f"Send the {agent.REPORT_HEADER} header with SKALD_REPORT_KEY from the keys "
                    "file, as the steps show.")
        return None
    if agent.ended(entry, now):
        _no(h, 410, "This code has expired or was cancelled. Ask the user to press Fix this "
                    "again in Skald.")
        return None
    return entry


def rows(h, folder, code: str, todo_id: str, now: float | None = None) -> None:
    """GET <code>/todo/<id>: every row of one to-do the line carries."""
    from .. import todo_rows
    now = time.time() if now is None else now
    entry = _checked(h, folder, code, now)
    if entry is None:
        return None
    if not any(t["id"] == todo_id for t in entry["todos"]):
        return _no(h, 404, "This line does not carry that to-do. Its ids are in the steps.")
    got = todo_rows.one(folder, entry["site"], todo_id)
    if got is None:
        return _no(h, 404, "That to-do is not on the site's list now (fixed, under its "
                           "threshold, or its second count disagreed). Tell the user.")
    keep = ("id", "kind", "subject", "title", "proof", "todo", "check", "window", "columns",
            "rows", "rows_total", "scrubbed")
    body = {"ok": True, "site": entry["site"], **{k: got.get(k) for k in keep},
            "holds": "page paths and counts, or where visits came from; never a visitor's "
                     "address or email"}
    from . import agent
    return agent._send(h, 200, json.dumps(body) + "\n", "application/json; charset=utf-8")


def _text(value, most: int) -> str:
    from . import agent
    return agent._text(value, most) or ""


def _change(value) -> str:
    """The change as sent: its lines kept, control characters (but tab and new line) out,
    anything shaped like a token or secret removed, capped."""
    from . import agent
    if not isinstance(value, str):
        return ""
    got = "".join(ch for ch in value if ch in "\n\t" or ch.isprintable())
    from ..todo_marks import FIX_CHANGE_MOST
    return agent.SECRETISH.sub("[removed]", got)[:FIX_CHANGE_MOST]


def clean_fix(raw, todo_ids) -> dict:
    """{id, state, change, files, left, notes}; ValueError in plain words."""
    from ..todo_marks import FIX_STATES
    if not isinstance(raw, dict):
        raise ValueError("The report is one JSON object.")
    tid = raw.get("id")
    if not isinstance(tid, str) or tid not in todo_ids:
        raise ValueError("`id` is one of this line's to-dos: " + ", ".join(todo_ids) + ".")
    state = raw.get("state")
    if state not in FIX_STATES:
        raise ValueError("`state` is done, partly or left.")
    files = []
    for one in raw["files"][:FILES_MOST * 5] if isinstance(raw.get("files"), list) else []:
        got = _text(one, 300)
        if got and got not in files:
            files.append(got)
        if len(files) == FILES_MOST:
            break
    left = []
    for one in (raw.get("left") or [])[:LEFT_MOST * 2] if isinstance(raw.get("left"), list) else []:
        if isinstance(one, dict):
            row, why = _text(one.get("row"), 300), _text(one.get("why"), 300)
        else:
            row, why = _text(one, 300), ""
        if row:
            left.append({"row": row, "why": why})
        if len(left) == LEFT_MOST:
            break
    return {"id": tid, "state": state, "change": _change(raw.get("change")), "files": files,
            "left": left, "notes": _text(raw.get("notes"), TEXT_MOST)}


def fix(h, folder, code: str, config: dict | None, config_path=None,
        now: float | None = None) -> None:
    """POST <code>/fix: one to-do's report."""
    now = time.time() if now is None else now
    try:
        length = int(h.headers.get("Content-Length") or -1)
    except ValueError:
        length = -1
    if length < 0:
        return _no(h, 411, "Send the report with a Content-Length.")
    if length > FIX_MOST:
        return _no(h, 413, f"The report is at most {FIX_MOST // 1024} KiB.")
    raw = h.rfile.read(length)
    entry = _checked(h, folder, code, now)
    if entry is None:
        return None
    try:
        got = clean_fix(json.loads(raw.decode("utf-8") or "null"), [t["id"] for t in entry["todos"]])
    except (ValueError, UnicodeDecodeError, RecursionError) as why:
        words = str(why) if isinstance(why, ValueError) and not isinstance(
            why, (json.JSONDecodeError, UnicodeDecodeError)) else "The report is one JSON object."
        return _no(h, 400, words)
    if config is None:
        return _no(h, 503, "Reports cannot be kept through this server. Tell the user what you did.")
    try:
        marked, day = keep(config, folder, config_path, entry, code, got)
    except (sqlite3.Error, OSError) as why:
        print(f"kit fix: the report for {entry['site']} could not be kept ({type(why).__name__})",
              file=sys.stderr)
        return _no(h, 503, "Skald could not keep the report just now. Try again in a minute.")
    if marked is None:
        return _no(h, 503, "Skald keeps no accounts here, so a report cannot be kept. Tell the "
                           "user what you did.")
    _note(folder, code, got, now)
    if got["state"] in ("done", "partly"):
        # 2.44: Skald asks the to-do's addresses now (Check again), in the background; its
        # answer shows beside this report on Overview > Insights.
        from .. import todo_check
        todo_check.after_report(config, config_path, folder, entry["site"], got["id"], ACTOR)
    words = {"done": f"Kept. The to-do is marked done{' from ' + day if marked else ' (it was already)'}"
                     ": Skald checks it with the same measure on every whole day after. The user "
                     "can undo the mark with one click.",
             "partly": "Kept. The to-do stays open; the user sees what you did and what is left.",
             "left": "Kept. The to-do stays open; the user sees why."}[got["state"]]
    from . import agent
    return agent._json(h, 200, {"ok": True, "id": got["id"], "state": got["state"],
                                "marked_done": bool(marked), "says": words})


def _today(config: dict, config_path, site: str) -> str:
    from datetime import datetime

    from ..conversions.hooks import site_configs
    from ..window import zone
    conf = site_configs(config, config_path).get(site) or config
    return datetime.now(zone(conf)).date().isoformat()


def keep(config: dict, folder, config_path, entry: dict, code: str, got: dict):
    """(True when this report marked the to-do done, the day) or (None, None) without
    accounts. One audit row."""
    from .. import todo_marks
    from ..accounts import auditlog
    from ..accounts import db as base
    from ..accounts.orgs import org_of_site
    from . import agent
    path = base.path_for(config, Path(folder))
    if path is None or not Path(path).is_file():
        return None, None
    site, lid = entry["site"], agent.link_id(code)
    db = base.connect(path)
    try:
        todo_marks.keep_fix(db, site, got["id"], got["state"], got["change"], got["files"],
                            got["left"], got["notes"], lid, ACTOR)
        day, marked = _today(config, config_path, site), False
        if got["state"] == "done":
            marked = todo_marks.agent_done(db, site, got["id"], day, ACTOR)
        org = org_of_site(db, site)
        auditlog.record(db, org["id"] if org else None, ACTOR, "todo.fixed", got["id"][:120],
                        f"{site} {got['state']}{'; marked done' if marked else ''}; link {lid}; "
                        f"{len(got['left'])} row(s) left")
    finally:
        db.close()
    return marked, day


def _note(folder, code: str, got: dict, now: float) -> None:
    """The line's own short record: {id: {state, at}} (agent.status shows it)."""
    from . import agent

    def change(entry):
        fixes = dict(entry.get("fixes") or {})
        fixes[got["id"]] = {"state": got["state"], "at": int(now)}
        entry.update(fixes=fixes, reported_at=int(now))
        return None, True
    agent._change(folder, code, change, now)
