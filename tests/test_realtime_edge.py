"""Real time at the 30-minute edge, and visits whatever order lines arrive in.

Live, 2026-10-26: `audit --live` on a busy shipped-log site now and then said
"visits active in the last 30 minutes: snapshot 14, recount 15", one visit, the
recount higher, with its country, city, source and device one higher too, and
every other figure matching. The cause was not the order of the shipped lines
(both roads read a window in time order, CLASSIFICATION.md "Line order"; the
tests below show the snapshot, the day and real time are the same for shuffled
lines). It was realtime.visit_figures: it skipped a visit that ended before the
first clock minute shown before counting it active, and that minute starts at
the next whole minute after `until` less 30 minutes. A live run at 12:00:40
shows the minutes 11:31 to 12:00, but "active" runs from 11:30:40, so a visit
whose last request was at 11:30:50 was active and was dropped.
"""
from __future__ import annotations

import json
import os
import random
import re
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald import realtime  # noqa: E402

from support import CHROME, Sandbox, line  # noqa: E402
from test_realtime import DAY, IPHONE, NOON  # noqa: E402

UTC = timezone.utc
AT = NOON + timedelta(seconds=40)        # a live run at 12:00:40: active from 11:30:40


def ago(minutes: float, seconds: float = 0) -> datetime:
    """That long before AT."""
    return AT - timedelta(minutes=minutes, seconds=seconds)


def edge_lines() -> list[str]:
    return [
        # Active: its last request at 11:30:50, after 11:30:40, before 11:31.
        line(ago(40), "203.0.113.50", "/start", country="US",
             referrer="https://www.google.com/"),
        line(ago(29, 50), "203.0.113.50", "/pricing", country="US"),
        # Not active: its last request at 11:30:30, before 11:30:40.
        line(ago(30, 10), "203.0.113.51", "/old", IPHONE, country="GB"),
        # Active, well inside the window.
        line(ago(10), "203.0.113.52", "/docs", country="CA"),
    ]


class Run:
    """A sandbox whose live run and audit run at AT (not on a whole minute)."""

    def __init__(self, lines: list[str]) -> None:
        self.box = Sandbox()
        self.box.log(lines)
        stamp = NOON.timestamp() - 60
        os.utime(self.box.root / "logs" / "access.log", (stamp, stamp))
        self._patch = mock.patch("skald.cli._now", lambda args, tz: AT.astimezone(tz))
        self._patch.start()

    def close(self) -> None:
        self._patch.stop()
        self.box.close()

    def live(self) -> dict:
        code, out, err = self.box.run("--today", DAY.isoformat(), "live")
        assert code == 0, err
        return json.loads((self.box.root / "live-example.com.json").read_text())

    def audit(self, *more: str):
        return self.box.run("--today", DAY.isoformat(), "audit", "--live", *more)


class TestActiveEdge(unittest.TestCase):
    def setUp(self):
        self.run = Run(edge_lines())

    def tearDown(self):
        self.run.close()

    def test_a_visit_ending_before_the_first_minute_shown_is_active(self):
        rt = self.run.live()["realtime"]
        self.assertEqual(rt["until"], "2026-10-07T12:00:40+00:00")
        self.assertEqual(rt["per_minute"][0]["at"], "2026-10-07T11:31+00:00")
        self.assertEqual(rt["active"], {"5": 0, "30": 2})
        self.assertEqual(rt["countries"]["US"], {"visits": 1, "active": 1})
        self.assertEqual(rt["countries"]["GB"], {"visits": 1, "active": 0})
        self.assertEqual(rt["sources"], {"Search engine": 1, "Direct or unknown": 1})
        self.assertEqual(len(rt["doing"]), rt["active"]["30"],
                         "the list and the count of active visits agree")
        # Not under way in any minute shown: it ended before 11:31.
        self.assertEqual(rt["per_minute"][0]["under_way"], 0)

    def test_the_recount_matches(self):
        self.run.live()
        code, out, err = self.run.audit()
        self.assertEqual(code, 0, err)
        self.assertIn("all match", out)

    def test_show_active_lists_both_roads(self):
        self.run.live()
        code, out, err = self.run.audit("--show-active")
        self.assertEqual(code, 0, err)
        self.assertIn("active since 2026-10-07T11:30:40+00:00, first minute shown "
                      "2026-10-07T11:31+00:00", out)
        self.assertIn("the snapshot: 2 active, 2 listed (at most 50); the recount: 2 active", out)
        rows = [r for r in out.splitlines() if r.startswith("  both")]
        self.assertEqual(len(rows), 2, out)
        self.assertIn("last 11:30:50  US  Desktop  Search engine  2 pages", out)
        self.assertNotIn("only", out)
        self.assertIsNone(re.search(r"\d+\.\d+\.\d+\.\d+", out), "no address")
        self.assertNotIn("Mozilla", out)

    def test_show_active_marks_a_visit_on_one_road(self):
        """What the 2026-10-26 runs would have shown: the edge visit missing from
        the snapshot."""
        self.run.live()
        path = self.run.box.root / "live-example.com.json"
        snap = json.loads(path.read_text())
        rt = snap["realtime"]
        rt["active"]["30"] -= 1
        rt["doing"] = [v for v in rt["doing"] if not v["last"].endswith("11:30:50+00:00")]
        path.write_text(json.dumps(snap))
        code, out, err = self.run.audit("--show-active")
        self.assertEqual(code, 1)
        self.assertIn("visits active in the last 30 minutes: the snapshot has 1, "
                      "the recount finds 2", err)
        self.assertIn("recount only  start 11:20  last 11:30:50  US  Desktop  Search engine", out)
        self.assertEqual(sum(r.startswith("  both") for r in out.splitlines()), 1)

    def test_visit_figures_at_the_edge(self):
        until = AT
        rows = [(ago(40), ago(29, 50), {"country": "US", "source": "Search engine",
                                        "device": "Desktop"}),
                (ago(31), ago(30, 10), {"country": "GB"}),
                (ago(30, 0), ago(30, 0), {"country": "FR"})]       # exactly at `since`
        got = realtime.visit_figures(rows, until)
        self.assertEqual(got["active"], {"5": 0, "30": 2})
        self.assertEqual(got["countries"]["FR"], {"visits": 1, "active": 1})
        self.assertEqual(got["countries"]["GB"], {"visits": 1, "active": 0})
        self.assertEqual(sum(got["under_way"]), 0)
        # On a whole minute the first minute shown starts at `since`: no gap.
        on = realtime.visit_figures([(ago(31), NOON - timedelta(minutes=30), {})], NOON)
        self.assertEqual(on["active"]["30"], 1)
        self.assertEqual(on["under_way"][0], 1)


