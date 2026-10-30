"""Revenue on leads (2.32): the hook's money fields and their notes, the
schema 9 rebuild, Stripe's amounts, renewals and refunds, conversions.json's
`revenue` and `ltv`, and the second count (audit_revenue.py) agreeing on good
data and withholding a day whose row was changed. Hosts are example.com;
addresses RFC 5737; the secrets are made up."""
from __future__ import annotations

import json
import sqlite3
import sys
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from conversions_support import SECRET, FakeHandler  # noqa: E402
from test_conversions_hooks import Base, T  # noqa: E402

from skald import audit_revenue, conversions_data  # noqa: E402
from skald.conversions import money, store  # noqa: E402
from skald.conversions.adapters import adapter  # noqa: E402
from skald.conversions.adapters.lead import sign_get  # noqa: E402

UTC = timezone.utc
DAY = 86400
TODAY = date(2026, 10, 13)
NOW = datetime(2026, 10, 13, 12, 0, tzinfo=UTC)
GOOGLE = {"referrer": "https://www.google.com/", "landing": "/pricing/"}
NEWS = {"utm_source": "newsletter", "utm_medium": "email", "landing": "/blog/"}


def sale(ref, **kw) -> dict:
    out = {"external_ref": ref, "action": "signup", "stage": "paid", "value": "49.99",
           "currency": "USD", "last_touch": GOOGLE, "first_touch": GOOGLE}
    out.update(kw)
    return out


class Money(Base):
    def send(self, body, at=None, tool="lead"):
        if at is not None:
            self.now = at
        return self.post(tool, body)

    def blob(self, **kw):
        return conversions_data.blob(self.config, self.folder, "example.com", UTC, TODAY, NOW,
                                     **kw)

    def day(self, got, d: str) -> dict:
        return next(x for x in got["days"] if x["day"] == d)


