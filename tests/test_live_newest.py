"""An older live count never replaces a newer one (#50).

Live runs overlap: the scheduler's round of every site takes minutes, Refresh
now counts one site at once, and a manual `live` can run beside both. Seen on
12 Nov 2026: Refresh now saved a count to 22:22:33 that showed a visitor; the
round that had started at 22:18 finished later and saved its count to 22:18:01
over it, so the visitor vanished until the next round. Pinned: a run whose
count ends before the one saved keeps the saved one (snapshot and request list
untouched) and says so; a later run, or a new day, writes as before. Today's
kept visits follow the same rule (a "kept up to" marker), one page draw and one
alerts check run at a time per site, and the open page takes a refreshed count
only when it is later (tests/js/live-newer.mjs)."""
from __future__ import annotations

import subprocess
import sys
import tempfile
import threading
import time
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald import live  # noqa: E402
from support import UTC, Sandbox, line  # noqa: E402

DAY = date(2026, 11, 12)


def at(hour: int, minute: int = 0, second: int = 0) -> datetime:
    return datetime(DAY.year, DAY.month, DAY.day, hour, minute, second, tzinfo=UTC)


class Rule(unittest.TestCase):
    def test_same_day_later_until_wins(self):
        have = {"day": "2026-11-12", "until": "2026-11-12T22:22:33+00:00"}
        self.assertTrue(live.newer_on_disk(have, {"day": "2026-11-12",
                                                  "until": "2026-11-12T22:18:01+00:00"}))
        self.assertFalse(live.newer_on_disk(have, {"day": "2026-11-12",
                                                   "until": "2026-11-12T22:24:00+00:00"}))
        self.assertFalse(live.newer_on_disk(have, dict(have)))       # the same count: write

    def test_until_in_another_zone_is_compared_as_a_time(self):
        have = {"day": "2026-11-12", "until": "2026-11-12T17:22:33-05:00"}   # 22:22:33 UTC
        self.assertTrue(live.newer_on_disk(have, {"day": "2026-11-12",
                                                  "until": "2026-11-12T22:20:00+00:00"}))

    def test_a_new_day_always_writes_and_an_old_day_never_does(self):
        have = {"day": "2026-11-12", "until": "2026-11-12T23:59:00+00:00"}
        self.assertFalse(live.newer_on_disk(have, {"day": "2026-11-13",
                                                   "until": "2026-11-13T00:01:00+00:00"}))
        self.assertTrue(live.newer_on_disk({"day": "2026-11-13", "until": "2026-11-13T00:01:00+00:00"},
                                           {"day": "2026-11-12", "until": "2026-11-12T23:59:00+00:00"}))

    def test_nothing_saved_or_unreadable_writes(self):
        self.assertFalse(live.newer_on_disk(None, {"day": "2026-11-12", "until": "x"}))
        self.assertFalse(live.newer_on_disk({"day": "2026-11-12"},
                                            {"day": "2026-11-12", "until": "2026-11-12T22:00:00+00:00"}))


class Runs(unittest.TestCase):
    def setUp(self):
        self.box = Sandbox()
        self.addCleanup(self.box.close)
        self.box.log([line(at(9, m), address=f"203.0.113.{10 + m}", path=f"/p{m}/")
                      for m in range(0, 50, 5)])
        self.path = live.path_for(self.box.root, "example.com")

    def run_at(self, when: datetime):
        with mock.patch("skald.cli._now", return_value=when):
            code, out, err = self.box.run("--today", DAY.isoformat(), "live")
        self.assertEqual(code, 0, err)
        return out

    def test_an_older_count_finishing_later_keeps_the_newer_one(self):
        self.run_at(at(12, 5))
        self.assertTrue(self.path.exists(), list(self.box.root.iterdir()))
        saved = self.path.read_bytes()
        feed = self.path.with_name(self.path.stem + "-requests.json")
        feed_saved = feed.read_bytes() if feed.exists() else None
        out = self.run_at(at(12, 1))                    # started earlier, ends later
        self.assertIn("a newer count is already saved; kept it", out)
        self.assertEqual(self.path.read_bytes(), saved)
        if feed_saved is not None:
            self.assertEqual(feed.read_bytes(), feed_saved)

    def test_a_later_count_still_writes(self):
        self.run_at(at(12, 1))
        first = live.load(self.path)["until"]
        out = self.run_at(at(12, 5))
        self.assertNotIn("kept it", out)
        later = live.load(self.path)["until"]
        self.assertGreater(datetime.fromisoformat(later), datetime.fromisoformat(first))
        self.assertEqual(datetime.fromisoformat(later) - datetime.fromisoformat(first),
                         timedelta(minutes=4))


