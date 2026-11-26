"""Yesterday stored soon after midnight: `skald close-day` (SKALD-61, 2026-11-26).

Seen live on 26 Nov at 02:40 New York time: every site's 25 Nov was "missing" (not
collected), so Yesterday showed nothing and 7 days ended its visit list on 24 Nov. A
day was stored only by run-daily at 07:15. Pinned here: close-day stores yesterday with
run-daily's own check, collect and audit, draws the dashboard, leaves a day already
stored alone, and the morning run still counts the day again (late lines included). The
scheduler runs it at 00:20 in the site's zone; "off" turns it off.
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald import cli, day_close, mailer, multisite, runs  # noqa: E402

from support import CHROME, SECRETS, Sandbox, day_lines, line  # noqa: E402

UTC = timezone.utc
DAY = date(2026, 10, 5)
TODAY = "2026-10-06"             # close-day closes the day before --today


def stored(box: Sandbox, day: date = DAY) -> dict:
    with sqlite3.connect(box.db) as db:
        row = db.execute("SELECT verified, collected_at FROM days WHERE site = ? AND day = ?",
                         ("example.com", day.isoformat())).fetchone()
        people = db.execute("SELECT hits FROM groups WHERE site = ? AND day = ? AND grp = 'people'",
                            ("example.com", day.isoformat())).fetchone()
    return {"verified": row[0], "collected_at": row[1], "people": people[0] if people else 0} if row else {}


class CloseDay(unittest.TestCase):

    def setUp(self):
        self.box = Sandbox()
        self.addCleanup(self.box.close)

    def ctx(self, *argv: str) -> cli.Context:
        return cli.Context(cli.parser().parse_args(["--config", str(self.box.config), *argv]))

    def test_yesterday_is_stored_audited_and_drawn(self):
        self.box.log(day_lines(DAY, 3))
        code, out, err = self.box.run("--today", TODAY, "close-day")
        self.assertEqual(code, 0, err)
        self.assertIn("all match", out, "the audit's recount, as at 07:15")
        self.assertIn(f"{DAY} closed; run-daily counts it again in the morning", out)
        got = stored(self.box)
        self.assertEqual((got["verified"], got["people"]), (1, 3))
        self.assertTrue((self.box.root / "www").exists(), "the dashboard is drawn again")
        entry = runs.load(self.ctx("--today", TODAY, "close-day").live_dir)["close-day"]
        self.assertEqual((entry["last_exit"], entry["last_outcome"]), (0, "ok"))

    def test_only_the_days_own_steps(self):
        """No mail, no recount beside the log, no network: those wait for run-daily."""
        names = [n for n, _ in day_close.close_steps(self.ctx("--today", TODAY, "close-day"))]
        self.assertEqual(names, ["check", "collect", "audit", "dashboard"])
        self.assertEqual(set(names) - set(day_close.CLOSE_STEPS), set())
        morning = [n for n, _ in cli.daily_steps(self.ctx("--today", TODAY, "run-daily"))]
        self.assertEqual(morning[:3], ["check", "collect", "audit"], "the same three, shared")

    def test_a_day_stored_already_is_left_alone(self):
        self.box.log(day_lines(DAY, 3))
        self.assertEqual(self.box.run("--today", TODAY, "close-day")[0], 0)
        first = stored(self.box)["collected_at"]
        code, out, _ = self.box.run("--today", TODAY, "close-day")
        self.assertEqual(code, 0)
        self.assertIn("nothing to close", out)
        self.assertEqual(stored(self.box)["collected_at"], first, "not counted a second time")

    def test_the_morning_run_counts_it_again_with_a_late_line(self):
        """A line a remote sender delivers after 00:20 is in the morning's count."""
        lines = day_lines(DAY, 3)
        self.box.log(lines)
        self.assertEqual(self.box.run("--today", TODAY, "close-day")[0], 0)
        self.assertEqual(stored(self.box)["people"], 3)
        late = datetime(2026, 10, 5, 23, 50, tzinfo=UTC)
        self.box.log(lines + [line(late, "203.0.113.99", "/late/", CHROME)])
        with mock.patch.dict(os.environ, SECRETS), mock.patch.object(mailer.smtplib, "SMTP"):
            code, out, err = self.box.run("--today", TODAY, "run-daily")
        self.assertEqual(code, 0, err + out)
        self.assertEqual(stored(self.box)["people"], 4, "the morning's count is the one kept")

    def test_a_day_that_does_not_add_up_is_not_stored(self):
        self.box.log(["this is not a log line\n"] * 3)
        code, _, err = self.box.run("--today", TODAY, "close-day")
        self.assertEqual(code, 1)
        self.assertIn("stopped at 'check'", err)
        self.assertEqual(stored(self.box), {})
        entry = runs.load(self.ctx("--today", TODAY, "close-day").live_dir)["close-day"]
        self.assertEqual((entry["last_outcome"], entry["last_step"]), ("failed", "check"))

    def test_an_audit_that_does_not_match_counts_the_day_once_more(self):
        """A late line landing between the collect and its audit (review): one more
        count reads it on both roads, so the day is not withheld till the morning."""
        self.box.log(day_lines(DAY, 3))
        real, calls = cli.audit_day, []

        def audit(ctx, day, *a, **kw):
            calls.append(day)
            return 1 if len(calls) == 1 else real(ctx, day, *a, **kw)
        with mock.patch.object(cli, "audit_day", audit):
            code, out, err = self.box.run("--today", TODAY, "close-day")
        self.assertEqual(code, 0, err)
        self.assertIn("the day is counted once more", out)
        self.assertEqual(len(calls), 2)
        self.assertEqual(stored(self.box)["verified"], 1)
        entry = runs.load(self.ctx("--today", TODAY, "close-day").live_dir)["close-day"]
        self.assertEqual(entry["last_outcome"], "ok")

    def test_a_second_mismatch_leaves_it_withheld(self):
        self.box.log(day_lines(DAY, 3))

        def audit(ctx, day, *a, **kw):
            ctx.by_design = "the audit's recount does not match; the day is withheld"
            return 1
        with mock.patch.object(cli, "audit_day", audit):
            code, _, _ = self.box.run("--today", TODAY, "close-day")
        self.assertEqual(code, 1)
        entry = runs.load(self.ctx("--today", TODAY, "close-day").live_dir)["close-day"]
        self.assertEqual((entry["last_outcome"], entry["last_step"]), ("withheld", "audit"))

    def test_every_site_and_never_a_paused_one(self):
        self.assertIn("close-day", multisite.PER_SITE)
        self.assertIn("close-day", multisite.COLLECTING)


