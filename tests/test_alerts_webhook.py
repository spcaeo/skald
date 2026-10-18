"""Alerts sent to a webhook (alerts.notify -> conversions/outgoing.py): the
`alert.opened` event, signed like Skald's own hooks, Slack's {"text"} shape for
a hooks.slack.com address, one deadline a delivery, a backoff and no storm of
retries, and never a secret in a log. Addresses are made up."""
from __future__ import annotations

import hashlib
import hmac
import json
import socket
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_conversions_outgoing import Catcher  # noqa: E402

from skald import alerts  # noqa: E402
from skald.conversions import outgoing, store  # noqa: E402

UTC = timezone.utc
NOW = datetime(2026, 10, 12, 15, 0, tzinfo=UTC)
SITE = "example.com"
SLACK = "https://hooks.slack.com/services/T0000/B0000/XXXXXXXX"
ALERT = {"id": "ai_cited_visits-20261012150000-0", "cause": "ai_cited_visits", "subject": "rose",
         "severity": "medium", "title": "Visits from AI answers rose to 25 on Sun 11 Oct",
         "detail": "Usual for a Sunday: 10.", "figure": 25, "threshold": 20.0, "unit": "visits",
         "data": {"kind": "cited_rose", "visits": 25, "median": 10}, "opened_at": NOW.isoformat()}


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.config = {"integrations": {"allow_private_urls": True}}
        self.db = store.connect(self.folder / "conversions.sqlite")
        self.addCleanup(self.db.close)
        self.errors = []

    def ctx(self):
        return SimpleNamespace(config=self.config, site=SITE, now=NOW,
                               db_path=self.folder / "history.sqlite", err=self.errors.append)

    def hook(self, url, events=("alert.opened",)):
        return outgoing.add(self.db, self.config, self.folder, SITE, url, list(events),
                            "owner@example.com", NOW)


class Body(unittest.TestCase):
    def test_the_body_is_site_alert_text_figures_at(self):
        body = alerts.hook_body(ALERT, SITE)
        self.assertEqual(body["event"], "alert.opened")
        self.assertEqual(body["alert"], {k: ALERT[k] for k in
                                         ("id", "cause", "subject", "severity", "title")})
        self.assertEqual(body["figures"], {"figure": 25, "threshold": 20.0, "unit": "visits",
                                           "data": ALERT["data"]})
        self.assertEqual(body["at"], NOW.isoformat())
        self.assertEqual(body["text"], f"[{SITE}] {ALERT['title']}\n{ALERT['detail']}")
        self.assertIn("alert.opened", outgoing.EVENTS)

    def test_slack_gets_text_and_everyone_else_the_body(self):
        raw = json.dumps(alerts.hook_body(ALERT, SITE))
        self.assertEqual(outgoing.wire("https://hooks.example.com/x", raw), raw.encode())
        self.assertEqual(json.loads(outgoing.wire(SLACK, raw)),
                         {"text": alerts.hook_body(ALERT, SITE)["text"]})
        self.assertFalse(outgoing.is_slack("https://hooks.slack.com.example.com/x"))
        self.assertTrue(outgoing.is_slack("https://HOOKS.slack.com./services/x"))
        conv = json.dumps({"event": "conversion.completed", "site": SITE, "action": "demo",
                           "stage": "completed", "source_type": "Search", "landing": "/p/",
                           "test": True})
        self.assertEqual(json.loads(outgoing.wire(SLACK, conv))["text"],
                         "[example.com] conversion.completed demo (completed) from Search "
                         "landed on /p/ (test)")


