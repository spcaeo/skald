"""From your tools, the routes: the kit's POST <code>/toolkey (kit/agent_tools.py)
and the dashboard's integrations/yourtools (yourtools/api.py), with a fake tool
(yourtools_support.Fake). No network.

  * toolkey: curl or Wget only, the report key, a line with the connect-tools
    job made by an install admin (checked again at the upload), the key from
    the body, never replaced unless replace=1, never echoed or logged; one
    audit row without the key; its own rate limit
  * the job's steps: find names only, list, ask per key, the curl command
  * the dashboard: members read the figures (never a key or its robot);
    admins paste a key (the "Me" road), set options, pause, remove the key,
    "Sync now" (rate limited); viewers change nothing
  * nginx: the kit's POST location takes toolkey

Test data: example.com names and RFC 5737 addresses; the keys are made up here.
"""
from __future__ import annotations

import contextlib
import io
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import yourtools_support as ys  # noqa: E402
from auth_support import A  # noqa: E402
from test_agent_many import Base  # noqa: E402

from skald.accounts import users  # noqa: E402
from skald.conversions import secrets_store  # noqa: E402
from skald.kit import agent  # noqa: E402
from skald.yourtools import api, conn, sync  # noqa: E402


class Tools(Base):
    def setUp(self):
        super().setUp()
        self.fake = ys.install()
        self.addCleanup(ys.remove)

    def install_admin(self, flag=True):
        db = self.accounts_db()
        try:
            if not flag:
                users.set_install_admin(db, self.uids["owner@example.com"], True, "cli")
            users.set_install_admin(db, self.uids["admin@example.com"], flag, "cli")
        finally:
            db.close()

    def send(self, code, body, key, query="tool=fake&account=acme", agent_name="curl/8.5.0"):
        hdrs = {} if key is None else {agent.REPORT_HEADER: key}
        self.n = getattr(self, "n", 0) + 1
        status, data = self.kit_call("POST", f"/traffic-kit/{code}/toolkey?{query}",
                                     body.encode(), hdrs, agent_name,
                                     address=f"198.51.100.{self.n}")
        return status, json.loads(data)

    def report_key(self, code):
        return agent.take(self.live, code)[2]["report_key"]

    def stored(self):
        return secrets_store.load(secrets_store.path_for(self.config, self.live)).get(
            f"tools/{A}/fake")


