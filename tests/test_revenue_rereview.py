"""Revenue on leads (2.32), the second review's findings, each checked through
both counting roads (conversions_revenue.py and audit_revenue.py): days
before the first value are not recorded (never 0), very long amounts, a
removal replayed at the time it happened, a refund kept without a value,
a whole refund after an unreadable one, a refund of 0, and a customer_ref
that is a phone number or an address. Hosts are example.com; addresses RFC
5737; the secrets are made up."""
from __future__ import annotations

import json
import sys
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_conversions_hooks import T  # noqa: E402
from test_revenue import DAY, TODAY, UTC, Money, StripeEvents, sale  # noqa: E402
from test_revenue_review import refund, totals  # noqa: E402

from skald import audit_revenue  # noqa: E402
from skald.conversions import money, store  # noqa: E402


class Removing(StripeEvents):
    """Rows taken away (store.remove) at the test's own clock."""

    def remove(self, ref: str, stage: str) -> None:
        real = store.stamp
        clock = lambda when=None: real(when or datetime.fromtimestamp(self.now, timezone.utc))  # noqa: E731
        db = store.connect(self.folder / "conversions.sqlite")
        try:
            with mock.patch.object(store, "stamp", clock):
                rid = db.execute("SELECT id FROM conversions WHERE external_ref = ? AND "
                                 "stage = ?", (ref, stage)).fetchone()[0]
                store.remove(db, rid, "a test of removal")
        finally:
            db.close()


class FirstDay(Money):
    """1. Revenue is recorded from the local day of the first value on, never 0 before."""

    def setUp(self):
        super().setUp()
        self.send({"external_ref": "N-1", "action": "signup", "stage": "completed"}, T - 5 * DAY)
        self.send(sale("S-1", value="100"), T)

    def test_days_before_the_first_value_carry_no_revenue(self):
        got = self.blob()
        self.assertEqual(got["withheld"], {})
        self.assertEqual(got["revenue_since"], "2026-10-11")
        before = self.day(got, "2026-10-06")
        self.assertEqual(before["state"], "ok")
        self.assertNotIn("revenue", before, "not recorded: absent, never {}")
        self.assertNotIn("revenue", self.day(got, "2026-10-10"))
        self.assertEqual(self.day(got, "2026-10-12")["revenue"], {}, "a known none")
        self.assertEqual(totals(self.day(got, "2026-10-11"))["gross_minor"], 10000)

    def test_a_revenue_block_planted_before_the_first_value_is_withheld(self):
        got = self.blob(audited=False)
        self.day(got, "2026-10-08")["revenue"] = {}
        problems = audit_revenue.check(self.config, self.folder, "example.com", UTC,
                                       date(2026, 4, 17), TODAY, got)
        self.assertIn("days/2026-10-08", problems)
        got = self.blob(audited=False)
        got["revenue_since"] = "2026-10-01"
        problems = audit_revenue.check(self.config, self.folder, "example.com", UTC,
                                       date(2026, 4, 17), TODAY, got)
        self.assertIn("revenue_since", problems)

    def test_a_disputed_first_day_is_withheld_even_when_the_file_says_none(self):
        from skald import conversions_data
        out = conversions_data.withhold({"days": [], "revenue_since": None},
                                        {"revenue_since": ["file None, SQL 2026-10-11"]})
        self.assertEqual(out["revenue_since"]["state"], "withheld")

    def test_a_site_with_no_value_has_none(self):
        from test_revenue import Money as Plain  # noqa: F401
        got = self.blob()
        self.assertTrue(all("revenue" not in d for d in got["days"] if d["day"] < "2026-10-11"))


class LongAmounts(Money):
    """2. An amount longer than MAX_AMOUNT_TEXT is dropped with a note, the lead kept."""

    def test_a_4400_digit_amount_is_dropped_and_the_lead_kept(self):
        status, answer = self.send(sale("L-1", value="1" * 4400))
        self.assertEqual(status, 200)
        self.assertIn(money.VALUE_NOTE, answer["notes"])
        self.assertEqual(self.rows("SELECT external_ref, value_minor FROM conversions"),
                         [("L-1", None)])
        self.assertEqual(self.blob()["withheld"], {})

    def test_a_json_batch_keeps_every_record(self):
        status, answer = self.post("json", [sale("J-1", value="1" * 4400), sale("J-2")])
        self.assertEqual((status, answer["recorded"]), (200, 2))
        self.assertEqual(self.rows("SELECT external_ref, value_minor FROM conversions ORDER BY "
                                   "id"), [("J-1", None), ("J-2", 4999)])

    def test_a_4400_digit_json_number_is_kept_without_a_value(self):
        body = json.dumps(sale("L-2", value=0)).replace('"value": 0', '"value": ' + "9" * 4400)
        status, answer = self.post("lead", None, raw=body.encode())
        self.assertEqual(status, 200, answer)
        self.assertEqual(self.rows("SELECT external_ref, value_minor FROM conversions"),
                         [("L-2", None)])
        self.assertEqual(self.blob()["withheld"], {})

    def test_both_readers_refuse_long_text_alike(self):
        for raw in ("1" * 4400, "1" * 31, "0" * 29 + "1.5", "1" * 30, 10 ** 40):
            with self.subTest(raw=str(raw)[:12]):
                self.assertEqual(money.minor(raw, "USD"), audit_revenue._minor(raw, "USD"))
                self.assertIsNone(money.minor(raw, "USD"))


