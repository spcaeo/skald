"""Overview > Insights shows only open problems (#5, #6) and Skald's own addresses are no
lost page (#16).

  * #16: /traffic-beacon, /traffic-js/, /traffic-hooks/ and /traffic-ingest/ (any case, with
    or without a trailing slash) are never a lost page, a Markdown ask or an address a
    re-check counts, on both roads (lost_pages.kind_of and audit_todos._sort); a look-alike
    (/traffic-beaconx/, /traffic/) stays a page;
  * a marked to-do's card status comes from its daily re-check of the log only: a live check
    that found every address fixed still shows "failed" while the log finds the problem (the
    sitemap case seen on one site, 2 to 8 Nov); the re-check names the addresses still failing;
  * the second count recounts those addresses and the status, and catches a nudged one;
  * #23: an old address only bots ask for (no person since the mark, no live page like it)
    is named apart and never fails a lost-pages fix; a person's ask, or a live page to send
    it to, keeps it failing; both roads agree and a nudged list or status is caught.

Every history row is written by SQL into a real history file (test_todos.Fixture), so the
second count reads the same file by its own road. Hosts are example.com; no address anywhere.
"""
from __future__ import annotations

import sys
import unittest
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald import audit_todos, lost_pages, todo_marks, todos  # noqa: E402

from test_todos import ANCHOR, NOW, SITE, Fixture, nf, served  # noqa: E402

OURS = ["/traffic-beacon", "/traffic-beacon/", "/Traffic-Beacon/", "/traffic-beacon?x=1",
        "/traffic-js/skald.js", "/traffic-js", "/traffic-hooks/example.com/journey", "/traffic-ingest/"]
LOOK_ALIKES = ["/traffic-beaconx/", "/traffic/", "/traffic-jsx/"]


class OwnAddresses(unittest.TestCase):
    """#16: Skald's own endpoints are never the site's lost pages."""

    def setUp(self):
        self.f = Fixture()
        self.f.sitemap(["/", "/pricing/"])
        for i in range(3):
            d = ANCHOR - timedelta(days=2 - i)
            rows = [nf(p, 4, "ai_training") for p in OURS] + [nf(p, 2, "people") for p in OURS[:2]]
            rows += [nf(p, 3, "search_engines") for p in LOOK_ALIKES] + [nf("/traffic-beacon.md", 2, "ai_asked")]
            self.f.day(d, rows, {"/": served(views=5)})

    def tearDown(self):
        self.f.close()

    def test_both_roads_leave_them_out(self):
        for path in OURS:
            self.assertIsNone(lost_pages.kind_of(path), path)
            self.assertIsNone(audit_todos._sort(path), path)
        for path in LOOK_ALIKES:
            self.assertEqual((lost_pages.kind_of(path), audit_todos._sort(path)), ("page", "page"), path)
        self.assertEqual(lost_pages.kind_of("/traffic-beacon.md"), "markdown", "a .md copy is the site's own")

    def test_lost_pages_and_the_audit_agree(self):
        p = self.f.page()
        body = lost_pages.build(p)
        self.assertEqual(body["withheld"], [])
        self.assertEqual({r["path"] for r in body["lost"]}, set(LOOK_ALIKES), "the look-alikes stay; ours move out")
        self.assertEqual((body["totals"]["people"], body["totals"]["search"], body["totals"]["ai"]), (0, 27, 0))
        found = lost_pages.Found(p)
        self.assertEqual(audit_todos.check_lost(p.history.db, SITE, found.first, found.last, body, found), [])
        # A beacon row slipped back into the list: the second count names it.
        body["lost"].append({"path": "/traffic-beacon/", "people": 6, "search": 0, "ai": 12})
        why = audit_todos.check_lost(p.history.db, SITE, found.first, found.last, body, found)
        self.assertTrue(why and "second count" in why[0], why)

    def test_the_recheck_never_counts_them(self):
        db = self.f.accounts()
        todo_marks.mark(db, SITE, "lost-pages", "done", (ANCHOR - timedelta(days=1)).isoformat())
        db.close()
        p = self.f.page()
        got = {t["id"]: t for t in todos.build(p)["todos"]}
        r = got["lost-pages"]["recheck"]
        # The day after the mark: the 3 look-alikes, 3 asks each; no beacon ask counted.
        self.assertEqual(r["figures"], {"asked": 9})
        self.assertEqual(r["still"], [[path, 3] for path in sorted(LOOK_ALIKES)])
        # Only search engines ask for the look-alikes and no live page is like them: bots only
        # (#23), so they are named but never fail the fix.
        self.assertEqual(r["bots_only"], sorted(LOOK_ALIKES))
        self.assertEqual(got["lost-pages"]["status"], "passed")