class Fields(Money):
    def test_money_fields_are_kept_as_minor_units(self):
        got = self.send(sale("S-1", customer_ref="cust_1", tags={"Plan": "Pro", "seats": 5}))
        self.assertEqual(got, (200, {"ok": True, "recorded": 1, "duplicates": 0}))
        self.assertEqual(self.rows("SELECT value_minor, currency, customer_ref, tags FROM "
                                   "conversions"),
                         [(4999, "USD", "cust_1", '{"plan":"pro","seats":"5"}')])

    def test_zero_and_three_decimal_currencies(self):
        self.send(sale("J-1", value=500, currency="jpy"))
        self.send(sale("K-1", value="1.234", currency="KWD"))
        self.assertEqual(self.rows("SELECT external_ref, value_minor, currency FROM conversions "
                                   "ORDER BY id"), [("J-1", 500, "JPY"), ("K-1", 1234, "KWD")])
        self.assertIsNone(money.minor("5.5", "JPY"), "JPY has no decimals")
        self.assertEqual(money.minor("49.990", "USD"), 4999)
        self.assertEqual(money.shown(1234, "KWD"), "1.234")

    def test_a_bad_optional_field_is_dropped_with_a_note_never_refused(self):
        cases = [({"value": "49.999"}, money.VALUE_NOTE), ({"value": -1}, money.VALUE_NOTE),
                 ({"currency": None}, money.VALUE_NOTE), ({"currency": "XYZ"}, money.VALUE_NOTE),
                 ({"value": True}, money.VALUE_NOTE), ({"value": "1e3"}, money.VALUE_NOTE),
                 ({"value": 10 ** 11}, money.VALUE_NOTE),
                 ({"customer_ref": "person@example.com"}, money.CUSTOMER_NOTE),
                 ({"tags": {"phone": "5551234567"}}, money.TAGS_NOTE),
                 ({"tags": {f"k{i}": "v" for i in range(6)}}, money.TAGS_NOTE),
                 ({"tags": ["plan"]}, money.TAGS_NOTE)]
        for i, (bad, note) in enumerate(cases):
            with self.subTest(bad=bad):
                status, answer = self.send(sale(f"B-{i}", **bad))
                self.assertEqual(status, 200)
                self.assertEqual(answer["recorded"], 1)
                self.assertIn(note, answer["notes"])
        rows = dict(((r[0], r[1:]) for r in self.rows(
            "SELECT external_ref, value_minor, currency, customer_ref, tags FROM conversions")))
        self.assertEqual(rows["B-0"], (None, None, None, None), "value and currency dropped")
        self.assertEqual(rows["B-7"], (4999, "USD", None, None), "only the email dropped")
        self.assertEqual(json.loads(rows["B-9"][3]), {f"k{i}": "v" for i in range(5)})
        logged = self.rows("SELECT error FROM deliveries WHERE external_ref = 'B-7'")
        self.assertIn("customer_ref", logged[0][0])
        self.assertNotIn("person@example.com", self.spooled(), "never an email in the spool")
        self.assertNotIn("5551234567", self.spooled(), "never a phone number in the spool")

    def test_a_refund_without_value_is_the_whole_sale(self):
        self.send(sale("R-1", value="20.00"))
        self.send({"external_ref": "R-1", "action": "signup", "stage": "refunded"})
        self.assertEqual(self.rows("SELECT stage, value_minor, currency FROM conversions "
                                   "ORDER BY id"), [("paid", 2000, "USD"),
                                                    ("refunded", 2000, "USD")])

    def test_a_larger_refund_total_raises_the_one_row(self):
        self.send(sale("R-2", value="30"))
        self.send({"external_ref": "R-2", "action": "signup", "stage": "refunded",
                   "value": "10", "currency": "USD"})
        got = self.send({"external_ref": "R-2", "action": "signup", "stage": "refunded",
                         "value": "25", "currency": "USD"})
        self.assertEqual(got[1]["recorded"], 1)
        self.send({"external_ref": "R-2", "action": "signup", "stage": "refunded",
                   "value": "5", "currency": "USD"})
        self.assertEqual(self.rows("SELECT value_minor FROM conversions WHERE stage = "
                                   "'refunded'"), [(2500,)], "one row, the largest total")

    def test_reconcile_get_returns_the_money(self):
        self.send(sale("G-1", customer_ref="cust_9", tags={"plan": "pro"}))
        target = "/traffic-hooks/example.com/leads"
        status, got = self.rx.http(FakeHandler(target, b"", sign_get(target, SECRET, self.now),
                                               "GET"))
        self.assertEqual(status, 200)
        row = got["rows"][0]
        self.assertEqual({k: row[k] for k in ("value", "value_minor", "currency",
                                              "customer_ref", "tags")},
                         {"value": "49.99", "value_minor": 4999, "currency": "USD",
                          "customer_ref": "cust_9", "tags": {"plan": "pro"}})


