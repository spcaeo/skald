"""Sale alerts (alerts_sales.py, 2.33): a lead that gains a counted sale value
alerts once, through the site's alert mail and the `alert.opened` webhook
(Slack's shape on hooks.slack.com); never again after a restart, a second
run, a rebuilt conversions file or a replayed spool; off by default; a
per-currency minimum; a test lead never alerts; amounts formatted as the
dashboard formats them; a counted refund part is its own alert; a failed
mail is noted and never retried, a failed webhook retried by the outbox.
Hosts are example.com, nothing about a person is in an alert. Nothing here
sends a real mail or calls Slack."""
from __future__ import annotations

import json
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald import alerts, alerts_sales, settings_store  # noqa: E402
from skald.conversions import money, outgoing, store  # noqa: E402

from support import SECRETS, Sandbox  # noqa: E402

UTC = timezone.utc
T0 = datetime(2026, 10, 20, 9, 0, tzinfo=UTC)
SITE = "example.com"
SLACK = "https://hooks.slack.com/services/T0000/B0000/XXXXXXXX"


def signals(now):
    return {"minutes": {}, "beats": [], "newest": now, "since": now - timedelta(hours=6)}


def row(ref, stage="paid", value=4999, currency="USD", at=T0, received=None, tool="lead",
        **kw) -> dict:
    out = {"site": SITE, "action": "signup", "stage": stage, "at": store.stamp(at),
           "external_ref": ref, "tool": tool, "source_type": "Search",
           "first_source": "AI assistant", "campaign": "spring", "landing": "/pricing/?ref=x",
           "country": "DE", "device": "desktop", "value_minor": value, "currency": currency,
           "customer_ref": "cust_9", "received_at": store.stamp(received or at)}
    out.update(kw)
    return out


