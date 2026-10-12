"""The site's lead database as a conversion source (conversions/from_leads.py):
read-only, idempotent, incremental, no personal data unless identity is
full, and a second count (audit_conversions.recount_leads) by its own SQL.

Every name and email below is made up; addresses are example.com.
"""
from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import unittest
from datetime import date, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from support import NY  # noqa: E402
from test_leads import SCHEMA, touch  # noqa: E402

from skald import audit_conversions  # noqa: E402
from skald.conversions import from_leads, store  # noqa: E402

SITE = "example.com"
UTC = timezone.utc
SESSION = "sess_0123456789abcdef"

# (id, created_at, updated_at, type, status, first_touch, last_touch, visits, country, session)
LEADS = [
    (1, "2026-10-06T15:00:00.000Z", "2026-10-06T15:00:00.000Z", "demo_booked", "new",
     touch(referrerHost="www.google.com", landingPath="/pricing/",
           at="2026-10-04T15:00:00.000Z"),
     touch(utmSource="linkedin", utmMedium="social", utmCampaign="launch",
           landingPath="/features/"), 3, "CA", SESSION),
    (2, "2026-10-06T16:00:00.000Z", "2026-10-06T16:00:00.000Z", "contact", "spam",
     None, None, 1, None, None),
    (3, "2026-10-07T03:30:00.000Z", "2026-10-08T09:00:00.000Z", "signup", "won",
     touch(aiSource="chatgpt.com", referrerHost="chatgpt.com", landingPath="/compare/",
           at="2026-10-07T03:00:00.000Z"), None, 0, "us", None),
    (4, "2026-10-07T14:00:00.000Z", "2026-10-07T14:00:00.000Z", "demo_opened", "new",
     None, None, None, None, "x"),
    (5, "2026-10-07T18:00:00.000Z", "2026-10-07T18:00:00.000Z", "waitlist", "lost",
     None, None, None, "", None),
    (6, "2026-10-07T19:00:00.000Z", "2026-10-07T19:00:00.000Z", "contact", "contacted",
     "not json", None, None, None, None),
    (7, "2026-10-07T20:00:00.000Z", "2026-10-07T20:00:00.000Z", "Partner Form!", "new",
     None, None, None, None, None),
]


def lead_db(path: Path, rows=LEADS) -> Path:
    db = sqlite3.connect(path)
    db.executescript(SCHEMA)
    for r in rows:
        add(db, *r)
    db.commit()
    db.close()
    return path


def add(db, i, made, updated, kind, status, first, last, visits, country, session):
    db.execute("INSERT INTO submissions (id, type, email, fields, updated_at, created_at, "
               "status, name, first_touch, last_touch, visits, ip_country, session_id) "
               "VALUES (?, ?, ?, '{}', ?, ?, ?, ?, ?, ?, ?, ?, ?)",
               (i, kind, f"person{i}@example.com", updated, made, status, f"Person {i}",
                first, last, visits, country, session))