class Migration(unittest.TestCase):
    """A schema 8 file (made here as 2.31 made it) is rebuilt to schema 9."""

    def test_every_row_kept_with_its_id_test_label_and_identity(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "conversions.sqlite"
            old = sqlite3.connect(path)
            # Schema 10 (2.45) adds columns by ALTER on top: the file goes to the latest.
            old.executescript(store.SCHEMA.replace(
                store.CONVERSIONS.format(name="conversions"),
                store.CONVERSIONS_V8.format(name="conversions")))
            old.execute("INSERT INTO meta VALUES ('schema_version', '8')")
            old.execute("INSERT INTO identities (id, site, email_hash, email, name, created_at) "
                        "VALUES (7, 'example.com', 'h', 'person@example.com', 'A Person', "
                        "'2026-10-01T00:00:00Z')")
            for i, (stage, test, label, ident) in enumerate(
                    [("completed", 0, "sales", 7), ("paid", 1, None, None),
                     ("started", 2, "support", None)], start=40):
                old.execute("INSERT INTO conversions (id, site, action, stage, at, external_ref, "
                            "tool, received_at, test, label, identity_id) VALUES "
                            "(?, 'example.com', 'signup', ?, '2026-10-01T10:00:00Z', 'L-1', "
                            "'lead', '2026-10-01T10:00:00Z', ?, ?, ?)",
                            (i, stage, test, label, ident))
            old.commit()
            with self.assertRaises(sqlite3.IntegrityError):
                old.execute("INSERT INTO conversions (site, action, stage, at, external_ref, "
                            "tool, received_at) VALUES ('example.com', 'signup', 'refunded', "
                            "'2026-10-01T10:00:00Z', 'L-2', 'lead', '2026-10-01T10:00:00Z')")
            old.close()
            db = store.connect(path)
            try:
                self.assertEqual(store.schema_version(db), store.SCHEMA_VERSION)
                self.assertEqual(
                    [tuple(r) for r in db.execute(
                        "SELECT id, stage, test, label, identity_id, value_minor, currency, "
                        "customer_ref, tags, pay_ref FROM conversions ORDER BY id")],
                    [(40, "completed", 0, "sales", 7, None, None, None, None, None),
                     (41, "paid", 1, None, None, None, None, None, None, None),
                     (42, "started", 2, "support", None, None, None, None, None, None)])
                self.assertTrue(store.record_conversion(db, {
                    "site": "example.com", "action": "signup", "stage": "refunded",
                    "at": "2026-10-02T10:00:00Z", "external_ref": "L-1", "tool": "lead",
                    "value_minor": 100, "currency": "USD"}))
                names = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE "
                                                  "type = 'index'")}
                self.assertTrue({"conversions_at", "conversions_vid", "conversions_received",
                                 "conversions_customer", "conversions_pay"} <= names)
            finally:
                db.close()
            self.assertTrue((Path(tmp) / "conversions.sqlite.v8.bak").is_file(),
                            "a copy of the old file is kept first")


class StripeEvents(Money):
    def event(self, kind, obj, at):
        self.now = at
        return self.post("stripe", {"id": f"evt_{kind}_{at}", "object": "event",
                                    "created": at, "type": kind, "data": {"object": obj}})

    def checkout(self, at=T, **kw):
        obj = {"id": "cs_1", "object": "checkout.session", "payment_status": "paid",
               "amount_total": 4900, "currency": "usd", "customer": "cus_1",
               "payment_intent": "pi_1", "customer_details": {"email": "person@example.com"}}
        obj.update(kw)
        return self.event("checkout.session.completed", obj, at)


