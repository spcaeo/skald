"""Tests for the system around the report: day windows, history, dashboard,
mail and the run-daily chain. Standard library only.

The same rules as test_skald.py: addresses are RFC 5737 documentation
ranges, the host is example.com, and every expected number is stated exactly.
Logs are written into a temporary directory per test, dated for the day under
test, so nothing depends on the date the suite happens to run.
"""
from __future__ import annotations

import gzip
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald import Group, check  # noqa: E402
from skald import cli, dashboard, mailer  # noqa: E402
from skald.store import SCHEMA_VERSION, History  # noqa: E402
from skald import data_files  # noqa: E402
from skald.verify import Problem  # noqa: E402
from skald.window import (analyse_window, day_window, files_for,  # noqa: E402
                                 range_window)

from support import (FIXTURES, NY, ROOT, SECRETS, UTC, Sandbox,  # noqa: E402
                     day_lines, line, totals_for)


# ------------------------------------------------------------------ windows

class TestDayWindows(unittest.TestCase):
    """A day is local midnight to local midnight, however long that is."""

    def test_an_ordinary_day_is_twenty_four_hours_from_local_midnight(self):
        start, end = day_window(date(2026, 10, 5), NY)
        self.assertEqual(start, datetime(2026, 10, 5, 4, tzinfo=UTC))
        self.assertEqual(end - start, timedelta(hours=24))

    def test_the_day_clocks_go_forward_is_twenty_three_hours(self):
        start, end = day_window(date(2026, 3, 8), NY)
        self.assertEqual(start, datetime(2026, 3, 8, 5, tzinfo=UTC))
        self.assertEqual(end - start, timedelta(hours=23))

    def test_the_day_clocks_go_back_is_twenty_five_hours(self):
        start, end = day_window(date(2026, 11, 1), NY)
        self.assertEqual(start, datetime(2026, 11, 1, 4, tzinfo=UTC))
        self.assertEqual(end, datetime(2026, 11, 2, 5, tzinfo=UTC))
        self.assertEqual(end - start, timedelta(hours=25))

    def test_a_range_runs_from_the_first_midnight_to_the_last(self):
        start, end = range_window(date(2026, 9, 28), date(2026, 10, 4), NY)
        self.assertEqual(start, datetime(2026, 9, 28, 4, tzinfo=UTC))
        self.assertEqual(end, datetime(2026, 10, 5, 4, tzinfo=UTC))

    def test_hits_are_cut_exactly_at_local_midnight_on_a_dst_day(self):
        """1 Nov 2026 in New York: 01:00-02:00 happens twice, and both
        happen on that day."""
        stamps = [
            datetime(2026, 11, 1, 3, 59, 59, tzinfo=UTC),   # 31 Oct 23:59:59 EDT - out
            datetime(2026, 11, 1, 4, 0, 0, tzinfo=UTC),     # 1 Nov 00:00 EDT - in
            datetime(2026, 11, 1, 5, 30, tzinfo=UTC),       # 01:30 EDT - in
            datetime(2026, 11, 1, 6, 30, tzinfo=UTC),       # 01:30 EST, again - in
            datetime(2026, 11, 2, 4, 59, 59, tzinfo=UTC),   # 1 Nov 23:59:59 EST - in
            datetime(2026, 11, 2, 5, 0, 0, tzinfo=UTC),     # 2 Nov 00:00 EST - out
        ]
        # Written with a local offset, as nginx would on a New York server.
        lines = [line(s.astimezone(NY), f"203.0.113.{20 + i}")
                 for i, s in enumerate(stamps)]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "access.log"
            path.write_text("".join(lines))
            start, end = day_window(date(2026, 11, 1), NY)
            totals = analyse_window({"logs": {"format": "auto"},
                                     "site": {"require_rendering": False}}, start, end,
                                    paths=[path])
        self.assertEqual(totals.parsed, 4)
        self.assertEqual(totals.groups[Group.PEOPLE].visits, 4)
        self.assertEqual(check(totals), [])

    def test_a_window_with_no_lines_fails_verify_rather_than_reading_zero(self):
        start, end = day_window(date(2026, 1, 1), UTC)
        totals = analyse_window({}, start, end, paths=[FIXTURES / "mixed_extended.log"])
        self.assertEqual(totals.parsed, 0)
        self.assertIn("nothing parsed", [p.what for p in check(totals)])