class ToolKey(Tools):
    def test_only_an_install_admins_line_with_the_job(self):
        _, code = self.line(jobs=["connect-tools"])
        status, got = self.send(code, ys.KEY, self.report_key(code))
        self.assertEqual(status, 403)
        self.assertIn("whoever runs this Skald", got["error"])
        self.install_admin()
        _, other = self.line(jobs=["script"])
        status, got = self.send(other, ys.KEY, self.report_key(other))
        self.assertEqual(status, 403)
        self.assertIn("no connect-tools job", got["error"])
        self.assertIsNone(self.stored())
        self.assertEqual(agent.route("A" * 43 + "/toolkey"), "toolkey", "its own limit")

    def test_kept_once_never_replaced_unless_asked_never_echoed(self):
        self.install_admin()
        body, code = self.line(jobs=["connect-tools"])
        key = self.report_key(code)
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            refused = [self.send(code, ys.KEY, key, agent_name="Mozilla/5.0 (Claude-User)"),
                       self.send(code, ys.KEY, None), self.send(code, ys.KEY, "x" * 32),
                       self.send(code, ys.KEY, key, query="tool=nope"),
                       self.send(code, ys.KEY, key, query="tool=fake&account=NO!"),
                       self.send(code, "fk_bad_" + "y" * 16, key),
                       self.send(code, "", key)]
            self.assertEqual([s for s, _ in refused], [403, 403, 403, 400, 400, 400, 400])
            self.assertIsNone(self.stored(), "nothing kept before a good key")
            status, got = self.send(code, ys.KEY, key)
            self.assertEqual((status, got), (200, {"ok": True, "tool": "fake",
                                                   "who": "token ...QrSt", "replaced": False}))
            again = self.send(code, ys.OTHER, key)
            self.assertEqual((again[0], again[1]["who"]), (409, "token ...QrSt"))
            self.assertEqual(self.stored(), ys.KEY)
            status, got = self.send(code, ys.OTHER, key,
                                    query="tool=fake&account=acme&replace=1")
            self.assertEqual((status, got["replaced"]), (200, True))
        self.assertEqual(self.stored(), ys.OTHER)
        part = conn.load(self.live, A)["fake"]
        self.assertEqual((part["on"], part["options"], part["connected_by"]),
                         (True, {"account": "acme"}, "ai-agent"))
        rows = self.audit("tools.key")
        self.assertEqual(len(rows), 2)
        self.assertEqual((rows[0]["actor"], rows[0]["target"]), ("ai-agent", A))
        self.assertIn(f"link {body['link_id']}", rows[-1]["detail"])
        seen = json.dumps(rows) + err.getvalue() + json.dumps([g for _, g in refused])
        for secret in (ys.KEY, ys.OTHER, "fk_bad_"):
            self.assertNotIn(secret, seen, "a key is never logged or echoed")

    def test_checked_again_at_the_upload(self):
        self.install_admin()
        _, code = self.line(jobs=["connect-tools"])
        key = self.report_key(code)
        self.install_admin(False)
        self.assertEqual(self.send(code, ys.KEY, key)[0], 403)

    def test_google_analytics_uses_the_search_console_robot(self):
        from search_support import service_key
        from skald.search import google
        self.install_admin()
        secrets_store.put(secrets_store.path_for(self.config, self.live), google.SECRET,
                          service_key("search-robot@example.com"))
        _, code = self.line(jobs=["connect-tools"])
        text = agent.steps(agent.find(self.live, code), code, "")
        self.assertIn("search-robot@example.com", text)
        self.assertIn("toolkey?tool=ga4&property=<property-id>&key=search' < /dev/null", text)
        key = self.report_key(code)
        status, got = self.send(code, "", key, query="tool=ga4&property=123456789&key=search")
        self.assertEqual((status, got["tool"]), (200, "ga4"), got)
        part = conn.load(self.live, A)["ga4"]
        self.assertEqual(part["options"], {"property": "123456789", "key": "search"})
        self.assertIsNone(secrets_store.load(secrets_store.path_for(self.config, self.live))
                          .get(f"tools/{A}/ga4"), "nothing copied")
        self.assertIn("the Search Console key", self.audit("tools.key")[0]["detail"])

    def test_the_steps_list_ask_and_send_from_stdin(self):
        self.install_admin()
        _, code = self.line(jobs=["connect-tools"])
        text = agent.steps(agent.find(self.live, code), code, "")
        self.assertIn("## Step 2. Connect the user's own tools", text)
        self.assertIn("Fake Tool (`fake`): Not connected; no key yet", text)
        self.assertIn("`FAKE_TOOL_TOKEN`", text)
        self.assertIn("Account: `FAKE_ACCOUNT`", text)
        self.assertIn("ask about each key **on its own**", text)
        self.assertIn(f"/traffic-kit/{code}/toolkey?tool=fake&account=<account>", text)
        self.assertIn("--data-binary @-", text)
        self.assertIn("never print a value", text)
        self.assertNotIn("__", text.replace("__SITE", ""), "no placeholder left")


