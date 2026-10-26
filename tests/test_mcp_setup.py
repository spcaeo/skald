"""The MCP set-up tools (2.39.0, skald/mcp/tools_setup.py) and the
token scope `setup` (accounts/apitokens.py), on a real helper with two
organisations (ingest_support.TenantServer: alpha.example, beta.example).

Pinned: setup_left answers the page's own checklist lines (the same GET
settings and GET integrations answers, worked out by setup_items.py) with each
agent job and its dialog's address, and "nothing left" for a finished site;
setup_line needs a token with the setup scope for exactly that site, checks
its jobs, calls kit_api.make_agent_line with the token maker as the actor and
writes an audit row without the code; only an owner or admin may make a setup
token (accounts and the token API), for one site, with mcp; a demoted maker's
token stops. RFC 5737 addresses, example.com mail."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from auth_support import A, B, ORIGIN  # noqa: E402
from ingest_support import TenantServer  # noqa: E402
from test_setup_items import FINISHED  # noqa: E402

from skald import kit_api, setup_items  # noqa: E402
from skald.accounts import apitokens  # noqa: E402
from skald.mcp import tools  # noqa: E402
from skald.mcp.data import Context  # noqa: E402

LINE = ("finish setting up Skald for alpha.example (Logs, Script tag) — read "
        "https://www.example.com/traffic-kit/llms.txt and use code k1w1-c0de (works once, "
        "24 hours)")


def rpc(name, args):
    return {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": name, "arguments": args}}


class SetupTools(TenantServer):
    def setUp(self):
        super().setUp()
        self.config["mcp"] = {"enabled": True}
        # No hook helper, whatever listens on this machine's 127.0.0.1:8766 (port 9 refuses).
        self.config.setdefault("hooks", {})["test_url"] = "http://127.0.0.1:9"
        self.owner = self.uids["owner@example.com"]

    def make(self, scopes, sites=(A,), actor=None, org=None):
        db = self.db()
        try:
            return apitokens.create(db, (org or self.alpha)["id"], "agent", sites=list(sites),
                                    scopes=scopes, actor=self.owner if actor is None else actor)
        finally:
            db.close()

    def mcp(self, token, name, args):
        return self.call("POST", "/traffic-mcp", body=rpc(name, args),
                         headers={"Authorization": f"Bearer {token}"})

    def result(self, token, name, args) -> dict:
        got = self.mcp(token, name, args)
        self.assertEqual(got.status, 200, got.json)
        return got.json["result"]

    def refused(self, token, name, args, words):
        got = self.result(token, name, args)
        self.assertTrue(got["isError"], got)
        self.assertIn(words, got["content"][0]["text"])

    def audit(self, action):
        db = self.db()
        try:
            return [dict(r) for r in db.execute(
                "SELECT actor, target, detail FROM audit WHERE action = ?", (action,))]
        finally:
            db.close()

    # ------------------------------------------------------------ setup_left

    def test_setup_left_on_a_fresh_site_is_the_pages_checklist(self):
        cookie, _ = self.session("owner@example.com")
        page = self.call("GET", f"/traffic/{A}/settings", cookie=cookie).json
        integ = self.call("GET", f"/traffic/{A}/integrations?site={A}", cookie=cookie).json
        self.assertTrue(page["ok"] and integ["ok"], (page, integ))
        lines = setup_items.items(None, status=integ["status"], tools=integ["tools"],
                                  settings=page["settings"], waiting=page["mail_waiting"])
        token = self.make(("mcp",))
        got = self.result(token, "setup_left", {"site": A})
        self.assertFalse(got["isError"], got)
        left = got["structuredContent"]["left"]
        self.assertEqual([(i["id"], i["state"], i["says"]) for i in left],
                         [(i["id"], i["state"], i["says"]) for i in lines
                          if i["state"] != "done"])
        by = {i["id"]: i for i in left}
        self.assertEqual(by["logs"]["state"], "todo")
        self.assertEqual(by["logs"]["job"], "logs")
        self.assertEqual(by["logs"]["dialog"], f"{ORIGIN}/traffic/{A}/#settings/api?setup=logs")
        self.assertEqual(by["mail"]["job"], None)
        self.assertEqual(by["mail"]["dialog"], f"{ORIGIN}/traffic/{A}/#settings/api?setup=mail")
        self.assertEqual(by["privacy"]["job"], "privacy")
        self.assertFalse(got["structuredContent"]["done"])
        self.assertEqual(got["structuredContent"]["jobs"][0], "logs")
        self.assertIn("AI agent job: logs", got["content"][0]["text"])

    def test_setup_left_reads_only_the_tokens_own_sites(self):
        other = self.make(("mcp",), sites=(B,), org=self.beta, actor="cli")
        self.refused(other, "setup_left", {"site": A}, f"You may not read {A}")
        self.refused(self.make(("mcp",)), "setup_left", {"site": "kiwi.example"},
                     "You may not read kiwi.example")

    # ------------------------------------------------------------ setup_line

    def fake(self, calls, answer=None, error=None):
        def make_agent_line(db, config, org, site, jobs, actor, **kw):
            calls.append({"org": org["id"], "site": site, "jobs": jobs, "actor": actor, **kw})
            if error:
                raise ValueError(error)
            return answer or {"line": LINE, "llms_url": f"{ORIGIN}/traffic-kit/llms.txt",
                              "steps_url": f"{ORIGIN}/traffic-kit/k1w1-c0de/steps",
                              "expires_at": "2026-10-12T14:00:00Z", "token_id": "0a1b2c3d",
                              "link_id": "0123456789abcdef", "cancelled": 1, "jobs": jobs}
        return mock.patch.object(kit_api, "make_agent_line", make_agent_line, create=True)

    def test_setup_line_makes_the_line_as_the_tokens_maker(self):
        token = self.make(("mcp", "setup"))
        calls = []
        with self.fake(calls):
            got = self.result(token, "setup_line", {"site": A, "jobs": ["script", "logs", "logs"]})
        self.assertFalse(got["isError"], got)
        self.assertEqual(len(calls), 1)
        call = calls[0]
        self.assertEqual((call["org"], call["site"], call["jobs"], call["actor"]),
                         (self.alpha["id"], A, ["logs", "script"], str(self.owner)))
        self.assertEqual(call["origin"], ORIGIN)
        self.assertEqual(call["allowed"], {ORIGIN})
        self.assertEqual(Path(call["config_path"]), self.config_path)
        data = got["structuredContent"]
        self.assertEqual(data["line"], LINE)
        self.assertEqual(data["jobs"], ["logs", "script"])
        self.assertEqual(data["link_id"], "0123456789abcdef")
        self.assertNotIn("token_id", data)
        self.assertIn(LINE, got["content"][0]["text"])
        self.assertIn("ended 1 older line", got["content"][0]["text"])
        rows = self.audit("mcp.setup_line")
        self.assertEqual(len(rows), 1)
        tid = token.split("_", 2)[1]
        self.assertEqual((rows[0]["actor"], rows[0]["target"]), (str(self.owner), A))
        self.assertIn(f"token {tid}", rows[0]["detail"])
        self.assertIn("jobs logs,script; link 0123456789abcdef", rows[0]["detail"])
        self.assertNotIn("k1w1", json.dumps(rows))
        self.assertNotIn(token, json.dumps(rows))

    def test_setup_line_refusals(self):
        calls = []
        setup = self.make(("mcp", "setup"))
        with self.fake(calls):
            self.refused(self.make(("mcp",)), "setup_line", {"site": A, "jobs": ["logs"]},
                         "needs a token with the setup scope")
            self.refused(self.make(("mcp", "read")), "setup_line", {"site": A, "jobs": ["logs"]},
                         "this token has no setup scope")
            self.refused(setup, "setup_line", {"site": B, "jobs": ["logs"]},
                         "this token is not for that site")
            self.refused(setup, "setup_line", {"site": A, "jobs": ["countries"]},
                         "Not a job an AI agent can do: countries")
            self.refused(setup, "setup_line", {"site": A, "jobs": ["mail", "logs"]},
                         "Not a job an AI agent can do: mail")
            self.refused(setup, "setup_line", {"site": A, "jobs": []}, "at least one job")
            self.refused(setup, "setup_line", {"site": A, "jobs": "logs"}, "jobs is an array")
            self.refused(setup, "setup_line", {"site": A}, "jobs is needed")
        self.assertEqual(calls, [])
        with self.fake(calls, error="The log endpoint is switched off on this server."):
            self.refused(setup, "setup_line", {"site": A, "jobs": ["logs"]},
                         "The log endpoint is switched off")
        self.assertEqual(self.audit("mcp.setup_line"), [])
        # A token without the mcp scope does not get in at all.
        self.assertEqual(self.mcp(self.make(("read",)), "setup_line",
                                  {"site": A, "jobs": ["logs"]}).status, 401)

    def test_a_demoted_makers_setup_token_stops(self):
        token = self.make(("mcp", "setup"), actor=self.uids["admin@example.com"])
        db = self.db()
        try:
            db.execute("UPDATE members SET role = 'viewer' WHERE user_id = ?",
                       (self.uids["admin@example.com"],))
        finally:
            db.close()
        with self.fake([]):
            self.assertEqual(self.mcp(token, "setup_line", {"site": A, "jobs": ["logs"]}).status,
                             401)

    def test_setup_line_without_a_token_is_refused(self):
        got = tools.call(Context(None), "setup_line", {"site": A, "jobs": ["logs"]})
        self.assertTrue(got["isError"])
        self.assertIn("This connection has no token", got["content"][0]["text"])

    @unittest.skipUnless(hasattr(kit_api, "make_agent_line"),
                         "needs kit_api.make_agent_line(db, config, org, site, jobs, actor, *, "
                         "live_dir, config_path, allowed, origin): the agent line with jobs "
                         "(2.39.0), built beside this tool")
    def test_setup_line_with_the_real_agent_line(self):
        got = self.result(self.make(("mcp", "setup")), "setup_line",
                          {"site": A, "jobs": ["script"]})
        self.assertFalse(got["isError"], got)
        data = got["structuredContent"]
        self.assertIn(A, data["line"])
        self.assertIn("use code", data["line"])
        self.assertRegex(data["link_id"], r"^[0-9a-f]{16}$")
        self.assertEqual(len(self.audit("kit.agentlink")), 1)
        self.assertEqual(len(self.audit("mcp.setup_line")), 1)

    # ------------------------------------------------------------ the scope

    def test_only_an_owner_or_admin_makes_a_setup_token_for_one_site(self):
        viewer = self.uids["viewer@example.com"]
        for why, kw in (("Only an owner or admin", {"actor": viewer}),
                        ("exactly one site", {"sites": ()}),
                        ("exactly one site", {"sites": (A, B)})):
            with self.subTest(why=why), self.assertRaisesRegex(ValueError, why):
                self.make(("mcp", "setup"), **kw)
        with self.assertRaisesRegex(ValueError, "give it the mcp scope too"):
            self.make(("setup",))
        self.assertTrue(self.make(("mcp", "setup"), actor=self.uids["admin@example.com"]))
        self.assertTrue(self.make(("mcp", "setup"), actor="cli"))     # made on the server
        # The token API: a viewer is refused; an admin gets it for one site only.
        form = {"name": "Set-up agent", "sites": [A], "scopes": ["mcp", "setup"]}
        cookie, csrf = self.session("viewer@example.com")
        viewer_try = self.post(f"/traffic/{A}/tokens/create", form, cookie, csrf)
        self.assertEqual(viewer_try.status, 403, viewer_try.json)
        self.assertIn("Only an admin", viewer_try.json["error"])
        cookie, csrf = self.session("admin@example.com")
        two = self.post(f"/traffic/{A}/tokens/create", {**form, "sites": None}, cookie, csrf)
        self.assertEqual(two.status, 400, two.json)
        self.assertIn("exactly one site", two.json["error"])
        made = self.post(f"/traffic/{A}/tokens/create", form, cookie, csrf)
        self.assertEqual(made.status, 200, made.json)
        self.assertEqual(made.json["scopes"], ["mcp", "setup"])
        # setup reads nothing: not the data API either.
        db = self.db()
        try:
            ok, why, _ = apitokens.check(db, f"Bearer {made.json['token']}", A, "read")
        finally:
            db.close()
        self.assertFalse(ok)
        self.assertIn("no read scope", why)


class FinishedSite(unittest.TestCase):
    def test_setup_left_on_a_finished_site_says_nothing_is_left(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "www"
            (out / "example.com" / "data").mkdir(parents=True)
            (out / "example.com" / "data" / "app.json").write_text(json.dumps(FINISHED["app"]))
            parts = {k: FINISHED[k] for k in ("status", "tools", "settings")}
            ctx = Context(out, checker=lambda s: (True, "", False))
            with mock.patch.object(setup_items, "answers",
                                   return_value={**parts, "waiting": []}):
                got = tools.call(ctx, "setup_left", {"site": "example.com"})
        self.assertFalse(got["isError"], got)
        self.assertEqual(got["structuredContent"]["left"], [])
        self.assertTrue(got["structuredContent"]["done"])
        self.assertEqual(got["structuredContent"]["jobs"], [])
        self.assertIn("Nothing is left", got["content"][0]["text"])


if __name__ == "__main__":
    unittest.main()
