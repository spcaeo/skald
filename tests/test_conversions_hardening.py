"""The hook receiver's second security review: the signature is checked
before a rate-limit bucket is spent (an unsigned flood cannot starve a real
hook), failed signatures are one row a minute, the spool keeps only what
each tool's adapter and the audit read (allow-lists), and a Cal.com or
Typeform body (no timestamp) cannot be replayed to bring back a forgotten
conversion. Addresses are RFC 5737; hosts example.com."""
from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from conversions_support import SECRET, VID, FakeHandler  # noqa: E402

from skald.conversions import secrets_store, spool, store, strip  # noqa: E402
from skald.conversions.adapters import adapter  # noqa: E402
from skald.conversions.hooks import Receiver  # noqa: E402

T = 1791720000          # 2026-10-11 12:00 UTC
PROXY = "127.0.0.1"


def lead(ref: str = "L-1") -> dict:
    return {"external_ref": ref, "action": "demo", "vid": VID}


class Base(unittest.TestCase):
    hooks: dict = {}
    visitor_ids = False             # the default; with it off no ID is spooled (2.38.0)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)
        self.config = {"site": {"name": "example.com", "hosts": ["example.com"]},
                       "history": {"db": str(self.folder / "history.sqlite")},
                       "hooks": {"per_minute": 600, "burst": 100, **self.hooks},
                       # Anonymous on purpose: 2.4.0 keeps names and emails by default.
                       "conversions": {"identity": "anonymous"},
                       "beacon": {"visitor_ids": self.visitor_ids}}
        path = secrets_store.path_for(self.config, self.folder)
        for tool in ("lead", "calendly", "typeform", "calcom", "hubspot"):
            secrets_store.put(path, secrets_store.key("example.com", tool), SECRET)
        self.now = T
        self.rx = Receiver(self.config, self.folder, clock=lambda: self.now)

    def tearDown(self):
        self.tmp.cleanup()

    def post(self, tool: str, payload=None, secret: str = SECRET, peer: str = PROXY,
             real_ip: str | None = "192.0.2.10", raw: bytes | None = None):
        body = raw if raw is not None else json.dumps(payload).encode()
        path = f"/traffic-hooks/example.com/{tool}"
        headers = {"Host": "www.example.com", "X-Forwarded-Proto": "https",
                   **adapter(tool).sign(body, secret, self.now, "POST",
                                        "https://www.example.com" + path)}
        if real_ip:
            headers["X-Real-IP"] = real_ip
        handler = FakeHandler(path, body, headers)
        handler.client_address = (peer, 40000)
        return self.rx.http(handler)

    def rows(self, sql: str, args=()) -> list:
        db = sqlite3.connect(self.folder / "conversions.sqlite")
        try:
            return db.execute(sql, args).fetchall()
        finally:
            db.close()

    def spooled(self) -> list[str]:
        day = datetime.fromtimestamp(self.now, tz=timezone.utc).date()
        path = spool.day_file(self.folder / "hooks", day)
        return path.read_text().splitlines() if path.exists() else []


# ------------------------------------------------------------ finding 3

