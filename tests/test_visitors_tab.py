"""Traffic > Visitors: new and returning visits, and how engaged visits were.

Found in review: the tab's "New and returning" said "-" on Today. The live
snapshot counts returning readers (visitors.annotate), but the app's Today
(dashboard_webapp.from_snapshot) dropped them. Pinned here: Today carries them in
a stored day's shape, none when no visitor key is set (never 0), and the page's
own arithmetic (js/visitorfigs.js, run in node) adds up or withholds.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from skald.dashboard_webapp import from_snapshot  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


class TestTodayCarriesReturning(unittest.TestCase):

    def test_the_live_snapshots_returning_readers_reach_today(self):
        snap = {"people": {"readers": 62, "visits": 62, "views": 90},
                "returning": {"readers": 62, "returning": 9, "first_touch": {"Search engine": 6},
                              "by_source": {"Search engine": {"readers": 20, "returning": 3}}, "warming_up": False}}
        self.assertEqual(from_snapshot(snap)["returning"], {"readers": 62, "returning": 9})

    def test_no_visitor_key_means_not_recorded_never_zero(self):
        self.assertNotIn("returning", from_snapshot({"people": {"readers": 5}, "returning": None}))
        self.assertNotIn("returning", from_snapshot({"people": {"readers": 5}}))


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class TestThePagesArithmetic(unittest.TestCase):

    def test_adds_up_or_withholds(self):
        done = subprocess.run(["node", str(ROOT / "tests" / "js" / "visitorfigs.mjs")],
                              capture_output=True, text=True, timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("visitorfigs: all passed", done.stdout)


if __name__ == "__main__":
    unittest.main()