class Unit(unittest.TestCase):
    """alerts_sales.due over one conversions file and one state dict."""

    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "conversions.sqlite"
        self.db = store.connect(self.path)
        self.addCleanup(self.db.close)
        self.state: dict = {}
        self.config = {"alerts": {"enabled": True, "sale": True}}

    def due(self, now, config=None):
        return alerts_sales.due(self.state, config or self.config, self.db, SITE, UTC, now)

    def add(self, *a, **kw):
        store.record_conversion(self.db, row(*a, **kw))

    def test_off_by_default(self):
        self.assertFalse(alerts_sales.settings({})["sale"])
        self.assertFalse(alerts_sales.settings({})["sale_refund"])
        self.assertIs(settings_store.explain({})["alerts.sale"]["value"], False)
        self.assertIs(settings_store.explain({})["alerts.sale_refund"]["value"], False)
        self.add("S-1", received=T0 + timedelta(minutes=1))
        self.assertEqual(self.due(T0 + timedelta(minutes=2), {"alerts": {"enabled": True}}), [])
        self.assertEqual(self.state.get("sales", {}).get("since", {}), {})

    def test_sent_once_and_never_again(self):
        self.assertEqual(self.due(T0), [])                  # switched on now: since = T0
        self.add("S-1", at=T0 + timedelta(minutes=1))
        got = self.due(T0 + timedelta(minutes=2))
        self.assertEqual([a["cause"] for a in got], ["sale"])
        a = got[0]
        self.assertEqual(a["title"], "Sale: $49.99, paid")
        self.assertEqual(a["data"]["amount"], "$49.99")
        self.assertEqual((a["data"]["value_minor"], a["data"]["currency"]), (4999, "USD"))
        self.assertEqual(a["closed_at"], a["opened_at"])    # an event: opened and closed
        for words in ("example.com", "$49.99", "paid", "Search", "AI assistant", "spring",
                      "/pricing/", "2026-10-20 09:01 UTC"):
            self.assertIn(words, a["detail"])
        body = json.dumps(a)
        for personal in ("cust_9", "S-1", "?ref=x", "@"):
            self.assertNotIn(personal, body)
        self.assertEqual(self.due(T0 + timedelta(minutes=4)), [])
        # A paid row after an alerted completed one is the same sale: no second alert.
        self.add("S-2", stage="completed", at=T0 + timedelta(minutes=5))
        self.assertEqual(len(self.due(T0 + timedelta(minutes=6))), 1)
        self.add("S-2", stage="paid", value=5999, at=T0 + timedelta(minutes=7))
        self.assertEqual(self.due(T0 + timedelta(minutes=8)), [])

    def test_a_lead_that_gains_a_value_later_alerts_then(self):
        self.due(T0)
        self.add("L-1", stage="completed", value=None, currency=None,
                 at=T0 + timedelta(minutes=1))
        self.assertEqual(self.due(T0 + timedelta(minutes=2)), [])   # a lead, no sale yet
        self.add("L-1", stage="paid", value=2000, at=T0 + timedelta(minutes=3))
        got = self.due(T0 + timedelta(minutes=4))
        self.assertEqual([a["data"]["amount"] for a in got], ["$20.00"])

    def test_a_rebuilt_file_or_replayed_rows_do_not_alert_again(self):
        self.due(T0)
        self.add("S-1", at=T0 + timedelta(minutes=1))
        self.assertEqual(len(self.due(T0 + timedelta(minutes=2))), 1)
        # The same delivery again (a replayed spool): the store keeps one row.
        self.add("S-1", at=T0 + timedelta(minutes=1))
        self.assertEqual(self.due(T0 + timedelta(minutes=3)), [])
        # A rebuilt file: new row ids and new received times, the same sale.
        self.db.close()
        self.path.unlink()
        self.db = store.connect(self.path)
        self.add("S-1", at=T0 + timedelta(minutes=1), received=T0 + timedelta(minutes=9))
        self.assertEqual(self.due(T0 + timedelta(minutes=10)), [])

    def test_old_sales_and_sales_before_switching_on_never_alert(self):
        self.add("OLD", at=T0 - timedelta(days=5), received=T0 + timedelta(minutes=1))
        self.add("EARLY", at=T0 - timedelta(minutes=5), received=T0 - timedelta(minutes=5))
        self.due(T0)
        self.add("BACKFILL", at=T0 - timedelta(hours=alerts_sales.MAX_AGE_HOURS + 1),
                 received=T0 + timedelta(minutes=1))
        self.assertEqual(self.due(T0 + timedelta(minutes=2)), [])

    def test_switched_off_and_on_again_starts_from_then(self):
        self.due(T0)
        off = {"alerts": {"enabled": True, "sale": False}}
        self.due(T0 + timedelta(minutes=1), off)
        self.add("WHILE-OFF", at=T0 + timedelta(minutes=2))
        self.due(T0 + timedelta(minutes=3), off)
        self.assertEqual(self.due(T0 + timedelta(minutes=4)), [])

    def test_minimum_per_currency(self):
        cfg = {"alerts": {"enabled": True, "sale": True, "sale_minimum": "USD 100, EUR 90.50"}}
        self.due(T0, cfg)
        at = T0 + timedelta(minutes=1)
        self.add("SMALL", value=9999, at=at)                      # USD 99.99: under
        self.add("BIG", value=10000, at=at)                       # USD 100.00: alerts
        self.add("EURO", value=9049, currency="EUR", at=at)       # under EUR 90.50
        self.add("YEN", value=50, currency="JPY", at=at)          # not listed: any amount
        got = self.due(T0 + timedelta(minutes=2), cfg)
        self.assertEqual(sorted(a["data"]["amount"] for a in got), ["$100.00", "¥50"])
        # Below the minimum is decided too: lowering it later does not mail old sales.
        low = {"alerts": {"enabled": True, "sale": True}}
        self.assertEqual(self.due(T0 + timedelta(minutes=3), low), [])

    def test_a_test_lead_never_alerts(self):
        self.due(T0)
        self.add("T-1", at=T0 + timedelta(minutes=1), test=True)
        self.add("T-2", at=T0 + timedelta(minutes=1))
        store.mark_test(self.db, SITE, [r[0] for r in self.db.execute(
            "SELECT id FROM conversions WHERE external_ref = 'T-2'")])
        self.assertEqual(self.due(T0 + timedelta(minutes=2)), [])

    def test_nothing_before_revenue_since(self):
        self.due(T0)
        self.add("S-1", at=T0 + timedelta(minutes=1))
        with mock.patch("skald.conversions_revenue.first_day",
                        return_value="2026-10-21"):
            self.assertEqual(self.due(T0 + timedelta(minutes=2)), [])

    def test_refunds_are_their_own_kind_and_off_by_default(self):
        self.due(T0)
        self.add("S-1", at=T0 + timedelta(minutes=1))
        self.assertEqual(len(self.due(T0 + timedelta(minutes=2))), 1)
        self.add("S-1", stage="refunded", value=1000, at=T0 + timedelta(minutes=3))
        self.assertEqual(self.due(T0 + timedelta(minutes=4)), [])     # sale_refund is off
        both = {"alerts": {"enabled": True, "sale": True, "sale_refund": True}}
        self.due(T0 + timedelta(minutes=5), both)                     # on from now
        self.add("S-1", stage="refunded", value=2500, at=T0 + timedelta(minutes=6))
        got = self.due(T0 + timedelta(minutes=7), both)
        self.assertEqual([a["cause"] for a in got], ["sale_refunded"])
        self.assertEqual(got[0]["title"], "Refund: $15.00 of a $49.99 sale")
        self.assertIn("Refunded so far on that sale: $25.00 of $49.99", got[0]["detail"])
        self.assertEqual(self.due(T0 + timedelta(minutes=8), both), [])
        # A refund with no counted sale is counted nowhere and never alerts.
        self.add("NOSALE", stage="refunded", value=500, at=T0 + timedelta(minutes=9))
        self.assertEqual(self.due(T0 + timedelta(minutes=10), both), [])

    def test_at_most_per_run_the_rest_next_run(self):
        self.due(T0)
        for i in range(alerts_sales.PER_RUN + 3):
            self.add(f"S-{i}", at=T0 + timedelta(minutes=1))
        first = self.due(T0 + timedelta(minutes=2))
        second = self.due(T0 + timedelta(minutes=4))
        self.assertEqual((len(first), len(second)), (alerts_sales.PER_RUN, 3))
        self.assertFalse({a["id"] for a in first} & {a["id"] for a in second})
        self.assertEqual(self.due(T0 + timedelta(minutes=6)), [])


