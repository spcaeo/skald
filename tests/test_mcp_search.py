"""The search_performance MCP tool and Search Console in your_tools (2.48).

Against the MCP fixture's history with search days written as the sync writes
them (search/days.fold, write). Pinned: the engine's own figures per day for the
site and for one path (http and https, www and none added together); a page with
no row is 0 only on a day whose page table is complete, else null and named; a
day not stored is named; the page's top queries come from query_page; index
status from search_inspect; your_tools names Search Console's state."""
from __future__ import annotations

import sys
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_mcp_support import SITE, Fixture  # noqa: E402
from skald import audit_search_pages  # noqa: E402
from skald.mcp import protocol  # noqa: E402
from skald.search import days as sd, inspect, state  # noqa: E402
from skald.store import History  # noqa: E402

FX = None
D1, D2, D3, D5 = (date(2026, 10, n) for n in (1, 2, 3, 5))
HOME = "https://www.example.com/"
PRICING = "https://www.example.com/pricing/"
PRICING_HTTP = "http://example.com/pricing/"
NOW = datetime(2026, 10, 6, 15, tzinfo=timezone.utc)


def page_blob(rows, total=None, top=sd.TOP["page"]):
    return sd.fold(rows, total, top)


def setUpModule():
    global FX
    FX = Fixture()
    qp = sd.QP_SEP
    days = {
        # D1: complete page table; /pricing/ in it twice (www https and http).
        D1: {"total": sd.fold([], {"clicks": 9, "impressions": 300, "position": 4.0}, 0),
             "page": page_blob([[HOME, 5, 200, 3.0], [PRICING, 3, 80, 5.0],
                                [PRICING_HTTP, 1, 20, 10.0]]),
             "query_page": page_blob([[f"log analytics{qp}{PRICING}", 2, 50, 4.0],
                                      [f"skald price{qp}{PRICING_HTTP}", 1, 20, 9.0],
                                      [f"log analytics{qp}{HOME}", 4, 100, 2.0]],
                                     None, sd.TOP["query_page"]),
             "query": page_blob([["log analytics", 6, 150, 2.6]], None, sd.TOP["query"]),
             "page_country": page_blob([[f"{PRICING}{qp}usa", 3, 70, 5.0],
                                        [f"{PRICING_HTTP}{qp}usa", 1, 10, 9.0],
                                        [f"{PRICING}{qp}deu", 0, 10, 6.0],
                                        [f"{HOME}{qp}usa", 5, 200, 3.0]],
                                       None, sd.TOP["page_country"]),
             "country": page_blob([["usa", 9, 300, 4.0]], None, sd.TOP["country"])},
        # D2: complete, /pricing/ has no row: 0 for it.
        D2: {"total": sd.fold([], {"clicks": 4, "impressions": 90, "position": 6.0}, 0),
             "page": page_blob([[HOME, 4, 90, 6.0]])},
        # D3: not complete (one page kept, the rest summed): /pricing/ not known.
        D3: {"total": sd.fold([], {"clicks": 7, "impressions": 200, "position": 5.0}, 0),
             "page": page_blob([[HOME, 6, 150, 4.0], ["https://www.example.com/x", 1, 50, 8.0]],
                               None, 1)},
        # D4 missing; D5 stored.
        D5: {"total": sd.fold([], {"clicks": 2, "impressions": 40, "position": 7.0}, 0),
             "page": page_blob([[PRICING, 2, 40, 7.0]])},
    }
    finals = {D1: True, D2: True, D3: True, D5: False}
    with History(FX.box.db) as h:
        sd.write(h.db, SITE, "google", days, finals, "sc-domain:example.com", NOW)
        ask = lambda url, verdict, cov, when: inspect.row_of(  # noqa: E731
            SITE, url, "sc-domain:example.com",
            {"inspectionResult": {"indexStatusResult": {
                "verdict": verdict, "coverageState": cov, "lastCrawlTime": "2026-10-04T01:02:03Z",
                "googleCanonical": url, "userCanonical": url}}}, when)
        inspect.write(h.db, [ask(PRICING, "NEUTRAL", "Crawled - currently not indexed", NOW),
                             ask(PRICING, "PASS", "Submitted and indexed",
                                 NOW + timedelta(days=1)),
                             ask(HOME, "NEUTRAL", "Discovered - currently not indexed", NOW)],
                      NOW + timedelta(days=1))
    state.update(FX.box.db.parent, SITE, "google", ok=True, source="sc-domain:example.com",
                 last_sync="2026-10-06T15:00:00+00:00", last_ok="2026-10-06T15:00:00+00:00")


def tearDownModule():
    FX.close()


