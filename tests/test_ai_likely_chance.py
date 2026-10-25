"""Likely from an AI assistant, unless chance explains it (ai_likely.by_chance).

A day where ChatGPT-User fetches the home page every hour and people type
the home page in all day: none of those visits is "likely ChatGPT", while a
rarely visited page fetched once and visited right after still is. Both roads
agree, a planted error in the by-chance list is caught, a day stored before
the rule still audits clean, and leads leave the same fetches out.
"""
from __future__ import annotations

import json
import sqlite3
import sys
import unittest
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from support import ASKED, Sandbox, line  # noqa: E402

from skald import ai_likely, audit_leads  # noqa: E402
from skald.store import History  # noqa: E402

UTC = timezone.utc
DAY = date(2026, 10, 5)
TODAY = "2026-10-06"
START = datetime(2026, 10, 5, 0, 30, tzinfo=UTC)


def busy_day() -> list[str]:
    """ChatGPT-User fetches / at :00 of every hour (24 fetches, 384 minutes
    covered); 24 people type / in at :05 and 24 at :40 (48 direct visits:
    chance 48 x 384 / 1440 = 12.8); one fetch of /rare and a visit 3
    minutes later (chance 1 x 16 / 1440 = 0.01)."""
    lines = []
    for h in range(24):
        hour = datetime(2026, 10, 5, h, tzinfo=UTC)
        lines.append(line(hour, "198.51.100.40", "/", ASKED))
        lines.append(line(hour + timedelta(minutes=5), f"203.0.113.{h + 1}", "/"))
        lines.append(line(hour + timedelta(minutes=40), f"203.0.113.{h + 101}", "/"))
    lines.append(line(datetime(2026, 10, 5, 12, 20, tzinfo=UTC), "198.51.100.40", "/rare",
                      ASKED))
    lines.append(line(datetime(2026, 10, 5, 12, 23, tzinfo=UTC), "203.0.113.250", "/rare"))
    return sorted(lines)


class TestTheRule(unittest.TestCase):
    def test_by_chance_is_the_base_rate(self):
        fetches = {"/": [(m, "chatgpt.com") for m in range(0, 1440, 60)],
                   "/rare": [(740, "chatgpt.com")]}
        got = ai_likely.by_chance(fetches, Counter({"/": 48, "/rare": 1}), 15)
        self.assertEqual(got, {("chatgpt.com", "/")})
        # A quiet home page: 2 direct visits x 384 / 1440 = 0.53, still by chance;
        # one visit and 3 fetches (48 minutes): 0.03, evidence.
        self.assertIn(("chatgpt.com", "/"),
                      ai_likely.by_chance(fetches, Counter({"/": 2}), 15))
        few = {"/": [(0, "chatgpt.com"), (300, "chatgpt.com"), (600, "chatgpt.com")]}
        self.assertEqual(ai_likely.by_chance(few, Counter({"/": 1}), 15), set())

    def test_overlapping_windows_count_each_minute_once(self):
        fetches = {"/a": [(100, "claude.ai"), (101, "claude.ai"), (102, "claude.ai")]}
        # 18 distinct minutes; 20 visits: 20 x 18 / 1440 = 0.25, by chance.
        self.assertEqual(ai_likely.by_chance(fetches, Counter({"/a": 20}), 15),
                         {("claude.ai", "/a")})
        self.assertEqual(ai_likely.by_chance(fetches, Counter({"/a": 19}), 15), set())


class TestTheDay(unittest.TestCase):
    def setUp(self):
        self.box = Sandbox()
        self.box.log(busy_day())
        self.assertEqual(self.box.run("--today", TODAY, "collect")[0], 0)

    def tearDown(self):
        self.box.close()

    def stored(self):
        with History(self.box.db) as h:
            return h.extras("example.com", DAY, DAY)[DAY.isoformat()]

    def tamper(self, blob):
        db = sqlite3.connect(str(self.box.db))
        with db:
            db.execute("UPDATE day_extras SET data = ? WHERE kind = 'ai_likely'",
                       (json.dumps(blob),))
        db.close()

    def test_the_home_page_is_not_likely_and_the_rare_page_is(self):
        blob = self.stored()["ai_likely"]
        self.assertEqual((blob["direct"], blob["likely"]), (49, 1))
        self.assertEqual(blob["by_assistant"], {"chatgpt.com": 1})
        self.assertEqual(blob["pages"], {"/rare": 1})
        self.assertEqual(blob["by_chance"], {"chatgpt.com": ["/"]})
        self.assertEqual(blob["chance_limit"], 0.25)
        # The fetch-side figure is a fact, not an attribution: unchanged.
        self.assertEqual(blob["followed"], {"chatgpt.com": 25})
        code, out, err = self.box.run("--today", TODAY, "audit")
        self.assertEqual(code, 0, err + out)
        self.assertIn("all match", out)

    def test_a_planted_error_is_caught(self):
        blob = dict(self.stored()["ai_likely"], by_chance={})
        self.tamper(blob)
        code, _, err = self.box.run("--today", TODAY, "audit")
        self.assertEqual(code, 1)
        self.assertIn("ai_likely: chatgpt.com's fetches of / by chance: history has 0, "
                      "the recount finds 1", err)

    def test_a_day_counted_before_the_rule_still_audits_clean(self):
        """No chance_limit stored: the recount uses no limit, as the day did."""
        box = Sandbox()
        self.addCleanup(box.close)
        box.log(busy_day())
        with mock.patch.object(ai_likely, "by_chance", lambda *a, **k: set()):
            self.assertEqual(box.run("--today", TODAY, "collect")[0], 0)
        with History(box.db) as h:
            blob = h.extras("example.com", DAY, DAY)[DAY.isoformat()]["ai_likely"]
        self.assertEqual(blob["likely"], 25)
        for key in ("chance_limit", "by_chance"):
            blob.pop(key)
        db = sqlite3.connect(str(box.db))
        with db:
            db.execute("UPDATE day_extras SET data = ? WHERE kind = 'ai_likely'",
                       (json.dumps(blob),))
        db.close()
        code, out, err = box.run("--today", TODAY, "audit")
        self.assertEqual(code, 0, err + out)

    def test_leads_leave_the_same_fetches_out(self):
        with History.reader(self.box.db) as history:
            index = ai_likely.fetch_index(history, "example.com", DAY, DAY)
        home = datetime(2026, 10, 5, 9, 5, tzinfo=UTC)
        rare = datetime(2026, 10, 5, 12, 23, tzinfo=UTC)
        self.assertEqual(ai_likely.likely_for(index, "/", home, 15, UTC), "(none)")
        self.assertEqual(ai_likely.likely_for(index, "/rare", rare, 15, UTC), "chatgpt.com")
        days, pages = audit_leads._fetches(self.box.db, "example.com", DAY, DAY)
        self.assertNotIn("/", pages)
        self.assertEqual([w for _, w in pages["/rare"]], ["chatgpt.com"])


if __name__ == "__main__":
    unittest.main()
