"""A page from a new outside source starts a new visit, inside the gap too.

The bug it pins (docomatic.ai): a reader opened the site directly, came back
from perplexity.ai two minutes later, and was one "Direct or unknown" visit,
so the citation tracker said perplexity.ai 1 while the sources, the visits
list and the assistant drill-down said 0. The rule now (SOP.md, "What a
visit is"): inside an open visit, a page view whose source is outside the
site - an assistant, another website, a search engine, social, email, a
tagged link - and differs from the visit's own starts a new visit. A page
from the site itself, a page with no referrer and no tag, and an asset or
payload never do. The audit's own split (audit.py) agrees.
"""
from __future__ import annotations

import sqlite3
import sys
import unittest
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald import check  # noqa: E402
from skald.classify import Group  # noqa: E402

from support import CHROME, UTC, Sandbox, day_lines, line, totals_for  # noqa: E402

DAY = date(2026, 10, 5)
TODAY = "2026-10-06"
T = datetime(2026, 10, 5, 14, 16, tzinfo=UTC)
SITE = "https://example.com"
WHO = "203.0.113.80"


def at(minutes: float, path: str, referrer: str = "-") -> str:
    return line(T + timedelta(minutes=minutes), WHO, path, CHROME, referrer, country="CA")


def direct_then_perplexity() -> list[str]:
    """Direct at 14:16, its stylesheet, then back from perplexity.ai at 14:18."""
    return [at(0, "/"), at(0.01, "/_next/static/a.css", f"{SITE}/"),
            at(2, "/pricing", "https://www.perplexity.ai/"),
            at(2.01, "/_next/static/b.js", f"{SITE}/pricing")]


class TestTheRule(unittest.TestCase):

    def visits(self, lines: list[str]):
        totals = totals_for(lines)
        self.assertEqual(check(totals), [])
        people = totals.groups[Group.PEOPLE]
        self.assertEqual(totals.visits.visits, people.readers)
        return totals, people

    def test_direct_then_an_assistant_inside_the_gap_is_two_visits(self):
        totals, people = self.visits(direct_then_perplexity())
        self.assertEqual((people.visits, people.readers), (2, 2))
        first, second = totals.journeys
        self.assertEqual((first["source"], first["landing"]), ("Direct or unknown", "/"))
        self.assertEqual((second["source"], second["via"], second["landing"]),
                         ("AI assistant", "Perplexity", "/pricing"))
        self.assertEqual(people.by["source"],
                         Counter({"Direct or unknown": 1, "AI assistant": 1}))
        # The citation tracker and the visits now say the same.
        self.assertEqual(dict(people.cited_by), {"perplexity.ai": 1})
        cube = totals.extras["visit_cube"]["rows"]
        self.assertEqual(sum(r[-1] for r in cube if r[2] == "AI assistant"
                             and r[3] == "perplexity.ai"), 1)

    def test_same_site_navigation_does_not_split(self):
        totals, people = self.visits([
            at(0, "/", "https://www.google.com/"), at(1, "/pricing", f"{SITE}/"),
            at(2, "/contact", f"{SITE}/pricing")])
        self.assertEqual((people.visits, people.readers), (1, 1))
        self.assertEqual(totals.journeys[0]["pages"], 3)
        self.assertEqual(totals.journeys[0]["source"], "Search engine")

    def test_a_page_with_no_referrer_mid_visit_does_not_split(self):
        totals, people = self.visits([
            at(0, "/", "https://chatgpt.com/"), at(3, "/pricing")])
        self.assertEqual((people.visits, people.readers), (1, 1))
        self.assertEqual(totals.journeys[0]["source"], "AI assistant")

    def test_the_same_outside_source_again_does_not_split(self):
        totals, people = self.visits([
            at(0, "/", "https://www.perplexity.ai/"), at(1, "/pricing", f"{SITE}/"),
            at(4, "/guides/alpha", "https://www.perplexity.ai/")])
        self.assertEqual((people.visits, people.readers), (1, 1))
        self.assertEqual(totals.journeys[0]["pages"], 3)

    def test_an_asset_or_payload_from_outside_does_not_split(self):
        totals, people = self.visits([
            at(0, "/"), at(1, "/pricing?_rsc=1", "https://www.perplexity.ai/"),
            at(1.01, "/og/card.png", "https://news.example.org/")])
        self.assertEqual((people.visits, people.readers), (1, 1))

    def test_a_tagged_link_and_another_website_each_start_one(self):
        totals, people = self.visits([
            at(0, "/"), at(2, "/?utm_source=newsletter&utm_medium=email"),
            at(4, "/guides/alpha", "https://news.example.org/post"),
            at(5, "/guides/beta", f"{SITE}/guides/alpha")])
        self.assertEqual((people.visits, people.readers), (3, 3))
        self.assertEqual([j["source"] for j in totals.journeys],
                         ["Direct or unknown", "Email", "Other website"])
        self.assertEqual(totals.journeys[-1]["pages"], 2)

    def test_the_requests_feed_labels_rows_by_the_split_visit(self):
        from skald.parse import read
        from skald.requests_feed import Feed
        from skald.classify import Classifier
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "access.log"
            path.write_text("".join(direct_then_perplexity()))
            hits = list(read([path]))
        feed = Feed(T - timedelta(hours=1), 100, own_hosts=["example.com"])
        classifier = Classifier([])
        for hit in hits:
            feed(hit, classifier(hit))
        sources = [visit["source"] for _, _, _, visit, *_ in feed.rows]
        self.assertEqual(sources, ["Direct or unknown"] * 2 + ["AI assistant"] * 2)


class TestTheAuditAgrees(unittest.TestCase):

    def setUp(self):
        self.box = Sandbox()

    def tearDown(self):
        self.box.close()

    def test_a_day_with_source_splits_recounts_exactly(self):
        later = [line(l_when, "203.0.113.81", path, CHROME, ref, country="US")
                 for l_when, path, ref in (
                     (T + timedelta(hours=1), "/", "https://www.google.com/"),
                     (T + timedelta(hours=1, minutes=1), "/pricing", f"{SITE}/"),
                     (T + timedelta(hours=1, minutes=3), "/?utm_source=chatgpt.com", "-"),
                     (T + timedelta(hours=1, minutes=4), "/guides/alpha", "-"))]
        self.box.log(day_lines(DAY, 3) + direct_then_perplexity() + later)
        code, out, err = self.box.run("--today", TODAY, "collect")
        self.assertEqual(code, 0, err)
        code, out, err = self.box.run("--today", TODAY, "audit")
        self.assertEqual(code, 0, err + out)
        self.assertIn("all match", out)
        db = sqlite3.connect(str(self.box.db))
        try:
            got = dict(db.execute(
                "SELECT name, n FROM counts WHERE site = 'example.com' AND day = ? AND "
                "kind = 'reader_source'", (DAY.isoformat(),)).fetchall())
        finally:
            db.close()
        # 3 standard readers (one from chatgpt.com) + 2 + 2 split visits.
        self.assertEqual(sum(got.values()), 7)
        self.assertEqual(got.get("AI assistant"), 3)


if __name__ == "__main__":
    unittest.main()
