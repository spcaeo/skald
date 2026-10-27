"""Insights' "Check again" in the demo (tools/demo.py, 2.44): one sample answer per to-do.

The demo has no server behind it and its site, example.com, is never asked. So each
to-do's answer is made here through the real road (todo_check.check, into a throwaway
accounts table, then todo_api.checks_of as the page reads it) with a made-up site that
answers like a site half-way through its fixes: most old addresses redirect to their
closest live page, a few still answer 404; the Markdown copies and the sitemap are
served; the server errors are gone. A visits to-do says it cannot be checked now, as on
a live install. Written beside the page as data/demo/todo-check-<id>.json; the page
reads it when Check again is pressed in the demo, and says it is a sample.

Sample data only: example.com paths, no address, no email."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path


def _site(t: dict):
    """A made-up site's answers for one to-do's rows."""
    from skald import site_fetch
    rows = [r for r in t.get("rows") or [] if isinstance(r.get("path"), str)]
    # Half-way through: every sixth old address, and the last one, still answer 404.
    still = {r["path"] for i, r in enumerate(rows) if t["kind"] == "lost" and (i % 6 == 5 or i == len(rows) - 1)}
    targets = {r["path"]: r.get("target") or "/" for r in rows}

    def fetch(url, method, deadline):
        path = url.split("example.com", 1)[1] if "example.com" in url else "/"
        if t["kind"] == "lost" and path in targets:
            if path in still:
                return site_fetch.Answer(404)
            return site_fetch.Answer(301, {"location": [targets[path]]})
        return site_fetch.Answer(200)
    return fetch


def answers(site_dir: Path, now: datetime, site: str = "example.com") -> dict[str, str]:
    """{to-do id: data/demo/todo-check-<id>.json}."""
    from skald import todo_api, todo_check
    body = json.loads((site_dir / "data" / "todos.json").read_text())
    folder = site_dir / "data" / "demo"
    folder.mkdir(parents=True, exist_ok=True)
    cfg = {"site": {"name": site, "hosts": [site]}}
    out = {}
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT)")
    db.execute("INSERT INTO users (id, email) VALUES (1, 'owner@example.com')")
    at = now.astimezone(timezone.utc) - timedelta(minutes=4)
    for i, t in enumerate(body.get("todos") or []):
        if not t.get("id") or not t.get("kind"):
            continue
        got = todo_check.check(db, cfg, site, t, 0, 1, "person", fetch=_site(t),
                               reader=lambda *a: {"read": False}, now=at + timedelta(minutes=i * 2),
                               today=at.date().isoformat(), sleep=lambda s: None)
        shown = todo_api.checks_of(db, site).get(t["id"]) or got
        name = f"todo-check-{t['id']}.json"
        (folder / name).write_text(json.dumps({"ok": True, "check": shown, "demo": True}, separators=(",", ":")))
        out[t["id"]] = f"data/demo/{name}"
    db.close()
    return out
