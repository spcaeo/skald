"""One name per action (Phase 4b step 3): Calendly, Cal.com, HubSpot meetings
and the page's demo events are all "demo"; Stripe is "paid"; forms are
"contact" or "signup". The store's schema 2 renames old rows, adds the
stages "won" and "lost", and keeps a copy of the file it upgraded.
Hosts are example.com; the secret is made up."""
from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from conversions_support import VID  # noqa: E402

from skald import audit_conversions  # noqa: E402
from skald.conversions import ALIASES, EVENTS, STAGES, action_name, store  # noqa: E402
from skald.conversions.adapters import adapter  # noqa: E402

V1 = """
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE conversions (
  id INTEGER PRIMARY KEY, site TEXT NOT NULL, action TEXT NOT NULL,
  stage TEXT NOT NULL CHECK (stage IN ('started', 'completed', 'cancelled',
                                       'rescheduled', 'no_show', 'paid')),
  at TEXT NOT NULL, vid TEXT, external_ref TEXT NOT NULL, tool TEXT NOT NULL,
  source_type TEXT, first_source TEXT, campaign TEXT, landing TEXT, country TEXT,
  device TEXT, first_touch_at TEXT, visits_before INTEGER, identity_id INTEGER,
  received_at TEXT NOT NULL, UNIQUE (site, tool, external_ref, stage));
INSERT INTO meta VALUES ('schema_version', '1');
"""


def old_row(db, action, stage, tool, ref):
    db.execute("INSERT INTO conversions (site, action, stage, at, external_ref, tool, "
               "received_at) VALUES ('example.com', ?, ?, '2026-10-10T10:00:00Z', ?, ?, "
               "'2026-10-10T10:00:00Z')", (action, stage, ref, tool))


class Names(unittest.TestCase):
    def test_every_tool_says_demo_paid_contact(self):
        acts = {tool: {a for a, _ in m.values()} for tool, m in EVENTS.items()}
        self.assertEqual(acts["calendly"], {"demo"})
        self.assertEqual(acts["calcom"], {"demo"})
        self.assertEqual(acts["stripe"], {"paid"})
        self.assertEqual(acts["typeform"], {"contact"})
        self.assertEqual(acts["hubspot"], {"contact", "demo", "deal"})
        self.assertEqual(EVENTS["hubspot"]["deal.propertyChange+closedwon"], ("deal", "won"))
        self.assertIn("won", STAGES)
        self.assertIn("lost", STAGES)

    def test_aliases(self):
        self.assertEqual(action_name("booking"), "demo")
        self.assertEqual(action_name("Checkout"), "paid")
        self.assertEqual(action_name("form"), "contact")
        self.assertEqual(action_name("trial"), "trial")
        self.assertEqual(ALIASES["demo_booked"], "demo")

    def test_lead_hook_aliases(self):
        r = adapter("lead").record({"external_ref": "L1", "action": "booking"})
        self.assertEqual(r["action"], "demo")

    def test_stripe_unpaid_is_a_start(self):
        mod = adapter("stripe")
        body = {"object": "event", "type": "checkout.session.completed", "created": 1,
                "data": {"object": {"id": "cs_1", "payment_status": "unpaid"}}}
        self.assertEqual((mod.to_records(body)[0]["action"], mod.to_records(body)[0]["stage"]),
                         ("paid", "started"))

    def test_hubspot_meeting_and_workflow(self):
        mod = adapter("hubspot")
        got = mod.to_records([{"subscriptionType": "object.creation", "objectTypeId": "0-47",
                               "objectId": 3}])
        self.assertEqual([(r["action"], r["stage"], r["external_ref"]) for r in got],
                         [("demo", "completed", "demo:3")])
        flow = mod.to_records({"objectId": 7, "properties": {
            "skald_action": {"value": "demo"}, "skv": {"value": VID}}})[0]
        self.assertEqual((flow["action"], flow["external_ref"]), ("demo", "workflow:7"))
        plain = mod.to_records({"objectId": 8, "properties": {}})[0]
        self.assertEqual(plain["action"], "contact")
        # The second count reads both the same way.
        self.assertEqual(audit_conversions._read("hubspot", [
            {"subscriptionType": "object.creation", "objectTypeId": "0-47", "objectId": 3}]),
            [("demo", "completed", "demo:3", None)])
        self.assertEqual(audit_conversions._read("hubspot", {
            "objectId": 7, "properties": {"skald_action": {"value": "booking"}}})[0][:3],
            ("demo", "completed", "workflow:7"))
        self.assertEqual(audit_conversions._read("lead", {"external_ref": "x",
                                                          "action": "checkout"})[0][:2],
                         ("paid", "completed"))


class Upgrade(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "conversions.sqlite"
        raw = sqlite3.connect(self.path)
        raw.executescript(V1)
        old_row(raw, "booking", "completed", "calendly", "u1")
        old_row(raw, "booking", "cancelled", "calendly", "u1")
        old_row(raw, "checkout", "completed", "stripe", "cs_1")
        old_row(raw, "checkout", "paid", "stripe", "cs_2")
        old_row(raw, "deal", "paid", "hubspot", "deal:9")
        old_row(raw, "form", "completed", "typeform", "tk")
        old_row(raw, "form", "completed", "hubspot", "workflow:7")
        old_row(raw, "trial", "completed", "json", "Z1")
        raw.commit()
        raw.close()

    def tearDown(self):
        self.tmp.cleanup()

    def test_upgrade_renames_and_keeps_a_copy(self):
        db = store.connect(self.path)
        try:
            self.assertEqual(store.schema_version(db), store.SCHEMA_VERSION)
            got = sorted(tuple(r) for r in db.execute(
                "SELECT tool, external_ref, action, stage FROM conversions"))
            self.assertEqual(got, sorted([
                ("calendly", "u1", "demo", "completed"), ("calendly", "u1", "demo", "cancelled"),
                ("stripe", "cs_1", "paid", "started"), ("stripe", "cs_2", "paid", "paid"),
                ("hubspot", "deal:9", "deal", "won"), ("typeform", "tk", "contact", "completed"),
                ("hubspot", "workflow:7", "contact", "completed"),
                ("json", "Z1", "trial", "completed")]))
            # The new stages are allowed now; the old unique rule still holds.
            self.assertTrue(store.record_conversion(db, {
                "site": "example.com", "tool": "site", "action": "demo", "stage": "won",
                "at": "2026-10-10T10:00:00Z", "external_ref": "7"}))
            self.assertFalse(store.record_conversion(db, {
                "site": "example.com", "tool": "calendly", "action": "demo",
                "stage": "completed", "at": "2026-10-10T10:00:00Z", "external_ref": "u1"}))
            indexes = {r[0] for r in db.execute("SELECT name FROM sqlite_master "
                                                "WHERE type = 'index'")}
            self.assertTrue({"conversions_at", "conversions_vid"} <= indexes)
            tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master "
                                               "WHERE type = 'table'")}
            self.assertTrue({"webhooks", "outbox"} <= tables)
        finally:
            db.close()
        copy = self.path.with_name("conversions.sqlite.v1.bak")
        self.assertTrue(copy.exists())
        old = sqlite3.connect(copy)
        self.assertEqual(old.execute("SELECT COUNT(*) FROM conversions WHERE action = "
                                     "'booking'").fetchone()[0], 2)
        old.close()
        # A second open changes nothing more.
        store.connect(self.path).close()


if __name__ == "__main__":
    unittest.main()
