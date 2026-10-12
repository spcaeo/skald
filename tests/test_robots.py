"""robots.txt beside what each crawler fetched (robots.py, robots.json):
verdicts by the crawler's own token, the per-day paths verified and
recounted by the audit, and a fetch that never repeats inside the hour or
loses the last good copy."""
from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald import robots  # noqa: E402

from support import GOOGLEBOT, GPTBOT, UTC, Sandbox, line  # noqa: E402

ROBOTS = "User-agent: GPTBot\nDisallow: /private/\n\nUser-agent: *\nAllow: /\n\nSitemap: https://example.com/sitemap.xml\n"
NOW = datetime(2026, 10, 6, 12, tzinfo=UTC)


class TestRules(unittest.TestCase):
    def test_verdict_and_groups(self):
        self.assertFalse(robots.verdict(ROBOTS, "GPTBot", "/private/x"))
        self.assertTrue(robots.verdict(ROBOTS, "GPTBot", "/"))
        self.assertTrue(robots.verdict(ROBOTS, "Googlebot", "/private/x"))
        got = robots.parse(ROBOTS)
        self.assertEqual(got["groups"][0], {"agents": ["GPTBot"], "allow": [],
                                            "disallow": ["/private/"], "crawl_delay": None})
        self.assertEqual(got["sitemaps"], ["https://example.com/sitemap.xml"])
        self.assertEqual(robots.applies(got["groups"], "GPTBot"), "GPTBot")
        self.assertEqual(robots.applies(got["groups"], "Googlebot"), "*")
        self.assertIsNone(robots.token_of("claims to be GPTBot"))


class TestRefresh(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.config = {"site": {"hosts": ["example.com", "www.example.com"]}}

    def tearDown(self):
        self.tmp.cleanup()

    def test_once_an_hour_and_the_last_good_copy_stays(self):
        calls = []

        def good(url):
            calls.append(url)
            return ROBOTS.encode()

        state = robots.refresh(self.config, self.dir, NOW, good)
        self.assertEqual(calls, ["https://www.example.com/robots.txt"])
        self.assertTrue(state["ok"])
        robots.refresh(self.config, self.dir, NOW + timedelta(minutes=30), good)
        self.assertEqual(len(calls), 1)

        def bad(url):
            raise OSError("down")

        state = robots.refresh(self.config, self.dir, NOW + timedelta(hours=2), bad)
        self.assertFalse(state["ok"])
        self.assertIn("down", state["error"])
        self.assertEqual(robots.cached(self.dir), ROBOTS)


class TestDay(unittest.TestCase):
    def setUp(self):
        self.box = Sandbox()
        t = datetime(2026, 10, 5, 12, tzinfo=UTC)
        self.box.log([line(t, "198.51.100.40", "/private/x", GPTBOT),
                      line(t + timedelta(minutes=1), "198.51.100.40", "/private/x", GPTBOT),
                      line(t + timedelta(minutes=2), "198.51.100.40", "/", GPTBOT),
                      line(t + timedelta(minutes=3), "198.51.100.42", "/", GOOGLEBOT),
                      line(t + timedelta(minutes=4), "203.0.113.5", "/private/x")])
        (self.box.root / robots.TEXT).write_text(ROBOTS)
        (self.box.root / robots.STATE).write_text(json.dumps(
            {"ok": True, "url": "https://example.com/robots.txt",
             "fetched_at": "2026-10-06T11:00:00+00:00"}))

    def tearDown(self):
        self.box.close()

    def stored(self) -> dict:
        with sqlite3.connect(self.box.db) as db:
            return json.loads(db.execute(
                "SELECT data FROM day_extras WHERE site = 'example.com' AND "
                "kind = 'crawler_paths'").fetchone()[0])

    def test_disallowed_fetches_counted_and_audited(self):
        self.assertEqual(self.box.run("--today", "2026-10-06", "collect")[0], 0)
        blob = self.stored()
        self.assertEqual(blob["GPTBot"], {"group": "answer_engines", "requests": 3,
                                          "paths": {"/private/x": 2, "/": 1}})
        self.assertEqual(blob["Googlebot"]["requests"], 1)
        code, out, err = self.box.run("--today", "2026-10-06", "audit")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.box.run("--today", "2026-10-06", "dashboard")[0], 0)
        got = json.loads((self.box.root / "www" / "example.com" / "data" /
                          "robots.json").read_text())
        by = {c["name"]: c for c in got["crawlers"]}
        self.assertEqual((by["GPTBot"]["disallowed"], by["GPTBot"]["applies"]), (2, "GPTBot"))
        self.assertEqual(by["GPTBot"]["disallowed_paths"], [{"path": "/private/x", "n": 2}])
        self.assertTrue(by["GPTBot"]["root_allowed"])
        self.assertEqual((by["Googlebot"]["disallowed"], by["Googlebot"]["applies"]), (0, "*"))
        day = next(d for d in got["days"] if d["day"] == "2026-10-05")
        self.assertEqual(day["crawlers"]["GPTBot"], {"requests": 3, "disallowed": 2})
        self.assertTrue(got["robots"]["ok"])

    def test_the_audit_catches_a_nudged_path(self):
        self.assertEqual(self.box.run("--today", "2026-10-06", "collect")[0], 0)
        blob = self.stored()
        blob["GPTBot"]["paths"]["/private/x"] += 1
        blob["GPTBot"]["requests"] += 1
        with sqlite3.connect(self.box.db) as db:
            db.execute("UPDATE day_extras SET data = ? WHERE kind = 'crawler_paths' AND "
                       "site = 'example.com'", (json.dumps(blob),))
        code, out, err = self.box.run("--today", "2026-10-06", "audit")
        self.assertEqual(code, 1)
        self.assertIn("GPTBot: /private/x", err)

    def test_verify_holds_the_sums(self):
        from skald.verify import check
        from support import totals_for
        totals = totals_for([line(NOW, "198.51.100.40", "/a", GPTBOT)])
        self.assertEqual(check(totals), [])
        totals.extras["crawler_paths"]["GPTBot"]["paths"]["/a"] += 1
        self.assertTrue(any(p.what == "crawler paths" for p in check(totals)))


if __name__ == "__main__":
    unittest.main()
