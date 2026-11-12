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



class LeadVisits(unittest.TestCase):
    """#30 (2.46.5): a lead sent by the site's server, linked to its own visits.
    Shaped on freshlycited.com lead 1179 (11 Nov): a form sent at the lead's
    second (proven), a later visit from the same address and browser (likely),
    one from another browser at the same address (not linked), and a payment
    no visit sent (unmatched)."""

    def setUp(self):
        self.box = Sandbox(mail=False)
        firefox = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:131.0) Gecko/20100101 Firefox/131.0"
        t = datetime(2026, 10, 6, 16, 24, tzinfo=UTC)
        self.box.log(day_lines(date(2026, 10, 6), 3) + [
            line(t, PERSON, "/bing-webmaster-tools/ai-performance-report", referrer="https://www.bing.com/"),
            post(t + timedelta(seconds=82), PERSON, "/api/xray"),
            line(t + timedelta(minutes=38), PERSON, "/app/"),
            line(t + timedelta(minutes=46), PERSON, "/other/", agent=firefox),
            line(t + timedelta(minutes=2), "192.0.2.99", "/")])
        code, _, err = self.box.run("--today", "2026-10-07", "collect")
        self.assertEqual(code, 0, err)
        self.config = load_config(self.box.config)
        self.config["_resolved"] = {"history_db": str(self.box.db)}
        db = store.connect(store.path_for(self.config, self.box.root))
        try:
            for stage, action, when in (("completed", "xray", t + timedelta(seconds=82)),
                                        ("paid", "signup", t + timedelta(minutes=26))):
                store.record_conversion(db, {"site": SITE, "tool": "lead", "external_ref": "u_1",
                                             "action": action, "stage": stage,
                                             "at": store.stamp(when)})
        finally:
            db.close()

    def tearDown(self):
        self.box.close()

    def test_a_server_lead_walks_back_to_its_visits(self):
        got = lookup.person(self.config, self.box.root, SITE, "u_1", self.box.root)
        walk = got["path"]
        self.assertEqual([(v["landing"], v["link"]) for v in walk["visits"]],
                         [("/bing-webmaster-tools/ai-performance-report", "proven"), ("/app/", "likely")])
        self.assertEqual([s["action"] for s in walk["visits"][0]["steps"]], ["xray"])
        self.assertEqual(walk["first"]["landing"], "/bing-webmaster-tools/ai-performance-report")
        self.assertIn("bing", (walk["first"]["referrer"] or "") + (walk["first"]["via"] or "").lower())
        self.assertEqual([(s["action"], s["stage"]) for s in walk["unmatched"]], [("signup", "paid")])
        self.assertIn(PERSON, got["keys"]["ips"])
        self.assertNotIn("/other/", [v["landing"] for v in walk["visits"]], "another browser is not linked")

    def test_two_visits_sending_a_form_at_that_second_prove_nothing(self):
        from skald.people import lead_visits
        db = store.connect(store.path_for(self.config, self.box.root))
        try:
            visit = db.execute("SELECT * FROM visits WHERE landing = '/' AND ip = '192.0.2.99'").fetchone()
            v = dict(visit)
            db.execute("UPDATE visits SET posts = ?, start = ?, end = ? WHERE id = ?",
                       (json.dumps(["2026-10-06T16:25:24Z"]), "2026-10-06T16:25:00Z",
                        "2026-10-06T16:25:30Z", v["id"]))
            got = lead_visits.path(db, SITE, [{"at": "2026-10-06T16:25:22Z", "action": "xray",
                                               "stage": "completed", "tool": "lead"}])
        finally:
            db.close()
        self.assertEqual(got["visits"], [])
        self.assertEqual(got["unmatched"][0]["why"], "2 visits sent a form at its time")

    def test_a_dropped_address_links_no_other_visit(self):
        from skald.people import lead_visits
        db = store.connect(store.path_for(self.config, self.box.root))
        try:
            db.execute("UPDATE visits SET ip = '(removed)'")
            got = lead_visits.path(db, SITE, [{"at": "2026-10-06T16:25:22Z", "action": "xray",
                                               "stage": "completed", "tool": "lead"}])
        finally:
            db.close()
        self.assertEqual([v["link"] for v in got["visits"]], ["proven"], "no likely visit")


    def test_the_audit_finds_the_same_links_by_its_own_road(self):
        from types import SimpleNamespace
        from skald import audit_lead_visits, audit_more
        self.assertIn("lead_visits", audit_more.DAILY)
        said = []
        ctx = SimpleNamespace(config=self.config, db_path=self.box.db, site=SITE, out=said.append)
        self.assertTrue(audit_lead_visits.set_up(ctx))
        self.assertEqual(audit_lead_visits.daily(ctx, date(2026, 10, 6)), [])
        self.assertIn("2 conversion(s)", said[0])

    def test_the_audit_catches_a_wrong_proven_visit(self):
        from unittest import mock
        from skald import audit_lead_visits
        from skald.people import lead_visits
        real = lead_visits.posted_near
        with mock.patch.object(lead_visits, "posted_near",
                               lambda db, site, at, **kw: real(db, site, at, before=3600, after=3600)):
            db = sqlite3.connect(store.path_for(self.config, self.box.root))
            try:
                n, problems = audit_lead_visits.check(db, SITE, "2026-10-06T00:00:00Z",
                                                      "2026-10-07T00:00:00Z")
            finally:
                db.close()
        self.assertEqual(n, 2)
        self.assertTrue(any("proven visit(s) shown" in p for p in problems), problems)
        self.assertFalse(any(PERSON in p for p in problems), "no address in a problem")

    # #31: the Lead / Customer pill on Traffic > Visitors.
    WEEK = ("2026-10-05T00:00:00Z", "2026-10-08T00:00:00Z")

    def seq_of(self, db, landing):
        return db.execute("SELECT day || '.' || seq FROM visits WHERE landing = ?",
                          (landing,)).fetchone()[0]

    def test_the_proven_visit_of_someone_who_paid_is_a_customer(self):
        from skald.people import lead_visits
        db = store.connect(store.path_for(self.config, self.box.root))
        try:
            got = lead_visits.visit_marks(db, SITE, *self.WEEK)
            key = self.seq_of(db, "/bing-webmaster-tools/ai-performance-report")
        finally:
            db.close()
        # The xray step was sent by that visit; u_1 paid later (from no visit): a customer.
        # The likely visit (/app/) and the other browser are never marked.
        self.assertEqual(got, {key: "customer"})

    def test_a_lead_that_has_not_paid_is_a_lead_and_a_step_alone_is_nothing(self):
        from skald.people import lead_visits
        db = store.connect(store.path_for(self.config, self.box.root))
        try:
            db.execute("DELETE FROM conversions WHERE stage = 'paid'")
            self.assertEqual(lead_visits.visit_marks(db, SITE, *self.WEEK), {},
                             "xray is no lead action: no pill without a payment")
            db.execute("UPDATE conversions SET action = 'contact'")
            got = lead_visits.visit_marks(db, SITE, *self.WEEK)
            key = self.seq_of(db, "/bing-webmaster-tools/ai-performance-report")
            db.execute("UPDATE conversions SET test = 1")
            test = lead_visits.visit_marks(db, SITE, *self.WEEK)
        finally:
            db.close()
        self.assertEqual(got, {key: "lead"})
        self.assertEqual(test, {}, "a test row marks nothing")

    def test_two_visits_sending_a_form_at_that_second_mark_neither(self):
        from skald.people import lead_visits
        db = store.connect(store.path_for(self.config, self.box.root))
        try:
            v = dict(db.execute("SELECT * FROM visits WHERE ip = '192.0.2.99'").fetchone())
            db.execute("UPDATE visits SET posts = ?, start = ?, end = ? WHERE id = ?",
                       (json.dumps(["2026-10-06T16:25:24Z"]), "2026-10-06T16:25:00Z",
                        "2026-10-06T16:25:30Z", v["id"]))
            self.assertEqual(lead_visits.visit_marks(db, SITE, *self.WEEK), {})
        finally:
            db.close()

    def test_app_json_carries_the_mark_on_that_visit_only(self):
        from skald import dashboard_webapp
        from skald.store import History
        h = History(self.box.db)
        try:
            out = self.box.root / "out"
            dashboard_webapp.write(out, h, SITE, UTC, datetime(2026, 10, 7, 12, tzinfo=UTC),
                                   None, config=self.config)
        finally:
            h.close()
        app = json.loads(next(out.rglob("app.json")).read_text())
        won = [(j["trail"][0]["path"], j["won"]) for j in app["journeys"] if "won" in j]
        self.assertEqual(won, [("/bing-webmaster-tools/ai-performance-report", "customer")])
        for j in app["journeys"]:
            self.assertFalse({"ip", "user_agent", "external_ref", "ref"} & set(j), "labels only")

    def test_no_store_or_a_broken_one_leaves_the_visits_as_they_are(self):
        from skald.people import lead_visits
        js = [{"day": "2026-10-06", "seq": 0, "start": "x"}]
        self.assertIs(lead_visits.mark_journeys({}, self.box.root / "none", SITE, js), js)
        broken = self.box.root / "broken"
        broken.mkdir()
        (broken / store.FILE).write_text("not a database")
        self.assertIs(lead_visits.mark_journeys({}, broken, SITE, js), js)
        self.assertEqual(lead_visits.mark_journeys(self.config, self.box.root, SITE, []), [])

    def test_the_audit_checks_every_pill_by_its_own_road(self):
        from unittest import mock
        from skald import audit_lead_visits
        from skald.people import lead_visits
        db = sqlite3.connect(store.path_for(self.config, self.box.root))
        db.row_factory = sqlite3.Row
        try:
            rows = [dict(r) for r in db.execute("SELECT * FROM conversions")]
            key = self.seq_of(db, "/bing-webmaster-tools/ai-performance-report")
            self.assertEqual(audit_lead_visits.marks_by_own_road(db, SITE, rows), {key: "customer"})
            self.assertEqual(audit_lead_visits.check_marks(db, SITE, *self.WEEK, rows), [])
            other = self.seq_of(db, "/app/")
            with mock.patch.object(lead_visits, "visit_marks", lambda *a: {key: "lead", other: "lead"}):
                problems = audit_lead_visits.check_marks(db, SITE, *self.WEEK, rows)
        finally:
            db.close()
        self.assertEqual(len(problems), 2, problems)
        self.assertTrue(any("marked lead, this road finds customer" in p for p in problems), problems)
        self.assertTrue(any("marked lead, this road finds nothing" in p for p in problems), problems)
        self.assertFalse(any(PERSON in p for p in problems), "no address in a problem")

class PersonPathPage(unittest.TestCase):
    """The drawer part of #30, run in node (tests/js/person-path.mjs)."""

    def test_person_path(self):
        import shutil
        import subprocess
        if not shutil.which("node"):
            self.skipTest("node is not installed")
        js = Path(__file__).resolve().parent / "js" / "person-path.mjs"
        done = subprocess.run(["node", str(js)], capture_output=True, text=True, timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("person-path: all passed", done.stdout)

    def test_lead_profile_and_pill(self):
        """#31: the lead drawer's profile and the Lead / Customer pill (tests/js/lead-profile.mjs)."""
        import shutil
        import subprocess
        if not shutil.which("node"):
            self.skipTest("node is not installed")
        js = Path(__file__).resolve().parent / "js" / "lead-profile.mjs"
        done = subprocess.run(["node", str(js)], capture_output=True, text=True, timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("lead-profile: all passed", done.stdout)

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
