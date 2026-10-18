"""Lines out of time order: both roads read a day in time order.

nginx writes a line when a request ends; some formats stamp it with the
request's start, shipped logs (skald-ship, ingest) and rotations can
interleave. So a slow request can sit in the file after a later, faster one.

The rule (CLASSIFICATION.md, "Line order"; COUNTING-TRAPS.md): a window's
lines are counted in timestamp order, ties kept in file order, on both roads.
The main road reorders as it streams (parse.in_time_order), holding back only
as far as the window's lines are actually out of order; the audit sorts its
own list.

What is pinned: a day whose visit is written out of order (a page logged
before an earlier one, 1-3 s apart; an asset before its page) is stored
exactly as the same day written in order - steps, exits, landing pages,
trails, flow, funnels, first touch, ai_read and every other figure - and the
audit says "all match"; a line far out of order (hours) is placed too; the
reorder holds back only what it must.
"""
from __future__ import annotations

import json
import random
import sqlite3
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from support import ASKED, CHROME, UTC, Sandbox, day_lines, line  # noqa: E402
from test_funnel_history import STEPS, saved, write_funnels  # noqa: E402
from test_visits import DAY, T  # noqa: E402

SITE = "https://example.com"
IPHONE = ("Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) AppleWebKit/605.1.15 "
          "(KHTML, like Gecko) Version/26.0 Mobile/15E148 Safari/604.1")


def visit_lines() -> list[tuple[datetime, str]]:
    """(when, line) for a day with order-dependent visits, in time order."""
    out = []

    def add(when, *a, **k):
        out.append((when, line(when, *a, **k)))
    # ChatGPT's user fetcher reads two pages a minute before the reader comes.
    add(T - timedelta(seconds=70), "198.51.100.41", "/compare/x/", ASKED)
    add(T - timedelta(seconds=65), "198.51.100.41", "/features/", ASKED)
    # A reader from ChatGPT: lands, moves to /features/ 2 s later, then pricing.
    add(T, "203.0.113.50", "/compare/x/", IPHONE, "https://chatgpt.com/", country="CA")
    add(T + timedelta(seconds=1), "203.0.113.50", "/_next/static/a.js", IPHONE,
        f"{SITE}/compare/x/", country="CA")
    add(T + timedelta(seconds=2), "203.0.113.50", "/features", IPHONE,
        f"{SITE}/compare/x/", country="CA")
    add(T + timedelta(seconds=3), "203.0.113.50", "/pricing/", IPHONE,
        f"{SITE}/features", country="CA")
    # A reader from Google: two pages 3 s apart, then a 404.
    add(T + timedelta(minutes=5), "203.0.113.60", "/", CHROME,
        "https://www.google.com/", country="US")
    add(T + timedelta(minutes=5, seconds=3), "203.0.113.60", "/guides/alpha", CHROME,
        f"{SITE}/", country="US")
    add(T + timedelta(minutes=5, seconds=4), "203.0.113.60", "/nope", CHROME,
        f"{SITE}/guides/alpha", status=404, country="US")
    # The same Google reader comes back from a newsletter link 2 s after a
    # direct page: a new visit by source, so which came first decides it.
    add(T + timedelta(minutes=9), "203.0.113.61", "/guides/beta", CHROME, country="DE")
    add(T + timedelta(minutes=9, seconds=2), "203.0.113.61",
        "/pricing/?utm_source=news&utm_medium=email", CHROME,
        "https://news.example.org/", country="DE")
    return out


def in_order() -> list[str]:
    return day_lines(DAY, 3) + [text for _, text in sorted(visit_lines())]


def out_of_order() -> list[str]:
    """The same lines, each visit's later lines written first (1-3 s)."""
    got = [text for _, text in sorted(visit_lines())]
    # chatgpt reader: /features (T+2) and /pricing/ (T+3) before /compare/x/ (T)
    got[2:6] = [got[4], got[5], got[3], got[2]]
    # google reader: /guides/alpha (+3 s) before / ; the 404 first of all
    got[6:9] = [got[8], got[7], got[6]]
    # tagged page (+2 s) before the direct one
    got[9:11] = [got[10], got[9]]
    return day_lines(DAY, 3) + got


