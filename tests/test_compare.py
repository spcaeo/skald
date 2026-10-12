"""Compare two date ranges, and a page's lifecycle (compare.py, lifecycle.py).

What is pinned: only whole verified days count and the others are named;
every metric is the sum of the days' own totals; the dimension rows add up
to them (reconciled) and include every page and value; filters never put a
whole-site figure under a filter; a range across the clocks going back
works; a page published mid-range shows its milestones in order, its days
from publish with missing days as null, and the audit recounts every first
time and every visit-cube field from the raw log."""
from __future__ import annotations

import io
import json
import sqlite3
import sys
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald import compare, lifecycle  # noqa: E402
from skald.store import History  # noqa: E402

from support import CHROME, GOOGLEBOT, GPTBOT, UTC, Sandbox, line  # noqa: E402

IPHONE = ("Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) AppleWebKit/605.1.15 "
          "(KHTML, like Gecko) Version/26.0 Mobile/15E148 Safari/604.1")
FIREFOX = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:131.0) Gecko/20100101 Firefox/131.0"


def at(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=UTC)


def readers(day: date, n: int, path: str = "/", country: str = "US", agent: str = CHROME,
            ref: str = "-", first_ip: int = 10) -> list[str]:
    return [line(at(day, 12, i), f"203.0.113.{first_ip + i}", path, agent, ref, country=country)
            for i in range(n)]


class Week(unittest.TestCase):
    """Oct 1-8: B = Oct 1-4, A = Oct 5-8; Oct 3 has no lines at all."""

    def setUp(self):
        self.box = Sandbox()
        d = date(2026, 10, 1)
        lines = []
        for i, n in enumerate([3, 4, 0, 5, 6, 2, 7, 4]):
            day = d + timedelta(days=i)
            if not n:
                continue
            lines += readers(day, n, "/pricing/" if i % 2 else "/", "CA" if i > 4 else "US")
            lines.append(line(at(day, 15), "198.51.100.40", "/", GPTBOT))
            lines.append(line(at(day, 15, 5), "198.51.100.41", "/", GOOGLEBOT))
        # A reader from search on a page only A has, on an iPhone.
        lines += readers(date(2026, 10, 7), 1, "/new/", "GB", IPHONE,
                         "https://www.google.com/", first_ip=90)
        self.box.log(lines)
        code, out, err = self.box.run("--today", "2026-10-09", "backfill", "--days", "8")
        assert code == 0, err

    def tearDown(self):
        self.box.close()

    def run_compare(self, **filters):
        with History(self.box.db) as h:
            return compare.compare(h, "example.com", None, "2026-10-05..2026-10-08",
                                   "2026-10-01..2026-10-04", filters, {}, UTC)

    def test_metrics_are_the_whole_days_sums_and_reconcile(self):
        got = self.run_compare()
        m = {r["key"]: r for r in got["metrics"]}
        self.assertEqual((m["visitors"]["a"], m["visitors"]["b"]), (6 + 2 + 8 + 4, 3 + 4 + 5))
        self.assertEqual(m["visitors"]["delta"], 8)
        self.assertEqual(m["visitors"]["delta_pct"], 66.7)
        self.assertEqual((m["ai_training"]["a"], m["search"]["b"]), (4, 3))
        self.assertIsNone(m["leads"]["a"])                     # no CMS here: not 0
        self.assertEqual(got["b"]["excluded"], [{"day": "2026-10-03", "state": "missing"}])
        self.assertEqual((got["a"]["used"], got["b"]["used"]), (4, 3))
        self.assertTrue(got["reconciled"], got["problems"])
        self.assertEqual(sum(r["a"] for r in got["dimensions"]["countries"]), 20)
        pages = {r["name"]: r for r in got["dimensions"]["pages"]}
        self.assertTrue(pages["/new/"]["new"])
        self.assertEqual(pages["/new/"]["b"], 0)
        browsers = {r["name"]: r["a"] for r in got["dimensions"]["browsers"]}
        self.assertEqual(browsers["Safari"], 1)
        conts = {r["name"]: r for r in got["dimensions"]["continents"]}
        self.assertEqual((conts["North America"]["a"], conts["Europe"]["a"]), (19, 1))
        self.assertEqual(got["presets"]["previous"], {"from": "2026-10-01", "to": "2026-10-04"})
        self.assertEqual(got["presets"]["last_year"]["from"], "2025-10-05")

    def test_a_series_per_calendar_day_adds_up(self):
        got = self.run_compare()
        b = got["series"]["b"]
        self.assertEqual([r["day"] for r in b], ["2026-10-01", "2026-10-02", "2026-10-03",
                                                "2026-10-04"])
        self.assertEqual(b[2], {"day": "2026-10-03", "state": "missing", "visitors": None,
                                "pages_read": None, "visitors_from_ai": None, "ai_asked": None,
                                "ai_training": None, "search": None, "leads": None})
        self.assertEqual(sum(r["visitors"] for r in got["series"]["a"]), 20)
        self.assertEqual(got["series"]["a"][0]["ai_training"], 1)
        ca = self.run_compare(country="CA")["series"]["a"]
        self.assertEqual([r["visitors"] for r in ca], [0, 2, 7, 4])
        self.assertIsNone(ca[0]["pages_read"])

    def test_filters_never_show_whole_site_figures(self):
        got = self.run_compare(country="CA")
        m = {r["key"]: r for r in got["metrics"]}
        self.assertEqual((m["visitors"]["a"], m["visitors"]["b"]), (13, 0))
        self.assertIsNone(m["pages_read"]["a"])
        self.assertIsNone(m["ai_training"]["a"])
        page = self.run_compare(page="/pricing/")
        m = {r["key"]: r for r in page["metrics"]}
        self.assertEqual((m["visitors"]["a"], m["pages_read"]["a"]), (2 + 4, 2 + 4))
        self.assertIsNone(page["dimensions"]["devices"])
        with self.assertRaises(compare.Invalid):
            self.run_compare(colour="red")

    def test_ranges_are_checked(self):
        for bad in ("2026-10-08..2026-10-01", "yesterday", "2025-01-01..2026-10-01"):
            with self.subTest(bad=bad), self.assertRaises(compare.Invalid):
                compare.parse_range(bad)

    def test_the_command_and_retention(self):
        code, out, err = self.box.run("--today", "2026-10-09", "compare", "--a",
                                      "2026-10-05..2026-10-08", "--b", "2026-10-01..2026-10-04")
        self.assertEqual(code, 0, err)
        self.assertIn("Visitors", out)
        with History(self.box.db) as h:
            gone = h.prune_extras(date(2026, 10, 9), 5, ("pages", "visit_cube"))
            self.assertEqual(gone, 2 * 2)           # Oct 1 and 2 are older than 5 days
            got = compare.compare(h, "example.com", None, "2026-10-01..2026-10-04",
                                  "2026-10-05..2026-10-08", {}, {}, UTC)
        self.assertEqual(got["a"]["unmeasured"], ["2026-10-01", "2026-10-02"])


