"""AI crawler controls (bot_policy.py, bot_policy_api.py).

What is pinned: the catalog names every assistant and training crawler the
classifier knows; only catalog names and fixed modes survive validation, so
nothing from the policy file reaches nginx but fixed lines; "block training"
keeps AI search and a person's question; apply tests nginx before a reload,
puts the old file back when the test fails, and never follows a symlink;
the helper answers same-origin only and stores the policy; 403s per crawler
are counted on both roads and agree.
"""
from __future__ import annotations

import io
import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from support import CHROME, GPTBOT, UTC, Sandbox, line  # noqa: E402

from skald import bot_policy as bp  # noqa: E402
from skald import bot_policy_api  # noqa: E402
from skald.classify import AI_ASKED, AI_TRAINING  # noqa: E402
from skald.refresh_server import make_handler  # noqa: E402

NOON = datetime(2026, 10, 5, 12, tzinfo=UTC)


def names(pattern: re.Pattern) -> set[str]:
    return set(pattern.pattern.split("|"))


class Catalog(unittest.TestCase):

    def test_every_classifier_name_is_in_the_catalog(self):
        known = names(AI_TRAINING) | names(AI_ASKED)
        self.assertLessEqual(known, set(bp.BY_NAME))
        self.assertLessEqual({c.name for c in bp.CATALOG if not c.robots_only}, known)

    def test_names_are_safe_in_an_nginx_string(self):
        for c in bp.CATALOG:
            self.assertRegex(c.name, bp.SAFE_NAME)
            self.assertIn(c.tier, bp.TIERS)

    def test_match_by_user_agent(self):
        self.assertEqual(bp.match(GPTBOT).name, "GPTBot")
        self.assertEqual(bp.match("Mozilla/5.0 (compatible; Claude-SearchBot/1.0)").name,
                         "Claude-SearchBot")
        self.assertIsNone(bp.match(CHROME))
        self.assertIsNone(bp.match("Google-Extended"))       # robots-only token


class Policy(unittest.TestCase):

    def test_all_allow_by_default(self):
        conf = bp.nginx_conf(bp.empty())
        self.assertNotIn("~*", conf)
        self.assertIn("default 0;", conf)
        self.assertIn("/robots.txt 0;", conf)
        self.assertEqual(bp.robots_lines(bp.empty()), "")

    def test_block_training_keeps_search_and_questions(self):
        policy = bp.validate({"owners": {"OpenAI": "block_training", "Google": "block_training"}})
        self.assertEqual([c.name for c in bp.blocked(policy)], ["GPTBot", "Google-Extended"])
        conf = bp.nginx_conf(policy)
        self.assertIn('"~*GPTBot" 1;', conf)
        self.assertNotIn("OAI-SearchBot", conf)
        self.assertNotIn("Google-Extended", conf)             # nginx cannot see it
        self.assertIn("User-agent: Google-Extended\nDisallow: /", bp.robots_lines(policy))

    def test_block_all_and_a_crawler_override(self):
        policy = bp.validate({"owners": {"Anthropic": "block"},
                              "crawlers": {"Claude-User": "allow", "CCBot": "block"}})
        self.assertEqual(sorted(c.name for c in bp.blocked(policy)),
                         ["CCBot", "Claude-SearchBot", "Claude-Web", "ClaudeBot", "anthropic-ai"])
        view = bp.view(policy)
        anthropic = next(a for a in view["assistants"] if a["owner"] == "Anthropic")
        user = next(c for c in anthropic["crawlers"] if c["name"] == "Claude-User")
        self.assertEqual((anthropic["mode"], user["override"], user["effective"]),
                         ("block", "allow", "allow"))

    def test_only_known_names_and_modes(self):
        for bad in ([], "x", {"owners": []}, {"owners": {"Evil": "block"}},
                    {"owners": {"OpenAI": "deny"}}, {"crawlers": {"GPTBot": "block_training"}},
                    {"crawlers": {'x" 1; } server { "': "block"}}):
            with self.subTest(bad=bad):
                with self.assertRaises(bp.Invalid):
                    bp.validate(bad)
        self.assertEqual(bp.validate({"owners": {"OpenAI": "allow"}})["owners"], {})


