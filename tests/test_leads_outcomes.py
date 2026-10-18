"""A lead that is later won or lost (2.14.x): it counts once, on the day it was
completed (or paid), whatever happens to it later; won and lost are outcomes,
shown apart, never a lead again and never taking one away. Checked on both
roads for Overview's Leads tile (conversions.json days, the sums leadfigs.js
and conversions_leads.day_leads make), the mails and client reports
(conversions_leads.period_leads, audit_client_reports.recount_leads), the
Overview recount (audit_conversions_leads.range_counts) and Leads & sales
(the lead database: leads.json and audit_leads; the tools: conversions.json).

Two roads in: the site's lead database (its status changed by the team) and a
lead hook that later posts the same ref with stage won or lost. Names and
addresses are made up; hosts example.com.
"""
from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from support import NY  # noqa: E402
from test_conversions_from_leads import lead_db  # noqa: E402

from skald import (audit_client_reports, audit_conversions_figures,  # noqa: E402
                          audit_conversions_leads, audit_leads, conversions_data, conversions_leads,
                          leads)
from skald.conversions import FINISHED, from_leads, store  # noqa: E402

SITE = "example.com"
DAY = date(2026, 10, 6)            # every lead is completed on this day (New York)
LATER = date(2026, 10, 9)          # the outcomes arrive by this day
TODAY = date(2026, 10, 10)
# (id, created_at, updated_at, type, status, first_touch, last_touch, visits, country, session)
LEADS = [(1, "2026-10-06T15:00:00.000Z", "2026-10-06T15:00:00.000Z", "signup", "new",
          None, None, None, None, None),
         (2, "2026-10-06T16:00:00.000Z", "2026-10-06T16:00:00.000Z", "contact", "new",
          None, None, None, None, None)]


class History:
    """What period_leads reads of the history: where its file is."""

    def __init__(self, folder: Path):
        self.path = folder / "history.sqlite"


