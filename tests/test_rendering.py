"""A browser-like visit counts as a person only if a browser drew the page.

Pinned here (rendering.py, audit_rendered.py, CLASSIFICATION.md rule 9,
COUNTING-TRAPS.md trap 9): a real browser visit; a page-only scraper sending
a browser agent; a cached browser seen rendering earlier that day, or a
reader on an earlier day; a visit vouched for by the beacon alone; and a page
whose assets arrive the next second, or out of order in the log. The
independent recount agrees with what is stored, and the figures say how many
browser-like requests were moved.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald import Group  # noqa: E402
from skald.classify import NOT_RENDERED  # noqa: E402
from skald.store import History  # noqa: E402
from skald.window import analyse_window, day_window  # noqa: E402

from support import CHROME, UTC, Sandbox, line  # noqa: E402

DAY = date(2026, 10, 5)
TODAY = "2026-10-06"
FIREFOX = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:151.0) Gecko/20100101 Firefox/151.0"
KEY = {"SKALD_VISITOR_KEY": "test-key-not-secret"}
CONFIG = {"site": {"hosts": ["example.com"]}}


def at(hour, minute=0, second=0, day=DAY):
    return datetime(day.year, day.month, day.day, hour, minute, second, tzinfo=UTC)


def asset(when, address, name="app.css", agent=CHROME):
    return line(when, address, f"/_next/static/css/{name}", agent, "https://example.com/")


def count(lines, config=None):
    """The day's totals with the rule on, from these lines."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "access.log"
        path.write_text("".join(lines))
        start, end = day_window(DAY, UTC)
        return analyse_window(config or CONFIG, start, end, paths=[path])


def people(totals):
    g = totals.groups.get(Group.PEOPLE)
    return (g.hits, g.visits, g.readers) if g else (0, 0, 0)


class TestWhoRendered(unittest.TestCase):

    def test_a_real_browser_visit_counts(self):
        totals = count([line(at(10), "203.0.113.10", "/pricing/"),
                        asset(at(10, 0, 1), "203.0.113.10"),
                        asset(at(10, 0, 1), "203.0.113.10", "main.js")])
        self.assertEqual(people(totals), (3, 1, 1))
        self.assertEqual(totals.groups[Group.BOTS].hits if Group.BOTS in totals.groups else 0, 0)

    def test_a_page_only_scraper_is_a_bot_and_is_counted_as_one(self):
        totals = count([line(at(10), "203.0.113.20", "/", FIREFOX),
                        line(at(10, 5), "203.0.113.21", "/pricing/", CHROME)])
        self.assertEqual(people(totals), (0, 0, 0))
        bots = totals.groups[Group.BOTS]
        self.assertEqual((bots.hits, bots.agents[NOT_RENDERED]), (2, 2))
        moved = totals.extras["bots"]["not_rendered"]
        self.assertEqual(moved, {"requests": 2, "pages": 2, "readers": 2})

    def test_the_next_second_and_out_of_order_lines_still_render(self):
        # A streamed page is logged when it ends: its stylesheet's line can
        # come first, stamped a second or two earlier.
        totals = count([asset(at(10, 0, 3), "203.0.113.30"),
                        line(at(10, 0, 5), "203.0.113.30", "/guides/alpha"),
                        line(at(11), "203.0.113.31", "/"),
                        asset(at(11, 0, 1), "203.0.113.31")])
        self.assertEqual(people(totals)[2], 2)

    def test_assets_long_after_the_page_or_images_alone_do_not_count(self):
        totals = count([line(at(10), "203.0.113.40", "/"),
                        asset(at(10, 2), "203.0.113.40"),          # two minutes later
                        line(at(12), "203.0.113.41", "/"),
                        line(at(12, 0, 1), "203.0.113.41", "/og/home.png"),
                        line(at(12, 0, 1), "203.0.113.41", "/favicon.ico")])
        self.assertEqual(people(totals), (0, 0, 0))
        self.assertEqual(totals.extras["bots"]["not_rendered"]["readers"], 2)

    def test_a_framework_payload_is_rendering_too(self):
        totals = count([line(at(10), "203.0.113.42", "/"),
                        line(at(10, 0, 2), "203.0.113.42", "/pricing/?_rsc=abc12")])
        self.assertEqual(people(totals)[2], 1)

    def test_a_cached_browser_that_rendered_earlier_that_day_counts(self):
        totals = count([line(at(9), "203.0.113.50", "/"),
                        asset(at(9, 0, 1), "203.0.113.50"),
                        # Back four hours later: everything cached, page only.
                        line(at(13), "203.0.113.50", "/pricing/")])
        self.assertEqual(people(totals), (3, 2, 2))

    def test_rendering_later_does_not_vouch_for_an_earlier_visit(self):
        totals = count([line(at(9), "203.0.113.51", "/"),
                        line(at(13), "203.0.113.51", "/pricing/"),
                        asset(at(13, 0, 1), "203.0.113.51")])
        self.assertEqual(people(totals), (2, 1, 1))
        self.assertEqual(totals.extras["bots"]["not_rendered"]["readers"], 1)

    def test_one_page_that_rendered_carries_its_whole_visit(self):
        totals = count([line(at(10), "203.0.113.52", "/"),
                        line(at(10, 5), "203.0.113.52", "/pricing/"),
                        asset(at(10, 5, 1), "203.0.113.52")])
        self.assertEqual(people(totals), (3, 1, 1))
        self.assertEqual(totals.groups[Group.PEOPLE].views, 2)

    def test_the_rule_can_be_switched_off(self):
        totals = count([line(at(10), "203.0.113.20", "/")],
                       {"site": {"hosts": ["example.com"], "require_rendering": False}})
        self.assertEqual(people(totals), (1, 1, 1))

    def test_other_asset_folders_can_be_named(self):
        config = {"site": {"hosts": ["example.com"], "asset_prefixes": ["/assets/"]}}
        totals = count([line(at(10), "203.0.113.20", "/"),
                        line(at(10, 0, 1), "203.0.113.20", "/assets/site.css")], config)
        self.assertEqual(people(totals)[2], 1)


