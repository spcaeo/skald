"""`skald doctor` (doctor.py): one line per part, OK or NEEDS ATTENTION, the
fix in plain words, the same as JSON, and the helper probe (roads.helper).
Addresses are RFC 5737; hosts example.com; the SMTP login is made up."""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import threading
import unittest
from datetime import date, datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from support import SECRETS, Sandbox, line  # noqa: E402

from skald import doctor, runs  # noqa: E402
from skald.conversions import roads  # noqa: E402

DOWN = {"up": False, "script": None, "error": "ConnectionRefusedError: refused"}
UP = {"up": True, "script": False, "error": None}
NOW = datetime(2026, 10, 9, 8, 0, tzinfo=timezone.utc)


def readers(day: date, n: int) -> list[str]:
    noon = datetime(day.year, day.month, day.day, 12, tzinfo=timezone.utc)
    return [line(noon + timedelta(minutes=i), f"203.0.113.{10 + i}") for i in range(n)]


class Doctor(unittest.TestCase):
    def setUp(self):
        self.box = Sandbox(mail=False)
        patcher = mock.patch.object(roads, "helper", return_value=DOWN)
        patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        self.box.close()

    def doctor(self, *extra):
        return self.box.run("--today", "2026-10-09", "doctor", *extra)

    def stored_week(self):
        """Oct 1-8 in the log, Oct 3 without a line; Oct 5 then withheld."""
        lines = []
        for i in range(8):
            day = date(2026, 10, 1) + timedelta(days=i)
            if day != date(2026, 10, 3):
                lines += readers(day, 3)
        self.box.log(lines)
        code, _, err = self.box.run("--today", "2026-10-09", "backfill", "--days", "8")
        self.assertIn(code, (0, 1), err)
        db = sqlite3.connect(self.box.db)
        try:
            db.execute("UPDATE days SET verified = 0 WHERE day = '2026-10-05'")
            db.commit()
        finally:
            db.close()

    def test_a_fresh_install_says_what_to_do(self):
        code, out, err = self.doctor()
        self.assertEqual(code, 1, out + err)
        self.assertIn("NEEDS ATTENTION  Daily run: has never run here", out)
        self.assertIn("Days stored: no day stored yet", out)
        self.assertIn("backfill --days 14", out)
        self.assertIn("Hook receiver: the beacon helper does not answer", out)
        self.assertIn("OFF              Hooks: no hook set up", out)
        self.assertIn("OFF              Mail: no SMTP server set", out)
        self.assertIn("OFF              Page assets: not needed", out)
        self.assertIn("Web app: off: the dashboard is a plain page", out)   # app: false here
        self.assertIn("Remove `app: false`", out)
        self.assertRegex(out, r"\d+ parts need attention")

    def test_missing_and_withheld_days_and_the_backfill_command(self):
        self.stored_week()
        runs.record(self.box.root, "run-daily", 0, now=NOW, outcome="ok")
        _, out, _ = self.doctor()
        self.assertIn("OK               Daily run: ran 4 h ago", out)
        self.assertIn("Days stored: 1 missing (2026-10-03), 1 withheld (2026-10-05)", out)
        self.assertIn("backfill --days 6`", out)
        self.assertIn("audit --day 2026-10-05", out)

    def test_yesterday_waits_for_todays_run(self):
        self.stored_week()
        db = sqlite3.connect(self.box.db)
        try:
            db.execute("DELETE FROM days WHERE day = '2026-10-08'")
            db.execute("UPDATE days SET verified = 1")
            db.commit()
        finally:
            db.close()
        runs.record(self.box.root, "run-daily", 0, now=NOW - timedelta(days=1), outcome="ok")
        _, out, _ = self.doctor()
        self.assertIn("missing (2026-10-03)", out)
        self.assertNotIn("2026-10-08", out)
        runs.record(self.box.root, "run-daily", 1, now=NOW, outcome="failed")
        _, out, _ = self.doctor()
        self.assertIn("2 missing (2026-10-03, 2026-10-08)", out)
        self.assertIn("Daily run: failed 4 h ago", out)

    def test_a_late_or_withheld_run(self):
        runs.record(self.box.root, "run-daily", 0, now=NOW - timedelta(days=3), outcome="ok")
        _, out, _ = self.doctor()
        self.assertIn("Daily run: last ran 3 days ago: it did not run today", out)
        runs.record(self.box.root, "run-daily", 1, now=NOW, outcome="withheld")
        _, out, _ = self.doctor()
        self.assertIn("stopped on purpose 4 h ago", out)

    def test_json_is_the_same_list(self):
        code, out, _ = self.doctor("--json")
        got = json.loads(out)
        self.assertEqual(code, 1)
        self.assertEqual(got["site"], "example.com")
        ids = [c["id"] for c in got["checks"]]
        for want in ("daily_run", "days", "logs", "assets", "app", "receiver", "hooks",
                     "script", "mail", "version", "disk"):
            self.assertIn(want, ids)
        self.assertEqual(got["attention"],
                         sum(1 for c in got["checks"] if c["state"] == "NEEDS ATTENTION"))
        self.assertTrue(all(set(c) == {"id", "part", "state", "says", "fix"}
                            for c in got["checks"]))

    def test_asset_prefix_seen_or_not(self):
        text = self.box.config.read_text().replace("  require_rendering: false\n",
                                                   "  asset_prefixes: [/assets/]\n")
        self.box.config.write_text(text)
        self.box.log(readers(date(2026, 10, 8), 2))
        _, out, _ = self.doctor()
        self.assertIn("NEEDS ATTENTION  Page assets: no request for /assets/", out)
        self.assertIn("site.asset_prefixes", out)
        self.box.log(readers(date(2026, 10, 8), 2) + [
            line(datetime(2026, 10, 8, 12, 1, tzinfo=timezone.utc), path="/assets/app.js")])
        _, out, _ = self.doctor()
        self.assertIn("OK               Page assets: requests for /assets/ seen", out)

    def test_a_missing_or_unreadable_log(self):
        text = self.box.config.read_text().replace(str(self.box.root / "logs"),
                                                   str(self.box.root / "nowhere"))
        self.box.config.write_text(text)
        _, out, _ = self.doctor()
        self.assertIn("Access log: the folder", out)
        self.assertIn("Set logs.dir", out)

    def test_mail_is_checked_never_sent_unless_asked(self):
        box = Sandbox(mail=True)
        self.addCleanup(box.close)
        _, out, _ = box.run("doctor")
        self.assertIn("NEEDS ATTENTION  Mail: cannot send: mail.user_env is not set", out)
        sent = []
        with mock.patch.dict(os.environ, SECRETS), \
                mock.patch("skald.mailer.send", lambda msg, cfg: sent.append(msg)):
            _, out, _ = box.run("doctor")
            self.assertIn("OK               Mail: set up: smtp.example.com:587 to 2 recipients",
                          out)
            self.assertEqual(sent, [])
            _, out, _ = box.run("doctor", "--send-test")
        self.assertIn("a test mail went to owner@example.com, second@example.com", out)
        self.assertEqual(len(sent), 1)
        self.assertIn("Test mail from the doctor", sent[0]["Subject"])

    def test_a_newer_version_from_the_file_only(self):
        (self.box.root / "updates.json").write_text(json.dumps({
            "checked_at": "2026-10-09T07:00:00+00:00", "ok": True, "latest": {
                "version": "99.0.0", "url": "https://github.com/spcaeo/skald/releases/tag/v99.0.0",
                "notes": []}}))
        with mock.patch("skald.updates._get", side_effect=AssertionError("network")):
            _, out, _ = self.doctor()
        self.assertIn("NEEDS ATTENTION  Version:", out)
        self.assertIn("99.0.0 is available", out)
        self.assertIn("upgrade --dry-run", out)

    def test_hooks_and_the_receiver(self):
        self.box.run("hooks", "secret", "example.com", "lead")
        with mock.patch.object(roads, "helper", return_value=UP):
            _, out, _ = self.doctor()
        self.assertIn("OK               Hook receiver: the beacon helper answers", out)
        self.assertIn("Hook Your site's server (lead): secret set, but nothing has arrived", out)
        self.assertIn("hooks test example.com lead", out)

    def test_the_commands_name_the_install(self):
        with mock.patch.object(doctor, "in_docker", return_value=True):
            self.assertEqual(doctor.command("/x/config.yml"), "docker exec skald skald")
        with mock.patch.object(doctor, "in_docker", return_value=False), \
                mock.patch.object(Path, "exists", return_value=False):
            self.assertEqual(doctor.command("/x/config.yml"), "./bin/skald --config /x/config.yml")

    def test_a_check_that_breaks_says_so(self):
        with mock.patch.object(doctor, "disk", side_effect=OSError("no such disk")):
            _, out, _ = self.doctor()
        self.assertIn("NEEDS ATTENTION  Disk: could not check: OSError: no such disk", out)


class Helper(unittest.TestCase):
    def serve(self, status: int):
        class Handler(BaseHTTPRequestHandler):
            def do_HEAD(self):
                self.send_response(status)
                self.send_header("Content-Length", "0")
                self.end_headers()

            def log_message(self, *a):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return f"http://127.0.0.1:{server.server_address[1]}"

    def test_up_with_or_without_the_script(self):
        self.assertEqual(roads.helper(self.serve(404)), UP)
        self.assertEqual(roads.helper(self.serve(200))["script"], True)

    def test_down(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), BaseHTTPRequestHandler)
        port = server.server_address[1]
        server.server_close()
        got = roads.helper(f"http://127.0.0.1:{port}", timeout=1)
        self.assertFalse(got["up"])
        self.assertTrue(got["error"])


if __name__ == "__main__":
    unittest.main()
