"""#34, the owner's decisions 6 and 7 (11 Nov 2026).

6. A visit whose referrer is a payment page (payment_names.PAYMENT_HOSTS, or
   the site's own `site.checkout_hosts`) is "Returned from payment": never a
   referral, never a new source. Inside the visit gap it continues the open
   visit (its source kept); after the gap it is a visit of its own with that
   label. A lead made after it keeps the source of the visit before it.
7. A lead sent by the script tag takes the source of the visit it was sent
   from (its visitor ID's page views), not the event's own; with no page
   view to prove a visit, the event's own source stays, and a payment page's
   is NULL ("Not recorded").

Each rule is recounted by its own second road (audit.py with audit_labels.py
for the visits, audit_filled.py for the leads), and a planted change is
caught. Hosts are example.com, example.net; addresses RFC 5737.
"""
from __future__ import annotations

import sqlite3
import sys
import unittest
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from conversions_support import VID  # noqa: E402
from support import CHROME, Sandbox, day_lines, line, totals_for  # noqa: E402
import test_conversions_beacon as beacon_tests  # noqa: E402
import test_conversions_hooks as hook_tests  # noqa: E402

from skald import audit_filled, audit_labels, check, dimensions as dim  # noqa: E402
from skald import leads as cms_leads  # noqa: E402
from skald.classify import Group  # noqa: E402
from skald.conversions import normalise, store  # noqa: E402
from skald.payment_names import PAYMENT_HOSTS, RETURNED  # noqa: E402

UTC = timezone.utc
DAY = date(2026, 10, 5)
TODAY = "2026-10-06"
T = datetime(2026, 10, 5, 14, 0, tzinfo=UTC)
SITE = "https://example.com"
WHO = "203.0.113.84"
STRIPE = "https://checkout.stripe.com/c/pay/cs_test_a1b2c3"
PAYPAL = "https://www.paypal.com/checkoutnow?token=EC-0000"


def at(minutes: float, path: str, referrer: str = "-", who: str = WHO) -> str:
    return line(T + timedelta(minutes=minutes), who, path, CHROME, referrer, country="CA")


def paid_inside_the_gap(back_from: str = STRIPE, who: str = WHO) -> list[str]:
    """From a search, to checkout, back from the payment page 12 minutes later."""
    return [at(0, "/pricing", "https://www.google.com/", who),
            at(2, "/checkout", f"{SITE}/pricing", who),
            at(14, "/thank-you?session_id=cs_test_a1b2c3", back_from, who),
            at(15, "/account", f"{SITE}/thank-you", who)]


def paid_after_the_gap(back_from: str = STRIPE, who: str = WHO) -> list[str]:
    """From a search, to checkout, back from the payment page 45 minutes later."""
    return [at(0, "/pricing", "https://www.google.com/", who),
            at(2, "/checkout", f"{SITE}/pricing", who),
            at(47, "/thank-you", back_from, who),
            at(48, "/account", f"{SITE}/thank-you", who)]


# ------------------------------------------------------------ the labels

class TheLabel(unittest.TestCase):
    own = {"example.com"}

    def test_every_payment_host_is_returned_from_payment(self):
        for host in PAYMENT_HOSTS:
            self.assertEqual(dim.source_type(f"https://{host}/x", "/", False, self.own),
                             RETURNED, host)
            self.assertEqual(dim.referrer_label(f"https://{host}/x", self.own), "(payment page)")
        self.assertIn(RETURNED, dim.SOURCE_TYPES)
        self.assertIn(RETURNED, dim.INSIDE_SOURCES)

    def test_only_the_named_hosts(self):
        # stripe.com itself (its docs, its blog) is a website; so is a lookalike.
        for ref in ("https://stripe.com/docs", "https://dashboard.stripe.com/",
                    "https://paypal.com.example.net/", "https://notpaypal.com/"):
            self.assertEqual(dim.source_type(ref, "/", False, self.own), "Other website", ref)

    def test_the_sites_own_checkout_host(self):
        hosts = dim.site_hosts(["example.com"], ["pay.example.net"])
        self.assertEqual(dim.source_type("https://pay.example.net/order/1", "/", False, hosts),
                         RETURNED)
        self.assertNotIn("pay.example.net", hosts, "a checkout host is not the site itself")
        self.assertEqual(dim.source_type("https://pay.example.net/", "/", False, self.own),
                         "Other website", "only when configured")
        got = dim.hosts_of({"site": {"hosts": ["example.com"], "checkout_hosts": "pay.example.net"}})
        self.assertEqual((set(got), set(got.checkout)), ({"example.com"}, {"pay.example.net"}))

    def test_the_audits_labels_agree(self):
        class L:
            url = "/"

        for ref in (STRIPE, PAYPAL, "https://checkout.paypal.com/", "https://stripe.com/"):
            L.referrer = ref
            self.assertEqual(audit_labels.source_of(L, False, self.own),
                             dim.source_type(ref, "/", False, self.own), ref)
            self.assertEqual(audit_labels.referrer_of(L, self.own),
                             dim.referrer_label(ref, self.own), ref)
        L.referrer = "https://pay.example.net/"
        self.assertEqual(audit_labels.source_of(L, False, self.own, {"pay.example.net"}), RETURNED)


