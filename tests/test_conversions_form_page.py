"""The page each form was sent from (#57): recorded beside the form's time
(visits.py), kept in conversions.sqlite's `visits.posts_from` (schema 11),
and used by conversions_pages.Finder when the trail's rounded times cannot
tell; counted again by audit_conversions_page.py. Example data only: site
example.com, RFC 5737 addresses, no real person."""
from __future__ import annotations

import json
import shutil
import sqlite3
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from support import CHROME, Sandbox, line  # noqa: E402

from skald import (audit_conversions, audit_conversions_page, audit_filled,  # noqa: E402
                         conversions_data, conversions_pages)
from skald.conversions import PAGE_UNKNOWN, store  # noqa: E402
from skald.people import visits as people_visits  # noqa: E402

UTC = timezone.utc
SITE = "example.com"
DAY = date(2026, 10, 20)
NOW = "2026-10-22T12:00:00Z"


def at(hms: str) -> str:
    return f"{DAY.isoformat()}T{hms}Z"


def post(when: datetime, referrer: str) -> str:
    return (f'{when.isoformat()} 203.0.113.60 example.com "POST /api/form HTTP/2.0" 200 64 '
            f'"{referrer}" "{CHROME}" 0.004 cc=CA ray=0-LHR\n')


class Recorded(unittest.TestCase):
    """visits.py keeps each form's same-site referrer, aligned with its time."""

    def test_a_collect_keeps_the_page_each_form_was_sent_from(self):
        box = Sandbox(mail=False)
        self.addCleanup(box.close)
        t = datetime(2026, 10, 6, 14, 0, tzinfo=UTC)
        box.log([line(t, "203.0.113.60", "/book/", country="CA"),
                 post(t + timedelta(seconds=20), "https://example.com/book/?step=2"),
                 post(t + timedelta(seconds=30), "https://elsewhere.example.net/form/"),
                 post(t + timedelta(seconds=40), "-")])
        code, _, err = box.run("--today", "2026-10-07", "collect")
        self.assertEqual(code, 0, err)
        db = sqlite3.connect(box.db.parent / store.FILE)
        self.addCleanup(db.close)
        posts, sent_from = db.execute(
            "SELECT posts, posts_from FROM visits WHERE ip = '203.0.113.60'").fetchone()
        self.assertEqual(len(json.loads(posts)), 3)
        self.assertEqual(json.loads(sent_from), ["/book/", "", ""],
                         "the path only; another site or no referrer is ''")

    def test_a_visit_counted_without_it_writes_null(self):
        journey = {"trail": [["/", True]], "at": [0], "pages": 1}
        when = datetime(2026, 10, 6, 14, 0, tzinfo=UTC)
        old, new = people_visits.rows(SITE, "2026-10-06", [journey, journey], [
            {"ip": "192.0.2.1", "posts": [when]},
            {"ip": "192.0.2.2", "posts": [when], "posts_from": ["/book/"]}])
        self.assertIsNone(old[-1])
        self.assertEqual(json.loads(new[-1]), ["/book/"])


