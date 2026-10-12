"""Page speed from Google PageSpeed Insights (pagespeed.py): the v5 answer
read and stored exactly (the round-trip check stands in for a recount: the
numbers are Google's, not the log's), the schema 10 table added to an older
history with a backup first, one test per page and strategy a day, failures
stored, the API key used but never printed, and speed.json's medians."""
from __future__ import annotations

import io
import json
import os
import sqlite3
import sys
import tempfile
import unittest
import urllib.error
from contextlib import redirect_stderr, redirect_stdout
from datetime import date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald import pagespeed  # noqa: E402
from skald.store import SCHEMA_VERSION, History  # noqa: E402

from support import UTC, Sandbox, day_lines, totals_for  # noqa: E402

DAY = date(2026, 10, 5)
NOW = datetime(2026, 10, 6, 12, tzinfo=UTC)
CONFIG = {"site": {"name": "example.com", "hosts": ["example.com", "www.example.com"]}}


def answer(score=0.91, lcp=1830.5, field_lcp=2100, cls_x100=4, inp=180, field=True) -> dict:
    """A trimmed v5 answer with the fields the module reads, shaped as Google
    sends them."""
    def experience(lcp_p75):
        return {"id": "https://www.example.com/", "overall_category": "FAST",
                "metrics": {
                    "LARGEST_CONTENTFUL_PAINT_MS": {"percentile": lcp_p75, "category": "FAST"},
                    "CUMULATIVE_LAYOUT_SHIFT_SCORE": {"percentile": cls_x100, "category": "FAST"},
                    "INTERACTION_TO_NEXT_PAINT": {"percentile": inp, "category": "FAST"},
                    "FIRST_CONTENTFUL_PAINT_MS": {"percentile": 900, "category": "FAST"}}}
    return {
        "captchaResult": "CAPTCHA_NOT_NEEDED", "kind": "pagespeedonline#result",
        "id": "https://www.example.com/",
        "loadingExperience": experience(field_lcp) if field else {"initial_url": "x"},
        "originLoadingExperience": experience(field_lcp + 100),
        "lighthouseResult": {
            "requestedUrl": "https://www.example.com/", "lighthouseVersion": "12.6.0",
            "categories": {"performance": {"id": "performance", "score": score}},
            "audits": {
                "largest-contentful-paint": {"numericValue": lcp, "displayValue": "1.8 s"},
                "cumulative-layout-shift": {"numericValue": 0.012, "displayValue": "0.012"},
                "total-blocking-time": {"numericValue": 40, "displayValue": "40 ms"},
                "first-contentful-paint": {"numericValue": 950.2, "displayValue": "1.0 s"},
                "speed-index": {"numericValue": 1400.7, "displayValue": "1.4 s"}}},
        "analysisUTCTimestamp": "2026-10-06T11:40:00.000Z"}


