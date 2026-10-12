"""MCP protocol (skald/mcp/protocol.py): JSON-RPC 2.0, the lifecycle,
version negotiation, errors, batches, notifications, the tool, resource and
prompt listings."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from skald.mcp import protocol  # noqa: E402
from skald.mcp.data import Context  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
NAMES = {"list_sites", "overview", "breakdown", "top_pages", "ai_activity", "leads", "funnel",
         "compare", "page_story", "live_today", "data_quality", "site_health", "conversions",
         "find_person"}


def rpc(method, params=None, mid=1):
    msg = {"jsonrpc": "2.0", "id": mid, "method": method}
    if params is not None:
        msg["params"] = params
    return msg


class Protocol(unittest.TestCase):
    def setUp(self):
        self.ctx = Context(None)

    def ask(self, message):
        return protocol.handle(message, self.ctx)

    def code(self, message):
        return self.ask(message)["error"]["code"]

    def test_initialize_answers_our_version_and_server(self):
        got = self.ask(rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                          "clientInfo": {"name": "t", "version": "1"}}))
        r = got["result"]
        self.assertEqual((got["jsonrpc"], got["id"]), ("2.0", 1))
        self.assertEqual(r["protocolVersion"], "2025-06-18")
        self.assertEqual(r["serverInfo"]["name"], "skald")
        self.assertEqual(r["serverInfo"]["version"], (ROOT / "VERSION").read_text().strip())
        for cap in ("tools", "resources", "prompts"):
            self.assertIs(r["capabilities"][cap]["listChanged"], False)
        self.assertIn("upper bound on people", r["instructions"])

    def test_older_and_unknown_versions_get_the_one_we_support(self):
        for asked in ("2025-03-26", "2024-11-05", "2099-01-01"):
            with self.subTest(asked=asked):
                got = self.ask(rpc("initialize", {"protocolVersion": asked}))
                self.assertEqual(got["result"]["protocolVersion"], "2025-06-18")

    def test_initialize_without_a_version_is_invalid_params(self):
        self.assertEqual(self.code(rpc("initialize", {})), -32602)

    def test_notifications_get_no_answer(self):
        self.assertIsNone(self.ask({"jsonrpc": "2.0", "method": "notifications/initialized"}))
        self.assertIsNone(self.ask({"jsonrpc": "2.0", "method": "notifications/cancelled",
                                    "params": {"requestId": 3}}))
        self.assertIsNone(self.ask({"jsonrpc": "2.0", "method": "no/such/notification"}))

    def test_a_clients_own_response_gets_no_answer(self):
        self.assertIsNone(self.ask({"jsonrpc": "2.0", "id": 9, "result": {}}))

    def test_ping(self):
        self.assertEqual(self.ask(rpc("ping", mid="a"))["result"], {})
        self.assertEqual(self.ask(rpc("ping", mid="a"))["id"], "a")

    def test_unknown_method(self):
        got = self.ask(rpc("tools/delete"))
        self.assertEqual((got["id"], got["error"]["code"]), (1, -32601))

    def test_invalid_requests(self):
        self.assertEqual(self.code({"id": 1, "method": "ping"}), -32600)          # no jsonrpc
        self.assertEqual(self.code({"jsonrpc": "1.0", "id": 1, "method": "ping"}), -32600)
        self.assertEqual(self.code({"jsonrpc": "2.0", "id": 1, "method": 5}), -32600)
        self.assertEqual(self.code({"jsonrpc": "2.0", "id": None, "method": "ping"}), -32600)
        self.assertEqual(self.code({"jsonrpc": "2.0", "id": True, "method": "ping"}), -32600)
        self.assertEqual(self.code("ping"), -32600)
        self.assertEqual(self.code([]), -32600)
        self.assertEqual(self.code(rpc("ping", ["not", "an", "object"])), -32602)

    def test_batch_answers_requests_only_in_order(self):
        got = self.ask([rpc("ping", mid=1), {"jsonrpc": "2.0", "method": "notifications/x"},
                        rpc("nope", mid=2), 7])
        self.assertEqual([g.get("id") for g in got], [1, 2, None])
        self.assertIn("result", got[0])
        self.assertEqual(got[1]["error"]["code"], -32601)
        self.assertEqual(got[2]["error"]["code"], -32600)
        self.assertIsNone(self.ask([{"jsonrpc": "2.0", "method": "notifications/initialized"}]))

    def test_tools_list_has_every_tool_with_a_schema(self):
        tools = self.ask(rpc("tools/list"))["result"]["tools"]
        self.assertEqual({t["name"] for t in tools}, NAMES)
        for t in tools:
            with self.subTest(tool=t["name"]):
                self.assertEqual(t["inputSchema"]["type"], "object")
                self.assertTrue(t["description"])
                self.assertIs(t["annotations"]["readOnlyHint"], True)
                self.assertNotIn("run", t)
                for name, p in t["inputSchema"]["properties"].items():
                    self.assertTrue(p.get("description"), name)
                    if name in ("from", "to", "a_from", "a_to", "b_from", "b_to"):
                        self.assertEqual(p["pattern"], r"^\d{4}-\d{2}-\d{2}$")
        dims = next(t for t in tools if t["name"] == "breakdown")["inputSchema"]
        for d in ("country", "source", "campaign", "landing", "device", "browser", "hour"):
            self.assertIn(d, dims["properties"]["dimension"]["enum"])
        self.assertEqual(dims["required"], ["dimension"])

    def test_tools_call_errors(self):
        self.assertEqual(self.code(rpc("tools/call", {"name": "drop_tables"})), -32602)
        self.assertEqual(self.code(rpc("tools/call", {"arguments": {}})), -32602)
        self.assertEqual(self.code(rpc("tools/call", {"name": "overview", "arguments": [1]})),
                         -32602)

    def test_a_bad_argument_is_a_tool_error_not_a_protocol_error(self):
        got = self.ask(rpc("tools/call", {"name": "overview", "arguments": {"colour": "red"}}))
        self.assertIs(got["result"]["isError"], True)
        self.assertIn("Unknown argument", got["result"]["content"][0]["text"])

    def test_resources(self):
        listed = self.ask(rpc("resources/list"))["result"]["resources"]
        uris = {r["uri"] for r in listed}
        self.assertTrue({"skald://docs/api", "skald://docs/counting"} <= uris)
        got = self.ask(rpc("resources/read", {"uri": "skald://docs/api"}))["result"]
        self.assertEqual(got["contents"][0]["mimeType"], "text/markdown")
        self.assertIn("read-only API", got["contents"][0]["text"])
        got = self.ask(rpc("resources/read", {"uri": "skald://docs/counting"}))["result"]
        self.assertIn("upper bound on humans", got["contents"][0]["text"])
        self.assertEqual(self.code(rpc("resources/read", {"uri": "skald://nothing"})), -32002)
        self.assertEqual(self.code(rpc("resources/read", {})), -32602)
        templates = self.ask(rpc("resources/templates/list"))["result"]["resourceTemplates"]
        self.assertEqual(templates[0]["uriTemplate"], "skald://sites/{site}/overview")

    def test_prompts(self):
        listed = self.ask(rpc("prompts/list"))["result"]["prompts"]
        self.assertEqual([p["name"] for p in listed], ["weekly_report"])
        got = self.ask(rpc("prompts/get", {"name": "weekly_report",
                                           "arguments": {"site": "example.com"}}))["result"]
        text = got["messages"][0]["content"]["text"]
        self.assertEqual(got["messages"][0]["role"], "user")
        for words in ("example.com", "visits (an upper bound on people)", "withheld",
                      "never", "overview", "compare"):
            self.assertIn(words, text)
        self.assertEqual(self.code(rpc("prompts/get", {"name": "monthly"})), -32602)
        self.assertEqual(self.code(rpc("prompts/get", {"name": "weekly_report",
                                                       "arguments": {"site": 3}})), -32602)

    def test_an_internal_failure_is_32603_without_details(self):
        def boom(params, ctx):
            raise RuntimeError("secret detail")
        from unittest import mock
        import io
        with mock.patch.dict(protocol.METHODS, {"ping": boom}), \
                mock.patch("sys.stderr", io.StringIO()):
            got = self.ask(rpc("ping"))
        self.assertEqual(got["error"], {"code": -32603, "message": "Internal error"})


if __name__ == "__main__":
    unittest.main()
