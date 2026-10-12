"""The second count of conversions (audit_conversions.py) and the commands
(cli_conversions.py). Hosts are example.com; the secret is made up."""
from __future__ import annotations

import json
import stat
import sys
import threading
import unittest
from datetime import date, datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))

from conversions_support import SECRET, VID  # noqa: E402
from support import Sandbox  # noqa: E402
from test_conversions_hooks import Base, lead  # noqa: E402

from skald import audit_conversions, audit_more, cli_more  # noqa: E402
from skald.config import load_config  # noqa: E402
from skald.conversions import spool, store  # noqa: E402
from skald.conversions.hooks import handle  # noqa: E402

UTC = timezone.utc
DAY = date(2026, 10, 11)


class SecondCount(Base):
    def deliver(self):
        uri = "https://api.calendly.com/scheduled_events/E/invitees/I"
        self.post("lead", lead())
        self.post("lead", lead())                                        # a repeat
        self.post("lead", lead(external_ref="L-2", stage="started", at="2026-10-10T23:30:00Z"))
        self.post("lead", lead(action="Not A Token"))                    # refused, spooled
        self.post("json", {"records": [{"external_ref": "Z1", "action": "trial"},
                                       {"external_ref": "Z2", "action": "trial"}]})
        self.post("calendly", {"event": "invitee.created", "created_at": "2026-10-11T08:00:00Z",
                               "payload": {"uri": uri}})
        self.post("calendly", {"event": "invitee.canceled", "created_at": "2026-10-11T09:00:00Z",
                               "payload": {"uri": uri, "rescheduled": True}})
        self.post("stripe", {"object": "event", "type": "checkout.session.completed",
                             "created": self.now, "data": {"object": {
                                 "id": "cs_1", "payment_status": "unpaid"}}})
        self.post("hubspot", [{"subscriptionType": "contact.creation", "objectId": 4},
                              {"subscriptionType": "deal.propertyChange", "objectId": 4,
                               "propertyName": "dealstage", "propertyValue": "closedwon"}])
        self.post("typeform", {"event_type": "form_response", "form_response": {
            "token": "tk", "submitted_at": "2026-10-11T10:00:00Z"}})
        self.post("calcom", {"triggerEvent": "BOOKING_CREATED", "createdAt": "2026-10-11T10:00Z",
                             "payload": {"uid": "B1"}})

    def find(self, tz=UTC):
        return audit_conversions.findings(self.config, self.folder, "example.com", tz,
                                          date(2026, 10, 1), DAY)

    def test_not_set_up(self):
        self.config.pop("beacon", None)             # Base turns visitor IDs on for the hooks
        self.assertIsNone(self.find())

    def test_the_two_roads_agree(self):
        self.deliver()
        self.assertEqual(self.find(), {})
        self.assertEqual(self.find(ZoneInfo("America/New_York")), {})
        counted = audit_conversions.recount(self.folder / "hooks", "example.com", UTC,
                                            date(2026, 10, 1), DAY)
        self.assertEqual(counted["2026-10-10"], {("demo", "started"): 1})
        self.assertEqual(counted["2026-10-11"][("demo", "rescheduled")], 1)
        self.assertEqual(counted["2026-10-11"][("paid", "started")], 1)
        self.assertEqual(counted["2026-10-11"][("trial", "completed")], 2)

    def test_a_lost_row_is_withheld(self):
        self.deliver()
        db = store.connect(self.folder / "conversions.sqlite")
        db.execute("DELETE FROM conversions WHERE external_ref = 'tk'")
        db.close()
        found = self.find()
        self.assertEqual(list(found), ["2026-10-11"])
        self.assertIn("contact completed: stored 1, recounted from the spool 2", found["2026-10-11"][0])

    def test_an_extra_spool_line_is_withheld(self):
        self.deliver()
        day = datetime.fromtimestamp(self.now, tz=UTC).date()
        spool.append(self.folder / "hooks", day, spool.line_for(
            "2026-10-11T12:00:00Z", "example.com", "lead",
            {"external_ref": "ghost", "action": "demo"}, False))
        self.assertIn("2026-10-11", self.find())

    def test_daily_step(self):
        self.deliver()
        ctx = SimpleNamespace(config=self.config, db_path=self.folder / "history.sqlite",
                              site="example.com", tz=UTC)
        self.assertEqual(audit_conversions.daily(ctx, DAY), [])
        self.assertTrue(audit_conversions.set_up(ctx))
        self.assertFalse(audit_conversions.set_up(SimpleNamespace(
            config={}, db_path=self.folder / "elsewhere" / "history.sqlite")))
        self.assertEqual(audit_more.DAILY.get("conversions"), "audit_conversions")