class TestRotationChoice(unittest.TestCase):
    """Which rotated files a day needs, decided from modification times."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        # Rotated at 06:25 UTC each day, so file k covers (rotation k+1,
        # rotation k]: .1 was last written 6 Oct 06:25, .2.gz 5 Oct, .3.gz
        # 4 Oct. The current file was written to a moment ago.
        self.paths = []
        for k, name in enumerate(["access.log", "access.log.1",
                                  "access.log.2.gz", "access.log.3.gz"]):
            p = self.dir / name
            p.write_text("")
            stamp = datetime(2026, 10, 7 - k, 6, 25, tzinfo=UTC).timestamp()
            if k == 0:
                stamp = datetime(2026, 10, 6, 20, 0, tzinfo=UTC).timestamp()
            os.utime(p, (stamp, stamp))
            self.paths.append(p)

    def tearDown(self):
        self._tmp.cleanup()

    def test_a_day_needs_the_two_files_either_side_of_its_rotation(self):
        start, end = day_window(date(2026, 10, 4), UTC)
        names = [p.name for p in files_for(self.paths, start, end)]
        # .3.gz holds up to 4 Oct 06:25, .2.gz the rest of the 4th. .1 starts
        # at 5 Oct 06:25, beyond the end of the day plus the six-hour slack.
        self.assertEqual(names, ["access.log.2.gz", "access.log.3.gz"])

    def test_a_file_last_written_before_the_window_is_never_opened(self):
        start, end = day_window(date(2026, 10, 6), UTC)
        names = [p.name for p in files_for(self.paths, start, end)]
        self.assertEqual(names, ["access.log", "access.log.1"])

    def test_a_day_split_across_a_rotation_is_counted_exactly(self):
        """Lines for 4 Oct live in two files; both halves are found and
        nothing from the 3rd or 5th leaks in."""
        def at(day, hour):
            return datetime(2026, 10, day, hour, tzinfo=UTC)
        files = {
            "access.log": [line(at(6, 8))],
            "access.log.1": [line(at(6, 5)), line(at(5, 7), "203.0.113.31")],
            "access.log.2.gz": [line(at(5, 5), "203.0.113.32"),
                                line(at(4, 23), "203.0.113.33"),
                                line(at(4, 7), "203.0.113.34")],
            "access.log.3.gz": [line(at(4, 5), "203.0.113.35"),
                                line(at(3, 23), "203.0.113.36")],
        }
        for p in self.paths:
            stamp = os.stat(p).st_mtime
            if p.suffix == ".gz":
                with gzip.open(p, "wt") as handle:
                    handle.write("".join(files[p.name]))
            else:
                p.write_text("".join(files[p.name]))
            os.utime(p, (stamp, stamp))
        config = {"logs": {"dir": str(self.dir), "base": "access.log"}}
        start, end = day_window(date(2026, 10, 4), UTC)
        totals = analyse_window(config, start, end,
                                now=datetime(2026, 10, 6, 21, tzinfo=UTC))
        self.assertEqual(totals.parsed, 3)


class TestReportDayOption(unittest.TestCase):
    """report.py --day: one exact day; --days keeps its old meaning."""

    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(ROOT / "report.py"), *args],
                              cwd=ROOT, capture_output=True, text=True, timeout=120)

    def test_day_selects_exactly_that_day(self):
        done = self.run_cli("--config", "config.example.yml", "--log",
                            "tests/fixtures/mixed_extended.log",
                            "--day", "2026-10-06", "--check")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("16 requests", done.stdout)

    def test_a_day_with_nothing_in_it_is_refused(self):
        done = self.run_cli("--config", "config.example.yml", "--log",
                            "tests/fixtures/mixed_extended.log",
                            "--day", "2026-10-07", "--check")
        self.assertEqual(done.returncode, 1)
        self.assertIn("nothing parsed", done.stderr)

    def test_the_cli_now_applies_site_hosts(self):
        """It did not: summarise was called without the host list, so a
        config's site.hosts was silently ignored on the command line."""
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "access.log"
            log.write_text("".join(day_lines(date(2026, 10, 5), 2)))
            done = self.run_cli("--config", "config.example.yml",
                                "--log", str(log), "--check")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("ok: 6 requests", done.stdout)


