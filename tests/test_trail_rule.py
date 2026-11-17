"""Trail rule 2 (#62, skald/trail_names.py): referrers that are not a move.

Pages loaded ahead of a click (Chrome's speculation rules, checked in Chrome on
16 Nov 2026) made journeys read "pricing, consulting, implementation, pricing,
consulting, implementation", three steps "seen in the browser" and "under 1 s"
between them. What is pinned:

  * the live visit's request pattern (times, paths and referrers; test address,
    example.com) now reads pricing, consulting, implementation, no browser step;
  * the Back button, then a click elsewhere, is still a browser step;
  * a move inside a site that navigates in the browser, to a page loaded long
    before, is still a browser step; two pages from the same page seconds apart
    are still a move back;
  * the audit's own road (audit_visits.trail_of) reads every case the same, and
    a collected day with them recounts exactly.

Addresses are RFC 5737, hosts example.com.
"""
from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald import audit_visits  # noqa: E402
from skald.trail_names import OWN_FILES_SECONDS, TOGETHER_SECONDS  # noqa: E402

from support import CHROME, UTC, Sandbox, day_lines, line, totals_for  # noqa: E402
from test_visits import DAY  # noqa: E402

T = datetime(2026, 10, 5, 10, 31, 17, tzinfo=UTC)
SITE = "https://example.com"
P, C, I, O = "/pricing-plans/", "/consulting/", "/implementation/", "/onboarding/"


def visit(address: str, reqs: list[tuple[int, str, str]]) -> list[str]:
    """Lines for (seconds after T, path, referrer: a path on the site, or a full URL)."""
    return [line(T + timedelta(seconds=s), address, path, CHROME,
                 ref if ref.startswith("http") else SITE + ref) for s, path, ref in reqs]


# The live visit (13 Nov), its assets trimmed to one or two per page.
LOADED_AHEAD = visit("203.0.113.77", [
    (0, P, "https://www.google.com/"),
    (0, "/_astro/layout.css", P),
    (1, "/_astro/pricing.avif", P),
    (97, C, P),                              # consulting ...
    (97, I, P),                              # ... and implementation, the same second, from pricing
    (98, "/_astro/consulting.avif", C),
    (98, "/_astro/form.js", C),
    (247, "/_astro/implementation.avif", I),
])
# Consulting, Back to pricing (no request: the browser's cache), then onboarding.
BACK = visit("203.0.113.78", [
    (0, P, "https://www.google.com/"),
    (1, "/_astro/pricing.avif", P),
    (20, C, P),
    (21, "/_astro/consulting.avif", C),
    (60, O, P),                              # its referrer: pricing, gone back to
])
# A site that navigates in the browser: / loaded, then /features/ in the browser
# (an RSC payload, no page), then later a request from / again, long after it loaded.
IN_BROWSER = visit("203.0.113.79", [
    (0, "/", "https://www.google.com/"),
    (1, "/_next/static/a.js", "/"),
    (40, "/_next/static/b.js", "/features/"),
    (40 + OWN_FILES_SECONDS + 30, "/_next/static/c.js", "/"),
])
# Two pages from the same page, but seconds apart: a real move back between them.
APART = visit("203.0.113.80", [
    (0, P, "https://www.google.com/"),
    (10, C, P),
    (10 + TOGETHER_SECONDS + 3, I, P),
])


def trail(lines) -> list[tuple[str, str]]:
    totals = totals_for(day_lines(DAY, 0) + lines)
    (j,) = [j for j in totals.journeys if j["landing"] in (P, "/")]
    return [tuple(x) for x in j["trail"]], j


class MainRoad(unittest.TestCase):

    def test_pages_loaded_ahead_read_as_three_pages(self):
        got, j = trail(LOADED_AHEAD)
        self.assertEqual(got, [(P, "page"), (C, "page"), (I, "page")])
        self.assertEqual((j["pages"], j["seen"], j["in_app"], j["seconds"]), (3, 3, 0, 247))

    def test_the_back_button_is_still_a_browser_step(self):
        got, j = trail(BACK)
        self.assertEqual(got, [(P, "page"), (C, "page"), (P, "app"), (O, "page")])
        self.assertEqual(j["in_app"], 1)

    def test_a_move_in_the_browser_is_still_seen(self):
        got, _ = trail(IN_BROWSER)
        self.assertEqual(got, [("/", "page"), ("/features/", "app"), ("/", "app")])

    def test_pages_seconds_apart_are_still_a_move_back(self):
        got, _ = trail(APART)
        self.assertEqual(got, [(P, "page"), (C, "page"), (P, "app"), (I, "page")])


class AuditRoad(unittest.TestCase):
    """audit_visits.trail_of, on the same lines, by its own code."""

    @staticmethod
    def seen(lines):
        rows = []
        for raw in lines:
            parts = raw.split(" ")
            when = datetime.fromisoformat(parts[0])
            path = parts[4]
            ref = raw.split('"')[3]
            rows.append(SimpleNamespace(when=when, path=path, referrer=ref, status="200",
                                        host="example.com"))
        recount = audit_visits.VisitRecount({"example.com"})
        page = lambda l: "." not in l.path.rsplit("/", 1)[-1] and "/_" not in l.path  # noqa: E731
        got, _, moved = audit_visits.trail_of(rows, page, recount._where)
        return got, moved

    def test_each_case_reads_the_same_as_the_main_road(self):
        for lines in (LOADED_AHEAD, BACK, IN_BROWSER, APART):
            with self.subTest(first=lines[0][:40]):
                main, j = trail(lines)
                got, moved = self.seen(lines)
                self.assertEqual(got, [p for p, _ in main])
                self.assertEqual(moved, j["in_app"])


class CollectedDay(unittest.TestCase):

    def test_a_day_with_every_case_recounts_exactly(self):
        box = Sandbox()
        try:
            box.log(day_lines(DAY, 2) + LOADED_AHEAD + BACK + IN_BROWSER + APART)
            code, _, err = box.run("--today", "2026-10-06", "collect", "--day", "2026-10-05")
            self.assertEqual(code, 0, err)
            code, out, err = box.run("--today", "2026-10-06", "audit", "--day", "2026-10-05")
            self.assertEqual(code, 0, err)
            self.assertIn("all match", out)
        finally:
            box.close()


if __name__ == "__main__":
    unittest.main()
