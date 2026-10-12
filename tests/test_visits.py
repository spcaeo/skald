"""Visits: anonymous journeys, their metrics, and our own traffic by label.

What is pinned: a visit is the readers' session, so visits equal readers and
their pages add up to the pages read; an in-app move is seen from the next
request's referrer and shown, never counted as a page; verify withholds
figures that do not add up; no address, user agent or visitor key is ever
stored, shown or exported; journeys are deleted after report.journey_days
while totals stay; the dashboard, export and mail carry the right pieces;
and our own traffic is listed by label, never by address.
"""
from __future__ import annotations

import json
import sqlite3
import sys
import unittest
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald import Classifier, check, mailer  # noqa: E402
from skald.classify import Group  # noqa: E402
from skald.config import ours_rules, tiny_yaml  # noqa: E402
from skald.store import History  # noqa: E402
from skald.visits import duration_words, seconds_bucket, sentence  # noqa: E402

from support import CHROME, SECRETS, UTC, Sandbox, day_lines, line, totals_for  # noqa: E402

IPHONE = ("Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) AppleWebKit/605.1.15 "
          "(KHTML, like Gecko) Version/26.0 Mobile/15E148 Safari/604.1")
DAY = date(2026, 10, 5)
T = datetime(2026, 10, 5, 15, tzinfo=UTC)
OFFICE = "192.0.2.77"


def journey_day() -> list[str]:
    """Three readers: one from ChatGPT on an iPhone who loads two pages and
    moves in-app once, one from Google who meets a 404, and one who reads a
    page, goes quiet for two hours and comes back (two visits)."""
    site = "https://example.com"
    return [
        line(T, "203.0.113.50", "/compare/x/", IPHONE, "https://chatgpt.com/", country="CA"),
        line(T + timedelta(seconds=2), "203.0.113.50", "/_next/static/a.js", IPHONE,
             f"{site}/compare/x/", country="CA"),
        line(T + timedelta(seconds=40), "203.0.113.50", "/pricing/?_rsc=1", IPHONE,
             f"{site}/features/", country="CA"),
        line(T + timedelta(seconds=100), "203.0.113.50", "/pricing/", IPHONE,
             f"{site}/features/", country="CA"),
        line(T + timedelta(minutes=5), "203.0.113.60", "/", CHROME,
             "https://www.google.com/", country="US"),
        line(T + timedelta(minutes=6), "203.0.113.60", "/nope", CHROME,
             f"{site}/", status=404, country="US"),
        line(T + timedelta(minutes=7), "203.0.113.70", "/guides/alpha", CHROME, country="GB"),
        line(T + timedelta(hours=2), "203.0.113.70", "/guides/beta", CHROME, country="GB"),
        # A cancelled request names the page the visitor just left: no move.
        line(T + timedelta(hours=2, seconds=1), "203.0.113.70", "/x.png", CHROME,
             f"{site}/guides/alpha", status=499, country="GB"),
    ]