class SignatureBeforeBucket(Base):
    hooks = {"per_minute": 1, "burst": 2, "preauth_per_minute": 1, "preauth_burst": 5}

    def test_an_unsigned_flood_does_not_starve_a_signed_hook(self):
        for i in range(40):
            status, _ = self.post("lead", lead(f"X{i}"), secret="wrong",
                                  real_ip=f"192.0.2.{100 + i}")
            self.assertEqual(status, 401)
        status, answer = self.post("lead", lead())
        self.assertEqual(status, 200, answer)
        self.assertEqual(self.rows("SELECT COUNT(*) FROM conversions")[0][0], 1)

    def test_verified_requests_still_meet_the_per_hook_limit(self):
        codes = [self.post("lead", lead(f"R{i}"))[0] for i in range(4)]
        self.assertEqual(codes, [200, 200, 429, 429])

    def test_failed_signatures_from_one_address_meet_a_small_bucket(self):
        codes = [self.post("lead", lead(), secret="wrong")[0] for _ in range(8)]
        self.assertEqual(codes[:5], [401] * 5)
        self.assertEqual(set(codes[5:]), {429})
        # Another address is not held by the first one's bucket.
        self.assertEqual(self.post("lead", lead(), secret="wrong",
                                   real_ip="198.51.100.9")[0], 401)
        # A real hook from the same address as the flood still gets in.
        self.assertEqual(self.post("lead", lead())[0], 200)

    def test_x_real_ip_is_believed_only_from_the_proxy(self):
        # Not the proxy: X-Real-IP is ignored, so changing it does not
        # give a fresh bucket.
        codes = [self.post("lead", lead(), secret="wrong", peer="203.0.113.5",
                           real_ip=f"192.0.2.{i}")[0] for i in range(8)]
        self.assertEqual(set(codes[5:]), {429})

    def test_bad_signatures_are_one_row_a_minute(self):
        for i in range(20):
            self.post("lead", lead(), secret="wrong", real_ip=f"192.0.2.{i}")
        got = self.rows("SELECT outcome, http_status FROM deliveries")
        self.assertEqual(got, [("bad_signature", 401)])
        self.now = T + 61
        self.post("lead", lead(), secret="wrong", real_ip="192.0.2.99")
        got = self.rows("SELECT outcome, error FROM deliveries ORDER BY id")
        self.assertEqual(len(got), 2)
        self.assertEqual(got[1], ("bad_signature", "20 refused"))


# ------------------------------------------------------------ finding 6

REVIEW_BODY = {  # the review's proof (poc_strip.py): keys that survived
    "objectId": 1,
    "properties": {"email": {"value": "a@example.com"}, "mobilephone": {"value": "+1 555 0100"},
                   "hs_additional_emails": {"value": "b@example.com"}, "company": "Acme",
                   "ip_city": "Paris", "jobtitle": "CFO", "firstname": "Ann",
                   "skv": {"value": VID}, "utm_source": {"value": "linkedin"}},
    "payload": {"cancel_url": "https://calendly.com/cancellations/XYZ",
                "reschedule_url": "https://calendly.com/reschedulings/XYZ",
                "Email": "c@example.com", "work_email": "d@example.com",
                "uri": "https://api.calendly.com/x", "tracking": {"utm_content": VID}}}
NEVER = ("mobilephone", "hs_additional_emails", "ip_city", "jobtitle", "firstname",
         "cancel_url", "reschedule_url", "Email", "work_email", "company", "Acme", "CFO",
         "Ann", "Paris", "+1 555", "a@example.com", "b@example.com", "c@example.com",
         "d@example.com", "XYZ")


class AllowLists(unittest.TestCase):
    def test_the_reviews_surviving_keys_are_gone_for_every_tool(self):
        for tool in (None, "hubspot", "calendly", "calcom", "lead", "json", "stripe",
                     "typeform"):
            text = json.dumps(strip(REVIEW_BODY, False, tool))
            for word in NEVER:
                self.assertNotIn(word, text, f"{word} kept for {tool}")

    def test_what_the_adapters_read_is_kept(self):
        got = strip(REVIEW_BODY, False, "hubspot")
        self.assertEqual(got["objectId"], 1)
        self.assertEqual(got["properties"], {"skv": {"value": VID},
                                             "utm_source": {"value": "linkedin"}})
        cal = strip(REVIEW_BODY, False, "calendly")
        self.assertEqual(cal["payload"], {"uri": "https://api.calendly.com/x",
                                          "tracking": {"utm_content": VID}})

    def test_identity_full_keeps_only_name_and_the_primary_email(self):
        body = {"payload": {"name": "Ann", "email": "a@example.com", "Email": "c@example.com",
                            "work_email": "d@example.com", "phone": "+1 555 0100",
                            "ip": "192.0.2.1", "user_agent": "Mozilla",
                            "cancel_url": "https://calendly.com/cancellations/XYZ",
                            "uri": "u", "text_reminder_number": "+1 555 0101"}}
        got = strip(body, True, "calendly")
        self.assertEqual(got, {"payload": {"name": "Ann", "email": "a@example.com",
                                           "uri": "u"}})

    def test_every_tools_sample_still_reads_after_stripping(self):
        for tool in ("lead", "json", "calendly", "calcom", "stripe", "typeform", "hubspot"):
            mod = adapter(tool)
            body = mod.sample("example.com", T)
            before = [{k: r.get(k) for k in ("action", "stage", "external_ref", "at", "vid")}
                      for r in mod.to_records(body)]
            after = [{k: r.get(k) for k in ("action", "stage", "external_ref", "at", "vid")}
                     for r in mod.to_records(strip(body, False, tool))]
            self.assertEqual(before, after, tool)
            self.assertNotIn("test@example.com", json.dumps(strip(body, False, tool)))


