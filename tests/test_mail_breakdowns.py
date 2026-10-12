"""The breakdowns in the report and the mail: who the readers were, and site
health.

What is pinned: both parts of the mail carry the same breakdowns, read back
from history; the HTML still reaches for nothing but the dashboard and the
country credit; and a period that includes a day collected before the
breakdowns existed says so instead of showing a partial sum.
"""
from __future__ import annotations

import os
import re
import sys
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald import mailer  # noqa: E402
from skald.classify import Group  # noqa: E402
from skald.config import load_config  # noqa: E402
from skald.report import as_html, as_text  # noqa: E402
from skald.report_breakdowns import NOT_RECORDED, zone_words  # noqa: E402
from skald.store import History  # noqa: E402

from support import (SECRETS, UTC, Sandbox, day_lines, line,  # noqa: E402
                     totals_for)

IPHONE_LINKEDIN = ("Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) "
                   "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 "
                   "[LinkedInApp]")
CREDIT = ("IP geolocation by DB-IP", "https://db-ip.com")


def lines_for(day: date) -> list[str]:
    """day_lines' six readers (3 US, 3 GB, one cited), plus a 404 seen by a
    person from Google, and a Canadian reader on an iPhone from LinkedIn."""
    one = datetime(day.year, day.month, day.day, 13, tzinfo=UTC)
    return day_lines(day, 6) + [
        line(one, "203.0.113.77", "/nope", status=404,
             referrer="https://www.google.com/"),
        line(one + timedelta(minutes=1), "203.0.113.78",
             "/?utm_source=LinkedIn&utm_medium=social&utm_campaign=Launch",
             IPHONE_LINKEDIN, country="CA"),
    ]


class TestReportCards(unittest.TestCase):

    def setUp(self):
        self.totals = totals_for(lines_for(date(2026, 10, 5)))

    def test_text_breaks_the_readers_down(self):
        text = as_text(self.totals, list(Group), CREDIT, "America/New_York")
        self.assertIn("WHO THE READERS WERE", text)
        self.assertIn("\U0001F1FA\U0001F1F8 United States 3 (43%)", text)
        self.assertIn("\U0001F1E8\U0001F1E6 Canada 1 (14%)", text)
        self.assertIn("Chrome 6 (86%), LinkedIn app 1 (14%)", text)
        self.assertIn("Desktop 6 (86%), Mobile 1 (14%), Tablet 0 (0%)", text)
        self.assertIn("Social media 1 (14%)", text)
        self.assertIn("linkedin / social / launch 1", text)
        self.assertIn("12:00-13:00 6", text)
        self.assertIn("(New York time)", text)
        self.assertIn("SITE HEALTH", text)
        self.assertIn("1 page-not-found (404) responses to people: /nope 1", text)
        self.assertIn("0 5xx responses", text)

    def test_html_carries_the_same_figures(self):
        html = as_html(self.totals, list(Group), "t", credit=CREDIT,
                       tz_name="America/New_York")
        self.assertIn("Who the readers were", html)
        self.assertIn("\U0001F1FA\U0001F1F8 United States 3 (43%)", html)
        self.assertIn("Desktop 6 (86%), Mobile 1 (14%), Tablet 0 (0%)", html)
        self.assertIn("Site health", html)
        self.assertIn("/nope 1", html)

    def test_cards_follow_the_people_card(self):
        text = as_text(self.totals, list(Group))
        self.assertLess(text.index("REAL PEOPLE"), text.index("WHO THE READERS WERE"))
        self.assertLess(text.index("SITE HEALTH"), text.index("ANSWER ENGINES"))

    def test_without_the_people_card_they_still_come_last(self):
        text = as_text(self.totals, [Group.BOTS])
        self.assertIn("WHO THE READERS WERE", text)
        self.assertGreater(text.index("SITE HEALTH"), text.index("BOTS AND SCANNERS"))

    def test_hand_built_totals_say_not_recorded(self):
        self.totals.breakdowns = False
        text = as_text(self.totals, list(Group))
        self.assertNotIn("WHO THE READERS WERE", text)
        self.assertIn("Breakdowns not recorded", text)

    def test_zone_words(self):
        self.assertEqual(zone_words("America/New_York"), "New York time")
        self.assertEqual(zone_words("UTC"), "UTC")
        self.assertEqual(zone_words(None), "local time")

    def test_no_response_time_in_the_log_is_said(self):
        people = self.totals.groups[Group.PEOPLE]
        people.speeds.clear()
        people.speeds["not logged"] = people.views
        self.assertIn("response time is not in the log",
                      as_text(self.totals, list(Group)))