# ------------------------------------------------------------ the visits

class TheVisits(unittest.TestCase):

    def visits(self, lines: list[str]):
        totals = totals_for(lines)
        self.assertEqual(check(totals), [])
        people = totals.groups[Group.PEOPLE]
        self.assertEqual(totals.visits.visits, people.readers)
        return totals, people

    def test_a_stripe_return_mid_visit_keeps_the_earlier_source(self):
        totals, people = self.visits(paid_inside_the_gap())
        self.assertEqual((people.visits, people.readers), (1, 1))
        self.assertEqual(people.by["source"], Counter({"Search engine": 1}))
        self.assertEqual(people.by["referrer"], Counter({"google.com": 1}))
        self.assertEqual((totals.journeys[0]["source"], totals.journeys[0]["pages"]),
                         ("Search engine", 4))

    def test_a_stripe_return_after_the_gap_is_returned_from_payment(self):
        totals, people = self.visits(paid_after_the_gap())
        self.assertEqual((people.visits, people.readers), (2, 2))
        self.assertEqual(people.by["source"], Counter({"Search engine": 1, RETURNED: 1}))
        self.assertNotIn("Other website", people.by["source"], "no referral added")
        self.assertEqual(people.by["referrer"], Counter({"google.com": 1, "(payment page)": 1}))
        self.assertEqual([j["source"] for j in totals.journeys], ["Search engine", RETURNED])

    def test_paypal_the_same(self):
        for ref in (PAYPAL, "https://checkout.paypal.com/webapps/hermes"):
            totals, people = self.visits(paid_inside_the_gap(ref))
            self.assertEqual(people.by["source"], Counter({"Search engine": 1}), ref)
            totals, people = self.visits(paid_after_the_gap(ref))
            self.assertEqual(people.by["source"], Counter({"Search engine": 1, RETURNED: 1}),
                             ref)

    def test_a_payment_visit_then_a_new_outside_source_splits(self):
        totals, people = self.visits(paid_after_the_gap() + [
            at(50, "/blog", "https://news.example.org/post")])
        self.assertEqual([j["source"] for j in totals.journeys],
                         ["Search engine", RETURNED, "Other website"])

    def test_the_visit_says_where_it_came_back_from(self):
        from skald.visits import came_from
        self.assertEqual(came_from({"source": RETURNED, "via": "checkout.stripe.com"}),
                         "back from a payment page (checkout.stripe.com)")


