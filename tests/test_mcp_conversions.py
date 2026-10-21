"""The MCP `conversions` tool: by action and stage, by source, abandoned,
over a range of conversions.json; withheld and not-recorded days named,
never counted as zero. A hand-written dashboard folder, host example.com."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_mcp_withheld import Base  # noqa: E402

from skald.mcp import tools  # noqa: E402

WHY = "the second count (audit_conversions.py) disagrees: planted"


def day(d, demo_started=0, demo_done=0, contact=0, abandoned=0, src="Search engine"):
    stages = {}
    if demo_started or demo_done:
        stages["demo"] = {k: v for k, v in (("started", demo_started),
                                            ("completed", demo_done)) if v}
    if contact:
        stages["contact"] = {"completed": contact}
    by = {"source_type": {}}
    if demo_done:
        by["source_type"]["demo"] = {src: demo_done}
    if contact:
        by["source_type"]["contact"] = {"Direct or unknown": contact}
    return {"day": d, "state": "ok", "stages": stages,
            "abandoned": {"demo": abandoned} if abandoned else {}, "by": by}


class Conversions(Base):
    def file(self, **over):
        doc = {"available": True, "min_rate": 10, "finished": ["completed", "paid"],
               "since": "2026-10-01",
               "days": [{"day": "2026-09-30", "state": "before"},
                        day("2026-10-01", 12, 5, contact=1, abandoned=6),
                        {"day": "2026-10-02", "state": "withheld", "why": WHY},
                        day("2026-10-03", 3, 2, abandoned=1, src="Social media")]}
        doc.update(over)
        self.write("conversions", doc)

    def test_sums_and_names_what_is_left_out(self):
        self.file()
        text, data = self.run_tool("conversions", **{"from": "2026-09-30", "to": "2026-10-03"})
        self.assertEqual(data["actions"]["demo"], {"started": 15, "completed": 7,
                                                   "abandoned": 7, "completion_rate": 0.4667})
        self.assertEqual(data["actions"]["contact"]["completed"], 1)
        self.assertIsNone(data["actions"]["contact"]["completion_rate"], "no starts seen")
        self.assertEqual(data["by_source"], {"Search engine": 5, "Social media": 2,
                                             "Direct": 1}, "shown as Direct (labels.py)")
        self.assertEqual([w["day"] for w in data["withheld"]], ["2026-10-02"])
        self.assertEqual(data["not_recorded"], ["2026-09-30"])
        self.assertIn("2026-10-02", text)
        self.assertIn("demo: 15 started, 7 completed, 7 abandoned", text)

    def test_one_action_and_too_few(self):
        self.file(days=[day("2026-10-03", 3, 2)])
        _, data = self.run_tool("conversions", action="demo", **{"from": "2026-10-03",
                                                                 "to": "2026-10-03"})
        self.assertEqual(list(data["actions"]), ["demo"])
        self.assertIsNone(data["actions"]["demo"]["completion_rate"], "under 10 starts")

    def test_leads_and_another_breakdown(self):
        d = day("2026-10-03", 3, 2, contact=1)
        d["stages"]["paid"] = {"paid": 4}
        d["by"]["source_type"]["paid"] = {"Email": 4}
        d["by"]["landing"] = {"demo": {"/pricing/": 2}, "contact": {"/": 1}, "paid": {"/": 4}}
        self.file(days=[d], lead_actions=["contact", "signup", "waitlist", "trial", "demo"],
                  demo_actions=["demo"])
        text, data = self.run_tool("conversions", by="landing",
                                   **{"from": "2026-10-03", "to": "2026-10-03"})
        self.assertEqual((data["leads"], data["demos_booked"], data["by"]), (3, 2, "landing"))
        self.assertEqual(data["by_source"], {"/": 5, "/pricing/": 2})
        self.assertEqual(data["leads_by"], {"/pricing/": 2, "/": 1}, "payments are not leads")
        self.assertIn("Leads (forms sent and demos booked, completed): 3, of them 2", text)
        self.assertIn("Leads, by landing page: /pricing/ 2, / 1.", text)

    def test_one_label(self):
        """2.18: a lead label narrows the stages and abandoned starts to the file's
        `labels`; the breakdowns are not split by label, so none is given."""
        d = day("2026-10-03", 3, 2, contact=4, abandoned=1)
        d["labels"] = {"contact": {"sales": {"completed": 3}, "support": {"completed": 1}},
                       "demo": {"sales": {"started": 1}}}
        d["labels_abandoned"] = {"demo": {"sales": 1}}
        self.file(days=[d])
        text, data = self.run_tool("conversions", label="Sales",
                                   **{"from": "2026-10-03", "to": "2026-10-03"})
        self.assertEqual(data["label"], "sales")
        self.assertEqual(data["actions"]["contact"]["completed"], 3)
        self.assertEqual((data["actions"]["demo"]["started"], data["actions"]["demo"]["completed"],
                          data["actions"]["demo"]["abandoned"]), (1, 0, 1))
        self.assertIsNone(data["by_source"], "not split by label: none, never zero")
        self.assertIn("not split by label", text)
        _, none = self.run_tool("conversions", label="partnership",
                                **{"from": "2026-10-03", "to": "2026-10-03"})
        self.assertEqual(none["actions"], {})

    def test_not_available(self):
        self.file(available=False, reason="no conversions yet")
        text, data = self.run_tool("conversions")
        self.assertFalse(data["available"])
        self.assertIn("never as zero", text)

    def test_listed(self):
        self.assertIn("conversions", {t["name"] for t in tools.listing()})


if __name__ == "__main__":
    unittest.main()
