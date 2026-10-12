"""Export of the breakdowns: readers by dimension, statuses, 404s, 5xx,
posts, response times and slow pages.

What is pinned: each readers dimension adds up to the day's readers; the
other tables say what history says; filters that would need two breakdowns
crossed are refused, not answered; a day collected before the breakdowns
existed is named "unmeasured", never exported as zeroes; and today so far
exports from the snapshot, for the site and for a view.
"""
from __future__ import annotations

import csv
import io
import json
import os
import sqlite3
import sys
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald import export  # noqa: E402
from skald.aggregate import READER_DIMS  # noqa: E402
from skald.classify import Group  # noqa: E402
from skald.store import History  # noqa: E402

from support import Sandbox, day_lines, line  # noqa: E402

UTC = timezone.utc
D1, D2 = date(2026, 10, 5), date(2026, 10, 6)
TODAY = "2026-10-07"
VIEWS = ["{name: Canada, path_prefix: /ca/}"]
IPHONE = ("Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) AppleWebKit/605.1.15 "
          "(KHTML, like Gecko) Version/27.0 Mobile/15E148 Safari/604.1")


def at(day, hour, minute=0):
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=UTC)


def rows(text: str) -> list[dict]:
    return list(csv.DictReader(io.StringIO(text)))


def extra(day) -> list[str]:
    """A Canadian iPhone reader from Google landing on /ca/pricing, a person
    hitting a missing page, a POST, and a 5xx."""
    return [
        line(at(day, 15), "203.0.113.77", "/ca/pricing", IPHONE, country="CA",
             referrer="https://www.google.com/"),
        line(at(day, 15, 5), "203.0.113.78", "/missing", status=404),
        line(at(day, 15, 6), "203.0.113.79", "/broken", status=502),
    ]


def post(when, address="203.0.113.80", path="/contact"):
    return (f'{when.isoformat()} {address} example.com "POST {path} HTTP/2.0" '
            f'200 10 "-" "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
            f'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36" '
            f'0.004 cc=US ray=-\n')


class Case(unittest.TestCase):

    def setUp(self):
        self.box = Sandbox(views=VIEWS)
        lines = []
        for day, n in ((D1, 2), (D2, 3)):
            lines += day_lines(day, n) + extra(day) + [post(at(day, 16))]
        self.box.log(lines)
        code, _, err = self.box.run("--today", TODAY, "backfill", "--days", "2")
        self.assertEqual(code, 0, err)

    def tearDown(self):
        self.box.close()

    def export(self, *args):
        return self.box.run("--today", TODAY, "export", "--from", D1.isoformat(),
                            "--to", D2.isoformat(), *args)

    def readers(self, day) -> int:
        with History(self.box.db) as h:
            return h.period("example.com", day, day).totals.groups[Group.PEOPLE].readers