class Answer(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class Google:
    """A stand-in for urlopen: records each URL, answers from `plan`."""

    def __init__(self, plan=None):
        self.urls, self.plan = [], plan or (lambda url: answer())

    def __call__(self, request, timeout=None):
        self.urls.append(request.full_url)
        got = self.plan(request.full_url)
        if isinstance(got, Exception):
            raise got
        return Answer(json.dumps(got).encode())


class TestParse(unittest.TestCase):
    def test_lab_field_and_origin(self):
        got = pagespeed.parse(answer())
        self.assertEqual(got["score"], 91.0)
        self.assertEqual(got["lab"], {"lcp_ms": 1830.5, "cls": 0.012, "tbt_ms": 40.0,
                                      "fcp_ms": 950.2, "si_ms": 1400.7})
        self.assertEqual(got["field"], {"lcp_ms": 2100, "cls": 0.04, "inp_ms": 180,
                                        "category": "FAST"})
        self.assertEqual(got["origin"]["lcp_ms"], 2200)

    def test_no_field_data_is_none_and_no_result_is_an_error(self):
        self.assertIsNone(pagespeed.parse(answer(field=False))["field"])
        with self.assertRaises(ValueError):
            pagespeed.parse({"error": {"code": 500, "message": "Lighthouse returned error"}})


class DayCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.history = History(Path(self.tmp.name) / "history.sqlite")
        self.history.record("example.com", DAY, totals_for(day_lines(DAY, 12)), "UTC", [])
        self.out, self.err = [], []

    def tearDown(self):
        self.history.close()
        self.tmp.cleanup()

    def run_day(self, google, force=False):
        return pagespeed.test_day(self.history, "example.com", CONFIG, DAY, NOW, force,
                                  google, self.out.append, self.err.append)


class TestDay(DayCase):
    def test_top_landings_on_both_strategies_once_a_day(self):
        google = Google()
        got = self.run_day(google)
        paths = pagespeed.top_landings(self.history, "example.com", DAY)
        self.assertEqual(paths, ["/", "/guides/alpha"])
        self.assertEqual(got, {"tested": 4, "failed": 0, "skipped": 0})
        self.assertTrue(all(u.startswith(pagespeed.API + "?url=https%3A%2F%2Fwww.example.com%2F")
                            for u in google.urls))
        self.assertEqual(sorted(u.split("strategy=")[1].split("&")[0] for u in google.urls),
                         ["desktop", "desktop", "mobile", "mobile"])
        again = Google()
        self.assertEqual(self.run_day(again), {"tested": 0, "failed": 0, "skipped": 4})
        self.assertEqual(again.urls, [])
        self.assertEqual(self.run_day(Google(), force=True)["tested"], 4)

    def test_stored_is_what_google_said(self):
        self.run_day(Google())
        parsed = pagespeed.parse(answer())
        for path in ("/", "/guides/alpha"):
            for strategy in pagespeed.STRATEGIES:
                self.assertEqual(pagespeed.check(self.history.db, "example.com", DAY, path,
                                                 strategy, parsed), [])
        self.history.db.execute("UPDATE page_speed SET score = 12 WHERE path = '/'")
        self.assertTrue(pagespeed.check(self.history.db, "example.com", DAY, "/", "mobile", parsed))

    def test_a_failure_is_stored_with_its_reason(self):
        def plan(url):
            if "strategy=desktop" in url:
                return urllib.error.HTTPError(url, 500, "boom", {}, None)
            return {"error": {"message": "Lighthouse returned error: NO_FCP"}}
        with mock.patch.object(pagespeed.time, "sleep"):
            got = self.run_day(Google(plan))
        self.assertEqual(got["failed"], 4)
        rows = pagespeed.rows(self.history.db, "example.com", DAY, DAY)
        self.assertEqual({r["error"] for r in rows},
                         {"HTTP 500", "no Lighthouse result: Lighthouse returned error: NO_FCP"})
        self.assertFalse(any(r["ok"] for r in rows))

    def test_a_refused_test_is_tried_again_next_run(self):
        """Google's keyless quota answers 429: the day is not "done" until
        the tests are answered."""
        refused = Google(lambda url: urllib.error.HTTPError(url, 429, "quota", {}, None))
        with mock.patch.object(pagespeed.time, "sleep"):
            self.assertEqual(self.run_day(refused)["failed"], 4)
        later = Google()
        self.assertEqual(self.run_day(later), {"tested": 4, "failed": 0, "skipped": 0})
        self.assertTrue(all(r["ok"] for r in pagespeed.rows(self.history.db, "example.com",
                                                             DAY, DAY)))

    def test_the_key_is_sent_and_never_shown(self):
        secret = "AIzaTESTKEY123"

        def plan(url):
            return urllib.error.URLError(f"cannot reach {url}")
        with mock.patch.dict(os.environ, {pagespeed.ENV_KEY: secret}), \
                mock.patch.object(pagespeed.time, "sleep"):
            google = Google(plan)
            self.run_day(google)
        self.assertTrue(all("key=" + secret in u for u in google.urls))
        rows = pagespeed.rows(self.history.db, "example.com", DAY, DAY)
        shown = " ".join(self.out + self.err + [r["error"] or "" for r in rows])
        self.assertNotIn(secret, shown)
        self.assertIn("***", shown)


class TestRunNeverFails(unittest.TestCase):
    def test_run_exits_0_and_records_the_run(self):
        box = Sandbox()
        try:
            with History(box.db) as h:
                h.record("example.com", DAY, totals_for(day_lines(DAY, 3)), "UTC", [])
            from skald import cli
            ctx = cli.Context(cli.parser().parse_args(["--config", str(box.config),
                                                       "--today", "2026-10-06", "pagespeed"]))
            out, err = io.StringIO(), io.StringIO()
            with redirect_stdout(out), redirect_stderr(err), \
                    mock.patch.object(pagespeed, "fetch", side_effect=RuntimeError("down")):
                self.assertEqual(ctx.args.run(ctx), 0)
            self.assertIn("failed 4", out.getvalue())
            # Nothing answered: the run still exits 0, and is recorded as FAILED.
            self.assertIn("FAILED - Google refused every test", err.getvalue())
            runs = json.loads((box.root / "runs.json").read_text())
            self.assertEqual(runs["pagespeed"]["last_exit"], 1)
            self.assertIsNotNone(runs["pagespeed"]["last_fail"])
            # One answered test is a working run.
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()), \
                    mock.patch.object(pagespeed, "fetch", side_effect=[answer()] + [
                        RuntimeError("down")] * 3):
                self.assertEqual(ctx.args.run(ctx), 0)
            runs = json.loads((box.root / "runs.json").read_text())
            self.assertEqual(runs["pagespeed"]["last_exit"], 0)
        finally:
            box.close()

    def test_switched_off(self):
        self.assertFalse(pagespeed.enabled({"site": {"hosts": ["a.example"]},
                                            "pagespeed": {"enabled": False}}))
        self.assertFalse(pagespeed.enabled({}))
        self.assertTrue(pagespeed.enabled(CONFIG))
        self.assertEqual(pagespeed.base_url(CONFIG), "https://www.example.com")
        self.assertEqual(pagespeed.base_url({**CONFIG, "pagespeed": {"base_url": "https://x.example/"}}),
                         "https://x.example")


