"""From your tools, the framework (skald/yourtools/): a fake tool
(yourtools_support.Fake) through every part, no network.

  * keys: where a site's key lives (the environment the config names, else
    secrets.json, 0600), never shown; a file others can read is refused
  * conn: the one state every screen shows, with its pill: off, paused,
    needs its key, waiting, answering, last try failed, stopped answering,
    withheld
  * store: each answer kept as it came, with its figures and where each was
    read; a newer answer for the same window replaces the older one
  * sync: the figures kept, a NULL kept NULL (never 0); a failure keeps the
    last figures, mails once per run of failures; a site's lock
  * recount: every figure read again from the stored answer; a changed
    figure, a changed answer, a 0 where the tool gave nothing: each a mismatch
  * the CLI: connect (the key from stdin), status (never the key), pause, audit
  * the scheduler's tools job, at a lower priority than the others

Test data: example.com names; the keys are made up here.
"""
from __future__ import annotations

import io
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import yourtools_support as ys  # noqa: E402

from skald import yourtools  # noqa: E402
from skald.conversions import secrets_store  # noqa: E402
from skald.yourtools import conn, keys, recount, store, sync  # noqa: E402
from skald.yourtools.names import COUNTED_FROM  # noqa: E402

SITE = "example.com"
NOW = datetime(2026, 10, 27, 9, 0, tzinfo=timezone.utc)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.config = {"site": {"name": SITE}, "history": {"db": str(self.folder / "h.sqlite")}}
        self.fake = ys.install()
        self.addCleanup(ys.remove)
        self.mails = []

    def job(self, now=NOW):
        out = []
        return sync.Job(self.config, SITE, self.folder, now, out.append, out.append,
                        send=lambda msg, cfg: self.mails.append(msg)), out

    def connect(self, key=ys.KEY, **options):
        return sync.connect(self.config, self.folder, SITE, "fake",
                            options or {"account": "acme"}, "cli", key=key)


class Registry(Base):
    def test_a_tool_is_one_file_found_by_its_name(self):
        self.assertIn("fake", yourtools.adapters())
        self.assertIs(yourtools.get("fake"), self.fake)
        self.assertIsNone(yourtools.get("nope"))
        for tool, adapter in yourtools.adapters().items():
            self.assertEqual(adapter.id, tool)
            self.assertTrue(adapter.name and adapter.permission and adapter.key_words)


class Keys(Base):
    def test_kept_in_secrets_json_and_never_shown(self):
        self.assertEqual(keys.state(self.config, self.folder, SITE, "fake")["set"], False)
        got = self.connect()
        self.assertEqual(got, {"tool": "fake", "who": "token ...QrSt", "replaced": False})
        path = secrets_store.path_for(self.config, self.folder)
        self.assertEqual(oct(path.stat().st_mode & 0o777), "0o600")
        self.assertEqual(secrets_store.load(path)["tools/example.com/fake"], ys.KEY)
        state = keys.state(self.config, self.folder, SITE, "fake")
        self.assertEqual(state, {"set": True, "where": "file", "who": "token ...QrSt",
                                 "problem": None})
        self.assertNotIn(ys.KEY, json.dumps(state))

    def test_never_replaced_unless_asked(self):
        self.connect()
        with self.assertRaises(ValueError) as no:
            self.connect(ys.OTHER)
        self.assertIn("keeps that one", str(no.exception))
        got = sync.connect(self.config, self.folder, SITE, "fake", {}, "cli", key=ys.OTHER,
                           replace=True)
        self.assertTrue(got["replaced"])
        self.assertEqual(keys.find(self.config, self.folder, SITE, "fake")[0], ys.OTHER)

    def test_a_bad_key_or_option_is_refused_in_plain_words(self):
        with self.assertRaises(ValueError) as bad:
            self.connect("fk_bad_" + "x" * 16)
        self.assertNotIn("fk_bad_", str(bad.exception), "never echoed")
        with self.assertRaises(ValueError) as opt:
            self.connect(account="Not An Account!")
        self.assertIn("account", str(opt.exception).lower())
        self.assertEqual(conn.load(self.folder, SITE), {}, "nothing switched on")

    def test_the_environment_the_config_names_wins_and_cannot_be_changed(self):
        self.config["your_tools"] = {f"{SITE}/fake": "SKALD_TEST_FAKE_TOOL"}
        with mock.patch.dict(os.environ, {"SKALD_TEST_FAKE_TOOL": ys.OTHER}):
            self.assertEqual(keys.find(self.config, self.folder, SITE, "fake"),
                             (ys.OTHER, "env SKALD_TEST_FAKE_TOOL"))
            with self.assertRaises(ValueError) as no:
                self.connect()
            self.assertIn("environment", str(no.exception))
        self.config["your_tools"] = {SITE: {"fake": {"key_env": "SKALD_TEST_FAKE_TOOL"}}}
        self.assertEqual(keys.env_name(self.config, SITE, "fake"), "SKALD_TEST_FAKE_TOOL")

    def test_a_secrets_file_others_can_read_is_refused(self):
        self.connect()
        path = secrets_store.path_for(self.config, self.folder)
        path.chmod(0o644)
        got = keys.state(self.config, self.folder, SITE, "fake")
        self.assertEqual((got["set"], got["problem"]),
                         (False, "secrets.json can be read by others; it must be 0600."))

    def test_removed_key_keeps_the_rest(self):
        self.connect()
        self.assertTrue(keys.remove(self.config, self.folder, SITE, "fake"))
        self.assertFalse(keys.remove(self.config, self.folder, SITE, "fake"))
        self.assertFalse(keys.state(self.config, self.folder, SITE, "fake")["set"])


