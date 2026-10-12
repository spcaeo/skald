"""2.4.0: look a person up, list what the figures leave out, mark test rows.

Addresses are RFC 5737, names and emails made up at example.com.
"""
from __future__ import annotations

import json
import sqlite3
import sys
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from support import CHROME, Sandbox, day_lines, line  # noqa: E402
from test_conversions_from_leads import LEADS, lead_db  # noqa: E402

from skald import audit_conversions, tokens  # noqa: E402
from skald.config import load_config  # noqa: E402
from skald.conversions import from_leads, store  # noqa: E402
from skald.people import api, lookup  # noqa: E402

UTC = timezone.utc
SITE = "example.com"
PERSON = "203.0.113.50"


def post(when: datetime, address: str, path: str) -> str:
    return (f'{when.isoformat()} {address} example.com "POST {path} HTTP/2.0" 200 64 '
            f'"https://example.com/contact/" "{CHROME}" 0.004 cc=CA ray=0-LHR\n')


class Lookup(unittest.TestCase):
    def setUp(self):
        self.box = Sandbox(mail=False)
        self.leads = lead_db(self.box.root / "leads.db")
        self.box.config.write_text(self.box.config.read_text()
                                   + f"leads:\n  db: {self.leads}\n")
        # Lead 1 was made 2026-10-06 15:00 UTC; this visit sent a form 30 s before.
        t = datetime(2026, 10, 6, 14, 58, tzinfo=UTC)
        self.box.log(day_lines(date(2026, 10, 6), 3)
                     + [line(t, PERSON, "/contact/", country="CA"),
                        post(t + timedelta(seconds=90), PERSON, "/api/form")])
        code, _, err = self.box.run("--today", "2026-10-07", "collect")
        self.assertEqual(code, 0, err)
        self.config = load_config(self.box.config)
        self.config["_resolved"] = {"history_db": str(self.box.db)}
        self.assertNotIn("error", from_leads.run(self.config, self.box.root, SITE, full=True))

    def tearDown(self):
        self.box.close()

    def find(self, q):
        return lookup.person(self.config, self.box.root, SITE, q, self.box.root)

    def test_kinds(self):
        self.assertEqual(lookup.kind_of(" 192.0.2.7 "), ("ip", "192.0.2.7"))
        self.assertEqual(lookup.kind_of("Person1@Example.com"), ("email", "person1@example.com"))
        self.assertEqual(lookup.kind_of("skv_" + "A" * 22)[0], "vid")
        self.assertEqual(lookup.kind_of("42"), ("lead", "42"))
        for bad in ("", "a b c", "x" * 400, "not@an@email"):
            with self.assertRaises(lookup.Invalid):
                lookup.kind_of(bad)

    def test_an_address_finds_its_visits_and_the_lead_by_time(self):
        got = self.find(PERSON)
        self.assertEqual(len(got["visits"]), 1)
        v = got["visits"][0]
        self.assertEqual((v["landing"], v["country"], v["pages"]), ("/contact/", "CA", 1))
        self.assertIn("Chrome", v["user_agent"])
        self.assertEqual(len(v["posts"]), 1)
        self.assertEqual([c["lead"] for c in got["candidates"]], ["1"], "the lead by time")

    def test_an_email_finds_the_lead_its_conversions_and_the_visit_that_sent_it(self):
        got = self.find("person1@example.com")
        self.assertEqual([str(r["id"]) for r in got["leads"]], ["1"])
        self.assertEqual(got["leads"][0]["email"], "person1@example.com")
        self.assertEqual({r["external_ref"] for r in got["conversions"]}, {"1"})
        self.assertEqual([c["ip"] for c in got["candidates"]], [PERSON])
        self.assertIn(PERSON, got["keys"]["ips"])

    def test_a_lead_id_and_spam_too(self):
        got = self.find("2")
        self.assertEqual(got["leads"][0]["status"], "spam")
        self.assertTrue(got["leads"][0]["left_out"])
        self.assertEqual(got["conversions"], [])

    def test_left_out_lists_spam_and_hides_emails_from_viewers(self):
        got = lookup.left_out(self.config, self.box.root, SITE, private=False)
        self.assertEqual([(str(r["id"]), r["why"]) for r in got["leads"]], [("2", "spam")])
        self.assertNotIn("email", got["leads"][0])
        mine = lookup.left_out(self.config, self.box.root, SITE, private=True)
        self.assertEqual(mine["leads"][0]["email"], "person2@example.com")
        self.assertIsNone(got["leads"][0]["vid"], "a viewer never gets a visitor ID")

    def test_lead_visitor_id_only_for_admins_with_visitor_ids_on(self):
        import sqlite3 as sq
        db = sq.connect(self.leads)
        db.execute("UPDATE submissions SET session_id = 'sess-abcdefgh12' WHERE id = 2")
        db.commit(); db.close()
        off = lookup.left_out(self.config, self.box.root, SITE, private=True)
        self.assertIsNone(off["leads"][0]["vid"], "visitor IDs off: a session is no visitor")
        on = {**self.config, "beacon": {**(self.config.get("beacon") or {}), "visitor_ids": True}}
        self.assertEqual(lookup.left_out(on, self.box.root, SITE, private=True)["leads"][0]["vid"],
                         "sess-abcdefgh12")
        self.assertIsNone(lookup.left_out(on, self.box.root, SITE, private=False)["leads"][0]["vid"])

    def test_a_status_change_keeps_the_removed_row(self):
        db = sqlite3.connect(self.leads)
        db.execute("UPDATE submissions SET status = 'spam', updated_at = '2026-10-09T00:00:00Z' "
                    "WHERE id = 1")
        db.commit()
        db.close()
        from_leads.run(self.config, self.box.root, SITE)
        got = lookup.conversions_listing(self.config, self.box.root, SITE, "removed", True)
        self.assertEqual([r["external_ref"] for r in got["rows"]], ["1"])
        self.assertIn("marked spam", got["rows"][0]["why"])
        self.assertEqual(got["rows"][0]["row"]["email"], "person1@example.com")
        anon = lookup.conversions_listing(self.config, self.box.root, SITE, "removed", False)
        self.assertNotIn("email", anon["rows"][0]["row"])
        self.assertEqual(len(self.find("1")["removed"]), 1)

    def test_mark_test_leaves_a_row_out_of_figures_and_both_counts_agree(self):
        db = store.connect(self.box.root / "conversions.sqlite")
        cid = db.execute("SELECT id FROM conversions WHERE external_ref = '3' AND "
                         "stage = 'completed'").fetchone()[0]
        db.close()
        code, out, err = self.box.run("conversions", "mark-test", SITE, str(cid))
        self.assertEqual(code, 0, err)
        self.assertIn("2 row(s) marked test", out)          # completed and won
        db = store.connect(self.box.root / "conversions.sqlite")
        try:
            days = store.day_counts(db, SITE, UTC, date(2026, 10, 1), date(2026, 10, 9))
        finally:
            db.close()
        self.assertNotIn(("signup", "completed"), days.get("2026-10-07", {}))
        found = audit_conversions.findings(self.config, self.box.root, SITE, UTC,
                                           date(2026, 10, 1), date(2026, 10, 9))
        self.assertEqual(found, {})
        listed = lookup.left_out(self.config, self.box.root, SITE, True)["conversions"]
        self.assertEqual({r["stage"] for r in listed}, {"completed", "won"})
        code, out, _ = self.box.run("conversions", "mark-test", SITE, str(cid), "--unmark")
        self.assertIn("2 row(s) unmarked", out)
        self.assertEqual(self.box.run("conversions", "mark-test", SITE, "99999")[0], 2)

    def test_forget_by_email_deletes_the_removed_rows_too(self):
        db = sqlite3.connect(self.leads)
        db.execute("DELETE FROM submissions WHERE id = 1")
        db.commit()
        db.close()
        from_leads.run(self.config, self.box.root, SITE, full=True)
        self.assertEqual(len(lookup.conversions_listing(
            self.config, self.box.root, SITE, "removed", True)["rows"]), 1)
        code, out, err = self.box.run("forget", "--email", "person1@example.com")
        self.assertEqual(code, 0, err)
        self.assertIn("1 removed row(s)", out)
        self.assertEqual(lookup.conversions_listing(
            self.config, self.box.root, SITE, "removed", True)["rows"], [])


