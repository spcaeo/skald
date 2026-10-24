"""Revenue on leads (2.32), the defects an independent review found, each
checked through both counting roads (conversions_revenue.py and
audit_revenue.py): a refund with no sale, a refund before its sale, Stripe's
basil payloads, a refund over or beside its sale, tags holding phone numbers
and addresses, hostile amounts, the WordPress plugin's form fields, and a
raised refund counted on its own day. Hosts are example.com; addresses RFC
5737; the secrets are made up."""
from __future__ import annotations

import sqlite3
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_conversions_hooks import T  # noqa: E402
from test_revenue import DAY, Money, StripeEvents, sale  # noqa: E402

from skald import audit_revenue  # noqa: E402
from skald.conversions import money  # noqa: E402

KIT = Path(__file__).resolve().parents[1] / "skald" / "kit" / "leads"


def refund(ref: str, **kw) -> dict:
    return {"external_ref": ref, "action": "signup", "stage": "refunded", **kw}


def totals(day: dict, cur: str = "USD") -> dict:
    block = (day.get("revenue") or {}).get(cur) or {}
    return {k: block.get(k) for k in audit_revenue.TOTALS}


class Orphans(StripeEvents):
    """1. A refund whose sale is not kept is stored, never counted, and shown."""

    def test_a_refund_with_no_sale_is_not_subtracted_anywhere(self):
        self.event("charge.refunded", {"id": "ch_9", "object": "charge", "payment_intent":
                                       "pi_9", "amount_refunded": 700, "currency": "eur"}, T)
        got = self.blob()
        self.assertEqual(got["withheld"], {})
        self.assertEqual(self.day(got, "2026-10-11")["revenue"], {}, "no Unknown subtraction")
        self.assertEqual(got["currencies"], {})
        self.assertEqual(got["refunds_without_sale"], {"count": 1, "currencies": {"EUR": 700}})

    def test_a_refund_of_a_test_sale_sent_as_test_is_without_a_sale(self):
        self.send(sale("S-1", test=True))
        self.send(refund("S-1", value="10", currency="USD"))
        got = self.blob()
        self.assertEqual(got["withheld"], {})
        self.assertEqual(got["refunds_without_sale"], {"count": 1, "currencies": {"USD": 1000}})
        self.assertEqual(self.day(got, "2026-10-11")["revenue"], {})

    def test_a_site_whose_refunds_all_have_sales_shows_none(self):
        self.send(sale("S-1"))
        self.send(refund("S-1", value="10", currency="USD"))
        got = self.blob()
        self.assertEqual(got["refunds_without_sale"], {"count": 0, "currencies": {}})
        self.assertEqual(totals(self.day(got, "2026-10-11"))["refunded_minor"], 1000)


class Early(StripeEvents):
    """2. A refund that came before its sale moves onto it when the sale comes."""

    def test_a_raise_after_the_sale_is_counted_once(self):
        charge = {"id": "ch_1", "object": "charge", "payment_intent": "pi_1",
                  "amount_refunded": 1000, "currency": "usd"}
        self.event("charge.refunded", charge, T + 10)
        self.checkout(at=T + 20)
        self.event("charge.refunded", {**charge, "amount_refunded": 3000}, T + 60)
        self.assertEqual(self.rows("SELECT external_ref, stage, value_minor FROM conversions "
                                   "ORDER BY id"),
                         [("cs_1", "refunded", 3000), ("cs_1", "paid", 4900)])
        got = self.blob()
        self.assertEqual(got["withheld"], {})
        self.assertEqual(totals(self.day(got, "2026-10-11")),
                         {"gross_minor": 4900, "refunded_minor": 3000, "net_minor": 1900,
                          "sales": 1, "refunds": 2, "new_customers": 1, "renewals": 0})
        self.assertEqual(got["refunds_without_sale"]["count"], 0)

    def test_a_whole_refund_before_its_sale_takes_the_sale_value(self):
        self.send(refund("S-3"), T)
        self.send(sale("S-3"), T + 60)
        self.assertEqual(self.rows("SELECT stage, value_minor, currency FROM conversions "
                                   "ORDER BY id"), [("refunded", 4999, "USD"),
                                                    ("paid", 4999, "USD")])
        got = self.blob()
        self.assertEqual(got["withheld"], {})
        self.assertEqual(totals(self.day(got, "2026-10-11"))["net_minor"], 0)

    def test_an_early_refund_over_its_sale_is_cut_to_it(self):
        self.send(refund("S-4", value="80", currency="USD"), T)
        self.send(sale("S-4"), T + 60)
        self.assertEqual(self.rows("SELECT value_minor FROM conversions WHERE stage = "
                                   "'refunded'"), [(4999,)])
        self.assertEqual(self.blob()["withheld"], {})


