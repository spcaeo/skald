"""Today so far: the live snapshot and its dashboard panel.

The rules under test are about what live may NOT do: count yesterday, write
the daily history, show figures that do not reconcile, carry an address or a
user agent, or leak into run-daily's figures and mail.
"""
from __future__ import annotations

import gzip
import json
import os
import sys
import time
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald import dashboard, live, mailer  # noqa: E402
from skald.store import History  # noqa: E402
from skald.verify import Problem  # noqa: E402

from support import (ASKED, CHROME, GOOGLEBOT, GPTBOT, NY, SECRETS,  # noqa: E402
                     Sandbox, day_lines, line)

TODAY = date(2026, 10, 7)          # a Wednesday; --today runs at local noon
YESTERDAY = TODAY - timedelta(days=1)


def at(day: date, hour: int, minute: int = 0, second: int = 0) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, second, tzinfo=NY)


def morning() -> list[str]:
    """Today before noon in New York: 2 people (one cited, with an asset
    request on the same referrer), GPTBot, ChatGPT-User, Googlebot, a probe.
    And one line a second before local midnight, which is yesterday."""
    return [
        line(at(YESTERDAY, 23, 59, 59), "203.0.113.90", "/late", GPTBOT),
        line(at(TODAY, 0, 0, 1), "203.0.113.11", "/"),
        line(at(TODAY, 8, 0), "203.0.113.12", "/guides/alpha",
             referrer="https://www.perplexity.ai/"),
        line(at(TODAY, 8, 0, 1), "203.0.113.12", "/_next/static/app.js",
             referrer="https://www.perplexity.ai/"),
        line(at(TODAY, 9, 0), "198.51.100.40", "/guides/alpha", GPTBOT),
        line(at(TODAY, 9, 30), "198.51.100.41", "/guides/beta", ASKED),
        line(at(TODAY, 10, 0), "198.51.100.42", "/", GOOGLEBOT),
        line(at(TODAY, 10, 5), "198.51.100.52", "/.env", "curl/8.7.1", status=404),
        line(at(TODAY, 13, 0), "203.0.113.99", "/afternoon"),  # after "now"
    ]


class LiveCase(unittest.TestCase):

    def setUp(self):
        self.box = Sandbox(tz="America/New_York")

    def tearDown(self):
        self.box.close()

    def live(self, *extra):
        # A log file's modification time is when its last line was written,
        # and live opens only files written to since midnight. Make the
        # sandbox's files look written this morning, as a real log would.
        for path in (self.box.root / "logs").glob("access.log"):
            stamp = at(TODAY, 11, 59).timestamp()
            os.utime(path, (stamp, stamp))
        return self.box.run("--today", TODAY.isoformat(), "live", *extra)

    @property
    def snap_path(self) -> Path:
        return self.box.root / "live-example.com.json"

    def snap(self) -> dict:
        return json.loads(self.snap_path.read_text())

    @property
    def page(self) -> str:
        return (self.box.root / "www" / "example.com" / "index.html").read_text()