class FormPage(unittest.TestCase):
    def setUp(self):
        self.folder = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.folder)
        self.path = self.folder / store.FILE
        self.db = store.connect(self.path)
        self.addCleanup(self.db.close)
        self.n = 0
        # A: the form at 2 min 5 s; /book/ is in its own 10-second step. Kept: sent from /book/.
        self.visit(0, at("09:00:00"), [["/", "page", 0], ["/pricing/", "page", 60],
                                       ["/book/", "page", 120]], [at("09:02:05")], ["/book/"])
        self.conv("demo", "completed", at("09:02:06"))
        # B: sent from a page the trail does not hold (its view was not kept).
        self.visit(1, at("10:00:00"), [["/", "page", 0], ["/blog/", "page", 120]],
                   [at("10:02:05")], ["/landing/"])
        self.conv("demo", "completed", at("10:02:06"))
        # C: the page read twice; the path runs to its last place at or before the form.
        self.visit(2, at("11:00:00"), [["/", "page", 0], ["/book/", "page", 30],
                                       ["/pricing/", "page", 40], ["/book/", "page", 50],
                                       ["/thanks/", "page", 70]], [at("11:00:55")], ["/book/"])
        self.conv("contact", "completed", at("11:00:56"))
        # D: a row kept before schema 11 (NULL): today's rule, its own step not told.
        self.visit(3, at("12:00:00"), [["/", "page", 0], ["/book/", "page", 120]],
                   [at("12:02:05")], None)
        self.conv("demo", "completed", at("12:02:06"))
        # E: a form sent with no referrer from this site (""): today's rule, under a minute.
        self.visit(4, at("13:00:00"), [["/", "page", 0], ["/contact/", "page", 20]],
                   [at("13:00:45")], [""])
        self.conv("contact", "completed", at("13:00:50"))
        self.db.execute("INSERT INTO visit_days (site, day, state, visits, pages, written_at) "
                        "VALUES (?, ?, 'whole', 5, 13, ?)", (SITE, DAY.isoformat(), NOW))
        self.db.commit()

    def conv(self, action, stage, when):
        self.n += 1
        self.db.execute("INSERT INTO conversions (site, action, stage, at, external_ref, tool, "
                        "received_at) VALUES (?, ?, ?, ?, ?, 'lead', ?)",
                        (SITE, action, stage, when, f"ref-{self.n}", when))

    def visit(self, seq, start, trail, posts, sent_from):
        self.db.execute("INSERT INTO visits (site, day, seq, ip, start, end, pages, trail, "
                        "posts, posts_from) VALUES (?, ?, ?, '(removed)', ?, ?, ?, ?, ?, ?)",
                        (SITE, DAY.isoformat(), seq, start, posts[-1], len(trail),
                         json.dumps(trail), json.dumps(posts),
                         None if sent_from is None else json.dumps(sent_from)))

    def day(self):
        per = conversions_data.figures(self.db, SITE, UTC, DAY, DAY, NOW, 24.0)
        return {"day": DAY.isoformat(), "state": "ok", **per[DAY.isoformat()]}

    def test_the_form_page_decides_where_kept(self):
        d = self.day()
        self.assertEqual(d["pages_at"], {"demo": {"/book/": 1, "/landing/": 1, PAGE_UNKNOWN: 1},
                                         "contact": {"/book/": 1, "/contact/": 1}})
        self.assertEqual(d["paths_to"]["demo"], {"/ → /pricing/ → /book/": 1,
                                                 "/ → /landing/": 1, PAGE_UNKNOWN: 1},
                         "in its own step: that page; not in the trail: the pages before, then it")
        self.assertEqual(d["paths_to"]["contact"], {"/ → /book/ → /pricing/ → /book/": 1,
                                                    "/ → /contact/": 1})
        self.assertEqual(d["page_link"], {"demo": {"server_log": 3},
                                          "contact": {"server_log": 2}},
                         "the roads keep their meaning")
        self.assertEqual(d["page_form"], {"demo": 2, "contact": 1})

    def test_an_old_row_keeps_the_old_answer(self):
        self.db.execute("UPDATE visits SET posts_from = NULL")
        d = self.day()
        self.assertEqual(d["pages_at"], {"demo": {PAGE_UNKNOWN: 3},
                                         "contact": {"/book/": 1, "/contact/": 1}})
        self.assertEqual(d["page_form"], {})

    def test_a_list_not_aligned_with_the_forms_is_not_used(self):
        self.db.execute("UPDATE visits SET posts_from = '[\"/book/\", \"/x/\"]' WHERE seq = 0")
        self.assertEqual(self.day()["pages_at"]["demo"], {"/landing/": 1, PAGE_UNKNOWN: 2})
        self.assertEqual(audit_conversions_page.check(self.path, SITE, UTC, DAY, DAY,
                                                      [self.day()]), {})

    def test_second_count_agrees_and_catches_a_planted_wrong_page(self):
        days = [self.day()]
        self.assertEqual(audit_conversions_page.check(self.path, SITE, UTC, DAY, DAY, days), {})
        days[0]["pages_at"]["demo"]["/book/"] -= 1
        days[0]["pages_at"]["demo"]["/pricing/"] = 1
        found = audit_conversions_page.check(self.path, SITE, UTC, DAY, DAY, days)
        self.assertIn("page demo /book/: file 0, SQL recount 1", "\n".join(found[DAY.isoformat()]))
        days = [self.day()]
        days[0]["page_form"]["contact"] = 2
        found = audit_conversions_page.check(self.path, SITE, UTC, DAY, DAY, days)
        self.assertIn("form contact page_form: file 2, SQL recount 1",
                      "\n".join(found[DAY.isoformat()]))

    def test_a_wrong_form_page_withholds_its_day(self):
        real = conversions_pages.Finder.where

        def lie(finder, row):
            road, page, trail, exact = real(finder, row)
            return (road, "/pricing/" if exact else page, trail, exact)

        with mock.patch.object(audit_conversions, "findings", return_value={}), \
                mock.patch.object(audit_filled, "check", return_value={}):
            good = conversions_data.blob({}, self.folder, SITE, UTC, DAY,
                                         datetime(2026, 10, 20, 18, 0, tzinfo=UTC))
            with mock.patch.object(conversions_pages.Finder, "where", lie):
                bad = conversions_data.blob({}, self.folder, SITE, UTC, DAY,
                                            datetime(2026, 10, 20, 18, 0, tzinfo=UTC))
        self.assertEqual(good["withheld"], {})
        self.assertIn(f"days/{DAY.isoformat()}", bad["withheld"])


