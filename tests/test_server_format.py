"""The reference server's log format and the country-source credit."""
from __future__ import annotations

import os
import re
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald import Classifier, Group, check, dashboard, read, summarise  # noqa: E402
from skald.store import History  # noqa: E402

from support import (CHROME, SECRETS, UTC, Sandbox, day_lines, line,  # noqa: E402
                     totals_for)


class TestServerLogFormat(unittest.TestCase):
    """The reference server's format: nginx_extended with a GeoIP2 country
    and a literal "ray=-", in a file that starts in the stock combined
    format because the log_format changed part-way through the day."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, lines):
        path = self.dir / "access.log"
        path.write_text("".join(lines))
        return path

    def combined(self, when, address, path="/", agent=CHROME):
        return (f'{address} - - [{when:%d/%b/%Y:%H:%M:%S %z}] "GET {path} HTTP/1.1" '
                f'200 512 "-" "{agent}"\n')

    def test_a_file_that_changes_format_part_way_parses_every_line(self):
        """Detection samples the start, so it picks the old format; every
        new-format line used to be dropped without a word."""
        start = datetime(2026, 10, 6, 22, 0, tzinfo=UTC)
        old = [self.combined(start + timedelta(minutes=i), f"203.0.113.{i}")
               for i in range(30)]
        new = [line(start + timedelta(hours=3, minutes=i), f"198.51.100.{i}")
               for i in range(20)]
        hits = list(read([self.write(old + new)]))
        self.assertEqual(len(hits), 50)
        self.assertEqual(sum(1 for h in hits if h.host == "example.com"), 20)

    def test_lines_without_a_host_are_counted_and_said_to_be_unfiltered(self):
        start = datetime(2026, 10, 6, 22, 0, tzinfo=UTC)
        lines = ([self.combined(start, "203.0.113.1"),
                  self.combined(start, "203.0.113.2", agent="curl/8.7.1")]
                 + [line(start, "198.51.100.1"),
                    line(start, "198.51.100.2", host="api.example.com")])
        totals = summarise(read([self.write(lines)]), Classifier(), 30,
                           hosts=["example.com"])
        self.assertEqual((totals.parsed, totals.hits, totals.other_hosts,
                          totals.unfiltered), (4, 3, 1, 2))
        self.assertEqual(check(totals), [])
        from skald import as_html, as_text
        cards = [Group.PEOPLE, Group.BOTS]
        self.assertIn("2 of these had no host", as_text(totals, cards))
        self.assertIn("2 of these had no host", as_html(totals, cards, "t"))
        with tempfile.TemporaryDirectory() as tmp, History(Path(tmp) / "h") as h:
            h.record("example.com", date(2026, 10, 6), totals, "UTC", [])
            again = h.period("example.com", date(2026, 10, 6), date(2026, 10, 6))
            self.assertEqual(again.totals.unfiltered, 2)
            page = dashboard.render(h, "example.com", UTC,
                                    datetime(2026, 10, 7, 12, tzinfo=UTC))
        self.assertIn("2 requests over the", page)

    def test_a_geoip_country_with_a_literal_ray_dash(self):
        from skald.parse import PARSERS
        base = (f'2026-10-07T01:00:00+00:00 203.0.113.9 example.com "GET / HTTP/2.0" '
                f'200 512 "-" "{CHROME}" 0.004 ')
        for tail, want in (("cc=CA ray=-", "CA"), ("cc=- ray=-", ""),
                           ("cc= ray=-", ""), ("cc=ZZ ray=-", "")):
            with self.subTest(tail=tail):
                got = PARSERS["nginx_extended"](base + tail)
                self.assertIsNotNone(got)
                self.assertEqual(got.country, want)


class TestCountryCredit(unittest.TestCase):
    """A GeoIP licence's attribution, wherever countries are shown, as a
    text link and nothing fetched."""

    CREDIT = ("IP geolocation by DB-IP", "https://db-ip.com")

    def test_it_is_read_from_config_and_only_links_http(self):
        from skald.config import country_credit
        self.assertIsNone(country_credit({}))
        self.assertEqual(country_credit({"report": {
            "country_credit": "IP geolocation by DB-IP",
            "country_credit_url": "https://db-ip.com"}}), self.CREDIT)
        self.assertEqual(country_credit({"report": {
            "country_credit": "x", "country_credit_url": "javascript:alert(1)"}}),
            ("x", None))

    def test_dashboard_shows_it_under_the_countries_and_fetches_nothing(self):
        with tempfile.TemporaryDirectory() as tmp, History(Path(tmp) / "h") as h:
            day = date(2026, 10, 5)
            h.record("example.com", day, totals_for(day_lines(day, 3)), "UTC", [])
            page = dashboard.render(h, "example.com", UTC,
                                    datetime(2026, 10, 6, 12, tzinfo=UTC), self.CREDIT)
        self.assertIn('<a href="https://db-ip.com">IP geolocation by DB-IP</a>', page)
        countries = page.index("<h3>Countries (")
        self.assertGreater(page.index("IP geolocation by DB-IP"), countries)
        self.assertEqual(set(re.findall(r"https?://[^\s\"'<]+", page)),
                         {"https://db-ip.com"})
        for forbidden in ("<img", "src=", "<link", "<script", "url("):
            self.assertNotIn(forbidden, page)

    def test_mail_shows_it_in_both_parts(self):
        box = Sandbox()
        try:
            text = box.config.read_text().replace(
                "  timezone: UTC\n", "  timezone: UTC\n  country_credit: "
                "IP geolocation by DB-IP\n  country_credit_url: https://db-ip.com\n")
            box.config.write_text(text)
            day = date(2026, 10, 5)
            with History(box.db) as h:
                h.record("example.com", day, totals_for(day_lines(day, 3)), "UTC", [])
            with mock.patch.dict(os.environ, SECRETS):
                code, out, err = box.run("--today", "2026-10-06", "mail", "--daily",
                                         "--dry-run", "--save-html",
                                         str(box.root / "m.html"))
            html = (box.root / "m.html").read_text()
        finally:
            box.close()
        self.assertEqual(code, 0, err)
        self.assertIn("IP geolocation by DB-IP (https://db-ip.com)", out)
        self.assertIn('href="https://db-ip.com"', html)
        self.assertIn(">IP geolocation by DB-IP</a>", html)




if __name__ == "__main__":
    unittest.main()
