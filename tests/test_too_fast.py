"""Too fast to be a person (too_fast.py, audit_too_fast.py, CLASSIFICATION.md rule 9b).

Found on the live site on 14 Oct 2026: a visit counted as a person read 17
pages, all at second 0 of the visit. Pinned here: that visit moves to bots,
whole, as "too fast to be a person", and the groups still add up to the log;
a fast clicker (3 pages in 2 s), 5 pages in a second, 6 pages over 10 s and a
fast start followed by slower reading all stay people; the rule's two
settings; a visit that never rendered stays NOT_RENDERED; and the audit's own
road agrees ("all match") and catches a changed figure.

Also here: the Recent requests feed calls the script tag's posts to Skald's
own endpoints what they are, never "form post".
"""
from __future__ import annotations

import ast
import json
import sqlite3
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald import Group  # noqa: E402
from skald.classify import NOT_RENDERED, TOO_FAST, Classifier  # noqa: E402
from skald.parse import Hit  # noqa: E402
from skald import requests_feed  # noqa: E402
from skald.store import History  # noqa: E402
from skald.window import analyse_window, day_window  # noqa: E402

from support import CHROME, UTC, Sandbox, line  # noqa: E402

DAY = date(2026, 10, 14)
TODAY = "2026-10-15"
CONFIG = {"site": {"hosts": ["example.com"]}}
SAFARI = ("Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 "
          "(KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1")


def at(hour, minute=0, second=0):
    return datetime(DAY.year, DAY.month, DAY.day, hour, minute, second, tzinfo=UTC)


def asset(when, address, agent=CHROME, page="/"):
    return line(when, address, "/_next/static/css/app.css", agent, f"https://example.com{page}")


def pages(address, start, offsets, agent=CHROME, rendered=True):
    """A page at each offset (seconds from `start`), in time order, and the
    first page's stylesheet in the same second when `rendered`."""
    out = [line(start + timedelta(seconds=s), address, f"/p{i}/", agent)
           for i, s in enumerate(offsets)]
    if rendered:
        out.insert(1, asset(start + timedelta(seconds=offsets[0]), address, agent, "/p0/"))
    return out


def count(lines, config=None):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "access.log"
        path.write_text("".join(lines))
        start, end = day_window(DAY, UTC)
        return analyse_window(config or CONFIG, start, end, paths=[path])


def people(totals):
    g = totals.groups.get(Group.PEOPLE)
    return (g.hits, g.visits, g.readers) if g else (0, 0, 0)


def bots_named(totals, name):
    g = totals.groups.get(Group.BOTS)
    return g.agents.get(name, 0) if g else 0


class TestTooFast(unittest.TestCase):

    def test_seventeen_pages_in_one_second_are_a_bot_and_the_groups_add_up(self):
        # The live case: 17 pages, every one at second 0 of the visit.
        fast = pages("203.0.113.10", at(10), [0] * 17)
        real = pages("203.0.113.11", at(11), [0, 40])
        totals = count(fast + real)
        self.assertEqual(people(totals), (3, 1, 1))
        self.assertEqual(bots_named(totals, TOO_FAST), 18)
        self.assertEqual(totals.extras["bots"]["too_fast"],
                         {"requests": 18, "pages": 17, "readers": 1})
        self.assertEqual(totals.extras["bots"]["not_rendered"]["requests"], 0)
        self.assertEqual(sum(g.hits for g in totals.groups.values()), len(fast + real))
        self.assertEqual(totals.groups[Group.PEOPLE].views, 2)

    def test_a_fast_clicker_stays_a_person(self):
        totals = count(pages("203.0.113.20", at(10), [0, 1, 2]))      # 3 pages in 2 s
        self.assertEqual(people(totals), (4, 1, 1))
        self.assertEqual(totals.extras["bots"]["too_fast"]["requests"], 0)

    def test_below_the_count_or_slower_than_the_limit_stays_a_person(self):
        for offsets in ([0, 0, 0, 1, 1],              # 5 pages in a second
                        [0, 2, 4, 6, 8, 10],          # 6 pages over 10 s
                        [0, 0, 0, 1, 1, 1, 3]):       # 7 pages, the last at 3 s
            with self.subTest(offsets=offsets):
                totals = count(pages("203.0.113.30", at(10), offsets))
                self.assertEqual(people(totals)[1:], (1, 1))
                self.assertEqual(bots_named(totals, TOO_FAST), 0)

    def test_a_fast_start_then_slower_reading_stays_a_person(self):
        # Six pages at once (tabs restored, say), then a page a minute later:
        # the visit's pages are not all inside the limit.
        totals = count(pages("203.0.113.40", at(10), [0, 0, 0, 0, 0, 0, 60]))
        self.assertEqual(people(totals)[1:], (1, 1))

    def test_six_pages_inside_two_seconds_is_the_edge(self):
        totals = count(pages("203.0.113.41", at(10), [0, 0, 1, 1, 2, 2]))
        self.assertEqual(people(totals), (0, 0, 0))
        self.assertEqual(totals.extras["bots"]["too_fast"]["readers"], 1)

    def test_the_rule_is_per_visit(self):
        # The same browser comes back after the session gap and reads slowly.
        fast = pages("203.0.113.42", at(9), [0] * 8)
        later = pages("203.0.113.42", at(12), [0, 30])
        totals = count(fast + later)
        self.assertEqual(people(totals), (3, 1, 1))
        self.assertEqual(totals.extras["bots"]["too_fast"]["requests"], 9)

    def test_the_settings(self):
        fast = pages("203.0.113.50", at(10), [0] * 8)
        off = count(fast, {"site": {"hosts": ["example.com"], "too_fast_pages": 0}})
        self.assertEqual(people(off)[1:], (1, 1))
        clicker = pages("203.0.113.51", at(10), [0, 1, 2])
        strict = count(clicker, {"site": {"hosts": ["example.com"], "too_fast_pages": 3}})
        self.assertEqual(people(strict), (0, 0, 0))
        wide = count(pages("203.0.113.52", at(10), [0, 2, 4, 6, 8, 10]),
                     {"site": {"hosts": ["example.com"], "too_fast_seconds": 10}})
        self.assertEqual(people(wide), (0, 0, 0))

    def test_a_visit_that_never_rendered_stays_not_rendered(self):
        totals = count(pages("203.0.113.60", at(10), [0] * 10, rendered=False))
        self.assertEqual((bots_named(totals, NOT_RENDERED), bots_named(totals, TOO_FAST)),
                         (10, 0))

    def test_redirects_are_not_pages(self):
        # Three pages, each through a trailing-slash redirect: 6 lines, 3 pages.
        lines = []
        for i in range(3):
            lines.append(line(at(10, 0, i), "203.0.113.70", f"/p{i}", status=301))
            lines.append(line(at(10, 0, i), "203.0.113.70", f"/p{i}/"))
        lines.insert(2, asset(at(10, 0, 0), "203.0.113.70", page="/p0/"))
        totals = count(lines)
        self.assertEqual(people(totals)[1:], (1, 1))