class KeptVisits(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = live.path_for(Path(self.tmp.name), "example.com")

    def keep(self, day, until):
        with live.keeping(self.path, day, until) as newest:
            return newest

    def test_an_older_run_does_not_replace_the_kept_visits(self):
        self.assertTrue(self.keep("2026-11-12", "2026-11-12T22:24:02+00:00"))
        self.assertFalse(self.keep("2026-11-12", "2026-11-12T22:19:47+00:00"))
        self.assertTrue(self.keep("2026-11-12", "2026-11-12T22:30:00+00:00"))
        self.assertTrue(self.keep("2026-11-13", "2026-11-13T00:01:00+00:00"))   # a new day
        self.assertFalse(self.keep("2026-11-12", "2026-11-12T23:59:00+00:00"))  # yesterday's late run

    def test_build_skips_keeping_when_a_later_run_kept_them(self):
        box = Sandbox()
        self.addCleanup(box.close)
        box.log([line(at(9, 0))])
        path = live.path_for(box.root, "example.com")
        with live.keeping(path, DAY.isoformat(), at(12, 5).isoformat()):
            pass
        from skald import cli
        with mock.patch("skald.people.visits.keep_live") as kept, \
                mock.patch("skald.cli._now", return_value=at(12, 1)):
            self.assertEqual(box.run("--today", DAY.isoformat(), "live")[0], 0)
        kept.assert_not_called()
        with mock.patch("skald.people.visits.keep_live") as kept, \
                mock.patch("skald.cli._now", return_value=at(12, 9)):
            self.assertEqual(box.run("--today", DAY.isoformat(), "live")[0], 0)
        kept.assert_called_once()


class OneAtATime(unittest.TestCase):
    def test_a_second_draw_waits_for_the_first(self):
        with tempfile.TemporaryDirectory() as folder:
            order = []

            def draw(name, hold):
                with live.site_lock(folder, "example.com", "draw"):
                    order.append(f"{name} in")
                    time.sleep(hold)
                    order.append(f"{name} out")

            a = threading.Thread(target=draw, args=("a", 0.3))
            a.start()
            time.sleep(0.05)
            b = threading.Thread(target=draw, args=("b", 0))
            b.start()
            a.join(); b.join()
            self.assertEqual(order, ["a in", "a out", "b in", "b out"])

    def test_the_draw_and_the_alerts_use_the_lock(self):
        root = Path(__file__).resolve().parent.parent / "skald"
        self.assertIn('live.site_lock(live_dir, site, "draw")', (root / "dashboard.py").read_text())
        self.assertIn('live.site_lock(ctx.live_dir, ctx.site, "alerts")', (root / "cli.py").read_text())

    def test_a_read_only_folder_still_runs(self):
        with live.site_lock("/nonexistent-folder-for-a-test", "example.com", "draw"):
            pass


class OpenPage(unittest.TestCase):
    def test_the_page_takes_only_a_later_count(self):
        got = subprocess.run(["node", str(Path(__file__).resolve().parent / "js" / "live-newer.mjs")],
                             capture_output=True, text=True, timeout=60)
        self.assertEqual(got.returncode, 0, got.stderr)
        self.assertIn("live newer: ok", got.stdout)


if __name__ == "__main__":
    unittest.main()
