"""The organisation drawer's figures (org_figures.py) and their second count
(audit_orgs.py): the requests of the 7 days before today and the last day
with data, shown only when the daily totals and the day's groups agree;
None (Not recorded) when the history holds nothing, never 0."""
from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from skald import audit_orgs, org_figures  # noqa: E402
from skald.store import History  # noqa: E402

TODAY = date(2026, 10, 27)
A, B, OTHER = "alpha.example", "beta.example", "other.example"


class Figures(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = Path(self._tmp.name) / "history.sqlite"
        with History(self.path):
            pass
        rows = [(A, "2026-10-19", 50), (A, "2026-10-20", 10), (A, "2026-10-26", 7),
                (B, "2026-10-25", 3), (A, "2026-10-27", 99), (OTHER, "2026-10-24", 1000)]
        db = sqlite3.connect(self.path)
        with db:
            for site, day, hits in rows:
                db.execute("INSERT INTO days (site, day, timezone, collected_at, verified, "
                           "parsed, hits, other_hosts, cited_visits) VALUES "
                           "(?, ?, 'UTC', '2026-10-27T00:00:00Z', 1, ?, ?, 0, 0)",
                           (site, day, hits, hits))
                for grp, n in (("people", hits - hits // 3), ("bots", hits // 3)):
                    db.execute("INSERT INTO groups (site, day, grp, hits, views, visits, probes) "
                               "VALUES (?, ?, ?, ?, 0, 0, 0)", (site, day, grp, n))
        db.close()

    def test_the_window_and_the_two_counts_agree(self):
        self.assertEqual(org_figures.window(TODAY), ("2026-10-20", "2026-10-26"))
        got = org_figures.recent(self.path, [A, B], TODAY)
        # 10 + 7 + 3: the 19th is before the window, today (the 27th) after it,
        # and another organisation's site is not counted.
        self.assertEqual(got, {"requests_7d": 20, "last_day": "2026-10-27", "withheld": None})
        self.assertEqual(audit_orgs.recount(self.path, [A, B], "2026-10-20", "2026-10-26"),
                         (20, "2026-10-27"))

    def test_withheld_when_they_disagree(self):
        db = sqlite3.connect(self.path)
        with db:
            db.execute("UPDATE groups SET hits = hits + 1 WHERE site = ? AND day = ? AND "
                       "grp = 'people'", (A, "2026-10-26"))
        db.close()
        got = org_figures.recent(self.path, [A], TODAY)
        self.assertIsNone(got["requests_7d"])
        self.assertIn("do not add up", got["withheld"])

    def test_nothing_recorded_is_none_not_zero(self):
        self.assertEqual(org_figures.recent(self.path, ["nothing.example"], TODAY),
                         {"requests_7d": None, "last_day": None, "withheld": None})
        self.assertEqual(org_figures.recent(None, [A], TODAY)["requests_7d"], None)
        self.assertEqual(org_figures.recent(self.path, [], TODAY)["requests_7d"], None)


if __name__ == "__main__":
    unittest.main()
