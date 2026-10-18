"""Retention cohorts (retention.py): who is the same visitor under each
privacy setting, new and back by the site's own weeks, inputs that expire,
the page's file, the visitors behind a cell, and the audit's agreement
(audit_retention.py).
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald import audit_retention, retention as rt, retention_page  # noqa: E402
from skald.conversions import store  # noqa: E402
from skald.store import History  # noqa: E402

from support import GPTBOT, NY, UTC, Sandbox, line  # noqa: E402

SITE = "example.com"
A, B, C, X = "203.0.113.30", "203.0.113.31", "203.0.113.32", "203.0.113.33"
MON = date(2026, 9, 7)                      # a Monday
KEY = {"SKALD_VISITOR_KEY": "ef" * 32}


# ------------------------------------------------------------------ a kept store

class Stores:
    """A history and a conversions.sqlite written by hand: whole days of kept visits."""

    def __init__(self, keep_days: int = 395, keep_ips: bool = True) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.history = History(self.root / "history.sqlite")
        self.cdb = store.connect(self.root / store.FILE)
        self.config = {"site": {"name": SITE, "hosts": [SITE]},
                       "privacy": {"keep_ips": keep_ips, "keep_days": keep_days},
                       "history": {"db": str(self.root / "history.sqlite")}}
        self.seq: dict[str, int] = {}

    def close(self) -> None:
        self.cdb.close()
        self.history.close()
        self.tmp.cleanup()

    def days(self, first: date, last: date) -> None:
        d = first
        while d <= last:
            self.cdb.execute("INSERT OR IGNORE INTO visit_days (site, day, state, visits, pages, "
                             "written_at) VALUES (?, ?, 'whole', 0, 0, '2026-01-01T00:00:00Z')",
                             (SITE, d.isoformat()))
            d += timedelta(days=1)
        self.cdb.commit()

    def visit(self, day: date, ip: str, pages: int = 1, source: str = "Direct or unknown",
              hour: int = 12, country: str = "US", landing: str = "/", browser: str = "Chrome",
              device: str = "Desktop") -> None:
        seq = self.seq.get(day.isoformat(), 0)
        self.seq[day.isoformat()] = seq + 1
        start = datetime(day.year, day.month, day.day, hour, tzinfo=UTC)
        self.cdb.execute(
            "INSERT INTO visits (site, day, seq, ip, user_agent, start, end, source, landing, "
            "country, device, browser, os, pages, seconds, trail, posts) VALUES "
            "(?, ?, ?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, 'macOS', ?, 30, '[]', '[]')",
            (SITE, day.isoformat(), seq, ip, store.stamp(start),
             store.stamp(start + timedelta(minutes=1)), source, landing, country, device,
             browser, pages))
        self.cdb.commit()

    def record(self, today: date, keyed=None):
        return rt.record(self.config, self.root, self.history.db, SITE, today, keyed)

    def blob(self, kind: str, day: date) -> dict | None:
        row = self.history.db.execute("SELECT data FROM day_extras WHERE site = ? AND day = ? "
                                      "AND kind = ?", (SITE, day.isoformat(), kind)).fetchone()
        return json.loads(row[0]) if row else None

    def audit(self, today: date, on: str | None = "x") -> dict:
        return audit_retention.check(self.history.db, self.cdb, SITE, today, on)


class Rule(unittest.TestCase):
    def test_lookback_and_reach(self):
        self.assertEqual((rt.lookback(395), rt.reach(395)), (332, 62))
        self.assertEqual((rt.lookback(30), rt.reach(30)), (15, 14))
        self.assertEqual((rt.lookback(90), rt.reach(90)), (45, 44))
        for h in (1, 7, 30, 60, 126, 200, 395, 730):
            self.assertEqual(rt.lookback(h), audit_retention._rule(h), h)

    def test_weeks_start_on_monday(self):
        self.assertEqual(rt.week_of(date(2026, 9, 13)), MON)          # a Sunday
        self.assertEqual(rt.week_of(date(2026, 9, 14)), date(2026, 9, 14))
        # Only weeks that are over: on a Saturday the week is not.
        self.assertEqual(rt.starts("week", date(2026, 9, 19), 2), [date(2026, 8, 31), MON])
        self.assertEqual(rt.starts("week", date(2026, 9, 20), 1), [date(2026, 9, 14)])


class Identity(unittest.TestCase):
    def setUp(self):
        self.s = Stores()

    def tearDown(self):
        self.s.close()

    def test_kept_addresses_come_first(self):
        got = rt.identity(self.s.config, self.s.root, keyed=True)
        self.assertEqual((got["by"], got["horizon"], got["lookback"]), ("address", 395, 332))

    def test_the_30_day_code_without_kept_addresses(self):
        self.s.config["privacy"]["keep_ips"] = False
        with mock.patch.dict(os.environ, KEY):
            got = rt.identity(self.s.config, self.s.root)
        self.assertEqual((got["by"], got["horizon"], got["reach"]), ("hash", 30, 14))
        self.s.config["visitors"] = {"repeat_days": 60}
        self.assertEqual(rt.identity(self.s.config, self.s.root, keyed=True)["horizon"], 60)

    def test_neither_counts_nothing_and_says_why(self):
        self.s.config["privacy"]["keep_ips"] = False
        with mock.patch.dict(os.environ, {"SKALD_VISITOR_KEY": ""}):
            self.assertIsNone(rt.identity(self.s.config, self.s.root))
            self.assertIsNone(self.s.record(date(2026, 10, 1)))
        self.assertEqual(self.s.history.db.execute(
            "SELECT COUNT(*) FROM day_extras").fetchone()[0], 0)


class Address(unittest.TestCase):
    """A and B new in the week of MON; A back in the next two weeks (2 pages in
    the second); C new the week after; X a forgotten address."""

    def setUp(self):
        s = self.s = Stores()
        s.days(MON - timedelta(days=7), MON + timedelta(days=27))
        s.visit(MON, A, source="Search engine", country="GB", landing="/guides/alpha")
        s.visit(MON + timedelta(days=1), A)                   # same week: not a return
        s.visit(MON + timedelta(days=2), B, source="AI assistant")
        s.visit(MON + timedelta(days=8), A)
        s.visit(MON + timedelta(days=9), C)
        s.visit(MON + timedelta(days=15), A, pages=3)
        s.visit(MON + timedelta(days=3), "(removed)")
        self.today = MON + timedelta(days=28)

    def tearDown(self):
        self.s.close()

    def test_a_weekly_cohort(self):
        got = self.s.record(self.today)
        self.assertEqual(got["identity"]["by"], "address")
        w = self.s.blob("retention_week", MON)
        self.assertEqual((w["size"], w["removed"], w["end"]), (2, 1, "2026-09-13"))
        self.assertEqual(w["cells"], {"1": [1, 0], "2": [1, 1], "3": [0, 0]})
        self.assertEqual(w["split"]["source"]["Search engine"],
                         {"size": 1, "cells": {"1": [1, 0], "2": [1, 1], "3": [0, 0]}})
        self.assertEqual(w["split"]["source"]["AI assistant"]["size"], 1)
        self.assertEqual(w["split"]["country"]["GB"]["size"], 1)
        self.assertEqual(w["split"]["landing"]["/guides/alpha"]["size"], 1)
        nxt = self.s.blob("retention_week", MON + timedelta(days=7))
        self.assertEqual(nxt["size"], 1, "A came before: only C is new")
        self.assertEqual(self.s.blob("retention_day", MON + timedelta(days=8))["size"], 0)
        # nothing about a person in a blob
        self.assertNotIn("203.0.113", json.dumps(w))

    def test_a_visitor_seen_inside_the_lookback_is_not_new(self):
        self.s.visit(MON - timedelta(days=5), B)
        self.s.record(self.today)
        self.assertEqual(self.s.blob("retention_week", MON)["size"], 1)

    def test_a_different_browser_is_a_different_visitor(self):
        self.s.visit(MON + timedelta(days=10), A, browser="Firefox")
        self.s.record(self.today)
        self.assertEqual(self.s.blob("retention_week", MON + timedelta(days=7))["size"], 2)

    def test_the_audit_agrees_then_catches_a_change(self):
        self.s.record(self.today)
        got = self.s.audit(self.today)
        self.assertEqual(got["problems"], [])
        self.assertGreater(got["checked"], 30)
        self.assertEqual(self.s.blob("retention_week", MON)["audit"]["ok"], True)
        self.s.cdb.execute("UPDATE visits SET pages = 1 WHERE pages = 3")
        self.s.cdb.commit()
        got = self.s.audit(self.today)
        self.assertTrue(any("+2 came back and read 2 or more pages" in p for p in got["problems"]),
                        got["problems"])
        self.assertFalse(any("203.0.113" in p for p in got["problems"]))
        self.assertEqual(self.s.blob("retention_week", MON)["audit"]["ok"], False)

    def test_run_daily_recounts_step(self):
        from types import SimpleNamespace
        said = []
        ctx = SimpleNamespace(config={**self.s.config, "conversions": {"db": str(
            self.s.root / store.FILE)}}, site=SITE, db_path=self.s.root / "history.sqlite",
            now=datetime(self.today.year, self.today.month, self.today.day, 9, tzinfo=UTC),
            history=lambda: History(self.s.root / "history.sqlite"), out=said.append)
        self.assertFalse(audit_retention.set_up(ctx), "nothing stored yet: no step")
        self.s.record(self.today)
        self.assertTrue(audit_retention.set_up(ctx))
        self.assertEqual(audit_retention.daily(ctx, self.today - timedelta(days=1)), [])
        self.assertIn("cohorts recounted", said[-1])

    def test_the_cell_list_is_for_admins_and_owners_and_logged(self):
        from skald.people import api
        self.s.record(self.today)
        self.s.config["report"] = {"timezone": "UTC"}
        sent = []

        class H:
            def _json(self, code, body):
                sent.append((code, body))

        q = {"grain": "week", "start": MON.isoformat(), "k": "2"}
        hist = self.s.root / "history.sqlite"
        api._cohort(H(), q, self.s.config, self.s.root, SITE, False, self.s.config, None, None,
                    "viewer@example.com", hist)
        self.assertEqual(sent[-1][0], 403)
        api._cohort(H(), {**q, "k": "two"}, self.s.config, self.s.root, SITE, True,
                    self.s.config, None, None, "owner@example.com", hist)
        self.assertEqual(sent[-1][0], 400)
        with mock.patch("skald.people.api.datetime") as clock:
            clock.now.return_value = datetime(2026, 10, 5, 9, tzinfo=UTC)
            api._cohort(H(), q, self.s.config, self.s.root, SITE, True, self.s.config,
                        self.s.root, None, "owner@example.com", hist)
        self.assertEqual(sent[-1][0], 200, sent[-1])
        self.assertEqual(sent[-1][1]["listed"], 1)
        log = (self.s.root / "privacy.log").read_text()
        self.assertIn("people.cohort", log)
        self.assertNotIn("203.0.113", log + json.dumps(sent[-1][1]))

    def test_a_tampered_blob_is_caught(self):
        self.s.record(self.today)
        w = self.s.blob("retention_week", MON)
        w["size"] = 3
        w["split"]["country"]["(other)"] = {"size": 1, "cells": {}}
        self.s.history.db.execute("UPDATE day_extras SET data = ? WHERE day = ? AND kind = ?",
                                  (json.dumps(w), MON.isoformat(), "retention_week"))
        self.s.history.db.commit()
        got = self.s.audit(self.today)
        self.assertTrue(any("new visitors: stored 3, the recount finds 2" in p
                            for p in got["problems"]), got["problems"])
        self.assertTrue(any("by country (other)" in p for p in got["problems"]))

    def test_turning_keep_ips_off_counts_nothing_by_address(self):
        self.s.config["privacy"]["keep_ips"] = False
        self.assertIsNone(self.s.record(self.today, keyed=False))

    def test_the_visitors_behind_a_cell(self):
        self.s.record(self.today)
        got = retention_page.visitors(self.s.config, self.s.root, self.s.history.db, SITE,
                                      "week", MON.isoformat(), 2, today=self.today)
        self.assertEqual((got["listed"], got["stored"]), (1, 1))
        row = got["rows"][0]
        self.assertEqual((row["day"], row["seq"], row["pages"]), ("2026-09-22", 0, 3))
        self.assertNotIn("ip", row)
        deep = retention_page.visitors(self.s.config, self.s.root, self.s.history.db, SITE,
                                       "week", MON.isoformat(), 1, deep=True, today=self.today)
        self.assertEqual((deep["listed"], deep["stored"]), (0, 0))
        size = retention_page.visitors(self.s.config, self.s.root, self.s.history.db, SITE,
                                       "week", MON.isoformat(), 0, "source", "AI assistant",
                                       today=self.today)
        self.assertEqual([r["day"] for r in size["rows"]], ["2026-09-09"])
        bad = retention_page.visitors(self.s.config, self.s.root, self.s.history.db, SITE,
                                      "week", (MON + timedelta(days=1)).isoformat(), 1,
                                      today=self.today)
        self.assertFalse(bad["ok"])


class Expiry(unittest.TestCase):
    """keep_days 30: lookback 15, reach 14. Pruned stores: later cells are not recorded."""

    def setUp(self):
        self.s = Stores(keep_days=30)

    def tearDown(self):
        self.s.close()

    def test_beyond_the_reach_is_not_recorded_and_old_inputs_are_not_checkable(self):
        s = self.s
        today = MON + timedelta(days=35)
        # The store holds exactly the kept days: it has been pruned.
        s.days(today - timedelta(days=30), today - timedelta(days=1))
        start = MON + timedelta(days=21)           # a cohort week whose lookback is kept
        s.visit(start, A)
        s.visit(start + timedelta(days=8), A)
        s.record(today)
        w = s.blob("retention_week", start)
        self.assertEqual(w["cells"], {"1": [1, 0]})
        self.assertIsNone(w["since"])
        # An older cohort's lookback starts before the kept days: not counted.
        self.assertIsNone(s.blob("retention_week", MON + timedelta(days=14)))
        # Weeks later the cohort's inputs are pruned: left as counted, not checkable.
        later = today + timedelta(days=21)
        s.cdb.execute("DELETE FROM visit_days WHERE day < ?",
                      ((later - timedelta(days=30)).isoformat(),))
        s.cdb.execute("DELETE FROM visits WHERE day < ?", ((later - timedelta(days=30)).isoformat(),))
        s.days(today, later - timedelta(days=1))
        s.cdb.commit()
        got = s.record(later)
        self.assertGreater(got["left"], 0)
        self.assertEqual(s.blob("retention_week", start)["cells"], {"1": [1, 0]})
        checked = s.audit(later)
        self.assertGreater(checked["expired"], 0)
        self.assertEqual(checked["problems"], [])

    def test_a_young_store_counts_with_since(self):
        s = self.s
        s.days(MON, MON + timedelta(days=20))
        s.visit(MON, A)
        s.visit(MON + timedelta(days=15), A)
        s.record(MON + timedelta(days=21))
        w = s.blob("retention_week", MON)
        self.assertEqual(w["since"], MON.isoformat())
        self.assertEqual(w["cells"], {"1": [0, 0], "2": [1, 0]})


class Hash(unittest.TestCase):
    """No kept addresses: the 30-day code. Day and source only."""

    def setUp(self):
        self.s = Stores(keep_ips=False)
        db = self.s.history.db
        rows = [("v1", MON, "Search engine"), ("v1", MON + timedelta(days=9), ""),
                ("v2", MON + timedelta(days=1), "AI assistant")]
        db.executemany("INSERT INTO visitor_days (site, day, visitor, kind, n, source) VALUES "
                       "(?, ?, ?, 'reader', 1, ?)", [(SITE, d.isoformat(), v, src)
                                                     for v, d, src in rows])
        db.commit()

    def tearDown(self):
        self.s.close()

    def test_counted_by_the_code(self):
        today = MON + timedelta(days=21)
        got = self.s.record(today, keyed=True)
        self.assertEqual(got["identity"]["by"], "hash")
        w = self.s.blob("retention_week", MON)
        self.assertEqual((w["size"], w["deep"]), (2, None))
        self.assertEqual(w["cells"], {"1": [1, None], "2": [0, None]})
        self.assertEqual(list(w["split"]), ["source"])
        self.assertEqual(w["split"]["source"]["Search engine"]["cells"]["1"], [1, None])
        self.assertEqual(self.s.audit(today)["problems"], [])


class TimeZone(unittest.TestCase):
    """Days are the site's own: Sunday 23:30 in New York is Monday in UTC."""

    def test_a_week_ends_at_local_midnight(self):
        box = Sandbox(mail=False, tz="America/New_York")
        try:
            sun = date(2026, 9, 13)
            lines = [line(datetime(2026, 9, 13, 23, 30, tzinfo=NY), X, "/"),
                     line(datetime(2026, 9, 14, 10, 0, tzinfo=NY), X, "/guides/alpha",
                          referrer="https://example.com/"),
                     line(datetime(2026, 9, 14, 10, 5, tzinfo=NY), X, "/blog/")]
            lines += [line(datetime(d.year, d.month, d.day, 6, tzinfo=NY), "198.51.100.40",
                           "/", GPTBOT)
                      for d in (sun - timedelta(days=i) for i in range(-7, 7))]
            box.log(sorted(lines))
            for i in range(-7, 7):
                d = sun - timedelta(days=i)
                code, _, err = box.run("--today", (d + timedelta(days=1)).isoformat(),
                                       "collect", "--day", d.isoformat())
                self.assertEqual(code, 0, err)
            code, out, err = box.run("--today", "2026-09-21", "collect", "--day", "2026-09-20")
            self.assertIn("retention:", out)
            h = History(box.db)
            try:
                w = json.loads(h.db.execute(
                    "SELECT data FROM day_extras WHERE kind = 'retention_week' AND day = ?",
                    ("2026-09-07",)).fetchone()[0])
            finally:
                h.close()
            self.assertEqual(w["size"], 1)
            self.assertEqual(w["cells"]["1"], [1, 1], "Monday's visit is the next week's")
        finally:
            box.close()


