"""The failure mail (owner's rule, 2026-10-11): one short mail when the
morning run fails, none when it held a day back by design.

What is pinned: run-daily notes in runs.json whether a stop was by design (a
day that does not reconcile, an audit mismatch, a weekly mail held back for
an incomplete week) or a failure (a crash, no log line at all, a mail
setting missing); notify-failure mails only for a failure, once per failed
run, with no secret and no address in it; a run that left no fresh record
(it crashed on import) is mailed; and skald still mails when the package
itself does not import.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald import audit, cli, failmail, mailer, runs  # noqa: E402
from skald.verify import Problem  # noqa: E402

from support import FIXTURES, ROOT, SECRETS, Sandbox, day_lines  # noqa: E402

TODAY = "2026-10-06"
MONDAY = "2026-10-05"


class FailCase(unittest.TestCase):

    def setUp(self):
        self.box = Sandbox()
        self.logfile = self.box.root / "run.log"

    def tearDown(self):
        self.box.close()

    def run_daily(self, today: str = TODAY, env: dict = SECRETS):
        """run-daily as cron runs it, its output appended to run.log."""
        with mock.patch.dict(os.environ, env), \
                mock.patch.object(mailer.smtplib, "SMTP"):
            code, out, err = self.box.run("--today", today, "run-daily")
        with open(self.logfile, "a") as handle:
            handle.write(out + err)
        return code

    def notify(self, *extra: str, code: int = 1):
        with mock.patch.dict(os.environ, SECRETS), \
                mock.patch.object(failmail.smtplib, "SMTP") as smtp:
            got, out, err = self.box.run("notify-failure", "--job", "run-daily",
                                         "--exit", str(code), "--log", str(self.logfile),
                                         *extra)
        sent = [c[0][0] for c in smtp.return_value.send_message.call_args_list]
        return got, out, sent

    def outcome(self) -> str:
        return runs.load(self.box.root)["run-daily"]["last_outcome"]


class TestByDesignSendsNothing(FailCase):

    def test_a_good_run_is_ok(self):
        self.box.log(day_lines(date(2026, 10, 5), 3))
        self.assertEqual(self.run_daily(), 0)
        self.assertEqual(self.outcome(), "ok")

    def test_figures_that_do_not_reconcile_are_withheld_not_failed(self):
        self.box.log(day_lines(date(2026, 10, 5), 3))
        wrong = [("site", [Problem("groups do not add up", "1 short")])]
        with mock.patch.object(cli.Context, "problems", return_value=wrong):
            self.assertEqual(self.run_daily(), 1)
        self.assertIn("stopped at 'check'", self.logfile.read_text())
        self.assertEqual(self.outcome(), "withheld")
        code, out, sent = self.notify()
        self.assertEqual((code, sent), (0, []))
        self.assertIn("by design", out)

    def test_an_audit_mismatch_is_withheld_not_failed(self):
        self.box.log(day_lines(date(2026, 10, 5), 3))
        real = audit.recount

        def off_by_one(*args, **kwargs):
            figures = real(*args, **kwargs)
            figures["requests"] += 1
            return figures

        with mock.patch.object(audit, "recount", off_by_one):
            self.assertEqual(self.run_daily(), 1)
        self.assertIn("stopped at 'audit'", self.logfile.read_text())
        self.assertEqual(self.outcome(), "withheld")
        self.assertEqual(self.notify()[2], [])

    def test_a_weekly_mail_held_back_for_an_incomplete_week_is_by_design(self):
        self.box.log(day_lines(date(2026, 10, 4), 3))
        self.assertEqual(self.run_daily(MONDAY), 1)
        self.assertIn("stopped at 'weekly mail'", self.logfile.read_text())
        self.assertEqual(self.outcome(), "withheld")
        self.assertEqual(self.notify()[2], [])


class TestFailuresAreMailedOnce(FailCase):

    def test_a_crashing_step_is_noted_and_mailed_once(self):
        self.box.log(day_lines(date(2026, 10, 5), 3))
        with mock.patch.object(cli, "cmd_dashboard", side_effect=RuntimeError("disk full")):
            with self.assertRaises(RuntimeError):
                self.run_daily()
        self.assertEqual(self.outcome(), "failed")
        self.logfile.write_text("check ok\nRuntimeError: disk full\n")
        code, out, sent = self.notify()
        self.assertEqual(code, 0, out)
        self.assertEqual(len(sent), 1)
        msg = sent[0]
        self.assertEqual(msg["Subject"],
                         f"[traffic] Daily run failed {datetime.now(timezone.utc):%Y-%m-%d}")
        self.assertEqual(msg["To"], "owner@example.com, second@example.com")
        body = msg.get_content()
        self.assertIn("RuntimeError: disk full", body)
        self.assertIn("What to check", body)
        # The same failed run again (a second cron line, a hand rerun): no second mail.
        code, out, sent = self.notify()
        self.assertEqual((code, sent), (0, []))
        self.assertIn("already mailed", out)
        self.assertEqual(len(self.notify("--force")[2]), 1)

    def test_no_log_line_for_the_day_is_a_failure(self):
        self.box.log((FIXTURES / "unparsable.log").read_text().splitlines(True))
        self.assertEqual(self.run_daily(), 1)
        self.assertEqual(self.outcome(), "failed")
        self.assertEqual(len(self.notify()[2]), 1)

    def test_a_mail_setting_missing_is_a_failure(self):
        self.box.log(day_lines(date(2026, 10, 5), 3))
        self.assertEqual(self.run_daily(env={}), 1)
        self.assertIn("stopped at 'daily mail'", self.logfile.read_text())
        self.assertEqual(self.outcome(), "failed")

    def test_a_run_that_left_no_fresh_record_is_mailed(self):
        """Yesterday's record says withheld; today's run crashed on import
        and wrote nothing. That is a failure."""
        old = datetime.now(timezone.utc) - timedelta(days=1)
        runs.record(self.box.root, "run-daily", 1, now=old, outcome="withheld")
        self.logfile.write_text("ImportError: cannot import name 'x'\n")
        code, out, sent = self.notify()
        self.assertEqual(len(sent), 1)
        self.assertIn("left no record of this run", sent[0].get_content())

    def test_an_exit_code_that_disagrees_with_the_record_is_mailed(self):
        runs.record(self.box.root, "run-daily", 1, outcome="withheld")
        self.assertEqual(len(self.notify(code=2)[2]), 1)

    def test_a_mail_that_cannot_be_sent_is_said_once_and_never_retried(self):
        self.logfile.write_text("Traceback\n")
        with mock.patch.dict(os.environ, SECRETS), \
                mock.patch.object(failmail.smtplib, "SMTP") as smtp:
            smtp.return_value.send_message.side_effect = OSError("relay down")
            code, out, err = self.box.run("notify-failure", "--exit", "1",
                                          "--log", str(self.logfile))
        self.assertEqual(code, 1)
        self.assertIn("NOT SENT", out)
        state = json.loads((self.box.root / failmail.STATE).read_text())
        self.assertEqual(state["run-daily"]["error"], "OSError")
        self.assertEqual(self.notify()[2], [])

    def test_exit_zero_sends_nothing(self):
        self.assertEqual(self.notify(code=0)[2], [])


class TestNoSecretInTheMail(FailCase):

    def test_login_values_are_hidden_and_addresses_masked(self):
        self.logfile.write_text(
            f"login failed for {SECRETS['TI_TEST_SMTP_USER']} with "
            f"{SECRETS['TI_TEST_SMTP_PASSWORD']}\n"
            "from 192.0.2.44 and 2001:db8::7 at 11:15:02\n")
        sent = self.notify()[2]
        body = sent[0].get_content()
        for value in list(SECRETS.values()) + ["192.0.2.44", "2001:db8::7"]:
            self.assertNotIn(value, body)
            self.assertNotIn(value, str(sent[0]))
        self.assertIn("[hidden]", body)
        self.assertIn("[address]", body)
        self.assertIn("11:15:02", body)


class TestSameRecipientsAsTheDailyMail(FailCase):
    """Recipients and the sender set on the Mail page (settings_store, rows
    in accounts.sqlite beside the history) reach the failure mail too; a
    recipient who has not confirmed does not. If the merged view cannot be
    read, config.yml's own list is used."""

    def setUp(self):
        super().setUp()
        from skald import accounts, mail_confirm, settings_store
        db = accounts.connect(self.box.root / "accounts.sqlite")
        try:
            org = accounts.create_org(db, "Example", "cli")
            accounts.assign_site(db, "example.com", org["id"], "cli")
            settings_store.put(db, "site:example.com", "mail.to",
                               ["owner@example.com", "added@example.com",
                                "waiting@example.com"], "cli")
            settings_store.put(db, "install", "mail.from", "reports@example.com", "cli")
            mail_confirm.mark_confirmed(db, org["id"], "added@example.com")
        finally:
            db.close()
        self.box.log(day_lines(date(2026, 10, 5), 3))
        with mock.patch.object(cli, "cmd_dashboard", side_effect=RuntimeError("disk full")):
            with self.assertRaises(RuntimeError):
                self.run_daily()

    def test_the_mail_page_recipients_confirmed_only(self):
        code, out, sent = self.notify()
        self.assertEqual((code, len(sent)), (0, 1), out)
        to = sent[0]["To"]
        self.assertIn("owner@example.com", to)
        self.assertIn("added@example.com", to)
        self.assertNotIn("waiting@example.com", to)
        self.assertNotIn("second@example.com", to)     # the page's list replaces config.yml's
        self.assertIn("reports@example.com", sent[0]["From"])

    def test_config_yml_when_the_merged_view_cannot_be_read(self):
        import argparse
        from skald import settings_store
        args = argparse.Namespace(config=str(self.box.config), job="run-daily", exit=1,
                                  log=str(self.logfile), dry_run=False, force=False)
        said = []
        with mock.patch.dict(os.environ, SECRETS), \
                mock.patch.object(failmail.smtplib, "SMTP") as smtp, \
                mock.patch.object(settings_store, "apply", side_effect=RuntimeError("broken")):
            code = failmail.notify(args, said.append)
        sent = [c[0][0] for c in smtp.return_value.send_message.call_args_list]
        self.assertEqual((code, len(sent)), (0, 1), said)
        self.assertIn("config.yml", " ".join(said))
        self.assertEqual(sent[0]["To"], "owner@example.com, second@example.com")
        self.assertIn("traffic@example.com", sent[0]["From"])