class Schema11(unittest.TestCase):
    def setUp(self):
        self.folder = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.folder)
        self.path = self.folder / store.FILE

    def test_a_schema_10_file_upgrades_with_its_copy_kept(self):
        store.connect(self.path).close()
        db = sqlite3.connect(self.path)       # as Skald at schema 10 left it
        db.execute("ALTER TABLE visits DROP COLUMN posts_from")
        db.execute("UPDATE meta SET value = '10' WHERE key = 'schema_version'")
        db.execute("INSERT INTO visits (site, day, seq, ip, start, end, pages, trail, posts) "
                   "VALUES (?, ?, 0, '192.0.2.9', ?, ?, 1, '[]', ?)",
                   (SITE, DAY.isoformat(), at("09:00:00"), at("09:01:00"),
                    json.dumps([at("09:00:30")])))
        db.commit()
        db.close()
        db = store.connect(self.path)
        try:
            self.assertEqual(store.schema_version(db), 11)
            self.assertEqual([tuple(r) for r in db.execute(
                "SELECT ip, posts, posts_from FROM visits")],
                [("192.0.2.9", json.dumps([at("09:00:30")]), None)], "the old row stays, NULL")
        finally:
            db.close()
        copy = self.folder / f"{store.FILE}.v10.bak"
        self.assertTrue(copy.exists(), "a copy kept before the upgrade")
        old = sqlite3.connect(copy)
        try:
            self.assertEqual(old.execute("SELECT value FROM meta WHERE key = "
                                         "'schema_version'").fetchone()[0], "10")
            self.assertNotIn("posts_from", {r[1] for r in old.execute(
                "PRAGMA table_info(visits)")})
            self.assertEqual(old.execute("SELECT COUNT(*) FROM visits").fetchone()[0], 1)
        finally:
            old.close()

    def test_an_older_skald_refuses_a_schema_11_file_plainly(self):
        store.connect(self.path).close()
        with mock.patch.object(store, "SCHEMA_VERSION", 10):
            with self.assertRaisesRegex(RuntimeError, "conversions file is schema 11, this code "
                                        "understands 10; upgrade skald before reading"):
                store.connect(self.path)
        db = sqlite3.connect(self.path)
        try:
            self.assertEqual(db.execute("SELECT value FROM meta WHERE key = "
                                        "'schema_version'").fetchone()[0], "11", "untouched")
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
