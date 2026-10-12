"""Returning visitors (keyed hashes, 30 days), AI activity, and insights.

What is pinned: with the visitor key set, a reader seen on an earlier day
is "returning" and counted in the KPI; the hashes are pruned after 30 days;
no address or key reaches history; today's AI events carry the address
and repeat flags in their own private file only; the audit recounts the
hashes; without the key every repeat field is None; and an insight's
numbers are the sums of the stored figures it names, compared only between
whole periods.
"""
from __future__ import annotations

import json
import os
import sys
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald import insights  # noqa: E402
from skald.store import History  # noqa: E402

from support import ASKED, CHROME, GPTBOT, SECRETS, UTC, Sandbox, line  # noqa: E402

KEY = {"SKALD_VISITOR_KEY": "test-key-not-secret"}


def at(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=UTC)


class Returning(unittest.TestCase):

    def setUp(self):
        self.box = Sandbox()
        self.d1, self.d2, self.d3 = date(2026, 10, 4), date(2026, 10, 5), date(2026, 10, 6)
        self.box.log([
            line(at(self.d1, 9), "203.0.113.50", "/", CHROME),
            line(at(self.d1, 10), "198.51.100.40", "/guides/alpha", GPTBOT),
            line(at(self.d2, 9), "203.0.113.50", "/pricing/", CHROME),
            line(at(self.d2, 9, 30), "203.0.113.60", "/", CHROME),
            line(at(self.d3, 8), "203.0.113.50", "/", CHROME, "https://chatgpt.com/"),
            line(at(self.d3, 8, 5), "198.51.100.41", "/guides/beta", ASKED),
            line(at(self.d3, 8, 6), "198.51.100.40", "/guides/alpha", GPTBOT),
        ])

    def tearDown(self):
        self.box.close()

    def collect(self, day: date, today: date) -> None:
        code, _, err = self.box.run("--today", today.isoformat(), "collect", "--day",
                                    day.isoformat())
        self.assertEqual(code, 0, err)

    def test_returning_readers_and_repeat_ai(self):
        with mock.patch.dict(os.environ, KEY):
            self.collect(self.d1, self.d2)
            self.collect(self.d2, self.d3)
            code, out, err = self.box.run("--today", self.d3.isoformat(), "audit", "--day",
                                          self.d2.isoformat())
            self.assertEqual(code, 0, err)
            with mock.patch("skald.cli._now", return_value=at(self.d3, 12)):
                self.assertEqual(self.box.run("live")[0], 0)
                code, out, err = self.box.run("audit", "--live")
                self.assertEqual(code, 0, err)
        with History(self.box.db) as h:
            journeys = {j["landing"]: j for j in h.journeys("example.com", self.d2, self.d2)}
            self.assertEqual((journeys["/pricing/"]["returning"],
                              journeys["/pricing/"]["days_seen_30d"]), (True, 2))
            self.assertFalse(journeys["/"]["returning"])
            ret = h.extras("example.com", self.d2, self.d2)[self.d2.isoformat()]["returning"]
            self.assertEqual((ret["readers"], ret["returning"]), (2, 1))
            period = h.period("example.com", self.d2, self.d2)
            self.assertEqual(period.totals.returning, {"readers": 2, "returning": 1})
            dump = "\n".join(h.db.iterdump())
        for secret in ("203.0.113.", "198.51.100.", "test-key-not-secret"):
            self.assertNotIn(secret, dump)
        ai = json.loads((self.box.root / "live-example.com-ai.json").read_text())
        gpt = next(e for e in ai["events"] if e["name"] == "GPTBot")
        self.assertEqual((gpt["ip"], gpt["repeat"], gpt["times_seen_30d"], gpt["first_seen"]),
                         ("198.51.100.40", True, 2, "2026-10-04"))
        asked = next(e for e in ai["events"] if e["kind"] == "asked")
        self.assertFalse(asked["repeat"])
        referred = next(e for e in ai["events"] if e["kind"] == "referred")
        self.assertTrue(referred["repeat"])
        snap = (self.box.root / "live-example.com.json").read_text()
        self.assertNotIn("198.51.100.", snap)
        page = json.loads((self.box.root / "www" / "example.com" / "data" /
                           "ai_activity.json").read_text())
        self.assertEqual(page["today"]["events"][0]["ip"], "198.51.100.40")
        for name in ("overview", "visits", "campaigns", "live"):
            text = (self.box.root / "www" / "example.com" / "data" / f"{name}.json").read_text()
            self.assertNotIn("198.51.100.", text)
            self.assertNotIn("203.0.113.", text)

    def test_a_tampered_hash_count_fails_the_audit(self):
        with mock.patch.dict(os.environ, KEY):
            self.collect(self.d1, self.d2)
            with History(self.box.db) as h:
                h.db.execute("UPDATE visitor_days SET n = n + 1")
                h.db.commit()
            code, _, err = self.box.run("--today", self.d2.isoformat(), "audit", "--day",
                                        self.d1.isoformat())
        self.assertEqual(code, 1)
        self.assertIn("visitor hash", err)

    def test_hashes_are_pruned_after_30_days(self):
        with mock.patch.dict(os.environ, KEY):
            self.collect(self.d1, self.d2)
            self.collect(self.d2, self.d1 + timedelta(days=31))
        with History(self.box.db) as h:
            days = {d for (d,) in h.db.execute("SELECT DISTINCT day FROM visitor_days")}
        self.assertEqual(days, {self.d2.isoformat()})

    def test_without_the_key_nothing_is_hashed(self):
        self.collect(self.d1, self.d2)
        with History(self.box.db) as h:
            self.assertEqual(h.db.execute("SELECT COUNT(*) FROM visitor_days").fetchone()[0], 0)
            j = h.journeys("example.com", self.d1, self.d1)[0]
            self.assertIsNone(j["returning"])