class StatusFromTheLog(unittest.TestCase):
    """#5, #6: the card's status, and the addresses a failed fix still has."""

    def setUp(self):
        self.f = Fixture()
        self.f.sitemap(["/", "/pricing/"])
        self.mark = (ANCHOR - timedelta(days=2)).isoformat()
        for i in range(4):
            d = ANCHOR - timedelta(days=3 - i)
            rows = [nf("/news_sitemap.xml", 2, "ai_training")]
            if d.isoformat() <= self.mark:      # fixed on the mark's day: these two stop
                rows += [nf("/sitemap-a.xml", 2, "search_engines"), nf("/sitemap-b.xml", 2, "ai_training")]
            self.f.day(d, rows, {"/": served(views=5)},
                       counts=[("server_error_page", "/", 3), ("status_bots", "5xx", 3)] if i < 2 else [])

    def tearDown(self):
        self.f.close()

    def build(self):
        p = self.f.page()
        return p, todos.build(p)

    def test_open_then_failed_even_after_a_passing_live_check(self):
        p, body = self.build()
        got = {t["id"]: t for t in body["todos"]}
        self.assertEqual(got["sitemap"]["status"], "open")
        self.assertEqual(got["sitemap"]["figures"]["paths"], 3)
        db = self.f.accounts()
        todo_marks.mark(db, SITE, "sitemap", "done", self.mark)
        todo_marks.mark_checked(db, SITE, "sitemap", True, self.mark)     # the one live check passed
        todo_marks.mark(db, SITE, "server-errors", "done", self.mark)
        db.close()
        p, body = self.build()
        self.assertEqual(body["withheld"], [])
        got = {t["id"]: t for t in body["todos"]}
        sm = got["sitemap"]
        self.assertIn(sm["state"], ("fixed", "done"))
        self.assertEqual(sm["recheck"]["verdict"], "not_yet")
        self.assertEqual(sm["status"], "failed", "the log decides, not the live check")
        self.assertEqual((sm["recheck"]["still"], sm["recheck"]["still_total"]), ([["/news_sitemap.xml", 4]], 1))
        # 1 of 3 sitemaps is still missing: both figures are in the file.
        self.assertEqual((sm["recheck"]["still_total"], sm["figures"]["paths"]), (1, 3))
        # Server errors stopped after the mark: passed; still names nothing.
        er = got["server-errors"]
        self.assertEqual((er["status"], er["recheck"]["still"], er["recheck"]["still_total"]), ("passed", [], 0))

    def test_waiting_is_checking_and_not_now_stays(self):
        db = self.f.accounts()
        todo_marks.mark(db, SITE, "sitemap", "done", ANCHOR.isoformat())
        todo_marks.mark(db, SITE, "server-errors", "notnow", ANCHOR.isoformat())
        db.close()
        _, body = self.build()
        got = {t["id"]: t for t in body["todos"]}
        self.assertEqual(got["sitemap"]["status"], "checking", "no whole day after the mark yet")
        self.assertEqual(got["server-errors"]["status"], "notnow")
        self.assertEqual(todos.status_of({"state": "open"}), "open")

    def test_the_second_count_recounts_the_addresses_and_the_status(self):
        db = self.f.accounts()
        todo_marks.mark(db, SITE, "sitemap", "done", self.mark)
        db.close()
        p, body = self.build()
        held = lambda: audit_todos.check_todos(p.history.db, SITE, body["todos"], p.live_dir, p.anchor.isoformat())  # noqa: E731
        self.assertEqual(held(), {})
        sm = next(t for t in body["todos"] if t["id"] == "sitemap")
        sm["status"] = "passed"                                   # a nudged status
        self.assertIn("the status", held()["sitemap"])
        sm["status"] = "failed"
        sm["recheck"]["still"] = [["/news_sitemap.xml", 3]]       # a nudged address figure
        self.assertIn("addresses", held()["sitemap"])
        sm["recheck"]["still"] = [["/news_sitemap.xml", 4]]
        sm["recheck"]["still_total"] = 2                          # a nudged count
        self.assertIn("addresses", held()["sitemap"])