class AcrossTheClockChange(unittest.TestCase):
    def test_the_25_hour_day_counts_once(self):
        box = Sandbox(tz="America/New_York")
        try:
            d = date(2025, 11, 1)
            lines = []
            for i in range(3):
                day = d + timedelta(days=i)
                lines += [line(at(day, 13) + timedelta(hours=h), f"203.0.113.{i * 30 + h}", "/")
                          for h in range(0, 24, 4)]
            box.log(lines)
            self.assertEqual(box.run("--today", "2025-11-04", "backfill", "--days", "3")[0], 0)
            self.assertEqual(box.run("--today", "2025-11-04", "audit", "--day", "2025-11-02")[0], 0)
            with History(box.db) as h:
                got = compare.compare(h, "example.com", None, "2025-11-02..2025-11-02",
                                      "2025-11-01..2025-11-01", {}, {}, ZoneInfo("America/New_York"))
            self.assertTrue(got["reconciled"], got["problems"])
            self.assertEqual(sum(r["a"] for r in got["dimensions"]["sources"]),
                             got["metrics"][0]["a"])
        finally:
            box.close()


class Lifecycle(unittest.TestCase):
    """/launch/ is published Oct 3; the logs run Oct 4-7."""

    def setUp(self):
        self.box = Sandbox()
        meta = self.box.root / "pages.json"
        meta.write_text(json.dumps({"generated": "2026-10-08", "pages": [
            {"path": "/launch/", "key": "launch/", "locale": "en-us", "title": "Launch",
             "published": "2026-10-03", "updated": "2026-10-05"}]}))
        self.box.config.write_text(self.box.config.read_text().replace(
            "report:\n", f"report:\n  pages_meta: {meta}\n"))
        self.box.log([
            line(at(date(2026, 10, 4), 9), "198.51.100.41", "/launch/", GOOGLEBOT),
            line(at(date(2026, 10, 4), 10), "203.0.113.5", "/", CHROME),
            line(at(date(2026, 10, 5), 9), "198.51.100.40", "/launch/", GPTBOT),
            line(at(date(2026, 10, 5), 8), "198.51.100.40", "/launch/", GPTBOT),
            line(at(date(2026, 10, 6), 11), "203.0.113.6", "/launch/", FIREFOX,
                 "https://www.google.com/search?q=x"),
            line(at(date(2026, 10, 7), 14), "203.0.113.7", "/launch/", CHROME,
                 "https://chatgpt.com/"),
            line(at(date(2026, 10, 7), 15), "203.0.113.8", "/launch/", CHROME,
                 "https://chatgpt.com/"),
        ])
        code, out, err = self.box.run("--today", "2026-10-08", "backfill", "--days", "4")
        assert code == 0, err

    def tearDown(self):
        self.box.close()

    def test_milestones_and_days_since_publish(self):
        with History(self.box.db) as h:
            got = lifecycle.story(h, "example.com", "/launch", {"report": {
                "pages_meta": str(self.box.root / "pages.json")}}, UTC, date(2026, 10, 8))
        self.assertTrue(got["ok"])
        self.assertEqual((got["published"], got["date_source"], got["days_since_publish"]),
                         ("2026-10-03", "website", 5))
        m = got["milestones"]
        self.assertEqual(m["googlebot"]["at"], "2026-10-04T09:00:00+00:00")
        self.assertEqual(m["ai_training"], [{"who": "GPTBot", "at": "2026-10-05T08:00:00+00:00"}])
        self.assertEqual(m["human"]["at"], "2026-10-06T11:00:00+00:00")
        self.assertEqual((m["from_search"]["at"], m["from_search"]["who"]),
                         ("2026-10-06T11:00:00+00:00", "google.com"))
        self.assertEqual(m["from_ai"], [{"who": "chatgpt.com", "at": "2026-10-07T14:00:00+00:00"}])
        self.assertIsNone(m["bingbot"])
        days = {d["day"]: d for d in got["days"]}
        self.assertEqual(list(days)[0], "2026-10-03")
        # Published before the logs began: that day is "before", with no figures.
        self.assertEqual((days["2026-10-03"]["state"], days["2026-10-03"]["views"]),
                         ("before", None))
        self.assertEqual((days["2026-10-07"]["readers"], days["2026-10-07"]["days_since_publish"]),
                         (2, 4))
        self.assertEqual(days["2026-10-04"]["search"], 1)

    def test_a_later_backfill_never_moves_a_milestone_later(self):
        self.assertEqual(self.box.run("--today", "2026-10-08", "backfill", "--days", "4",
                                      "--force")[0], 0)
        with History(self.box.db) as h:
            rows = h.milestones("example.com", "/launch/")
        self.assertEqual(len([r for r in rows if r[1] == "human"]), 1)

    def test_the_audit_recounts_first_times_and_catches_a_change(self):
        self.assertEqual(self.box.run("--today", "2026-10-08", "audit", "--day", "2026-10-05")[0], 0)
        with sqlite3.connect(self.box.db) as db:
            blob = json.loads(db.execute("SELECT data FROM day_extras WHERE kind = 'page_firsts' "
                                         "AND day = '2026-10-05' AND site = 'example.com'")
                              .fetchone()[0])
            blob["/launch/"]["ai_training|GPTBot"][0] = "2026-10-05T09:00:00+00:00"
            db.execute("UPDATE day_extras SET data = ? WHERE kind = 'page_firsts' AND "
                       "day = '2026-10-05' AND site = 'example.com'", (json.dumps(blob),))
        code, out, err = self.box.run("--today", "2026-10-08", "audit", "--day", "2026-10-05")
        self.assertEqual(code, 1)
        self.assertIn("first ai_training|GPTBot", err)

    def test_page_index_and_the_helper(self):
        self.assertEqual(self.box.run("--today", "2026-10-08", "dashboard")[0], 0)
        index = json.loads((self.box.root / "www" / "example.com" / "data" /
                            "page_index.json").read_text())
        row = next(r for r in index["pages"] if r["path"] == "/launch/")
        self.assertEqual((row["published"], row["first_seen"], row["milestones"]["googlebot"]),
                         ("2026-10-03", "2026-10-04", "2026-10-04T09:00:00+00:00"))
        home = next(r for r in index["pages"] if r["path"] == "/")
        self.assertEqual(home["date_source"], "first seen")
        from skald.config import load_config
        from skald.refresh_server import make_handler

        class Runner:
            def refresh(self, force=False):
                return "ran"
        handler = make_handler(Runner(), set(), load_config(self.box.config),
                               self.box.root / "www", self.box.root, self.box.db)

        def get(path):
            raw = f"GET {path} HTTP/1.1\r\nHost: x\r\n\r\n".encode()
            out = io.BytesIO()

            class Sock:
                def makefile(self, *a, **k):
                    return io.BytesIO(raw)

                def sendall(self, data):
                    out.write(data)
            handler(Sock(), ("127.0.0.1", 1), None)
            head, _, body = out.getvalue().partition(b"\r\n\r\n")
            return int(head.split()[1]), json.loads(body)
        code, got = get("/traffic/example.com/api/compare?a=2026-10-06..2026-10-07"
                        "&b=2026-10-04..2026-10-05")
        self.assertEqual((code, got["metrics"][0]["a"]), (200, 3))
        code, got = get("/traffic/example.com/api/compare?a=nope&b=2026-10-04..2026-10-05")
        self.assertEqual(code, 400)
        code, got = get("/traffic/example.com/api/page?path=/launch/")
        self.assertEqual((code, got["published"]), (200, "2026-10-03"))
        self.assertEqual(get("/traffic/example.com/api/page?path=/nowhere/")[0], 404)


if __name__ == "__main__":
    unittest.main()