class TestHistoryTables(Case):

    def test_each_reader_dimension_adds_up_to_the_readers(self):
        code, out, err = self.export("--table", "readers")
        self.assertEqual(code, 0, err)
        got = rows(out)
        for day in (D1, D2):
            want = self.readers(day)
            for dim in READER_DIMS:
                with self.subTest(day=day, dim=dim):
                    total = sum(int(r["readers"]) for r in got
                                if r["day"] == day.isoformat() and r["dimension"] == dim)
                    self.assertEqual(total, want)
        canada = [r for r in got if r["dimension"] == "country" and r["name"] == "CA"]
        self.assertEqual([r["readers"] for r in canada], ["1", "1"])

    def test_a_value_filter_picks_its_dimension(self):
        code, out, err = self.export("--table", "readers", "--country", "ca")
        self.assertEqual(code, 0, err)
        self.assertEqual({(r["dimension"], r["name"]) for r in rows(out)}, {("country", "CA")})
        code, out, err = self.export("--table", "readers", "--device", "mobile", "--total")
        self.assertEqual(code, 0, err)
        self.assertEqual(rows(out), [{"state": "ok", "dimension": "device",
                                      "name": "Mobile", "readers": "2"}])
        code, out, err = self.export("--table", "readers", "--path-prefix", "/ca/")
        self.assertEqual({r["dimension"] for r in rows(out)}, {"landing"})

    def test_two_dimensions_cannot_be_crossed(self):
        code, _, err = self.export("--table", "readers", "--country", "CA",
                                   "--browser", "Chrome")
        self.assertEqual(code, 2)
        self.assertIn("cannot be crossed", err)
        code, _, err = self.export("--table", "readers", "--dimension", "os",
                                   "--device", "Mobile")
        self.assertEqual(code, 2)
        code, _, err = self.export("--table", "readers", "--dimension", "colour")
        self.assertEqual(code, 2)
        code, _, err = self.export("--table", "statuses", "--status", "418")
        self.assertEqual(code, 2)
        code, _, err = self.export("--table", "not_found", "--browser", "Chrome")
        self.assertEqual(code, 2)

    def test_statuses_add_up_to_each_group(self):
        code, out, err = self.export("--table", "statuses")
        self.assertEqual(code, 0, err)
        got = rows(out)
        with History(self.box.db) as h:
            for day in (D1, D2):
                totals = h.period("example.com", day, day).totals
                for g, stats in totals.groups.items():
                    total = sum(int(r["requests"]) for r in got if r["day"] == day.isoformat()
                                and r["group"] == g.value)
                    self.assertEqual(total, stats.hits, (day, g))
        code, out, _ = self.export("--table", "statuses", "--status", "5xx", "--total")
        self.assertEqual(rows(out), [{"state": "ok", "group": "people", "status": "5xx",
                                      "requests": "2"}])

    def test_paths_tables(self):
        cases = {
            "not_found": ("/missing", "requests"),
            "server_errors": ("/broken", "requests"),
            "posts": ("/contact", "requests"),
        }
        for table, (path, num) in cases.items():
            with self.subTest(table=table):
                code, out, err = self.export("--table", table, "--total")
                self.assertEqual(code, 0, err)
                got = rows(out)
                self.assertIn(path, [r["path"] for r in got])
                self.assertEqual(sum(int(r[num]) for r in got if r["path"] == path), 2)
        code, out, _ = self.export("--table", "posts", "--group", "bots")
        self.assertEqual(rows(out), [])

    def test_speed_and_slow_pages(self):
        code, out, err = self.export("--table", "speed", "--total")
        self.assertEqual(code, 0, err)
        got = rows(out)
        with History(self.box.db) as h:
            views = h.period("example.com", D1, D2).totals.groups[Group.PEOPLE].views
        self.assertEqual(sum(int(r["page_views"]) for r in got), views)
        code, out, err = self.export("--table", "slow_pages")
        self.assertEqual(code, 0, err)
        self.assertEqual(rows(out), [])     # every test line answered in 4 ms

    def test_a_day_before_the_breakdowns_is_unmeasured_not_zero(self):
        db = sqlite3.connect(self.box.db)
        db.execute("UPDATE days SET breakdowns = NULL WHERE day = ?", (D1.isoformat(),))
        db.commit()
        db.close()
        code, out, err = self.export("--table", "readers", "--format", "json")
        self.assertEqual(code, 0, err)
        got = json.loads(out)
        self.assertEqual(got["coverage"]["unmeasured"], [D1.isoformat()])
        self.assertEqual({r["day"] for r in got["rows"]}, {D2.isoformat()})
        # Tables that existed before keep exporting that day.
        code, out, _ = self.export("--table", "daily")
        self.assertIn(D1.isoformat(), {r["day"] for r in rows(out)})

    def test_a_view_exports_its_own_breakdowns(self):
        code, out, err = self.export("--table", "readers", "--view", "Canada",
                                     "--dimension", "country", "--total")
        self.assertEqual(code, 0, err)
        self.assertEqual(rows(out), [{"state": "ok", "dimension": "country", "name": "CA",
                                      "readers": "2"}])


class TestLive(Case):

    def live(self):
        today = date(2026, 10, 7)
        logs = self.box.root / "logs" / "access.log"
        # --today runs at local noon: everything here is the morning.
        self.box.log([line(at(today, 9), "203.0.113.10", "/"),
                      line(at(today, 9, 1), "203.0.113.11", "/guides/alpha"),
                      line(at(today, 10), "203.0.113.77", "/ca/pricing", IPHONE,
                           country="CA", referrer="https://www.google.com/"),
                      line(at(today, 10, 5), "203.0.113.78", "/missing", status=404),
                      line(at(today, 10, 6), "203.0.113.79", "/broken", status=502)])
        stamp = at(today, 18).timestamp()
        os.utime(logs, (stamp, stamp))
        code, _, err = self.box.run("--today", TODAY, "live")
        self.assertEqual(code, 0, err)

    def test_readers_and_statuses_today(self):
        self.live()
        code, out, err = self.box.run("--today", TODAY, "export", "--live",
                                      "--table", "readers", "--dimension", "device")
        self.assertEqual(code, 0, err)
        got = {r["name"]: int(r["readers"]) for r in rows(out)}
        self.assertEqual(got, {"Desktop": 2, "Mobile": 1})
        self.assertEqual({r["state"] for r in rows(out)}, {"live"})
        code, out, err = self.box.run("--today", TODAY, "export", "--live",
                                      "--table", "statuses", "--group", "people")
        self.assertEqual(code, 0, err)
        self.assertEqual({r["status"]: int(r["requests"]) for r in rows(out)},
                         {"2xx": 3, "404": 1, "5xx": 1})

    def test_a_view_today(self):
        self.live()
        code, out, err = self.box.run("--today", TODAY, "export", "--live", "--view",
                                      "Canada", "--table", "readers", "--dimension",
                                      "source")
        self.assertEqual(code, 0, err)
        self.assertEqual([(r["name"], r["readers"]) for r in rows(out)],
                         [("Search engine", "1")])

    def test_an_older_snapshot_is_refused(self):
        with self.assertRaises(export.ExportError):
            export.rows_from_live({"state": "ok", "day": TODAY}, "speed", export.Filters())


if __name__ == "__main__":
    unittest.main()
