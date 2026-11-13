"""Where each finished conversion happened (#52): conversions_pages.py's
`pages_at`, `paths_to` and `page_link` in conversions.json, and their second
count (audit_conversions_page.py), which withholds a day it disagrees with.
Example data only: site example.com, made-up visitor IDs, no address."""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from skald import (audit_conversions, audit_conversions_page, audit_filled,  # noqa: E402
                         conversions_data, conversions_pages)
from skald.conversions import PAGE_NOT_KEPT, PAGE_UNKNOWN, store  # noqa: E402

UTC = timezone.utc
SITE = "example.com"
DAY, NEXT = date(2026, 10, 20), date(2026, 10, 21)
NOW = "2026-10-22T12:00:00Z"


def at(day: date, hms: str) -> str:
    return f"{day.isoformat()}T{hms}Z"


class Pages(unittest.TestCase):
    def setUp(self):
        self.folder = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.folder)
        self.path = self.folder / store.FILE
        self.db = store.connect(self.path)
        self.addCleanup(self.db.close)
        self.n = 0
        # A: an earlier visit, then /, /pricing/ twice, /demo/, and a demo booked.
        for when, page in (("08:00:00", "/blog/"), ("10:00:00", "/"), ("10:05:00", "/pricing/"),
                           ("10:06:00", "/pricing/"), ("10:10:00", "/demo/")):
            self.view("skv_A", at(DAY, when), page)
        self.conv("demo", "completed", at(DAY, "10:12:00"), vid="skv_A")
        self.conv("demo", "started", at(DAY, "10:11:00"), vid="skv_A")      # not finished
        self.conv("demo", "completed", at(DAY, "10:12:30"), vid="skv_A", test=1)  # a test row
        # B: a visitor ID last seen two hours before its payment: no visit holds it.
        self.view("skv_B", at(DAY, "09:00:00"), "/")
        self.conv("paid", "paid", at(DAY, "11:00:00"), vid="skv_B")
        # C: a server-log visit sends its form at 45 s; the thank-you page comes after.
        self.visit(0, at(DAY, "12:00:00"), [["/", "page", 0], ["/contact/", "page", 20],
                                            ["/thanks/", "page", 46]], [at(DAY, "12:00:45")])
        self.conv("contact", "completed", at(DAY, "12:00:50"))
        # D: a form at 2 min 5 s, a page seen in the same 10-second step: not told.
        self.visit(1, at(DAY, "13:00:00"), [["/", "page", 0], ["/book/", "page", 120]],
                   [at(DAY, "13:02:05")])
        self.conv("demo", "completed", at(DAY, "13:02:06"))
        # E: two visits send a form at the same time: none is proven.
        self.visit(2, at(DAY, "14:00:00"), [["/a/", "page", 0]], [at(DAY, "14:00:03")])
        self.visit(3, at(DAY, "14:00:01"), [["/b/", "page", 0]], [at(DAY, "14:00:04")])
        self.conv("contact", "completed", at(DAY, "14:00:05"))
        # F: the next day keeps no server-log visit.
        self.conv("contact", "completed", at(NEXT, "09:00:00"))
        # G: a long visit, twelve pages: only the last ten are written.
        for i in range(12):
            self.view("skv_G", at(NEXT, f"10:{i:02d}:00"), f"/p{i}/")
        self.conv("signup", "completed", at(NEXT, "10:12:00"), vid="skv_G")
        self.db.execute("INSERT INTO visit_days (site, day, state, visits, pages, written_at) "
                        "VALUES (?, ?, 'whole', 4, 7, ?)", (SITE, DAY.isoformat(), NOW))
        self.db.commit()

    def view(self, vid, when, page):
        self.db.execute("INSERT INTO journeys (vid, site, at, path, source_type) VALUES "
                        "(?, ?, ?, ?, 'Search engine')", (vid, SITE, when, page))

    def conv(self, action, stage, when, vid=None, test=0):
        self.n += 1
        self.db.execute("INSERT INTO conversions (site, action, stage, at, vid, external_ref, "
                        "tool, received_at, test) VALUES (?, ?, ?, ?, ?, ?, 'lead', ?, ?)",
                        (SITE, action, stage, when, vid, f"ref-{self.n}", when, test))

    def visit(self, seq, start, trail, posts):
        self.db.execute("INSERT INTO visits (site, day, seq, ip, start, end, pages, trail, "
                        "posts) VALUES (?, ?, ?, '(removed)', ?, ?, ?, ?, ?)",
                        (SITE, DAY.isoformat(), seq, start, posts[-1], len(trail),
                         json.dumps(trail), json.dumps(posts)))

    def days(self):
        per = conversions_data.figures(self.db, SITE, UTC, DAY, NEXT, NOW, 24.0)
        return [{"day": d.isoformat(), "state": "ok", **per[d.isoformat()]} for d in (DAY, NEXT)]

    def test_page_path_and_link(self):
        one, two = self.days()
        self.assertEqual(one["pages_at"], {"demo": {"/demo/": 1, PAGE_UNKNOWN: 1},
                                           "paid": {PAGE_UNKNOWN: 1},
                                           "contact": {"/contact/": 1, PAGE_UNKNOWN: 1}})
        self.assertEqual(one["paths_to"]["demo"], {"/ → /pricing/ → /demo/": 1, PAGE_UNKNOWN: 1},
                         "a page read twice in a row is once; the earlier visit is not in it")
        self.assertEqual(one["paths_to"]["contact"], {"/ → /contact/": 1, PAGE_UNKNOWN: 1})
        self.assertEqual(one["page_link"], {"demo": {"visitor_id": 1, "server_log": 1},
                                            "paid": {"none": 1},
                                            "contact": {"server_log": 1, "none": 1}})
        self.assertEqual(two["pages_at"], {"contact": {PAGE_NOT_KEPT: 1}, "signup": {"/p11/": 1}})
        self.assertEqual(list(two["paths_to"]["signup"]),
                         ["… → " + " → ".join(f"/p{i}/" for i in range(2, 12))])
        # Every finished row counts once in each block, never dropped.
        for d in (one, two):
            for block in ("pages_at", "paths_to", "page_link"):
                self.assertEqual({a: sum(v.values()) for a, v in d[block].items()},
                                 {a: sum(v.values()) for a, v in d["by"]["tool"].items()})

    def test_second_count_agrees_and_catches_a_planted_mismatch(self):
        days = self.days()
        self.assertEqual(audit_conversions_page.check(self.path, SITE, UTC, DAY, NEXT, days), {})
        days[0]["pages_at"]["demo"]["/demo/"] += 1
        days[1]["paths_to"]["signup"] = {"/p11/": 1}
        found = audit_conversions_page.check(self.path, SITE, UTC, DAY, NEXT, days)
        self.assertEqual(sorted(found), [DAY.isoformat(), NEXT.isoformat()])
        self.assertIn("page demo /demo/: file 2, SQL recount 1", found[DAY.isoformat()][0])

    def test_a_wrong_page_withholds_its_day(self):
        """Through conversions.json's own check (audit_conversions.check_file)."""
        good = self.blob()
        self.assertEqual(good["withheld"], {})
        real = conversions_pages.Finder.where

        def lie(finder, row):
            road, page, trail, exact = real(finder, row)
            return (road, "/elsewhere/" if page == "/demo/" else page, trail, exact)

        with mock.patch.object(conversions_pages.Finder, "where", lie):
            got = self.blob()
        self.assertIn(f"days/{DAY.isoformat()}", got["withheld"])
        self.assertIn("audit_conversions.py", got["withheld"][f"days/{DAY.isoformat()}"])
        self.assertEqual(next(d for d in got["days"] if d["day"] == NEXT.isoformat())["state"],
                         "ok", "the other day stands")

    def blob(self):
        # The rows here are written by hand, with no hook spool and no touch filled:
        # only those two other checks are set aside, every other one runs.
        with mock.patch.object(audit_conversions, "findings", return_value={}), \
                mock.patch.object(audit_filled, "check", return_value={}):
            return conversions_data.blob({}, self.folder, SITE, UTC, NEXT,
                                         datetime(2026, 10, 22, 12, 0, tzinfo=UTC))


if __name__ == "__main__":
    unittest.main()
