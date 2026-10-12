"""Outgoing webhooks (conversions/outgoing.py): what is queued, the signed
POST, retries and backoff, abandoned starts once, no redirects, no private
addresses, and nothing done without a webhook. A local receiver on
127.0.0.1 stands in for the CRM (allow_private_urls is on for that). Hosts
are example.com; the secrets are made up."""
from __future__ import annotations

import hashlib
import hmac
import json
import sys
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from conversions_support import VID  # noqa: E402

from skald.conversions import outgoing, secrets_store, store  # noqa: E402

UTC = timezone.utc
NOW = datetime(2026, 10, 11, 14, 0, tzinfo=UTC)


class Catcher:
    """A receiver that answers with the next status in `codes` (then 200)."""

    def __init__(self):
        self.got, self.codes = [], []
        catcher = self

        class H(BaseHTTPRequestHandler):
            def do_POST(self):
                n = int(self.headers.get("Content-Length") or 0)
                catcher.got.append((dict(self.headers), self.rfile.read(n), self.path))
                code = catcher.codes.pop(0) if catcher.codes else 200
                self.send_response(code)
                if code in (301, 302):
                    self.send_header("Location", "http://127.0.0.1:9/elsewhere")
                self.send_header("Content-Length", "0")
                self.end_headers()

            def log_message(self, *a):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self.server.serve_forever, args=(0.02,), daemon=True).start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}/hook?x=1"

    def stop(self):
        self.server.shutdown()
        self.server.server_close()


def conv(db, **kw):
    rec = {"site": "example.com", "tool": "calendly", "action": "demo", "stage": "completed",
           "at": "2026-10-11T13:00:00Z", "external_ref": "u1", "vid": VID,
           "source_type": "Search", "first_touch_at": "2026-10-10T13:00:00Z",
           "identity": {"email": "p@example.com", "name": "Pat"}}
    rec.update(kw)
    store.record_conversion(db, rec)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.config = {"integrations": {"allow_private_urls": True}}
        self.catcher = Catcher()
        self.addCleanup(self.catcher.stop)
        self.db = store.connect(self.folder / "conversions.sqlite")
        self.addCleanup(self.db.close)

    def add(self, events=("conversion.completed", "conversion.abandoned", "lead.won"),
            url=None):
        hook, secret = outgoing.add(self.db, self.config, self.folder, "example.com",
                                    url or self.catcher.url, list(events), "owner@example.com",
                                    NOW)
        return hook, secret

    def run_at(self, when=NOW):
        return outgoing.run(self.config, self.folder, "example.com", when)


class Nothing(unittest.TestCase):
    def test_no_file_no_webhook(self):
        with tempfile.TemporaryDirectory() as tmp:
            got = outgoing.run({}, Path(tmp), "example.com", NOW)
            self.assertEqual(got["queued"], 0)
            self.assertFalse((Path(tmp) / "conversions.sqlite").exists())
            store.connect(Path(tmp) / "conversions.sqlite").close()
            self.assertEqual(outgoing.run({}, Path(tmp), "example.com", NOW)["sent"], 0)


