"""Settings > Integrations, 2.4.0: the doctor's lines for the roads in, each
hook's state in words, the Calendly and Cal.com event types kept per site
(a settings row the receiver reads), and one lead from two tools.
Hosts are example.com; the secrets are made up."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_integrations_api import A, Base  # noqa: E402

from skald.conversions import event_types, roads, store  # noqa: E402

TYPE_A = "https://api.calendly.com/event_types/AAAA1111"
DOWN = {"up": False, "script": None, "error": "ConnectionRefusedError: refused"}


class Status(Base):
    def setUp(self):
        super().setUp()
        patcher = mock.patch.object(roads, "helper", return_value=DOWN)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_the_status_lines_and_each_hooks_words(self):
        j = self.get().json
        parts = {s["id"]: s for s in j["status"]}
        self.assertEqual(parts["receiver"]["state"], "NEEDS ATTENTION")
        self.assertEqual(parts["hooks"]["state"], "OFF")
        lead = next(t for t in j["tools"] if t["tool"] == "lead")
        self.assertEqual((lead["state"], lead["words"]), ("needs_secret", "needs a secret"))
        self.do("secret", {"tool": "lead"})
        j = self.get().json
        lead = next(t for t in j["tools"] if t["tool"] == "lead")
        self.assertEqual((lead["state"], lead["attention"]), ("never", True))
        self.assertIn("hook:lead", {s["id"] for s in j["status"]})
        self.do("test", {"tool": "lead"})
        lead = next(t for t in self.get().json["tools"] if t["tool"] == "lead")
        self.assertEqual(lead["state"], "ready")
        self.assertEqual(j["duplicates"], [])

    def test_event_types_are_a_settings_row_the_receiver_reads(self):
        j = self.get().json
        cal = next(t for t in j["tools"] if t["tool"] == "calendly")
        self.assertEqual(cal["event_types"]["value"], [])
        self.assertTrue(cal["event_types"]["editable"])
        self.assertIsNone(next(t for t in j["tools"] if t["tool"] == "lead")["event_types"])
        self.assertEqual(self.do("hooks/types", {"tool": "lead", "types": ["x"]}).status, 400)
        self.assertEqual(self.do("hooks/types", {"tool": "calendly",
                                                 "types": ["two words"]}).status, 400)
        self.assertEqual(self.do("hooks/types", {"tool": "calendly", "types": [TYPE_A]},
                                 "viewer@example.com").status, 403)
        got = self.do("hooks/types", {"tool": "calendly", "types": [TYPE_A, TYPE_A]})
        self.assertEqual(got.status, 200, got.json)
        self.assertEqual(got.json["types"], [TYPE_A])
        cal = next(t for t in self.get().json["tools"] if t["tool"] == "calendly")
        self.assertEqual((cal["event_types"]["value"], cal["event_types"]["source"]),
                         ([TYPE_A], "site"))
        self.assertEqual(event_types.wanted(self.config, A, "calendly", self.live), [TYPE_A])
        self.assertTrue(any(r[1] == "hooks.calendly.event_types" for r in
                            [(x["action"], x["target"]) for x in self.audit()]))
        got = self.do("hooks/types", {"tool": "calendly", "types": []})
        self.assertEqual(got.json["types"], [])
        self.assertEqual(event_types.wanted(self.config, A, "calendly", self.live), [])

    def test_one_lead_from_two_tools_is_flagged(self):
        db = store.connect(self.live / "conversions.sqlite")
        try:
            for tool in ("lead", "site"):
                store.record_conversion(db, {
                    "site": A, "tool": tool, "action": "demo", "stage": "completed",
                    "at": "2026-10-11T10:00:00Z", "external_ref": "L-1",
                    "received_at": "2026-10-11T10:00:00Z"})
            db.commit()
        finally:
            db.close()
        j = self.get().json
        self.assertEqual([(d["ref"], d["tools"]) for d in j["duplicates"]],
                         [("L-1", ["lead", "site"])])
        twice = next(s for s in j["status"] if s["id"] == "duplicates")
        self.assertEqual(twice["state"], "NEEDS ATTENTION")
        self.assertIn("L-1 (lead and site)", twice["says"])


if __name__ == "__main__":
    unittest.main()
