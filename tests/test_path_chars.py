"""Whole page paths (#71, skald/path_names.py).

Every figure keyed by a page kept only a path's first 70 characters. On a live
visitor drawer (16 Nov 2026) an 82-character blog address was drawn as its first
70 and opened as a page not found; two articles that differ only after the 70th
character were counted as one row. What is pinned:

  * both roads keep a path up to PATH_CHARS: an 82-character page stays whole,
    two pages that differ after character 70 stay two rows, and a longer path
    (a probe) is cut at PATH_CHARS; a collected day with them recounts exactly;
  * no module cuts at 70 any more, path_names.py holds numbers only, and the
    dashboard's pathnames.js has the same numbers;
  * the AI alerts do not call a long page "started" or "stopped" only because
    older days kept its first 70 characters (alerts_ai._known);
  * llms.txt still leaves out a path of exactly 70 characters (it may be cut).

Addresses are RFC 5737, hosts example.com.
"""
from __future__ import annotations

import ast
import re
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald import alerts_ai, path_names  # noqa: E402
from skald.classify import Group  # noqa: E402
from skald.path_names import OLD_PATH_CHARS, PATH_CHARS  # noqa: E402

from support import UTC, Sandbox, day_lines, line, totals_for  # noqa: E402
from test_visits import DAY  # noqa: E402

LONG = "/blog/five-features-every-route-planning-tool-needs-for-trash-valet-services"
SIBLING = LONG + "-2026"                      # the same first 70 characters, another article
PROBE = "/" + "x" * (PATH_CHARS + 100)
T = datetime(2026, 10, 5, 10, 0, tzinfo=UTC)
SITE = "https://example.com"

LINES = [
    line(T, "203.0.113.20", LONG, referrer="https://www.google.com/"),
    line(T + timedelta(seconds=40), "203.0.113.20", SIBLING, referrer=SITE + LONG),
    line(T + timedelta(minutes=3), "203.0.113.21", SIBLING, referrer="https://www.google.com/"),
    line(T + timedelta(minutes=5), "203.0.113.22", PROBE, status=404),
]


class TheNumbers(unittest.TestCase):

    def test_the_fixture_is_what_it_says(self):
        self.assertGreater(len(LONG), OLD_PATH_CHARS)
        self.assertEqual(LONG[:OLD_PATH_CHARS], SIBLING[:OLD_PATH_CHARS])

    def test_path_names_holds_numbers_only(self):
        tree = ast.parse(Path(path_names.__file__).read_text())
        self.assertFalse([n for n in ast.walk(tree)
                          if isinstance(n, (ast.FunctionDef, ast.ClassDef, ast.Import, ast.ImportFrom))])
        self.assertEqual((PATH_CHARS, OLD_PATH_CHARS), (512, 70))

    def test_no_module_cuts_a_path_at_70_any_more(self):
        found = [f"{p.relative_to(ROOT)}:{i}" for p in (ROOT / "skald").rglob("*.py")
                 for i, text in enumerate(p.read_text().splitlines(), 1)
                 if re.search(r"\[:\s*70\s*\]|slice\(0,\s*70\)", text)]
        found += [f"{p.relative_to(ROOT)}:{i}" for p in (ROOT / "skald" / "webapp" / "js").rglob("*.js")
                  for i, text in enumerate(p.read_text().splitlines(), 1)
                  if re.search(r"slice\(0,\s*70\)|substring\(0,\s*70\)", text)]
        self.assertEqual(found, [])

    def test_the_dashboard_has_the_same_numbers(self):
        js = (ROOT / "skald" / "webapp" / "js" / "pathnames.js").read_text()
        got = {k: int(v) for k, v in re.findall(r"export const (\w+) = (\d+);", js)}
        self.assertEqual(got, {"PATH_CHARS": PATH_CHARS, "OLD_PATH_CHARS": OLD_PATH_CHARS})


class MainRoad(unittest.TestCase):

    def setUp(self):
        self.totals = totals_for(day_lines(DAY, 0) + LINES)
        self.people = self.totals.groups[Group.PEOPLE]

    def test_a_long_page_keeps_every_character(self):
        self.assertEqual(self.people.pages[LONG], 1)
        self.assertNotIn(LONG[:OLD_PATH_CHARS], self.people.pages)

    def test_two_pages_that_differ_after_70_stay_two_rows(self):
        self.assertEqual(self.people.pages[SIBLING], 2)
        landings = sorted(j["landing"] for j in self.totals.journeys)
        self.assertEqual(landings, [LONG, SIBLING])
        (first,) = [j for j in self.totals.journeys if j["landing"] == LONG]
        self.assertEqual([p for p, _ in first["trail"]], [LONG, SIBLING])

    def test_a_longer_path_is_cut_at_path_chars(self):
        self.assertEqual([len(p) for p in self.people.not_found], [PATH_CHARS])


class CollectedDay(unittest.TestCase):

    def test_a_day_with_long_paths_recounts_exactly(self):
        box = Sandbox()
        try:
            box.log(day_lines(DAY, 2) + LINES)
            code, _, err = box.run("--today", "2026-10-06", "collect", "--day", "2026-10-05")
            self.assertEqual(code, 0, err)
            code, out, err = box.run("--today", "2026-10-06", "audit", "--day", "2026-10-05")
            self.assertEqual(code, 0, err)
            self.assertIn("all match", out)
        finally:
            box.close()


class AlertsAcrossTheChange(unittest.TestCase):
    """Days counted before #71 kept LONG as its first 70 characters."""

    def test_a_long_page_is_the_same_page_as_its_old_cut_name(self):
        cut = LONG[:OLD_PATH_CHARS]
        self.assertTrue(alerts_ai._known(LONG, {cut}))       # not "started reading"
        self.assertTrue(alerts_ai._known(cut, {LONG}))       # not "stopped reading"
        self.assertTrue(alerts_ai._known(LONG, {LONG}))

    def test_other_pages_are_still_new(self):
        self.assertFalse(alerts_ai._known(LONG, {"/pricing"}))
        self.assertFalse(alerts_ai._known("/pricing", {LONG}))
        self.assertFalse(alerts_ai._known(LONG, {LONG[:OLD_PATH_CHARS - 1]}))


if __name__ == "__main__":
    unittest.main()