class Sending(Base):
    def test_old_rows_are_not_flooded_and_new_ones_are_signed(self):
        conv(self.db, external_ref="old")
        hook, secret = self.add()
        self.assertTrue(secret.startswith("skw_"))
        kept = secrets_store.load(self.folder / "secrets.json")
        self.assertEqual(kept[outgoing.secret_key("example.com", hook["id"])], secret)
        store.record_page_view(self.db, "example.com", VID, "2026-10-11T12:59:00Z", "/pricing/",
                               "Search")
        conv(self.db, external_ref="new")
        conv(self.db, external_ref="new", stage="started")      # not wanted by this hook
        got = self.run_at()
        self.assertEqual((got["queued"], got["sent"]), (1, 1), got)
        headers, raw, path = self.catcher.got[0]
        self.assertEqual(path, "/hook?x=1")
        body = json.loads(raw)
        self.assertEqual((body["event"], body["external_ref"], body["action"]),
                         ("conversion.completed", "new", "demo"))
        self.assertEqual(body["seconds_to_convert"], 86400)
        self.assertEqual(body["journey"], [{"at": "2026-10-11T12:59:00Z", "path": "/pricing/",
                                            "source_type": "Search"}])
        self.assertNotIn("p@example.com", raw.decode())
        self.assertNotIn("Pat", raw.decode())
        t = headers["X-Skald-Signature"].split(",")[0][2:]
        want = hmac.new(secret.encode(), f"{t}.".encode() + raw, hashlib.sha256).hexdigest()
        self.assertEqual(headers["X-Skald-Signature"], f"t={t},v1={want}")
        # Nothing new: nothing sent again.
        self.assertEqual(self.run_at()["sent"], 0)
        self.assertEqual(len(self.catcher.got), 1)
        log = outgoing.listing(self.db, "example.com")[0]["deliveries"]
        self.assertEqual([(r["state"], r["http_status"]) for r in log], [("sent", 200)])

    def test_won_and_abandoned(self):
        self.add()
        conv(self.db, tool="site", external_ref="7", stage="won")
        conv(self.db, tool="beacon", external_ref="b1", stage="started",
             at="2026-10-11T14:30:00Z")
        got = self.run_at()
        self.assertEqual(got["sent"], 1)          # lead.won; the start is not abandoned yet
        later = NOW + timedelta(hours=25)
        self.assertEqual(self.run_at(later)["sent"], 1)
        self.assertEqual(self.run_at(later + timedelta(hours=1))["sent"], 0, "once only")
        events = [json.loads(raw)["event"] for _, raw, _ in self.catcher.got]
        self.assertEqual(events, ["lead.won", "conversion.abandoned"])

    def test_retries_with_backoff_then_failed(self):
        self.add()
        self.catcher.codes = [500] * 10
        conv(self.db)
        when = NOW
        self.assertEqual(self.run_at(when)["retry"], 1)
        self.assertEqual(self.run_at(when + timedelta(seconds=30))["retry"], 0, "not due yet")
        for wait in outgoing.BACKOFF[:-1]:
            when += timedelta(seconds=wait)
            self.assertEqual(self.run_at(when)["retry"], 1)
        when += timedelta(seconds=outgoing.BACKOFF[-1])
        self.assertEqual(self.run_at(when)["failed"], 1)
        row = outgoing.log(self.db, 1)[0]
        self.assertEqual((row["state"], row["attempts"], row["error"]),
                         ("failed", outgoing.MAX_ATTEMPTS, "HTTP 500"))
        ids = {json.loads(raw)["id"] for _, raw, _ in self.catcher.got}
        self.assertEqual(len(ids), 1, "the same id on every retry")

    def test_a_redirect_is_not_followed(self):
        self.add()
        self.catcher.codes = [302]
        conv(self.db)
        self.run_at()
        self.assertEqual(len(self.catcher.got), 1)
        self.assertIn("redirect", outgoing.log(self.db, 1)[0]["error"])

    def test_test_delivery_and_remove(self):
        hook, _ = self.add()
        got = outgoing.test(self.db, self.config, self.folder, "example.com", hook["id"], NOW)
        self.assertEqual(got["state"], "sent")
        self.assertTrue(json.loads(self.catcher.got[0][1])["test"])
        self.assertIsNone(outgoing.test(self.db, self.config, self.folder, "example.com", 99))
        self.assertTrue(outgoing.remove(self.db, self.config, self.folder, "example.com",
                                        hook["id"]))
        self.assertEqual(outgoing.listing(self.db, "example.com"), [])
        self.assertFalse(secrets_store.load(self.folder / "secrets.json").get(
            outgoing.secret_key("example.com", hook["id"])))
        conv(self.db, external_ref="after")
        self.assertEqual(self.run_at()["sent"], 0)

    def test_prune(self):
        self.add()
        conv(self.db)
        self.run_at()
        self.assertEqual(self.run_at(NOW + timedelta(days=91))["pruned"], 1)


class Refusals(unittest.TestCase):
    def test_urls_and_events(self):
        strict = {}
        for bad in ("http://example.com/x", "ftp://example.com", "https://", "nope",
                    "https://u:p@example.com/", "https://example.com/a b"):
            with self.assertRaises(outgoing.Refused, msg=bad):
                outgoing.check_url(bad, strict)
        self.assertEqual(outgoing.check_url(" https://example.com/h ", strict),
                         "https://example.com/h")
        with self.assertRaises(outgoing.Refused):
            outgoing.check_events(["lead.won", "conversion.exploded"])
        with self.assertRaises(outgoing.Refused):
            outgoing.check_events([])
        self.assertEqual(outgoing.check_events("lead.won,conversion.started"),
                         ["conversion.started", "lead.won"])

    def test_private_addresses(self):
        for address in ("127.0.0.1", "10.0.0.5", "169.254.169.254", "192.0.2.10", "::1"):
            answer = [(2, 1, 6, "", (address, 443))]
            with mock.patch("socket.getaddrinfo", return_value=answer):
                with self.assertRaises(outgoing.Refused, msg=address):
                    outgoing.public_address("hooks.example.com", 443, {})
        with mock.patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("8.8.8.8", 443))]):
            self.assertEqual(outgoing.public_address("hooks.example.com", 443, {}), "8.8.8.8")
        with mock.patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("10.0.0.5", 443))]):
            status, error = outgoing.post("https://hooks.example.com/x", b"{}", "s", {}, 0)
        self.assertEqual(status, 0)
        self.assertIn("private", error)


if __name__ == "__main__":
    unittest.main()
