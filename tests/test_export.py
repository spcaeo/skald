"""Export and the dashboard's CSV downloads.

Exports read the same aggregates the dashboard draws, so the tests check
three things: the rows say what history says, nothing that identifies a
visitor can come out, and a request that cannot be answered honestly - a
filter that does not apply, a withheld day, a stale live snapshot - is
refused rather than answered with something plausible.
"""
from __future__ import annotations

import csv
import io
import json
import os
import sys
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald import export  # noqa: E402
from skald.store import History  # noqa: E402
from skald.verify import Problem  # noqa: E402

from support import ASKED, GOOGLEBOT, GPTBOT, Sandbox, day_lines, line, totals_for  # noqa: E402

UTC = timezone.utc
D1, D2, D3 = date(2026, 10, 4), date(2026, 10, 5), date(2026, 10, 6)
TODAY = "2026-10-07"
VIEWS = ["{name: Canada, path_prefix: /ca/}"]


def at(day, hour, minute=0):
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=UTC)


def rows(text: str) -> list[dict]:
    return list(csv.DictReader(io.StringIO(text)))


class ExportCase(unittest.TestCase):
    """Three days in history: 2, 3 and 4 people a day (day_lines), plus a
    page under /ca/ and a GB country on each."""

    def setUp(self):
        self.box = Sandbox(views=VIEWS)
        lines = []
        for day, n in ((D1, 2), (D2, 3), (D3, 4)):
            lines += day_lines(day, n)
            lines.append(line(at(day, 15), "203.0.113.77", "/ca/pricing", country="CA"))
        self.box.log(lines)
        code, _, err = self.box.run("--today", TODAY, "backfill", "--days", "3")
        self.assertEqual(code, 0, err)

    def tearDown(self):
        self.box.close()

    def export(self, *args):
        return self.box.run("--today", TODAY, "export", "--from", D1.isoformat(),
                            "--to", D3.isoformat(), *args)


class TestTables(ExportCase):

    def test_daily_is_one_row_per_group_per_day_and_adds_up(self):
        code, out, err = self.export()
        self.assertEqual(code, 0, err)
        got = rows(out)
        self.assertEqual(len(got), 15)
        with History(self.box.db) as h:
            for day in (D1, D2, D3):
                stored = h.period("example.com", day, day).totals.hits
                day_rows = [r for r in got if r["day"] == day.isoformat()]
                self.assertEqual(sum(int(r["requests"]) for r in day_rows), stored)
        people = [r for r in got if r["group"] == "people"]
        self.assertEqual([int(r["visits"]) for r in people], [3, 4, 5])
        self.assertEqual([r["cited_visits"] for r in people], ["1", "1", "1"])

    def test_group_filter(self):
        code, out, _ = self.export("--group", "bots")
        self.assertEqual({r["group"] for r in rows(out)}, {"bots"})
        self.assertEqual([r["probes"] for r in rows(out)], ["1", "1", "1"])

    def test_pages_total_with_a_path_prefix(self):
        code, out, err = self.export("--table", "pages", "--total", "--path-prefix", "/ca/")
        self.assertEqual(code, 0, err)
        self.assertEqual(rows(out), [{"state": "ok", "group": "people",
                                      "path": "/ca/pricing", "page_views": "3"}])

    def test_ai_pages_and_engines_by_tier_and_name(self):
        code, out, _ = self.export("--table", "ai_pages", "--total")
        self.assertEqual({r["path"]: r["page_views"] for r in rows(out)},
                         {"/guides/alpha": "3", "/guides/beta": "3"})
        code, out, _ = self.export("--table", "engines", "--total", "--tier", "asked")
        self.assertEqual(rows(out), [{"state": "ok", "group": "answer_engines",
                                      "tier": "asked", "name": "ChatGPT-User",
                                      "requests": "3"}])
        code, out, _ = self.export("--table", "engines", "--total",
                                   "--group", "search_engines")
        self.assertEqual([(r["name"], r["requests"]) for r in rows(out)],
                         [("Googlebot", "3")])
        code, out, _ = self.export("--table", "engines", "--engine", "gptbot")
        self.assertEqual({r["name"] for r in rows(out)}, {"GPTBot"})

    def test_citations_and_countries(self):
        code, out, _ = self.export("--table", "citations", "--total",
                                   "--source", "chatgpt.com")
        self.assertEqual(rows(out), [{"state": "ok", "source": "chatgpt.com",
                                      "visitors": "3"}])
        code, out, _ = self.export("--table", "countries", "--total", "--country", "ca")
        # Visits, not requests: one CA reader a day.
        self.assertEqual([(r["country"], r["visits"]) for r in rows(out)], [("CA", "3")])

    def test_a_view_exports_only_its_own_paths(self):
        code, out, err = self.export("--view", "Canada", "--table", "pages", "--total")
        self.assertEqual(code, 0, err)
        self.assertEqual([r["path"] for r in rows(out)], ["/ca/pricing"])
        code, _, err = self.export("--view", "Mars")
        self.assertEqual(code, 2)
        self.assertIn("no view named", err)

    def test_json_carries_the_coverage_and_the_filters(self):
        code, out, _ = self.box.run("--today", TODAY, "export", "--from", "2026-10-03",
                                    "--to", D3.isoformat(), "--table", "citations",
                                    "--format", "json")
        doc = json.loads(out)
        self.assertEqual(doc["table"], "citations")
        self.assertEqual(doc["coverage"]["missing"], ["2026-10-03"])
        self.assertEqual(doc["coverage"]["recorded"],
                         [d.isoformat() for d in (D1, D2, D3)])
        self.assertEqual(len(doc["rows"]), 3)

    def test_out_writes_a_file(self):
        target = self.box.root / "x.csv"
        code, out, err = self.export("--out", str(target))
        self.assertEqual(code, 0, err)
        self.assertEqual(out, "")
        self.assertEqual(len(rows(target.read_text())), 15)