class TestMailBreakdowns(unittest.TestCase):

    def setUp(self):
        self.box = Sandbox()
        self.anchor = date(2026, 10, 5)
        self.now = datetime(2026, 10, 6, 9, tzinfo=UTC)
        self.history = History(self.box.db)
        self.config = load_config(self.box.config)

    def tearDown(self):
        self.history.close()
        self.box.close()

    def fill(self, days: int):
        for i in range(days):
            day = self.anchor - timedelta(days=i)
            self.history.record("example.com", day, totals_for(lines_for(day)),
                                "UTC", [])

    def build(self, kind="daily"):
        with mock.patch.dict(os.environ, SECRETS):
            msg = mailer.build(kind, self.config, self.history, UTC, self.now)
        return (msg.get_body(("plain",)).get_content(),
                msg.get_body(("html",)).get_content())

    def test_daily_mail_carries_the_breakdowns_in_both_parts(self):
        self.fill(1)
        text, html = self.build()
        self.assertIn("\U0001F1FA\U0001F1F8 United States 3 (43%)", text)
        self.assertIn("Chrome 6 (86%)", text)
        self.assertIn("Desktop 6 (86%), Mobile 1 (14%), Tablet 0 (0%)", text)
        self.assertIn("Direct or unknown 5 (71%)", text)
        self.assertIn("page-not-found (404) responses to people", text)
        self.assertIn("(UTC)", text)
        # The branded HTML (mail_html.py) groups the same figures in tables.
        flat = re.sub(r"<[^>]+>", "|", html)
        self.assertRegex(flat, r"\U0001F1FA\U0001F1F8 United States\|+3\|+43%")
        self.assertRegex(flat, r"Direct or unknown\|+5\|+71%")
        self.assertIn("Broken links people hit (404)", html)

    def test_the_numbers_are_the_ones_in_history(self):
        self.fill(1)
        period = self.history.period("example.com", self.anchor, self.anchor)
        people = period.totals.groups[Group.PEOPLE]
        self.assertTrue(period.totals.breakdowns)
        self.assertEqual(sum(people.by["browser"].values()), people.readers)
        text, _ = self.build()
        self.assertIn(f"Chrome {people.by['browser']['Chrome']}", text)
        self.assertIn(f"{people.statuses['404']} page-not-found", text)

    def test_the_html_reaches_for_nothing_but_the_dashboard_and_the_credit(self):
        self.fill(1)
        self.config.setdefault("report", {}).update(
            country_credit=CREDIT[0], country_credit_url=CREDIT[1])
        _, html = self.build()
        urls = set(re.findall(r"https?://[^\s\"'<)]+", html))
        self.assertEqual(urls, {"https://stats.example.com/example.com/",
                                "https://db-ip.com"})
        # The one image is the Skald mark inside the mail (cid:), never fetched.
        self.assertEqual(re.findall(r'src="([^"]*)"', html), ["cid:skald-mark"])
        for forbidden in ("<link", "<script", "url("):
            self.assertNotIn(forbidden, html)

    def test_a_day_from_before_the_breakdowns_says_so(self):
        self.fill(7)
        self.history.db.execute(
            "UPDATE days SET breakdowns = NULL WHERE day = ?",
            ((self.anchor - timedelta(days=3)).isoformat(),))
        self.history.db.commit()
        self.now = datetime(2026, 10, 6, 9, tzinfo=UTC)
        text, html = self.build("weekly")
        self.assertIn("Breakdowns not recorded", text)
        self.assertNotIn("WHO THE READERS WERE", text)
        self.assertIn(NOT_RECORDED[:40], html)
        # The 404 and 5xx KPIs are not recorded for this week, and the week
        # before is not recorded at all.
        self.assertRegex(text, r"Page not found, seen by people\s+-\s+-")
        self.assertRegex(text, r"Server errors \(5xx\)\s+-\s+-")

    def test_weekly_compares_the_new_kpis_when_both_weeks_have_them(self):
        self.fill(14)
        text, _ = self.build("weekly")
        self.assertRegex(text, r"Page not found, seen by people\s+7\s+7\s+about the same")
        self.assertRegex(text, r"Server errors \(5xx\)\s+0\s+0\s+no change")


if __name__ == "__main__":
    unittest.main()
