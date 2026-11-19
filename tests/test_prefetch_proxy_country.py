"""SKALD-41 follow-up (2.54.1): a joined proxy page takes the phone's country
when the log carries no country and the country file fills it in.

Seen live on 19 Nov 2026, right after 2.54.0: on sites whose log lines carry
no country (`cc=-`), the classifier's first pass read the log without the
country file, so the join stored the phone's country as "" and the page line
kept the proxy's (filled later, in the counting pass). The reader showed in
the proxy's country, with no city, while the audit's road (which fills
countries before it joins) said the phone's: `audit --live` disagreed, and a
daily run would have withheld the day. The audit's "yesterday at this hour"
(audit_by_now) and per-view (audit_views) roads did not rejoin at all.

Pinned here, with lines that carry no country and a country file that knows
both addresses: the reader is the phone's country on the main road; the day
audit agrees; audit_by_now and audit_views count the joined page as the
phone's visit, as the main road does.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald import Group, audit_by_now, audit_views  # noqa: E402
from skald.window import analyse_window, day_window  # noqa: E402

from conversions_support import mmdb  # noqa: E402
from support import UTC, Sandbox, line  # noqa: E402
from test_prefetch_proxy import (ANDROID, DAY, GOOGLE, PHONE, PROXY, TODAY, at,  # noqa: E402
                                 ranges)

NETS = {"2001:db8:1::/48": "IN",          # the phone
        "2001:db8:7::/48": "US"}          # the proxy


def bare(when, address, path, referrer="-"):
    """A line that carries no country (cc=-): the country file fills it."""
    return line(when, address, path, ANDROID, referrer, country="-")


def visit():
    """The proxy's page, the phone's files for it, then a second page the
    phone opened itself (with its files), within the visit's gap."""
    page = "https://example.com/"
    return [bare(at(8, 13, 43), PROXY, "/", GOOGLE),
            bare(at(8, 13, 44), PHONE, "/_next/static/css/app.css", page),
            bare(at(8, 13, 44), PHONE, "/_next/static/chunks/main.js", page),
            bare(at(8, 15), PHONE, "/pricing/", page),
            bare(at(8, 15, 1), PHONE, "/_next/static/css/app.css", "https://example.com/pricing/")]


class Setup:

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.db = root / "country.mmdb"
        self.db.write_bytes(mmdb(NETS))
        self.log = root / "access.log"
        self.log.write_text("".join(visit()))
        self.config = {"site": {"hosts": ["example.com"]},
                       "logs": {"country_db": str(self.db)},
                       "bots": {"ranges_dir": str(ranges(root / "ranges"))}}

    def tearDown(self):
        self.tmp.cleanup()


class MainRoad(Setup, unittest.TestCase):

    def test_the_reader_is_the_phones_country_not_the_proxys(self):
        start, end = day_window(DAY, UTC)
        totals = analyse_window(self.config, start, end, paths=[self.log])
        people = totals.groups[Group.PEOPLE]
        self.assertEqual((people.visits, people.readers, people.views), (1, 1, 2))
        self.assertEqual(dict(people.countries), {"IN": 1})
        self.assertEqual(dict(people.by["country"]), {"IN": 1})


class AuditRoads(Setup, unittest.TestCase):

    def test_yesterday_at_this_hour_counts_the_joined_page_as_the_phones_visit(self):
        start, end = day_window(DAY, UTC)
        got = audit_by_now.recount(self.config, UTC, start, end, paths=[self.log])
        # As the main road: one visitor, two pages, at 08:00.
        self.assertEqual((got["visitors"], got["pages"]), (1, 2))
        self.assertEqual(got["hours"]["visitors"][8], 1)

    def test_a_view_counts_the_joined_page_as_the_phones_visit(self):
        figures = audit_views.recount(self.config, DAY, UTC,
                                      [{"name": "Everything", "path_prefix": "/"}],
                                      paths=[self.log])
        got = figures["everything"]
        self.assertEqual(got["groups"].get("people"), 5)
        self.assertEqual((got["visits"], got["readers"]), (1, 1))


class TheDayAudit(unittest.TestCase):

    def test_collect_and_the_audit_agree_on_the_country(self):
        box = Sandbox()
        try:
            folder = ranges(box.root / "ranges")
            db = box.root / "country.mmdb"
            db.write_bytes(mmdb(NETS))
            text = box.config.read_text().replace("  require_rendering: false\n", "")
            text = text.replace("  format: auto\n", f"  format: auto\n  country_db: {db}\n", 1)
            box.config.write_text(text + f"bots:\n  ranges_dir: {folder}\n")
            box.log(visit())
            code, _, err = box.run("--today", TODAY, "collect", "--day", DAY.isoformat())
            self.assertEqual(code, 0, err)
            code, out, err = box.run("--today", TODAY, "audit", "--day", DAY.isoformat())
            self.assertEqual(code, 0, err + out)
            self.assertIn("all match", out)
        finally:
            box.close()


if __name__ == "__main__":
    unittest.main()