class TestRefusals(ExportCase):

    def test_a_filter_that_does_not_apply_is_an_error_not_ignored(self):
        for args in (("--table", "pages", "--country", "CA"),
                     ("--table", "daily", "--engine", "GPTBot"),
                     ("--table", "countries", "--group", "people"),
                     ("--table", "engines", "--tier", "cited"),
                     ("--table", "citations", "--tier", "training"),
                     ("--table", "pages", "--group", "bots"),
                     ("--group", "robots")):
            with self.subTest(args=args):
                code, out, err = self.export(*args)
                self.assertEqual(code, 2)
                self.assertEqual(out, "")
                self.assertIn("export:", err)

    def test_withheld_days_are_left_out_unless_asked_and_then_marked(self):
        with History(self.box.db) as h:
            h.record("example.com", D2, totals_for(day_lines(D2, 3)), "UTC",
                     [Problem("groups do not sum", "test")])
        code, out, _ = self.export("--group", "people")
        self.assertEqual([r["day"] for r in rows(out)], ["2026-10-04", "2026-10-06"])
        code, out, _ = self.export("--group", "people", "--include-withheld")
        self.assertEqual([(r["day"], r["state"]) for r in rows(out)],
                         [("2026-10-04", "ok"), ("2026-10-05", "withheld"),
                          ("2026-10-06", "ok")])
        code, out, _ = self.export("--group", "people", "--include-withheld", "--total")
        self.assertEqual({r["state"] for r in rows(out)}, {"ok", "withheld"})

    def test_nothing_that_identifies_a_visitor_can_come_out(self):
        for table in export.TABLES:
            for fmt in ("csv", "json"):
                code, out, err = self.export("--table", table, "--format", fmt,
                                             "--include-withheld")
                self.assertEqual(code, 0, err)
                for forbidden in ("203.0.113.", "198.51.100.", "Mozilla/",
                                  "Chrome/", "AppleWebKit", "curl/"):
                    self.assertNotIn(forbidden, out, (table, fmt))

    def test_a_cell_a_spreadsheet_would_run_is_neutralised(self):
        text = export.as_csv([{"path": "=HYPERLINK(1)"}, {"path": "+1"},
                              {"path": "/ok"}, {"path": "@x"}])
        self.assertEqual(rows(text), [{"path": "'=HYPERLINK(1)"}, {"path": "'+1"},
                                      {"path": "/ok"}, {"path": "'@x"}])


