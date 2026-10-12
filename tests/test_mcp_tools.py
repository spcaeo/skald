"""MCP tools against a real dashboard output folder (test_mcp_support.Fixture).

Pinned: each tool answers from the data files (the expected figures are
worked out from the fixture's logs, not from the tools); only whole,
verified days are summed and the withheld day is named by date; the text
says "visits (an upper bound on people)" and never "users"; a site the
caller may not read is a tool error; addresses only with read_private."""
from __future__ import annotations

import json
import re
import sys
import unittest
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_mcp_support import FIRST, OTHER, SITE, Fixture, readers_on  # noqa: E402
from skald.mcp import protocol  # noqa: E402
from skald.mcp.data import Refused  # noqa: E402

FX = None
ADDRESS = re.compile(r"(203\.0\.113|198\.51\.100|192\.0\.2)\.\d+")
# "users" as a word of our own; a crawler's name such as ChatGPT-User is not one.
USERS = re.compile(r"(?<![\w-])users?\b", re.I)


def setUpModule():
    global FX
    FX = Fixture()


def tearDownModule():
    FX.close()


def call(ctx, tool_name, **args):
    got = protocol.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                           "params": {"name": tool_name, "arguments": args}}, ctx)
    return got["result"]


def text(result):
    return result["content"][0]["text"]


def expected_visits(days):
    return sum(readers_on(d) for d in days)


def day(n):
    return FIRST + timedelta(days=n - 1)          # day(1) = 2026-10-01


