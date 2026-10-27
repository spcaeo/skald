"""Traffic > Pages > a page: "did my change work?" (page_changes.py, todo_marks.py).

The marks (an append-only row per change, kept apart by page and day, stopped with
"open", the old table's rows kept when it is rebuilt), the windows (the same number of
whole days before and after, the day of the change in neither, at most 28, too early
until 14), what is not recorded (null, never 0), unequal coverage, the verdicts, the
leads from conversions.sqlite, the markers, and the second count
(audit_page_changes.py) agreeing and catching a wrong figure.

Every history row is written by SQL into a real history file, so the second count
reads the same file by its own road. Pages are paths on example.com; no address
anywhere.
"""
from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from skald import audit_page_changes, markers, page_changes, todo_marks  # noqa: E402
from skald.data_files import Page  # noqa: E402
from skald.store import History  # noqa: E402

UTC = timezone.utc
NOW = datetime(2026, 10, 25, 15, tzinfo=UTC)
TODAY = date(2026, 10, 25)
ANCHOR = date(2026, 10, 24)
SITE = "example.com"
PAGE = "/pricing/"


def landings(pages: dict, folded=0) -> dict:
    return {"fields": ["visits", "one_page", "views", "search", "ai"], "top": 200, "folded": folded,
            "pages": pages}


class Fixture:
    """A history file, the accounts file beside it, and (when asked) conversions.sqlite."""

    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.path = self.dir / "history.sqlite"
        History(self.path).db.close()
        self.db = sqlite3.connect(self.path)
        self.config = {"site": {"name": SITE, "hosts": [SITE]}, "report": {"timezone": "UTC"},
                       "_resolved": {"history_db": str(self.path), "live_dir": str(self.dir)}}
        self.accounts = sqlite3.connect(self.dir / "accounts.sqlite")

    def day(self, d: date, visits=0, one=0, search=0, ai=0, reads=0, verified=1, land=True, fetch=True,
            folded=0, page=PAGE):
        iso = d.isoformat()
        self.db.execute("INSERT OR REPLACE INTO days (site, day, timezone, collected_at, verified, parsed, hits, "
                        "other_hosts, cited_visits, extras) VALUES (?, ?, 'UTC', ?, ?, 0, 0, 0, 0, 1)",
                        (SITE, iso, NOW.isoformat(), verified))
        if land:
            rows = {"/": [3, 1, 5, 0, 0]}
            if visits:
                rows[page] = [visits, one, visits * 2, search, ai]
            self.db.execute("INSERT OR REPLACE INTO day_extras (site, day, kind, data) VALUES (?, ?, 'landings', ?)",
                            (SITE, iso, json.dumps(landings(rows, folded))))
        if fetch:
            # [minute, assistant, path, requests, reads]: two requests per read
            rows = [[f"{iso}T10:00", "chatgpt.com", "/pricing", reads * 2, reads]] if reads else []
            rows.append([f"{iso}T11:00", "claude.ai", "/other/", 2, 1])
            self.db.execute("INSERT OR REPLACE INTO day_extras (site, day, kind, data) VALUES (?, ?, 'ai_fetches', ?)",
                            (SITE, iso, json.dumps({"rows": rows})))
        self.db.commit()

    def mark(self, day: str, kind="title", note="New title", path=PAGE):
        return todo_marks.mark_change(self.accounts, SITE, path, day, kind, note, TODAY.isoformat(), 1,
                                      now=NOW)

    def page(self):
        return Page(History(self.path), SITE, SITE, None, UTC, NOW, None, self.config, live_dir=self.dir)

    def close(self):
        self.db.close()
        self.accounts.close()
        self.tmp.cleanup()


def fig(change: dict, key: str) -> dict:
    return next(f for f in change["figures"] if f["key"] == key)