# ------------------------------------------------------------------ history

class TestHistory(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "h.sqlite"
        self.history = History(self.path)
        self.day = date(2026, 10, 5)
        self.totals = totals_for(day_lines(self.day, 3))

    def tearDown(self):
        self.history.close()
        self._tmp.cleanup()

    def counts(self):
        return {t: self.history.db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                for t in ("days", "groups", "counts")}

    def test_the_schema_version_is_stored(self):
        self.assertEqual(self.history.schema_version, SCHEMA_VERSION)

    def test_a_newer_schema_is_refused_not_misread(self):
        with self.history.db:
            self.history.db.execute(
                "UPDATE meta SET value = ? WHERE key = 'schema_version'",
                (str(SCHEMA_VERSION + 1),))
        with self.assertRaises(RuntimeError):
            History(self.path)

    def test_recording_a_day_twice_leaves_one_copy(self):
        self.history.record("example.com", self.day, self.totals, "UTC", [])
        first = self.counts()
        self.history.record("example.com", self.day, self.totals, "UTC", [])
        self.assertEqual(self.counts(), first)
        self.assertEqual(first["days"], 1)

    def test_a_second_record_replaces_the_first(self):
        self.history.record("example.com", self.day, self.totals, "UTC", [])
        bigger = totals_for(day_lines(self.day, 5))
        self.history.record("example.com", self.day, bigger, "UTC", [])
        period = self.history.period("example.com", self.day, self.day)
        self.assertEqual(period.totals.groups[Group.PEOPLE].visits, 5)
        self.assertEqual(period.totals.hits, bigger.hits)

    def test_a_period_rebuilds_the_same_figures_and_they_still_verify(self):
        self.history.record("example.com", self.day, self.totals, "UTC", [])
        got = self.history.period("example.com", self.day, self.day).totals
        self.assertEqual(check(got), [])
        self.assertEqual(got.hits, 7)
        self.assertEqual(got.parsed, 8)
        self.assertEqual(got.other_hosts, 1)
        for g in Group:
            if g in self.totals.groups:
                self.assertEqual(got.groups[g].hits, self.totals.groups[g].hits, g)
        people = got.groups[Group.PEOPLE]
        self.assertEqual((people.visits, people.views, people.cited_visits), (3, 3, 1))
        self.assertEqual(dict(people.cited_by), {"chatgpt.com": 1})
        self.assertEqual(dict(got.groups[Group.ANSWER_ENGINE].tiers),
                         {"training": 1, "asked": 1})
        self.assertEqual(dict(got.groups[Group.SEARCH_ENGINE].engines), {"Googlebot": 1})
        self.assertEqual(got.groups[Group.BOTS].probes, 1)

    def test_engines_are_stored_per_tier(self):
        self.history.record("example.com", self.day, self.totals, "UTC", [])
        tiers = self.history.engine_tiers("example.com", self.day, self.day)
        self.assertEqual(dict(tiers["training"]), {"GPTBot": 1})
        self.assertEqual(dict(tiers["asked"]), {"ChatGPT-User": 1})

    def test_a_week_sums_its_days(self):
        for i in range(7):
            self.history.record("example.com", self.day - timedelta(days=i),
                                self.totals, "UTC", [])
        period = self.history.period("example.com", self.day - timedelta(days=6), self.day)
        self.assertTrue(period.complete)
        self.assertEqual(period.totals.groups[Group.PEOPLE].visits, 21)
        self.assertEqual(check(period.totals), [])

    def test_no_address_or_user_agent_is_ever_written(self):
        totals = totals_for(day_lines(self.day, 3)
                            + open(FIXTURES / "mixed_extended.log").readlines())
        self.history.record("example.com", self.day, totals, "UTC", [])
        self.history.close()
        dump = "\n".join(sqlite3.connect(str(self.path)).iterdump())
        self.history = History(self.path)
        for forbidden in ("203.0.113.", "198.51.100.", "Mozilla/", "Chrome/",
                          "Macintosh", "AppleWebKit"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, dump)

    def test_a_withheld_day_is_kept_but_never_summed(self):
        self.history.record("example.com", self.day, self.totals, "UTC",
                            [Problem("groups do not sum", "test")])
        self.assertIs(self.history.status("example.com", self.day), False)
        period = self.history.period("example.com", self.day, self.day)
        self.assertEqual(period.withheld, [self.day])
        self.assertEqual(period.recorded, [])
        self.assertEqual(period.totals.hits, 0)


# The schema exactly as 01af148 created it - version 1, before
# days.unfiltered. A history file on a server was written by this.
# ---------------------------------------------------------------- dashboard

class TestDashboard(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.history = History(self.root / "h.sqlite")
        self.now = datetime(2026, 10, 6, 9, tzinfo=UTC)
        self.anchor = date(2026, 10, 5)
        # Previous week: 2 people a day. This week: 3 a day. One withheld day
        # three weeks back, inside the 30-day chart.
        for i in range(14):
            day = self.anchor - timedelta(days=i)
            self.history.record("example.com", day,
                                totals_for(day_lines(day, 3 if i < 7 else 2)), "UTC", [])
        bad = self.anchor - timedelta(days=20)
        self.history.record("example.com", bad, totals_for(day_lines(bad, 2)), "UTC",
                            [Problem("groups do not sum", "test")])
        self.page = dashboard.render(self.history, "example.com", UTC, self.now)

    def tearDown(self):
        self.history.close()
        self._tmp.cleanup()

    def test_it_carries_the_robots_and_referrer_metas(self):
        self.assertIn('<meta name="robots" content="noindex, nofollow, noarchive">', self.page)
        self.assertIn('<meta name="referrer" content="no-referrer">', self.page)

    def test_it_makes_no_external_request(self):
        for forbidden in ("http://", "https://", "<script", "<link", "src=",
                          "url(", "@import", "<img", "<iframe"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, self.page)

    def test_the_headline_numbers_match_history(self):
        week = self.history.period("example.com", self.anchor - timedelta(days=6),
                                   self.anchor).totals
        visits = week.groups[Group.PEOPLE].visits
        self.assertEqual(visits, 21)
        self.assertIn(f'<td>Last 7 days</td><td class="v">{visits}</td>', self.page)
        self.assertIn('<td>Yesterday</td><td class="v">3</td>', self.page)
        # 21 against 14 the week before.
        self.assertRegex(self.page, r'class="v">21</td><td class="c"[^>]*>▲ 50%')

    def test_a_partial_period_is_not_compared(self):
        self.assertIn("not comparable", self.page)  # 30 days: history starts later

    def test_a_withheld_day_is_shown_as_withheld_not_zero(self):
        self.assertIn("withheld: the figures did not reconcile", self.page)

    def test_charts_and_tables_are_accessible(self):
        # Requests by group (30 and 90 days), people, readers by hour.
        self.assertEqual(self.page.count('role="img"'), 4)
        self.assertEqual(len(re.findall(r"<desc id=", self.page)), 4)
        self.assertIn("<caption>", self.page)
        self.assertIn('<th scope="col"', self.page)
        self.assertIn('lang="en"', self.page)

    def test_tables_hold_the_history_figures(self):
        self.assertIn("GPTBot", self.page)
        self.assertIn("someone just asked", self.page)
        self.assertIn("Googlebot", self.page)
        self.assertIn("chatgpt.com", self.page)
        self.assertIn("Scanner probes", self.page)

    def test_write_is_atomic_and_leaves_no_temp_files(self):
        out = self.root / "www"
        written = dashboard.write(out, self.history, UTC, self.now)
        names = sorted(p.relative_to(out).as_posix() for p in written)
        self.assertEqual([n for n in names if n.endswith(".html")],
                         ["example.com/index.html", "index.html"])
        self.assertEqual([n for n in names if "/exports/" in n],
                         sorted(f"example.com/exports/{f}" for f in dashboard.EXPORTS))
        self.assertEqual([n for n in names if not n.endswith(".html") and "/exports/" not in n],
                         sorted(f"example.com/data/{f}.json" for f in data_files.files()))
        self.assertEqual([p.name for p in out.rglob(".*")], [])
        self.assertIn('href="example.com/"', (out / "index.html").read_text())
        self.assertEqual(oct(os.stat(out / "index.html").st_mode & 0o777), "0o644")

    def test_an_empty_history_still_renders(self):
        empty = History(self.root / "empty.sqlite")
        page = dashboard.render(empty, "example.com", UTC, self.now)
        empty.close()
        self.assertIn("No data collected yet", page)


# --------------------------------------------------------------------- mail

class TestMailer(unittest.TestCase):

    def setUp(self):
        self.box = Sandbox()
        self.anchor = date(2026, 10, 5)
        self.now = datetime(2026, 10, 6, 9, tzinfo=UTC)
        self.history = History(self.box.db)
        from skald.config import load_config
        self.config = load_config(self.box.config)

    def tearDown(self):
        self.history.close()
        self.box.close()

    def fill(self, days: int, people_now: int = 3, people_before: int = 2):
        for i in range(days):
            day = self.anchor - timedelta(days=i)
            self.history.record("example.com", day, totals_for(
                day_lines(day, people_now if i < 7 else people_before)), "UTC", [])

    def build(self, kind="daily"):
        with mock.patch.dict(os.environ, SECRETS):
            return mailer.build(kind, self.config, self.history, UTC, self.now)

    def test_daily_mail_is_multipart_text_and_html(self):
        self.fill(1)
        msg = self.build()
        self.assertEqual(msg.get_content_type(), "multipart/alternative")
        parts = [p.get_content_type() for p in msg.iter_parts()]
        # The HTML travels with the Skald mark it shows (a cid: image).
        self.assertEqual(parts, ["text/plain", "multipart/related"])
        related = [p.get_content_type() for p in list(msg.iter_parts())[1].iter_parts()]
        self.assertEqual(related, ["text/html", "image/png"])
        self.assertEqual(msg["To"], "owner@example.com, second@example.com")
        self.assertEqual(msg["Subject"],
                         "[traffic] example.com: daily traffic, Mon 5 Oct 2026")
        text = msg.get_body(("plain",)).get_content()
        html = msg.get_body(("html",)).get_content()
        self.assertIn("3 visits that read at least one page", text)
        self.assertIn("1 arrived by following a citation", text)
        self.assertIn("Dashboard: https://stats.example.com/example.com/", text)
        self.assertIn('href="https://stats.example.com/example.com/"', html)

    def test_the_html_reaches_for_nothing_but_the_dashboard_link(self):
        self.fill(1)
        html = self.build().get_body(("html",)).get_content()
        urls = set(re.findall(r"https?://[^\s\"'<]+", html))
        self.assertEqual(urls, {"https://stats.example.com/example.com/"})
        self.assertEqual(re.findall(r'src="([^"]*)"', html), ["cid:skald-mark"])
        for forbidden in ("<link", "<script", "url("):
            self.assertNotIn(forbidden, html)

    def test_weekly_mail_compares_with_the_week_before(self):
        self.fill(14)
        msg = self.build("weekly")
        text = msg.get_body(("plain",)).get_content()
        self.assertIn("weekly traffic, 29 Sep to 5 Oct 2026", msg["Subject"])
        self.assertRegex(text, r"Real people: readers\s+21\s+14\s+▲ 50%")
        self.assertIn("▲ 50%", msg.get_body(("html",)).get_content())

    def test_weekly_without_a_full_previous_week_says_so(self):
        self.fill(7)
        text = self.build("weekly").get_body(("plain",)).get_content()
        self.assertIn("not comparable", text)
        self.assertIn("not fully recorded", text)

    def test_refused_when_the_day_failed_verify(self):
        self.history.record("example.com", self.anchor,
                            totals_for(day_lines(self.anchor, 3)), "UTC",
                            [Problem("groups do not sum", "test")])
        with self.assertRaisesRegex(mailer.Refused, "did not reconcile"):
            self.build()

    def test_refused_when_the_day_was_never_collected(self):
        with self.assertRaisesRegex(mailer.Refused, "not collected"):
            self.build()

    def test_refused_when_the_window_parsed_nothing(self):
        from skald.aggregate import Totals
        self.history.record("example.com", self.anchor, Totals(), "UTC", [])
        with self.assertRaisesRegex(mailer.Refused, "parsed zero lines"):
            self.build()

    def test_refused_when_the_stored_figures_no_longer_reconcile(self):
        self.fill(1)
        with self.history.db:
            self.history.db.execute("UPDATE days SET hits = hits + 5")
        with self.assertRaisesRegex(mailer.Refused, "do not reconcile"):
            self.build()

    def test_weekly_refused_when_a_day_is_missing(self):
        self.fill(14)
        with self.history.db:
            self.history.db.execute("DELETE FROM days WHERE day = '2026-10-02'")
        with self.assertRaisesRegex(mailer.Refused, "2026-10-02"):
            self.build("weekly")

    def test_a_named_credential_that_is_not_set_is_a_refusal(self):
        self.fill(1)
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(mailer.Refused, "TI_TEST_SMTP_PASSWORD|TI_TEST_SMTP_USER"):
                mailer.build("daily", self.config, self.history, UTC, self.now)

    def test_credentials_are_never_sent_without_tls(self):
        self.config["mail"]["security"] = "none"
        with mock.patch.dict(os.environ, SECRETS):
            with self.assertRaisesRegex(mailer.Refused, "without TLS"):
                mailer.settings(self.config)

    def test_send_uses_starttls_and_the_environment_login(self):
        self.fill(1)
        with mock.patch.dict(os.environ, SECRETS), \
                mock.patch.object(mailer.smtplib, "SMTP") as smtp:
            code, out, err = self.box.run("--today", "2026-10-06", "mail", "--daily")
        self.assertEqual(code, 0, err)
        server = smtp.return_value
        smtp.assert_called_once_with("smtp.example.com", 587, timeout=30)
        server.starttls.assert_called_once()
        server.login.assert_called_once_with("relay-user", "relay-pass")
        server.send_message.assert_called_once()
        self.assertIn("sent daily mail", out)

    def test_port_465_uses_implicit_tls(self):
        self.config["mail"]["port"] = "465"
        with mock.patch.dict(os.environ, SECRETS):
            cfg = mailer.settings(self.config)
        self.assertEqual(cfg["security"], "ssl")
        with mock.patch.object(mailer.smtplib, "SMTP_SSL") as smtp_ssl:
            mailer.send(mock.Mock(), cfg)
        smtp_ssl.return_value.send_message.assert_called_once()

    def test_dry_run_prints_and_sends_nothing(self):
        self.fill(1)
        with mock.patch.dict(os.environ, SECRETS), \
                mock.patch.object(mailer.smtplib, "SMTP") as smtp, \
                mock.patch.object(mailer.smtplib, "SMTP_SSL") as smtp_ssl:
            code, out, err = self.box.run("--today", "2026-10-06", "mail",
                                          "--daily", "--dry-run")
        self.assertEqual(code, 0, err)
        smtp.assert_not_called()
        smtp_ssl.assert_not_called()
        self.assertIn("Subject: [traffic] example.com: daily traffic", out)
        self.assertIn("3 visits that read at least one page", out)

    def test_a_refused_mail_exits_non_zero_and_sends_nothing(self):
        with mock.patch.dict(os.environ, SECRETS), \
                mock.patch.object(mailer.smtplib, "SMTP") as smtp:
            code, out, err = self.box.run("--today", "2026-10-06", "mail", "--daily")
        self.assertEqual(code, 1)
        self.assertIn("REFUSED", err)
        smtp.assert_not_called()


# -------------------------------------------------------------- the commands

class TestCommands(unittest.TestCase):

    def setUp(self):
        self.box = Sandbox()

    def tearDown(self):
        self.box.close()

    def stored_days(self):
        with History(self.box.db) as h:
            return [r[0] for r in h.db.execute("SELECT day FROM days ORDER BY day")]

    def test_collect_stores_yesterday(self):
        self.box.log(day_lines(date(2026, 10, 5), 3))
        code, out, err = self.box.run("--today", "2026-10-06", "collect")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.stored_days(), ["2026-10-05"])
        self.assertIn("stored 2026-10-05: 7 requests", out)

    def test_collect_of_an_empty_day_stores_nothing(self):
        self.box.log(day_lines(date(2026, 10, 5), 3))
        code, out, err = self.box.run("--today", "2026-10-06", "collect",
                                      "--day", "2026-10-01")
        self.assertEqual(code, 1)
        self.assertEqual(self.stored_days(), [])

    def test_backfill_fills_from_rotations_and_skips_what_it_has(self):
        lines = []
        for i in range(3):
            lines += day_lines(date(2026, 10, 5) - timedelta(days=i), 2)
        self.box.log(lines)
        code, out, err = self.box.run("--today", "2026-10-06", "backfill", "--days", "3")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.stored_days(), ["2026-10-03", "2026-10-04", "2026-10-05"])
        code, out, _ = self.box.run("--today", "2026-10-06", "backfill", "--days", "3")
        self.assertIn("skipped 3", out)
        code, out, _ = self.box.run("--today", "2026-10-06", "backfill", "--days", "3",
                                    "--force")
        self.assertIn("ok 3", out)

    def test_dashboard_command_writes_to_the_configured_directory(self):
        self.box.log(day_lines(date(2026, 10, 5), 2))
        self.box.run("--today", "2026-10-06", "collect")
        code, out, err = self.box.run("--today", "2026-10-06", "dashboard")
        self.assertEqual(code, 0, err)
        self.assertTrue((self.box.root / "www" / "example.com" / "index.html").exists())

    def test_ti_py_runs_as_a_script_without_pyyaml(self):
        self.box.log(day_lines(date(2026, 10, 5), 2))
        with tempfile.TemporaryDirectory() as hide:
            (Path(hide) / "yaml.py").write_text('raise ImportError("hidden")\n')
            env = dict(os.environ, PYTHONPATH=hide)
            done = subprocess.run(
                [sys.executable, str(ROOT / "bin/skald"), "--config", str(self.box.config),
                 "--today", "2026-10-06", "check"],
                capture_output=True, text=True, env=env, timeout=120)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("ok: 2026-10-05: 6 requests", done.stdout)


