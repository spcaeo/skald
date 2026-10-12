"""MCP tools never count a withheld, missing or not-recorded figure as zero.

A small dashboard folder written by hand (example.com, days 2026-10-01 to
2026-10-03): leads.json with a withheld day and withheld blocks, quality.json
with a day whose unreadable lines were not recorded, live.json without a
search figure, and a page story whose whole day has no visits figure. Each
tool leaves such a figure out, names it, and gives null rather than 0.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from skald.mcp import tools  # noqa: E402
from skald.mcp.data import Context  # noqa: E402

SITE = "example.com"
WHY = "the second count (audit_leads.py) disagrees: planted"


def lead_day(day, signup, contact=0, spam=0):
    return {"day": day, "leads": {"signup": signup, "contact": contact}, "status": {},
            "spam": spam, "duplicates": 0}


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.data = self.tmp / SITE / "data"
        self.data.mkdir(parents=True)
        self.write("overview", {"anchor": "2026-10-03", "today": "2026-10-04",
                                "timezone": "UTC", "days": []})
        self.ctx = Context(self.tmp, checker=lambda s: (True, "", False))

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def write(self, name, doc):
        (self.data / f"{name}.json").write_text(json.dumps(doc))

    def run_tool(self, name, **args):
        got = tools.call(self.ctx, name, args)
        self.assertIs(got["isError"], False, got["content"][0]["text"])
        return got["content"][0]["text"], got["structuredContent"]


class TestLeads(Base):

    def leads_file(self, **over):
        doc = {"available": True, "types": ["signup", "contact"],
               "days": [lead_day("2026-10-01", 2, 1, spam=1),
                        {"day": "2026-10-02", "state": "withheld", "why": WHY},
                        lead_day("2026-10-03", 4)],
               "period": {"first": "2026-09-04", "last": "2026-10-03",
                          "first_touch": {"source": {"Search engine": 3}}},
               "by_source_type": {"first_touch": {}}, "funnel": {"steps": []},
               "withheld": {"days/2026-10-02": WHY}}
        doc.update(over)
        self.write("leads", doc)

    def test_a_withheld_day_is_left_out_and_named(self):
        self.leads_file()
        text, s = self.run_tool("leads", **{"from": "2026-10-01", "to": "2026-10-03"})
        self.assertEqual(s["leads"], {"signup": 6, "contact": 1})
        self.assertEqual(s["days_counted"], 2)
        self.assertEqual(s["days_withheld"], [{"day": "2026-10-02", "why": WHY}])
        self.assertIn("2026-10-02", text)
        self.assertIn("withheld", text)

    def test_only_withheld_days_give_null_never_zero(self):
        self.leads_file()
        text, s = self.run_tool("leads", **{"from": "2026-10-02", "to": "2026-10-02"})
        self.assertIsNone(s["leads"])
        self.assertIsNone(s["spam"])
        self.assertIsNone(s["duplicates"])
        self.assertEqual(s["days_counted"], 0)
        self.assertNotIn("signup 0", text)
        self.assertIn("not recorded", text)

    def test_a_day_with_a_figure_not_recorded_is_left_out(self):
        self.leads_file(days=[lead_day("2026-10-01", 2), {"day": "2026-10-03", "leads": None}])
        text, s = self.run_tool("leads", **{"from": "2026-10-01", "to": "2026-10-03"})
        self.assertEqual(s["leads"], {"signup": 2, "contact": 0})
        self.assertEqual(s["days_counted"], 1)
        self.assertEqual(s["days_not_held"], ["2026-10-02", "2026-10-03"])

    def test_withheld_blocks_are_named_not_shown(self):
        block = {"state": "withheld", "why": WHY}
        self.leads_file(period=block, by_source_type=block, funnel=block,
                        withheld={"period": WHY, "by_source_type": WHY, "funnel": WHY})
        text, s = self.run_tool("leads")
        self.assertIsNone(s["last_30_days"])
        self.assertIsNone(s["by_source_type"])
        self.assertIsNone(s["funnel"])
        self.assertEqual(s["blocks_withheld"], {"period": WHY, "by_source_type": WHY,
                                                "funnel": WHY})
        self.assertIn("withheld", text)
        self.assertIn("by source", text)


class TestOtherTools(Base):

    def test_data_quality_unreadable_lines_not_recorded_is_null(self):
        self.write("quality", {"days": [
            {"day": "2026-10-01", "state": "ok", "unparsed": 3},
            {"day": "2026-10-02", "state": "ok", "unparsed": None},
            {"day": "2026-10-03", "state": "missing"}], "builders_failing": []})
        text, s = self.run_tool("data_quality", **{"from": "2026-10-01", "to": "2026-10-03"})
        self.assertEqual(s["unparsed"], 3)
        self.assertEqual(s["unparsed_not_recorded"], ["2026-10-02", "2026-10-03"])
        self.assertIn("2026-10-02", text.split("could not be read")[1])
        self.write("quality", {"days": [{"day": "2026-10-03", "state": "missing"}]})
        text, s = self.run_tool("data_quality", **{"from": "2026-10-03", "to": "2026-10-03"})
        self.assertIsNone(s["unparsed"])
        self.assertIn("could not be read: not recorded", text)

    def test_live_today_without_a_search_figure_is_null(self):
        self.write("live", {"state": "ok", "day": "2026-10-04", "from": "a", "until": "b",
                            "people": {"readers": 2, "views": 3}, "requests": 9})
        text, s = self.run_tool("live_today")
        self.assertIsNone(s["search_engine_fetches"])
        self.assertIn("Search-engine fetches: not recorded", text)
        self.write("live", {"state": "ok", "day": "2026-10-04", "people": {}, "search": {}})
        self.assertEqual(self.run_tool("live_today")[1]["search_engine_fetches"], 0)

    def test_page_story_a_whole_day_without_visits_makes_the_sum_null(self):
        story = {"ok": True, "path": "/", "published": "2026-10-01", "milestones": {},
                 "days": [{"day": "2026-10-01", "state": "ok", "readers": 3, "views": 4},
                          {"day": "2026-10-02", "state": "ok", "readers": None, "views": 2},
                          {"day": "2026-10-03", "state": "withheld", "readers": None,
                           "views": None}]}
        history = mock.Mock()
        with mock.patch("skald.mcp.tools_more._history", return_value=history), \
                mock.patch("skald.lifecycle.story", return_value=story):
            text, s = self.run_tool("page_story", path="/")
        self.assertIsNone(s["visits_total"])
        self.assertEqual(s["page_views_total"], 6)
        self.assertIn("read it: not recorded", text)


if __name__ == "__main__":
    unittest.main()