class Marks(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")

    def test_a_change_is_one_row_per_page_and_day_and_never_deleted(self):
        a = todo_marks.mark_change(self.db, SITE, PAGE, "2026-10-01", "title", "  New\ttitle \n", "2026-10-25")
        self.assertEqual(a["note"], "New title")
        self.assertRegex(a["id"], r"^c[0-9a-f]{8}$")
        todo_marks.mark_change(self.db, SITE, PAGE, "2026-10-01", "content", "Added a pricing table", "2026-10-25")
        todo_marks.mark_change(self.db, SITE, PAGE, "2026-10-10", "redirect", "", "2026-10-25")
        got = todo_marks.changes(self.db, SITE)
        self.assertEqual([(c["day"], c["kind"]) for c in got], [("2026-10-10", "redirect"), ("2026-10-01", "content")])
        self.assertEqual(got[1]["note"], "Added a pricing table")
        todo_marks.stop_change(self.db, SITE, PAGE, "2026-10-10")
        self.assertEqual([c["day"] for c in todo_marks.changes(self.db, SITE)], ["2026-10-01"])
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM todo_marks").fetchone()[0], 4)
        # A page's change is not a to-do: current() never lists it, and mark() refuses it.
        self.assertEqual(todo_marks.current(self.db, SITE), {})
        with self.assertRaises(ValueError):
            todo_marks.mark(self.db, SITE, "page:/pricing/", "done", "2026-10-25")

    def test_what_a_change_may_be(self):
        for day, kind, path in (("2026-10-26", "title", PAGE),      # after today
                                ("2025-10-01", "title", PAGE),      # more than a year back
                                ("2026-13-01", "title", PAGE), ("yesterday", "title", PAGE),
                                ("2026-10-01", "new", PAGE), ("2026-10-01", "title", "pricing"),
                                ("2026-10-01", "title", "/a\nb")):
            with self.assertRaises(ValueError, msg=(day, kind, path)):
                todo_marks.mark_change(self.db, SITE, path, day, kind, "", "2026-10-25")
        long = todo_marks.mark_change(self.db, SITE, PAGE, "2026-10-25", "other", "x" * 500, "2026-10-25")
        self.assertEqual(len(long["note"]), todo_marks.NOTE_MOST)

    def test_an_older_table_is_rebuilt_with_every_row_kept(self):
        self.db.execute("CREATE TABLE todo_marks (site TEXT NOT NULL, item TEXT NOT NULL, state TEXT NOT NULL "
                        "CHECK (state IN ('done', 'notnow', 'fixed', 'open')), day TEXT NOT NULL, at TEXT NOT NULL, "
                        "by_user INTEGER)")
        self.db.execute("INSERT INTO todo_marks VALUES (?, 'lost-pages', 'done', '2026-10-20', '2026-10-20T10:00:00Z', 1)",
                        (SITE,))
        todo_marks.mark_change(self.db, SITE, PAGE, "2026-10-21", "title", "", "2026-10-25")
        self.assertEqual(todo_marks.current(self.db, SITE)["lost-pages"]["state"], "done")
        self.assertEqual(len(todo_marks.changes(self.db, SITE)), 1)


class Windows(unittest.TestCase):
    def test_the_same_whole_days_on_each_side_the_day_itself_in_neither(self):
        d = date(2026, 10, 4)
        before, after = page_changes.windows(d, ANCHOR)
        self.assertEqual((len(before), len(after)), (20, 20))
        self.assertEqual((before[0], before[-1], after[0], after[-1]),
                         (date(2026, 9, 14), date(2026, 10, 3), date(2026, 10, 5), ANCHOR))
        self.assertEqual([len(x) for x in page_changes.windows(date(2026, 8, 1), ANCHOR)], [28, 28])
        self.assertEqual(page_changes.windows(TODAY, ANCHOR), ([], []))
        self.assertEqual(page_changes.windows(ANCHOR, ANCHOR), ([], []))


class Figures(unittest.TestCase):
    def setUp(self):
        self.f = Fixture()

    def tearDown(self):
        self.f.close()

    def fill(self, change: date, before, after, **kw):
        for i, v in enumerate(before):
            self.f.day(change - timedelta(days=len(before) - i), **v, **kw)
        self.f.day(change, visits=50)                       # the day itself counts nowhere
        for i, v in enumerate(after):
            self.f.day(change + timedelta(days=i + 1), **v, **kw)

    def build(self):
        return page_changes.build(self.f.page())

    def test_a_clear_rise_and_fewer_leaving_at_once(self):
        change = ANCHOR - timedelta(days=20)
        self.fill(change, [{"visits": 2 + i % 2, "one": 2, "search": 1, "reads": 1} for i in range(20)],
                  [{"visits": 8 + i % 2, "one": 2, "search": 1, "reads": 1} for i in range(20)])
        self.f.mark(change.isoformat())
        body = self.build()
        self.assertTrue(body["marks"])
        self.assertEqual(body["withheld"], [])
        c = body["changes"][0]
        self.assertEqual((c["status"], c["days_after"], c["before"]["days"]), ("ready", 20, 20))
        self.assertEqual([r["side"] for r in c["days"]].count("change"), 1)
        v = fig(c, "visits")
        self.assertEqual((v["before"]["days"], v["before"]["total"], v["after"]["total"]), (20, 50, 170))
        self.assertEqual(v["before"]["per_day"], 2.5)
        self.assertEqual(v["verdict"], "up")
        self.assertEqual(v["change"]["pct"], 240)
        left = fig(c, "left")
        self.assertEqual((left["before"]["share"], left["verdict"]), (0.8, "down"))
        self.assertEqual(fig(c, "search")["verdict"], "no_clear_change")    # 1 a day, both sides
        self.assertEqual(fig(c, "reads")["after"]["total"], 20)            # "/pricing" is the same page
        self.assertEqual(fig(c, "ai")["verdict"], "too_few")                 # 0 on both sides
        # No conversions on this install: not recorded, never 0.
        self.assertIsNone(fig(c, "leads")["before"]["total"])
        self.assertEqual(fig(c, "leads")["verdict"], "not_recorded")
        self.assertEqual(c["days"][0]["leads_state"], "off")

    def test_too_early_until_fourteen_days(self):
        change = ANCHOR - timedelta(days=6)
        self.fill(change, [{"visits": 3}] * 6, [{"visits": 9}] * 6)
        self.f.mark(change.isoformat())
        c = self.build()["changes"][0]
        self.assertEqual((c["status"], c["days_after"]), ("too_early", 6))
        self.assertEqual({f["verdict"] for f in c["figures"]}, {"too_early"})
        self.assertEqual(c["verdict_on"], (change + timedelta(days=15)).isoformat())
        # Marked today: nothing to count yet.
        self.f.mark(TODAY.isoformat(), path="/new/")
        got = {x["path"]: x for x in self.build()["changes"]}
        self.assertEqual((got["/new/"]["status"], got["/new/"]["days_after"]), ("waiting", 0))

    def test_unequal_coverage_and_not_recorded_days(self):
        change = ANCHOR - timedelta(days=16)
        self.fill(change, [{"visits": 4, "one": 1}] * 16, [{"visits": 4, "one": 1}] * 16)
        for k in (3, 5, 7):                                  # three days before: not stored at all
            self.f.db.execute("DELETE FROM days WHERE day = ?", ((change - timedelta(days=k)).isoformat(),))
        self.f.db.execute("DELETE FROM day_extras WHERE day = ? AND kind = 'landings'",
                          ((change + timedelta(days=2)).isoformat(),))   # an after day without landings
        self.f.day(change + timedelta(days=4), visits=4, verified=0)      # withheld: never summed
        self.f.db.commit()
        self.f.mark(change.isoformat())
        c = self.build()["changes"][0]
        v = fig(c, "visits")
        self.assertEqual((v["before"]["days"], v["after"]["days"], v["unequal"]), (13, 14, True))
        self.assertEqual(v["verdict"], "no_clear_change")
        self.assertEqual((c["before"]["whole"], c["after"]["whole"]), (13, 15))
        gap = next(r for r in c["days"] if r["day"] == (change + timedelta(days=2)).isoformat())
        self.assertEqual((gap["state"], gap["visits"], gap["reads"]), ("ok", None, 0))
        held = next(r for r in c["days"] if r["day"] == (change + timedelta(days=4)).isoformat())
        self.assertEqual((held["state"], held["visits"]), ("withheld", None))

    def test_a_page_outside_the_kept_top_pages_is_a_floor(self):
        change = ANCHOR - timedelta(days=15)
        self.fill(change, [{"visits": 0}] * 15, [{"visits": 3}] * 15, folded=4)
        self.f.mark(change.isoformat())
        c = self.build()["changes"][0]
        self.assertTrue(fig(c, "visits")["before"]["at_least"])
        self.assertFalse(fig(c, "visits")["after"]["at_least"])

    def test_the_second_count_catches_a_wrong_figure(self):
        change = ANCHOR - timedelta(days=15)
        self.fill(change, [{"visits": 3, "reads": 1}] * 15, [{"visits": 5, "reads": 2}] * 15)
        self.f.mark(change.isoformat())
        p = self.f.page()
        marks = todo_marks.changes(self.f.accounts, SITE)
        found = page_changes.figures(p.history, p.key, p.anchor, marks, None)
        self.assertEqual(audit_page_changes.check(p, found, None), {})
        found[0]["days"][3]["visits"] += 1
        fig(found[0], "reads")["after"]["total"] += 1
        fig(found[0], "visits")["verdict"] = "no_clear_change"
        held = audit_page_changes.check(p, found, None)[found[0]["id"]]
        self.assertTrue(any("visits shown" in x for x in held), held)
        self.assertTrue(any("reads after total" in x for x in held), held)
        self.assertTrue(any("visits verdict" in x for x in held), held)
        # In the file: the change is left out and named.
        with mock.patch.object(page_changes, "side", lambda rows, m: {**_side(rows, m), "days": 0}):
            body = page_changes.build(self.f.page())
        self.assertEqual(body["changes"], [])
        self.assertEqual(body["withheld"][0]["path"], PAGE)

    def test_a_mark_the_file_leaves_out_is_caught(self):
        change = ANCHOR - timedelta(days=15)
        self.fill(change, [{"visits": 3}] * 15, [{"visits": 5}] * 15)
        self.f.mark(change.isoformat())
        self.f.mark(change.isoformat(), path="/about/")
        p = self.f.page()
        found = page_changes.figures(p.history, p.key, p.anchor, todo_marks.changes(self.f.accounts, SITE)[:1], None)
        self.assertTrue(audit_page_changes.check(p, found, None))

    def test_without_accounts_nothing_is_tracked(self):
        self.f.accounts.close()
        (self.f.dir / "accounts.sqlite").unlink()
        self.f.accounts = sqlite3.connect(":memory:")
        body = self.build()
        self.assertEqual((body["marks"], body["changes"]), (False, []))

    def test_a_page_group_is_the_whole_sites(self):
        p = self.f.page()
        p.view = object()
        self.assertEqual(page_changes.build(p), {"whole_site_only": True})

    def test_the_change_is_a_marker_on_every_chart(self):
        self.f.mark("2026-10-21", kind="content", note="Added a pricing table")
        got = markers.page_changes(self.f.config, SITE, self.f.dir, NOW, UTC)
        self.assertEqual((got[0]["day"], got[0]["kind"]), ("2026-10-21", "page_change"))
        self.assertEqual(got[0]["label"], "/pricing/: content update, Added a pricing table")


_side = page_changes.side


class Leads(unittest.TestCase):
    """Leads that landed on the page, from conversions.sqlite through conversions.json."""

    def setUp(self):
        self.f = Fixture()
        from skald.conversions import store
        self.store = store
        self.change = ANCHOR - timedelta(days=15)
        for k in range(-15, 16):
            self.f.day(self.change + timedelta(days=k), visits=4, one=2)
        db = store.connect(self.f.dir / "conversions.sqlite")
        n = 0
        for k in range(-15, 16):
            for _ in range(1 if k < 0 else 3 if k > 0 else 0):
                n += 1
                at = datetime.combine(self.change + timedelta(days=k), datetime.min.time(), UTC) + timedelta(hours=12)
                store.record_conversion(db, {"site": SITE, "action": "signup", "stage": "completed",
                                             "at": store.stamp(at), "external_ref": f"L{n}", "tool": "lead",
                                             "source_type": "Search", "landing": "/pricing/?ref=ad",
                                             "received_at": store.stamp(at)})
        store.record_conversion(db, {"site": SITE, "action": "signup", "stage": "completed",
                                     "at": store.stamp(NOW - timedelta(days=3)), "external_ref": "other",
                                     "tool": "lead", "landing": "/about/", "received_at": store.stamp(NOW)})
        db.close()
        self.f.mark(self.change.isoformat())

    def tearDown(self):
        self.f.close()

    def test_leads_before_and_after(self):
        with mock.patch("skald.audit_conversions.findings", return_value={}):
            body = page_changes.build(self.f.page())
        self.assertEqual(body["withheld"], [])
        c = body["changes"][0]
        leads = fig(c, "leads")
        self.assertEqual((leads["before"]["total"], leads["after"]["total"]), (15, 45))
        self.assertEqual(leads["verdict"], "up")

    def test_the_second_count_catches_a_wrong_lead_count(self):
        from skald import conversions_data
        p = self.f.page()
        with mock.patch("skald.audit_conversions.findings", return_value={}):
            conv = conversions_data.build(p)
        found = page_changes.figures(p.history, p.key, p.anchor, todo_marks.changes(self.f.accounts, SITE), conv)
        self.assertEqual(audit_page_changes.check(p, found, conv), {})
        row = next(r for r in found[0]["days"] if r["leads"])
        row["leads"] += 1
        self.assertTrue(any("leads shown" in x for x in audit_page_changes.check(p, found, conv)[found[0]["id"]]))
        # A day shown without a figure that conversions do record: caught too.
        row["leads"], row["leads_state"] = None, "before"
        self.assertTrue(any("leads not shown" in x for x in audit_page_changes.check(p, found, conv)[found[0]["id"]]))


if __name__ == "__main__":
    unittest.main()