class FakeRun:
    def __init__(self, test_code=0, reload_code=0):
        self.calls, self.codes = [], {"test": test_code, "reload": reload_code}

    def __call__(self, cmd, **kw):
        kind = "test" if "-t" in cmd else "reload"
        self.calls.append(kind)
        return subprocess.CompletedProcess(cmd, self.codes[kind], "", "emerg: bad thing")


class Apply(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.policy = self.root / "bot-policy.json"
        self.conf = self.root / "skald-bot-policy.conf"
        self.status = self.root / "bot-policy-applied.json"

    def tearDown(self):
        self._tmp.cleanup()

    def apply(self, run):
        return bp.apply(self.policy, self.conf, self.status, run=run)

    def test_no_policy_writes_the_all_allow_map(self):
        run = FakeRun()
        self.assertEqual(self.apply(run), 0)
        self.assertEqual(run.calls, ["test", "reload"])
        self.assertEqual(self.conf.read_text(), bp.nginx_conf(bp.empty()))
        state = json.loads(self.status.read_text())
        self.assertEqual((state["ok"], state["changed"], state["blocked"]), (True, True, []))

    def test_unchanged_does_not_reload(self):
        self.apply(FakeRun())
        run = FakeRun()
        self.assertEqual(self.apply(run), 0)
        self.assertEqual(run.calls, [])

    def test_a_failed_test_puts_the_old_file_back(self):
        self.apply(FakeRun())
        before = self.conf.read_text()
        bp.save(self.policy, {"owners": {"OpenAI": "block"}})
        run = FakeRun(test_code=1)
        self.assertEqual(self.apply(run), 1)
        self.assertEqual(run.calls, ["test"])
        self.assertEqual(self.conf.read_text(), before)
        state = json.loads(self.status.read_text())
        self.assertFalse(state["ok"])
        self.assertIn("previous file kept", state["error"])

    def test_first_install_failing_leaves_no_file(self):
        self.assertEqual(self.apply(FakeRun(test_code=1)), 1)
        self.assertFalse(self.conf.exists())

    def test_a_bad_policy_changes_nothing(self):
        self.apply(FakeRun())
        before = self.conf.read_text()
        self.policy.write_text('{"owners": {"Evil": "block"}}')
        run = FakeRun()
        self.assertEqual(self.apply(run), 1)
        self.assertEqual((run.calls, self.conf.read_text()), ([], before))
        self.assertIn("unknown assistant", json.loads(self.status.read_text())["error"])

    def test_a_symlinked_policy_is_refused(self):
        secret = self.root / "secret"
        secret.write_text('{"owners": {}}')
        os.symlink(secret, self.policy)
        self.assertEqual(self.apply(FakeRun()), 1)
        self.assertFalse(json.loads(self.status.read_text())["ok"])

    def test_the_status_file_replaces_a_symlink_never_follows_it(self):
        target = self.root / "victim"
        target.write_text("keep")
        os.symlink(target, self.status)
        self.apply(FakeRun())
        self.assertEqual(target.read_text(), "keep")
        self.assertFalse(self.status.is_symlink())

    def test_a_blocking_policy_reaches_the_map(self):
        bp.save(self.policy, {"owners": {"OpenAI": "block_training"}}, by="morgan")
        self.assertEqual(self.apply(FakeRun()), 0)
        self.assertIn('"~*GPTBot" 1;', self.conf.read_text())
        self.assertEqual(json.loads(self.status.read_text())["blocked"], ["GPTBot"])


class FakeRunner:
    def refresh(self, force=False):
        return "ran"


class Helper(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.file = root / "bot-policy.json"
        self.config = {"bot_policy": {"file": str(self.file),
                                      "status": str(root / "bot-policy-applied.json")},
                       "history": {"db": str(root / "history.sqlite")}}
        bot_policy_api._last["at"] = None

    def tearDown(self):
        self._tmp.cleanup()

    def request(self, method, path, body=b"", headers=None):
        handler = make_handler(FakeRunner(), {"https://www.example.com"}, self.config)
        headers = {"Sec-Fetch-Site": "same-origin", **(headers or {})}
        raw = (f"{method} {path} HTTP/1.1\r\nHost: x\r\nContent-Length: {len(body)}\r\n"
               "Content-Type: application/json\r\n"
               + "".join(f"{k}: {v}\r\n" for k, v in headers.items())
               + "\r\n").encode() + body
        out = io.BytesIO()

        class Socket:
            def makefile(self, mode, *a, **k):
                return io.BytesIO(raw)

            def sendall(self, data):
                out.write(data)

        handler(Socket(), ("127.0.0.1", 5555), None)
        head, _, data = out.getvalue().partition(b"\r\n\r\n")
        return int(head.split()[1]), json.loads(data) if data.startswith(b"{") else None

    def test_paths(self):
        self.assertTrue(bot_policy_api.is_policy("/traffic/example.com/bot-policy"))
        self.assertTrue(bot_policy_api.is_policy("/traffic/example.com/guides/bot-policy"))
        self.assertFalse(bot_policy_api.is_policy("/traffic/../bot-policy"))
        self.assertFalse(bot_policy_api.is_policy("/bot-policy"))

    def test_read_save_and_refuse(self):
        code, got = self.request("GET", "/traffic/example.com/bot-policy")
        self.assertEqual((code, got["blocked"], got["applied"]), (200, [], None))
        self.assertEqual(len(got["assistants"]), len(bp.OWNERS))
        body = json.dumps({"owners": {"OpenAI": "block_training"}}).encode()
        code, got = self.request("POST", "/traffic/example.com/bot-policy", body)
        self.assertEqual((code, got["blocked"]), (200, ["GPTBot"]))
        self.assertEqual(json.loads(self.file.read_text())["owners"], {"OpenAI": "block_training"})
        code, got = self.request("POST", "/traffic/example.com/bot-policy", body)
        self.assertEqual(code, 429)
        bot_policy_api._last["at"] = None
        code, got = self.request("POST", "/traffic/example.com/bot-policy",
                                 b'{"owners": {"OpenAI": "nope"}}')
        self.assertEqual((code, got["ok"], got["blocked"]), (400, False, ["GPTBot"]))
        code, got = self.request("POST", "/traffic/example.com/bot-policy", b"not json")
        self.assertEqual(code, 400)

    def test_same_origin_only(self):
        code, _ = self.request("POST", "/traffic/example.com/bot-policy", b"{}",
                               {"Sec-Fetch-Site": "cross-site"})
        self.assertEqual(code, 403)
        self.assertFalse(self.file.exists())


class ApiFlag(unittest.TestCase):
    """bots.json names the settings route only when bot_policy.enabled."""

    def test_flag(self):
        from skald import data_files

        class Page:
            def __init__(self, config):
                self.config, self.extras, self.snap, self.live_ok = config, {}, None, False

            def counts(self, kinds):
                return {}

            def per_day(self, figures):
                return []

            def today_block(self):
                return None

        self.assertIsNone(data_files.bots(Page({}))["api"])
        self.assertIsNone(data_files.bots(Page({"bot_policy": {"enabled": "yes"}}))["api"])
        self.assertEqual(data_files.bots(Page({"bot_policy": {"enabled": True}}))["api"],
                         {"bot_policy": "bot-policy"})


class Counted(unittest.TestCase):
    """403s per AI crawler: in the day's bots figures, and the audit agrees."""

    def test_collect_and_audit(self):
        box = Sandbox()
        try:
            box.log([line(NOON, "198.51.100.40", "/a", GPTBOT, status=403),
                     line(NOON + timedelta(minutes=1), "198.51.100.40", "/b", GPTBOT, status=403),
                     line(NOON + timedelta(minutes=2), "198.51.100.40", "/robots.txt", GPTBOT),
                     line(NOON + timedelta(minutes=3), "203.0.113.9", "/", CHROME, status=403)])
            code, out, err = box.run("--today", "2026-10-06", "collect")
            self.assertEqual(code, 0, err)
            with sqlite3.connect(box.db) as db:
                bots = json.loads(db.execute(
                    "SELECT data FROM day_extras WHERE site = 'example.com' AND day = "
                    "'2026-10-05' AND kind = 'bots'").fetchone()[0])
            self.assertEqual(bots["blocked"], {"GPTBot": 2})
            code, out, err = box.run("--today", "2026-10-06", "audit")
            self.assertEqual(code, 0, out + err)
        finally:
            box.close()


if __name__ == "__main__":
    unittest.main()