class TestLiveSnapshot(LiveCase):

    def test_it_counts_today_from_local_midnight_to_now_and_nothing_else(self):
        self.box.log(morning())
        code, out, err = self.live()
        self.assertEqual(code, 0, err)
        snap = self.snap()
        self.assertEqual(snap["state"], "ok")
        self.assertEqual(snap["day"], "2026-10-07")
        # 7 lines today before noon; the 23:59:59 line and the 13:00 one are out.
        self.assertEqual(snap["requests"], 7)
        self.assertEqual(snap["people"]["visits"], 2)
        self.assertEqual(snap["people"]["views"], 2)
        self.assertEqual(snap["people"]["cited_visits"], 1)
        self.assertEqual(snap["people"]["cited_by"], {"perplexity.ai": 1})
        self.assertEqual(snap["ai"], {"training": {"GPTBot": 1},
                                      "asked": {"ChatGPT-User": 1}})
        self.assertEqual(snap["search"], {"Googlebot": 1})
        self.assertEqual(snap["bots"], {"requests": 1, "probes": 1})
        self.assertNotIn("/late", json.dumps(snap))
        self.assertNotIn("/afternoon", json.dumps(snap))

    def test_latest_activity_is_newest_first_one_row_per_page_landing(self):
        self.box.log(morning())
        self.live()
        events = self.snap()["events"]
        self.assertEqual([(e["kind"], e["who"], e["path"]) for e in events], [
            ("asked", "ChatGPT-User", "/guides/beta"),
            ("training", "GPTBot", "/guides/alpha"),
            ("citation", "perplexity.ai", "/guides/alpha"),   # not the .js too
        ])
        self.assertEqual(events[0]["at"], "2026-10-07T09:30:00-04:00")

    def test_only_the_twenty_most_recent_events_are_kept(self):
        self.box.log([line(at(TODAY, 1, i), f"198.51.100.{i}", f"/p{i}", GPTBOT)
                      for i in range(45)])
        self.live()
        events = self.snap()["events"]
        self.assertEqual(len(events), live.EVENTS)
        self.assertEqual(events[0]["path"], "/p44")
        self.assertEqual(events[-1]["path"], "/p25")

    def test_no_address_or_user_agent_is_written_anywhere(self):
        self.box.log(morning())
        self.live()
        snap = self.snap()
        # crawler_cost keeps a named crawler's own strings, never a person's
        # (and never a scanner's: a probe's string may be a browser's).
        cost = json.dumps(snap["extras"].pop("crawler_cost"))
        self.assertIn("GPTBot", cost)
        for forbidden in ("203.0.113.", "198.51.100.", "Chrome/", "Macintosh", "curl/8"):
            with self.subTest(crawler_cost=forbidden):
                self.assertNotIn(forbidden, cost)
        for text in (json.dumps(snap), self.page):
            for forbidden in ("203.0.113.", "198.51.100.", "Mozilla/", "Chrome/",
                              "AppleWebKit", "curl/8"):
                with self.subTest(forbidden=forbidden):
                    self.assertNotIn(forbidden, text)

    def test_it_never_writes_the_daily_history(self):
        self.box.log(morning())
        self.live()
        self.live()
        with History(self.box.db) as h:
            self.assertEqual(h.db.execute("SELECT COUNT(*) FROM days").fetchone()[0], 0)
            self.assertEqual(h.db.execute("SELECT COUNT(*) FROM groups").fetchone()[0], 0)
            self.assertEqual(h.db.execute("SELECT COUNT(*) FROM counts").fetchone()[0], 0)
            self.assertEqual(h.sites(), [])

    def test_figures_that_do_not_reconcile_are_withheld(self):
        self.box.log(morning())
        with mock.patch.object(live, "check",
                               return_value=[Problem("groups do not sum", "test")]):
            code, out, err = self.live()
        self.assertEqual(code, 1)
        self.assertIn("WITHHELD", err)
        snap = self.snap()
        self.assertEqual(snap["state"], "withheld")
        for figure in ("requests", "people", "ai", "events", "groups"):
            self.assertNotIn(figure, snap)
        self.assertIn("Withheld.", self.page)
        self.assertIn("groups do not sum", self.page)

    def test_a_day_with_nothing_logged_yet_is_empty_not_withheld(self):
        self.box.log([line(at(YESTERDAY, 22, 0))])
        code, out, err = self.live()
        self.assertEqual(code, 0, err)
        self.assertEqual(self.snap()["state"], "empty")
        self.assertIn("No requests logged yet today.", self.page)

    def test_the_snapshot_is_replaced_atomically(self):
        self.box.log(morning())
        self.live()
        self.live()
        leftovers = [p.name for p in self.box.root.glob(".live-*")]
        self.assertEqual(leftovers, [])


class TestLivePanel(LiveCase):

    def test_the_dashboard_shows_the_panel_and_reloads_itself(self):
        self.box.log(morning())
        self.live()
        page = self.page
        self.assertIn('<meta http-equiv="refresh" content="120">', page)
        self.assertIn('<meta name="robots" content="noindex, nofollow, noarchive">', page)
        self.assertIn('<meta name="referrer" content="no-referrer">', page)
        self.assertIn("Today so far", page)
        self.assertIn("Live, partial", page)
        self.assertIn("not checked against a full day; not used in comparisons "
                      "or emails", page)
        self.assertIn("Updated 12:00 EDT", page)
        self.assertIn("Latest AI activity today", page)
        self.assertIn("perplexity.ai", page)
        self.assertLess(page.index("Today so far"), page.index("At a glance"))
        for forbidden in ("<script", "<link", "src=", "url(", "@import"):
            self.assertNotIn(forbidden, page)

    def test_a_page_without_live_data_does_not_reload(self):
        self.box.log(day_lines(YESTERDAY, 2, NY))
        self.box.run("--today", TODAY.isoformat(), "collect")
        self.box.run("--today", TODAY.isoformat(), "dashboard")
        self.assertNotIn("http-equiv", self.page)
        self.assertNotIn("Today so far", self.page)

    def test_yesterdays_snapshot_is_never_shown_as_today(self):
        self.box.log(morning())
        self.live()
        code, _, err = self.box.run("--today", "2026-10-08", "dashboard")
        self.assertEqual(code, 0, err)
        self.assertIn("No live figures for today yet", self.page)
        self.assertNotIn("Latest AI activity today", self.page)


