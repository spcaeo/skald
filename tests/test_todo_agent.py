"""Insights' to-dos fixed by the person's own AI agent (2.41,
docs/plans/2026-10-26-todos-to-agents.md): todo_rows.py, kit/agent_todos.py,
todo_agent.py, todo_api.py's settings/todo-agent and settings/todo-rows, and the MCP
tools fix_todo and mark_todo_done.

Pinned:
  - the rows the agent gets are todos.py's full rows, even when the browser's
    todos.json is cut short; paths and counts only, an email or address in a path
    "[removed]"; the file is 0600 beside the history, never in the dashboard folder
  - the steps run as written under bash with curl: keys once, every row into a 0600
    file, the report built with python3 and posted; the key is never on a command line
  - one line reads only its own site's to-dos, only the ones it carries; an expired or
    cancelled line answers 410; a new to-do line never ends a set-up line
  - a "done" report marks the to-do done (the re-check then runs), audited without the
    change; "partly" and "left" leave it open
  - the MCP: fix_todo reads any token's own site; mark_todo_done needs the setup scope for
    that one site, writes "mcp.todo_done"
  - a mail never holds a code; the "todo.new" webhook holds no code and no row
Test data: example.com, RFC 5737 addresses; the keys are made here.
"""
from __future__ import annotations

import http.client
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from auth_support import A, B, ORIGIN  # noqa: E402
from ingest_support import TenantServer  # noqa: E402
from test_todos import ANCHOR, SITE, Fixture, nf, served, visit  # noqa: E402

from skald import summary_mail, todo_marks, todo_rows, todos  # noqa: E402
from skald.accounts import apitokens  # noqa: E402
from skald.kit import agent, agent_todos, link  # noqa: E402

LOST = {"id": "lost-pages", "kind": "lost", "subject": None, "tag": "Lost traffic",
        "title": "Send old pages somewhere useful", "proof": "3 old page addresses answered 'not found'.",
        "todo": "Redirect each to the closest live page.", "check": "the not-found answers to the same addresses",
        "figures": {"paths": 3}, "window": {"first": "2026-10-01", "last": "2026-10-10"},
        "columns": [{"key": "path", "label": "Old address", "path": True}, {"key": "people", "label": "People"},
                    {"key": "target", "label": "Closest live page", "path": True}],
        "rows": [{"path": "/old-pricing/", "people": 7, "target": "/pricing/"},
                 {"path": "/gone/", "people": 2, "target": None},
                 {"path": "/u/someone@example.com/", "people": 1, "target": None}],
        "rows_total": 3, "file": "old-pages.csv", "first_seen": "2026-10-09"}
ERRORS = {**LOST, "id": "server-errors", "kind": "errors", "title": "Fix the server errors",
          "rows": [{"path": "/wp-json/", "errors": 18}], "rows_total": 1, "file": "server-errors.csv"}
BETA = {**LOST, "rows": [{"path": "/beta-only/", "people": 5, "target": "/"}], "rows_total": 1}


def rows_file(folder, site, items):
    todo_rows._write(todo_rows.path_for(folder, site), {
        "site": site, "generated_at": "2026-10-11T07:20:00Z", "window": LOST["window"],
        "todos": items, "seen": {t["id"]: t["first_seen"] for t in items}})


# ------------------------------------------------------------------ the rows file