def call(name, **args):
    got = protocol.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                           "params": {"name": name, "arguments": args}},
                          FX.context(default_site=SITE))
    return got["result"]


class SearchPerformance(unittest.TestCase):
    def ok(self, **args):
        r = call("search_performance", **args)
        self.assertIs(r["isError"], False, r["content"][0]["text"])
        return r["structuredContent"], r["content"][0]["text"]

    def test_the_whole_site(self):
        s, text = self.ok(**{"from": "2026-10-01", "to": "2026-10-05"})
        self.assertEqual(s["missing_days"], ["2026-10-04"])
        self.assertEqual(s["provisional_days"], ["2026-10-05"])
        self.assertEqual([d["clicks"] for d in s["days"]], [9, 4, 7, 2])
        self.assertEqual(s["totals"]["clicks"], 22)
        self.assertEqual(s["totals"]["impressions"], 630)
        top = {p["path"]: p for p in s["top_pages"]}
        self.assertEqual(top["/pricing/"]["clicks"], 6)            # 3 + 1 + 2
        self.assertEqual(top["/pricing/"]["impressions"], 140)
        self.assertEqual(s["state"], "answering")
        self.assertEqual(s["index"]["by_status"], {"indexed": 1, "discovered_not_indexed": 1})
        self.assertIn("not Skald's", text)
        self.assertIn("Not stored: 2026-10-04", text)

    def test_one_page(self):
        s, text = self.ok(path="/pricing/", **{"from": "2026-10-01", "to": "2026-10-05"})
        days = {d["day"]: d for d in s["days"]}
        self.assertEqual((days["2026-10-01"]["clicks"], days["2026-10-01"]["impressions"]),
                         (4, 100))
        self.assertEqual(days["2026-10-01"]["position"], 6.0)      # (80x5 + 20x10) / 100
        self.assertEqual(days["2026-10-02"]["clicks"], 0)          # complete table: 0
        self.assertIsNone(days["2026-10-03"]["clicks"])            # not complete: unknown
        self.assertEqual(s["not_in_page_table"], ["2026-10-03"])
        self.assertTrue(s["totals_partial"])
        self.assertEqual(s["totals"]["clicks"], 6)
        self.assertEqual([q["query"] for q in s["top_queries"]], ["log analytics", "skald price"])
        self.assertEqual([(c["country"], c["clicks"], c["impressions"]) for c in s["countries"]],
                         [("usa", 4, 80), ("deu", 0, 10)])
        self.assertEqual(s["countries_not_stored"], ["2026-10-02", "2026-10-03", "2026-10-05"])
        self.assertEqual(s["index"]["status"], "indexed")
        self.assertEqual(s["index"]["before"]["status"], "crawled_not_indexed")
        self.assertIs(s["index"]["canonical_match"], True)
        self.assertIn("Not known", text)

    def test_a_page_never_inspected_says_so(self):
        s, text = self.ok(path="/nowhere/", **{"from": "2026-10-01", "to": "2026-10-02"})
        self.assertIsNone(s["index"])
        self.assertIn("has not been inspected yet", text)

    def test_refusals(self):
        for args in ({"path": "pricing"}, {"from": "2026-10-05", "to": "2026-10-01"},
                     {"from": "2026-01-01", "to": "2026-10-01"}):
            self.assertIs(call("search_performance", **args)["isError"], True, args)

    def test_bing_not_connected(self):
        s, text = self.ok(engine="bing")
        self.assertEqual(s["state"], "not connected")
        self.assertIn("connect it", text)


class YourTools(unittest.TestCase):
    def test_search_console_is_listed_with_its_state(self):
        r = call("your_tools")
        self.assertIs(r["isError"], False)
        got = {e["engine"]: e for e in r["structuredContent"]["search"]}
        self.assertEqual(got["google"]["state"], "answering")
        self.assertIn("Search Console: answering", r["content"][0]["text"])


class Audit(unittest.TestCase):
    def test_the_second_count_agrees(self):
        with History(FX.box.db) as h:
            problems, checked = audit_search_pages.check(h.db, SITE)
        self.assertEqual(problems, [])
        self.assertGreater(checked, 0)

    def test_the_second_count_finds_a_wrong_figure(self):
        from unittest import mock
        from skald.mcp import tools_search
        real = tools_search.figures

        def wrong(*a, **k):
            got = real(*a, **k)
            if got["days"] and got["days"][0]["clicks"] is not None:
                got["days"][0]["clicks"] += 1
            return got
        with History(FX.box.db) as h, mock.patch.object(tools_search, "figures", wrong):
            problems, _ = audit_search_pages.check(h.db, SITE)
        self.assertTrue(problems)


if __name__ == "__main__":
    unittest.main()