class Formatting(unittest.TestCase):
    def test_amounts_as_the_dashboard_shows_them(self):
        nb = " "
        cases = [(4999, "USD", "$49.99"), (123456789, "USD", "$1,234,567.89"),
                 (1200, "JPY", "¥1,200"), (1500, "KWD", f"KWD{nb}1.500"),
                 (4900, "EUR", "€49.00"), (4900, "GBP", "£49.00"),
                 (4900, "CHF", f"CHF{nb}49.00"), (4900, "CAD", "CA$49.00"),
                 (7, "INR", "₹0.07"), (0, "USD", "$0.00"), (100, "XOF", f"F CFA{nb}100")]
        for minor, cur, want in cases:
            self.assertEqual(money.display(minor, cur), want, cur)
        self.assertIsNone(money.display(None, "USD"))

    def test_minimum_words_are_checked_and_canonical(self):
        self.assertEqual(alerts_sales.clean_minimum("usd 100, 90.5 EUR"), "EUR 90.50, USD 100.00")
        self.assertEqual(alerts_sales.clean_minimum({"JPY": 1200}), "JPY 1200")
        self.assertIsNone(alerts_sales.clean_minimum("  "))
        for bad in ("USD", "XYZ 10", "USD 1.234", "USD 1, USD 2", "JPY 1.5"):
            with self.assertRaises(ValueError, msg=bad):
                alerts_sales.clean_minimum(bad)
        self.assertEqual(settings_store.validate("alerts.sale_minimum", "eur 5"), "EUR 5.00")
        with self.assertRaises(settings_store.Invalid):
            settings_store.validate("alerts.sale_minimum", "five dollars")
        self.assertEqual(alerts_sales.minimums("EUR 90.50, junk, USD 100"),
                         {"EUR": 9050, "USD": 10000})


