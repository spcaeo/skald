"""An account made from an invite link shown to the admin (must_reset) in an
organisation that requires two-step sign-in: its first sign-in asks for the
new password first, then sets up two-step sign-in, and the answer that
signs it in carries the recovery codes. Before the fix the codes were made
by the setup step and then dropped by the "choose a new password" answer."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from auth_support import A, PW, SAME, Server  # noqa: E402

from skald import accounts, settings_store as store  # noqa: E402
from skald.accounts import totp  # noqa: E402

T = f"/traffic/{A}/"
NEW_PW = "quiet-harbour-lantern-47"


class ResetThenTwoStep(Server):
    def setUp(self):
        super().setUp()
        cookie, csrf = self.session("admin@example.com")
        link = self.post(T + "team/invite", {"email": "new@example.com", "role": "viewer"},
                         cookie, csrf).json["link"]
        got = self.call("POST", "/traffic-auth/invite",
                        {"token": link.split("t=", 1)[1], "name": "New", "password": PW}, SAME)
        self.assertFalse(got.json["signed_in"])
        db = self.db()
        try:
            store.put(db, f"org:{self.alpha['id']}", "security.require_totp", True, "cli")
        finally:
            db.close()

    def code(self, secret):
        return totp.code_at(secret, int(self._now.timestamp()))

    def test_the_codes_reach_the_page(self):
        first = self.login("new@example.com")
        self.assertEqual((first.status, first.json.get("must_change")), (200, True), first.json)
        weak = self.login("new@example.com", new_password="short")
        self.assertEqual((weak.status, weak.json.get("must_change")), (400, True))
        setup = self.login("new@example.com", new_password=NEW_PW)
        self.assertTrue(setup.json.get("needs_setup"), setup.json)
        self.assertIsNone(setup.cookie)
        # Nothing changed yet: the old password still signs in to this step.
        done = self.login("new@example.com", new_password=NEW_PW,
                          setup_code=self.code(setup.json["secret"]))
        self.assertEqual(done.status, 200, done.json)
        self.assertEqual(len(done.json.get("recovery_codes") or []), 10, done.json)
        self.assertIsNotNone(done.cookie)
        self.assertEqual(self.check(T, done.cookie).status, 200)
        db = self.db()
        try:
            user = accounts.users.find_user(db, email="new@example.com")
        finally:
            db.close()
        self.assertTrue(user["totp_on"])
        self.assertFalse(user["must_reset"])
        self.assertEqual(self.login("new@example.com", PW).status, 401)
        self.assertTrue(self.login("new@example.com", NEW_PW).json.get("needs_code"))

    def test_a_same_password_is_refused_before_two_step_starts(self):
        same = self.login("new@example.com", new_password=PW)
        self.assertEqual((same.status, same.json.get("must_change")), (400, True))
        self.assertNotIn("needs_setup", same.json)


if __name__ == "__main__":
    unittest.main()
