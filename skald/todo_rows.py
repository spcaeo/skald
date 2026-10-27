"""The to-dos' full rows, kept on the server for the person's own AI agent (2.41).

todos.json (the browser's file) carries at most todos.ROWS_MOST rows a to-do, and the
big browser files (not_found.json, page_index.json) may be cut to their top rows for
speed. An AI agent that fixes a to-do needs every row. So todos.build() also writes
this file beside the history, never in the dashboard folder:

    <history folder>/todo-rows/<site>.json      mode 0600

    {"site", "generated_at", "window",
     "todos": [{id, kind, subject, tag, title, proof, todo, check, figures, window,
                columns, rows (every row, at most AGENT_MOST), rows_total, file,
                first_seen}],
     "seen": {to-do id: the first day it was on the list, open}}

Only the to-dos the second count agreed with are in it (the withheld ones are named
in todos.json, never given out). It is read by the kit (GET /traffic-kit/<code>/todo/<id>,
kit/agent_todos.py), by the dashboard (settings/todo-rows, todo_api.py) and by the MCP
tool fix_todo: the same rows todos.py made, whatever the browser's files hold.

What a row holds: page paths and counts (lost, markdown, sitemap, errors), or where the
visits came from and how many (leave). Never a visitor's address or email; an email or
an IPv4 address inside a path (a link someone pasted) is replaced by "[removed]" when
the rows are handed out (`scrub`).

"New": `seen` keeps the day each open to-do first qualified (a to-do that left the
list and came back is new again). A new one queues the outgoing webhook "todo.new"
(conversions/outgoing.py): its id, title, proof, figures and the link that opens it
with "Fix this", never a code and never a row.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from .files import own_like_folder, slug

AGENT_MOST = 20000                # rows a to-do hands an agent
FOLDER = "todo-rows"
EVENT = "todo.new"
KEEP = ("id", "kind", "subject", "tag", "title", "proof", "todo", "check", "figures", "window",
        "columns", "rows", "rows_total", "file", "open")
EMAIL = re.compile(r"[^\s/?#&=]+@[^\s/?#&=]+\.[A-Za-z]{2,}")
IPV4 = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])")
REMOVED = "[removed]"


def path_for(folder, site: str) -> Path:
    return Path(folder) / FOLDER / f"{slug(site)}.json"


def folder_of(p) -> Path | None:
    """The history folder of a data_files.Page, or None (a history in memory)."""
    where = getattr(p.history, "path", None)
    if where is None or str(where) == ":memory:":
        return None
    return Path(where).resolve().parent


def read(folder, site: str) -> dict | None:
    try:
        got = json.loads(path_for(folder, site).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return got if isinstance(got, dict) and got.get("site") == site else None


def one(folder, site: str, todo_id: str) -> dict | None:
    """One to-do with every row, scrubbed, or None."""
    got = read(folder, site) if folder is not None else None
    for t in (got or {}).get("todos") or []:
        if isinstance(t, dict) and t.get("id") == todo_id:
            return scrub(t)
    return None


def scrub(todo: dict) -> dict:
    """The to-do as handed out: an email or IPv4 address inside a row's words is
    "[removed]" (`scrubbed`: how many values)."""
    out, n = dict(todo), 0
    rows = []
    for r in todo.get("rows") or []:
        row = {}
        for k, v in r.items():
            if isinstance(v, str) and (EMAIL.search(v) or IPV4.search(v)):
                v = IPV4.sub(REMOVED, EMAIL.sub(REMOVED, v))
                n += 1
            row[k] = v
        rows.append(row)
    out["rows"] = rows
    out["scrubbed"] = n
    return out


def _write(path: Path, body: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(body, separators=(",", ":")))
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    own_like_folder(path)


def keep(p, todos: list[dict], full: dict, withheld: list[str], window: dict) -> dict[str, str]:
    """Write the file for a page's to-dos (todos.build, the site's own page only).
    `full`: {id: every row}. {id: first_seen} of the open to-dos. Never raises: a
    failure leaves the old file and is said on stderr."""
    import sys
    folder = folder_of(p)
    if folder is None or p.view is not None:
        return {}
    site = p.key.split("::", 1)[0]
    try:
        old = (read(folder, site) or {}).get("seen") or {}
        today = p.anchor.isoformat()
        seen = {k: v for k, v in old.items() if k in withheld}
        new = []
        for t in todos:
            if t.get("state") != "open":
                continue
            if t["id"] in old:
                seen[t["id"]] = old[t["id"]]
            else:
                seen[t["id"]] = today
                new.append(t)
        rows = []
        for t in todos:
            got = {k: t.get(k) for k in KEEP}
            every = full.get(t["id"], t.get("rows") or [])
            got["rows"] = every[:AGENT_MOST]
            got["rows_total"] = len(every)
            got["first_seen"] = seen.get(t["id"])
            rows.append(got)
        _write(path_for(folder, site), {
            "site": site, "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "window": window, "todos": rows, "seen": seen})
        if new:
            notify(p.config, folder, site, new, seen)
        return {t["id"]: seen[t["id"]] for t in todos if t["id"] in seen}
    except Exception as why:              # noqa: BLE001 - the to-do list is written either way
        print(f"todos: the agents' rows file was not written ({type(why).__name__})", file=sys.stderr)
        return {}


def hook_body(config: dict, site: str, t: dict, first_seen: str) -> dict:
    """The outgoing "todo.new" body: words, figures and the link. No code, no row."""
    from .todo_api import link
    return {"event": EVENT, "site": site,
            "todo": {k: t.get(k) for k in ("id", "kind", "subject", "title", "proof", "todo", "check")},
            "figures": t.get("figures"), "rows_total": t.get("rows_total", len(t.get("rows") or [])),
            "link": link(config, t["id"]) + "&fix=1&by=agent", "first_seen": first_seen,
            "text": f"[{site}] New to-do: {t.get('title')}. {t.get('proof') or ''}".strip()}


def notify(config: dict, folder: Path, site: str, new: list[dict], seen: dict) -> int:
    """Queue "todo.new" for each new to-do, for the site's webhooks that ticked it."""
    try:
        from .conversions import outgoing
        now = datetime.now(timezone.utc)
        return sum(outgoing.notify(config, Path(folder), site, EVENT, f"{t['id']}:{seen[t['id']]}",
                                   hook_body(config, site, t, seen[t["id"]]), now) for t in new)
    except Exception:                     # noqa: BLE001 - a webhook never stops the list
        return 0