class RenderingBox(unittest.TestCase):
    """A sandbox with the rule on, the beacon on, and the audit run."""

    def setUp(self):
        self.box = Sandbox()
        text = self.box.config.read_text().replace("  require_rendering: false\n", "")
        self.box.config.write_text(text + "beacon:\n  enabled: true\n")
        self.spool = self.box.root / "beacon"
        self.spool.mkdir()

    def tearDown(self):
        self.box.close()

    def beacon(self, day, rows):
        with open(self.spool / f"{day.isoformat()}.jsonl", "a") as handle:
            for row in rows:
                handle.write(json.dumps(row) + "\n")

    def collect(self, day=DAY, today=TODAY):
        code, _, err = self.box.run("--today", today, "collect", "--day", day.isoformat())
        self.assertEqual(code, 0, err)

    def audit(self, day=DAY, today=TODAY):
        code, out, err = self.box.run("--today", today, "audit", "--day", day.isoformat())
        self.assertEqual(code, 0, err + out)
        self.assertIn("all match", out)

    def stored(self, day=DAY):
        with History(self.box.db) as h:
            row = h.db.execute("SELECT hits, visits, readers FROM groups WHERE site = ? AND "
                               "day = ? AND grp = 'people'",
                               ("example.com", day.isoformat())).fetchone()
            bots = h.extras("example.com", day, day)[day.isoformat()]["bots"]
        return tuple(row or (0, 0, 0)), bots["not_rendered"]


class TestBeaconAndAudit(RenderingBox):

    def test_a_beacon_only_visit_counts_once_and_the_audit_agrees(self):
        self.box.log([
            line(at(10), "203.0.113.10", "/pricing/"),             # real, assets cached
            line(at(10, 0, 1), "203.0.113.99", "/pricing/", FIREFOX),  # a scraper, same page
            line(at(11), "203.0.113.11", "/"),
            asset(at(11, 0, 1), "203.0.113.11"),
            line(at(12), "203.0.113.12", "/guides/alpha", FIREFOX),  # page only
        ])
        # One page opening on /pricing/ at 10:00 (event 7 s in): vouches for
        # the nearest visit only, never for both.
        self.beacon(DAY, [{"at": at(10, 0, 7).isoformat(), "e": "cta_click", "g": "people",
                           "id": "demo_header", "p": "/pricing/", "r": "", "s": "Direct or unknown",
                           "t": 7, "u": "", "vw": "lg"},
                          {"at": at(10, 0, 9).isoformat(), "e": "scroll_75", "g": "people",
                           "p": "/pricing/", "r": "", "s": "Direct or unknown", "t": 9, "u": "",
                           "vw": "lg"}])
        self.collect()
        (hits, visits, readers), moved = self.stored()
        self.assertEqual((hits, visits, readers), (3, 2, 2))
        self.assertEqual(moved, {"requests": 2, "pages": 2, "readers": 2})
        self.audit()

    def test_an_uncounted_page_opening_vouches_too(self):
        """2.10.1: a page_view the beacon does not count as an event (no
        beacon-only mode, no visitor IDs) is kept in the opens file. A
        returning phone with every asset cached is a reader on both roads."""
        from skald import beacon
        self.box.log([line(at(10), "203.0.113.30", "/privacy/"),          # assets cached
                      line(at(10, 0, 5), "203.0.113.30", "/story/"),
                      line(at(12), "203.0.113.31", "/guides/alpha", FIREFOX)])  # a scraper
        with open(beacon.opens_file(self.spool, DAY), "a") as handle:
            handle.write(json.dumps({"at": at(10, 0, 1).isoformat(), "g": "people",
                                     "e": "page_view", "p": "/privacy/", "t": 0}) + "\n")
        self.collect()
        (hits, visits, readers), moved = self.stored()
        self.assertEqual((hits, visits, readers), (2, 1, 1))
        self.assertEqual(moved["readers"], 1)
        self.audit()

    def test_the_audit_catches_a_changed_figure(self):
        self.box.log([line(at(10), "203.0.113.12", "/"),
                      line(at(11), "203.0.113.11", "/"), asset(at(11, 0, 1), "203.0.113.11")])
        self.collect()
        import sqlite3
        db = sqlite3.connect(str(self.box.db))
        with db:
            raw = db.execute("SELECT data FROM day_extras WHERE kind = 'bots'").fetchone()[0]
            blob = json.loads(raw)
            blob["not_rendered"]["readers"] += 1
            db.execute("UPDATE day_extras SET data = ? WHERE kind = 'bots'", (json.dumps(blob),))
        db.close()
        code, out, err = self.box.run("--today", TODAY, "audit", "--day", DAY.isoformat())
        self.assertEqual(code, 1)
        self.assertIn("browser-like, never rendered: readers", err)