class BeforeTheMorningRun(unittest.TestCase):
    """Until run-daily has run since midnight, yesterday may be close-day's count (review)."""

    def setUp(self):
        self.tmp = Path(__import__("tempfile").mkdtemp())
        self.addCleanup(__import__("shutil").rmtree, self.tmp, True)
        self.tz = __import__("zoneinfo").ZoneInfo("America/New_York")
        self.now = datetime(2026, 11, 26, 6, 0, tzinfo=UTC)               # 01:00 EST

    def test_morning_ran(self):
        self.assertFalse(day_close.morning_ran(self.tmp, self.now, self.tz), "never ran")
        runs.record(self.tmp, "run-daily", 0, now=datetime(2026, 11, 25, 12, 30, tzinfo=UTC))
        self.assertFalse(day_close.morning_ran(self.tmp, self.now, self.tz), "yesterday's run")
        later = datetime(2026, 11, 26, 13, 30, tzinfo=UTC)               # 08:30 EST
        runs.record(self.tmp, "run-daily", 1, now=datetime(2026, 11, 26, 12, 40, tzinfo=UTC))
        self.assertTrue(day_close.morning_ran(self.tmp, later, self.tz), "a failed run counts too")
        self.assertTrue(day_close.morning_ran(None, self.now, self.tz), "no folder: as before")

    def test_doctor_does_not_call_a_withheld_yesterday_a_problem_before_the_morning(self):
        from skald import doctor
        from skald.store import History
        box = Sandbox()
        self.addCleanup(box.close)
        box.log(day_lines(date(2026, 11, 24), 2) + day_lines(date(2026, 11, 25), 2))
        for d in ("2026-11-24", "2026-11-25"):
            self.assertEqual(box.run("--today", "2026-11-26", "collect", "--day", d)[0], 0)
        with History(box.db) as h:
            h.db.execute("UPDATE days SET verified = 0 WHERE day = '2026-11-25'")
            h.db.commit()
        tz = __import__("zoneinfo").ZoneInfo("UTC")
        now = datetime(2026, 11, 26, 1, 0, tzinfo=UTC)
        got = doctor.days_stored({}, box.db, "example.com", tz, now, self.tmp, "skald")
        self.assertEqual(got["state"], doctor.OK, got)
        runs.record(self.tmp, "run-daily", 1, now=datetime(2026, 11, 26, 7, 30, tzinfo=UTC))
        got = doctor.days_stored({}, box.db, "example.com", tz, now.replace(hour=8), self.tmp, "skald")
        self.assertNotEqual(got["state"], doctor.OK)
        self.assertIn("1 withheld", got["says"])


    def test_a_client_report_waits_for_the_mornings_count(self):
        """A report is sent once and never again: not from close-day's early count."""
        from skald import client_reports as cr, client_reports_send as rs
        box = Sandbox()
        self.addCleanup(box.close)
        box.log(day_lines(date(2026, 11, 25), 2))
        self.assertEqual(box.run("--today", "2026-11-26", "collect", "--day", "2026-11-25")[0], 0)
        report = {"spec": {"name": "weekly", "period": "last_7_days"}, "org_id": 1, "id": 1,
                  "created_at": None}
        now = datetime(2026, 11, 26, 3, 0, tzinfo=UTC)
        said = []
        with mock.patch.object(cr, "org_reports", return_value=[report]), \
                mock.patch.object(cr, "sends", return_value=[]), \
                mock.patch.object(cr, "due", return_value=date(2026, 11, 26)), \
                mock.patch.object(cr, "period_for", return_value=(date(2026, 11, 19), date(2026, 11, 25))), \
                mock.patch.object(rs, "send", return_value=(True, "sent")) as send:
            run = lambda when: rs.run_due({"report": {"timezone": "UTC"}}, box.db, None, "example.com",
                                          None, when, out=said.append, live_dir=self.tmp)
            run(now)
            send.assert_not_called()
            self.assertIn("waits for 2026-11-25 to be stored", said[-1])
            runs.record(self.tmp, "run-daily", 0, now=datetime(2026, 11, 26, 7, 40, tzinfo=UTC))
            run(now.replace(hour=8))
            send.assert_called_once()


