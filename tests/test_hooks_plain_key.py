"""The plain key (2.30): `lead` and `json` take `Authorization: Bearer <secret>`
when no X-Skald-Signature is sent, for senders that cannot sign (Zapier's
Webhooks step, a form plugin's custom headers). A wrong key is refused as a
bad signature; no other tool takes it; the key is never logged or kept.
Hosts are example.com; the secrets are made up."""
from __future__ import annotations

import contextlib
import io
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from conversions_support import SECRET, FakeHandler  # noqa: E402
from test_conversions_hooks import Base, lead  # noqa: E402

from skald.conversions.adapters import lead as lead_mod  # noqa: E402

WRONG = "skh_wrong-key-made-up-for-the-test"


class PlainKey(Base):
    def keyed(self, tool: str, payload, key: str, extra: dict | None = None):
        body = json.dumps(payload).encode()
        headers = {"Host": "www.example.com", "Content-Type": "application/json",
                   "Authorization": f"Bearer {key}", **(extra or {})}
        return self.rx.http(FakeHandler(f"/traffic-hooks/example.com/{tool}", body, headers))

    def test_the_right_key_is_taken_for_lead_and_json(self):
        got = self.keyed("lead", lead(external_ref="K-1"), SECRET)
        self.assertEqual(got, (200, {"ok": True, "recorded": 1, "duplicates": 0}))
        got = self.keyed("json", {"records": [lead(external_ref="K-2")]}, SECRET)
        self.assertEqual(got[0], 200, got)
        self.assertEqual(self.rows("SELECT tool, external_ref FROM conversions ORDER BY id"),
                         [("lead", "K-1"), ("json", "K-2")])
        self.assertEqual(self.keyed("lead", lead(external_ref="K-1"), SECRET)[1]["duplicates"],
                         1, "a repeat is a duplicate, as signed")
        lower = {"Authorization": f"bearer  {SECRET} "}
        body = json.dumps(lead(external_ref="K-3")).encode()
        got = self.rx.http(FakeHandler("/traffic-hooks/example.com/lead", body, lower))
        self.assertEqual(got[0], 200, "the scheme in any case, spaces trimmed")

    def test_a_wrong_or_empty_key_is_a_bad_signature(self):
        self.assertEqual(self.keyed("lead", lead(), WRONG)[0], 401)
        self.now += 61                                  # past the once-a-minute row
        self.assertEqual(self.keyed("json", lead(), "")[0], 401)
        self.now += 61
        got = self.keyed("lead", lead(), SECRET, {"Authorization": f"Basic {SECRET}"})
        self.assertEqual(got[0], 401, "only Bearer")
        self.assertEqual(self.rows("SELECT tool, outcome, http_status FROM deliveries"),
                         [("lead", "bad_signature", 401), ("json", "bad_signature", 401),
                          ("lead", "bad_signature", 401)])
        self.assertEqual(self.rows("SELECT COUNT(*) FROM conversions"), [(0,)])
        self.assertEqual(self.spooled(), "", "nothing spooled before the key holds")

    def test_a_signature_is_always_read_as_one(self):
        """With X-Skald-Signature sent, the key is not looked at: a bad signature
        stays refused even beside the right key, and a good one needs no key."""
        got = self.post("lead", lead(external_ref="S-1"), secret="wrong",
                        extra={"Authorization": f"Bearer {SECRET}"})
        self.assertEqual(got[0], 401)
        got = self.post("lead", lead(external_ref="S-2"),
                        extra={"Authorization": f"Bearer {WRONG}"})
        self.assertEqual(got[0], 200, got)
        self.assertEqual(self.post("json", lead(external_ref="S-3"))[0], 200)

    def test_other_tools_never_take_the_key(self):
        for tool in ("calendly", "calcom", "stripe", "typeform", "hubspot"):
            self.now += 61
            with self.subTest(tool=tool):
                self.assertEqual(self.keyed(tool, {"event": "x"}, SECRET)[0], 401)
        outcomes = self.rows("SELECT DISTINCT outcome FROM deliveries")
        # 2.45: the plain key is no signature of theirs, so each is "unsigned".
        self.assertEqual(outcomes, [("unsigned",)])

    def test_the_leads_test_mark_stays_signed_only(self):
        body = json.dumps({"refs": ["K-1"], "test": True}).encode()
        got = self.rx.http(FakeHandler("/traffic-hooks/example.com/leads/test", body,
                                       {"Authorization": f"Bearer {SECRET}"}))
        self.assertEqual(got[0], 401)

    def test_the_key_is_never_logged_or_kept(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.keyed("lead", lead(external_ref="K-9"), SECRET)
            self.now += 61
            self.keyed("lead", lead(), WRONG)
        kept = json.dumps(self.rows("SELECT * FROM deliveries")) + \
            json.dumps(self.rows("SELECT * FROM conversions")) + self.spooled() + err.getvalue()
        for key in (SECRET, WRONG):
            self.assertNotIn(key, kept)
        self.assertNotIn("Bearer", kept)

    def test_verify_key_by_itself(self):
        self.assertTrue(lead_mod.verify_key({"authorization": f"Bearer {SECRET}"}, SECRET))
        self.assertFalse(lead_mod.verify_key({"authorization": f"Bearer {SECRET}"}, ""))
        self.assertFalse(lead_mod.verify_key({"authorization": "Bearer"}, SECRET))
        self.assertFalse(lead_mod.verify_key({"authorization": f"Bearer {SECRET}x"}, SECRET))
        self.assertFalse(lead_mod.verify_key({"authorization": "Bearer café"}, SECRET))
        self.assertFalse(lead_mod.keyed({"x-skald-signature": "t=1,v1=ab",
                                         "authorization": f"Bearer {SECRET}"}))


if __name__ == "__main__":
    unittest.main()