def stored(db: Path) -> dict:
    """Every stored figure of the day, without what describes the read itself
    (which files, when it ran)."""
    con = sqlite3.connect(str(db))
    try:
        out = {}
        tables = [t for (t,) in con.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'")]
        for table in tables:
            cols = [c[1] for c in con.execute(f"PRAGMA table_info({table})")]
            skip = {"collected_at", "created", "updated", "at", "run_at", "ran_at"}
            keep = [c for c in cols if c not in skip]
            rows = con.execute(f"SELECT {', '.join(keep)} FROM {table}").fetchall()
            norm = []
            for row in rows:
                row = list(row)
                for i, v in enumerate(row):
                    if isinstance(v, str) and v.startswith("{"):
                        try:
                            blob = json.loads(v)
                        except ValueError:
                            continue
                        if isinstance(blob, dict):
                            blob.pop("files", None)
                            row[i] = json.dumps(blob, sort_keys=True)
                norm.append(tuple(row))
            out[table] = sorted(norm, key=repr)
        return out
    finally:
        con.close()


class TestOutOfOrderDay(unittest.TestCase):

    def collect(self, lines):
        box = Sandbox()
        self.addCleanup(box.close)
        box.log(lines)
        write_funnels(box.root, saved(), saved("From ChatGPT", source="ChatGPT"),
                      saved("Any to features", steps=STEPS[:2]))
        code, _, err = box.run("--today", "2026-10-06", "collect", "--day", "2026-10-05")
        self.assertEqual(code, 0, err)
        return box

    def test_out_of_order_lines_are_stored_as_if_in_order(self):
        ordered = stored(self.collect(in_order()).db)
        shuffled = stored(self.collect(out_of_order()).db)
        for table in ordered:
            self.assertEqual(shuffled[table], ordered[table], table)

    def test_the_audit_agrees_on_an_out_of_order_day(self):
        box = self.collect(out_of_order())
        code, out, err = box.run("--today", "2026-10-06", "audit", "--day", "2026-10-05")
        self.assertEqual(code, 0, err + out)
        self.assertIn("all match", out)

    def test_the_steps_are_the_visit_in_time_order(self):
        from skald.store import History
        box = self.collect(out_of_order())
        with History(box.db) as h:
            steps = dict(h.db.execute(
                "SELECT name, n FROM counts WHERE kind = 'visit_step' AND site = "
                "'example.com'").fetchall())
            landing = dict(h.db.execute(
                "SELECT name, n FROM counts WHERE kind = 'reader_landing' AND site = "
                "'example.com'").fetchall())
        self.assertEqual(steps.get("/compare/x/ → /features"), 1, steps)
        self.assertNotIn("/features → /compare/x/", steps)
        self.assertEqual(landing.get("/compare/x/"), 1, landing)
        self.assertNotIn("/features", landing)

    def test_a_line_hours_out_of_order_is_placed_on_both_roads(self):
        # A rotation or a shipped batch written late: a reader's morning page
        # after the afternoon lines.
        late = line(T - timedelta(hours=3), "203.0.113.60", "/early/", CHROME,
                    "https://www.google.com/", country="US")
        early_first = in_order()
        early_first.insert(len(day_lines(DAY, 3)), late)
        ordered = stored(self.collect(early_first).db)
        box = self.collect(out_of_order() + [late])
        self.assertEqual(stored(box.db), ordered)
        code, out, err = box.run("--today", "2026-10-06", "audit", "--day", "2026-10-05")
        self.assertEqual(code, 0, err + out)
        self.assertIn("all match", out)

    def test_a_shuffled_day_audits_and_stores_the_same(self):
        rng = random.Random(7)
        lines = in_order()
        base = stored(self.collect(lines).db)
        for _ in range(3):
            mixed = list(lines)
            # Swap neighbours a few seconds apart, as a busy server does.
            for i in range(len(mixed) - 1):
                if rng.random() < 0.5:
                    mixed[i], mixed[i + 1] = mixed[i + 1], mixed[i]
            box = self.collect(mixed)
            self.assertEqual(stored(box.db), base)
            code, out, err = box.run("--today", "2026-10-06", "audit", "--day", "2026-10-05")
            self.assertEqual(code, 0, err + out)
            self.assertIn("all match", out)


class _Hit:
    def __init__(self, when, name):
        self.when, self.name = when, name


class TestInTimeOrder(unittest.TestCase):
    """parse.in_time_order (main road) against audit.in_time_order (a whole
    sort, its own code): the same order whenever the hold covers the
    lateness, and the main road holds back only a minute of lines."""

    def hits(self, seed: int, n: int = 400, jitter: int = 4):
        rng = random.Random(seed)
        out = []
        for i in range(n):
            # Whole seconds, so ties are common; up to `jitter` s out of order.
            when = T + timedelta(seconds=i // 3 + rng.randrange(0, jitter))
            out.append(_Hit(when, i))
        return out

    def test_the_same_order_as_a_whole_sort_ties_in_read_order(self):
        from skald import audit, parse
        for seed in range(20):
            hits = self.hits(seed)
            seen = parse.Lateness()
            got = [h.name for h in parse.in_time_order(iter(hits), seen=seen)]
            want = [h.name for h in audit.in_time_order(hits)]
            self.assertEqual(got, want)
            self.assertFalse(seen.inverted)
            self.assertLessEqual(seen.most, timedelta(seconds=4))

    def test_a_line_later_than_the_hold_is_reported_and_a_second_read_is_exact(self):
        from skald import audit, parse
        hits = self.hits(1)
        hits.append(_Hit(T - timedelta(hours=3), "late"))
        seen = parse.Lateness()
        first = [h.name for h in parse.in_time_order(iter(hits), seen=seen)]
        want = [h.name for h in audit.in_time_order(hits)]
        self.assertNotEqual(first, want)
        self.assertTrue(seen.inverted)
        self.assertGreaterEqual(seen.hold(), timedelta(hours=3))
        again = [h.name for h in parse.in_time_order(iter(hits), seen.hold())]
        self.assertEqual(again, want)
        self.assertEqual(again[0], "late")

    def test_only_a_minute_of_lines_is_held(self):
        from skald import parse
        held = []

        def stream():
            for i in range(3000):
                held.append(i)
                yield _Hit(T + timedelta(seconds=i), i)
        for out in parse.in_time_order(stream()):
            # Read so far minus passed on: what is held at this moment.
            self.assertLessEqual(len(held) - out.name, 62)

    def test_a_timestamp_without_offset_is_utc(self):
        from skald import parse
        naive = _Hit(T.replace(tzinfo=None) + timedelta(seconds=1), "naive")
        aware = _Hit(T, "aware")
        self.assertEqual([h.name for h in parse.in_time_order([naive, aware])],
                         ["aware", "naive"])


if __name__ == "__main__":
    unittest.main()