class TestBothRoads(unittest.TestCase):
    """collect, then the audit's own road: all match."""

    def setUp(self):
        self.box = Sandbox()

    def tearDown(self):
        self.box.close()

    def run_day(self):
        code, _, err = self.box.run("--today", TODAY, "collect", "--day", DAY.isoformat())
        self.assertEqual(code, 0, err)
        return self.box.run("--today", TODAY, "audit", "--day", DAY.isoformat())

    def stored(self):
        with History(self.box.db) as h:
            row = h.db.execute("SELECT hits, visits, readers FROM groups WHERE site = ? AND "
                               "day = ? AND grp = 'people'",
                               ("example.com", DAY.isoformat())).fetchone()
            bots = h.extras("example.com", DAY, DAY)[DAY.isoformat()]["bots"]
        return tuple(row or (0, 0, 0)), bots["too_fast"]

    def test_the_audit_agrees(self):
        self.box.log(pages("203.0.113.10", at(10), [0] * 17)          # the live case
                     + pages("203.0.113.11", at(11), [0, 1, 2])        # a fast clicker
                     + pages("203.0.113.12", at(12), [0, 30, 90], SAFARI))
        code, out, err = self.run_day()
        self.assertEqual(code, 0, err + out)
        self.assertIn("all match", out)
        (hits, visits, readers), moved = self.stored()
        self.assertEqual((visits, readers), (2, 2))
        self.assertEqual(moved, {"requests": 18, "pages": 17, "readers": 1})

    def test_the_audit_catches_a_changed_figure(self):
        self.box.log(pages("203.0.113.10", at(10), [0] * 8))
        code, _, err = self.box.run("--today", TODAY, "collect", "--day", DAY.isoformat())
        self.assertEqual(code, 0, err)
        db = sqlite3.connect(str(self.box.db))
        with db:
            raw = db.execute("SELECT data FROM day_extras WHERE kind = 'bots'").fetchone()[0]
            blob = json.loads(raw)
            blob["too_fast"]["readers"] += 1
            db.execute("UPDATE day_extras SET data = ? WHERE kind = 'bots'", (json.dumps(blob),))
        db.close()
        code, out, err = self.box.run("--today", TODAY, "audit", "--day", DAY.isoformat())
        self.assertEqual(code, 1)
        self.assertIn("too fast to be a person: readers", err)


class TestIndependence(unittest.TestCase):

    def test_the_audits_rule_shares_only_a_name_list(self):
        from skald import audit_too_fast
        tree = ast.parse(Path(audit_too_fast.__file__).read_text())
        got = {(n.module, a.name) for n in ast.walk(tree)
               if isinstance(n, ast.ImportFrom) and n.level for a in n.names}
        self.assertEqual(got, {("classify", "OTHER_BOT")})


class TestOwnEndpointsInTheFeed(unittest.TestCase):
    """Skald's own endpoints are never "form post" (parse.OWN_ENDPOINT)."""

    def test_kinds_and_rules(self):
        c = Classifier()
        cases = [("/traffic-beacon", "script_event", "people: script tag event"),
                 ("/traffic-js/e", "script_event", "people: script tag event"),
                 ("/traffic-hooks/example.com/cal", "skald_endpoint", "people: Skald endpoint"),
                 ("/traffic-ingest/example.com", "skald_endpoint", "people: Skald endpoint"),
                 ("/contact", "post", "people: form post"),
                 # A page's own script (form_names.py): on the list, or a 204 with no body.
                 ("/api/events", "page_script", "people: page's own script (not a form)"),
                 ("/contact?204", "page_script", "people: page's own script (not a form)")]
        for path, kind, rule in cases:
            with self.subTest(path=path):
                status = "204" if path.endswith("?204") else "200"
                hit = Hit(at(10), "203.0.113.5", "example.com", "POST", path, status,
                          "https://example.com/", CHROME)
                got = requests_feed.row(hit, c(hit), UTC, lambda ip: False, False)
                self.assertEqual((got["kind"], got["rule"], got["page_view"]), (kind, rule, False))
        self.assertNotIn("form", requests_feed.KIND_WORDS["script_event"])


if __name__ == "__main__":
    unittest.main()
