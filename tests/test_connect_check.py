"""Has it arrived yet? (2.44: connect_check.py, POST <page>/sites/arrived): the one answer,
in plain words, behind the Test button beside every line, command, snippet, share page and
webhook address Skald gives someone.

  - each kind answers wait, then ok once its thing arrived: the logs, a webhook, an agent
    line (opened, keys, reported), a share page (opened, then what its task brings), a token
    (first use), Search Console (its history syncing), the tag, recorded journeys;
  - the first line is a sentence, never a code; the technical words are in `tech`;
  - a viewer is refused; an unknown kind is 400; a press is counted (429 past the hour's
    limit), a plain poll is not;
  - tests/js/live.mjs (the page's pieces) runs from here.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from auth_support import A  # noqa: E402
from ingest_support import TenantServer, lines  # noqa: E402

from skald import connect_check, setup_live  # noqa: E402
from skald.accounts import apitokens  # noqa: E402

T = f"/traffic/{A}/"
CODE = re.compile(r"\b[A-Z_]{4,}\b|Traceback|Error:")


class Words(unittest.TestCase):
    def test_search_words_say_the_history_syncing(self):
        part = {"connected": "sc-domain:example.com",
                "status": {"backfill": {"state": "running", "done": 36, "of": 70}},
                "summary": {"days": 120}}
        got = connect_check.search_words(part)
        self.assertEqual(got["verdict"], "ok")
        self.assertEqual(got["head"], "Connected. Getting the history: 36 of 70 weeks.")
        self.assertEqual(got["says"], "120 days are here so far.")
        got = connect_check.search_words({"connected": None})
        self.assertEqual((got["verdict"], got["head"]), ("wait", "Search Console is not connected yet."))
        got = connect_check.search_words({"connected": "x", "status": {"error": "HTTP 403: denied"},
                                          "summary": {"days": 3}})
        self.assertEqual(got["verdict"], "bad")
        self.assertNotIn("403", got["head"], "the code is behind Details")
        self.assertEqual(got["tech"], "HTTP 403: denied")

    def test_every_kind_is_named(self):
        self.assertEqual(set(connect_check.KINDS), {"logs", "tag", "search", "journeys", "agent",
                                                    "hook", "tool", "share", "token"})


class Arrived(TenantServer):
    def setUp(self):
        super().setUp()
        self.cookie, self.csrf = self.session("owner@example.com")

    def ask(self, what, press=False, who=None):
        cookie, csrf = (self.cookie, self.csrf) if who is None else self.session(who)
        body = {"site": A, "what": what, **({"press": True} if press else {})}
        return self.post(T + "sites/arrived", body, cookie, csrf)

    def answer(self, what, press=False):
        got = self.ask(what, press)
        self.assertEqual(got.status, 200, got.json)
        t = got.json["test"]
        self.assertIn(t["verdict"], ("ok", "wait", "bad"))
        self.assertTrue(t["head"].endswith("."), t["head"])
        self.assertIsNone(CODE.search(t["head"]), f"a code on the first line: {t['head']}")
        self.assertRegex(t["at"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
        return t

    def test_logs_wait_then_arrive(self):
        t = self.answer("logs")
        self.assertEqual((t["verdict"], t["head"]), ("wait", "Waiting: no data has arrived yet."))
        token = self.token(self.alpha, sites=[A])
        self.assertEqual(self.ship(A, token, lines(12)).status, 200)
        t = self.answer("logs", press=True)
        self.assertEqual(t["verdict"], "ok")
        self.assertIn("12 lines in the last 15 minutes", t["says"])

    def test_a_webhook_waits_for_its_first_real_delivery(self):
        t = self.answer("hook:calendly")
        self.assertEqual(t["verdict"], "wait")
        self.assertIn("signing key is not saved", t["head"])
        got = self.post(T + "integrations/secret", {"site": A, "tool": "calendly"}, self.cookie, self.csrf)
        self.assertEqual(got.status, 200, got.json)
        t = self.answer("hook:calendly")
        self.assertEqual(t["head"], "Waiting for Calendly: nothing real has arrived yet.")
        self.assertEqual(t["fix"], "Book a test call on your Calendly page.")
        got = self.post(T + "integrations/test", {"site": A, "tool": "calendly"}, self.cookie, self.csrf)
        self.assertEqual(got.status, 200, got.json)
        t = self.answer("hook:calendly")
        self.assertEqual(t["verdict"], "wait", "a test of Skald's own is not a real delivery")
        # 2.44.1: the Test is signed with the key Skald has: it proves the address only.
        self.assertEqual(t["says"], "Skald's address works. Only a real Calendly event proves "
                                    "the signing key: make a test booking.")
        steps = {s["id"]: s["done"] for s in t["steps"]}
        self.assertEqual(steps, {"secret": True, "test": True, "real": False})
        self.assertEqual(self.ask("hook:nosuch").status, 400)

    def test_an_agent_line_ticks_opened_keys_reported(self):
        got = self.post(T + "sites/agentlink", {"site": A}, self.cookie, self.csrf)
        self.assertEqual(got.status, 200, got.json)
        lid = got.json["link_id"]
        t = self.answer(f"agent:{lid}")
        self.assertEqual(t["head"], "Waiting for your agent: it has not opened the line yet.")
        self.assertIn("Claude Code", t["fix"])
        self.assertEqual([s["id"] for s in t["steps"]][:3], ["opened", "keys", "reported"])
        from skald.kit import agent
        code = re.search(r"use code ([A-Za-z0-9_-]{43}) ", got.json["line"]).group(1)
        agent.opened(self.live, code)
        t = self.answer(f"agent:{lid}")
        self.assertEqual(t["head"], "Your agent read the steps but has not taken its keys yet.")
        self.assertTrue(t["steps"][0]["done"])
        t = self.answer("agent:0000000000000000")
        self.assertEqual((t["verdict"], t["final"]), ("bad", True))

    def test_a_share_page_says_opened_then_arrived(self):
        got = self.post(T + "sites/share", {"site": A, "task": "send", "method": "docker", "days": 7},
                        self.cookie, self.csrf)
        self.assertEqual(got.status, 200, got.json)
        ref = got.json["ref"]
        t = self.answer(f"share:{ref}")
        self.assertEqual(t["head"], "Waiting for your developer: they have not opened the page yet.")
        page = "/" + got.json["link"].split("/", 3)[3]
        self.assertEqual(self.call("GET", page).status, 200)
        t = self.answer(f"share:{ref}")
        self.assertEqual(t["head"], "Your developer opened the page but has not taken the secret yet.")
        token = self.token(self.alpha, sites=[A])
        self.assertEqual(self.ship(A, token, lines(3)).status, 200)
        t = self.answer(f"share:{ref}")
        self.assertEqual((t["verdict"], t["head"]), ("ok", "Done: your developer finished."))

    def test_a_token_says_when_the_assistant_first_used_it(self):
        db = self.accounts_db()
        try:
            apitokens.create(db, self.alpha["id"], "Claude", sites=[A], scopes=("read",))
            tid = apitokens.listing(db, self.alpha["id"])[0]["id"]
        finally:
            db.close()
        t = self.answer(f"token:{tid}")
        self.assertEqual(t["head"], "Waiting: your assistant has not used this key yet.")
        db = self.accounts_db()
        try:
            db.execute("UPDATE tokens SET last_used = ? WHERE id = ?", ("2026-10-27T10:42:00Z", tid))
            db.commit()
        finally:
            db.close()
        t = self.answer(f"token:{tid}")
        self.assertEqual((t["verdict"], t["head"]), ("ok", "Connected: your assistant used this key."))
        self.assertIn("10:42 UTC", t["says"])

    def test_search_tag_journeys_and_tools_answer(self):
        self.assertEqual(self.answer("search")["head"], "Search Console is not connected yet.")
        self.assertIn(self.answer("tag")["verdict"], ("wait", "bad"))
        self.assertEqual(self.answer("journeys")["head"], "Recorded journeys are not connected yet.")
        self.assertIn("not connected", self.answer("tool:ga4")["head"])

    def test_refusals_and_the_limit(self):
        self.assertEqual(self.ask("logs", who="viewer@example.com").status, 403)
        self.assertEqual(self.ask("nonsense").status, 400)
        self.assertEqual(self.ask("agent:").status, 400)
        with mock.patch.object(setup_live, "CHECK_PER_HOUR", 2):
            for _ in range(5):
                self.assertEqual(self.ask("logs").status, 200, "a plain poll is never counted")
            self.assertEqual(self.ask("logs", press=True).status, 200)
            self.assertEqual(self.ask("logs", press=True).status, 200)
            got = self.ask("logs", press=True)
            self.assertEqual(got.status, 429)
            self.assertEqual(got.json["error"], "Too many checks. Try again in a few minutes.")


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class Page(unittest.TestCase):
    """tests/js/live.mjs: the poller, the redraw, the Test button, arrivedBox, Search's words."""

    def test_live_pieces(self):
        root = Path(__file__).resolve().parent.parent
        done = subprocess.run(["node", str(root / "tests" / "js" / "live.mjs")], capture_output=True,
                              text=True, timeout=120, cwd=root)
        self.assertEqual(done.returncode, 0, done.stderr[-4000:])
        self.assertIn("live: all passed", done.stdout)


if __name__ == "__main__":
    unittest.main()