class TestMigration(unittest.TestCase):
    def test_a_v9_file_gets_the_table_after_a_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "history.sqlite"
            with History(path) as h:
                h.record("example.com", DAY, totals_for(day_lines(DAY, 3)), "UTC", [])
            db = sqlite3.connect(path)            # make it a schema 9 file again
            db.execute("DROP TABLE page_speed")
            db.execute("UPDATE meta SET value = '9' WHERE key = 'schema_version'")
            db.commit()
            db.close()
            with History(path) as h:
                self.assertEqual(h.migrated_from, 9)
                self.assertEqual(h.schema_version, SCHEMA_VERSION)
                self.assertEqual(h.db.execute("SELECT COUNT(*) FROM days").fetchone()[0], 1)
                h.db.execute("SELECT * FROM page_speed").fetchall()
            backup = path.with_name("history.sqlite.schema-v9.bak")
            self.assertTrue(backup.exists())
            old = sqlite3.connect(backup)
            self.assertEqual(old.execute("SELECT name FROM sqlite_master WHERE name = "
                                         "'page_speed'").fetchall(), [])
            self.assertEqual(old.execute("SELECT COUNT(*) FROM days").fetchone()[0], 1)
            old.close()


class TestSpeedJson(DayCase):
    def test_days_latest_and_median_trend(self):
        scores = iter([0.90, 0.70, 0.60, 0.80])

        def plan(url):
            return answer(score=next(scores), lcp=1000 if "mobile" in url else 2000)
        self.run_day(Google(plan))
        page = SimpleNamespace(key="example.com::us-english", today=DAY + timedelta(days=1),
                               config=CONFIG, history=self.history)
        got = pagespeed.build(page)
        self.assertEqual(len(got["days"]), pagespeed.DAYS)
        day = next(d for d in got["days"] if d["day"] == DAY.isoformat())
        self.assertEqual(len(day["tests"]), 4)
        self.assertEqual(day["tests"][0]["url"], "https://www.example.com/")
        self.assertEqual(len(got["latest"]), 4)
        trend = {s: [t for t in got["trend"][s] if t["day"] == DAY.isoformat()][0]
                 for s in pagespeed.STRATEGIES}
        scored = sorted(t["score"] for t in day["tests"] if t["strategy"] == "mobile")
        self.assertEqual(trend["mobile"]["score"], round(sum(scored) / 2, 4))
        self.assertEqual(trend["mobile"]["lcp_ms"], 1000)
        self.assertEqual(trend["desktop"]["lcp_ms"], 2000)
        self.assertEqual(trend["mobile"]["inp_ms"], 180)


class TestStatus(DayCase):
    def page(self):
        return SimpleNamespace(key="example.com", today=DAY + timedelta(days=1),
                               config=CONFIG, history=self.history)

    def test_every_test_refused_says_a_key_is_needed(self):
        refused = Google(lambda url: urllib.error.HTTPError(url, 429, "quota", {}, None))
        with mock.patch.object(pagespeed.time, "sleep"):
            self.run_day(refused)
        got = pagespeed.build(self.page())["status"]
        self.assertEqual((got["state"], got["day"]), ("failing", DAY.isoformat()))
        self.assertEqual(got["message"], "Not working: Google refused every test. A free "
                         "PageSpeed API key is needed (PSI_API_KEY in /etc/skald/env).")

    def test_other_failures_name_their_reason_and_one_answer_is_ok(self):
        def plan(url):
            return urllib.error.HTTPError(url, 500, "boom", {}, None)
        with mock.patch.object(pagespeed.time, "sleep"):
            self.run_day(Google(plan))
        got = pagespeed.build(self.page())["status"]
        self.assertEqual(got["state"], "failing")
        self.assertIn("HTTP 500", got["message"])
        self.assertNotIn("API key", got["message"])
        self.run_day(Google())
        self.assertEqual(pagespeed.build(self.page())["status"]["state"], "ok")

    def test_nothing_tested(self):
        self.assertEqual(pagespeed.status([])["state"], "not tested")


if __name__ == "__main__":
    unittest.main()