class Dashboard(unittest.TestCase):
    """app.json says when yesterday's count was stored: the period line names it."""

    def test_yesterday_carries_its_counted_time(self):
        box = Sandbox(tz="America/New_York")
        self.addCleanup(box.close)
        box.config.write_text(box.config.read_text().replace("app: false", "app: true"))
        box.log(day_lines(DAY, 2, tz=__import__("zoneinfo").ZoneInfo("America/New_York")))
        code, _, err = box.run("--today", TODAY, "close-day")
        self.assertEqual(code, 0, err)
        app = json.loads(next((box.root / "www").rglob("app.json")).read_text())
        last = app["days"][-1]
        self.assertEqual((last["day"], last["state"]), (DAY.isoformat(), "ok"))
        when = datetime.fromisoformat(last["counted_at"])
        zone = __import__("zoneinfo").ZoneInfo("America/New_York")
        self.assertEqual(when.utcoffset(), datetime.now(zone).utcoffset(), "in the site's zone")
        self.assertLess(abs((when - datetime.now(UTC)).total_seconds()), 600)
        self.assertTrue(all("counted_at" not in d for d in app["days"][:-1]), "yesterday only")


class Scheduler(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, str(ROOT / "docker"))
        import scheduler
        self.s = scheduler
        # Its start line goes to stdout; keep the suite's last line "OK" (make-public verify).
        quiet = mock.patch("builtins.print")
        quiet.start()
        self.addCleanup(quiet.stop)

    def test_close_day_runs_at_00_20_in_the_sites_zone(self):
        sch = self.s.Scheduler("/tmp/config.yml", "America/New_York", 2, "07:15", "03:30",
                               close_at="00:20")
        job = next(j for j in sch.jobs if j.name == "close-day")
        self.assertEqual(job.args[-1], "close-day")
        self.assertFalse(job.notify, "run-daily counts the same day again and mails then")
        after = datetime(2026, 11, 26, 3, 0, tzinfo=UTC)          # 22:00 EST on 25 Nov
        self.assertEqual(job.due_after(after), datetime(2026, 11, 26, 5, 20, tzinfo=UTC))
        names = [j.name for j in sch.jobs]
        self.assertLess(names.index("close-day"), names.index("backup"))

    def test_the_default_and_off(self):
        self.assertEqual(self.s.daily_time(None, "00:20"), "00:20")
        self.assertEqual(self.s.daily_time("00:45", "00:20"), "00:45")
        self.assertIsNone(self.s.daily_time("off", "00:20"))
        sch = self.s.Scheduler("/tmp/config.yml", "UTC", 2, "07:15", "03:30")
        self.assertNotIn("close-day", [j.name for j in sch.jobs])

    def test_main_reads_skald_close_at(self):
        seen = {}

        class Fake:
            def __init__(self, *a, **kw):
                seen.update(kw)

            def run(self):
                return 0
        with mock.patch.object(self.s, "Scheduler", Fake), \
                mock.patch.dict(os.environ, {"SKALD_CLOSE_AT": ""}, clear=False):
            os.environ.pop("SKALD_CLOSE_AT")
            self.assertEqual(self.s.main(["--config", "/tmp/c.yml", "--tz", "UTC"]), 0)
        self.assertEqual(seen["close_at"], "00:20")
        with mock.patch.object(self.s, "Scheduler", Fake), \
                mock.patch.dict(os.environ, {"SKALD_CLOSE_AT": "off"}):
            self.s.main(["--config", "/tmp/c.yml", "--tz", "UTC"])
        self.assertIsNone(seen["close_at"])


if __name__ == "__main__":
    unittest.main()
