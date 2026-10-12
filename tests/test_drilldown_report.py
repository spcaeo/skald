"""Drill-down and reports: the daily cube (exact while not folded, audited),
the request rows' visit source, `skald report` as HTML and a CSV ZIP, the
weekly mail's optional attachment, and favicons only when switched on."""
from __future__ import annotations

import io
import json
import os
import sqlite3
import sys
import unittest
import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald import cube, mailer, requests_feed  # noqa: E402
from skald.classify import Classifier  # noqa: E402
from skald.parse import Hit  # noqa: E402
from skald.store import History  # noqa: E402

from support import (CHROME, SECRETS, UTC, Sandbox, day_lines, line,  # noqa: E402
                     totals_for)

IPHONE = ("Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) AppleWebKit/605.1.15 "
          "(KHTML, like Gecko) Version/26.0 Mobile/15E148 Safari/604.1")
DAY = date(2026, 10, 5)


def journey(country="CA", landing="/", source="Direct or unknown", via="", device="Desktop"):
    return {"country": country, "landing": landing, "source": source, "via": via,
            "device": device}


class TestCube(unittest.TestCase):
    def test_rows_add_up_and_fold_past_the_cap(self):
        js = [journey(), journey(), journey("US", source="AI assistant", via="chatgpt.com"),
              journey("GB", "/pricing", device="Mobile")]
        got = cube.rows(js)
        self.assertEqual(got["rows"][0], ["CA", "/", "Direct or unknown", "", "Desktop", 2])
        self.assertIn(["US", "/", "AI assistant", "chatgpt.com", "Desktop", 1], got["rows"])
        self.assertFalse(got["folded"])
        small = cube.rows(js, cap=1)
        self.assertTrue(small["folded"])
        self.assertEqual(small["rows"][-1], [cube.OTHER] * 5 + [2])
        self.assertEqual(sum(r[-1] for r in small["rows"]), 4)

    def test_fields_must_equal_the_readers_breakdowns(self):
        blob = cube.rows([journey(), journey("US")])
        self.assertEqual(cube.against(blob, {"country": {"CA": 1, "US": 1},
                                             "device": {"Desktop": 2},
                                             "source": {"Direct or unknown": 2},
                                             "landing": {"/": 2}}), [])
        self.assertTrue(cube.against(blob, {"country": {"CA": 2}, "device": {"Desktop": 2},
                                            "source": {"Direct or unknown": 2},
                                            "landing": {"/": 2}}))

    def test_collected_audited_and_in_cube_json(self):
        box = Sandbox()
        try:
            t = datetime(2026, 10, 5, 15, tzinfo=UTC)
            box.log(day_lines(DAY, 4) + [
                line(t, "203.0.113.50", "/pricing", IPHONE, "https://www.google.com/", country="CA")])
            self.assertEqual(box.run("--today", "2026-10-06", "collect")[0], 0)
            code, out, err = box.run("--today", "2026-10-06", "audit")
            self.assertEqual(code, 0, err)
            with sqlite3.connect(box.db) as db:
                data = json.loads(db.execute("SELECT data FROM day_extras WHERE kind='cube' "
                                             "AND site='example.com'").fetchone()[0])
            self.assertEqual(sum(r[-1] for r in data["rows"]), 5)
            self.assertIn(["CA", "/pricing", "Search engine", "", "Mobile", 1], data["rows"])
            self.assertIn(["US", "/", "AI assistant", "ChatGPT", "Desktop", 1], data["rows"])
            # A nudged row is caught by the recount.
            data["rows"][0][-1] += 1
            with sqlite3.connect(box.db) as db:
                db.execute("UPDATE day_extras SET data = ? WHERE kind='cube' AND "
                           "site='example.com'", (json.dumps(data),))
            code, out, err = box.run("--today", "2026-10-06", "audit")
            self.assertEqual(code, 1)
            self.assertIn("cube", err)
            self.assertEqual(box.run("--today", "2026-10-06", "dashboard")[0], 0)
            got = json.loads((box.root / "www" / "example.com" / "data" / "cube.json").read_text())
            self.assertEqual(got["dims"], list(cube.DIMS) + ["visits"])
            self.assertEqual(got["days"][-1]["day"], "2026-10-05")
        finally:
            box.close()


class TestRequestSource(unittest.TestCase):
    def test_every_request_of_a_visit_carries_its_source(self):
        c = Classifier()
        t = datetime(2026, 10, 5, 12, tzinfo=UTC)
        feed = requests_feed.Feed(t - timedelta(hours=1), 100, own_hosts=["example.com"])
        for i, (url, ref) in enumerate([("/pricing", "https://www.google.com/"),
                                        ("/_next/static/a.js", "https://example.com/pricing"),
                                        ("/features", "https://example.com/pricing")]):
            h = Hit(t + timedelta(seconds=i), "203.0.113.5", "example.com", "GET", url, "200",
                    ref, CHROME)
            feed(h, c(h))
        bot = Hit(t, "198.51.100.1", "example.com", "GET", "/", "200", "", "curl/8")
        feed(bot, c(bot))
        got = feed.result(UTC, lambda ip: False, t, t + timedelta(minutes=1), 6, 100, "x")
        self.assertEqual({r["path"]: r["source"] for r in got["rows"]},
                         {"/pricing": "Search engine", "/_next/static/a.js": "Search engine",
                          "/features": "Search engine", "/": ""})