class Commands(unittest.TestCase):
    def setUp(self):
        self.box = Sandbox(mail=False)
        self.assertIn("cli_conversions", cli_more.MODULES)

    def tearDown(self):
        self.box.close()

    def serve(self):
        config = load_config(self.box.config)
        folder = self.box.root

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                handle(self, config, folder)

            def log_message(self, *a):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return f"http://127.0.0.1:{server.server_address[1]}"

    def test_secret_list_and_test(self):
        code, out, err = self.box.run("hooks", "secret", "example.com", "lead")
        self.assertEqual(code, 0, err)
        secret = out.splitlines()[1].strip()
        self.assertTrue(secret.startswith("skh_"))
        path = self.box.root / "secrets.json"
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.assertEqual(json.loads(path.read_text()), {"hooks/example.com/lead": secret})
        code, out, _ = self.box.run("hooks", "list")
        self.assertIn("example.com/lead: /traffic-hooks/example.com/lead  secret: file", out)
        self.assertNotIn(secret, out, "the secret is shown once only")
        url = self.serve()
        code, out, err = self.box.run("hooks", "test", "example.com", "lead", "--url", url)
        self.assertEqual(code, 0, out + err)
        self.assertIn('"test":true', out)
        code, out, _ = self.box.run("hooks", "list")
        self.assertIn("200  test", out)
        self.assertEqual(self.box.run("hooks", "secret", "nowhere.example.com", "lead")[0], 2)
        self.assertEqual(self.box.run("hooks", "test", "example.com", "stripe", "--url", url)[0], 2)

    def test_forget_and_prune(self):
        # Visitor IDs on, or the hook keeps no vid to forget (2.2.3).
        self.box.config.write_text(self.box.config.read_text() + "beacon:\n  visitor_ids: true\n")
        self.box.run("hooks", "secret", "example.com", "lead", "--value", SECRET)
        url = self.serve()
        import urllib.request
        from skald.conversions.adapters import adapter
        import time
        for ref in ("L-1", "L-2"):
            body = json.dumps(lead(external_ref=ref, vid=VID if ref == "L-1" else None)).encode()
            req = urllib.request.Request(url + "/traffic-hooks/example.com/lead", body,
                                         adapter("lead").sign(body, SECRET, time.time()))
            self.assertEqual(urllib.request.urlopen(req, timeout=5).status, 200)
        code, out, _ = self.box.run("conversions", "forget", "--vid", VID, "--dry-run")
        self.assertIn("would delete 1 conversion(s)", out)
        self.assertIn("1 spool line(s)", out)
        code, out, _ = self.box.run("conversions", "forget", "--vid", VID)
        self.assertEqual(code, 0)
        self.assertIn("deleted 1 conversion(s)", out)
        log = (self.box.root / "privacy.log").read_text()
        self.assertIn("conversions forget vid sha256:", log)
        self.assertNotIn(VID, log)
        config = load_config(self.box.config)
        today = datetime.now(UTC).date()
        self.assertEqual(audit_conversions.findings(config, self.box.root, "example.com", UTC,
                                                    today, today), {})
        code, out, _ = self.box.run("--today", "2028-06-01", "conversions", "prune")
        self.assertEqual(code, 0)
        self.assertIn("1 conversion(s)", out)
        self.assertIn("1 spool file(s)", out)


if __name__ == "__main__":
    unittest.main()