class TestLiveStaysOutOfTheDailyRun(LiveCase):

    def test_run_daily_figures_and_mail_ignore_the_live_snapshot(self):
        """A snapshot with absurd figures, dated both yesterday and today,
        changes nothing that run-daily stores or sends."""
        self.box.log(day_lines(YESTERDAY, 3, NY))
        fake = {"version": live.LIVE_VERSION, "site": "example.com",
                "timezone": "America/New_York", "state": "ok",
                "from": "2026-10-07T00:00:00-04:00",
                "generated_at": "2026-10-07T11:00:00-04:00",
                "requests": 987654, "people": {"visits": 777777, "views": 1},
                "groups": {}, "ai": {}, "events": []}
        for day in (YESTERDAY, TODAY):
            live.save(live.path_for(self.box.root, "example.com") if day == TODAY
                      else self.box.root / "live-yesterday.json",
                      dict(fake, day=day.isoformat()))
        with mock.patch.dict(os.environ, SECRETS), \
                mock.patch.object(mailer.smtplib, "SMTP") as smtp:
            code, out, err = self.box.run("--today", TODAY.isoformat(), "run-daily")
        self.assertEqual(code, 0, err)
        with History(self.box.db) as h:
            period = h.period("example.com", YESTERDAY, YESTERDAY)
            days = [r[0] for r in h.db.execute("SELECT day FROM days")]
        self.assertEqual(days, ["2026-10-06"])
        self.assertEqual(period.totals.hits, 7)
        sent = smtp.return_value.send_message.call_args[0][0]
        body = sent.get_body(("plain",)).get_content()
        self.assertIn("3 visits that read at least one page", body)
        for absurd in ("777,777", "777777", "987,654", "987654"):
            self.assertNotIn(absurd, body)
            self.assertNotIn(absurd, sent.get_body(("html",)).get_content())


class TestLiveCost(LiveCase):
    """Run every two minutes, it must stay cheap on a busy log: only the
    files that can hold today are opened, and yesterday's lines are parsed
    but never classified."""

    def test_a_busy_log_is_read_quickly_and_only_where_today_can_be(self):
        logs = self.box.root / "logs"
        rotated = at(TODAY, 2, 25)                   # logrotate, 06:25 UTC
        # .1: a busy day, 60,000 lines from yesterday's rotation to 23:15,
        # plus the first minutes of today.
        busy = [line(at(YESTERDAY, 2, 25) + timedelta(seconds=i * 1.25),
                     f"203.0.113.{i % 250}", f"/p{i % 400}",
                     CHROME.replace("129.0", f"{100 + i % 300}.0"))
                for i in range(60_000)]
        early = [line(at(TODAY, 0, 10) + timedelta(seconds=i), "203.0.113.7", "/early")
                 for i in range(50)]
        self.box.log(busy + early, "access.log.1")
        # Today after the rotation: 3,000 requests.
        self.box.log([line(at(TODAY, 3, 0) + timedelta(seconds=i * 3),
                           f"198.51.100.{i % 200}", f"/q{i % 50}", GPTBOT)
                      for i in range(3_000)])
        # A decoy two rotations back, dated today: if it is read, counts change.
        decoy = logs / "access.log.2.gz"
        with gzip.open(decoy, "wt") as handle:
            handle.write("".join(line(at(TODAY, 5), "203.0.113.200", "/decoy")
                                 for _ in range(500)))
        stamps = {"access.log": at(TODAY, 11, 59), "access.log.1": rotated,
                  "access.log.2.gz": at(YESTERDAY, 2, 25)}
        for name, when in stamps.items():
            os.utime(logs / name, (when.timestamp(), when.timestamp()))

        started = time.perf_counter()
        code, out, err = self.box.run("--today", TODAY.isoformat(), "live")
        took = time.perf_counter() - started
        self.assertEqual(code, 0, err)
        snap = self.snap()
        self.assertEqual(snap["requests"], 3_050)
        self.assertNotIn("/decoy", json.dumps(snap))
        # Measured at about a second; the bound is loose so a slow machine
        # does not fail it, and tight enough to catch classifying all of
        # yesterday or reading every rotation.
        self.assertLess(took, 15, f"live took {took:.1f}s")


class TestLiveSites(unittest.TestCase):

    def test_a_site_with_only_a_snapshot_still_gets_a_page(self):
        box = Sandbox(tz="America/New_York")
        try:
            log = box.log(morning())
            stamp = at(TODAY, 11, 59).timestamp()
            os.utime(log, (stamp, stamp))
            box.run("--today", TODAY.isoformat(), "live")
            self.assertTrue((box.root / "www" / "example.com" / "index.html").exists())
            self.assertIn('href="example.com/"', (box.root / "www" / "index.html").read_text())
        finally:
            box.close()

    def test_a_corrupt_snapshot_is_ignored_not_trusted(self):
        box = Sandbox()
        try:
            path = live.path_for(box.root, "example.com")
            path.write_text("{not json")
            self.assertIsNone(live.load(path))
            path.write_text(json.dumps({"version": 999, "site": "example.com"}))
            self.assertIsNone(live.load(path))
        finally:
            box.close()

    def test_slug_is_shared_by_the_page_and_the_snapshot(self):
        self.assertEqual(live.path_for(Path("/x"), "a b/c").name,
                         f"live-{dashboard.slug('a b/c')}.json")


if __name__ == "__main__":
    unittest.main()