class Delivery(Base):
    def test_signed_with_the_webhooks_own_secret(self):
        catcher = Catcher()
        self.addCleanup(catcher.stop)
        hook, secret = self.hook(catcher.url)
        self.hook(catcher.url, events=("lead.won",))         # did not ask for alerts
        self.assertEqual(alerts.notify(self.ctx(), [ALERT]), 1)
        self.assertEqual(alerts.notify(self.ctx(), [ALERT]), 0)    # once per alert
        got = outgoing.deliver_due(self.db, self.config, self.folder, SITE, NOW)
        self.assertEqual(got["sent"], 1)
        headers, raw, _ = catcher.got[0]
        t = headers["X-Skald-Signature"].split(",")[0][2:]
        want = hmac.new(secret.encode(), f"{t}.".encode() + raw, hashlib.sha256).hexdigest()
        self.assertEqual(headers["X-Skald-Signature"], f"t={t},v1={want}")
        body = json.loads(raw)
        self.assertEqual((body["event"], body["site"], body["alert"]["cause"]),
                         ("alert.opened", SITE, "ai_cited_visits"))
        self.assertNotIn(secret, raw.decode())

    def test_a_slack_address_gets_slacks_shape(self):
        hook, secret = self.hook(SLACK)
        alerts.notify(self.ctx(), [ALERT])
        seen = []

        def fake(method, url, body, headers, config, seconds, max_bytes):
            seen.append((url, body, headers, seconds))
            return 200, b""
        with mock.patch.object(outgoing, "_request", side_effect=fake):
            got = outgoing.deliver_due(self.db, self.config, self.folder, SITE, NOW)
        self.assertEqual(got["sent"], 1)
        url, body, headers, seconds = seen[0]
        self.assertEqual(url, SLACK)
        self.assertEqual(set(json.loads(body)), {"text"})
        self.assertTrue(json.loads(body)["text"].startswith("[example.com] Visits from AI"))
        self.assertIn("X-Skald-Signature", headers)
        self.assertLessEqual(seconds, outgoing.DEADLINE)

    def test_a_silent_receiver_times_out_backs_off_and_leaks_no_secret(self):
        quiet = socket.socket()
        quiet.bind(("127.0.0.1", 0))
        quiet.listen(5)                 # accepts, never answers
        self.addCleanup(quiet.close)
        hook, secret = self.hook(f"http://127.0.0.1:{quiet.getsockname()[1]}/hook")
        alerts.notify(self.ctx(), [ALERT])
        with mock.patch.object(outgoing, "DEADLINE", 0.5):
            got = outgoing.deliver_due(self.db, self.config, self.folder, SITE, NOW)
            self.assertEqual(got["retry"], 1)
            # Due again only after the first backoff: no storm of retries.
            again = outgoing.deliver_due(self.db, self.config, self.folder, SITE,
                                         NOW + timedelta(seconds=30))
            self.assertEqual(again["retry"] + again["sent"] + again["failed"], 0)
        row = outgoing.listing(self.db, SITE)[0]["deliveries"][0]
        self.assertEqual((row["state"], row["attempts"]), ("pending", 1))
        self.assertIn("timed out", row["error"])
        self.assertEqual(row["next_at"], store.stamp(NOW + timedelta(seconds=outgoing.BACKOFF[0])))
        logged = json.dumps(outgoing.listing(self.db, SITE)) + " ".join(self.errors)
        self.assertNotIn(secret, logged)

    def test_a_broken_queue_is_one_line_without_the_secret(self):
        hook, secret = self.hook("http://127.0.0.1:9/hook")
        with mock.patch.object(outgoing, "notify", side_effect=RuntimeError(secret)):
            self.assertEqual(alerts.notify(self.ctx(), [ALERT]), 0)
        self.assertEqual(self.errors, ["alerts: alert.opened webhook: RuntimeError"])

    def test_https_only_without_the_test_switch(self):
        with self.assertRaises(outgoing.Refused):
            outgoing.add(self.db, {}, self.folder, SITE, "http://hooks.example.com/x",
                         ["alert.opened"], "owner@example.com", NOW)
        got, _ = outgoing.add(self.db, {}, self.folder, SITE, SLACK, ["alert.opened"],
                              "owner@example.com", NOW)
        self.assertEqual(got["events"], ["alert.opened"])


if __name__ == "__main__":
    unittest.main()
