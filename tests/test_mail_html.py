"""The branded daily and weekly mails (mail_html.py), and the owner's rule
that the daily and weekly reports are the only mail: alerts with
`alerts.mail: false` send nothing."""
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

from skald import alerts, mailer  # noqa: E402
from skald.config import load_config, tiny_yaml  # noqa: E402
from skald.store import History  # noqa: E402

from support import CHROME, SECRETS, UTC, Sandbox, day_lines, line, totals_for  # noqa: E402

ANCHOR = date(2026, 10, 5)
NOW = datetime(2026, 10, 6, 9, tzinfo=UTC)
BRAND = {"name": "Skald", "version": "1.0.0", "tagline": "Every visit, truly told.",
         "release": 70, "commit": "abc", "deployed_at": None}


class MailCase(unittest.TestCase):
    def setUp(self):
        self.box = Sandbox()
        self.history = History(self.box.db)
        self.patch = mock.patch("skald.brand.load", return_value=BRAND)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.history.close()
        self.box.close()

    def fill(self, days: int, people=3, partial_last=False):
        for i in range(days):
            day = ANCHOR - timedelta(days=i)
            totals = totals_for(day_lines(day, people if i < 7 else 2))
            if partial_last and i == 0:
                totals.partial_from = datetime(day.year, day.month, day.day, 14, tzinfo=UTC)
            self.history.record("example.com", day, totals, "UTC", [])

    def build(self, kind="daily"):
        with mock.patch.dict(os.environ, SECRETS):
            msg = mailer.build(kind, load_config(self.box.config), self.history, UTC, NOW)
        return msg, msg.get_body(("html",)).get_content()


class TestDaily(MailCase):
    def test_brand_header_kpis_sections_and_footer(self):
        self.fill(8)
        msg, html = self.build()
        flat = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))
        self.assertIn("Skald Every visit, truly told.", flat)
        self.assertIn("example.com · Daily report · Mon 5 Oct 2026", flat)
        self.assertIn("Midnight to midnight", flat)
        for title in ("The headline", "Where visitors came from", "Top pages", "Countries",
                      "AI and crawlers", "Site health"):
            self.assertIn(title, flat)
        # 3 readers against 2 a week before (both whole); leads and returning
        # are not recorded here, so "—", never 0; no heartbeat, no uptime.
        self.assertRegex(flat, r"Visitors 3 ▲ 50%")
        self.assertRegex(flat, r"Visitors from AI 1 same")
        self.assertRegex(flat, r"Uptime \(our 5-minute check\) —")
        self.assertRegex(flat, r"Leads — —")
        self.assertIn("Open the dashboard", html)
        self.assertIn("Skald v1.0.0 · release 70 · Every visit, truly told.", flat)
        self.assertIn("You get this because owner@example.com, second@example.com are on the "
                      "report list", flat)
        # Email-safe: nothing fetched, no pure white, colour scheme declared.
        self.assertEqual(re.findall(r'src="([^"]*)"', html), ["cid:skald-mark"])
        self.assertNotIn("#ffffff", html.lower())
        self.assertIn('name="color-scheme" content="light dark"', html)
        self.assertIn("max-width:640px", html)
        logo = [p for p in msg.walk() if p.get_content_type() == "image/png"]
        self.assertEqual(logo[0]["Content-ID"], "<skald-mark>")

    def test_one_recipient_is_on_the_list_several_are(self):
        self.fill(14)
        for kind in ("daily", "weekly"):
            config = load_config(self.box.config)
            config["mail"]["to"] = ["owner@example.com"]
            with mock.patch.dict(os.environ, SECRETS):
                msg = mailer.build(kind, config, self.history, UTC, NOW)
            flat = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", msg.get_body(("html",)).get_content()))
            self.assertIn("because owner@example.com is on the report list", flat)
            _, html = self.build(kind)
            flat = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))
            self.assertIn("owner@example.com, second@example.com are on the report list", flat)
            self.assertNotIn("second@example.com is on", flat)

    def test_every_attribute_parses(self):
        """A double quote inside a style ended the attribute early: fonts and
        colours fell apart in every client."""
        from html.parser import HTMLParser
        self.fill(1)
        _, html = self.build()
        names = set()

        class Attrs(HTMLParser):
            def handle_starttag(self, tag, attrs):
                names.update(k for k, _ in attrs)
        Attrs().feed(html)
        self.assertLessEqual(names, {"lang", "charset", "name", "content", "class", "style",
                                     "role", "width", "cellpadding", "cellspacing", "bgcolor",
                                     "align", "valign", "height", "src", "alt", "href"})

    def test_no_change_without_a_whole_week_before(self):
        self.fill(1)
        _, html = self.build()
        flat = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))
        self.assertRegex(flat, r"Visitors 3 —")

    def test_a_partial_day_says_so_and_compares_nothing(self):
        self.fill(8, partial_last=True)
        _, html = self.build()
        flat = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))
        self.assertIn("Partial day: data from 14:00.", flat)
        self.assertRegex(flat, r"Visitors 3 —")

    def test_tables_have_at_most_five_rows(self):
        self.fill(1, people=12)
        _, html = self.build()
        for title in ("Top pages", "Countries", "Where visitors came from"):
            card = html.split(title, 1)[1].split("s-card", 1)[0]
            self.assertLessEqual(card.count('<tr><td class="s-ink s-rule"'), 5, title)


class TestWeekly(MailCase):
    def test_seven_bars_and_the_week_before(self):
        self.fill(14)
        _, html = self.build("weekly")
        flat = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))
        self.assertIn("Weekly report · Tue 29 Sep – Mon 5 Oct 2026", flat)
        self.assertIn("Visitors per day", flat)
        self.assertEqual(html.count('class="s-bar"'), 7)
        self.assertRegex(flat, r"Visitors 21 ▲ 50%")


class TestOnlyTheReportsAreMailed(unittest.TestCase):
    def test_the_example_config_keeps_alert_mail_off(self):
        example = Path(__file__).resolve().parent.parent / "config.example.yml"
        self.assertIs(tiny_yaml(example.read_text())["alerts"]["mail"], False)

    def test_alerts_with_mail_off_send_nothing_from_a_live_run(self):
        box = Sandbox()
        try:
            t = datetime(2026, 10, 6, 11, 55, tzinfo=UTC)
            box.log([line(t + timedelta(seconds=i), f"203.0.113.{i}", "/x", CHROME, status=502)
                     for i in range(12)])
            box.config.write_text(box.config.read_text()
                                  + "alerts:\n  enabled: true\n  mail: false\n  digest_hour: 0\n")
            with mock.patch.dict(os.environ, SECRETS), \
                    mock.patch("skald.mailer.smtplib.SMTP") as smtp, \
                    mock.patch("skald.mailer.smtplib.SMTP_SSL") as ssl_smtp, \
                    mock.patch("skald.cli._now", return_value=t + timedelta(minutes=1)):
                for _ in range(2):
                    self.assertEqual(box.run("live")[0], 0)
                with mock.patch("skald.cli._now",
                                return_value=t + timedelta(minutes=40)):
                    self.assertEqual(box.run("live")[0], 0)     # cleared: no resolved mail
            smtp.assert_not_called()
            ssl_smtp.assert_not_called()
            state = alerts.load_state(box.root)
            self.assertFalse(state["mail"])
            self.assertTrue(state["alerts"])                    # shown on the page
        finally:
            box.close()


if __name__ == "__main__":
    unittest.main()