class TestReports(unittest.TestCase):
    def setUp(self):
        self.box = Sandbox()
        self.history = History(self.box.db)
        for i in range(7):
            day = DAY - timedelta(days=i)
            self.history.record("example.com", day, totals_for(day_lines(day, 3)), "UTC", [])
        self.history.close()

    def tearDown(self):
        self.box.close()

    def test_html_report_is_self_contained(self):
        out = self.box.root / "r.html"
        code, text, err = self.box.run("--today", "2026-10-06", "report", "--out", str(out))
        self.assertEqual(code, 0, err)
        html = out.read_text()
        self.assertIn("traffic report, 29 Sep 2026 to 05 Oct 2026", html)
        self.assertIn("Day by day", html)
        self.assertIn("7 of 7", html)
        for forbidden in ("<script", "<img", "<link"):
            self.assertNotIn(forbidden, html)

    def test_csv_zip_has_every_table_and_a_readme(self):
        out = self.box.root / "r.zip"
        code, text, err = self.box.run("--today", "2026-10-06", "report", "--format", "csv-zip",
                                       "--out", str(out))
        self.assertEqual(code, 0, err)
        with zipfile.ZipFile(out) as z:
            names = set(z.namelist())
            self.assertIn("README.txt", names)
            self.assertIn("daily.csv", names)
            self.assertEqual(len(z.read("daily.csv").decode().strip().splitlines()), 1 + 7 * 5)

    def test_refused_without_verified_days(self):
        code, text, err = self.box.run("--today", "2026-10-06", "report", "--from", "2026-09-01",
                                       "--to", "2026-09-02", "--out", str(self.box.root / "x"))
        self.assertEqual(code, 1)
        self.assertIn("REFUSED", err)

    def weekly(self, extra: str = ""):
        from skald.config import load_config
        self.box.config.write_text(self.box.config.read_text().replace(
            "mail:\n", "mail:\n" + extra))
        config = load_config(self.box.config)
        with History(self.box.db) as h, mock.patch.dict(os.environ, SECRETS):
            return mailer.build("weekly", config, h, UTC, datetime(2026, 10, 6, 9, tzinfo=UTC))

    def test_weekly_attachment_only_when_switched_on(self):
        self.assertEqual(self.weekly().get_content_type(), "multipart/alternative")
        msg = self.weekly("  weekly_report_attachment: true\n")
        names = [p.get_filename() for p in msg.iter_attachments()]
        self.assertEqual(names, ["traffic-report-2026-09-29-to-2026-10-05.html"])


class TestFaviconsSwitch(unittest.TestCase):
    def test_the_live_run_fetches_icons_only_when_switched_on(self):
        box = Sandbox()
        try:
            # The day's lines start at noon; the live window ends at the start
            # of "now"'s second, so look from one o'clock.
            box.log(day_lines(date(2026, 10, 6), 2))
            later = datetime(2026, 10, 6, 13, tzinfo=UTC)
            with mock.patch("skald.favicons.refresh") as refresh, \
                    mock.patch("skald.cli._now", return_value=later):
                self.assertEqual(box.run("--today", "2026-10-06", "live")[0], 0)
                refresh.assert_not_called()
                box.config.write_text(box.config.read_text().replace(
                    "dashboard:\n", "dashboard:\n  favicons: true\n"))
                self.assertEqual(box.run("--today", "2026-10-06", "live")[0], 0)
                self.assertEqual(refresh.call_count, 1)
                self.assertIn("chatgpt.com", refresh.call_args[0][3])
        finally:
            box.close()


if __name__ == "__main__":
    unittest.main()


class TestFeedCutsOnWholeSeconds(unittest.TestCase):
    """The audit recounts the feed from its written "from" (to the second); a
    cut inside a second left out lines the recount counted."""

    def test_lines_in_the_cutoff_second_are_in_feed_and_recount_alike(self):
        box = Sandbox()
        try:
            now = datetime(2026, 10, 6, 12, 0, 0, 600000, tzinfo=UTC)
            edge = datetime(2026, 10, 6, 6, 0, 0, tzinfo=UTC)      # now - 6 h, whole second
            box.log([line(edge, f"203.0.113.{i}", "/", CHROME) for i in range(3)]
                    + [line(now - timedelta(minutes=5), "203.0.113.9", "/x", CHROME)])
            with mock.patch("skald.cli._now", return_value=now):
                self.assertEqual(box.run("live")[0], 0)
                code, out, err = box.run("audit", "--live")
            self.assertEqual(code, 0, err)
            feed = requests_feed.load(requests_feed.path_for(box.root, "example.com"))
            self.assertEqual(feed["total"], 4)
        finally:
            box.close()