class TheAuditAgrees(unittest.TestCase):

    def setUp(self):
        self.box = Sandbox()
        text = self.box.config.read_text().replace(
            "  hosts: [example.com]\n", "  hosts: [example.com]\n"
            "  checkout_hosts: [pay.example.net]\n", 1)
        self.box.config.write_text(text)
        self.box.log(day_lines(DAY, 3) + paid_inside_the_gap() +
                     paid_after_the_gap(PAYPAL, "203.0.113.85") +
                     paid_after_the_gap("https://pay.example.net/order/7", "203.0.113.86"))

    def tearDown(self):
        self.box.close()

    def counts(self, kind: str) -> dict:
        db = sqlite3.connect(str(self.box.db))
        try:
            return dict(db.execute(
                "SELECT name, n FROM counts WHERE site = 'example.com' AND day = ? AND kind = ?",
                (DAY.isoformat(), kind)).fetchall())
        finally:
            db.close()

    def test_collected_and_recounted_exactly(self):
        code, out, err = self.box.run("--today", TODAY, "collect")
        self.assertEqual(code, 0, err)
        code, out, err = self.box.run("--today", TODAY, "audit")
        self.assertEqual(code, 0, err + out)
        self.assertIn("all match", out)
        got = self.counts("reader_source")
        self.assertEqual(got.get(RETURNED), 2, "PayPal and the site's own checkout, after the gap")
        self.assertNotIn("checkout.stripe.com", self.counts("reader_referrer"))
        self.assertEqual(self.counts("reader_referrer").get("(payment page)"), 2)

    def test_a_planted_change_is_caught(self):
        # The main road counted with the old rule (a payment page a referral
        # that splits the visit): the audit's own road disagrees.
        with mock.patch.object(dim, "_PAYMENT", frozenset()), \
                mock.patch.object(dim, "INSIDE_SOURCES", ("This site", "Direct or unknown")):
            code, out, err = self.box.run("--today", TODAY, "collect")
        self.assertEqual(code, 0, err)
        code, out, err = self.box.run("--today", TODAY, "audit")
        self.assertEqual(code, 1, out)
        self.assertIn("readers by source: Other website: history has 2, the recount finds 0",
                      err)
        self.assertIn("readers by source: Returned from payment", err)


# ------------------------------------------------------- hook leads (6)

class HookLeads(hook_tests.Base):

    def views(self, *rows):
        db = store.connect(self.folder / "conversions.sqlite")
        try:
            for when, path, source in rows:
                store.record_page_view(db, "example.com", VID, when, path, source, "",
                                       "(no campaign tag)")
        finally:
            db.close()

    def row(self) -> dict:
        db = store.connect(self.folder / "conversions.sqlite")
        try:
            return dict(db.execute("SELECT * FROM conversions WHERE external_ref = 'L-1'")
                        .fetchone())
        finally:
            db.close()

    def audit(self) -> dict:
        return audit_filled.check(self.folder / "conversions.sqlite", "example.com", UTC,
                                  date(2026, 9, 1), date(2026, 10, 31))

    def test_a_last_touch_from_stripe_keeps_the_first_touchs_source(self):
        got = self.post("lead", hook_tests.lead(
            vid=None, first_touch={"referrer": "https://www.google.com/", "landing": "/"},
            last_touch={"referrer": STRIPE, "landing": "/thank-you"}))
        self.assertEqual(got[0], 200)
        row = self.row()
        self.assertEqual((row["source_type"], row["first_source"]),
                         ("Search engine", "Search engine"))
        self.assertEqual(self.audit(), {})

    def test_a_sender_cannot_name_it_a_source(self):
        rec = {"action": "demo", "stage": "completed", "external_ref": "x",
               "source_type": RETURNED, "last_touch": {"referrer": PAYPAL}}
        got = normalise.row(rec, "example.com", "lead", "2026-10-11T12:00:00Z", set(), False)
        self.assertEqual((got["source_type"], got["first_source"]), (None, None))

    def test_page_views_skip_a_payment_return_back_to_the_visit_before(self):
        self.views(("2026-10-10T09:00:00Z", "/blog/", "Social media"),
                   ("2026-10-10T09:05:00Z", "/pricing/", "This site"),
                   ("2026-10-11T11:40:00Z", "/thank-you/", RETURNED),
                   ("2026-10-11T11:45:00Z", "/account/", RETURNED))
        self.assertEqual(self.post("lead", hook_tests.lead(last_touch=None))[0], 200)
        row = self.row()
        self.assertEqual((row["source_type"], row["first_source"], row["landing"]),
                         ("Social media", "Social media", "/blog/"))
        self.assertEqual(self.audit(), {})
        # A planted change: the row as the old rule filled it.
        db = sqlite3.connect(str(self.folder / "conversions.sqlite"))
        try:
            db.execute("UPDATE conversions SET source_type = ? WHERE external_ref = 'L-1'",
                       (RETURNED,))
            db.commit()
        finally:
            db.close()
        problems = [p for day in self.audit().values() for p in day]
        self.assertTrue(any("never a lead's source" in p for p in problems), problems)
        self.assertTrue(any("its page views say 'Social media'" in p for p in problems),
                        problems)