class States(unittest.TestCase):
    def test_every_state_has_its_pill_and_words(self):
        ok = (NOW - timedelta(hours=2)).isoformat()
        old = (NOW - timedelta(hours=conn.STALE_HOURS + 1)).isoformat()
        cases = [
            ({}, True, "off", "off", "Not connected"),
            ({"on": False, "connected_at": ok, "paused_at": ok}, True, "off", "off", "Paused"),
            ({"on": True}, False, "no_key", "warn", "Needs its key"),
            ({"on": True}, True, "waiting", "info", "Waiting for its first answer"),
            ({"on": True, "last_try": ok, "last_ok": ok, "ok": True}, True, "answering", "good",
             "Answering"),
            ({"on": True, "last_try": ok, "last_ok": ok, "ok": False}, True, "failing", "warn",
             "Last try failed"),
            ({"on": True, "last_try": ok, "last_ok": old, "ok": False}, True, "stopped", "bad",
             "Stopped answering"),
            ({"on": True, "last_try": ok, "ok": False}, True, "stopped", "bad", "Not answering"),
            ({"on": True, "last_try": ok, "last_ok": ok, "ok": True, "audit": {"ok": False}},
             True, "withheld", "bad", "Withheld"),
        ]
        for part, key, state, pill, words in cases:
            with self.subTest(state=state, words=words):
                got = conn.status(part, key, NOW)
                self.assertEqual((got["state"], got["pill"], got["words"]), (state, pill, words))
        self.assertEqual(conn.status({"last_ok": ok}, True, NOW)["ago"], "2 h ago")
        self.assertEqual(conn.status({}, True, NOW)["ago"], "never")