class TestRunDaily(unittest.TestCase):
    """check -> collect -> dashboard -> daily mail (-> weekly on Monday),
    each step only if the one before it succeeded."""

    def setUp(self):
        self.box = Sandbox()

    def tearDown(self):
        self.box.close()

    def test_run_steps_stops_at_the_first_failure(self):
        ran = []

        def step(name, code):
            return name, lambda: ran.append(name) or code

        result = cli.run_steps([step("a", 0), step("b", 1), step("c", 0)],
                               err=lambda *a: None)
        self.assertEqual(result, 1)
        self.assertEqual(ran, ["a", "b"])

    def test_run_daily_notes_the_step_and_why_it_stopped(self):
        from unittest import mock
        from skald import runs
        parsed = cli.parser().parse_args(
            ["--config", str(self.box.config), "--today", "2026-10-12", "run-daily"])
        ctx = cli.Context(parsed)
        why = ("weekly mail: partial day(s) 2026-10-06 (partial day, data from 14:05); "
               "a week needs seven whole days")

        def refused():
            ctx.by_design = why
            return 1
        steps = [("collect", lambda: 0), ("weekly mail", refused), ("after", lambda: 0)]
        with mock.patch.object(cli, "daily_steps", lambda c: steps):
            self.assertEqual(cli.cmd_run_daily(ctx), 1)
        got = runs.load(ctx.live_dir)["run-daily"]
        self.assertEqual((got["last_outcome"], got["last_step"], got["last_reason"]),
                         ("withheld", "weekly mail", why))
        with mock.patch.object(cli, "daily_steps", lambda c: steps[:1]):
            self.assertEqual(cli.cmd_run_daily(ctx), 0)
        got = runs.load(ctx.live_dir)["run-daily"]
        self.assertEqual((got["last_outcome"], got["last_step"], got["last_reason"]),
                         ("ok", None, None))

    def test_the_steps_run_in_order_and_weekly_only_on_monday(self):
        def names(today):
            parsed = cli.parser().parse_args(
                ["--config", str(self.box.config), "--today", today, "run-daily"])
            return [n for n, _ in cli.daily_steps(cli.Context(parsed))]
        self.assertEqual(names("2026-10-06"),
                         ["check", "collect", "audit", "updates", "dashboard", "daily mail"])
        self.assertEqual(names("2026-10-05"),
                         ["check", "collect", "audit", "updates", "dashboard", "daily mail",
                          "weekly mail"])

    def test_a_failed_check_stores_draws_and_sends_nothing(self):
        self.box.log(open(FIXTURES / "unparsable.log").readlines())
        with mock.patch.dict(os.environ, SECRETS), \
                mock.patch.object(mailer.smtplib, "SMTP") as smtp:
            code, out, err = self.box.run("--today", "2026-10-06", "run-daily")
        self.assertEqual(code, 1)
        self.assertIn("stopped at 'check'", err)
        self.assertFalse((self.box.root / "www").exists())
        smtp.assert_not_called()
        with History(self.box.db) as h:
            self.assertEqual(h.sites(), [])

    def test_a_good_day_is_stored_drawn_and_mailed_once(self):
        self.box.log(day_lines(date(2026, 10, 5), 3))
        with mock.patch.dict(os.environ, SECRETS), \
                mock.patch.object(mailer.smtplib, "SMTP") as smtp:
            code, out, err = self.box.run("--today", "2026-10-06", "run-daily")
        self.assertEqual(code, 0, err)
        self.assertTrue((self.box.root / "www" / "example.com" / "index.html").exists())
        self.assertEqual(smtp.return_value.send_message.call_count, 1)

    def test_on_monday_the_weekly_mail_is_gated_on_a_complete_week(self):
        """Daily goes out; the weekly is refused because only one day of
        the week is in history, and the run exits non-zero to say so."""
        self.box.log(day_lines(date(2026, 10, 4), 3))
        with mock.patch.dict(os.environ, SECRETS), \
                mock.patch.object(mailer.smtplib, "SMTP") as smtp:
            code, out, err = self.box.run("--today", "2026-10-05", "run-daily")
        self.assertEqual(code, 1)
        self.assertIn("stopped at 'weekly mail'", err)
        self.assertEqual(smtp.return_value.send_message.call_count, 1)

    def test_dry_run_runs_every_step_but_sends_nothing(self):
        self.box.log(day_lines(date(2026, 10, 5), 3))
        with mock.patch.dict(os.environ, SECRETS), \
                mock.patch.object(mailer.smtplib, "SMTP") as smtp:
            code, out, err = self.box.run("--today", "2026-10-06", "run-daily",
                                          "--dry-run")
        self.assertEqual(code, 0, err)
        smtp.assert_not_called()
        self.assertIn("Subject:", out)