class CmsLeads(unittest.TestCase):
    """The website's own lead database (leads.json): the same rule, both roads."""

    def test_kept_touches(self):
        google = {"referrerHost": "google.com", "landingPath": "/"}
        stripe = {"referrerHost": "checkout.stripe.com", "landingPath": "/thank-you"}
        self.assertEqual(cms_leads.kept_touches(google, stripe), (google, google))
        self.assertEqual(cms_leads.kept_touches(stripe, stripe), (None, None))
        self.assertEqual(cms_leads.kept_touches(google, None), (google, None))

    def test_find_a_person_reads_the_same_rule(self):
        import json
        import tempfile
        from skald.people import lookup
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "leads.sqlite"
            db = sqlite3.connect(path)
            db.execute("CREATE TABLE submissions (id INTEGER PRIMARY KEY, created_at TEXT, "
                       "updated_at TEXT, type TEXT, status TEXT, page TEXT, first_touch TEXT, "
                       "last_touch TEXT, session_id TEXT, ip_country TEXT, flags TEXT)")
            db.execute("INSERT INTO submissions VALUES (1, '2026-10-06T10:00:00Z', NULL, "
                       "'demo', 'new', '/', ?, ?, '', 'CA', '')",
                       (json.dumps({"referrerHost": "google.com", "landingPath": "/"}),
                        json.dumps({"referrerHost": "checkout.stripe.com",
                                    "landingPath": "/thank-you"})))
            db.commit()
            db.close()
            with mock.patch("skald.leads.db_path", return_value=str(path)):
                rows = lookup._lead_rows({})
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0]["first_source"], rows[0]["last_source"]),
                         ("Search engine", "Search engine"), "the payment return is no source")


# ----------------------------------------------- script-tag leads (6, 7)

class ScriptTagLeads(beacon_tests.Server):

    def audit(self) -> dict:
        return audit_filled.check(self.db_path, "example.com", UTC, beacon_tests.DAY,
                                  beacon_tests.DAY + timedelta(days=1))

    def page(self, path: str, referrer: str = "", after: float = 0) -> None:
        self.post(beacon_tests.body(e="page_view", p=path, id=None, r=referrer or None),
                  after=after)

    def lead(self, referrer: str = "", after: float = 30) -> dict:
        self.post(beacon_tests.body(e="form_submit", p="/thank-you/", id="contact",
                                    r=referrer or None), after=after)
        return self.rows()[-1]

    def test_a_lead_takes_its_visits_first_touch(self):
        self.page("/pricing/", "google.com")
        self.page("/contact/", after=60)          # the tab lost its session source
        got = self.lead()                          # sent with no referrer: "Direct or unknown"
        self.assertEqual(got["source_type"], "Search engine")
        self.assertIn("source_type", got["filled"])
        self.assertEqual(self.audit(), {})

    def test_after_a_stripe_return_inside_the_gap(self):
        self.page("/pricing/", "linkedin.com")
        self.page("/thank-you/", "checkout.stripe.com", after=600)
        got = self.lead("checkout.stripe.com")
        self.assertEqual((got["source_type"], got["first_source"]),
                         ("Social media", "Social media"))
        self.assertEqual(self.audit(), {})

    def test_after_a_stripe_return_past_the_gap(self):
        self.page("/pricing/", "linkedin.com")
        self.page("/thank-you/", "checkout.stripe.com", after=45 * 60)
        got = self.lead("checkout.stripe.com")
        self.assertEqual(got["source_type"], "Social media", "the visit before it")
        pages = self.rows("SELECT source_type FROM journeys ORDER BY at")
        self.assertEqual([p["source_type"] for p in pages], ["Social media", RETURNED])
        self.assertEqual(self.audit(), {})

    def test_no_proven_visit_keeps_the_events_own_source(self):
        got = self.lead("google.com")
        self.assertEqual((got["source_type"], got["filled"]), ("Search engine", None))
        self.assertEqual(self.audit(), {})

    def test_no_proven_visit_from_a_payment_page_stays_unknown(self):
        got = self.lead("checkout.stripe.com")
        self.assertEqual((got["source_type"], got["first_source"]), (None, None))
        self.assertEqual(self.audit(), {})

    def test_a_planted_change_is_caught(self):
        self.page("/pricing/", "google.com")
        self.lead()
        db = sqlite3.connect(str(self.db_path))
        try:
            db.execute("UPDATE conversions SET source_type = 'Direct or unknown'")
            db.commit()
        finally:
            db.close()
        problems = [p for day in self.audit().values() for p in day]
        self.assertTrue(any("source_type" in p and "Search engine" in p for p in problems),
                        problems)


if __name__ == "__main__":
    unittest.main()