class Basil(StripeEvents):
    """3. Stripe API 2025-03-31 (basil) took `payment_intent` off the Invoice and
    `invoice` off the Charge; the invoice_payment.paid event (an InvoicePayment:
    `invoice`, `payment.payment_intent`) links them. Field names from
    docs.stripe.com/changelog/basil/2025-03-31/add-support-for-multiple-partial-
    payments-on-invoices and docs.stripe.com/api/invoice-payment/object."""

    def link(self, invoice, intent, at):
        return self.event("invoice_payment.paid", {
            "id": f"inpay_{invoice}", "object": "invoice_payment", "invoice": invoice,
            "amount_paid": 4900, "currency": "usd", "status": "paid", "is_default": True,
            "payment": {"type": "payment_intent", "payment_intent": intent}}, at)

    def renewal(self, at):
        # basil: no payment_intent on the invoice.
        return self.event("invoice.paid", {
            "id": "in_2", "object": "invoice", "billing_reason": "subscription_cycle",
            "amount_paid": 4900, "currency": "usd", "customer": "cus_1",
            "parent": {"subscription_details": {"subscription": "sub_1", "metadata": {}}}}, at)

    def charge(self, intent, amount, at):
        # basil: no invoice on the charge.
        return self.event("charge.refunded", {"id": f"ch_{intent}", "object": "charge",
                                              "payment_intent": intent, "amount_refunded":
                                              amount, "currency": "usd"}, at)

    def check(self):
        self.assertEqual(self.rows("SELECT external_ref, value_minor FROM conversions WHERE "
                                   "stage = 'refunded'"), [("in_2", 1500)])
        got = self.blob()
        self.assertEqual(got["withheld"], {})
        self.assertEqual(got["refunds_without_sale"]["count"], 0)
        self.assertEqual(totals(self.day(got, "2026-10-12"))["refunded_minor"], 1500)

    def test_a_renewal_refund_after_the_link(self):
        self.checkout()
        self.renewal(T + DAY)
        self.assertEqual(self.link("in_2", "pi_2", T + DAY + 1)[0], 200)
        self.charge("pi_2", 1500, T + DAY + 60)
        self.check()

    def test_a_renewal_refund_before_the_link(self):
        self.checkout()
        self.renewal(T + DAY)
        self.charge("pi_2", 1500, T + DAY + 60)
        self.link("in_2", "pi_2", T + DAY + 120)
        self.check()

    def test_a_link_before_the_renewal(self):
        self.checkout()
        self.link("in_2", "pi_2", T + DAY - 5)
        self.renewal(T + DAY)
        self.charge("pi_2", 1500, T + DAY + 60)
        self.check()

    def test_a_subscription_checkout_refund(self):
        self.checkout(payment_intent=None, invoice="in_1", mode="subscription")
        self.link("in_1", "pi_1", T + 1)
        self.charge("pi_1", 900, T + 60)
        self.assertEqual(self.rows("SELECT external_ref, value_minor FROM conversions WHERE "
                                   "stage = 'refunded'"), [("cs_1", 900)])
        self.assertEqual(self.blob()["withheld"], {})

    def test_an_old_payload_still_finds_its_invoice(self):
        self.checkout()
        self.event("invoice.paid", {"id": "in_2", "object": "invoice", "billing_reason":
                                    "subscription_cycle", "amount_paid": 4900, "currency":
                                    "usd", "customer": "cus_1", "payment_intent": "pi_2"},
                   T + DAY)
        self.event("charge.refunded", {"id": "ch_2", "object": "charge", "payment_intent":
                                       "pi_2", "invoice": "in_2", "amount_refunded": 1500,
                                       "currency": "usd"}, T + DAY + 60)
        self.check()

    def test_the_link_alone_records_nothing(self):
        status, answer = self.link("in_7", "pi_7", T)
        self.assertEqual((status, answer["recorded"]), (200, 0))
        self.assertEqual(self.rows("SELECT COUNT(*) FROM conversions"), [(0,)])


