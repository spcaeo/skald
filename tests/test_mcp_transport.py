"""MCP transports: POST /traffic-mcp (skald/mcp/http.py) on a tiny
ThreadingHTTPServer with organisation tokens in a real accounts file, and
`skald mcp` over stdio in a subprocess.

Pinned: the switch, POST only (405), foreign Origins refused (403), a
bearer token with the mcp scope (401 + WWW-Authenticate otherwise), the
64 KiB limit, parse errors, 202 for notifications, a tools/call round trip,
site isolation between organisations, addresses only with read_private;
stdio answers one JSON line per request, nothing else on stdout."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import unittest
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_mcp_support import OTHER, SITE, Fixture  # noqa: E402
from skald import accounts  # noqa: E402
from skald.mcp.http import handle_http, is_mcp  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
FX = None
ORIGIN = "https://www.example.com"


def setUpModule():
    global FX
    FX = Fixture()


def tearDownModule():
    FX.close()


class Http(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.live = FX.root / "lib"
        cls.live.mkdir(exist_ok=True)
        db = accounts.connect(cls.live / "accounts.sqlite")
        try:
            a = accounts.create_org(db, "Org A", "test")["id"]
            b = accounts.create_org(db, "Org B", "test")["id"]
            accounts.assign_site(db, SITE, a, "test")
            accounts.assign_site(db, OTHER, b, "test")
            make = accounts.apitokens.create
            cls.token = make(db, a, "agent", scopes=("mcp",))
            cls.private = make(db, a, "ops agent", scopes=("mcp", "read_private"))
            cls.read_only = make(db, a, "sheet", scopes=("read",))
            cls.token_b = make(db, b, "b agent", scopes=("mcp",))
        finally:
            db.close()
        cls.config = {"mcp": {"enabled": True}, "access": {"mode": "sessions"}}
        test = cls

        class Handler(BaseHTTPRequestHandler):
            def _mcp(self):
                if not is_mcp(self.path):
                    self.send_response(404)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                handle_http(self, test.config, test.live, FX.out, history_path=FX.box.db,
                            allowed_origins={ORIGIN})

            do_POST = do_GET = do_DELETE = _mcp

            def log_message(self, *a):
                pass

        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        self.config.clear()
        self.config.update({"mcp": {"enabled": True}, "access": {"mode": "sessions"}})

    def post(self, body, token="mine", headers=None, method="POST", raw=None):
        token = self.token if token == "mine" else token
        conn = HTTPConnection("127.0.0.1", self.server.server_address[1], timeout=10)
        data = raw if raw is not None else json.dumps(body).encode()
        h = {"Content-Type": "application/json",
             "Accept": "application/json, text/event-stream"}
        if token:
            h["Authorization"] = f"Bearer {token}"
        h.update(headers or {})
        conn.request(method, "/traffic-mcp", body=data if method == "POST" else None,
                     headers=h)
        r = conn.getresponse()
        payload = r.read()
        conn.close()
        return r.status, dict(r.getheaders()), (json.loads(payload) if payload else None)

    def call(self, name, token="mine", **args):
        code, _, body = self.post({"jsonrpc": "2.0", "id": 7, "method": "tools/call",
                                   "params": {"name": name, "arguments": args}}, token)
        self.assertEqual(code, 200)
        return body["result"]

    def test_initialize_round_trip(self):
        code, headers, body = self.post(
            {"jsonrpc": "2.0", "id": 1, "method": "initialize",
             "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                        "clientInfo": {"name": "test", "version": "1"}}},
            headers={"MCP-Protocol-Version": "2025-06-18"})
        self.assertEqual(code, 200)
        self.assertEqual(headers["Content-Type"], "application/json")
        self.assertEqual(body["result"]["protocolVersion"], "2025-06-18")
        self.assertEqual(body["result"]["serverInfo"]["name"], "skald")

    def test_tools_call_round_trip(self):
        r = self.call("overview", site=SITE)
        self.assertIs(r["isError"], False)
        self.assertIn("Visits (an upper bound on people)", r["content"][0]["text"])
        self.assertEqual(r["structuredContent"]["site"], SITE)
        listed = self.call("list_sites")
        self.assertEqual([s["site"] for s in listed["structuredContent"]["sites"]], [SITE])

    def test_get_and_other_methods_are_405(self):
        for method in ("GET", "DELETE"):
            code, headers, _ = self.post(None, method=method)
            self.assertEqual(code, 405, method)
            self.assertEqual(headers["Allow"], "POST")

    def test_no_or_bad_token_is_401_with_www_authenticate(self):
        ping = {"jsonrpc": "2.0", "id": 1, "method": "ping"}
        for token in (None, "skald_nope_nope", "not-a-token", self.read_only):
            with self.subTest(token=token and token[:12]):
                code, headers, body = self.post(ping, token)
                self.assertEqual(code, 401)
                self.assertTrue(headers["WWW-Authenticate"].startswith("Bearer"))
                self.assertEqual(body["error"]["code"], -32600)
        code, _, body = self.post(ping, self.read_only)
        self.assertIn("no mcp scope", body["error"]["message"])
        self.assertNotIn(self.read_only.split("_", 2)[2], json.dumps(body))

    def test_a_revoked_token_is_401(self):
        db = accounts.connect(self.live / "accounts.sqlite")
        try:
            org = accounts.org_of_site(db, SITE)["id"]
            gone = accounts.apitokens.create(db, org, "gone", scopes=("mcp",))
            accounts.apitokens.revoke(db, org, gone.split("_")[1], "test")
        finally:
            db.close()
        self.assertEqual(self.post({"jsonrpc": "2.0", "id": 1, "method": "ping"}, gone)[0],
                         401)

    def test_a_foreign_origin_is_refused(self):
        ping = {"jsonrpc": "2.0", "id": 1, "method": "ping"}
        self.assertEqual(self.post(ping, headers={"Origin": "https://evil.example.net"})[0],
                         403)
        self.assertEqual(self.post(ping, headers={"Origin": ORIGIN})[0], 200)

    def test_protocol_version_header(self):
        ping = {"jsonrpc": "2.0", "id": 1, "method": "ping"}
        self.assertEqual(self.post(ping, headers={"MCP-Protocol-Version": "1999-01-01"})[0],
                         400)
        for v in ("2025-06-18", "2025-03-26", "2024-11-05"):
            self.assertEqual(self.post(ping, headers={"MCP-Protocol-Version": v})[0], 200)

    def test_body_limit_and_parse_error(self):
        code, _, body = self.post(None, raw=b"{" + b" " * (64 * 1024))
        self.assertEqual(code, 413)
        code, _, body = self.post(None, raw=b"{not json")
        self.assertEqual((code, body["error"]["code"]), (400, -32700))

    def test_notifications_only_is_202_without_a_body(self):
        code, _, body = self.post({"jsonrpc": "2.0", "method": "notifications/initialized"})
        self.assertEqual((code, body), (202, None))

    def test_batch(self):
        code, _, body = self.post([{"jsonrpc": "2.0", "id": 1, "method": "ping"},
                                   {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}])
        self.assertEqual(code, 200)
        self.assertEqual([b["id"] for b in body], [1, 2])

    def test_a_token_reads_only_its_own_organisations_sites(self):
        r = self.call("overview", site=OTHER)
        self.assertIs(r["isError"], True)
        self.assertIn("not for that site", r["content"][0]["text"])
        r = self.call("overview", token=self.token_b, site=OTHER)
        self.assertIs(r["isError"], False)
        r = self.call("overview", token=self.token_b, site=SITE)
        self.assertIs(r["isError"], True)

    def test_addresses_need_read_private(self):
        r = self.call("ai_activity", site=SITE)
        self.assertIsNone(r["structuredContent"]["today_events"])
        self.assertNotIn("203.0.113.", json.dumps(r))
        r = self.call("ai_activity", token=self.private, site=SITE)
        self.assertTrue(r["structuredContent"]["today_events"][0]["ip"])

    def test_off_unless_switched_on_and_needs_sessions_mode(self):
        ping = {"jsonrpc": "2.0", "id": 1, "method": "ping"}
        self.config["mcp"] = {"enabled": False}
        self.assertEqual(self.post(ping)[0], 404)
        self.config.update({"mcp": {"enabled": True}, "access": {"mode": "basic"}})
        code, _, body = self.post(ping)
        self.assertEqual(code, 401)
        self.assertIn("access.mode: sessions", body["error"]["message"])


class Stdio(unittest.TestCase):
    def run_ti(self, lines, *extra):
        script = ("import sys\n"
                  "from skald import cli_more\n"
                  "if 'mcp' not in cli_more.MODULES:\n"
                  "    cli_more.MODULES = (*cli_more.MODULES, 'mcp')\n"
                  "from skald import cli\n"
                  "sys.exit(cli.main(sys.argv[1:]))\n")
        done = subprocess.run([sys.executable, "-c", script, "--config", str(FX.config),
                               "mcp", *extra],
                              input="".join(lines), capture_output=True, text=True,
                              cwd=ROOT, timeout=60, env={**os.environ, "PYTHONPATH": str(ROOT)})
        return done

    def test_round_trip(self):
        msgs = [{"jsonrpc": "2.0", "id": 1, "method": "initialize",
                 "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                            "clientInfo": {"name": "t", "version": "1"}}},
                {"jsonrpc": "2.0", "method": "notifications/initialized"},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
                {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                 "params": {"name": "overview", "arguments": {}}}]
        lines = [json.dumps(m) + "\n" for m in msgs] + ["{broken\n", "\n"]
        done = self.run_ti(lines, "--site", SITE)
        self.assertEqual(done.returncode, 0, done.stderr)
        out = [json.loads(x) for x in done.stdout.splitlines()]
        self.assertEqual([o.get("id") for o in out], [1, 2, 3, None])
        self.assertEqual(out[0]["result"]["protocolVersion"], "2025-06-18")
        # 2.39.0: setup_left, setup_line; 2.41: fix_todo, mark_todo_done
        self.assertEqual(len(out[1]["result"]["tools"]), 24)
        r = out[2]["result"]
        self.assertIs(r["isError"], False, r)
        self.assertEqual(r["structuredContent"]["site"], SITE)
        self.assertEqual(out[3]["error"]["code"], -32700)
        self.assertIn("skald mcp", done.stderr)

    def test_site_flag_limits_the_server_and_addresses_need_private(self):
        call = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                "params": {"name": "ai_activity", "arguments": {}}}
        done = self.run_ti([json.dumps(call) + "\n"], "--site", SITE)
        r = json.loads(done.stdout)["result"]
        self.assertIsNone(r["structuredContent"]["today_events"])
        done = self.run_ti([json.dumps(call) + "\n"], "--site", SITE, "--private")
        r = json.loads(done.stdout)["result"]
        self.assertTrue(r["structuredContent"]["today_events"])


if __name__ == "__main__":
    unittest.main()