class RowsFile(unittest.TestCase):
    """todos.build() writes every row beside the history, whatever todos.json holds
    (test_todos.Todos' history)."""

    def setUp(self):
        from datetime import timedelta
        self.f = Fixture()
        self.addCleanup(self.f.close)
        self.f.sitemap(["/", "/pricing/", "/guides/", "/guides/setup/"])
        for i in range(3):
            d = ANCHOR - timedelta(days=2 - i)
            self.f.day(d, [nf("/old-pricing/", 3), nf("/old-post/", 2, "search_engines"),
                           nf("/guides/setup.md", 2, "ai_asked"), nf("/sitemap_index.xml", 1, "search_engines")],
                       {"/": served(views=10)},
                       counts=[("server_error_page", "/", 2), ("status_people", "5xx", 1),
                               ("status_bots", "5xx", 1)],
                       journeys=[visit("/landing/") for _ in range(9)] + [visit("/", pages=3)])

    def build(self):
        return todos.build(self.f.page())

    def test_every_row_even_when_the_browser_file_is_cut_short(self):
        whole = self.build()
        with mock.patch.object(todos, "ROWS_MOST", 1):
            cut = self.build()
        lost = {t["id"]: t for t in cut["todos"]}["lost-pages"]
        self.assertEqual(len(lost["rows"]), 1, "the browser's file: cut to ROWS_MOST")
        self.assertEqual(lost["rows_total"], 2)
        path = todo_rows.path_for(self.f.dir, SITE)
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        kept = {t["id"]: t for t in todo_rows.read(self.f.dir, SITE)["todos"]}
        for t in whole["todos"]:
            self.assertEqual(kept[t["id"]]["rows"], t["rows"], t["id"])
            self.assertEqual(kept[t["id"]]["rows_total"], len(t["rows"]))
        self.assertTrue(lost["agent"])
        self.assertEqual(set(todos.AGENT_KINDS), set(agent_todos.KINDS))
        self.assertEqual(set(todos.AGENT_KINDS), set(summary_mail.AGENT_KINDS))

    def test_first_seen_holds_and_the_webhook_says_each_new_one_once(self):
        with mock.patch("skald.conversions.outgoing.notify", return_value=1) as hook:
            first = self.build()
            again = self.build()
        ids = [t["id"] for t in first["todos"] if t["state"] == "open"]
        self.assertEqual(hook.call_count, len(ids), "each new to-do once, not on the next build")
        self.assertEqual({t["id"]: t["first_seen"] for t in first["todos"]},
                         {t["id"]: t["first_seen"] for t in again["todos"]})
        for call in hook.call_args_list:
            _, _, site, event, ref, body, _ = call.args
            self.assertEqual(event, "todo.new")
            self.assertTrue(ref.startswith(body["todo"]["id"] + ":"))
            self.assertNotIn("rows", body)
            self.assertNotIn("rows", body["todo"])
            self.assertIn("&fix=1&fixby=agent", body["link"])
            self.assertNotRegex(json.dumps(body), r"[A-Za-z0-9_-]{43}", "never a code")

    def test_scrub(self):
        got = todo_rows.scrub({"rows": [{"path": "/u/someone@example.com/"}, {"path": "/ip/192.0.2.7/x"},
                                        {"path": "/fine/", "n": 3}]})
        self.assertEqual([r["path"] for r in got["rows"]], ["/u/[removed]/", "/ip/[removed]/x", "/fine/"])
        self.assertEqual(got["scrubbed"], 2)


# ------------------------------------------------------------------ the line and the kit routes