class LaterOutcomes(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.leads = lead_db(self.dir / "leads.db", LEADS)
        self.config = {"site": {"name": SITE}, "leads": {"db": str(self.leads)}}
        self.path = self.dir / "conversions.sqlite"
        self.db = store.connect(self.path)
        from_leads.sync(self.db, self.leads, SITE)
        # Two leads through the lead hook, completed the same day.
        self.hook("h1", "demo", "completed", "2026-10-06T17:00:00Z")
        self.hook("h2", "contact", "completed", "2026-10-06T18:00:00Z")

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def hook(self, ref: str, action: str, stage: str, at: str) -> None:
        store.record_conversion(self.db, {"site": SITE, "tool": "lead", "external_ref": ref,
                                          "action": action, "stage": stage, "at": at})

    def outcomes(self) -> None:
        """The team marks lead 1 won and lead 2 lost in the lead database, and
        the hook posts h1 won and h2 lost, days later."""
        raw = sqlite3.connect(self.leads)
        raw.execute("UPDATE submissions SET status = 'won', updated_at = "
                    "'2026-10-09T10:00:00.000Z' WHERE id = 1")
        raw.execute("UPDATE submissions SET status = 'lost', updated_at = "
                    "'2026-10-08T10:00:00.000Z' WHERE id = 2")
        raw.commit()
        raw.close()
        from_leads.sync(self.db, self.leads, SITE)
        self.hook("h1", "demo", "won", "2026-10-09T12:00:00Z")
        self.hook("h2", "contact", "lost", "2026-10-08T12:00:00Z")

    # ------------------------------------------------------------ the counts
    def tile(self, first: date, last: date) -> tuple[int, dict]:
        """Overview's Leads tile: conversions.json's checked days, summed."""
        days = conversions_data.figures(self.db, SITE, NY, first, last, store.stamp(), 0)
        return sum(conversions_leads.day_leads(d) for d in days.values()), days

    def recounts(self, first: date, last: date) -> tuple[int, int]:
        ro = audit_conversions_figures._open(self.path)
        try:
            overview = audit_conversions_leads.range_counts(
                ro, SITE, NY, first.isoformat(), last.isoformat(), None)["leads"]
        finally:
            ro.close()
        reports = sum((audit_client_reports.recount_leads(self.path, SITE, NY, first, last)
                       or {}).values())
        return overview, reports

    def mails(self, first: date, last: date) -> dict:
        return conversions_leads.period_leads(self.config, History(self.dir), SITE, NY, first, last)

    def every_count(self) -> dict:
        tile, _ = self.tile(DAY, LATER)
        mail = self.mails(DAY, LATER)
        overview, reports = self.recounts(DAY, LATER)
        return {"tile": tile, "mails": mail["total"], "by_action": mail["by_action"],
                "overview recount": overview, "reports recount": reports,
                "after the day": (self.tile(DAY.replace(day=7), LATER)[0],
                                  self.mails(DAY.replace(day=7), LATER)["total"],
                                  *self.recounts(DAY.replace(day=7), LATER))}

    # ------------------------------------------------------------ the tests
    def test_a_lead_counts_once_on_its_day_and_stays_counted_once_won_or_lost(self):
        before = self.every_count()
        self.assertEqual(before["tile"], 4)
        self.assertEqual(before["by_action"], {"signup": 1, "contact": 2, "demo": 1})
        self.outcomes()
        after = self.every_count()
        self.assertEqual(after, before, "a later won or lost neither adds a lead nor takes one away")
        self.assertEqual((after["overview recount"], after["reports recount"]), (4, 4))
        self.assertEqual(after["after the day"], (0, 0, 0, 0),
                         "the days the outcomes arrive count no lead")
        self.assertEqual(audit_client_reports.check_leads(
            self.path, SITE, NY, DAY, LATER, self.mails(DAY, LATER)), [])

    def test_won_and_lost_are_shown_apart_as_outcomes(self):
        self.outcomes()
        _, days = self.tile(DAY, LATER)
        stages = {}
        for d, f in days.items():
            for action, per in f["stages"].items():
                for stage, n in per.items():
                    stages[(d, action, stage)] = n
        # The lead database's outcome sits on the lead's own day (as known now), the
        # hook's on the day it was posted; the completed rows are all still there.
        self.assertEqual(stages[("2026-10-06", "signup", "won")], 1)
        self.assertEqual(stages[("2026-10-06", "contact", "lost")], 1)
        self.assertEqual(stages[("2026-10-09", "demo", "won")], 1)
        self.assertEqual(stages[("2026-10-08", "contact", "lost")], 1)
        self.assertEqual(sum(n for (d, a, st), n in stages.items() if st in FINISHED), 4)
        self.assertNotIn("won", FINISHED)
        self.assertNotIn("lost", FINISHED)

    def test_leads_and_sales_from_the_lead_database(self):
        self.outcomes()
        blob = leads.blob(self.config, NY, TODAY, [], date(2026, 10, 1))
        day = next(d for d in blob["days"] if d["day"] == DAY.isoformat())
        self.assertEqual(day["leads"], {"signup": 1, "contact": 1}, "each lead once, on its day")
        self.assertEqual(day["status"], {"won": 1, "lost": 1}, "the outcome is its status")
        self.assertTrue(all(not d["leads"] for d in blob["days"] if d["day"] > DAY.isoformat()))
        recount = audit_leads.audit_leads(self.leads, NY, date(2026, 10, 1), TODAY)
        self.assertEqual(audit_leads.compare(blob, recount), [])
        self.assertEqual(recount["days"][DAY.isoformat()]["leads"], {"signup": 1, "contact": 1})

    def test_an_outcome_alone_is_not_a_lead(self):
        # A hook that posts "won" for a ref never completed: an outcome with no lead.
        self.hook("h3", "contact", "won", "2026-10-06T19:00:00Z")
        self.assertEqual(self.every_count()["tile"], 4)
        self.assertEqual(self.recounts(DAY, LATER), (4, 4))


if __name__ == "__main__":
    unittest.main()