class Dashboard(Tools):
    def get(self, path, cookie=None):
        return self.call("GET", f"/traffic/{A}/{path}", cookie=cookie or self.cookie)

    def change(self, act, body, cookie=None, csrf=None):
        return self.post(f"/traffic/{A}/integrations/yourtools/{act}", {"site": A, **body},
                         cookie or self.cookie, csrf or self.csrf)

    def test_an_admin_pastes_a_key_and_sets_pauses_removes(self):
        got = self.get("integrations/yourtools")
        self.assertEqual(got.status, 200, got.json)
        fake = next(t for t in got.json["tools"] if t["id"] == "fake")
        self.assertEqual((fake["state"], fake["pill"], fake["words"]), ("off", "off",
                                                                       "Not connected"))
        self.assertEqual(fake["option_specs"]["account"]["label"], "Account")
        self.assertEqual(self.change("key", {"tool": "fake", "key": "fk_bad_" + "z" * 16,
                                             "options": {"account": "acme"}}).status, 400)
        got = self.change("key", {"tool": "fake", "key": ys.KEY, "options": {"account": "acme"}})
        self.assertEqual((got.status, got.json["who"]), (200, "token ...QrSt"), got.json)
        self.assertEqual(self.change("key", {"tool": "fake", "key": ys.OTHER}).status, 409)
        fake = next(t for t in self.get("integrations/yourtools").json["tools"]
                    if t["id"] == "fake")
        self.assertEqual((fake["state"], fake["key"]["who"], fake["options"]),
                         ("waiting", "token ...QrSt", {"account": "acme"}))
        self.assertNotIn(ys.KEY, json.dumps(fake))
        self.assertEqual(self.change("set", {"tool": "fake",
                                             "options": {"account": "beta-co"}}).status, 200)
        self.assertEqual(conn.load(self.live, A)["fake"]["options"], {"account": "beta-co"})
        self.assertEqual(self.change("pause", {"tool": "fake"}).status, 200)
        self.assertFalse(conn.load(self.live, A)["fake"]["on"])
        self.assertEqual(self.change("remove", {"tool": "fake"}).status, 200)
        self.assertIsNone(self.stored())
        actions = [r["action"] for r in self.audit(None) if r["action"].startswith("tools.")]
        self.assertEqual(sorted(set(actions)), ["tools.key", "tools.pause", "tools.remove",
                                                "tools.set"])

    def test_members_read_figures_never_a_key(self):
        sync.connect(self.config, self.live, A, "fake", {"account": "acme"}, "cli", key=ys.KEY)
        job = sync.Job(self.config, A, self.live, sync.datetime.now(sync.timezone.utc),
                       lambda *a: None, lambda *a: None)
        self.assertEqual(sync.run(job), 0)
        viewer, _ = self.session("viewer@example.com")
        got = self.get("integrations/yourtools/figures", cookie=viewer)
        self.assertEqual(got.status, 200, got.json)
        tool = got.json["tools"][0]
        self.assertEqual((tool["name"], tool["state"], tool["counted_from"]),
                         ("Fake Tool", "answering", "Counted from: Fake Tool"))
        self.assertEqual([(f["label"], f["value"]) for f in tool["headline"]],
                         [("Visits", 120), ("Signups", None)])
        self.assertNotIn("key", tool)
        self.assertNotIn("QrSt", json.dumps(got.json))
        self.assertEqual(self.get("integrations/yourtools", cookie=viewer).status, 403)
        self.assertEqual(self.change("pause", {"tool": "fake"}, viewer,
                                     self.session("viewer@example.com")[1]).status, 403)

    def test_sync_now_is_rate_limited(self):
        self.assertEqual(self.change("sync", {"tool": "fake"}).status, 409, "not connected")
        sync.connect(self.config, self.live, A, "fake", {"account": "acme"}, "cli", key=ys.KEY)
        with mock.patch.object(api, "spawn") as spawn:
            self.assertEqual(self.change("sync", {"tool": "fake"}).status, 200)
            again = self.change("sync", {"tool": "fake"})
        self.assertEqual(again.status, 429)
        self.assertEqual(spawn.call_count, 1)

    def test_the_setup_line_names_each_tool(self):
        got = self.get("integrations")
        self.assertEqual(got.status, 200)
        fake = next(t for t in got.json["yourtools"] if t["tool"] == "fake")
        self.assertEqual(fake, {"tool": "fake", "name": "Fake Tool", "state": "off",
                                "words": "Not connected"})


class Nginx(unittest.TestCase):
    def test_the_kit_post_location_takes_toolkey(self):
        import test_nginx_routes as routes
        config = routes.from_deploy()
        got = routes.find(config.locations, "/traffic-kit/" + "a" * 43 + "/toolkey")
        self.assertEqual(got.directives("client_max_body_size"), [["16k"]])
        self.assertEqual(got.directives("limit_except")[0], ["POST"])
        root = Path(__file__).resolve().parent.parent
        self.assertIn("|toolkey)$", (root / "docker" / "nginx.conf").read_text())


if __name__ == "__main__":
    unittest.main()