class Sync(Base):
    def test_figures_kept_with_where_they_were_read_and_null_kept_null(self):
        self.connect()
        job, out = self.job()
        self.assertEqual(sync.run(job), 0, out)
        db = store.reader(self.folder)
        try:
            got = store.latest(db, SITE, "fake")
        finally:
            db.close()
        self.assertEqual(len(got), 1)
        figs = {(f["name"], f["dim"]): f for f in got[0]["figures"]}
        self.assertEqual(figs[("visits", None)]["value"], 120)
        self.assertIsNone(figs[("signups", None)]["value"], "not given: NULL, never 0")
        self.assertIsNone(figs[("signups", None)]["src"])
        self.assertEqual(figs[("visits", "/pricing")]["src"], "/rows/0/visits")
        self.assertEqual(got[0]["note"], "the tool's own day")
        part = conn.load(self.folder, SITE)["fake"]
        self.assertTrue(part["ok"] and part["last_ok"] and part["audit"]["ok"], part)
        self.assertEqual(conn.status(part, True)["state"], "answering")
        self.assertEqual(self.fake.asked, [(ys.KEY, {"account": "acme"})])

    def test_a_newer_answer_for_the_same_window_replaces_the_older(self):
        self.connect()
        self.assertEqual(sync.run(self.job()[0]), 0)
        self.fake.body = {"total": {"visits": "121", "signups": "2"}, "rows": []}
        self.assertEqual(sync.run(self.job()[0]), 0)
        db = store.reader(self.folder)
        try:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM answers").fetchone()[0], 1)
            figs = store.latest(db, SITE, "fake")[0]["figures"]
        finally:
            db.close()
        self.assertEqual([(f["name"], f["value"]) for f in figs],
                         [("visits", 121), ("signups", 2)])
        self.assertEqual(sync.run(self.job(NOW + timedelta(days=1))[0]), 0)
        db = store.reader(self.folder)
        try:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM answers").fetchone()[0], 2,
                             "another window is kept")
            self.assertEqual(store.latest(db, SITE, "fake")[0]["end"], "2026-10-28")
        finally:
            db.close()

    def test_a_failure_keeps_the_figures_and_mails_once(self):
        self.config["mail"] = {"host": "smtp.example.com", "from": "skald@example.com",
                               "to": ["owner@example.com"], "security": "none"}
        self.connect()
        self.assertEqual(sync.run(self.job()[0]), 0)
        self.fake.fail = "Fake Tool refused the token: it may have been deleted."
        for _ in range(3):
            self.assertEqual(sync.run(self.job()[0]), 1)
        part = conn.load(self.folder, SITE)["fake"]
        self.assertEqual(part["error"], self.fake.fail)
        self.assertEqual(conn.status(part, True)["state"], "failing")
        self.assertEqual(len(self.mails), 1, "one mail per run of failures")
        self.assertIn("stopped answering for example.com", self.mails[0]["Subject"])
        self.assertNotIn(ys.KEY, self.mails[0].as_string())
        db = store.reader(self.folder)
        try:
            self.assertEqual(len(store.latest(db, SITE, "fake")[0]["figures"]), 4, "kept")
        finally:
            db.close()
        later = conn.status(part, True, datetime.now(timezone.utc) + timedelta(hours=27))
        self.assertEqual(later["words"], "Stopped answering")
        self.fake.fail = None
        self.assertEqual(sync.run(self.job()[0]), 0)
        part = conn.load(self.folder, SITE)["fake"]
        self.assertEqual((part["error"], part["error_mailed"]), (None, None))

    def test_an_answer_the_tool_cannot_read_keeps_nothing(self):
        self.connect()
        self.fake.body = {"total": {"visits": "many"}, "rows": []}
        job, out = self.job()
        self.assertEqual(sync.run(job), 1)
        self.assertIn("could not read Fake Tool's answer (ValueError)",
                      conn.load(self.folder, SITE)["fake"]["error"])
        self.assertIsNone(store.reader(self.folder), "nothing stored")

    def test_off_or_without_a_key_nothing_is_asked(self):
        self.assertEqual(sync.run(self.job()[0]), 0)
        sync.connect(self.config, self.folder, SITE, "fake", {"account": "acme"}, "cli")
        self.assertEqual(sync.run(self.job()[0]), 0)
        self.assertEqual(self.fake.asked, [])
        self.connect()
        sync.pause(self.folder, SITE, "fake")
        self.assertEqual(sync.run(self.job()[0]), 0)
        self.assertEqual(self.fake.asked, [], "paused: never asked")
        self.assertTrue(keys.state(self.config, self.folder, SITE, "fake")["set"], "key stays")

    def test_one_sync_of_a_site_at_a_time(self):
        self.connect()
        with conn.lock(self.folder, SITE):
            job, out = self.job()
            self.assertEqual(sync.run(job), 3)
        self.assertIn("already running", " ".join(out))


class Audit(Base):
    def synced(self):
        self.connect()
        self.assertEqual(sync.run(self.job()[0]), 0)
        return sqlite3.connect(store.path_for(self.folder))

    def test_every_figure_matches_its_answer(self):
        self.synced().close()
        got = recount.check(self.folder, SITE)
        self.assertEqual(got["fake"]["ok"], True, got)
        self.assertEqual((got["fake"]["answers"], got["fake"]["figures"]), (1, 4))

    def test_a_changed_figure_a_zero_for_nothing_or_a_changed_answer_is_a_mismatch(self):
        db = self.synced()
        with db:
            db.execute("UPDATE figures SET value = 121 WHERE name = 'visits' AND dim IS NULL")
            db.execute("UPDATE figures SET value = 0 WHERE name = 'signups'")
            db.execute("UPDATE figures SET dim = '/about' WHERE dim = '/pricing'")
        db.close()
        problems = recount.check(self.folder, SITE)["fake"]["problems"]
        self.assertTrue(any("shown 121, the answer says 120" in p for p in problems), problems)
        self.assertTrue(any("shown as 0 with no place" in p for p in problems), problems)
        self.assertTrue(any("'/about'" in p and "'/pricing'" in p for p in problems), problems)
        db = sqlite3.connect(store.path_for(self.folder))
        with db:
            db.execute("UPDATE answers SET body = replace(body, '120', '999')")
        db.close()
        problems = recount.check(self.folder, SITE)["fake"]["problems"]
        self.assertIn("changed since it came", problems[0])

    def test_the_sync_keeps_the_recheck_and_a_mismatch_withholds(self):
        db = self.synced()
        with db:
            db.execute("UPDATE figures SET value = 7 WHERE name = 'visits' AND dim = '/'")
        db.close()
        with mock.patch.object(store, "keep", lambda *a, **k: None):
            self.assertEqual(sync.run(self.job()[0]), 1, "the recheck failed")
        part = conn.load(self.folder, SITE)["fake"]
        self.assertFalse(part["audit"]["ok"])
        self.assertEqual(conn.status(part, True)["state"], "withheld")

    def test_the_audit_shares_only_the_name_lists(self):
        import ast
        tree = ast.parse(Path(recount.__file__).read_text())
        imported = {(n.module, n.level) for n in ast.walk(tree)
                    if isinstance(n, ast.ImportFrom)}
        self.assertEqual({m for m, level in imported if level}, {"names"})


