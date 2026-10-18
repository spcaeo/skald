"""A visit's pages, said honestly everywhere it is shown.

Found on the live site: a visit showed "1 page, 11 s" beside the trail
/install/ > /story/ > /, where /story/ and / were seen in the browser (moves
found from the next request's referrer: a cached page, or a click the site
handled in the browser). Pinned here: the stored `pages` keeps its meaning
(page views, on both roads), and every view says "3 pages (2 seen in the
browser)" - the journey sentence (CSV, mail, data files), the server page's
table, the web app (js/visitpages.js, run in node) - from the journey's own
`in_app`, which the app's journeys now carry.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import unittest
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald.dashboard_visits import journeys_table  # noqa: E402
from skald.dashboard_webapp import journey as app_journey  # noqa: E402
from skald.visits import pages_words, sentence  # noqa: E402

from support import CHROME, UTC, line, totals_for  # noqa: E402

DAY = date(2026, 10, 14)


def at(hour, minute=0, second=0):
    return datetime(DAY.year, DAY.month, DAY.day, hour, minute, second, tzinfo=UTC)


class TestPagesWords(unittest.TestCase):

    def live_case(self):
        """The visit as the log had it: one page loaded, then two requests
        whose referrers name /story/ and /: moves seen in the browser."""
        lines = [line(at(9), "203.0.113.10", "/install/"),
                 line(at(9, 0, 4), "203.0.113.10", "/og/a.png", CHROME,
                      "https://example.com/story/"),
                 line(at(9, 0, 11), "203.0.113.10", "/og/b.png", CHROME,
                      "https://example.com/")]
        totals = totals_for(lines)
        (j,) = totals.journeys
        return totals, j

    def test_the_live_case(self):
        totals, j = self.live_case()
        self.assertEqual([[p, how] for p, how in j["trail"]],
                         [["/install/", "page"], ["/story/", "app"], ["/", "app"]])
        # The stored figure is unchanged: one page view, as both roads count it.
        self.assertEqual((j["pages"], j["seen"], j["in_app"]), (1, 3, 2))
        self.assertEqual(totals.visits.views(), 1)
        self.assertEqual(pages_words(j), "3 pages (2 seen in the browser)")
        self.assertIn("· 3 pages (2 seen in the browser) · 11s", sentence(j))
        self.assertIn("3 pages (2 seen in the browser)", journeys_table([j], 1, "v.csv"))

    def test_the_app_journey_carries_the_counts(self):
        _, j = self.live_case()
        got = app_journey(j)
        self.assertEqual((got["pages"], got["seen"], got["in_app"]), (1, 3, 2))
        self.assertEqual([s["page"] for s in got["trail"]], [True, False, False])

    def test_plain_visits_read_as_before(self):
        self.assertEqual(pages_words({"pages": 1, "in_app": 0}), "1 page")
        self.assertEqual(pages_words({"pages": 4}), "4 pages")
        # An older journey without in_app: from its trail.
        self.assertEqual(pages_words({"pages": 1, "trail": [["/a", "page"], ["/b", "app"]]}),
                         "2 pages (1 seen in the browser)")


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class TestWebApp(unittest.TestCase):

    def test_the_apps_words(self):
        js = Path(__file__).resolve().parent / "js" / "visitpages.mjs"
        done = subprocess.run(["node", str(js)], capture_output=True, text=True, timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("visitpages: all passed", done.stdout)


if __name__ == "__main__":
    unittest.main()