class SpooledThroughTheReceiver(Base):
    visitor_ids = True              # so the ID is a field the spool must keep

    def test_a_hubspot_workflow_body_is_spooled_without_extra_fields(self):
        status, _ = self.post("hubspot", REVIEW_BODY)
        self.assertEqual(status, 200)
        text = "\n".join(self.spooled())
        self.assertIn(VID, text)
        for word in NEVER:
            self.assertNotIn(word, text)


# ----------------------------------------------------------- finding 12

def typeform_body(token: str = "tok-1") -> dict:
    return {"event_id": f"ev-{token}", "event_type": "form_response",
            "form_response": {"form_id": "F", "token": token,
                              "submitted_at": "2026-10-11T11:59:00Z",
                              "hidden": {"skv": VID}}}


def calcom_body(uid: str = "uid-1") -> dict:
    return {"triggerEvent": "BOOKING_CREATED", "createdAt": "2026-10-11T11:59:00Z",
            "payload": {"uid": uid, "metadata": {"skv": VID}}}


class NoReplayAfterForget(Base):
    def _forget(self, ref: str) -> None:
        db = store.connect(self.folder / "conversions.sqlite")
        try:
            store.forget(db, "example.com", external_ref=ref)
        finally:
            db.close()

    def _replay_refused(self, tool: str, body: dict, ref: str) -> None:
        self.assertEqual(self.post(tool, body)[1]["recorded"], 1)
        self._forget(ref)
        self.assertEqual(self.rows("SELECT COUNT(*) FROM conversions")[0][0], 0)
        lines = len(self.spooled())
        self.now = T + 3600
        status, answer = self.post(tool, body)
        self.assertEqual((status, answer["recorded"]), (200, 0))
        self.assertEqual(self.rows("SELECT COUNT(*) FROM conversions")[0][0], 0,
                         "a replay does not bring back a forgotten conversion")
        self.now = T
        self.assertEqual(len(self.spooled()), lines, "a replay is not spooled again")
        self.assertEqual(self.rows("SELECT outcome FROM deliveries ORDER BY id")[-1][0],
                         "replay")

    def test_typeform(self):
        self._replay_refused("typeform", typeform_body(), "tok-1")

    def test_calcom(self):
        self._replay_refused("calcom", calcom_body(), "uid-1")

    def test_a_new_body_is_still_kept(self):
        self.post("typeform", typeform_body("tok-1"))
        self.assertEqual(self.post("typeform", typeform_body("tok-2"))[1]["recorded"], 1)

    def test_only_a_hash_is_kept_and_it_goes_after_30_days(self):
        self.post("calcom", calcom_body("uid-secret-77"))
        dump = "\n".join(sqlite3.connect(self.folder / "conversions.sqlite").iterdump())
        replay = [line for line in dump.splitlines() if "hook_replays" in line]
        self.assertTrue(replay)
        self.assertFalse(any("uid-secret-77" in line for line in replay))
        db = store.connect(self.folder / "conversions.sqlite")
        try:
            store.prune(db, date(2026, 11, 9))
            self.assertEqual(db.execute("SELECT COUNT(*) FROM hook_replays").fetchone()[0], 1)
            store.prune(db, date(2026, 11, 12))
            self.assertEqual(db.execute("SELECT COUNT(*) FROM hook_replays").fetchone()[0], 0)
        finally:
            db.close()

    def test_a_failed_store_does_not_block_the_retry(self):
        from unittest import mock
        with mock.patch.object(store, "record_conversion", side_effect=RuntimeError("x")):
            self.assertEqual(self.post("typeform", typeform_body())[0], 500)
        self.assertEqual(self.post("typeform", typeform_body())[1]["recorded"], 1)


if __name__ == "__main__":
    unittest.main()