class TodoLine(TenantServer):
    def setUp(self):
        super().setUp()
        from skald.beacon_server import Limiter, Sink, make_handler
        rows_file(self.live, A, [LOST, ERRORS])
        rows_file(self.live, B, [BETA])
        sink = Sink(self.config, self.live / "beacon")
        sink.config_path = self.config_path
        self.beacon = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(sink, Limiter(), set()))
        threading.Thread(target=self.beacon.serve_forever, daemon=True).start()
        self.addCleanup(self.beacon.server_close)
        self.addCleanup(self.beacon.shutdown)
        self.cookie, self.csrf = self.session("admin@example.com")
        self.n = 0

    # the dashboard
    def agent_call(self, body, site=A, cookie=None, csrf=None):
        return self.post(f"/traffic/{site}/settings/todo-agent", body, cookie or self.cookie, csrf or self.csrf)

    def make_line(self, items=("lost-pages",)):
        got = self.agent_call({"act": "make", "items": list(items)})
        self.assertEqual(got.status, 200, got.json)
        return got.json, re.search(r"use code ([A-Za-z0-9_-]{43}) ", got.json["line"]).group(1)

    # the beacon helper, as curl
    def kit(self, path, method="GET", body=None, key=None, ua="curl/8.5.0"):
        self.n += 1
        conn = http.client.HTTPConnection("127.0.0.1", self.beacon.server_address[1], timeout=10)
        hdrs = {"User-Agent": ua, "X-Real-IP": f"198.51.100.{self.n}"}
        if key:
            hdrs[agent.REPORT_HEADER] = key
        if body is not None:
            body = json.dumps(body).encode() if not isinstance(body, bytes) else body
            hdrs["Content-Type"] = "application/json"
        conn.request(method, path, body=body, headers=hdrs)
        got = conn.getresponse()
        data = got.read().decode()
        conn.close()
        return got.status, data

    def key_of(self, code):
        return link.unseal(agent.find(self.live, code)["sealed_report"], code, agent.REPORT_LABEL)

    def audit(self, action):
        db = self.db()
        try:
            return [dict(r) for r in db.execute("SELECT actor, target, detail FROM audit WHERE action = ?",
                                                (action,))]
        finally:
            db.close()

    def test_the_line_and_its_steps(self):
        body, code = self.make_line()
        self.assertEqual(body["line"], f'fix the Skald to-do "{LOST["title"]}" for {A} — read '
                                       f'{ORIGIN}/traffic-kit/llms.txt and use code {code} (works once, 24 hours)')
        self.assertEqual(body["todos"], [{"id": "lost-pages", "kind": "lost", "title": LOST["title"]}])
        self.assertEqual(body["link_id"], agent.link_id(code))
        two, code2 = self.make_line(["lost-pages", "server-errors"])
        self.assertTrue(two["line"].startswith(f'fix the Skald to-dos for {A} (2: "{LOST["title"]}", '
                                               f'"{ERRORS["title"]}") — read '))
        self.assertEqual(two["cancelled"], 1, "the older to-do line ends")
        status, steps = self.kit(f"/traffic-kit/{code2}/steps")
        self.assertEqual(status, 200)
        for words in ("Check first", "nginx -t", "/todo/lost-pages", "/todo/server-errors", "X-Skald-Report-Key",
                      "Never change", "-H @-"):
            self.assertIn(words, steps, words)
        self.assertNotIn("SKALD_INGEST_TOKEN", steps, "a to-do line takes no sending key")
        rows = self.audit("kit.todoline")
        self.assertEqual(len(rows), 2)
        self.assertNotIn(code, json.dumps(rows))

    def test_a_new_todo_line_never_ends_a_setup_line(self):
        setup, _, _ = agent.make(self.live, A, None, None, {"base": ORIGIN}, leads=False, jobs=["script"])
        self.make_line()
        self.assertEqual(agent.status(self.live, A, agent.link_id(setup))["state"], "waiting")
        _, _, ended = agent.make(self.live, A, None, None, {"base": ORIGIN}, leads=False, jobs=["script"],
                                 replace=True)
        _, code = self.make_line()
        self.assertEqual(agent.status(self.live, A, agent.link_id(code))["state"], "waiting",
                         "a set-up line never ends a to-do line")

    def test_rows_from_the_server_file_only_its_own_site_and_todos(self):
        _, code = self.make_line()
        key = self.key_of(code)
        status, data = self.kit(f"/traffic-kit/{code}/todo/lost-pages", key=key)
        self.assertEqual(status, 200, data)
        got = json.loads(data)
        self.assertEqual(got["site"], A)
        self.assertEqual([r["path"] for r in got["rows"]], ["/old-pricing/", "/gone/", "/u/[removed]/"])
        self.assertEqual((got["rows_total"], got["scrubbed"]), (3, 1))
        self.assertNotIn("/beta-only/", data, "never another site's rows")
        self.assertEqual(self.kit(f"/traffic-kit/{code}/todo/server-errors", key=key)[0], 404,
                         "a to-do the line does not carry")
        self.assertEqual(self.kit(f"/traffic-kit/{code}/todo/lost-pages")[0], 403, "no report key")
        self.assertEqual(self.kit(f"/traffic-kit/{code}/todo/lost-pages", key="x" * 32)[0], 403)
        self.assertEqual(self.kit(f"/traffic-kit/{code}/todo/lost-pages", key=key,
                                  ua="Mozilla/5.0 (compatible; Claude-User/1.0)")[0], 403, "a web reader")
        # A site of another organisation: the dashboard refuses to make its line.
        self.assertIn(self.agent_call({"act": "make", "items": ["lost-pages"]}, site=B).status, (403, 404))

    def test_expiry_and_cancel_answer_410(self):
        body, code = self.make_line()
        key = self.key_of(code)
        got = self.agent_call({"act": "cancel", "link_id": body["link_id"]})
        self.assertEqual((got.status, got.json["state"]), (200, "cancelled"))
        self.assertEqual(self.kit(f"/traffic-kit/{code}/todo/lost-pages", key=key)[0], 410)
        self.assertEqual(self.kit(f"/traffic-kit/{code}/fix", "POST", {"id": "lost-pages", "state": "done"},
                                  key=key)[0], 410)
        _, code = self.make_line()
        key = self.key_of(code)
        later = time.time() + 25 * 3600
        with mock.patch("time.time", return_value=later):
            self.assertEqual(self.kit(f"/traffic-kit/{code}/todo/lost-pages", key=key)[0], 410)

    def test_done_marks_the_todo_and_the_recheck_starts(self):
        body, code = self.make_line(["lost-pages", "server-errors"])
        key = self.key_of(code)
        change = "location = /old-pricing/ { return 301 /pricing/; }\n"
        status, data = self.kit(f"/traffic-kit/{code}/fix", "POST",
                                {"id": "lost-pages", "state": "done", "change": change,
                                 "files": ["deploy/nginx/site.conf"], "left": [{"row": "/gone/", "why": "asked first"}],
                                 "notes": "Tested with nginx -t."}, key=key)
        self.assertEqual(status, 200, data)
        self.assertEqual(json.loads(data)["marked_done"], True)
        status, data = self.kit(f"/traffic-kit/{code}/fix", "POST",
                                {"id": "server-errors", "state": "left", "notes": "The route is not in this code."}, key=key)
        self.assertEqual((status, json.loads(data)["marked_done"]), (200, False))
        db = self.db()
        try:
            marks = todo_marks.current(db, A)
            fixes = todo_marks.fixes(db, A)
        finally:
            db.close()
        self.assertEqual(marks["lost-pages"]["state"], "done")
        self.assertNotIn("server-errors", marks, "left: stays open")
        self.assertEqual(fixes["lost-pages"]["change"], change)
        self.assertEqual(fixes["lost-pages"]["link_id"], body["link_id"])
        rows = self.audit("todo.fixed")
        self.assertEqual({r["actor"] for r in rows}, {"ai-agent"})
        self.assertNotIn("return 301", json.dumps(rows), "the change is never in the audit log")
        # The dashboard sees the report, and the mark (so the re-check runs).
        got = self.agent_call({"act": "status", "link_id": body["link_id"]})
        self.assertEqual(set(got.json["reports"]), {"lost-pages", "server-errors"})
        page = self.call("GET", f"/traffic/{A}/settings/todos", cookie=self.cookie).json
        self.assertEqual(page["marks"]["lost-pages"]["state"], "done")
        self.assertEqual(page["fixes"]["lost-pages"]["state"], "done")
        # Unknown, bad and too big reports.
        self.assertEqual(self.kit(f"/traffic-kit/{code}/fix", "POST", {"id": "sitemap", "state": "done"}, key=key)[0], 400)
        self.assertEqual(self.kit(f"/traffic-kit/{code}/fix", "POST", {"id": "lost-pages", "state": "maybe"}, key=key)[0], 400)
        self.assertEqual(self.kit(f"/traffic-kit/{code}/fix", "POST", b"x" * (agent_todos.FIX_MOST + 1), key=key)[0], 413)

    def test_every_row_for_me(self):
        got = self.call("GET", f"/traffic/{A}/settings/todo-rows?item=lost-pages", cookie=self.cookie)
        self.assertEqual(got.status, 200, got.json)
        self.assertEqual(got.json["todo"]["rows_total"], 3)
        self.assertEqual(self.call("GET", f"/traffic/{A}/settings/todo-rows?item=nope", cookie=self.cookie).status, 404)

    def test_a_viewer_cannot_make_a_line(self):
        cookie, csrf = self.session("viewer@example.com")
        self.assertEqual(self.agent_call({"act": "make", "items": ["lost-pages"]}, cookie=cookie, csrf=csrf).status, 403)

    @unittest.skipIf(shutil.which("curl") is None, "curl is not installed")
    def test_the_steps_run_as_written_under_bash(self):
        _, code = self.make_line()
        port = self.beacon.server_address[1]
        _, steps = self.kit(f"/traffic-kit/{code}/steps")
        here = f"http://127.0.0.1:{port}"
        cmds = [line.strip() for line in steps.replace(ORIGIN, here).splitlines() if line.startswith("    ")]
        take = next(c for c in cmds if c.startswith("umask 077 && mkdir -p ~/.config/skald && curl"))
        fetch = next(c for c in cmds if "/todo/lost-pages" in c)
        build = next(c for c in cmds if c.startswith("python3 -c 'import json,sys; L="))
        send = next(c for c in cmds if c.startswith("grep '^SKALD_REPORT_KEY='") and "--data-binary" in c)
        build = build.replace("'<id>'", "'lost-pages'").replace("'<state>'", "'partly'").replace("'<notes>'", "'One row left.'")
        home = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, home, True)
        env_dir = home / ".config" / "skald"
        script = "\n".join([
            "set -e", take, fetch,
            f"printf 'location = /old-pricing/ {{ return 301 /pricing/; }}\\n' > {env_dir}/{A}.change.txt",
            f"printf '/gone/\\tno live page close to it\\n' > {env_dir}/{A}.left.tsv",
            build, send, ""])
        got = subprocess.run(["bash", "-c", script], capture_output=True, text=True,
                             env={**os.environ, "HOME": str(home)}, timeout=60)
        self.assertEqual(got.returncode, 0, got.stderr + got.stdout)
        self.assertEqual(got.stdout.count("HTTP 200"), 3, got.stdout)
        self.assertIn('"marked_done": false', got.stdout)
        keys = env_dir / f"{A}.env"
        self.assertEqual(stat.S_IMODE(keys.stat().st_mode), 0o600)
        self.assertEqual({line.split("=")[0] for line in keys.read_text().splitlines() if line and not line.startswith("#")},
                         {"SKALD_SITE", "SKALD_REPORT_KEY"})
        rows = env_dir / f"{A}.todo-lost-pages.json"
        self.assertEqual(stat.S_IMODE(rows.stat().st_mode), 0o600)
        self.assertEqual(json.loads(rows.read_text())["rows_total"], 3)
        key = next(line.split("=", 1)[1] for line in keys.read_text().splitlines() if line.startswith("SKALD_REPORT_KEY="))
        self.assertNotIn(key, script + got.stdout + got.stderr, "the key is never on a command line")
        self.assertIsNone(agent.find(self.live, code)["sealed_report"], "taken once: no seal left")
        db = self.db()
        try:
            fix = todo_marks.fixes(db, A)["lost-pages"]
        finally:
            db.close()
        self.assertEqual((fix["state"], fix["left"]), ("partly", [{"row": "/gone/", "why": "no live page close to it"}]))


