"""Phase 4, lane B: engagement and new/returning visitors by source and device.

What is pinned:
- engagement.py (day kind `engagement`): per source type and per device,
  visits, pages loaded, one-page visits and visits by length bucket, from
  the day's people visits; its sums are checked, a planted error is caught,
  and a day with no people at all still works;
- audit_engagement.py: the audit counts the same rows again from the raw
  lines with its own labels and buckets, and a tampered stored row fails
  the audit (and the live audit);
- visitors.annotate: returning visitors also by THIS visit's source
  (`by_source`), the old `first_touch` kept, a "warming up" flag for the
  first 30 days of hashes, nothing without the key; the audit recounts
  `by_source` against visitor_days;
- visits.json: `engagement` and `returning_by_source` per day and today,
  null when not recorded, and no address or key in them.
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald import engagement, extras, visitors  # noqa: E402
from skald.store import History  # noqa: E402

from support import CHROME, GPTBOT, Sandbox, line, totals_for  # noqa: E402

UTC = timezone.utc
DAY = date(2026, 10, 5)
TODAY = "2026-10-06"
IPHONE = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
          "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")
KEY = {"SKALD_VISITOR_KEY": "test-key-not-secret"}


def at(day: date, hour: int, minute: int = 0, second: int = 0) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, second, tzinfo=UTC)


def four_visits(day: date, hour: int = 12) -> list[str]:
    """A: 3 pages over 100 s from ChatGPT (desktop); B: 1 page, mobile,
    direct; C: 2 pages over 45 s from Google (desktop); D: 1 page, direct."""
    noon = at(day, hour)
    s = timedelta(seconds=1)
    return [
        line(noon, "203.0.113.10", "/", referrer="https://chatgpt.com/"),
        line(noon + 40 * s, "203.0.113.10", "/pricing/"),
        line(noon + 100 * s, "203.0.113.10", "/guides/alpha"),
        line(noon + 200 * s, "203.0.113.11", "/", IPHONE),
        line(noon + 300 * s, "203.0.113.12", "/", referrer="https://www.google.com/"),
        line(noon + 345 * s, "203.0.113.12", "/guides/alpha"),
        line(noon + 400 * s, "203.0.113.13", "/"),
        line(noon + 3600 * s, "198.51.100.40", "/guides/alpha", GPTBOT),
    ]


def row(visits, views, one_page, seconds):
    return {"visits": visits, "views": views, "one_page": one_page, "seconds": seconds}


WANT = {
    "by_source": {"AI assistant": row(1, 3, 0, {"100": 1}),
                  "Direct or unknown": row(2, 2, 2, {"0": 2}),
                  "Search engine": row(1, 2, 0, {"45": 1})},
    "by_device": {"Desktop": row(3, 6, 1, {"100": 1, "45": 1, "0": 1}),
                  "Mobile": row(1, 1, 1, {"0": 1})},
}


class TestEngagementDay(unittest.TestCase):

    def test_rows_by_source_and_device(self):
        totals = totals_for(four_visits(DAY))
        self.assertEqual(totals.extras["engagement"], WANT)
        self.assertEqual(extras.check(totals), [])

    def test_a_row_that_does_not_add_up_is_caught(self):
        totals = totals_for(four_visits(DAY))
        totals.extras["engagement"]["by_device"]["Mobile"]["visits"] += 1
        what = [p.what for p in extras.check(totals)]
        self.assertIn("engagement by device: visits does not sum", what)

    def test_a_length_bucket_that_does_not_add_up_is_caught(self):
        totals = totals_for(four_visits(DAY))
        totals.extras["engagement"]["by_source"]["Search engine"]["seconds"] = {"50": 1}
        self.assertTrue(extras.check(totals))

    def test_a_day_with_no_people(self):
        totals = totals_for([line(at(DAY, 12), "198.51.100.40", "/", GPTBOT)])
        self.assertEqual(totals.extras["engagement"], {"by_source": {}, "by_device": {}})
        self.assertEqual(extras.check(totals), [])

    def test_not_counted_without_journeys(self):
        self.assertIsNone(engagement.finish(None, SimpleNamespace(), None, {}, {}))


class TestEngagementAudit(unittest.TestCase):

    def setUp(self):
        self.box = Sandbox()
        self.box.log(four_visits(DAY, 9))      # before --today's noon (the live test)

    def tearDown(self):
        self.box.close()

    def test_the_recount_matches_and_a_planted_error_is_caught(self):
        self.assertEqual(self.box.run("--today", TODAY, "collect")[0], 0)
        code, _, err = self.box.run("--today", TODAY, "audit")
        self.assertEqual(code, 0, err)
        with History(self.box.db) as h:
            got = h.extras("example.com", DAY, DAY)[DAY.isoformat()]["engagement"]
        self.assertEqual(got, WANT)
        got["by_source"]["Search engine"]["views"] = 3
        db = sqlite3.connect(str(self.box.db))
        with db:
            db.execute("UPDATE day_extras SET data = ? WHERE kind = 'engagement'",
                       (json.dumps(got),))
        db.close()
        code, _, err = self.box.run("--today", TODAY, "audit")
        self.assertEqual(code, 1)
        self.assertIn("engagement by source: Search engine: pages loaded: history has 3, "
                      "the recount finds 2", err)

    def test_the_live_audit_compares_it_too(self):
        stamp = at(DAY, 23).timestamp()
        os.utime(self.box.root / "logs" / "access.log", (stamp, stamp))
        self.assertEqual(self.box.run("--today", DAY.isoformat(), "live")[0], 0)
        code, _, err = self.box.run("--today", DAY.isoformat(), "audit", "--live")
        self.assertEqual(code, 0, err)
        snap = self.box.root / "live-example.com.json"
        got = json.loads(snap.read_text())
        self.assertEqual(got["extras"]["engagement"], WANT)
        got["extras"]["engagement"]["by_device"]["Mobile"]["one_page"] = 0
        snap.write_text(json.dumps(got))
        code, _, err = self.box.run("--today", DAY.isoformat(), "audit", "--live")
        self.assertEqual(code, 1)
        self.assertIn("engagement by device: Mobile: one-page visits", err)


class TestReturningBySource(unittest.TestCase):
    """d1: A direct. d2: A again and B, both direct. d3: A from ChatGPT."""

    def setUp(self):
        self.box = Sandbox()
        self.d1, self.d2, self.d3 = date(2026, 10, 4), date(2026, 10, 5), date(2026, 10, 6)
        self.box.log([
            line(at(self.d1, 9), "203.0.113.50", "/", CHROME),
            line(at(self.d2, 9), "203.0.113.50", "/pricing/", CHROME),
            line(at(self.d2, 9, 30), "203.0.113.60", "/", CHROME),
            line(at(self.d3, 8), "203.0.113.50", "/", CHROME, "https://chatgpt.com/"),
        ])

    def tearDown(self):
        self.box.close()

    def collect(self, day: date) -> None:
        code, _, err = self.box.run("--today", (day + timedelta(days=1)).isoformat(),
                                    "collect", "--day", day.isoformat())
        self.assertEqual(code, 0, err)

    def returning(self, day: date) -> dict:
        with History(self.box.db) as h:
            return h.extras("example.com", day, day)[day.isoformat()]["returning"]

    def test_by_this_visits_source_and_its_recount(self):
        with mock.patch.dict(os.environ, KEY):
            for d in (self.d1, self.d2, self.d3):
                self.collect(d)
            r2, r3 = self.returning(self.d2), self.returning(self.d3)
            self.assertEqual(r2["by_source"], {"Direct or unknown": {"readers": 2, "returning": 1}})
            # This visit came from ChatGPT; its first visit in 30 days was direct.
            self.assertEqual(r3["by_source"], {"AI assistant": {"readers": 1, "returning": 1}})
            self.assertEqual(r3["first_touch"], {"Direct or unknown": 1})
            self.assertTrue(r3["warming_up"])
            for d in (self.d2, self.d3):
                code, _, err = self.box.run("--today", "2026-10-07", "audit", "--day",
                                            d.isoformat())
                self.assertEqual(code, 0, err)
            r3["by_source"]["AI assistant"]["returning"] = 0
            db = sqlite3.connect(str(self.box.db))
            with db:
                db.execute("UPDATE day_extras SET data = ? WHERE kind = 'returning' AND day = ?",
                           (json.dumps(r3), self.d3.isoformat()))
            db.close()
            code, _, err = self.box.run("--today", "2026-10-07", "audit", "--day",
                                        self.d3.isoformat())
        self.assertEqual(code, 1)
        self.assertIn("returning by source: AI assistant: returning: history has 0, "
                      "the recount finds 1", err)

    def test_visits_json_carries_both_and_nothing_personal(self):
        with mock.patch.dict(os.environ, KEY):
            for d in (self.d1, self.d2, self.d3):
                self.collect(d)
            self.assertEqual(self.box.run("--today", "2026-10-07", "dashboard")[0], 0)
        text = (self.box.root / "www" / "example.com" / "data" / "visits.json").read_text()
        for secret in ("203.0.113.", "test-key-not-secret"):
            self.assertNotIn(secret, text)
        days = {d["day"]: d for d in json.loads(text)["days"]}
        self.assertEqual(days["2026-10-06"]["returning_by_source"],
                         {"by_source": {"AI assistant": {"readers": 1, "returning": 1}},
                          "warming_up": True})
        self.assertEqual(days["2026-10-06"]["engagement"]["by_source"],
                         {"AI assistant": row(1, 1, 1, {"0": 1})})
        self.assertNotIn("engagement", days["2026-10-03"])        # not collected

    def test_without_the_key_it_is_not_recorded(self):
        self.collect(self.d2)
        self.assertEqual(self.box.run("--today", "2026-10-07", "dashboard")[0], 0)
        text = (self.box.root / "www" / "example.com" / "data" / "visits.json").read_text()
        day = next(d for d in json.loads(text)["days"] if d["day"] == "2026-10-05")
        self.assertIsNone(day["returning_by_source"])
        self.assertEqual(day["engagement"]["by_device"]["Desktop"]["visits"], 2)


class TestIndependence(unittest.TestCase):

    def test_the_recount_imports_only_the_audits_own_code(self):
        import ast
        from skald import audit_engagement
        tree = ast.parse(Path(audit_engagement.__file__).read_text())
        mods = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.level}
        self.assertLessEqual(mods, {"audit_extras", "audit_visits"})


class TestWarmingUp(unittest.TestCase):

    def db(self, *days: date):
        db = sqlite3.connect(":memory:")
        db.executescript(visitors.SCHEMA)
        db.executemany("INSERT INTO visitor_days VALUES ('s', ?, 'v', 'reader', 1, '')",
                       [(d.isoformat(),) for d in days])
        return db

    def test_until_30_days_of_hashes_are_behind_the_day(self):
        self.assertTrue(visitors.warming_up(self.db(), "s", DAY))
        self.assertTrue(visitors.warming_up(self.db(DAY - timedelta(days=28), DAY), "s", DAY))
        self.assertFalse(visitors.warming_up(self.db(DAY - timedelta(days=29)), "s", DAY))

    def test_annotate_without_the_key_leaves_it_out(self):
        totals = SimpleNamespace(visitor_keys=None, journeys=[{"source": "Email"}],
                                 returning=None, extras=None)
        visitors.annotate(totals, self.db(), "s", DAY)
        self.assertIsNone(totals.returning)
        self.assertIsNone(totals.journeys[0]["returning"])


if __name__ == "__main__":
    unittest.main()