class Fitted(Money):
    """4. A refund is checked against its sale: never more, never another currency."""

    def test_a_refund_over_its_sale_is_cut_with_a_note(self):
        self.send(sale("S-1"))
        status, answer = self.send(refund("S-1", value="500", currency="USD"))
        self.assertEqual(status, 200)
        self.assertIn(money.REFUND_OVER_NOTE, answer["notes"])
        self.assertEqual(self.rows("SELECT value_minor FROM conversions WHERE stage = "
                                   "'refunded'"), [(4999,)])
        got = self.blob()
        self.assertEqual(got["withheld"], {})
        self.assertEqual(totals(self.day(got, "2026-10-11"))["net_minor"], 0)

    def test_a_refund_in_another_currency_keeps_no_value(self):
        self.send(sale("S-2"))
        status, answer = self.send(refund("S-2", value="10", currency="EUR"))
        self.assertIn(money.REFUND_CURRENCY_NOTE, answer["notes"])
        self.assertEqual(self.rows("SELECT value_minor, currency FROM conversions WHERE stage = "
                                   "'refunded'"), [(None, None)])
        got = self.blob()
        self.assertEqual(got["withheld"], {})
        self.assertEqual(sorted(self.day(got, "2026-10-11")["revenue"]), ["USD"])
        self.assertEqual(got["currencies"], {"USD": 2})


class Tags(Money):
    """5. A tag never holds a phone number, an address or a personal key."""

    def test_phone_numbers_addresses_and_personal_keys_are_dropped(self):
        status, answer = self.send(sale("S-4", tags={
            "a": "555-123-4567", "b": "555.123.4567", "c": "192.0.2.10", "d": "192.0.2.1",
            "phone": "pro"}))
        self.assertIn(money.TAGS_NOTE, answer["notes"])
        self.assertEqual(self.rows("SELECT tags FROM conversions"), [(None,)])
        spooled = self.spooled()
        for gone in ("555-123-4567", "555.123.4567", "192.0.2.10", "192.0.2.1", '"phone"'):
            self.assertNotIn(gone, spooled)

    def test_good_tags_are_kept(self):
        self.send(sale("S-5", tags={"plan": "pro", "seats": "12", "v": "2-1"}))
        self.assertEqual(self.rows("SELECT tags FROM conversions"),
                         [('{"plan":"pro","seats":"12","v":"2-1"}',)])

    def test_a_tag_with_seven_digits_in_all(self):
        for value, kept in (("123456", True), ("1234567", False), ("12-34-567", False),
                            ("a1b2c3d4e5f6g7", False), ("12.345", True)):
            got, _ = money.tags_of({"k": value})
            self.assertEqual(got is not None, kept, value)


# value, currency, the minor units both roads must give (None: refused)
HOSTILE = (
    ("49.99", "USD", 4999), ("49.990", "USD", 4999), (".5", "USD", 50), ("5.", "USD", 500),
    ("49.990000000000000000000000000000000001", "USD", None),
    ("1" + "0" * 40, "USD", None), ("0." + "0" * 40 + "1", "USD", None),
    ("-0", "USD", None), (-0.0, "USD", None), ("+5", "USD", None), ("1e3", "USD", None),
    ("1,000", "USD", None), ("1_000", "USD", None), ("１２", "USD", None),
    (" 7 ", "USD", 700), ("", "USD", None), (".", "USD", None), ("5.5", "JPY", None),
    ("500.0", "JPY", 500), ("1.234", "KWD", 1234), ("1.2345", "KWD", None),
    (float("nan"), "USD", None), (float("inf"), "USD", None), (1e300, "USD", None),
    (0.1 + 0.2, "USD", None), (12.5, "USD", 1250), (7, "JPY", 7), (-1, "USD", None),
    (True, "USD", None), (10 ** 10 + 1, "USD", None), (10 ** 9, "JPY", 10 ** 9),
    ("NaN", "USD", None), ("Infinity", "USD", None), ("0x10", "USD", None),
)


class Hostile(Money):
    """6. Every hostile amount gives the same answer on both roads."""

    def test_both_roads_read_every_amount_alike(self):
        for raw, cur, want in HOSTILE:
            with self.subTest(raw=raw, cur=cur):
                self.assertEqual(money.minor(raw, cur), want, "the main road")
                self.assertEqual(audit_revenue._minor(raw, cur), want, "the second count")

    def test_a_long_decimal_is_dropped_and_nothing_is_withheld(self):
        status, answer = self.send(sale("S-1", value="49.990000000000000000000000000000000001"))
        self.assertIn(money.VALUE_NOTE, answer["notes"])
        self.assertEqual(self.rows("SELECT value_minor FROM conversions"), [(None,)])
        self.assertEqual(self.blob()["withheld"], {})