class TestLiveExport(ExportCase):

    def live(self):
        logs = self.box.root / "logs" / "access.log"
        self.box.log(day_lines(date(2026, 10, 7), 2)[:3] + [
            line(at(date(2026, 10, 7), 9), "198.51.100.40", "/x", GPTBOT),
            line(at(date(2026, 10, 7), 9, 1), "198.51.100.41", "/y", ASKED),
            line(at(date(2026, 10, 7), 9, 2), "198.51.100.42", "/", GOOGLEBOT)])
        stamp = at(date(2026, 10, 7), 11).timestamp()
        os.utime(logs, (stamp, stamp))
        return self.box.run("--today", TODAY, "live")

    def test_today_so_far_exports_from_the_snapshot(self):
        code, _, err = self.live()
        self.assertEqual(code, 0, err)
        code, out, err = self.box.run("--today", TODAY, "export", "--live",
                                      "--table", "engines")
        self.assertEqual(code, 0, err)
        self.assertEqual({(r["state"], r["tier"], r["name"]) for r in rows(out)},
                         {("live", "training", "GPTBot"), ("live", "asked", "ChatGPT-User"),
                          ("live", "", "Googlebot")})

    def test_no_snapshot_for_today_is_a_refusal(self):
        code, out, err = self.box.run("--today", TODAY, "export", "--live")
        self.assertEqual(code, 1)
        self.assertIn("no live snapshot for today", err)
        self.live()
        code, out, err = self.box.run("--today", "2026-10-08", "export", "--live")
        self.assertEqual(code, 1)

    def test_live_takes_no_range_but_does_take_a_view(self):
        self.live()
        code, _, err = self.box.run("--today", TODAY, "export", "--live",
                                    "--from", "2026-10-06")
        self.assertEqual(code, 2)
        # Live snapshots carry each view's figures since the breakdowns.
        code, _, err = self.box.run("--today", TODAY, "export", "--live", "--view", "Canada")
        self.assertEqual(code, 0, err)


class TestDashboardDownloads(ExportCase):

    def setUp(self):
        super().setUp()
        code, _, err = self.box.run("--today", TODAY, "dashboard")
        self.assertEqual(code, 0, err)
        self.page_dir = self.box.root / "www" / "example.com"

    def test_every_table_links_a_csv_that_exists(self):
        page = (self.page_dir / "index.html").read_text()
        for name in ("daily.csv", "pages-30d.csv", "ai-pages-30d.csv", "ai-30d.csv",
                     "search-30d.csv", "citations-30d.csv", "readers-country-30d.csv",
                     "readers-browser-30d.csv", "statuses-30d.csv", "not-found-30d.csv"):
            with self.subTest(name=name):
                self.assertIn(f'href="exports/{name}" download>Download CSV</a>', page)
                self.assertTrue((self.page_dir / "exports" / name).exists())
        self.assertNotIn("<script", page)

    def test_the_csv_holds_the_same_figures_as_the_table(self):
        got = rows((self.page_dir / "exports" / "pages-30d.csv").read_text())
        page = (self.page_dir / "index.html").read_text()
        for r in got[:3]:
            self.assertIn(f'<td class="path">{r["path"]}</td><td class="n">'
                          f'{r["page_views"]}</td>', page)

    def test_each_view_has_its_own_files(self):
        got = rows((self.page_dir / "canada" / "exports" / "pages-30d.csv").read_text())
        self.assertEqual([r["path"] for r in got], ["/ca/pricing"])

    def test_today_csv_exists_only_with_a_live_snapshot_for_today(self):
        self.assertFalse((self.page_dir / "exports" / "today.csv").exists())
        TestLiveExport.live(self)
        today = self.page_dir / "exports" / "today.csv"
        self.assertTrue(today.exists())
        self.assertIn('href="exports/today.csv"', (self.page_dir / "index.html").read_text())
        self.box.run("--today", "2026-10-08", "dashboard")
        self.assertFalse(today.exists())


if __name__ == "__main__":
    unittest.main()