class TestStillMailsWhenThePackageIsBroken(unittest.TestCase):

    def test_ti_py_loads_the_failure_mail_by_its_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "skald").mkdir()
            (root / "bin").mkdir()
            shutil.copy(ROOT / "bin/skald", root / "bin/skald")
            for name in ("failmail.py", "config.py", "brand.py"):
                shutil.copy(ROOT / "skald" / name, root / "skald" / name)
            # The rest of the package does not even import.
            (root / "skald" / "__init__.py").write_text("raise ImportError('broken')\n")
            (root / "skald" / "cli.py").write_text("this is not python\n")
            config = root / "config.yml"
            config.write_text(
                "site:\n  name: example.com\nhistory:\n  db: history.sqlite\n"
                "mail:\n  host: smtp.example.com\n  from: traffic@example.com\n"
                "  to: [owner@example.com]\n  user_env: TI_TEST_SMTP_USER\n"
                "  password_env: TI_TEST_SMTP_PASSWORD\n")
            log = root / "run.log"
            log.write_text("SyntaxError: invalid syntax\n")
            env = {**os.environ, **SECRETS}
            got = subprocess.run(
                [sys.executable, str(root / "bin/skald"), "--config", str(config),
                 "notify-failure", "--job", "run-daily", "--exit", "1",
                 "--log", str(log), "--dry-run"],
                capture_output=True, text=True, env=env, cwd=tmp, timeout=60)
            self.assertEqual(got.returncode, 0, got.stderr)
            self.assertIn("Subject: [", got.stdout)
            self.assertIn("Daily run failed", got.stdout)
            self.assertIn("SyntaxError: invalid syntax", got.stdout)
            self.assertNotIn(SECRETS["TI_TEST_SMTP_PASSWORD"], got.stdout)


if __name__ == "__main__":
    unittest.main()
