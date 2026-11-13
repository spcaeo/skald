"""A live round of many sites takes minutes, not the planned two (#54).

Seen on 12 Nov 2026: on a server with 13 sites one live round took 5-6
minutes, so the footer said "next any moment" for most of every round and
Data quality showed amber "late" badges for part of every round. Pinned:
runs.json keeps the last few gaps between a job's successes (a gap over six
hours, a stopped server, is not a round), the measured interval is their
median and never below the plan, an old runs.json without gaps still loads,
Data quality calls a job late only after twice the measured interval, the
footer counts down to it (tests/js/live-round.mjs), and the MCP's late check
reads the same figure."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from skald import quality, runs  # noqa: E402

T0 = datetime(2026, 11, 12, 17, 0, tzinfo=timezone.utc)


class Folder(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def ok_every(self, *minutes, name="live"):
        """A success at T0, then one after each gap in minutes."""
        at = T0
        runs.record(self.dir, name, 0, now=at)
        for m in minutes:
            at += timedelta(minutes=m)
            runs.record(self.dir, name, 0, now=at)
        return at


class Gaps(Folder):
    def test_gaps_kept_the_last_six(self):
        self.ok_every(5, 6, 5, 6, 7, 6, 5, 6)
        self.assertEqual(runs.load(self.dir)["live"]["gaps_s"], [300, 360, 420, 360, 300, 360])

    def test_a_failure_adds_no_gap(self):
        self.ok_every(6)
        runs.record(self.dir, "live", 1, now=T0 + timedelta(minutes=9))
        self.assertEqual(runs.load(self.dir)["live"]["gaps_s"], [360])

    def test_median_once_two_gaps(self):
        self.ok_every(6)
        state = runs.load(self.dir)
        self.assertIsNone(runs.measured_s(state["live"]), "one gap is not yet a measure")
        self.assertEqual(runs.every_s(state, "live"), 120.0, "the plan until measured")
        runs.path_for(self.dir).unlink()
        self.ok_every(5, 6, 7)
        state = runs.load(self.dir)
        self.assertEqual(runs.measured_s(state["live"]), 360.0)
        self.assertEqual(runs.every_s(state, "live"), 360.0)

    def test_even_count_median(self):
        self.ok_every(5, 6)
        self.assertEqual(runs.measured_s(runs.load(self.dir)["live"]), 330.0)

    def test_never_below_the_plan(self):
        # Refresh now between rounds: short gaps, still never below 2 minutes.
        self.ok_every(0.5, 1, 0.5)
        state = runs.load(self.dir)
        self.assertEqual(runs.measured_s(state["live"]), 30.0)
        self.assertEqual(runs.every_s(state, "live"), 120.0)

    def test_a_long_gap_is_ignored(self):
        self.ok_every(6, 60 * 7, 6)       # a server stopped for seven hours
        self.assertEqual(runs.load(self.dir)["live"]["gaps_s"], [360, 360])

    def test_an_old_file_loads(self):
        old = {"live": {"last_ok": T0.isoformat(), "last_fail": None, "last_exit": 0}}
        runs.path_for(self.dir).write_text(json.dumps(old))
        state = runs.load(self.dir)
        self.assertIsNone(runs.measured_s(state["live"]))
        self.assertEqual(runs.every_s(state, "live"), 120.0)
        self.assertEqual(runs.every_s({}, "live"), 120.0)
        self.assertIsNone(runs.every_s(None, "nothing-planned"))
        runs.record(self.dir, "live", 0, now=T0 + timedelta(minutes=6))
        self.assertEqual(runs.load(self.dir)["live"]["gaps_s"], [360])

    def test_a_bad_last_ok_adds_no_gap(self):
        runs.path_for(self.dir).write_text(json.dumps({"live": {"last_ok": "not a time"}}))
        runs.record(self.dir, "live", 0, now=T0)
        self.assertNotIn("gaps_s", runs.load(self.dir)["live"])


class Late(Folder):
    """Data quality: late only after twice the measured interval."""

    def build(self):
        p = SimpleNamespace(daily=[], snap=None, live_ok=False, live_dir=self.dir,
                            config={"logs": {"dir": str(self.dir / "no-logs")}}, failures=None)
        with mock.patch.object(quality, "_lines", return_value={}):
            return quality.build(p)["runs"]

    @staticmethod
    def late(job, now):
        """The page's rule (tabs/quality.js jobState), on this file's figures."""
        every = float(job["expected_every_min"])
        gone = (now - datetime.fromisoformat(job["last_ok"])).total_seconds()
        return gone > every * 2 * 60

    def test_measured_interval_sets_late(self):
        at = self.ok_every(6, 6, 6, 6)
        got = self.build()["live"]
        self.assertEqual((got["expected_every_min"], got["measured_every_min"]), (6.0, 6.0))
        self.assertFalse(self.late(got, at + timedelta(minutes=5)), "inside a round")
        self.assertFalse(self.late(got, at + timedelta(minutes=11)), "the old rule said late here")
        self.assertTrue(self.late(got, at + timedelta(minutes=13)), "two rounds missed")

    def test_unmeasured_keeps_the_plan(self):
        runs.record(self.dir, "live", 0, now=T0)
        got = self.build()
        self.assertEqual((got["live"]["expected_every_min"], got["live"]["measured_every_min"]),
                         (2, None))
        self.assertEqual(got["run-daily"]["expected_every_min"], 1440)
        self.assertEqual(list(got), ["live", "run-daily", "verify-bots", "alerts", "backup",
                                     "pagespeed", "heartbeat"])

    def test_the_mcp_reads_the_same_figure(self):
        from skald.mcp import tools_more
        now = T0 + timedelta(minutes=11)
        quality_json = {"generated_at": now.isoformat(), "runs": {
            "live": {"last_ok": T0.isoformat(), "expected_every_min": 6.0,
                     "measured_every_min": 6.0},
            "alerts": {"last_ok": (T0 - timedelta(minutes=5)).isoformat(),
                       "expected_every_min": 2, "measured_every_min": None}}}
        ctx = SimpleNamespace(
            site=lambda s: "example.com",
            load=lambda site, view, name, required=False: quality_json if name == "quality" else {})
        data = tools_more.site_health(ctx, {})[1]
        self.assertEqual([r["run"] for r in data["runs_late"]], ["alerts"])


class Footer(unittest.TestCase):
    def test_next_follows_the_measured_round(self):
        got = subprocess.run(["node", str(Path(__file__).resolve().parent / "js" / "live-round.mjs")],
                             capture_output=True, text=True, timeout=60)
        self.assertEqual(got.returncode, 0, got.stderr)
        self.assertIn("live round: ok", got.stdout)


if __name__ == "__main__":
    unittest.main()