class TestJourneys(unittest.TestCase):

    def setUp(self):
        self.totals = totals_for(day_lines(DAY, 3) + journey_day())
        self.people = self.totals.groups[Group.PEOPLE]
        self.stats = self.totals.visits

    def test_visits_are_the_readers_and_pages_add_up(self):
        self.assertEqual(check(self.totals), [])
        self.assertEqual(self.stats.visits, self.people.readers)
        self.assertEqual(self.stats.visits, 3 + 4)
        self.assertEqual(self.stats.views(), self.people.views)
        self.assertEqual(sum(j["pages"] for j in self.totals.journeys), self.people.views)
        self.assertEqual(len(self.totals.journeys), self.stats.visits)

    def test_a_journey_reads_as_one_line(self):
        chat = next(j for j in self.totals.journeys if j["landing"] == "/compare/x/")
        self.assertEqual([p for p, _ in chat["trail"]],
                         ["/compare/x/", "/features/", "/pricing/"])
        self.assertEqual([h for _, h in chat["trail"]], ["page", "app", "page"])
        self.assertEqual((chat["pages"], chat["seen"], chat["in_app"], chat["seconds"]),
                         (2, 3, 1, 100))
        self.assertEqual(sentence(chat),
                         "15:00 · \U0001F1E8\U0001F1E6 Canada · Mobile, Safari on iOS · from "
                         "ChatGPT → /compare/x/ → /features/ (in-app) → /pricing/ · "
                         "2 pages · 1m 40s")

    def test_flags_and_lists(self):
        self.assertEqual(self.stats.flags, Counter({"not_found": 1, "in_app": 1}))
        self.assertEqual(self.stats.steps["/compare/x/ → /features/"], 1)
        self.assertEqual(sum(self.stats.steps.values()), self.stats.seen() - self.stats.visits)
        self.assertEqual(self.stats.exits["/pricing/"], 1)
        # A cancelled request is no move: the second visit stays one page.
        beta = next(j for j in self.totals.journeys if j["landing"] == "/guides/beta")
        self.assertEqual(beta["seen"], 1)

    def test_a_long_gap_makes_two_visits(self):
        landings = [j["landing"] for j in self.totals.journeys]
        self.assertIn("/guides/alpha", landings)
        self.assertIn("/guides/beta", landings)

    def test_visit_labels_equal_the_readers_breakdowns(self):
        for mine, theirs in (("entries", "landing"), ("source", "source"),
                             ("country", "country"), ("device", "device")):
            self.assertEqual(Counter(getattr(self.stats, mine)),
                             Counter(self.people.by[theirs]))

    def test_nothing_identifying_is_in_a_journey(self):
        text = json.dumps(self.totals.journeys)
        for secret in ("203.0.113.", "Mozilla", "AppleWebKit", "https://", "Version/26"):
            self.assertNotIn(secret, text)
        keys = set().union(*(j.keys() for j in self.totals.journeys))
        self.assertFalse(keys & {"address", "user_agent", "key", "hash", "referrer"})
        self.assertTrue(all(len(j["start"]) == 16 for j in self.totals.journeys))

    def test_verify_withholds_visits_that_do_not_add_up(self):
        self.stats.pages["1"] += 1
        whats = [p.what for p in check(self.totals)]
        self.assertTrue(any("visits" in w for w in whats), whats)
        self.stats.pages["1"] -= 1
        self.totals.journeys.pop()
        self.assertIn("journeys does not sum", [p.what for p in check(self.totals)])

    def test_median_and_buckets(self):
        self.assertEqual([seconds_bucket(s) for s in (0, 59, 61, 599, 601, 3599, 3700)],
                         [0, 59, 60, 590, 600, 3540, 3600])
        self.assertEqual(duration_words(100), "1m 40s")
        self.assertEqual(duration_words(3900), "1h 5m")


class TestOursLabels(unittest.TestCase):

    def test_old_and_labelled_forms_both_work(self):
        old = Classifier(["Crawl"], None, [OFFICE])
        new = Classifier([{"agent": "Crawl", "label": "Our crawler"}], None,
                         [{"ip": OFFICE, "label": "Office Mac"}])
        from skald.parse import Hit
        hit = Hit(T, OFFICE, "example.com", "GET", "/", "200", "", CHROME)
        self.assertEqual((old(hit).group, old(hit).engine), (Group.OURS, "Listed address 1"))
        self.assertEqual(new(hit).engine, "Office Mac")
        bot = Hit(T, "203.0.113.9", "example.com", "GET", "/", "200", "", "Crawl/1")
        self.assertEqual(new(bot).engine, "Our crawler")
        self.assertEqual(old(bot).engine, "Crawl")

    def test_the_small_parser_reads_labelled_entries(self):
        text = ("ours:\n  user_agents:\n    - LibreCrawl\n"
                "    - {agent: skald-heartbeat, label: heartbeat}\n"
                f'  addresses: [{{ip: {OFFICE}, label: "Office Mac (Morgan)"}}]\n')
        config = tiny_yaml(text)
        self.assertEqual(config["ours"]["addresses"], [{"ip": OFFICE, "label": "Office Mac (Morgan)"}])
        rules = ours_rules(config)
        self.assertEqual([r["label"] for r in rules], ["LibreCrawl", "heartbeat", "Office Mac (Morgan)"])
        self.assertNotIn(OFFICE, json.dumps(rules))

    def test_requests_by_label_add_up_to_ours(self):
        totals = totals_for([line(T, "203.0.113.9", "/", "MyCompanyCrawler/1")] * 3)
        self.assertEqual(totals.ours_labels, Counter({"MyCompanyCrawler": 3}))
        totals.ours_labels["MyCompanyCrawler"] += 1
        self.assertIn("our own traffic by label does not sum", [p.what for p in check(totals)])