class FromLeads(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.leads = lead_db(self.dir / "leads.db")
        self.config = {"leads": {"db": str(self.leads)}, "site": {"name": SITE}}
        self.db = store.connect(self.dir / "conversions.sqlite")

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def rows(self, sql="SELECT external_ref, action, stage, at FROM conversions "
                       "WHERE tool = 'site' ORDER BY CAST(external_ref AS INTEGER), stage"):
        return [tuple(r) for r in self.db.execute(sql)]

    def sync(self, **kw):
        return from_leads.sync(self.db, self.leads, SITE, **kw)

    def test_enabled(self):
        self.assertTrue(from_leads.enabled(self.config))
        self.assertFalse(from_leads.enabled({}))
        self.assertFalse(from_leads.enabled({**self.config,
                                             "conversions": {"from_leads": False}}))

    def test_maps_each_lead(self):
        got = self.sync()
        self.assertEqual(got["added"], 7)
        self.assertEqual(self.rows(), [
            ("1", "demo", "completed", "2026-10-06T15:00:00Z"),
            ("3", "signup", "completed", "2026-10-07T03:30:00Z"),
            ("3", "signup", "won", "2026-10-07T03:30:00Z"),
            ("4", "demo", "started", "2026-10-07T14:00:00Z"),
            ("5", "waitlist", "completed", "2026-10-07T18:00:00Z"),
            ("5", "waitlist", "lost", "2026-10-07T18:00:00Z"),
            ("6", "contact", "completed", "2026-10-07T19:00:00Z")],
            "spam is no lead; a type that is no token is left out")

    def test_a_session_id_is_no_visitor_id_unless_visitor_ids_are_on(self):
        self.sync()
        one = self.db.execute("SELECT vid FROM conversions WHERE external_ref = '1'").fetchone()
        self.assertIsNone(one[0], "a 30-minute session would count a later booking as abandoned")
        got = self.sync(full=True, keep_vid=True)
        self.assertGreater(got["removed"], 0, "turning visitor IDs on rewrites the rows")
        one = self.db.execute("SELECT vid FROM conversions WHERE external_ref = '1'").fetchone()
        self.assertEqual(one[0], SESSION)

    def test_fields(self):
        self.sync(keep_vid=True)
        one = dict(self.db.execute("SELECT * FROM conversions WHERE external_ref = '1'").fetchone())
        self.assertEqual(one["vid"], SESSION)
        self.assertEqual(one["source_type"], "Social media")        # the last touch
        self.assertEqual(one["first_source"], "Search engine")
        self.assertEqual(one["campaign"], "linkedin / social / launch")
        self.assertEqual(one["landing"], "/pricing/")
        self.assertEqual(one["country"], "CA")
        self.assertIsNone(one["device"], "the lead DB does not say")
        self.assertEqual(one["visits_before"], 3)
        self.assertEqual(one["first_touch_at"], "2026-10-04T15:00:00Z")
        self.assertIsNone(one["identity_id"])
        three = dict(self.db.execute("SELECT * FROM conversions WHERE external_ref = '3' "
                                     "AND stage = 'completed'").fetchone())
        self.assertEqual((three["source_type"], three["first_source"], three["country"]),
                         ("AI assistant", "AI assistant", "US"))
        self.assertEqual(three["visits_before"], 0)
        four = dict(self.db.execute("SELECT * FROM conversions WHERE external_ref = '4'")
                    .fetchone())
        self.assertIsNone(four["vid"], "too short for a visitor ID")
        self.assertIsNone(four["source_type"], "no touch: not recorded, never Direct")
        self.assertIsNone(four["visits_before"])
        self.assertIsNone(four["country"])

    def test_no_personal_data(self):
        self.sync()
        dump = "\n".join(self.db.iterdump())
        self.assertNotIn("person1@example.com", dump)
        self.assertNotIn("Person 1", dump)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM identities").fetchone()[0], 0)

    def test_identity_full_keeps_name_and_email(self):
        self.sync(identity_full=True)
        got = self.db.execute("SELECT i.email, i.name FROM conversions c JOIN identities i "
                              "ON i.id = c.identity_id WHERE c.external_ref = '1'").fetchone()
        self.assertEqual(tuple(got), ("person1@example.com", "Person 1"))

    def test_idempotent_and_incremental(self):
        self.sync()
        before = self.rows("SELECT id, external_ref, stage FROM conversions ORDER BY id")
        again = self.sync()
        self.assertEqual((again["added"], again["removed"]), (0, 0))
        self.assertEqual(self.rows("SELECT id, external_ref, stage FROM conversions "
                                   "ORDER BY id"), before, "unchanged rows keep their ids")
        # Lead 1 is won later; lead 6 turns out to be spam; a new lead arrives.
        raw = sqlite3.connect(self.leads)
        raw.execute("UPDATE submissions SET status = 'won', updated_at = "
                    "'2026-10-09T10:00:00.000Z' WHERE id = 1")
        raw.execute("UPDATE submissions SET status = 'spam', updated_at = "
                    "'2026-10-09T10:00:00.000Z' WHERE id = 6")
        add(raw, 8, "2026-10-09T11:00:00.000Z", "2026-10-09T11:00:00.000Z", "contact", "new",
            None, None, None, None, None)
        raw.commit()
        raw.close()
        got = self.sync()
        # The three changed, and lead 3, whose updated_at was the last one seen.
        self.assertEqual(got["read"], 4, "only what changed since the last sync")
        self.assertEqual((got["added"], got["removed"]), (2, 1))
        refs = self.rows("SELECT external_ref, stage FROM conversions WHERE tool = 'site'")
        self.assertIn(("1", "won"), refs)
        self.assertNotIn(("6", "completed"), refs)
        self.assertIn(("8", "completed"), refs)

    def test_full_sync_drops_deleted_leads(self):
        self.sync()
        raw = sqlite3.connect(self.leads)
        raw.execute("DELETE FROM submissions WHERE id = 6")
        raw.commit()
        raw.close()
        self.assertEqual(self.sync()["removed"], 0, "an incremental sync cannot see a delete")
        self.assertEqual(self.sync(full=True)["removed"], 1)
        self.assertNotIn(("6",), self.rows("SELECT external_ref FROM conversions"))

    def test_read_only(self):
        before = self.leads.read_bytes()
        self.sync()
        self.assertEqual(self.leads.read_bytes(), before)

    def test_run_needs_the_setting(self):
        folder = self.dir / "h"
        self.assertIsNone(from_leads.run({}, folder, SITE))
        self.assertFalse((folder / "conversions.sqlite").exists())
        got = from_leads.run(self.config, folder, SITE)
        self.assertEqual(got["added"], 7)
        bad = {"leads": {"db": str(self.dir / "missing.db")}}
        self.assertEqual(from_leads.run(bad, folder, SITE)["error"][:9], "not found")

    def test_second_count_agrees_and_catches(self):
        self.sync()
        first, last = date(2026, 10, 1), date(2026, 10, 11)
        for tz in (UTC, NY):
            counted = audit_conversions.recount_leads(self.leads, tz, first, last)
            stored = store.day_counts(self.db, SITE, tz, first, last, tools=("site",))
            self.assertEqual(counted, stored)
        ny = audit_conversions.recount_leads(self.leads, NY, first, last)
        # 03:30 UTC on the 7th is 23:30 on the 6th in New York.
        self.assertEqual(ny["2026-10-06"], {("demo", "completed"): 1, ("signup", "completed"): 1,
                                            ("signup", "won"): 1})
        self.db.execute("DELETE FROM conversions WHERE external_ref = '5' AND stage = 'lost'")
        stored = store.day_counts(self.db, SITE, UTC, first, last, tools=("site",))
        found = audit_conversions.compare(
            stored, audit_conversions.recount_leads(self.leads, UTC, first, last), first, last)
        self.assertEqual(list(found), ["2026-10-07"])


if __name__ == "__main__":
    unittest.main()