# ------------------------------------------------------------- line order

AGENTS = (CHROME, IPHONE)
REFERRERS = ("-", "-", "https://example.com/a", "https://www.google.com/",
             "https://chatgpt.com/")
PATHS = ("/", "/a", "/b", "/c", "/a?utm_source=news", "/_next/static/app.js",
         "/api/ping", "/img/logo.png")


def busy_lines(seed: int) -> list[tuple[datetime, str]]:
    """Several visitors over the last 90 minutes, around the 30-minute edge
    too, as (when, line), in time order."""
    r = random.Random(seed)
    out = []
    for v in range(8):
        address, agent = f"203.0.113.{60 + v // 2}", AGENTS[v % 2]
        t = r.uniform(20, 90)
        for _ in range(r.randint(1, 9)):
            t -= r.uniform(0, 1 / 30) if r.random() < 0.3 else r.uniform(0, 14)
            if t <= 0.05:
                break
            when = (AT - timedelta(minutes=t)).replace(microsecond=0)
            out.append((when, line(when, address, r.choice(PATHS), agent,
                                   referrer=r.choice(REFERRERS),
                                   status=r.choice((200, 200, 200, 304, 404)),
                                   country=r.choice(("US", "CA", "GB")))))
    out.append((ago(29, 50), line(ago(29, 50), "203.0.113.90", "/edge", country="US")))
    out.sort(key=lambda x: x[0])
    return out


def shipped(lines: list[tuple[datetime, str]], seed: int) -> list[str]:
    """The same lines as shipped batches arrive: cut into batches, some sent
    late (up to the whole window behind)."""
    r = random.Random(seed)
    batches, i = [], 0
    while i < len(lines):
        n = r.randint(1, 4)
        batches.append([text for _, text in lines[i:i + n]])
        i += n
    out = []
    while batches:
        out.extend(batches.pop(0 if r.random() < 0.5 else r.randrange(len(batches))))
    return out


class TestLineOrder(unittest.TestCase):
    """Out-of-order lines give the same visits as the same lines in time order:
    the live snapshot, real time, its recount, and the day's totals."""

    SEEDS = (1, 2, 3)

    def counts(self, lines: list[str]) -> tuple[dict, dict]:
        run = Run(lines)
        try:
            snap = run.live()
            code, out, err = run.audit()
            self.assertEqual(code, 0, err)
            from skald.classify import Group
            from skald.config import load_config
            from skald.window import analyse_window, day_window
            # The day as collect counts it (the whole day: these lines are all of it).
            start, end = day_window(DAY, UTC)
            day = analyse_window(load_config(run.box.config), start, end)
            people = day.groups[Group.PEOPLE]
            return snap, {"visits": day.visits.as_dict(), "journeys": day.journeys,
                          "readers": people.readers, "sessions": people.visits,
                          "by": {k: dict(v) for k, v in people.by.items()},
                          "groups": {g.value: s.hits for g, s in day.groups.items()}}
        finally:
            run.close()

    def test_shuffled_batches_count_as_the_sorted_lines(self):
        for seed in self.SEEDS:
            with self.subTest(seed=seed):
                lines = busy_lines(seed)
                order = shipped(lines, seed)
                self.assertNotEqual(order, [t for _, t in lines], "out of time order")
                snap_sorted, day_sorted = self.counts([t for _, t in lines])
                snap_shipped, day_shipped = self.counts(order)
                self.assertEqual(snap_shipped["realtime"], snap_sorted["realtime"])
                self.assertEqual(snap_shipped["journeys"], snap_sorted["journeys"])
                self.assertEqual(snap_shipped["people"], snap_sorted["people"])
                self.assertEqual(snap_shipped["visits"], snap_sorted["visits"])
                self.assertEqual(day_shipped, day_sorted)
                self.assertGreater(snap_sorted["realtime"]["active"]["30"], 0)


if __name__ == "__main__":
    unittest.main()