class WordPress(unittest.TestCase):
    """7. Money never comes from the visitor's own form post."""

    def test_the_plugin_reads_no_money_from_post(self):
        php = (KIT / "wordpress" / "skald-leads" / "skald-leads.php").read_text()
        for key in ("skald_value", "skald_currency", "skald_customer_ref", "'skald_' . $key"):
            self.assertNotIn(key, php)
        self.assertIn("apply_filters('skald_leads_lead'", php)
        for line in php.splitlines():
            if "$_POST[" in line and "isset(" not in line.split("$_POST[")[0][-8:]:
                self.assertIn("wp_unslash", line, line)

    def test_the_kit_readme_says_so(self):
        text = (KIT / "README.md").read_text()
        self.assertNotIn("skald_value", text)
        self.assertIn("skald_leads_lead", text)


class OwnDay(Money):
    """8. Each part of a refund counts on the day it arrived."""

    def test_a_raise_counts_on_its_own_day(self):
        self.send(sale("S-1"), T)
        self.send(refund("S-1", value="10", currency="USD"), T + 60)
        self.send(refund("S-1", value="30", currency="USD"), T + DAY)
        self.send(refund("S-1", value="20", currency="USD"), T + DAY + 60)   # smaller: nothing
        got = self.blob()
        self.assertEqual(got["withheld"], {})
        self.assertEqual(totals(self.day(got, "2026-10-11")),
                         {"gross_minor": 4999, "refunded_minor": 1000, "net_minor": 3999,
                          "sales": 1, "refunds": 1, "new_customers": 1, "renewals": 0})
        self.assertEqual(totals(self.day(got, "2026-10-12")),
                         {"gross_minor": 0, "refunded_minor": 2000, "net_minor": -2000,
                          "sales": 0, "refunds": 1, "new_customers": 0, "renewals": 0})
        self.assertEqual(got["ltv"]["currencies"]["USD"]["net_minor"], 1999)

    def test_a_tampered_part_withholds_its_day(self):
        self.send(sale("S-1"), T)
        self.send(refund("S-1", value="10", currency="USD"), T + 60)
        self.send(refund("S-1", value="30", currency="USD"), T + DAY)
        db = sqlite3.connect(self.folder / "conversions.sqlite")
        try:
            db.execute("UPDATE refund_parts SET value_minor = 2500 WHERE value_minor = 2000")
            db.commit()
        finally:
            db.close()
        got = self.blob()
        self.assertIn("days/2026-10-12", got["withheld"])
        self.assertNotIn("days/2026-10-11", got["withheld"])
        self.assertIn("ltv", got["withheld"], "the parts no longer add up to the row's total")


class Lifecycle(Money):
    """A refund's parts go with their row: copied when it is removed, deleted
    when it is pruned; Stripe's links are pruned by the same retention."""

    def test_removed_keeps_the_parts_and_prune_takes_them(self):
        import json
        from datetime import date
        from skald.conversions import store
        self.send(sale("S-1"), T)
        self.send(refund("S-1", value="10", currency="USD"), T + 60)
        self.send(refund("S-1", value="30", currency="USD"), T + DAY)
        db = store.connect(self.folder / "conversions.sqlite")
        try:
            rid = db.execute("SELECT id FROM conversions WHERE stage = 'refunded'").fetchone()[0]
            store.remove(db, rid, "a test of removal")
            row = json.loads(db.execute("SELECT row FROM removed").fetchone()[0])
            self.assertEqual([p["value_minor"] for p in row["refund_parts"]], [1000, 2000])
            self.assertEqual(db.execute("SELECT COUNT(*) FROM refund_parts").fetchone()[0], 0)
            db.execute("INSERT INTO pay_links VALUES ('example.com', 'stripe', 'in_1', 'pi_1', "
                       "'2020-01-01T00:00:00Z')")
            self.send(refund("S-1", value="10", currency="USD"), T + 2 * DAY)
            store.prune(db, date(2028, 1, 1))
            self.assertEqual(db.execute("SELECT COUNT(*) FROM refund_parts").fetchone()[0], 0)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM pay_links").fetchone()[0], 0)
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