class Stripe(StripeEvents):

    def test_a_checkout_keeps_its_amount_customer_and_payment(self):
        self.checkout()
        self.assertEqual(self.rows("SELECT stage, value_minor, currency, customer_ref, pay_ref "
                                   "FROM conversions"), [("paid", 4900, "USD", "cus_1", "pi_1")])
        self.assertNotIn("person@example.com", self.spooled())

    def test_renewals_and_partial_refunds(self):
        self.checkout()
        sub = {"id": "in_2", "object": "invoice", "billing_reason": "subscription_cycle",
               "amount_paid": 4900, "currency": "usd", "customer": "cus_1",
               "payment_intent": "pi_2", "parent": {"subscription_details": {
                   "metadata": {"skv": "skv_" + "R" * 22}}}}
        self.event("invoice.paid", sub, T + DAY)
        self.event("invoice.paid", {**sub, "id": "in_1", "billing_reason":
                                    "subscription_create"}, T + DAY)
        charge = {"id": "ch_1", "object": "charge", "payment_intent": "pi_1",
                  "amount_refunded": 1000, "currency": "usd"}
        self.event("charge.refunded", charge, T + DAY)
        self.event("charge.refunded", {**charge, "amount_refunded": 3000}, T + DAY + 60)
        self.event("charge.refunded", {**charge, "amount_refunded": 1000}, T + DAY + 120)
        self.assertEqual(self.rows("SELECT external_ref, stage, value_minor, vid FROM "
                                   "conversions ORDER BY id"),
                         [("cs_1", "paid", 4900, None), ("in_2", "paid", 4900, "skv_" + "R" * 22),
                          ("cs_1", "refunded", 3000, None)])
        got = self.blob()
        self.assertEqual(got["withheld"], {})
        day1, day2 = self.day(got, "2026-10-11"), self.day(got, "2026-10-12")
        self.assertEqual({k: day1["revenue"]["USD"][k] for k in audit_revenue.TOTALS},
                         {"gross_minor": 4900, "refunded_minor": 0, "net_minor": 4900,
                          "sales": 1, "refunds": 0, "new_customers": 1, "renewals": 0})
        self.assertEqual({k: day2["revenue"]["USD"][k] for k in audit_revenue.TOTALS},
                         {"gross_minor": 4900, "refunded_minor": 3000, "net_minor": 1900,
                          "sales": 1, "refunds": 2, "new_customers": 0, "renewals": 1},
                         "two refunds came: 1000, then a total of 3000 (2000 more)")
        self.assertEqual(got["ltv"]["currencies"]["USD"]["customers"], 1)
        self.assertEqual(got["ltv"]["currencies"]["USD"]["net_minor"], 6800)
        self.assertEqual(got["ltv"]["currencies"]["USD"]["repeat_customers"], 1)

    def test_a_refund_of_a_sale_marked_test_is_test_too(self):
        self.checkout()
        db = store.connect(self.folder / "conversions.sqlite")
        try:
            store.mark_refs(db, "example.com", "stripe", ["cs_1"])
        finally:
            db.close()
        self.event("charge.refunded", {"id": "ch_1", "object": "charge", "payment_intent":
                                       "pi_1", "amount_refunded": 900, "currency": "usd"}, T)
        self.assertEqual(self.rows("SELECT external_ref, stage, test FROM conversions ORDER BY "
                                   "id"), [("cs_1", "paid", 1), ("cs_1", "refunded", 1)])
        got = self.blob()
        self.assertEqual(got["withheld"], {}, "the spool's count finds the refund's sale too")
        self.assertIsNone(got["currencies"], "test rows are never money")

    def test_isk_is_sent_in_hundredths(self):
        self.checkout(amount_total=50000, currency="isk")
        self.checkout(id="cs_2", amount_total=50050, currency="isk", payment_intent="pi_9")
        self.assertEqual(self.rows("SELECT value_minor, currency FROM conversions ORDER BY id"),
                         [(500, "ISK"), (None, None)])

    def test_a_refund_with_no_sale_kept_stays_on_its_payment(self):
        self.event("charge.refunded", {"id": "ch_9", "object": "charge", "payment_intent":
                                       "pi_9", "amount_refunded": 700, "currency": "eur"}, T)
        self.assertEqual(self.rows("SELECT external_ref, stage, value_minor FROM conversions"),
                         [("pi_9", "refunded", 700)])
        self.assertEqual(self.blob()["withheld"], {})


