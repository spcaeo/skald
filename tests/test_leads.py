"""Leads from the website's CMS (leads.py): read-only, aggregates only, sums
that hold, and an SQL recount that agrees.

The CMS file is a temporary SQLite database with the website's
`submissions` schema; every email and name in it is made up and must never
appear in the output.
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from support import NY, Sandbox, day_lines  # noqa: E402

from skald import audit_leads, leads  # noqa: E402

SCHEMA = """
CREATE TABLE `submissions` (
  `id` integer PRIMARY KEY NOT NULL, `type` text NOT NULL, `email` text,
  `fields` text NOT NULL, `consent` integer DEFAULT false, `ip_hash` text, `locale` text,
  `updated_at` text NOT NULL, `created_at` text NOT NULL,
  `status` text DEFAULT 'new' NOT NULL, `notes` text, `duplicate_of_id` integer,
  `name` text, `company` text, `source` text, `ai_source` text, `page` text,
  `first_touch` text, `last_touch` text, `session_id` text, `pages_viewed` numeric,
  `visits` numeric, `flags` text, `fill_seconds` numeric, `browser` text,
  `ip_country` text, `external_ref` text, `delivery_team` text, `delivery_sender` text);
"""


def touch(**kw) -> str:
    base = {"at": "2026-10-01T10:00:00.000Z", "landingPath": "/", "referrerHost": "",
            "utmSource": "", "utmMedium": "", "utmCampaign": "", "utmTerm": "",
            "utmContent": "", "gclid": "", "msclkid": "", "fbclid": "", "aiSource": "",
            "locale": "en-us"}
    base.update(kw)
    return json.dumps(base)


# (created_at UTC, type, status, locale, page, first_touch, last_touch)
ROWS = [
    ("2026-10-06T15:00:00.000Z", "signup", "new", "en-us", "/signup/",
     touch(aiSource="chatgpt.com", referrerHost="chatgpt.com", landingPath="/compare/x/"), None),
    ("2026-10-06T16:00:00.000Z", "contact", "spam", "en-us", "/contact/", touch(), None),
    ("2026-10-06T16:05:00.000Z", "contact", "duplicate", "en-us", "/contact/", touch(), None),
    # 23:30 on 2026-10-06 in New York, already 2026-10-07 in UTC.
    ("2026-10-07T03:30:00.000Z", "waitlist", "qualified", "fr-ca", "/ca/fr/adhesion/",
     touch(utmSource="linkedin", utmMedium="social", utmCampaign="Launch",
           landingPath="/ca/fr/"), touch(referrerHost="google.com")),
    ("2026-10-07T14:00:00.000Z", "demo_opened", "new", "en-ca", "/ca/pricing/",
     touch(referrerHost="news.example.org", landingPath="/ca/"), None),
    ("2026-10-07T14:05:00.000Z", "demo_booked", "new", "en-ca", "/ca/pricing/",
     touch(referrerHost="news.example.org", landingPath="/ca/"), None),
    ("2026-10-07T18:00:00.000Z", "signup", "won", "en-us", "/signup/", None, None),
    ("2026-10-07T19:00:00.000Z", "contact", "new", "en-us", "/contact/", "not json", None),
]


def make_db(path: Path, rows=ROWS) -> Path:
    db = sqlite3.connect(path)
    db.executescript(SCHEMA)
    for i, (at, kind, status, locale, page, first, last) in enumerate(rows, 1):
        db.execute(
            "INSERT INTO submissions (id, type, email, fields, locale, updated_at, created_at, "
            "status, name, company, page, first_touch, last_touch, session_id, ip_hash) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (i, kind, f"person{i}@example.com", json.dumps({"phone": "+1 555 0100"}), locale,
             at, at, status, f"Person {i}", f"Company {i}", page, first, last,
             f"session-{i}", f"hash-{i}"))
    db.commit()
    db.close()
    return path


TODAY = date(2026, 10, 7)
JOURNEYS = [
    {"day": "2026-10-06", "source": "AI assistant", "landing": "/compare/x/",
     "trail": [["/compare/x/", "page"], ["/pricing/", "app"], ["/signup/", "page"]]},
    {"day": "2026-10-06", "source": "Direct or unknown", "landing": "/",
     "trail": [["/", "page"]]},
    {"day": "2026-10-07", "source": "Social media", "landing": "/ca/fr/",
     "trail": [["/ca/fr/", "page"], ["/ca/fr/tarifs/", "page"]]},
    {"day": "2026-10-07", "source": "Direct or unknown", "landing": "/ca/contact",
     "trail": [["/ca/contact", "page"]]},
]


class LeadsTest(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = make_db(Path(self._tmp.name) / "payload.db")
        self.config = {"leads": {"db": str(self.path)}}

    def tearDown(self):
        self._tmp.cleanup()

    def blob(self, config=None):
        return leads.blob(config or self.config, NY, TODAY, JOURNEYS, date(2026, 9, 30))


class TestReading(LeadsTest):

    def test_not_configured_or_missing_is_not_available_and_creates_nothing(self):
        self.assertEqual(leads.blob({}, NY, TODAY, [], TODAY)["error"], "leads.db not set")
        missing = Path(self._tmp.name) / "absent.db"
        got = leads.blob({"leads": {"db": str(missing)}}, NY, TODAY, [], TODAY)
        self.assertFalse(got["available"])
        self.assertFalse(missing.exists())

    def test_the_database_is_opened_read_only(self):
        db = leads.connect(self.path)
        with self.assertRaises(sqlite3.OperationalError):
            db.execute("DELETE FROM submissions")
        db.close()
        before = os.stat(self.path).st_mtime_ns
        self.blob()
        self.assertEqual(os.stat(self.path).st_mtime_ns, before)

    def test_nothing_personal_leaves_the_module(self):
        text = json.dumps(self.blob())
        for secret in ("@example.com", "Person 1", "Company 1", "555", "session-", "hash-"):
            self.assertNotIn(secret, text)

    def test_an_older_schema_without_attribution_columns(self):
        old = Path(self._tmp.name) / "old.db"
        db = sqlite3.connect(old)
        db.execute("CREATE TABLE submissions (id integer, type text, email text, "
                   "created_at text, status text)")
        db.execute("INSERT INTO submissions VALUES (1, 'signup', 'a@example.com', "
                   "'2026-10-07T12:00:00.000Z', 'new')")
        db.commit()
        db.close()
        got = leads.blob({"leads": {"db": str(old)}}, NY, TODAY, [], TODAY)
        self.assertTrue(got["available"], got.get("error"))
        self.assertEqual(got["period"]["first_touch"]["source"], {"(none)": 1})
        self.assertEqual(got["period"]["page"], {"(none)": 1})


class TestCounts(LeadsTest):

    def test_days_are_local_and_spam_and_duplicates_are_apart(self):
        days = {d["day"]: d for d in self.blob()["days"]}
        self.assertEqual(len(days), leads.DAYS)
        six = days["2026-10-06"]
        # The 03:30 UTC lead belongs to the 6th in New York.
        self.assertEqual(six["leads"], {"signup": 1, "waitlist": 1})
        self.assertEqual((six["spam"], six["duplicates"]), (1, 1))
        self.assertEqual(six["status"], {"new": 1, "spam": 1, "duplicate": 1, "qualified": 1})
        self.assertEqual(days["2026-10-07"]["leads"],
                         {"demo_opened": 1, "demo_booked": 1, "signup": 1, "contact": 1})

    def test_first_touch_breakdowns(self):
        p = self.blob()["period"]
        ft = p["first_touch"]
        self.assertEqual(ft["source"], {"AI assistant": 1, "Social media": 1,
                                        "Other website": 2, "(none)": 2})
        self.assertEqual(ft["ai"], {"chatgpt.com": 1, "(none)": 5})
        self.assertEqual(ft["utm_campaign"]["launch"], 1)
        self.assertEqual(p["last_touch"]["source"]["Search engine"], 1)
        self.assertEqual(p["locale"], {"en-us": 3, "en-ca": 2, "fr-ca": 1})
        self.assertEqual(p["status"]["spam"], 1)

    def test_every_breakdown_adds_up(self):
        got = self.blob()
        self.assertTrue(got["available"], got.get("error"))
        self.assertEqual(leads.check(got), [])

    def test_check_catches_a_breakdown_that_does_not_add_up(self):
        got = self.blob()
        got["period"]["first_touch"]["source"]["AI assistant"] += 1
        self.assertTrue(any("first_touch.source" in p for p in leads.check(got)))


class TestFunnel(LeadsTest):

    def test_log_steps_by_visit_source_and_cms_steps_by_first_touch(self):
        f = self.blob()["funnel"]
        rows = {r["source"]: r for r in f["by_source"]}
        ai = rows["AI assistant"]
        self.assertEqual((ai["readers"], ai["pricing"], ai["form_page"], ai["leads"]), (1, 1, 1, 1))
        social = rows["Social media"]
        self.assertEqual((social["readers"], social["pricing"], social["leads"]), (1, 1, 1))
        direct = rows["Direct or unknown"]
        self.assertEqual((direct["readers"], direct["form_page"]), (2, 1))   # /ca/contact
        other = rows["Other website"]
        self.assertEqual((other["readers"], other["demo_opened"], other["demo_booked"]), (0, 1, 1))
        self.assertEqual(rows["(none)"]["leads"], 2)
        self.assertEqual(f["total"]["readers"], 4)
        self.assertEqual(f["total"]["leads"], 4)        # spam and the duplicate excluded

    def test_page_lists_can_be_overridden(self):
        config = {"leads": {"db": str(self.path), "pricing_paths": ["/ca/fr/tarifs/"],
                            "form_paths": "signup"}}
        rows = {r["source"]: r for r in self.blob(config)["funnel"]["by_source"]}
        self.assertEqual(rows["AI assistant"]["pricing"], 0)
        self.assertEqual(rows["Social media"]["pricing"], 1)
        self.assertEqual(rows["Direct or unknown"]["form_page"], 0)


class TestAudit(LeadsTest):

    def test_the_sql_recount_matches(self):
        got = self.blob()
        recount = audit_leads.audit_leads(self.path, NY, date(2026, 9, 7), TODAY)
        self.assertEqual(audit_leads.compare(got, recount), [])
        self.assertEqual(recount["days"]["2026-10-06"]["leads"], {"signup": 1, "waitlist": 1})

    def test_the_recount_sees_a_wrong_figure(self):
        got = self.blob()
        got["days"][-1]["leads"]["signup"] = 2
        recount = audit_leads.audit_leads(self.path, NY, date(2026, 9, 7), TODAY)
        self.assertTrue(audit_leads.compare(got, recount))


class TestCommand(unittest.TestCase):

    def setUp(self):
        self.box = Sandbox(tz="America/New_York", mail=False)
        self.path = make_db(self.box.root / "payload.db")
        with open(self.box.config, "a") as handle:
            handle.write(f"leads:\n  db: {self.path}\n")

    def tearDown(self):
        self.box.close()

    def test_leads_prints_aggregates_and_audits(self):
        code, out, err = self.box.run("--today", "2026-10-07", "leads", "--audit")
        self.assertEqual(code, 0, err)
        self.assertIn("LEADS", out)
        self.assertIn("the SQL recount matches", out)
        self.assertNotIn("@example.com", out)
        code, out, _ = self.box.run("--today", "2026-10-07", "leads", "--json")
        self.assertEqual(json.loads(out)["period"]["leads"]["signup"], 2)

    def test_the_dashboard_writes_leads_json(self):
        self.box.log(day_lines(date(2026, 10, 6), 3, NY))
        code, _, err = self.box.run("--today", "2026-10-07", "collect", "--day", "2026-10-06")
        self.assertEqual(code, 0, err)
        code, _, err = self.box.run("--today", "2026-10-07", "dashboard")
        self.assertEqual(code, 0, err)
        path = self.box.root / "www" / "example.com" / "data" / "leads.json"
        got = json.loads(path.read_text())
        self.assertTrue(got["available"], got.get("error"))
        self.assertEqual(got["site"], "example.com")
        self.assertEqual(got["funnel"]["total"]["readers"], 3)    # the 6th's stored journeys


if __name__ == "__main__":
    unittest.main()