class Run(unittest.TestCase):
    """Through alerts.run: the site's alert mail, the webhook, the state file."""

    def setUp(self):
        self.box = Sandbox()
        self.addCleanup(self.box.close)
        self.box.config.write_text(self.box.config.read_text()
                                   + "alerts:\n  enabled: true\n  sale: true\n"
                                   + "integrations:\n  allow_private_urls: true\n")
        self.sent = []
        self.fail = None

    def ctx(self, now):
        from skald import cli
        ctx = cli.Context(cli.parser().parse_args(["--config", str(self.box.config), "live"]))
        ctx.now = now
        ctx.out = ctx.err = lambda *a: None
        return ctx

    def send(self, config, subject, text, now):
        self.sent.append((subject, text))
        return self.fail

    def conv(self):
        ctx = self.ctx(T0)
        return store.connect(store.path_for(ctx.config, Path(ctx.db_path).parent))

    def run_at(self, now):
        ctx = self.ctx(now)
        self.assertEqual(alerts.run(ctx, None, signals(now), self.send), 0)
        return ctx

    def test_mailed_once_across_restarts_with_the_webhook_queued_once(self):
        db = self.conv()
        try:
            outgoing.add(db, {"integrations": {"allow_private_urls": True}}, self.box.root, SITE,
                         SLACK, ["alert.opened"], "owner@example.com", T0)
            self.run_at(T0)
            store.record_conversion(db, row("S-1", at=T0 + timedelta(minutes=1)))
        finally:
            db.close()
        ctx = self.run_at(T0 + timedelta(minutes=2))
        self.run_at(T0 + timedelta(minutes=4))              # a new process each time
        self.assertEqual([s for s, _ in self.sent], ["Sale on example.com: $49.99"])
        text = self.sent[0][1]
        self.assertIn("Sale: $49.99, paid", text)
        self.assertIn("Dashboard: https://stats.example.com/example.com/", text)
        got = alerts.build(type("P", (), {"config": ctx.config, "live_dir": ctx.live_dir}))
        self.assertEqual([a["cause"] for a in got["closed"]], ["sale"])
        self.assertIn("sale", [r["cause"] for r in got["rules"]])
        self.assertEqual({r["setting"] for r in got["rules"] if r["cause"].startswith("sale")},
                         {"alerts.sale", "alerts.sale_refund"})
        db = self.conv()
        try:
            rows = db.execute("SELECT event, body FROM outbox").fetchall()
            self.assertEqual(len(rows), 1)
            body = json.loads(rows[0][1])
            self.assertEqual((body["event"], body["alert"]["cause"]), ("alert.opened", "sale"))
            self.assertTrue(body["text"].startswith("[example.com] Sale: $49.99, paid"))
            self.assertNotIn("cust_9", rows[0][1])
            # A Slack failure is the outbox's: kept and tried again later, not re-queued.
            with mock.patch.object(outgoing, "_request", return_value=(500, b"")):
                done = outgoing.deliver_due(db, ctx.config, self.box.root, SITE,
                                            T0 + timedelta(minutes=5))
            self.assertEqual(done["retry"], 1)
        finally:
            db.close()
        self.run_at(T0 + timedelta(minutes=6))
        db = self.conv()
        try:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM outbox").fetchone()[0], 1)
        finally:
            db.close()

    def test_a_failed_mail_is_noted_and_never_retried(self):
        self.run_at(T0)
        db = self.conv()
        try:
            store.record_conversion(db, row("S-1", at=T0 + timedelta(minutes=1)))
        finally:
            db.close()
        self.fail = "SMTPException: relay said no"
        ctx = self.run_at(T0 + timedelta(minutes=2))
        self.fail = None
        self.run_at(T0 + timedelta(minutes=4))
        self.assertEqual(len(self.sent), 1)
        alert = alerts.load_state(ctx.live_dir)["alerts"][-1]
        self.assertEqual((alert["cause"], alert["mailed"], alert["mail_error"]),
                         ("sale", 0, "SMTPException: relay said no"))

    def test_a_real_mail_failure_never_fails_the_run(self):
        self.run_at(T0)
        db = self.conv()
        try:
            store.record_conversion(db, row("S-1", at=T0 + timedelta(minutes=1)))
        finally:
            db.close()
        ctx = self.ctx(T0 + timedelta(minutes=2))
        with mock.patch.dict(os.environ, SECRETS), \
                mock.patch("skald.mailer.smtplib.SMTP", side_effect=OSError("refused")):
            self.assertEqual(alerts.run(ctx, None, signals(ctx.now)), 0)
        alert = alerts.load_state(ctx.live_dir)["alerts"][-1]
        self.assertIn("refused", alert["mail_error"])
        self.assertEqual(alert["mailed"], 0)

    def test_kept_as_done_before_the_mail_goes(self):
        self.run_at(T0)
        db = self.conv()
        try:
            store.record_conversion(db, row("S-1", at=T0 + timedelta(minutes=1)))
        finally:
            db.close()
        ctx = self.ctx(T0 + timedelta(minutes=2))

        def crash(config, subject, text, now):
            raise KeyboardInterrupt          # the process dies while mailing
        with self.assertRaises(KeyboardInterrupt):
            alerts.run(ctx, None, signals(ctx.now), crash)
        self.run_at(T0 + timedelta(minutes=4))
        self.assertEqual(self.sent, [])      # at most once: never mailed twice

    def test_never_from_a_replay(self):
        from skald import cli
        self.run_at(T0)
        db = self.conv()
        try:
            store.record_conversion(db, row("S-1", at=T0 + timedelta(minutes=1)))
        finally:
            db.close()
        argv = ["--config", str(self.box.config), "--today", "2026-10-20", "live"]
        ctx = cli.Context(cli.parser().parse_args(argv))
        ctx.now = T0 + timedelta(minutes=2)
        ctx.out = ctx.err = lambda *a: None
        alerts.run(ctx, None, signals(ctx.now), self.send)
        self.assertEqual(self.sent, [])
        self.run_at(T0 + timedelta(minutes=3))
        self.assertEqual(len(self.sent), 1)  # the replay decided nothing


if __name__ == "__main__":
    unittest.main()