class Tools(unittest.TestCase):
    def setUp(self):
        self.ctx = FX.context(default_site=SITE)

    def ok(self, tool_name, **args):
        r = call(self.ctx, tool_name, **args)
        self.assertIs(r["isError"], False, text(r))
        self.assertNotRegex(text(r), USERS)
        return r

    def refused(self, tool_name, ctx=None, **args):
        r = call(ctx or self.ctx, tool_name, **args)
        self.assertIs(r["isError"], True)
        self.assertNotIn("structuredContent", r)
        return text(r)

    def test_list_sites(self):
        r = self.ok("list_sites")
        self.assertEqual([s["site"] for s in r["structuredContent"]["sites"]], [SITE, OTHER])
        first = r["structuredContent"]["sites"][0]
        self.assertEqual((first["first_day"], first["last_whole_day"]), ("2026-10-01",
                                                                        "2026-10-08"))
        only = call(FX.context(sites=[SITE]), "list_sites")
        self.assertEqual([s["site"] for s in only["structuredContent"]["sites"]], [SITE])
        self.assertNotIn(OTHER, text(only))

    def test_overview_default_is_the_last_7_whole_days_without_the_withheld_one(self):
        r = self.ok("overview")
        s = r["structuredContent"]
        self.assertEqual((s["from"], s["to"]), ("2026-10-02", "2026-10-08"))
        counted = [day(n) for n in (2, 3, 5, 6, 7, 8)]          # 10-04 withheld
        self.assertEqual(s["figures"]["visits"], expected_visits(counted))
        self.assertEqual(s["figures"]["ai_fetches_asked"], 6)
        self.assertEqual(s["figures"]["ai_fetches_training"], 6)
        self.assertEqual(s["coverage"]["withheld"][0]["day"], "2026-10-04")
        self.assertEqual(s["coverage"]["counted"], 6)
        t = text(r)
        self.assertIn("Visits (an upper bound on people): " + f"{expected_visits(counted):,}", t)
        self.assertIn("withheld", t)
        self.assertIn("2026-10-04", t)
        self.assertIsNone(s["previous"])                     # not complete: no change
        self.assertIn("No change is stated", t)

    def test_overview_states_a_change_only_between_complete_periods(self):
        s = self.ok("overview", **{"from": "2026-10-07", "to": "2026-10-08"})["structuredContent"]
        a, b = expected_visits([day(7), day(8)]), expected_visits([day(5), day(6)])
        self.assertEqual(s["previous"]["figures"]["visits"], b)
        self.assertEqual(s["previous"]["change_pct"]["visits"], round((a - b) / b * 100, 1))
        s = self.ok("overview", **{"from": "2026-10-05", "to": "2026-10-08"})["structuredContent"]
        self.assertIsNone(s["previous"])                     # B holds the withheld day

    def test_a_range_with_only_left_out_days_is_null_never_zero(self):
        r = self.ok("overview", **{"from": "2026-10-04", "to": "2026-10-04"})
        self.assertIsNone(r["structuredContent"]["figures"]["visits"])
        self.assertIn("not recorded", text(r))
        r = self.ok("overview", **{"from": "2026-09-20", "to": "2026-09-21"})
        self.assertEqual(r["structuredContent"]["coverage"]["missing"], ["2026-09-20",
                                                                          "2026-09-21"])
        r = self.ok("overview", **{"from": "2026-10-08", "to": "2026-10-09"})
        self.assertEqual(r["structuredContent"]["coverage"]["not_over"], ["2026-10-09"])
        self.assertIn("live_today", text(r))

    def test_bad_dates_are_plain_tool_errors(self):
        self.assertIn("YYYY-MM-DD", self.refused("overview", to="8 Oct"))
        self.assertIn("not a real date", self.refused("overview", to="2026-02-30"))
        self.assertIn("before", self.refused("overview", **{"from": "2026-10-08",
                                                             "to": "2026-10-01"}))
        self.assertIn("at most 180", self.refused("overview", **{"from": "2026-01-01",
                                                                  "to": "2026-10-08"}))

    def test_breakdown_adds_up_to_the_visits(self):
        r = self.ok("breakdown", dimension="country")
        s = r["structuredContent"]
        counted = [day(n) for n in (2, 3, 5, 6, 7, 8)]
        gb = sum(readers_on(d) // 2 for d in counted)            # odd readers are GB
        rows = {row["label"]: row["n"] for row in s["rows"]}
        self.assertEqual(rows, {"GB": gb, "US": expected_visits(counted) - gb})
        self.assertEqual(s["total"], expected_visits(counted))
        self.assertIs(s["reconciled"], True)
        self.assertIn("2026-10-04", text(r))
        self.assertIn("upper bound on people", text(r))
        self.assertIn("dimension is one of", self.refused("breakdown", dimension="planet"))
        self.assertIn("dimension is needed", self.refused("breakdown"))

    def test_breakdown_folds_the_tail_and_keeps_the_sum(self):
        s = self.ok("breakdown", dimension="landing", limit=1)["structuredContent"]
        self.assertEqual(len(s["rows"]), 2)
        self.assertEqual(s["rows"][-1]["label"], "(all others)")
        self.assertEqual(s["total"], expected_visits([day(n) for n in (2, 3, 5, 6, 7, 8)]))

    def test_top_pages(self):
        r = self.ok("top_pages", limit=5)
        pages = {p["path"]: p for p in r["structuredContent"]["pages"]}
        self.assertEqual(set(pages), {"/", "/guides/alpha"})
        self.assertEqual(sum(p["page_views"] for p in pages.values()),
                         expected_visits([day(n) for n in (2, 3, 5, 6, 7, 8)]))
        self.assertEqual(pages["/guides/alpha"]["ai_fetches"], 6)     # GPTBot once a day
        self.assertIn("top 50", text(r))

    def test_ai_activity(self):
        r = self.ok("ai_activity")
        s = r["structuredContent"]
        self.assertEqual((s["fetches_asked"], s["fetches_training"],
                          s["visits_from_ai_citations"]), (6, 6, 6))
        self.assertEqual(s["asked_by_assistant"], [{"label": "ChatGPT-User", "n": 6}])
        self.assertEqual(s["training_by_crawler"], [{"label": "GPTBot", "n": 6}])
        self.assertIsNone(s["today_events"])
        self.assertIn("a floor", text(r))
        self.assertIn("not measurable", text(r))

    def test_addresses_only_with_read_private(self):
        public = FX.context()
        with self.assertRaises(Refused):
            public.load(SITE, None, "requests")
        with self.assertRaises(Refused):
            public.load(SITE, None, "ai_activity")
        private = FX.context(private=True)
        r = call(private, "ai_activity", site=SITE)
        events = r["structuredContent"]["today_events"]
        self.assertTrue(events and all(ADDRESS.match(e["ip"]) for e in events))

    def test_no_tool_returns_an_address_without_read_private(self):
        ctx = FX.context(default_site=SITE)
        calls = [("list_sites", {}), ("overview", {}), ("breakdown", {"dimension": "source"}),
                 ("top_pages", {}), ("ai_activity", {}), ("leads", {}), ("funnel", {}),
                 ("compare", {}), ("page_story", {"path": "/"}), ("live_today", {}),
                 ("data_quality", {}), ("site_health", {})]
        for name, args in calls:
            with self.subTest(tool=name):
                r = call(ctx, name, **args)
                self.assertIs(r["isError"], False, text(r))
                self.assertNotRegex(json.dumps(r), ADDRESS)
                self.assertNotRegex(text(r), USERS)

    def test_leads_not_available_is_said_not_zeroed(self):
        r = self.ok("leads")
        self.assertIs(r["structuredContent"]["available"], False)
        self.assertIn("not available", text(r))
        self.assertNotIn("leads", r["structuredContent"])

    def test_funnel_saved_and_custom(self):
        r = self.ok("funnel")
        names = [f["name"] for f in r["structuredContent"]["funnels"]]
        self.assertIn("Landing to lead", names)
        r = self.ok("funnel", name="landing to lead")
        self.assertEqual(len(r["structuredContent"]["funnels"]), 1)
        self.assertIn("not per visit", text(r))
        self.assertIn("no funnel named", self.refused("funnel", name="Nope"))
        # The same journeys the dashboard wrote, counted here by hand.
        visits = json.loads((FX.out / SITE / "data" / "visits.json").read_text())
        good = {d["day"] for d in visits["days"] if d["state"] in ("ok", "partial")}
        journeys = [j for j in visits["journeys"] if j["day"] in good]
        journeys += visits["today"]["journeys"]
        want = sum(1 for j in journeys if any(p == "/guides/alpha" for p, _ in j["trail"]))
        r = self.ok("funnel", steps=[{"label": "All", "kind": "any"},
                                     {"label": "Guide", "kind": "path", "match": "equals",
                                      "paths": ["/guides/alpha"]}])
        steps = r["structuredContent"]["funnel"]["result"]["steps"]
        self.assertEqual((steps[0]["n"], steps[1]["n"]), (len(journeys), want))
        self.assertIn("2026-10-04", r["structuredContent"]["days_left_out"])
        self.assertIn("not valid", self.refused("funnel", steps=[{"kind": "path"}]))
        self.assertIn("saved", self.refused("funnel", steps=[
            {"label": "All", "kind": "any"}, {"label": "L", "kind": "lead",
                                              "types": ["signup"]}]))

    def test_compare_uses_the_helpers_answer(self):
        r = self.ok("compare")
        s = r["structuredContent"]
        self.assertEqual((s["a"]["from"], s["a"]["to"]), ("2026-10-02", "2026-10-08"))
        self.assertEqual((s["b"]["from"], s["b"]["to"]), ("2026-09-25", "2026-10-01"))
        m = {x["key"]: x for x in s["metrics"]}
        self.assertEqual(m["visitors"]["a"],
                         expected_visits([day(n) for n in (2, 3, 5, 6, 7, 8)]))
        self.assertIn({"day": "2026-10-04", "state": "withheld"}, s["a"]["excluded"])
        self.assertIn("withheld 2026-10-04", text(r))
        self.assertIn("No change is stated", text(r))           # B is not whole
        self.assertIn("Visits (an upper bound on people): A", text(r))
        r = self.ok("compare", a_from="2026-10-07", a_to="2026-10-08",
                    b_from="2026-10-05", b_to="2026-10-06", filters={"country": "GB"})
        m = {x["key"]: x for x in r["structuredContent"]["metrics"]}
        self.assertEqual(m["visitors"]["a"], readers_on(day(7)) // 2 + readers_on(day(8)) // 2)
        self.assertIn("A 9, B 7 (+28.6%)", text(r))             # both whole: a change
        self.assertIn("not valid", self.refused("compare", filters={"planet": "Mars"}))

    def test_page_story(self):
        r = self.ok("page_story", path="/")
        s = r["structuredContent"]
        self.assertEqual(s["path"], "/")
        self.assertTrue(s["milestones"]["googlebot"]["at"].startswith("2026-10-01"))
        self.assertIn("Googlebot first fetched it: 2026-10-01", text(r))
        self.assertIn("2026-10-04", text(r))
        self.assertIn("upper bound on people", text(r))
        self.assertIn("no page", self.refused("page_story", path="/nowhere/"))
        self.assertIn("starts with /", self.refused("page_story", path="pricing"))

    def test_live_today(self):
        r = self.ok("live_today")
        s = r["structuredContent"]
        self.assertEqual((s["state"], s["day"], s["visits"]), ("ok", "2026-10-09", 2))
        self.assertTrue(s["events"])
        self.assertTrue(all("ip" not in e for e in s["events"]))
        self.assertIn("never compare with whole days", text(r))

    def test_data_quality_and_site_health(self):
        r = self.ok("data_quality")
        self.assertIn("2026-10-04 (groups do not sum: test)", text(r))
        self.assertEqual(r["structuredContent"]["builders_failing"], [])
        r = self.ok("site_health")
        self.assertIn("Open alerts: 0", text(r))
        self.assertEqual(r["structuredContent"]["open_alerts"], [])

    def test_a_site_the_caller_may_not_read_is_a_tool_error(self):
        mine = FX.context(sites=[SITE])
        for name, args in (("overview", {}), ("breakdown", {"dimension": "country"}),
                           ("compare", {}), ("page_story", {"path": "/"}),
                           ("live_today", {}), ("site_health", {}), ("leads", {})):
            with self.subTest(tool=name):
                t = self.refused(name, ctx=mine, site=OTHER, **args)
                self.assertIn(f"You may not read {OTHER}", t)
        # The same words for a site that does not exist: nothing leaks.
        self.assertIn("You may not read nothing.example.com",
                      self.refused("overview", ctx=mine, site="nothing.example.com"))
        self.assertIn("not a site name", self.refused("overview", ctx=mine, site="../etc"))
        got = protocol.handle({"jsonrpc": "2.0", "id": 1, "method": "resources/read",
                               "params": {"uri": f"skald://sites/{OTHER}/overview"}}, mine)
        self.assertEqual(got["error"]["code"], -32002)
        listed = protocol.handle({"jsonrpc": "2.0", "id": 1, "method": "resources/list"}, mine)
        uris = [x["uri"] for x in listed["result"]["resources"]]
        self.assertIn(f"skald://sites/{SITE}/overview", uris)
        self.assertNotIn(f"skald://sites/{OTHER}/overview", uris)

    def test_the_site_must_be_named_when_there_are_several(self):
        self.assertIn("Say which site", self.refused("overview", ctx=FX.context()))
        self.assertIs(call(FX.context(sites=[OTHER]), "overview")["isError"], False)

    def test_site_overview_resource(self):
        got = protocol.handle({"jsonrpc": "2.0", "id": 1, "method": "resources/read",
                               "params": {"uri": f"skald://sites/{SITE}/overview"}}, self.ctx)
        doc = json.loads(got["result"]["contents"][0]["text"])
        self.assertEqual((doc["site"], doc["anchor"]), (SITE, "2026-10-08"))

    def test_a_file_that_failed_to_build_is_said_so(self):
        path = FX.out / OTHER / "data" / "leads.json"
        before = path.read_text()
        try:
            path.write_text(json.dumps({"schema_version": 1, "state": "error",
                                        "error": "database locked"}))
            self.assertIn("could not be built", self.refused("leads", site=OTHER))
        finally:
            path.write_text(before)


if __name__ == "__main__":
    unittest.main()
