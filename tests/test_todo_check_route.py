"""Insights' "Check again" through the helper (2.44): POST settings/todo-check, GET
settings/todos' `checks`, and the check that runs after an AI agent's "done" report.

Pinned: owners and admins only, CSRF, a viewer reads the result but cannot press it,
an audit row "todo.checked" without a row's address, a to-do not on the list is 404, the
fixed mark and the second count in GET, the agent's report followed by the same check
(by "your AI agent"). Fake fetches only (no network). Test data: example names,
RFC 5737 addresses.
"""
from __future__ import annotations

import http.client
import json
import re
import sys
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from auth_support import A  # noqa: E402
from ingest_support import TenantServer  # noqa: E402
from test_todo_agent import ERRORS, LOST, rows_file  # noqa: E402
from test_todo_check import FakeSite  # noqa: E402

from skald import site_fetch, todo_check  # noqa: E402
from skald.kit import agent, link  # noqa: E402


class Route(TenantServer):
    def setUp(self):
        super().setUp()
        rows_file(self.live, A, [LOST, ERRORS])
        self.cookie, self.csrf = self.session("admin@example.com")
        self.site = FakeSite({"/old-pricing/": (301, "/pricing/"), "/pricing/": (200, None)}, default=(410, None))
        for p in (mock.patch("skald.stack.reserved", lambda host: False),
                  mock.patch.object(todo_check, "_default_fetch", self.site),
                  mock.patch.object(todo_check, "GAP", 0)):
            p.start()
            self.addCleanup(p.stop)

    def check(self, item="lost-pages", start=0, cookie=None, csrf=None):
        return self.post(f"/traffic/{A}/settings/todo-check", {"item": item, "start": start},
                         cookie or self.cookie, csrf if csrf is not None else self.csrf)

    def audit(self, action):
        db = self.db()
        try:
            return [dict(r) for r in db.execute("SELECT actor, target, detail FROM audit WHERE action = ?", (action,))]
        finally:
            db.close()

    def test_an_admin_checks_and_it_is_marked_fixed(self):
        got = self.check()
        self.assertEqual(got.status, 200, got.json)
        self.assertEqual(got.json["check"]["verdict"], "fixed")
        self.assertEqual(got.json["check"]["by"], "admin@example.com")
        self.assertEqual(got.json["marks"]["lost-pages"]["state"], "fixed")
        self.assertEqual(got.json["checks_withheld"], {})
        self.assertTrue(all(url.startswith(f"https://{A}/") for _, url in self.site.asked))
        rows = self.audit("todo.checked")
        self.assertEqual([r["actor"] for r in rows], ["admin@example.com"])
        self.assertNotIn("/old-pricing/", json.dumps(rows), "no address in the audit log")
        page = self.call("GET", f"/traffic/{A}/settings/todos", cookie=self.cookie).json
        self.assertEqual(page["checks"]["lost-pages"]["verdict"], "fixed")
        # Pressed again at once: one start a minute.
        self.assertEqual(self.check().status, 429)

    def test_a_viewer_sees_the_result_not_the_button(self):
        self.check()
        cookie, csrf = self.session("viewer@example.com")
        self.assertEqual(self.check("server-errors", cookie=cookie, csrf=csrf).status, 403)
        page = self.call("GET", f"/traffic/{A}/settings/todos", cookie=cookie).json
        self.assertFalse(page["can_mark"])
        self.assertEqual(page["checks"]["lost-pages"]["verdict"], "fixed")

    def test_csrf_and_bad_asks(self):
        self.assertEqual(self.check(csrf="").status, 403)
        self.assertEqual(self.check("sitemap").status, 404, "not on the list")
        self.assertEqual(self.check("Bad Id").status, 400)
        self.assertEqual(self.check(start=-1).status, 400)
        self.assertEqual(self.call("GET", f"/traffic/{A}/settings/todo-check", cookie=self.cookie).status, 405)


class AfterAgent(TenantServer):
    def setUp(self):
        super().setUp()
        from skald.beacon_server import Limiter, Sink, make_handler
        rows_file(self.live, A, [LOST, ERRORS])
        sink = Sink(self.config, self.live / "beacon")
        sink.config_path = self.config_path
        self.beacon = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(sink, Limiter(), set()))
        threading.Thread(target=self.beacon.serve_forever, daemon=True).start()
        self.addCleanup(self.beacon.server_close)
        self.addCleanup(self.beacon.shutdown)
        self.cookie, self.csrf = self.session("admin@example.com")
        self.site = FakeSite({"/gone/": (404, None)}, default=(410, None))
        for p in (mock.patch("skald.stack.reserved", lambda host: False),
                  mock.patch.object(todo_check, "_default_fetch", self.site),
                  mock.patch.object(todo_check, "RUNNER", lambda fn: fn()),
                  mock.patch.object(todo_check, "GAP", 0)):
            p.start()
            self.addCleanup(p.stop)

    def kit(self, path, body, key):
        conn = http.client.HTTPConnection("127.0.0.1", self.beacon.server_address[1], timeout=10)
        conn.request("POST", path, body=json.dumps(body).encode(), headers={
            "User-Agent": "curl/8.5.0", "X-Real-IP": "198.51.100.7", agent.REPORT_HEADER: key,
            "Content-Type": "application/json"})
        got = conn.getresponse()
        data = got.read().decode()
        conn.close()
        return got.status, data

    def test_a_done_report_is_checked_at_once(self):
        made = self.post(f"/traffic/{A}/settings/todo-agent", {"act": "make", "items": ["lost-pages"]},
                         self.cookie, self.csrf).json
        code = re.search(r"use code ([A-Za-z0-9_-]{43}) ", made["line"]).group(1)
        key = link.unseal(agent.find(self.live, code)["sealed_report"], code, agent.REPORT_LABEL)
        status, _ = self.kit(f"/traffic-kit/{code}/fix", {"id": "lost-pages", "state": "done"}, key)
        self.assertEqual(status, 200)
        page = self.call("GET", f"/traffic/{A}/settings/todos", cookie=self.cookie).json
        got = page["checks"]["lost-pages"]
        self.assertEqual((got["verdict"], got["by"], got["by_who"]), ("partly", "your AI agent", "ai-agent"))
        self.assertTrue(got["words"].startswith("1 of 2 addresses still answer 404"), got["words"])
        self.assertIn("1 address was not asked", got["words"])
        self.assertEqual(page["marks"]["lost-pages"]["state"], "done", "the agent's mark stays; not fixed")
        self.assertEqual(len(self.site.asked), 2, "the scrubbed address is never asked")

    def test_an_unreachable_site_keeps_the_report(self):
        self.site.default = site_fetch.Unreachable("it did not answer in time")
        self.site.pages = {}
        made = self.post(f"/traffic/{A}/settings/todo-agent", {"act": "make", "items": ["lost-pages"]},
                         self.cookie, self.csrf).json
        code = re.search(r"use code ([A-Za-z0-9_-]{43}) ", made["line"]).group(1)
        key = link.unseal(agent.find(self.live, code)["sealed_report"], code, agent.REPORT_LABEL)
        self.assertEqual(self.kit(f"/traffic-kit/{code}/fix", {"id": "lost-pages", "state": "done"}, key)[0], 200)
        page = self.call("GET", f"/traffic/{A}/settings/todos", cookie=self.cookie).json
        self.assertEqual(page["checks"]["lost-pages"]["verdict"], "error")
        self.assertEqual(page["fixes"]["lost-pages"]["state"], "done")


if __name__ == "__main__":
    unittest.main()