class FakeHandler:
    def __init__(self, path, role):
        self.path, self.role, self.who, self.sent = path, role, None, None

    def _user(self):
        return "pat", self.role

    def _json(self, code, body):
        self.sent = (code, body)


class Routes(Lookup):
    def ask(self, path, role="admin"):
        h = FakeHandler(path, role)
        self.assertTrue(api.is_people(path.split("?")[0]))
        api.handle(h, self.config, self.box.root, self.box.db, self.box.config)
        return h.sent

    def test_admins_find_people_viewers_do_not(self):
        code, body = self.ask(f"/traffic/{SITE}/people?q={PERSON}")
        self.assertEqual(code, 200)
        self.assertEqual(len(body["visits"]), 1)
        code, body = self.ask(f"/traffic/{SITE}/people?q={PERSON}", "viewer")
        self.assertEqual(code, 403)
        log = (self.box.root / "privacy.log").read_text()
        self.assertIn("people.search", log)
        self.assertNotIn(PERSON, log, "the audit line never holds the value")

    def test_listings_for_every_member(self):
        code, body = self.ask(f"/traffic/{SITE}/people/left-out", "viewer")
        self.assertEqual((code, body["private"]), (200, False))
        code, body = self.ask(f"/traffic/{SITE}/people/conversions?kind=cancelled", "viewer")
        self.assertEqual(code, 200)
        code, _ = self.ask(f"/traffic/{SITE}/people/conversions?kind=everything")
        self.assertEqual(code, 400)
        code, _ = self.ask(f"/traffic/{SITE}/people?q=a%20b")
        self.assertEqual(code, 400)

    def test_tokens_need_the_private_scope(self):
        path = self.box.root / "tokens.json"
        plain = tokens.create(path, "plain")
        private = tokens.create(path, "private", private=True)
        self.assertFalse(tokens.check(path, f"Bearer {plain}", SITE, "people")[0])
        self.assertTrue(tokens.check(path, f"Bearer {private}", SITE, "people")[0])


if __name__ == "__main__":
    unittest.main()