class TestReturningReader(RenderingBox):

    def test_a_reader_on_an_earlier_day_counts_with_a_cached_page(self):
        d1, d2 = date(2026, 10, 4), DAY
        self.box.log([
            line(at(9, day=d1), "203.0.113.50", "/"), asset(at(9, 0, 1, day=d1), "203.0.113.50"),
            line(at(9, day=d1), "203.0.113.70", "/"),             # never rendered
            line(at(9, day=d2), "203.0.113.50", "/pricing/"),     # back, page only
            line(at(9, 5, day=d2), "203.0.113.70", "/pricing/"),  # still page only
        ])
        with mock.patch.dict(os.environ, KEY):
            self.collect(d1, d2.isoformat())
            self.collect(d2)
            self.assertEqual(self.stored(d1)[0][2], 1)
            (hits, visits, readers), moved = self.stored(d2)
            self.assertEqual(readers, 1)
            self.assertEqual(moved["readers"], 1)
            self.audit(d2)
            self.audit(d1, d2.isoformat())

    def test_live_today_and_its_audit(self):
        today = date(2026, 10, 6)
        self.box.log([line(at(8, day=today), "203.0.113.10", "/"),
                      asset(at(8, 0, 1, day=today), "203.0.113.10"),
                      line(at(8, 2, day=today), "203.0.113.20", "/", FIREFOX)])
        with mock.patch("skald.cli._now", return_value=at(12, day=today)):
            self.assertEqual(self.box.run("live")[0], 0)
            code, out, err = self.box.run("audit", "--live")
            self.assertEqual(code, 0, err + out)
        snap = json.loads((self.box.root / "live-example.com.json").read_text())
        self.assertEqual(snap["people"]["readers"], 1)
        self.assertEqual(snap["extras"]["bots"]["not_rendered"]["readers"], 1)


class TestRecount(unittest.TestCase):

    def test_a_forced_backfill_takes_away_a_scrapers_first_visitor(self):
        box = Sandbox()
        try:
            box.log([line(at(9), "203.0.113.99", "/guides/alpha", FIREFOX),   # scraper
                     line(at(10), "203.0.113.10", "/"), asset(at(10, 0, 1), "203.0.113.10")])
            code, _, err = box.run("--today", TODAY, "collect", "--day", DAY.isoformat())
            self.assertEqual(code, 0, err)

            def humans():
                with History(box.db) as h:
                    return sorted(p for p, kind, *_ in h.milestones("example.com")
                                  if kind == "human")
            self.assertEqual(humans(), ["/", "/guides/alpha"])     # the old rule
            box.config.write_text(box.config.read_text().replace(
                "  require_rendering: false\n", ""))
            code, out, err = box.run("--today", TODAY, "backfill", "--days", "1", "--force")
            self.assertEqual(code, 0, err)
            self.assertIn("page milestones rebuilt", out)
            self.assertEqual(humans(), ["/"])
            code, out, err = box.run("--today", TODAY, "audit", "--day", DAY.isoformat())
            self.assertEqual(code, 0, err + out)
        finally:
            box.close()


class TestIndependence(unittest.TestCase):

    def test_the_audits_rule_shares_only_a_name_list(self):
        import ast
        from skald import audit_rendered
        source = Path(audit_rendered.__file__).read_text()
        imported = set()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.ImportFrom) and node.level:
                imported |= {(node.module, a.name) for a in node.names}
        self.assertLessEqual(imported, {("classify", "OTHER_BOT")})


if __name__ == "__main__":
    unittest.main()