class Insights(unittest.TestCase):

    def setUp(self):
        self.box = Sandbox()
        self.anchor = date(2026, 10, 5)
        lines = []
        for i in range(14):
            day = self.anchor - timedelta(days=i)
            readers = 6 if i < 7 else 2
            for r in range(readers):
                lines.append(line(at(day, 9, r), f"203.0.113.{r + 10}", "/a/", CHROME))
            lines.append(line(at(day, 10), "203.0.113.99", "/", CHROME,
                              "https://news.example.org/x" if i >= 7 else "-"))
        for r in range(3):
            lines.append(line(at(self.anchor, 11, r), f"203.0.113.{r + 40}", "/brand-new/", CHROME))
        self.box.log(sorted(lines))
        code, _, err = self.box.run("--today", "2026-10-06", "backfill", "--days", "14")
        self.assertEqual(code, 0, err)

    def tearDown(self):
        self.box.close()

    def test_numbers_are_the_stored_sums(self):
        with History(self.box.db) as h:
            found = insights.compute(h, "example.com", self.anchor, {})["insights"]
            rising = next(i for i in found if i["type"] == "working"
                          and i["subject"] == {"kind": "page", "name": "/a/"}
                          and i["period"]["after"][0] == "2026-09-29")
            ex = h.extras("example.com", self.anchor - timedelta(days=13), self.anchor)
        def total(first, last):
            return sum((ex[d]["pages"].get("/a/") or {}).get("readers", 0) for d in ex
                       if first <= d <= last)
        self.assertEqual(rising["after"], total("2026-09-29", "2026-10-05"))
        self.assertEqual(rising["before"], total("2026-09-22", "2026-09-28"))
        self.assertEqual((rising["before"], rising["after"], rising["change_pct"]), (14, 42, 200.0))
        self.assertEqual(rising["filter"], {"path": "/a/"})
        gone = [i for i in found if i["type"] == "gone"]
        self.assertIn("news.example.org", [i["subject"]["name"] for i in gone])

    def test_a_page_never_seen_before_is_new(self):
        with History(self.box.db) as h:
            found = insights.compute(h, "example.com", self.anchor, {})["insights"]
            short = insights.compute(h, "example.com", self.anchor,
                                     {"insights": {"min_history_days": 30}})["insights"]
        new = [i for i in found if i["type"] == "new"]
        self.assertEqual([(i["subject"], i["after"]) for i in new if i["subject"]["kind"] == "page"],
                         [({"kind": "page", "name": "/brand-new/"}, 3)])
        self.assertFalse([i for i in short if i["type"] == "new"])

    def test_an_incomplete_period_is_not_compared(self):
        with History(self.box.db) as h:
            h.withhold("example.com", self.anchor - timedelta(days=10), ["test"])
            found = insights.compute(h, "example.com", self.anchor, {})["insights"]
        self.assertFalse([i for i in found if i["type"] in ("working", "dropped", "gone")
                          and i["period"]["before"] and i["period"]["after"][0] == "2026-09-29"])

    def test_the_mail_carries_the_top_insights(self):
        with mock.patch.dict(os.environ, SECRETS):
            code, out, err = self.box.run("--today", "2026-10-06", "mail", "--daily", "--dry-run")
        self.assertEqual(code, 0, err)
        self.assertIn("WHAT CHANGED", out)
        self.assertIn("/a/", out)


if __name__ == "__main__":
    unittest.main()
