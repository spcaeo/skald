"""Skald's side of the Search cross-check: people from search engines by
engine and landing page (day kind `search_landing`, search_landing.py), its
second count (audit_search_landing.py) catching a planted error, and
search.json (search/data.py) putting Search Console's clicks beside it."""
from __future__ import annotations

import json
import sqlite3
import sys
import unittest
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from support import Sandbox, line, totals_for  # noqa: E402

from skald import audit_more, audit_search_landing, day_more, extras  # noqa: E402
from skald.data_files import Page  # noqa: E402
from skald.search import data, days  # noqa: E402
from skald.store import History  # noqa: E402

NOON = datetime(2026, 10, 5, 12, tzinfo=timezone.utc)
DAY, TODAY = date(2026, 10, 5), "2026-10-06"
VISITS = [
    ("/", "https://www.google.com/"),
    ("/guides/alpha", "https://www.google.co.uk/"),
    ("/", "https://www.google.de/"),
    ("/guides/alpha", "https://www.bing.com/"),
    ("/?gclid=abc123", "https://www.google.com/"),          # an ad click: Paid
    ("/", "https://duckduckgo.com/"),                        # another engine
    ("/", "android-app://com.google.android.googlequicksearchbox/"),
    ("/", "https://mail.google.com/"),                       # webmail: not a search
    ("/pricing", "-"),                                       # direct
]


def lines() -> list[str]:
    return [line(NOON + timedelta(minutes=i), f"203.0.113.{20 + i}", path, referrer=ref)
            for i, (path, ref) in enumerate(VISITS)]


class Kind(unittest.TestCase):
    def test_registered(self):
        self.assertIn("search_landing", day_more.modules())
        self.assertIn("search_landing", audit_more._modules(audit_more.RECOUNTS))
        self.assertIn("search", audit_more._modules(audit_more.DAILY))

    def test_by_engine_and_page(self):
        totals = totals_for(lines())
        blob = totals.extras["search_landing"]
        self.assertEqual(blob["engines"], {"Google": 4, "Bing": 1, "Other": 1, "Paid": 1})
        self.assertEqual(blob["visits"], 7)
        self.assertEqual(blob["pages"]["Google"], {"/": 3, "/guides/alpha": 1})
        self.assertEqual(blob["pages"]["Bing"], {"/guides/alpha": 1})
        self.assertEqual(extras.check(totals), [])

    def test_check_catches_pages_that_do_not_add_up(self):
        totals = totals_for(lines())
        totals.extras["search_landing"]["pages"]["Google"]["/x"] = 1
        self.assertIn("search_landing: Google by landing page does not sum",
                      [p.what for p in extras.check(totals)])

    def test_the_recount_reads_the_raw_line(self):
        from skald.audit import line_hit
        r = audit_search_landing.Recount({}, DAY, timezone.utc, {"example.com"})
        for i, raw in enumerate(lines()):
            got = line_hit(raw)
            source = "Search engine" if i < 7 else "x"      # the audit's own label, given
            r.visit([got], lambda _l: True, {"landing": got.path[:70], "source": source})
        self.assertEqual(r.names, Counter({"Google": 4, "Bing": 1, "Other": 1, "Paid": 1}))

    def test_audit_matches_and_catches_a_planted_error(self):
        box = Sandbox()
        try:
            box.log(lines())
            self.assertEqual(box.run("--today", TODAY, "collect")[0], 0)
            code, _, err = box.run("--today", TODAY, "audit")
            self.assertEqual(code, 0, err)
            db = sqlite3.connect(str(box.db))
            with db:
                got = json.loads(db.execute("SELECT data FROM day_extras WHERE "
                                            "kind = 'search_landing'").fetchone()[0])
                got["engines"]["Bing"] = 2
                db.execute("UPDATE day_extras SET data = ? WHERE kind = 'search_landing'",
                           (json.dumps(got),))
            db.close()
            code, _, err = box.run("--today", TODAY, "audit")
            self.assertEqual(code, 1)
            self.assertIn("search_landing: Bing: history has 2, the recount finds 1", err)
        finally:
            box.close()


class SearchJson(unittest.TestCase):
    """search.json from a collected day and a synced Search Console day."""

    def setUp(self):
        self.box = Sandbox()
        self.addCleanup(self.box.close)
        self.box.log(lines())
        self.assertEqual(self.box.run("--today", TODAY, "collect")[0], 0)
        with History(self.box.db) as h:
            for d, final in ((DAY, True), (DAY + timedelta(days=1), False)):
                total = {"clicks": 5, "impressions": 80, "position": 4.2}
                page = days.fold([["https://www.example.com/", 3, 50, 3.0],
                                  ["https://example.com/guides/alpha", 2, 30, 6.0]], total, 300)
                query = days.fold([["skald", 4, 60, 2.0]], total, 500)
                days.write(h.db, "example.com", "google", {d: {
                    "total": days.fold([["(all)", 5, 80, 4.2]], total, 1),
                    "page": page, "query": query}},
                    {d: final}, "sc-domain:example.com")

    def build(self, config=None):
        config = config or {"search_console": {"property": "sc-domain:example.com"},
                            "site": {"hosts": ["example.com"]}}
        with History(self.box.db) as h:
            p = Page(h, "example.com", "example.com", None, ZoneInfo("UTC"),
                     datetime(2026, 10, 6, 9, tzinfo=timezone.utc), None, config)
            return data.build(p)

    def test_engines_and_periods(self):
        got = self.build()
        g = got["engines"]["google"]
        self.assertEqual(g["connected"], "sc-domain:example.com")
        self.assertEqual(g["summary"]["days"], 2)
        self.assertEqual(g["summary"]["provisional"], 1)
        self.assertEqual([d["final"] for d in g["days"]], [True, False])
        week = g["periods"]["7"]
        self.assertEqual(week["totals"]["clicks"], 10)
        self.assertEqual(week["totals"]["ctr"], round(10 / 160, 4))
        self.assertEqual(week["provisional_days"], ["2026-10-06"])
        self.assertEqual(week["query"]["rows"][0][:3], ["skald", 8, 120])
        self.assertEqual(week["query"]["unattributed"], {"clicks": 2, "impressions": 40})
        self.assertIsNone(got["engines"]["bing"]["connected"])
        self.assertEqual(got["engines"]["bing"]["days"], [])

    def test_crosscheck_side_by_side(self):
        cross = self.build()["crosscheck"]
        self.assertEqual(cross["days"], [{"day": "2026-10-05", "search_console_clicks": 5,
                                          "skald_visits": 4, "difference": -1, "ratio": 0.8}])
        pages = {r["path"]: r for r in cross["pages"]}
        self.assertEqual(pages["/"]["search_console_clicks"], 3)
        self.assertEqual(pages["/"]["skald_visits"], 3)
        self.assertEqual(pages["/guides/alpha"]["skald_visits"], 1)
        self.assertTrue(any("A person who clicks twice" in n for n in cross["notes"]))
        self.assertTrue(any("Pacific Time" in n for n in cross["notes"]))

    def test_not_connected(self):
        got = self.build({"site": {"hosts": ["example.com"]}})
        self.assertIsNone(got["engines"]["google"]["connected"])


if __name__ == "__main__":
    unittest.main()