class Page(unittest.TestCase):
    def test_cells_say_what_they_are(self):
        s = Stores(keep_days=30)
        try:
            today = MON + timedelta(days=35)
            s.days(today - timedelta(days=30), today - timedelta(days=1))
            start = MON + timedelta(days=21)
            s.visit(start, A)
            s.record(today)
            blob = s.blob("retention_week", start)
            states = {(today - timedelta(days=i)).isoformat(): {"state": "ok"}
                      for i in range(1, 40)}
            got = retention_page.cohort(blob, "week", today - timedelta(days=1), today,
                                        states, today - timedelta(days=30))
            self.assertEqual(got["status"]["1"], "ok")
            self.assertEqual(got["status"]["2"], "pending")
            later = start + timedelta(days=60)
            states.update({(later - timedelta(days=i)).isoformat(): {"state": "ok"}
                           for i in range(1, 70)})
            got = retention_page.cohort(blob, "week", later - timedelta(days=1), later,
                                        states, later - timedelta(days=30))
            self.assertEqual(got["status"]["2"], "nr", "beyond the 14 days it can follow")
            self.assertFalse(got["checkable"])
            states[(start + timedelta(days=9)).isoformat()] = {"state": "withheld"}
            got = retention_page.cohort(blob, "week", later - timedelta(days=1), later,
                                        states, later - timedelta(days=30))
            self.assertEqual(got["status"]["1"], "held")
            blob["audit"] = {"on": "x", "ok": False, "problems": 1}
            got = retention_page.cohort(blob, "week", later - timedelta(days=1), later,
                                        states, later - timedelta(days=30))
            self.assertEqual((got["state"], got["size"]), ("withheld", None))
        finally:
            s.close()


if __name__ == "__main__":
    unittest.main()