class TestConfig(unittest.TestCase):

    def test_the_fallback_parser_reads_the_new_sections(self):
        from skald.config import tiny_yaml
        parsed = tiny_yaml((ROOT / "config.example.yml").read_text())
        self.assertEqual(parsed["report"]["timezone"], "America/New_York")
        self.assertEqual(parsed["history"]["db"], "/var/lib/skald/history.sqlite")
        self.assertEqual(parsed["dashboard"]["url"], "https://stats.example.com/example.com/")
        mail = parsed["mail"]
        self.assertEqual(mail["to"], ["owner@example.com"])
        self.assertEqual(int(mail["port"]), 587)
        self.assertEqual(mail["subject_prefix"], "[traffic]")
        self.assertEqual(mail["password_env"], "SMTP_PASSWORD")
        self.assertEqual(parsed["report"]["country_credit"], "IP geolocation by DB-IP")
        self.assertEqual(parsed["report"]["country_credit_url"], "https://db-ip.com")

    def test_it_agrees_with_pyyaml_when_pyyaml_is_there(self):
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML not installed")
        from skald.config import tiny_yaml
        text = (ROOT / "config.example.yml").read_text()
        ours, theirs = tiny_yaml(text), yaml.safe_load(text)
        for section, values in theirs.items():
            for key, value in values.items():
                self.assertEqual(str(ours[section][key]), str(value), (section, key))

    def test_the_package_names_no_product_or_domain(self):
        """Domain agnostic by construction: example.com in docs and tests
        only, never in the package."""
        for path in (ROOT / "skald").glob("*.py"):
            text = path.read_text()
            with self.subTest(path=path.name):
                self.assertNotIn("example.com", text)


if __name__ == "__main__":
    unittest.main()
