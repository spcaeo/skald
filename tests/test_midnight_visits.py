"""#66: a visit that went on past midnight, marked so the drawer draws it as one.

Each day is counted on its own, midnight to midnight in the site's time zone, so a
visit still going at midnight is closed with its day and the next day's count opens
another. people/timeline._past_midnight marks the next day's part (`continues`) when
inside one day the two would have been one visit: the next day, within the session
gap, from no new outside source. What is pinned:

  * the split pair is marked, with the part before's [day, seq];
  * a new outside source, a longer gap, a day skipped or the same day: not marked;
  * the site's own session gap (report.session_gap_minutes) is the gap;
  * nothing is written: the kept visits, and so every figure, stay as counted.

Addresses are RFC 5737, the site example.com.
"""
from __future__ import annotations

import json
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald.conversions import store  # noqa: E402
from skald.people import timeline  # noqa: E402

SITE = "example.com"
IP = "203.0.113.90"
AGENT = "Mozilla/5.0 (example)"
CONFIG = {"privacy": {"keep_ips": "full"}, "conversions": {"identity": "full"},
          "report": {"timezone": "America/New_York"}}
D15, D16, D17 = "2026-11-15", "2026-11-16", "2026-11-17"


class PastMidnight(unittest.TestCase):

    def setUp(self):
        self.folder = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.folder)
        self.db = store.connect(self.folder / store.FILE)
        self.addCleanup(self.db.close)

    def visit(self, day, seq, start, end, source, landing="/", pages=1):
        self.db.execute("INSERT INTO visits (site, day, seq, ip, user_agent, start, end, source, "
                        "landing, pages, trail, posts) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '[]')",
                        (SITE, day, seq, IP, AGENT, start, end, source, landing, pages,
                         json.dumps([[landing, "page", 0]])))
        self.db.commit()

    def got(self, day, seq, config=CONFIG):
        out = timeline.visitor(config, self.folder, SITE, day, seq)
        self.assertTrue(out["found"], out.get("why"))
        return {(v["day"], v["seq"]): v.get("continues") for v in out["visits"] if v["kind"] == "kept"}

    # New York: 23:50 on 15 Nov is 04:50 UTC on 16 Nov.
    def test_a_visit_cut_at_midnight_is_marked(self):
        self.visit(D15, 7, "2026-11-16T04:50:00Z", "2026-11-16T04:50:01Z", "Direct or unknown")
        self.visit(D16, 0, "2026-11-16T05:00:00Z", "2026-11-16T05:10:00Z", "This site", "/features/", 2)
        self.assertEqual(self.got(D16, 0), {(D15, 7): None, (D16, 0): [D15, 7]})
        self.assertEqual(self.got(D15, 7)[(D16, 0)], [D15, 7], "the same from either part")

    def test_a_new_outside_source_after_midnight_is_a_new_visit(self):
        self.visit(D15, 7, "2026-11-16T04:50:00Z", "2026-11-16T04:55:00Z", "Direct or unknown")
        self.visit(D16, 0, "2026-11-16T05:01:00Z", "2026-11-16T05:02:00Z", "Search engine")
        self.assertIsNone(self.got(D16, 0)[(D16, 0)])

    def test_a_gap_longer_than_the_session_gap_is_a_new_visit(self):
        self.visit(D15, 7, "2026-11-16T04:20:00Z", "2026-11-16T04:25:00Z", "Direct or unknown")
        self.visit(D16, 0, "2026-11-16T05:00:00Z", "2026-11-16T05:01:00Z", "This site")
        self.assertIsNone(self.got(D16, 0)[(D16, 0)], "35 minutes apart, the gap is 30")
        wider = {**CONFIG, "report": {**CONFIG["report"], "session_gap_minutes": 45}}
        self.assertEqual(self.got(D16, 0, wider)[(D16, 0)], [D15, 7], "the site's own gap")

    def test_a_day_skipped_or_the_same_day_is_never_marked(self):
        self.visit(D15, 7, "2026-11-16T04:50:00Z", "2026-11-16T04:55:00Z", "Direct or unknown")
        self.visit(D17, 0, "2026-11-16T05:00:00Z", "2026-11-16T05:01:00Z", "This site")
        self.visit(D16, 3, "2026-11-17T15:00:00Z", "2026-11-17T15:01:00Z", "Direct or unknown")
        self.visit(D16, 4, "2026-11-17T15:10:00Z", "2026-11-17T15:11:00Z", "This site")
        got = self.got(D16, 3)
        self.assertIsNone(got[(D17, 0)], "two days on")
        self.assertIsNone(got[(D16, 4)], "the same day: the count already chose two visits")

    def test_nothing_is_written(self):
        self.visit(D15, 7, "2026-11-16T04:50:00Z", "2026-11-16T04:50:01Z", "Direct or unknown")
        self.visit(D16, 0, "2026-11-16T05:00:00Z", "2026-11-16T05:10:00Z", "This site")
        before = list(self.db.execute("SELECT * FROM visits ORDER BY day, seq"))
        self.got(D16, 0)
        self.assertEqual(list(self.db.execute("SELECT * FROM visits ORDER BY day, seq")), before)
        self.assertNotIn("continues", [d[1] for d in self.db.execute("PRAGMA table_info(visits)")])


if __name__ == "__main__":
    unittest.main()
