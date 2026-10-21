"""Leads & sales > Leads (people/leadlist.py, people/api.py people/leads): the period's
leads, one row per lead; names and emails only for admins and owners, only with the
page's CSRF value (same-origin in basic mode), only where the site keeps them, and
one audit row per load that never holds a value. The list's counted rows are the
same rows the Leads figure counts (conversions_data.figures), never a new count."""
from __future__ import annotations

import sqlite3
import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_people_lookup as base  # noqa: E402
from test_people_lookup import SITE, FakeHandler  # noqa: E402

from skald import conversions_data  # noqa: E402
from skald.conversions import FINISHED, LEAD_ACTIONS, store  # noqa: E402
from skald.people import api, leadlist  # noqa: E402
from skald.window import zone  # noqa: E402

FIRST, LAST = date(2026, 10, 1), date(2026, 10, 10)
URL = f"/traffic/{SITE}/people/leads?first=2026-10-01&last=2026-10-10"


class Handler(FakeHandler):
    def __init__(self, path, role, headers=None):
        super().__init__(path, role)
        self.headers = headers or {}


class LeadList(unittest.TestCase):
    setUp = base.Lookup.setUp
    tearDown = base.Lookup.tearDown

    def ask(self, path, role="admin", headers=None, who=None):
        h = Handler(path, role, {"Sec-Fetch-Site": "same-origin"} if headers is None else headers)
        h.who = who
        self.assertTrue(api.is_people(path.split("?")[0]))
        api.handle(h, self.config, self.box.root, self.box.db, self.box.config,
                   sessions_mode=who is not None)
        return h.sent

    def figure(self) -> int:
        """The Leads figure of the same days, as conversions.json counts it."""
        db = store.connect(store.path_for(self.config, self.box.root))
        try:
            per = conversions_data.figures(db, SITE, zone(self.config), FIRST, LAST,
                                           "2026-10-21T00:00:00Z", 24)
        finally:
            db.close()
        return sum(v for d in per.values() for a, st in d["stages"].items() if a in LEAD_ACTIONS
                   for k, v in st.items() if k in FINISHED)

    def test_the_counted_rows_are_the_leads_figure(self):
        got = leadlist.rows(self.config, self.box.root, SITE, FIRST, LAST, names=False)
        counted = [r for r in got["rows"] if not r["left_out"]]
        self.assertGreater(len(counted), 0)
        self.assertEqual(len(counted), self.figure())
        self.assertEqual([r["at"] for r in got["rows"]], sorted((r["at"] for r in got["rows"]), reverse=True))
        won = [r for r in counted if r["now"] == "won"]
        self.assertEqual(len(won), 1, "a lead marked won says so as its stage now")
        self.assertTrue(all(r["tool"] == "site" for r in counted), "from the lead database")
        spam = [r for r in got["rows"] if r["left_out"] == "spam"]
        self.assertEqual(len(spam), 1, "the lead database's spam is listed, left out")

    def test_no_names_without_asking_and_none_for_viewers(self):
        code, body = self.ask(URL, "viewer")
        self.assertEqual(code, 200)
        self.assertFalse(body["names"])
        for r in body["rows"]:
            self.assertNotIn("email", r)
            self.assertNotIn("name", r)
            self.assertNotIn("vid", r)
        code, body = self.ask(URL + "&names=1", "viewer")
        self.assertEqual(code, 403, "a viewer never gets names")
        self.assertFalse((self.box.root / "privacy.log").exists() and
                         "people.leads" in (self.box.root / "privacy.log").read_text())

    def test_admins_get_names_with_the_page_and_an_audit_row(self):
        code, body = self.ask(URL + "&names=1")
        self.assertEqual(code, 200)
        self.assertTrue(body["names"])
        emails = {r.get("email") for r in body["rows"]}
        self.assertIn("person3@example.com", emails)
        log = (self.box.root / "privacy.log").read_text()
        self.assertIn("people.leads site=example.com", log)
        self.assertIn("lead list viewed 2026-10-01..2026-10-10", log)
        self.assertNotIn("@example.com", log, "the audit row never holds a value")
        self.assertNotIn("Person 3", log)

    def test_names_need_the_page_itself(self):
        code, _ = self.ask(URL + "&names=1", headers={"Sec-Fetch-Site": "cross-site"})
        self.assertEqual(code, 403, "basic mode: only a same-origin request")
        who = {"role": "admin", "csrf": "c" * 32, "org": None, "user_id": 1}
        code, _ = self.ask(URL + "&names=1", headers={}, who=who)
        self.assertEqual(code, 403, "sessions: no CSRF value, no names")
        code, body = self.ask(URL + "&names=1", headers={"X-Skald-CSRF": "c" * 32}, who=who)
        self.assertEqual(code, 200)
        self.assertTrue(body["names"])

    def test_an_anonymous_site_shows_no_names_even_to_admins(self):
        self.config.setdefault("conversions", {})["identity"] = "anonymous"
        code, body = self.ask(URL + "&names=1")
        self.assertEqual(code, 200)
        self.assertFalse(body["names"])
        self.assertIn("anonymous", body["why"])
        self.assertTrue(all("email" not in r for r in body["rows"]))
        log = self.box.root / "privacy.log"
        self.assertFalse(log.exists() and "people.leads" in log.read_text(), "nothing shown, nothing logged")

    def test_a_bad_period_is_refused(self):
        for q in ("first=2026-10-10&last=2026-10-01", "first=x&last=y", "first=2024-01-01&last=2026-10-01"):
            code, _ = self.ask(f"/traffic/{SITE}/people/leads?{q}")
            self.assertEqual(code, 400, q)

    def test_test_rows_are_listed_left_out(self):
        path = store.path_for(self.config, self.box.root)
        db = sqlite3.connect(path)
        db.execute("UPDATE conversions SET test = 1 WHERE external_ref = '3'")
        db.commit()
        db.close()
        got = leadlist.rows(self.config, self.box.root, SITE, FIRST, LAST, names=False)
        self.assertTrue(any(r["left_out"] == "test" for r in got["rows"]))
        self.assertEqual(len([r for r in got["rows"] if not r["left_out"]]), self.figure())


if __name__ == "__main__":
    unittest.main()