class BotsOnly(unittest.TestCase):
    """#23: addresses only bots ask for never fail a lost-pages fix."""

    def setUp(self):
        self.f = Fixture()
        self.f.sitemap(["/", "/pricing/", "/twenty-crm-consulting/"])
        self.mark = (ANCHOR - timedelta(days=2)).isoformat()

    def tearDown(self):
        self.f.close()

    def days(self, after_rows):
        """Four days: before the mark, every address asked; after it, `after_rows`."""
        before = [nf("/twenty-crm-services/", 6, "ai_training"), nf("/wp-/", 4, "search_engines"),
                  nf("/_astro/", 4, "search_engines"), nf("/old-launch/", 5, "people")]
        for i in range(4):
            d = ANCHOR - timedelta(days=3 - i)
            self.f.day(d, before if d.isoformat() <= self.mark else after_rows,
                       {"/": served(views=5), "/twenty-crm-consulting/": served(views=2)})

    def marked(self):
        db = self.f.accounts()
        todo_marks.mark(db, SITE, "lost-pages", "done", self.mark)
        db.close()
        p = self.f.page()
        body = todos.build(p)
        return p, body, next(t for t in body["todos"] if t["id"] == "lost-pages")

    def test_only_bots_left_passes(self):
        self.days([nf("/wp-/", 2, "search_engines"), nf("/_astro/", 1, "ai_training")])
        p, body, t = self.marked()
        r = t["recheck"]
        self.assertEqual((r["still_total"], r["bots_only"]), (2, ["/_astro/", "/wp-/"]))
        self.assertEqual((r["verdict"], t["status"]), ("fixed", "passed"))
        self.assertEqual(audit_todos.check_todos(p.history.db, SITE, body["todos"], p.live_dir,
                                                 p.anchor.isoformat()), {})

    def test_a_page_to_send_it_to_or_a_person_keeps_it_failing(self):
        for rows, failing in (([nf("/twenty-crm-services/", 3, "ai_training"), nf("/wp-/", 2, "search_engines")],
                               "/twenty-crm-services/"),          # a live page like it: send it there
                              ([nf("/old-launch/", 1, "people"), nf("/wp-/", 2, "search_engines")],
                               "/old-launch/")):           # no page like it, but a person asked
            with self.subTest(failing):
                self.tearDown()
                self.setUp()
                self.days(rows)
                p, body, t = self.marked()
                self.assertEqual(t["recheck"]["bots_only"], ["/wp-/"])
                self.assertIn(failing, [x[0] for x in t["recheck"]["still"]])
                self.assertEqual(t["status"], "failed")
                self.assertEqual(audit_todos.check_todos(p.history.db, SITE, body["todos"], p.live_dir,
                                                         p.anchor.isoformat()), {})

    def test_the_second_count_catches_a_nudged_list_or_status(self):
        self.days([nf("/twenty-crm-services/", 3, "ai_training"), nf("/wp-/", 2, "search_engines")])
        p, body, t = self.marked()
        held = lambda: audit_todos.check_todos(p.history.db, SITE, body["todos"], p.live_dir,  # noqa: E731
                                               p.anchor.isoformat())
        self.assertEqual(held(), {})
        t["recheck"]["bots_only"] = ["/twenty-crm-services/", "/wp-/"]     # a real page called a probe
        self.assertIn("only bots", held()["lost-pages"])
        t["recheck"]["bots_only"] = ["/wp-/"]
        t["status"] = "passed"                                       # a nudged status
        self.assertIn("the status", held()["lost-pages"])


if __name__ == "__main__":
    unittest.main()