class Removals(Removing):
    """3, 4. A removal is replayed at the time it happened."""

    def test_a_whole_refund_then_its_sale_removed(self):
        self.send(sale("S-1", value="100"), T)
        self.send(refund("S-1"), T + 60)
        self.now = T + 120
        self.remove("S-1", "paid")
        got = self.blob()
        self.assertEqual(got["withheld"], {})
        self.assertEqual(got["refunds_without_sale"], {"count": 1, "currencies": {"USD": 10000}})

    def test_a_cut_refund_then_its_sale_removed(self):
        self.send(sale("S-1", value="100"), T)
        self.send(refund("S-1", value="150", currency="USD"), T + 60)
        self.now = T + 120
        self.remove("S-1", "paid")
        got = self.blob()
        self.assertEqual(got["withheld"], {})
        self.assertEqual(got["refunds_without_sale"], {"count": 1, "currencies": {"USD": 10000}})

    def test_a_sale_removed_then_sent_again(self):
        self.send(sale("S-1", value="100"), T)
        self.send(refund("S-1", value="30", currency="USD"), T + 60)
        self.now = T + 120
        self.remove("S-1", "paid")
        self.send(refund("S-1", value="150", currency="USD"), T + 180)
        self.send(sale("S-1", value="100"), T + 240)
        got = self.blob()
        self.assertEqual(got["withheld"], {})
        self.assertEqual(totals(self.day(got, "2026-10-11"))["refunded_minor"], 10000)

    def test_a_refund_moved_onto_its_sale_then_removed(self):
        self.event("invoice.paid", {"id": "in_2", "object": "invoice", "billing_reason":
                                    "subscription_cycle", "amount_paid": 4900, "currency": "usd",
                                    "customer": "cus_1"}, T)
        self.event("charge.refunded", {"id": "ch_2", "object": "charge", "payment_intent": "pi_2",
                                       "amount_refunded": 1000, "currency": "usd"}, T + 60)
        self.event("invoice_payment.paid", {"id": "inpay_1", "object": "invoice_payment",
                                            "invoice": "in_2", "payment": {
                                                "type": "payment_intent",
                                                "payment_intent": "pi_2"}}, T + 120)
        self.now = T + 180
        self.remove("in_2", "refunded")
        got = self.blob()
        self.assertEqual(got["withheld"], {})
        self.assertEqual(totals(self.day(got, "2026-10-11"))["refunded_minor"], 0)


class NoValue(Removing):
    """5, a. A refund kept without a value is listed; a whole refund after an
    unreadable one still counts."""

    def test_a_refund_in_another_currency_is_listed(self):
        self.send(sale("S-2"))
        self.send(refund("S-2", value="10", currency="EUR"))
        got = self.blob()
        self.assertEqual(got["withheld"], {})
        self.assertEqual(got["refunds_without_sale"], {"count": 1, "currencies": {}})

    def test_a_sale_changing_currency_lists_its_refund(self):
        self.send(sale("C-1", stage="completed", value="100"), T)
        self.send(refund("C-1", value="50", currency="USD"), T + 60)
        self.send(sale("C-1", value="80", currency="EUR"), T + 120)
        got = self.blob()
        self.assertEqual(got["withheld"], {})
        self.assertEqual(got["refunds_without_sale"]["count"], 1)

    def test_a_whole_refund_after_an_unreadable_one(self):
        self.send(refund("W-1", value="abc", currency="USD"), T)
        status, answer = self.send(refund("W-1"), T + 30)
        self.assertEqual(answer["recorded"], 1, "not a duplicate")
        self.send(sale("W-1", value="100"), T + 60)
        self.assertEqual(self.rows("SELECT value_minor FROM conversions WHERE stage = "
                                   "'refunded'"), [(10000,)])
        got = self.blob()
        self.assertEqual(got["withheld"], {})
        self.assertEqual(totals(self.day(got, "2026-10-11"))["net_minor"], 0)
        self.assertEqual(got["refunds_without_sale"]["count"], 0)


class Zero(Money):
    """b. A refund of 0 is no refund."""

    def test_a_zero_refund_is_not_counted(self):
        self.send(sale("Z-1", value="100"), T)
        self.send(refund("Z-1", value="0", currency="USD"), T + 60)
        got = self.blob()
        self.assertEqual(got["withheld"], {})
        self.assertEqual(totals(self.day(got, "2026-10-11"))["refunds"], 0)
        self.send(refund("Z-1", value="10", currency="USD"), T + 80)
        got = self.blob()
        self.assertEqual(got["withheld"], {})
        self.assertEqual(totals(self.day(got, "2026-10-11"))["refunds"], 1)
        self.assertEqual(totals(self.day(got, "2026-10-11"))["refunded_minor"], 1000)


class Customer(Money):
    """c. customer_ref is never a phone number or an address."""

    def test_phone_numbers_and_addresses_are_dropped(self):
        for i, ref in enumerate(("198.51.100.7", "15551234567", "+1 (555) 123-4567",
                                 "555.123.4567")):
            status, answer = self.send(sale(f"P-{i}", customer_ref=ref))
            self.assertIn(money.CUSTOMER_NOTE, answer["notes"], ref)
            self.assertNotIn(ref, self.spooled())
        self.assertEqual(self.rows("SELECT DISTINCT customer_ref FROM conversions"), [(None,)])
        self.assertEqual(self.blob()["withheld"], {})

    def test_opaque_ids_are_kept(self):
        for i, ref in enumerate(("cus_9", "550e8400-e29b-41d4-a716-446655440000", "c_10293847",
                                 "123456")):
            self.send(sale(f"K-{i}", customer_ref=ref))
        self.assertEqual(len(self.rows("SELECT customer_ref FROM conversions WHERE customer_ref "
                                       "IS NOT NULL")), 4)
        self.assertEqual(self.blob()["withheld"], {})


if __name__ == "__main__":
    unittest.main()