class Cli(Base):
    def run_cli(self, *args, stdin=""):
        from skald import cli
        cfg = self.folder / "config.yml"
        cfg.write_text(json.dumps(self.config))
        out = io.StringIO()
        with mock.patch("sys.stdin", io.StringIO(stdin)), redirect_stdout(out):
            code = cli.main(["--config", str(cfg), *args])
        return code, out.getvalue()

    def test_connect_from_stdin_status_pause_and_audit(self):
        code, out = self.run_cli("tools", "connect", "fake", "--option", "account=acme",
                                 "--key-stdin", stdin=ys.KEY + "\n")
        self.assertEqual(code, 0, out)
        self.assertIn("connected (token ...QrSt)", out)
        code, out = self.run_cli("tools", "status")
        self.assertIn("Fake Tool example.com: Waiting for its first answer; account acme; "
                      "key: file (token ...QrSt)", out)
        self.assertNotIn(ys.KEY, out)
        self.assertEqual(self.run_cli("tools", "sync")[0], 0)
        code, out = self.run_cli("tools", "audit")
        self.assertEqual((code, "1 answer, 4 figures: match" in out), (0, True), out)
        self.assertEqual(self.run_cli("tools", "pause", "fake")[0], 0)
        self.assertIn("Paused", self.run_cli("tools", "status")[1])


class Scheduler(unittest.TestCase):
    def test_the_tools_job_runs_below_every_other_job(self):
        import importlib.util
        root = Path(__file__).resolve().parent.parent
        spec = importlib.util.spec_from_file_location("skald_sched_tools",
                                                      root / "docker" / "scheduler.py")
        sched = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(sched)
        s = sched.Scheduler("/x/config.yml", "UTC", 2, "07:15", "03:30", tools_hours=6)
        job = next(j for j in s.jobs if j.name == "tools")
        self.assertEqual(job.args[-2:], ["tools", "sync"])
        self.assertEqual(job.nicer, sched.TOOLS_NICE)
        self.assertGreater(job.nicer, 0)
        self.assertEqual({j.nicer for j in s.jobs if j.name != "tools"}, {0})
        off = sched.Scheduler("/x/config.yml", "UTC", 2, "07:15", "03:30", tools_hours=0)
        self.assertNotIn("tools", [j.name for j in off.jobs])


class Mcp(Base):
    def ctx(self):
        folder, config = self.folder, self.config
        return type("Ctx", (), {"site": lambda s, x: x or SITE, "config_for": lambda s, x: config,
                                "history_path": folder / "h.sqlite", "live_dir": folder})()

    def test_your_tools_labels_every_figure_and_never_a_key(self):
        from skald.mcp import tools_yourtools
        text, got = tools_yourtools.your_tools(self.ctx(), {})
        self.assertIn("no tool of the user's own is connected", text)
        self.connect()
        self.assertEqual(sync.run(self.job()[0]), 0)
        text, got = tools_yourtools.your_tools(self.ctx(), {"site": SITE})
        self.assertIn("never add them to Skald's figures", text)
        self.assertIn("Fake Tool: Answering", text)
        self.assertIn("Counted from: Fake Tool", text)
        self.assertIn("Visits 120, Signups not given", text)
        self.assertIn("/pricing: Visits 40", text)
        self.assertNotIn("QrSt", text + json.dumps(got))
        self.assertNotIn("key", got["tools"][0])


class Words(unittest.TestCase):
    def test_the_label_names_the_tool(self):
        self.assertEqual(COUNTED_FROM, "Counted from")


if __name__ == "__main__":
    unittest.main()