# ------------------------------------------------------------------ the MCP tools

def rpc(name, args):
    return {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": args}}


class McpTools(TenantServer):
    def setUp(self):
        super().setUp()
        self.config["mcp"] = {"enabled": True}
        rows_file(self.live, A, [LOST, ERRORS])
        rows_file(self.live, B, [BETA])
        self.owner = self.uids["owner@example.com"]

    def make(self, scopes, sites=(A,), org=None, actor=None):
        db = self.db()
        try:
            return apitokens.create(db, (org or self.alpha)["id"], "agent", sites=list(sites), scopes=scopes,
                                    actor=self.owner if actor is None else actor)
        finally:
            db.close()

    def result(self, token, name, args):
        got = self.call("POST", "/traffic-mcp", body=rpc(name, args), headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(got.status, 200, got.json)
        return got.json["result"]

    def refused(self, token, name, args, words):
        got = self.result(token, name, args)
        self.assertTrue(got["isError"], got)
        self.assertIn(words, got["content"][0]["text"])

    def test_fix_todo_hands_every_row_and_the_steps(self):
        token = self.make(("mcp",))
        listed = self.result(token, "fix_todo", {"site": A})
        self.assertEqual([t["id"] for t in listed["structuredContent"]["todos"]], ["lost-pages", "server-errors"])
        got = self.result(token, "fix_todo", {"site": A, "id": "lost-pages"})
        self.assertFalse(got["isError"], got)
        self.assertEqual(got["structuredContent"]["rows_total"], 3)
        self.assertIn("/u/[removed]/", got["content"][0]["text"])
        self.assertIn("mark_todo_done", got["structuredContent"]["steps"])
        self.assertIn("nginx -t", got["structuredContent"]["steps"])
        page = self.result(token, "fix_todo", {"site": A, "id": "lost-pages", "offset": 2, "limit": 1})
        self.assertEqual(page["structuredContent"]["rows"], [{"path": "/u/[removed]/", "people": 1, "target": None}])
        self.refused(token, "fix_todo", {"site": B, "id": "lost-pages"}, f"You may not read {B}")
        self.refused(token, "fix_todo", {"site": A, "id": "sitemap"}, "has no to-do 'sitemap'")

    def test_mark_todo_done_refusals_and_the_audit_row(self):
        args = {"site": A, "id": "lost-pages", "state": "done", "change": "location = /old-pricing/ { return 301 /pricing/; }"}
        self.refused(self.make(("mcp",)), "mark_todo_done", args, "setup scope")
        self.refused(self.make(("mcp", "setup"), sites=(B,), org=self.beta, actor="cli"), "mark_todo_done", args,
                     "setup scope")
        setup = self.make(("mcp", "setup"))
        self.refused(setup, "mark_todo_done", {**args, "id": "sitemap"}, "has no to-do 'sitemap'")
        self.refused(setup, "mark_todo_done", {**args, "state": "maybe"}, "done, partly, left")
        got = self.result(setup, "mark_todo_done", args)
        self.assertFalse(got["isError"], got)
        self.assertTrue(got["structuredContent"]["marked_done"])
        db = self.db()
        try:
            self.assertEqual(todo_marks.current(db, A)["lost-pages"]["state"], "done")
            self.assertTrue(todo_marks.fixes(db, A)["lost-pages"]["by"].startswith("mcp:"))
            rows = [dict(r) for r in db.execute("SELECT actor, target, detail FROM audit WHERE action = 'mcp.todo_done'")]
        finally:
            db.close()
        self.assertEqual(len(rows), 1)
        self.assertIn("to-do lost-pages; done; marked done", rows[0]["detail"])
        self.assertNotIn("return 301", json.dumps(rows))
        again = self.result(setup, "mark_todo_done", args)
        self.assertFalse(again["structuredContent"]["marked_done"], "done already: no second mark")


# ------------------------------------------------------------------ the mail

class NoCodeInMail(unittest.TestCase):
    def test_the_mail_links_to_fix_this_never_a_code(self):
        it = {"item": "lost-pages", "title": "Send old pages somewhere useful.", "todo": "Redirect each.",
              "link": "https://stats.example.com/traffic/example.com/#overview/insights?todo=lost-pages",
              "fix": "https://stats.example.com/traffic/example.com/#overview/insights?todo=lost-pages&fix=1&fixby=agent"}
        line = summary_mail._line(it, "New: ")
        self.assertIn("Fix it with your AI agent: https://stats.example.com/traffic/example.com/"
                      "#overview/insights?todo=lost-pages&fix=1&fixby=agent", line)
        self.assertNotIn("use code", line)
        self.assertNotIn("/traffic-kit/", line)
        import inspect
        src = inspect.getsource(summary_mail)
        self.assertNotIn("make_todo_line", src, "the mail never makes a line")
        self.assertNotIn("agent.make", src)


if __name__ == "__main__":
    unittest.main()