class TestSystem(unittest.TestCase):

    def setUp(self):
        self.box = Sandbox(views=["{name: Guides, path_prefix: /guides/}"])
        text = self.box.config.read_text().replace(
            "ours:\n  user_agents: [MyCompanyCrawler]\n",
            "ours:\n  user_agents: [MyCompanyCrawler]\n  addresses:\n"
            f'    - {{ip: {OFFICE}, label: "Office Mac (Morgan)"}}\n')
        self.box.config.write_text(text.replace("report:\n", "report:\n  journey_days: 2\n"))
        office = [line(T + timedelta(minutes=30), OFFICE, "/", CHROME, country="CA")]
        self.box.log(day_lines(DAY, 2) + journey_day() + office)

    def tearDown(self):
        self.box.close()

    def test_collect_stores_metrics_and_journeys_and_nothing_identifying(self):
        code, out, err = self.box.run("--today", "2026-10-06", "collect", "--day", "2026-10-05")
        self.assertEqual(code, 0, err)
        with History(self.box.db) as h:
            period = h.period("example.com", DAY, DAY)
            self.assertEqual(period.totals.visits.visits, 2 + 4)
            self.assertEqual(period.totals.ours_labels, Counter({"Office Mac (Morgan)": 1}))
            self.assertEqual(check(period.totals), [])
            self.assertEqual(len(h.journeys("example.com", DAY, DAY)), 6)
            # The view's own visits: one standard reader, and alpha and beta.
            self.assertEqual(len(h.journeys("example.com::guides", DAY, DAY)), 3)
            dump = "\n".join(h.db.iterdump())
        for secret in ("203.0.113.", OFFICE, "Mozilla", "AppleWebKit", "https://"):
            self.assertNotIn(secret, dump)

    def test_journeys_expire_but_totals_stay(self):
        self.box.run("--today", "2026-10-06", "collect", "--day", "2026-10-05")
        # Two days later, with journey_days 2, the 5th is past keeping.
        self.box.run("--today", "2026-10-08", "collect", "--day", "2026-10-07")
        with History(self.box.db) as h:
            self.assertEqual(h.journeys("example.com", DAY, DAY), [])
            self.assertEqual(h.period("example.com", DAY, DAY).totals.visits.visits, 6)

    def test_live_dashboard_export_and_mail(self):
        today = "2026-10-05"
        with mock.patch("skald.cli._now",
                        return_value=datetime(2026, 10, 5, 20, tzinfo=UTC)):
            code, out, err = self.box.run("live")
        self.assertEqual(code, 0, err)
        page = (self.box.root / "www" / "example.com" / "index.html").read_text()
        for words in ("Visits today", "Pages, in order", "Entry pages (today",
                      "Exit pages (today", "Top 2-step paths (today", "Median visit length",
                      "Our own traffic (today)", "Office Mac (Morgan)", "(in-app)",
                      'href="exports/today-journeys.csv"', "from ChatGPT"):
            self.assertIn(words, page)
        self.assertNotIn(OFFICE, page)
        self.assertNotIn("203.0.113.", page)
        exports = self.box.root / "www" / "example.com" / "exports"
        csv = (exports / "today-journeys.csv").read_text()
        self.assertIn("/compare/x/ → /features/ (in-app) → /pricing/", csv)
        self.assertNotIn("203.0.113.", csv)
        guides = (self.box.root / "www" / "example.com" / "guides" / "index.html").read_text()
        self.assertIn("Visits today", guides)

        # History, the period page, export and mail, the next morning.
        code, out, err = self.box.run("--today", "2026-10-06", "collect", "--day", today)
        self.assertEqual(code, 0, err)
        self.assertEqual(self.box.run("--today", "2026-10-06", "dashboard")[0], 0)
        page = (self.box.root / "www" / "example.com" / "index.html").read_text()
        self.assertIn("Every anonymous journey kept (CSV)", page)
        code, out, err = self.box.run("--today", "2026-10-06", "export", "--table",
                                      "visits", "--total")
        self.assertEqual(code, 0, err)
        self.assertIn("visits,page_views,pages_per_visit", out)
        self.assertNotIn("_stats", out)
        code, out, err = self.box.run("--today", "2026-10-06", "export", "--table",
                                      "journeys", "--country", "CA")
        self.assertEqual(code, 0, err)
        self.assertEqual(len(out.strip().splitlines()), 1 + 1)
        code, _, err = self.box.run("--today", "2026-10-06", "export", "--table",
                                    "journeys", "--total")
        self.assertEqual(code, 2)
        with mock.patch.dict("os.environ", SECRETS):
            code, out, err = self.box.run("--today", "2026-10-06", "mail", "--daily",
                                          "--dry-run")
        self.assertEqual(code, 0, err)
        self.assertIn("VISITS", out)
        self.assertIn("Pages per visit", out)
        self.assertNotIn("(in-app)", out)            # metrics only, no journeys
        self.assertNotIn("15:00 ·", out)

    def test_an_older_history_day_has_no_visits_and_says_so(self):
        self.box.run("--today", "2026-10-06", "collect", "--day", "2026-10-05")
        db = sqlite3.connect(self.box.db)
        db.execute("UPDATE days SET journeys = NULL")
        db.commit()
        db.close()
        with History(self.box.db) as h:
            period = h.period("example.com", DAY, DAY)
        self.assertIsNone(period.totals.visits)
        self.assertEqual(period.unmeasured_visits, 1)
        self.assertEqual(check(period.totals), [])


if __name__ == "__main__":
    unittest.main()
