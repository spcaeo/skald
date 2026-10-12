"""Hourly figures by UTC hour (hourly.json `hours_utc`), so a page can show
any time zone exactly - the day the clocks go back has two local 01:00 hours,
which the local "01" key merges and the UTC keys keep apart."""
from __future__ import annotations

import json
import sqlite3
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from support import CHROME, GPTBOT, UTC, Sandbox, line  # noqa: E402


class TestHoursUtc(unittest.TestCase):
    def setUp(self):
        self.box = Sandbox(tz="America/New_York")
        # 2 Nov 2025, New York: 01:30 EDT is 05:30 UTC, 01:30 EST is 06:30 UTC.
        self.box.log([line(datetime(2025, 11, 2, 5, 30, tzinfo=UTC), "203.0.113.1", "/", CHROME),
                      line(datetime(2025, 11, 2, 6, 30, tzinfo=UTC), "203.0.113.2", "/", CHROME),
                      line(datetime(2025, 11, 2, 6, 40, tzinfo=UTC), "198.51.100.3", "/", GPTBOT),
                      line(datetime(2025, 11, 2, 18, 0, tzinfo=UTC), "203.0.113.4", "/b", CHROME,
                           status=502)])

    def tearDown(self):
        self.box.close()

    def stored(self) -> dict:
        with sqlite3.connect(self.box.db) as db:
            return {k: json.loads(v) for k, v in db.execute(
                "SELECT kind, data FROM day_extras WHERE site = 'example.com'")}

    def test_the_repeated_hour_is_two_utc_hours_and_the_audit_agrees(self):
        self.assertEqual(self.box.run("--today", "2025-11-03", "collect")[0], 0)
        got = self.stored()
        self.assertEqual(got["hourly"]["01"]["people"], 2)
        utc = got["hourly_utc"]
        self.assertEqual((utc["2025-11-02T05"]["people"], utc["2025-11-02T06"]["people"]), (1, 1))
        self.assertEqual(utc["2025-11-02T06"]["ai_training"], 1)
        self.assertEqual(utc["2025-11-02T18"]["server_errors"], 1)
        self.assertEqual(sum(h["readers"] for h in utc.values()), 2)   # the 502 read nothing
        code, out, err = self.box.run("--today", "2025-11-03", "audit")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.box.run("--today", "2025-11-03", "dashboard")[0], 0)
        page = json.loads((self.box.root / "www" / "example.com" / "data" /
                           "hourly.json").read_text())
        day = next(d for d in page["days"] if d["day"] == "2025-11-02")
        self.assertEqual(day["hours_utc"], utc)

    def test_a_nudged_utc_hour_is_caught(self):
        self.assertEqual(self.box.run("--today", "2025-11-03", "collect")[0], 0)
        utc = self.stored()["hourly_utc"]
        utc["2025-11-02T05"]["people"] += 1
        with sqlite3.connect(self.box.db) as db:
            db.execute("UPDATE day_extras SET data = ? WHERE kind = 'hourly_utc' AND "
                       "site = 'example.com'", (json.dumps(utc),))
        code, out, err = self.box.run("--today", "2025-11-03", "audit")
        self.assertEqual(code, 1)
        self.assertIn("UTC hour 2025-11-02T05: people", err)


if __name__ == "__main__":
    unittest.main()