class Counting(Money):
    def setUp(self):
        super().setUp()
        # Day 1: a USD sale from Google (customer A), a EUR one from the newsletter
        # (no customer ref), a JPY one; a test sale and a sale later removed.
        self.send(sale("U-1", customer_ref="cust_a", tags={"plan": "pro"}, label="sales"), T)
        self.send(sale("E-1", value="10.50", currency="EUR", last_touch=NEWS, first_touch=NEWS),
                  T + 60)
        self.send(sale("J-1", value=1200, currency="JPY"), T + 120)
        self.send(sale("X-1", value="999", test=True), T + 180)
        self.send(sale("D-1", value="77"), T + 240)
        db = store.connect(self.folder / "conversions.sqlite")
        try:
            gone = db.execute("SELECT id FROM conversions WHERE external_ref = 'D-1'").fetchone()
            store.remove(db, gone[0], "a test of removal")
        finally:
            db.close()
        # Day 2: customer A renews (a new ref), A's first sale is part-refunded;
        # a sign-up completes then pays (one lead, one sale: the paid row).
        self.send(sale("U-2", value="49.99", customer_ref="cust_a", last_touch=None,
                       first_touch=None), T + DAY)
        self.send({"external_ref": "U-1", "action": "signup", "stage": "refunded",
                   "value": "9.99", "currency": "USD"}, T + DAY + 60)
        self.send(sale("P-1", stage="completed", value="5", last_touch=NEWS, first_touch=NEWS),
                  T + DAY + 120)
        self.send(sale("P-1", value="20", last_touch=None, first_touch=None), T + DAY + 180)

    def test_the_revenue_block(self):
        got = self.blob()
        self.assertEqual(got["withheld"], {})
        self.assertEqual(got["currencies"], {"EUR": 2, "JPY": 0, "USD": 2})
        d1, d2 = self.day(got, "2026-10-11")["revenue"], self.day(got, "2026-10-12")["revenue"]
        self.assertEqual(sorted(d1), ["EUR", "JPY", "USD"], "two currencies and more, never one")
        self.assertEqual((d1["USD"]["gross_minor"], d1["USD"]["sales"]), (4999, 1),
                         "the test and the removed sale left out")
        self.assertEqual(d1["JPY"]["gross_minor"], 1200)
        self.assertEqual(d1["EUR"]["by"]["source"], {"Email": {"net_minor": 1050, "sales": 1}})
        self.assertEqual(d1["USD"]["by"]["label"], {"sales": {"net_minor": 4999, "sales": 1}})
        self.assertEqual(d1["USD"]["by"]["tag"], {"plan": {"pro": {"net_minor": 4999,
                                                                   "sales": 1}}})
        usd = d2["USD"]
        self.assertEqual({k: usd[k] for k in audit_revenue.TOTALS},
                         {"gross_minor": 4999 + 2000, "refunded_minor": 999,
                          "net_minor": 4999 + 2000 - 999, "sales": 2, "refunds": 1,
                          "new_customers": 1, "renewals": 1})
        # The refund is counted on its own day, under its sale's source and tag.
        self.assertEqual(usd["by"]["tag"], {"plan": {"pro": {"net_minor": -999, "sales": 0}}})
        self.assertEqual(usd["by"]["source"]["Search engine"]["net_minor"], -999)
        # The paid row is the sale, its attribution the lead's first finish (the newsletter).
        self.assertEqual(usd["by"]["source"]["Email"], {"net_minor": 2000, "sales": 1})
        self.assertEqual(self.day(got, "2026-10-12")["stages"]["signup"],
                         {"paid": 1, "completed": 1, "refunded": 1},
                         "a paid after its completed is one lead: the paid row is not a lead")

    def test_ltv(self):
        got = self.blob()["ltv"]["currencies"]
        self.assertEqual(got["USD"]["customers"], 2)
        self.assertEqual(got["USD"]["renewals"], 1)
        self.assertEqual(got["USD"]["repeat_customers"], 1)
        self.assertEqual(got["USD"]["net_minor"], 4999 + 4999 - 999 + 2000)
        self.assertEqual(got["USD"]["by_first_source"]["Search engine"],
                         {"customers": 1, "net_minor": 4999 + 4999 - 999, "renewals": 1,
                          "repeat_customers": 1})
        self.assertEqual(got["USD"]["by_first_source"]["Email"]["customers"], 1,
                         "the paid sign-up: the first source of its lead")
        self.assertEqual(got["EUR"]["customers"], 1)

    def test_a_site_without_money_has_no_revenue(self):
        db = store.connect(self.folder / "conversions.sqlite")
        try:
            db.execute("UPDATE conversions SET value_minor = NULL, currency = NULL")
        finally:
            db.close()
        got = self.blob(audited=False)
        self.assertIsNone(got["currencies"])
        self.assertIsNone(got["ltv"])
        self.assertNotIn("revenue", self.day(got, "2026-10-11"))

    def test_a_changed_row_is_withheld(self):
        db = store.connect(self.folder / "conversions.sqlite")
        try:
            db.execute("UPDATE conversions SET value_minor = 5999 WHERE external_ref = 'U-1' "
                       "AND stage = 'paid'")
        finally:
            db.close()
        got = self.blob()
        self.assertEqual(self.day(got, "2026-10-11")["state"], "withheld")
        self.assertIn("spool recount", self.day(got, "2026-10-11")["why"])
        self.assertEqual(self.day(got, "2026-10-12")["state"], "ok")
        self.assertEqual(got["ltv"]["state"], "withheld")

    def test_a_changed_refund_withholds_its_own_day(self):
        db = store.connect(self.folder / "conversions.sqlite")
        try:
            db.execute("UPDATE refund_parts SET value_minor = 1")
        finally:
            db.close()
        got = self.blob()
        self.assertEqual(self.day(got, "2026-10-11")["state"], "ok")
        self.assertEqual(self.day(got, "2026-10-12")["state"], "withheld")

    def test_a_changed_refund_total_withholds_the_lifetime_value(self):
        db = store.connect(self.folder / "conversions.sqlite")
        try:
            db.execute("UPDATE conversions SET value_minor = 1 WHERE stage = 'refunded'")
        finally:
            db.close()
        got = self.blob()
        self.assertEqual(self.day(got, "2026-10-12")["state"], "ok", "its parts still agree")
        self.assertEqual(got["ltv"]["state"], "withheld", "the parts no longer add up to it")

    def test_the_sql_road_alone_finds_a_planted_figure(self):
        got = self.blob(audited=False)
        self.day(got, "2026-10-11")["revenue"]["USD"]["by"]["country"] = {
            "CA": {"net_minor": 4999, "sales": 1}}
        problems = audit_revenue.check(self.config, self.folder, "example.com", UTC,
                                       date(2026, 4, 17), TODAY, got)
        self.assertEqual(list(problems), ["days/2026-10-11"])
        self.assertTrue(all("SQL recount" in p for p in problems["days/2026-10-11"]))

    def test_conversions_list_shows_the_value(self):
        from types import SimpleNamespace
        from skald.cli_conversions import cmd_conversions_list
        said = []
        ctx = SimpleNamespace(config=self.config, db_path=self.folder / "history.sqlite",
                              args=SimpleNamespace(site="example.com", test=False, limit=50),
                              out=said.append)
        self.assertEqual(cmd_conversions_list(ctx), 0)
        self.assertTrue(any("12.00 JPY" not in line and "1200 JPY" in line for line in said))
        self.assertTrue(any("49.99 USD" in line for line in said))

    def test_the_lead_drawer_carries_the_money(self):
        from skald.people import leadlist
        got = leadlist.rows(self.config, self.folder, "example.com", date(2026, 10, 11),
                            TODAY, False)
        u1 = next(r for r in got["rows"] if r["ref"] == "U-1")
        self.assertEqual((u1["value_minor"], u1["currency"], u1["refunded_minor"],
                          u1["customer_ref"], u1["tags"]),
                         (4999, "USD", 999, "cust_a", {"plan": "pro"}))
        p1 = next(r for r in got["rows"] if r["ref"] == "P-1")
        self.assertEqual((p1["stage"], p1["value_minor"]), ("completed", 2000))

    def test_the_drawer_takes_the_customer_from_the_sale(self):
        from skald.people import leadlist
        self.send(sale("Q-1", stage="completed", value=None), T + DAY + 200)
        self.send(sale("Q-1", value="30", customer_ref="cust_q", tags={"tier": "gold"}),
                  T + DAY + 240)
        got = leadlist.rows(self.config, self.folder, "example.com", date(2026, 10, 11),
                            TODAY, False)
        q1 = next(r for r in got["rows"] if r["ref"] == "Q-1")
        self.assertEqual((q1["value_minor"], q1["customer_ref"], q1["tags"]),
                         (3000, "cust_q", {"tier": "gold"}), "the sale's, as Revenue counts")


if __name__ == "__main__":
    unittest.main()
